"""WP20 steering metrics, evaluators, visual status and fixtures. No engine."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from flyonenomics.behaviour import buridan as buridan_module
from flyonenomics.behaviour.buridan import (
    K3R_K_STEER,
    P2_STAGE,
    SIGN_CHECK_AZIMUTHS,
    VT_CAL_RATES_HZ,
    _p2_experiment,
    _p2_run_context,
    behaviour_step_min_mm,
    bias_from_run,
    choose_k3r,
    choose_sign_from_gains,
    evaluate_4_1r,
    evaluate_4_2r,
    evaluate_vtcal,
    k3r_finalists,
    k3r_objective,
    k3r_row,
    load_buridan_controls,
    measure_bias,
    open_loop_blocks,
    p2_missing_dependencies,
    sign_from_run,
    steer_gains_from_run,
)
from flyonenomics.behaviour.metrics import (
    Geometry,
    bias_corrected_delta,
    distractor_capture_hz,
    fixation_retention,
    interval_excludes_zero,
    score,
    steer_gain,
)
from flyonenomics.behaviour.visual_calibration import (
    declared_drive_present,
    declared_substrate,
    declared_substrate_id,
)
from flyonenomics.behaviour.visual_status import decide_visual_status, record_template
from flyonenomics.schema import load_experiment
from flyonenomics.types import load_params
from flyonenomics.drive.rest import resolve_configurations
from flyonenomics.validation import level4_p2
from flyonenomics.validation.execute import bind_entry, discover_suites

ROOT = Path(__file__).resolve().parents[1]


def trajectory(t: np.ndarray, x: np.ndarray, y: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({"t_s": t, "x_mm": x, "y_mm": y, "segment": np.zeros(len(t), dtype=int)})


def test_steer_gain_known_slope_and_bias_cancellation() -> None:
    """Slope is 0.1 Hz/deg and a constant bias does not change it."""
    azimuths = np.array([-60.0, -45.0, -30.0, 0.0, 30.0, 45.0, 60.0, 90.0, 150.0])
    delta = 0.1 * azimuths + 3.0
    assert steer_gain(azimuths, delta, bias_hz=3.0) == pytest.approx(0.1, abs=1e-12)
    with pytest.raises(ValueError, match="at least two"):
        steer_gain(np.array([90.0, 120.0]), np.array([1.0, 2.0]))


def test_fixation_retention_and_capture() -> None:
    """Retention is during FI minus pre FI. Capture subtracts bias once per block."""
    params = load_params()
    geometry = Geometry.from_params(params)
    t = np.arange(0, 15.05, 0.05)
    y = np.where(t < 5.0, -50 + 10 * t, 2.0 * np.cos(5 * (t - 5.0)))
    x = np.where(t < 5.0, 0.0, 2.0 * np.sin(5 * (t - 5.0)))
    result = fixation_retention(trajectory(t, x, y), geometry, params, onset_s=5.0, duration_s=10.0)
    assert result["pre_fixation_index"] == pytest.approx(1.0)
    assert result["during_fixation_index"] == pytest.approx(1 / 3, abs=0.05)
    assert result["fixation_retention"] == pytest.approx(
        result["during_fixation_index"] - result["pre_fixation_index"])
    assert distractor_capture_hz(1.5, 0.4, bias_hz=0.3) == pytest.approx(1.1)
    assert distractor_capture_hz(1.5, 0.4, bias_hz=9.0) == pytest.approx(1.1)
    assert bias_corrected_delta(5.0, 1.0, 2.0) == pytest.approx(2.0)


def test_behaviour_step_min_mm_reads_the_file_not_params() -> None:
    """Review r13 seam: scoring uses the behaviour file's step_min_mm."""
    experiment = SimpleNamespace(substrate=SimpleNamespace(behaviour_version="base-v0.2"))
    assert behaviour_step_min_mm(experiment) == pytest.approx(0.8)
    assert behaviour_step_min_mm(experiment, record={"step_min_mm": 0.6}) == pytest.approx(0.6)
    with pytest.raises(ValueError, match="step_min_mm"):
        behaviour_step_min_mm(experiment, record={})
    t = np.arange(0, 2.1, 0.05)
    still = trajectory(t, np.zeros(len(t)), np.zeros(len(t)))
    geometry = Geometry.from_params()
    loose = score(still, geometry, mode="full", step_min_mm=0.05)
    tight = score(still, geometry, mode="full", step_min_mm=0.8)
    assert loose["activity"] >= tight["activity"]


def test_sign_check_p2_positive_negative_and_flat() -> None:
    """+1 above zero, −1 below, flat when the interval includes zero."""
    rng = np.random.default_rng(0)
    plus = choose_sign_from_gains([0.05, 0.06, 0.07], rng, 400)
    assert plus["sign_steer"] == 1 and not plus["flat"]
    rng = np.random.default_rng(0)
    minus = choose_sign_from_gains([-0.05, -0.06, -0.07], rng, 400)
    assert minus["sign_steer"] == -1 and not minus["flat"]
    rng = np.random.default_rng(0)
    flat = choose_sign_from_gains([-0.02, 0.0, 0.02], rng, 400)
    assert flat["flat"]
    assert not interval_excludes_zero(flat["ci95"])


def test_k3r_objective_winner_and_lower_gain_tie() -> None:
    """Lowest objective wins; a tie takes the lower K_steer."""
    target = {"fixation_index_median": 0.5, "fixation_index_iqr": 0.2,
              "stripe_deviation_deg_median": 20.0, "stripe_deviation_deg_iqr": 5.0}
    same = k3r_objective(0.48, 21.0, target)
    table = [
        {"K_steer": 4.0, "objective": same},
        {"K_steer": 2.0, "objective": same},
        {"K_steer": 8.0, "objective": same + 1.0},
    ]
    winner = choose_k3r(table)
    assert winner["K_steer"] == 2.0
    assert [row["K_steer"] for row in k3r_finalists(table, 2)] == [2.0, 4.0]
    assert k3r_objective(None, 1.0, target) == float("inf")


def test_4_1r_and_4_2r_and_vtcal_on_constructed_tables() -> None:
    """Evaluators pass and fail on known constructed values."""
    rng = np.random.default_rng(1)
    passed = evaluate_4_1r([0.04] * 10, [1.0] * 10, [0.0] * 10, 1, rng, 200)
    assert passed["outcome"] == "passed"
    rng = np.random.default_rng(1)
    failed = evaluate_4_1r([0.0] * 10, [0.01] * 10, [0.0] * 10, 1, rng, 200)
    assert failed["outcome"] == "failed"
    on = {"fixation_index": [0.8] * 10, "stripe_deviation_deg": [10.0] * 10}
    off = {"fixation_index": [0.5] * 10, "stripe_deviation_deg": [30.0] * 10}
    enc = {"fixation_index": [0.4] * 10, "stripe_deviation_deg": [35.0] * 10}
    assert evaluate_4_2r(on, off, enc)["outcome"] == "passed"
    assert evaluate_4_2r(off, on, enc)["outcome"] == "failed"
    table = [
        {"r_vis_max_hz": 40.0, "mean_delta_steer_hz": 0.1, "delta_interval_excludes_zero": False,
         "central_input_carried": False, "steering_carried": False},
        {"r_vis_max_hz": 100.0, "mean_delta_steer_hz": 0.8, "delta_interval_excludes_zero": True,
         "central_input_carried": True, "steering_carried": True},
        {"r_vis_max_hz": 150.0, "mean_delta_steer_hz": 1.0, "delta_interval_excludes_zero": True,
         "central_input_carried": True, "steering_carried": True},
    ]
    chosen = evaluate_vtcal(table)
    assert chosen["status"] == "passed"
    assert chosen["selected_r_vis_max_hz"] == 100.0


def test_4_0c_and_suite_ids() -> None:
    """4.0c passes on constructed data. Every WP20 id is in the discovered suite."""
    entry = level4_p2.verify_4_0c()
    assert entry.outcome == "passed"
    assert entry.measured["heading_ok"]
    assert entry.measured["bias_once_ok"]
    assert entry.test_id == "4.0c"
    suites = discover_suites()
    for test_id in level4_p2.SUITE:
        assert test_id in suites
        result = suites[test_id]()
        assert result.test_id == test_id
        assert result.outcome in ("passed", "failed", "recorded", "unavailable", "not run")
    for test_id in ("4.4r", "4.5r", "4.6r", "4.7r",
                    "4.4r-T", "4.5r-T", "4.6r-T", "4.7r-T"):
        result = suites[test_id]()
        assert result.outcome == "not run"
        assert "SPEC-P2 item 144" in result.measured["reason"]
        assert result.fixture_path is None
        assert "constructed" not in result.measured


def test_p2_experiment_files_load() -> None:
    """The five owned experiment files validate as schema 1.3."""
    singles = ("bias", "signcheck", "k3r", "k3r-tubu")
    loaded = {name: load_experiment(ROOT / "data/experiments/p2" / f"{name}.json") for name in singles}
    assert loaded["bias"].substrate.behaviour_version == "base-v0.2"
    assert loaded["signcheck"].arms[0].protocol[0].duration_s == 39
    blocks = loaded["signcheck"].arms[0].protocol[0].params.blocks
    assert [block.azimuth_deg for block in blocks] == list(SIGN_CHECK_AZIMUTHS)
    assert loaded["k3r"].meta["k_grid"] is True
    assert loaded["k3r"].meta["grid"]["K_steer"] == list(K3R_K_STEER)
    assert loaded["k3r-tubu"].arms[0].protocol[0].params.inject_at == "TuBu"
    controls = load_buridan_controls()
    assert set(controls) == {"stripes_on", "stripes_off", "encoder_off"}
    assert controls["stripes_on"].arms[0].protocol[0].params.stripes is True
    assert controls["stripes_off"].arms[0].protocol[0].params.stripes is False
    assert controls["encoder_off"].arms[0].protocol[0].params.encoder == "off"
    assert all(exp.arms[0].protocol[0].params.initial_heading == "random" for exp in controls.values())
    assert tuple(VT_CAL_RATES_HZ) == (40.0, 70.0, 100.0, 150.0, 280.0)


def test_visual_status_state_machine() -> None:
    """Section 3.7: photoreceptor closed loop, step 1 wait, TuBu, then open loop."""
    passed = {"present": True, "status": "passed", "outcome": "passed", "flat": False,
              "selected_r_light_hz": 50.0}
    photo = {
        "vcal": {**passed, "kind": "vcal"},
        "v1": passed, "v3": passed, "sign": passed,
        "4.1r": passed, "4.2r": passed,
    }
    result = decide_visual_status(photo)
    assert result["status"] == "photoreceptor closed loop"
    assert result["step_reached"] == 0
    assert result["controller"] == "closed_loop"
    flat_sign = {**photo, "sign": {"present": True, "status": "flat", "flat": True, "outcome": "failed"}}
    waiting = decide_visual_status({**flat_sign, "next_r3_candidate": "closed-with-item-122"})
    assert waiting["status"] == "waiting" and waiting["step_reached"] == 2
    assert all("WP19" not in item for item in waiting["waiting_for"])
    tubu_ok = {name: passed for name in ("vtcal", "bias_t", "sign_t", "k3r_t", "4.1r_t", "4.2r_t")}
    tubu = decide_visual_status({**flat_sign, **tubu_ok})
    assert tubu["status"] == "TuBu closed loop"
    failed_tubu = {**flat_sign,
                   "vtcal": {"present": True, "status": "failed", "outcome": "failed", "flat": True},
                   "v3_rates": [{"v3_passed": True, "r_light_hz": 50.0, "mean_delta_steer_hz": 0.2},
                                {"v3_passed": True, "r_light_hz": 100.0, "mean_delta_steer_hz": -0.9}]}
    opened = decide_visual_status(failed_tubu)
    assert opened["status"] == "open loop"
    assert opened["open_loop_encoder"]["inject_at"] == "photoreceptors"
    assert opened["open_loop_encoder"]["r_light_hz"] == 100.0
    parked = decide_visual_status({"missing_dependencies": ["data/visual-v0.2.yaml", "data/dopamine-v0.2.yaml"]})
    assert parked["status"] == "waiting"
    assert "data/visual-v0.2.yaml" in parked["waiting_for"]
    template = record_template()
    assert template["status"] == "waiting"
    assert template["failures"] == []


def test_p2_stages_wait_only_on_real_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """P2 stages wait on item 122's real inputs, never on Q-rest or an engine."""
    missing_visual = tmp_path / "visual-v0.2.yaml"
    monkeypatch.setattr(buridan_module, "VISUAL_PATH", missing_visual)
    monkeypatch.setattr(buridan_module, "VISUAL_P2", missing_visual)
    missing = p2_missing_dependencies()
    assert "Q-rest" not in ", ".join(missing)
    assert "data/visual-v0.2.yaml" in missing
    assert ("data/dopamine-v0.2.yaml" in missing) == (not (ROOT / "data/dopamine-v0.2.yaml").is_file())
    if not declared_drive_present():
        assert "data/drive-v0.2.yaml" in missing
    record = measure_bias()
    assert record["status"] == "blocked"
    assert "Waiting for" in record["reason"]
    assert record["declared_substrate"]["candidate_id"] == "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
    # No fallback trigger exists in this constructed dependency fixture.
    monkeypatch.setattr(buridan_module, "P2_RECORDS", tmp_path / "records")
    for name, func in P2_STAGE.items():
        row = func()
        assert row["status"] == "blocked"
        assert row["stage"] == name
        assert row["substrate_id"] == declared_substrate_id()


@pytest.mark.parametrize("stage", ["VT-cal", "open-loop"])
def test_visual_producer_dependencies(stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Producers skip their output pin, while open loop also needs a TuBu failure."""
    monkeypatch.setattr(buridan_module, "declared_substrate_present", lambda: True)
    monkeypatch.setattr(buridan_module, "declared_drive_present", lambda: True)
    monkeypatch.setattr(buridan_module, "VISUAL_PATH", tmp_path / "visual.yaml")
    dopamine = tmp_path / "dopamine.yaml"
    dopamine.touch()
    monkeypatch.setattr(buridan_module, "DOPAMINE_PATH", dopamine)
    monkeypatch.setattr(buridan_module, "P2_RECORDS", tmp_path)
    photo_failure = "recorded photoreceptor failure (SPEC-P2 3.7)"
    tubu_failure = "recorded TuBu failure (SPEC-P2 3.7)"
    expected = [photo_failure, *([tubu_failure] if stage == "open-loop" else [])]
    assert p2_missing_dependencies(stage) == expected
    vcal = tmp_path / "visual-vcal.json"
    vcal.write_text(json.dumps({"status": "blocked", "selected_r_light_hz": None}))
    assert p2_missing_dependencies(stage) == expected
    vcal.write_text(json.dumps({"status": "passed", "selected_r_light_hz": 100}))
    assert p2_missing_dependencies(stage) == expected
    vcal.write_text(json.dumps({"status": "failed", "selected_r_light_hz": None,
                               "outcomes": [{"rate_hz": 150, "v3": {"passed": True},
                                             "v1": {"delta_steer": {"mean": 2.6}}}]}))
    if stage == "open-loop":
        assert p2_missing_dependencies(stage) == [tubu_failure]
        vtcal = tmp_path / "vtcal.json"
        vtcal.write_text(json.dumps({"status": "passed", "selected_r_vis_max_hz": 70}))
        assert p2_missing_dependencies(stage) == [tubu_failure]
        vtcal.write_text(json.dumps({"status": "failed", "selected_r_vis_max_hz": 70}))
    assert p2_missing_dependencies(stage) == []
    for consumer in (None, "bias", "bias-T", "4.1r-sign", "4.1r-T-sign", "K3r", "K3r-T",
                     "4.1r", "4.1r-T", "4.2r", "4.2r-T"):
        assert p2_missing_dependencies(consumer) == ["data/visual-v0.2.yaml"]

    # Exercise the real producer entry points, stopping before any engine work.
    class ReachedProducer(Exception):
        pass

    def reached(*args, **kwargs):
        if stage == "VT-cal":
            experiment = args[0]
            assert experiment.substrate.visual_version is None
            assert experiment.meta["grid"] == {"r_vis_max": list(buridan_module.VT_CAL_RATES_HZ)}
            assert all(probe.params.inject_at == "TuBu" for probe in experiment.arms[0].expanded())
        raise ReachedProducer

    monkeypatch.setattr(buridan_module, "_run_experiment", reached)
    monkeypatch.setattr(buridan_module, "_commit_visual", reached)
    with pytest.raises(ReachedProducer):
        (buridan_module.run_vtcal if stage == "VT-cal" else buridan_module.run_open_loop)()
    dopamine.unlink()
    assert p2_missing_dependencies(stage) == ["data/dopamine-v0.2.yaml"]
    monkeypatch.setattr(buridan_module, "declared_drive_present", lambda: False)
    assert "data/drive-v0.2.yaml" in p2_missing_dependencies(stage)
    monkeypatch.setattr(buridan_module, "declared_substrate_present", lambda: False)
    assert "item 122 declared substrate" in p2_missing_dependencies(stage)


@pytest.mark.parametrize("rate", buridan_module.VT_CAL_RATES_HZ)
def test_vtcal_grid_resolves_tubu_without_visual_file(rate: float) -> None:
    """The actual fixture must target TuBu, not schema-defaulted photoreceptors."""
    from flyonenomics.behaviour import load_settings
    from flyonenomics.orchestrator.phases import build_topology

    experiment = _p2_experiment("vpath-vtcal.json", meta={"r_vis_max": rate})
    params = buridan_module._p2_params()
    assert experiment.substrate.visual_version is None
    assert experiment.substrate.behaviour_version == "base-v0.2"
    assert experiment.meta["grid"] == {"r_vis_max": list(buridan_module.VT_CAL_RATES_HZ)}
    settings = load_settings("base-v0.2", params, assays={"open_loop_steering"},
                             meta=experiment.meta, grid=experiment.meta["grid"], encoder_grid=True)
    assert settings["r_vis_max"] == rate
    assert settings["sigma_vis"] == 20.0
    assert all(probe.params.inject_at == "TuBu" for probe in experiment.arms[0].expanded())

    class Registry:
        def population(self, name):
            assert name == "TuBu"  # topology must not extend R1_6
            return type("Population", (), {"idx": np.array([2, 3], dtype=np.int32)})()

    topology = build_topology(experiment, Registry(), params=params)
    assert topology.topology.extended_idx.tolist() == [2, 3]
    assert topology.behaviour_settings["r_vis_max"] == rate


@pytest.mark.parametrize("stage", ["VT-cal", "open-loop"])
def test_k3r_cli_checks_first_stage(stage: str, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """The CLI must not reintroduce the visual producer/consumer deadlock."""
    import runpy

    calls = []
    monkeypatch.setattr(buridan_module, "p2_missing_dependencies", lambda name=None:
                        calls.append(name) or ([] if name == stage else ["data/visual-v0.2.yaml"]))
    monkeypatch.setattr(buridan_module, "run_wave", lambda stages: {
        "results": {stage: {"status": "recorded"}}, "checkpoint": None})
    main = runpy.run_path(str(ROOT / "scripts/camber/k3r.py"))["main"]
    main(["--run", "--stages", f"{stage},bias", "--workers", "1"])
    assert calls == [None, stage]  # plan query, then stage-specific execution guard
    assert json.loads(capsys.readouterr().out)["status"] == "done"


def test_wp20_entries_bind_item_122_substrate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every level-4 P2 entry and the suite binder use item 122's one reader."""
    declared = declared_substrate()
    assert declared is not None and declared["candidate_id"] == "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
    declared_id = declared_substrate_id()
    if declared_id is not None:
        assert declared_id.startswith("rest:") and len(declared_id.split(":")[1]) == 16
    for test_id, factory in level4_p2.SUITE.items():
        entry = factory()
        assert entry.identity.substrate_id == (declared_id or "bare"), test_id
        assert entry.measured["declared_substrate"]["candidate_id"] == declared["candidate_id"], test_id
        assert entry.measured["declared_drive"] == declared_drive_present(), test_id

    # Reproduce status regeneration after the drive lands without writing a
    # fake drive file: a rest-bound matching-layers entry must not be compared
    # to bind_entry's old implicit `bare` context.
    from flyonenomics.behaviour import visual_calibration

    rest_id = "rest:0123456789abcdef"
    entry = level4_p2.verify_4_1r()
    entry = entry.model_copy(update={
        "identity": entry.identity.model_copy(update={"substrate_id": rest_id}),
    })
    monkeypatch.setattr(visual_calibration, "declared_substrate_id", lambda: rest_id)
    assert bind_entry(entry).outcome == "passed"
    monkeypatch.setattr(visual_calibration, "declared_substrate_id", lambda: "rest:fedcba9876543210")
    stale = bind_entry(entry)
    assert stale.outcome == "stale"
    assert stale.measured["binding_reason"] == "substrate mismatch"


def test_k3r_script_plan() -> None:
    """--plan prints the section 6.3 credits without starting an engine."""
    script = ROOT / "scripts/camber/k3r.py"
    planned = subprocess.run([sys.executable, str(script), "--plan"], cwd=ROOT,
                             check=True, capture_output=True, text=True)
    payload = json.loads(planned.stdout)
    assert payload["rows"]["K3r_proposal"]["brain_s"] == pytest.approx(550.0)
    assert payload["rows"]["4.8r"]["brain_s"] == pytest.approx(8580.0)
    assert payload["total_credits_rho1"] == pytest.approx(3.1)
    assert payload["under_cap"] is True
    assert payload["substrate_id"] == declared_substrate_id()
    assert ("data/visual-v0.2.yaml" in payload["missing"]) == (not (ROOT / "data/visual-v0.2.yaml").is_file())
    assert "Q-rest" not in payload["reason"]


def _open_loop_table(blocks: list[dict], values: list[float]) -> pd.DataFrame:
    """Constructed arena table for one open-loop probe. Units: s, Hz, deg/s."""
    total = sum(float(block["transition_s"]) + float(block["dwell_s"]) for block in blocks)
    t = np.arange(0.0, total, 0.1)
    r_l = np.zeros(len(t))
    r_r = np.zeros(len(t))
    omega = np.zeros(len(t))
    start = 0.0
    for block, value in zip(blocks, values):
        period = float(block["transition_s"]) + float(block["dwell_s"])
        dwell = (t >= start + float(block["transition_s"])) & (t < start + period)
        r_r[dwell] = value
        omega[dwell] = 4.0 * value
        start += period
    return pd.DataFrame({"t_ms": t * 1000.0, "r_L": r_l, "r_R": r_r, "omega": omega})


def _write_open_loop_run(root: Path, experiment, values_by_seed: dict[int, list[float]],
                         probe: int = 0, rate_values_by_seed: dict[int, list[float]] | None = None) -> Path:
    """Write a constructed open-loop run with arena and optional TuBu rates. Hz, deg/s."""
    document = experiment.model_dump(mode="json")
    root.mkdir(parents=True, exist_ok=True)
    (root / "experiment.json").write_text(json.dumps(document))
    arm = document["arms"][0]["label"]
    blocks = document["arms"][0]["protocol"][probe]["params"]["blocks"]
    for seed, values in values_by_seed.items():
        directory = root / f"arm-{arm}" / f"seed-{seed}"
        directory.mkdir(parents=True, exist_ok=True)
        arena = _open_loop_table(blocks, values)
        arena.to_parquet(directory / f"probe-{probe}-arena.parquet")
        if rate_values_by_seed is not None:
            rates = _open_loop_table(blocks, rate_values_by_seed[seed])[["t_ms", "r_R"]]
            rates = rates.rename(columns={"r_R": "TuBu"})
            rates.insert(0, "tick", np.arange(len(rates), dtype=np.int64))
            rates.to_parquet(directory / f"probe-{probe}-rates.parquet")
    return root


def test_p2_open_loop_scorers_on_constructed_runs(tmp_path: Path) -> None:
    """Bias and sign come from constructed arena tables, dwell only. Units: Hz, Hz/degree."""
    bias_run = _write_open_loop_run(tmp_path / "bias", _p2_experiment("bias.json", seeds=(1, 2, 3)),
                                    {seed: [0.2 + 0.01 * seed] for seed in (1, 2, 3)})
    bias = bias_from_run(bias_run)
    assert bias["n"] == 3
    assert bias["bias_hz"] == pytest.approx(np.mean([0.21, 0.22, 0.23]))

    azimuths = list(SIGN_CHECK_AZIMUTHS)
    sign_run = _write_open_loop_run(tmp_path / "sign", _p2_experiment("signcheck.json", seeds=(1, 2, 3)),
                                    {seed: [0.05 * azimuth for azimuth in azimuths] for seed in (1, 2, 3)})
    assert all(abs(gain - 0.05) < 1e-12 for gain in steer_gains_from_run(sign_run))
    decision = sign_from_run(sign_run)
    assert decision["sign_steer"] == 1 and not decision["flat"]
    rows = open_loop_blocks(sign_run)
    assert len(rows) == 3 and len(rows[0]["blocks"]) == 13


def test_run_wave_stops_after_a_failed_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    """A flat sign check cannot spend the K3r or consistency waves."""
    called: list[str] = []
    monkeypatch.setattr(buridan_module, "measure_bias", lambda: {"status": "recorded"})
    monkeypatch.setattr(buridan_module, "sign_check_p2", lambda: {"status": "failed", "flat": True})
    monkeypatch.setattr(buridan_module, "run_k3r", lambda: called.append("K3r") or {"status": "recorded"})
    result = buridan_module.run_wave(("bias", "4.1r-sign", "K3r"))
    assert list(result["results"]) == ["bias", "4.1r-sign"]
    assert called == []


def test_run_wave_checkpoints_after_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Consistency runs wait until the newly written controller is committed."""
    called: list[str] = []
    monkeypatch.setattr(buridan_module, "run_k3r", lambda: {
        "status": "recorded", "behaviour_sha256": "abc"})
    monkeypatch.setattr(buridan_module, "run_4_1r", lambda: called.append("4.1r") or {
        "outcome": "passed"})
    result = buridan_module.run_wave(("K3r", "4.1r"))
    assert called == []
    assert result["checkpoint"] == {
        "after": "K3r", "configuration": "data/behaviour-v0.2.yaml", "remaining": ["4.1r"]}


def test_p2_run_context_records_oracle_identity_and_settle(tmp_path: Path) -> None:
    """Stage evidence keeps the manifest's substrate, engine, platform and actual settles."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "manifest.json").write_text(json.dumps({
        "substrate_id": declared_substrate_id(),
        "engine_model": "lif",
        "identity": {"platform": "linux-aarch64"},
        "probe_offsets": [{"settle_s": 2.0}, {"settle_s": 3.5}],
    }))
    context = _p2_run_context([run])
    assert context["substrate_id"] == declared_substrate_id()
    assert context["engine_model"] == "lif"
    assert context["platform"] == "linux-aarch64"
    assert context["platforms"] == ["linux-aarch64"]
    assert context["settle_s_by_run"][0]["platform"] == "linux-aarch64"
    assert context["settle_s_by_run"][0]["settle_s"] == [2.0, 3.5]

    other = tmp_path / "other"
    other.mkdir()
    (other / "manifest.json").write_text(json.dumps({
        "substrate_id": declared_substrate_id(), "engine_model": "lif+sfa",
        "identity": {"platform": "linux-aarch64"}, "probe_offsets": [],
    }))
    with pytest.raises(ValueError, match="mixed run engine_model"):
        _p2_run_context([run, other])


def test_parent_evidence_keeps_mixed_platform_provenance() -> None:
    """K3r may combine platforms while retaining both as provenance."""
    records = [
        {"substrate_id": declared_substrate_id(), "engine_model": "lif", "platform": "linux-aarch64"},
        {"substrate_id": declared_substrate_id(), "engine_model": "lif", "platform": "darwin-arm64"},
    ]
    context = buridan_module._p2_evidence_context(records)
    assert "platform" not in context
    assert context["platforms"] == ["darwin-arm64", "linux-aarch64"]


def test_vtcal_selected_rate_reaches_runtime_settings() -> None:
    """The VT-cal metadata selects TuBu at the requested rate with three or ten seeds."""
    for seeds in ((1, 2, 3), tuple(range(1, 11))):
        experiment = _p2_experiment(
            "vpath-vcal.json", seeds=seeds, meta={"r_vis_max": 70.0},
            record_rates=["steering_L", "steering_R", "TuBu"])
        resolved = resolve_configurations(
            params=load_params(ROOT / "data/params-v0.2.yaml"),
            behaviour_path=ROOT / "data/behaviour-base-v0.2.yaml",
            behaviour_version="base-v0.2", assays={"open_loop_steering"},
            meta=experiment.meta, grid=experiment.meta.get("grid"), encoder_grid=True)
        assert experiment.seeds == list(seeds)
        assert resolved.visual.inject_at == "TuBu"
        assert resolved.visual.r_vis_max == 70.0
        assert resolved.behaviour.r_vis_max == 70.0


def test_p2_k3r_row_on_constructed_run(tmp_path: Path) -> None:
    """k3r_row scores a constructed Buridan run and computes the objective. Fraction, degrees."""
    experiment = _p2_experiment("k3r.json", seeds=(1, 2))
    document = experiment.model_dump(mode="json")
    (tmp_path / "experiment.json").write_text(json.dumps(document))
    arm = document["arms"][0]["label"]
    t = np.arange(0.0, 20.05, 0.05)
    frame = pd.DataFrame({"t_ms": t * 1000.0, "x": np.zeros(len(t)), "y": t * 20.0,
                          "r_L": np.zeros(len(t)), "r_R": np.zeros(len(t)), "omega": np.zeros(len(t))})
    for seed in (1, 2):
        directory = tmp_path / f"arm-{arm}" / f"seed-{seed}"
        directory.mkdir(parents=True)
        frame.to_parquet(directory / "probe-0-arena.parquet")
    target = {"fixation_index_median": 0.5, "fixation_index_iqr": 0.2,
              "stripe_deviation_deg_median": 20.0, "stripe_deviation_deg_iqr": 5.0}
    row = k3r_row(4.0, tmp_path, target)
    assert row["K_steer"] == 4.0 and row["n"] == 2
    assert row["model_fi"] is not None and np.isfinite(row["objective"])


def test_p2_k3r_meta_is_injected_into_the_fixture() -> None:
    """The K-grid runner sets sign, bias, visual blob and one K_steer grid point."""
    experiment = _p2_experiment("k3r.json", seeds=(1, 2),
                                meta={"sign_steer": -1, "bias_hz": 0.3, "visual": "blob",
                                      "grid": {"K_steer": 8.0}})
    assert experiment.meta["k_grid"] is True
    assert experiment.meta["grid"] == {"K_steer": 8.0}
    assert experiment.meta["sign_steer"] == -1 and experiment.meta["bias_hz"] == 0.3
    assert experiment.meta["visual"] == "blob" and experiment.seeds == [1, 2]


def _v1t_frame(blocks: list[dict], central: dict[str, float]) -> pd.DataFrame:
    """Constructed V1-T rates table: ambient base, stripe deltas, ±45 Δsteer. Units: Hz."""
    total = sum(float(block["transition_s"]) + float(block["dwell_s"]) for block in blocks)
    t = np.arange(0.0, total, 0.1)
    data: dict[str, np.ndarray] = {"t_ms": t * 1000.0}
    for name in ("TuBu", "visual_projection", "LAL_neurons"):
        data[name] = np.zeros(len(t))
    data["steering_L"] = np.zeros(len(t))
    data["steering_R"] = np.zeros(len(t))
    start = 0.0
    for block in blocks:
        period = float(block["transition_s"]) + float(block["dwell_s"])
        dwell = (t >= start + float(block["transition_s"])) & (t < start + period)
        azimuth = block["azimuth_deg"]
        if azimuth is not None:
            for name, value in central.items():
                data[name][dwell] = value
            data["steering_R"][dwell] = 1.0 if azimuth == 45.0 else -1.0
        start += period
    return pd.DataFrame(data)


def test_v1t_row_measures_central_input_and_steering(tmp_path: Path) -> None:
    """VT-cal measures the central-input populations and the Δsteer; SPEC-P2 section 3.7."""
    from flyonenomics.behaviour.buridan import _p2_experiment, v1t_row

    experiment = _p2_experiment("vpath-vcal.json", seeds=(1, 2, 3))
    document = experiment.model_dump(mode="json")
    root = tmp_path / "v1t"
    root.mkdir()
    (root / "experiment.json").write_text(json.dumps(document))
    arm = document["arms"][0]["label"]
    blocks = document["arms"][0]["protocol"][1]["params"]["blocks"]
    for seed in (1, 2, 3):
        directory = root / f"arm-{arm}" / f"seed-{seed}"
        directory.mkdir(parents=True)
        _v1t_frame(blocks, {"TuBu": 0.4, "visual_projection": 0.5, "LAL_neurons": 0.0}).to_parquet(
            directory / "probe-1-rates.parquet")
    row = v1t_row(root, r_vis_max=100.0, rng=np.random.default_rng(0), n_boot=200)
    assert row["central_input_carried"] is True
    assert row["steering_carried"] is True
    assert row["mean_delta_steer_hz"] == pytest.approx(2.0)
    assert "TuBu" in row["central_input_populations"]


def test_encoder_records_follow_the_visual_file() -> None:
    """TuBu writes bias-T and 4.1r-T-sign; the photoreceptor path keeps bias and signcheck."""
    from flyonenomics.behaviour import buridan

    original = buridan._p2_encoder
    buridan._p2_encoder = lambda: "TuBu"
    try:
        assert buridan._encoder_records() == {"bias": "bias-T", "sign": "4.1r-T-sign",
                                              "k3r": "k3r-tubu", "4.1r": "4.1r-T", "4.2r": "4.2r-T"}
    finally:
        buridan._p2_encoder = original
    assert buridan._encoder_records()["bias"] == ("bias-T" if buridan._p2_encoder() == "TuBu" else "bias")


def test_open_loop_records_side_resolved_v1_and_full_v3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Step 3 must use corrected WP18 observers, not bilateral means or steering-only V3."""
    from flyonenomics.behaviour.visual_run import V1_POPULATIONS

    monkeypatch.setattr(buridan_module, "P2_RECORDS", tmp_path)
    monkeypatch.setattr(buridan_module, "VISUAL_PATH", tmp_path / "visual.yaml")
    monkeypatch.setattr(buridan_module, "VISUAL_P2", tmp_path / "visual.yaml")
    monkeypatch.setattr(buridan_module, "p2_missing_dependencies", lambda stage=None: [])
    monkeypatch.setattr(buridan_module, "_p2_run_context", lambda paths: {"platform": "linux-aarch64"})
    (tmp_path / "visual-vcal.json").write_text(json.dumps({"outcomes": [
        {"rate_hz": 150, "v3": {"passed": True}, "v1": {"delta_steer": {"mean": 2}}}]}))
    (tmp_path / "bias-open-loop.json").write_text("{}")
    monkeypatch.setattr(buridan_module, "measure_bias", lambda **kwargs: {
        "bias_hz": 0.25, "record": "bias-open-loop", "run_dir": str(tmp_path / "bias")})
    documents = []
    monkeypatch.setattr(buridan_module, "_write_behaviour", lambda doc: documents.append(doc) or "sha")

    def run(experiment, workers):
        protocol = experiment.meta["visual_path_protocol"]
        assert experiment.substrate.visual_version == "v0.2"
        assert experiment.substrate.behaviour_version == "base-v0.2"
        directory = tmp_path / protocol
        directory.mkdir()
        (directory / "experiment.json").write_text(experiment.model_dump_json())
        (directory / "manifest.json").write_text(json.dumps({"identity": {"platform": "linux-aarch64"}}))
        for seed in experiment.seeds:
            row = ({"seed": seed, "delta_steer_hz": 2.0, "stage_delta_hz": {
                name: {"ipsilateral": 1.0, "contralateral": -1.0} for name in V1_POPULATIONS}}
                if protocol == "v1" else {
                    "seed": seed, "F": 1.2, "b": 0.01, "stability_ratio": 1.0,
                    "central_hz": 0.2, "DAN_hz": 0.8, "KC_hz": 0.09,
                    "ignited": False, "steering_diff_hz": 0.5})
            seed_dir = directory / "arm-wild-type" / f"seed-{seed}"
            seed_dir.mkdir(parents=True)
            (seed_dir / "metrics.json").write_text(json.dumps({"probes": {"0": {"visual_path": row}}}))
        return directory

    monkeypatch.setattr(buridan_module, "_run_experiment", run)
    result = buridan_module.run_open_loop()
    assert result["v1"]["passed"]
    assert result["v1"]["evaluation"]["contralateral"]["L1"]["mean"] == -1.0
    assert result["v3"]["status"] == "failed"
    assert result["v3"]["checks"]["central"] == pytest.approx(0.2)
    assert (tmp_path / "V1-open-loop.json").is_file()
    assert (tmp_path / "V3-open-loop.json").is_file()
    assert documents[0]["controller"] == "open_loop"


def test_open_loop_encoder_selection() -> None:
    """Step 3 prefers a V3 passer, else the VT-cal value with the largest |Δsteer|. Units: Hz."""
    from flyonenomics.behaviour.buridan import _open_loop_encoder

    vcal = {"outcomes": [
        {"rate_hz": 50.0, "v3": {"passed": True}, "v1": {"delta_steer": {"mean": 0.2}}},
        {"rate_hz": 100.0, "v3": {"passed": True}, "v1": {"delta_steer": {"mean": -0.9}}},
        {"rate_hz": 150.0, "v3": {"passed": False}, "v1": {"delta_steer": {"mean": 5.0}}},
    ]}
    encoder = _open_loop_encoder(vcal, None)
    assert encoder["inject_at"] == "photoreceptors" and encoder["r_light"] == 100.0
    vtcal = {"sigma_vis": 20.0, "table": [{"r_vis_max_hz": 40.0, "mean_delta_steer_hz": 0.1},
                                          {"r_vis_max_hz": 100.0, "mean_delta_steer_hz": 1.2}]}
    encoder = _open_loop_encoder(None, vtcal)
    assert encoder["inject_at"] == "TuBu" and encoder["r_vis_max"] == 100.0
    assert _open_loop_encoder(None, None) == {}


def test_4_8r_variant_settings() -> None:
    """The 13 section 3.5 sensitivity variants map to engine settings."""
    from flyonenomics.behaviour.buridan import WP20_VARIANTS, variant_settings

    assert len(WP20_VARIANTS) == 13
    assert variant_settings("perm-0") == {"perm": 1}
    assert variant_settings("jitter-4") == {"jitter": 4}
    assert variant_settings("sigma_h-0") == {"sigma_h": 0.0}
    assert variant_settings("v_fwd-half") == {"v_fwd_scale": 0.5}
    assert variant_settings("v_fwd-double") == {"v_fwd_scale": 2.0}
    assert variant_settings("histamine-off") == {"histamine_off": True}
    with pytest.raises(ValueError, match="unknown 4.8r variant"):
        variant_settings("nope")


def test_histamine_off_preserves_non_photoreceptor_scale_factors() -> None:
    """4.8r histamine-off changes only presynaptic photoreceptor connection rows."""
    scale = np.array([-2.0, 3.0, 4.0, -5.0], dtype=np.float32)
    i_pre = np.array([0, 1, 2, 0], dtype=np.int32)
    photoreceptor = np.array([True, False, False])
    changed = buridan_module._connection_sign_scale(scale, i_pre, photoreceptor)
    np.testing.assert_array_equal(changed, np.array([1.0, 3.0, 4.0, 1.0], dtype=np.float32))
    np.testing.assert_array_equal(scale, np.array([-2.0, 3.0, 4.0, -5.0], dtype=np.float32))
