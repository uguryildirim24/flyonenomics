"""Small causal probes of optic-lobe silence; development measurements, not qualification.

Four arms x three paired seeds x four conditions x (2 s settle + 2 s count)
= 192 brain-seconds. Run on Oracle with --workers 2 (or up to 4).
Canonical YAMLs are read, never changed. See docs/optic-lobe-silence.md.
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

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("declared", "optic-1mV", "optic-2mV", "connection-sign")
CONDITIONS = ("ambient", "stripe-left", "stripe-right", "dark")
NAMES = ("R1_6", "L1", "L2", "Mi1", "Tm1", "Tm2", "Tm3", "Tm4", "Tm9",
         "T5", "LC10", "LC_all", "LPLC", "MeTu", "TuBu")
MASTER = 20260912


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def counts_of(values):
    labels, counts = np.unique(values, return_counts=True)
    return {str(k): int(v) for k, v in zip(labels, counts)}


def run_arm(job):
    from brian2 import mV
    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.behaviour.buridan import _connection_sign_scale
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import apply_rest_substrate, load_drive_rest, rest_background_weights
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.io import read_yaml, hash_file
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.registry import build_registry
    from flyonenomics.schema.experiment import Probe
    from flyonenomics.substrate.transmitters import annotations_in_engine, load_transmitters, PHOTORECEPTOR_TYPES
    from flyonenomics.types import LayerFlags, load_params

    arm, destination = job
    destination = Path(destination)
    started = time.monotonic()
    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    groups = group_indices(registry)
    drive = load_drive_rest(ROOT / "data/drive-v0.2.yaml")
    dopamine = read_yaml(ROOT / "data/dopamine-v0.2.yaml")
    extended = np.sort(registry.population("R1_6").idx).astype(np.int32)
    topology = InputTopology(background=True, extended_idx=extended)
    engine = BrianEngine()
    engine.seed(MASTER)
    engine.build(connectome_files("783"), params, topology, mechanisms=None)
    base, scale = apply_rest_substrate(engine, params, drive)
    frame, roots = annotations_in_engine()
    assert np.array_equal(roots, registry.root_ids)
    completeness, connectivity = connectome_source_paths("783")
    loaded_roots, pre, post, raw_weights = load_connectome_arrays(completeness, connectivity)
    assert np.array_equal(loaded_roots, registry.root_ids)
    if arm == "connection-sign":
        mask = frame["cell_type"].fillna("").isin(PHOTORECEPTOR_TYPES).to_numpy()
        scale = _connection_sign_scale(scale, pre, mask)
        engine.set_weight_scale(scale)
    bg = rest_background_weights(registry, drive, params)
    if arm.startswith("optic-"):
        bg[groups["optic"]] = 1.0 if arm == "optic-1mV" else 2.0
    engine.set_background(bg)
    engine.store("initial")
    classes = load_transmitters()["class_array"]
    group_names = np.empty(registry.n, dtype=object)
    for name, idx in groups.items():
        group_names[idx] = name
    populations = {name: registry.population(name) for name in NAMES}
    subsets = {}
    inventory = {}
    retino = read_yaml(ROOT / "data/populations-v0.2.yaml")["retinotopy"]["types"]
    for name, pop in populations.items():
        idx = np.asarray(pop.idx, dtype=np.int32)
        inventory[name] = {"n": len(idx), "indices": idx.tolist(),
                           "root_ids": np.asarray(pop.root_ids).tolist(),
                           "side": counts_of(pop.side), "groups": counts_of(group_names[idx]),
                           "classes": counts_of(classes[idx]), "background_mV": counts_of(bg[idx]),
                           "base_threshold_mV": counts_of(base[idx])}
        subsets[name + ":all"] = idx
        for side in ("left", "right"):
            subsets[name + ":" + side] = idx[np.asarray(pop.side) == side]
        info = retino.get(name, {})
        if info.get("column_subsets"):
            az = dict(zip(info["root_ids"], info["azimuth_deg"]))
            angles = np.asarray([az.get(int(root), np.nan) for root in pop.root_ids], dtype=np.float64)
            for side, angle in (("left", -45.0), ("right", 45.0)):
                subsets[name + ":column-" + side] = idx[np.abs((angles-angle+180) % 360-180) <= 10]
    inventory["subsets"] = {name: idx.tolist() for name, idx in subsets.items()}
    connections = {}
    effective = np.asarray(engine._base_w_mv) * scale
    for source, target in (("R1_6", "L1"), ("R1_6", "L2"), ("L1", "Mi1"),
                           ("L1", "Tm3"), ("L2", "Tm1"), ("L2", "Tm2")):
        keep = np.isin(pre, populations[source].idx) & np.isin(post, populations[target].idx)
        w = effective[keep]
        r = raw_weights[keep]
        connections[source + "->" + target] = {
            "pairs": int(keep.sum()), "anatomical_synapses": float(np.abs(r).sum()),
            "connection_signed_synapses": float(r.sum()),
            "effective_negative_pairs": int((w < 0).sum()),
            "effective_positive_pairs": int((w > 0).sum()), "effective_zero_pairs": int((w == 0).sum()),
            "effective_sum_mV": float(w.sum()), "effective_min_mV": float(w.min()),
            "effective_max_mV": float(w.max()), "target_cells_reached": len(np.unique(post[keep]))}
    file_names = ("params-v0.2.yaml", "drive-v0.2.yaml", "dopamine-v0.2.yaml", "populations-v0.2.yaml", "transmitters-v0.2.yaml")
    identity = {"platform": f"{platform.system().lower()}-{platform.machine()}", "engine": "lif",
                "source_commit": os.environ["OPTIC_SOURCE_COMMIT"],
                "source_sha256": {str(p.relative_to(ROOT)): hash_file(p)
                                  for p in sorted((ROOT / "src").rglob("*.py"))},
                "runner_sha256": hash_file(Path(__file__)),
                "inputs_sha256": {n: hash_file(ROOT / "data" / n) for n in file_names},
                "connectome_sha256": {p.name: hash_file(p) for p in (completeness, connectivity)},
                "scale_sha256": digest(scale), "background_sha256": digest(bg),
                "started_utc": datetime.now(timezone.utc).isoformat()}
    dump(destination / (arm + "-structure.json"), {"arm": arm, "identity": identity,
         "inventory": inventory, "connections": connections,
         "model_strings": engine.model_strings(),
         "parameters": {key: params.get(key) for key in ("lif.v_0", "lif.v_th", "lif.t_mbr", "lif.tau", "lif.w_syn", "bg.n_bg", "bg.r_bg")}})
    # Release large audit temporaries before running.
    del effective, pre, post, raw_weights, frame
    rows, raw_counts = [], {}
    for seed in (1, 2, 3):
        for condition in CONDITIONS:
            engine.restore("initial")
            engine.seed(brian_seed(MASTER, seed, 0))
            mod = Neuromod(registry, params, LayerFlags(background=True, dopamine_A=True, transporter_C=True),
                           dopamine, base_v_th=base, schema_version="1.3", drive_groups=groups)
            mod.reset_fast()  # live pools, no DA clamp
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            engine.compose_refractory()
            stimulus = "stripe" if condition.startswith("stripe") else condition
            azimuth = -45.0 if condition == "stripe-left" else 45.0
            probe = Probe.model_validate({"type": "probe", "assay": "open_loop_steering", "duration_s": 4.0,
                "label": condition, "params": {"inject_at": "photoreceptors", "blocks": [
                {"stimulus": stimulus, "azimuth_deg": azimuth if stimulus == "stripe" else None,
                 "transition_s": 2.0, "dwell_s": 2.0}]}})
            arena = Behaviour(SimpleNamespace(topology=topology), registry, params, probe,
                              v_fwd=0.0, sign_steer=1, K_steer=0.0, r_vis_max=150.0, sigma_vis=20.0)
            arena.reset(np.random.default_rng(seed))
            counts = np.zeros(registry.n, dtype=np.int64)
            voltage_sum = np.zeros(registry.n)
            voltage_max = np.full(registry.n, -np.inf)
            chunk_ms = float(params.get("engine.chunk_ms"))
            samples = 0
            for step in range(int(4000 / chunk_ms)):
                engine.set_input_rates(arena.rates(arena.view(), step * chunk_ms / 1000))
                result = engine.run_chunk(chunk_ms)
                mod.on_chunk(result.counts, chunk_ms / 1000)
                composed = mod.compose()
                engine.set_threshold(composed.v_th)
                engine.set_gain(composed.gain)
                if step >= int(2000 / chunk_ms):
                    counts += result.counts
                    voltage = np.asarray(engine._neu.v[:] / mV)
                    voltage_sum += voltage
                    np.maximum(voltage_max, voltage, out=voltage_max)
                    samples += 1
            key = f"{arm}-{seed}-{condition}"
            raw_counts[key] = counts
            measured = {}
            for name, idx in subsets.items():
                if not len(idx):
                    measured[name] = {"n": 0}
                    continue
                measured[name] = {"n": len(idx), "spikes": int(counts[idx].sum()),
                                  "active_cells": int(np.count_nonzero(counts[idx])),
                                  "rate_hz": float(counts[idx].mean() / 2.0),
                                  "sampled_mean_v_mV": float(voltage_sum[idx].mean() / samples),
                                  "sampled_max_v_mV": float(voltage_max[idx].max()),
                                  "threshold_min_mV": float(composed.v_th[idx].min()),
                                  "threshold_max_mV": float(composed.v_th[idx].max())}
            rows.append({"seed": seed, "brian_seed": brian_seed(MASTER, seed, 0), "condition": condition,
                         "populations": measured, "da_min_uM": float(mod.da_c.min()), "da_max_uM": float(mod.da_c.max()),
                         "input_min_hz": float(arena.rates(arena.view(), 0).min()),
                         "input_max_hz": float(arena.rates(arena.view(), 0).max())})
            dump(destination / (arm + ".json"), {"identity": identity, "arm": arm, "rows": rows,
                 "brain_seconds": 4 * len(rows), "wall_seconds": time.monotonic() - started})
            np.savez_compressed(destination / (arm + "-counts.npz"), **raw_counts)
            print(key, "complete", flush=True)
    return arm


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--workers", type=int, choices=(2, 3, 4), default=2)
    parser.add_argument("--out", type=Path, default=Path("camber-runs/diag/optic-lobe"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        print(list(pool.map(run_arm, [(arm, str(args.out)) for arm in ARMS])), flush=True)


if __name__ == "__main__":
    main()
