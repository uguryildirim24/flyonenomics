"""WP27 experiment-2 sigma grid: packing and collector. No Brian2 engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flyonenomics.drive.rest_map import TARGETS
from flyonenomics.drive.rest_tier3 import (
    SIGMA_TH_GRID,
    SIGMA_WEIGHTS,
    closest_3d_unit,
    collect_sigma,
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


def _screen_evals(*, f: float, central: float = 1.0, kc: float = 0.1) -> list[dict]:
    rows = []
    for weight in SIGMA_WEIGHTS:
        for seed in (1, 2, 3):
            rows.append({
                "w_bg": float(weight),
                "seed": seed,
                "F": f,
                "b": 0.002,
                "stability_ratio": 1.0,
                "rates_hz": {**TARGETS, "central": central, "DAN": 1.0, "KC": kc},
            })
    return rows


def test_sigma_tasks_cover_grid_and_grade_point() -> None:
    """Experiment 2 screens 0.75 to 1.00 mV at four sigma values."""
    packed = wp27_wave_tasks()
    job1 = packed["jobs"][1]
    screens = [t for t in job1 if t["kind"] == "t1"]
    assert len(screens) == 12
    weights = {round(float(w), 8) for t in screens for w, _seed in t["probes"]}
    assert weights == {round(float(w), 8) for w in SIGMA_WEIGHTS}
    assert 1.0 in weights
    sigmas = {round(float(t["unit"]["sigma_th"]), 8) for t in screens}
    assert sigmas == {round(float(s), 8) for s in SIGMA_TH_GRID}
    t0 = [t for t in job1 if t["kind"] == "unit"]
    assert len(t0) == 4


def test_collect_sigma_empty_ranked_keeps_closest_miss(tmp_path: Path) -> None:
    """A failing F grid admits nothing and records S, F, KC, central."""
    out = tmp_path / "job1"
    tasks = []
    for sigma in SIGMA_TH_GRID:
        unit = closest_3d_unit(sigma_th=sigma)
        for seed in (1, 2, 3):
            path = out / f"sigma{sigma}-s{seed}.ndjson"
            evals = [row for row in _screen_evals(f=4.0) if row["seed"] == seed]
            _write_ndjson(path, evals, extra={"unit": unit, "sigma_th": sigma})
            tasks.append({
                "kind": "t1", "path": str(path), "unit": unit, "sigma_th": sigma, "seed": seed,
            })
        t0_path = out / f"sigma{sigma}-t0.ndjson"
        _write_ndjson(t0_path, [{"seed": seed, "difference_hz": 31.3} for seed in range(1, 11)])
        tasks.append({"kind": "unit", "path": str(t0_path), "unit": unit, "sigma_th": sigma})
    bare = out / "bare.ndjson"
    _write_ndjson(bare, [{"seed": seed, "difference_hz": 56.0} for seed in range(1, 11)])
    tasks.append({"kind": "bare", "path": str(bare), "job_index": 1})
    record = collect_sigma([(out, tasks)])
    assert record["admitted_t1"] is False
    assert record["admitted_t2"] is False
    assert record["ranked"] == []
    assert record["failed_stage"] == "R-screen"
    miss = record["closest_miss"]
    assert miss is not None
    assert miss["S"] > 0
    assert miss["measured_F_max_pair"] == pytest.approx(4.0)
    assert miss["measured_kc_hz_mean"] == pytest.approx(0.1)
    assert miss["measured_central_hz_mean"] == pytest.approx(1.0)
    assert all(row["t0_passed"] for row in record["t0"])


def test_collect_sigma_item_74_fails_on_3_hz_pair_seed(tmp_path: Path) -> None:
    """A screen passer with a_hz min 3 Hz fails item 74; (b) would pass alone."""
    out = tmp_path / "job1"
    tasks = []
    for sigma in SIGMA_TH_GRID:
        unit = closest_3d_unit(sigma_th=sigma)
        f = 2.9 if sigma == 1.0 else 4.0
        for seed in (1, 2, 3):
            path = out / f"sigma{sigma}-s{seed}.ndjson"
            evals = [row for row in _screen_evals(f=f) if row["seed"] == seed]
            _write_ndjson(path, evals, extra={"unit": unit, "sigma_th": sigma})
            tasks.append({
                "kind": "t1", "path": str(path), "unit": unit, "sigma_th": sigma, "seed": seed,
            })
        t0_path = out / f"sigma{sigma}-t0.ndjson"
        _write_ndjson(t0_path, [{"seed": seed, "difference_hz": 31.3} for seed in range(1, 11)])
        tasks.append({"kind": "unit", "path": str(t0_path), "unit": unit, "sigma_th": sigma})
        diffs_by_w = {
            0.75: [31.0, 35.0, 30.0, 32.0, 31.0, 34.0, 27.0, 29.0, 38.0, 29.0],
            0.80: [36.0, 83.0, 3.0, 4.0, -4.0, -20.0, 35.0, 36.0, 83.0, -45.0],
            0.85: [20.0] * 10,
            0.90: [20.0] * 10,
            0.95: [20.0] * 10,
        }
        for weight, diffs in diffs_by_w.items():
            path = out / f"sigma{sigma}-sugar-{weight}.ndjson"
            evals = [{"seed": seed, "w_bg": weight, "difference_hz": diffs[seed - 1]}
                     for seed in range(1, 11)]
            _write_ndjson(path, evals, extra={"unit": unit, "sigma_th": sigma, "w_bg": weight})
            tasks.append({
                "kind": "sigma-sugar", "path": str(path), "unit": unit,
                "w_bg": weight, "sigma_th": sigma,
            })
    bare = out / "bare.ndjson"
    _write_ndjson(bare, [{"seed": seed, "difference_hz": 56.0} for seed in range(1, 11)])
    tasks.append({"kind": "bare", "path": str(bare), "job_index": 1})
    record = collect_sigma([(out, tasks)])
    ranked = [row for row in record["ranked"] if row["candidate_id"].startswith("1.0-4.0-1.0")]
    assert ranked
    first = next(row for row in ranked if row["w_bg"] == 0.75)
    reflex = first["reflex"]
    assert reflex["a_hz"] == [31.0, 35.0, 30.0, 36.0, 83.0, 3.0]
    assert reflex["b_hz"][0] == 31.0 and min(reflex["b_hz"]) == 27.0
    assert reflex["reflex_verdicts"]["harmonised"]["job_bare_mean"] == pytest.approx(56.0)
    assert reflex["reflex_verdicts"]["harmonised"]["reflex_passed"] is False
    assert reflex["reflex_harmonised"] is False
    assert record["admitted_t2"] is False
