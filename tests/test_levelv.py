"""WP18 photoreceptor encoder, V0 to V-cal, and visual-path v2 constructed-input tests."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from flyonenomics.behaviour.encoder import (
    EYE_SPAN_DEG,
    PhotoreceptorEncoder,
    midpoint_rank_azimuths,
    photoreceptor_input_rates,
)
from flyonenomics.behaviour.visual_calibration import (
    P2_STAGE,
    STAGE,
    declared_substrate_id,
    run_r3,
    run_vcal,
)
from flyonenomics.diagnostics import visual_path as vp
from flyonenomics.orchestrator.seeds import ANALYSIS, stream
from flyonenomics.types import load_params
from flyonenomics.validation import levelv

ROOT = Path(__file__).resolve().parents[1]


def _registry(n: int, preferred: np.ndarray | None = None) -> SimpleNamespace:
    idx = np.arange(n, dtype=np.int32)
    sides = np.array(["left"] * (n // 2) + ["right"] * (n - n // 2))
    pop = SimpleNamespace(idx=idx, root_ids=np.arange(n, dtype=np.int64), side=sides)
    if preferred is not None:
        pop.azimuth_deg = preferred
    return SimpleNamespace(population=lambda name: pop)


def test_midpoint_rank_azimuths_open_interval_and_monotone() -> None:
    sides = np.array(["left", "left", "left", "right", "right", "right"])
    z = np.array([30.0, 10.0, 20.0, 5.0, 25.0, 15.0])
    az = midpoint_rank_azimuths(sides, z)
    left = az[sides == "left"]
    right = az[sides == "right"]
    left_z = z[sides == "left"]
    right_z = z[sides == "right"]
    assert np.all(left < 0) and np.all(right > 0)
    assert np.all(np.diff(left[np.argsort(left_z)]) < 0)
    assert np.all(np.diff(right[np.argsort(right_z)]) > 0)
    assert np.min(np.abs(left)) > 0 and np.max(np.abs(left)) < EYE_SPAN_DEG
    assert np.min(right) > 0 and np.max(right) < EYE_SPAN_DEG
    check = levelv.check_v0_a(sides, z, az)
    assert check["passed"]
    assert check["eyes"]["right"]["monotone"] and check["eyes"]["left"]["covers"]


def test_v0_b_spearman_on_constructed_l2() -> None:
    n = 20
    sides = np.array(["left"] * 10 + ["right"] * 10)
    z = np.concatenate([np.linspace(0, 9, 10), np.linspace(0, 9, 10)])
    rank = midpoint_rank_azimuths(sides, z)
    jitter = np.deg2rad(2.0)
    propagated = rank + 2.0 * np.sin(np.deg2rad(rank)) * jitter
    result = levelv.check_v0_b(z, sides, propagated)
    assert result["passed"]
    assert result["axis_used"] == "z_rank"
    assert result["z_rank"]["left"]["rho"] >= 0.9
    shuffled = rank.copy()
    shuffled[:10] = rank[9::-1]
    failed = levelv.check_v0_b(z, sides, shuffled)
    assert not failed["passed"]


def test_v0_b_principal_axis_gates_when_z_rank_fails() -> None:
    from scipy.stats import spearmanr

    rng = np.random.default_rng(15)
    n = 24
    sides = np.array(["left"] * 12 + ["right"] * 12)
    axis = np.concatenate([np.linspace(0, 11, 12), np.linspace(0, 11, 12)])
    z = axis + rng.normal(scale=10.0, size=n)
    if float(spearmanr(axis, z).statistic) < 0.0:
        z = -z
    xyz = np.column_stack([10.0 * axis, np.zeros(n), z])
    propagated = midpoint_rank_azimuths(sides, axis)
    result = levelv.check_v0_b(z, sides, propagated, l2_xyz=xyz)
    assert result["z_rank"]["left"]["rho"] is not None
    assert result["z_rank"]["left"]["rho"] < 0.9
    assert result["principal_axis"]["left"]["rho"] >= 0.9
    assert result["principal_axis"]["right"]["rho"] >= 0.9
    assert result["axis_used"] == "principal_axis"
    assert result["passed"] is True
    assert result["gating"] is True


def test_v0_b_recorded_not_gating_when_both_axes_fail() -> None:
    rng = np.random.default_rng(16)
    n = 24
    sides = np.array(["left"] * 12 + ["right"] * 12)
    z = np.linspace(0, 23, n)
    xyz = np.column_stack([z, np.zeros(n), np.zeros(n)])
    propagated = rng.normal(size=n)
    result = levelv.check_v0_b(z, sides, propagated, l2_xyz=xyz)
    assert result["recorded_not_gating"] is True
    assert result["gating"] is False
    assert result["passed"] is False
    assert result["axis_used"] == "recorded"


def test_v0_c_encoder_matches_independent_formula() -> None:
    constructed = levelv.constructed_v0_c_case()
    assert constructed["passed"]
    assert constructed["stripe"]["max_relative_error"] <= 1e-12
    assert constructed["ambient"]["passed"]
    assert constructed["dark"]["passed"]
    params = load_params()
    preferred = np.array([-90.0, -10.0, 10.0, 90.0])
    encoder = PhotoreceptorEncoder(
        _registry(4, preferred), np.arange(4, dtype=np.int32), params, "R1_6",
        preferred=preferred, r_light=100.0,
    )
    stimuli = [{"az_fly": 10.0, "width": 20.0, "contrast": 1.0}]
    off = encoder.rates(stimuli, enabled=False, r_light=100.0)
    ambient = encoder.rates([], kind="ambient", r_light=100.0)
    np.testing.assert_allclose(off, ambient)
    np.testing.assert_allclose(off, 100.0)
    dark = encoder.rates(stimuli, kind="dark", r_light=100.0)
    np.testing.assert_allclose(dark, 0.0)


def test_photoreceptor_full_cover_and_cap() -> None:
    preferred = np.array([0.0])
    rates = photoreceptor_input_rates(
        preferred, [{"az_fly": 0.0, "width": 80.0, "contrast": 1.0}],
        r_light=200.0, r_dark=0.0, acceptance_deg=5.0, r_max=150.0,
    )
    assert rates[0] < 1e-6
    capped = photoreceptor_input_rates(
        preferred, [], r_light=400.0, r_dark=0.0, acceptance_deg=5.0, r_max=300.0, kind="ambient",
    )
    assert capped[0] == 300.0


def test_column_subset_and_spread() -> None:
    azimuths = np.array([-40.0, -45.0, -80.0, 40.0, 45.0, 80.0])
    sides = np.array(["left", "left", "left", "right", "right", "right"])
    plus = vp.column_subset_indices(azimuths, sides, 45.0, halfwidth_deg=10.0)
    assert set(plus.tolist()) == {3, 4}
    minus = vp.column_subset_indices(azimuths, sides, -45.0, halfwidth_deg=10.0)
    assert set(minus.tolist()) == {0, 1}
    tight = np.array([44.0, 45.0, 46.0])
    assert vp.circular_std_deg(tight) < 20.0
    assert vp.uses_column_subsets(vp.circular_std_deg(tight))
    wide = np.array([-150.0, 0.0, 150.0])
    assert not vp.uses_column_subsets(vp.circular_std_deg(wide))


def test_v1_and_v2_statistics_on_constructed_seeds() -> None:
    rng = stream(20260912, 0, 0, ANALYSIS)
    n = 10
    carried = {
        "R1_6": np.full(n, 8.0),
        "L2": np.full(n, 3.0),
        "Tm1": np.full(n, 1.5),
        "T5": np.full(n, 1.2),
        "TuBu": np.full(n, 0.9),
        "steering_L": np.full(n, 2.0),
    }
    delta_steer = np.full(n, 2.0)
    result = vp.evaluate_v1(carried, delta_steer, rng, min_delta_hz=0.5, bootstrap_n=200)
    assert result["passed"]
    assert result["steer_pass"]
    assert result["break_at"] is None
    silent_medulla = dict(carried)
    silent_medulla["Tm1"] = np.zeros(n)
    broken = vp.evaluate_v1(silent_medulla, delta_steer, rng, min_delta_hz=0.5, bootstrap_n=200)
    assert not broken["passed"]
    assert broken["break_at"] == "medulla"
    v2 = vp.evaluate_v2(np.full(n, 2.0), np.full(n, -0.4))
    assert v2["passed"]
    assert not vp.evaluate_v2(np.full(n, -0.1), np.full(n, -0.4))["passed"]


def test_delta_steer_sign() -> None:
    value = vp.delta_steer(plus45_right_hz=5.0, plus45_left_hz=1.0, minus45_right_hz=1.0, minus45_left_hz=4.0)
    assert value == pytest.approx(7.0)


def test_v2_condition_grid_includes_dark_and_ambient() -> None:
    rows = vp.condition_grid_v2(r_light=150.0, seeds=(1, 2), histamine_scales=(1.0,))
    kinds = {row["kind"] for row in rows}
    assert kinds == {"dark", "ambient", "stripe"}
    assert any(row["azimuth"] == 45.0 for row in rows)
    assert any(row["azimuth"] == -45.0 for row in rows)
    record = vp.histamine_scale_record(1.0)
    assert record["drive.g_his"] == 1.0
    assert record["applied"] is False


def test_levelv_suite_v0_on_wp14_tables(monkeypatch, tmp_path) -> None:
    from flyonenomics.behaviour import visual_calibration

    for name in ("V1_RECORD", "V3_RECORD", "VCAL_RECORD"):
        monkeypatch.setattr(levelv, name, tmp_path / name)
    monkeypatch.setattr(visual_calibration, "VCAL_RECORD", tmp_path / "vcal")
    entry = levelv.verify_v0()
    assert entry.test_id == "V0"
    assert entry.compatibility == "canonical"
    assert entry.measured["c"]["passed"]
    assert entry.measured["a"]["passed"]
    z_left = entry.measured["b"]["z_rank"]["left"]["rho"]
    z_right = entry.measured["b"]["z_rank"]["right"]["rho"]
    assert z_left == pytest.approx(0.6727929181835998, abs=1e-6)
    assert z_right == pytest.approx(0.6761623028608588, abs=1e-6)
    pca_left = entry.measured["b"]["principal_axis"]["left"]["rho"]
    pca_right = entry.measured["b"]["principal_axis"]["right"]["rho"]
    assert pca_left == pytest.approx(0.4709881383553192, abs=1e-6)
    assert pca_right == pytest.approx(0.29099239902730023, abs=1e-6)
    assert entry.measured["b"]["recorded_not_gating"]
    assert entry.measured["b"]["axis_used"] == "recorded"
    assert entry.outcome == "passed"
    assert levelv.verify_v1().outcome == "unavailable"
    assert levelv.verify_v2().outcome == "unavailable"
    assert levelv.verify_v3().outcome == "unavailable"
    assert levelv.verify_vcal().outcome == "unavailable"


def test_r3_and_vcal_bind_to_item_122() -> None:
    from flyonenomics.behaviour.visual_calibration import declared_drive_present, declared_substrate

    assert STAGE["R3"] is run_r3
    assert "V-cal" not in STAGE
    declared = declared_substrate()
    assert declared is not None
    assert declared["candidate_id"] == "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
    assert declared["arm_id"] == "sens"
    assert declared["w_bg_mv"] == 1.0
    assert declared["g_gaba"] == 1.0 and declared["g_glu"] == 4.0
    assert declared["g_gaba_kc"] == 6.0 and declared["n_bg"] == 100
    assert declared["freeze"]["seeds"] == "11-20"
    assert declared["freeze"]["reflex_mean_hz"] is not None
    assert len(declared["records"]) == 2
    table = run_r3()
    assert table["status"] == "recorded"
    assert table["table"][0]["candidate_id"] == declared["candidate_id"]
    assert table["table"][0]["declared"] is True
    cells = table["table"][0]["rates"].values()
    expected = any((c.get("v3") or {}).get("passed") and
                   (c.get("v1_three_seed") or {}).get("passed") for c in cells)
    if any(c.get("v3") is not None for c in cells):
        assert table["table"][0]["passed"] == expected
    else:
        assert table["table"][0]["passed"] is None
    assert table["substrate_id"] == declared_substrate_id()
    constructed = run_r3([{"id": "cand-a", "rank": 1}, {"id": "cand-b", "rank": 2}])
    assert constructed["status"] == "recorded"
    assert len(constructed["table"]) == 2
    vcal = run_vcal()
    assert vcal["declared_substrate"]["candidate_id"] == declared["candidate_id"]
    if levelv.VCAL_RECORD.is_file():
        assert vcal["status"] in ("passed", "failed")
    elif declared_drive_present():
        assert vcal["status"] == "blocked"
        assert "engine run is not yet recorded" in vcal["reason"]
    else:
        assert "drive-v0.2.yaml" in vcal["reason"]
    assert P2_STAGE["R3"] is run_r3
    assert P2_STAGE["V-cal"] is run_vcal


def test_vcal_screen_records_the_declared_substrate() -> None:
    """When the run records exist they carry the Oracle identity and the screen label."""
    from flyonenomics.io import read_json
    from flyonenomics.validation.binding import sha256_file

    records = (
        (levelv.V3_RECORD, ROOT / "data/experiments/p2/vpath-v3.json"),
        (levelv.V1_RECORD, ROOT / "data/experiments/p2/vpath-v1.json"),
    )
    for path, fixture in records:
        if not path.is_file():
            continue
        record = read_json(path)
        assert record["status"] in ("passed", "failed")
        assert record["identity"]["platform"]
        assert record["identity"]["code_scope"]
        assert record["identity"]["engine_model"]
        assert record["identity"]["inputs"]
        assert record["identity"]["fixture_hash"] == sha256_file(fixture)
    if levelv.V1_RECORD.is_file():
        assert read_json(levelv.V1_RECORD)["screen"] in ("vcal_three_seed", "ten_seed", "ten_seed_selection")


def test_v_entries_record_the_declared_substrate() -> None:
    from flyonenomics.behaviour.visual_calibration import declared_substrate_id

    declared_id = declared_substrate_id()
    v0 = levelv.verify_v0()
    assert v0.measured["declared_substrate"]["candidate_id"] == "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
    assert declared_id is not None and declared_id.startswith("rest:")
    assert len(declared_id.split(":")[1]) == 16
    assert v0.identity.substrate_id == declared_id
    for entry in (levelv.verify_v1(), levelv.verify_v3(), levelv.verify_vcal()):
        assert entry.measured["declared_substrate"]["candidate_id"] == "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
        assert entry.identity.substrate_id == declared_id


def test_drive_v0_2_materialises_item_122() -> None:
    """One canonical drive for the declared substrate, per item 123."""
    from flyonenomics.drive.mechanisms import substrate_id_for
    from flyonenomics.drive.rest import load_drive_rest
    from flyonenomics.io import read_yaml
    from flyonenomics.validation.binding import sha256_file

    path = ROOT / "data" / "drive-v0.2.yaml"
    assert path.is_file()
    doc = read_yaml(path)
    assert "configuration_class" not in doc and "candidate_id" not in doc and "selection" not in doc
    assert doc["version"] == "v0.2"
    scales = doc["scales"]
    assert scales["g_gaba"] == 1.0 and scales["g_glu"] == 4.0
    assert scales["g_gaba_kc"] == 6.0 and scales["g_his"] == 1.0
    background = doc["background"]
    assert background["n_bg"] == 100 and background["r_bg"] == 10.0
    groups = background["groups"]
    assert groups["sensory"]["w_bg"] == 1.0
    assert all(row["w_bg"] == 0.0 for name, row in groups.items() if name != "sensory")
    assert doc["threshold"] is None and doc["optic_exemption"] is False
    provenance = doc["provenance"]
    assert provenance["item"] == 122
    assert provenance["declared_substrate"] == "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
    for key, rel in (
        ("rest-T3e-decision", "validation/records/p2/rest-T3e-decision.json"),
        ("rest-T3e-freeze-partial", "validation/records/p2/rest-T3e-freeze-partial.json"),
    ):
        assert provenance["records"][key]["path"] == rel
        assert provenance["records"][key]["sha256"] == sha256_file(ROOT / rel)
    loaded = load_drive_rest(path)
    assert loaded["g_gaba_kc"] == 6.0 and loaded["n_bg"] == 100.0
    tag = substrate_id_for(path)
    assert tag == declared_substrate_id()
    assert tag.startswith("rest:") and len(tag.split(":")[1]) == 16


def test_vpath_fixtures_exist_and_are_json() -> None:
    names = ("vpath-v0.json", "vpath-v1.json", "vpath-v2.json", "vpath-v3.json", "vpath-vcal.json")
    for name in names:
        path = ROOT / "data" / "experiments" / "p2" / name
        payload = json.loads(path.read_text())
        assert payload["schema_version"] == "1.3"
        assert payload["substrate"]["behaviour_version"] == "base-v0.2"
    vcal = json.loads((ROOT / "data/experiments/p2/vpath-vcal.json").read_text())
    assert vcal["meta"]["encoder_grid"] is True
    assert vcal["meta"]["grid"]["r_light"] == [50, 100, 150, 300]
    v1 = json.loads((ROOT / "data/experiments/p2/vpath-v1.json").read_text())
    blocks = v1["arms"][0]["protocol"][0]["params"]["blocks"]
    assert [row["stimulus"] for row in blocks] == ["ambient", "stripe", "ambient", "stripe"]
    duration = sum(row["transition_s"] + row["dwell_s"] for row in blocks)
    assert duration == v1["arms"][0]["protocol"][0]["duration_s"]


def test_v2_formula_cli(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "diagnose_visual_path_wp18", ROOT / "scripts" / "diagnose_visual_path.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    out = tmp_path / "v2"
    import sys

    old = sys.argv
    sys.argv = ["diagnose_visual_path.py", "--v2-formula", "--out", str(out)]
    try:
        module.main()
    finally:
        sys.argv = old
    payload = json.loads((out / "formula.json").read_text())
    assert payload["r_light_hz"] == 150.0
    assert len(payload["rates"]["ambient"]) == 21
    np.testing.assert_allclose(payload["rates"]["ambient"], 150.0)
    np.testing.assert_allclose(payload["rates"]["dark"], 0.0)


def test_engine_swap_budget_constant() -> None:
    assert vp.SWAP_BUDGET_M == 4000.0
    assert vp.engine_swap_ok(3999.0)
    assert not vp.engine_swap_ok(4000.1)


def test_wait_for_machine_does_not_sleep_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vp, "machine_status", lambda: {
        "ready": False, "abort": False, "bench": False, "other_heavy_python": 0, "swap_used_m": 100.0,
    })
    with pytest.raises(RuntimeError, match="machine not ready"):
        vp.wait_for_machine()


def test_encoder_dispatch_selects_photoreceptor_class() -> None:
    from flyonenomics.behaviour import encoder_class_for
    from flyonenomics.behaviour.encoder import VisualEncoder

    assert encoder_class_for("photoreceptors") is PhotoreceptorEncoder
    assert encoder_class_for("TuBu") is VisualEncoder
    assert encoder_class_for("ER") is VisualEncoder


def test_arena_passes_light_level_and_dark_state_to_photoreceptors() -> None:
    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.schema.experiment import Probe

    preferred = np.array([-90.0, 90.0])
    registry = _registry(2, preferred)
    probe = Probe.model_validate({
        "type": "probe", "assay": "open_loop_steering", "duration_s": 4, "label": "v",
        "params": {"inject_at": "photoreceptors", "blocks": [
            {"stimulus": "ambient", "transition_s": 1, "dwell_s": 1},
            {"stimulus": "dark", "transition_s": 1, "dwell_s": 1},
        ]},
    })
    plan = SimpleNamespace(topology=SimpleNamespace(extended_idx=np.arange(2, dtype=np.int32)))
    arena = Behaviour(
        plan, registry, load_params(), probe, v_fwd=10, sign_steer=1,
        K_steer=1, r_vis_max=100, sigma_vis=20,
    )
    np.testing.assert_allclose(arena.rates(arena.view(), 0.5), 100.0)
    np.testing.assert_allclose(arena.rates(arena.view(), 2.5), 0.0)


def test_within_eye_permutation_keeps_eye_sets() -> None:
    preferred = np.array([-120.0, -40.0, 40.0, 120.0])
    encoder = PhotoreceptorEncoder(
        _registry(4, preferred), np.arange(4, dtype=np.int32), load_params(), "R1_6",
        preferred=preferred, r_light=150.0,
    )
    encoder.encoder_seed = 7
    encoder.stream = np.random.default_rng(1)
    left = set(preferred[:2].tolist())
    right = set(preferred[2:].tolist())
    encoder.permutation(1)
    assert set(encoder.preferred[:2].tolist()) == left
    assert set(encoder.preferred[2:].tolist()) == right
    encoder.permutation(0)
    np.testing.assert_array_equal(encoder.preferred, preferred)


def test_photoreceptor_encoder_loads_wp14_azimuths() -> None:
    from flyonenomics.substrate.retinotopy import load_retinotopy

    table = load_retinotopy()
    r16 = table["types"]["R1_6"]
    n = 6
    roots = np.asarray(r16["root_ids"][:n], dtype=np.int64)
    sides = np.array(["left", "left", "left", "right", "right", "right"])
    idx = np.arange(n, dtype=np.int32)
    pop = SimpleNamespace(idx=idx, root_ids=roots, side=sides)
    encoder = PhotoreceptorEncoder(
        SimpleNamespace(population=lambda name: pop), idx, load_params(), "R1_6",
    )
    expected = np.array([float(v) for v in r16["azimuth_deg"][:n]])
    np.testing.assert_allclose(encoder.preferred, expected)


def test_photoreceptor_rates_treat_arena_ambient_as_l1() -> None:
    preferred = np.array([-90.0, 90.0])
    encoder = PhotoreceptorEncoder(
        _registry(2, preferred), np.arange(2, dtype=np.int32), load_params(), "R1_6",
        preferred=preferred,
    )
    ambient = [{"name": "ambient", "az_fly": 0.0, "width": 360.0, "contrast": 1.0}]
    rates = encoder.rates(ambient, enabled=True, maximum_hz=150.0, sigma_deg=20.0)
    np.testing.assert_allclose(rates, 150.0)
    off = encoder.rates([{"az_fly": 90.0, "width": 15.0, "contrast": 1.0}], enabled=False, maximum_hz=150.0)
    np.testing.assert_allclose(off, 150.0)
    dark = encoder.rates([], enabled=True, r_light=150.0, lit=False)
    np.testing.assert_allclose(dark, 0.0)
