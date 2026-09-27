"""Benchmarks B1 and B2 of SPEC sections 3.1 and 3.10.

B1: one process, background object on with every w_bg_i equal to zero
by default, or with --drive weights supplied by WP3; the spontaneous assay with a 200-neuron
extended input at 50 Hz, 20 s of brain time, engine only. Reports wall
seconds per brain second q1 and the build time from process start to
store("initial") on v783, cold and warm Cython cache.

B2 measures the acceptance experiment at four workers with the WP9 memory gate.

Units: seconds of wall time, seconds of brain time, Hz for rates.
Shapes: scalars only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from flyonenomics.io import read_json

ROOT = Path(__file__).resolve().parents[1]

B1_BRAIN_S = 20.0
B1_CHUNK_MS = 10.0
B1_EXTENDED_N = 200
B1_EXTENDED_RATE_HZ = 50.0


def run_b1_worker(drive_path: str | None = None) -> dict[str, float | str]:
    """Build the v783 B1 engine and run 20 s in one process.

    Units: seconds, Hz. Shapes: scalars only. Prints one JSON line
    with build seconds, run seconds, q1, spike totals, and the
    background path, and returns the mapping.
    """
    import numpy as np

    from flyonenomics.types import ConnectomeFiles, load_params
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.engine.brian_engine import cache_dir

    t_start = time.perf_counter()
    base = cache_dir() / "Drosophila_brain_model"
    connectome = ConnectomeFiles(
        completeness=base / "Completeness_783.csv",
        connectivity=base / "Connectivity_783.parquet",
        version="783",
    )
    engine = BrianEngine()
    engine.seed(20260912)
    engine.build(
        connectome,
        load_params(),
        InputTopology(
            extended_idx=np.arange(B1_EXTENDED_N, dtype=np.int32),
            background=True,
        ),
    )
    if drive_path is None:
        build_worker_s = time.perf_counter() - t_start
        print("BUILD-DONE", flush=True)
    engine.restore("initial")
    g_inh = 1.0
    if drive_path is None:
        weights = np.zeros(engine.n)
    else:
        from flyonenomics.registry import build_registry
        from flyonenomics.drive.background import _connection_signs, background_weights, load_drive, weight_scale

        drive = load_drive(drive_path)
        g_inh = drive.g_inh
        weights = background_weights(build_registry("783"), drive)
        if g_inh > 1:
            engine.set_weight_scale(weight_scale(_connection_signs(connectome.connectivity), g_inh))
        params = load_params()
        engine.set_threshold(np.full(engine.n, float(params.get("lif.v_th"))))
        engine.set_gain(np.ones(engine.n))
    engine.set_background(weights)
    if drive_path is not None:
        engine.store("initial")
        build_worker_s = time.perf_counter() - t_start
        print("BUILD-DONE", flush=True)
    engine.set_input_rates(
        np.full(B1_EXTENDED_N, B1_EXTENDED_RATE_HZ, dtype=np.float64)
    )
    engine.seed(20260912)
    n_chunks = int(B1_BRAIN_S * 1000.0 / B1_CHUNK_MS)
    t_run = time.perf_counter()
    total = 0
    for _ in range(n_chunks):
        total += int(engine.run_chunk(B1_CHUNK_MS).counts.sum())
    run_s = time.perf_counter() - t_run
    result: dict[str, float | str] = {
        "build_worker_s": build_worker_s,
        "run_s": run_s,
        "brain_s": B1_BRAIN_S,
        "q1": run_s / B1_BRAIN_S,
        "total_spikes": float(total),
        "background_path": engine.background_path,
        "background_weights": drive_path or "all zero (background-off figure)",
        "g_inh": g_inh,
        "n": float(engine.n),
    }
    print(json.dumps(result))
    return result


def clear_cython_cache() -> None:
    """Remove this lane's Cython build cache. Units: none. Shapes: none."""
    from flyonenomics.engine.brian_engine import CYTHON_CACHE_DIR

    shutil.rmtree(CYTHON_CACHE_DIR, ignore_errors=True)


def run_b1(drive_path: str | None = None) -> dict[str, dict[str, float | str]]:
    """Measure genuine cold and warm B1 legs in fresh processes.

    Units: wall seconds from process launch to store and through run.
    Shapes: nested mappings of scalars.
    """
    def run_leg(label: str) -> dict[str, float | str]:
        started = time.perf_counter()
        proc = subprocess.Popen(
            [sys.executable, __file__, "--b1-worker"] + (["--drive", drive_path] if drive_path else []),
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None
        marker = proc.stdout.readline()
        build_s = time.perf_counter() - started
        output, errors = proc.communicate()
        if marker.strip() != "BUILD-DONE" or proc.returncode != 0:
            raise RuntimeError(
                f"B1 {label} worker failed: {marker} {output[-1000:]} {errors[-2000:]}"
            )
        result: dict[str, float | str] = json.loads(output.strip().splitlines()[-1])
        result["build_s"] = build_s
        return result

    clear_cython_cache()
    cold_result = run_leg("cold")
    warm_result = run_leg("warm")
    return {"cold": cold_result, "warm": warm_result}


def _swap_used_mib() -> float:
    """Read current macOS swap usage in MiB."""
    output = subprocess.check_output(["sysctl", "vm.swapusage"], text=True)
    match = re.search(r"used\s*=\s*([0-9.]+)([MG])", output)
    if match is None:
        raise RuntimeError("vm.swapusage used value missing")
    return float(match.group(1)) * (1024 if match.group(2) == "G" else 1)


def _memory_free_percent() -> float:
    """Read macOS memory_pressure free percentage."""
    output = subprocess.check_output(["memory_pressure"], text=True)
    match = re.search(r"System-wide memory free percentage:\s*([0-9.]+)%", output)
    if match is None:
        raise RuntimeError("memory_pressure free percentage missing")
    return float(match.group(1))


def _other_engine_pids() -> list[int]:
    """Find already-running spawned whole-brain workers before B2."""
    output = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True)
    return [int(line.split(None, 1)[0]) for line in output.splitlines()
            if "from multiprocessing.spawn import spawn_main" in line]


def _rss_mib(pids: list[int]) -> float:
    """Sum sampled resident KiB over the live B2 worker PIDs, returning MiB."""
    if not pids:
        return 0.0
    result = subprocess.run(["ps", "-o", "rss=", "-p", ",".join(map(str, pids))],
                            capture_output=True, text=True)
    return sum(float(line.strip()) for line in result.stdout.splitlines() if line.strip()) / 1024


def _b2_input() -> Path:
    """Write a seeds-1-to-4 derivative of the committed acceptance file to ignored cache."""
    source = ROOT / "data/experiments/acceptance-wt-mph-buridan-distractor.json"
    document = read_json(source)
    if document["layers"]["background"] or not document["layers"]["dopamine_A"] or not document["layers"]["transporter_C"]:
        raise ValueError("B2 needs the final bare acceptance substrate")
    document["seeds"] = [1, 2, 3, 4]
    document["name"] += "-b2"
    path = ROOT / ".cache/wp9-b2-experiment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n")
    return path


def _b2_precondition() -> dict[str, Any]:
    """Apply the orchestrator's amended B2 gate before any four-worker start."""
    pids = _other_engine_pids()
    swap = _swap_used_mib()
    free = _memory_free_percent()
    result = {"other_engine_pids": pids, "swap_used_mib": swap, "memory_free_percent": free}
    print("B2 precondition: " + json.dumps(result), flush=True)
    if pids or swap > 3000 or free < 50:
        raise RuntimeError("B2 precondition not met")
    return result


def _run_b2_leg(experiment_path: Path, workers: int) -> dict[str, Any]:
    """Run one B2 leg and sample summed worker RSS and swap every five wall seconds."""
    from flyonenomics.store import ResultsStore
    before = {path.name for path in (ROOT / "runs").glob("*/")}
    log_path = ROOT / ".cache" / f"wp9-b2-workers-{workers}.log"
    log = log_path.open("w")
    started = time.monotonic()
    process = subprocess.Popen([sys.executable, str(ROOT / "scripts/run_experiment.py"),
                                str(experiment_path), "--workers", str(workers)],
                               cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy())
    directory: Path | None = None
    first_probe_elapsed_s: float | None = None
    next_sample = started
    samples: list[dict[str, Any]] = []
    stop_reason: str | None = None
    try:
        while True:
            now = time.monotonic()
            if directory is None:
                candidates = [path for path in (ROOT / "runs").glob("*/")
                              if path.name not in before and (path / "status.json").is_file()]
                if len(candidates) == 1:
                    directory = candidates[0]
                elif len(candidates) > 1:
                    raise RuntimeError("multiple new B2 runs appeared")
            status: dict[str, Any] = {}
            if directory is not None:
                try:
                    status = read_json(directory / "status.json")
                except (OSError, ValueError):
                    pass
                if status.get("state") == "running" and first_probe_elapsed_s is None:
                    first_probe_elapsed_s = float(status["wall_time_s"])
            if now >= next_sample:
                pids = status.get("worker_pids", [])
                sample = {"elapsed_s": round(now - started, 3),
                          "worker_rss_mib": _rss_mib(pids), "swap_used_mib": _swap_used_mib(),
                          "worker_pids": pids}
                samples.append(sample)
                print("B2 sample: " + json.dumps(sample), flush=True)
                next_sample = now + 5
                if sample["swap_used_mib"] > 3800 and stop_reason is None:
                    stop_reason = "swap used exceeded 3800 MiB"
                    if directory is not None:
                        ResultsStore(ROOT / "runs").cancel(directory.name)
            if process.poll() is not None:
                break
            time.sleep(.1)
        process.wait()
        if directory is None:
            raise RuntimeError("B2 exited without a run directory; see " + str(log_path))
        status = read_json(directory / "status.json")
        if stop_reason is None and process.returncode != 0:
            stop_reason = "worker killed" if "worker killed" in status.get("traceback", "") else "run failed"
        result: dict[str, Any] = {"workers": workers, "run_id": directory.name,
                                  "returncode": process.returncode, "state": status.get("state"),
                                  "stop_reason": stop_reason, "log_path": str(log_path),
                                  "samples": samples,
                                  "peak_worker_rss_mib": max((row["worker_rss_mib"] for row in samples), default=0),
                                  "peak_swap_used_mib": max((row["swap_used_mib"] for row in samples), default=0)}
        if status.get("state") == "done" and (directory / "manifest.json").is_file():
            manifest = read_json(directory / "manifest.json")
            document = read_json(experiment_path)
            duration = {arm["label"]: {i: phase["duration_s"] for i, phase in enumerate(arm["protocol"])
                                        if phase["type"] == "probe"} for arm in document["arms"]}
            settle = []
            brain_s = 0.0
            for path in directory.glob("arm-*/seed-*/probe-*-settle.json"):
                arm = path.parents[1].name.removeprefix("arm-")
                index = int(path.stem.split("-")[1])
                seconds = float(read_json(path)["settle_s"])
                settle.append(seconds)
                brain_s += seconds + duration[arm][index]
            if not settle or first_probe_elapsed_s is None:
                raise RuntimeError("B2 missing settle or probe-phase timing")
            t_probe = (manifest["wall_times"]["total_s"] -
                       manifest["wall_times"]["aggregation_s"] - first_probe_elapsed_s)
            result.update({"t_probe_s": t_probe, "brain_s": brain_s,
                           "q2": t_probe / brain_s, "mean_settle_s": sum(settle) / len(settle),
                           "t_build_s": manifest["wall_times"]["process_start_to_initial_store_s"],
                           "engine_build_s": manifest["wall_times"]["max_worker_build_s"],
                           "t_agg_s": manifest["wall_times"]["aggregation_s"],
                           "first_probe_elapsed_s": first_probe_elapsed_s,
                           "total_wall_s": manifest["wall_times"]["total_s"]})
        return result
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=30)
        log.close()


def run_b2() -> dict[str, Any]:
    """Execute four-worker B2 once, with the specified memory fallback if needed."""
    precondition = _b2_precondition()
    path = _b2_input()
    first = _run_b2_leg(path, 4)
    legs = [first]
    if first["stop_reason"] in ("swap used exceeded 3800 MiB", "worker killed"):
        legs.append(_run_b2_leg(path, 2))
    elif first["stop_reason"] is None and first["peak_worker_rss_mib"] > 20 * 1024:
        legs.append(_run_b2_leg(path, 3))
    result = {"precondition": precondition, "legs": legs,
              "selected": legs[-1] if legs[-1]["state"] == "done" else None}
    output = ROOT / ".cache/wp9-b2-results.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("B2 result: " + str(output), flush=True)
    if result["selected"] is None:
        raise RuntimeError("B2 did not complete; see " + str(output))
    return result


def _variable_array(owner: Any, name: str) -> np.ndarray:
    """Return one Brian2 variable array without a unit conversion copy."""
    return owner.variables[name].get_value()


def _array_row(label: str, array: np.ndarray) -> dict[str, Any]:
    """Describe one array: bytes, dtype and shape."""
    return {"label": label, "nbytes": int(array.nbytes), "dtype": str(array.dtype),
            "shape": [int(n) for n in array.shape]}


def run_footprint_probe() -> dict[str, Any]:
    """Build one v783 worker and report where memory sits after store('initial').

    Units: bytes and MiB. Shapes: one process, one built network. Does not
    spawn multiprocessing workers.
    """
    import gc
    import tracemalloc

    import numpy as np
    import pandas as pd

    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.engine.brian_engine import cache_dir
    from flyonenomics.types import ConnectomeFiles, load_params

    gc.collect()
    tracemalloc.start()
    snap0 = tracemalloc.take_snapshot()
    t0 = time.perf_counter()
    base = cache_dir() / "Drosophila_brain_model"
    engine = BrianEngine()
    engine.seed(20260912)
    engine.build(
        ConnectomeFiles(base / "Completeness_783.csv", base / "Connectivity_783.parquet", version="783"),
        load_params(),
        InputTopology(),
    )
    build_s = time.perf_counter() - t0
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    snap1 = tracemalloc.take_snapshot()
    top = [{"file": st.traceback[0].filename, "line": st.traceback[0].lineno,
            "size_mib": round(st.size / 1024 ** 2, 3)}
           for st in snap1.compare_to(snap0, "lineno")[:12]]
    syn = engine._syn
    neu = engine._neu
    spk = engine._spk
    net = engine._net
    rows = [
        _array_row("syn.i", _variable_array(syn, "i")),
        _array_row("syn.j", _variable_array(syn, "j")),
        _array_row("syn.w", _variable_array(syn, "w")),
        _array_row("engine._base_w_mv", np.asarray(engine._base_w_mv)),
        _array_row("engine._rfc_base_ms", np.asarray(engine._rfc_base_ms)),
        _array_row("neu.v", _variable_array(neu, "v")),
        _array_row("neu.g", _variable_array(neu, "g")),
        _array_row("spk.count", _variable_array(spk, "count")),
        _array_row("root_ids", np.asarray(engine.root_ids)),
    ]
    frames = []
    ndarrays = []
    for obj in gc.get_objects():
        if isinstance(obj, pd.DataFrame):
            frames.append({"columns": list(obj.columns)[:8], "nbytes": int(obj.memory_usage(deep=True).sum()),
                           "shape": list(obj.shape)})
        elif isinstance(obj, np.ndarray) and obj.nbytes >= 10 * 1024 * 1024:
            ndarrays.append(_array_row("gc.ndarray", obj))
    rss_kib = float(subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())], text=True).strip() or 0)
    footprint_text = ""
    footprint_cmd = subprocess.run(["footprint", "-p", str(os.getpid())], capture_output=True, text=True)
    if footprint_cmd.returncode == 0:
        footprint_text = footprint_cmd.stdout[-4000:]
    result: dict[str, Any] = {
        "pid": os.getpid(),
        "n": engine.n,
        "n_syn": engine.n_syn,
        "build_s": build_s,
        "tracemalloc_current_mib": current / 1024 ** 2,
        "tracemalloc_peak_mib": peak / 1024 ** 2,
        "rss_mib": rss_kib / 1024,
        "network_stored_keys": list(getattr(net, "_stored_state", getattr(net, "stored_states", {})) or []),
        "arrays": rows,
        "pandas_frames": frames,
        "large_ndarrays_mib": [{"label": r["label"], "nbytes": r["nbytes"], "dtype": r["dtype"],
                                "shape": r["shape"]} for r in ndarrays],
        "tracemalloc_top": top,
        "footprint_tail": footprint_text,
        "base_w_mv_flags": {"owndata": bool(np.asarray(engine._base_w_mv).flags.owndata),
                            "writeable": bool(np.asarray(engine._base_w_mv).flags.writeable)},
    }
    print(json.dumps({k: v for k, v in result.items() if k != "footprint_tail"}, indent=2))
    print(footprint_text)
    dest = ROOT / ".reports" / "WP11-footprint-probe.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n")
    match = re.search(r"phys_footprint:\s*([0-9]+)\s*MB", footprint_text)
    if match:
        from flyonenomics.orchestrator.budget import record_footprint_bytes
        record_footprint_bytes(int(match.group(1)) * 1024 * 1024)
    return result


def run_footprint_scaling() -> dict[str, Any]:
    """Measure per-worker footprint and wall at 4, 8, 12 and the budget maximum.

    Units: MiB and wall seconds. Spawns engine workers; call only when the
    machine rule allows the requested counts.
    """
    from flyonenomics.orchestrator.budget import recommend_workers

    sugar = read_json(ROOT / "data/experiments/sugar-reflex.json")
    sugar["arms"] = sugar["arms"][:1]
    sugar["seeds"] = list(range(1, 13))
    sugar["name"] = "wp11-footprint"
    maximum = recommend_workers()
    counts = sorted({n for n in (4, 8, 12, maximum) if n >= 1})
    runs_root = ROOT / ".cache" / "wp11-footprint-runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    legs = []
    for workers in counts:
        document = json.loads(json.dumps(sugar))
        path = ROOT / ".cache" / f"wp11-footprint-{workers}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2) + "\n")
        before = {p.name for p in runs_root.glob("*/")}
        log_path = ROOT / ".cache" / f"wp11-footprint-{workers}.log"
        started = time.monotonic()
        with log_path.open("w") as log:
            process = subprocess.Popen(
                [sys.executable, str(ROOT / "scripts/run_experiment.py"), str(path),
                 "--workers", str(workers), "--runs-dir", str(runs_root)],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy(),
            )
            samples: list[dict[str, Any]] = []
            directory: Path | None = None
            try:
                while process.poll() is None:
                    if directory is None:
                        found = [p for p in runs_root.glob("*/")
                                 if p.name not in before and (p / "status.json").is_file()]
                        if len(found) == 1:
                            directory = found[0]
                    pids: list[int] = []
                    if directory is not None:
                        try:
                            pids = read_json(directory / "status.json").get("worker_pids") or []
                        except (OSError, ValueError):
                            pids = []
                    samples.append({"elapsed_s": round(time.monotonic() - started, 3),
                                    "worker_rss_mib": _rss_mib(pids), "swap_used_mib": _swap_used_mib(),
                                    "n_pids": len(pids)})
                    time.sleep(5)
                process.wait()
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=30)
        wall_s = time.monotonic() - started
        peak = max((row["worker_rss_mib"] for row in samples), default=0.0)
        n_live = max((row["n_pids"] for row in samples), default=0)
        per_worker = peak / n_live if n_live else 0.0
        legs.append({"workers": workers, "returncode": process.returncode, "wall_s": wall_s,
                     "peak_worker_rss_mib": peak, "per_worker_rss_mib": per_worker,
                     "peak_swap_used_mib": max((row["swap_used_mib"] for row in samples), default=0.0),
                     "run_id": directory.name if directory is not None else None,
                     "log_path": str(log_path)})
    result = {"legs": legs, "budget_max": maximum}
    dest = ROOT / ".reports" / "WP11-footprint-scaling.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return result


def run_b1_rest(drive_path: str | None = None) -> dict[str, Any]:
    """Engine-only B1 on an actual selected rest configuration, 20 brain s.

    The shared lease is one engine. No candidate is invented if the drive is
    absent. The measured configuration bytes are recorded with the result.
    """
    from flyonenomics.drive import rest_calibration as rest
    path = Path(drive_path) if drive_path else rest._drive()
    if rest.development() and drive_path is None:
        # Development R4 selects the committed development file itself.
        selection = read_json(rest._rec() / "R4.json") if (rest._rec() / "R4.json").is_file() else {}
        if selection.get("status") != "passed" or rest._sha(rest.DEV_SOURCE) != selection["source"]["sha256"]:
            raise ValueError("development B1-rest requires the passed development R4 selection")
        path = rest.DEV_SOURCE
    if not path.is_file():
        selection = rest._rec() / "R4.json"
        if drive_path is not None or not selection.is_file():
            raise ValueError("B1-rest requires the selected rest configuration; waiting for WP17")
        r4 = read_json(selection)
        if r4.get("status") != "passed":
            raise ValueError("B1-rest requires passed R4 selection")
        # Benchmark the selected common-weight bytes before K1r tunes them.
        # This cache fixture is not the final configuration freeze.
        document, _, _ = rest._candidate_drive(r4["candidate"])
        path = ROOT / ".cache/wp19-b1-candidate.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        import yaml
        path.write_text(yaml.safe_dump(document, sort_keys=False))
    from flyonenomics.drive.rest import load_drive_rest
    load_drive_rest(path)
    result = rest.run_jobs([{"kind": "B1-rest", "seed": 1, "drive_path": str(path.resolve())}], workers="auto")
    result["configuration_sha256"] = rest._sha(path)
    result["q1"] = result["rows"][0]["q1"]
    result["above_escalation_threshold"] = result["q1"] > 30
    result.update(rest._class_fields())
    from flyonenomics.store.results import atomic_json
    atomic_json(rest._rec() / "B1-rest.json", result)
    return result


def run_b2_rest(workers: str = "auto") -> dict[str, Any]:
    """Section 6.4: B2-rest is Q-rest itself, at the granted auto concurrency."""
    from flyonenomics.drive.rest_calibration import run_qrest
    if workers != "auto":
        raise ValueError("B2-rest uses the shared auto worker budget")
    return run_qrest()


def plan_experiment(path: str | Path, *, settle_s: float | None = None) -> dict[str, Any]:
    """Expand an experiment's section 6.3 factors without loading an engine.

    Units: brain seconds; counts of arms, seeds, and expanded probes. Waits
    advance slow state only and contribute no engine time. Unlike wall-budget
    planning, this uses budget.plan_settle_s (2 s), not settle.max_s.
    """
    from flyonenomics.schema import load_experiment
    from flyonenomics.types import load_params

    experiment = load_experiment(path)
    if settle_s is None:
        params = load_params(ROOT / "data/params-v0.2.yaml")
        settle_s = float(params.get("budget.plan_settle_s"))
    if not __import__("math").isfinite(settle_s) or settle_s < 0:
        raise ValueError("planning settle must be finite and nonnegative")
    arms = []
    for arm in experiment.arms:
        probes = [{"phase": index, "assay": phase.assay,
                   "duration_s": float(phase.duration_s)}
                  for index, phase in enumerate(arm.expanded()) if phase.type == "probe"]
        arms.append({"label": arm.label, "probes": len(probes),
                     "per_probe": probes,
                     "brain_s_per_seed": sum(p["duration_s"] + settle_s for p in probes)})
    return {"arms": len(arms), "seeds": len(experiment.seeds),
            "seed_ids": list(experiment.seeds), "planning_settle_s": settle_s,
            "probes": sum(a["probes"] for a in arms),
            "expanded_probes": len(experiment.seeds) * sum(a["probes"] for a in arms),
            "per_arm": arms,
            "brain_s": len(experiment.seeds) * sum(a["brain_s_per_seed"] for a in arms)}


MECH_SUB_TIER = {"sfa": "T3a", "std": "T3b", "cbi": "T3c"}
MECH_W1_BRAIN_S = 12.0
MECH_W2_BRAIN_S = 10.0
MECH_RECORD = ROOT / "validation" / "records" / "p2"


def _phys_footprint_mib() -> float:
    """Peak process phys_footprint in MiB, with ru_maxrss fallback."""
    import resource

    footprint_cmd = subprocess.run(
        ["footprint", "-p", str(os.getpid())], capture_output=True, text=True
    )
    match = re.search(r"phys_footprint:\s*([0-9.]+)\s*M", footprint_cmd.stdout or "")
    if match:
        return float(match.group(1))
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return rss / (1024 * 1024)
    return rss / 1024


def _mech_section(tag: str, setting_name: str):
    """Resolved Mechanisms and drive section for one B-mech setting, or both None."""
    from flyonenomics.drive.mechanisms import mask_sha256, mechanisms_from_section, real_scope_mask
    from flyonenomics.drive.rest_tier3 import BLOCK_NAME, ENGINE_MODEL, grid_extremes, section_for_unit

    if setting_name == "off":
        return None, None
    sub = MECH_SUB_TIER[tag]
    weak, strong = grid_extremes(sub)
    chosen = weak if setting_name == "weak" else strong
    unit = {"sub_tier": sub, "setting": chosen, "baseline": False, "engine_model": ENGINE_MODEL[sub]}
    block_name = BLOCK_NAME[sub]
    digest = None
    n = None
    if block_name != "conductance_inhibition":
        mask = real_scope_mask(chosen["scope"])
        digest = mask_sha256(mask)
        n = int(mask.shape[0])
    section = section_for_unit(unit, mask_digest=digest)
    return mechanisms_from_section(section, n=n or 1), section


def run_mech_worker(tag: str, setting_name: str, workload: str) -> dict[str, Any]:
    """One B-mech process: one cold build, then three warm repeats.

    Units: seconds and spike counts. Shapes: scalars and short lists.
    """
    from flyonenomics.drive.rest_map import Setting, _build_engine, _probe

    mechs, section = _mech_section(tag, setting_name)
    t_build = time.perf_counter()
    if workload == "w1":
        built = _build_engine(Setting(3.0, 6.0), mechanisms=mechs, mechanisms_section=section)
        brain_s = MECH_W1_BRAIN_S
    else:
        built = _build_engine(
            Setting(1.0, 1.0), mode="extended", feedforward=True,
            mechanisms=mechs, mechanisms_section=section,
        )
        brain_s = MECH_W2_BRAIN_S
    build_s = time.perf_counter() - t_build
    peak = _phys_footprint_mib()
    walls: list[float] = []
    spikes: list[float] = []
    for _repeat in range(4):
        started = time.perf_counter()
        spike_total = 0.0
        if workload == "w1":
            row = _probe(built, 1.15, 1, seconds=10.0)
            groups = built["groups"]
            spike_total = sum(
                float(row["rates_hz"][name]) * len(idx) * 10.0 for name, idx in groups.items()
            )
        else:
            silent = _probe(built, 0.0, 1, seconds=3.0)
            sugar = _probe(built, 0.0, 1, seconds=3.0, active=True)
            groups = built["groups"]
            spike_total = sum(
                (float(silent["rates_hz"][name]) + float(sugar["rates_hz"][name])) * len(idx) * 3.0
                for name, idx in groups.items()
            )
        walls.append(time.perf_counter() - started)
        spikes.append(spike_total)
        peak = max(peak, _phys_footprint_mib())
    per_brain = [wall / brain_s for wall in walls]
    result: dict[str, Any] = {
        "tag": tag,
        "setting": setting_name,
        "workload": workload,
        "build_s": build_s,
        "brain_s": brain_s,
        "cold_wall_s": walls[0],
        "warm_wall_s": walls[1:],
        "wall_per_brain_s": per_brain,
        "warm_wall_per_brain_s": per_brain[1:],
        "spike_count": spikes,
        "peak_phys_footprint_mib": peak,
        "engine_model": built["engine"].engine_model(),
        "n": float(built["engine"].n),
    }
    print(json.dumps(result))
    return result


def run_mech(tag: str) -> dict[str, Any]:
    """Run B-mech for one engine-model tag. Units: seconds. Shapes: nested mappings."""
    from statistics import median

    from flyonenomics.orchestrator.budget import acquire_engine_slots
    from flyonenomics.store.results import atomic_json

    if tag not in MECH_SUB_TIER:
        raise ValueError("B-mech tag must be sfa, std or cbi")
    legs: dict[str, dict[str, Any]] = {}
    with acquire_engine_slots(1):
        for workload in ("w1", "w2"):
            for setting_name in ("off", "weak", "strong"):
                proc = subprocess.run(
                    [sys.executable, __file__, "--mech-worker",
                     tag, setting_name, workload],
                    cwd=str(ROOT), capture_output=True, text=True, check=False,
                )
                if proc.returncode != 0:
                    raise RuntimeError(
                        f"B-mech {tag} {workload} {setting_name} failed: "
                        f"{proc.stdout[-1000:]} {proc.stderr[-2000:]}"
                    )
                line = proc.stdout.strip().splitlines()[-1]
                legs[f"{workload}-{setting_name}"] = json.loads(line)
    ratios: list[float] = []
    for workload in ("w1", "w2"):
        off_med = median(legs[f"{workload}-off"]["warm_wall_per_brain_s"])
        for setting_name in ("weak", "strong"):
            on_med = median(legs[f"{workload}-{setting_name}"]["warm_wall_per_brain_s"])
            ratios.append(on_med / off_med if off_med > 0 else 1.0)
    rho = max(1.0, max(ratios))
    record = {
        "class": "development",
        "tag": tag,
        "engine_model": {"sfa": "lif+sfa", "std": "lif+std", "cbi": "lif+cbi"}[tag],
        "rho_mech": rho,
        "ratios": ratios,
        "legs": legs,
    }
    dest = MECH_RECORD / f"bench-mech-{tag}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(dest, record)
    print(json.dumps({"rho_mech": rho, "path": str(dest), "ratios": ratios}, indent=2))
    return record


def main() -> None:
    """Entry point for scripts/bench.py. Units: none. Shapes: scalars."""
    parser = argparse.ArgumentParser(description="flyonenomics benchmarks B1, B2, footprint and B-mech")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--b1-rest", action="store_true", help="B1 on a selected rest configuration")
    group.add_argument("--b2-rest", action="store_true", help="Q-rest measured as B2-rest, workers auto")
    group.add_argument("--plan", metavar="FILE", help="section 6.3 factors, no engine")
    group.add_argument("--b1", action="store_true", help="run benchmark B1")
    group.add_argument("--b1-worker", action="store_true", help="single B1 process")
    group.add_argument("--b2", action="store_true", help="acceptance B2, four workers with memory monitor")
    group.add_argument("--footprint-probe", action="store_true",
                       help="one-process post-build footprint breakdown")
    group.add_argument("--footprint", action="store_true",
                       help="per-worker footprint and wall at 4, 8, 12 and budget max")
    group.add_argument("--mech", choices=("sfa", "std", "cbi"), help="B-mech for one engine-model tag")
    group.add_argument("--mech-worker", nargs=3, metavar=("TAG", "SETTING", "WORKLOAD"),
                       help="single B-mech process")
    parser.add_argument("--workers", default="auto", choices=("auto",), help="shared budget for rest benchmarks")
    parser.add_argument("--drive", help="YAML drive table for nonzero B1 background weights")
    args = parser.parse_args()
    if args.b1_rest:
        print(json.dumps(run_b1_rest(args.drive), indent=2))
    elif args.b2_rest:
        print(json.dumps(run_b2_rest(args.workers), indent=2))
    elif args.plan:
        print(json.dumps(plan_experiment(args.plan), indent=2))
    elif args.b1_worker:
        run_b1_worker(args.drive)
    elif args.b1:
        results = run_b1(args.drive)
        print(json.dumps(results, indent=2))
    elif args.b2:
        run_b2()
    elif args.footprint_probe:
        run_footprint_probe()
    elif args.footprint:
        run_footprint_scaling()
    elif args.mech_worker:
        tag, setting_name, workload = args.mech_worker
        run_mech_worker(tag, setting_name, workload)
    elif args.mech:
        run_mech(args.mech)


if __name__ == "__main__":
    main()
