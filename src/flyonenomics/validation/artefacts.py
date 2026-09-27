"""Artefact detectors and registry suites (WP2 owns the registry rows).

SUITE entries registry.inventory, registry.labels,
registry.precedence, and registry.completeness are canonical checks
(section 7.1: inventory, label, and precedence checks must pass;
completeness may be unknown). The Fano, weight-jitter, and
encoder-permutation detectors are WP3 hooks. SPEC-P2 section 9.2 adds
ignition, off-rest, DA gap, bias, photoreceptor-sign, and platform-agreement
detectors, within-eye encoder shuffles, and per
population sign-disagreement fractions.
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from flyonenomics.types import ENCODER, JITTER, Params, load_params

_INHIBITORY_NT = frozenset({"gaba", "glutamate", "histamine"})
_EXCITATORY_NT = frozenset({"acetylcholine", "dopamine", "serotonin", "octopamine", "tyramine"})
SIGN_DISAGREE_MAX = 0.10


def _param_or(params: Params | None, key: str, default: float) -> float:
    """Return a detector threshold from params (v0.2 when none are given). Units: per key.

    The section 9.2 rows exist only in params-v0.2.yaml. A missing row raises;
    default is kept in the signature as documentation of the SPEC value.
    """
    del default
    from flyonenomics.types import params_path_for_version

    store = params or load_params(params_path_for_version("v0.2"))
    return float(store.get(key))


def _transmitter_sign(value: Any, *, curated: bool = False) -> int | None:
    """Map one curated or predicted transmitter string to +1, -1, or None.

    Curated labels use the section 2.2.1 rule (first classical token, else
    modulatory), the same reading as the transmitter census.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if curated:
        from flyonenomics.substrate.transmitters import curated_class

        label = curated_class(value)
        if label is None:
            return None
        return -1 if label in ("Glu", "GABA", "His") else 1
    text = str(value).strip()
    if not text:
        return None
    token = text.replace("|", ",").replace(";", ",").split(",")[0].strip().lower()
    if token in _INHIBITORY_NT:
        return -1
    if token in _EXCITATORY_NT:
        return 1
    return None

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = "tests/fixtures/registry/checks.json"
DATA_DEPENDENCIES = [
    "params-v0.1.yaml",
    "populations-v0.1.yaml",
    "compartments-v0.1.yaml",
    "receptors-v0.1.yaml",
]


@functools.lru_cache(maxsize=1)
def _registry():  # type: ignore[no-untyped-def]
    """Build (once) the v783 registry.

    Units: per Registry fields. Shapes: W (n, 37), M (37, n).
    """
    from flyonenomics.registry import build_registry

    return build_registry()


@functools.lru_cache(maxsize=1)
def _annotations() -> pd.DataFrame:
    """Load (once) the v2.1.0 annotation artefact.

    Units: per column. Shapes: (139255, 27).
    """
    from flyonenomics.registry import annotations as ann

    return ann.load_annotations("v2.1.0")


def label_check() -> dict[str, Any]:
    """Count top_nt disagreements per population (section 9.2).

    Units: counts are neurons. Shapes: one row per population.
    Returns disagreements per population with an expected
    transmitter, the Kenyon-cell dopamine count, whether any
    selector was defined through top_nt, and the trip flag (trips
    only if a population was defined through top_nt, which none
    is).
    """
    from flyonenomics.registry.populations import (
        ExplicitSelector,
        RegexSelector,
        load_population_table,
    )

    registry = _registry()
    frame = _annotations().set_index("root_id")
    _, entries = load_population_table()
    per_population: dict[str, int] = {}
    missing: dict[str, int] = {}
    uses_top_nt = False
    for entry in entries:
        selector = entry.selector
        columns = []
        if not isinstance(selector, ExplicitSelector):
            columns.append(selector.column)
            if isinstance(selector, RegexSelector):
                if selector.or_column is not None:
                    columns.append(selector.or_column)
                if selector.and_column is not None:
                    columns.append(selector.and_column)
                if selector.not_column is not None:
                    columns.append(selector.not_column)
        if "top_nt" in columns:
            uses_top_nt = True
        if entry.expected_nt is None:
            continue
        population = registry.population(entry.name)
        disagree = 0
        absent = 0
        for root in (int(value) for value in population.root_ids):
            try:
                predicted = frame.loc[root, "top_nt"]
            except KeyError:
                absent += 1
                continue
            if pd.isna(predicted):
                absent += 1
            elif str(predicted) != entry.expected_nt:
                disagree += 1
        per_population[entry.name] = disagree
        missing[entry.name] = absent
    sign_fraction: dict[str, float] = {}
    sign_flagged: list[str] = []
    for name in registry.populations():
        population = registry.population(name)
        compared = 0
        disagree_sign = 0
        for root in (int(value) for value in population.root_ids):
            try:
                row = frame.loc[root]
            except KeyError:
                continue
            curated = _transmitter_sign(row["known_nt"] if "known_nt" in row.index else None, curated=True)
            predicted = _transmitter_sign(row["top_nt"] if "top_nt" in row.index else None)
            if curated is None or predicted is None:
                continue
            compared += 1
            if curated != predicted:
                disagree_sign += 1
        fraction = (disagree_sign / compared) if compared else 0.0
        sign_fraction[name] = fraction
        if fraction > SIGN_DISAGREE_MAX:
            sign_flagged.append(name)
    kenyon = registry.population("KC")
    kc_dopamine = 0
    for root in (int(value) for value in kenyon.root_ids):
        try:
            if str(frame.loc[root, "top_nt"]) == "dopamine":
                kc_dopamine += 1
        except KeyError:
            continue
    return {
        "per_population": per_population,
        "missing_top_nt": missing,
        "kc_dopamine": int(kc_dopamine),
        "kc_total": int(kenyon.count),
        "uses_top_nt": bool(uses_top_nt),
        "tripped": bool(uses_top_nt),
        "sign_disagreement_fraction": sign_fraction,
        "sign_disagreement_flagged": sign_flagged,
        "sign_disagreement_threshold": SIGN_DISAGREE_MAX,
    }


def input_completeness() -> dict[str, Any]:
    """Report population input completeness (SPEC 9.2 and 11.12).

    Units: synapses and dimensionless fractions. Shapes: one value per
    population. Divide summed in-model inputs by summed external totals,
    not an unweighted mean of neuron fractions. Empty populations, missing
    denominators, and zero total input report unknown; known fractions
    below the parameter threshold trip the detector.
    """
    from flyonenomics.registry import annotations as ann
    from flyonenomics.types import load_params

    registry = _registry()
    records = ann.provenance_records()
    codex = records.get("FlyWire Codex per-neuron synapse counts")
    threshold = float(load_params().get("artefact.completeness_min"))
    counts = ann.load_input_counts(registry.root_ids)
    fractions: dict[str, float | str] = {}
    details: dict[str, Any] = {}
    for name in registry.populations():
        idx = registry.population(name).idx
        if counts is None:
            fractions[name] = "unknown"
            details[name] = {"reason": "denominator not fetched"}
            continue
        numerator, denominator, present = counts
        missing = int((~present[idx]).sum())
        n_input, n_total = int(numerator[idx].sum()), int(denominator[idx].sum())
        details[name] = {"in_model_inputs": n_input, "total_inputs": n_total,
                         "missing_denominators": missing}
        fractions[name] = (float(n_input / n_total)
                           if idx.size and not missing and n_total > 0 else "unknown")
    tripped = [name for name, fraction in fractions.items()
               if isinstance(fraction, float) and fraction < threshold]
    return {
        "codex_status": codex.status if codex else "not fetched",
        "denominator_source": ann.POST_COUNT_ITEM,
        "denominator_status": "fetched" if counts is not None else "not fetched",
        "threshold": threshold,
        "populations": fractions,
        "details": details,
        "tripped_populations": tripped,
        "tripped": bool(tripped),
    }


class FanoAccumulator:
    """Online 1 ms population-bin detector; bin counts shape (n_bins,)."""

    def __init__(self, n_neurons: int, params: Params | None = None) -> None:
        """Create accumulator. Units: neurons; shapes: scalar state."""
        if n_neurons <= 0:
            raise ValueError("n_neurons must be positive")
        self.n_neurons = n_neurons
        self.params = params or load_params()
        self.n_bins = 0
        self.total = 0.0
        self.squares = 0.0
        self.maximum = 0.0

    def add(self, hist_1ms: np.ndarray) -> None:
        """Add one chunk's population spikes; units spikes/1 ms, shape (bins,)."""
        bins = np.asarray(hist_1ms, dtype=np.float64)
        if bins.ndim != 1 or np.any(bins < 0):
            raise ValueError("hist_1ms must be a nonnegative vector")
        self.n_bins += bins.size
        self.total += float(bins.sum())
        self.squares += float(np.square(bins).sum())
        self.maximum = max(self.maximum, float(bins.max(initial=0)))

    def report(self) -> dict[str, float | str | None]:
        """Return F and peak fraction; units dimensionless, shapes scalars."""
        if self.n_bins == 0 or self.total == 0:
            return {"F": None, "max_bin_fraction": 0.0, "status": "unknown"}
        mean = self.total / self.n_bins
        fano = max(0.0, self.squares / self.n_bins - mean * mean) / mean
        fraction = self.maximum / self.n_neurons
        tripped = (fano > float(self.params.get("artefact.sync_fano_max")) or
                   fraction > float(self.params.get("artefact.sync_bin_fraction_max")))
        return {"F": fano, "max_bin_fraction": fraction,
                "status": "tripped" if tripped else "clear"}


def fano_factor_detector(hist_1ms: np.ndarray | None = None, n_neurons: int | None = None,
                         params: Params | None = None) -> dict[str, float | str | None] | str:
    """Detect synchrony over bins; units spikes/1 ms, shape (n_bins,); no input means not run."""
    if hist_1ms is None and n_neurons is None:
        return "not run"
    if hist_1ms is None or n_neurons is None:
        raise ValueError("hist_1ms and n_neurons are required together")
    accumulator = FanoAccumulator(n_neurons, params)
    accumulator.add(hist_1ms)
    return accumulator.report()


def weight_jitter_detector(rerun: Callable[[np.ndarray], dict[str, float]] | None = None,
                           n_syn: int | None = None, baseline: dict[str, float] | None = None,
                           seed: int | None = None, params: Params | None = None) -> dict[str, Any] | str:
    """Rerun on log-normal scales; shape (n_syn,), headline scalars; no input means not run."""
    if rerun is None and n_syn is None and baseline is None and seed is None:
        return "not run"
    if rerun is None or n_syn is None or baseline is None or seed is None:
        raise ValueError("rerun, n_syn, baseline, and seed are required together")
    from flyonenomics.orchestrator.seeds import stream as _stream

    p = params or load_params()
    sigma = float(p.get("artefact.jitter_sigma"))
    records: list[dict[str, float]] = []
    for j in range(int(p.get("artefact.jitter_seeds"))):
        rng = _stream(seed, 0, j, JITTER)
        scale = rng.lognormal(mean=-sigma * sigma / 2, sigma=sigma, size=n_syn).astype(np.float32)
        records.append(rerun(scale))
    sign_changes = {key: any(np.sign(row[key]) != np.sign(value) for row in records)
                    for key, value in baseline.items()}
    return {"baseline": baseline, "reruns": records, "sign_changes": sign_changes,
            "status": "not robust to weights" if any(sign_changes.values()) else "clear"}


def within_eye_azimuth_shuffles(
    azimuths: np.ndarray, sides: np.ndarray, seed: int, n: int = 3,
    params: Params | None = None,
) -> list[np.ndarray]:
    """Return n within-eye shuffles of the R1-6 azimuth table. Units: degrees.

    Shapes: azimuths and sides (n_cells,); each shuffle copies azimuths.
    """
    from flyonenomics.orchestrator.seeds import stream as _stream

    values = np.asarray(azimuths)
    labels = np.asarray(sides)
    if values.shape != labels.shape:
        raise ValueError("azimuths and sides must share one shape")
    count = n if params is None else int((params or load_params()).get("artefact.encoder_perms"))
    shuffles: list[np.ndarray] = []
    for j in range(count):
        rng = _stream(seed, 0, j, ENCODER)
        shuffled = values.copy()
        for side in np.unique(labels):
            idx = np.flatnonzero(labels == side)
            shuffled[idx] = rng.permutation(shuffled[idx])
        shuffles.append(shuffled)
    return shuffles


def encoder_permutation_detector(rerun: Callable[[np.ndarray], dict[str, float]] | None = None,
                                 n_inputs: int | None = None, baseline: dict[str, float] | None = None,
                                 seed: int | None = None, params: Params | None = None,
                                 azimuths: np.ndarray | None = None, sides: np.ndarray | None = None,
                                 ) -> dict[str, Any] | str:
    """Rerun encoder permutations; shape (n_inputs,), headline scalars; no input means not run.

    When azimuths and sides are supplied, each rerun is one within-eye shuffle
    of the R1-6 azimuth table (SPEC-P2 section 9.2). A conclusion that survives
    every shuffle is reported not retinotopic.
    """
    if rerun is None and n_inputs is None and baseline is None and seed is None and azimuths is None:
        return "not run"
    if rerun is None or baseline is None or seed is None:
        raise ValueError("rerun, baseline, and seed are required together")
    from flyonenomics.orchestrator.seeds import stream as _stream

    p = params or load_params()
    n_perm = int(p.get("artefact.encoder_perms"))
    if azimuths is not None and sides is not None:
        orders = within_eye_azimuth_shuffles(azimuths, sides, seed, n_perm, params=p)
    else:
        if n_inputs is None:
            raise ValueError("n_inputs is required when azimuths are omitted")
        orders = [_stream(seed, 0, j, ENCODER).permutation(n_inputs) for j in range(n_perm)]
    records = [rerun(order) for order in orders]
    sign_changes = {key: any(np.sign(row[key]) != np.sign(value) for row in records)
                    for key, value in baseline.items()}
    survived = not any(sign_changes.values())
    if azimuths is not None and survived:
        status = "not retinotopic"
    else:
        status = "encoder-dependent" if any(sign_changes.values()) else "clear"
    return {"baseline": baseline, "reruns": records, "sign_changes": sign_changes,
            "status": status, "within_eye": azimuths is not None}


def ignition_detector(
    central_hz: np.ndarray | None = None, settled_central_mean: float | None = None,
    params: Params | None = None,
) -> dict[str, Any] | str:
    """Flag a 1 s rest-substrate window above ign.factor or ign.max_central_hz."""
    if central_hz is None and settled_central_mean is None:
        return "not run"
    if central_hz is None or settled_central_mean is None:
        raise ValueError("central_hz and settled_central_mean are required together")
    series = np.asarray(central_hz, dtype=float)
    factor = _param_or(params, "ign.factor", 3.0)
    cap = _param_or(params, "ign.max_central_hz", 8.0)
    floor = _param_or(params, "ign.min_baseline_hz", 0.5)
    peak = float(series.max()) if series.size else 0.0
    settled = float(settled_central_mean)
    relative = settled >= floor and peak > factor * settled
    tripped = relative or peak > cap
    return {"peak_hz": peak, "settled_mean_hz": settled,
            "status": "ignited" if tripped else "clear", "tripped": tripped}


def off_rest_detector(
    rates: dict[str, float] | None = None, qrest_rates: dict[str, float] | None = None,
    targeted: Sequence[str] | None = None, params: Params | None = None,
) -> dict[str, Any] | str:
    """Flag wild-type groups outside offrest.factor of the Q-rest rate. Reported, not failing."""
    if rates is None and qrest_rates is None:
        return "not run"
    if rates is None or qrest_rates is None:
        raise ValueError("rates and qrest_rates are required together")
    factor = _param_or(params, "offrest.factor", 2.0)
    skip = set(targeted or ())
    flagged: dict[str, dict[str, float]] = {}
    for name, rate in rates.items():
        if name in skip or name not in qrest_rates:
            continue
        ref = float(qrest_rates[name])
        observed = float(rate)
        if ref <= 0:
            continue
        ratio = float("inf") if observed <= 0 else (observed / ref if observed >= ref else ref / observed)
        if ratio > factor:
            flagged[name] = {"rate_hz": observed, "qrest_hz": ref, "ratio": ratio}
    return {"flagged": flagged, "status": "off-rest" if flagged else "clear", "tripped": False}


def da_gap_detector(
    gaps: dict[str, float] | None = None, fixed_points: dict[str, float] | None = None,
    params: Params | None = None,
) -> dict[str, Any] | str:
    """Flag compartments whose fixed-point gap exceeds detector.da_gap_fraction. Reported."""
    if gaps is None and fixed_points is None:
        return "not run"
    if gaps is None or fixed_points is None:
        raise ValueError("gaps and fixed_points are required together")
    fraction = _param_or(params, "detector.da_gap_fraction", 0.25)
    flagged: dict[str, dict[str, float]] = {}
    for name, gap in gaps.items():
        fp = float(fixed_points.get(name, 0.0))
        if fp <= 0:
            continue
        value = abs(float(gap))
        if value > fraction * fp:
            flagged[name] = {"gap": value, "fixed_point": fp, "fraction": value / fp}
    return {"flagged": flagged, "status": "da-gap" if flagged else "clear", "tripped": False}


def bias_dominated_detector(
    bias_hz: float | None = None, tuning_hz: np.ndarray | None = None,
    params: Params | None = None,
) -> dict[str, Any] | str:
    """Flag |bias_hz| above bias.max_fraction of the 4.1r tuning range."""
    if bias_hz is None and tuning_hz is None:
        return "not run"
    if bias_hz is None or tuning_hz is None:
        raise ValueError("bias_hz and tuning_hz are required together")
    curve = np.asarray(tuning_hz, dtype=float)
    span = float(curve.max() - curve.min()) if curve.size else 0.0
    fraction = _param_or(params, "bias.max_fraction", 0.5)
    tripped = span > 0 and abs(float(bias_hz)) > fraction * span
    return {"bias_hz": float(bias_hz), "tuning_span_hz": span,
            "status": "bias-dominated" if tripped else "clear", "tripped": tripped}


def photoreceptor_sign_detector(
    conclusion: str | None = None, histamine_off_conclusion: str | None = None,
) -> dict[str, Any] | str:
    """Report 4.8r dependence on photoreceptor sign. Expected, not a failure."""
    if conclusion is None and histamine_off_conclusion is None:
        return "not run"
    if conclusion is None or histamine_off_conclusion is None:
        raise ValueError("both conclusions are required together")
    depends = conclusion != histamine_off_conclusion
    return {"conclusion": conclusion, "histamine_off": histamine_off_conclusion,
            "status": "depends on photoreceptor sign" if depends else "clear", "tripped": False}


def platform_agreement_detector(
    mac: dict[str, Any] | None = None, camber: dict[str, Any] | None = None,
    criterion_key: str = "passed",
) -> dict[str, Any] | str:
    """Flag Camber vs Mac central-rate disagreement above 25 percent, or a criterion flip."""
    if mac is None and camber is None:
        return "not run"
    if mac is None or camber is None:
        raise ValueError("mac and camber mappings are required together")
    mac_hz = float(mac.get("central_hz", 0.0))
    camber_hz = float(camber.get("central_hz", 0.0))
    # Keep the established Mac-denominator convention for this comparison metric.
    rel = abs(mac_hz - camber_hz) / abs(mac_hz) if mac_hz != 0 else (0.0 if camber_hz == 0 else float("inf"))
    flip = bool(mac.get(criterion_key)) != bool(camber.get(criterion_key))
    tripped = rel > 0.25 or flip
    return {"relative_central_difference": rel, "criterion_flip": flip,
            "status": "platform-sensitive" if tripped else "clear", "tripped": tripped}


def _entry(test_id: str, measured: dict[str, Any]) -> Any:
    """Wrap measured values in a canonical ValidationEntry.

    Units: per measured row. Shapes: scalars and small mappings.
    """
    from flyonenomics.types import LayerFlags
    from flyonenomics.validation.binding import ValidationEntry, build_identity

    identity = build_identity(
        ROOT,
        connectome_version="783",
        layers=LayerFlags(),
        assay="registry",
        fixture=FIXTURE,
    )
    return ValidationEntry(
        test_id=test_id,
        category="verification",
        outcome="passed",
        compatibility="canonical",
        identity=identity,
        measured=measured,
        data_dependencies=list(DATA_DEPENDENCIES),
        fixture_path=FIXTURE,
    )


def check_inventory_suite() -> Any:
    """Inventory check: every population resolves within its interval.

    Units: counts are neurons. Shapes: one row per population.
    Registry construction already fails on breach; this records the
    counts.
    """
    registry = _registry()
    counts = {}
    for name in registry.populations():
        count, (low, high) = registry.inventory(name)
        assert low <= count <= high, name
        counts[name] = {"count": int(count), "low": int(low), "high": int(high)}
    return _entry("registry.inventory", {"populations": counts})


def check_labels_suite() -> Any:
    """Label check: top_nt disagreements with the Kenyon-cell count.

    Units: counts are neurons. Shapes: one row per population with
    an expected transmitter.
    """
    report = label_check()
    assert report["tripped"] is False
    return _entry("registry.labels", report)


def check_precedence_suite() -> Any:
    """Precedence check: the receptor order is total over overlaps.

    Units: none. Shapes: one overlap list per row population.
    """
    from flyonenomics.registry import receptors as rec

    registry = _registry()
    table = rec.load_receptor_table()
    roots_of = {name: registry.population(name).root_ids for name in registry.populations()}
    overlaps = rec.check_precedence(table, roots_of)
    return _entry("registry.precedence", {
        "precedence": list(table.precedence),
        "overlaps": {name: list(others) for name, others in overlaps.items()},
    })


def check_completeness_suite() -> Any:
    """Record completeness, including advisory trips and unknown values.

    Units: fractions dimensionless. Shapes: one row per population.
    """
    report = input_completeness()
    return _entry("registry.completeness", report)


SUITE = {
    "registry.inventory": check_inventory_suite,
    "registry.labels": check_labels_suite,
    "registry.precedence": check_precedence_suite,
    "registry.completeness": check_completeness_suite,
}
