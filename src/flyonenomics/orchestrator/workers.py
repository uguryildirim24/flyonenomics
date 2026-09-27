"""Spawn-only workers: one built network per process, sequential arm/seed jobs."""
from __future__ import annotations
import contextlib
import dataclasses
import multiprocessing as mp
import os
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
import numpy as np
if TYPE_CHECKING:
    from flyonenomics.engine.base import Engine
from flyonenomics.orchestrator.live import LiveStream, open_loop_block
from flyonenomics.orchestrator.phases import TopologyPlan, probe_inputs
from flyonenomics.orchestrator.seeds import BEHAVIOUR, ENCODER, LIVE, brian_seed, stream
from flyonenomics.orchestrator.slowstate import SECONDS_PER_HOUR
from flyonenomics.orchestrator.components import make_neuromod, make_behaviour
from flyonenomics.orchestrator.stubs import Cancelled
from flyonenomics.schema.experiment import Dose, Experiment, Probe, Wait, Washout
from flyonenomics.io import load_npy, read_json
from flyonenomics.store.results import ProbeRecorder, atomic_json, table_schemas, write_settle, write_table
from flyonenomics.types import ConnectomeFiles, Params, SettleRecord, is_rest_drive, load_params

MS_PER_SECOND = 1000
PROCESS_START_METHOD = "spawn"


@dataclass(frozen=True)
class SharedCompartment:
    """Worker copy of a compartment row. Units: none. Shapes: scalars."""

    name: str
    side: str
    id: int


@dataclass
class SharedPopulation:
    """Worker copy of one resolved population. Units: none. Shapes: (count,)."""

    name: str
    root_ids: np.ndarray
    idx: np.ndarray
    side: np.ndarray
    selector: str
    count: int
    inventory_range: tuple[int, int]


@dataclass
class SharedReceptorMap:
    """Worker copy of receptor densities. Units: none. Shapes: (n,) float32."""

    r1: np.ndarray
    r2: np.ndarray
    rq: np.ndarray
    version: str


@dataclass
class RegistrySnapshot:
    """Worker registry selections; int64 roots (n,), population int32 indices (m,)."""
    root_ids: np.ndarray
    selected: dict[str, Any]
    compartment_list: list[Any]
    provenance_record: dict[str, Any]
    exposure_matrix: Any = None
    innervation_matrix: Any = None
    receptor_map: Any = None

    @property
    def n(self) -> int:
        """Return neuron count; neurons, scalar."""
        return len(self.root_ids)

    def population(self, name: str) -> Any:
        """Return one resolved population; indices int32 (m,), roots int64 (m,)."""
        return self.selected[name]

    def compartments(self) -> list[Any]:
        """Return compartment names in registry order; units none, list (n_comp,)."""
        return self.compartment_list

    def exposure(self) -> Any:
        """Return W, dimensionless CSR matrix (n, n_comp)."""
        return self.exposure_matrix

    def innervation(self) -> Any:
        """Return M, dimensionless CSR matrix (n_comp, n)."""
        return self.innervation_matrix

    def exposed_mask(self) -> np.ndarray:
        """Return exposed neurons, boolean vector (n,)."""
        return np.asarray(self.exposure_matrix.getnnz(axis=1) > 0)

    def receptors(self) -> Any:
        """Return receptor density arrays, dimensionless (n,)."""
        return self.receptor_map


def registry_share_key(snapshot: RegistrySnapshot) -> str:
    """Hash every array and record the share writes; units none, hex string.

    The share directory is reused whenever it is `ready`, so its name must change
    whenever any written content would (population, compartment, receptor or
    annotation inputs, in this worktree or another one sharing the cache).
    """
    import json
    import hashlib
    import scipy.sparse as sparse

    digest = hashlib.sha256()

    def add(label: str, array: Any, dtype: Any) -> None:
        values = np.ascontiguousarray(np.asarray(array, dtype=dtype))
        digest.update(f"{label}|{values.dtype.str}|{values.shape}|".encode())
        digest.update(values.tobytes())

    add("root_ids", snapshot.root_ids, np.int64)
    for name in sorted(snapshot.selected):
        population = snapshot.selected[name]
        add(f"{name}.root_ids", population.root_ids, np.int64)
        add(f"{name}.idx", population.idx, np.int32)
        add(f"{name}.side", np.asarray(population.side, dtype="U"), np.asarray(population.side, dtype="U").dtype)
        digest.update(json.dumps([population.name, population.selector, int(population.count),
                                  [int(v) for v in population.inventory_range]]).encode())
    digest.update(json.dumps([[c.name, c.side, int(c.id)] for c in snapshot.compartment_list]).encode())
    digest.update(json.dumps(snapshot.provenance_record, sort_keys=True, default=str).encode())
    for label, matrix in (("exposure", snapshot.exposure_matrix), ("innervation", snapshot.innervation_matrix)):
        if matrix is None:
            digest.update(f"{label}|none".encode())
            continue
        csr = sparse.csr_matrix(matrix)
        add(f"{label}.data", csr.data, csr.data.dtype)
        add(f"{label}.indices", csr.indices, csr.indices.dtype)
        add(f"{label}.indptr", csr.indptr, csr.indptr.dtype)
        digest.update(repr(csr.shape).encode())
    receptors = snapshot.receptor_map
    if receptors is None:
        digest.update(b"receptors|none")
    else:
        for label in ("r1", "r2", "rq"):
            add(label, getattr(receptors, label), np.float32)
        digest.update(str(receptors.version).encode())
    return digest.hexdigest()


def save_registry_share(snapshot: RegistrySnapshot, directory: Path) -> Path:
    """Write registry arrays to a shared directory. Units: none. Shapes: per array.

    Workers memory-map the files instead of unpickling a private copy.
    """
    import fcntl
    import json
    import scipy.sparse as sparse
    from flyonenomics.registry.receptors import ReceptorMap

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    ready = directory / "ready"
    lock_path = directory / "lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if ready.is_file():
            return directory
        np.save(directory / "root_ids.npy", np.ascontiguousarray(snapshot.root_ids, dtype=np.int64))
        selected_meta: dict[str, Any] = {}
        selected_dir = directory / "selected"
        selected_dir.mkdir(exist_ok=True)
        for name, population in snapshot.selected.items():
            pop_dir = selected_dir / name
            pop_dir.mkdir(exist_ok=True)
            np.save(pop_dir / "root_ids.npy", np.ascontiguousarray(population.root_ids, dtype=np.int64))
            np.save(pop_dir / "idx.npy", np.ascontiguousarray(population.idx, dtype=np.int32))
            np.save(pop_dir / "side.npy", np.asarray(population.side, dtype="U"))
            selected_meta[name] = {
                "name": population.name,
                "selector": population.selector,
                "count": int(population.count),
                "inventory_range": [int(population.inventory_range[0]), int(population.inventory_range[1])],
            }
        (directory / "selected.json").write_text(json.dumps(selected_meta, sort_keys=True) + "\n")
        compartments = [{"name": c.name, "side": c.side, "id": int(c.id)} for c in snapshot.compartment_list]
        (directory / "compartments.json").write_text(json.dumps(compartments) + "\n")
        (directory / "provenance.json").write_text(json.dumps(snapshot.provenance_record) + "\n")
        if snapshot.exposure_matrix is not None:
            matrix = sparse.csr_matrix(snapshot.exposure_matrix)
            np.savez(directory / "exposure.npz", data=matrix.data, indices=matrix.indices,
                     indptr=matrix.indptr, shape=np.array(matrix.shape, dtype=np.int64))
        if snapshot.innervation_matrix is not None:
            matrix = sparse.csr_matrix(snapshot.innervation_matrix)
            np.savez(directory / "innervation.npz", data=matrix.data, indices=matrix.indices,
                     indptr=matrix.indptr, shape=np.array(matrix.shape, dtype=np.int64))
        receptors = snapshot.receptor_map
        if receptors is not None:
            if not isinstance(receptors, ReceptorMap):
                receptors = ReceptorMap(r1=np.asarray(receptors.r1), r2=np.asarray(receptors.r2),
                                        rq=np.asarray(receptors.rq), version=str(receptors.version))
            np.save(directory / "r1.npy", np.ascontiguousarray(receptors.r1, dtype=np.float32))
            np.save(directory / "r2.npy", np.ascontiguousarray(receptors.r2, dtype=np.float32))
            np.save(directory / "rq.npy", np.ascontiguousarray(receptors.rq, dtype=np.float32))
            (directory / "receptors.json").write_text(json.dumps({"version": receptors.version}) + "\n")
        ready.write_text("ok\n")
        return directory


def _load_csr(path: Path) -> Any:
    """Load one CSR matrix from npz. Units: per file. Shapes: stored shape."""
    import scipy.sparse as sparse

    with load_npy(path) as payload:
        return sparse.csr_matrix(
            (payload["data"], payload["indices"], payload["indptr"]),
            shape=tuple(int(n) for n in payload["shape"]),
        )


def load_registry_share(directory: str | Path) -> RegistrySnapshot:
    """Memory-map a spilled registry snapshot. Units: none. Shapes: per array."""
    import json

    directory = Path(directory)
    root_ids = load_npy(directory / "root_ids.npy", mmap_mode="r")
    selected_meta = read_json(directory / "selected.json")
    selected: dict[str, Any] = {}
    for name, meta in selected_meta.items():
        pop_dir = directory / "selected" / name
        selected[name] = SharedPopulation(
            name=meta["name"],
            root_ids=load_npy(pop_dir / "root_ids.npy", mmap_mode="r"),
            idx=load_npy(pop_dir / "idx.npy", mmap_mode="r"),
            side=load_npy(pop_dir / "side.npy", mmap_mode="r"),
            selector=meta["selector"],
            count=int(meta["count"]),
            inventory_range=(int(meta["inventory_range"][0]), int(meta["inventory_range"][1])),
        )
    compartments = [SharedCompartment(**row) for row in read_json(directory / "compartments.json")]
    provenance = read_json(directory / "provenance.json")
    exposure = _load_csr(directory / "exposure.npz") if (directory / "exposure.npz").is_file() else None
    innervation = _load_csr(directory / "innervation.npz") if (directory / "innervation.npz").is_file() else None
    receptors = None
    if (directory / "r1.npy").is_file():
        version = read_json(directory / "receptors.json")["version"]
        receptors = SharedReceptorMap(
            r1=load_npy(directory / "r1.npy", mmap_mode="r"),
            r2=load_npy(directory / "r2.npy", mmap_mode="r"),
            rq=load_npy(directory / "rq.npy", mmap_mode="r"),
            version=version,
        )
    return RegistrySnapshot(root_ids, selected, compartments, provenance, exposure, innervation, receptors)


@dataclass
class WorkerContext:
    """Serializable worker inputs; paths and topology, arrays in engine order."""
    experiment: Experiment
    registry: RegistrySnapshot | None
    plan: TopologyPlan
    run_dir: Path
    background: np.ndarray | None
    fixture_settle_s: dict[int, float] | None = None
    dopamine_table: dict[str, Any] | None = None
    weight_scale: np.ndarray | None = None
    g_inh: float = 1.0
    registry_share: str | None = None
    base_v_th: np.ndarray | None = None
    drive_groups: dict[str, np.ndarray] | None = None


def settle_rule(experiment: Experiment) -> str:
    """Section 2.4 applies to schema 1.3 with background on; every other file keeps Phase 1."""
    return "1.3" if experiment.schema_version == "1.3" and experiment.layers.background else "1.2"


def connectome_files(version: str) -> ConnectomeFiles:
    """Locate canonical inputs through the selected dataset adapter."""
    from flyonenomics.datasets import get_dataset_adapter

    return get_dataset_adapter(version).connectome_files()


def check_cancel(run_dir: Path) -> None:
    """Raise at a cooperative boundary if CANCEL exists; units none, one path."""
    if (run_dir / "CANCEL").exists():
        raise Cancelled("CANCEL requested")


def execute_job(context: WorkerContext, engine: Engine, params: Params, arm_index: int, seed: int, emit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Run one arm/seed with probe resets; seconds/ticks/Hz, arrays (n,)."""
    exp, reg, plan = context.experiment, context.registry, context.plan
    arm = exp.arms[arm_index]
    directory = context.run_dir / f"arm-{arm.label}" / f"seed-{seed}"
    directory.mkdir(parents=True, exist_ok=True)
    schemas = table_schemas(exp.record, [c.name for c in reg.compartments()])
    write_table(directory / "index.parquet", schemas["index"], {"idx": np.arange(reg.n, dtype=np.int32), "root_id": reg.root_ids})
    engine.restore("initial")
    rule = settle_rule(exp)
    mod = make_neuromod(
        reg, params, exp.arm_layers(arm), context.dopamine_table or {},
        base_v_th=context.base_v_th, schema_version=rule,
        drive_groups=context.drive_groups if rule == "1.3" else None,
    )
    mod.check_cancel = lambda: check_cancel(context.run_dir)
    mod.apply_genotype(arm.genotype.expanded(), engine)
    engine.store("genotype")
    metrics: dict[str, Any] = {"probes": {}, "slow_state": "phase1-drug-only"}
    if any(isinstance(p, Dose) and p.drug != "vehicle" for p in arm.expanded()):
        metrics["free_parameters"] = {"pk.kappa": params.get("pk.kappa")}
        metrics["drug_approximation"] = "concentrations held within each probe, advanced after settle plus recording"
    boundaries: list[dict[str, Any]] = []
    offsets: list[dict[str, Any]] = []
    cancelled = False
    for k, phase in enumerate(arm.expanded()):
        try:
            check_cancel(context.run_dir)
        except Cancelled:
            cancelled = True
            break
        emit({"event": "phase", "arm": arm.label, "seed": seed, "phase_index": k, "brain_time_s": mod.slow.t_brain_s})
        if isinstance(phase, Probe):
            arena = make_behaviour(plan, reg, params, phase)
            engine.restore("genotype")
            engine.seed(brian_seed(exp.seed, seed, k))
            active, rates, overlap = probe_inputs(plan, phase, arm, reg)
            for bank, enabled in enumerate(active):
                engine.set_upstream_active(bank, enabled)
            engine.compose_refractory()
            arena.reset(stream(exp.seed, seed, k, BEHAVIOUR))
            arena.encoder_stream = stream(exp.seed, seed, k, ENCODER)
            mod.reset_fast()
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            mod.overlap = overlap
            mod.fixture_settle_s = (context.fixture_settle_s or {}).get(k)

            def stimulus() -> None:
                """Write held-arena input; Hz, vector (n_extended,)."""
                engine.set_input_rates(rates + arena.rates(arena.view(), 0))

            visual_probe = None
            if isinstance(exp.meta, dict) and exp.meta.get("visual_path_protocol"):
                from flyonenomics.behaviour.visual_run import VisualProbe

                visual_probe = VisualProbe(exp.meta["visual_path_protocol"], reg, params, phase,
                                           context.drive_groups)
            settle_begin_tick = engine.tick()
            try:
                recorded = [reg.population(n) for n in exp.record.rates]
                settle = (visual_probe.settle(engine, mod, stimulus, recorded) if visual_probe
                          else mod.settle(engine, stimulus, recorded))
            except Cancelled:
                cancelled = True
                settle = SettleRecord(False, (engine.tick() - settle_begin_tick) * engine.dt_ms / MS_PER_SECOND,
                                      np.zeros(0), np.zeros(0), np.zeros(len(exp.record.rates)), engine.tick(),
                                      upstream_extended_overlap_idx=overlap)
            start_tick = engine.tick()
            write_settle(directory / f"probe-{k}-settle.json", settle)
            offsets.append({"arm": arm.label, "seed": seed, "probe": k, "t_brain_s": mod.slow.t_brain_s,
                            "record_t_brain_s": mod.slow.t_brain_s + settle.settle_s,
                            "settle_s": settle.settle_s, "record_start_tick": start_tick,
                            "arena_at_recording_start": arena.state(), "converged": settle.converged})
            # Section 2.4: the dopamine fixed-point gap uses the recording window.
            da_sum = np.zeros(len(mod.mask))
            dan_input = np.zeros(len(mod.mask))
            recorded_s = 0.0
            recorder = ProbeRecorder(directory, k, exp.record, reg, start_tick, engine.dt_ms)
            live = LiveStream(directory / "live" / f"probe-{k}.ndjson", stream(exp.seed, seed, k, LIVE), params,
                              {name: reg.population(name).idx for name in exp.record.rates}, start_tick, engine.dt_ms, exp.record.live)
            probe_ended = False
            try:
                remaining_ms = int(round(phase.duration_s * MS_PER_SECOND))
                while remaining_ms and not cancelled:
                    check_cancel(context.run_dir)
                    chunk_ms = min(params.get("engine.chunk_ms"), remaining_ms)
                    recording_time = (engine.tick() - start_tick) * engine.dt_ms / MS_PER_SECOND
                    engine.set_input_rates(rates + arena.rates(arena.view(), recording_time))
                    result = engine.run_chunk(chunk_ms)
                    if visual_probe is not None:
                        visual_probe.chunk(result, recording_time)
                    mod.on_chunk(result.counts, chunk_ms / MS_PER_SECOND)
                    if rule == "1.3":
                        da_sum += mod.da_c * (chunk_ms / MS_PER_SECOND)
                        dan_input += np.asarray(mod.m @ result.counts.astype(np.float64)).ravel()
                        recorded_s += chunk_ms / MS_PER_SECOND
                    composed = mod.compose()
                    engine.set_threshold(composed.v_th)
                    engine.set_gain(composed.gain)
                    arena.step(result.counts, chunk_ms / MS_PER_SECOND)
                    recorder.chunk(result, mod.state(), arena.state(), start_tick)
                    # WP23: pass the open-loop block through the maybe_emit call (SPEC-P2 section 7).
                    block_index, block_stimulus = open_loop_block(phase.params, recording_time, params)
                    live.maybe_emit(result.counts, result.tick1, engine.spikes, mod.state().da_c, arena.state(),
                                    block=block_index, stimulus=block_stimulus)
                    remaining_ms -= chunk_ms
                    check_cancel(context.run_dir)
                probe_ended = True
            except Cancelled:
                cancelled = probe_ended = True
            finally:
                # A failed probe writes no short final window, so close cannot mask its error.
                live.close(flush=probe_ended)
            if rule == "1.3":
                gap = (mod.da_gap(da_sum / recorded_s, dan_input / recorded_s).tolist()
                       if recorded_s > 0 else [])
                settle = dataclasses.replace(settle, da_gap_um=[float(v) for v in gap])
                write_settle(directory / f"probe-{k}-settle.json", settle)
                offsets[-1]["unresolved"] = list(settle.unresolved or [])
                offsets[-1]["da_gap_um"] = settle.da_gap_um
            probe_metrics = recorder.finalise(engine.spikes(start_tick), phase.assay)
            if visual_probe is not None and not cancelled:
                probe_metrics["visual_path"] = visual_probe.result(seed)
                offsets[-1]["settle_rule"] = "SPEC-P2 3.4: fixed 2 s ambient"
            if phase.assay == "buridan" and hasattr(arena, "metrics"):
                probe_metrics["behaviour"] = arena.metrics()
            metrics["probes"][str(k)] = {"label": phase.label, "assay": phase.assay, **probe_metrics}
            mod.advance_slow(settle.settle_s + probe_metrics["duration_s"])
            offsets[-1]["duration_s"] = probe_metrics["duration_s"]
        elif isinstance(phase, Dose):
            mod.start_dose(phase.drug, phase.c_food_mm)
        elif isinstance(phase, Washout):
            mod.stop_dose(phase.drug)
        elif isinstance(phase, Wait):
            mod.advance_slow(phase.hours * SECONDS_PER_HOUR)
        boundary = mod.slow.row(phase.label if isinstance(phase, Probe) else f"{k}:{phase.type}")
        release = mod.state().rel
        if len(release):
            boundary["rel"] = float(release[0])
        boundaries.append(boundary)
        write_table(directory / "slow-state.parquet", schemas["slow-state"], boundaries)
        atomic_json(directory / "metrics.json", metrics)
        emit({"event": "phase", "arm": arm.label, "seed": seed, "phase_index": k, "brain_time_s": mod.slow.t_brain_s})
        if cancelled:
            break
    write_table(directory / "slow-state.parquet", schemas["slow-state"], boundaries)
    atomic_json(directory / "metrics.json", metrics)
    return {"arm": arm.label, "seed": seed, "metrics": metrics, "offsets": offsets, "cancelled": cancelled}


def worker_main(context: WorkerContext, jobs: list[tuple[int, int]], queue: Any) -> None:
    """Build once and execute assigned jobs; seconds of wall time, no parent engine."""
    from flyonenomics.engine.brian_engine import BrianEngine
    if context.registry is None and context.registry_share:
        context.registry = load_registry_share(context.registry_share)
    with (context.run_dir / "log.txt").open("a", buffering=1) as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            check_cancel(context.run_dir)
            from flyonenomics.types import params_path_for_version

            pins = context.experiment.substrate
            params = load_params(params_path_for_version(pins.params_version)) if pins.params_version else load_params()
            engine = BrianEngine()
            first_arm, first_seed = jobs[0]
            engine.seed(brian_seed(context.experiment.seed, first_seed, 0))
            start = time.monotonic()
            pins = context.experiment.substrate
            rest_background = is_rest_drive(pins.drive_version) and context.experiment.layers.background
            # Section 8.1 exception: scales only, on a background-off declared fixture.
            scales_only = (is_rest_drive(pins.drive_version) and not context.experiment.layers.background
                           and bool(context.experiment.apply_scales_without_background))
            drive = None
            mechanisms = None
            drive_path = None
            if rest_background or scales_only:
                from flyonenomics.drive.mechanisms import mechanisms_from_drive
                from flyonenomics.drive.rest import load_drive_rest

                drive_path = Path(__file__).resolve().parents[3] / "data" / f"drive-{pins.drive_version}.yaml"
                if not drive_path.is_file():
                    raise FileNotFoundError(f"rest substrate requested: missing pin {drive_path.name}")
                drive = load_drive_rest(drive_path)
                mechanisms = mechanisms_from_drive(drive)
            connectome = connectome_files(context.experiment.substrate.connectome_version)
            import inspect

            if "mechanisms" in inspect.signature(engine.build).parameters:
                engine.build(connectome, params, context.plan.topology, mechanisms=mechanisms)
            else:
                engine.build(connectome, params, context.plan.topology)
            # SPEC 11.44: the ratio accompanies the background layer only.
            if context.experiment.layers.background and context.background is not None:
                engine.set_background(context.background)
            ratio = context.g_inh if context.experiment.layers.background else 1.0
            # The build already carries ratio 1 exactly. Rewriting identity
            # scales would round-trip volts through mV and perturb bare weights.
            if rest_background or scales_only:
                from flyonenomics.drive.rest import apply_rest_substrate

                base_v_th, _scale = apply_rest_substrate(
                    engine, params, drive, n=engine.n,
                    connectome_version=pins.connectome_version, thresholds=rest_background,
                )
                if rest_background:
                    context.base_v_th = base_v_th
            elif context.experiment.layers.background and context.weight_scale is not None:
                engine.set_weight_scale(context.weight_scale)
            elif ratio > 1:
                from flyonenomics.drive.background import _connection_signs, weight_scale
                connectivity = connectome_files(context.experiment.substrate.connectome_version).connectivity
                engine.set_weight_scale(weight_scale(_connection_signs(connectivity), ratio))
            print(f"pinned drive g_inh={ratio:g}, background={'on' if context.experiment.layers.background else 'off'}", flush=True)
            # build() creates a base snapshot; replace it with the complete
            # run-wide state before any arm/seed can restore it.
            engine.store("initial")
            built_at = time.monotonic()
            from flyonenomics.drive.mechanisms import resolved_block

            model = "lif"
            if hasattr(engine, "engine_model") and callable(engine.engine_model):
                model = engine.engine_model()
            queue.put({
                "event": "built", "build_s": built_at - start,
                "pid": os.getpid(), "built_at": built_at,
                "engine_model": model,
                "mechanisms": resolved_block(drive["mechanisms"]) if drive is not None else None,
            })
            for arm_index, seed in jobs:
                check_cancel(context.run_dir)
                result = execute_job(context, engine, params, arm_index, seed, queue.put)
                queue.put({"event": "result", **result})
                if result["cancelled"]:
                    break
        except Cancelled:
            queue.put({"event": "cancelled"})
        except BaseException:
            queue.put({"event": "error", "traceback": traceback.format_exc()})
        finally:
            # SPEC-P2 5.1: a worker writes deps-<pid>.json when a log directory is set.
            from flyonenomics.io import flush

            flush()
            queue.put({"event": "finished"})


def spawn_context() -> Any:
    """Return the required spawn multiprocessing context; units none, scalar context."""
    return mp.get_context(PROCESS_START_METHOD)
