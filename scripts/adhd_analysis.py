"""Frozen seed-block analysis for docs/adhd-study-design.md; no engine imports.

Arrays: 5a rates (seed, off/position, cell); 5b (seed, condition, protocol, cell).
All rates are Hz. Cells and time bins are never independent replicates.
"""
from __future__ import annotations

import itertools
from typing import Any

import numpy as np

VERSION = "male-history-v1"
POSITIONS = (-150.0, -50.0, 50.0, 150.0)
CONDITIONS = ("wt-vehicle", "fumin-vehicle", "wt-release", "fumin-release")
PROTOCOLS = (("off", "off"), ("off", "A"), ("off", "B"), ("off", "AB"),
             ("A", "off"), ("A", "AB"), ("B", "off"), ("B", "AB"))
PAIR_ORDER = ((-50.0, 50.0), (-150.0, 150.0), (-150.0, 50.0),
              (-50.0, 150.0), (-150.0, -50.0), (50.0, 150.0))
BOOTSTRAPS = 10_000
BOOTSTRAP_SEED = 14620260922
CONFIRM_BOOTSTRAP_SEED = 14620260925
CONFIRM_SIGN_SEED = 14620260926
CONFIRM_SIGNS = 1_000_000
CONFIRM_CONDITIONS = CONDITIONS[:2]
CONFIRM_PROTOCOLS = PROTOCOLS[4:]


def decoder(rates: np.ndarray) -> dict[str, Any]:
    """LOSO nearest centroid; scale fitted only on training seeds, floor 1 Hz."""
    n, k, _ = rates.shape
    confusion = np.zeros((k, k), dtype=int)
    margins = np.empty((n, k))
    for held in range(n):
        train = rates[np.arange(n) != held]
        centroids = train.mean(axis=0)
        scale = np.maximum(train.reshape(-1, rates.shape[-1]).std(axis=0, ddof=1), 1.0)
        distance = np.square((rates[held, :, None] - centroids[None]) / scale).mean(axis=-1)
        prediction = distance.argmin(axis=1)
        confusion[np.arange(k), prediction] += 1
        correct = distance[np.arange(k), np.arange(k)].copy()
        distance[np.arange(k), np.arange(k)] = np.inf
        margins[held] = distance.min(axis=1) - correct
    return {"confusion": confusion.tolist(), "accuracy": float(confusion.trace() / (n * k)),
            "margins": margins.tolist()}


def templates(calibration: np.ndarray, pair: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    positions = [1 + POSITIONS.index(value) for value in pair]
    mean = calibration.mean(axis=0)
    basis = (mean[positions] - mean[0]).T
    difference = basis[:, 0] - basis[:, 1]
    norm = float(difference @ difference)
    if norm <= 0 or np.linalg.matrix_rank(basis) < 2:
        raise ValueError("unidentifiable A/B templates")
    return basis, difference / norm


def choose_pair(calibration: np.ndarray) -> dict[str, Any]:
    if calibration.ndim != 3 or calibration.shape[:2] != (10, 5):
        raise ValueError("5a needs ten complete seeds, off and four positions")
    rng = np.random.default_rng(BOOTSTRAP_SEED + 1)
    resamples = rng.integers(0, 10, (BOOTSTRAPS, 10))
    candidates = []
    chosen = None
    for pair in PAIR_ORDER:
        a, b = [1 + POSITIONS.index(value) for value in pair]
        comparisons = []
        for left, right in ((0, a), (0, b), (a, b)):
            result = decoder(calibration[:, [left, right]])
            margin = np.asarray(result["margins"])
            ci = np.quantile(margin[resamples].mean(axis=1), [0.025, 0.975], axis=0)
            comparisons.append({"indices": [left, right], **result,
                                "margin_ci95": ci.tolist(), "reliable": bool(np.all(ci[0] > 0))})
        try:
            basis, axis = templates(calibration, pair)
            independent = True
            condition = float(np.linalg.cond(basis))
        except ValueError:
            independent, condition = False, None
        eligible = all(c["reliable"] for c in comparisons) and independent
        candidates.append({"pair": list(pair), "comparisons": comparisons,
                           "template_condition_number": condition, "eligible": eligible})
        if eligible and chosen is None:
            chosen = pair
    record: dict[str, Any] = {"decoder_five_way": decoder(calibration),
                              "decoder_four_way": decoder(calibration[:, 1:]),
                              "candidates": candidates, "pair": chosen,
                              "prerequisite": "represented" if chosen else "failure"}
    if chosen:
        basis, axis = templates(calibration, chosen)
        record.update(axis=axis.tolist(), templates_hz=basis.tolist(),
                      template_gram=(basis.T @ basis).tolist())
    return record


def history_vectors(rates: np.ndarray) -> np.ndarray:
    """H before projection; protocol is the penultimate dimension."""
    return rates[..., 5, :] - rates[..., 4, :] - rates[..., 7, :] + rates[..., 6, :]


def contrasts(h: np.ndarray) -> np.ndarray:
    genotype = h[:, 1] - h[:, 0]
    return np.stack((genotype, h[:, 3] - h[:, 2] - genotype), axis=-1)


def sign_p(values: np.ndarray) -> float:
    """Exact two-sided sign randomisation, conditional on the fixed template."""
    signs = np.array(list(itertools.product((-1.0, 1.0), repeat=len(values))))
    null = np.abs(signs @ values / len(values))
    observed = abs(float(values.mean()))
    return float(np.mean(null >= observed - np.finfo(float).eps * max(1.0, observed) * 8))


def holm(p: np.ndarray) -> np.ndarray:
    order = np.argsort(p)
    adjusted = np.empty(len(p))
    adjusted[order] = np.minimum(1, np.maximum.accumulate(p[order] * np.arange(len(p), 0, -1)))
    return adjusted


def fit_affine(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Paired errors-in-variables moments over off/A/B (seed, stimulus, cell).

    Subtract sampling variance/covariance of the training stimulus means.
    A nonpositive corrected predictor variance has no identifiable slope;
    use an intercept-only prediction and report it, rather than extrapolate.
    """
    if x.shape != y.shape or x.shape[0] < 2 or x.shape[1] != 3:
        raise ValueError("affine fit requires paired seed blocks and three controls")
    n = len(x)
    xc, yc = x - x.mean(axis=1, keepdims=True), y - y.mean(axis=1, keepdims=True)
    xm, ym = xc.mean(axis=0), yc.mean(axis=0)
    dx, dy = xc - xm, yc - ym
    variance = np.mean(xm * xm - np.sum(dx * dx, axis=0) / (n * (n - 1)), axis=0)
    covariance = np.mean(xm * ym - np.sum(dx * dy, axis=0) / (n * (n - 1)), axis=0)
    resolved = variance > 0
    scale = np.maximum(0, np.divide(covariance, variance, out=np.zeros_like(variance), where=resolved))
    offset = y.mean(axis=(0, 1)) - scale * x.mean(axis=(0, 1))
    return scale, offset, resolved


def affine_residual(rates: np.ndarray, axis: np.ndarray, ids: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Cross-fit fumin vehicle from WT vehicle. Exclude duplicate held identities."""
    n = len(rates)
    ids = np.arange(n) if ids is None else ids
    hv = history_vectors(rates)
    residual = np.empty(n)
    predicted = np.empty((n, rates.shape[2], rates.shape[3]))
    unresolved = np.empty(n, dtype=int)
    for held in range(n):
        train = ids != ids[held]
        if np.unique(ids[train]).size < 2:
            raise ValueError("bootstrap has fewer than two independent training identities")
        a, b, resolved = fit_affine(rates[train, 0, :3], rates[train, 1, :3])
        residual[held] = (hv[held, 1] - a * hv[held, 0]) @ axis
        predicted[held] = a * rates[held, 0] + b
        unresolved[held] = np.sum(~resolved)
    return {"residual": residual, "predicted_fumin_hz": predicted, "unresolved_cells": unresolved}


def mixture(rates: np.ndarray, calibration: np.ndarray, pair: tuple[float, float]) -> dict[str, Any]:
    basis, _ = templates(calibration, pair)
    # Blank-prefix off is a condition-specific baseline; retain raw responses separately.
    evoked = rates - rates[:, :, :1, :]
    coefficients = evoked @ np.linalg.pinv(basis).T
    residual = evoked - coefficients @ basis.T
    return {"coefficients": coefficients.tolist(), "residual_hz": residual.tolist(),
            "residual_norm_hz": np.linalg.norm(residual, axis=-1).tolist(),
            "basis_condition_number": float(np.linalg.cond(basis)),
            "J_hz": (rates[:, :, 3] - rates[:, :, 1] - rates[:, :, 2] + rates[:, :, 0]).tolist()}


def analyse(rates: np.ndarray, calibration: np.ndarray, pair: tuple[float, float], *,
            replicates: int = BOOTSTRAPS) -> dict[str, Any]:
    if rates.shape[:3] != (10, 4, 8) or rates.shape[-1] != calibration.shape[-1]:
        raise ValueError("5b requires all ten seeds, four conditions and eight protocols")
    _, axis = templates(calibration, pair)
    hv = history_vectors(rates)
    h = hv @ axis
    delta = contrasts(h)
    secondary = affine_residual(rates, axis)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    boot = np.empty((replicates, 3))
    invalid = 0
    for r in range(replicates):
        take = rng.integers(0, 10, 10)
        cal_take = rng.integers(0, 10, 10)
        try:
            _, boot_axis = templates(calibration[cal_take], pair)
            boot[r, :2] = contrasts(hv[take] @ boot_axis).mean(axis=0)
            boot[r, 2] = affine_residual(rates[take], boot_axis, take)["residual"].mean()
        except ValueError:
            # Report undefined resamples; never silently substitute a fitted axis.
            boot[r] = np.nan
            invalid += 1
    valid = boot[np.all(np.isfinite(boot), axis=1)]
    if len(valid) == 0:
        raise ValueError("all bootstrap fits unidentifiable")
    ci = np.quantile(valid, [0.025, 0.975], axis=0)
    p = np.array([sign_p(delta[:, j]) for j in range(2)])
    adjusted = holm(p)
    primary = []
    for j, name in enumerate(("genotype", "difference_in_differences")):
        includes_zero = bool(ci[0, j] <= 0 <= ci[1, j])
        primary.append({"name": name, "mean": float(delta[:, j].mean()),
                        "per_seed": delta[:, j].tolist(), "ci95": ci[:, j].tolist(),
                        "p_exact": float(p[j]), "p_holm": float(adjusted[j]),
                        "reading": "no detected difference" if includes_zero else
                        ("detected difference" if adjusted[j] <= 0.05 else "nominal only; not Holm significant")})
    return {"version": VERSION, "H_per_seed_condition": h.tolist(), "primary": primary,
            "affine_secondary": {"mean": float(secondary["residual"].mean()),
                                 "ci95": ci[:, 2].tolist(),
                                 **{key: value.tolist() for key, value in secondary.items()}},
            "bootstrap": {"replicates": replicates, "invalid": invalid,
                          "pair_selection_uncertainty_included": False,
                          "template_uncertainty_included": True},
            "mixture": mixture(rates, calibration, pair),
            "genotype_gaps": [float(delta[:, 0].mean()), float((h[:, 3] - h[:, 2]).mean())]}


def monte_carlo_sign_p(values: np.ndarray, *, draws: int = CONFIRM_SIGNS,
                       seed: int = CONFIRM_SIGN_SEED) -> dict[str, Any]:
    """Two-sided paired sign randomisation; +1 avoids a reported zero p value."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or not len(values) or not np.all(np.isfinite(values)) or draws < 1:
        raise ValueError("nonempty finite paired values and positive draws required")
    rng = np.random.default_rng(seed)
    threshold = abs(float(values.mean())) - np.finfo(float).eps * max(1.0, abs(float(values.mean()))) * 8
    extreme = 0
    for start in range(0, draws, 10_000):
        signs = rng.integers(0, 2, (min(10_000, draws - start), len(values)), dtype=np.int8)
        extreme += int(np.count_nonzero(np.abs(((signs * 2 - 1) @ values) / len(values)) >= threshold))
    return {"extreme": extreme, "draws": draws, "seed": seed, "p": (extreme + 1) / (draws + 1)}


def confirm_analyse(rates: np.ndarray, calibration: np.ndarray, pair: tuple[float, float],
                    pilot: np.ndarray, *, replicates: int = BOOTSTRAPS,
                    draws: int = CONFIRM_SIGNS) -> dict[str, Any]:
    """The only confirmatory test; pilot data enter the descriptive pooled mean only."""
    from scipy.stats import ttest_1samp
    if rates.ndim != 4 or rates.shape[:3] != (40, 2, 4) or rates.shape[-1] != calibration.shape[-1]:
        raise ValueError("confirmation requires 40 complete seeds, two conditions, four history protocols")
    if pilot.shape != (10, 4, 8, rates.shape[-1]) or calibration.shape != (10, 5, rates.shape[-1]):
        raise ValueError("pilot and calibration shapes differ from frozen 5b/5a")
    if not np.all(np.isfinite(rates)) or not np.all(np.isfinite(pilot)):
        raise ValueError("nonfinite rates")
    _, axis = templates(calibration, pair)
    hv = rates[:, :, 1] - rates[:, :, 0] - rates[:, :, 3] + rates[:, :, 2]
    h = hv @ axis
    difference = h[:, 1] - h[:, 0]
    rng = np.random.default_rng(CONFIRM_BOOTSTRAP_SEED)
    boot = np.empty(replicates)
    invalid = 0
    for r in range(replicates):
        take = rng.integers(0, 40, 40)
        cal_take = rng.integers(0, 10, 10)
        try:
            _, boot_axis = templates(calibration[cal_take], pair)
            boot[r] = ((hv[take, 1] - hv[take, 0]) @ boot_axis).mean()
        except ValueError:
            boot[r] = np.nan
            invalid += 1
    valid = boot[np.isfinite(boot)]
    if not len(valid):
        raise ValueError("all bootstrap axes unidentifiable")
    ci = np.quantile(valid, [0.025, 0.975]).tolist()
    sign = monte_carlo_sign_p(difference, draws=draws)
    t = ttest_1samp(difference, 0)
    mean = float(difference.mean())
    sd = float(difference.std(ddof=1))
    pilot_h = history_vectors(pilot) @ axis
    pilot_difference = pilot_h[:, 1] - pilot_h[:, 0]
    pooled = np.concatenate((pilot_difference, difference))
    return {"version": "male-history-confirm-v1", "primary": {
                "name": "genotype", "mean": mean, "ci95": ci, "per_seed": difference.tolist(),
                "sign_randomisation": sign,
                "confirmed": bool(sign["p"] < 0.05 and mean < 0),
                "interval_reading": "no detected difference" if ci[0] <= 0 <= ci[1] else "interval excludes zero"},
            "bootstrap": {"replicates": replicates, "invalid": invalid,
                          "seed": CONFIRM_BOOTSTRAP_SEED, "template_uncertainty_included": True,
                          "pair_selection_uncertainty_included": False},
            "secondaries": {"paired_t": {"statistic": float(t.statistic) if np.isfinite(t.statistic) else None,
                                         "p_two_sided": float(t.pvalue) if np.isfinite(t.pvalue) else None},
                            "cohen_d_paired": mean / sd if sd else None,
                            "pooled_pilot_plus_confirmation": {"mean": float(pooled.mean()),
                                "per_seed": pooled.tolist(), "n": 50, "decision": False},
                            "H_per_seed_condition": h.tolist(),
                            "group_means_ranges": [{"condition": condition, "mean": float(h[:, j].mean()),
                                "range": [float(h[:, j].min()), float(h[:, j].max())]}
                                for j, condition in enumerate(CONFIRM_CONDITIONS)]}}


def synthetic_validation() -> dict[str, Any]:
    """Exact confound fixtures plus seeded overdispersed noisy planning examples."""
    rng = np.random.default_rng(14620260923)
    ncell = 245
    t_a = np.zeros(ncell); t_b = np.zeros(ncell)
    t_a[:80] = 4; t_b[80:160] = 4
    baseline = np.zeros(ncell); baseline[:180] = 0.5
    cal_mean = np.stack([baseline, baseline + t_a * 0.8, baseline + t_a,
                         baseline + t_b, baseline + t_b * 0.8])
    calibration = np.repeat(cal_mean[None], 10, axis=0)
    pair = (-50.0, 50.0)
    _, axis = templates(calibration, pair)
    records = []
    for scenario in ("symmetric_saturation", "fixed_spatial_bias", "affine_no_history",
                     "affine_with_history", "asymmetric_suppression", "known_genotype_shift"):
        x = np.zeros((10, 4, 8, ncell))
        pair_response = 0.6 * (t_a + t_b)
        if scenario == "fixed_spatial_bias":
            pair_response = 0.9 * t_a + 0.3 * t_b
        x[:] = baseline
        x[:, :, 1] += t_a; x[:, :, 2] += t_b
        x[:, :, [3, 5, 7]] += pair_response
        expected_h = 0.0
        expected_gen = 0.0
        if scenario in ("affine_with_history", "asymmetric_suppression"):
            x[:, :, 5] -= 0.25 * t_b
            x[:, :, 7] -= 0.25 * t_a
            expected_h = 0.25
        if scenario.startswith("affine"):
            scale = np.linspace(0.5, 1.8, ncell)
            x[:, 1] = x[:, 0] * scale + 0.3
            expected_gen = float(((scale - 1) * history_vectors(x)[0, 0]) @ axis)
        if scenario == "known_genotype_shift":
            x[:, 1, 5] += 0.2 * t_a
            x[:, 1, 7] += 0.2 * t_b
            expected_gen = 0.2
        h = history_vectors(x) @ axis
        gen = float(contrasts(h)[:, 0].mean())
        residual = float(affine_residual(x, axis)["residual"].mean())
        np.testing.assert_allclose(h[:, 0], expected_h, atol=1e-12)
        np.testing.assert_allclose(gen, expected_gen, atol=1e-12)
        if scenario.startswith("affine"):
            np.testing.assert_allclose(residual, 0, atol=1e-12)
        # Gamma-Poisson counts, 2 s exposure; no biological power assertion.
        mean_counts = x * 2
        noisy = rng.poisson(rng.gamma(10, mean_counts / 10)) / 2
        # Exercise exactly the inference used on real outcomes, including
        # cross-fitting and paired errors-in-variables bootstrap refits.
        noisy_record = analyse(noisy, calibration, pair, replicates=1000)
        records.append({"scenario": scenario, "exact_wt_H": expected_h,
                        "exact_genotype": gen, "exact_affine_residual": residual,
                        "noisy_primary": noisy_record["primary"],
                        "noisy_affine_secondary": {key: noisy_record["affine_secondary"][key]
                                                   for key in ("mean", "ci95", "unresolved_cells")},
                        "bootstrap": noisy_record["bootstrap"]})
    # Repeated seed noise is not allowed to select a distance-maximising pair.
    assert choose_pair(calibration)["pair"] == pair
    return {"version": VERSION, "cells": ncell, "seed": 14620260923,
            "noise": "Gamma-Poisson, variance=count_mean+count_mean^2/10, 2 s window; 65 sparse cells",
            "exact_assertions_passed": True, "scenarios": records,
            "interpretation": "Implementation validation, not a power guarantee or biological pass line"}
