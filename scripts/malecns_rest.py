#!/usr/bin/env python3
"""Measure MaleCNS rest under item 122's unchanged FlyWire settings.

Part A may run only ``--probe``.  ``--run`` is the held Part B entry point:
each persistent process builds one engine, arms are balanced across them, and
the parent writes a seed atomically only after all of its arms complete.  No
male outcome changes a configuration value.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import resource
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MALE_VERSION = "male-cns:v1.0"
MASTER_SEED = 20260912
SEEDS = tuple(range(1, 11))
SCREEN_WEIGHTS_MV = (1.0, 1.2)
GRADE_WEIGHT_MV = 1.4
SETTLE_S = 2.0
SCREEN_S = 10.0
LONG_S = 30.0
K2_S = 5.0


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system() == "Darwin" else value * 1024)


def _platform() -> dict[str, Any]:
    from flyonenomics.io import read_text

    memory: dict[str, int] = {}
    if platform.system() == "Linux":
        for line in read_text("/proc/meminfo").splitlines():
            key, _, value = line.partition(":")
            if key in {"MemTotal", "MemAvailable"}:
                memory[key] = int(value.strip().split()[0]) * 1024
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "memory_bytes": memory,
    }


def ruled_drive(registry: Any, sensory_weight_mv: float) -> dict[str, Any]:
    """Map item 122's settings to MaleCNS anatomical drive groups."""
    from flyonenomics.drive.background import group_indices

    groups = group_indices(registry)
    return {
        "g_gaba": 1.0,
        "g_glu": 4.0,
        "g_gaba_kc": 6.0,
        "g_his": 1.0,
        "scale_sha256": None,  # FlyWire's array hash cannot name a male-length array.
        "scope": "brain",
        "transmitters_blob_id": None,
        "optic_exemption": False,
        "sigma_th": 0.0,
        "seed": None,
        "z_sha256": None,
        "n_bg": 100.0,
        "r_bg": 10.0,
        "w_bg": {name: float(sensory_weight_mv if name == "sensory" else 0.0) for name in groups},
        "mechanisms": None,
    }


def _build(weight_mv: float = 1.0) -> dict[str, Any]:
    """Build one male engine in the fixed K1 screening state."""
    from flyonenomics.connectome_arrays import load_connectome_arrays
    from flyonenomics.datasets import get_dataset_adapter
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import apply_rest_substrate, rest_background_weights
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.registry import build_registry
    from flyonenomics.substrate.transmitters import load_transmitters
    from flyonenomics.types import LayerFlags, load_params

    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry(MALE_VERSION)
    groups = group_indices(registry)
    adapter = get_dataset_adapter(MALE_VERSION)
    files = adapter.connectome_files()
    _roots, pre, post, signed_weights = load_connectome_arrays(files.completeness, files.connectivity)
    transmitters = load_transmitters(ROOT / "data/transmitters-male-cns-v1.0.yaml")
    classes = np.asarray(transmitters["class_array"])
    s_pq = np.sign(np.asarray(signed_weights, dtype=np.float64))
    kc_mask = np.zeros(registry.n, dtype=np.uint8)
    kc_mask[registry.population("KC").idx] = 1
    drive = ruled_drive(registry, weight_mv)

    engine = BrianEngine()
    engine.seed(MASTER_SEED)
    build_started = time.perf_counter()
    engine.build(files, params, InputTopology(background=True), mechanisms=None)
    base_threshold, scale = apply_rest_substrate(
        engine,
        params,
        drive,
        classes=classes,
        s_pq=s_pq,
        pre=np.asarray(pre, dtype=np.int32),
        post=np.asarray(post, dtype=np.int32),
        kc_mask=kc_mask,
        n=registry.n,
        connectome_version=MALE_VERSION,
    )
    engine.set_background(rest_background_weights(registry, drive, params))
    # K1's clamp makes DA_ref the only effective dopamine value.  Pass no
    # calibrated table: item 149 forbids transferring FlyWire measurements,
    # and item 153 leaves every male R_c/alpha_c/S_c null until this run.
    mod = Neuromod(
        registry,
        params,
        LayerFlags(background=True, dopamine_A=True, transporter_C=True),
        None,
        base_v_th=base_threshold,
        schema_version="1.3",
        drive_groups=groups,
    )
    mod.clamp_pools(True)
    mod.reset_fast()
    composed = mod.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)
    engine.compose_refractory()
    engine.store("initial")
    return {
        "engine": engine,
        "mod": mod,
        "params": params,
        "registry": registry,
        "groups": groups,
        "drive": drive,
        "scale": scale,
        "build_wall_s": time.perf_counter() - build_started,
    }


def _reset(built: dict[str, Any], seed: int, weight_mv: float) -> None:
    from flyonenomics.drive.rest import rest_background_weights
    from flyonenomics.orchestrator.seeds import brian_seed

    engine, mod = built["engine"], built["mod"]
    engine.restore("initial")
    engine.seed(brian_seed(MASTER_SEED, seed, 0))
    mod.reset_fast()
    composed = mod.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)
    engine.compose_refractory()
    drive = ruled_drive(built["registry"], weight_mv)
    engine.set_background(rest_background_weights(built["registry"], drive, built["params"]))


def _measure(built: dict[str, Any], seed: int, weight_mv: float, seconds: float, stage: str) -> dict[str, Any]:
    from collections import deque

    from flyonenomics.validation.artefacts import FanoAccumulator, ignition_detector

    _reset(built, seed, weight_mv)
    engine, params, groups = built["engine"], built["params"], built["groups"]
    registry = built["registry"]
    chunk_ms = float(params.get("engine.chunk_ms"))
    chunk_s = chunk_ms / 1000.0
    per_second = round(1.0 / chunk_s)
    started = time.perf_counter()

    settled_central = 0
    for position in range(round(SETTLE_S / chunk_s)):
        result = engine.run_chunk(chunk_ms)
        if position >= round((SETTLE_S - 1.0) / chunk_s):
            settled_central += int(result.counts[groups["central"]].sum())
    settled_central_hz = settled_central / len(groups["central"])

    counts = np.zeros(engine.n, dtype=np.int64)
    fano = FanoAccumulator(engine.n, params)
    group_chunks: dict[str, list[int]] = {name: [] for name in groups}
    compartment_counts = np.zeros(len(registry.compartments()), dtype=np.float64)
    central_window: deque[int] = deque()
    rolling = 0
    rolling_hz: list[float] = []
    for _ in range(round(seconds / chunk_s)):
        result = engine.run_chunk(chunk_ms)
        counts += result.counts
        fano.add(result.hist_1ms)
        compartment_counts += np.asarray(built["mod"].m @ result.counts).ravel()
        for name, idx in groups.items():
            group_chunks[name].append(int(result.counts[idx].sum()))
        central_count = group_chunks["central"][-1]
        central_window.append(central_count)
        rolling += central_count
        if len(central_window) > per_second:
            rolling -= central_window.popleft()
        if len(central_window) == per_second:
            rolling_hz.append(rolling / len(groups["central"]))

    edge_s = 5.0 if stage == "R-long" else 1.0
    edge_chunks = round(edge_s / chunk_s)
    central = np.asarray(group_chunks["central"], dtype=np.float64)
    first_hz = float(central[:edge_chunks].sum() / (len(groups["central"]) * edge_s))
    last_hz = float(central[-edge_chunks:].sum() / (len(groups["central"]) * edge_s))
    rates = {name: float(counts[idx].mean() / seconds) for name, idx in groups.items()}
    sync = fano.report()
    ignition = ignition_detector(np.asarray(rolling_hz), settled_central_hz, params)
    assert isinstance(ignition, dict)
    return {
        "stage": stage,
        "seed": seed,
        "weight_mv": weight_mv,
        "settle_s": SETTLE_S,
        "measure_s": seconds,
        "state": "wild type; background on; layer A on; pools clamped at DA_ref; layer C on; no drug",
        "F": sync["F"],
        "b": sync["max_bin_fraction"],
        "rates_hz": rates,
        "first_central_hz": first_hz,
        "last_central_hz": last_hz,
        "stability_ratio": (first_hz / last_hz) if last_hz > 0 else None,
        "settled_central_hz": settled_central_hz,
        "ignition": ignition,
        "weighted_DAN_rates_by_compartment_hz": (compartment_counts / seconds).tolist(),
        "compartments": [item.name for item in registry.compartments()],
        "wall_s": time.perf_counter() - started,
    }


_WORKER_BUILT: dict[str, Any] | None = None


def _worker_init() -> None:
    """Build exactly one engine in each persistent Part B worker."""
    global _WORKER_BUILT
    _WORKER_BUILT = _build(1.0)


def _run_arm(task: tuple[int, str, float, float]) -> dict[str, Any]:
    """Run one arm on a persistent worker; the parent owns atomic seed files."""
    seed, stage, weight_mv, seconds = task
    if _WORKER_BUILT is None:
        raise RuntimeError("Part B worker was not initialized")
    return {
        "seed": seed,
        "stage": stage,
        "worker_pid": os.getpid(),
        "row": _measure(_WORKER_BUILT, seed, weight_mv, seconds, stage),
        "build_wall_s": _WORKER_BUILT["build_wall_s"],
        "peak_rss_bytes": _peak_rss_bytes(),
        "platform": _platform(),
    }


def _seed_payload(seed: int, arms: list[dict[str, Any]]) -> dict[str, Any]:
    screen = [arm["row"] for arm in arms if arm["stage"] in {"R-screen", "gradedness"}]
    screen.sort(key=lambda row: float(row["weight_mv"]))
    long_rows = [arm["row"] for arm in arms if arm["stage"] == "R-long"]
    k2_rows = [arm["row"] for arm in arms if arm["stage"] == "K2r-chain"]
    if len(screen) != 3 or len(long_rows) != 1 or len(k2_rows) != (1 if seed <= 3 else 0):
        raise ValueError(f"incomplete seed {seed}")
    return {
        "dataset": MALE_VERSION,
        "configuration": "item 122 unchanged, mapped by item 152 populations",
        "seed": seed,
        "worker_build_wall_s": [float(arm["build_wall_s"]) for arm in arms],
        "screen": screen,
        "long": long_rows[0],
        "k2": k2_rows[0] if k2_rows else None,
        "peak_rss_bytes": max(int(arm["peak_rss_bytes"]) for arm in arms),
        "platform": arms[0]["platform"],
        "interpretation": "Rest measurement only. The fly does not see; this is not behaviour.",
    }


def _tasks() -> list[tuple[int, str, float, float]]:
    """Longest-processing-time order keeps persistent workers balanced."""
    tasks = [(seed, "R-long", 1.0, LONG_S) for seed in SEEDS]
    tasks += [(seed, "R-screen", weight, SCREEN_S) for weight in SCREEN_WEIGHTS_MV for seed in SEEDS]
    tasks += [(seed, "gradedness", GRADE_WEIGHT_MV, SCREEN_S) for seed in SEEDS]
    tasks += [(seed, "K2r-chain", 1.0, K2_S) for seed in SEEDS if seed <= 3]
    return tasks


def calibration_chain(seed_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute section 2.5 arrays from seeds 1--3 without adopting them."""
    from flyonenomics.types import load_params

    params = load_params(ROOT / "data/params-v0.2.yaml")
    rows = [payload["k2"] for payload in seed_payloads if payload["k2"] is not None]
    if len(rows) != 3 or {int(row["seed"]) for row in rows} != {1, 2, 3}:
        raise ValueError("calibration chain needs K2r rows for seeds 1 through 3")
    rates = np.asarray([row["weighted_DAN_rates_by_compartment_hz"] for row in rows], dtype=float)
    r_c = rates.mean(axis=0)
    da_ref = float(params.get("da.DA_ref"))
    vmax = float(params.get("da.Vmax"))
    km = float(params.get("da.Km"))
    k_ns = float(params.get("da.k_ns"))
    r_min = float(params.get("da.R_min"))
    q_c = da_ref * (vmax / (km + da_ref) + k_ns)
    alpha = q_c / np.maximum(r_c, r_min)
    source = np.maximum(0.0, q_c - alpha * r_c)
    names = rows[0]["compartments"]
    return {
        "status": "computed, not adopted",
        "seeds": [1, 2, 3],
        "settle_s": SETTLE_S,
        "measure_s": K2_S,
        "Q_c_um_per_s": q_c,
        "R_c_weighted_spikes_per_s": r_c.tolist(),
        "alpha_c_um_per_weighted_spike": alpha.tolist(),
        "S_c_um_per_s": source.tolist(),
        "mode": ["derived" if value >= r_min else "source" for value in r_c],
        "compartments": names,
        "constants": {"DA_ref_um": da_ref, "Vmax_um_per_s": vmax, "Km_um": km, "k_ns_per_s": k_ns, "R_min_hz": r_min},
    }


def _summarize(directory: Path, output: Path) -> None:
    from flyonenomics.io import read_text

    payloads = [json.loads(read_text(directory / f"seed-{seed}.json")) for seed in SEEDS]
    summary = {
        "dataset": MALE_VERSION,
        "seeds": list(SEEDS),
        "configuration": "item 122 unchanged",
        "screen": [row for payload in payloads for row in payload["screen"]],
        "long": [payload["long"] for payload in payloads],
        "dopamine_calibration_chain": calibration_chain(payloads),
        "peak_rss_bytes": max(int(payload["peak_rss_bytes"]) for payload in payloads),
        "interpretation": "The fly does not see. These are rest metrics, not behaviour.",
    }
    _atomic_json(output, summary)


def _probe(output: Path) -> None:
    started = time.perf_counter()
    built = _build(1.0)
    after_build = time.perf_counter()
    _reset(built, 1, 1.0)
    engine = built["engine"]
    chunk_ms = float(built["params"].get("engine.chunk_ms"))
    counts = 0
    run_started = time.perf_counter()
    for _ in range(round(1000.0 / chunk_ms)):
        counts += int(engine.run_chunk(chunk_ms).counts.sum())
    run_wall = time.perf_counter() - run_started
    machine = _platform()
    total_memory = int(machine.get("memory_bytes", {}).get("MemTotal", 0))
    available = int(machine.get("memory_bytes", {}).get("MemAvailable", 0))
    peak = _peak_rss_bytes()
    memory_budget = max(0, available - math.ceil(total_memory / 3)) if total_memory else 0
    allowed = min(10, max(1, memory_budget // peak)) if peak else 1
    # Ten seed jobs: 3*(2+10) screen/grade + (2+30) long, plus K2r on 3 seeds.
    brain_s = len(SEEDS) * (3 * (SETTLE_S + SCREEN_S) + SETTLE_S + LONG_S) + 3 * (SETTLE_S + K2_S)
    full_build_wall = after_build - started
    estimate = full_build_wall + brain_s * run_wall / allowed
    payload = {
        "dataset": MALE_VERSION,
        "purpose": "Part A one-worker cost probe; no Part B outcome",
        "configuration": "item 122 unchanged, sensory-only 1.0 mV",
        "duration_s": 1.0,
        "seed": 1,
        "build_wall_s": after_build - started,
        "run_wall_s": run_wall,
        "wall_s_per_brain_s": run_wall,
        "total_wall_s": time.perf_counter() - started,
        "peak_rss_bytes": peak,
        "spikes": counts,
        "platform": machine,
        "plan": {
            "brain_s": brain_s,
            "seed_jobs": len(SEEDS),
            "workers": int(allowed),
            "worker_cap": 10,
            "memory_budget_bytes_above_one_third_free": memory_budget,
            "estimated_wall_s": estimate,
            "estimate_formula": "one parallel worker-build wave + total brain_s*1s run wall/workers",
        },
        "interpretation": "Cost only. Nothing was fitted; the fly does not see.",
    }
    _atomic_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--probe", action="store_true", help="Part A: one configured brain-second")
    modes.add_argument("--run", action="store_true", help="Part B: held ten-seed plan")
    modes.add_argument("--summarize", action="store_true", help="assemble completed atomic seed files")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.probe:
        if args.output is None:
            parser.error("--probe requires --output")
        _probe(args.output)
        return 0
    if args.summarize:
        if args.output_dir is None or args.output is None:
            parser.error("--summarize requires --output-dir and --output")
        _summarize(args.output_dir, args.output)
        return 0
    if args.output_dir is None:
        parser.error("--run requires --output-dir")
    if not 1 <= args.workers <= 10:
        parser.error("--workers must be in [1, 10]")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    expected = {seed: 5 if seed <= 3 else 4 for seed in SEEDS}
    arms: dict[int, list[dict[str, Any]]] = {seed: [] for seed in SEEDS}
    completed = []
    arm_log = []
    run_started = datetime.now(timezone.utc)
    print(json.dumps({
        "event": "run_start", "at": run_started.isoformat(), "workers": args.workers,
        "tasks": len(_tasks()), "brain_s": 701.0,
    }, sort_keys=True), flush=True)
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as pool:
        futures = [pool.submit(_run_arm, task) for task in _tasks()]
        for future in as_completed(futures):
            arm = future.result()
            seed = int(arm["seed"])
            arms[seed].append(arm)
            row = arm["row"]
            brain_s = float(row["settle_s"]) + float(row["measure_s"])
            log_row = {
                "event": "arm_complete", "at": datetime.now(timezone.utc).isoformat(),
                "worker_pid": int(arm["worker_pid"]), "seed": seed,
                "stage": arm["stage"], "weight_mv": float(row["weight_mv"]),
                "brain_s": brain_s, "wall_s": float(row["wall_s"]),
                "wall_s_per_brain_s": float(row["wall_s"]) / brain_s,
                "worker_peak_rss_bytes": int(arm["peak_rss_bytes"]),
                "worker_build_wall_s": float(arm["build_wall_s"]),
            }
            arm_log.append(log_row)
            print(json.dumps(log_row, sort_keys=True), flush=True)
            if len(arm_log) == args.workers:
                concurrent_q = sum(item["wall_s_per_brain_s"] for item in arm_log) / len(arm_log)
                completed_brain_s = sum(item["brain_s"] for item in arm_log)
                remaining_brain_s = 701.0 - completed_brain_s
                revised_wall_s = remaining_brain_s * concurrent_q / args.workers
                checkpoint = datetime.now(timezone.utc)
                print(json.dumps({
                    "event": "full_load_checkpoint", "at": checkpoint.isoformat(),
                    "completed_arms": len(arm_log), "mean_wall_s_per_brain_s": concurrent_q,
                    "remaining_brain_s_not_counting_inflight_progress": remaining_brain_s,
                    "revised_remaining_wall_s": revised_wall_s,
                    "revised_finish_utc": (checkpoint + timedelta(seconds=revised_wall_s)).isoformat(),
                }, sort_keys=True), flush=True)
            if len(arms[seed]) == expected[seed]:
                payload = _seed_payload(seed, arms[seed])
                path = args.output_dir / f"seed-{seed}.json"
                _atomic_json(path, payload)
                row = {"seed": seed, "path": str(path), "peak_rss_bytes": payload["peak_rss_bytes"]}
                completed.append(row)
                print(json.dumps(row, sort_keys=True), flush=True)
    _atomic_json(args.output_dir / "run-complete.json", {"completed": sorted(completed, key=lambda row: row["seed"])})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
