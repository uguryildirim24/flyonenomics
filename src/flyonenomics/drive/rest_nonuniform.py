"""Sub-tier 3e non-uniform vectors. No engine equation change.

Arms are per-neuron background, postsynaptic gain, threshold offset, or
outgoing hub scale. Units: weights and thresholds mV, K synapse counts,
scales dimensionless.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np

from flyonenomics.drive.rest_map import (
    CAP,
    SEEDS,
    TARGETS,
    THRESHOLD_SEED,
    Setting,
    _cbi_row_computable,
    _mean,
    number,
    objective,
    violation,
)

HUB_TYPE_NAMES: tuple[str, ...] = ("MBON06", "LPi13", "LPi15")
COMMON_LADDER: tuple[float, ...] = (0.75, 0.80, 0.85, 0.90)
SENS_LADDER: tuple[float, ...] = (0.80, 1.00, 1.20, 1.40)
THDEG_BETAS: tuple[float, ...] = (0.5, 1.0, 2.0)
HUB_FACTORS: tuple[float, ...] = (2.0, 3.0, 4.0)
LAB_FANO_N = 2000
LAB_PAIR_N = 500
LAB_FANO_MS = 100
LAB_CORR_MS = 50
K_FLOOR = 1.0


def arm_id(arm: dict[str, Any] | None) -> str:
    """Stable arm tag for candidate ids. Units: none."""
    if not arm:
        return ""
    return str(arm.get("id") or arm.get("name") or "")


def background_vector(
    n: int,
    weight: float,
    groups: dict[str, np.ndarray],
    policy: str | None = None,
) -> np.ndarray:
    """Per-neuron background weights. Units: mV. Shape: (n,)."""
    if n < 1:
        raise ValueError("n must be positive")
    w = np.full(int(n), float(weight), dtype=np.float64)
    sensory = np.asarray(groups["sensory"], dtype=np.int32)
    w[sensory] = 0.0
    name = policy or "default"
    if name == "default":
        return w
    if name == "sens":
        out = np.zeros(int(n), dtype=np.float64)
        out[sensory] = float(weight)
        return out
    if name == "nomotor":
        w[np.asarray(groups["motor"], dtype=np.int32)] = 0.0
        return w
    raise ValueError(f"unknown background policy {name}")


def incoming_synapse_counts(post: np.ndarray, weights: np.ndarray, n: int) -> np.ndarray:
    """Incoming synapse count K_i. Units: synapses. Shape: (n,)."""
    post_idx = np.asarray(post, dtype=np.int32)
    mag = np.abs(np.asarray(weights, dtype=np.float64))
    if post_idx.shape != mag.shape or post_idx.ndim != 1:
        raise ValueError("post and weights must share one shape")
    if n < 1:
        raise ValueError("n must be positive")
    if post_idx.size and (int(post_idx.min()) < 0 or int(post_idx.max()) >= n):
        raise ValueError("post indices are out of range")
    if np.any(~np.isfinite(mag)) or np.any(mag < 0):
        raise ValueError("synapse counts must be finite and nonnegative")
    return np.bincount(post_idx, weights=mag, minlength=n).astype(np.float64)


def k_distribution(k: np.ndarray) -> dict[str, float | int]:
    """Recorded K summary. Units: synapses."""
    values = np.asarray(k, dtype=np.float64).ravel()
    positive = values[values > 0]
    median = float(np.median(positive)) if positive.size else float("nan")
    return {
        "n": int(values.size),
        "n_zero": int(np.sum(values <= 0)),
        "k_min": float(values.min()) if values.size else 0.0,
        "k_max": float(values.max()) if values.size else 0.0,
        "k_median_positive": median,
        "k_p99": float(np.percentile(values, 99)) if values.size else 0.0,
        "k_mean": float(values.mean()) if values.size else 0.0,
        "choice": "K_i is the incoming synapse count; median is over K_i > 0; K_i < 1 uses 1",
    }


def indeg_gain(k: np.ndarray, k_median: float | None = None) -> np.ndarray:
    """Postsynaptic gain 1/sqrt(K_i / K_median). Units: dimensionless. Shape: (n,)."""
    values = np.asarray(k, dtype=np.float64).ravel()
    positive = values[values > 0]
    median = float(k_median) if k_median is not None else (
        float(np.median(positive)) if positive.size else 1.0
    )
    if not np.isfinite(median) or median <= 0:
        raise ValueError("K_median must be finite and positive")
    safe = np.maximum(values, K_FLOOR)
    return (1.0 / np.sqrt(safe / median)).astype(np.float64)


def incoming_gain_scale(post: np.ndarray, gain: np.ndarray) -> np.ndarray:
    """Per-synapse scale from postsynaptic gain. Shape: (n_syn,)."""
    post_idx = np.asarray(post, dtype=np.int32)
    g = np.asarray(gain, dtype=np.float64)
    if post_idx.ndim != 1 or g.ndim != 1:
        raise ValueError("post and gain must be one-dimensional")
    if post_idx.size and (int(post_idx.min()) < 0 or int(post_idx.max()) >= g.shape[0]):
        raise ValueError("post indices are out of range")
    return np.asarray(g[post_idx], dtype=np.float64)


def threshold_offset(k: np.ndarray, beta: float) -> np.ndarray:
    """v_th offset beta * K_i / 1000. Units: mV. Shape: (n,)."""
    if not np.isfinite(beta) or beta < 0:
        raise ValueError("beta must be finite and nonnegative")
    values = np.asarray(k, dtype=np.float64).ravel()
    return (float(beta) * values / 1000.0).astype(np.float64)


def type_name_mask(cell_type: np.ndarray, hemibrain_type: np.ndarray, name: str) -> np.ndarray:
    """True where either label is the named type. Shape: (n,)."""
    if not name:
        raise ValueError("type name must be nonempty")

    def hits(column: np.ndarray) -> np.ndarray:
        col = np.asarray(column, dtype=str)
        exact = col == name
        prefix = np.char.startswith(col, name)
        extra = np.array([
            len(text) > len(name) and not text[len(name)].isalnum() for text in col
        ], dtype=bool)
        return exact | (prefix & extra)

    return hits(cell_type) | hits(hemibrain_type)


def resolve_hub_types(
    cell_type: np.ndarray,
    hemibrain_type: np.ndarray,
    names: tuple[str, ...] = HUB_TYPE_NAMES,
) -> dict[str, Any]:
    """Engine-index sets for hub cell types. Skip the arm when any name is empty."""
    found: dict[str, list[int]] = {}
    missing: list[str] = []
    for name in names:
        idx = np.flatnonzero(type_name_mask(cell_type, hemibrain_type, name)).astype(np.int32)
        found[name] = [int(i) for i in idx]
        if idx.size == 0:
            missing.append(name)
    hub_idx = np.unique(np.concatenate(
        [np.asarray(found[name], dtype=np.int32) for name in names if found[name]] or [np.zeros(0, dtype=np.int32)]
    ))
    return {
        "names": list(names),
        "counts": {name: len(found[name]) for name in names},
        "idx": [int(i) for i in hub_idx],
        "missing": missing,
        "resolved": not missing,
        "skip_reason": None if not missing else (
            "registry labels do not resolve " + ", ".join(missing)
        ),
    }


def reciprocal_excitatory_partners(
    pre: np.ndarray,
    post: np.ndarray,
    signed: np.ndarray,
    hub_idx: np.ndarray,
) -> np.ndarray:
    """Excitatory partners with edges both ways. Shape: (k,)."""
    pre_idx = np.asarray(pre, dtype=np.int32)
    post_idx = np.asarray(post, dtype=np.int32)
    signs = np.asarray(signed, dtype=np.float64)
    hubs = np.asarray(hub_idx, dtype=np.int32)
    if pre_idx.shape != post_idx.shape or pre_idx.shape != signs.shape:
        raise ValueError("pre, post, and signs must share one shape")
    if hubs.size == 0:
        return np.zeros(0, dtype=np.int32)
    exc = signs > 0
    from_hub = exc & np.isin(pre_idx, hubs)
    to_hub = exc & np.isin(post_idx, hubs)
    posts = post_idx[from_hub]
    pres = pre_idx[to_hub]
    both = np.intersect1d(posts, pres)
    return np.setdiff1d(both, hubs).astype(np.int32)


def outgoing_factor_scale(
    pre: np.ndarray,
    n_syn: int,
    idx: np.ndarray,
    factor: float,
) -> np.ndarray:
    """Outgoing scale on synapses from idx. Shape: (n_syn,)."""
    if not np.isfinite(factor) or factor <= 0:
        raise ValueError("outgoing factor must be finite and positive")
    pre_idx = np.asarray(pre, dtype=np.int32)
    if int(pre_idx.shape[0]) != int(n_syn):
        raise ValueError("pre must have length n_syn")
    scale = np.ones(int(n_syn), dtype=np.float64)
    if np.asarray(idx).size:
        scale[np.isin(pre_idx, np.asarray(idx, dtype=np.int32))] = float(factor)
    return scale


def lab_sample_indices(central: np.ndarray, *, seed: int = THRESHOLD_SEED) -> dict[str, np.ndarray]:
    """Fixed 2000-neuron Fano sample and 500-neuron pair sample."""
    from flyonenomics.orchestrator.seeds import stream
    from flyonenomics.types import ANALYSIS

    pool = np.unique(np.asarray(central, dtype=np.int32))
    rng = stream(int(seed), 29, 0, ANALYSIS)
    n_fano = min(LAB_FANO_N, int(pool.size))
    n_pair = min(LAB_PAIR_N, int(pool.size))
    if n_fano < 1 or n_pair < 1:
        raise ValueError("central sample is empty")
    fano_idx = np.sort(rng.choice(pool, size=n_fano, replace=False).astype(np.int32))
    pair_idx = np.sort(rng.choice(pool, size=n_pair, replace=False).astype(np.int32))
    return {
        "fano_idx": np.ascontiguousarray(fano_idx, dtype=np.int32),
        "pair_idx": np.ascontiguousarray(pair_idx, dtype=np.int32),
    }


def _bin_neuron_counts(counts_chunk: np.ndarray, bin_chunks: int) -> np.ndarray:
    """Sum consecutive chunk columns. Shape: (n_neurons, n_bins)."""
    values = np.asarray(counts_chunk, dtype=np.float64)
    if values.ndim != 2 or int(bin_chunks) < 1:
        raise ValueError("counts must be (n, t) and bin_chunks >= 1")
    n = (values.shape[1] // int(bin_chunks)) * int(bin_chunks)
    if n == 0:
        return np.zeros((values.shape[0], 0), dtype=np.float64)
    trimmed = values[:, :n]
    return trimmed.reshape(trimmed.shape[0], -1, int(bin_chunks)).sum(axis=2)


def single_unit_fano(counts_bin: np.ndarray) -> dict[str, float | None | int]:
    """Mean single-unit Fano over neurons with a positive mean count."""
    bins = np.asarray(counts_bin, dtype=np.float64)
    if bins.ndim != 2 or bins.shape[1] < 2:
        return {"mean": None, "n_scored": 0, "n_silent": int(bins.shape[0]) if bins.ndim == 2 else 0}
    mean = bins.mean(axis=1)
    var = bins.var(axis=1)
    silent = mean <= 0
    scored = ~silent
    fano = np.divide(var, mean, out=np.full_like(mean, np.nan), where=scored)
    values = fano[np.isfinite(fano)]
    return {
        "mean": float(values.mean()) if values.size else None,
        "n_scored": int(values.size),
        "n_silent": int(np.sum(silent)),
    }


def mean_pairwise_correlation(counts_bin: np.ndarray) -> dict[str, float | None | int]:
    """Mean upper-triangle Pearson correlation. Units: dimensionless."""
    bins = np.asarray(counts_bin, dtype=np.float64)
    n = int(bins.shape[0]) if bins.ndim == 2 else 0
    if bins.ndim != 2 or n < 2 or bins.shape[1] < 2:
        return {"mean": None, "n_pairs": 0, "n_dropped": 0}
    centered = bins - bins.mean(axis=1, keepdims=True)
    denom = np.sqrt((centered * centered).sum(axis=1))
    good = denom > 0
    if int(np.sum(good)) < 2:
        return {"mean": None, "n_pairs": 0, "n_dropped": int(n * (n - 1) // 2)}
    kept = centered[good] / denom[good][:, None]
    corr = kept @ kept.T / float(bins.shape[1])
    iu = np.triu_indices(kept.shape[0], k=1)
    values = corr[iu]
    finite = values[np.isfinite(values)]
    n_possible = n * (n - 1) // 2
    return {
        "mean": float(finite.mean()) if finite.size else None,
        "n_pairs": int(finite.size),
        "n_dropped": int(n_possible - finite.size),
    }


def pca_participation_ratio(counts_bin: np.ndarray) -> dict[str, float | None | int]:
    """Participation ratio of the neuron-by-time covariance."""
    bins = np.asarray(counts_bin, dtype=np.float64)
    if bins.ndim != 2 or bins.shape[0] < 2 or bins.shape[1] < 2:
        return {"value": None, "n": int(bins.shape[0]) if bins.ndim == 2 else 0}
    cov = np.cov(bins)
    eig = np.linalg.eigvalsh(cov)
    eig = np.clip(eig, 0.0, None)
    total = float(eig.sum())
    sq = float(np.square(eig).sum())
    if total <= 0 or sq <= 0:
        return {"value": None, "n": int(bins.shape[0])}
    return {"value": float((total * total) / sq), "n": int(bins.shape[0])}


def lab_measures(
    fano_chunks: np.ndarray,
    pair_chunks: np.ndarray,
    *,
    chunk_ms: float,
) -> dict[str, Any]:
    """Recorded-only R1 lab measures from chunk counts. Units: ms, dimensionless."""
    dt = float(chunk_ms)
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError("chunk_ms must be finite and positive")
    fano_bins = max(1, int(round(LAB_FANO_MS / dt)))
    corr_bins = max(1, int(round(LAB_CORR_MS / dt)))
    fano = single_unit_fano(_bin_neuron_counts(fano_chunks, fano_bins))
    corr = mean_pairwise_correlation(_bin_neuron_counts(pair_chunks, corr_bins))
    pr = pca_participation_ratio(_bin_neuron_counts(pair_chunks, corr_bins))
    return {
        "single_unit_fano_100ms": fano,
        "mean_pairwise_corr_50ms": corr,
        "pca_participation_ratio": pr,
        "fano_n": int(np.asarray(fano_chunks).shape[0]),
        "pair_n": int(np.asarray(pair_chunks).shape[0]),
        "chunk_ms": dt,
    }


def screen_ladder(
    setting: Setting,
    w_bg: float,
    rows: list[dict],
    ladder: tuple[float, ...] | list[float],
    *,
    dt_ms: float | None = None,
) -> dict:
    """R-screen on one arm ladder. Same checks as screen_candidate. Units: Hz, mV."""
    grid = tuple(round(float(w), 8) for w in ladder)
    weight = round(float(w_bg), 8)
    if weight not in grid:
        raise ValueError("w_bg is not on the arm ladder")
    index = grid.index(weight)
    if index + 2 >= len(grid):
        raise ValueError("ladder candidate needs two adjacent weights and a next-grid point")
    weights = grid[index:index + 3]
    lookup = {}
    for row in rows:
        key = (round(float(row["w_bg"]), 8), int(row["seed"]))
        if key in lookup:
            raise ValueError(f"duplicate evaluation {key}")
        lookup[key] = row
    points = [[lookup.get((w, seed), {}) for seed in SEEDS] for w in weights]

    def field_of(row: dict, field: str) -> float | None:
        return None if not _cbi_row_computable(row, dt_ms=dt_ms) else number(row.get(field))

    def rate_of(row: dict, group: str) -> float | None:
        return None if not _cbi_row_computable(row, dt_ms=dt_ms) else number(row.get("rates_hz", {}).get(group))

    means = [{g: _mean(rate_of(r, g) for r in point) for g in TARGETS} for point in points]
    violations: dict[str, float] = {}
    checks: dict[str, bool] = {}
    for field, lo, hi, strict in (("F", None, 3, True), ("b", None, .05, True),
                                   ("stability_ratio", .5, 2, False)):
        vals = [field_of(r, field) for p in points[:2] for r in p]
        violations[field] = max(violation(v, lo, hi) for v in vals)
        checks[field] = all(v is not None and (lo is None or v >= lo)
                            and (v < hi if strict else v <= hi) for v in vals)
    for g, lo, hi in (("central", .5, 8), ("DAN", .5, 10), ("KC", None, 2)):
        vals = [p[g] for p in means[:2]]
        violations[g] = max(violation(v, lo, hi, floor=.01) for v in vals)
        checks[g] = all(v is not None and (lo is None or v >= lo) and v <= hi for v in vals)
    grades = []
    grade_ok = []
    for i in range(3):
        nxt = rate_of(points[2][i], "central")
        for p in points[:2]:
            c = rate_of(p[i], "central")
            grades.append(CAP if nxt is None or c is None else
                          violation(max(nxt, .01) / max(c, .01), upper=3))
            grade_ok.append(nxt is not None and c is not None and nxt < 3 * c)
    violations["gradedness"] = max(grades)
    checks["gradedness"] = all(grade_ok)
    stiff = any(not _cbi_row_computable(r, dt_ms=dt_ms) for p in points for r in p)
    flags = ["cbi-stiff"] if stiff else []
    return {**asdict(setting), "w_bg": float(weights[0]), "pair_weights": list(weights[:2]),
            "grade_weight": float(weights[2]), "ladder": list(grid),
            "rates_hz": means[0], "pair_rates_hz": means[:2],
            "violations": violations, "S": sum(violations.values()),
            "J": objective(means[0]), "screen_passed": all(checks.values()),
            "screen_checks": checks, "reflex_passed": None, "long_passed": None,
            "flags": flags}


def connectome_edges(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load cached pre, post, signed synapse counts. Shapes: (n_syn,)."""
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays

    completeness, connectivity = connectome_source_paths("783")
    _roots, pre, post, signed = load_connectome_arrays(completeness, connectivity)
    if int(_roots.shape[0]) != int(n):
        raise ValueError("connectome n does not match the engine")
    return (
        np.asarray(pre, dtype=np.int32),
        np.asarray(post, dtype=np.int32),
        np.asarray(signed, dtype=np.float64),
    )


def engine_type_labels(registry: Any) -> tuple[np.ndarray, np.ndarray]:
    """cell_type and hemibrain_type in engine order."""
    from flyonenomics.registry.annotations import load_annotations

    frame = load_annotations("v2.1.0").set_index("root_id").reindex(registry.root_ids)
    cell_type = frame["cell_type"].fillna("").astype(str).to_numpy()
    hemibrain = frame["hemibrain_type"].fillna("").astype(str).to_numpy()
    return cell_type, hemibrain


def apply_arm(built: dict[str, Any], arm: dict[str, Any] | None) -> dict[str, Any]:
    """Attach one 3e arm to a built engine. No-op when arm is None."""
    if not arm:
        return built
    engine = built["engine"]
    groups = built["groups"]
    n = int(engine.n)
    policy = str(arm.get("bg_policy") or "default")
    built["bg_policy"] = policy
    need_k = arm.get("scale") == "indeg" or arm.get("beta") is not None
    need_hubs = arm.get("hub_factor") is not None
    pre = post = signed = k = None
    k_info: dict[str, Any] | None = None
    if need_k or need_hubs:
        pre, post, signed = connectome_edges(n)
    if need_k:
        assert post is not None and signed is not None
        k = incoming_synapse_counts(post, signed, n)
        k_info = k_distribution(k)
        built["k_distribution"] = k_info
    if arm.get("scale") == "indeg":
        assert post is not None and k is not None and k_info is not None
        gain = indeg_gain(k, k_info["k_median_positive"])
        extra = incoming_gain_scale(post, gain)
        scale = np.asarray(built["weight_scale"], dtype=np.float64) * extra
        scale32 = scale.astype(np.float32)
        engine.set_weight_scale(scale32)
        built["weight_scale"] = scale32
    if arm.get("beta") is not None:
        assert k is not None
        built["v_th_offset"] = threshold_offset(k, float(arm["beta"]))
    else:
        built["v_th_offset"] = None
    if need_hubs:
        cell_type, hemibrain = engine_type_labels(built["registry"])
        resolved = resolve_hub_types(cell_type, hemibrain)
        built["hubs"] = resolved
        if not resolved["resolved"]:
            raise ValueError(resolved["skip_reason"] or "hub types did not resolve")
        assert pre is not None and post is not None and signed is not None
        hub_idx = np.asarray(resolved["idx"], dtype=np.int32)
        partners = reciprocal_excitatory_partners(pre, post, signed, hub_idx)
        targets = np.unique(np.concatenate([hub_idx, partners]))
        extra = outgoing_factor_scale(pre, int(engine.n_syn), targets, float(arm["hub_factor"]))
        scale = np.asarray(built["weight_scale"], dtype=np.float64) * extra
        scale32 = scale.astype(np.float32)
        engine.set_weight_scale(scale32)
        built["weight_scale"] = scale32
        built["hubs"] = {
            **resolved,
            "n_partners": int(partners.size),
            "n_targets": int(targets.size),
            "factor": float(arm["hub_factor"]),
        }
    central = groups["central"]
    built["lab_sample"] = lab_sample_indices(central)
    return built
