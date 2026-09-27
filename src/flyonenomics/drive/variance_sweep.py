"""Exploratory background-variance sweep, separate from the K1 drive record."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time

import numpy as np

from flyonenomics.drive.background import DEFAULT_SEED, group_indices
from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
from flyonenomics.engine import BrianEngine, InputTopology
from flyonenomics.registry import build_registry
from flyonenomics.types import load_params
from flyonenomics.validation.artefacts import FanoAccumulator
from flyonenomics.validation.level0 import connectome

SWEEP_N_BG = (10, 20)
SWEEP_WEIGHT_RANGES_MV = {10: (1.0, 6.0), 20: (0.5, 3.0)}
SWEEP_POINTS = 6
SWEEP_MEASURE_S = 3.0
SWEEP_WALL_CAP_S = 1740.0


def _measure(n_bg: int) -> None:
    """Build one v783 network and log six common weights; units mV/Hz, shapes (n,)."""
    params = copy.deepcopy(load_params())
    params.data["bg"]["n_bg"]["value"] = n_bg
    registry = build_registry("783")
    indices = group_indices(registry)
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params, InputTopology(background=True))
    chunk_ms = float(params.get("engine.chunk_ms"))
    settle_chunks = round(float(params.get("settle.min_s")) * 1000 / chunk_ms)
    measure_chunks = round(SWEEP_MEASURE_S * 1000 / chunk_ms)
    low, high = SWEEP_WEIGHT_RANGES_MV[n_bg]
    for position, weight in enumerate(np.geomspace(low, high, SWEEP_POINTS), start=1):
        started = time.perf_counter()
        engine.restore("initial")
        engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
        engine.set_threshold(np.full(engine.n, float(params.get("lif.v_th"))))
        engine.set_gain(np.ones(engine.n))
        vector = np.full(engine.n, float(weight))
        vector[indices["sensory"]] = 0.0
        engine.set_background(vector)
        for _ in range(settle_chunks):
            engine.run_chunk(chunk_ms)
        counts = np.zeros(engine.n, dtype=np.int64)
        fano = FanoAccumulator(engine.n, params)
        for _ in range(measure_chunks):
            result = engine.run_chunk(chunk_ms)
            counts += result.counts
            fano.add(result.hist_1ms)
        rates = {name: float(counts[idx].mean() / SWEEP_MEASURE_S)
                 for name, idx in indices.items()}
        print(json.dumps({"n_bg": n_bg, "r_bg_hz": float(params.get("bg.r_bg")),
                          "point": position, "weight_mv": float(weight),
                          "rates_hz": rates, "synchrony": fano.report(),
                          "wall_s": round(time.perf_counter() - started, 3)}), flush=True)


def main() -> None:
    """Run the two one-engine children sequentially; units wall seconds, JSON rows."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-bg", type=int, choices=SWEEP_N_BG)
    args = parser.parse_args()
    if args.n_bg is not None:
        _measure(args.n_bg)
        return
    began = time.perf_counter()
    for n_bg in SWEEP_N_BG:
        remaining = SWEEP_WALL_CAP_S - (time.perf_counter() - began)
        if remaining <= 0:
            print(json.dumps({"status": "wall cap reached", "n_bg_skipped": n_bg}), flush=True)
            break
        try:
            proc = subprocess.run([sys.executable, "-m", "flyonenomics.drive.variance_sweep",
                                   "--n-bg", str(n_bg)], timeout=remaining, check=False)
        except subprocess.TimeoutExpired:
            print(json.dumps({"status": "wall cap reached", "n_bg_interrupted": n_bg}), flush=True)
            break
        if proc.returncode:
            print(json.dumps({"status": "child failed", "n_bg": n_bg,
                              "exit_code": proc.returncode}), flush=True)
            break


if __name__ == "__main__":
    main()
