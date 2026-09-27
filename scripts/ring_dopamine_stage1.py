"""Stage 1 of the ring-neuron dopamine experiment.

``census`` answers, from the committed connectome and data files and with no
engine run, how dopamine reaches the ellipsoid body: which dopamine neurons
carry a nonzero ``EB`` column, which named population holds them, what
receptor complement the 228 traced ``ER`` ring neurons carry, and what
concentration the ``EB`` compartment reaches under the item-129 kinetics.
``plan`` fixes the trace set and the paired probe protocol. ``run`` executes
the paired 400-brain-second probe (TuBu injected on in both arms, dopamine
neurons dark versus driven) on the box. ``summarize`` reduces the raw runs
into the compact committed record. Every voltage, spike and concentration
value is a model measurement, never a pass line.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import time
from types import SimpleNamespace
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MASTER = 20260912
SEEDS = tuple(range(1, 11))
SETTLE_S = 2.0
PROBE_S = 20.0
TUBU_MAX_HZ = 70.0
SIGMA_DEG = 20.0
STRIPE_AZ_DEG = 45.0
DA_DRIVE_HZ = 50.0
SOURCE_POPULATION = "TuBu"
DOPAMINE_POPULATION = "CX_DAN"
DEFAULT_FIXTURE = Path("data/experiments/p2/ring-dopamine-stage1.json")
DEFAULT_PLAN = Path("camber-runs/ring-dopamine/plan.json")
DEFAULT_RAW = Path("camber-runs/ring-dopamine/raw")
DEFAULT_RECORD = Path("validation/records/p2/ring-dopamine-stage1.json")
SOURCE_COMMIT_ENV = "RING_DOPAMINE_SOURCE_COMMIT"
DECLARED_SUBSTRATE_ID = "rest:379cc4cc9030cdd1"
REACHED_RECORD = Path("validation/records/p2/tubu-reached-subset.json")
CONDITIONS = ("dark", "driven")


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def read(path: Path) -> dict[str, Any]:
    from flyonenomics.io import read_json

    return read_json(path)


def digest(array: np.ndarray, dtype: Any | None = None) -> str:
    value = np.asarray(array, dtype=dtype) if dtype is not None else np.asarray(array)
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def identity(platform_name: str) -> dict[str, Any]:
    from flyonenomics.connectome_arrays import connectome_source_paths
    from flyonenomics.io import hash_file

    source_commit = os.environ.get(SOURCE_COMMIT_ENV)
    if not source_commit:
        raise ValueError(f"{SOURCE_COMMIT_ENV} must bind the executed source commit")
    completeness, connectivity = connectome_source_paths("783")
    data_names = (
        "params-v0.2.yaml", "drive-v0.2.yaml", "dopamine-v0.2.yaml",
        "populations-v0.2.yaml", "transmitters-v0.2.yaml",
        "receptors-v0.1.yaml", "compartments-v0.1.yaml",
    )
    return {
        "platform": platform_name,
        "engine": "lif",
        "source_commit": source_commit,
        "source_sha256": {
            str(path.relative_to(ROOT)): hash_file(path)
            for path in sorted((ROOT / "src").rglob("*.py"))
        },
        "runner_sha256": hash_file(Path(__file__)),
        "inputs_sha256": {name: hash_file(ROOT / "data" / name) for name in data_names},
        "connectome_sha256": {
            completeness.name: hash_file(completeness),
            connectivity.name: hash_file(connectivity),
        },
    }


def eb_innervation() -> dict[str, Any]:
    """Census of the dopamine neurons with a nonzero EB column, with labels."""
    from flyonenomics.registry import build_registry
    from flyonenomics.registry.compartments import compartment_index

    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    matrix = registry.innervation().tocsr()
    names = registry.populations()
    member: dict[int, list[str]] = {}
    for name in names:
        for index in np.asarray(registry.population(name).idx):
            member.setdefault(int(index), []).append(name)
    compartment = compartment_index()["EB"]
    row = matrix.getrow(compartment).toarray().ravel()
    nonzero = np.flatnonzero(row > 0)
    ranked = nonzero[np.argsort(-row[nonzero])]
    neurons = []
    for index in ranked:
        populations = sorted(p for p in member.get(int(index), []) if p not in ("DA_exposed",))
        neurons.append({
            "engine_index": int(index),
            "root_id": int(registry.root_ids[index]),
            "eb_weight": float(row[index]),
            "populations": populations,
        })
    population_weight: dict[str, float] = {}
    population_count: dict[str, int] = {}
    for index in nonzero:
        for name in member.get(int(index), []):
            population_weight[name] = population_weight.get(name, 0.0) + float(row[index])
            population_count[name] = population_count.get(name, 0) + 1
    cxdan = np.asarray(registry.population("CX_DAN").idx, dtype=np.int32)
    cxdan_eb = np.intersect1d(cxdan, nonzero)
    dan = np.asarray(registry.population("DAN").idx, dtype=np.int32)
    return {
        "eb_compartment_index": int(compartment),
        "eb_weight_sum": float(np.sum(row.astype(np.float64))),
        "neurons": neurons,
        "population_weight": {name: float(value) for name, value in sorted(population_weight.items())},
        "population_count": {name: int(value) for name, value in sorted(population_count.items())},
        "cx_dan": {
            "n": int(len(cxdan)),
            "with_nonzero_eb": int(len(cxdan_eb)),
            "fraction_with_eb": float(len(cxdan_eb) / len(cxdan)),
            "eb_weight_sum": float(np.sum(row[cxdan_eb].astype(np.float64))),
        },
        "dan": {
            "n": int(len(dan)),
            "with_nonzero_eb": int(len(np.intersect1d(dan, nonzero))),
        },
    }


def ring_receptors(record_path: Path) -> dict[str, Any]:
    """Receptor complement and exposure of the traced ER cells, with d_v terms."""
    from flyonenomics.neuromod.receptors import receptor_effect
    from flyonenomics.registry import build_registry
    from flyonenomics.registry.compartments import compartment_index
    from flyonenomics.types import load_params

    reached = read(record_path)
    er_cells = [cell for cell in reached["cells"] if "ring_ER" in cell["classes"]]
    er_idx = np.asarray([cell["engine_index"] for cell in er_cells], dtype=np.int32)
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    exposure = registry.exposure().tocsr()
    receptors = registry.receptors()
    params = load_params(ROOT / "data/params-v0.2.yaml")
    rows = exposure[er_idx].toarray()
    eb = compartment_index()["EB"]
    nonzero_columns = np.flatnonzero(rows.any(axis=0))
    if nonzero_columns.tolist() != [eb]:
        raise ValueError("traced ER cells are exposed from a compartment other than EB")
    weights = np.unique(rows[:, eb])
    if weights.tolist() != [1.0]:
        raise ValueError("traced ER cells do not all read EB with weight 1.0")

    def dv(da_eb: float) -> float:
        da_c = np.full(len(registry.compartments()), params.get("da.DA_ref"))
        da_c[eb] = da_eb
        d_v, _, _, _ = receptor_effect(da_c, exposure, registry.exposed_mask(),
                                       np.asarray(receptors.r1), np.asarray(receptors.r2), params)
        return float(d_v[er_idx][0])

    r1 = np.unique(np.asarray(receptors.r1)[er_idx])
    r2 = np.unique(np.asarray(receptors.r2)[er_idx])
    rq = np.unique(np.asarray(receptors.rq)[er_idx])
    return {
        "n": int(len(er_idx)),
        "engine_index_sha256": digest(er_idx, np.int32),
        "exposure_compartment": "EB",
        "exposure_weight": 1.0,
        "r1": [float(value) for value in r1],
        "r2": [float(value) for value in r2],
        "rq": [float(value) for value in rq],
        "baseline_da_um": float(params.get("da.DA_ref")),
        "dv_baseline_mv": dv(float(params.get("da.DA_ref"))),
        "constants": {
            key: float(params.get(f"da.{key}"))
            for key in ("DA_ref", "Vmax", "Km", "k_ns", "R_min", "alpha_max")
        },
        "receptor_constants": {
            key: float(params.get(f"rec.{key}"))
            for key in ("Kd_D1", "Kd_D2", "dV_D1", "dV_D2", "gamma_D1", "gamma_D2")
        },
    }


def reachability(census: dict[str, Any]) -> dict[str, Any]:
    """Closed-form EB concentration under the item-129 kinetics, plus a 20 s Euler approach."""
    from flyonenomics.io import read_yaml

    table = read_yaml(ROOT / "data/dopamine-v0.2.yaml")
    compartments = table["compartments"]
    eb = compartments.index("EB")
    alpha = float(table["alpha_c"][eb])
    source = float(table["S_c"][eb])
    constants = {key: float(value) for key, value in table["constants"].items()}
    vmax = constants["Vmax"]
    km = constants["Km"]
    k_ns = constants["k_ns"]

    def fixed_point(q: float) -> float:
        b = vmax + k_ns * km - q
        if b >= 0:
            return 2.0 * q * km / (b + float(np.sqrt(b * b + 4.0 * k_ns * q * km)))
        return (float(np.sqrt(b * b + 4.0 * k_ns * q * km)) - b) / (2.0 * k_ns)

    def euler(q: float, seconds: float, start: float, dt_s: float = 0.001) -> float:
        value = start
        for _ in range(int(round(seconds / dt_s))):
            value += dt_s * (q - (vmax * value / (km + value) + k_ns * value))
        return value

    eb_weight_sum = census["cx_dan"]["eb_weight_sum"]
    scenarios = {}
    for label, rate_hz, weight in (
        ("all_cx_dan_at_drive", DA_DRIVE_HZ, eb_weight_sum),
        ("four_dominant_at_drive", DA_DRIVE_HZ,
         float(sum(n["eb_weight"] for n in census["neurons"][:4]))),
        ("single_largest_at_drive", DA_DRIVE_HZ,
         float(census["neurons"][0]["eb_weight"])),
    ):
        r_prime = rate_hz * weight
        q = alpha * r_prime + source
        scenarios[label] = {
            "drive_hz_per_neuron": float(rate_hz),
            "weighted_rate_hz": float(r_prime),
            "q_um_per_s": float(q),
            "fixed_point_um": float(fixed_point(q)),
            "euler_20s_from_baseline_um": float(euler(q, PROBE_S, float(table["constants"]["DA_ref"]))),
        }
    return {
        "alpha_um_per_spike": alpha,
        "s_um_per_s": source,
        "q_um_per_s": source,
        "source_mode": str(table["mode"][eb]),
        "scenarios": scenarios,
        "euler_note": "1 ms explicit Euler of the same pool balance used by Neuromod.on_chunk, 20 s from the 0.02 uM baseline",
    }


def build_census(destination: Path) -> None:
    """Write the Part A record; the probe key stays null until summarize."""
    started = time.monotonic()
    census = {
        "eb_innervation": eb_innervation(),
        "ring_receptors": ring_receptors(ROOT / REACHED_RECORD),
    }
    census["reachability"] = reachability(census["eb_innervation"])
    record = {
        "class": "development",
        "purpose": "ring-neuron dopamine stage 1: EB reach census and paired dark/driven probe",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "census": census,
        "probe": None,
        "wall_seconds": time.monotonic() - started,
    }
    dump(destination, record)
    print(json.dumps({
        "eb_weight_sum": census["eb_innervation"]["eb_weight_sum"],
        "eb_neurons": len(census["eb_innervation"]["neurons"]),
        "cx_dan_with_eb": census["eb_innervation"]["cx_dan"]["with_nonzero_eb"],
        "ring_dv_baseline_mv": census["ring_receptors"]["dv_baseline_mv"],
        "all_cx_dan_fixed_point_um": census["reachability"]["scenarios"]["all_cx_dan_at_drive"]["fixed_point_um"],
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def build_plan(destination: Path) -> None:
    """Fix the trace set (228 ER) and the paired probe protocol."""
    from flyonenomics.registry import build_registry
    from flyonenomics.registry.compartments import compartment_index

    reached = read(ROOT / REACHED_RECORD)
    er_cells = [cell for cell in reached["cells"] if "ring_ER" in cell["classes"]]
    trace_indices = sorted(int(cell["engine_index"]) for cell in er_cells)
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    compartment = compartment_index()
    fixture = read(ROOT / DEFAULT_FIXTURE)
    activation = None
    for arm in fixture["arms"]:
        for hook in arm["genotype"]["manipulations"]:
            if hook["type"] == "activate":
                activation = hook
    if activation is None or activation["population"] != DOPAMINE_POPULATION:
        raise ValueError("fixture must activate the dopamine population")
    output = {
        "class": "development",
        "purpose": "ring-neuron dopamine stage 1 paired probe plan",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "protocol": {
            "master_seed": MASTER,
            "seeds": list(SEEDS),
            "conditions": list(CONDITIONS),
            "settle_s": SETTLE_S,
            "probe_s": PROBE_S,
            "brain_seconds": PROBE_S * 2 * len(SEEDS),
            "inject_at": SOURCE_POPULATION,
            "dopamine_population": DOPAMINE_POPULATION,
            "dopamine_drive_hz": float(activation["rate_hz"]),
            "stripe_azimuth_deg": STRIPE_AZ_DEG,
            "stripe_width_deg": 5.0,
            "TuBu_max_hz": TUBU_MAX_HZ,
            "TuBu_sigma_deg": SIGMA_DEG,
            "eb_compartment_index": int(compartment["EB"]),
            "source_event_definition": (
                "sum over TuBu-to-target recurrent event amplitudes in the measurement window, "
                "after substrate weight scaling and live postsynaptic gain"
            ),
        },
        "fixture": str(DEFAULT_FIXTURE),
        "trace_indices": trace_indices,
        "trace_n": len(trace_indices),
        "cells": [{"engine_index": int(cell["engine_index"]), "root_id": int(cell["root_id"]),
                   "hemibrain_type": cell["hemibrain_type"], "side": cell["side"]} for cell in er_cells],
    }
    dump(destination, output)
    print(f"wrote {destination} ({len(trace_indices)} traced ER cells)", flush=True)


def probe(label: str) -> Any:
    from flyonenomics.schema.experiment import Probe

    return Probe.model_validate({
        "type": "probe",
        "assay": "open_loop_steering",
        "duration_s": PROBE_S,
        "label": label,
        "params": {
            "inject_at": SOURCE_POPULATION,
            "blocks": [{
                "stimulus": "stripe",
                "azimuth_deg": STRIPE_AZ_DEG,
                "transition_s": SETTLE_S,
                "dwell_s": PROBE_S - SETTLE_S,
            }],
        },
    })


def run_seed(job: tuple[int, str, str]) -> str:
    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import apply_rest_substrate, load_drive_rest, rest_background_weights
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.io import read_yaml
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.registry import build_registry
    from flyonenomics.types import LayerFlags, load_params

    seed, plan_path, destination = job
    destination_path = Path(destination)
    plan = read(Path(plan_path))
    probe_s = float(plan["protocol"]["probe_s"])
    settle_s = float(plan["protocol"]["settle_s"])
    drive_hz = float(plan["protocol"]["dopamine_drive_hz"])
    eb_index = int(plan["protocol"]["eb_compartment_index"])
    started = time.monotonic()
    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    groups = group_indices(registry)
    drive = load_drive_rest(ROOT / "data/drive-v0.2.yaml")
    dopamine = read_yaml(ROOT / "data/dopamine-v0.2.yaml")
    source = np.asarray(registry.population(SOURCE_POPULATION).idx, dtype=np.int32)
    dopamine_neurons = np.asarray(registry.population(DOPAMINE_POPULATION).idx, dtype=np.int32)
    targets = np.asarray(plan["trace_indices"], dtype=np.int32)
    if not len(targets) or len(np.unique(targets)) != len(targets):
        raise ValueError("plan supplied an invalid trace target set")
    extended = np.union1d(np.sort(source), np.sort(dopamine_neurons)).astype(np.int32)
    dopamine_positions = np.searchsorted(extended, dopamine_neurons)
    topology = InputTopology(background=True, extended_idx=extended, trace_idx=targets)
    engine = BrianEngine()
    engine.seed(MASTER)
    engine.build(connectome_files("783"), params, topology, mechanisms=None)
    base_threshold, scale = apply_rest_substrate(engine, params, drive)
    background = rest_background_weights(registry, drive, params)
    engine.set_background(background)
    engine.store("declared")

    completeness, connectivity = connectome_source_paths("783")
    roots, pre, post, raw = load_connectome_arrays(completeness, connectivity)
    effective = np.asarray(raw, dtype=np.float64) * float(params.get("lif.w_syn")) * scale
    incoming = np.isin(pre, source) & np.isin(post, targets)
    incoming_pre = np.asarray(pre[incoming], dtype=np.int32)
    incoming_post = np.asarray(post[incoming], dtype=np.int32)
    incoming_weight = effective[incoming]
    target_position = np.full(registry.n, -1, dtype=np.int32)
    target_position[targets] = np.arange(len(targets), dtype=np.int32)
    incoming_target_position = target_position[incoming_post]
    if np.any(incoming_target_position < 0):
        raise ValueError("source edge into a cell outside the trace set")

    rows = []
    chunk_ms = float(params.get("engine.chunk_ms"))
    settle_chunks = int(round(settle_s * 1000.0 / chunk_ms))
    total_chunks = int(round(probe_s * 1000.0 / chunk_ms))
    n_comp = len(registry.compartments())
    for condition in CONDITIONS:
        engine.restore("declared")
        engine.seed(brian_seed(MASTER, seed, 0))
        mod = Neuromod(
            registry, params,
            LayerFlags(background=True, dopamine_A=True, transporter_C=True),
            dopamine, base_v_th=base_threshold, schema_version="1.3", drive_groups=groups,
        )
        mod.reset_fast()
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        engine.compose_refractory()
        arena = Behaviour(
            SimpleNamespace(topology=topology), registry, params, probe(condition),
            v_fwd=0.0, sign_steer=1, K_steer=0.0, r_vis_max=TUBU_MAX_HZ, sigma_vis=SIGMA_DEG,
        )
        arena.reset(np.random.default_rng(seed))
        count = np.zeros(registry.n, dtype=np.int64)
        source_events = np.zeros(len(targets), dtype=np.float64)
        threshold_sum = np.zeros(len(targets), dtype=np.float64)
        threshold_min = np.full(len(targets), np.inf)
        threshold_max = np.full(len(targets), -np.inf)
        da_sum = np.zeros(n_comp, dtype=np.float64)
        da_min = np.full(n_comp, np.inf)
        da_max = np.full(n_comp, -np.inf)
        measurement_chunks = 0
        measure_tick = None
        input_min = np.inf
        input_max = -np.inf
        for step in range(total_chunks):
            rate = arena.rates(arena.view(), step * chunk_ms / 1000.0)
            if condition == "driven":
                rate[dopamine_positions] += drive_hz
            input_min = min(input_min, float(rate.min(initial=0.0)))
            input_max = max(input_max, float(rate.max(initial=0.0)))
            engine.set_input_rates(rate)
            if step == settle_chunks:
                measure_tick = engine.tick()
            gain_before = np.asarray(composed.gain[targets], dtype=np.float64)
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_ms / 1000.0)
            if step >= settle_chunks:
                count += result.counts
                amplitudes = result.counts[incoming_pre] * incoming_weight * gain_before[incoming_target_position]
                source_events += np.bincount(
                    incoming_target_position, weights=amplitudes, minlength=len(targets),
                )
                threshold = np.asarray(composed.v_th[targets], dtype=np.float64)
                threshold_sum += threshold
                np.minimum(threshold_min, threshold, out=threshold_min)
                np.maximum(threshold_max, threshold, out=threshold_max)
                da_sum += mod.da_c
                np.minimum(da_min, mod.da_c, out=da_min)
                np.maximum(da_max, mod.da_c, out=da_max)
                measurement_chunks += 1
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
        if measure_tick is None:
            raise RuntimeError("measurement tick was not set")
        traces = engine.traces(measure_tick)
        if not np.array_equal(traces.idx, targets) or traces.v_mv.shape[1] == 0:
            raise ValueError("trace target order or measurement window is wrong")
        target_rows = []
        for position, target in enumerate(targets):
            values = traces.v_mv[position]
            threshold_mean = float(threshold_sum[position] / measurement_chunks)
            target_rows.append({
                "engine_index": int(target),
                "root_id": int(roots[target]),
                "spike_count": int(count[target]),
                "spike_rate_hz": float(count[target] / (probe_s - settle_s)),
                "source_event_amplitude_mV": float(source_events[position]),
                "sampled_mean_v_mV": float(values.mean()),
                "sampled_min_v_mV": float(values.min()),
                "sampled_max_v_mV": float(values.max()),
                "threshold_mean_mV": threshold_mean,
                "threshold_min_mV": float(threshold_min[position]),
                "threshold_max_mV": float(threshold_max[position]),
                "mean_distance_to_threshold_mV": float(threshold_mean - values.mean()),
                "nearest_sampled_distance_to_threshold_mV": float(threshold_min[position] - values.max()),
            })
        rows.append({
            "condition": condition,
            "source_population": SOURCE_POPULATION,
            "source_n": int(len(source)),
            "source_spikes": int(count[source].sum()),
            "source_rate_hz": float(count[source].sum() / (len(source) * (probe_s - settle_s))),
            "dopamine_population": DOPAMINE_POPULATION,
            "dopamine_n": int(len(dopamine_neurons)),
            "dopamine_spikes": int(count[dopamine_neurons].sum()),
            "dopamine_rate_hz": float(count[dopamine_neurons].sum() / (len(dopamine_neurons) * (probe_s - settle_s))),
            "input_rate_min_hz": float(input_min),
            "input_rate_max_hz": float(input_max),
            "targets": target_rows,
            "eb_da_mean_um": float(da_sum[eb_index] / measurement_chunks),
            "eb_da_min_um": float(da_min[eb_index]),
            "eb_da_max_um": float(da_max[eb_index]),
            "da_mean_um": (da_sum / measurement_chunks).tolist(),
            "da_min_um": da_min.tolist(),
            "da_max_um": da_max.tolist(),
            "compartments": [compartment.name for compartment in registry.compartments()],
            "trace_samples": int(traces.v_mv.shape[1]),
        })
        print("seed", seed, condition, "complete", flush=True)
    dump(destination_path / f"seed-{seed}.json", {
        "identity": {
            **plan["identity"],
            "platform": f"{platform.system().lower()}-{platform.machine()}",
            "scale_sha256": digest(scale, np.float32),
            "background_sha256": digest(background),
        },
        "seed": seed,
        "brian_seed": brian_seed(MASTER, seed, 0),
        "settle_s": settle_s,
        "probe_s": probe_s,
        "brain_seconds": probe_s * 2,
        "rows": rows,
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    })
    return f"seed-{seed}.json"


def run_dynamic(plan_path: Path, destination: Path, workers: int, seeds: tuple[int, ...]) -> None:
    plan = read(plan_path)
    plan["identity"] = identity(f"{platform.system().lower()}-{platform.machine()}")
    dump(plan_path, plan)
    destination.mkdir(parents=True, exist_ok=True)
    jobs = [(seed, str(plan_path.resolve()), str(destination.resolve())) for seed in seeds]
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
        max_tasks_per_child=1,
    ) as pool:
        print(list(pool.map(run_seed, jobs)), flush=True)


def _field(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [float(row[key]) for row in rows]
    return {
        "mean": float(np.mean(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "values": values,
    }


def _distribution(values: list[float]) -> dict[str, Any]:
    """Summary of one value per cell; the interval is not a seed-level interval."""
    array = np.asarray(values, dtype=np.float64)
    return {
        "n": int(array.size),
        "min": float(array.min()),
        "median": float(np.median(array)),
        "max": float(array.max()),
        "mean": float(array.mean()),
        "sd": float(array.std(ddof=1)) if array.size > 1 else 0.0,
    }


def _paired_interval(values: list[float]) -> dict[str, Any]:
    """Mean paired difference and a 95 percent t-style interval over seeds."""
    array = np.asarray(values, dtype=np.float64)
    n = len(array)
    mean = float(array.mean())
    if n < 2:
        return {"mean": mean, "sd": 0.0, "se": 0.0, "lower": mean, "upper": mean,
                "includes_zero": True, "n": n}
    sd = float(array.std(ddof=1))
    se = sd / float(np.sqrt(n))
    half = 1.96 * se
    return {
        "mean": mean, "sd": sd, "se": se,
        "lower": mean - half, "upper": mean + half,
        "includes_zero": bool(mean - half <= 0.0 <= mean + half),
        "n": n,
    }


def summarize(raw: Path, plan_path: Path, destination: Path, seeds: tuple[int, ...]) -> None:
    from flyonenomics.io import hash_file

    plan = read(plan_path)
    record = read(destination)
    runs = [read(raw / f"seed-{seed}.json") for seed in seeds]
    probe_s = float(plan["protocol"]["probe_s"])
    if sum(float(run["brain_seconds"]) for run in runs) != probe_s * 2 * len(seeds):
        raise ValueError("paired probe brain-second total differs from the plan")
    identities = [run["identity"] for run in runs]
    if any(value != identities[0] for value in identities[1:]):
        raise ValueError("seed execution identities differ")
    cells = plan["cells"]
    paired_runs = []
    for run in runs:
        dark, driven = run["rows"]
        if [dark["condition"], driven["condition"]] != ["dark", "driven"]:
            raise ValueError("condition order differs from dark/driven")
        dark_targets = {int(row["engine_index"]): row for row in dark["targets"]}
        driven_targets = {int(row["engine_index"]): row for row in driven["targets"]}
        seed_rows = []
        for cell in cells:
            index = int(cell["engine_index"])
            a, b = dark_targets[index], driven_targets[index]
            seed_rows.append({
                "engine_index": index,
                "spike_dark": a["spike_count"],
                "spike_driven": b["spike_count"],
                "spike_delta": b["spike_count"] - a["spike_count"],
                "source_event_dark_mV": a["source_event_amplitude_mV"],
                "source_event_driven_mV": b["source_event_amplitude_mV"],
                "source_event_delta_mV": b["source_event_amplitude_mV"] - a["source_event_amplitude_mV"],
                "mean_v_dark_mV": a["sampled_mean_v_mV"],
                "mean_v_driven_mV": b["sampled_mean_v_mV"],
                "mean_v_delta_mV": b["sampled_mean_v_mV"] - a["sampled_mean_v_mV"],
                "max_v_dark_mV": a["sampled_max_v_mV"],
                "max_v_driven_mV": b["sampled_max_v_mV"],
                "max_v_delta_mV": b["sampled_max_v_mV"] - a["sampled_max_v_mV"],
                "threshold_dark_mV": a["threshold_mean_mV"],
                "threshold_driven_mV": b["threshold_mean_mV"],
                "threshold_delta_mV": b["threshold_mean_mV"] - a["threshold_mean_mV"],
                "mean_distance_dark_mV": a["mean_distance_to_threshold_mV"],
                "mean_distance_driven_mV": b["mean_distance_to_threshold_mV"],
                "mean_distance_delta_mV": b["mean_distance_to_threshold_mV"] - a["mean_distance_to_threshold_mV"],
                "nearest_distance_driven_mV": b["nearest_sampled_distance_to_threshold_mV"],
            })
        paired_runs.append({
            "seed": run["seed"],
            "source_rate_dark_hz": dark["source_rate_hz"],
            "source_rate_driven_hz": driven["source_rate_hz"],
            "source_rate_delta_hz": driven["source_rate_hz"] - dark["source_rate_hz"],
            "source_spikes_dark": dark["source_spikes"],
            "source_spikes_driven": driven["source_spikes"],
            "dopamine_rate_dark_hz": dark["dopamine_rate_hz"],
            "dopamine_rate_driven_hz": driven["dopamine_rate_hz"],
            "dopamine_spikes_dark": dark["dopamine_spikes"],
            "dopamine_spikes_driven": driven["dopamine_spikes"],
            "eb_da_dark_um": dark["eb_da_mean_um"],
            "eb_da_driven_um": driven["eb_da_mean_um"],
            "eb_da_delta_um": driven["eb_da_mean_um"] - dark["eb_da_mean_um"],
            "eb_da_driven_max_um": driven["eb_da_max_um"],
            "eb_da_dark_max_um": dark["eb_da_max_um"],
            "targets": seed_rows,
        })

    per_cell = []
    for cell in cells:
        index = int(cell["engine_index"])
        rows = [next(row for row in pair["targets"] if row["engine_index"] == index) for pair in paired_runs]
        per_cell.append({
            **cell,
            "spike_dark_values": [int(row["spike_dark"]) for row in rows],
            "spike_driven_values": [int(row["spike_driven"]) for row in rows],
            "spike_delta_values": [int(row["spike_delta"]) for row in rows],
            "spike_delta": _field(rows, "spike_delta"),
            "mean_spike_dark": float(np.mean([row["spike_dark"] for row in rows])),
            "mean_spike_driven": float(np.mean([row["spike_driven"] for row in rows])),
            "mean_v_dark_mV": _field(rows, "mean_v_dark_mV"),
            "mean_v_driven_mV": _field(rows, "mean_v_driven_mV"),
            "mean_v_delta_mV": _field(rows, "mean_v_delta_mV"),
            "max_v_dark_mV": _field(rows, "max_v_dark_mV"),
            "max_v_driven_mV": _field(rows, "max_v_driven_mV"),
            "max_v_delta_mV": _field(rows, "max_v_delta_mV"),
            "threshold_dark_mV": _field(rows, "threshold_dark_mV"),
            "threshold_driven_mV": _field(rows, "threshold_driven_mV"),
            "threshold_delta_mV": _field(rows, "threshold_delta_mV"),
            "mean_distance_dark_mV": _field(rows, "mean_distance_dark_mV"),
            "mean_distance_driven_mV": _field(rows, "mean_distance_driven_mV"),
            "mean_distance_delta_mV": _field(rows, "mean_distance_delta_mV"),
            "source_event_dark_mV": _field(rows, "source_event_dark_mV"),
            "source_event_driven_mV": _field(rows, "source_event_driven_mV"),
            "source_event_delta_mV": _field(rows, "source_event_delta_mV"),
            "seeds_spike_delta_positive": int(sum(row["spike_delta"] > 0 for row in rows)),
            "seeds_spike_delta_negative": int(sum(row["spike_delta"] < 0 for row in rows)),
            "seeds_spike_delta_zero": int(sum(row["spike_delta"] == 0 for row in rows)),
            "seeds_mean_v_delta_positive": int(sum(row["mean_v_delta_mV"] > 0 for row in rows)),
            "fires_dark_any_seed": bool(any(int(row["spike_dark"]) > 0 for row in rows)),
            "fires_driven_any_seed": bool(any(int(row["spike_driven"]) > 0 for row in rows)),
        })

    def seed_total(pair: dict[str, Any], key: str) -> int:
        return int(sum(int(row[key]) for row in pair["targets"]))

    def seed_responders(pair: dict[str, Any], key: str) -> int:
        return int(sum(int(row[key]) > 0 for row in pair["targets"]))

    def seed_mean(pair: dict[str, Any], key: str) -> float:
        return float(np.mean([float(row[key]) for row in pair["targets"]]))

    spike_deltas = [float(row["spike_delta"]["mean"]) for row in per_cell]
    mean_v_deltas = [float(row["mean_v_delta_mV"]["mean"]) for row in per_cell]
    max_v_deltas = [float(row["max_v_delta_mV"]["mean"]) for row in per_cell]
    threshold_deltas = [float(row["threshold_delta_mV"]["mean"]) for row in per_cell]
    eb_deltas = [float(pair["eb_da_delta_um"]) for pair in paired_runs]
    source_rate_deltas = [float(pair["source_rate_delta_hz"]) for pair in paired_runs]
    er_spike_dark = [seed_total(pair, "spike_dark") for pair in paired_runs]
    er_spike_driven = [seed_total(pair, "spike_driven") for pair in paired_runs]
    responders_dark = [seed_responders(pair, "spike_dark") for pair in paired_runs]
    responders_driven = [seed_responders(pair, "spike_driven") for pair in paired_runs]
    threshold_seed_dark = [seed_mean(pair, "threshold_dark_mV") for pair in paired_runs]
    threshold_seed_driven = [seed_mean(pair, "threshold_driven_mV") for pair in paired_runs]
    mean_v_seed_dark = [seed_mean(pair, "mean_v_dark_mV") for pair in paired_runs]
    mean_v_seed_driven = [seed_mean(pair, "mean_v_driven_mV") for pair in paired_runs]
    max_v_seed_delta = [seed_mean(pair, "max_v_delta_mV") for pair in paired_runs]
    source_event_seed_delta = [seed_mean(pair, "source_event_delta_mV") for pair in paired_runs]
    output = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 1: per-cell measurement of the ER response to injected TuBu "
            "input with the dopamine field dark versus driven; a null here is a real null"
        ),
        "declared_substrate_id": plan["declared_substrate_id"],
        "protocol": plan["protocol"],
        "identity": identities[0],
        "plan_sha256": hash_file(plan_path),
        "fixture": plan["fixture"],
        "fixture_sha256": hash_file(ROOT / plan["fixture"]),
        "trace_n": plan["trace_n"],
        "summary": {
            "n_cells": len(per_cell),
            "fires_dark_any_seed": int(sum(row["fires_dark_any_seed"] for row in per_cell)),
            "fires_driven_any_seed": int(sum(row["fires_driven_any_seed"] for row in per_cell)),
            "spike_dark_total": int(sum(sum(row["spike_dark_values"]) for row in per_cell)),
            "spike_driven_total": int(sum(sum(row["spike_driven_values"]) for row in per_cell)),
            "responders_dark": int(sum(any(value > 0 for value in row["spike_dark_values"]) for row in per_cell)),
            "responders_driven": int(sum(any(value > 0 for value in row["spike_driven_values"]) for row in per_cell)),
            "spike_delta_distribution": _distribution(spike_deltas),
        },
        "paired": {
            "unit": "paired difference is driven minus dark over the ten seeds; the interval is mean +/- 1.96 SE",
            "eb_da_delta_um": _paired_interval(eb_deltas),
            "eb_da_dark_um": [float(pair["eb_da_dark_um"]) for pair in paired_runs],
            "eb_da_driven_um": [float(pair["eb_da_driven_um"]) for pair in paired_runs],
            "source_rate_delta_hz": _paired_interval(source_rate_deltas),
            "seed_er_spikes_dark": er_spike_dark,
            "seed_er_spikes_driven": er_spike_driven,
            "seed_er_spikes_delta": _paired_interval(
                [d - k for d, k in zip(er_spike_driven, er_spike_dark, strict=True)]),
            "seed_responders_dark": responders_dark,
            "seed_responders_driven": responders_driven,
            "seed_responders_delta": _paired_interval(
                [d - k for d, k in zip(responders_driven, responders_dark, strict=True)]),
            "seed_threshold_dark_mV": threshold_seed_dark,
            "seed_threshold_driven_mV": threshold_seed_driven,
            "seed_threshold_delta_mV": _paired_interval(
                [d - k for d, k in zip(threshold_seed_driven, threshold_seed_dark, strict=True)]),
            "seed_mean_v_dark_mV": mean_v_seed_dark,
            "seed_mean_v_driven_mV": mean_v_seed_driven,
            "seed_mean_v_delta_mV": _paired_interval(
                [d - k for d, k in zip(mean_v_seed_driven, mean_v_seed_dark, strict=True)]),
            "seed_max_v_delta_mV": _paired_interval(max_v_seed_delta),
            "seed_source_event_delta_mV": _paired_interval(source_event_seed_delta),
            "cell_distribution_spike_delta": _distribution(spike_deltas),
            "cell_distribution_mean_v_delta_mV": _distribution(mean_v_deltas),
            "cell_distribution_max_v_delta_mV": _distribution(max_v_deltas),
            "cell_distribution_threshold_delta_mV": _distribution(threshold_deltas),
        },
        "paired_runs": paired_runs,
        "cells": per_cell,
        "raw_directory": str(raw),
        "raw_sha256": {f"seed-{seed}.json": hash_file(raw / f"seed-{seed}.json") for seed in seeds},
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    record["probe"] = output
    record["generated_utc"] = datetime.now(timezone.utc).isoformat()
    dump(destination, record)
    print(f"wrote {destination}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    census_parser = sub.add_parser("census")
    census_parser.add_argument("--out", type=Path, default=DEFAULT_RECORD)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--out", type=Path, default=DEFAULT_PLAN)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    run_parser.add_argument("--out", type=Path, default=DEFAULT_RAW)
    run_parser.add_argument("--workers", type=int, choices=range(1, 17), default=8)
    run_parser.add_argument("--seeds", default="1-10")
    run_parser.add_argument("--identity-only", action="store_true")
    summary_parser = sub.add_parser("summarize")
    summary_parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    summary_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    summary_parser.add_argument("--out", type=Path, default=DEFAULT_RECORD)
    summary_parser.add_argument("--seeds", default="1-10")
    args = parser.parse_args()

    def parse_seeds(text: str) -> tuple[int, ...]:
        if "-" in text:
            lo, hi = text.split("-")
            return tuple(range(int(lo), int(hi) + 1))
        return tuple(int(value) for value in text.split(","))

    if args.command == "census":
        build_census(args.out)
        return
    if args.command == "plan":
        build_plan(args.out)
        return
    if args.command == "run":
        seeds = parse_seeds(args.seeds)
        plan = read(args.plan)
        plan["identity"] = identity(f"{platform.system().lower()}-{platform.machine()}")
        dump(args.plan, plan)
        if args.identity_only:
            print(json.dumps(plan["identity"], indent=2), flush=True)
            return
        run_dynamic(args.plan, args.out, args.workers, seeds)
        return
    summarize(args.raw, args.plan, args.out, parse_seeds(args.seeds))


if __name__ == "__main__":
    main()
