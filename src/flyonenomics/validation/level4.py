"""Level 4 Buridan metric verification and provisional development status."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from flyonenomics.behaviour.brembs import load_reference, verify_4_0b as reference_check_4_0b
from flyonenomics.io import read_yaml
from flyonenomics.behaviour.buridan import choose_sign
from flyonenomics.behaviour.metrics import Geometry, mindistkeep3, score
from flyonenomics.types import LayerFlags, load_params
from flyonenomics.validation.binding import ValidationEntry, build_identity, sha256_file

ROOT = Path(__file__).resolve().parents[3]
LAYERS_OFF = LayerFlags(background=False, dopamine_A=False, transporter_C=False)


def _entry(test_id: str, category: str, outcome: str, measured: dict[str, Any], *,
           fixture: str, compatibility: str = "canonical", stub: str | None = None,
           layers: LayerFlags = LAYERS_OFF) -> ValidationEntry:
    """Bind one engine-free level-4 result; values carry units in measured mapping."""
    identity = build_identity(ROOT, connectome_version="783", layers=layers,
                              assay="open_loop_steering" if test_id.startswith("4.1") else "buridan", fixture=fixture)
    return ValidationEntry(test_id=test_id, category=category, outcome=outcome,
                           compatibility=compatibility, identity=identity,
                           measured=measured, data_dependencies=["params-v0.1.yaml"] +
                           (["behaviour-v0.1.yaml", "dopamine-v0.1.yaml"] if compatibility == "matching-layers" else []),
                           fixture_path=fixture, stub=stub)


def verify_4_0() -> ValidationEntry:
    """Verify engine-free constructed walk/freeze/stationary cases; mm, degrees, counts."""
    t = np.arange(0, 10.05, .05)
    straight = pd.DataFrame({"t_s": t, "x_mm": np.zeros(len(t)), "y_mm": -50 + 10 * t,
                             "segment": np.zeros(len(t), dtype=int)})
    geometry = Geometry.from_params()
    measured = score(straight, geometry)
    params = load_params()
    frozen = mindistkeep3(np.array([[0., 0.], [100., 0.], [101., 0.], [0., 0.]]),
                         params.get("metrics.step_min_mm"), params.get("metrics.step_max_mm"))
    passed = (measured["stripe_deviation_deg"] == 0 and measured["fixation_index"] == 1
              and measured["walks"] == 1 and measured["activity"] == 1
              and np.array_equal(frozen[:, 0], [0, 0, 101, 101]))
    return _entry("4.0", "verification", "passed" if passed else "failed",
                  {"straight": measured, "freeze_mm": frozen[:, 0].tolist(),
                   "constructed_cases_in": "tests/test_behaviour.py"}, fixture="tests/test_behaviour.py")


def verify_4_0b() -> ValidationEntry:
    """Run both CeTrAn threshold candidates over 128 pinned full records; degrees/count tolerances."""
    flies, excluded = load_reference()
    result = reference_check_4_0b(flies)
    measured = {"flies": len(flies), "excluded": excluded,
                "selected_step_min_mm": result["selected_step_min_mm"],
                "matches": {key: {k: value[k] for k in ("angle_matches", "walk_matches", "joint_matches")}
                            for key, value in result["candidates"].items()}}
    return _entry("4.0b", "verification", "passed" if result["passed"] else "failed", measured,
                  fixture="data/brembs-metrics.json")


def procedure_4_1() -> ValidationEntry:
    """Verify sign decision, reversal and flat classification on constructed 11-azimuth curves."""
    azimuths = list(range(-150, 151, 30))
    normal = [{"azimuth_deg": az, "omega_deg_s": az / 5} for az in azimuths]
    reverse = [{"azimuth_deg": az, "omega_deg_s": -az / 5} for az in azimuths]
    flat = [{"azimuth_deg": az, "omega_deg_s": 0} for az in azimuths]
    a, b, c = choose_sign(normal), choose_sign(reverse), choose_sign(flat)
    passed = a["sign_steer"] == 1 and a["acceptance_4_1"] and b["sign_steer"] == -1 and b["acceptance_4_1"] and c["status"].startswith("flat")
    return _entry("4.1-procedure", "verification", "passed" if passed else "failed",
                  {"normal": a, "reversed": b, "flat": c, "procedure_only": True,
                   "satisfies": []}, fixture="tests/test_behaviour.py")


def final_4_1() -> ValidationEntry:
    """Classify item 64's measured flat sign search on matching bare layers."""
    fixture = "data/experiments/open-loop-steering.json"
    record = read_yaml(ROOT / "data/behaviour-v0.1.yaml")
    sign = record.get("sign_check", {})
    attempts = sign.get("attempts", [])
    selected = next((row for row in attempts if row.get("r_vis_max_hz") == 280), None)
    if (sign.get("status") != "recorded" or selected is None or
            sign.get("layers") != record.get("layers") or
            selected.get("seeds") != [1, 2, 3] or len(selected.get("curve", [])) != 11):
        return _entry("4.1", "consistency", "unavailable",
                      {"reason": "final matching-layers sign measurement incomplete"},
                      fixture=fixture, compatibility="matching-layers", layers=LayerFlags())
    curve = selected["curve"]
    omega = {row["azimuth_deg"]: row["omega_deg_s"] for row in curve}
    flat = all(abs(value) < 5 for value in omega.values())
    direction = all(omega[az] > 0 for az in (30, 60)) and all(omega[az] < 0 for az in (-30, -60))
    outcome = "failed" if flat else ("passed" if direction else "failed")
    return _entry("4.1", "consistency", outcome,
                  {"source": "data/behaviour-v0.1.yaml sign_check", "run_id": Path(selected["run_dir"]).name,
                   "all_rates_hz": [row["r_vis_max_hz"] for row in attempts], "seeds": selected["seeds"],
                   "curve": curve, "flat": flat, "directional_pass": direction,
                   "sign_steer": sign["sign_steer"], "r_max_hz": sign["r_max_hz"],
                   "reason": "sign curve flat at 280 Hz, section 9.1 fallback" if flat else None},
                  fixture=fixture, compatibility="matching-layers", layers=LayerFlags())


def final_4_2() -> ValidationEntry:
    """Keep fixation controls unavailable when the frozen sign curve is flat."""
    return _entry("4.2", "consistency", "unavailable",
                  {"reason": "sign curve flat at 280 Hz, section 9.1 fallback"},
                  fixture="data/experiments/controls-stripes-on.json",
                  compatibility="matching-layers", layers=LayerFlags())


def final_4_3() -> ValidationEntry:
    """Preserve the sealed holdout: record its split hash without comparing any fly."""
    return _entry("4.3", "empirical validation", "unavailable",
                  {"reason": "sign curve flat at 280 Hz, section 9.1 fallback",
                   "brembs_split_sha256": sha256_file(ROOT / "data/brembs-split.json"),
                   "holdout_sealed": True, "comparison_executed": False},
                  fixture="data/experiments/holdout-wt-buridan.json",
                  compatibility="matching-layers", layers=LayerFlags())


def _pending_prediction(test_id: str) -> ValidationEntry:
    """Keep fixation predictions unavailable on the item-64 flat-curve path."""
    reason = "sign curve flat at 280 Hz, section 9.1 fallback"
    return _entry(test_id, "prediction" if test_id != "4.8" else "sensitivity", "unavailable",
                  {"reason": reason}, fixture="data/experiments/acceptance-wt-mph-buridan-distractor.json",
                  compatibility="matching-layers", layers=LayerFlags())


def _development(test_id: str, field: str, fixture: str) -> ValidationEntry:
    """Read saved provisional result only; no whole-brain process is started."""
    path = ROOT / "data/behaviour-dev.yaml"
    data = read_yaml(path) if path.exists() else {}
    measured = data.get(field, {"status": "pending"})
    present = isinstance(measured, dict) and measured.get("class") == "development"
    return _entry(test_id, "development", "recorded" if present else "unavailable",
                  measured, fixture=fixture, compatibility="development", stub="IdentityNeuromod")


def provisional_4_2() -> ValidationEntry:
    """Read provisional stripes-on versus controls, FI fractions and deviations degrees."""
    return _development("4.2-dev", "control_4_2", "data/experiments/controls-stripes-off.json")


def provisional_4_8() -> ValidationEntry:
    """Record provisional encoder-permutation/sensitivity status; no numerical sweep yet."""
    return _development("4.8-dev", "sensitivity_4_8", "data/experiments/controls-encoder-off.json")


SUITE: dict[str, Callable[[], ValidationEntry]] = {
    "4.0": verify_4_0, "4.0b": verify_4_0b, "4.1-procedure": procedure_4_1,
    "4.1": final_4_1, "4.2": final_4_2, "4.3": final_4_3,
    "4.2-dev": provisional_4_2, "4.8-dev": provisional_4_8,
}
for _test_id in ("4.4", "4.5", "4.6", "4.7", "4.8"):
    SUITE[_test_id] = lambda test_id=_test_id: _pending_prediction(test_id)
