#!/usr/bin/env python3
"""Camber resting-state map (SPEC items 35, 43, 45, 68). Engine API only.

Stage 1 shards by photoreceptor sign. Each (g_gaba, g_glu) pair is one
process with its own engine. No shared SQLite. Writes parquet and NDJSON
under results/resting-map/<sign>/.

--aggregate ranks pulled tables on the Mac (pandas only).
--confirm rebuilds candidates on Camber for the 30 s, sugar, and stripe legs.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from flyonenomics.io import read_json, read_parquet

ROOT = Path(__file__).resolve().parents[2]
G_VALUES = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0)
WEIGHTS_MV = tuple(round(0.70 + 0.05 * i, 2) for i in range(19))
SEEDS = (1, 2, 3)
CONFIRM_SEEDS = tuple(range(1, 11))
SETTLE_S = 2.0
MEASURE_S = 10.0
CONFIRM_MEASURE_S = 30.0
FIRST_LAST_WINDOW_S = 1.0
GRADE_RATE_MAX_FACTOR = 3.0
CENTRAL_MAX_HZ = 8.0
FANO_MAX = 3.0
BIN_FRACTION_MAX = 0.05
STABILITY_MIN_RATIO = 0.5
STABILITY_MAX_RATIO = 2.0
SUGAR_RATE_HZ = 150.0
SUGAR_DURATION_S = 1.0
STRIPE_RATE_HZ = 300.0
MN9_BASELINE_HZ = (86.0, 53.0)
RATE_NAMES = (
    "central", "DAN", "PAM", "PPL1", "KC", "ER", "descending", "optic",
    "L1", "Mi1", "Tm3", "MN9",
)
STRIPE_RATE_NAMES = ("L1", "Mi1", "Tm3", "T4", "T5", "LC_all", "DNa02_L", "DNa02_R")
WP3B_FIRST_ACTIVE = {
    1.0: {"weight_mv": 0.787346, "central_hz": 3.462, "F": 491.34},
    2.0: {"weight_mv": 0.812091, "central_hz": 6.227, "F": 5.05},
    3.0: {"weight_mv": 0.812091, "central_hz": 4.094, "F": 2.89},
    4.0: {"weight_mv": 0.812091, "central_hz": 2.993, "F": 14.97},
    6.0: {"weight_mv": 0.807080, "central_hz": 2.674, "F": 8.71},
    8.0: {"weight_mv": 0.807080, "central_hz": 2.062, "F": 6.90},
}


def _pairs() -> list[tuple[float, float]]:
    """Return the 36 (g_gaba, g_glu) pairs; scales dimensionless."""
    return [(g_gaba, g_glu) for g_gaba in G_VALUES for g_glu in G_VALUES]


def _git_commit() -> str:
    """Return HEAD sha if git exists, else the staged evaluation commit."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("FLYONENOMICS_CODE_SCOPE", "4e0220f")


def _job_id() -> str:
    """Job id from the environment if Camber or the submitter set one."""
    return os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID") or ""


def split_scale(signs: np.ndarray, pre: np.ndarray, nt: np.ndarray,
                g_gaba: float, g_glu: float, r16_idx: np.ndarray,
                histamine: bool) -> np.ndarray:
    """GABA/glutamate inhibitory split, optional R1-6 sign flip.

    Glutamate inhibitory synapses take g_glu. Every other inhibitory
    synapse takes g_gaba, so the diagonal matches WP3b global g_inh.
    Histamine multiplies currently excitatory R1-6 outgoing synapses by -1.
    Units: dimensionless. Shapes: (n_syn,).
    """
    scale = np.ones(len(signs), dtype=np.float32)
    inh = signs < 0
    glu = inh & (nt == "glutamate")
    scale[inh] = np.float32(g_gaba)
    scale[glu] = np.float32(g_glu)
    if histamine and r16_idx.size:
        from_r16 = np.isin(pre, r16_idx)
        flip = from_r16 & (signs > 0)
        scale[flip] = -np.abs(scale[flip])
    return scale


def _rate_indices(registry: Any, overlay: dict[str, Any]) -> dict[str, np.ndarray]:
    """Engine indices for recorded populations. Shapes: each (group size,)."""
    from flyonenomics.drive.background import group_indices

    indices = dict(group_indices(registry))
    indices["PAM"] = registry.population("PAM").idx
    indices["PPL1"] = registry.population("PPL1").idx
    indices["MN9"] = registry.population("MN9").idx
    for name in ("L1", "Mi1", "Tm3", "R1_6", "T4", "T5", "LC_all"):
        indices[name] = overlay[name].idx
    indices["DNa02_L"] = registry.population("DNa02_L").idx
    indices["DNa02_R"] = registry.population("DNa02_R").idx
    return indices


def _load_connectivity_and_nt(registry: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Parquet pre indices, signs, and presynaptic top_nt. Shapes (n_syn,)."""
    from flyonenomics.engine.brian_engine import resolve_connectome_path
    from flyonenomics.registry.annotations import load_annotations
    from flyonenomics.validation.level0 import connectome

    path = resolve_connectome_path(connectome("783").connectivity)
    frame = read_parquet(
        path,
        columns=["Presynaptic_Index", "Postsynaptic_Index", "Excitatory x Connectivity"],
    ).to_pandas()
    pre = frame["Presynaptic_Index"].to_numpy(dtype=np.int32)
    signs = frame["Excitatory x Connectivity"].to_numpy(dtype=np.float64)
    annotations = load_annotations("v2.1.0").set_index("root_id").reindex(registry.root_ids)
    neuron_nt = annotations["top_nt"].to_numpy()
    syn_nt = np.array(
        [str(neuron_nt[i]).strip().lower() if pd.notna(neuron_nt[i]) else "" for i in pre],
        dtype=object,
    )
    return pre, signs, syn_nt


def _point_ok(row: dict[str, Any]) -> bool:
    """Item 43/35 point gates except gradedness. Rates Hz, F dimensionless."""
    fano = row.get("F")
    ratio = row.get("stability_ratio")
    return (
        fano is not None
        and float(fano) < FANO_MAX
        and float(row["max_bin_fraction"]) < BIN_FRACTION_MAX
        and ratio is not None
        and STABILITY_MIN_RATIO <= float(ratio) <= STABILITY_MAX_RATIO
        and float(row["central_hz"]) <= CENTRAL_MAX_HZ
    )


def _violation(row: dict[str, Any], next_central: float | None) -> float:
    """Item 35 objective: sum of relative gate misses. Lower is closer."""
    fano = row.get("F")
    fano_v = 0.0 if fano is None else max(0.0, float(fano) - FANO_MAX) / FANO_MAX
    frac_v = max(0.0, float(row["max_bin_fraction"]) - BIN_FRACTION_MAX) / BIN_FRACTION_MAX
    ratio = row.get("stability_ratio")
    if ratio is None or not np.isfinite(ratio) or float(ratio) <= 0:
        stab_v = 1.0
    else:
        log_r = abs(np.log(float(ratio)))
        log_ok = abs(np.log(STABILITY_MAX_RATIO))
        stab_v = max(0.0, log_r - log_ok) / log_ok if log_ok else 0.0
    central_v = max(0.0, float(row["central_hz"]) - CENTRAL_MAX_HZ) / CENTRAL_MAX_HZ
    if next_central is None:
        grade_v = 1.0
    else:
        own = max(float(row["central_hz"]), 1e-9)
        grade_v = max(0.0, float(next_central) / own - GRADE_RATE_MAX_FACTOR) / GRADE_RATE_MAX_FACTOR
    return float(fano_v + frac_v + stab_v + central_v + grade_v)


def _measure(engine: Any, indices: dict[str, np.ndarray], params: Any,
             weight_mv: float, seed: int, measure_s: float) -> dict[str, Any]:
    """Restore, settle, measure. Units mV, Hz, seconds."""
    from flyonenomics.drive.background import DEFAULT_SEED
    from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
    from flyonenomics.validation.artefacts import FanoAccumulator

    began = time.perf_counter()
    engine.restore("initial")
    engine.seed(_brian_seed(DEFAULT_SEED, seed, 0))
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
    chunks = round(measure_s * 1000 / chunk_ms)
    window_chunks = round(FIRST_LAST_WINDOW_S * 1000 / chunk_ms)
    for position in range(chunks):
        result = engine.run_chunk(chunk_ms)
        counts += result.counts
        detector.add(result.hist_1ms)
        if position < window_chunks:
            first_central += int(result.counts[indices["central"]].sum())
        if position >= chunks - window_chunks:
            last_central += int(result.counts[indices["central"]].sum())
    rates = {name: float(counts[indices[name]].mean() / measure_s)
             for name in RATE_NAMES if name in indices and indices[name].size}
    first_hz = first_central / (indices["central"].size * FIRST_LAST_WINDOW_S)
    last_hz = last_central / (indices["central"].size * FIRST_LAST_WINDOW_S)
    ratio = last_hz / first_hz if first_hz else None
    synchrony = detector.report()
    record = {
        "weight_mv": weight_mv,
        "seed": seed,
        "measure_s": measure_s,
        "central_hz": rates.get("central", 0.0),
        "F": synchrony["F"],
        "max_bin_fraction": synchrony["max_bin_fraction"],
        "synchrony_status": synchrony["status"],
        "first_central_hz": first_hz,
        "last_central_hz": last_hz,
        "stability_ratio": ratio,
        "wall_s": round(time.perf_counter() - began, 3),
    }
    for name in RATE_NAMES:
        record[f"{name}_hz"] = rates.get(name, 0.0)
    record["point_ok"] = _point_ok(record)
    return record


def _build_stage1_engine(g_gaba: float, g_glu: float, sign: str) -> dict[str, Any]:
    """One engine, scale applied, base snapshot stored. Units: scales dimensionless."""
    from flyonenomics.drive.background import DEFAULT_SEED
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
    from flyonenomics.registry import annotations as ann
    from flyonenomics.registry import build_registry
    from flyonenomics.types import load_params
    from flyonenomics.validation.level0 import connectome
    from flyonenomics.diagnostics.visual_path import resolve_overlay

    params = load_params()
    registry = build_registry("783")
    overlay = resolve_overlay(ann.load_annotations("v2.1.0"), ann.load_engine_order("783"))
    pre, signs, syn_nt = _load_connectivity_and_nt(registry)
    r16 = overlay["R1_6"].idx
    scale = split_scale(signs, pre, syn_nt, g_gaba, g_glu, r16, sign == "histamine")
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params, InputTopology(background=True))
    if signs.shape != (engine.n_syn,):
        raise ValueError("parquet connection order and engine synapse count differ")
    engine.set_weight_scale(scale)
    engine.set_threshold(np.full(engine.n, float(params.get("lif.v_th"))))
    engine.set_gain(np.ones(engine.n))
    indices = _rate_indices(registry, overlay)
    initial_background = np.full(engine.n, WEIGHTS_MV[0], dtype=np.float64)
    initial_background[indices["sensory"]] = 0.0
    engine.set_background(initial_background)
    engine.store("initial")
    inh = signs < 0
    glu = inh & (syn_nt == "glutamate")
    census = {
        "n_syn": int(engine.n_syn),
        "n_inh": int(inh.sum()),
        "n_glu_inh": int(glu.sum()),
        "n_gaba_like_inh": int(inh.sum() - glu.sum()),
        "n_r16_flip": int((np.isin(pre, r16) & (signs > 0)).sum()) if sign == "histamine" else 0,
    }
    return {"engine": engine, "params": params, "indices": indices, "census": census}


def run_pair(payload: dict[str, Any]) -> dict[str, Any]:
    """One (g_gaba, g_glu, sign) process: 19 weights × 3 seeds. No shared store."""
    g_gaba = float(payload["g_gaba"])
    g_glu = float(payload["g_glu"])
    sign = str(payload["sign"])
    out_dir = Path(payload["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"gaba{g_gaba:g}-glu{g_glu:g}"
    ndjson_path = out_dir / f"{stem}.ndjson"
    parquet_path = out_dir / f"{stem}.parquet"
    meta = {
        "kind": "pair",
        "g_gaba": g_gaba,
        "g_glu": g_glu,
        "sign": sign,
        "job_id": _job_id(),
        "commit": _git_commit(),
        "code_scope": "4e0220f",
        "platform": "camber-large",
        "n_bg": 100,
        "r_bg_hz": 10.0,
        "settle_s": SETTLE_S,
        "measure_s": MEASURE_S,
    }
    rows: list[dict[str, Any]] = []
    with ndjson_path.open("w") as handle:
        handle.write(json.dumps({**meta, "kind": "pair-start"}, allow_nan=False) + "\n")
        handle.flush()
        built = _build_stage1_engine(g_gaba, g_glu, sign)
        handle.write(json.dumps({**meta, "kind": "census", **built["census"]},
                                allow_nan=False) + "\n")
        handle.flush()
        engine = built["engine"]
        for weight in WEIGHTS_MV:
            for seed in SEEDS:
                record = {
                    **meta,
                    "kind": "evaluation",
                    **_measure(engine, built["indices"], built["params"], weight, seed, MEASURE_S),
                }
                rows.append(record)
                handle.write(json.dumps(record, allow_nan=False) + "\n")
                handle.flush()
    frame = pd.DataFrame(rows)
    frame.to_parquet(parquet_path, index=False)
    return {"parquet": str(parquet_path), "ndjson": str(ndjson_path), "n": len(rows),
            "g_gaba" : g_gaba, "g_glu": g_glu, "sign": sign}


def _warmup_compile() -> None:
    """Fill the on-disk Cython cache before the worker pool starts."""
    from flyonenomics.drive.background import DEFAULT_SEED
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
    from flyonenomics.types import load_params
    from flyonenomics.validation.level0 import connectome

    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), load_params(), InputTopology(background=True))
    del engine


def run_shard(sign: str, workers: int, out_dir: Path, pair_slice: slice) -> None:
    """Run one photoreceptor-sign shard with one process per scale pair."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = _pairs()[pair_slice]
    print(json.dumps({"kind": "shard-start", "sign": sign, "n_pairs": len(pairs),
                      "workers": workers, "job_id": _job_id(), "commit": _git_commit()}),
          flush=True)
    _warmup_compile()
    payloads = [{"g_gaba": g_gaba, "g_glu": g_glu, "sign": sign, "out_dir": str(out_dir)}
                for g_gaba, g_glu in pairs]
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_pair, payload) for payload in payloads]
        for future in as_completed(futures):
            result = future.result()
            done += 1
            print(json.dumps({"kind": "pair-done", **result, "done": done,
                              "n_pairs": len(pairs)}), flush=True)
    parts = sorted(out_dir.glob("gaba*-glu*.parquet"))
    if not parts:
        raise SystemExit("no pair parquet files written")
    combined = pd.concat((read_parquet(path).to_pandas() for path in parts), ignore_index=True)
    combined.to_parquet(out_dir / "evaluations.parquet", index=False)
    combined.to_csv(out_dir / "evaluations.csv", index=False)
    print(json.dumps({"kind": "shard-done", "sign": sign, "n_eval": int(len(combined)),
                      "parquet": str(out_dir / "evaluations.parquet")}), flush=True)


def _seed_pair_ok(seed_frame: pd.DataFrame, i: int) -> bool:
    """True if weights i and i+1 pass and weight i+2 is graded, one seed."""
    if i + 2 >= len(seed_frame):
        return False
    left = seed_frame.iloc[i].to_dict()
    mid = seed_frame.iloc[i + 1].to_dict()
    right = seed_frame.iloc[i + 2]
    if not (_point_ok(left) and _point_ok(mid)):
        return False
    return float(right["central_hz"]) < GRADE_RATE_MAX_FACTOR * float(mid["central_hz"])


def rank_combinations(frame: pd.DataFrame) -> pd.DataFrame:
    """Rank (g_gaba, g_glu, sign) by item 35/43. One row per combination."""
    rows: list[dict[str, Any]] = []
    grouped = frame.groupby(["g_gaba", "g_glu", "sign"], sort=True)
    for (g_gaba, g_glu, sign), block in grouped:
        best_violation = float("inf")
        best_pair: tuple[float, float] | None = None
        candidate = False
        n_ok_pairs = 0
        for i in range(len(WEIGHTS_MV) - 2):
            w0, w1 = WEIGHTS_MV[i], WEIGHTS_MV[i + 1]
            seed_ok = []
            seed_v = []
            for seed, seed_block in block.groupby("seed"):
                ordered = seed_block.sort_values("weight_mv").reset_index(drop=True)
                ok = _seed_pair_ok(ordered, i)
                seed_ok.append(ok)
                left = ordered.iloc[i].to_dict()
                nxt = float(ordered.iloc[i + 1]["central_hz"])
                seed_v.append(_violation(left, nxt))
            if all(seed_ok):
                candidate = True
                n_ok_pairs += 1
            mean_v = float(np.mean(seed_v)) if seed_v else float("inf")
            if mean_v < best_violation:
                best_violation = mean_v
                best_pair = (w0, w1)
        at = block[block["weight_mv"] == (best_pair[0] if best_pair else WEIGHTS_MV[0])]
        rows.append({
            "g_gaba": float(g_gaba),
            "g_glu": float(g_glu),
            "sign": sign,
            "candidate": candidate,
            "n_ok_pairs": n_ok_pairs,
            "best_weight_mv": None if best_pair is None else best_pair[0],
            "best_pair_mv": None if best_pair is None else list(best_pair),
            "item35_violation": best_violation,
            "mean_central_hz": float(at["central_hz"].mean()) if len(at) else None,
            "mean_F": float(pd.to_numeric(at["F"], errors="coerce").mean()) if len(at) else None,
        })
    ranked = pd.DataFrame(rows).sort_values(
        ["candidate", "item35_violation", "mean_central_hz"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
    return ranked


def diagonal_check(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Compare model-sign diagonal nearest-weight central/F to WP3b first-active."""
    reports: list[dict[str, Any]] = []
    model = frame[frame["sign"] == "model"]
    for g_inh, expected in WP3B_FIRST_ACTIVE.items():
        sub = model[(model["g_gaba"] == g_inh) & (model["g_glu"] == g_inh)]
        if sub.empty:
            reports.append({"g_inh": g_inh, "status": "missing"})
            continue
        target = expected["weight_mv"]
        sub = sub.copy()
        sub["dw"] = (sub["weight_mv"] - target).abs()
        nearest_w = float(sub.loc[sub["dw"].idxmin(), "weight_mv"])
        at = sub[sub["weight_mv"] == nearest_w]
        reports.append({
            "g_inh": g_inh,
            "wp3b_weight_mv": target,
            "nearest_weight_mv": nearest_w,
            "wp3b_central_hz": expected["central_hz"],
            "map_mean_central_hz": float(at["central_hz"].mean()),
            "wp3b_F": expected["F"],
            "map_mean_F": float(pd.to_numeric(at["F"], errors="coerce").mean()),
            "n_seeds": int(len(at)),
        })
    return reports


def run_aggregate(in_dir: Path, out_dir: Path) -> None:
    """Rank pulled shard tables. Pandas only. No engine import."""
    parts = sorted(in_dir.glob("**/evaluations.parquet")) + sorted(in_dir.glob("**/*.parquet"))
    frames = []
    seen: set[str] = set()
    for path in parts:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        frame = read_parquet(path).to_pandas()
        if "g_gaba" not in frame.columns or "kind" in frame.columns and not len(frame):
            continue
        if "central_hz" not in frame.columns:
            continue
        frames.append(frame)
    if not frames:
        raise SystemExit(f"no evaluation parquet under {in_dir}")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["g_gaba", "g_glu", "sign", "weight_mv", "seed"])
    out_dir.mkdir(parents=True, exist_ok=True)
    ranked = rank_combinations(combined)
    ranked.to_csv(out_dir / "ranked.csv", index=False)
    diag = diagonal_check(combined)
    (out_dir / "diagonal.json").write_text(json.dumps(diag, indent=2) + "\n")
    candidates = ranked[ranked["candidate"]]
    if len(candidates):
        chosen = candidates.to_dict(orient="records")
        headline = f"Map: {len(candidates)} candidates"
    else:
        chosen = ranked.head(3).to_dict(orient="records")
        closest = ", ".join(
            f"gaba={r['g_gaba']:g} glu={r['g_glu']:g} {r['sign']}" for r in chosen
        )
        headline = f"Map: no candidate (closest: {closest})"
    payload = {
        "headline": headline,
        "n_eval": int(len(combined)),
        "n_candidates": int(len(candidates)),
        "confirm": chosen,
        "diagonal": diag,
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(headline, flush=True)
    print(json.dumps(payload, default=str), flush=True)


def _set_extended(engine: Any, extended_idx: np.ndarray, full: np.ndarray) -> None:
    """Write Poisson rates for extended_idx from a full-n vector. Units Hz."""
    engine.set_input_rates(full[extended_idx].astype(np.float64))


def _run_window_counts(engine: Any, seconds: float, chunk_ms: float) -> np.ndarray:
    """Advance without changing inputs. Returns spike counts (n,)."""
    counts = np.zeros(engine.n, dtype=np.int64)
    for _ in range(round(seconds * 1000 / chunk_ms)):
        counts += engine.run_chunk(chunk_ms).counts.astype(np.int64)
    return counts


def _build_confirm_engine(g_gaba: float, g_glu: float, sign: str,
                          weight_mv: float) -> dict[str, Any]:
    """Engine with background plus sugar and R1-6 extended banks."""
    from flyonenomics.drive.background import DEFAULT_SEED
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
    from flyonenomics.registry import annotations as ann
    from flyonenomics.registry import build_registry
    from flyonenomics.types import load_params
    from flyonenomics.validation.level0 import connectome
    from flyonenomics.diagnostics.visual_path import resolve_overlay

    params = load_params()
    registry = build_registry("783")
    annotations = ann.load_annotations("v2.1.0")
    overlay = resolve_overlay(annotations, ann.load_engine_order("783"))
    pre, signs, syn_nt = _load_connectivity_and_nt(registry)
    r16 = overlay["R1_6"].idx
    scale = split_scale(signs, pre, syn_nt, g_gaba, g_glu, r16, sign == "histamine")
    sugar = np.sort(registry.population("sugar_GRN_R").idx)
    extended = np.unique(np.concatenate([sugar, overlay["R1_6"].idx])).astype(np.int32)
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params,
                 InputTopology(extended_idx=extended, background=True))
    engine.set_weight_scale(scale)
    engine.set_threshold(np.full(engine.n, float(params.get("lif.v_th"))))
    engine.set_gain(np.ones(engine.n))
    indices = _rate_indices(registry, overlay)
    background = np.full(engine.n, weight_mv, dtype=np.float64)
    background[indices["sensory"]] = 0.0
    engine.set_background(background)
    engine.set_input_rates(np.zeros(len(extended), dtype=np.float64))
    engine.store("initial")
    return {
        "engine": engine,
        "params": params,
        "indices": indices,
        "extended": extended,
        "sugar": sugar,
        "overlay": overlay,
        "annotations": annotations,
        "weight_mv": weight_mv,
        "background": background,
    }


def run_confirm_one(payload: dict[str, Any]) -> dict[str, Any]:
    """30 s × 10 seeds, sugar on/off, three 300 Hz stripes. One candidate."""
    from flyonenomics.diagnostics.visual_path import extended_rates, site_preferred

    g_gaba = float(payload["g_gaba"])
    g_glu = float(payload["g_glu"])
    sign = str(payload["sign"])
    weight_mv = float(payload["weight_mv"])
    out_dir = Path(payload["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    built = _build_confirm_engine(g_gaba, g_glu, sign, weight_mv)
    engine = built["engine"]
    params = built["params"]
    chunk_ms = float(params.get("engine.chunk_ms"))
    rest_rows = []
    for seed in CONFIRM_SEEDS:
        row = _measure(engine, built["indices"], params, weight_mv, seed, CONFIRM_MEASURE_S)
        rest_rows.append(row)
        print(json.dumps({"kind": "confirm-rest", "g_gaba": g_gaba, "g_glu": g_glu,
                          "sign": sign, **{k: row[k] for k in ("seed", "central_hz", "F",
                          "max_bin_fraction", "stability_ratio", "wall_s")}}),
              flush=True)

    sugar_rows = []
    mn9 = built["indices"]["MN9"]
    for background_on in (True, False):
        for seed in CONFIRM_SEEDS:
            pair = []
            for active in (False, True):
                engine.restore("initial")
                if background_on:
                    engine.set_background(built["background"])
                else:
                    engine.set_background(np.zeros(engine.n, dtype=np.float64))
                full = np.zeros(engine.n, dtype=np.float64)
                if active:
                    full[built["sugar"]] = SUGAR_RATE_HZ
                _set_extended(engine, built["extended"], full)
                from flyonenomics.drive.background import DEFAULT_SEED
                from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
                engine.seed(_brian_seed(DEFAULT_SEED, seed, 0))
                _run_window_counts(engine, SETTLE_S, chunk_ms)
                counts = _run_window_counts(engine, SUGAR_DURATION_S, chunk_ms)
                pair.append(float(counts[mn9].mean() / SUGAR_DURATION_S))
            sugar_rows.append({
                "background_on": background_on,
                "seed": seed,
                "mn9_silent_hz": pair[0],
                "mn9_sugar_hz": pair[1],
                "mn9_difference_hz": pair[1] - pair[0],
            })

    from flyonenomics.types import load_params
    sigma = float(load_params().get("vis.sigma_vis"))
    site_idx, preferred = site_preferred(
        "R1_6", built["overlay"], built["annotations"], params,
    )
    stripe_rows = []
    for azimuth in ("-45", "45", "full"):
        rates = extended_rates(
            built["extended"], site_idx, preferred, azimuth=azimuth,
            rate_hz=STRIPE_RATE_HZ, sigma_deg=sigma, multiplier=1.0,
            uniform=(azimuth == "full"),
        )
        engine.restore("initial")
        engine.set_background(built["background"])
        engine.set_input_rates(rates)
        from flyonenomics.drive.background import DEFAULT_SEED
        from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
        engine.seed(_brian_seed(DEFAULT_SEED, 1, 0))
        _run_window_counts(engine, SETTLE_S, chunk_ms)
        counts = _run_window_counts(engine, MEASURE_S, chunk_ms)
        means = {name: float(counts[built["indices"][name]].mean() / MEASURE_S)
                 for name in STRIPE_RATE_NAMES if name in built["indices"]}
        stripe_rows.append({"azimuth": azimuth, "rate_hz": STRIPE_RATE_HZ, **{
            f"{name}_hz": means.get(name, 0.0) for name in STRIPE_RATE_NAMES
        }})
        print(json.dumps({"kind": "confirm-stripe", "g_gaba": g_gaba, "g_glu": g_glu,
                          "sign": sign, "azimuth": azimuth, **means}), flush=True)

    result = {
        "g_gaba": g_gaba,
        "g_glu": g_glu,
        "sign": sign,
        "weight_mv": weight_mv,
        "rest": rest_rows,
        "sugar": sugar_rows,
        "stripes": stripe_rows,
        "mn9_baseline_hz": list(MN9_BASELINE_HZ),
        "rest_all_item43": all(_point_ok(row) for row in rest_rows),
    }
    path = out_dir / f"confirm-gaba{g_gaba:g}-glu{g_glu:g}-{sign}.json"
    path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return result


def run_confirm(in_dir: Path, out_dir: Path, workers: int) -> None:
    """Confirm ranked candidates (or three closest) from summary.json."""
    summary_path = in_dir / "summary.json"
    if not summary_path.is_file():
        run_aggregate(in_dir, in_dir)
    summary = read_json(summary_path)
    chosen = summary["confirm"]
    out_dir.mkdir(parents=True, exist_ok=True)
    payloads = []
    for row in chosen:
        weight = row.get("best_weight_mv")
        if weight is None:
            continue
        payloads.append({
            "g_gaba": row["g_gaba"],
            "g_glu": row["g_glu"],
            "sign": row["sign"],
            "weight_mv": weight,
            "out_dir": str(out_dir),
        })
    results = []
    with ProcessPoolExecutor(max_workers=max(1, min(workers, len(payloads) or 1))) as pool:
        futures = [pool.submit(run_confirm_one, payload) for payload in payloads]
        for future in as_completed(futures):
            results.append(future.result())
    (out_dir / "confirm.json").write_text(json.dumps(results, indent=2, default=str) + "\n")
    print(json.dumps({"kind": "confirm-done", "n": len(results)}), flush=True)


def _parse_slice(text: str | None) -> slice:
    """Parse start:end pair indices (half-open)."""
    if not text:
        return slice(None)
    start_s, end_s = text.split(":", 1)
    start = int(start_s) if start_s else None
    end = int(end_s) if end_s else None
    return slice(start, end)


def main() -> None:
    """CLI: shard, aggregate, or confirm."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", choices=("model", "histamine"))
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--workers", type=int, default=None,
                        help="concurrent engine processes; required for --shard and --confirm")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--in-dir", type=Path, default=None)
    parser.add_argument("--pair-slice", type=str, default=None,
                        help="half-open start:end over the 36 pairs")
    args = parser.parse_args()
    if args.aggregate:
        in_dir = args.in_dir or (ROOT / "camber-runs" / "resting-map")
        out_dir = args.out or in_dir
        run_aggregate(in_dir, out_dir)
        return
    if (args.shard or args.confirm) and (args.workers is None or args.workers < 1):
        parser.error("--workers is required: it caps concurrent whole-brain engines")
    if args.confirm:
        in_dir = args.in_dir or (ROOT / "results" / "resting-map")
        out_dir = args.out or (ROOT / "results" / "resting-map" / "confirm")
        run_confirm(in_dir, out_dir, args.workers)
        return
    if not args.shard:
        parser.error("one of --shard, --aggregate, --confirm is required")
    out_dir = args.out or (ROOT / "results" / "resting-map" / args.shard)
    os.environ.setdefault("CAMBER_JOB_ID", os.environ.get("CAMBER_JOB_ID", ""))
    run_shard(args.shard, args.workers, out_dir, _parse_slice(args.pair_slice))


if __name__ == "__main__":
    import multiprocessing as mp
    try:
        mp.set_start_method("spawn")
    except RuntimeError:
        pass
    main()
