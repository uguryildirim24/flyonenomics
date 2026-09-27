"""Constructed-input tests for the WP18 V3/V1 engine driver and V-cal state machine."""
from __future__ import annotations

import runpy
import numpy as np

from flyonenomics.behaviour import visual_run as vr
from flyonenomics.types import load_params

SCRIPT = runpy.run_path(str(vr.REPO / "scripts/run_visual_path.py"))
experiment_for = SCRIPT["experiment_for"]


def _v3_row(**over: float | bool | None) -> dict:
    row = {
        "seed": 1, "F": 1.2, "b": 0.01, "stability_ratio": 1.0,
        "central_hz": 4.8, "DAN_hz": 0.8, "KC_hz": 0.09,
        "ignited": False, "steering_diff_hz": 0.5,
    }
    row.update(over)
    return row


def _v1_row(seed: int, ipsi: float, steer: float, contra: float = 0.0) -> dict:
    delta = {
        name: {"ipsilateral": ipsi, "contralateral": contra}
        for name in vr.V1_POPULATIONS
    }
    return {"seed": seed, "stage_delta_hz": delta, "delta_steer_hz": steer}


def test_v3_passed_rows() -> None:
    rows = [_v3_row(seed=s) for s in (1, 2, 3)]
    assert vr.v3_passed(rows)["passed"]
    bad_fano = [_v3_row(seed=s, F=3.5) for s in (1, 2, 3)]
    assert not vr.v3_passed(bad_fano)["passed"]
    bad_central = [_v3_row(seed=s, central_hz=0.2) for s in (1, 2, 3)]
    assert not vr.v3_passed(bad_central)["passed"]
    ignited = [_v3_row(seed=s, ignited=(s == 2)) for s in (1, 2, 3)]
    assert not vr.v3_passed(ignited)["passed"]


def test_v1_passed_uses_ipsilateral_and_records_contralateral() -> None:
    rows = [_v1_row(s, ipsi=2.0, steer=2.0, contra=0.0) for s in range(1, 11)]
    result = vr.v1_passed(rows)
    assert result["passed"], result
    assert result["steer_pass"]
    assert set(result["contralateral"]) == set(vr.V1_POPULATIONS)
    assert result["contralateral"]["L1"]["mean"] == 0.0
    broken = [_v1_row(s, ipsi=0.0, steer=0.0) for s in range(1, 11)]
    assert not vr.v1_passed(broken)["passed"]


def test_records_and_visual_document() -> None:
    rows = [_v3_row(seed=s) for s in (1, 2, 3)]
    record = vr.record_v3(rows, r_light=150.0)
    assert record["status"] == "passed" and record["passed"] is True
    assert record["r_light_hz"] == 150.0 and len(record["rows"]) == 3
    assert "identity" not in record
    v1_rows = [_v1_row(s, ipsi=2.0, steer=2.0) for s in range(1, 11)]
    v1_record = vr.record_v1(v1_rows, r_light=150.0, screen="ten_seed")
    assert v1_record["status"] == "passed"
    assert v1_record["screen"] == "ten_seed" and v1_record["seed_count"] == 10
    summary = {"selected_r_light_hz": 150.0, "stage1_hz": [50.0], "rows": []}
    vcal = vr.record_vcal(summary)
    assert vcal["status"] == "passed"
    assert vcal["visual_commit"] == "data/visual-v0.2.yaml"
    assert "rows" not in vcal
    document = vr.visual_document(150.0, load_params(vr.PARAMS_PATH), "abc")
    assert document["inject_at"] == "photoreceptors"
    assert document["r_light"] == 150.0
    assert document["version"] == "v0.2"
    assert document["provenance"]["vcal_sha256"] == "abc"


def test_vcal_runs_stage_two_only_without_a_stage_one_v3_pass() -> None:
    rates = vr.V_CAL_STAGE1_HZ
    all_pass = {rate: True for rate in rates}
    assert not vr.vcal_stage2_needed(all_pass, rates)
    none_pass = {rate: False for rate in rates}
    assert vr.vcal_stage2_needed(none_pass, rates)
    one_pass = {rate: (rate == 100.0) for rate in rates}
    assert not vr.vcal_stage2_needed(one_pass, rates)


def test_vcal_selects_the_lowest_passing_rate_and_never_a_failed_ten_seed() -> None:
    rates = [50.0, 100.0, 150.0, 300.0]
    v3 = {rate: {"passed": True} for rate in rates}
    screen = {
        50.0: {"passed": True, "delta_steer": {"mean": 0.1}},
        100.0: {"passed": True, "delta_steer": {"mean": 2.0}},
        150.0: {"passed": False, "delta_steer": {"mean": 0.0}},
        300.0: {"passed": False, "delta_steer": {"mean": 0.0}},
    }
    assert vr.vcal_candidate(list(reversed(rates)), v3, screen) == 50.0
    outcomes = [
        {"rate_hz": rate, "v3": v3[rate], "v1": screen[rate]} for rate in rates
    ]
    # No selection: V1 is recorded at the V3-passing rate with the largest |mean delta_steer|.
    assert vr.vcal_v1_failed_rate(outcomes) == 100.0
    no_v3 = [{"rate_hz": rate, "v3": {"passed": False}, "v1": {}} for rate in rates]
    assert vr.vcal_v1_failed_rate(no_v3) is None


def test_orchestrator_stimulus_uses_the_pinned_stripe_width() -> None:
    from flyonenomics.behaviour.arena import Behaviour

    arena = Behaviour.__new__(Behaviour)
    arena.params = load_params(vr.PARAMS_PATH)
    arena.probe = experiment_for("v1", 50., (1,)).arms[0].protocol[0]
    arena.t_s = 5.0
    arena.x = arena.y = arena.h = 0.0
    stimuli = arena._stimuli()
    assert np.isclose(stimuli[0]["width"], 5.0)
    assert np.isclose(stimuli[0]["az_fly"], 45.0)


def test_engine_reads_the_v02_dopamine_file() -> None:
    from flyonenomics.io import read_yaml

    assert vr.DOPAMINE_PATH.name == "dopamine-v0.2.yaml"
    assert vr.DOPAMINE_PATH.is_file()
    assert read_yaml(vr.DOPAMINE_PATH)["version"] == "v0.2"
    for protocol in ("v1", "v3"):
        exp = experiment_for(protocol, 100., (1, 2, 3))
        assert exp.substrate.dopamine_version == "v0.2"
        assert exp.substrate.visual_version is None
        assert exp.meta["r_light"] == 100.
        assert exp.arms[0].protocol[0].assay == "open_loop_steering"


def test_side_subsets_respect_spread_and_never_fall_back_to_bilateral() -> None:
    from types import SimpleNamespace

    pop = SimpleNamespace(idx=np.array([0, 1, 2, 3]), root_ids=np.array([10, 11, 12, 13]),
                          side=np.array(["right", "right", "left", "left"]))
    registry = SimpleNamespace(population=lambda name: pop)
    table = {"types": {"L1": {"column_subsets": False, "root_ids": [10, 11, 12, 13],
                              "azimuth_deg": [45, 100, -45, -100]},
                       "L2": {"column_subsets": True, "root_ids": [10, 11, 12, 13],
                              "azimuth_deg": [45, 100, -45, -100]}}}
    subsets = vr.stage_subsets(registry, load_params(vr.PARAMS_PATH), table)
    assert subsets["L1"]["45.0"]["ipsilateral"].tolist() == [0, 1]
    assert subsets["L1"]["45.0"]["contralateral"].tolist() == [2, 3]
    assert subsets["L2"]["45.0"]["ipsilateral"].tolist() == [0]
    assert subsets["L2"]["45.0"]["contralateral"].tolist() == [2]
    pop.side[:] = "right"
    subsets = vr.stage_subsets(registry, load_params(vr.PARAMS_PATH), table)
    assert subsets["L1"]["45.0"]["contralateral"].size == 0


def test_failed_ten_seed_cannot_select_or_commit_and_stage_two_is_skipped(monkeypatch, tmp_path) -> None:
    calls, records = [], {}

    def wave(protocol, rates, seeds, workers, out):
        calls.append((protocol, tuple(rates), len(seeds)))
        result = []
        for rate in rates:
            rows = ([_v3_row(seed=s) for s in seeds] if protocol == "v3" else
                    [_v1_row(s, ipsi=2., steer=2. if len(seeds) == 3 else 0.) for s in seeds])
            result.append({"r_light_hz": rate, "rows": rows, "identity": {"platform": "linux-aarch64"},
                           "frozen": False, "brain_s": len(seeds) * (12 if protocol == "v3" else 18)})
        return result

    def record(path, payload):
        records[path.name] = payload
        return "a" * 64

    monkeypatch.setitem(SCRIPT["run_vcal"].__globals__, "_wave", wave)
    monkeypatch.setattr(vr, "write_record", record)
    monkeypatch.setattr(vr, "VISUAL_PATH", tmp_path / "visual.yaml")
    summary = SCRIPT["run_vcal"](tmp_path, 12)
    assert summary["selected_r_light_hz"] is None
    assert summary["ten_seed_v1"]["passed"] is False
    assert not summary["stage2_ran"]
    assert all(25. not in rates and 10. not in rates for _, rates, _ in calls)
    assert not vr.VISUAL_PATH.exists()
    assert records["V1.json"]["passed"] is False
    assert records["R3.json"]["table"][0]["rates"]["50.0"]["v1_three_seed"] is not None


def test_visual_observer_accepts_the_orchestrator_registry_snapshot() -> None:
    from flyonenomics.orchestrator.workers import RegistrySnapshot

    reg = RegistrySnapshot(np.arange(3), {}, [], {})
    groups = {"central": np.array([0]), "DAN": np.array([1]), "KC": np.array([2])}
    phase = experiment_for("v3", 50., (1,)).arms[0].protocol[0]
    probe = vr.VisualProbe("v3", reg, load_params(vr.PARAMS_PATH), phase, groups)
    assert probe.groups is groups


def test_r3_requires_a_joint_v3_v1_pass() -> None:
    from flyonenomics.behaviour.visual_calibration import r3_record

    cells = {"50.0": {"v3": {"passed": True}, "v1_three_seed": {"passed": False}}}
    assert r3_record(cells)["table"][0]["passed"] is False
    cells["50.0"]["v1_three_seed"]["passed"] = True
    assert r3_record(cells)["table"][0]["passed"] is True
