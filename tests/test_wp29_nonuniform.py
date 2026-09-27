"""WP29 sub-tier 3e non-uniform arms: vectors, packing, collector. No Brian2 engine."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from flyonenomics.drive.rest_map import TARGETS, _probe
from flyonenomics.drive.rest_nonuniform import (
    COMMON_LADDER,
    SENS_LADDER,
    background_vector,
    incoming_gain_scale,
    incoming_synapse_counts,
    indeg_gain,
    k_distribution,
    lab_measures,
    lab_sample_indices,
    outgoing_factor_scale,
    reciprocal_excitatory_partners,
    resolve_hub_types,
    screen_ladder,
    threshold_offset,
    type_name_mask,
)
from flyonenomics.drive.rest_tier3 import SUB_TIERS, WP27_CAP_USD, candidate_id, closest_3d_unit, grid_of, t2_reflex_probe
from flyonenomics.drive.rest_tier3e import (
    WP29_CAP_USD,
    WP29_MAX_JOBS,
    collect_t3e,
    hubs_from_plan,
    t3e_arms,
    t3e_plan_record,
    t3e_unit,
    t3e_wave_tasks,
)
from flyonenomics.drive.rest_map import Setting


def _groups() -> dict[str, np.ndarray]:
    return {
        "sensory": np.array([0, 1], dtype=np.int32),
        "motor": np.array([4, 5], dtype=np.int32),
        "central": np.array([2, 3], dtype=np.int32),
    }


def test_background_default_zeros_sensory_only() -> None:
    """Default policy matches the historic _probe exemption."""
    w = background_vector(6, 0.8, _groups(), "default")
    np.testing.assert_array_equal(w, np.array([0.0, 0.0, 0.8, 0.8, 0.8, 0.8]))


def test_background_sens_inverts_exemption() -> None:
    """Arm A drives sensory neurons only."""
    w = background_vector(6, 1.2, _groups(), "sens")
    np.testing.assert_array_equal(w, np.array([1.2, 1.2, 0.0, 0.0, 0.0, 0.0]))


def test_background_nomotor_zeros_motor() -> None:
    """Arm B keeps the sensory exemption and zeros motor."""
    w = background_vector(6, 0.8, _groups(), "nomotor")
    np.testing.assert_array_equal(w, np.array([0.0, 0.0, 0.8, 0.8, 0.0, 0.0]))


def test_indeg_gain_and_incoming_scale() -> None:
    """1/sqrt(K_i/K_median) lands on postsynaptic rows."""
    post = np.array([0, 0, 1, 2], dtype=np.int32)
    weights = np.array([2.0, 2.0, 4.0, 1.0])
    k = incoming_synapse_counts(post, weights, 3)
    np.testing.assert_array_equal(k, np.array([4.0, 4.0, 1.0]))
    info = k_distribution(k)
    assert info["k_median_positive"] == pytest.approx(4.0)
    gain = indeg_gain(k, info["k_median_positive"])
    assert gain[0] == pytest.approx(1.0)
    assert gain[2] == pytest.approx(2.0)
    scale = incoming_gain_scale(post, gain)
    assert scale[0] == pytest.approx(1.0)
    assert scale[3] == pytest.approx(2.0)


def test_threshold_offset_is_beta_times_k_over_1000() -> None:
    """Arm D offset is deterministic in in-degree."""
    k = np.array([0.0, 1000.0, 2000.0])
    off = threshold_offset(k, 2.0)
    np.testing.assert_allclose(off, np.array([0.0, 2.0, 4.0]))


def test_hub_outgoing_and_reciprocal_partners() -> None:
    """Outgoing factor hits hubs and reciprocal excitatory partners only."""
    pre = np.array([0, 1, 2, 3], dtype=np.int32)
    post = np.array([1, 0, 1, 4], dtype=np.int32)
    signed = np.array([1.0, 1.0, 1.0, -1.0])
    hubs = np.array([0], dtype=np.int32)
    partners = reciprocal_excitatory_partners(pre, post, signed, hubs)
    np.testing.assert_array_equal(partners, np.array([1], dtype=np.int32))
    scale = outgoing_factor_scale(pre, 4, np.array([0, 1]), 3.0)
    np.testing.assert_array_equal(scale, np.array([3.0, 3.0, 1.0, 1.0]))


def test_type_name_mask_does_not_match_longer_digits() -> None:
    """MBON06 does not match MBON060."""
    cell = np.array(["MBON06", "MBON06_L", "MBON060", "LPi13"])
    hemi = np.array(["", "x", "", "other"])
    mask = type_name_mask(cell, hemi, "MBON06")
    np.testing.assert_array_equal(mask, np.array([True, True, False, False]))
    resolved = resolve_hub_types(cell, hemi)
    assert resolved["resolved"] is False
    assert "LPi15" in resolved["missing"]


def test_lab_measures_independent_counts_are_near_one() -> None:
    """Independent Poisson bins give Fano near 1 and low correlation."""
    rng = np.random.default_rng(0)
    fano = rng.poisson(1.0, size=(40, 200)).astype(np.float64)
    pair = rng.poisson(1.0, size=(20, 200)).astype(np.float64)
    lab = lab_measures(fano, pair, chunk_ms=10.0)
    assert lab["single_unit_fano_100ms"]["mean"] is not None
    assert 0.5 < lab["single_unit_fano_100ms"]["mean"] < 1.5
    assert lab["mean_pairwise_corr_50ms"]["mean"] is not None
    assert abs(lab["mean_pairwise_corr_50ms"]["mean"]) < 0.3
    assert lab["pca_participation_ratio"]["value"] is not None
    assert lab["pca_participation_ratio"]["value"] > 1.0


def test_lab_sample_indices_are_fixed() -> None:
    """The 2000/500 samples are deterministic."""
    central = np.arange(3000, dtype=np.int32)
    a = lab_sample_indices(central)
    b = lab_sample_indices(central)
    np.testing.assert_array_equal(a["fano_idx"], b["fano_idx"])
    np.testing.assert_array_equal(a["pair_idx"], b["pair_idx"])
    assert a["fano_idx"].size == 2000
    assert a["pair_idx"].size == 500


def test_screen_ladder_uses_arm_grid_not_the_19_point_grid() -> None:
    """A 4-point ladder grades against its next point."""
    setting = Setting(1.0, 4.0, g_gaba_kc=6.0)
    rows = []
    for weight in COMMON_LADDER:
        for seed in (1, 2, 3):
            rows.append({
                "w_bg": float(weight),
                "seed": seed,
                "F": 2.0,
                "b": 0.002,
                "stability_ratio": 1.0,
                "rates_hz": {**TARGETS, "central": 1.0, "DAN": 1.0, "KC": 0.1},
            })
    scored = screen_ladder(setting, 0.75, rows, COMMON_LADDER)
    assert scored["screen_passed"] is True
    assert scored["pair_weights"] == [0.75, 0.80]
    assert scored["grade_weight"] == pytest.approx(0.85)
    with pytest.raises(ValueError):
        screen_ladder(setting, 0.85, rows, COMMON_LADDER)


def test_screen_ladder_sens_grades_against_next_point() -> None:
    """Arm A candidates are (0.80, 1.00) and (1.00, 1.20)."""
    setting = Setting(1.0, 4.0, g_gaba_kc=6.0)
    rows = []
    for weight in SENS_LADDER:
        for seed in (1, 2, 3):
            rows.append({
                "w_bg": float(weight),
                "seed": seed,
                "F": 2.0,
                "b": 0.002,
                "stability_ratio": 1.0,
                "rates_hz": {**TARGETS, "central": 1.0, "DAN": 1.0, "KC": 0.1},
            })
    scored = screen_ladder(setting, 1.00, rows, SENS_LADDER)
    assert scored["pair_weights"] == [1.00, 1.20]
    assert scored["grade_weight"] == pytest.approx(1.40)


def test_probe_source_keeps_default_sensory_exemption() -> None:
    """Default _probe scoring path still zeros sensory background."""
    source = inspect.getsource(_probe)
    assert "w[groups['sensory']] = 0." in source
    assert "settle 2 s, measure" in _probe.__doc__
    assert "_instrumented_probe" not in source


def test_candidate_id_appends_arm() -> None:
    """3e ids stay distinct from the 3d substrate."""
    unit = t3e_unit({"id": "sens", "bg_policy": "sens", "ladder": list(SENS_LADDER)})
    unit["w_bg"] = 0.8
    assert candidate_id(unit).endswith("-sens")
    base = closest_3d_unit()
    base["w_bg"] = 0.85
    assert candidate_id(base) == "1.0-4.0-0.0-False-100-0.85-kc-6.0"


def _hubs_ok() -> dict:
    return {"resolved": True, "missing": [], "counts": {"MBON06": 2, "LPi13": 1, "LPi15": 1}, "idx": [1, 2, 3]}


def test_wave_fits_two_boxes_and_cap() -> None:
    """Nine settings pack into two IBM jobs under $20 list."""
    packed = t3e_wave_tasks(hubs=_hubs_ok())
    assert packed["launch"] is True
    assert packed["reason"] is None
    assert packed["n_jobs"] == WP29_MAX_JOBS
    assert packed["list_usd"] <= WP29_CAP_USD
    assert packed["list_usd"] > WP27_CAP_USD or packed["brain_s"] > 1000
    arms = {t["arm_id"] for job in packed["jobs"] for t in job if t.get("arm_id")}
    assert "sens" in arms and "nomotor" in arms and "indeg" in arms
    assert "thdeg-0.5" in arms and "hubs-2" in arms
    for job in packed["jobs"]:
        assert any(t["kind"] == "bare" for t in job)
        assert any(t["kind"] == "t1" for t in job)
        assert any(t["kind"] == "t3e-sugar" for t in job)
        assert any(t["kind"] == "unit" for t in job)
    assert packed["n_arms"] == len(t3e_arms(include_hubs=True))
    assert packed["brain_s"] == sum(float(t["brain_s"]) for job in packed["jobs"] for t in job)


def test_hub_skip_drops_arm_e() -> None:
    """Unresolved hub types omit arm E and keep the other four."""
    packed = t3e_wave_tasks(hubs={"resolved": False, "missing": ["LPi13"], "counts": {}, "idx": []})
    arms = {t["arm_id"] for job in packed["jobs"] for t in job if t.get("arm_id")}
    assert "hubs-2" not in arms
    assert "sens" in arms and "indeg" in arms
    assert packed["n_jobs"] == 2
    assert packed["launch"] is True


def _write_ndjson(path: Path, evals: list[dict], *, extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = extra or {}
    lines = [json.dumps({"kind": "task-build", "build_s": 1.0, **meta})]
    for row in evals:
        lines.append(json.dumps({"kind": "evaluation", **meta, **row}))
    lines.append(json.dumps({
        "kind": "task-complete", "evaluations": len(evals), "build_s": 1.0,
        "wall_s": 2.0, "brain_s": 10.0, "wall_per_brain_s": 0.2, **meta,
    }))
    path.write_text("\n".join(lines) + "\n")


def test_collect_t3e_empty_ranked_keeps_closest_miss(tmp_path: Path) -> None:
    """A failing F grid admits nothing and records S, F, KC, central, dark MN9."""
    out = tmp_path / "job0"
    arm = {"id": "indeg", "bg_policy": "default", "scale": "indeg", "ladder": list(COMMON_LADDER)}
    unit = t3e_unit(arm)
    tasks = []
    for seed in (1, 2, 3):
        path = out / f"t3e-indeg-s{seed}.ndjson"
        evals = []
        for weight in COMMON_LADDER:
            evals.append({
                "w_bg": float(weight),
                "seed": seed,
                "F": 4.0,
                "b": 0.002,
                "stability_ratio": 1.0,
                "mn9_hz": 0.1,
                "rates_hz": {**TARGETS, "central": 1.0, "DAN": 1.0, "KC": 0.1},
            })
        _write_ndjson(path, evals, extra={"unit": unit, "arm_id": "indeg"})
        tasks.append({"kind": "t1", "path": str(path), "unit": unit, "arm_id": "indeg", "seed": seed})
    t0_path = out / "t3e-indeg-t0.ndjson"
    _write_ndjson(t0_path, [{"seed": seed, "difference_hz": 40.0} for seed in range(1, 11)])
    tasks.append({"kind": "unit", "path": str(t0_path), "unit": unit, "arm_id": "indeg"})
    for weight in COMMON_LADDER:
        path = out / f"sugar-{weight}.ndjson"
        _write_ndjson(path, [{"seed": seed, "w_bg": weight, "difference_hz": 20.0} for seed in range(1, 11)])
        tasks.append({"kind": "t3e-sugar", "path": str(path), "unit": unit, "arm_id": "indeg", "w_bg": weight})
    bare = out / "bare-00.ndjson"
    _write_ndjson(bare, [{"seed": seed, "difference_hz": 56.0} for seed in range(1, 11)])
    tasks.append({"kind": "bare", "path": str(bare), "job_index": 0})
    record = collect_t3e([(out, tasks)])
    assert record["admitted_t1"] is False
    assert record["admitted_t2"] is False
    assert record["ranked"] == []
    assert record["failed_stage"] == "R-screen"
    assert record["qualified"] == []
    miss = record["closest_miss"]
    assert miss is not None
    assert miss["S"] > 0
    assert miss["pair_weights"] == [0.75, 0.80]
    assert miss["measured_F_max_pair"] == pytest.approx(4.0)
    assert miss["measured_kc_hz_mean"] == pytest.approx(0.1)
    assert miss["mn9_dark_max_hz"] == pytest.approx(0.1)
    assert miss["mn9_dark_every_seed_under_5"] is True
    assert record["misses"]


def test_collect_t3e_keeps_sens_pair_weights_not_3d_pair(tmp_path: Path) -> None:
    """closest_3d_unit pair_weights 0.85/0.90 must not overwrite the A ladder."""
    out = tmp_path / "job0"
    arm = {"id": "sens", "bg_policy": "sens", "ladder": list(SENS_LADDER)}
    unit = t3e_unit(arm)
    assert unit["pair_weights"] == [0.85, 0.9]
    tasks = []
    for seed in (1, 2, 3):
        path = out / f"t3e-sens-s{seed}.ndjson"
        evals = []
        for weight in SENS_LADDER:
            evals.append({
                "w_bg": float(weight),
                "seed": seed,
                "F": 4.0,
                "b": 0.002,
                "stability_ratio": 1.0,
                "mn9_hz": 0.2,
                "rates_hz": {**TARGETS, "central": 1.0, "DAN": 1.0, "KC": 0.1},
            })
        _write_ndjson(path, evals, extra={"unit": unit, "arm_id": "sens"})
        tasks.append({"kind": "t1", "path": str(path), "unit": unit, "arm_id": "sens", "seed": seed})
    t0_path = out / "t3e-sens-t0.ndjson"
    _write_ndjson(t0_path, [{"seed": seed, "difference_hz": 40.0} for seed in range(1, 11)])
    tasks.append({"kind": "unit", "path": str(t0_path), "unit": unit, "arm_id": "sens"})
    for weight in SENS_LADDER:
        path = out / f"sugar-{weight}.ndjson"
        _write_ndjson(path, [{"seed": seed, "w_bg": weight, "difference_hz": 20.0} for seed in range(1, 11)])
        tasks.append({"kind": "t3e-sugar", "path": str(path), "unit": unit, "arm_id": "sens", "w_bg": weight})
    bare = out / "bare-00.ndjson"
    _write_ndjson(bare, [{"seed": seed, "difference_hz": 56.0} for seed in range(1, 11)])
    tasks.append({"kind": "bare", "path": str(bare), "job_index": 0})
    record = collect_t3e([(out, tasks)])
    miss = record["closest_miss"]
    assert miss["pair_weights"] == [0.80, 1.00]
    assert miss["w_bg"] == pytest.approx(0.80)
    assert miss["measured_F_max_pair"] == pytest.approx(4.0)
    assert miss["mn9_dark_max_hz"] == pytest.approx(0.2)
    assert record["failed_stage"] == "R-screen"
    assert record["qualified"] == []


def test_hubs_from_plan_skips_arm_e_when_include_hubs_false() -> None:
    """A stored plan with include_hubs false omits E even if counts exist."""
    plan = {
        "include_hubs": False,
        "hubs": {"resolved": True, "missing": [], "counts": {"MBON06": 1}, "idx": [1]},
    }
    packed = t3e_wave_tasks(hubs=hubs_from_plan(plan))
    arms = {t["arm_id"] for job in packed["jobs"] for t in job if t.get("arm_id")}
    assert "hubs-2" not in arms
    assert "sens" in arms


def test_plan_record_omits_task_payloads() -> None:
    """The plan json has cost and shapes, not per-task units."""
    plan = t3e_plan_record(hubs=_hubs_ok())
    assert "jobs" not in plan
    assert plan["launch"] is True
    assert plan["list_usd"] <= WP29_CAP_USD
    assert plan["brain_s"] > 1000
    assert plan["n_jobs"] == WP29_MAX_JOBS
    assert plan["include_hubs"] is True
    assert {row["id"] for row in plan["arms"]} == {a["id"] for a in t3e_arms(include_hubs=True)}


def test_t3e_is_not_a_grid_sub_tier() -> None:
    """T3e is not in grid_of. Item 74 still applies."""
    assert "T3e" not in SUB_TIERS
    with pytest.raises(ValueError, match="unknown sub-tier"):
        grid_of("T3e")
    ff = {"upstream": [60.0] * 10, "extended": [60.0] * 10}
    ref = {"upstream": [100.0] * 10, "extended": [100.0] * 10}
    out = t2_reflex_probe(
        [30.0] * 6, [30.0] * 10, ff, ref, sub_tier="T3e", job_bare_mean=56.0,
    )
    assert out["reflex_passed"] is True
    assert out["reflex_harmonised"] is True


def test_item_74_on_the_sens_passer_numbers() -> None:
    """Live 3e passer diffs fail item 74 on min(a), mean(b), and min(b)."""
    ff = {"upstream": [31.3] * 10, "extended": [31.3] * 10}
    ref = {"upstream": [56.0] * 10, "extended": [56.0] * 10}
    a = [33.0, 34.0, 22.0, 19.0, 22.0, 21.0]
    b = [33.0, 34.0, 22.0, 26.0, 23.0, 27.0, 30.0, 27.0, 25.0, 27.0]
    out = t2_reflex_probe(a, b, ff, ref, sub_tier="T3e", job_bare_mean=56.0)
    assert min(a) == 19.0
    assert sum(b) / 10 == pytest.approx(27.4)
    assert min(b) == 22.0
    assert out["reflex_passed"] is False
    assert out["reflex_harmonised"] is False
    harm = out["reflex_verdicts"]["harmonised"]
    assert harm["mean_hz"] == pytest.approx(28.0)
    assert harm["seed_min_hz"] == pytest.approx(22.4)
    assert harm["reflex_passed"] is False


def test_item_74_harmonised_fails_when_only_min_b_is_under_floor() -> None:
    """Item 74 (b) needs min(b) >= 0.4 of the same-job bare, not only the mean."""
    ff = {"upstream": [31.3] * 10, "extended": [31.3] * 10}
    ref = {"upstream": [56.0] * 10, "extended": [56.0] * 10}
    a = [33.0, 34.0, 30.0, 29.0, 28.0, 27.0]
    b = [33.0, 34.0, 22.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0]
    assert min(a) >= 22.4
    assert sum(b) / 10 > 28.0
    assert min(b) < 22.4
    out = t2_reflex_probe(a, b, ff, ref, sub_tier="T3e", job_bare_mean=56.0)
    assert out["reflex_passed"] is False
    assert out["reflex_harmonised"] is False

