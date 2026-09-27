#!/usr/bin/env python3
"""Build MaleCNS v1.0 through the production adapter and step 1 s dark."""
from __future__ import annotations

import json
import platform
import resource
import subprocess
import time
from pathlib import Path

from flyonenomics.datasets import MALE_VERSION, cache_dir, get_dataset_adapter
from flyonenomics.engine.base import InputTopology
from flyonenomics.io import read_text
from flyonenomics.engine.brian_engine import BrianEngine
from flyonenomics.types import load_params

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260921


def peak_rss_bytes() -> int:
    """Return this process's peak RSS in bytes on macOS and Linux."""
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if platform.system() == "Darwin" else value * 1024)


def swap_provenance() -> str:
    """Return the platform's swap status without changing it."""
    if platform.system() == "Darwin":
        return subprocess.run(
            ["sysctl", "vm.swapusage"], capture_output=True, text=True, check=True
        ).stdout.strip()
    rows = {}
    for line in read_text("/proc/meminfo").splitlines():
        key, _, value = line.partition(":")
        if key in {"SwapTotal", "SwapFree"}:
            rows[key] = value.strip()
    return ", ".join(f"{key}: {rows.get(key, 'unknown')}" for key in ("SwapTotal", "SwapFree"))


def main() -> int:
    adapter = get_dataset_adapter(MALE_VERSION)
    files = adapter.connectome_files()
    params = load_params(ROOT / "data" / "params-v0.2.yaml")
    engine = BrianEngine()
    started = time.perf_counter()
    engine.build(files, params, InputTopology())
    build_wall_s = time.perf_counter() - started
    peak_after_build = peak_rss_bytes()
    engine.seed(SEED)
    started = time.perf_counter()
    result = engine.run_chunk(1000.0)
    run_wall_s = time.perf_counter() - started
    payload = {
        "dataset": MALE_VERSION,
        "purpose": "adapter build/runtime check, not calibration",
        "seed": SEED,
        "duration_s": 1.0,
        "dark": True,
        "inputs": "none",
        "parameters": "unchanged data/params-v0.2.yaml",
        "graph_nodes": engine.n,
        "graph_edges": engine.n_syn,
        "build_wall_s": build_wall_s,
        "run_wall_s": run_wall_s,
        "peak_rss_bytes_after_build": peak_after_build,
        "peak_rss_bytes_after_run": peak_rss_bytes(),
        "spikes": int(result.counts.sum()),
        "firing_neurons": int((result.counts > 0).sum()),
        "engine_model": engine.engine_model(),
        "method": engine.method(),
        "dt_ms": engine.dt_ms,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "swap": swap_provenance(),
        },
        "interpretation": "The fly does not see. This is a zero-input graph build and runtime check only.",
    }
    output = cache_dir() / "malecns-v1.0" / "probe.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
