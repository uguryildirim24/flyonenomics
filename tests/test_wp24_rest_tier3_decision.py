"""Constructed SPEC-P2 2.6 step 6 tier-3 decisions; no Brian2 engine."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from flyonenomics.drive.mechanisms import engine_model_of, mask_sha256, mechanisms_section, scope_mask
from flyonenomics.drive.rest_map import Setting, TARGETS, capped_candidates, screen_candidate
from flyonenomics.drive.rest_tier3 import (
    admit_t1,
    candidate_id,
    cbi_stiff,
    closest_miss,
    collect_packed_t0,
    collect_t0,
    decide_subtier,
    fails_only_reflex_ab,
    grid_edge_flag,
    harmonised_reflex_floors,
    makespan_s,
    mechanism_strength,
    next_sub_tier,
    p2_partial_b,
    parsimony,
    projection_engine_hours,
    ranked_list_row,
    round_trip_row,
    score_not_computable,
    t0_flags,
    t0_passed,
    t0_retention,
    t0_tasks,
    t0_unit_list,
    t1_tasks,
    t1_weight_slices,
    t2_reflex_probe,
    t2_tasks,
    admit_t2,
    task_worker_s,
    tier3_order_key,
)


def _unit(sub="T3a", g_gaba=1.0, g_glu=1.0, **setting):
    if sub == "T3a":
        setting = {"b_mv": setting.get("b_mv", 1.0), "tau_ms": setting.get("tau_ms", 150.0),
                   "scope": "non_sensory"}
    elif sub == "T3b":
        setting = {"U": setting.get("U", 0.2), "tau_ms": setting.get("tau_ms", 100.0),
                   "scope": setting.get("scope", "non_sensory_excitatory")}
    else:
        setting = {"E_inh_mv": setting.get("E_inh_mv", -72.0), "scope": "all"}
    return {
        "sub_tier": sub, "g_gaba": g_gaba, "g_glu": g_glu, "setting": setting,
        "M": mechanism_strength(sub, setting), "baseline": False,
        "sigma_th": 0.0, "optic_exemption": False, "n_bg": 100, "w_bg": 1.15,
        "S": 0.0, "J": 0.0, "t0_passed": True,
    }


def _screen_rows(setting: Setting, *, passed: bool = True, central_160: float = 1.0):
    rows = []
    for w in setting.weights:
        for seed in (1, 2, 3):
            central = 1.0 if w != 1.60 else central_160
            f = 2.0 if passed else 4.0
            rows.append({
                "w_bg": w, "seed": seed, "F": f, "b": 0.002, "stability_ratio": 1.0,
                "rates_hz": {**TARGETS, "central": central, "DAN": 1.0, "KC": 0.1},
            })
    return rows


def test_t0_retention_edge_and_per_job_denominator():
    assert t0_passed(0.5) and not t0_passed(0.499999)
    assert t0_retention(5.0, 10.0) == 0.5
    a = t0_retention(5.5, 11.0)
    b = t0_retention(5.0, 10.0)
    assert a == pytest.approx(0.5) and b == pytest.approx(0.5)
    flags_a = t0_flags(job_bare_seeds=[11.0] * 10, first_job_bare_seeds=[10.0] * 10,
                       bg_off_difference_hz=80)
    flags_b = t0_flags(job_bare_seeds=[10.0] * 10, first_job_bare_seeds=[10.0] * 10,
                       bg_off_difference_hz=40)
    assert "bare-mismatch" in flags_a and "t2-b-unreachable" not in flags_a
    assert "t2-b-unreachable" in flags_b
    unit_a = {**_unit(), "retention": a, "t0_passed": t0_passed(a), "job": 2}
    unit_b = {**_unit(g_glu=2.0), "retention": b, "t0_passed": t0_passed(b), "job": 1}
    assert unit_a["t0_passed"] and unit_b["t0_passed"]


def _write_t0_ndjson(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _synthetic_t0_job(
    root: Path,
    name: str,
    *,
    job_id: str,
    bare_seeds: list[float],
    unit_seeds: list[float],
    unit: dict,
    h_max: float | None = None,
) -> tuple[Path, list[dict]]:
    job_dir = root / name
    unit_path = job_dir / "unit.ndjson"
    bare_path = job_dir / "bare.ndjson"
    unit_rows = [
        {
            "kind": "evaluation",
            "seed": i + 1,
            "difference_hz": diff,
            "unit": unit,
            "job_id": job_id,
            **({"h_max": h_max} if h_max is not None else {}),
        }
        for i, diff in enumerate(unit_seeds)
    ]
    unit_rows.append({"kind": "task-complete", "wall_per_brain_s": 1.0})
    bare_rows = [
        {"kind": "evaluation", "seed": i + 1, "difference_hz": diff, "job_id": job_id}
        for i, diff in enumerate(bare_seeds)
    ]
    bare_rows.append({"kind": "task-complete", "wall_per_brain_s": 1.2})
    _write_t0_ndjson(unit_path, unit_rows)
    _write_t0_ndjson(bare_path, bare_rows)
    tasks = [
        {"path": str(unit_path), "kind": "unit"},
        {"path": str(bare_path), "kind": "bare"},
    ]
    return job_dir, tasks


def test_packed_t0_ndjson_flags_bare_mismatch(tmp_path: Path) -> None:
    """Packed two-job T0 NDJSON: disagreeing bare seeds flag every unit of that job."""
    unit_a = {**_unit(), "baseline": False}
    unit_b = {**_unit(g_glu=2.0), "baseline": False}
    job0_dir, job0_tasks = _synthetic_t0_job(
        tmp_path, "t3a-t0-00", job_id="27514",
        bare_seeds=[10.0] * 10, unit_seeds=[5.0] * 10, unit=unit_a,
    )
    job1_dir, job1_tasks = _synthetic_t0_job(
        tmp_path, "t3a-t0-01", job_id="27515",
        bare_seeds=[11.0] * 10, unit_seeds=[5.5] * 10, unit=unit_b,
    )
    lone = collect_t0(job1_dir, job1_tasks)
    assert lone["units"][0]["retention"] == pytest.approx(0.5)
    assert "bare-mismatch" not in lone["units"][0]["flags"]
    summaries = collect_packed_t0([(job0_dir, job0_tasks), (job1_dir, job1_tasks)])
    assert summaries[0]["units"][0]["retention"] == pytest.approx(0.5)
    assert summaries[1]["units"][0]["retention"] == pytest.approx(0.5)
    assert summaries[0]["global_bare_mean"] == pytest.approx(10.0)
    assert summaries[1]["global_bare_mean"] == pytest.approx(10.0)
    assert summaries[1]["job_bare_mean"] == pytest.approx(11.0)
    assert "bare-mismatch" not in summaries[0]["units"][0]["flags"]
    assert "bare-mismatch" in summaries[1]["units"][0]["flags"]
    assert summaries[1]["units"][0]["t0_passed"] is True


def test_baseline_rows_never_admitted():
    baseline = {**_unit(), "baseline": True, "t0_passed": True, "setting": None, "M": 0.0}
    passer = _unit(g_glu=2.0)
    result = admit_t1([baseline, passer], rho_mech=1.0, t0_brain_s=100.0)
    assert all(not u.get("baseline") for u in result["admitted"])
    assert baseline not in result["admitted"]


def test_admission_rounds_cap_and_projection():
    units = []
    for i, (g_gaba, g_glu) in enumerate(((1.0, 1.0), (1.0, 2.0), (1.5, 1.0))):
        for b in (3.0, 1.0, 0.3, 0.1):
            units.append(_unit(g_gaba=g_gaba, g_glu=g_glu, b_mv=b, tau_ms=50.0))
    forty = admit_t1(units, rho_mech=1.0, t0_brain_s=100.0, t1_max_units=40)
    assert len(forty["admitted"]) <= 40
    rho15 = admit_t1(units, rho_mech=1.5, t0_brain_s=11760.0)
    assert rho15["failed_stage"] is None or rho15["admitted"] is not None
    over = admit_t1(units, rho_mech=1.0, t0_brain_s=1e9)
    assert over["failed_stage"] == "R-screen" and over["reason"] == "cap"
    assert over["admitted"] == []
    proj1 = projection_engine_hours(t0_brain_s=11760, admitted_units=0, rho_mech=1.0)
    proj15 = projection_engine_hours(t0_brain_s=11760, admitted_units=0, rho_mech=1.5)
    assert proj15 / proj1 == pytest.approx(1.5)
    capped = admit_t1(units, rho_mech=1.0, t0_brain_s=100.0, t1_max_units=2)
    assert len(capped["admitted"]) == 2
    assert all(u.get("status") == "not tested (cap)" for u in capped["excluded"])
    first_pair = (capped["admitted"][0]["g_gaba"], capped["admitted"][0]["g_glu"])
    assert first_pair == (1.0, 1.0)
    assert capped["admitted"][0]["M"] >= capped["admitted"][1]["M"]


def test_ranked_list_round_trip_per_sub_tier():
    super_class = np.array(["sensory", "central", "sensory", "central"], dtype=str)
    mask = scope_mask("non_sensory", super_class=super_class)
    sha = mask_sha256(mask)
    s_cur = np.array([-1.0, 1.0, 1.0, 1.0])
    mask_exc = scope_mask("non_sensory_excitatory", super_class=super_class, s_cur=s_cur)
    sha_exc = mask_sha256(mask_exc)
    rows = [
        ranked_list_row(_unit("T3a"), w_bg=1.15, mechanisms=None, mask_sha256=sha),
        ranked_list_row(_unit("T3b"), w_bg=1.15, mechanisms=None, mask_sha256=sha_exc),
        ranked_list_row(_unit("T3c"), w_bg=1.15, mechanisms=None),
    ]
    ids = set()
    for row in rows:
        assert engine_model_of(row["mechanisms"]) == row["engine_model"]
        assert mechanisms_section(row) is not None
        round_trip_row(row, n=4, super_class=super_class, s_cur=s_cur)
        ids.add(row["candidate_id"])
    other = ranked_list_row(_unit("T3a", b_mv=3.0, tau_ms=50.0), w_bg=1.15,
                            mechanisms=None, mask_sha256=sha)
    assert other["candidate_id"] not in ids
    assert candidate_id(rows[0]) == rows[0]["candidate_id"]
    try:
        from flyonenomics.drive.rest_calibration import make_drive, ranked_candidates
    except ImportError:
        make_drive = ranked_candidates = None
    if ranked_candidates is not None:
        kept = ranked_candidates(rows)
        assert kept[0]["mechanisms"] == rows[0]["mechanisms"]
        assert kept[0]["engine_model"] == rows[0]["engine_model"]
    if make_drive is not None:
        doc = make_drive(rows[0])
        assert doc.get("mechanisms") == mechanisms_section(rows[0])


def test_several_candidates_from_one_unit_and_t2_cap():
    setting = Setting(1.0, 1.0)
    rows = _screen_rows(setting, passed=True)
    from flyonenomics.drive.rest_tier3 import candidates_from_unit

    unit = _unit()
    cands = candidates_from_unit(unit, rows)
    assert len(cands) >= 2
    many = [{**_unit(g_glu=1.0 + 0.001 * i), "screen_passed": True, "S": float(i), "J": 0.0,
             "w_bg": 1.15} for i in range(25)]
    admitted, excluded = capped_candidates(many, cap=20)
    assert len(admitted) == 20 and len(excluded) == 5


def test_order_key_ties_and_closest_miss_depth():
    a = _unit(b_mv=1.0, tau_ms=150.0)
    b = deepcopy(a)
    assert tier3_order_key(a) == tier3_order_key(b)
    stronger = _unit(b_mv=3.0, tau_ms=150.0)
    assert tier3_order_key(a) < tier3_order_key(stronger)
    tau_first = _unit(b_mv=1.0, tau_ms=50.0)
    tau_later = _unit(b_mv=1.0, tau_ms=500.0)
    assert tier3_order_key(tau_first) < tier3_order_key(tau_later)
    t0 = {**_unit(), "deepest": "T0", "S": 0.0}
    t1 = {**_unit(g_glu=2.0), "deepest": "T1", "S": 8.0}
    t2 = {**_unit(g_glu=4.0), "deepest": "T2", "S": 9.0}
    assert closest_miss([t0, t1, t2]) is t2
    assert closest_miss([t0, t1]) is t1


def test_each_failed_stage_and_chain():
    empty_t0 = decide_subtier(sub_tier="T3a", t0_units=[{**_unit(), "t0_passed": False, "deepest": "T0"}])
    assert empty_t0["failed_stage"] == "T0"
    assert next_sub_tier("T3a", "T0", []) == "T3b"
    cap = decide_subtier(
        sub_tier="T3a", t0_units=[_unit()],
        t1_admission={"failed_stage": "R-screen", "reason": "cap"},
    )
    assert cap["failed_stage"] == "R-screen" and cap["reason"] == "cap"
    no_screen = decide_subtier(
        sub_tier="T3a", t0_units=[_unit()],
        t1_admission={"failed_stage": None},
        t1_candidates=[{**_unit(), "screen_passed": False, "deepest": "T1"}],
    )
    assert no_screen["failed_stage"] == "R-screen"
    no_reflex = decide_subtier(
        sub_tier="T3a", t0_units=[_unit()],
        t1_candidates=[{**_unit(), "screen_passed": True}],
        t2_results=[{**_unit(), "reflex_passed": False, "deepest": "T2", "S": 1.0}],
    )
    assert no_reflex["failed_stage"] == "R-reflex"
    no_long = decide_subtier(
        sub_tier="T3a", t0_units=[_unit()],
        t2_results=[{**_unit(), "reflex_passed": True, "long_passed": False, "deepest": "T2", "S": 1.0}],
    )
    assert no_long["failed_stage"] == "R-long"
    qrest = decide_subtier(
        sub_tier="T3a", t0_units=[_unit()],
        t2_results=[{**_unit(), "reflex_passed": True, "long_passed": True, "deepest": "T2", "S": 0.0}],
        qrest_exhausted=True,
    )
    assert qrest["failed_stage"] == "Q-rest"
    ranked = decide_subtier(
        sub_tier="T3a", t0_units=[_unit()],
        t2_results=[{**_unit(), "reflex_passed": True, "long_passed": True, "S": 0.0, "deepest": "T2"}],
    )
    assert ranked["failed_stage"] is None and len(ranked["shortlist"]) == 1
    assert next_sub_tier("T3b", "T0", []) == "T3c"
    assert next_sub_tier("T3c", "T0", []) == "T3d"
    assert next_sub_tier("T3d", "T0", []) is None
    assert p2_partial_b("T3d", "T0", [])
    assert not p2_partial_b("T3c", "T0", [])
    assert not p2_partial_b("T3a", "T0", [])
    empty_3d = decide_subtier(
        sub_tier="T3d", t0_units=[{**_unit(), "t0_passed": True}],
        t1_admission={"failed_stage": None},
        t1_candidates=[{**_unit(), "screen_passed": False, "deepest": "T1"}],
    )
    assert empty_3d["failed_stage"] == "R-screen"
    assert empty_3d["ranked"] == []
    assert empty_3d["p2_partial_b"] is True


def test_cbi_stiff_and_grid_edge():
    assert cbi_stiff(19.1)
    assert not cbi_stiff(18.9)
    assert not cbi_stiff(19.0)
    setting = Setting(1.0, 1.0)
    rows = _screen_rows(setting, passed=False, central_160=0.2)
    scored = [screen_candidate(setting, w, rows) for w in setting.weights[:-2]]
    assert not any(r["screen_passed"] for r in scored)
    edge_rows = [r for r in rows if round(float(r["w_bg"]), 2) in (1.55, 1.60)]
    assert grid_edge_flag(edge_rows)
    ok_rows = _screen_rows(setting, passed=False, central_160=1.0)
    edge_ok = [r for r in ok_rows if round(float(r["w_bg"]), 2) in (1.55, 1.60)]
    assert not grid_edge_flag(edge_ok)


def test_cbi_stiff_metrics_are_not_computable_not_a_rest_failure():
    """h_max above 19 flags cbi-stiff; passing rest numbers do not admit the unit."""
    from flyonenomics.drive.rest_map import CAP

    assert "cbi-stiff" in t0_flags(h_max=19.1)
    assert "cbi-stiff" not in t0_flags(h_max=19.0)
    setting = Setting(1.0, 1.0)
    rows = _screen_rows(setting, passed=True)
    for row in rows:
        row["h_max"] = 19.1
        row["F"] = 2.0
    scored = screen_candidate(setting, 1.15, rows)
    assert scored["flags"] == ["cbi-stiff"]
    assert scored["violations"]["F"] == CAP
    assert scored["screen_passed"] is False


def test_collect_t0_cbi_stiff_blocks_pass_at_retention_0_6(tmp_path: Path) -> None:
    unit = {**_unit("T3c"), "baseline": False}
    _job_dir, tasks = _synthetic_t0_job(
        tmp_path, "t3c-t0-00", job_id="1",
        bare_seeds=[10.0] * 10, unit_seeds=[6.0] * 10, unit=unit, h_max=19.1,
    )
    summary = collect_t0(_job_dir, tasks)
    line = summary["units"][0]
    assert line["retention"] == pytest.approx(0.6)
    assert "cbi-stiff" in line["flags"]
    assert line["t0_passed"] is False
    assert line["h_max"] == pytest.approx(19.1)


def test_t2_reflex_probe_cbi_stiff_is_not_computable_and_does_not_pass():
    """Item 69: h_max above 19 flags cbi-stiff and blocks a T2 R-reflex pass.

    Passing Hz lists still pass when h_max is missing (3a/3b, no h_inh) or 19.0.
    """
    ff = {"upstream": [60.0] * 10, "extended": [60.0] * 10}
    ref = {"upstream": [100.0] * 10, "extended": [100.0] * 10}
    a = [40.0] * 6
    b = [51.0] * 10
    cap = score_not_computable()
    none = t2_reflex_probe(a, b, ff, ref, h_max=None)
    assert none["reflex_passed"] is True
    assert none["flags"] == []
    assert none["h_max"] is None
    at_cut = t2_reflex_probe(a, b, ff, ref, h_max=19.0)
    assert at_cut["reflex_passed"] is True
    assert "cbi-stiff" not in at_cut["flags"]
    below = t2_reflex_probe(a, b, ff, ref, h_max=18.9)
    assert below["reflex_passed"] is True
    stiff = t2_reflex_probe(a, b, ff, ref, h_max=19.1)
    assert stiff["reflex_passed"] is False
    assert stiff["flags"] == ["cbi-stiff"]
    assert stiff["h_max"] == pytest.approx(19.1)
    assert stiff["reflex_violations"] == {"a": cap, "b": cap, "c": cap}
    assert stiff["reflex_violation"] == 3 * cap
    assert stiff.get("reflex_harmonised") is False


def test_item_74_named_floors_when_bare_mean_missing():
    """Item 74: named 28/22 Hz floors apply only when the same-job bare mean is missing."""
    assert harmonised_reflex_floors(None) == (28.0, 22.0)
    assert harmonised_reflex_floors(float("nan")) == (28.0, 22.0)
    assert harmonised_reflex_floors(0.0) == (28.0, 22.0)


def test_item_74_harmonises_only_ab_fail_on_tier3():
    """Item 74: tier-3 T2 that fail only (a)/(b) are re-scored at 0.5/0.4 of bare."""
    ff = {"upstream": [60.0] * 10, "extended": [60.0] * 10}
    ref = {"upstream": [100.0] * 10, "extended": [100.0] * 10}
    a = [30.0] * 6
    b = [30.0] * 10
    mean_hz, seed_min_hz = harmonised_reflex_floors(56.0)
    assert mean_hz == pytest.approx(28.0)
    assert seed_min_hz == pytest.approx(22.4)
    skipped = t2_reflex_probe(a, b, ff, ref)
    assert skipped["reflex_passed"] is False
    assert skipped.get("reflex_harmonised") is False
    assert "reflex-harmonised" not in skipped["flags"]
    assert fails_only_reflex_ab(skipped)
    for sub in ("T3a", "T3b", "T3c", "T3d", "T3e"):
        out = t2_reflex_probe(a, b, ff, ref, sub_tier=sub, job_bare_mean=56.0)
        assert out["reflex_passed"] is True
        assert out["reflex_harmonised"] is True
        assert "reflex-harmonised" in out["flags"]
        assert out["reflex_verdicts"]["original"]["reflex_passed"] is False
        assert out["reflex_verdicts"]["harmonised"]["reflex_passed"] is True
        assert out["reflex_verdicts"]["harmonised"]["mean_hz"] == pytest.approx(28.0)
        assert out["reflex_verdicts"]["harmonised"]["seed_min_hz"] == pytest.approx(22.4)


def test_item_74_does_not_rescue_c_fail_stiff_or_low_hz():
    ff = {"upstream": [60.0] * 10, "extended": [60.0] * 10}
    ref = {"upstream": [100.0] * 10, "extended": [100.0] * 10}
    cap = score_not_computable()
    c_fail = t2_reflex_probe(
        [40.0] * 6, [51.0] * 10,
        {"upstream": [60.0] * 10, "extended": [40.0] * 10},
        ref, sub_tier="T3b", job_bare_mean=56.0,
    )
    assert c_fail["reflex_passed"] is False
    assert c_fail.get("reflex_harmonised") is False
    assert "reflex-harmonised" not in c_fail["flags"]
    assert "reflex_verdicts" not in c_fail
    low = t2_reflex_probe(
        [10.0] * 6, [10.0] * 10, ff, ref, sub_tier="T3b", job_bare_mean=56.0,
    )
    assert low["reflex_passed"] is False
    assert low["reflex_harmonised"] is False
    assert "reflex-harmonised" not in low["flags"]
    assert low["reflex_verdicts"]["harmonised"]["reflex_passed"] is False
    stiff = t2_reflex_probe(
        [30.0] * 6, [30.0] * 10, ff, ref, h_max=19.1,
        sub_tier="T3c", job_bare_mean=56.0,
    )
    assert stiff["reflex_passed"] is False
    assert stiff["flags"] == ["cbi-stiff"]
    assert stiff.get("reflex_harmonised") is False
    assert stiff["reflex_violations"] == {"a": cap, "b": cap, "c": cap}


def test_item_74_harmonised_passer_ranks_when_long_passes():
    unit = {**_unit("T3b"), "t0_passed": True, "baseline": False}
    screen = {**unit, "screen_passed": True, "S": 1.0, "J": 1.0, "w_bg": 1.15}
    t2_row = {
        **screen, "deepest": "T2",
        "reflex_passed": True, "long_passed": True,
        "flags": ["reflex-harmonised"], "reflex_harmonised": True,
    }
    decision = decide_subtier(
        sub_tier="T3b", t0_units=[unit], t1_candidates=[screen], t2_results=[t2_row],
    )
    assert decision["failed_stage"] is None
    assert decision["ranked"][0]["reflex_harmonised"] is True
    miss_t2 = {
        **t2_row, "reflex_passed": False, "long_passed": False,
        "reflex_harmonised": False, "flags": [],
    }
    empty = decide_subtier(
        sub_tier="T3b", t0_units=[unit], t1_candidates=[screen], t2_results=[miss_t2],
    )
    assert empty["failed_stage"] == "R-reflex"
    assert empty["ranked"] == []


def test_t0_unit_counts_and_t2_b_unreachable_does_not_block_admission():
    units_a = t0_unit_list("T3a")
    assert len([u for u in units_a if not u["baseline"]]) == 180
    assert len([u for u in units_a if u["baseline"]]) == 12
    flagged = {**_unit(), "flags": t0_flags(bg_off_difference_hz=10.0)}
    result = admit_t1([flagged], rho_mech=1.0, t0_brain_s=100.0)
    assert flagged in result["admitted"] or any(
        u["g_gaba"] == flagged["g_gaba"] for u in result["admitted"]
    )
    assert t0_unit_list("T3b") and t0_unit_list("T3c")
    assert len(t0_unit_list("T3c")) == 45


def test_t0_pack_matches_section_65_at_rho_1():
    """T0 jobs at ρ_mech 1 keep one bare task and stay under the 6.5 cap."""
    cap = 36 * makespan_s()
    expected = {"T3a": (4, 196, 11760), "T3b": (4, 184, 11040), "T3c": (1, 46, 2760)}
    for sub, (n_jobs, n_tasks, brain) in expected.items():
        packed = t0_tasks(sub, 1.0)
        assert packed["launch"]
        assert packed["n_jobs"] == n_jobs
        assert packed["n_tasks"] == n_tasks
        assert packed["t0_brain_s"] == brain
        assert all(sum(1 for t in job if t["kind"] == "bare") == 1 for job in packed["jobs"])
        for job in packed["jobs"]:
            cost = sum(task_worker_s(float(t["brain_s"]), 1.0) for t in job)
            assert cost <= cap + 1e-6


def test_t1_admission_orders_pairs_by_parsimony_then_gaba_then_glu():
    """Unlocked: T1 pair order is parsimony, then g_gaba, then g_glu."""
    # ln(1.5) ≈ 0.405 < ln(2) ≈ 0.693, so (1.5, 1) beats (1, 2).
    units = [
        _unit(g_gaba=1.0, g_glu=2.0, b_mv=3.0),
        _unit(g_gaba=1.5, g_glu=1.0, b_mv=3.0),
        _unit(g_gaba=1.0, g_glu=1.0, b_mv=3.0),
    ]
    assert parsimony(1.5, 1.0) < parsimony(1.0, 2.0)
    capped = admit_t1(units, rho_mech=1.0, t0_brain_s=100.0, t1_max_units=2)
    pairs = [(u["g_gaba"], u["g_glu"]) for u in capped["admitted"]]
    assert pairs == [(1.0, 1.0), (1.5, 1.0)]
    tied = admit_t1(
        [_unit(g_gaba=2.0, g_glu=1.0, b_mv=1.0), _unit(g_gaba=1.0, g_glu=2.0, b_mv=1.0)],
        rho_mech=1.0, t0_brain_s=100.0, t1_max_units=2,
    )
    assert [(u["g_gaba"], u["g_glu"]) for u in tied["admitted"]] == [(1.0, 2.0), (2.0, 1.0)]


def test_t1_pack_matches_section_65_at_rho_1():
    """T1 at ρ_mech 1 uses slices of 8, 8 and 3 and packs 40 units into 8 jobs."""
    units = [_unit(g_gaba=1.0, g_glu=1.0, b_mv=0.1 * (i + 1), tau_ms=50.0) for i in range(40)]
    packed = t1_tasks(units, 1.0)
    assert packed["launch"]
    assert packed["slices"] == [[0, 8], [8, 16], [16, 19]]
    assert packed["n_tasks"] == 360
    assert packed["n_jobs"] == 8
    assert packed["t1_brain_s"] == 40 * 19 * 3 * 12
    assert packed["n_units"] == 40
    cap = 36 * makespan_s()
    for job in packed["jobs"]:
        cost = sum(task_worker_s(float(t["brain_s"]), 1.0) for t in job)
        assert cost <= cap + 1e-6
    slices, b = t1_weight_slices(1.0)
    assert b == 100
    assert slices == [(0, 8), (8, 16), (16, 19)]


def test_t2_pack_matches_section_65_at_rho_1():
    """T2 at ρ_mech 1 packs 20 candidates into 4 jobs of 760 tasks and 9,760 brain s."""
    cands = []
    for i in range(20):
        row = _unit(g_glu=1.0 + 0.001 * i, b_mv=0.1, tau_ms=50.0)
        cands.append({
            **row,
            "w_bg": 1.15,
            "pair_weights": [1.15, 1.20],
            "screen_passed": True,
            "S": float(i),
            "J": 0.0,
            "violations": {"F": 0.0},
        })
    packed = t2_tasks(cands, 1.0)
    assert packed["launch"]
    assert packed["n_jobs"] == 4
    assert packed["n_tasks"] == 760
    assert packed["t2_brain_s"] == 9760
    assert packed["n_candidates"] == 20
    cap = 36 * makespan_s()
    for job in packed["jobs"]:
        assert sum(1 for t in job if t["kind"] == "bare") == 10
        assert sum(1 for t in job if t["kind"] != "bare") == 180
        kinds = [t["kind"] for t in job if t["kind"] != "bare"]
        assert kinds.count("reflex-a") == 30
        assert kinds.count("reflex-b") == 50
        assert kinds.count("reflex-c") == 50
        assert kinds.count("long") == 50
        cost = sum(task_worker_s(float(t["brain_s"]), 1.0) for t in job)
        assert cost <= cap + 1e-6
        indexes = {t["candidate_index"] for t in job if t["kind"] != "bare"}
        for idx in indexes:
            n = sum(1 for t in job if t.get("candidate_index") == idx)
            assert n == 36


def test_admit_t2_uses_tier3_order_key_and_cap():
    many = [
        {**_unit(g_glu=1.0 + 0.001 * i), "screen_passed": True, "S": float(25 - i),
         "J": 0.0, "w_bg": 1.15, "pair_weights": [1.15, 1.20], "violations": {}}
        for i in range(25)
    ]
    admitted, excluded = admit_t2(many, cap=20)
    assert len(admitted) == 20 and len(excluded) == 5
    assert all(c["status"] == "not tested (cap)" for c in excluded)
    keys = [tier3_order_key(c) for c in admitted]
    assert keys == sorted(keys)


def test_camber_rest_tier3_requires_workers():
    """r14a: the T0 driver has no worker-count default."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    missing = subprocess.run(
        [sys.executable, str(root / "scripts/camber/rest_tier3.py"),
         "t0", "--plan", "x", "--job-index", "0", "--out", "y"],
        cwd=root, capture_output=True, text=True,
    )
    assert missing.returncode != 0
    assert "workers" in (missing.stderr + missing.stdout).lower()
    shell = subprocess.run(
        ["bash", str(root / "scripts/camber/rest_tier3.sh"), "label", "plan.json", "0"],
        cwd=root, capture_output=True, text=True,
    )
    assert shell.returncode == 2
    assert "workers" in shell.stderr.lower()
    t2_shell = subprocess.run(
        ["bash", str(root / "scripts/camber/rest_tier3_t2.sh"), "label", "plan.json", "0"],
        cwd=root, capture_output=True, text=True,
    )
    assert t2_shell.returncode == 2
    assert "workers" in t2_shell.stderr.lower()
    t2_missing = subprocess.run(
        [sys.executable, str(root / "scripts/camber/rest_tier3.py"),
         "t2", "--plan", "x", "--job-index", "0", "--out", "y"],
        cwd=root, capture_output=True, text=True,
    )
    assert t2_missing.returncode != 0
    assert "workers" in (t2_missing.stderr + t2_missing.stdout).lower()
