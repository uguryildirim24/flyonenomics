"""Item 89 3c T1 at dt 0.05 ms: plan, stiffness cut, collect without T0 filter, decision."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from flyonenomics.drive.rest_map import CAP, SEEDS, Setting, TARGETS, WEIGHTS, screen_candidate
from flyonenomics.drive.rest_tier3 import (
    T3C_CONVERGENCE_REQUIRED_ID,
    T3C_T1_DT_MS,
    T3C_T1_PACK_RATE,
    cbi_stiff,
    collect_t1,
    decide_t3c_item89,
    t2_reflex_probe,
    t3c_t1_plan,
    t3c_t1_unit,
)

ROOT = Path(__file__).resolve().parents[1]
T0_PATH = ROOT / "validation" / "records" / "p2" / "rest-T3c-T0.json"
DECISION_PATH = ROOT / "validation" / "records" / "p2" / "rest-T3c-decision.json"


def _t0() -> dict:
    return json.loads(T0_PATH.read_text())


def _decision() -> dict:
    return json.loads(DECISION_PATH.read_text())


def _passing_rows(setting: Setting, *, h_max: float) -> list[dict]:
    rows = []
    for w in setting.weights:
        for seed in SEEDS:
            rows.append({
                "w_bg": w, "seed": seed, "F": 2.0, "b": 0.002, "stability_ratio": 1.0,
                "h_max": h_max,
                "rates_hz": {**TARGETS, "central": 1.0, "DAN": 1.0, "KC": 0.1},
            })
    return rows


def test_t3c_t1_plan_is_one_unit_at_half_step() -> None:
    plan = t3c_t1_plan(_t0())
    unit = t3c_t1_unit(_t0())
    assert plan["item"] == 89
    assert plan["dt_ms"] == T3C_T1_DT_MS == 0.05
    assert plan["n_units"] == 1
    assert plan["unit_id"] == T3C_CONVERGENCE_REQUIRED_ID
    assert plan["engine_model"] == "lif+cbi"
    assert plan["job_shapes"]["launch"] is True
    assert plan["job_shapes"]["n_jobs"] == 1
    assert plan["pack_worker_s_per_brain_s"] == T3C_T1_PACK_RATE
    assert len(plan["admitted"]) == 1
    assert plan["admitted"][0]["g_gaba"] == 1.0
    assert plan["admitted"][0]["g_glu"] == 1.0
    assert plan["admitted"][0]["setting"]["E_inh_mv"] == -72.0
    assert "cbi-stiff" not in (unit.get("flags") or [])
    assert "t2-b-unreachable" in (unit.get("flags") or [])
    n_tasks = int(plan["job_shapes"]["n_tasks"])
    assert n_tasks == 15
    assert plan["job_shapes"]["t1_brain_s"] == 19 * 3 * 12
    assert "T0 record not rewritten" in plan["note"]


def test_screen_clears_stiffness_at_dt_05_for_closest_miss_h_max() -> None:
    h_max = 19.65
    setting = Setting(1.0, 1.0)
    rows = _passing_rows(setting, h_max=h_max)
    assert cbi_stiff(h_max)
    assert not cbi_stiff(h_max, dt_ms=0.05)
    default = screen_candidate(setting, 1.15, rows)
    fine = screen_candidate(setting, 1.15, rows, dt_ms=0.05)
    assert default["flags"] == ["cbi-stiff"]
    assert default["screen_passed"] is False
    assert default["violations"]["F"] == CAP
    assert fine["flags"] == []
    assert fine["screen_passed"] is True


def test_t2_reflex_probe_clears_stiffness_at_dt_05() -> None:
    ff = {"upstream": [60.0] * 10, "extended": [60.0] * 10}
    ref = {"upstream": [100.0] * 10, "extended": [100.0] * 10}
    a = [40.0] * 6
    b = [51.0] * 10
    stiff = t2_reflex_probe(a, b, ff, ref, h_max=19.65)
    clear = t2_reflex_probe(a, b, ff, ref, h_max=19.65, dt_ms=0.05)
    assert stiff["reflex_passed"] is False
    assert stiff["flags"] == ["cbi-stiff"]
    assert clear["reflex_passed"] is True
    assert "cbi-stiff" not in (clear.get("flags") or [])


def _write_t1_task(path: Path, unit: dict, rows: list[dict]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"kind": "evaluation", "unit": unit, **row} for row in rows]
    lines.append({"kind": "task-complete", "wall_s": 1.0, "wall_per_brain_s": 1.0, "brain_s": 684.0})
    path.write_text("".join(json.dumps(row) + "\n" for row in lines))
    return {"path": str(path), "kind": "t1", "unit": unit}


def test_collect_t1_scores_t0_failure_when_t0_filter_omitted(tmp_path: Path) -> None:
    unit = t3c_t1_unit(_t0())
    setting = Setting(1.0, 1.0)
    rows = _passing_rows(setting, h_max=19.65)
    task = _write_t1_task(tmp_path / "u00.ndjson", unit, rows)
    skipped = collect_t1([(tmp_path, [task])], t0_units=[{**unit, "t0_passed": False}])
    assert skipped["n_units"] == 0
    scored = collect_t1([(tmp_path, [task])], dt_ms=0.05)
    assert scored["n_units"] == 1
    assert scored["dt_ms"] == 0.05
    assert scored["n_screen_passers"] > 0
    default_dt = collect_t1([(tmp_path, [task])])
    assert default_dt["n_screen_passers"] == 0


def _t0_era_decision() -> dict:
    """Item-89 input: the T0 decision, not the live updated file."""
    live = _decision()
    existing = copy.deepcopy(live)
    t0_miss = copy.deepcopy(live.get("t0_closest_miss") or live["closest_miss"])
    existing["failed_stage"] = "T0"
    existing["closest_miss"] = t0_miss
    existing["t1_launch"] = False
    existing["t2_launch"] = False
    existing["ranked"] = []
    existing["shortlist"] = []
    for key in (
        "item", "dt_ms", "t1_record", "n_t1_units", "n_screen_passers",
        "n_t2_admitted", "t1_jobs", "t0_closest_miss", "reason",
    ):
        existing.pop(key, None)
    return existing


def test_collect_t1_keeps_screen_cbi_stiff_flag(tmp_path: Path) -> None:
    unit = t3c_t1_unit(_t0())
    setting = Setting(1.0, 1.0)
    rows = _passing_rows(setting, h_max=19.65)
    task = _write_t1_task(tmp_path / "u00.ndjson", unit, rows)
    default_dt = collect_t1([(tmp_path, [task])])
    flags = default_dt["scored"][0]["flags"]
    assert "cbi-stiff" in flags
    assert "t2-b-unreachable" in flags
    fine = collect_t1([(tmp_path, [task])], dt_ms=0.05)
    fine_flags = fine["scored"][0]["flags"]
    assert "cbi-stiff" not in fine_flags
    assert "t2-b-unreachable" in fine_flags


def test_decide_t3c_item89_keeps_t0_bytes_and_t0_counts() -> None:
    original = T0_PATH.read_bytes()
    existing = _t0_era_decision()
    t0_n = existing["n_t0_units"]
    t0_pass = existing["n_t0_passers"]
    t0_stiff = existing["n_cbi_stiff"]
    t1 = {
        "n_units": 1,
        "n_screen_passers": 0,
        "n_t2_admitted": 0,
        "closest_miss": {"w_bg": 0.85, "S": 1.0, "deepest": "T1", "screen_passed": False},
        "scored": [],
    }
    out = decide_t3c_item89(existing, t1)
    assert T0_PATH.read_bytes() == original
    assert out["n_t0_units"] == t0_n
    assert out["n_t0_passers"] == t0_pass
    assert out["n_cbi_stiff"] == t0_stiff
    assert out["record"] == existing["record"]
    assert out["failed_stage"] == "R-screen"
    assert out["t1_launch"] is True
    assert out["t2_launch"] is False
    assert out["item"] == 89
    assert out["dt_ms"] == 0.05
    assert out["t0_closest_miss"] == existing["closest_miss"]
    assert existing["failed_stage"] == "T0"


def test_decide_t3c_item89_keeps_t0_closest_miss_on_reentry() -> None:
    original = T0_PATH.read_bytes()
    live = _decision()
    t0_miss = live["t0_closest_miss"]
    t1 = {
        "n_units": 1,
        "n_screen_passers": 0,
        "n_t2_admitted": 0,
        "closest_miss": live["closest_miss"],
        "scored": [],
    }
    out = decide_t3c_item89(live, t1)
    assert T0_PATH.read_bytes() == original
    assert out["t0_closest_miss"] == t0_miss
    assert out["t0_closest_miss"]["deepest"] == "T0"
    assert out["closest_miss"] == live["closest_miss"]


def test_decide_t3c_item89_ranks_when_t2_long_passes() -> None:
    existing = _t0_era_decision()
    original = T0_PATH.read_bytes()
    cand = {
        "g_gaba": 1.0, "g_glu": 1.0, "w_bg": 1.15, "S": 0.0, "J": 0.0, "M": 0.05,
        "sub_tier": "T3c", "sigma_th": 0.0, "optic_exemption": False, "n_bg": 100,
        "setting": {"E_inh_mv": -72.0, "scope": "all"},
        "reflex_passed": True, "long_passed": True, "deepest": "T2",
        "screen_passed": True,
    }
    t1 = {"n_units": 1, "n_screen_passers": 1, "n_t2_admitted": 1, "closest_miss": None}
    t2 = {"candidates": [cand], "n_reflex_passed": 1, "n_long_passed": 1}
    out = decide_t3c_item89(existing, t1, t2)
    assert T0_PATH.read_bytes() == original
    assert out["failed_stage"] is None
    assert len(out["ranked"]) == 1
    assert out["p2_partial_b"] is False
    assert out["t2_launch"] is True
    assert out["t0_closest_miss"] == existing["closest_miss"]
