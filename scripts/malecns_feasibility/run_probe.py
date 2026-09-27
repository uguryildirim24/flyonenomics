#!/usr/bin/env python3
"""Run one second of bare dark activity on the MaleCNS feasibility graph."""
from __future__ import annotations

import json
import platform
import resource
import subprocess
import time

import numpy as np

from common import COMPLETENESS, CONNECTIONS, CACHE, METADATA, write_json
from flyonenomics.engine.base import InputTopology
from flyonenomics.engine.brian_engine import BrianEngine
from flyonenomics.io import read_json
from flyonenomics.types import ConnectomeFiles, load_params

OUT = CACHE / "probe.json"
SEED = 20260921


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB.
    return int(value if platform.system() == "Darwin" else value * 1024)


def main() -> int:
    graph = read_json(METADATA)
    engine = BrianEngine()
    before = time.perf_counter()
    engine.build(
        ConnectomeFiles(completeness=COMPLETENESS, connectivity=CONNECTIONS, version="783"),
        load_params(),
        InputTopology(),
    )
    build_wall_s = time.perf_counter() - before
    peak_after_build = peak_rss_bytes()
    engine.seed(SEED)
    before = time.perf_counter()
    result = engine.run_chunk(1000.0)
    run_wall_s = time.perf_counter() - before
    peak_after_run = peak_rss_bytes()
    firing = result.counts > 0
    payload = {
        "dataset": "male-cns:v1.0",
        "purpose": "cost probe, not calibration",
        "engine": "flyonenomics BrianEngine lif, Cython backend",
        "seed": SEED,
        "duration_s": 1.0,
        "dark": True,
        "inputs": "none: no upstream banks, extended input, spike list, or background",
        "parameters": "unchanged data/params-v0.2.yaml",
        "graph_nodes": int(engine.n),
        "graph_edges": int(engine.n_syn),
        "build_wall_s": build_wall_s,
        "run_wall_s": run_wall_s,
        "peak_rss_bytes_after_build": peak_after_build,
        "peak_rss_bytes_after_run": peak_after_run,
        "spikes": int(result.counts.sum()),
        "firing_neurons": int(firing.sum()),
        "firing_fraction": float(firing.mean()),
        "engine_model": engine.engine_model(),
        "method": engine.method(),
        "dt_ms": engine.dt_ms,
        "graph_sign_coverage_fraction": graph["nodes_with_signed_consensus"] / graph["nodes"],
        "unknown_sign_policy": "unclear/missing consensus transmitter has zero outgoing weight",
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "swap": subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True, check=True).stdout.strip(),
        },
        "interpretation": "The fly does not see. Zero input and rest initialization make this only a graph-build/runtime probe.",
    }
    write_json(OUT, payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
