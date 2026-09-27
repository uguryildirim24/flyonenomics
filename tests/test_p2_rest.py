"""WP15 rest-substrate tests: 0.11, 0.13, composition and settle helpers."""

from __future__ import annotations

import numpy as np
import pytest

from flyonenomics.types import load_params
from flyonenomics.validation.level0_rest import run_0_11, run_0_13_cases, test_0_11 as suite_0_11
from flyonenomics.validation.level0_rest import test_0_13 as suite_0_13


def test_0_11_threshold_composition_bitwise() -> None:
    """Each engine threshold equals base + dopamine + shift, bitwise."""
    measured = run_0_11()
    assert measured["passed"]
    entry = suite_0_11()
    assert entry.test_id == "0.11"
    assert entry.outcome == "passed"


def test_0_13_settle_rule_synthetic() -> None:
    """Section 2.4 cases (a) and (b) pass; schema 1.2 keeps the Phase 1 DA rule."""
    measured = run_0_13_cases()
    assert measured["stationary_converge"] >= 0.99
    assert measured["drift20_converge"] <= 0.01
    assert measured["unresolved_labels_ok"]
    assert measured["schema_12_uses_phase1_da"]
    assert measured["passed"]
    entry = suite_0_13()
    assert entry.test_id == "0.13"
    assert entry.outcome == "passed"


def test_compose_starts_from_per_neuron_base() -> None:
    """compose uses the per-neuron base, not the scalar lif.v_th, when given."""
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.validation.level0_rest import _Registry
    from flyonenomics.types import LayerFlags

    params = load_params()
    base = np.array([-44.0, -46.0, -45.0, -47.0], dtype=np.float64)
    mod = Neuromod(_Registry(), params, LayerFlags(dopamine_A=False), base_v_th=base)
    composed = mod.compose()
    np.testing.assert_array_equal(composed.v_th, np.clip(base, *params.get("rec.vth_clip")))


def test_apply_rest_substrate_scale_and_drive_stream() -> None:
    """apply_rest_substrate writes scale_array output and draws the DRIVE stream."""
    from types import SimpleNamespace

    from flyonenomics.drive.rest import apply_rest_substrate
    from flyonenomics.substrate.scales import scale_array
    from flyonenomics.types import DRIVE

    classes = np.array(["ACh", "Glu", "GABA", "unk"])
    s_pq = np.array([1.0, 1.0, -1.0, -1.0])
    pre = np.array([0, 1, 2, 3], dtype=np.int32)
    drive = {"g_glu": 4.0, "g_gaba": 2.0, "g_his": 1.0, "sigma_th": 1.0, "seed": 20260914, "mechanisms": None}
    captured = {}

    class Engine:
        n = 4

        def set_weight_scale(self, scale):
            captured["scale"] = np.asarray(scale)

    params = load_params()
    base, scale = apply_rest_substrate(Engine(), params, drive, classes=classes, s_pq=s_pq, pre=pre, n=4)
    expected = scale_array(classes, s_pq, pre, 4.0, 2.0)
    np.testing.assert_array_equal(captured["scale"], expected)
    np.testing.assert_array_equal(scale, expected)
    rng = np.random.default_rng(np.random.SeedSequence(20260914, spawn_key=(0, 0, DRIVE)))
    np.testing.assert_array_equal(base, params.get("lif.v_th") + rng.standard_normal(4))
    # The section 8.1 scales-only fixture keeps lif.v_th everywhere.
    flat, _ = apply_rest_substrate(Engine(), params, drive, classes=classes, s_pq=s_pq, pre=pre, n=4, thresholds=False)
    np.testing.assert_array_equal(flat, np.full(4, params.get("lif.v_th")))


def test_threshold_z_is_truncated_by_redrawing_and_hashed() -> None:
    """z_i ~ N(0, 1) truncated to ±2; the float32 SHA-256 is checked against the drive file."""
    from flyonenomics.drive.rest import apply_rest_substrate, draw_threshold_z, z_sha256
    from flyonenomics.types import DRIVE

    z = draw_threshold_z(20260914, 5000)
    assert np.all(np.abs(z) <= 2.0)
    raw = np.random.default_rng(np.random.SeedSequence(20260914, spawn_key=(0, 0, DRIVE))).standard_normal(5000)
    inside = np.abs(raw) <= 2.0
    assert not np.all(inside)
    np.testing.assert_array_equal(z[inside], raw[inside])
    np.testing.assert_array_equal(draw_threshold_z(20260914, 5000), z)

    class Engine:
        def set_weight_scale(self, scale):
            pass

    args = dict(classes=np.array(["ACh"]), s_pq=np.array([1.0]), pre=np.array([0], dtype=np.int32), n=5000)
    drive = {"g_glu": 1.0, "g_gaba": 1.0, "sigma_th": 2.0, "seed": 20260914, "z_sha256": z_sha256(z), "mechanisms": None}
    base, _ = apply_rest_substrate(Engine(), load_params(), drive, **args)
    np.testing.assert_array_equal(base, load_params().get("lif.v_th") + 2.0 * z)
    with pytest.raises(ValueError, match="z SHA-256"):
        apply_rest_substrate(Engine(), load_params(), {**drive, "z_sha256": "0" * 64}, **args)
    with pytest.raises(ValueError, match="scales.sha256"):
        apply_rest_substrate(Engine(), load_params(), {**drive, "scale_sha256": "0" * 64}, **args)


def _drive_file(tmp_path, **changes):
    import yaml

    record = {
        "transmitter_rule": {"blob_id": "a" * 40, "scope": "brain"},
        "scales": {"g_gaba": 2.0, "g_glu": 4.0, "g_his": 1, "unk": "g_gaba when s_pq < 0", "sha256": "b" * 64},
        "background": {"n_bg": 100, "r_bg": 10, "groups": {"central": {"size": 3, "w_bg": 1.1}, "sensory": {"size": 1, "w_bg": 0.0}}},
        "threshold": None,
        "optic_exemption": False,
        "provenance": {"R1": "c" * 64},
    }
    record.update(changes)
    path = tmp_path / "drive-v0.2.yaml"
    path.write_text(yaml.safe_dump(record))
    return path


def test_drive_v02_loader_reads_the_section_2_5_structure(tmp_path) -> None:
    """Scales, background, threshold and scope come from their sections; no qualified flag."""
    from flyonenomics.drive.rest import load_drive_rest

    drive = load_drive_rest(_drive_file(tmp_path))
    assert (drive["g_glu"], drive["g_gaba"], drive["g_his"], drive["sigma_th"]) == (4.0, 2.0, 1.0, 0.0)
    assert drive["w_bg"] == {"central": 1.1, "sensory": 0.0}
    assert drive["scope"] == "brain" and drive["scale_sha256"] == "b" * 64
    for changes, message in (
        ({"qualified": True}, "qualified"),
        ({"threshold": {"sigma_th": 1.0, "seed": 20260914}}, "z_sha256"),
        ({"scales": {"g_gaba": 2.0, "g_glu": 4.0, "g_his": 2}}, "g_his"),
        ({"transmitter_rule": {"blob_id": "a" * 40, "scope": "central"}}, "scope"),
        ({"optic_exemption": "on"}, "optic_exemption"),
    ):
        with pytest.raises(ValueError, match=message):
            load_drive_rest(_drive_file(tmp_path, **changes))
    path = _drive_file(tmp_path)
    text = path.read_text().replace("optic_exemption: false\n", "")
    path.write_text(text)
    with pytest.raises(ValueError, match="misses sections"):
        load_drive_rest(path)


def test_rest_background_weights_follow_groups_and_params(tmp_path, monkeypatch) -> None:
    """drive-v0.2 group weights expand per neuron; n_bg and r_bg must match params."""
    import flyonenomics.drive.background as background
    from types import SimpleNamespace

    from flyonenomics.drive.rest import load_drive_rest, rest_background_weights

    registry = SimpleNamespace(n=4)
    monkeypatch.setattr(background, "group_indices", lambda reg: {
        "central": np.array([0, 2, 3], dtype=np.int32), "sensory": np.array([1], dtype=np.int32)})
    params = load_params()
    drive = load_drive_rest(_drive_file(tmp_path))
    np.testing.assert_array_equal(rest_background_weights(registry, drive, params), [1.1, 0.0, 1.1, 1.1])
    with pytest.raises(ValueError, match="n_bg"):
        rest_background_weights(registry, {**drive, "n_bg": 25.0}, params)
    with pytest.raises(ValueError, match="groups"):
        rest_background_weights(registry, {**drive, "w_bg": {"central": 1.1}}, params)


def test_encoder_dispatch_by_inject_at(monkeypatch) -> None:
    """inject_at photoreceptors selects PhotoreceptorEncoder when present."""
    from flyonenomics.behaviour import encoder_class_for
    from flyonenomics.behaviour.encoder import VisualEncoder

    assert encoder_class_for("TuBu") is VisualEncoder
    assert encoder_class_for("ER") is VisualEncoder
    import flyonenomics.behaviour.encoder as encoder_mod
    if not hasattr(encoder_mod, "PhotoreceptorEncoder"):
        with pytest.raises(ValueError, match="PhotoreceptorEncoder"):
            encoder_class_for("photoreceptors")

    class PhotoreceptorEncoder:
        pass

    monkeypatch.setattr(encoder_mod, "PhotoreceptorEncoder", PhotoreceptorEncoder, raising=False)
    assert encoder_class_for("photoreceptors") is PhotoreceptorEncoder
    assert encoder_class_for("TuBu") is VisualEncoder


def _assert_topology_adds_r16() -> None:
    """R1_6 enters extended_idx for photoreceptor injection and ambient spontaneous."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from flyonenomics.orchestrator.phases import build_topology
    from flyonenomics.schema.experiment import Experiment

    class Registry:
        def population(self, name: str):
            idx = {"R1_6": [10, 11], "TuBu": [0, 1], "ER": [4]}.get(name, [99])
            return SimpleNamespace(idx=np.array(idx, dtype=np.int32))

    proto = {
        "schema_version": "1.3",
        "name": "topo",
        "seed": 1,
        "seeds": [1],
        "layers": {"background": True},
        "arms": [{"label": "wild-type", "protocol": [
            {"type": "probe", "assay": "buridan", "duration_s": 0.01, "label": "b",
             "params": {"inject_at": "photoreceptors", "encoder": "off"}},
        ]}],
    }
    settings = {"v_fwd": 1, "sign_steer": 1, "K_steer": 1, "r_vis_max": 1, "sigma_vis": 20}
    with patch("flyonenomics.behaviour.load_settings", lambda *args, **kwargs: settings):
        plan = build_topology(Experiment.model_validate(proto), Registry())
        assert plan.topology.extended_idx.tolist() == [10, 11]
        proto["arms"][0]["protocol"] = [
            {"type": "probe", "assay": "spontaneous", "duration_s": 0.01, "label": "a",
             "params": {"stimulus": "ambient"}},
        ]
        plan = build_topology(Experiment.model_validate(proto), Registry())
        assert plan.topology.extended_idx.tolist() == [10, 11]


def test_topology_adds_r16_for_photoreceptor_and_ambient() -> None:
    """Keep InputTopology's package import out of the parent registry tests."""
    import subprocess
    import sys

    from pathlib import Path

    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'tests'); "
         "from test_p2_rest import _assert_topology_adds_r16 as check; check()"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1],
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_random_heading_and_bias_in_omega() -> None:
    """Random heading is the first BEHAVIOUR draw; bias sits only in omega."""
    from types import SimpleNamespace

    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.schema.experiment import Probe

    registry = SimpleNamespace(population=lambda name: SimpleNamespace(
        idx=np.array([0], dtype=np.int32) if name.endswith("_L") else np.array([1], dtype=np.int32),
        root_ids=np.array([11, 12], dtype=np.int64) if name == "TuBu" else np.array([1], dtype=np.int64),
        side=np.array(["left", "right"]) if name == "TuBu" else np.array(["left"]),
    ))
    probe = Probe.model_validate({
        "type": "probe", "assay": "buridan", "duration_s": 0.2, "label": "b",
        "params": {"inject_at": "TuBu", "initial_heading": "random"},
    })
    plan = SimpleNamespace(topology=SimpleNamespace(extended_idx=np.array([0, 1], dtype=np.int32)))
    # VisualEncoder needs TuBu in extended_idx matching idx 0,1 - Fake uses steering idx 0,1
    class Reg:
        def population(self, name: str):
            if name == "TuBu":
                return SimpleNamespace(idx=np.array([0, 1], dtype=np.int32),
                                       root_ids=np.array([11, 12], dtype=np.int64),
                                       side=np.array(["left", "right"]))
            if name == "steering_L":
                return SimpleNamespace(idx=np.array([2], dtype=np.int32))
            return SimpleNamespace(idx=np.array([3], dtype=np.int32))
    arena = Behaviour(plan, Reg(), load_params(), probe, v_fwd=10, sign_steer=1,
                      K_steer=4, r_vis_max=100, sigma_vis=20, bias_hz=2.0)
    stream = np.random.default_rng(np.random.SeedSequence(1, spawn_key=(0, 0, 2)))
    expected = 180.0 - float(np.random.default_rng(np.random.SeedSequence(1, spawn_key=(0, 0, 2))).random()) * 360.0
    arena.reset(stream)
    assert arena.h == pytest.approx(expected)
    arena.r_R = 5.0
    arena.r_L = 1.0
    arena.step(np.zeros(4, dtype=np.int32), 0.01)
    # After one filter step from 0, rates are small; omega uses (r_R - r_L - bias)
    assert arena.omega == pytest.approx(arena.sign_steer * arena.K_steer * ((arena.r_R - arena.r_L) - 2.0))


def test_da_exposed_requires_exposure_and_receptor() -> None:
    """DA_exposed is nonzero exposure AND a nonzero receptor weight."""
    from scipy.sparse import csr_matrix

    from flyonenomics.registry.derived import da_exposed
    from flyonenomics.registry.receptors import ReceptorMap

    class Registry:
        n = 4
        root_ids = np.arange(4, dtype=np.int64)

        def exposure(self):
            return csr_matrix(np.array([[1, 0], [0, 0], [0, 1], [0, 0]], dtype=np.float32))

        def receptors(self):
            return ReceptorMap(np.array([1, 1, 0, 0], dtype=np.float32),
                               np.zeros(4, dtype=np.float32), np.zeros(4, dtype=np.float32), "t")

    pop = da_exposed(Registry())
    assert pop.name == "DA_exposed"
    np.testing.assert_array_equal(pop.idx, np.array([0], dtype=np.int32))
    assert pop.count == 1


def _run_in_child(code: str) -> None:
    """Run engine-building code in a child interpreter.

    test_registry asserts the engine is never imported in this process, so
    in-process engine builds would fail it (test_engine does the same).
    """
    import subprocess
    import sys

    from pathlib import Path

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1])
    assert result.returncode == 0, result.stdout + result.stderr


def _check_0_10_engine_leg() -> None:
    """Child body of the 0.10-engine test."""
    from flyonenomics.validation.level0_rest import run_0_10_engine, test_0_10_engine as suite_0_10

    measured = run_0_10_engine()
    assert measured["passed"]
    entry = suite_0_10()
    assert entry.test_id == "0.10-engine"
    assert entry.outcome == "passed"


@pytest.mark.slow
def test_0_10_engine_leg() -> None:
    """783 engine weights equal _base_w_mv × scale after store/restore."""
    _run_in_child("import sys; sys.path.insert(0, 'tests'); "
                  "from test_p2_rest import _check_0_10_engine_leg as check; check()")



def test_settle_rule_dispatch_drive_groups_and_da_gap() -> None:
    """Section 2.4 only for 1.3 with background; drive groups are candidates; gap uses S_c × f."""
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.neuromod.pools import fixed_point
    from flyonenomics.types import LayerFlags, params_path_for_version
    from flyonenomics.validation.level0_rest import _Engine, _Pop, _Registry, rule_dispatch

    assert rule_dispatch()["passed"]
    params = load_params(params_path_for_version("v0.2"))
    groups = {"central": np.array([2, 3], dtype=np.int32)}
    mod = Neuromod(_Registry(), params, LayerFlags(), schema_version="1.3", drive_groups=groups)
    mod.reset_fast()
    record = mod.settle(_Engine(), lambda: None, [_Pop(np.array([0, 1], dtype=np.int32), "tiny")])
    assert record.unresolved == ["tiny", "group:central"]
    assert record.da_gap_um == []
    mod.silenced[:] = [True, False, False, False]
    measured = np.array([3.0, 5.0])
    mean_da = np.array([0.4, 0.6])
    vmax, km, rel = mod._kinetics()
    expected = mean_da - fixed_point(rel * (mod.alpha * measured + mod.s_c * mod._retained_dan_fraction()), vmax, km, mod.k_ns)
    np.testing.assert_array_equal(mod.da_gap(mean_da, measured), expected)
    phase1 = Neuromod(_Registry(), load_params(), LayerFlags(), schema_version="1.2")
    phase1.reset_fast()
    assert phase1.settle(_Engine(), lambda: None, [_Pop(np.array([0, 1], dtype=np.int32), "tiny")]).unresolved is None


def test_ambient_blocks_have_no_bar_and_dark_blocks_are_unlit() -> None:
    """Ambient is the bright wall with no bar; dark sets lit False; stripes still draw."""
    from types import SimpleNamespace

    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.schema.experiment import Probe

    class Reg:
        def population(self, name: str):
            if name == "TuBu":
                return SimpleNamespace(idx=np.array([0, 1], dtype=np.int32), root_ids=np.array([11, 12], dtype=np.int64),
                                       side=np.array(["left", "right"]))
            return SimpleNamespace(idx=np.array([2 if name.endswith("_L") else 3], dtype=np.int32))

    probe = Probe.model_validate({
        "type": "probe", "assay": "open_loop_steering", "duration_s": 6, "label": "o",
        "params": {"inject_at": "TuBu", "blocks": [
            {"stimulus": "ambient", "transition_s": 1, "dwell_s": 1},
            {"stimulus": "dark", "transition_s": 1, "dwell_s": 1},
            {"stimulus": "stripe", "azimuth_deg": 45, "transition_s": 1, "dwell_s": 1}]},
    })
    plan = SimpleNamespace(topology=SimpleNamespace(extended_idx=np.array([0, 1], dtype=np.int32)))
    arena = Behaviour(plan, Reg(), load_params(), probe, v_fwd=10, sign_steer=1, K_steer=1, r_vis_max=100, sigma_vis=20)
    arena.reset(np.random.default_rng(1))
    seen = []
    for t in (0.5, 2.5, 4.5, 6.5):
        arena.rates(arena.view(), t)
        seen.append((arena.lit(), [item["name"] for item in arena._stimuli()]))
    assert seen == [(True, []), (False, []), (True, ["A"]), (True, ["A"])]
    np.testing.assert_array_equal(arena.rates(arena.view(), 0.5), np.zeros(2))


def test_spontaneous_ambient_drives_r16_at_r_light() -> None:
    """A spontaneous ambient probe writes min(vis.r_max, r_light) to every R1_6 neuron, or refuses."""
    from types import SimpleNamespace

    from flyonenomics.orchestrator.phases import TopologyPlan, probe_inputs
    from flyonenomics.schema.experiment import Arm, Probe

    registry = SimpleNamespace(n=5, population=lambda name: SimpleNamespace(idx=np.array([1, 3], dtype=np.int32)))
    topology = SimpleNamespace(extended_idx=np.array([1, 3], dtype=np.int32), upstream_banks=[])
    probe = Probe.model_validate({"type": "probe", "assay": "spontaneous", "duration_s": 0.01, "label": "a",
                                  "params": {"stimulus": "ambient"}})
    arm = Arm.model_validate({"label": "wild-type", "protocol": [probe.model_dump()]})
    params = load_params()
    plan = TopologyPlan(topology, [], None, SimpleNamespace(r_light=120.0), params)
    _active, rates, _overlap = probe_inputs(plan, probe, arm, registry)
    np.testing.assert_array_equal(rates, [120.0, 120.0])
    plan = TopologyPlan(topology, [], None, SimpleNamespace(r_light=None), params)
    with pytest.raises(ValueError, match="r_light"):
        probe_inputs(plan, probe, arm, registry)


def _check_0_14_engine_twins() -> None:
    """Child body of the 0.14 engine test."""
    from flyonenomics.validation.level0_rest import test_0_14 as suite_0_14

    entry = suite_0_14()
    assert entry.test_id == "0.14"
    assert entry.outcome == "passed", entry.measured


@pytest.mark.slow
def test_0_14_engine_twins_bitwise() -> None:
    """Both twins run through the orchestrator with identical tables, metrics and settle files."""
    _run_in_child("import sys; sys.path.insert(0, 'tests'); "
                  "from test_p2_rest import _check_0_14_engine_twins as check; check()")


def test_runner_rest_identity_and_qualification(tmp_path, monkeypatch) -> None:
    """v0.2 pins ask qualification_of with the run identity; v0.1 keeps its flag; scales-only is not bare."""
    import json

    import flyonenomics.orchestrator.runner as runner
    import flyonenomics.validation.binding as binding
    from flyonenomics.schema.experiment import Experiment

    raw = json.loads((runner.REPO / "tests/fixtures/experiments/bare-twin-1.3.json").read_text())
    bare = Experiment.model_validate(raw)
    assert runner.substrate_id_of(bare) == "bare" and not runner.rest_drive_applied(bare)
    ff = Experiment.model_validate({**raw, "substrate": {**raw["substrate"], "drive_version": "v0.2"},
                                    "apply_scales_without_background": True})
    assert runner.rest_drive_applied(ff)
    assert runner.pinned_drive_ratio(ff) == 1.0
    (tmp_path / "data").mkdir()
    (tmp_path / "data/drive-v0.2.yaml").write_text("x: 1\n")
    assert runner.substrate_id_of(ff, root=tmp_path) == "rest:" + binding.sha256_file(tmp_path / "data/drive-v0.2.yaml")[:16]
    with pytest.raises(RuntimeError, match="missing pin"):
        runner.substrate_id_of(ff, root=tmp_path / "absent")
    assert runner._qualified("dopamine", "v0.1", {"qualified": True}, None) == (True, None)
    seen = {}

    def fake(component, run, *, results, repo):
        seen.update(component=component, run=run, repo=repo)
        return False, {"3.1br": "missing"}

    monkeypatch.setattr(binding, "qualification_of", fake)
    assert runner._qualified("drive", "v0.2", {"qualified": True}, "identity") == (False, {"3.1br": "missing"})
    assert seen == {"component": "rest substrate", "run": "identity", "repo": runner.REPO}
