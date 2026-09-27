"""Stage 4 ring-neuron position coding under CX_DAN activation.

Part A is static: it censuses the imposed TuBu encoder and direct TuBu->ER
projection, fixes four positions and a drive-matching rule, freezes the
seed-held-out analysis, and validates that analysis on synthetic counts whose
variability is estimated from stages 1--3.  It does not run the neural engine.
Part B must not be launched until the coordinator gives the explicit go.
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
from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar

import ring_dopamine_stage1 as s1
import ring_dopamine_stage2c as s2c
import ring_dopamine_stage3 as s3

ROOT = Path(__file__).resolve().parents[1]
MASTER = s1.MASTER
SEEDS = s1.SEEDS
SETTLE_S = s1.SETTLE_S
PROBE_S = s1.PROBE_S
SOURCE_POPULATION = s1.SOURCE_POPULATION
DOPAMINE_POPULATION = s1.DOPAMINE_POPULATION
DA_DRIVE_HZ = s1.DA_DRIVE_HZ
STRIPE_WIDTH_DEG = 5.0
SIGMA_DEG = s1.SIGMA_DEG
NOMINAL_MAX_HZ = s1.TUBU_MAX_HZ
CENSUS_AZIMUTHS = tuple(float(v) for v in range(-150, 151, 25))
POSITIONS = (-150.0, -50.0, 50.0, 150.0)
CONDITIONS = ("dark", "driven", "driven-clamped")
STIMULI = ("off", *POSITIONS)
DEFAULT_FIXTURE = Path("data/experiments/p2/ring-dopamine-stage4.json")
DEFAULT_PLAN = Path("camber-runs/ring-dopamine-stage4/plan.json")
DEFAULT_RAW = Path("camber-runs/ring-dopamine-stage4/raw")
DEFAULT_AUDIT = Path("camber-runs/ring-dopamine-stage4/audit.json")
DEFAULT_RECORD = Path("validation/records/p2/ring-dopamine-stage4.json")
REACHED_RECORD = s1.REACHED_RECORD
DECLARED_SUBSTRATE_ID = s1.DECLARED_SUBSTRATE_ID
SOURCE_COMMIT_ENV = s1.SOURCE_COMMIT_ENV
ANALYSIS_VERSION = "stage4-affine-eiv-lososeed-v1"
SYNTHETIC_SEED = 14520260921
ACTUAL_BOOTSTRAP_REPLICATES = 2000
SYNTHETIC_BOOTSTRAP_REPLICATES = 200


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def read(path: Path) -> dict[str, Any]:
    from flyonenomics.io import read_json

    return read_json(path)


def digest(value: np.ndarray, dtype: Any | None = None) -> str:
    array = np.asarray(value, dtype=dtype) if dtype is not None else np.asarray(value)
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def identity(platform_name: str) -> dict[str, Any]:
    """Hash this runner and every imported experiment runner used by stage 4."""
    from flyonenomics.connectome_arrays import connectome_source_paths
    from flyonenomics.io import hash_file

    source_commit = __import__("os").environ.get(SOURCE_COMMIT_ENV)
    if not source_commit:
        raise ValueError(f"{SOURCE_COMMIT_ENV} must bind the executed source commit")
    completeness, connectivity = connectome_source_paths("783")
    data_names = (
        "params-v0.2.yaml", "drive-v0.2.yaml", "dopamine-v0.2.yaml",
        "populations-v0.2.yaml", "transmitters-v0.2.yaml",
        "receptors-v0.1.yaml", "compartments-v0.1.yaml",
    )
    return {
        "platform": platform_name,
        "engine": "lif",
        "source_commit": source_commit,
        "runner_sha256": hash_file(Path(__file__)),
        "reused_stage3_runner_sha256": hash_file(Path(s3.__file__)),
        "reused_stage2c_runner_sha256": hash_file(Path(s2c.__file__)),
        "reused_stage1_runner_sha256": hash_file(Path(s1.__file__)),
        "source_sha256": {
            str(path.relative_to(ROOT)): hash_file(path)
            for path in sorted((ROOT / "src").rglob("*.py"))
        },
        "inputs_sha256": {name: hash_file(ROOT / "data" / name) for name in data_names},
        "fixture_sha256": hash_file(ROOT / DEFAULT_FIXTURE),
        "analysis": {"version": ANALYSIS_VERSION, "runner_sha256": hash_file(Path(__file__))},
        "connectome_sha256": {
            completeness.name: hash_file(completeness), connectivity.name: hash_file(connectivity)
        },
    }


def _wrap(angle: np.ndarray) -> np.ndarray:
    return (np.asarray(angle, dtype=np.float64) + 180.0) % 360.0 - 180.0


def _encoder_rows(registry: Any, params: Any) -> tuple[np.ndarray, list[dict[str, Any]], dict[float, np.ndarray]]:
    """Complete TuBu patterns under the frozen encoder-only drive match."""
    from flyonenomics.behaviour.encoder import preferred_azimuths

    population = registry.population(SOURCE_POPULATION)
    preferred = preferred_azimuths(
        np.asarray(population.root_ids, dtype=np.int64), np.asarray(population.side),
        tuple(params.get("vis.pref_range")),
    )
    unit = {
        theta: np.exp(-np.square(_wrap(theta - preferred)) / (2.0 * SIGMA_DEG * SIGMA_DEG))
        for theta in CENSUS_AZIMUTHS
    }
    # Match to the smallest encoder mass on the census grid.  This never raises
    # a cell above the inherited 70 Hz ceiling.
    target_mass = min(float(values.sum()) for values in unit.values()) * NOMINAL_MAX_HZ
    patterns: dict[float, np.ndarray] = {}
    rows = []
    for theta in CENSUS_AZIMUTHS:
        maximum = target_mass / float(unit[theta].sum())
        rates = maximum * unit[theta]
        patterns[theta] = rates
        cells = []
        for position, engine_index in enumerate(np.asarray(population.idx, dtype=np.int32)):
            cells.append({
                "engine_index": int(engine_index),
                "root_id": int(population.root_ids[position]),
                "side": str(population.side[position]),
                "preferred_azimuth_deg": float(preferred[position]),
                "rate_hz": float(rates[position]),
                "relative_rate_of_pattern": float(rates[position] / target_mass),
                "external_event_amplitude_mV": float(params.get("input.w_in")),
                "timing": "constant Poisson rate from 0 to 20 s; analysis uses [2,20) s",
            })
        rows.append({
            "azimuth_deg": theta,
            "matched_max_hz": float(maximum),
            "total_injected_rate_hz": float(rates.sum()),
            "nonzero_cells": int(np.count_nonzero(rates)),
            "rate_sha256_float64": digest(rates, np.float64),
            "cells": cells,
        })
    return preferred, rows, patterns


def encoder_census() -> dict[str, Any]:
    """Static encoder and direct-projection census.  No neural outcome is read."""
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.drive.rest import apply_rest_substrate, load_drive_rest
    from flyonenomics.registry import build_registry
    from flyonenomics.types import load_params

    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    params = load_params(ROOT / "data/params-v0.2.yaml")
    preferred, rows, patterns = _encoder_rows(registry, params)
    source = np.asarray(registry.population(SOURCE_POPULATION).idx, dtype=np.int32)
    reached = read(ROOT / REACHED_RECORD)
    er_cells = [cell for cell in reached["cells"] if "ring_ER" in cell["classes"]]
    targets = np.asarray(sorted(int(cell["engine_index"]) for cell in er_cells), dtype=np.int32)
    completeness, connectivity = connectome_source_paths("783")
    roots, pre, post, raw = load_connectome_arrays(completeness, connectivity)
    pre = np.asarray(pre, dtype=np.int32)
    post = np.asarray(post, dtype=np.int32)
    raw = np.asarray(raw, dtype=np.float64)

    class StaticScaleSink:
        n = registry.n
        def engine_model(self) -> str:
            return "lif"
        def set_weight_scale(self, value: np.ndarray) -> None:
            self.scale = np.asarray(value, dtype=np.float64)

    sink = StaticScaleSink()
    drive = load_drive_rest(ROOT / "data/drive-v0.2.yaml")
    _threshold, scale = apply_rest_substrate(sink, params, drive)
    effective = raw * float(params.get("lif.w_syn")) * scale
    mask = np.isin(pre, source) & np.isin(post, targets)
    edge_pre, edge_post, edge_weight = pre[mask], post[mask], effective[mask]
    source_position = np.full(registry.n, -1, dtype=np.int32)
    source_position[source] = np.arange(source.size, dtype=np.int32)
    target_position = np.full(registry.n, -1, dtype=np.int32)
    target_position[targets] = np.arange(targets.size, dtype=np.int32)
    sp = source_position[edge_pre]
    tp = target_position[edge_post]
    projections = []
    for row in rows:
        rates = patterns[float(row["azimuth_deg"])]
        weighted = np.bincount(tp, weights=rates[sp] * edge_weight, minlength=targets.size)
        reached_edges = []
        for k in range(edge_pre.size):
            reached_edges.append({
                "pre_engine_index": int(edge_pre[k]), "pre_root_id": int(roots[edge_pre[k]]),
                "pre_rate_hz": float(rates[sp[k]]), "post_engine_index": int(edge_post[k]),
                "post_root_id": int(roots[edge_post[k]]),
                "composed_weight_mV": float(edge_weight[k]),
                "rate_weighted_direct_drive_mV_per_s": float(rates[sp[k]] * edge_weight[k]),
            })
        projections.append({
            "azimuth_deg": row["azimuth_deg"], "direct_edge_count": int(edge_pre.size),
            "direct_target_count": int(np.unique(edge_post).size),
            "total_rate_weighted_direct_drive_mV_per_s": float(weighted.sum()),
            "per_er_rate_weighted_direct_drive_mV_per_s": [
                {"engine_index": int(index), "value": float(weighted[k])}
                for k, index in enumerate(targets)
            ],
            "edges": reached_edges,
        })
    hashes = [row["rate_sha256_float64"] for row in rows]
    return {
        "mapping_source": {
            "kind": "imposed geometric mapping, not independently supported TuBu receptive fields",
            "assignment": (
                "src/flyonenomics/behaviour/encoder.py:19-36 assigns each side an even 0..150 degree "
                "grid by ascending root ID; lines 94-95 select it for TuBu"
            ),
            "rate_equation": (
                "src/flyonenomics/behaviour/encoder.py:110-128 applies the Gaussian; sigma is 20 degrees"
            ),
            "external_amplitude": (
                "src/flyonenomics/engine/brian_engine.py:461-478 gives every injected event "
                "w_in = w_syn*f_poi = 68.75 mV"
            ),
            "timing": (
                "src/flyonenomics/behaviour/arena.py:120-142 presents the stripe throughout its block; "
                "the first 2 s are an analysis transition, not an encoder ramp"
            ),
        },
        "population_n": int(source.size),
        "represented_range_deg": [float(preferred.min()), float(preferred.max())],
        "grid_azimuths_deg": list(CENSUS_AZIMUTHS),
        "drive_matching": {
            "rule": (
                "On the fixed -150..150 degree census grid, set target total rate to the smallest "
                "70-Hz encoder total, then set each position's maximum rate to target/sum(unit Gaussian). "
                "This uses the encoder alone, makes total injected Hz exact across positions, and never "
                "exceeds 70 Hz in any cell."
            ),
            "target_total_rate_hz": float(rows[0]["total_injected_rate_hz"]),
            "nominal_cell_ceiling_hz": NOMINAL_MAX_HZ,
        },
        "patterns": rows,
        "direct_tubu_to_er": {
            "definition": (
                "connectome signed edge count times lif.w_syn times the declared substrate transmitter "
                "scale; the per-position value further multiplies by the matched presynaptic encoder rate"
            ),
            "projections": projections,
        },
        "encoder_collapse": bool(len(set(hashes)) == 1),
        "stop_rule": (
            "Stop only if every cell-resolved injection distribution is identical.  Direct projections "
            "alone never trigger the stop."
        ),
        "chosen_positions_deg": list(POSITIONS),
        "position_rule": (
            "Choose the two endpoints of the imposed represented range and the two interior census-grid "
            "points that divide the 300-degree span into three equal 100-degree intervals: "
            "-150, -50, +50, +150 degrees.  This uses only encoder geometry and spans both sides."
        ),
    }


def historical_count_variability() -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    """Per-cell count level and NB overdispersion from all 45-degree stage 1--3 arms."""
    paths = [
        ROOT / "validation/records/p2/ring-dopamine-stage1.json",
        ROOT / "validation/records/p2/ring-dopamine-stage2.json",
        ROOT / "validation/records/p2/ring-dopamine-stage3.json",
    ]
    records = [read(path)["probe"] for path in paths]
    metadata = [{k: cell[k] for k in ("engine_index", "root_id", "hemibrain_type", "side")}
                for cell in records[0]["cells"]]
    groups: list[list[np.ndarray]] = [[] for _ in metadata]
    for stage, record in enumerate(records):
        for i, cell in enumerate(record["cells"]):
            if int(cell["engine_index"]) != int(metadata[i]["engine_index"]):
                raise ValueError("historical ER cell order differs")
            if stage == 0:
                groups[i].extend([
                    np.asarray(cell["spike_dark_values"], dtype=np.float64),
                    np.asarray(cell["spike_driven_values"], dtype=np.float64),
                ])
            else:
                groups[i].extend(np.asarray(arm["spike_values"], dtype=np.float64)
                                 for arm in cell["arms"].values())
    level = np.zeros(len(groups), dtype=np.float64)
    alpha = np.zeros(len(groups), dtype=np.float64)
    for i, cell_groups in enumerate(groups):
        means = np.asarray([values.mean() for values in cell_groups])
        variances = np.asarray([values.var(ddof=1) for values in cell_groups])
        level[i] = float(np.median(means))
        usable = means > 0
        estimates = (variances[usable] - means[usable]) / np.maximum(means[usable] ** 2, 1e-12)
        alpha[i] = float(np.clip(np.median(estimates) if estimates.size else 0.0, 0.0, 10.0))
    return np.stack([level, alpha], axis=1), metadata, {
        "sources": [str(path.relative_to(ROOT)) for path in paths],
        "source_position_deg": 45.0,
        "groups_per_cell": int(len(groups[0])),
        "method": (
            "cellwise median arm mean and median max(0,(sample variance-mean)/mean^2) over every "
            "stage 1--3 arm; each arm contributes its ten per-seed 18-s counts"
        ),
        "active_level_cells": int(np.count_nonzero(level)),
        "level_count_summary": _summary(level),
        "nb_alpha_summary": _summary(alpha),
    }


def _summary(values: np.ndarray) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    return {"n": int(array.size), "min": float(array.min()), "median": float(np.median(array)),
            "mean": float(array.mean()), "max": float(array.max())}


def _variance(raw: np.ndarray, prior_alpha: float) -> np.ndarray:
    """Condition-specific training variance with a historical shrinkage target."""
    mean = raw.mean(axis=0)
    sample = raw.var(axis=0, ddof=1) if raw.shape[0] > 1 else np.zeros(raw.shape[1])
    prior = mean + float(prior_alpha) * mean * mean
    return np.maximum(0.25, 0.5 * sample + 0.5 * prior)


def _fit_affine(dark: np.ndarray, driven: np.ndarray, prior_alpha: float) -> dict[str, Any]:
    """Generalised Deming fit to raw off/on means with shared-off covariance.

    dark/driven have shape (training seeds, off + four positions).  Signed
    responses are parameters derived from the five jointly supplied raw means;
    they are not treated as count observations.
    """
    n = dark.shape[0]
    md, mv = dark.mean(axis=0), driven.mean(axis=0)
    vd, vv = _variance(dark, prior_alpha), _variance(driven, prior_alpha)
    x, y = md[1:] - md[0], mv[1:] - mv[0]
    cx = np.diag(vd[1:] / n) + np.full((4, 4), vd[0] / n)
    cy = np.diag(vv[1:] / n) + np.full((4, 4), vv[0] / n)

    def profile(a: float) -> tuple[float, float]:
        covariance = cy + a * a * cx + np.eye(4) * 1e-9
        inverse = np.linalg.inv(covariance)
        one = np.ones(4)
        b = float(one @ inverse @ (y - a * x) / (one @ inverse @ one))
        residual = y - a * x - b
        sign, logdet = np.linalg.slogdet(covariance)
        objective = float(residual @ inverse @ residual + logdet) if sign > 0 else 1e100
        return objective, b

    result = minimize_scalar(lambda a: profile(float(a))[0], bounds=(0.0, 8.0), method="bounded")
    a = float(result.x)
    _objective, b = profile(a)
    prediction = np.r_[mv[0], mv[0] + a * (md[1:] - md[0]) + b]
    return {"a": a, "b": b, "dark_mean": md, "driven_mean": prediction,
            "dark_variance": vd, "driven_variance": vv}


def _fold_score(counts: np.ndarray, prior_alpha: np.ndarray, held: int,
                train_indices: np.ndarray | None = None) -> tuple[float, np.ndarray, list[dict[str, Any]]]:
    """Held-seed raw-count score: affine loss minus condition-specific loss."""
    if train_indices is None:
        train_indices = np.flatnonzero(np.arange(counts.shape[0]) != held)
    per_cell = np.zeros(counts.shape[1], dtype=np.float64)
    fits = []
    for cell in range(counts.shape[1]):
        dark = counts[train_indices, cell, 0, :]
        driven = counts[train_indices, cell, 1, :]
        fit = _fit_affine(dark, driven, float(prior_alpha[cell]))
        observed = counts[held, cell]
        independent_dark = dark.mean(axis=0)
        independent_driven = driven.mean(axis=0)
        vd, vv = fit["dark_variance"], fit["driven_variance"]
        affine_loss = np.sum((observed[0] - fit["dark_mean"]) ** 2 / vd)
        affine_loss += np.sum((observed[1] - fit["driven_mean"]) ** 2 / vv)
        flexible_loss = np.sum((observed[0] - independent_dark) ** 2 / vd)
        flexible_loss += np.sum((observed[1] - independent_driven) ** 2 / vv)
        per_cell[cell] = float(affine_loss - flexible_loss)
        fits.append({"a": fit["a"], "b": fit["b"]})
    return float(per_cell.sum()), per_cell, fits


def primary_endpoint(counts: np.ndarray, prior_alpha: np.ndarray) -> dict[str, Any]:
    """LOSO primary endpoint on a (seed, cell, condition, off+4) count tensor."""
    if counts.shape[1:] != (228, 2, 5):
        raise ValueError("primary counts must have shape (seeds,228,2,5)")
    seed_scores, cell_scores, fold_fits = [], [], []
    for held in range(counts.shape[0]):
        score, cells, fits = _fold_score(counts, prior_alpha, held)
        seed_scores.append(score)
        cell_scores.append(cells)
        fold_fits.append(fits)
    return {
        "score": float(np.mean(seed_scores)),
        "seed_scores": [float(value) for value in seed_scores],
        "per_cell_scores": np.mean(np.asarray(cell_scores), axis=0).tolist(),
        "fold_fits": fold_fits,
    }


def bootstrap_primary(counts: np.ndarray, prior_alpha: np.ndarray, *, replicates: int,
                      seed: int) -> dict[str, Any]:
    """Seed-block bootstrap; every resample refits every held-seed model."""
    point = primary_endpoint(counts, prior_alpha)
    rng = np.random.default_rng(seed)
    values = []
    while len(values) < replicates:
        selected = rng.integers(0, counts.shape[0], size=counts.shape[0])
        unique, multiplicity = np.unique(selected, return_counts=True)
        if unique.size < 3:
            continue
        held_scores = []
        for held, copies in zip(unique, multiplicity, strict=True):
            # A seed block copied into a bootstrap sample is excluded in all its
            # copies when that seed is held out.  This prevents train/test
            # leakage between duplicate copies of one block.
            train_indices = selected[selected != held]
            score, _cells, _fits = _fold_score(counts, prior_alpha, int(held), train_indices)
            held_scores.extend([score] * int(copies))
        values.append(float(np.mean(held_scores)))
    centered = np.asarray(values, dtype=np.float64) - float(np.mean(values))
    offset_lower, offset_upper = np.percentile(centered, [2.5, 97.5])
    lower = point["score"] + float(offset_lower)
    upper = point["score"] + float(offset_upper)
    return {**point, "bootstrap_replicates": replicates, "bootstrap_seed": seed,
            "interval_method": "seed-block bootstrap percentile deviations centered on the observed LOSO score",
            "interval": {"lower": float(lower), "upper": float(upper),
                         "includes_zero": bool(lower <= 0.0 <= upper)},
            "interpretation": (
                "positive score favours condition-specific tuning; a lower bound above zero is a "
                "detected change not explained by per-cell additive and multiplicative transformations "
                "of mean firing"
            )}


def cellwise_and_subtype_indices(primary: dict[str, Any], metadata: list[dict[str, Any]]) -> dict[str, Any]:
    """Exploratory frozen decomposition of the primary score; cells are not replicates."""
    values = np.asarray(primary["per_cell_scores"], dtype=np.float64)
    if values.size != len(metadata):
        raise ValueError("primary cell scores and metadata differ")
    subtype: dict[str, list[float]] = {}
    cells = []
    for value, cell in zip(values, metadata, strict=True):
        name = str(cell["hemibrain_type"])
        subtype.setdefault(name, []).append(float(value))
        cells.append({**cell, "held_seed_mean_score": float(value)})
    return {
        "cells": cells,
        "subtypes": {
            name: {"n": len(group), "score_sum": float(np.sum(group)),
                   "score_mean": float(np.mean(group))}
            for name, group in sorted(subtype.items())
        },
        "warning": "exploratory decomposition; the ten seed blocks, not cells, are independent replicates",
    }


def secondary_decoder(counts: np.ndarray, fold_fits: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Fixed LOSO nearest-centroid decoder and an affine-rate null."""
    correct = {"dark": 0, "driven": 0, "affine_rate_null": 0}
    total = counts.shape[0] * 4
    for held in range(counts.shape[0]):
        train = np.arange(counts.shape[0]) != held
        # Raw on-minus-off vectors are continuous decoder features, not counts in a count likelihood.
        response = counts[:, :, :, 1:] - counts[:, :, :, [0]]
        for condition, label in ((0, "dark"), (1, "driven")):
            train_vectors = np.transpose(response[train, :, condition, :], (0, 2, 1))
            centre = train_vectors.mean(axis=0)
            scale = np.maximum(train_vectors.reshape(-1, 228).std(axis=0, ddof=1), 1.0)
            test = response[held, :, condition, :].T
            distance = ((test[:, None, :] - centre[None, :, :]) / scale) ** 2
            predicted = np.argmin(distance.sum(axis=2), axis=1)
            correct[label] += int(np.sum(predicted == np.arange(4)))
        fits = fold_fits[held]
        a = np.asarray([fit["a"] for fit in fits])
        b = np.asarray([fit["b"] for fit in fits])
        dark_train = np.transpose(response[train, :, 0, :], (0, 2, 1))
        null_train = dark_train * a[None, None, :] + b[None, None, :]
        centre = null_train.mean(axis=0)
        scale = np.maximum(null_train.reshape(-1, 228).std(axis=0, ddof=1), 1.0)
        null_test = response[held, :, 0, :].T * a[None, :] + b[None, :]
        predicted = np.argmin((((null_test[:, None, :] - centre[None, :, :]) / scale) ** 2).sum(axis=2), axis=1)
        correct["affine_rate_null"] += int(np.sum(predicted == np.arange(4)))
    return {key: {"correct": value, "total": total, "accuracy": value / total}
            for key, value in correct.items()}


def _negative_binomial(rng: np.random.Generator, mean: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    output = np.zeros_like(mean, dtype=np.int64)
    poisson = alpha <= 1e-12
    output[poisson] = rng.poisson(mean[poisson])
    if np.any(~poisson):
        shape = 1.0 / alpha[~poisson]
        rate = rng.gamma(shape, mean[~poisson] / shape)
        output[~poisson] = rng.poisson(rate)
    return output


def synthetic_counts(history: np.ndarray, metadata: list[dict[str, Any]], *, nonaffine_fraction: float,
                     seed: int) -> tuple[np.ndarray, dict[str, Any]]:
    """Synthetic 4-position/off counts; only the variability and levels come from prior runs."""
    rng = np.random.default_rng(seed)
    level, alpha = history[:, 0], history[:, 1]
    n = level.size
    shape = np.asarray([0.20, 0.55, 1.00, 0.55])
    tuning = np.empty((n, 4), dtype=np.float64)
    signs = np.empty((n, 4), dtype=np.float64)
    contrast = np.asarray([-1.0, 1.0, -1.0, 1.0])
    for i, cell in enumerate(metadata):
        shift = int(cell["root_id"]) % 4
        tuning[i] = np.roll(shape, shift)
        signs[i] = np.roll(contrast, shift)
    off_dark = 0.25 * level
    response_dark = level[:, None] * (0.20 + 0.80 * tuning)
    dark_mean = np.c_[off_dark, off_dark[:, None] + response_dark]
    a = 0.8 + (np.asarray([int(cell["root_id"]) % 5 for cell in metadata]) / 10.0)
    b = 0.10 * level
    off_driven = 1.10 * off_dark
    response_driven = a[:, None] * response_dark + b[:, None]
    response_driven += nonaffine_fraction * level[:, None] * signs
    driven_mean = np.c_[off_driven, np.maximum(0.0, off_driven[:, None] + response_driven)]
    means = np.stack([dark_mean, driven_mean], axis=1)
    # Driven variability is deliberately changed even in the affine-only case.
    alphas = np.stack([np.repeat(alpha[:, None], 5, axis=1),
                       np.repeat((1.5 * alpha + 0.01)[:, None], 5, axis=1)], axis=1)
    counts = np.empty((len(SEEDS), n, 2, 5), dtype=np.int64)
    for s in range(len(SEEDS)):
        counts[s] = _negative_binomial(rng, means, alphas)
    return counts, {
        "nonaffine_fraction_of_historical_cell_level": nonaffine_fraction,
        "known_affine_a_range": [float(a.min()), float(a.max())],
        "known_b": "0.10 times each cell's historical median count level",
        "sparse_cells": int(np.count_nonzero(level == 0)),
        "changed_variability": "driven alpha = 1.5*historical alpha + 0.01; dark uses historical alpha",
        "generator": "negative binomial (Poisson where alpha=0), ten seed blocks",
    }


def synthetic_validation(history: np.ndarray, metadata: list[dict[str, Any]]) -> dict[str, Any]:
    scenarios = []
    for k, size in enumerate((0.0, 0.10, 0.25, 0.50)):
        counts, design = synthetic_counts(history, metadata, nonaffine_fraction=size,
                                          seed=SYNTHETIC_SEED + k)
        endpoint = bootstrap_primary(counts, history[:, 1], replicates=SYNTHETIC_BOOTSTRAP_REPLICATES,
                                     seed=SYNTHETIC_SEED + 100 + k)
        indices = cellwise_and_subtype_indices(endpoint, metadata)
        endpoint["fold_fits"] = "omitted from record; deterministically recomputed by the frozen runner"
        decoder = secondary_decoder(counts, primary_endpoint(counts, history[:, 1])["fold_fits"])
        scenarios.append({"design": design, "primary": endpoint, "cellwise_and_subtype": indices,
                          "secondary_decoder": decoder,
                          "reported_nonaffine_change": bool(endpoint["interval"]["lower"] > 0.0)})
    return {
        "seed": SYNTHETIC_SEED,
        "scenarios": scenarios,
        "reading": (
            "The zero-size scenario is the false-shape check.  Nonzero sizes are planning figures "
            "under this synthetic generator, not power guarantees or pass lines."
        ),
    }


def analysis_spec(history_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": ANALYSIS_VERSION,
        "input": "integer count tensor (seed, 228 ER cells, dark/driven, stripe off + four positions)",
        "primary": {
            "model": "mu_driven(theta)=a_i*mu_dark(theta)+b_i, a_i>=0",
            "signed_response_definition": (
                "mu is the latent stripe-on raw mean minus that condition's latent stripe-off raw mean; "
                "it may be signed. b is an azimuth-independent evoked component."
            ),
            "fit": (
                "leave one whole seed out; estimate all five raw means in each condition from training "
                "counts; fit a>=0 and b by generalised Deming regression using the full covariance from "
                "the shared off count. Dark and driven noise both enter Cy+a^2 Cx."
            ),
            "comparison": (
                "held-seed variance-standardised raw-count prediction loss under the affine fit minus "
                "the condition-specific five-mean fit, summed over all 228 cells and averaged over folds"
            ),
            "noise": (
                "position- and condition-specific training variance, half sample variance and half "
                "historical NB target mean+alpha*mean^2, floor 0.25; historical alpha is frozen"
            ),
            "uncertainty": (
                f"{ACTUAL_BOOTSTRAP_REPLICATES} seed-block resamples; every resample reruns all LOSO fits; "
                "the interval uses bootstrap percentile deviations centered on the observed score"
            ),
            "detection": "lower 2.5 percentile above zero; otherwise unresolved unless an external relevance bound exists",
            "historical_variability": history_info,
        },
        "secondary": {
            "decoder": (
                "fixed nearest-centroid decoder of signed 228-cell response vectors, whole seeds held "
                "out, per-cell scaling learned inside each fold"
            ),
            "null": (
                "affine-rate null: transform held-out and training dark response vectors with each fold's "
                "per-cell a,b before the same decoder; compare driven accuracy to this null"
            ),
            "indices": "report per-cell primary score and sums by hemibrain subtype; exploratory only",
        },
        "flat_outcome_bound": {
            "available": False,
            "reason": (
                "No biological or behavioural calibration maps a change in this imposed TuBu label code, "
                "the cross-validated loss, or four-position decoder accuracy to scientific relevance. "
                "Choosing a percentage would be another model-invented pass line. Therefore a "
                "nonsignificant result is unresolved and the strong flat-outcome label is unavailable."
            ),
        },
    }


def build_part_a(destination: Path) -> None:
    census = encoder_census()
    history, metadata, history_info = historical_count_variability()
    record = {
        "class": "development",
        "purpose": "ring-neuron dopamine stage 4 part A: encoder census and frozen position-code analysis",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "first_sentence": "This is input injected at TuBu, downstream of a visual pathway that does not conduct; the fly does not see.",
        "part_a": {
            "stage4_neural_outcome_used": False,
            "historical_neural_outcome_use": (
                "only the contract-required stage 1--3 per-cell, per-seed 45-degree counts used to "
                "set synthetic count levels and variability; no encoder choice uses a neural outcome"
            ),
            "encoder": census,
            "analysis": analysis_spec(history_info),
            "synthetic_validation": synthetic_validation(history, metadata),
            "decision": "continue_to_part_b_after_coordinator_go" if not census["encoder_collapse"] else "encoder_collapse_stop",
        },
        "part_b": None,
        "limits": [
            "The mapping is an imposed geometric TuBu label, not independently supported receptive fields.",
            "This measures coarse position discrimination and stimulus selectivity, not stimulus selection.",
            "The design establishes no selection state or competing-stimulus mechanism.",
            "All 228 ER cells have one uniform receptor assignment; R2/R5 calcium results cannot calibrate the threshold and gain coefficients.",
        ],
    }
    dump(destination, record)
    print(json.dumps({
        "encoder_collapse": census["encoder_collapse"],
        "positions": census["chosen_positions_deg"],
        "target_total_rate_hz": census["drive_matching"]["target_total_rate_hz"],
        "synthetic": [{"size": row["design"]["nonaffine_fraction_of_historical_cell_level"],
                       "score": row["primary"]["score"], "interval": row["primary"]["interval"],
                       "reported": row["reported_nonaffine_change"]}
                      for row in record["part_a"]["synthetic_validation"]["scenarios"]],
    }, indent=2))
    print(f"wrote {destination}")


def _probe_for(label: str, stimulus: float | str) -> Any:
    """One 20 s fixed open-loop stimulus; the first 2 s remain in the run."""
    from flyonenomics.schema.experiment import Probe

    block = {
        "stimulus": "ambient" if stimulus == "off" else "stripe",
        "azimuth_deg": None if stimulus == "off" else float(stimulus),
        "transition_s": SETTLE_S,
        "dwell_s": PROBE_S - SETTLE_S,
    }
    return Probe.model_validate({
        "type": "probe", "assay": "open_loop_steering", "duration_s": PROBE_S,
        "label": label, "params": {"inject_at": SOURCE_POPULATION, "blocks": [block]},
    })


def build_plan(destination: Path) -> None:
    """Fix all 15 arms without changing the Part A analysis."""
    from flyonenomics.registry.compartments import compartment_index

    fixture = read(ROOT / DEFAULT_FIXTURE)
    fixture_labels = [arm["label"] for arm in fixture["arms"]]
    stimulus_of = fixture["meta"]["arm_stimulus"]
    expected = []
    for condition in CONDITIONS:
        for stimulus in STIMULI:
            suffix = "off" if stimulus == "off" else ("m" if float(stimulus) < 0 else "p") + str(abs(int(float(stimulus))))
            expected.append(f"{condition}-{suffix}")
    if fixture_labels != expected or set(stimulus_of) != set(expected):
        raise ValueError("fixture labels or arm-stimulus mapping differ from frozen stage 4 order")
    census = encoder_census()
    maximum_of = {float(row["azimuth_deg"]): float(row["matched_max_hz"])
                  for row in census["patterns"]}
    reached = read(ROOT / REACHED_RECORD)
    er_cells = [cell for cell in reached["cells"] if "ring_ER" in cell["classes"]]
    trace_indices = sorted(int(cell["engine_index"]) for cell in er_cells)
    arms = []
    for label in expected:
        condition = next(name for name in sorted(CONDITIONS, key=len, reverse=True)
                         if label.startswith(name + "-"))
        stimulus = stimulus_of[label]
        stimulus = "off" if stimulus == "off" else float(stimulus)
        dark_label = label.replace(condition + "-", "dark-", 1)
        arms.append({
            "label": label, "condition": condition, "stimulus": stimulus,
            "drive_hz": 0.0 if condition == "dark" else DA_DRIVE_HZ,
            "matched_max_hz": 0.0 if stimulus == "off" else maximum_of[float(stimulus)],
            "replay": dark_label if condition == "driven-clamped" else None,
            "dan_fast_synapses": "retain",
        })
    output = {
        "class": "development",
        "purpose": "stage 4 fifteen-arm paired position-code probe plan",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "protocol": {
            "master_seed": MASTER, "seeds": list(SEEDS), "arms": arms,
            "settle_s": SETTLE_S, "probe_s": PROBE_S,
            "analysis_window_s": [SETTLE_S, PROBE_S],
            "brain_seconds": PROBE_S * len(arms) * len(SEEDS),
            "inject_at": SOURCE_POPULATION, "dopamine_population": DOPAMINE_POPULATION,
            "dopamine_drive_hz": DA_DRIVE_HZ, "positions_deg": list(POSITIONS),
            "stripe_width_deg": STRIPE_WIDTH_DEG, "TuBu_sigma_deg": SIGMA_DEG,
            "drive_matching": census["drive_matching"],
            "eb_compartment_index": int(compartment_index()["EB"]),
            "replay_definition": (
                "for each seed and stimulus separately, Stage3Neuromod.receptor_terms replaces "
                "applied d_v and gain on the 228 traced ER cells with that paired CX_DAN-dark "
                "trajectory at the native 10 ms cadence; chemistry, occupancies, every non-ER "
                "term, fast transmission, and feedback remain live"
            ),
        },
        "fixture": str(DEFAULT_FIXTURE),
        "frozen_part_a_commit": "1cb0d6a045b73bc5b8cfd27a0eeeefd484a56ca7",
        "analysis_version": ANALYSIS_VERSION,
        "trace_indices": trace_indices, "trace_n": len(trace_indices),
        "cells": [{"engine_index": int(cell["engine_index"]), "root_id": int(cell["root_id"]),
                   "hemibrain_type": cell["hemibrain_type"], "side": cell["side"]}
                  for cell in er_cells],
    }
    dump(destination, output)
    print(f"wrote {destination} ({len(arms)} arms, {output['protocol']['brain_seconds']} brain-s)")


def build_audit(destination: Path) -> None:
    """Run the inherited disconnect/clamp audits and paired replay audit."""
    started = time.monotonic()
    # Stage 3's audit reuses stage 2c's InstrumentedNeuromod and both inherited
    # audits, then verifies the same native-cadence replay class used here.
    inherited_path = destination.with_name("stage3-reused-audit.json")
    old_audit, old_disconnect = s3.DEFAULT_AUDIT, s3.DEFAULT_DISCONNECT_AUDIT
    s3.DEFAULT_AUDIT = inherited_path
    s3.DEFAULT_DISCONNECT_AUDIT = destination.with_name("stage2c-reused-audit.json")
    try:
        s3.build_audit(inherited_path)
    finally:
        s3.DEFAULT_AUDIT, s3.DEFAULT_DISCONNECT_AUDIT = old_audit, old_disconnect
    inherited = read(inherited_path)
    output = {
        "class": "development", "purpose": "stage 4 inherited audits",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "replay": inherited["replay"], "stage2c": inherited["stage2c"],
        "stage4_replay_pairing": (
            "the run plan binds each driven-clamped arm to the dark arm carrying the same seed "
            "and the same off/position stimulus; run_seed refuses a missing trajectory"
        ),
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination, output)
    print(json.dumps({"replay": output["replay"], "wrote": str(destination)}, indent=2))


def run_seed(job: tuple[int, str, str]) -> str:
    """Run all fifteen arms for one seed in one declared engine."""
    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags

    seed, plan_name, destination_name = job
    plan = read(Path(plan_name))
    destination = Path(destination_name)
    targets = np.asarray(plan["trace_indices"], dtype=np.int32)
    ctx = s3._prepare_declared(targets, with_traces=False)
    engine, params, registry = ctx["engine"], ctx["params"], ctx["registry"]
    source = np.asarray(ctx["source"], dtype=np.int32)
    cx_dan = np.asarray(ctx["dopamine_neurons"], dtype=np.int32)
    dan = np.asarray(registry.population("DAN").idx, dtype=np.int32)
    extended = np.asarray(ctx["extended"], dtype=np.int32)
    cx_positions = np.searchsorted(extended, cx_dan)
    chunk_ms = float(params.get("engine.chunk_ms"))
    total_chunks = int(round(PROBE_S * 1000.0 / chunk_ms))
    settle_chunks = int(round(SETTLE_S * 1000.0 / chunk_ms))
    eb = int(plan["protocol"]["eb_compartment_index"])
    rows = []
    trajectories: dict[str, dict[str, np.ndarray]] = {}
    started = time.monotonic()
    for arm in plan["protocol"]["arms"]:
        label = arm["label"]
        replay_name = arm["replay"]
        replay = trajectories.get(replay_name) if replay_name else None
        if replay_name and replay is None:
            raise ValueError(f"missing paired dark replay trajectory for {label}: {replay_name}")
        engine.restore("declared")
        paired_brian_seed = brian_seed(MASTER, seed, 0)
        engine.seed(paired_brian_seed)
        mod = s3.Stage3Neuromod(
            registry, params,
            LayerFlags(background=True, dopamine_A=True, transporter_C=True,
                       dan_fast_synapses="retain"),
            ctx["dopamine"], base_v_th=ctx["base_threshold"], schema_version="1.3",
            drive_groups=ctx["groups"], er_idx=targets, dv_dark_mv=None,
            gain_dark=None, replay=replay,
        )
        mod.apply_genotype(named_manipulations("wild_type"), engine)
        mod.reset_fast()
        mod.replay_step = 0
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        engine.compose_refractory()
        arena = Behaviour(
            SimpleNamespace(topology=ctx["topology"]), registry, params,
            _probe_for(label, arm["stimulus"]), v_fwd=0.0, sign_steer=1,
            K_steer=0.0, r_vis_max=float(arm["matched_max_hz"]), sigma_vis=SIGMA_DEG,
        )
        arena.reset(np.random.default_rng(seed))
        counts = np.zeros(registry.n, dtype=np.int64)
        dv_sum = np.zeros(targets.size, dtype=np.float64)
        gain_sum = np.zeros(targets.size, dtype=np.float64)
        natural_dv_sum = np.zeros(targets.size, dtype=np.float64)
        natural_gain_sum = np.zeros(targets.size, dtype=np.float64)
        full_dv = np.empty((total_chunks, targets.size), dtype=np.float64)
        full_gain = np.empty((total_chunks, targets.size), dtype=np.float64)
        eb_chunks: list[float] = []
        applied_dv_chunks: list[float] = []
        applied_gain_chunks: list[float] = []
        source_sparse: list[list[int]] = []
        measure_chunks = 0
        for step in range(total_chunks):
            rate = arena.rates(arena.view(), step * chunk_ms / 1000.0)
            if float(arm["drive_hz"]):
                rate[cx_positions] += float(arm["drive_hz"])
            engine.set_input_rates(rate)
            mod.replay_step = step
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            full_dv[step] = np.asarray(mod.last_applied_dv[targets], dtype=np.float64)
            full_gain[step] = np.asarray(mod.last_applied_gain[targets], dtype=np.float64)
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_ms / 1000.0)
            if step >= settle_chunks:
                counts += result.counts
                local = np.flatnonzero(result.counts[source])
                source_sparse.extend([[step - settle_chunks, int(source[k]), int(result.counts[source[k]])]
                                      for k in local])
                applied_dv = np.asarray(mod.last_applied_dv[targets], dtype=np.float64)
                applied_gain = np.asarray(mod.last_applied_gain[targets], dtype=np.float64)
                dv_sum += applied_dv
                gain_sum += applied_gain
                natural_dv_sum += np.asarray(mod.last_natural_dv[targets], dtype=np.float64)
                natural_gain_sum += np.asarray(mod.last_natural_gain[targets], dtype=np.float64)
                eb_chunks.append(float(mod.da_c[eb]))
                applied_dv_chunks.append(float(applied_dv[0]))
                applied_gain_chunks.append(float(applied_gain[0]))
                measure_chunks += 1
        trajectories[label] = {"dv": full_dv, "gain": full_gain}
        source_counts = counts[source]
        target_rows = [{
            "engine_index": int(index), "root_id": int(ctx["roots"][index]),
            "spike_count": int(counts[index]),
            "natural_dv_mean_mV": float(natural_dv_sum[k] / measure_chunks),
            "applied_dv_mean_mV": float(dv_sum[k] / measure_chunks),
            "natural_gain_mean": float(natural_gain_sum[k] / measure_chunks),
            "applied_gain_mean": float(gain_sum[k] / measure_chunks),
        } for k, index in enumerate(targets)]
        rows.append({
            "condition": label, "condition_class": arm["condition"],
            "stimulus": arm["stimulus"], "matched_max_hz": arm["matched_max_hz"],
            "replay": replay_name, "dopamine_drive_hz": arm["drive_hz"],
            "targets": target_rows,
            "source_population": SOURCE_POPULATION, "source_n": int(source.size),
            "source_spikes": int(source_counts.sum()),
            "source_rate_hz": float(source_counts.sum() / (source.size * (PROBE_S - SETTLE_S))),
            "source_cell_counts": [{"engine_index": int(index), "root_id": int(ctx["roots"][index]),
                                    "spike_count": int(source_counts[k])}
                                   for k, index in enumerate(source)],
            "source_chunk_counts_sparse": source_sparse,
            "source_chunk_definition": "[0-based 10 ms analysis-window chunk, engine index, emitted spike count]",
            "cx_dan_spikes": int(counts[cx_dan].sum()),
            "cx_dan_rate_hz": float(counts[cx_dan].sum() / (cx_dan.size * (PROBE_S - SETTLE_S))),
            "non_cx_dan_spikes": int(counts[dan].sum()),
            "non_cx_dan_rate_hz": float(counts[dan].sum() / (dan.size * (PROBE_S - SETTLE_S))),
            "eb_da_mean_um": float(np.mean(eb_chunks)), "eb_da_min_um": float(np.min(eb_chunks)),
            "eb_da_max_um": float(np.max(eb_chunks)), "eb_da_chunks_um": eb_chunks,
            "applied_dv_chunks_mV": applied_dv_chunks,
            "applied_gain_chunks": applied_gain_chunks,
        })
        print("seed", seed, label, "complete", flush=True)
    output = {
        "identity": {**plan["identity"], "platform": f"{platform.system().lower()}-{platform.machine()}",
                     "scale_sha256": digest(ctx["scale"], np.float32),
                     "background_sha256": digest(ctx["background"])},
        "seed": seed, "brian_seed": brian_seed(MASTER, seed, 0),
        "settle_s": SETTLE_S, "probe_s": PROBE_S,
        "brain_seconds": PROBE_S * len(plan["protocol"]["arms"]),
        "rows": rows, "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination / f"seed-{seed}.json", output)
    return f"seed-{seed}.json"


def run_dynamic(plan_path: Path, destination: Path, workers: int, seeds: tuple[int, ...]) -> None:
    plan = read(plan_path)
    plan["identity"] = identity(f"{platform.system().lower()}-{platform.machine()}")
    dump(plan_path, plan)
    destination.mkdir(parents=True, exist_ok=False)
    jobs = [(seed, str(plan_path.resolve()), str(destination.resolve())) for seed in seeds]
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                             max_tasks_per_child=1) as pool:
        print(list(pool.map(run_seed, jobs)), flush=True)


def _paired_interval(values: list[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    mean = float(array.mean())
    se = float(array.std(ddof=1) / np.sqrt(array.size)) if array.size > 1 else 0.0
    lower, upper = mean - 1.96 * se, mean + 1.96 * se
    return {"mean": mean, "se": se, "lower": lower, "upper": upper,
            "includes_zero": bool(lower <= 0.0 <= upper), "n": int(array.size)}


def _source_decoder(source_counts: np.ndarray) -> dict[str, Any]:
    """LOSO nearest-centroid decoding of the four emitted TuBu patterns."""
    correct = 0
    for held in range(source_counts.shape[0]):
        train = np.arange(source_counts.shape[0]) != held
        centroids = source_counts[train].mean(axis=0)  # position, cell
        scale = np.maximum(source_counts[train].reshape(-1, source_counts.shape[-1]).std(axis=0, ddof=1), 1.0)
        distance = (((source_counts[held, :, None, :] - centroids[None, :, :]) / scale) ** 2).sum(axis=2)
        correct += int(np.sum(np.argmin(distance, axis=1) == np.arange(4)))
    total = source_counts.shape[0] * 4
    return {"correct": correct, "total": total, "accuracy": correct / total}


def summarize(raw: Path, plan_path: Path, destination: Path, seeds: tuple[int, ...]) -> None:
    """Apply only the analysis frozen at 1cb0d6a to the completed Part B run."""
    from flyonenomics.io import hash_file

    plan = read(plan_path)
    paths = [raw / f"seed-{seed}.json" for seed in seeds]
    if len(paths) != 10 or any(not path.is_file() for path in paths):
        raise ValueError("Part B requires all ten seed files")
    runs = [read(path) for path in paths]
    if any(len(run["rows"]) != 15 for run in runs):
        raise ValueError("every seed file must contain all fifteen arms")
    labels = [arm["label"] for arm in plan["protocol"]["arms"]]
    if any([row["condition"] for row in run["rows"]] != labels for run in runs):
        raise ValueError("raw arm order differs from the frozen plan")
    identities = [run["identity"] for run in runs]
    if any(identity != identities[0] for identity in identities[1:]):
        raise ValueError("seed identities differ")
    if sum(float(run["brain_seconds"]) for run in runs) != 3000.0:
        raise ValueError("raw brain-second total is not 3000")

    cells = plan["cells"]
    cell_indices = [int(cell["engine_index"]) for cell in cells]
    suffixes = ("off", "m150", "m50", "p50", "p150")
    conditions = ("dark", "driven", "driven-clamped")
    counts = np.empty((10, 228, 3, 5), dtype=np.int64)
    source_counts = np.empty((10, 150, 3, 5), dtype=np.int64)
    arm_summary: dict[str, dict[str, Any]] = {}
    for s, run in enumerate(runs):
        rows = {row["condition"]: row for row in run["rows"]}
        for c, condition in enumerate(conditions):
            for p, suffix in enumerate(suffixes):
                label = f"{condition}-{suffix}"
                row = rows[label]
                target_of = {int(value["engine_index"]): int(value["spike_count"])
                             for value in row["targets"]}
                counts[s, :, c, p] = [target_of[index] for index in cell_indices]
                if len(row["source_cell_counts"]) != 150:
                    raise ValueError("TuBu pattern does not contain all 150 cells")
                source_counts[s, :, c, p] = [int(value["spike_count"])
                                              for value in row["source_cell_counts"]]
                bucket = arm_summary.setdefault(label, {key: [] for key in (
                    "er_spikes", "active_er_cells", "tubu_spikes", "cx_dan_spikes",
                    "non_cx_dan_spikes", "eb_da_mean_um", "eb_da_max_um",
                    "applied_dv_mean_mV", "applied_gain_mean")})
                bucket["er_spikes"].append(int(counts[s, :, c, p].sum()))
                bucket["active_er_cells"].append(int(np.count_nonzero(counts[s, :, c, p])))
                bucket["tubu_spikes"].append(int(source_counts[s, :, c, p].sum()))
                bucket["cx_dan_spikes"].append(int(row["cx_dan_spikes"]))
                bucket["non_cx_dan_spikes"].append(int(row["non_cx_dan_spikes"]))
                bucket["eb_da_mean_um"].append(float(row["eb_da_mean_um"]))
                bucket["eb_da_max_um"].append(float(row["eb_da_max_um"]))
                bucket["applied_dv_mean_mV"].append(float(np.mean(
                    [value["applied_dv_mean_mV"] for value in row["targets"]])))
                bucket["applied_gain_mean"].append(float(np.mean(
                    [value["applied_gain_mean"] for value in row["targets"]])))
    arm_summary = {label: {key: {"mean": float(np.mean(values)), "values": values}
                           for key, values in fields.items()}
                   for label, fields in arm_summary.items()}
    er_position_contrasts = {}
    for suffix in suffixes:
        er_position_contrasts[suffix] = {}
        for condition in ("driven", "driven-clamped"):
            left = arm_summary[f"{condition}-{suffix}"]["er_spikes"]["values"]
            right = arm_summary[f"dark-{suffix}"]["er_spikes"]["values"]
            er_position_contrasts[suffix][f"{condition}_minus_dark"] = _paired_interval(
                [float(a) - float(b) for a, b in zip(left, right, strict=True)])

    history, metadata, history_info = historical_count_variability()
    primary_counts = counts[:, :, (0, 1), :]
    primary = bootstrap_primary(primary_counts, history[:, 1],
                                replicates=ACTUAL_BOOTSTRAP_REPLICATES, seed=14520260922)
    primary_indices = cellwise_and_subtype_indices(primary, metadata)
    primary_decoder_result = secondary_decoder(primary_counts, primary["fold_fits"])
    primary_decoder_result["interpretation"] = (
        "dark, activated, and affine-rate-null decoding are all saturated at 40/40, so the "
        "decoder supplies no between-condition or model separation"
    )
    # The intervention was prespecified, but these exact endpoint comparisons and
    # bootstrap seeds were added after the run and are post hoc.
    clamp_counts = counts[:, :, (0, 2), :]
    clamp_endpoint = bootstrap_primary(clamp_counts, history[:, 1],
                                       replicates=ACTUAL_BOOTSTRAP_REPLICATES, seed=14520260923)
    direct_clamp_counts = counts[:, :, (2, 1), :]
    direct_clamp_endpoint = bootstrap_primary(direct_clamp_counts, history[:, 1],
                                              replicates=ACTUAL_BOOTSTRAP_REPLICATES,
                                              seed=14520260924)

    def reading(endpoint: dict[str, Any]) -> str:
        interval = endpoint["interval"]
        if interval["lower"] > 0:
            return "change not explained by per-cell additive and multiplicative transformations of mean firing"
        if interval["upper"] < 0:
            return "affine model favoured"
        return "unresolved"

    primary["three_way_reading"] = reading(primary)
    clamp_endpoint["three_way_reading"] = reading(clamp_endpoint)
    direct_clamp_endpoint["three_way_reading"] = reading(direct_clamp_endpoint)

    # Input-side positive control: emitted TuBu patterns and paired total-count contrasts.
    source_control = {"decoder": {}, "condition_contrasts": {}}
    for c, condition in enumerate(conditions):
        source_control["decoder"][condition] = _source_decoder(
            np.transpose(source_counts[:, :, c, 1:], (0, 2, 1)))
    for condition, c in (("driven_minus_dark", 1), ("driven_clamped_minus_dark", 2)):
        source_control["condition_contrasts"][condition] = {}
        for p, suffix in enumerate(suffixes):
            delta = (source_counts[:, :, c, p].sum(axis=1)
                     - source_counts[:, :, 0, p].sum(axis=1)).astype(float).tolist()
            source_control["condition_contrasts"][condition][suffix] = _paired_interval(delta)
    source_control["complete_pattern_record"] = (
        "every raw arm carries all 150 per-cell TuBu counts and sparse 10 ms emitted-spike chunks"
    )
    source_control["decoder_interpretation"] = (
        "all three TuBu decoders are saturated at 40/40 and supply no between-condition separation"
    )

    # Verify replay against the paired dark trajectory for each seed/stimulus.
    replay_dv_max = replay_gain_max = 0.0
    replay_dv_mean_max = replay_gain_mean_max = 0.0
    target_comparisons = 0
    for run in runs:
        rows = {row["condition"]: row for row in run["rows"]}
        for suffix in suffixes:
            dark, clamped = rows[f"dark-{suffix}"], rows[f"driven-clamped-{suffix}"]
            replay_dv_max = max(replay_dv_max, float(np.max(np.abs(
                np.asarray(dark["applied_dv_chunks_mV"]) - np.asarray(clamped["applied_dv_chunks_mV"])))))
            replay_gain_max = max(replay_gain_max, float(np.max(np.abs(
                np.asarray(dark["applied_gain_chunks"]) - np.asarray(clamped["applied_gain_chunks"])))))
            dark_targets = {int(value["engine_index"]): value for value in dark["targets"]}
            clamped_targets = {int(value["engine_index"]): value for value in clamped["targets"]}
            if dark_targets.keys() != clamped_targets.keys():
                raise ValueError("dark and clamped ER targets differ")
            target_comparisons += len(dark_targets)
            replay_dv_mean_max = max(replay_dv_mean_max, max(
                abs(float(dark_targets[index]["applied_dv_mean_mV"])
                    - float(clamped_targets[index]["applied_dv_mean_mV"]))
                for index in dark_targets
            ))
            replay_gain_mean_max = max(replay_gain_mean_max, max(
                abs(float(dark_targets[index]["applied_gain_mean"])
                    - float(clamped_targets[index]["applied_gain_mean"]))
                for index in dark_targets
            ))
    replay = {
        "same_seed_same_stimulus": True,
        "max_abs_applied_dv_difference_mV": replay_dv_max,
        "max_abs_applied_gain_difference": replay_gain_max,
        "exact_chunkwise_match": bool(replay_dv_max == 0.0 and replay_gain_max == 0.0),
        "cadence_ms": 10.0,
        "per_target_window_mean_comparisons": target_comparisons,
        "max_abs_per_target_applied_dv_mean_difference_mV": replay_dv_mean_max,
        "max_abs_per_target_applied_gain_mean_difference": replay_gain_mean_max,
        "exact_per_target_window_mean_match": bool(
            replay_dv_mean_max == 0.0 and replay_gain_mean_max == 0.0
        ),
    }

    per_cell = []
    for i, cell in enumerate(cells):
        per_cell.append({**cell, "counts": {
            condition: {suffix: counts[:, i, c, p].astype(int).tolist()
                        for p, suffix in enumerate(suffixes)}
            for c, condition in enumerate(conditions)}})

    record = read(destination)
    record["first_sentence"] = (
        "Position is an imposed TuBu label assigned by ascending root ID, not seen and not "
        "validated visual coordinates; the fly does not see."
    )
    record["part_b"] = {
        "status": "complete", "outcome": reading(primary),
        "protocol": plan["protocol"], "frozen_part_a_commit": plan["frozen_part_a_commit"],
        "identity": identities[0], "executed_runner_sha256": identities[0]["runner_sha256"],
        "summarizing_runner_sha256": hash_file(Path(__file__)),
        "analysis_provenance": {
            "confirmatory_result": "dark versus activated primary endpoint only",
            "frozen_part_a_commit": "1cb0d6a045b73bc5b8cfd27a0eeeefd484a56ca7",
            "score_implementation_changed_after_freeze": False,
            "score_functions": [
                "historical_count_variability", "_variance", "_fit_affine", "_fold_score",
                "primary_endpoint", "bootstrap_primary", "cellwise_and_subtype_indices",
                "secondary_decoder",
            ],
            "post_run_changes": [
                "the raw-to-count-tensor summary wrapper and exact clamp comparisons were added after the neural run",
                "the read helper was routed from Path.read_text through flyonenomics.io.read_json after a static I/O gate failure",
            ],
        },
        "plan_sha256": hash_file(plan_path), "fixture_sha256": hash_file(ROOT / DEFAULT_FIXTURE),
        "brain_seconds": 3000.0, "seed_files": 10, "arms_per_seed": 15,
        "primary": primary, "cellwise_and_subtype": primary_indices,
        "secondary_decoder": primary_decoder_result,
        "joint_clamp_follow_up": {
            "status": "post_hoc",
            "status_reason": (
                "the joint-clamp intervention was fixed before launch, but Part A did not freeze "
                "these two endpoint comparisons or their bootstrap seeds"
            ),
            "dark_vs_driven_clamped": clamp_endpoint,
            "driven_clamped_vs_driven": direct_clamp_endpoint,
            "replay": replay,
            "interpretation_limit": (
                "as post-hoc evidence, the direct comparison says the measured tuning-pattern "
                "change depends on the implemented ER-local threshold-and-gain coupling with "
                "feedback live; it does not separate threshold from gain and is not evidence of "
                "a biological mechanism"
            ),
        },
        "stage5_condition": {
            "flywire_stage4_reproducible_er_position_code": True,
            "evidence": (
                "dark ER patterns decode at 40/40 with whole seeds held out across ten seeds; "
                "decoder saturation supplies no between-condition separation"
            ),
            "item_149_effect": (
                "no further FlyWire stage starts; stage 5 moves to the male brain after calibration, "
                "and this result does not establish a position code on that substrate"
            ),
        },
        "input_positive_control": source_control,
        "arm_summary": arm_summary, "er_position_contrasts": er_position_contrasts,
        "cells": per_cell,
        "historical_variability": history_info,
        "run_notes": {
            "platform": "linux-aarch64", "workers": 10,
            "prelaunch_memory_estimate": (
                "1.2 GB peak per worker, 12 GB total, from the prior 0.789 GB engine footprint "
                "plus build/Python margin; 88 GB was available, retaining more than one third of 94 GB"
            ),
            "measured_worker_rss": "1.23 to 1.46 GB during the run; at least 78 GB remained available",
            "disk_incident": (
                "the shared box disk was full from before 21:30 until about 21:55 UTC because "
                "another project's build output occupied it; run.log contains 148 logging-error "
                "blocks with OSError 28 from that window. At 22:00 all ten workers were alive and "
                "each seed had completed all five dark arms. There were no worker exceptions or "
                "Brian2 cache writes. run_seed writes seed-N.json atomically only at completion, "
                "so no result was partial or lost. At completion all ten files were present and "
                "each contained fifteen arms."
            ),
            "raw_directory": str(raw),
            "raw_sha256": {path.name: hash_file(path) for path in paths},
            "all_processes_ended": True,
        },
        "limits": [
            "Position is an imposed geometric TuBu label, not validated visual coordinates.",
            "The fly does not see because injection is downstream of a visual pathway that does not conduct.",
            "Four samples measure coarse position discrimination and cannot identify peak narrowing or shift.",
            "All 228 ER cells have one uniform receptor assignment; R2/R5 calcium results cannot calibrate the threshold and gain coefficients.",
            "The result applies to the transient-inclusive 18 s spike-count window only.",
        ],
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    record["generated_utc"] = datetime.now(timezone.utc).isoformat()
    dump(destination, record)
    print(json.dumps({
        "outcome": record["part_b"]["outcome"], "primary_score": primary["score"],
        "primary_interval": primary["interval"], "decoder": primary_decoder_result,
        "clamp_dark_interval": clamp_endpoint["interval"],
        "direct_clamp_interval": direct_clamp_endpoint["interval"],
        "replay": replay,
    }, indent=2))


def _parse_seeds(text: str) -> tuple[int, ...]:
    if "-" in text:
        lo, hi = text.split("-")
        return tuple(range(int(lo), int(hi) + 1))
    return tuple(int(value) for value in text.split(","))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    part = sub.add_parser("part-a", help="static census plus synthetic validation; no engine run")
    part.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--out", type=Path, default=DEFAULT_PLAN)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--out", type=Path, default=DEFAULT_AUDIT)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    run_parser.add_argument("--out", type=Path, default=DEFAULT_RAW)
    run_parser.add_argument("--workers", type=int, choices=range(1, 17), default=10)
    run_parser.add_argument("--seeds", default="1-10")
    run_parser.add_argument("--identity-only", action="store_true")
    summary_parser = sub.add_parser("summarize")
    summary_parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    summary_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    summary_parser.add_argument("--out", type=Path, default=DEFAULT_RECORD)
    summary_parser.add_argument("--seeds", default="1-10")
    args = parser.parse_args()
    if args.command == "part-a":
        build_part_a(args.record)
    elif args.command == "plan":
        build_plan(args.out)
    elif args.command == "audit":
        build_audit(args.out)
    elif args.command == "run":
        plan = read(args.plan)
        plan["identity"] = identity(f"{platform.system().lower()}-{platform.machine()}")
        dump(args.plan, plan)
        if args.identity_only:
            print(json.dumps(plan["identity"], indent=2))
        else:
            run_dynamic(args.plan, args.out, args.workers, _parse_seeds(args.seeds))
    elif args.command == "summarize":
        summarize(args.raw, args.plan, args.out, _parse_seeds(args.seeds))


if __name__ == "__main__":
    main()
