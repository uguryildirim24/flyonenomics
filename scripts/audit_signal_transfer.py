"""Locate the first transfer failure after R1-6 and TuBu on the declared substrate.

``static`` audits connectivity and the corrected WP20 fixture without advancing
Brian time. ``run`` executes the paired 48-brain-second voltage probe.
``summarize`` binds the raw files into the compact committed evidence record.
All voltage and event-amplitude values are model measurements, not pass lines.
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
import subprocess
import time
from types import SimpleNamespace
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MASTER = 20260912
SEEDS = (1, 2, 3)
PATHS = ("eye", "TuBu")
CONDITIONS = {"eye": ("ambient", "stripe"), "TuBu": ("off", "on")}
SOURCE_POPULATION = {"eye": "R1_6", "TuBu": "TuBu"}
INPUT_RATE_HZ = {"eye": 150.0, "TuBu": 70.0}
MAX_TARGETS = 64
FIXTURE_COMMIT = "5f2cefcf83972033e0d9ec89a88934d3ac9bb7b8"
FIXTURE_PATH = "data/experiments/p2/vpath-vtcal.json"
VTCAL_PATH = "validation/records/p2/vtcal.json"
OBSERVER_POPULATIONS = (
    "TuBu", "visual_projection", "LAL_neurons", "steering_L", "steering_R",
)
PATH_POPULATIONS = (
    "visual_projection", "LAL_neurons", "steering_L", "steering_R",
    "DNa02_L", "DNa02_R",
)


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


def git_bytes(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


def identity(platform_name: str) -> dict[str, Any]:
    from flyonenomics.connectome_arrays import connectome_source_paths
    from flyonenomics.io import hash_file

    source_commit = os.environ.get("SIGNAL_SOURCE_COMMIT")
    if not source_commit:
        raise ValueError("SIGNAL_SOURCE_COMMIT must bind the executed source commit")
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


def substrate_arrays() -> tuple[Any, Any, dict, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load registry, parameters, drive, graph, raw counts and composed weights."""
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.drive.rest import apply_rest_substrate, kc_mask_in_engine, load_drive_rest
    from flyonenomics.registry import build_registry
    from flyonenomics.substrate.transmitters import load_transmitters
    from flyonenomics.types import load_params

    class ScaleSink:
        n = 138639

        @staticmethod
        def engine_model() -> str:
            return "lif"

        @staticmethod
        def set_weight_scale(value: np.ndarray) -> None:
            del value

    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    drive = load_drive_rest(ROOT / "data/drive-v0.2.yaml")
    completeness, connectivity = connectome_source_paths("783")
    roots, pre, post, raw = load_connectome_arrays(completeness, connectivity)
    classes = load_transmitters()["class_array"]
    base, scale = apply_rest_substrate(
        ScaleSink(), params, drive, classes=classes, pre=pre, post=post,
        kc_mask=kc_mask_in_engine(), n=registry.n,
    )
    effective = np.asarray(raw, dtype=np.float64) * float(params.get("lif.w_syn")) * scale
    return registry, params, drive, np.asarray(roots), np.asarray(pre), np.asarray(post), np.asarray(raw), effective


def input_rate_deltas(registry: Any, params: Any) -> dict[str, np.ndarray]:
    """Condition-B minus condition-A source input rates, Hz in source order."""
    from flyonenomics.behaviour.encoder import PhotoreceptorEncoder, VisualEncoder

    result: dict[str, np.ndarray] = {}
    stripe = [{"name": "A", "az_fly": 45.0, "width": 5.0, "contrast": 1.0}]
    eye = registry.population("R1_6")
    eye_encoder = PhotoreceptorEncoder(registry, np.sort(eye.idx).astype(np.int32), params)
    ambient = eye_encoder.rates([], r_light=INPUT_RATE_HZ["eye"], kind="ambient")
    striped = eye_encoder.rates(stripe, r_light=INPUT_RATE_HZ["eye"], kind="stripe")
    result["eye"] = striped[eye_encoder.positions] - ambient[eye_encoder.positions]
    tubu = registry.population("TuBu")
    tubu_encoder = VisualEncoder(registry, np.sort(tubu.idx).astype(np.int32), params, "TuBu")
    off = tubu_encoder.rates([], maximum_hz=INPUT_RATE_HZ["TuBu"], sigma_deg=20.0)
    on = tubu_encoder.rates(stripe, maximum_hz=INPUT_RATE_HZ["TuBu"], sigma_deg=20.0)
    result["TuBu"] = on[tubu_encoder.positions] - off[tubu_encoder.positions]
    return result


def edge_detail(u: int, v: int, pre: np.ndarray, post: np.ndarray,
                raw: np.ndarray, effective: np.ndarray) -> dict[str, Any]:
    lo = int(np.searchsorted(pre, u, side="left"))
    hi = int(np.searchsorted(pre, u, side="right"))
    rows = np.flatnonzero(post[lo:hi] == v) + lo
    if len(rows) != 1:
        raise ValueError(f"expected one edge {u}->{v}, found {len(rows)}")
    row = int(rows[0])
    return {
        "anatomical_synapses": float(abs(raw[row])),
        "effective_weight_mV": float(effective[row]),
        "sign": 1 if effective[row] > 0 else -1,
    }


def shortest_paths(registry: Any, roots: np.ndarray, pre: np.ndarray, post: np.ndarray,
                   raw: np.ndarray, effective: np.ndarray) -> dict[str, Any]:
    """Shortest directed paths from any injected TuBu, annotated with composed signs."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra

    n = registry.n
    keep = effective != 0
    graph = csr_matrix(
        (np.ones(int(keep.sum()), dtype=np.uint8), (pre[keep], post[keep])),
        shape=(n, n),
    )
    source = np.asarray(registry.population("TuBu").idx, dtype=np.int32)
    distance, predecessor, origin = dijkstra(
        graph, directed=True, indices=source, return_predecessors=True,
        unweighted=True, min_only=True,
    )
    output: dict[str, Any] = {}
    for name in ("DNa02_L", "DNa02_R", "LAL_neurons", "steering_L", "steering_R"):
        target_idx = np.asarray(registry.population(name).idx, dtype=np.int32)
        finite = target_idx[np.isfinite(distance[target_idx])]
        if not len(finite):
            output[name] = {"reachable": False}
            continue
        minimum = int(np.min(distance[finite]))
        nearest = finite[distance[finite] == minimum]
        examples = []
        for target in nearest[:5]:
            nodes = [int(target)]
            while int(predecessor[nodes[-1]]) >= 0:
                nodes.append(int(predecessor[nodes[-1]]))
            nodes.reverse()
            edges = [edge_detail(u, v, pre, post, raw, effective)
                     for u, v in zip(nodes[:-1], nodes[1:], strict=True)]
            sign = int(np.prod([edge["sign"] for edge in edges], dtype=np.int64))
            examples.append({
                "origin_engine_index": int(origin[int(target)]),
                "engine_indices": nodes,
                "root_ids": [int(roots[node]) for node in nodes],
                "path_sign": sign,
                "edges": edges,
            })
        output[name] = {
            "reachable": True,
            "minimum_hops": minimum,
            "targets_at_minimum_hops": int(len(nearest)),
            "reachable_targets": int(len(finite)),
            "population_n": int(len(target_idx)),
            "examples": examples,
        }
    return output


def static_audit(destination: Path) -> None:
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import rest_background_weights
    from flyonenomics.io import hash_file
    from flyonenomics.substrate.transmitters import annotations_in_engine, load_transmitters

    started = time.monotonic()
    registry, params, drive, roots, pre, post, raw, effective = substrate_arrays()
    frame, annotation_roots = annotations_in_engine()
    if not np.array_equal(annotation_roots, roots) or not np.array_equal(registry.root_ids, roots):
        raise ValueError("annotation, registry and connectome engine orders differ")
    classes = load_transmitters()["class_array"]
    groups = group_indices(registry)
    group_name = np.empty(registry.n, dtype=object)
    for name, idx in groups.items():
        group_name[idx] = name
    bg = rest_background_weights(registry, drive, params)
    rate_delta = input_rate_deltas(registry, params)
    audits: dict[str, Any] = {}
    for path_name in PATHS:
        source_pop = registry.population(SOURCE_POPULATION[path_name])
        source_idx = np.asarray(source_pop.idx, dtype=np.int32)
        source_mask = np.isin(pre, source_idx)
        edge_rows = np.flatnonzero(source_mask)
        target_idx = np.unique(post[source_mask]).astype(np.int32)
        source_position = np.full(registry.n, -1, dtype=np.int32)
        source_position[source_idx] = np.arange(len(source_idx), dtype=np.int32)
        predicted = effective[source_mask] * rate_delta[path_name][source_position[pre[source_mask]]]
        predicted_by_target = np.bincount(
            post[source_mask], weights=predicted, minlength=registry.n,
        )
        strength = np.abs(predicted_by_target)
        strongest = target_idx[np.argsort(strength[target_idx], kind="stable")[::-1][:MAX_TARGETS]]
        target_rows = []
        memberships = {name: np.isin(np.arange(registry.n), registry.population(name).idx)
                       for name in PATH_POPULATIONS}
        for target in target_idx:
            rows = edge_rows[post[edge_rows] == target]
            signed = effective[rows]
            target_rows.append({
                "engine_index": int(target),
                "root_id": int(roots[target]),
                "cell_type": None if frame.iloc[target]["cell_type"] != frame.iloc[target]["cell_type"] else str(frame.iloc[target]["cell_type"]),
                "hemibrain_type": None if frame.iloc[target]["hemibrain_type"] != frame.iloc[target]["hemibrain_type"] else str(frame.iloc[target]["hemibrain_type"]),
                "super_class": None if frame.iloc[target]["super_class"] != frame.iloc[target]["super_class"] else str(frame.iloc[target]["super_class"]),
                "side": str(frame.iloc[target]["side"]),
                "curated_transmitter": str(classes[target]),
                "background_group": str(group_name[target]),
                "background_mV": float(bg[target]),
                "memberships": [name for name, mask in memberships.items() if mask[target]],
                "connection_pairs": int(len(rows)),
                "anatomical_synapses": float(np.abs(raw[rows]).sum()),
                "effective_weight_sum_mV": float(signed.sum()),
                "effective_absolute_sum_mV": float(np.abs(signed).sum()),
                "effective_positive_pairs": int((signed > 0).sum()),
                "effective_negative_pairs": int((signed < 0).sum()),
                "effective_zero_pairs": int((signed == 0).sum()),
                "predicted_condition_event_rate_delta_mV_per_s": float(predicted_by_target[target]),
                "selected_for_voltage_probe": bool(target in strongest),
            })
        coverage = {}
        target_set = set(int(value) for value in target_idx)
        for name in PATH_POPULATIONS:
            pop_idx = np.asarray(registry.population(name).idx, dtype=np.int32)
            reached = [int(value) for value in pop_idx if int(value) in target_set]
            coverage[name] = {
                "population_n": int(len(pop_idx)), "reached_n": int(len(reached)),
                "coverage_fraction": float(len(reached) / len(pop_idx)) if len(pop_idx) else None,
                "reached_root_ids": [int(roots[value]) for value in reached],
            }
        audits[path_name] = {
            "source_population": SOURCE_POPULATION[path_name],
            "source_n": int(len(source_idx)),
            "source_root_ids_sha256": digest(source_pop.root_ids, np.int64),
            "source_cells_with_outgoing_edges": int(len(np.unique(pre[source_mask]))),
            "connection_pairs": int(source_mask.sum()),
            "anatomical_synapses": float(np.abs(raw[source_mask]).sum()),
            "effective_weight_sum_mV": float(effective[source_mask].sum()),
            "effective_absolute_sum_mV": float(np.abs(effective[source_mask]).sum()),
            "effective_positive_pairs": int((effective[source_mask] > 0).sum()),
            "effective_negative_pairs": int((effective[source_mask] < 0).sum()),
            "effective_zero_pairs": int((effective[source_mask] == 0).sum()),
            "immediate_targets_n": int(len(target_idx)),
            "immediate_target_cell_types": counts(frame.iloc[target_idx]["cell_type"].fillna("<missing>").to_numpy()),
            "immediate_target_super_classes": counts(frame.iloc[target_idx]["super_class"].fillna("<missing>").to_numpy()),
            "coverage": coverage,
            "target_ranking": "absolute expected condition-B minus condition-A source event amplitude rate",
            "strongest_target_indices": [int(value) for value in strongest],
            "strongest_target_root_ids": [int(roots[value]) for value in strongest],
            "targets": target_rows,
        }
    fixture_bytes = git_bytes(FIXTURE_COMMIT, FIXTURE_PATH)
    vtcal_bytes = git_bytes(FIXTURE_COMMIT, VTCAL_PATH)
    fixture = json.loads(fixture_bytes)
    vtcal = json.loads(vtcal_bytes)
    injections = [probe["params"].get("inject_at")
                  for arm in fixture["arms"] for probe in arm["protocol"]]
    fixture_observers = list(dict.fromkeys(fixture["record"]["spikes"] + fixture["record"]["rates"]))
    record_observers = set()
    for row in vtcal["table"] + [vtcal["ten_seed"]]:
        record_observers.update(row["central_ci95"])
    record_observers.update(("steering_L", "steering_R"))
    observer_rows = {}
    for name in fixture_observers:
        pop = registry.population(name)
        observer_rows[name] = {
            "n": int(len(pop.idx)),
            "engine_indices_sha256": digest(pop.idx, np.int32),
            "root_ids_sha256": digest(pop.root_ids, np.int64),
        }
    fixture_audit = {
        "commit": FIXTURE_COMMIT,
        "path": FIXTURE_PATH,
        "sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "all_probe_inject_at": injections,
        "all_probes_inject_TuBu": all(value == "TuBu" for value in injections),
        "extended_input_population": "TuBu",
        "extended_input_n": int(len(registry.population("TuBu").idx)),
        "extended_input_unique_n": int(len(np.unique(registry.population("TuBu").idx))),
        "extended_input_root_ids_sha256": digest(registry.population("TuBu").root_ids, np.int64),
        "fixture_observers": fixture_observers,
        "record_observers": sorted(record_observers),
        "observer_sets_match_record": set(fixture_observers) == record_observers,
        "observers": observer_rows,
        "record_path": VTCAL_PATH,
        "record_sha256": hashlib.sha256(vtcal_bytes).hexdigest(),
    }
    id_record = identity(f"{platform.system().lower()}-{platform.machine()}")
    id_record.update({
        "scale_sha256": digest((effective / (np.asarray(raw, dtype=np.float64) * float(params.get("lif.w_syn")))).astype(np.float32), np.float32),
        "background_sha256": digest(bg),
    })
    output = {
        "class": "development",
        "purpose": "zero-brain-second structural audit, not qualification or calibration",
        "identity": id_record,
        "declared_substrate_id": "rest:379cc4cc9030cdd1",
        "fixture": fixture_audit,
        "paths": audits,
        "shortest_signed_paths_from_TuBu": shortest_paths(registry, roots, pre, post, raw, effective),
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination, output)
    print(f"wrote {destination}", flush=True)


def probe(path_name: str, condition: str) -> Any:
    from flyonenomics.schema.experiment import Probe

    stimulus = "stripe" if condition in ("stripe", "on") else "ambient"
    return Probe.model_validate({
        "type": "probe", "assay": "open_loop_steering", "duration_s": 4.0,
        "label": f"{path_name}-{condition}",
        "params": {
            "inject_at": "photoreceptors" if path_name == "eye" else "TuBu",
            "blocks": [{
                "stimulus": stimulus,
                "azimuth_deg": 45.0 if stimulus == "stripe" else None,
                "transition_s": 2.0, "dwell_s": 2.0,
            }],
        },
    })


def run_pair(job: tuple[str, int, str, str]) -> str:
    from brian2 import mV
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

    path_name, seed, static_path, destination = job
    destination_path = Path(destination)
    audit = read(Path(static_path))
    started = time.monotonic()
    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    groups = group_indices(registry)
    drive = load_drive_rest(ROOT / "data/drive-v0.2.yaml")
    dopamine = read_yaml(ROOT / "data/dopamine-v0.2.yaml")
    source = np.asarray(registry.population(SOURCE_POPULATION[path_name]).idx, dtype=np.int32)
    targets = np.asarray(audit["paths"][path_name]["strongest_target_indices"], dtype=np.int32)
    if len(targets) > MAX_TARGETS or not len(targets):
        raise ValueError("static audit supplied an invalid trace target set")
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
    incoming_mask = np.isin(post, targets)
    incoming_pre = np.asarray(pre[incoming_mask], dtype=np.int32)
    incoming_post = np.asarray(post[incoming_mask], dtype=np.int32)
    incoming_weight = effective[incoming_mask]
    target_position = np.full(registry.n, -1, dtype=np.int32)
    target_position[targets] = np.arange(len(targets), dtype=np.int32)
    incoming_target_position = target_position[incoming_post]
    source_edge = np.isin(incoming_pre, source)
    rows = []
    for condition in CONDITIONS[path_name]:
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
            SimpleNamespace(topology=topology), registry, params, probe(path_name, condition),
            v_fwd=0.0, sign_steer=1, K_steer=0.0,
            r_vis_max=INPUT_RATE_HZ[path_name], sigma_vis=20.0,
        )
        arena.reset(np.random.default_rng(seed))
        count = np.zeros(registry.n, dtype=np.int64)
        recurrent_events = np.zeros(len(targets), dtype=np.float64)
        source_events = np.zeros(len(targets), dtype=np.float64)
        threshold_sum = np.zeros(len(targets), dtype=np.float64)
        threshold_min = np.full(len(targets), np.inf)
        threshold_max = np.full(len(targets), -np.inf)
        gain_sum = np.zeros(len(targets), dtype=np.float64)
        measurement_chunks = 0
        chunk_ms = float(params.get("engine.chunk_ms"))
        settle_chunks = int(round(2000.0 / chunk_ms))
        total_chunks = int(round(4000.0 / chunk_ms))
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
                recurrent_events += np.bincount(
                    incoming_target_position, weights=amplitudes, minlength=len(targets),
                )
                source_events += np.bincount(
                    incoming_target_position[source_edge], weights=amplitudes[source_edge],
                    minlength=len(targets),
                )
                threshold = np.asarray(composed.v_th[targets], dtype=np.float64)
                threshold_sum += threshold
                np.minimum(threshold_min, threshold, out=threshold_min)
                np.maximum(threshold_max, threshold, out=threshold_max)
                gain_sum += gain_before
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
            connected_rows = np.flatnonzero(source_edge & (incoming_target_position == position))
            connected_source = np.unique(incoming_pre[connected_rows])
            values = traces.v_mv[position]
            threshold_mean = threshold_sum[position] / measurement_chunks
            target_rows.append({
                "engine_index": int(target),
                "root_id": int(roots[target]),
                "connected_source_cells": int(len(connected_source)),
                "connected_source_spikes": int(count[connected_source].sum()),
                "target_spikes": int(count[target]),
                "sampled_mean_v_mV": float(values.mean()),
                "sampled_min_v_mV": float(values.min()),
                "sampled_max_v_mV": float(values.max()),
                "threshold_mean_mV": float(threshold_mean),
                "threshold_min_mV": float(threshold_min[position]),
                "threshold_max_mV": float(threshold_max[position]),
                "mean_distance_to_threshold_mV": float(threshold_mean - values.mean()),
                "nearest_sampled_distance_to_threshold_mV": float(threshold_min[position] - values.max()),
                "postsynaptic_gain_mean": float(gain_sum[position] / measurement_chunks),
                "all_recurrent_incoming_event_amplitude_sum_mV": float(recurrent_events[position]),
                "source_incoming_event_amplitude_sum_mV": float(source_events[position]),
            })
        rows.append({
            "condition": condition,
            "source_population": SOURCE_POPULATION[path_name],
            "source_n": int(len(source)),
            "source_spikes": int(count[source].sum()),
            "source_active_cells": int(np.count_nonzero(count[source])),
            "source_rate_hz": float(count[source].sum() / (len(source) * 2.0)),
            "input_rate_min_hz": float(input_min),
            "input_rate_max_hz": float(input_max),
            "targets": target_rows,
            "da_min_uM": float(mod.da_c.min()),
            "da_max_uM": float(mod.da_c.max()),
            "trace_samples": int(traces.v_mv.shape[1]),
        })
        print(path_name, seed, condition, "complete", flush=True)
    result = {
        "identity": {
            **audit["identity"],
            "platform": f"{platform.system().lower()}-{platform.machine()}",
            "scale_sha256": digest(scale, np.float32),
            "background_sha256": digest(background),
        },
        "path": path_name,
        "seed": seed,
        "brian_seed": brian_seed(MASTER, seed, 0),
        "settle_s": 2.0,
        "measure_s": 2.0,
        "brain_seconds": 8.0,
        "target_indices": [int(value) for value in targets],
        "target_root_ids": [int(roots[value]) for value in targets],
        "rows": rows,
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    output = destination_path / f"{path_name}-{seed}.json"
    dump(output, result)
    return output.name


def run_dynamic(static_path: Path, destination: Path, workers: int) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    jobs = [(path_name, seed, str(static_path.resolve()), str(destination.resolve()))
            for path_name in PATHS for seed in SEEDS]
    # Brian2/Cython owns process-global objects; never build a second whole-brain
    # network in a worker after the first job has torn one down.
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
        max_tasks_per_child=1,
    ) as pool:
        print(list(pool.map(run_pair, jobs)), flush=True)


def summarize(source: Path, destination: Path) -> None:
    from flyonenomics.io import hash_file

    static = read(source / "static.json")
    runs = [read(source / f"{path_name}-{seed}.json")
            for path_name in PATHS for seed in SEEDS]
    if sum(float(row["brain_seconds"]) for row in runs) != 48.0:
        raise ValueError("dynamic probe must total 48 brain-seconds")
    dynamic_identities = []
    paths: dict[str, Any] = {}
    for path_name in PATHS:
        path_runs = [run for run in runs if run["path"] == path_name]
        if [run["seed"] for run in path_runs] != list(SEEDS):
            raise ValueError(f"{path_name} does not have seeds 1, 2, 3")
        for run in path_runs:
            if [row["condition"] for row in run["rows"]] != list(CONDITIONS[path_name]):
                raise ValueError(f"{path_name} condition order differs")
            dynamic_identities.append(run["identity"])
        target_idx = path_runs[0]["target_indices"]
        if any(run["target_indices"] != target_idx for run in path_runs):
            raise ValueError("target selection changed across seeds")
        paired = []
        for run in path_runs:
            before, after = run["rows"]
            before_targets = {row["engine_index"]: row for row in before["targets"]}
            after_targets = {row["engine_index"]: row for row in after["targets"]}
            target_deltas = []
            for target in target_idx:
                a, b = before_targets[target], after_targets[target]
                target_deltas.append({
                    "engine_index": target,
                    "root_id": a["root_id"],
                    "source_spike_delta": b["connected_source_spikes"] - a["connected_source_spikes"],
                    "target_spike_delta": b["target_spikes"] - a["target_spikes"],
                    "mean_v_delta_mV": b["sampled_mean_v_mV"] - a["sampled_mean_v_mV"],
                    "max_v_delta_mV": b["sampled_max_v_mV"] - a["sampled_max_v_mV"],
                    "mean_distance_to_threshold_delta_mV": b["mean_distance_to_threshold_mV"] - a["mean_distance_to_threshold_mV"],
                    "nearest_distance_to_threshold_delta_mV": b["nearest_sampled_distance_to_threshold_mV"] - a["nearest_sampled_distance_to_threshold_mV"],
                    "all_recurrent_event_delta_mV": b["all_recurrent_incoming_event_amplitude_sum_mV"] - a["all_recurrent_incoming_event_amplitude_sum_mV"],
                    "source_event_delta_mV": b["source_incoming_event_amplitude_sum_mV"] - a["source_incoming_event_amplitude_sum_mV"],
                    "before": a,
                    "after": b,
                })
            paired.append({
                "seed": run["seed"],
                "source_spike_delta": after["source_spikes"] - before["source_spikes"],
                "source_rate_delta_hz": after["source_rate_hz"] - before["source_rate_hz"],
                "targets": target_deltas,
            })
        per_target = []
        static_targets = {row["engine_index"]: row for row in static["paths"][path_name]["targets"]}
        for target in target_idx:
            rows = [next(row for row in pair["targets"] if row["engine_index"] == target) for pair in paired]
            fields = (
                "source_spike_delta", "target_spike_delta", "mean_v_delta_mV",
                "max_v_delta_mV", "mean_distance_to_threshold_delta_mV",
                "nearest_distance_to_threshold_delta_mV", "all_recurrent_event_delta_mV",
                "source_event_delta_mV",
            )
            summary = {}
            for field in fields:
                values = [float(row[field]) for row in rows]
                summary[field] = {
                    "mean": float(np.mean(values)), "min": float(np.min(values)),
                    "max": float(np.max(values)), "values": values,
                }
            per_target.append({
                "engine_index": target,
                "root_id": static_targets[target]["root_id"],
                "cell_type": static_targets[target]["cell_type"],
                "super_class": static_targets[target]["super_class"],
                "memberships": static_targets[target]["memberships"],
                "anatomy": {
                    key: static_targets[target][key] for key in (
                        "connection_pairs", "anatomical_synapses", "effective_weight_sum_mV",
                        "predicted_condition_event_rate_delta_mV_per_s",
                    )
                },
                "paired_summary": summary,
            })
        paths[path_name] = {
            "conditions": list(CONDITIONS[path_name]),
            "source_population": SOURCE_POPULATION[path_name],
            "source_n": path_runs[0]["rows"][0]["source_n"],
            "source_rate_delta_hz": [row["source_rate_delta_hz"] for row in paired],
            "source_spike_delta": [row["source_spike_delta"] for row in paired],
            "targets_n": len(target_idx),
            "paired_rows": paired,
            "per_target_three_seed_summary": per_target,
            "wall_seconds": [run["wall_seconds"] for run in path_runs],
        }
    common_dynamic = dynamic_identities[0]
    if any(value != common_dynamic for value in dynamic_identities[1:]):
        raise ValueError("dynamic execution identities differ")
    raw_files = sorted(path for path in source.iterdir() if path.is_file())
    output = {
        "class": "development",
        "purpose": "signal-transfer localization, not qualification or calibration",
        "declared_substrate_id": "rest:379cc4cc9030cdd1",
        "protocol": {
            "master_seed": MASTER, "seeds": list(SEEDS), "paths": list(PATHS),
            "conditions": CONDITIONS, "settle_s": 2.0, "measure_s": 2.0,
            "brain_seconds": 48.0, "max_targets_per_path": MAX_TARGETS,
            "stripe_azimuth_deg": 45.0, "stripe_width_deg": 5.0,
            "eye_light_hz": INPUT_RATE_HZ["eye"], "TuBu_max_hz": INPUT_RATE_HZ["TuBu"],
            "TuBu_sigma_deg": 20.0,
            "target_ranking": "absolute expected paired source-event amplitude-rate change",
            "incoming_event_definition": "sum of recurrent event amplitudes after substrate scaling and live postsynaptic gain; external/background events excluded",
        },
        "static_identity": static["identity"],
        "dynamic_identity": common_dynamic,
        "fixture": static["fixture"],
        "static_paths": static["paths"],
        "shortest_signed_paths_from_TuBu": static["shortest_signed_paths_from_TuBu"],
        "dynamic_paths": paths,
        "raw_directory": str(source),
        "raw_sha256": {path.name: hash_file(path) for path in raw_files},
    }
    dump(destination, output)
    print(f"wrote {destination}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    static_parser = sub.add_parser("static")
    static_parser.add_argument("--out", type=Path, default=Path("camber-runs/diag/signal-transfer/static.json"))
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--static", type=Path, default=Path("camber-runs/diag/signal-transfer/static.json"))
    run_parser.add_argument("--out", type=Path, default=Path("camber-runs/diag/signal-transfer"))
    run_parser.add_argument("--workers", type=int, choices=range(1, 7), default=4)
    summary_parser = sub.add_parser("summarize")
    summary_parser.add_argument("--source", type=Path, default=Path("camber-runs/diag/signal-transfer"))
    summary_parser.add_argument("--out", type=Path, default=Path("validation/records/p2/signal-transfer-audit.json"))
    args = parser.parse_args()
    if args.command == "static":
        static_audit(args.out)
    elif args.command == "run":
        run_dynamic(args.static, args.out, args.workers)
    else:
        summarize(args.source, args.out)


if __name__ == "__main__":
    main()
