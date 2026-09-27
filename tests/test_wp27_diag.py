"""WP27 experiment-1 diagnostics: analysis, packing, collector. No Brian2 engine."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from flyonenomics.drive.rest_map import (
    DIAG_BLOCK_ORDER,
    _json_safe,
    _probe,
    covariance_decomposition,
    diag_sample_indices,
    disjoint_diag_blocks,
    fano_at_bins,
    fano_from_counts,
    median_rate_22r,
    shuffle_block_fano,
)
from flyonenomics.drive.rest_tier3 import (
    CLOSEST_3D_ID,
    WP27_CAP_USD,
    WP27_MAX_JOBS,
    closest_3d_unit,
    collect_diag,
    t2_reflex_probe,
    wp27_list_usd,
    wp27_plan_record,
    wp27_wave_tasks,
)


def test_probe_source_has_no_instrumentation() -> None:
    """Scoring _probe stays a separate function from the diagnostic probe."""
    source = inspect.getsource(_probe)
    assert "_instrumented_probe" not in source
    assert "analyse_spike_windows" not in source
    assert "disjoint_diag_blocks" not in source
    assert "settle 2 s, measure" in _probe.__doc__


def test_instrumented_t1_window_starts_after_two_second_settle() -> None:
    """T1-comparable fields use [2, 12), the same settle as `_probe`."""
    from flyonenomics.drive.rest_map import _instrumented_probe

    source = inspect.getsource(_instrumented_probe)
    assert "settle_chunks = 2 * chunks_second" in source
    assert "settle_chunks <= pos < settle_chunks + t1_chunks" in source
    assert "chunks_second <= pos < chunks_second + t1_chunks" not in source


def test_fano_from_counts_and_bins() -> None:
    """Independent 0/1 counts give F near 1; coarser bins stay defined."""
    rng = np.random.default_rng(0)
    counts = rng.binomial(20, 0.1, size=10000)
    f1 = fano_from_counts(counts)
    assert f1 is not None and 0.8 < f1 < 1.3
    bins = fano_at_bins(counts)
    assert list(bins) == ["1", "5", "10", "50", "100"]
    assert all(v is None or v >= 0 for v in bins.values())
    assert fano_from_counts(np.zeros(10)) is None


def test_median_rate_22r_bounds() -> None:
    """2.2r passes inside [0.2, 5] Hz with almost no 50 Hz cells."""
    rates = np.full(100, 1.0)
    ok = median_rate_22r(rates)
    assert ok["passed"] is True
    low = median_rate_22r(np.full(100, 0.05))
    assert low["passed"] is False
    hot = np.full(100, 1.0)
    hot[:5] = 60.0
    assert median_rate_22r(hot)["passed"] is False


def test_covariance_decomposition_separates_shared_from_independent() -> None:
    """Identical spike trains put variance in the covariance term."""
    n_bins = 8000
    p = 0.2
    rng = np.random.default_rng(1)
    shared = (rng.random(n_bins) < p).astype(np.float64)
    other = (rng.random(n_bins) < p).astype(np.float64)
    pop = shared + shared
    totals = np.array([shared.sum(), shared.sum()])
    block_1ms = {"A": shared, "B": shared}
    block_neuron = {"A": totals[:1], "B": totals[1:]}
    coupled = covariance_decomposition(pop, block_1ms, totals, block_neuron, n_bins)
    assert coupled["F"] is not None and coupled["F"] > 1.4
    assert coupled["covariance_term"] == pytest.approx(coupled["independent"], rel=0.05)
    assert coupled["covariance_term"] > 0
    assert coupled["pairs"]["A:B"] > 0
    pop_i = shared + other
    totals_i = np.array([shared.sum(), other.sum()])
    independent = covariance_decomposition(
        pop_i, {"A": shared, "B": other}, totals_i, {"A": totals_i[:1], "B": totals_i[1:]}, n_bins,
    )
    assert independent["covariance_term"] < coupled["covariance_term"]


def test_shuffle_block_fano_breaks_synchrony() -> None:
    """Permuting inside 100 ms blocks drops shared-bin F."""
    n_ms = 1000
    idx = np.array([0, 1] * 50, dtype=np.int32)
    ms = np.repeat(np.arange(0, 1000, 20, dtype=np.int64), 2)
    original = fano_from_counts(np.bincount(ms, minlength=n_ms))
    shuffled = shuffle_block_fano(idx, ms, n_ms, rng=0)
    assert original is not None and shuffled is not None
    assert shuffled < original


def test_disjoint_diag_blocks_partition(monkeypatch) -> None:
    """MN9, APL, DAN, KC, optic, central, rest are exclusive and cover n."""
    n = 12

    class Pop:
        def __init__(self, idx):
            self.idx = np.array(idx, dtype=np.int32)

    class Registry:
        n = 12

        def population(self, name):
            return Pop([0] if name == "MN9" else [])

    class Series:
        def __init__(self, values):
            self._values = values

        def fillna(self, _value):
            return self

        def to_numpy(self, dtype=str):
            return np.array(self._values, dtype=dtype)

    class Frame(dict):
        pass

    hemibrain = ["x", "APL"] + ["x"] * 10
    annotations = Frame(hemibrain_type=Series(hemibrain))

    monkeypatch.setattr(
        "flyonenomics.drive.background.group_indices",
        lambda _reg: {
            "DAN": np.array([2, 3], dtype=np.int32),
            "KC": np.array([4, 5], dtype=np.int32),
            "optic": np.array([6, 7], dtype=np.int32),
            "central": np.array([8, 9, 10], dtype=np.int32),
        },
    )
    monkeypatch.setattr(
        "flyonenomics.substrate.transmitters.annotations_in_engine",
        lambda: (annotations, np.arange(n)),
    )
    blocks = disjoint_diag_blocks(Registry())
    assert list(blocks) == list(DIAG_BLOCK_ORDER)
    assigned = np.concatenate([blocks[name] for name in DIAG_BLOCK_ORDER])
    assert sorted(assigned.tolist()) == list(range(n))
    assert blocks["MN9"].tolist() == [0]
    assert blocks["APL"].tolist() == [1]
    assert blocks["rest"].tolist() == [11]
    sample = diag_sample_indices(blocks, n, seed=20260912)
    assert sample["trace_idx"].size <= 20
    assert sample["central_sample"].size == 3


def test_json_safe_rejects_nan() -> None:
    """Diagnostic JSON has no NaN."""
    payload = _json_safe({"a": np.float64(1.5), "b": float("nan"), "c": [np.int64(3)]})
    json.dumps(payload, allow_nan=False)
    assert payload["b"] is None
    assert payload["c"] == [3]


def test_wp27_wave_fits_two_boxes_and_cap() -> None:
    """Experiments 1 and 2 pack into two IBM jobs under $15 list."""
    packed = wp27_wave_tasks()
    assert packed["launch"] is True
    assert packed["reason"] is None
    assert packed["n_jobs"] == WP27_MAX_JOBS
    assert packed["list_usd"] <= WP27_CAP_USD
    assert packed["candidate_id"] == CLOSEST_3D_ID
    job0, job1 = packed["jobs"]
    kinds0 = {t["kind"] for t in job0}
    assert kinds0 == {"diag-long", "diag-sugar", "diag-ff", "bare"}
    assert sum(1 for t in job0 if t["kind"] == "diag-long") == 12
    kinds1 = {t["kind"] for t in job1}
    assert "t1" in kinds1 and "unit" in kinds1 and "sigma-sugar" in kinds1 and "bare" in kinds1
    assert closest_3d_unit()["g_gaba_kc"] == 6.0
    assert wp27_list_usd(packed["jobs"]) == pytest.approx(packed["list_usd"])
    plan = wp27_plan_record()
    assert "jobs" not in plan
    assert plan["launch"] is True
    assert plan["n_jobs"] == 2
    assert plan["list_usd"] <= WP27_CAP_USD
    assert plan["pack_worker_s_per_brain_s"] == 75.0
    json.dumps(plan, allow_nan=False)


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


def test_collect_diag_flags_diagnostic_and_admits_nothing(tmp_path: Path) -> None:
    """Collector writes both reflex verdicts and admits nothing."""
    out = tmp_path / "job0"
    tasks = []
    window = {
        "early": {
            "median_22r": {"median_hz": 0.1, "fraction_above_50_hz": 0.0, "passed": False},
            "F_bins": {"1": 3.1},
        },
        "late": {
            "median_22r": {"median_hz": 0.1, "fraction_above_50_hz": 0.0, "passed": False},
            "F_bins": {"1": 2.8},
        },
    }
    for i, (clamp, weight, seed) in enumerate(
        (c, w, s) for c in (True, False) for w in (0.85, 0.90) for s in (1, 2, 3)
    ):
        name = f"long-{i}.ndjson"
        path = out / name
        _write_ndjson(path, [{
            "seed": seed, "w_bg": weight, "F": 3.1, "pools": "clamped" if clamp else "free",
            "windows": window, "mn9_hz": 2.0,
        }])
        tasks.append({"kind": "diag-long", "path": str(path), "clamp": clamp, "w_bg": weight, "seed": seed})
    for weight in (0.85, 0.90):
        name = f"sugar-{weight}.ndjson"
        path = out / name
        evals = [{"seed": seed, "w_bg": weight, "difference_hz": 10.0 + seed} for seed in range(1, 11)]
        _write_ndjson(path, evals)
        tasks.append({"kind": "diag-sugar", "path": str(path), "w_bg": weight})
    ff_path = out / "ff.ndjson"
    _write_ndjson(ff_path, [{"seed": seed, "difference_hz": 31.0} for seed in range(1, 11)])
    tasks.append({"kind": "diag-ff", "path": str(ff_path)})
    bare_path = out / "bare.ndjson"
    _write_ndjson(bare_path, [{"seed": seed, "difference_hz": 56.0} for seed in range(1, 11)])
    tasks.append({"kind": "bare", "path": str(bare_path), "job_index": 0})
    record = collect_diag([(out, tasks)])
    assert record["admitted_t1"] is False
    assert record["admitted_t2"] is False
    assert "diagnostic" in record["flags"]
    assert record["diagnostic"] is True
    reflex = record["reflex"]
    assert reflex["diagnostic"] is True
    assert "reflex_verdicts" in reflex
    assert reflex["reflex_verdicts"]["original"]["mean_hz"] == 50.0
    assert reflex["reflex_verdicts"]["harmonised"]["mean_hz"] == pytest.approx(28.0)
    assert record["median_22r"]["passed"] is False
    assert record["candidate_id"] == CLOSEST_3D_ID


def test_t2_reflex_probe_both_verdicts_on_weak_ab() -> None:
    """Item 74 keeps original fail and may pass the 28.0/22.4 floors."""
    a = [23.0] * 6
    b = [29.0] * 10
    c = [31.3] * 10
    bare = [56.0] * 10
    scored = t2_reflex_probe(
        a, b, {"upstream": c, "extended": c}, {"upstream": bare, "extended": bare},
        sub_tier="T3d", job_bare_mean=56.0,
    )
    assert scored["reflex_verdicts"]["original"]["reflex_passed"] is False
    assert scored["reflex_verdicts"]["harmonised"]["mean_hz"] == pytest.approx(28.0)
    assert scored["reflex_verdicts"]["harmonised"]["seed_min_hz"] == pytest.approx(22.4)
    assert scored["reflex_verdicts"]["harmonised"]["reflex_passed"] is True


def test_item_74_fails_when_one_of_six_a_seeds_is_3_hz() -> None:
    """(a) is the min of six pair-weight seeds; a 3 Hz seed fails 22.4 Hz."""
    a = [31.0, 35.0, 30.0, 36.0, 83.0, 3.0]
    b = [31.0, 35.0, 30.0, 32.0, 31.0, 34.0, 27.0, 29.0, 38.0, 29.0]
    c = [31.3] * 10
    bare = [56.0] * 10
    scored = t2_reflex_probe(
        a, b, {"upstream": c, "extended": c}, {"upstream": bare, "extended": bare},
        sub_tier="T3d", job_bare_mean=56.0,
    )
    assert min(a) == 3.0
    assert min(b) >= 22.4 and sum(b) / 10 > 28.0
    assert scored["reflex_verdicts"]["original"]["reflex_passed"] is False
    assert scored["reflex_verdicts"]["harmonised"]["reflex_passed"] is False
    assert scored["reflex_harmonised"] is False
    assert "reflex-harmonised" not in (scored.get("flags") or [])
