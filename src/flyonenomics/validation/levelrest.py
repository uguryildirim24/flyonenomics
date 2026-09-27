"""WP19 rest qualification: pure evaluators and recorded, input-bound entries.

Rates are per-neuron Hz, times seconds, dopamine µM. Evaluators accept
constructed tables as well as the measurement worker's rows. Missing,
nonfinite, duplicate or incomplete seed measurements cannot qualify.
"""
from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from flyonenomics.io import read_json
from flyonenomics.types import load_params

ROOT = Path(__file__).resolve().parents[3]
Q_ORDER = ("3.1br", "2.3r", "2.7r", "2.6r", "2.2r", "1.4r", "1.4r-ff", "2.4r")
IDS = ("1.3r", "1.4r", "1.4r-ff", "2.1r", "2.2r", "2.3r", "2.4r", "2.5r", "2.6r", "2.7r", "3.1r", "3.1r-alg", "3.1br")


def _vector(values: Any) -> np.ndarray:
    a = np.asarray(values, dtype=float)
    if a.ndim != 1 or not a.size or not np.isfinite(a).all():
        raise ValueError("measurement must be a nonempty finite vector")
    return a


def _seeds(rows: list[dict], count: int) -> None:
    if len(rows) != count or {r["seed"] for r in rows} != set(range(1, count + 1)):
        raise ValueError(f"expected exactly seeds 1 through {count}")


def _result(checks: dict[str, bool], **measured: Any) -> dict:
    return {"outcome": "passed" if all(checks.values()) else "failed", "checks": checks, **measured}


def objective(rates: dict[str, float], targets: dict[str, float]) -> float:
    """Placeholder-target J; rates/targets in Hz, one scalar squared-log sum."""
    observed, desired = _vector([rates[k] for k in targets]), _vector(list(targets.values()))
    if np.any(observed < 0) or np.any(desired <= 0):
        raise ValueError("rates must be nonnegative and targets positive")
    return float(np.square(np.log(np.maximum(observed, .01) / desired)).sum())


def reflex(differences: Any) -> dict:
    values = _vector(differences)
    if values.size != 10:
        raise ValueError("1.4r requires ten paired seeds")
    p = load_params(ROOT / "data/params-v0.2.yaml")
    return _result({"mean": bool(values.mean() > p.get("rest.reflex_mean_hz")),
                    "floor": bool(values.min() >= p.get("rest.reflex_seed_min_hz"))},
                   mean_hz=float(values.mean()), minimum_hz=float(values.min()), per_seed_hz=values.tolist())


def feedforward(bare: dict[str, Any], candidate: dict[str, Any]) -> dict:
    """Matched ten-seed sugar-minus-silent rates for both modes; ratios scalar."""
    ratios = {}
    for mode in ("upstream", "extended"):
        b, c = _vector(bare[mode]), _vector(candidate[mode])
        if b.size != 10 or c.size != 10 or b.mean() <= 0:
            raise ValueError("feed-forward retention needs ten seeds and a positive reference")
        ratios[mode] = float(c.mean() / b.mean())
    return _result({"extended_retention": ratios["extended"] >= .5}, retention=ratios,
                   bare=bare, candidate=candidate)


def validate_ff_fixtures(bare: str | Path, candidate: str | Path) -> None:
    """Enforce the declared scales-only exception using resolved twins, no engine.

    Only the owned paths qualify, and every resolved field except the flag and
    drive pin must agree. Dopamine remains v0.1, thresholds/background stay off.
    """
    from flyonenomics.schema import load_experiment
    expected = ROOT / "data/experiments/p2"
    if Path(bare).resolve() != (expected / "ff-bare.json").resolve() or Path(candidate).resolve() != (expected / "ff-candidate.json").resolve():
        raise ValueError("scales-only qualification is restricted to declared ff fixtures")
    b, c = (load_experiment(path).model_dump(mode="json") for path in (bare, candidate))
    # Labels are deliberately identical in the committed twins.
    if c["schema_version"] != "1.3" or not c["apply_scales_without_background"] or b.get("apply_scales_without_background"):
        raise ValueError("invalid scales-only fixture flags")
    if c["substrate"]["drive_version"] != "v0.2" or c["substrate"]["dopamine_version"] != "v0.1":
        raise ValueError("ff candidate must pin drive v0.2 and dopamine v0.1")
    if c["layers"]["background"] or not c["layers"]["dopamine_A"] or not c["layers"]["transporter_C"]:
        raise ValueError("ff requires background off with A and C on")
    c.pop("apply_scales_without_background", None)
    b.pop("apply_scales_without_background", None)
    c["substrate"].pop("drive_version", None)
    b["substrate"].pop("drive_version", None)
    if c != b or b["seeds"] != list(range(1, 11)):
        raise ValueError("feed-forward twins differ in matched protocol or seeds")
    probes = b["arms"][0]["protocol"]
    modes = {(p["params"].get("mode"), p["params"].get("rate_hz")) for p in probes}
    if len(b["arms"]) != 1 or len(probes) != 4 or modes != {(m, r) for m in ("upstream", "extended") for r in (0, 150)}:
        raise ValueError("ff fixtures require paired silent/sugar probes in both modes")
    if any(p["assay"] != "sugar_reflex" or p["duration_s"] != 1 or p["params"]["population"] != "sugar_GRN_R" for p in probes):
        raise ValueError("ff windows must be one-second sugar-GRN probes")


def bitter_suppression(sugar_hz: Any, coactivated_hz: Any) -> dict:
    """1.3r recorded bitter coactivation response; paired MN9 rates in Hz."""
    sugar, both = _vector(sugar_hz), _vector(coactivated_hz)
    if sugar.shape != both.shape or np.any(sugar < 0) or np.any(both < 0):
        raise ValueError("bitter suppression requires matched nonnegative rates")
    return {"outcome":"recorded", "below_half":bool(np.all(both < sugar/2)),
            "sugar_hz":sugar.tolist(), "sugar_bitter_hz":both.tolist()}


def rate_safety(rates: Any, *, stimulated: bool = False) -> dict:
    a = _vector(rates)
    if np.any(a < 0):
        raise ValueError("negative firing rate")
    median, high = float(np.median(a)), float(np.mean(a > 50))
    return _result({"median": (stimulated or median >= .2) and median <= 5,
                    "high_tail": high < .01}, median_hz=median, fraction_above_50_hz=high)


def screen(rows: list[dict]) -> dict:
    _seeds(rows, 3)
    p = load_params(ROOT / "data/params-v0.2.yaml")
    for row in rows:
        _vector([row[k] for k in ("F", "b", "stability_ratio", "central", "DAN", "KC")])
    means = {k: float(np.mean([r[k] for r in rows])) for k in ("central", "DAN", "KC")}
    checks = {"settled": all(r["settled"] is True for r in rows),
              "F": all(0 <= r["F"] < p.get("rest.fano_max") for r in rows),
              "b": all(0 <= r["b"] < p.get("rest.bin_fraction_max") for r in rows),
              "stability": all(.5 <= r["stability_ratio"] <= 2 for r in rows),
              "central": .5 <= means["central"] <= 8,
              "DAN": .5 <= means["DAN"] <= 10, "KC": 0 <= means["KC"] <= 2}
    return _result(checks, seed_means_hz=means, per_seed=rows)


def long_window(rows: list[dict]) -> dict:
    _seeds(rows, 10)
    for r in rows:
        _vector([r["F"], r["edge_ratio"]])
    return _result({"settled": all(r["settled"] is True for r in rows),
                    "F": all(0 <= r["F"] < 3 for r in rows),
                    "no_ignition": all(r["ignited"] is False for r in rows),
                    "stability": all(.5 <= r["edge_ratio"] <= 2 for r in rows)}, per_seed=rows)


def margin(baseline: list[dict], plus: list[dict], minus: list[dict]) -> dict:
    for rows in (baseline, plus, minus):
        _seeds(rows, 3)
    by_seed = [{r["seed"]: r for r in rows} for rows in (baseline, plus, minus)]
    checks = {}
    for seed in range(1, 4):
        b, p, m = (rows[seed] for rows in by_seed)
        _vector([b["central"], p["central"], m["central"], p["F"]])
        checks[str(seed)] = (b["central"] > 0 and p["central"] < 3*b["central"]
                            and m["central"] > b["central"]/3 and 0 <= p["F"] < 3
                            and all(r["settled"] is True for r in (b, p, m)))
    return _result(checks, baseline=baseline, plus=plus, minus=minus)


def jitter(baseline: dict, rows: list[dict]) -> dict:
    if len(rows) != 5 or {r["stream"] for r in rows} != set(range(5)):
        raise ValueError("2.4r requires five distinct JITTER streams")
    d = float(baseline["difference_hz"])
    checks = {}
    for r in rows:
        _vector([d, r["difference_hz"], r["F"], *baseline["groups"].values(), *r["groups"].values()])
        if set(r["groups"]) != set(baseline["groups"]):
            raise ValueError("jitter group set differs")
        group_ok = all((r["groups"][g] == 0 if v == 0 else 1/1.5 < r["groups"][g]/v < 1.5)
                       for g, v in baseline["groups"].items())
        checks[str(r["stream"])] = (abs(r["difference_hz"]-d) < .25*abs(d)
                                    and group_ok and 0 <= r["F"] < 3 and r["settled"] is True)
    return _result(checks, baseline=baseline, reruns=rows)


def qualification(rows: list[dict]) -> dict:
    _seeds(rows, 3)
    return _result({str(r["seed"]): r["settled"] is True and r["qualification"]["passed"] is True
                    for r in rows}, per_seed=rows)


def algebra() -> dict:
    """3.1r-alg checks fixed points independently at the seven boundary rates."""
    from flyonenomics.neuromod.calibration import rest_release_constants
    from flyonenomics.neuromod.pools import fixed_point
    p = load_params(ROOT / "data/params-v0.2.yaml")
    rmin = float(p.get("da.R_min"))
    rates = np.array([0, .01, .1, rmin-1e-9, rmin, rmin+1e-9, 10])
    alpha, source, mode = rest_release_constants(rates, p)
    balance = alpha*rates + source
    fp = fixed_point(balance, np.full(7, p.get("da.Vmax")), np.full(7, p.get("da.Km")), p.get("da.k_ns"))
    q = p.get("da.DA_ref")*(p.get("da.Vmax")/(p.get("da.Km")+p.get("da.DA_ref"))+p.get("da.k_ns"))
    return _result({"fixed_point": bool(np.all(np.abs(fp-p.get("da.DA_ref")) <= 1e-9)),
                    "nonnegative_source": bool(np.all(source >= 0)),
                    "bounded_alpha": bool(np.all(alpha <= q/rmin)),
                    "derived_source_zero": bool(np.all(source[rates >= rmin] == 0))},
                   rates_hz=rates.tolist(), alpha_c=alpha.tolist(), S_c=source.tolist(), mode=mode,
                   fixed_points_um=fp.tolist())


def entry(test_id: str):
    """Return measured evidence with its original identity; never relabel old bytes."""
    from flyonenomics.validation.binding import ValidationEntry, build_identity
    from flyonenomics.types import LayerFlags
    if test_id == "3.1r-alg":
        measured = algebra()
        inputs = ["data/params-v0.2.yaml"]
        identity = build_identity(ROOT, connectome_version="783", layers=LayerFlags(background=True),
                                  assay="spontaneous", declared_inputs=inputs, fixture="data/params-v0.2.yaml")
        return ValidationEntry(test_id=test_id, category="verification", outcome=measured["outcome"],
                               identity=identity, measured=measured, declared_inputs=inputs, fixture_path="data/params-v0.2.yaml")
    path = ROOT / "validation/records/p2" / f"entry-{test_id}.json"
    if path.is_file():
        result = ValidationEntry.model_validate(read_json(path))
        if result.test_id != test_id:
            raise ValueError("stored rest entry id differs")
        return result
    identity = build_identity(ROOT, connectome_version="783", layers=LayerFlags(background=True), assay="spontaneous")
    return ValidationEntry(test_id=test_id, category="consistency", outcome="unavailable", identity=identity,
                           compatibility="development", stub="WP19 measurement pending", measured={"reason": "not measured"})


SUITE = {test_id: partial(entry, test_id) for test_id in IDS}
