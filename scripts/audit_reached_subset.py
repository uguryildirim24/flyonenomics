"""Measure the cells TuBu actually reaches, one cell at a time.

``plan`` builds the per-cell census (directly reached visual-projection and
LAL cells, matched unreached controls, positive two-hop intermediates and
endpoints, and the ring-neuron and bulb cells TuBu supplies) and fixes the
run-wide trace set. ``run`` executes the paired 400-brain-second TuBu
off/on probe per seed. ``summarize`` reduces the raw runs into the compact
committed record. Every voltage and event value is a model measurement, not
a pass line.

The engine's declared trace cap is raised in ``brian_engine.TRACE_MAX`` so
one build can carry the whole census; the simulated dynamics do not depend
on which cells are traced.
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

import audit_signal_transfer as transfer

ROOT = Path(__file__).resolve().parents[1]
MASTER = 20260912
SEEDS = tuple(range(1, 11))
SETTLE_S = 2.0
PROBE_S = 20.0
MAX_HZ = 70.0
SIGMA_DEG = 20.0
STRIPE_AZ_DEG = 45.0
PI = 3.141592653589793
SOURCE_POPULATION = "TuBu"
ENDPOINT_POPULATIONS = ("DNa02_L", "DNa02_R", "steering_L", "steering_R")
CONTROL_POPULATIONS = ("visual_projection", "LAL_neurons")
DEFAULT_PLAN = Path("camber-runs/diag/reached-subset/plan.json")
DEFAULT_RAW = Path("camber-runs/diag/reached-subset")
DEFAULT_RECORD = Path("validation/records/p2/tubu-reached-subset.json")
SOURCE_COMMIT_ENV = "REACHED_SOURCE_COMMIT"
DECLARED_SUBSTRATE_ID = "rest:379cc4cc9030cdd1"


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


def counts(values: np.ndarray) -> dict[str, int]:
    labels, ns = np.unique(np.asarray(values, dtype=str), return_counts=True)
    return {str(label): int(n) for label, n in zip(labels, ns, strict=True)}


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


def cell_metadata() -> tuple[Any, Any, Any]:
    from flyonenomics.substrate.transmitters import annotations_in_engine

    return annotations_in_engine()


def clean(value: Any) -> str | None:
    return None if value != value else str(value)


def control_match(reached: np.ndarray, population_idx: np.ndarray,
                  cell_type: np.ndarray, side: np.ndarray) -> list[int]:
    """Pair every reached cell with an unreached cell of the same type and side.

    Deterministic: candidates are ordered by engine index and never reused.
    Falls back to any unreached cell of the same type, then to any unreached
    cell of the population, when a type/side group is exhausted.
    """
    reached_set = set(int(value) for value in reached)
    unreached = [int(value) for value in population_idx if int(value) not in reached_set]
    by_type_side: dict[tuple[str, str], list[int]] = {}
    by_type: dict[str, list[int]] = {}
    for value in sorted(unreached):
        by_type_side.setdefault((cell_type[value], side[value]), []).append(value)
        by_type.setdefault(cell_type[value], []).append(value)
    used: set[int] = set()
    matched: list[int] = []
    for target in sorted(reached_set):
        typed = [value for value in by_type_side.get((cell_type[target], side[target]), []) if value not in used]
        if not typed:
            typed = [value for value in by_type.get(cell_type[target], []) if value not in used]
        if not typed:
            typed = [value for value in sorted(unreached) if value not in used]
        if not typed:
            raise ValueError(f"no unreached control remains for engine index {target}")
        chosen = typed[0]
        used.add(chosen)
        matched.append(chosen)
    return matched


def build_plan(destination: Path) -> None:
    from flyonenomics.substrate.transmitters import annotations_in_engine

    started = time.monotonic()
    registry, params, drive, roots, pre, post, raw, effective = transfer.substrate_arrays()
    frame, annotation_roots = annotations_in_engine()
    if not np.array_equal(annotation_roots, roots):
        raise ValueError("annotation and connectome engine orders differ")
    cell_type = frame["cell_type"].fillna("<missing>").astype(str).to_numpy()
    hemibrain = frame["hemibrain_type"].fillna("<missing>").astype(str).to_numpy()
    super_class = frame["super_class"].fillna("<missing>").astype(str).to_numpy()
    side = frame["side"].fillna("<missing>").astype(str).to_numpy()

    source = np.asarray(registry.population(SOURCE_POPULATION).idx, dtype=np.int32)
    source_mask = np.isin(pre, source)
    source_rows = np.flatnonzero(source_mask)
    immediate = np.unique(post[source_mask]).astype(np.int32)
    immediate_set = set(int(value) for value in immediate)

    def anatomy(target: int) -> dict[str, Any]:
        rows = source_rows[post[source_rows] == target]
        signs = effective[rows]
        return {
            "source_pairs": int(len(rows)),
            "source_synapses": float(np.abs(raw[rows]).sum()),
            "source_weight_sum_mV": float(signs.sum()),
            "source_positive_pairs": int((signs > 0).sum()),
            "source_negative_pairs": int((signs < 0).sum()),
        }

    population_of: dict[str, np.ndarray] = {
        name: np.asarray(registry.population(name).idx, dtype=np.int32)
        for name in ("visual_projection", "LAL_neurons", "ER") + ENDPOINT_POPULATIONS
    }
    reached_vp = np.intersect1d(immediate, population_of["visual_projection"])
    reached_lal = np.intersect1d(immediate, population_of["LAL_neurons"])

    control_groups: dict[str, list[int]] = {}
    for name in CONTROL_POPULATIONS:
        population = population_of[name]
        reached = reached_vp if name == "visual_projection" else reached_lal
        control_groups[name] = control_match(reached, population, cell_type, side)
    controls = [value for group in control_groups.values() for value in group]

    # Positive two-hop intermediates into each endpoint population.
    pos = np.flatnonzero(effective > 0)
    pos_pre = np.asarray(pre[pos], dtype=np.int32)
    pos_post = np.asarray(post[pos], dtype=np.int32)
    incoming: dict[int, list[int]] = {}
    for a, b in zip(pos_pre.tolist(), pos_post.tolist(), strict=True):
        incoming.setdefault(b, []).append(a)
    endpoints: dict[str, list[int]] = {}
    intermediates: dict[str, list[int]] = {}
    for name in ENDPOINT_POPULATIONS:
        cells = [int(value) for value in population_of[name]]
        endpoints[name] = cells
        found: set[int] = set()
        for target in cells:
            for predecessor in incoming.get(target, []):
                if predecessor in immediate_set and predecessor != target:
                    found.add(predecessor)
        intermediates[name] = sorted(found)
    intermediate_union = sorted(set().union(*intermediates.values()))
    endpoint_union = sorted(set().union(*endpoints.values()))

    ring_er = sorted(int(value) for value in np.intersect1d(immediate, population_of["ER"]))
    ring_er_set = set(ring_er)
    ring_exr2 = sorted(int(value) for value in immediate if "ExR2" in cell_type[value])
    bulb = sorted(int(value) for value in immediate
                  if "AOTU" in hemibrain[value] or "AOTU" in cell_type[value])

    classes: dict[int, list[str]] = {}
    for value in reached_vp:
        classes.setdefault(int(value), []).append("reached_visual_projection")
    for value in reached_lal:
        classes.setdefault(int(value), []).append("reached_LAL")
    for name, group in control_groups.items():
        for value in group:
            classes.setdefault(int(value), []).append(f"control_{name}")
    for value in intermediate_union:
        classes.setdefault(int(value), []).append("second_hop_intermediate")
    for value in endpoint_union:
        classes.setdefault(int(value), []).append("endpoint")
    for value in ring_er:
        classes.setdefault(int(value), []).append("ring_ER")
    for value in ring_exr2:
        classes.setdefault(int(value), []).append("ring_ExR2")
    for value in bulb:
        classes.setdefault(int(value), []).append("bulb_AOTU")

    trace_indices = sorted(classes)
    memberships = {
        "visual_projection": set(int(v) for v in population_of["visual_projection"]),
        "LAL_neurons": set(int(v) for v in population_of["LAL_neurons"]),
        "ER": ring_er_set,
    }
    for name in ENDPOINT_POPULATIONS:
        memberships[name] = set(int(v) for v in population_of[name])

    cells = []
    for index in trace_indices:
        cells.append({
            "engine_index": int(index),
            "root_id": int(roots[index]),
            "cell_type": clean(cell_type[index]),
            "hemibrain_type": clean(hemibrain[index]),
            "super_class": clean(super_class[index]),
            "side": clean(side[index]),
            "classes": sorted(classes[index]),
            "in_populations": sorted(name for name, values in memberships.items() if index in values),
            "anatomy": anatomy(index),
        })

    output = {
        "class": "development",
        "purpose": "per-cell TuBu reach census and 400-brain-second paired probe plan",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "protocol": {
            "master_seed": MASTER,
            "seeds": list(SEEDS),
            "conditions": ["off", "on"],
            "settle_s": SETTLE_S,
            "probe_s": PROBE_S,
            "brain_seconds": PROBE_S * 2 * len(SEEDS),
            "inject_at": SOURCE_POPULATION,
            "stripe_azimuth_deg": STRIPE_AZ_DEG,
            "stripe_width_deg": float(params.get("arena.stripe_width")),
            "TuBu_max_hz": MAX_HZ,
            "TuBu_sigma_deg": SIGMA_DEG,
            "source_event_definition": (
                "sum over TuBu-to-target recurrent event amplitudes in the measurement window, "
                "after substrate weight scaling and live postsynaptic gain"
            ),
        },
        "source": {
            "population": SOURCE_POPULATION,
            "n": int(len(source)),
            "root_ids_sha256": digest(registry.population(SOURCE_POPULATION).root_ids, np.int64),
        },
        "summary": {
            "immediate_targets_n": int(len(immediate)),
            "reached_visual_projection_n": int(len(reached_vp)),
            "reached_LAL_n": int(len(reached_lal)),
            "controls_n": int(len(controls)),
            "second_hop_intermediates_n": int(len(intermediate_union)),
            "endpoint_cells_n": int(len(endpoint_union)),
            "ring_ER_n": int(len(ring_er)),
            "ring_ExR2_n": int(len(ring_exr2)),
            "bulb_AOTU_n": int(len(bulb)),
            "trace_cells_n": int(len(trace_indices)),
            "trace_class_counts": counts(np.concatenate([np.asarray(v) for v in classes.values()])),
        },
        "two_hop": {
            name: {
                "endpoints": endpoints[name],
                "positive_intermediates": intermediates[name],
            }
            for name in ENDPOINT_POPULATIONS
        },
        "trace_indices": [int(value) for value in trace_indices],
        "cells": cells,
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination, output)
    print(json.dumps(output["summary"], indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def probe(condition: str, probe_s: float, settle_s: float) -> Any:
    from flyonenomics.schema.experiment import Probe

    stimulus = "stripe" if condition == "on" else "ambient"
    return Probe.model_validate({
        "type": "probe",
        "assay": "open_loop_steering",
        "duration_s": probe_s,
        "label": f"TuBu-{condition}",
        "params": {
            "inject_at": SOURCE_POPULATION,
            "blocks": [{
                "stimulus": stimulus,
                "azimuth_deg": STRIPE_AZ_DEG if stimulus == "stripe" else None,
                "transition_s": settle_s,
                "dwell_s": probe_s - settle_s,
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
    started = time.monotonic()
    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    groups = group_indices(registry)
    drive = load_drive_rest(ROOT / "data/drive-v0.2.yaml")
    dopamine = read_yaml(ROOT / "data/dopamine-v0.2.yaml")
    source = np.asarray(registry.population(SOURCE_POPULATION).idx, dtype=np.int32)
    targets = np.asarray(plan["trace_indices"], dtype=np.int32)
    if not len(targets) or len(np.unique(targets)) != len(targets):
        raise ValueError("plan supplied an invalid trace target set")
    topology = InputTopology(background=True, extended_idx=np.sort(source), trace_idx=targets)
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
    for condition in ("off", "on"):
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
            SimpleNamespace(topology=topology), registry, params, probe(condition, probe_s, settle_s),
            v_fwd=0.0, sign_steer=1, K_steer=0.0, r_vis_max=MAX_HZ, sigma_vis=SIGMA_DEG,
        )
        arena.reset(np.random.default_rng(seed))
        count = np.zeros(registry.n, dtype=np.int64)
        source_events = np.zeros(len(targets), dtype=np.float64)
        threshold_sum = np.zeros(len(targets), dtype=np.float64)
        threshold_min = np.full(len(targets), np.inf)
        threshold_max = np.full(len(targets), -np.inf)
        measurement_chunks = 0
        measure_tick = None
        input_min = np.inf
        input_max = -np.inf
        for step in range(total_chunks):
            rate = arena.rates(arena.view(), step * chunk_ms / 1000.0)
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
            "input_rate_min_hz": float(input_min),
            "input_rate_max_hz": float(input_max),
            "targets": target_rows,
            "trace_samples": int(traces.v_mv.shape[1]),
            "da_min_uM": float(mod.da_c.min()),
            "da_max_uM": float(mod.da_c.max()),
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


def summarize(raw: Path, plan_path: Path, destination: Path, seeds: tuple[int, ...]) -> None:
    from flyonenomics.io import hash_file

    plan = read(plan_path)
    runs = [read(raw / f"seed-{seed}.json") for seed in seeds]
    probe_s = float(plan["protocol"]["probe_s"])
    if sum(float(run["brain_seconds"]) for run in runs) != probe_s * 2 * len(seeds):
        raise ValueError("dynamic probe brain-second total differs from the plan")
    identities = [run["identity"] for run in runs]
    if any(value != identities[0] for value in identities[1:]):
        raise ValueError("seed execution identities differ")
    cells = plan["cells"]
    by_index = {int(cell["engine_index"]): cell for cell in cells}
    paired_runs = []
    for run in runs:
        off, on = run["rows"]
        if [off["condition"], on["condition"]] != ["off", "on"]:
            raise ValueError("condition order differs from off/on")
        off_targets = {int(row["engine_index"]): row for row in off["targets"]}
        on_targets = {int(row["engine_index"]): row for row in on["targets"]}
        seed_rows = []
        for cell in cells:
            index = int(cell["engine_index"])
            a, b = off_targets[index], on_targets[index]
            seed_rows.append({
                "engine_index": index,
                "spike_off": a["spike_count"],
                "spike_on": b["spike_count"],
                "spike_delta": b["spike_count"] - a["spike_count"],
                "source_event_off_mV": a["source_event_amplitude_mV"],
                "source_event_on_mV": b["source_event_amplitude_mV"],
                "source_event_delta_mV": b["source_event_amplitude_mV"] - a["source_event_amplitude_mV"],
                "mean_v_off_mV": a["sampled_mean_v_mV"],
                "mean_v_on_mV": b["sampled_mean_v_mV"],
                "mean_v_delta_mV": b["sampled_mean_v_mV"] - a["sampled_mean_v_mV"],
                "max_v_off_mV": a["sampled_max_v_mV"],
                "max_v_on_mV": b["sampled_max_v_mV"],
                "max_v_delta_mV": b["sampled_max_v_mV"] - a["sampled_max_v_mV"],
                "mean_distance_off_mV": a["mean_distance_to_threshold_mV"],
                "mean_distance_on_mV": b["mean_distance_to_threshold_mV"],
                "mean_distance_delta_mV": b["mean_distance_to_threshold_mV"] - a["mean_distance_to_threshold_mV"],
                "nearest_distance_on_mV": b["nearest_sampled_distance_to_threshold_mV"],
            })
        paired_runs.append({
            "seed": run["seed"],
            "source_rate_off_hz": off["source_rate_hz"],
            "source_rate_on_hz": on["source_rate_hz"],
            "source_rate_delta_hz": on["source_rate_hz"] - off["source_rate_hz"],
            "source_spikes_off": off["source_spikes"],
            "source_spikes_on": on["source_spikes"],
            "targets": seed_rows,
        })

    per_cell = []
    for cell in cells:
        index = int(cell["engine_index"])
        rows = [next(row for row in pair["targets"] if row["engine_index"] == index) for pair in paired_runs]
        spike_deltas = [float(row["spike_delta"]) for row in rows]
        source_deltas = [float(row["source_event_delta_mV"]) for row in rows]
        mean_deltas = [float(row["mean_v_delta_mV"]) for row in rows]
        max_deltas = [float(row["max_v_delta_mV"]) for row in rows]
        per_cell.append({
            **cell,
            "spike_off_values": [int(row["spike_off"]) for row in rows],
            "spike_on_values": [int(row["spike_on"]) for row in rows],
            "spike_delta_values": [int(row["spike_delta"]) for row in rows],
            "spike_delta": _field(rows, "spike_delta"),
            "source_event_delta_mV": _field(rows, "source_event_delta_mV"),
            "source_event_off_mV": _field(rows, "source_event_off_mV"),
            "source_event_on_mV": _field(rows, "source_event_on_mV"),
            "mean_v_off_mV": _field(rows, "mean_v_off_mV"),
            "mean_v_on_mV": _field(rows, "mean_v_on_mV"),
            "mean_v_delta_mV": _field(rows, "mean_v_delta_mV"),
            "max_v_off_mV": _field(rows, "max_v_off_mV"),
            "max_v_on_mV": _field(rows, "max_v_on_mV"),
            "max_v_delta_mV": _field(rows, "max_v_delta_mV"),
            "mean_distance_off_mV": _field(rows, "mean_distance_off_mV"),
            "mean_distance_on_mV": _field(rows, "mean_distance_on_mV"),
            "mean_distance_delta_mV": _field(rows, "mean_distance_delta_mV"),
            "nearest_distance_on_mV": _field(rows, "nearest_distance_on_mV"),
            "spike_on_mean": float(np.mean([row["spike_on"] for row in rows])),
            "spike_off_mean": float(np.mean([row["spike_off"] for row in rows])),
            "seeds_spike_delta_positive": int(sum(value > 0 for value in spike_deltas)),
            "seeds_spike_delta_negative": int(sum(value < 0 for value in spike_deltas)),
            "seeds_spike_delta_zero": int(sum(value == 0 for value in spike_deltas)),
            "seeds_source_delta_positive": int(sum(value > 0 for value in source_deltas)),
            "seeds_mean_v_delta_positive": int(sum(value > 0 for value in mean_deltas)),
            "seeds_max_v_delta_positive": int(sum(value > 0 for value in max_deltas)),
            "fires_off_any_seed": bool(any(int(row["spike_off"]) > 0 for row in rows)),
            "fires_on_any_seed": bool(any(int(row["spike_on"]) > 0 for row in rows)),
            "mean_spike_delta": float(np.mean(spike_deltas)),
        })

    def class_stats(label: str) -> dict[str, Any]:
        members = [row for row in per_cell if label in row["classes"]]
        if not members:
            return {"n": 0}
        deltas = [float(row["mean_spike_delta"]) for row in members]
        return {
            "n": len(members),
            "with_any_on_spike": int(sum(row["fires_on_any_seed"] for row in members)),
            "with_any_off_spike": int(sum(row["fires_off_any_seed"] for row in members)),
            "with_positive_mean_spike_delta": int(sum(value > 0 for value in deltas)),
            "with_zero_mean_spike_delta": int(sum(value == 0 for value in deltas)),
            "with_negative_mean_spike_delta": int(sum(value < 0 for value in deltas)),
            "mean_spike_delta_distribution": {
                "min": float(np.min(deltas)),
                "median": float(np.median(deltas)),
                "max": float(np.max(deltas)),
                "mean": float(np.mean(deltas)),
            },
        }

    classes = sorted({label for row in per_cell for label in row["classes"]})
    source_deltas = [float(pair["source_rate_delta_hz"]) for pair in paired_runs]
    output = {
        "class": "development",
        "purpose": (
            "per-cell measurement of the TuBu reachable set on the declared resting substrate; "
            "a null here is a real null"
        ),
        "declared_substrate_id": plan["declared_substrate_id"],
        "protocol": plan["protocol"],
        "identity": identities[0],
        "plan_sha256": hash_file(plan_path),
        "source": plan["source"],
        "summary": plan["summary"],
        "source_paired": {
            "rate_delta_hz": source_deltas,
            "rate_delta_hz_mean": float(np.mean(source_deltas)),
            "rate_delta_hz_min": float(np.min(source_deltas)),
            "rate_delta_hz_max": float(np.max(source_deltas)),
            "spikes_off": [pair["source_spikes_off"] for pair in paired_runs],
            "spikes_on": [pair["source_spikes_on"] for pair in paired_runs],
        },
        "two_hop": plan["two_hop"],
        "class_stats": {label: class_stats(label) for label in classes},
        "paired_runs": paired_runs,
        "cells": per_cell,
        "raw_directory": str(raw),
        "raw_sha256": {f"seed-{seed}.json": hash_file(raw / f"seed-{seed}.json") for seed in seeds},
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination, output)
    print(f"wrote {destination}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
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
