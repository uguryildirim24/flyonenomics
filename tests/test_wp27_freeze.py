"""WP27 experiment-4 freeze packer and collector. No Brian2 engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flyonenomics.drive.rest_map import TARGETS
from flyonenomics.drive.rest_tier3 import (
    FREEZE_ID,
    FREEZE_PAIR_WEIGHTS,
    FREEZE_PERTURB_SEEDS,
    FREEZE_PERTURB_WEIGHTS,
    FREEZE_SEEDS,
    WP27_FREEZE_CAP_USD,
    WP27_FREEZE_MAX_JOBS,
    WP27_SCORED_WINDOW,
    candidate_id,
    collect_freeze,
    freeze_unit,
    overlay_window_f_mn9,
    wp27_freeze_plan_record,
    wp27_freeze_wave_tasks,
    wp27_wave_tasks,
)


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


def test_freeze_id_matches_item_90_contender() -> None:
    """The freeze unit is the sigma_th 1 pair 0.75/0.80 passer."""
    unit = freeze_unit()
    assert candidate_id(unit) == FREEZE_ID
    assert unit["sigma_th"] == 1.0
    assert unit["w_bg"] == 0.75
    assert unit["pair_weights"] == [0.75, 0.80]
    assert unit["g_gaba_kc"] == 6.0


def test_freeze_wave_fits_one_box_and_cap() -> None:
    """Experiment 4 packs into one IBM job under $10 list."""
    packed = wp27_freeze_wave_tasks()
    assert packed["launch"] is True
    assert packed["reason"] is None
    assert packed["n_jobs"] == WP27_FREEZE_MAX_JOBS
    assert packed["list_usd"] <= WP27_FREEZE_CAP_USD
    assert packed["candidate_id"] == FREEZE_ID
    job = packed["jobs"][0]
    longs = [t for t in job if t["kind"] == "diag-long"]
    assert len(longs) == 40
    seeds = {int(t["seed"]) for t in longs}
    assert seeds == set(FREEZE_SEEDS)
    weights = {round(float(t["w_bg"]), 8) for t in longs}
    assert weights == {round(float(w), 8) for w in FREEZE_PAIR_WEIGHTS}
    pools = {(t["clamp"], t["pools"]) for t in longs}
    assert pools == {(True, "clamped"), (False, "free")}
    sugars = [t for t in job if t["kind"] == "diag-sugar"]
    assert len(sugars) == 2
    assert {tuple(t["seeds"]) for t in sugars} == {FREEZE_SEEDS}
    pert = [t for t in job if t["kind"] == "t1"]
    assert len(pert) == 3
    assert {int(t["seed"]) for t in pert} == set(FREEZE_PERTURB_SEEDS)
    probes = {round(float(w), 8) for t in pert for w, _seed in t["probes"]}
    assert probes == {round(float(w), 8) for w in FREEZE_PERTURB_WEIGHTS}
    assert any(t["kind"] == "bare" and t.get("job_index") == 0 for t in job)
    assert any(t["kind"] == "diag-ff" for t in job)
    plan = wp27_freeze_plan_record()
    assert plan["stage"] == "freeze"
    assert "jobs" not in plan
    assert plan["launch"] is True
    assert plan["n_jobs"] == 1
    json.dumps(plan, allow_nan=False)


def test_diag_wave_unchanged_by_freeze_packer() -> None:
    """The experiment 1+2 packer still uses two boxes and the old pair."""
    packed = wp27_wave_tasks()
    assert packed["n_jobs"] == 2
    assert packed["candidate_id"] != FREEZE_ID


def test_collect_freeze_flags_diagnostic_and_admits_nothing(tmp_path: Path) -> None:
    """Collector writes both reflex verdicts and admits nothing."""
    out = tmp_path / "job0"
    tasks = []
    window = {
        "early": {
            "median_22r": {"median_hz": 0.0, "fraction_above_50_hz": 0.0, "passed": False},
            "F_bins": {"1": 2.8},
            "mn9_hz": 2.0,
        },
        "late": {
            "median_22r": {"median_hz": 0.0, "fraction_above_50_hz": 0.0, "passed": False},
            "F_bins": {"1": 2.7},
            "mn9_hz": 2.1,
        },
    }
    rates = {**TARGETS, "central": 5.5, "DAN": 1.0, "KC": 0.25}
    for clamp in (True, False):
        pools = "clamped" if clamp else "free"
        for weight in FREEZE_PAIR_WEIGHTS:
            for seed in FREEZE_SEEDS:
                name = f"long-{pools}-w{int(weight * 100):03d}-s{seed}.ndjson"
                path = out / name
                _write_ndjson(path, [{
                    "seed": seed, "w_bg": weight, "F": 2.8, "b": 0.002,
                    "stability_ratio": 1.0, "pools": pools, "windows": window,
                    "mn9_hz": 2.0, "rates_hz": rates,
                }])
                tasks.append({
                    "kind": "diag-long", "path": str(path), "clamp": clamp,
                    "w_bg": weight, "seed": seed,
                })
    for weight in FREEZE_PAIR_WEIGHTS:
        path = out / f"sugar-w{int(weight * 100):03d}.ndjson"
        evals = [{"seed": seed, "w_bg": weight, "difference_hz": 20.0} for seed in FREEZE_SEEDS]
        _write_ndjson(path, evals)
        tasks.append({"kind": "diag-sugar", "path": str(path), "w_bg": weight})
    ff_path = out / "ff.ndjson"
    _write_ndjson(ff_path, [{"seed": seed, "difference_hz": 31.0} for seed in FREEZE_SEEDS])
    tasks.append({"kind": "diag-ff", "path": str(ff_path)})
    bare_path = out / "bare.ndjson"
    _write_ndjson(bare_path, [{"seed": seed, "difference_hz": 56.0} for seed in FREEZE_SEEDS])
    tasks.append({"kind": "bare", "path": str(bare_path), "job_index": 0})
    for seed in FREEZE_PERTURB_SEEDS:
        path = out / f"pert-s{seed}.ndjson"
        evals = [
            {
                "seed": seed, "w_bg": weight, "F": 2.8, "b": 0.002,
                "stability_ratio": 1.0, "rates_hz": rates,
            }
            for weight in FREEZE_PERTURB_WEIGHTS
        ]
        _write_ndjson(path, evals)
        tasks.append({"kind": "t1", "path": str(path), "seed": seed})
    record = collect_freeze([(out, tasks)])
    assert record["admitted_t1"] is False
    assert record["admitted_t2"] is False
    assert record["diagnostic"] is True
    assert record["candidate_id"] == FREEZE_ID
    assert record["screen_holds"] is True
    assert record["perturbation"]["holds"] is True
    reflex = record["reflex"]
    assert reflex["diagnostic"] is True
    assert "reflex_verdicts" in reflex
    assert reflex["reflex_verdicts"]["original"]["mean_hz"] == 50.0
    assert reflex["reflex_verdicts"]["harmonised"]["mean_hz"] == pytest.approx(28.0)
    assert record["a_hz"] == [20.0] * 6
    assert record["b_hz"] == [20.0] * 10
    assert record["scored_window"] == WP27_SCORED_WINDOW
    assert record["long"][0]["F_recorded"] == 2.8
    assert record["long"][0]["F"] == 2.8
    assert record["long"][0]["mn9_hz"] == 2.0
    assert record["long"][0]["mn9_hz_recorded"] == 2.0


def test_overlay_window_f_mn9_falls_back_to_npz(tmp_path: Path) -> None:
    """npz sidecar is the WP16-logged fallback when windows.early is missing."""
    import numpy as np

    from flyonenomics.drive.rest_map import fano_from_counts

    counts = np.zeros((7, 13000), dtype=np.int64)
    counts[:, 2000:12000] = 1
    mn9 = np.zeros(13000, dtype=np.float64)
    mn9[2000:2020] = 1.0
    npz = tmp_path / "sidecar.npz"
    np.savez_compressed(npz, block_1ms=counts, mn9_1ms=mn9)
    row = overlay_window_f_mn9({"F": 9.2, "mn9_hz": 47.5, "npz": str(npz)})
    assert row["F_recorded"] == 9.2
    assert row["F"] == pytest.approx(fano_from_counts(counts[:, 2000:12000].sum(axis=0)))
    assert row["mn9_hz_recorded"] == 47.5
    assert row["mn9_hz"] == pytest.approx(2.0)
    assert row["f_mn9_rescore_source"] == "npz"


def test_overlay_window_f_mn9_uses_early_bins() -> None:
    """Decision 95: [2, 12) F_bins and mn9 replace the live [1, 11) fields."""
    row = overlay_window_f_mn9({
        "F": 9.2,
        "mn9_hz": 47.5,
        "windows": {
            "early": {"F_bins": {"1": 2.8}, "mn9_hz": 54.1},
        },
    })
    assert row["F_recorded"] == 9.2
    assert row["F"] == 2.8
    assert row["mn9_hz_recorded"] == 47.5
    assert row["mn9_hz"] == 54.1
    assert row["F_scored_window"] == WP27_SCORED_WINDOW
    assert row["f_mn9_rescore_source"] == "windows.early"


def test_collect_freeze_screen_uses_rescored_f(tmp_path: Path) -> None:
    """A live [1, 11) F over 3 still passes the freeze screen on [2, 12)."""
    out = tmp_path / "job0"
    tasks = []
    window = {
        "early": {
            "median_22r": {"median_hz": 0.0, "fraction_above_50_hz": 0.0, "passed": False},
            "F_bins": {"1": 2.8},
            "mn9_hz": 1.5,
        },
        "late": {
            "median_22r": {"median_hz": 0.0, "fraction_above_50_hz": 0.0, "passed": False},
            "F_bins": {"1": 2.7},
            "mn9_hz": 1.6,
        },
    }
    rates = {**TARGETS, "central": 5.5, "DAN": 1.0, "KC": 0.25}
    for clamp in (True, False):
        pools = "clamped" if clamp else "free"
        for weight in FREEZE_PAIR_WEIGHTS:
            for seed in FREEZE_SEEDS:
                name = f"long-{pools}-w{int(weight * 100):03d}-s{seed}.ndjson"
                path = out / name
                _write_ndjson(path, [{
                    "seed": seed, "w_bg": weight, "F": 9.2, "b": 0.002,
                    "stability_ratio": 1.0, "pools": pools, "windows": window,
                    "mn9_hz": 47.5, "rates_hz": rates,
                }])
                tasks.append({
                    "kind": "diag-long", "path": str(path), "clamp": clamp,
                    "w_bg": weight, "seed": seed,
                })
    for weight in FREEZE_PAIR_WEIGHTS:
        path = out / f"sugar-w{int(weight * 100):03d}.ndjson"
        evals = [{"seed": seed, "w_bg": weight, "difference_hz": 20.0} for seed in FREEZE_SEEDS]
        _write_ndjson(path, evals)
        tasks.append({"kind": "diag-sugar", "path": str(path), "w_bg": weight})
    ff_path = out / "ff.ndjson"
    _write_ndjson(ff_path, [{"seed": seed, "difference_hz": 31.0} for seed in FREEZE_SEEDS])
    tasks.append({"kind": "diag-ff", "path": str(ff_path)})
    bare_path = out / "bare.ndjson"
    _write_ndjson(bare_path, [{"seed": seed, "difference_hz": 56.0} for seed in FREEZE_SEEDS])
    tasks.append({"kind": "bare", "path": str(bare_path), "job_index": 0})
    for seed in FREEZE_PERTURB_SEEDS:
        path = out / f"pert-s{seed}.ndjson"
        evals = [
            {
                "seed": seed, "w_bg": weight, "F": 2.8, "b": 0.002,
                "stability_ratio": 1.0, "rates_hz": rates,
            }
            for weight in FREEZE_PERTURB_WEIGHTS
        ]
        _write_ndjson(path, evals)
        tasks.append({"kind": "t1", "path": str(path), "seed": seed})
    record = collect_freeze([(out, tasks)])
    assert record["screen_holds"] is True
    assert record["screen"]["measured_F_max_pair"] == pytest.approx(2.8)
    assert record["long"][0]["F_recorded"] == 9.2
    assert record["long"][0]["mn9_hz"] == 1.5
