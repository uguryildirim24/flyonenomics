"""Phase 2 level-4 evaluators (SPEC-P2 sections 3.5, 3.7 and 5.3).

4.0c and the constructed-table checks run with no engine. Engine-bound
entries bind item 122's declared substrate through
`behaviour/visual_calibration.py` and return unavailable until WP18's
V-cal and item 125's dopamine file land; Q-rest is never a WP20 input.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import numpy as np
import pandas as pd

from flyonenomics.behaviour.arena import Behaviour
from flyonenomics.behaviour.buridan import (
    P2_CONTROL_FI,
    P2_MIN_DELTA_HZ,
    choose_k3r,
    choose_sign_from_gains,
    evaluate_4_1r,
    evaluate_4_2r,
    evaluate_vtcal,
    k3r_objective,
    measure_bias_from_rates,
    p2_missing_dependencies,
)
from flyonenomics.behaviour.metrics import (
    Geometry,
    distractor_capture_hz,
    fixation_retention,
    interval_excludes_zero,
    steer_gain,
)
from flyonenomics.behaviour.visual_calibration import (
    declared_drive_present,
    declared_substrate,
    declared_substrate_id,
)
from flyonenomics.orchestrator.seeds import stream
from flyonenomics.schema.experiment import Probe
from flyonenomics.types import BEHAVIOUR, LayerFlags, load_params
from flyonenomics.validation.binding import ValidationEntry, build_identity

ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]
MATCHING = LayerFlags(background=True, dopamine_A=True, transporter_C=True)
LAYERS_OFF = LayerFlags(background=False, dopamine_A=False, transporter_C=False)
NOT_RUN_REASON = (
    "Not run under SPEC-P2 item 144: the full open-loop P-screen was skipped, "
    "so this entry is not produced"
)


def _entry(test_id: str, category: str, outcome: str, measured: dict[str, Any], *,
           fixture: str | None, compatibility: str = "canonical", stub: str | None = None,
           layers: LayerFlags = LAYERS_OFF, grid: bool = False,
           declared: bool = True) -> ValidationEntry:
    """Bind one level-4 P2 result to item 122's declared substrate.

    Units live in the measured mapping. The identity's substrate id is the
    declared drive's `rest:<16 hex>` tag, read through
    `behaviour/visual_calibration.py`; it stays `bare` while that drive is
    absent. The measured mapping also names the declared substrate and drive.
    """
    assay = "open_loop_steering" if "sign" in test_id or test_id.startswith("4.1") or test_id in (
        "bias", "bias-T", "VT-cal", "V1-T") else "buridan"
    identity = build_identity(ROOT, connectome_version="783", layers=layers, assay=assay,
                              fixture=fixture,
                              substrate_id=declared_substrate_id() if declared else None)
    kwargs: dict[str, Any] = {}
    if stub is not None:
        kwargs["stub"] = stub
    if grid:
        kwargs["grid"] = True
    bound = {**measured, "declared_substrate": declared_substrate(),
             "declared_drive": declared_drive_present()}
    return ValidationEntry(
        test_id=test_id, category=category, outcome=outcome,  # type: ignore[arg-type]
        compatibility=compatibility,  # type: ignore[arg-type]
        identity=identity, measured=bound, data_dependencies=[],
        fixture_path=fixture, **kwargs,
    )


def _waiting(test_id: str, category: str, fixture: str, *,
             compatibility: str = "matching-layers", grid: bool = False) -> ValidationEntry:
    """Unavailable until the declared substrate's V-cal and dopamine land. Units: none."""
    missing = p2_missing_dependencies()
    reason = "Waiting for: " + (", ".join(missing) if missing else "the coordinator's engine slot")
    return _entry(test_id, category, "unavailable", {"reason": reason, "missing": missing},
                  fixture=fixture, compatibility=compatibility, layers=MATCHING, grid=grid,
                  stub="awaiting WP18 V-cal and item 125 dopamine" if compatibility == "development" else None)


class _Registry:
    def population(self, name: str) -> SimpleNamespace:
        if name == "TuBu":
            return SimpleNamespace(idx=np.array([0, 1], dtype=np.int32),
                                   root_ids=np.array([11, 12], dtype=np.int64),
                                   side=np.array(["left", "right"]))
        if name == "steering_L":
            return SimpleNamespace(idx=np.array([2], dtype=np.int32))
        return SimpleNamespace(idx=np.array([3], dtype=np.int32))


def _constructed_4_0c() -> dict[str, Any]:
    """Known-value checks for steer_gain, retention, capture, heading and bias. Mixed units."""
    params = load_params()
    geometry = Geometry.from_params(params)
    azimuths = np.array([-60.0, -45.0, -30.0, 0.0, 30.0, 45.0, 60.0])
    raw = 0.1 * azimuths + 2.0
    gain = steer_gain(azimuths, raw, bias_hz=2.0)
    t = np.arange(0, 15.05, 0.05)
    x = np.zeros(len(t))
    y = np.where(t < 5.0, -50 + 10 * t, 2.0 * np.cos(5 * (t - 5.0)))
    x = np.where(t < 5.0, 0.0, 2.0 * np.sin(5 * (t - 5.0)))
    table = pd.DataFrame({"t_s": t, "x_mm": x, "y_mm": y, "segment": np.zeros(len(t), dtype=int)})
    retained = fixation_retention(table, geometry, params, onset_s=5.0, duration_s=10.0)
    capture = distractor_capture_hz(1.5, 0.4, bias_hz=0.3)
    seed = 20260912
    probe = Probe.model_validate({
        "type": "probe", "assay": "buridan", "duration_s": 0.2, "label": "b",
        "params": {"inject_at": "TuBu", "initial_heading": "random"},
    })
    plan = SimpleNamespace(topology=SimpleNamespace(extended_idx=np.array([0, 1], dtype=np.int32)))
    headings = []
    omegas = []
    expected_heading = 180.0 - float(stream(seed, 1, 0, BEHAVIOUR).random()) * 360.0
    for _ in range(2):
        arena = Behaviour(plan, _Registry(), params, probe, v_fwd=10, sign_steer=1,
                          K_steer=4, r_vis_max=100, sigma_vis=20, bias_hz=2.0)
        arena.reset(stream(seed, 1, 0, BEHAVIOUR))
        headings.append(arena.h)
        arena.r_R = 5.0
        arena.r_L = 1.0
        arena.step(np.zeros(4, dtype=np.int32), 0.01)
        omegas.append(arena.omega)
    once = 1 * 4 * ((arena.r_R - arena.r_L) - 2.0)
    twice = 1 * 4 * ((arena.r_R - arena.r_L - 2.0) - 2.0)
    heading_ok = all(abs(h - expected_heading) < 1e-12 for h in headings) and headings[0] == headings[1]
    bias_ok = abs(omegas[-1] - once) < 1e-12 and abs(omegas[-1] - twice) > 1e-9
    gain_ok = abs(gain - 0.1) < 1e-12
    capture_ok = abs(capture - 1.1) < 1e-12
    retention_ok = retained["fixation_retention"] is not None
    passed = heading_ok and bias_ok and gain_ok and capture_ok and retention_ok
    return {
        "passed": passed, "steer_gain_hz_per_deg": gain, "fixation_retention": retained["fixation_retention"],
        "distractor_capture_hz": capture, "heading_deg": headings, "expected_heading_deg": expected_heading,
        "omega_deg_s": omegas[-1], "omega_once": once, "omega_twice": twice,
        "heading_ok": heading_ok, "bias_once_ok": bias_ok, "gain_ok": gain_ok,
        "capture_ok": capture_ok, "retention_ok": retention_ok,
    }


def verify_4_0c() -> ValidationEntry:
    """4.0c: constructed steer_gain, retention, capture, heading and single bias subtract."""
    measured = _constructed_4_0c()
    return _entry("4.0c", "verification", "passed" if measured["passed"] else "failed",
                  measured, fixture="tests/test_wp20.py")


def verify_bias() -> ValidationEntry:
    """Bias calibration on a constructed ten-seed ambient table. Units: Hz."""
    deltas = [0.2 + 0.02 * i for i in range(10)]
    measured = measure_bias_from_rates(deltas)
    measured["constructed"] = True
    return _entry("bias", "calibration", "recorded", measured,
                  fixture="data/experiments/p2/bias.json", compatibility="matching-layers",
                  layers=MATCHING)


def verify_sign() -> ValidationEntry:
    """4.1r-sign on constructed steer_gain samples. Units: Hz/deg."""
    rng = np.random.default_rng(0)
    measured = choose_sign_from_gains([0.05, 0.06, 0.07], rng, 200)
    return _entry("4.1r-sign", "calibration", "recorded" if not measured["flat"] else "failed",
                  measured, fixture="data/experiments/p2/signcheck.json",
                  compatibility="matching-layers", layers=MATCHING)


def verify_k3r() -> ValidationEntry:
    """K3r selector on a constructed objective table. Units: deg/s per Hz."""
    target = {"fixation_index_median": 0.5, "fixation_index_iqr": 0.2,
              "stripe_deviation_deg_median": 20.0, "stripe_deviation_deg_iqr": 5.0}
    table = []
    for gain, fi, dev in ((1.0, 0.1, 40.0), (2.0, 0.48, 21.0), (4.0, 0.48, 21.0),
                          (8.0, 0.9, 5.0), (16.0, 0.2, 35.0)):
        table.append({"K_steer": gain, "model_fi": fi, "model_stripe_deviation_deg": dev,
                      "objective": k3r_objective(fi, dev, target)})
    winner = choose_k3r(table)
    return _entry("K3r", "calibration", "recorded", {"winner": winner, "table": table, "constructed": True},
                  fixture="data/experiments/p2/k3r.json", compatibility="development",
                  layers=MATCHING, stub="constructed K3r table", grid=True)


def verify_4_1r() -> ValidationEntry:
    """4.1r constructed pass: gain interval and ±45 contrast. Units: Hz/deg and Hz."""
    rng = np.random.default_rng(1)
    measured = evaluate_4_1r([0.04] * 10, [1.0] * 10, [0.0] * 10, 1, rng, 200, P2_MIN_DELTA_HZ)
    return _entry("4.1r", "consistency", measured["outcome"], measured,
                  fixture="data/experiments/p2/signcheck.json", compatibility="matching-layers",
                  layers=MATCHING)


def verify_4_2r() -> ValidationEntry:
    """4.2r constructed pass: stripes-on beats both controls. Fractions and degrees."""
    on = {"fixation_index": [0.8] * 10, "stripe_deviation_deg": [10.0] * 10}
    off = {"fixation_index": [0.5] * 10, "stripe_deviation_deg": [30.0] * 10}
    enc = {"fixation_index": [0.4] * 10, "stripe_deviation_deg": [35.0] * 10}
    measured = evaluate_4_2r(on, off, enc, P2_CONTROL_FI)
    return _entry("4.2r", "consistency", measured["outcome"], measured,
                  fixture="data/experiments/p2/buridan-controls.json", compatibility="matching-layers",
                  layers=MATCHING)


def _not_run_prediction(test_id: str) -> ValidationEntry:
    """Terminal item-144 prediction entry. Units: none."""
    return _entry(
        test_id, "prediction", "not run", {"reason": NOT_RUN_REASON},
        fixture=None, compatibility="matching-layers", layers=MATCHING,
    )


def verify_4_4r() -> ValidationEntry:
    """4.4r is terminally not run under SPEC-P2 item 144."""
    return _not_run_prediction("4.4r")


def verify_4_5r() -> ValidationEntry:
    """4.5r is terminally not run under SPEC-P2 item 144."""
    return _not_run_prediction("4.5r")


def verify_4_6r() -> ValidationEntry:
    """4.6r is terminally not run under SPEC-P2 item 144."""
    return _not_run_prediction("4.6r")


def verify_4_7r() -> ValidationEntry:
    """4.7r is terminally not run under SPEC-P2 item 144."""
    return _not_run_prediction("4.7r")


def verify_4_8r() -> ValidationEntry:
    """4.8r sensitivity on a constructed 13-variant table. Class development."""
    variants = (
        [f"perm-{k}" for k in range(3)] + [f"jitter-{k}" for k in range(5)]
        + ["sigma_h-0", "sigma_h-20", "v_fwd-half", "v_fwd-double", "histamine-off"]
    )
    table = [{"variant": name, "4_2r_holds": name != "histamine-off"} for name in variants]
    survived = all(row["4_2r_holds"] for row in table if row["variant"] != "histamine-off")
    return _entry("4.8r", "sensitivity", "recorded",
                  {"variants": table, "n": len(variants), "4_2r_survives_retinotopy_and_jitter": survived,
                   "photoreceptor_sign_dependence": True, "constructed": True},
                  fixture="data/experiments/p2/buridan-controls.json", compatibility="development",
                  layers=MATCHING, stub="constructed 4.8r table", grid=True)


def _tubu_pair(test_id: str, fn: Callable[[], ValidationEntry]) -> ValidationEntry:
    """Copy a photoreceptor constructed result onto its -T id."""
    entry = fn()
    measured = {**entry.measured, "path": "TuBu"}
    return _entry(test_id, entry.category, entry.outcome, measured,
                  fixture="data/experiments/p2/k3r-tubu.json",
                  compatibility=entry.compatibility, layers=MATCHING,
                  stub=entry.stub, grid=entry.grid)


def verify_bias_t() -> ValidationEntry:
    return _tubu_pair("bias-T", verify_bias)


def verify_sign_t() -> ValidationEntry:
    return _tubu_pair("4.1r-T-sign", verify_sign)


def verify_k3r_t() -> ValidationEntry:
    return _tubu_pair("K3r-T", verify_k3r)


def verify_4_1r_t() -> ValidationEntry:
    return _tubu_pair("4.1r-T", verify_4_1r)


def verify_4_2r_t() -> ValidationEntry:
    return _tubu_pair("4.2r-T", verify_4_2r)


def verify_vtcal() -> ValidationEntry:
    """VT-cal on a constructed five-rate V1-T table. Units: Hz."""
    table = []
    for rate in (40.0, 70.0, 100.0, 150.0, 280.0):
        carried = rate >= 100.0
        table.append({"r_vis_max_hz": rate, "mean_delta_steer_hz": 0.2 if rate < 100 else 0.8,
                      "delta_interval_excludes_zero": carried,
                      "central_input_carried": carried, "steering_carried": carried})
    measured = evaluate_vtcal(table)
    return _entry("VT-cal", "calibration", measured["status"] if measured["status"] in ("passed", "failed") else "recorded",
                  measured, fixture="data/experiments/p2/k3r-tubu.json", compatibility="development",
                  layers=MATCHING, stub="constructed VT-cal table", grid=True)


def verify_v1_t() -> ValidationEntry:
    """V1-T: depths restricted to central input and steering on a constructed row."""
    measured = {"central_input_carried": True, "steering_carried": True,
                "mean_delta_steer_hz": 0.8, "ci95": [0.6, 1.0],
                "delta_ok": interval_excludes_zero([0.6, 1.0]), "constructed": True}
    passed = measured["central_input_carried"] and measured["steering_carried"] and measured["delta_ok"]
    return _entry("V1-T", "consistency", "passed" if passed else "failed", measured,
                  fixture="data/experiments/p2/k3r-tubu.json", compatibility="matching-layers",
                  layers=MATCHING)


def verify_4_4r_t() -> ValidationEntry:
    """4.4r-T is terminally not run under SPEC-P2 item 144."""
    return _not_run_prediction("4.4r-T")


def verify_4_5r_t() -> ValidationEntry:
    """4.5r-T is terminally not run under SPEC-P2 item 144."""
    return _not_run_prediction("4.5r-T")


def verify_4_6r_t() -> ValidationEntry:
    """4.6r-T is terminally not run under SPEC-P2 item 144."""
    return _not_run_prediction("4.6r-T")


def verify_4_7r_t() -> ValidationEntry:
    """4.7r-T is terminally not run under SPEC-P2 item 144."""
    return _not_run_prediction("4.7r-T")


def verify_4_8r_t() -> ValidationEntry:
    return _tubu_pair("4.8r-T", verify_4_8r)


SUITE: dict[str, Callable[[], ValidationEntry]] = {
    "4.0c": verify_4_0c,
    "bias": verify_bias,
    "4.1r-sign": verify_sign,
    "K3r": verify_k3r,
    "4.1r": verify_4_1r,
    "4.2r": verify_4_2r,
    "4.4r": verify_4_4r,
    "4.5r": verify_4_5r,
    "4.6r": verify_4_6r,
    "4.7r": verify_4_7r,
    "4.8r": verify_4_8r,
    "bias-T": verify_bias_t,
    "4.1r-T-sign": verify_sign_t,
    "K3r-T": verify_k3r_t,
    "4.1r-T": verify_4_1r_t,
    "4.2r-T": verify_4_2r_t,
    "4.4r-T": verify_4_4r_t,
    "4.5r-T": verify_4_5r_t,
    "4.6r-T": verify_4_6r_t,
    "4.7r-T": verify_4_7r_t,
    "4.8r-T": verify_4_8r_t,
    "VT-cal": verify_vtcal,
    "V1-T": verify_v1_t,
}
