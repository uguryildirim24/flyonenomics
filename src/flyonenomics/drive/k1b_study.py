"""WP3b inhibitory-ratio composition and bounded transition map on v783."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from flyonenomics.drive.background import DEFAULT_SEED, group_indices, weight_scale
from flyonenomics.io import read_parquet
from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
from flyonenomics.registry import build_registry
from flyonenomics.registry.annotations import load_annotations
from flyonenomics.types import load_params

# Study mechanics and decision bounds are named from tasks/WP3b.md.
G_INH_VALUES = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0)
G_INH_LANE_A = (1.0, 3.0, 6.0)
G_INH_LANE_B = (2.0, 4.0, 8.0)
COMMON_MIN_MV = 0.70
COMMON_MAX_MV = 1.40
COMMON_POINTS = 8
TRANSITION_BISECTIONS = 4
SETTLE_S = 2.0
MEASURE_S = 5.0
LOW_SIDE_RATE_MAX_HZ = 3.0
AMENDED_CENTRAL_MAX_HZ = 8.0  # Orchestrator amendment, 2026-09-13
STABILITY_MIN_RATIO = 0.5
STABILITY_MAX_RATIO = 2.0
GRADE_RATE_MAX_FACTOR = 3.0
FIRST_LAST_WINDOW_S = 1.0
TOP_INHIBITORY_SOURCES = 10
STUDY_WALL_CAP_S = 7.5 * 3600
EXTRA_N_BG = 10
EXTRA_MIN_MV = 1.0
EXTRA_MAX_MV = 6.0
ROOT = Path(__file__).resolve().parents[3]
COMMON_LOG = ROOT / ".reports/k1b-map.log"


def _emit(record: dict[str, Any], *, shared: bool = False) -> None:
    """Print one JSON record and optionally append to shared map log; units per field."""
    line = json.dumps(record, allow_nan=False) + "\n"
    print(line, end="", flush=True)
    if shared:
        descriptor = os.open(COMMON_LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(descriptor, line.encode())
        finally:
            os.close(descriptor)


def _signed_connectivity() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read parquet order; units indices and signed synapse counts, shapes (n_syn,)."""
    from flyonenomics.engine.brian_engine import resolve_connectome_path
    from flyonenomics.validation.level0 import connectome
    path = resolve_connectome_path(connectome("783").connectivity)
    frame = read_parquet(path, columns=["Presynaptic_Index", "Postsynaptic_Index",
                                           "Excitatory x Connectivity"]).to_pandas()
    return (frame["Presynaptic_Index"].to_numpy(dtype=np.int32),
            frame["Postsynaptic_Index"].to_numpy(dtype=np.int32),
            frame["Excitatory x Connectivity"].to_numpy(dtype=np.float64))


def composition() -> dict[str, Any]:
    """Summarize (n_syn,) edges as connection counts, mV sums, and group scalars."""
    params = load_params()
    registry = build_registry("783")
    groups = group_indices(registry)
    pre, post, signed = _signed_connectivity()
    abs_mv = np.abs(signed) * float(params.get("lif.w_syn"))
    inhibitory = signed < 0
    excitatory = signed > 0
    counts = {"inhibitory": int(inhibitory.sum()), "excitatory": int(excitatory.sum()),
              "zero": int((signed == 0).sum()), "total": int(signed.size)}
    sums = {"inhibitory": float(abs_mv[inhibitory].sum()),
            "excitatory": float(abs_mv[excitatory].sum()),
            "total": float(abs_mv.sum())}
    names = list(groups)
    group_of = np.empty(registry.n, dtype=np.int16)
    for number, name in enumerate(names):
        group_of[groups[name]] = number
    post_group = group_of[post]
    all_in = np.bincount(post_group, weights=abs_mv, minlength=len(names))
    inh_in = np.bincount(post_group[inhibitory], weights=abs_mv[inhibitory], minlength=len(names))
    shares = {name: {"neurons": int(groups[name].size),
                     "all_in_mv": float(all_in[number]),
                     "inhibitory_in_mv": float(inh_in[number]),
                     "inhibitory_share": float(inh_in[number] / all_in[number]) if all_in[number] else None}
              for number, name in enumerate(names)}
    annotations = load_annotations("v2.1.0").set_index("root_id")
    top: dict[str, list[dict[str, Any]]] = {}
    for name in ("KC", "central"):
        post_is_target = np.zeros(registry.n, dtype=bool)
        post_is_target[groups[name]] = True
        mask = inhibitory & post_is_target[post]
        source_total = np.bincount(pre[mask], weights=abs_mv[mask], minlength=registry.n)
        largest = np.argsort(source_total)[-TOP_INHIBITORY_SOURCES:][::-1]
        rows: list[dict[str, Any]] = []
        for idx in largest:
            root_id = int(registry.root_ids[idx])
            label = annotations.loc[root_id]
            rows.append({"root_id": root_id, "weight_mv": float(source_total[idx]),
                         "cell_type": None if pd.isna(label["cell_type"]) else str(label["cell_type"]),
                         "super_class": None if pd.isna(label["super_class"]) else str(label["super_class"])})
        top[name] = rows
    return {"connectome": "783", "w_syn_mv": float(params.get("lif.w_syn")),
            "counts": counts, "absolute_weight_mv": sums,
            "inhibitory_share_by_drive_group": shares,
            "top_inhibitory_sources": top}


def _measure(engine: Any, registry: Any, params: Any, g_inh: float, weight_mv: float,
             phase: str, number: int, n_bg: int) -> dict[str, Any]:
    """Restore and measure one candidate; units mV, Hz, seconds; arrays (n,)/(bins,)."""
    from flyonenomics.validation.artefacts import FanoAccumulator

    began = time.perf_counter()
    indices = group_indices(registry)
    engine.restore("initial")
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    weights = np.full(engine.n, weight_mv, dtype=np.float64)
    weights[indices["sensory"]] = 0.0
    engine.set_background(weights)
    chunk_ms = float(params.get("engine.chunk_ms"))
    for _ in range(round(SETTLE_S * 1000 / chunk_ms)):
        engine.run_chunk(chunk_ms)
    counts = np.zeros(engine.n, dtype=np.int64)
    detector = FanoAccumulator(engine.n, params)
    first_central = 0
    last_central = 0
    chunks = round(MEASURE_S * 1000 / chunk_ms)
    window_chunks = round(FIRST_LAST_WINDOW_S * 1000 / chunk_ms)
    for position in range(chunks):
        result = engine.run_chunk(chunk_ms)
        counts += result.counts
        detector.add(result.hist_1ms)
        if position < window_chunks:
            first_central += int(result.counts[indices["central"]].sum())
        if position >= chunks - window_chunks:
            last_central += int(result.counts[indices["central"]].sum())
    rates = {name: float(counts[idx].mean() / MEASURE_S) for name, idx in indices.items()}
    first_hz = first_central / (indices["central"].size * FIRST_LAST_WINDOW_S)
    last_hz = last_central / (indices["central"].size * FIRST_LAST_WINDOW_S)
    ratio = last_hz / first_hz if first_hz else None
    synchrony = detector.report()
    low = rates["central"] <= LOW_SIDE_RATE_MAX_HZ and synchrony["status"] != "tripped"
    stable = ratio is not None and STABILITY_MIN_RATIO <= ratio <= STABILITY_MAX_RATIO
    candidate = (rates["central"] <= AMENDED_CENTRAL_MAX_HZ
                 and synchrony["F"] is not None
                 and synchrony["F"] < float(params.get("artefact.sync_fano_max"))
                 and synchrony["max_bin_fraction"] < float(params.get("artefact.sync_bin_fraction_max"))
                 and stable)
    record = {"kind": "evaluation", "g_inh": g_inh, "n_bg": n_bg, "number": number,
              "phase": phase, "weight_mv": weight_mv, "rates_hz": rates,
              "F": synchrony["F"], "max_bin_fraction": synchrony["max_bin_fraction"],
              "synchrony_status": synchrony["status"], "first_central_hz": first_hz,
              "last_central_hz": last_hz, "stability_ratio": ratio,
              "low_for_bracket": low, "amended_point_candidate": candidate,
              "wall_s": round(time.perf_counter() - began, 3)}
    _emit(record, shared=True)
    return record


def qualifying_pairs(grid: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Screen adjacent points using each point's next-grid rate; rates Hz, weights mV."""
    return [(left, right) for left, right, following in zip(grid, grid[1:], grid[2:])
            if left["amended_point_candidate"] and right["amended_point_candidate"]
            and right["rates_hz"]["central"] < GRADE_RATE_MAX_FACTOR * left["rates_hz"]["central"]
            and following["rates_hz"]["central"] < GRADE_RATE_MAX_FACTOR * right["rates_hz"]["central"]]


def _map_lane(values: tuple[float, ...], *, n_bg: int | None = None,
              low_mv: float = COMMON_MIN_MV, high_mv: float = COMMON_MAX_MV) -> None:
    """Map several g_inh values with one built engine; units ratios/mV, group arrays."""
    from brian2 import mV
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.validation.level0 import connectome

    if len(values) != 1:
        raise ValueError("one inhibitory ratio per fresh engine process is required")
    began = time.perf_counter()
    params = load_params()
    if n_bg is None:
        n_bg = int(params.get("bg.n_bg"))
    if n_bg != int(params.get("bg.n_bg")):
        import copy
        params = copy.deepcopy(params)
        params.data["bg"]["n_bg"]["value"] = n_bg
    registry = build_registry("783")
    _, _, signs = _signed_connectivity()
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params, InputTopology(background=True))
    engine.store("base")
    if signs.shape != (engine.n_syn,):
        raise ValueError("parquet connection order and engine synapse count differ")
    indices = group_indices(registry)
    inhibitory_idx = int(np.flatnonzero(signs < 0)[0])
    for g_inh in values:
        if time.perf_counter() - began >= STUDY_WALL_CAP_S:
            _emit({"kind": "cap", "g_inh": g_inh, "reason": "study wall cap reached"})
            return
        engine.restore("base")
        engine.set_weight_scale(weight_scale(signs, g_inh))
        engine.set_threshold(np.full(engine.n, float(params.get("lif.v_th"))))
        engine.set_gain(np.ones(engine.n))
        initial_background = np.full(engine.n, low_mv, dtype=np.float64)
        initial_background[indices["sensory"]] = 0.0
        engine.set_background(initial_background)
        engine.store("initial")
        engine.restore("initial")
        # Read-only inspection of Brian2's public `w` state through the engine's
        # synapse handle; verifies that the scaled snapshot survived restore.
        assert engine._syn is not None
        observed_mv = float(engine._syn.w[inhibitory_idx] / mV)
        expected_mv = float(signs[inhibitory_idx] * params.get("lif.w_syn") * g_inh)
        if not np.isclose(observed_mv, expected_mv):
            raise AssertionError("scaled inhibitory weight did not survive initial restore")
        _emit({"kind": "scale_snapshot_check", "g_inh": g_inh,
               "synapse_index": inhibitory_idx, "expected_mv": expected_mv,
               "observed_mv": observed_mv})
        evaluations: list[dict[str, Any]] = []
        for number, weight in enumerate(np.geomspace(low_mv, high_mv, COMMON_POINTS), start=1):
            if time.perf_counter() - began >= STUDY_WALL_CAP_S:
                _emit({"kind": "cap", "g_inh": g_inh, "reason": "study wall cap reached"})
                return
            evaluations.append(_measure(engine, registry, params, g_inh, float(weight),
                                        "common grid", number, n_bg))
        accepted = [row for row in evaluations if row["low_for_bracket"]]
        rejected = [row for row in evaluations if not row["low_for_bracket"]]
        if accepted:
            lower = max(row["weight_mv"] for row in accepted)
            higher = [row["weight_mv"] for row in rejected if row["weight_mv"] > lower]
            if higher:
                upper = min(higher)
                for _ in range(TRANSITION_BISECTIONS):
                    if time.perf_counter() - began >= STUDY_WALL_CAP_S:
                        _emit({"kind": "cap", "g_inh": g_inh, "reason": "study wall cap reached"})
                        return
                    weight = float(np.sqrt(lower * upper))
                    row = _measure(engine, registry, params, g_inh, weight,
                                   "transition bisection", len(evaluations) + 1, n_bg)
                    evaluations.append(row)
                    if row["low_for_bracket"]:
                        lower = weight
                    else:
                        upper = weight
        grid = evaluations[:COMMON_POINTS]
        pairs = qualifying_pairs(grid)
        rest_pair = min(pairs, key=lambda pair: pair[0]["rates_hz"]["central"]) if pairs else None
        nonzero = [row["weight_mv"] for row in evaluations if sum(row["rates_hz"].values()) > 0]
        silent = [row["weight_mv"] for row in evaluations if sum(row["rates_hz"].values()) == 0]
        low_weights = [row["weight_mv"] for row in evaluations if row["low_for_bracket"]]
        _emit({"kind": "summary", "g_inh": g_inh, "n_bg": n_bg,
               "silent_edge_mv": max(silent) if silent else None,
               "highest_low_rate_mv": max(low_weights) if low_weights else None,
               "first_active_mv": min(nonzero) if nonzero else None,
               "rest_pair_weights_mv": [row["weight_mv"] for row in rest_pair] if rest_pair else None,
               "rest_pair_rates_hz": [row["rates_hz"] for row in rest_pair] if rest_pair else None,
               "evaluations": len(evaluations)})


def _run_lane(values: tuple[float, ...]) -> None:
    """Run ratios in fresh child engines, one at a time; ratios dimensionless."""
    for g_inh in values:
        subprocess.run([sys.executable, "-m", "flyonenomics.drive.k1b_study",
                        "--single-g", str(g_inh)], check=True)


def main() -> None:
    """Run one study mode; units mV/Hz, arrays internal (n_syn,) and (n,)."""
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--composition", action="store_true")
    group.add_argument("--map-a", action="store_true")
    group.add_argument("--map-b", action="store_true")
    group.add_argument("--single-g", type=float)
    group.add_argument("--extra-g", type=float)
    args = parser.parse_args()
    if args.composition:
        print(json.dumps(composition(), allow_nan=False, indent=2))
    elif args.map_a:
        _run_lane(G_INH_LANE_A)
    elif args.map_b:
        _run_lane(G_INH_LANE_B)
    elif args.single_g is not None:
        if args.single_g not in G_INH_VALUES:
            raise ValueError("single g_inh must be from the mapped grid")
        _map_lane((args.single_g,))
    elif args.extra_g is not None:
        if args.extra_g not in G_INH_VALUES:
            raise ValueError("extra g_inh must be from the mapped grid")
        _map_lane((args.extra_g,), n_bg=EXTRA_N_BG, low_mv=EXTRA_MIN_MV, high_mv=EXTRA_MAX_MV)


if __name__ == "__main__":
    main()
