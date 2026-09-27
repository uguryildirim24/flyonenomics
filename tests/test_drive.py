"""Small deterministic WP3 contracts; no Brian2 networks are built here."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from flyonenomics.drive import background as bg
from flyonenomics.validation.artefacts import (
    FanoAccumulator, encoder_permutation_detector, fano_factor_detector,
    weight_jitter_detector,
)


class FakeEngine:
    """Monotone rates with a synchronous infeasible region; units mV/Hz."""

    n = 300

    def __init__(self) -> None:
        self.thresholds: list[np.ndarray] = []
        self.gains: list[np.ndarray] = []
        self.weights = np.zeros(self.n)
        self.step = 0
        self.restores = 0

    def restore(self, key: str) -> None:
        """Reset fake time; units chunks, shape scalar."""
        assert key == "initial"
        self.step = 0
        self.restores += 1

    def seed(self, seed: int) -> None:
        """Accept uint32 seed; units none, shape scalar."""
        assert 0 <= seed < 2**32

    def set_threshold(self, values: np.ndarray) -> None:
        """Record fixed mV array; shape (n,)."""
        self.thresholds.append(values.copy())

    def set_gain(self, values: np.ndarray) -> None:
        """Record fixed gain array; shape (n,)."""
        self.gains.append(values.copy())

    def set_background(self, values: np.ndarray) -> None:
        """Set mV array; shape (n,)."""
        self.weights = values.copy()

    def run_chunk(self, ms: float) -> SimpleNamespace:
        """Return deterministic fake counts; units spikes, shape (n,) and (10,)."""
        assert ms == 10
        self.step += 1
        counts = np.zeros(self.n, dtype=np.int32)
        for start, end, optimum, target in ((0, 100, 0.7, 2.0), (100, 200, 0.7, 2.0)):
            rate = target * self.weights[start] / optimum
            offset = np.arange(end - start) / (end - start)
            before = np.floor((self.step - 1) * rate / 100 + offset)
            after = np.floor(self.step * rate / 100 + offset)
            counts[start:end] = (after - before).astype(np.int32)
        hist = np.full(10, 0, dtype=np.int32)
        if self.weights[0] >= 0.95:
            hist[0] = 100
        else:
            hist[:min(10, int(counts.sum()))] = 1
        return SimpleNamespace(counts=counts, hist_1ms=hist)


def test_k1_fixed_arrays_cap_and_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """K1 preserves tonic arrays, respects cap, and rejects a Fano trip."""
    indices = {"a": np.arange(0, 100), "b": np.arange(100, 200),
               "sensory": np.arange(200, 300)}
    monkeypatch.setattr(bg, "group_indices", lambda registry: indices)
    engine = FakeEngine()
    registry = SimpleNamespace(n=300)
    threshold = np.full(300, -45.0)
    threshold[:100] += 1.5  # constructed nonzero tonic offset
    gain = np.ones(300)
    gain[100:200] = 1.2
    original_th, original_gain = threshold.copy(), gain.copy()
    result = bg.calibrate(engine, registry, {"a": 2.0, "b": 2.0}, 20260912, 18,
                          threshold, gain)
    assert result.evaluation_count <= 18
    assert engine.restores == result.evaluation_count
    assert len(engine.thresholds) == result.evaluation_count
    assert all(np.array_equal(v, original_th) for v in engine.thresholds)
    assert all(np.array_equal(v, original_gain) for v in engine.gains)
    assert np.array_equal(threshold, original_th)
    assert np.array_equal(gain, original_gain)
    assert abs(result.groups["a"].w_bg - 0.7) < 0.07
    assert abs(result.groups["b"].w_bg - 0.7) < 0.07
    assert result.synchrony["status"] == "clear"
    assert "caller" in result.calibration_state
    assert np.array_equal(engine.thresholds[-1], original_th)


def test_fano_known_inputs() -> None:
    """Independent Poisson is clear, bursts trip, silence is unknown."""
    rng = np.random.default_rng(np.random.SeedSequence(20260912, spawn_key=(0, 0, 6)))
    poisson = rng.poisson(10, size=10_000)
    accumulator = FanoAccumulator(1000)
    for block in np.split(poisson, 10):
        accumulator.add(block)
    report = accumulator.report()
    assert report["status"] == "clear"
    assert abs(float(report["F"]) - 1) < 0.1
    burst = np.zeros(1000, dtype=np.int32)
    burst[::100] = 100
    burst_report = fano_factor_detector(burst, 1000)
    assert burst_report["status"] == "tripped"
    assert burst_report["F"] == pytest.approx(99)
    assert burst_report["max_bin_fraction"] == pytest.approx(.1)
    assert fano_factor_detector(np.zeros(1000), 1000)["status"] == "unknown"


def test_robustness_hooks() -> None:
    """Derived jitter and encoder reruns report sign changes and counts."""
    jitter = weight_jitter_detector(lambda scale: {"effect": float(scale.mean() - 2)},
                                    20, {"effect": 1.0}, 20260912)
    assert len(jitter["reruns"]) == 5
    assert jitter["sign_changes"]["effect"]
    permutation = encoder_permutation_detector(
        lambda order: {"effect": float(order[0] - 2)}, 4, {"effect": 1.0}, 20260912)
    assert len(permutation["reruns"]) == 3


def test_background_weights_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expand group weights to registry order; units mV, shape (n,)."""
    monkeypatch.setattr(bg, "group_indices", lambda registry: {
        "central": np.array([0, 2]), "sensory": np.array([1])})
    drive = bg.DriveTable(drive_version="dev", configuration_class="development",
        groups={"central": bg.DriveGroup(size=2, w_bg=0.5, target_hz=1, measured_hz=1),
                "sensory": bg.DriveGroup(size=1, w_bg=0, target_hz=None, measured_hz=0)},
        objective=0, evaluation_count=1, seed=20260912, date="2026-09-12",
        params_version="v0.1", receptor_map_version="v0.1",
        arrays_note="base arrays, layer A off", calibration_state=bg.CALIBRATION_STATE,
        qualified=False, synchrony={"status": "clear", "F": 1.0, "max_bin_fraction": 0.01},
        misses=[], wall_s=1)
    assert np.array_equal(bg.background_weights(SimpleNamespace(n=3), drive), [0.5, 0, 0.5])
    assert np.array_equal(bg.background_weights(SimpleNamespace(n=3), drive.model_dump()), [0.5, 0, 0.5])
    assert drive.g_inh == 1
    assert drive.model_copy(update={"g_inh": 4}).model_dump()["g_inh"] == 4
    with pytest.raises(Exception):
        bg.DriveTable.model_validate({**drive.model_dump(), "g_inh": 0.9})
    with pytest.raises(Exception):
        bg.DriveGroup(size=1, w_bg=2.1, target_hz=1, measured_hz=1)
    with pytest.raises(Exception):
        bg.DriveGroup(size=1, w_bg=0.1, target_hz=1, measured_hz=1, extra=1)


def test_inhibitory_weight_scale() -> None:
    """Only negative signed connections get g_inh; units ratio, shape (n_syn,)."""
    signs = np.array([-2, 0, 3, -1], dtype=np.float64)
    result = bg.weight_scale(signs, 3)
    assert result.dtype == np.float32
    assert np.array_equal(result, [3, 1, 1, 3])
    assert np.array_equal(bg.weight_scale(signs, 1), np.ones(4))
    with pytest.raises(ValueError):
        bg.weight_scale(signs, 0.9)


def test_k1b_uses_mapped_start_and_fixed_arrays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mapped-ratio K1 preserves tonic arrays and converges within its evaluation cap."""
    indices = {"a": np.arange(0, 100), "b": np.arange(100, 200),
               "sensory": np.arange(200, 300)}
    monkeypatch.setattr(bg, "group_indices", lambda registry: indices)
    engine = FakeEngine()
    threshold = np.full(300, -45.0)
    threshold[:100] += 1.5
    gain = np.ones(300)
    gain[100:200] = 1.2
    result = bg._calibrate_k1b(engine, SimpleNamespace(n=300), {"a": 2.0, "b": 2.0},
                               20260912, 12, threshold, gain, 0.65, 4.0)
    assert result.g_inh == 4
    assert result.evaluation_count <= 12
    assert abs(result.groups["a"].w_bg - 0.7) < 0.07
    assert abs(result.groups["b"].w_bg - 0.7) < 0.07
    assert all(np.array_equal(values, threshold) for values in engine.thresholds)
    assert all(np.array_equal(values, gain) for values in engine.gains)
    assert engine.restores == result.evaluation_count


@pytest.mark.parametrize("keys", [(0, 0, 0), (20260912, 0, 0), (4294967295, 31, 9)])
def test_seed_derivation_equality(keys: tuple[int, int, int]) -> None:
    from flyonenomics.types import ENGINE
    def _stream(S, s, k, component):
        return np.random.default_rng(np.random.SeedSequence(S, spawn_key=(s, k, component)))
    def _brian_seed(S, s, k):
        return int(np.random.SeedSequence(S, spawn_key=(s, k, ENGINE)).generate_state(1, dtype=np.uint32)[0])
    from flyonenomics.orchestrator.seeds import stream, brian_seed
    from flyonenomics.types import ENGINE, BEHAVIOUR, ENCODER, JITTER, LIVE, ANALYSIS
    assert _brian_seed(*keys) == brian_seed(*keys)
    for component in (ENGINE, BEHAVIOUR, ENCODER, JITTER, LIVE, ANALYSIS):
        assert np.array_equal(_stream(*keys, component).bytes(256), stream(*keys, component).bytes(256))


@pytest.mark.parametrize("entry", ["_measure_2_2", "_measure_2_3"])
def test_ten_second_recording_follows_unrecorded_settle(monkeypatch: pytest.MonkeyPatch, entry: str) -> None:
    from flyonenomics.validation import level2
    calls = []
    engine = SimpleNamespace(n=1000)
    params = bg.load_params()
    monkeypatch.setattr(level2, "_engine", lambda: (engine, None, params))
    monkeypatch.setattr(level2, "_prepare", lambda *args: None)
    def run(engine, params, seconds, detector=None):
        calls.append((seconds, detector is not None))
        if detector is not None:
            detector.add(np.tile([9, 11], 5000))
        return np.full(1000, 10)
    monkeypatch.setattr(level2, "_run", run)
    measured = getattr(level2, entry)()["measured"]
    assert calls == [(float(params.get("settle.min_s")), False), (10., entry == "_measure_2_3")]
    assert measured["settle_s"] == 2 and measured["record_s"] == 10


def test_map_pair_requires_both_next_grid_comparisons() -> None:
    from flyonenomics.drive.k1b_study import qualifying_pairs
    def row(rate):
        return {"rates_hz": {"central": rate}, "amended_point_candidate": True}
    assert qualifying_pairs([row(1), row(2)]) == []
    assert qualifying_pairs([row(1), row(2), row(6)]) == []
    assert len(qualifying_pairs([row(1), row(2), row(5.9)])) == 1


def test_jitter_uses_named_stream_and_param_sigma() -> None:
    from flyonenomics.orchestrator.seeds import stream
    from flyonenomics.types import JITTER, load_params
    params = load_params()
    seen = []
    weight_jitter_detector(lambda scale: seen.append(scale.copy()) or {"effect": 1.}, 1000, {"effect": 1.}, 20260912, params)
    sigma = params.get("artefact.jitter_sigma")
    for j, scale in enumerate(seen):
        expected = stream(20260912, 0, j, JITTER).lognormal(-sigma*sigma/2, sigma, size=1000).astype(np.float32)
        assert np.array_equal(scale, expected)


def test_scaled_inhibitory_weight_survives_real_restore() -> None:
    import subprocess, sys
    code = """
import numpy as np
from pathlib import Path
import tempfile
import pandas as pd
from brian2 import mV
from flyonenomics.engine import BrianEngine, InputTopology
from flyonenomics.types import ConnectomeFiles, load_params
from flyonenomics.drive.background import weight_scale
p = Path('tests/fixtures/engine')
temporary = tempfile.TemporaryDirectory()
connectivity = Path(temporary.name)/'tiny_signed.parquet'
frame = pd.read_parquet(p/'tiny_connectivity.parquet')
frame.loc[frame.index[0], 'Excitatory x Connectivity'] *= -1
frame.to_parquet(connectivity)
e = BrianEngine()
e.build(ConnectomeFiles(p/'tiny_completeness.csv', connectivity, version='630'), load_params(), InputTopology(background=True))
base = np.asarray(e._syn.w[:]/mV).copy()
assert np.any(base < 0)
e.set_background(np.full(e.n, .2))
e.set_weight_scale(weight_scale(base, 4))
e.store('initial')
e.set_weight_scale(np.ones(e.n_syn, dtype=np.float32))
e.restore('initial')
assert np.array_equal(np.asarray(e._syn.w[:]/mV), base*weight_scale(base, 4))
assert np.all(np.asarray(e._neu.w_bg_i[:]/mV)==.2)
"""
    proc = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_k1_rejects_synchronous_candidate_even_at_zero_rate_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An apparently perfect rate fit cannot override a synchrony trip."""
    indices = {"a": np.arange(100), "b": np.arange(100, 200), "sensory": np.arange(200, 300)}
    monkeypatch.setattr(bg, "group_indices", lambda registry: indices)
    class TrapEngine(FakeEngine):
        def run_chunk(self, ms: float) -> SimpleNamespace:
            result = super().run_chunk(ms)
            if self.weights[0] >= .95:
                result.counts[:] = 0
                result.counts[[0, 1, 100, 101]] = 1  # exactly 2 Hz in both target groups
            return result
    result = bg.calibrate(TrapEngine(), SimpleNamespace(n=300), {"a": 2., "b": 2.},
                          20260912, 8, np.full(300, -45.), np.ones(300))
    assert result.evaluation_count == 8
    assert result.objective > 0  # zero-error .95 mV candidate was infeasible
    assert result.groups["a"].w_bg < .95 and result.synchrony["status"] == "clear"
