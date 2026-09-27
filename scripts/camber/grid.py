#!/usr/bin/env python3
"""Run the 27-setting three-seed sensitivity grid on one Camber node.

Overrides travel only through FLYONENOMICS_PARAM_OVERRIDES_JSON in each
child. This process never writes data/params-v0.1.yaml.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flyonenomics.io import read_bytes, read_text
from flyonenomics.neuromod.protocols import sensitivity_protocols
from flyonenomics.store import ResultsStore
from flyonenomics.types import load_params
from flyonenomics.validation.level3 import sensitivity_grid

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "grid"
WORKERS_PER_SETTING = 4
# Concurrent settings; each runs WORKERS_PER_SETTING engines. No default: main() refuses to start without it.
MAX_CONCURRENT = int(os.environ.get("CAMBER_GRID_CONCURRENT", "0"))


def summed_engine_rss_mib() -> float:
    """Sum RSS of experiment workers from /proc; MiB, 0 if not Linux."""
    proc = Path("/proc")
    if not proc.is_dir():
        return 0.0
    page = os.sysconf("SC_PAGE_SIZE")
    total = 0
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmd = read_bytes(entry / "cmdline")
        except OSError:
            continue
        if b"run_experiment.py" not in cmd and b"spawn_main" not in cmd:
            continue
        try:
            pages = int(read_text(entry / "statm").split()[1])
        except (OSError, ValueError, IndexError):
            continue
        total += pages * page
    return total / (1024 * 1024)


def store_roots(index: int) -> list[Path]:
    """Candidate ResultsStore roots: isolated first, then the shared first-wave dir."""
    return [OUT / "stores" / f"{index:02d}", OUT / "runs"]


def existing_record(index: int, group: str, level: str, overrides: dict[str, float],
                    experiment_path: Path) -> dict[str, object] | None:
    """Return a completed validated record if this setting already has a run."""
    run_id = f"camber-grid-{index:02d}"
    for root in store_roots(index):
        store = ResultsStore(root)
        run_dir = store.run_path(run_id)
        if not run_dir.is_dir():
            continue
        errors = store.validate_run(run_id)
        if errors:
            continue
        return {
            "index": index,
            "group": group,
            "level": level,
            "overrides": overrides,
            "experiment": str(experiment_path),
            "run_id": run_id,
            "runs_dir": str(root),
            "validation_errors": errors,
            "wall_s": 0.0,
            "returncode": 0,
            "log": str(OUT / f"{index:02d}.log"),
            "skipped": True,
        }
    return None


def run_setting(index: int, group: str, level: str, overrides: dict[str, float],
                experiment_path: Path) -> dict[str, object]:
    """Run one setting in a child with isolated overrides; seconds and paths."""
    reused = existing_record(index, group, level, overrides, experiment_path)
    if reused is not None:
        print(f"GRID SKIP {index:02d}", flush=True)
        return reused
    run_id = f"camber-grid-{index:02d}"
    runs_dir = OUT / "stores" / f"{index:02d}"
    runs_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["FLYONENOMICS_PARAM_OVERRIDES_JSON"] = json.dumps(overrides, sort_keys=True)
    env["PYTHONUNBUFFERED"] = "1"
    log_path = OUT / f"{index:02d}.log"
    started = time.monotonic()
    with log_path.open("w") as log:
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_experiment.py"),
                str(experiment_path),
                "--workers",
                str(WORKERS_PER_SETTING),
                "--runs-dir",
                str(runs_dir),
                "--run-id",
                run_id,
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    store = ResultsStore(runs_dir)
    run_dir = store.run_path(run_id)
    errors: list[str]
    if run_dir.is_dir():
        errors = store.validate_run(run_id)
    else:
        errors = ["no run directory"]
    return {
        "index": index,
        "group": group,
        "level": level,
        "overrides": overrides,
        "experiment": str(experiment_path),
        "run_id": run_id,
        "runs_dir": str(runs_dir),
        "validation_errors": errors,
        "wall_s": round(time.monotonic() - started, 3),
        "returncode": process.returncode,
        "log": str(log_path),
        "skipped": False,
    }


def main() -> None:
    """Build 27 protocol files and run them in waves of MAX_CONCURRENT settings."""
    if MAX_CONCURRENT < 1:
        raise SystemExit("set CAMBER_GRID_CONCURRENT: it caps concurrent settings "
                         f"({WORKERS_PER_SETTING} engines each)")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "experiments").mkdir(exist_ok=True)
    (OUT / "runs").mkdir(exist_ok=True)
    params = load_params()
    settings = sensitivity_grid(params)
    protocols = sensitivity_protocols(params)
    if len(settings) != 27 or len(protocols) != 27:
        raise RuntimeError(f"expected 27 settings, got {len(settings)} {len(protocols)}")
    jobs: list[tuple[int, str, str, dict[str, float], Path]] = []
    for index, (setting, (experiment, overrides)) in enumerate(zip(settings, protocols, strict=True)):
        if setting["overrides"] != overrides:
            raise RuntimeError(f"override mismatch at {index}")
        document = experiment.model_dump(mode="json")
        document["name"] = f"dose-series-sensitivity-{index:02d}"
        document["description"] = (
            f"Isolated sensitivity setting {index:02d}: {setting['group']} {setting['level']}"
        )
        document["meta"] = {
            "sensitivity_group": setting["group"],
            "sensitivity_level": setting["level"],
            "parameter_overrides": overrides,
        }
        path = OUT / "experiments" / f"{index:02d}.json"
        path.write_text(json.dumps(document, indent=2) + "\n")
        jobs.append((index, setting["group"], setting["level"], overrides, path))

    results: list[dict[str, object] | None] = [None] * 27
    peak_rss = 0.0
    started = time.monotonic()
    print(
        f"GRID start concurrent={MAX_CONCURRENT} workers_per_setting={WORKERS_PER_SETTING}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
        futures = [
            pool.submit(run_setting, index, group, level, overrides, path)
            for index, group, level, overrides, path in jobs
        ]
        unfinished = set(futures)
        while unfinished:
            peak_rss = max(peak_rss, summed_engine_rss_mib())
            ready = [fut for fut in unfinished if fut.done()]
            if not ready:
                time.sleep(10)
                continue
            for fut in ready:
                unfinished.remove(fut)
                record = fut.result()
                results[int(record["index"])] = record
                (OUT / "grid-results.json").write_text(
                    json.dumps([row for row in results if row is not None], indent=2) + "\n"
                )
                print("GRID RESULT " + json.dumps(record), flush=True)

    wall = round(time.monotonic() - started, 3)
    missing = [i for i, row in enumerate(results) if row is None]
    if missing:
        raise RuntimeError(f"missing results for settings {missing}")
    failures = [
        row["index"]
        for row in results
        if row["returncode"] != 0 or row["validation_errors"]
    ]
    summary = {
        "n_settings": 27,
        "concurrent": MAX_CONCURRENT,
        "workers_per_setting": WORKERS_PER_SETTING,
        "wall_s": wall,
        "peak_engine_rss_mib": round(peak_rss, 3),
        "failures": failures,
        "results": results,
    }
    (OUT / "grid-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("GRID SUMMARY " + json.dumps({k: summary[k] for k in ("n_settings", "wall_s", "peak_engine_rss_mib", "failures")}), flush=True)
    if failures:
        raise SystemExit(f"grid settings failed: {failures}")


if __name__ == "__main__":
    main()
