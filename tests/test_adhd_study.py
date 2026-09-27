"""Required stage-5 synthetic confound, pairing and analysis checks (item 146)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pickle
import subprocess
import sys

import numpy as np
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("adhd_analysis", SCRIPTS / "adhd_analysis.py")
analysis = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = analysis
spec.loader.exec_module(analysis)
spec = importlib.util.spec_from_file_location("adhd_study", SCRIPTS / "adhd_study.py")
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def test_required_synthetic_confounds_and_known_shift() -> None:
    record = analysis.synthetic_validation()
    rows = {r["scenario"]: r for r in record["scenarios"]}
    assert record["exact_assertions_passed"]
    for name in ("symmetric_saturation", "fixed_spatial_bias", "affine_no_history"):
        assert rows[name]["exact_wt_H"] == 0
        assert rows[name]["exact_genotype"] == pytest.approx(0, abs=1e-12)
    assert rows["asymmetric_suppression"]["exact_wt_H"] == 0.25
    assert rows["affine_with_history"]["exact_genotype"] != 0
    assert rows["affine_with_history"]["exact_affine_residual"] == pytest.approx(0, abs=1e-12)
    assert rows["known_genotype_shift"]["exact_genotype"] == pytest.approx(0.2)


def test_full_pipeline_recovers_known_shift_and_reversal() -> None:
    cal = np.tile(np.array([[1., 1.], [3., 1.], [5., 1.], [1., 5.], [1., 3.]]), (10, 1, 1))
    rates = np.ones((10, 4, 8, 2))
    rates[:, :, 1] += [4, 0]
    rates[:, :, 2] += [0, 4]
    rates[:, :, [3, 5, 7]] += [2, 2]
    rates[:, 1, 5] += [0.8, 0]
    rates[:, 1, 7] += [0, 0.8]
    record = analysis.analyse(rates, cal, (-50., 50.), replicates=100)
    assert record["primary"][0]["mean"] == pytest.approx(0.2)
    assert record["primary"][1]["mean"] == pytest.approx(-0.2)
    assert all(p["reading"] == "detected difference" for p in record["primary"])
    assert record["affine_secondary"]["mean"] == pytest.approx(0.2)


def test_pair_prerequisite_rejects_absent_input_and_never_maximises_distance() -> None:
    absent = np.zeros((10, 5, 245))
    assert analysis.choose_pair(absent)["prerequisite"] == "failure"
    cal = absent.copy()
    cal[:, 1, 0] = 100
    cal[:, 2, 0] = 4
    cal[:, 3, 1] = 4
    cal[:, 4, 1] = 100
    record = analysis.choose_pair(cal)
    assert record["pair"] == (-50, 50)  # Not the much more distant outer pair.
    basis, axis = analysis.templates(cal, record["pair"])
    assert (basis[:, 0] - basis[:, 1]) @ axis == pytest.approx(1)


def test_affine_fit_sparse_nonnegative_and_duplicate_seed_exclusion() -> None:
    x = np.repeat(np.array([[[0., 0], [1., 0], [2., 0]]]), 4, axis=0)
    y = 3 * x + 2
    a, b, resolved = analysis.fit_affine(x, y)
    np.testing.assert_allclose(a, [3, 0])
    np.testing.assert_allclose(b, [2, 2])
    np.testing.assert_array_equal(resolved, [True, False])
    a, _, _ = analysis.fit_affine(x, 10 - x)
    assert np.all(a >= 0)
    rates = np.zeros((10, 4, 8, 2))
    with pytest.raises(ValueError, match="independent training"):
        analysis.affine_residual(rates, np.ones(2), np.array([0] * 5 + [1] * 5))


def test_confirmatory_single_contrast_and_monte_carlo_exact_check() -> None:
    cal = np.tile(np.array([[1., 1.], [3., 1.], [5., 1.], [1., 5.], [1., 3.]]), (10, 1, 1))
    rates = np.ones((40, 2, 4, 2))
    rates[:, 1, 1, 0] -= .8  # fumin A->AB only; negative H shift
    pilot = np.ones((10, 4, 8, 2))
    result = analysis.confirm_analyse(rates, cal, (-50., 50.), pilot, replicates=100, draws=5000)
    assert result["primary"]["mean"] == pytest.approx(-.1)
    assert result["primary"]["confirmed"]
    assert result["primary"]["ci95"] == pytest.approx([-.1, -.1])
    assert result["secondaries"]["pooled_pilot_plus_confirmation"]["mean"] == pytest.approx(-.08)
    assert len(result["secondaries"]["H_per_seed_condition"]) == 40
    with pytest.raises(ValueError, match="40 complete"):
        analysis.confirm_analyse(rates[:39], cal, (-50., 50.), pilot, replicates=10, draws=100)
    for values in (np.array([1., 2., -1., 3., 2., -2., 1., 0., 1., 3.]),
                   np.ones(10), np.zeros(10)):
        exact = analysis.sign_p(values)
        mc = analysis.monte_carlo_sign_p(values, draws=100_000, seed=91)
        sigma = np.sqrt(exact * (1 - exact) / 100_000)
        assert abs(mc["p"] - exact) <= 5 * sigma + 1 / 100_001


def test_reviewed_5b_records_remain_byte_identical() -> None:
    # Hashes of the previously reviewed immutable plan, pair and results.
    for name, expected in {
        "adhd-study-plan.json": "dc1fb1df32b795303a16a931673cabdbf570d7ef0b446542808e8c5e37835b29",
        "adhd-study-pair.json": "b941a440714244811e9ce305a45e678d5f9e5ea25a4a8f2ed638c0f630eff4dc",
        "adhd-study-results.json": "47c6fc6e9ef83b13bdacc3af1b89b96f6b3b8d6f25c0bd1dd577d42326c0657e",
    }.items():
        assert study.sha(study.ROOT / "validation/records/p2" / name) == expected


def test_male_array_binding_tracks_explicit_inputs() -> None:
    inputs = {"connectome_version": "male-cns:v1.0", "n": 3,
              "classes": np.array(["ACh", "GABA", "unk"]),
              "kc_mask": np.array([0, 1, 0], dtype=np.uint8),
              "pre": np.array([0, 1]), "s_pq": np.array([1., -1.])}
    ctx = {"scale_inputs": inputs, "engine_arrays_sha256": {"roots": "male-test"}}
    scale = np.array([1., 6.], dtype=np.float32)
    before = study.male_array_binding(ctx, scale)
    assert (before["n_neurons"], before["n_edges"]) == (3, 2)
    assert before["connectome_version"] == "male-cns:v1.0"
    inputs["kc_mask"][1] = 0
    after = study.male_array_binding(ctx, scale)
    assert before["kc_mask_u8_sha256"] != after["kc_mask_u8_sha256"]
    assert before["scale_f32le_sha256"] == after["scale_f32le_sha256"]


def test_rng_fingerprint_uses_unread_values_not_memory_addresses() -> None:
    numpy_state = np.random.RandomState(101).get_state()
    first = np.arange(8, dtype=np.float64)
    second = first.copy()

    def state(buffer, index=3):
        return {"numpy_state": numpy_state,
                "rand_buffer": np.array([buffer.ctypes.data], dtype=np.intp),
                "rand_buffer_index": np.array([index], dtype=np.int32),
                "randn_buffer": np.array([0], dtype=np.intp),
                "randn_buffer_index": np.array([0], dtype=np.int32)}

    a, b = state(first), state(second)
    # The failed audit hashed these different addresses despite equal draws.
    assert pickle.dumps(a, protocol=5) != pickle.dumps(b, protocol=5)
    assert study.rng_state_hash(a, 8) == study.rng_state_hash(b, 8)
    second[0] += 1  # Already consumed; cannot affect the next draw.
    assert study.rng_state_hash(a, 8) == study.rng_state_hash(b, 8)
    old_serialisation = pickle.dumps(b, protocol=5)
    second[3] += 1  # Same pointer, changed next value: the old audit misses it.
    assert pickle.dumps(b, protocol=5) == old_serialisation
    assert study.rng_state_hash(a, 8) != study.rng_state_hash(b, 8)
    assert study.rng_state_hash(state(first, 0), 8) == study.rng_state_hash(state(second, 0), 8)
    b = state(second, 0)
    b["numpy_state"] = np.random.RandomState(102).get_state()
    assert study.rng_state_hash(state(first, 0), 8) != study.rng_state_hash(b, 8)
    with pytest.raises(ValueError, match="no storage"):
        study.rng_state_hash({**a, "rand_buffer": np.array([0])}, 8)


def test_rng_fingerprint_survives_real_cython_snapshot_replay() -> None:
    # Separate interpreter: start with empty native buffers, as each study worker does.
    code = f'''import sys
sys.path.insert(0, {str(SCRIPTS)!r})
import adhd_study as study
import brian2 as b
b.prefs.codegen.target = "cython"
source = b.PoissonGroup(3, rates=2500*b.Hz)
monitor = b.SpikeMonitor(source)
network = b.Network(source, monitor)
network.store("initial")
states, events = [], []
for seed in (101, 101, 102):
    network.restore("initial", restore_random_state=True)
    b.seed(seed)
    initial = study.rng_hash()
    network.run(2*b.ms)
    states.append((initial, study.rng_hash()))
    events.append((monitor.i[:].tolist(), (monitor.t[:]/b.ms).tolist()))
assert states[0] == states[1]
assert events[0] == events[1] and len(events[0][0]) > 0
assert states[0] != states[2]
'''
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


def test_random_input_audit_keeps_exact_state_and_event_requirements() -> None:
    rows = [dict(protocol=[prefix, "AB"], rng_initial_sha256="initial", rng_final_sha256="final",
                 injected_test_events_sha256="same") for prefix in ("off", "A", "B")]
    study.audit_rows(rows, history=True)
    rows[1]["injected_test_events_sha256"] = "different"
    with pytest.raises(ValueError, match="identical final stimuli"):
        study.audit_rows(rows, history=True)
    rows[1]["injected_test_events_sha256"] = "same"
    rows[1]["rng_final_sha256"] = "different"
    with pytest.raises(ValueError, match="consumption differs"):
        study.audit_rows(rows, history=True)
    rows[1]["rng_final_sha256"] = "final"
    rows[1]["rng_initial_sha256"] = "different"
    with pytest.raises(ValueError, match="consumption differs"):
        study.audit_rows(rows, history=True)


def test_history_timing_and_holm_are_frozen() -> None:
    from flyonenomics.drive.paired_inputs import trial_segments
    assert trial_segments("5b", ("A", "AB"), dict(settle_s=2, prefix_s=5, gap_s=1, test_s=14)) == [
        ("settle", "off", 2), ("prefix", "A", 5), ("gap", "off", 1), ("test", "AB", 14)]
    assert study.DURATION == 22
    np.testing.assert_allclose(analysis.holm(np.array([0.04, 0.01])), [0.04, 0.02])
    assert analysis.sign_p(np.zeros(10)) == 1
    assert analysis.sign_p(np.ones(10)) == 2 / 1024
