"""3.2r-3.10r and 4.7 evaluators on constructed tables; no engine."""
from __future__ import annotations

import json

import numpy as np

from flyonenomics.analysis.contrasts import analysis_rng
from flyonenomics.validation.level3_p2 import (
    SUITE,
    evaluate_3_2r,
    evaluate_3_3r,
    evaluate_3_4r,
    evaluate_3_5r,
    evaluate_3_10r,
    relative_change,
    smallest_coupling_lever,
)
from flyonenomics.analysis.plan import write_experiments
from pathlib import Path

write_experiments(Path(__file__).resolve().parents[1])


def test_3_2r_constructed_da() -> None:
    """Wild-type DA above zero; fumin at least 2× and within 20 percent of the fixed point."""
    wt = {"a": 0.02, "b": 0.03}
    fumin = {"a": 0.05, "b": 0.07}
    fp = {"a": 0.05, "b": 0.07}
    assert evaluate_3_2r(wt, fumin, fp)["passed"]
    silent = evaluate_3_2r({"a": 0.0}, {"a": 0.0}, {"a": 0.0})
    assert not silent["passed"]


def test_3_3r_monotone_between_wt_and_fumin() -> None:
    """Settled mean DA rises with dose and lies between wild type and fumin."""
    vehicle = np.array([0.02, 0.02, 0.02])
    drug = np.array([0.03, 0.04, 0.05])
    fumin = np.array([0.08, 0.08, 0.08])
    assert evaluate_3_3r(vehicle, drug, fumin)["passed"]
    assert not evaluate_3_3r(vehicle, np.array([0.03, 0.025, 0.05]), fumin)["passed"]


def test_3_4r_fumin_null_interval() -> None:
    """Paired MPH-minus-vehicle interval sits inside ±5 percent of the fumin vehicle mean."""
    vehicle = np.full(3, 0.08)
    drug = np.array([0.0801, 0.0799, 0.08])
    rng = analysis_rng(20260912)
    result = evaluate_3_4r(vehicle, drug, rng, 10_000, 0.05)
    assert result["passed"]
    shifted = evaluate_3_4r(vehicle, vehicle + 0.02, analysis_rng(20260912), 10_000, 0.05)
    assert not shifted["passed"]


def test_3_5r_3iy_lowers_da() -> None:
    """3-IY lowers settled DA in both genotypes."""
    vehicle = {"wild_type": np.array([0.02, 0.021]), "fumin": np.array([0.08, 0.075])}
    treated = {"wild_type": np.array([0.01, 0.015]), "fumin": np.array([0.04, 0.05])}
    assert evaluate_3_5r(vehicle, treated)["passed"]


def test_3_10r_interval_excludes_zero() -> None:
    """Coupling passes when the DA_exposed paired interval excludes zero."""
    wt = np.full(10, 1.0)
    fumin = np.full(10, 2.0)
    result = evaluate_3_10r(wt, fumin, analysis_rng(20260912), 10_000)
    assert result["passed"]
    tied = evaluate_3_10r(wt, wt, analysis_rng(20260912), 10_000)
    assert not tied["passed"]


def test_4_7_smallest_lever_on_constructed_sweep() -> None:
    """Report the smallest in-range gamma/dV/Kd change that excludes zero."""
    results = [
        {"group": "Kd_D1", "level": "default", "ci95": [-0.01, 0.01], "relative_change": 0.0},
        {"group": "Kd_D1", "level": "high", "ci95": [0.2, 0.4], "relative_change": 2.0},
        {"group": "gamma_*", "level": "high", "ci95": [0.05, 0.2], "relative_change": 0.5},
        {"group": "Ki_mph", "level": "high", "ci95": [0.1, 0.2], "relative_change": 0.1},
    ]
    found = smallest_coupling_lever(results)
    assert found["change"] == 0.5
    assert found["setting"]["group"] == "gamma_*"
    assert relative_change({"rec.gamma_D1": 0.45}, {"rec.gamma_D1": 0.3}) == 0.5


def test_suite_ids_and_recorded_3_10r() -> None:
    """SUITE covers 3.2r-3.10r and 4.9-4.11 and preserves record provenance."""
    assert set(SUITE) == {"3.2r", "3.3r", "3.4r", "3.5r", "3.6r", "3.8r", "3.9r", "3.10r", "4.9", "4.10", "4.11"}
    entry = SUITE["3.10r"]()
    assert entry.outcome == "passed"
    assert entry.compatibility == "development"
    assert entry.stub == "RecordedDevelopment"
    assert entry.measured["record"] == "validation/records/p2/wp21-neural.json"
    assert entry.measured["platform"] == "linux-aarch64"
    assert entry.fixture_path == "data/experiments/p2/coupling.json"
    assert entry.identity.platform == "linux-aarch64"
    assert entry.identity.substrate_id == "rest:379cc4cc9030cdd1"


def test_neural_half_measured_and_terminal_entries_state_real_reasons() -> None:
    """Measured entries retain their record class; item-144 entries are terminally not run."""
    record = json.loads((Path(__file__).resolve().parents[1] /
                         "validation/records/p2/wp21-neural.json").read_text())
    assert record["class_reason"] == (
        "SPEC-P2 item 147 drops platform as a class reason; this record has no canonical "
        "binding (no fixture hash or input blobs)"
    )
    assert [row["class"] for row in record["class_history"]] == ["development", "development"]
    assert "missing canonical binding" in record["class_history"][-1]["reason"]
    for test_id in ("3.2r", "3.3r", "3.4r", "3.5r", "3.10r"):
        entry = SUITE[test_id]()
        assert entry.outcome == "passed", test_id
        assert entry.compatibility == "development", test_id
        assert entry.stub == "RecordedDevelopment", test_id
        assert entry.measured["platform"] == "linux-aarch64", test_id
        assert entry.measured["dopamine_sha256"].startswith("629d4017"), test_id
    prediction = SUITE["3.6r"]()
    assert prediction.outcome == "recorded"
    assert prediction.compatibility == "development"
    assert prediction.stub == "RecordedDevelopment"
    for field in ("pam_minus_baseline_dn_all_hz", "fumin_minus_wild_type_da_exposed_hz",
                  "fumin_minus_wild_type_dn_all_hz"):
        assert field in prediction.measured
    assert prediction.measured["missing_required_readouts"] == []
    for test_id in ("3.8r", "3.9r"):
        entry = SUITE[test_id]()
        assert entry.outcome == "unavailable", test_id
        assert "WP20" not in entry.measured["reason"], test_id
        assert "drive-v0.2.yaml" not in entry.measured["reason"], test_id
    assert "3.8r" in SUITE["3.8r"]().measured["reason"]
    for test_id in ("4.9", "4.10", "4.11"):
        entry = SUITE[test_id]()
        assert entry.outcome == "not run", test_id
        assert "SPEC-P2 item 144" in entry.measured["reason"], test_id
        assert entry.fixture_path is None, test_id


def test_fixture_form_tracks_recorded_visual_status() -> None:
    """3.8r and the 4.x entries use the form matching the recorded status (SPEC-P2 4.4)."""
    from flyonenomics.validation import level3_p2 as mod

    status = mod.recorded_visual_status()
    assert status in {"open loop", "photoreceptor closed loop", "TuBu closed loop"}
    form = mod.visual_fixture_form()
    assert form == ("openloop" if status == "open loop" else "buridan")
    test_id, stem = "3.8r", "ablation-p2"
    assert SUITE[test_id]().fixture_path == f"data/experiments/p2/{stem}-{form}.json"
    other = "buridan" if form == "openloop" else "openloop"
    assert (Path(__file__).resolve().parents[1] /
            f"data/experiments/p2/{stem}-{other}.json").is_file()
    assert mod.visual_fixture_form("open loop") == "openloop"
    assert mod.visual_fixture_form("photoreceptor closed loop") == "buridan"
    assert mod.visual_fixture_form("TuBu closed loop") == "buridan"
