"""Visual-status state machine (SPEC-P2 section 3.7).

The record format is `validation/records/p2/visual-status.json`. This
module classifies constructed records. It does not write a committed
status file. Item 122 closed the rest search, so photoreceptor failure
continues directly to the TuBu path rather than restarting the former
WP19 candidate chain.
"""
from __future__ import annotations

from typing import Any, Literal

VisualStatus = Literal["photoreceptor closed loop", "TuBu closed loop", "open loop", "waiting"]
PHOTORECEPTOR_FAILURES = (
    "vcal_no_selection",
    "v1_failed",
    "v3_failed",
    "sign_flat",
    "4.1r_failed",
    "4.2r_failed",
)
TUBU_STEPS = ("vtcal", "bias_t", "sign_t", "k3r_t", "4.1r_t", "4.2r_t")
STATUSES = ("photoreceptor closed loop", "TuBu closed loop", "open loop", "waiting")


def _outcome_failed(row: dict[str, Any] | None, *, fail_on_flat: bool = False) -> bool:
    """True when a named outcome is a failure. Units: none."""
    if not isinstance(row, dict):
        return False
    if row.get("selected") is False or row.get("selected_r_light_hz") is None and row.get("kind") == "vcal":
        return True
    status = str(row.get("status") or row.get("outcome") or "")
    if status in ("failed", "unavailable"):
        return True
    if fail_on_flat and (row.get("flat") is True or status.startswith("flat")):
        return True
    return False


def photoreceptor_failures(outcomes: dict[str, Any]) -> list[str]:
    """Return section 3.7 step-1 failure tokens present in outcomes. Units: none."""
    found: list[str] = []
    vcal = outcomes.get("vcal") or {}
    if isinstance(vcal, dict) and vcal.get("present"):
        selected = vcal.get("selected_r_light_hz")
        if selected is None or vcal.get("outcome") in ("failed", "unavailable"):
            found.append("vcal_no_selection")
    for key, token, extra in (
        ("v1", "v1_failed", False),
        ("v3", "v3_failed", False),
        ("sign", "sign_flat", True),
        ("4.1r", "4.1r_failed", False),
        ("4.2r", "4.2r_failed", False),
    ):
        row = outcomes.get(key)
        if isinstance(row, dict) and row.get("present") and _outcome_failed(row, fail_on_flat=extra):
            found.append(token)
    return found


def _all_present_passed(outcomes: dict[str, Any], names: tuple[str, ...]) -> bool:
    """True when every named outcome is present and passed. Units: none."""
    for name in names:
        row = outcomes.get(name)
        if not isinstance(row, dict) or not row.get("present"):
            return False
        status = str(row.get("status") or row.get("outcome") or "")
        if status not in ("passed", "recorded") or row.get("flat") is True:
            return False
        if name in ("4.1r", "4.2r", "4.1r_t", "4.2r_t", "v1", "v3", "vtcal") and status != "passed":
            return False
    return True


def _open_loop_encoder(outcomes: dict[str, Any]) -> dict[str, Any]:
    """Pick the open-loop encoder of section 3.7 step 3. Units: Hz."""
    v3_rates = list(outcomes.get("v3_rates") or [])
    passed = [row for row in v3_rates if row.get("v3_passed")]
    if passed:
        best = max(passed, key=lambda row: abs(float(row.get("mean_delta_steer_hz") or 0.0)))
        return {"inject_at": "photoreceptors", "r_light_hz": best.get("r_light_hz"),
                "mean_delta_steer_hz": best.get("mean_delta_steer_hz")}
    vt_rates = list(outcomes.get("vtcal_rates") or [])
    if vt_rates:
        best = max(vt_rates, key=lambda row: abs(float(row.get("mean_delta_steer_hz") or 0.0)))
        return {"inject_at": "TuBu", "r_vis_max_hz": best.get("r_vis_max_hz"),
                "mean_delta_steer_hz": best.get("mean_delta_steer_hz")}
    return {"inject_at": None}


def decide_visual_status(outcomes: dict[str, Any]) -> dict[str, Any]:
    """Classify one constructed visual-status record. Units: none.

    Shape: status, step_reached (0..3), failures, encoder, controller,
    waiting_for. Does not write a file.
    """
    missing_deps = list(outcomes.get("missing_dependencies") or [])
    if missing_deps and not outcomes.get("force_classify"):
        return {
            "status": "waiting",
            "step_reached": 0,
            "failures": [],
            "encoder": None,
            "controller": None,
            "waiting_for": missing_deps,
            "reason": "Waiting for: " + ", ".join(missing_deps),
        }
    failures = photoreceptor_failures(outcomes)
    if not failures and _all_present_passed(outcomes, ("vcal", "v1", "v3", "sign", "4.1r", "4.2r")):
        return {
            "status": "photoreceptor closed loop",
            "step_reached": 0,
            "failures": [],
            "encoder": "photoreceptors",
            "controller": "closed_loop",
            "waiting_for": [],
            "reason": "step 1 was never triggered",
        }
    if failures:
        # Item 122 closed the rest search and item 123 closed WP19. The
        # former step-1 candidate retry is therefore skipped.
        if _all_present_passed(outcomes, TUBU_STEPS):
            return {
                "status": "TuBu closed loop",
                "step_reached": 2,
                "failures": failures,
                "encoder": "TuBu",
                "controller": "closed_loop",
                "waiting_for": [],
                "reason": "TuBu path passed after photoreceptor failure",
            }
        tubu_missing = [name for name in TUBU_STEPS
                        if not (isinstance(outcomes.get(name), dict) and outcomes[name].get("present"))]
        tubu_failed = [name for name in TUBU_STEPS
                       if isinstance(outcomes.get(name), dict) and outcomes[name].get("present")
                       and _outcome_failed(outcomes[name], fail_on_flat=name in ("sign_t", "vtcal"))]
        if tubu_missing and not tubu_failed:
            return {
                "status": "waiting",
                "step_reached": 2,
                "failures": failures,
                "encoder": "TuBu",
                "controller": None,
                "waiting_for": [f"TuBu {name}" for name in tubu_missing],
                "reason": "photoreceptor failure; the closed rest search proceeds to TuBu",
            }
        encoder = _open_loop_encoder(outcomes)
        return {
            "status": "open loop",
            "step_reached": 3,
            "failures": failures + [f"tubu_{name}" for name in tubu_failed],
            "encoder": encoder.get("inject_at"),
            "open_loop_encoder": encoder,
            "controller": "open_loop",
            "waiting_for": [],
            "reason": "TuBu path failed; open-loop encoder selected",
        }
    missing = [name for name in ("vcal", "v1", "v3", "sign", "4.1r", "4.2r")
               if not (isinstance(outcomes.get(name), dict) and outcomes[name].get("present"))]
    return {
        "status": "waiting",
        "step_reached": 0,
        "failures": [],
        "encoder": "photoreceptors",
        "controller": None,
        "waiting_for": missing,
        "reason": "photoreceptor path not finished",
    }


def record_template() -> dict[str, Any]:
    """Empty visual-status.json document. Units: none. Shapes: one mapping."""
    return {
        "status": "waiting",
        "step_reached": 0,
        "failures": [],
        "encoder": None,
        "controller": None,
        "waiting_for": ["data/visual-v0.2.yaml", "data/dopamine-v0.2.yaml"],
        "reason": "Waiting for: data/visual-v0.2.yaml, data/dopamine-v0.2.yaml",
    }
