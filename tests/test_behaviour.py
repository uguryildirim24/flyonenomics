"""Engine-free WP6 metric, encoder, arena, and archive checks."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from flyonenomics.behaviour.arena import Behaviour, stripe_view
from flyonenomics.behaviour import make_behaviour
from flyonenomics.behaviour.brembs import load_reference, split, verify_4_0b
from flyonenomics.behaviour.buridan import OPEN_LOOP_AZIMUTHS, calibration_target, choose_sign, steering_curve
from flyonenomics.behaviour.encoder import VisualEncoder, preferred_azimuths
from flyonenomics.behaviour.metrics import Geometry, mindistkeep3, score, score_unit
from flyonenomics.orchestrator.phases import build_topology
from flyonenomics.schema.experiment import Probe
from flyonenomics.schema import load_experiment
from flyonenomics.types import load_params


def trajectory(t: np.ndarray, x: np.ndarray, y: np.ndarray, segment: np.ndarray | None = None) -> pd.DataFrame:
    return pd.DataFrame({"t_s": t, "x_mm": x, "y_mm": y,
                         "segment": np.zeros(len(t), dtype=int) if segment is None else segment})


def geometry() -> Geometry:
    return Geometry.from_params(load_params())


def test_4_0_straight_walk() -> None:
    t = np.arange(0, 10.05, 0.05)
    result = score(trajectory(t, np.zeros(len(t)), -50 + 10 * t), geometry())
    assert result["stripe_deviation_deg"] == pytest.approx(0)
    assert result["fixation_index"] == pytest.approx(1)
    assert result["walks"] == 1
    assert result["activity"] == 1


def test_4_0_circular_walk() -> None:
    t = np.arange(0, 20.05, 0.05)
    angle = 5 * t
    result = score(trajectory(t, 2 * np.sin(angle), 2 * np.cos(angle)), geometry())
    assert result["stripe_deviation_deg"] == pytest.approx(45, abs=2)
    assert result["fixation_index"] == pytest.approx(1 / 3, abs=0.03)
    assert result["walks"] == 0


def test_4_0_split_gap_and_return() -> None:
    first_t = np.arange(0, 5.05, 0.05)
    second_t = np.arange(6, 11.05, 0.05)
    t = np.r_[first_t, second_t]
    y = np.r_[-50 + 10 * first_t, 10 * (second_t - 6)]
    segments = np.r_[np.zeros(len(first_t), dtype=int), np.ones(len(second_t), dtype=int)]
    result = score(trajectory(t, np.zeros(len(t)), y, segments), geometry(), mode="full")
    assert result["angular_denominator"] == 98
    # First segment ends in B; second starts in A, then returns to B.
    left = trajectory(np.array([0., .1, .2]), np.zeros(3), np.array([-49., -50., -50.]))
    right = trajectory(np.arange(1., 11.1, .1), np.zeros(101), np.linspace(50, -50, 101),
                       np.ones(101, dtype=int))
    both = pd.concat([left, right], ignore_index=True)
    assert score(both, geometry(), mode="full")["walks"] == 1


def test_4_0_freeze_and_stationary() -> None:
    points = np.array([[0., 0.], [100., 0.], [101., 0.], [0., 0.]])
    assert mindistkeep3(points, .8, 70)[:, 0].tolist() == [0, 0, 101, 101]
    drift = np.column_stack([np.arange(5) * .5, np.zeros(5)])
    assert mindistkeep3(drift, .8, 70)[:, 0].tolist() == [0, 0, 1, 1, 2]
    still = trajectory(np.arange(0, 2.1, .1), np.zeros(21), np.zeros(21))
    result = score(still, geometry(), mode="full")
    assert result["activity"] == 0
    assert result["stripe_deviation_deg"] is None
    assert result["angular_denominator"] == result["walks"] == 0
    windowed = score(still, geometry())
    assert windowed["activity"] == 0
    assert windowed["stripe_deviation_deg"] is None
    assert windowed["angular_denominator"] == windowed["walks"] == 0


def test_window_median_and_fraction() -> None:
    t = np.arange(0, 40, .05)
    x = np.zeros(len(t))
    y = np.where(t < 20, -50 + 5 * t, 50.)
    result = score(trajectory(t, x, y), geometry())
    assert result["total_windows"] == 2
    assert result["valid_windows"] == 1
    assert result["fixation_index"] == 1


def test_distractor_switch_valid_and_invalid_denominators() -> None:
    t = np.arange(0, 1.1, .1)
    x = np.r_[np.zeros(6), np.arange(1, 6)]
    y = np.r_[np.arange(6), np.full(5, 5)]
    sampled = trajectory(t, x, y)
    episode = pd.DataFrame({"onset_s": [0.], "azimuth_deg": [90.]})
    switched = score_unit(sampled, geometry(), episodes=episode)
    assert switched["switches"] == switched["valid_switch_windows"] == 1
    assert switched["invalid_switch_windows"] == 0
    assert switched["switch_rate"] == 1
    still = sampled.assign(x_mm=0., y_mm=0.)
    invalid = score_unit(still, geometry(), episodes=episode)
    assert invalid["valid_switch_windows"] == 0
    assert invalid["invalid_switch_windows"] == 1
    assert invalid["switch_rate"] is None


def test_4_0b_pinned_reference() -> None:
    flies, excluded = load_reference()
    assert len(flies) == 128
    partition = split(flies)
    assert len(partition["calibration"]) == len(partition["holdout"]) == 64
    # The pinned XML has two published IDs pointing to one raw file.
    assert {"197_CS_BvS", "202_CS_BvS"} <= set(partition["calibration"])
    result = verify_4_0b(flies)
    assert result["passed"]
    assert result["selected_step_min_mm"] == .8
    assert result["candidates"]["0.8"]["joint_matches"] == 128
    assert result["candidates"]["0.6"]["joint_matches"] == 120


class FakeRegistry:
    def __init__(self) -> None:
        self.entries = {
            "TuBu": SimpleNamespace(idx=np.array([0, 1], dtype=np.int32),
                                    root_ids=np.array([11, 12], dtype=np.int64), side=np.array(["left", "right"])),
            "steering_L": SimpleNamespace(idx=np.array([2], dtype=np.int32)),
            "steering_R": SimpleNamespace(idx=np.array([3], dtype=np.int32)),
            "ER": SimpleNamespace(idx=np.array([4], dtype=np.int32),
                                  root_ids=np.array([13], dtype=np.int64), side=np.array(["center"])),
        }

    def population(self, name: str) -> SimpleNamespace:
        return self.entries[name]


def fake_arena(assay: str = "buridan", params: dict | None = None, *, speed: float = 10) -> Behaviour:
    probe = Probe.model_validate({"type": "probe", "assay": assay, "duration_s": 33 if assay == "open_loop_steering" else 20,
                                  "label": "test", "params": params or {}})
    plan = SimpleNamespace(topology=SimpleNamespace(extended_idx=np.array([0, 1], dtype=np.int32)))
    arena = Behaviour(plan, FakeRegistry(), load_params(), probe, v_fwd=speed, sign_steer=1,
                      K_steer=4, r_vis_max=100, sigma_vis=20)
    arena.reset(np.random.default_rng(3))
    return arena


def test_encoder_cap_and_distractor_duty() -> None:
    arena = fake_arena(params={"distractor": {"azimuth": 90, "flicker_hz": 2, "contrast": 1,
                                               "onset_s": 1, "duration_s": 1}})
    arena.encoder.preferred[:] = 0
    one = arena.encoder.rates([{"az_fly": 0., "contrast": 1.}])
    assert one[0] == 100
    two = arena.encoder.rates([{"az_fly": 0., "contrast": 1.}, {"az_fly": 180., "contrast": 1.}])
    assert two[0] == 100
    arena.t_s = 1.1
    assert arena.state()["contrast_distractor"] == 1
    arena.t_s = 1.3
    assert arena.state()["contrast_distractor"] == 0
    arena.t_s = 1.6
    assert arena.state()["contrast_distractor"] == 1


def test_encoder_gaussian_relative_heading_and_invalid_populations() -> None:
    encoder = fake_arena().encoder
    encoder.preferred[:] = 0
    assert encoder.rates([{"az_fly": 20., "contrast": .5}])[0] == pytest.approx(50 * np.exp(-.5))
    assert np.all(encoder.rates([{"az_fly": 0., "contrast": -1}]) == 0)
    assert np.all(encoder.rates([{"az_fly": 0., "contrast": 1}], enabled=False) == 0)
    assert stripe_view(np.zeros(2), 40, 10, 5, 146.5, 1, "A")["az_fly"] == -30
    reg = FakeRegistry()
    with pytest.raises(ValueError, match="absent from extended"):
        VisualEncoder(reg, np.array([], dtype=np.int32), load_params(), "TuBu")
    reg.entries["TuBu"].idx = np.array([], dtype=np.int32)
    with pytest.raises(ValueError, match="population is empty"):
        VisualEncoder(reg, np.array([], dtype=np.int32), load_params(), "TuBu")


def test_chunk_stimulus_matches_input_at_transition_boundary() -> None:
    arena = fake_arena("open_loop_steering")
    arena.rates(arena.view(), 2.99)
    arena.step(np.zeros(4, dtype=np.int32), .01)
    assert arena.state()["az_fly_A"] == -150
    arena.rates(arena.view(), 3.0)
    arena.step(np.zeros(4, dtype=np.int32), .01)
    assert arena.state()["az_fly_A"] == pytest.approx(-120)


def test_known_turn_in_degrees_without_noise() -> None:
    arena = fake_arena(speed=10)
    arena.stream = SimpleNamespace(normal=lambda: 0.)
    dt = load_params().get("engine.chunk_ms") / 1000
    arena.step(np.array([0, 0, 0, 1], dtype=np.int32), dt)
    rate = (1 - np.exp(-dt / .05)) / dt
    heading = 4 * rate * dt
    assert arena.h == pytest.approx(heading)
    assert arena.x == pytest.approx(10 * dt * np.sin(np.deg2rad(heading)))
    assert arena.y == pytest.approx(10 * dt * np.cos(np.deg2rad(heading)))


def test_arena_sign_filter_edge_and_reset() -> None:
    arena = fake_arena(speed=0)
    assert arena.state()["x"] == arena.state()["y"] == arena.state()["h"] == 0
    counts = np.array([0, 0, 0, 1], dtype=np.int32)
    arena.step(counts, .05)
    assert arena.r_R == pytest.approx((1 - np.exp(-1)) * 20)
    assert arena.omega > 0
    arena = fake_arena(speed=100)
    class Draws:
        n = 0
        def normal(self) -> float:
            self.n += 1
            return 0.
    draws = Draws()
    arena.stream = draws
    arena.y = 53
    arena.step(np.zeros(4, dtype=np.int32), .01)
    assert draws.n == 2  # heading noise and exactly one edge draw
    assert np.hypot(arena.x, arena.y) == pytest.approx(53.5)
    assert arena.h == 180


def test_open_loop_schedule() -> None:
    arena = fake_arena("open_loop_steering")
    azimuths = load_params().get("openloop.azimuths")
    for index, azimuth in enumerate(azimuths):
        arena.t_s = index * 3
        assert arena.state()["az_fly_A"] == pytest.approx(azimuth)
        arena.t_s += 1
        assert arena.state()["az_fly_A"] == pytest.approx(azimuth)
    arena.step(np.zeros(4, dtype=np.int32), .01)
    assert (arena.x, arena.y, arena.h) == (0, 0, 0)


def test_preferred_grid_permutation_and_wall_geometry() -> None:
    roots = np.array([50, 10, 40, 20], dtype=np.int64)
    sides = np.array(["left", "left", "right", "right"])
    preferred = preferred_azimuths(roots, sides, (0, 150))
    assert preferred.tolist() == [-150, -0., 150, 0.]
    reg = FakeRegistry()
    plan_idx = np.array([0, 1], dtype=np.int32)
    encoder = VisualEncoder(reg, plan_idx, load_params(), "TuBu")
    encoder.stream = np.random.default_rng(13)
    encoder.permutation(1)
    first = encoder.preferred.copy()
    encoder.permutation(0)
    encoder.permutation(1)
    assert np.array_equal(encoder.preferred, first)
    centre = stripe_view(np.zeros(2), 0, 0, 5, 146.5, 1, "A")
    offset = stripe_view(np.array([20., 0.]), 0, 0, 5, 146.5, 1, "A")
    assert centre["width"] == pytest.approx(5)
    assert offset["width"] != pytest.approx(5)


def test_steering_curve_dwell_excludes_transition(tmp_path) -> None:
    root = tmp_path / "arm-wild-type" / "seed-1"
    root.mkdir(parents=True)
    t = np.arange(0, 33, .1)
    az_index = np.floor(t / 3).astype(int)
    dwell = (t % 3) >= 1
    az = np.asarray(OPEN_LOOP_AZIMUTHS)[az_index]
    pd.DataFrame({"t_ms": t * 1000, "r_L": np.zeros(len(t)),
                  "r_R": np.where(dwell, az, 1000),
                  "omega": np.where(dwell, 4 * az, 4000)}).to_parquet(root / "probe-0-arena.parquet")
    curve = steering_curve(tmp_path)
    assert len(curve) == 11
    assert curve[0]["rate_difference_hz"] == pytest.approx(-150)
    assert curve[-1]["omega_deg_s"] == pytest.approx(600)
    assert choose_sign(curve)["sign_steer"] == 1
    assert choose_sign([{**row, "omega_deg_s": -row["omega_deg_s"]} for row in curve])["sign_steer"] == -1
    assert choose_sign([{**row, "omega_deg_s": 0} for row in curve])["status"] == "flat (provisional)"


def test_calibration_half_has_defined_denominators() -> None:
    target = calibration_target()
    assert target["fixation_index_defined_flies"] == 61
    assert target["stripe_deviation_deg_defined_flies"] == 61
    assert target["fixation_index_iqr"] > 0


def _assert_topology_injection_and_factory() -> None:
    from pathlib import Path
    import json
    registry = FakeRegistry()
    experiment = load_experiment(Path("data/experiments/open-loop-steering.json"))
    plan = build_topology(experiment, registry)
    assert plan.topology.extended_idx.tolist() == [0, 1]
    probe = experiment.arms[0].protocol[0]
    arena = make_behaviour(plan, registry, load_params(), probe)
    assert isinstance(arena, Behaviour)
    assert arena.v_fwd == pytest.approx(json.loads(Path("data/brembs-metrics.json").read_text())["v_fwd_mm_s"])
    arena.reset(np.random.default_rng(1))
    for _ in range(3):
        arena.rates(arena.view(), 0)
    assert (arena.x, arena.y, arena.h) == (0, 0, 0)

    buridan = load_experiment(Path("data/experiments/controls-encoder-off.json"))
    data = buridan.model_dump(mode="json")
    data["arms"][0]["protocol"][0]["params"]["inject_at"] = "ER"
    er_experiment = type(buridan).model_validate(data)
    er_plan = build_topology(er_experiment, registry)
    assert er_plan.topology.extended_idx.tolist() == [4]
    er_arena = make_behaviour(er_plan, registry, load_params(), er_experiment.arms[0].protocol[0])
    assert isinstance(er_arena, Behaviour)
    assert er_arena.encoder.population == "ER"

    # Execute the pre-WP6 function from the pinned base to compare topology,
    # including bank contents, rather than only checking an expected length.
    import subprocess
    from types import ModuleType
    import sys
    legacy = ModuleType("_wp6_legacy_phases")
    sys.modules[legacy.__name__] = legacy
    try:
        code = subprocess.check_output(["git", "show", "7806261:src/flyonenomics/orchestrator/phases.py"], text=True)
        exec(compile(code, "7806261:phases.py", "exec"), legacy.__dict__)
        registry.entries["sugar_GRN_R"] = registry.entries["TuBu"]
        for filename in ("sugar-reflex.json", "spontaneous.json"):
            experiment = load_experiment(Path("data/experiments") / filename)
            before, after = legacy.build_topology(experiment, registry), build_topology(experiment, registry)
            np.testing.assert_array_equal(before.topology.extended_idx, after.topology.extended_idx)
            assert before.bank_keys == after.bank_keys
            assert after.behaviour_settings is None
            for a, b in zip(before.topology.upstream_banks, after.topology.upstream_banks, strict=True):
                np.testing.assert_array_equal(a.idx, b.idx)
                assert a.rate_hz == b.rate_hz
    finally:
        sys.modules.pop(legacy.__name__, None)


def test_pinned_settings_never_read_holdout_or_ambient_overrides(monkeypatch, tmp_path) -> None:
    from pathlib import Path
    import flyonenomics.behaviour as package
    (tmp_path / "data").mkdir()
    (tmp_path / "data/behaviour-test.yaml").write_text("v_fwd_mm_s: 12\nsign_steer: -1\nselected:\n  K_steer: 8\n")
    monkeypatch.setattr(package, "ROOT", tmp_path)
    monkeypatch.setenv("FLYONENOMICS_BEHAVIOUR_OVERRIDE", '{"K_steer": 999}')
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        assert path.name != "brembs-metrics.json"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded)
    settings = package.load_settings("test", load_params())
    assert settings["v_fwd"] == 12 and settings["K_steer"] == 8 and settings["sign_steer"] == -1
    with pytest.raises(ValueError, match="missing pin behaviour-v0.1.yaml"):
        package.load_settings("v0.1", load_params())
    with pytest.raises(ValueError, match="require behaviour_version=dev"):
        package.load_settings("test", load_params(), {"K_steer": 2})


def test_worker_factory_falls_back_only_for_absent_package(monkeypatch) -> None:
    from flyonenomics.orchestrator import workers
    from flyonenomics.orchestrator.stubs import IdentityBehaviour
    def absent(name):
        raise ModuleNotFoundError(name=name)
    from flyonenomics.orchestrator import components
    monkeypatch.setattr(components.importlib, "import_module", absent)
    plan = SimpleNamespace(topology=SimpleNamespace(extended_idx=np.array([0, 1])))
    assert isinstance(workers.make_behaviour(plan, None, load_params(), fake_arena().probe), IdentityBehaviour)
    def broken(name):
        raise ModuleNotFoundError(name="missing_dependency")
    monkeypatch.setattr(components.importlib, "import_module", broken)
    with pytest.raises(ModuleNotFoundError):
        workers.make_behaviour(plan, None, load_params(), fake_arena().probe)


def test_level4_procedure_cannot_satisfy_final_sign_or_fixation() -> None:
    from flyonenomics.validation import level4
    assert level4.procedure_4_1().test_id == "4.1-procedure"
    measured = level4.final_4_1()
    assert measured.compatibility == "matching-layers" and measured.outcome == "failed"
    assert measured.measured["flat"] and measured.measured["seeds"] == [1, 2, 3]
    assert level4.final_4_2().outcome == "unavailable"
    holdout = level4.final_4_3()
    assert holdout.outcome == "unavailable" and holdout.measured["holdout_sealed"]
    assert not measured.identity.layer_flags["background"]
    for entry in (level4.provisional_4_2(), level4.provisional_4_8()):
        assert entry.compatibility == "development"
        assert not entry.identity.layer_flags["background"]


def test_arena_metrics_include_episode_without_recording_arena() -> None:
    arena = fake_arena(params={"distractor": {"azimuth": 90, "flicker_hz": 2, "contrast": 1,
                                               "onset_s": 0, "duration_s": 1}})
    t = np.arange(0, 1.2, .05)
    arena.trajectory = trajectory(t, np.where(t < .5, 0, 10 * (t - .5)),
                                  np.minimum(t, .5) * 10).to_dict("records")
    result = arena.metrics()
    assert result["switches"] == result["valid_switch_windows"] == 1
    assert result["switch_rate"] == 1
    arena.reset(np.random.default_rng(3))
    assert arena.metrics()["angular_denominator"] == 0


def test_reference_sources_are_verified_before_archive(monkeypatch) -> None:
    import flyonenomics.behaviour.brembs as module
    checked = []
    def verify(path, record):
        checked.append(record.item)
        if record.item == module.CETRAN_ITEMS[-1]:
            raise ValueError("checksum mismatch")
    monkeypatch.setattr(module, "verify_file", verify)
    monkeypatch.setattr(module, "archive_path", lambda: pytest.fail("archive opened before source verification"))
    with pytest.raises(ValueError, match="checksum mismatch"):
        module.load_reference()
    assert checked == list(module.CETRAN_ITEMS)


def test_published_fly_100_from_its_pinned_raw_trajectory() -> None:
    flies, _ = load_reference()
    meta, table = next((m, t) for m, t in flies if m["id"] == "100_CSJC")
    result = score(table, geometry(), mode="full", step_min_mm=.8)
    assert meta["dat"].endswith("/CSJC_A1.dat")
    assert meta["published_stripe_deviation_deg"] == pytest.approx(13.1313398096326)
    assert result["stripe_deviation_deg"] == pytest.approx(meta["published_stripe_deviation_deg"], abs=2)
    assert result["walks"] == meta["published_walks"] == 13
    assert result["angular_denominator"] == 1065


def test_acceptance_resolves_on_bare_substrate_and_requires_only_behaviour_pin(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    import json
    from flyonenomics.server.mcp_server import validate_experiment
    from flyonenomics.orchestrator import run
    import flyonenomics.orchestrator.runner as runner
    from flyonenomics.store import ResultsStore
    path = Path("data/experiments/acceptance-wt-mph-buridan-distractor.json")
    result = validate_experiment(json.loads(path.read_text()))
    assert result["ok"], result
    experiment = load_experiment(path)
    assert not experiment.layers.background
    assert runner.background_weights(None, experiment) is None
    monkeypatch.setattr(runner, "REPO", tmp_path)
    with pytest.raises(ValueError) as error:
        run(experiment, ResultsStore(tmp_path), 1)
    assert "behaviour-v0.1.yaml" in str(error.value)
    assert "drive-v0.1.yaml" not in str(error.value)
    assert not list(tmp_path.glob("*/status.json"))


def test_sign_check_uses_recorded_sign_without_toggling(tmp_path, monkeypatch) -> None:
    import json
    import flyonenomics.behaviour.buridan as module
    (tmp_path / "status.json").write_text('{"state": "done"}')
    (tmp_path / "manifest.json").write_text('{"behaviour_settings": {"sign_steer": -1}}')
    for seed in module.SIGN_SEEDS:
        (tmp_path / "arm-wild-type" / f"seed-{seed}").mkdir(parents=True)
    monkeypatch.setattr(module, "steering_curve", lambda path: [
        {"azimuth_deg": az, "omega_deg_s": az} for az in module.OPEN_LOOP_AZIMUTHS])
    monkeypatch.setattr(module, "_read_development", lambda: {})
    saved = []
    monkeypatch.setattr(module, "_write_development", saved.append)
    assert module.sign_check(tmp_path)["sign_steer"] == -1
    assert module.sign_check(tmp_path)["sign_steer"] == -1


def test_cetran_walk_mask_survives_reentry_into_same_area() -> None:
    from flyonenomics.behaviour.metrics import _walks
    points = np.column_stack([np.zeros(4), [-50., 0., -50., 50.]])
    assert _walks(points, geometry(), load_params().get("metrics.walk_area_fraction")) == 1


def test_k3_tie_uses_earliest_candidate_and_calibration_half_only(monkeypatch, tmp_path) -> None:
    import flyonenomics.behaviour.buridan as module
    progress = {"sign_result": {"flat": False, "sign_steer": 1, "selected_r_vis_max_hz": 100}}
    monkeypatch.setattr(module, "_progress", lambda: progress)
    monkeypatch.setattr(module, "_save_progress", lambda value: None)
    target = {"fixation_index_median": .7, "fixation_index_iqr": .3,
              "stripe_deviation_deg_median": 20., "stripe_deviation_deg_iqr": 10.}
    monkeypatch.setattr(module, "calibration_target", lambda: target)
    seen = []
    def construct(source, name, seeds, override):
        seen.append(override)
        assert source == "controls-encoder-off.json" and seeds == module.FINAL_SEEDS
        return override
    def execute(experiment):
        return tmp_path
    monkeypatch.setattr(module, "_final_experiment", construct)
    monkeypatch.setattr(module, "_run_final", execute)
    monkeypatch.setattr(module, "model_probe_metrics", lambda path: [
        {"metrics": {"fixation_index": .7, "stripe_deviation_deg": 20.}} for _ in module.FINAL_SEEDS])
    frozen = []
    monkeypatch.setattr(module, "_freeze_final", lambda sign, selected, table: frozen.append((selected, table)))
    result = module.final_k3()
    assert len(seen) == len(frozen[0][1]) == 48
    assert result["winner"]["objective"] == 0
    assert frozen[0][0] == result["winner"]
    assert {key: result["winner"][key] for key in ("K_steer", "r_vis_max", "sigma_vis")} == {
        "K_steer": 1, "r_vis_max": 40, "sigma_vis": 15}


def test_final_sign_and_k3_replay_frozen_record_without_progress(monkeypatch, tmp_path) -> None:
    """A clean checkout has no lane progress file; the frozen fallback replays, no engine runs."""
    import flyonenomics.behaviour.buridan as module
    monkeypatch.setattr(module, "PROGRESS", tmp_path / "absent.json")
    def refuse(*args, **kwargs):
        raise AssertionError("a frozen calibration must not start an engine")
    monkeypatch.setattr(module, "_run_final", refuse)
    monkeypatch.setattr(module, "_freeze_final", refuse)
    frozen = module._frozen_sign_check()
    assert frozen is not None and frozen["flat"] is True
    assert [row["r_vis_max_hz"] for row in frozen["attempts"]] == [100, 140, 280]
    sign = module.final_sign_check()
    assert sign["status"] == "recorded" and sign["attempts"] == frozen["attempts"]
    k3 = module.final_k3()
    assert k3["outcome"] == "unavailable" and k3["candidates"] == 0
    assert not (tmp_path / "absent.json").exists()


def test_saved_probe_analysis_reads_its_distractor_episode(tmp_path) -> None:
    import json
    from pathlib import Path
    from flyonenomics.behaviour.buridan import model_probe_metrics
    source = load_experiment(Path("data/experiments/controls-encoder-off.json"))
    document = source.model_dump(mode="json")
    document["arms"][0]["protocol"][0]["params"]["distractor"] = {
        "azimuth": 90, "flicker_hz": 2, "contrast": 1, "onset_s": 0, "duration_s": 1}
    (tmp_path / "experiment.json").write_text(json.dumps(document))
    directory = tmp_path / f"arm-{document['arms'][0]['label']}" / "seed-1"
    directory.mkdir(parents=True)
    t = np.arange(0, 1.2, .05)
    pd.DataFrame({"t_ms": t * 1000, "x": np.where(t < .5, 0, 10 * (t - .5)),
                  "y": np.minimum(t, .5) * 10}).to_parquet(directory / "probe-0-arena.parquet")
    result = model_probe_metrics(tmp_path)[0]["metrics"]
    assert result["switches"] == result["valid_switch_windows"] == 1


def test_topology_injection_and_factory() -> None:
    """Keep InputTopology's package import out of the parent registry tests; no network is built."""
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'tests'); "
                             "from test_behaviour import _assert_topology_injection_and_factory as check; check()"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
