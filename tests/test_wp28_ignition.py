"""Item 87 ignition floor: silent is clear, hot stays ignited, boundary."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from flyonenomics.drive.rest_map import (
    build_ignition_recheck,
    ignition_flag_change,
    probe_ignited,
    scan_ignition_document,
)
from flyonenomics.types import load_params
from flyonenomics.validation import artefacts

ROOT = Path(__file__).resolve().parents[1]
PARAMS = load_params(ROOT / "data" / "params-v0.2.yaml")


def test_params_row_is_half_hertz() -> None:
    assert PARAMS.get("ign.min_baseline_hz") == 0.5
    assert PARAMS.get("ign.factor") == 3
    assert PARAMS.get("ign.max_central_hz") == 8


def test_silent_network_is_not_ignited() -> None:
    """Pro's 3d w_bg 0.75 seed-1 pathology: zero baseline, 0.000188 Hz peak."""
    silent = artefacts.ignition_detector(
        np.array([0.000188]), settled_central_mean=0.0, params=PARAMS,
    )
    assert silent["tripped"] is False
    assert silent["status"] == "clear"
    assert probe_ignited(0.0, 0.000188, PARAMS) is False


def test_ignited_network_still_is() -> None:
    hot_abs = artefacts.ignition_detector(
        np.array([1.0, 10.0]), settled_central_mean=2.0, params=PARAMS,
    )
    assert hot_abs["status"] == "ignited"
    hot_rel = artefacts.ignition_detector(
        np.array([4.0]), settled_central_mean=1.0, params=PARAMS,
    )
    assert hot_rel["status"] == "ignited"
    assert probe_ignited(1.0, 4.0, PARAMS) is True


def test_floor_boundary() -> None:
    """Relative test uses >; exact 3x at the 0.5 Hz floor is clear."""
    at_floor = artefacts.ignition_detector(
        np.array([1.5]), settled_central_mean=0.5, params=PARAMS,
    )
    assert at_floor["tripped"] is False
    above_floor = artefacts.ignition_detector(
        np.array([1.51]), settled_central_mean=0.5, params=PARAMS,
    )
    assert above_floor["tripped"] is True
    below_floor = artefacts.ignition_detector(
        np.array([2.0]), settled_central_mean=0.499, params=PARAMS,
    )
    assert below_floor["tripped"] is False
    below_but_absolute = artefacts.ignition_detector(
        np.array([8.1]), settled_central_mean=0.0, params=PARAMS,
    )
    assert below_but_absolute["tripped"] is True


def test_recheck_lists_only_flag_changes() -> None:
    silent = {
        "kind": "evaluation", "stage": "T1", "seed": 1, "task_id": "u19-s1",
        "unit": {"sub_tier": "T3d", "g_gaba": 1.0, "g_glu": 4.0},
        "settled_central_hz": 0.0, "max_rolling_central_hz": 0.000188,
        "ignited": True, "w_bg": 0.75,
    }
    live = {
        "kind": "evaluation", "stage": "T1", "seed": 1, "task_id": "u19-s1",
        "settled_central_hz": 5.74, "max_rolling_central_hz": 5.85,
        "ignited": False, "w_bg": 0.85,
    }
    n, changes = scan_ignition_document(silent, source="mem", params=PARAMS)
    assert n == 1 and len(changes) == 1
    assert changes[0]["ignited_recorded"] is True
    assert changes[0]["ignited_item87"] is False
    n_ok, none = scan_ignition_document(live, source="mem", params=PARAMS)
    assert n_ok == 1 and none == []
    nested = {
        "kind": "evaluation", "stage": "T0", "seed": 1,
        "silent": silent, "sugar": live,
    }
    n_nested, nested_changes = scan_ignition_document(nested, source="mem", params=PARAMS)
    assert n_nested == 2 and len(nested_changes) == 1
    assert nested_changes[0]["kind"] == "silent"


def test_flag_change_helper_on_constructed_probe() -> None:
    change = ignition_flag_change(
        {"settled_central_hz": 0.0, "max_rolling_central_hz": 0.000188, "ignited": True},
        PARAMS,
    )
    assert change is not None and change["ignited_item87"] is False
    assert ignition_flag_change(
        {"settled_central_hz": 2.0, "max_rolling_central_hz": 10.0, "ignited": True},
        PARAMS,
    ) is None


def test_build_recheck_on_tmp_ndjson(tmp_path: Path) -> None:
    path = tmp_path / "row.ndjson"
    path.write_text(json.dumps({
        "kind": "evaluation", "stage": "T1", "seed": 1, "task_id": "x",
        "w_bg": 0.75, "settled_central_hz": 0.0,
        "max_rolling_central_hz": 0.000188, "ignited": True,
        "unit": {"sub_tier": "T3d", "g_gaba": 1.0, "g_glu": 4.0},
    }) + "\n")
    body = build_ignition_recheck([path], params=PARAMS)
    assert body["n_probes"] == 1
    assert body["n_changed"] == 1
    assert body["changes"][0]["source"].endswith("row.ndjson")
