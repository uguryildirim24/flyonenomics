"""WP26: g_gaba_kc on GABA→KC rows only. No Brian2 engine."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from flyonenomics.drive.rest import apply_rest_substrate, kc_mask_in_engine, load_drive_rest
from flyonenomics.drive.rest_tier3 import (
    T3D_T1_SLICE_WORKER_S,
    _t1_identity_key,
    candidate_id,
    collect_t1,
    gaba_kc_grid,
    gaba_kc_pairs,
    load_config,
    mechanism_strength,
    next_sub_tier,
    p2_partial_b,
    plan_record,
    t0_unit_list,
    t2_reflex_probe,
    t3d_wave_tasks,
)
from flyonenomics.io import read_json
from flyonenomics.substrate.scales import scale_array
from flyonenomics.types import load_params

ROOT = Path(__file__).resolve().parents[1]


def _core_drive(**extra):
    record = {
        "transmitter_rule": {"blob_id": "a" * 40, "scope": "brain"},
        "scales": {"g_gaba": 2.0, "g_glu": 4.0, "g_his": 1, "unk": "g_gaba when s_pq < 0", "sha256": "b" * 64},
        "background": {
            "n_bg": 100,
            "r_bg": 10,
            "groups": {"central": {"size": 3, "w_bg": 1.1}, "sensory": {"size": 1, "w_bg": 0.0}},
        },
        "threshold": None,
        "optic_exemption": False,
        "provenance": {"R1": "c" * 64},
    }
    record.update(extra)
    return record


def test_g_gaba_kc_one_is_byte_identical_to_bare() -> None:
    """g_gaba_kc 1 matches omitting the factor, even when post and mask are passed."""
    classes = np.array(["ACh", "Glu", "GABA", "unk"])
    s_pq = np.array([1.0, 1.0, -1.0, -1.0])
    pre = np.array([0, 1, 2, 3], dtype=np.int32)
    post = np.array([3, 3, 3, 3], dtype=np.int32)
    mask = np.array([0, 0, 0, 1], dtype=np.uint8)
    bare = scale_array(classes, s_pq, pre, g_glu=4.0, g_gaba=2.0)
    one = scale_array(
        classes, s_pq, pre, g_glu=4.0, g_gaba=2.0,
        g_gaba_kc=1.0, post=post, kc_mask=mask,
    )
    assert one.tobytes() == bare.tobytes()
    np.testing.assert_array_equal(one, bare)


def test_only_gaba_to_kc_rows_change() -> None:
    """A factor other than 1 multiplies GABA→KC rows and leaves every other row."""
    classes = np.array(["ACh", "Glu", "GABA", "GABA", "unk"])
    s_pq = np.array([1.0, 1.0, -1.0, -1.0, -1.0])
    pre = np.arange(5, dtype=np.int32)
    post = np.array([0, 0, 0, 1, 1], dtype=np.int32)
    mask = np.array([0, 1, 0, 0, 0], dtype=np.uint8)
    bare = scale_array(classes, s_pq, pre, g_glu=4.0, g_gaba=2.0)
    scaled = scale_array(
        classes, s_pq, pre, g_glu=4.0, g_gaba=2.0,
        g_gaba_kc=3.0, post=post, kc_mask=mask,
    )
    changed = np.flatnonzero(scaled != bare)
    np.testing.assert_array_equal(changed, np.array([3], dtype=np.int64))
    assert scaled[3] == pytest.approx(bare[3] * 3.0)
    assert scaled[2] == bare[2]
    assert scaled[4] == bare[4]
    with pytest.raises(ValueError, match="g_gaba_kc"):
        scale_array(
            classes, s_pq, pre, g_glu=4.0, g_gaba=2.0,
            g_gaba_kc=0.5, post=post, kc_mask=mask,
        )


def test_real_connectome_only_gaba_to_kc_rows_change() -> None:
    """On v783, g_gaba_kc 2 changes GABA→KC rows only, and 1 matches bare."""
    from flyonenomics.substrate.transmitters import annotations_in_engine, load_connection_columns, load_transmitters

    transmitters = load_transmitters()
    classes = transmitters["class_array"]
    table = load_connection_columns(("Presynaptic_Index", "Postsynaptic_Index", "Excitatory"))
    pre = np.asarray(table.column("Presynaptic_Index").to_numpy(), dtype=np.int32)
    post = np.asarray(table.column("Postsynaptic_Index").to_numpy(), dtype=np.int32)
    s_pq = np.sign(np.asarray(table.column("Excitatory").to_numpy(), dtype=np.float64))
    mask = kc_mask_in_engine()
    frame, _order = annotations_in_engine()
    assert int(mask.sum()) == 5177
    assert int((frame["cell_class"].fillna("").to_numpy(dtype=str) == "Kenyon_Cell").sum()) == 5177
    bare = scale_array(classes, s_pq, pre, g_glu=1.0, g_gaba=1.0)
    one = scale_array(
        classes, s_pq, pre, g_glu=1.0, g_gaba=1.0,
        g_gaba_kc=1.0, post=post, kc_mask=mask,
    )
    assert one.tobytes() == bare.tobytes()
    scaled = scale_array(
        classes, s_pq, pre, g_glu=1.0, g_gaba=1.0,
        g_gaba_kc=2.0, post=post, kc_mask=mask,
    )
    changed = scaled != bare
    gaba_to_kc = (classes[pre] == "GABA") & (mask[post] != 0)
    assert int(changed.sum()) == 21990
    assert int(changed.sum()) == int(gaba_to_kc.sum())
    np.testing.assert_array_equal(changed, gaba_to_kc)
    np.testing.assert_allclose(scaled[gaba_to_kc], bare[gaba_to_kc] * 2.0)


def test_load_drive_rest_g_gaba_kc_default_and_key(tmp_path: Path) -> None:
    """Absent g_gaba_kc is 1; scales.g_gaba_kc loads; a factor under 1 or non-numeric is rejected."""
    path = tmp_path / "drive.yaml"
    path.write_text(yaml.safe_dump(_core_drive()))
    loaded = load_drive_rest(path)
    assert loaded["g_gaba_kc"] == 1.0
    with_kc = _core_drive()
    with_kc["scales"]["g_gaba_kc"] = 4.0
    path.write_text(yaml.safe_dump(with_kc))
    assert load_drive_rest(path)["g_gaba_kc"] == 4.0
    with_kc["scales"]["g_gaba_kc"] = 0.5
    path.write_text(yaml.safe_dump(with_kc))
    with pytest.raises(ValueError, match="g_gaba_kc"):
        load_drive_rest(path)
    with_kc["scales"]["g_gaba_kc"] = 0.0
    path.write_text(yaml.safe_dump(with_kc))
    with pytest.raises(ValueError, match="g_gaba_kc"):
        load_drive_rest(path)
    with_kc["scales"]["g_gaba_kc"] = "not-a-number"
    path.write_text(yaml.safe_dump(with_kc))
    with pytest.raises(ValueError):
        load_drive_rest(path)


def test_apply_rest_substrate_passes_g_gaba_kc() -> None:
    """apply_rest_substrate writes the KC-scaled array when g_gaba_kc is set."""
    classes = np.array(["GABA", "GABA"])
    s_pq = np.array([-1.0, -1.0])
    pre = np.array([0, 1], dtype=np.int32)
    post = np.array([0, 1], dtype=np.int32)
    mask = np.array([0, 1], dtype=np.uint8)
    captured = {}

    class Engine:
        n = 2

        def set_weight_scale(self, scale):
            captured["scale"] = np.asarray(scale)

    drive = {
        "g_glu": 1.0, "g_gaba": 2.0, "g_gaba_kc": 3.0, "g_his": 1.0,
        "sigma_th": 0.0, "seed": 1, "mechanisms": None,
    }
    params = load_params()
    _base, scale = apply_rest_substrate(
        Engine(), params, drive,
        classes=classes, s_pq=s_pq, pre=pre, post=post, kc_mask=mask, n=2,
    )
    expected = scale_array(
        classes, s_pq, pre, 1.0, 2.0, g_gaba_kc=3.0, post=post, kc_mask=mask,
    )
    np.testing.assert_array_equal(captured["scale"], expected)
    np.testing.assert_array_equal(scale, expected)
    assert scale[0] == pytest.approx(2.0)
    assert scale[1] == pytest.approx(6.0)


def test_t3d_grid_has_24_units_and_kc_candidate_ids() -> None:
    """24 units: three pairs × {none, 3a} × four factors. M is g_gaba_kc."""
    load_config.cache_clear()
    units = t0_unit_list("T3d")
    assert len(units) == 24
    assert gaba_kc_pairs() == [(1.0, 1.0), (1.0, 2.0), (1.0, 4.0)]
    assert [row["g_gaba_kc"] for row in gaba_kc_grid()] == [2.0, 3.0, 4.0, 6.0] * 2
    none = [u for u in units if u["engine_model"] == "lif"]
    sfa = [u for u in units if u["engine_model"] == "lif+sfa"]
    assert len(none) == 12 and len(sfa) == 12
    assert {u["g_gaba_kc"] for u in units} == {2.0, 3.0, 4.0, 6.0}
    for unit in units:
        assert mechanism_strength("T3d", unit["setting"]) == unit["g_gaba_kc"]
        ident = candidate_id({**unit, "w_bg": 1.15})
        assert ident.endswith(f"-kc-{float(unit['g_gaba_kc'])}")
        if unit["engine_model"] == "lif":
            assert "-sfa-" not in ident
        else:
            assert "-sfa-1.0-50.0-non_sensory-" in ident
    bare = candidate_id({**none[0], "w_bg": 1.15})
    assert bare == "1.0-1.0-0.0-False-100-1.15-kc-2.0"
    with_sfa = candidate_id({**sfa[0], "w_bg": 1.15})
    assert with_sfa == "1.0-1.0-0.0-False-100-1.15-sfa-1.0-50.0-non_sensory-kc-2.0"
    assert next_sub_tier("T3c", "T0", []) == "T3d"
    assert p2_partial_b("T3d", "R-screen", [])
    assert not p2_partial_b("T3c", "R-screen", [])


def test_t3d_plan_packs_t0_and_t1_in_three_ibm_boxes() -> None:
    """Plan: 24 units, T0+T1 wave, three boxes, IBM 45.75, cap projection ~259."""
    load_config.cache_clear()
    wave = t3d_wave_tasks()
    plan = plan_record("T3d", 1.0)
    assert wave["launch"]
    assert wave["n_jobs"] <= 3
    assert plan["job_shapes"]["n_jobs"] == wave["n_jobs"]
    assert plan["job_shapes"]["wave"] == "T0+T1"
    assert plan["job_shapes"]["max_boxes"] == 3
    assert len(plan["units"]) == 24
    assert plan["rho_mech"] == 1.0
    assert plan["ibm"]["worker_s_per_brain_s"] == 45.75
    assert plan["ibm"]["workers"] == 36
    assert plan["ibm"]["setup_s"] == 600
    assert plan["brain_s_at_caps"] == pytest.approx(27736.0)
    assert plan["ibm_engine_hours_at_caps"] == pytest.approx(353.0, abs=0.6)
    assert plan["cap_projection_engine_hours"] == pytest.approx(259.0, abs=1.0)
    kinds = {t["kind"] for job in wave["jobs"] for t in job}
    assert "unit" in kinds and "t1" in kinds and "bare" in kinds
    n_bare = sum(1 for job in wave["jobs"] for t in job if t["kind"] == "bare")
    assert n_bare == 2
    max_t1 = max(float(t["brain_s"]) for job in wave["jobs"] for t in job if t["kind"] == "t1")
    assert max_t1 * T3D_T1_SLICE_WORKER_S + 250.0 < 9000.0
    assert wave["t1_slice_worker_s_per_brain_s"] == T3D_T1_SLICE_WORKER_S
    committed = read_json(ROOT / "validation/records/p2/rest-T3d-plan.json")
    assert committed == json.loads(json.dumps(plan))


def _ff_ok():
    return {"upstream": [60.0] * 10, "extended": [60.0] * 10}


def _bare_ok():
    return {"upstream": [100.0] * 10, "extended": [100.0] * 10}


def test_item_74_rejudges_only_a_b_at_half_bare() -> None:
    """Written 40/50 stay. (a)/(b)-only miss at 30 Hz passes 0.4/0.5 of 56 Hz."""
    a = [30.0] * 6
    b = [51.0] * 10
    written = t2_reflex_probe(a, b, _ff_ok(), _bare_ok(), h_max=None)
    assert written["reflex_passed"] is False
    scored = t2_reflex_probe(
        a, b, _ff_ok(), _bare_ok(), h_max=None, sub_tier="T3d", job_bare_mean=56.0,
    )
    assert scored["reflex_verdicts"]["original"]["reflex_passed"] is False
    assert scored["reflex_verdicts"]["harmonised"]["seed_min_hz"] == pytest.approx(22.4)
    assert scored["reflex_verdicts"]["harmonised"]["mean_hz"] == pytest.approx(28.0)
    assert scored["reflex_passed"] is True
    assert scored["reflex_harmonised"] is True
    assert "reflex-harmonised" in scored["flags"]


def test_item_74_does_not_rejudge_when_c_fails() -> None:
    """(c) miss is not an (a)/(b)-only miss."""
    a = [30.0] * 6
    b = [51.0] * 10
    weak = {"upstream": [60.0] * 10, "extended": [40.0] * 10}
    written = t2_reflex_probe(a, b, weak, _bare_ok(), h_max=None)
    scored = t2_reflex_probe(
        a, b, weak, _bare_ok(), h_max=None, sub_tier="T3d", job_bare_mean=56.0,
    )
    assert written["reflex_passed"] is False
    assert scored["reflex_passed"] is False
    assert scored.get("reflex_harmonised") is False
    assert "reflex-harmonised" not in scored["flags"]
    assert "reflex_verdicts" not in scored


def test_item_74_still_fails_below_harmonised_floors() -> None:
    """A 20 Hz seed min fails 22.4 Hz at bare 56 Hz."""
    a = [20.0] * 6
    b = [51.0] * 10
    scored = t2_reflex_probe(
        a, b, _ff_ok(), _bare_ok(), h_max=None, sub_tier="T3d", job_bare_mean=56.0,
    )
    assert scored["reflex_passed"] is False
    assert scored["reflex_verdicts"]["harmonised"]["reflex_passed"] is False
    assert "reflex-harmonised" not in scored["flags"]


def test_item_74_written_pass_is_not_flagged() -> None:
    """A 40/50 pass is not reflex-harmonised."""
    a = [40.0] * 6
    b = [51.0] * 10
    written = t2_reflex_probe(a, b, _ff_ok(), _bare_ok(), h_max=None)
    scored = t2_reflex_probe(
        a, b, _ff_ok(), _bare_ok(), h_max=None, sub_tier="T3d", job_bare_mean=56.0,
    )
    assert written["reflex_passed"] is True
    assert scored["reflex_passed"] is True
    assert "reflex-harmonised" not in scored["flags"]
    assert scored.get("reflex_harmonised") is False


def test_t1_skips_t0_failures_even_when_t1_rows_exist() -> None:
    """Wave T1 rows exist for every unit; collect_t1 scores T0 passers only."""
    passer = {
        "g_gaba": 1.0, "g_glu": 1.0, "setting": {"g_gaba_kc": 2.0},
        "t0_passed": True, "baseline": False,
    }
    failed = {
        "g_gaba": 1.0, "g_glu": 4.0, "setting": {"g_gaba_kc": 6.0},
        "t0_passed": False, "baseline": False,
    }
    keys = {
        _t1_identity_key(unit)
        for unit in (passer, failed)
        if unit.get("t0_passed") and not unit.get("baseline")
    }
    assert _t1_identity_key(passer) in keys
    assert _t1_identity_key(failed) not in keys
    summary = collect_t1([], t0_units=[passer, failed])
    assert summary["n_units"] == 0
