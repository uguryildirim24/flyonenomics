"""WP30 3e sensory freeze packer and collector. No Brian2 engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from flyonenomics.drive.rest_map import TARGETS
from flyonenomics.drive.rest_tier3e import (
    WP30_CANDIDATE_WEIGHTS,
    WP30_CAP_USD,
    WP30_MAX_JOBS,
    WP30_PASSER_ID,
    WP30_PERTURB_SEEDS,
    WP30_SEEDS,
    collect_t3e_freeze,
    t3e_freeze_plan_record,
    t3e_freeze_unit,
    t3e_freeze_wave_tasks,
    wp30_pair_weights,
    wp30_perturb_union,
    wp30_run_weights,
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


def test_pair_of_the_passer_is_the_3e_pair() -> None:
    """Weight 1.0 keeps the arm A pair 1.0/1.2 mV."""
    assert wp30_pair_weights(1.0) == (1.0, 1.2)
    assert wp30_pair_weights(0.9) == (0.9, 1.1)
    assert wp30_pair_weights(1.1) == (1.1, 1.3)
    assert wp30_run_weights() == (0.9, 1.0, 1.1, 1.2, 1.3)
    unit = t3e_freeze_unit()
    assert unit["arm"]["bg_policy"] == "sens"
    from flyonenomics.drive.rest_tier3 import candidate_id
    unit["w_bg"] = 1.0
    assert candidate_id(unit) == WP30_PASSER_ID


def test_freeze_wave_fits_one_box_and_cap() -> None:
    """Item 120 packs into one IBM job under $8 list."""
    packed = t3e_freeze_wave_tasks()
    assert packed["launch"] is True
    assert packed["reason"] is None
    assert packed["n_jobs"] == WP30_MAX_JOBS
    assert packed["list_usd"] <= WP30_CAP_USD
    assert packed["engine_usd"] <= WP30_CAP_USD
    assert packed["candidate_id"] == WP30_PASSER_ID
    job = packed["jobs"][0]
    longs = [t for t in job if t["kind"] == "diag-long"]
    assert len(longs) == len(wp30_run_weights()) * len(WP30_SEEDS)
    assert {int(t["seed"]) for t in longs} == set(WP30_SEEDS)
    assert {round(float(t["w_bg"]), 8) for t in longs} == set(wp30_run_weights())
    assert all(t.get("clamp") is True for t in longs)
    assert all(t.get("pools") == "clamped" for t in longs)
    sugars = [t for t in job if t["kind"] == "diag-sugar"]
    assert len(sugars) == len(wp30_run_weights())
    assert {tuple(t["seeds"]) for t in sugars} == {WP30_SEEDS}
    pert = [t for t in job if t["kind"] == "t1"]
    assert len(pert) == len(WP30_PERTURB_SEEDS)
    probes = {round(float(w), 8) for t in pert for w, _seed in t["probes"]}
    assert probes == set(wp30_perturb_union())
    assert any(t["kind"] == "bare" and t.get("job_index") == 0 for t in job)
    assert any(t["kind"] == "diag-ff" for t in job)
    plan = t3e_freeze_plan_record()
    assert plan["stage"] == "freeze"
    assert plan["wave"] == "wp30"
    assert "jobs" not in plan
    assert plan["launch"] is True
    json.dumps(plan, allow_nan=False)


def test_collect_freeze_can_rank_a_weight(tmp_path: Path) -> None:
    """A quiet ten-seed pair that clears item 74 ranks; others are recorded."""
    out = tmp_path / "job0"
    tasks = []
    rates = {**TARGETS, "central": 5.5, "DAN": 1.0, "KC": 0.25}
    lab = {
        "single_unit_fano_100ms_mean": 0.4,
        "mean_pairwise_corr_50ms_mean": 1e-5,
        "pca_participation_ratio": 18.0,
        "fano_n_scored": 200,
        "fano_n_silent": 1800,
    }
    for weight in wp30_run_weights():
        for seed in WP30_SEEDS:
            name = f"long-clamped-w{int(round(weight * 100)):03d}-s{seed}.ndjson"
            path = out / name
            _write_ndjson(path, [{
                "seed": seed, "w_bg": weight, "F": 2.4, "b": 0.002,
                "stability_ratio": 1.0, "pools": "clamped",
                "mn9_hz": 1.0, "rates_hz": rates, "lab": lab,
            }])
            tasks.append({
                "kind": "diag-long", "path": str(path), "clamp": True,
                "w_bg": weight, "seed": seed,
            })
    for weight in wp30_run_weights():
        path = out / f"sugar-w{int(round(weight * 100)):03d}.ndjson"
        evals = [
            {
                "seed": seed, "w_bg": weight, "difference_hz": 33.0,
                "mn9_dark_hz": 1.0, "silent": {"mn9_hz": 1.0},
            }
            for seed in WP30_SEEDS
        ]
        _write_ndjson(path, evals)
        tasks.append({"kind": "diag-sugar", "path": str(path), "w_bg": weight})
    ff_path = out / "ff.ndjson"
    _write_ndjson(ff_path, [{"seed": seed, "difference_hz": 31.0} for seed in WP30_SEEDS])
    tasks.append({"kind": "diag-ff", "path": str(ff_path)})
    bare_path = out / "bare.ndjson"
    _write_ndjson(bare_path, [{"seed": seed, "difference_hz": 56.0} for seed in WP30_SEEDS])
    tasks.append({"kind": "bare", "path": str(bare_path), "job_index": 0})
    for seed in WP30_PERTURB_SEEDS:
        path = out / f"pert-s{seed}.ndjson"
        evals = [
            {
                "seed": seed, "w_bg": weight, "F": 2.4, "b": 0.002,
                "stability_ratio": 1.0, "rates_hz": rates,
            }
            for weight in wp30_perturb_union()
        ]
        _write_ndjson(path, evals)
        tasks.append({"kind": "t1", "path": str(path), "seed": seed})
    record = collect_t3e_freeze([(out, tasks)])
    assert record["admitted_t1"] is False
    assert record["admitted_t2"] is False
    assert record["diagnostic"] is False
    assert record["partial"] is False
    assert record["p2_partial_b"] is False
    assert set(record["ranked"]) == {
        "1.0-4.0-0.0-False-100-0.9-kc-6.0-sens",
        "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens",
        "1.0-4.0-0.0-False-100-1.1-kc-6.0-sens",
    }
    best = record["ranked_rows"][0]
    assert best["reflex_verdicts"]["harmonised"]["mean_hz"] == pytest.approx(28.0)
    assert best["reflex_verdicts"]["harmonised"]["seed_min_hz"] == pytest.approx(22.4)
    assert min(best["b_hz"]) >= 22.4
    assert best["mn9_dark_every_seed_under_5"] is True
    assert record["t0"]["t0_passed"] is True


def test_collect_freeze_fails_when_only_min_b_is_under_floor(tmp_path: Path) -> None:
    """Item 74 (b) needs min(b) at 0.4 of the same-job bare (decision 113)."""
    out = tmp_path / "job0"
    tasks = []
    rates = {**TARGETS, "central": 5.5, "DAN": 1.0, "KC": 0.25}
    lab = {
        "single_unit_fano_100ms_mean": 0.4,
        "mean_pairwise_corr_50ms_mean": 1e-5,
        "pca_participation_ratio": 18.0,
        "fano_n_scored": 200,
        "fano_n_silent": 1800,
    }
    for weight in wp30_run_weights():
        for seed in WP30_SEEDS:
            name = f"long-clamped-w{int(round(weight * 100)):03d}-s{seed}.ndjson"
            path = out / name
            _write_ndjson(path, [{
                "seed": seed, "w_bg": weight, "F": 2.4, "b": 0.002,
                "stability_ratio": 1.0, "pools": "clamped",
                "mn9_hz": 1.0, "rates_hz": rates, "lab": lab,
            }])
            tasks.append({
                "kind": "diag-long", "path": str(path), "clamp": True,
                "w_bg": weight, "seed": seed,
            })
    for weight in wp30_run_weights():
        path = out / f"sugar-w{int(round(weight * 100)):03d}.ndjson"
        evals = []
        for seed in WP30_SEEDS:
            hz = 22.0 if round(float(weight), 8) == 1.0 and seed == 20 else 33.0
            evals.append({
                "seed": seed, "w_bg": weight, "difference_hz": hz,
                "mn9_dark_hz": 1.0, "silent": {"mn9_hz": 1.0},
            })
        _write_ndjson(path, evals)
        tasks.append({"kind": "diag-sugar", "path": str(path), "w_bg": weight})
    ff_path = out / "ff.ndjson"
    _write_ndjson(ff_path, [{"seed": seed, "difference_hz": 31.0} for seed in WP30_SEEDS])
    tasks.append({"kind": "diag-ff", "path": str(ff_path)})
    bare_path = out / "bare.ndjson"
    _write_ndjson(bare_path, [{"seed": seed, "difference_hz": 56.0} for seed in WP30_SEEDS])
    tasks.append({"kind": "bare", "path": str(bare_path), "job_index": 0})
    for seed in WP30_PERTURB_SEEDS:
        path = out / f"pert-s{seed}.ndjson"
        evals = [
            {
                "seed": seed, "w_bg": weight, "F": 2.4, "b": 0.002,
                "stability_ratio": 1.0, "rates_hz": rates,
            }
            for weight in wp30_perturb_union()
        ]
        _write_ndjson(path, evals)
        tasks.append({"kind": "t1", "path": str(path), "seed": seed})
    record = collect_t3e_freeze([(out, tasks)])
    passer = "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
    assert record["partial"] is False
    assert passer not in record["ranked"]
    row = next(r for r in record["weights"] if r["candidate_id"] == passer)
    assert min(row["a_hz"]) >= 22.4
    assert sum(row["b_hz"]) / 10 > 28.0
    assert min(row["b_hz"]) < 22.4
    assert row["reflex_harmonised"] is False
    assert row["ranked_here"] is False


def _pair_only_job(
    tmp_path: Path,
    *,
    candidate: float,
    sugar_hz,
) -> tuple[Path, list[dict]]:
    """Long and sugar rows for one candidate pair, plus shared bare, T0, and pert."""
    out = tmp_path / "job0"
    tasks: list[dict] = []
    rates = {**TARGETS, "central": 5.5, "DAN": 1.0, "KC": 0.25}
    lab = {
        "single_unit_fano_100ms_mean": 0.4,
        "mean_pairwise_corr_50ms_mean": 1e-5,
        "pca_participation_ratio": 18.0,
        "fano_n_scored": 200,
        "fano_n_silent": 1800,
    }
    pair = wp30_pair_weights(candidate)
    for weight in pair:
        for seed in WP30_SEEDS:
            name = f"long-clamped-w{int(round(weight * 100)):03d}-s{seed}.ndjson"
            path = out / name
            _write_ndjson(path, [{
                "seed": seed, "w_bg": weight, "F": 2.4, "b": 0.002,
                "stability_ratio": 1.0, "pools": "clamped",
                "mn9_hz": 1.0, "rates_hz": rates, "lab": lab,
            }])
            tasks.append({
                "kind": "diag-long", "path": str(path), "clamp": True,
                "w_bg": weight, "seed": seed,
            })
    for weight in pair:
        path = out / f"sugar-w{int(round(weight * 100)):03d}.ndjson"
        evals = []
        for seed in WP30_SEEDS:
            hz = sugar_hz(weight, seed)
            evals.append({
                "seed": seed, "w_bg": weight, "difference_hz": hz,
                "mn9_dark_hz": 1.0, "silent": {"mn9_hz": 1.0},
            })
        _write_ndjson(path, evals)
        tasks.append({"kind": "diag-sugar", "path": str(path), "w_bg": weight})
    ff_path = out / "ff.ndjson"
    _write_ndjson(ff_path, [{"seed": seed, "difference_hz": 31.0} for seed in WP30_SEEDS])
    tasks.append({"kind": "diag-ff", "path": str(ff_path)})
    bare_path = out / "bare.ndjson"
    _write_ndjson(bare_path, [{"seed": seed, "difference_hz": 56.0} for seed in WP30_SEEDS])
    tasks.append({"kind": "bare", "path": str(bare_path), "job_index": 0})
    for seed in WP30_PERTURB_SEEDS:
        path = out / f"pert-s{seed}.ndjson"
        evals = [
            {
                "seed": seed, "w_bg": weight, "F": 2.4, "b": 0.002,
                "stability_ratio": 1.0, "rates_hz": rates,
            }
            for weight in wp30_perturb_union()
        ]
        _write_ndjson(path, evals)
        tasks.append({"kind": "t1", "path": str(path), "seed": seed})
    return out, tasks


def test_collect_freeze_partial_weight_can_rank(tmp_path: Path) -> None:
    """A 1.0-only collect ranks that weight and does not require 0.9 or 1.1."""
    out, tasks = _pair_only_job(
        tmp_path, candidate=1.0, sugar_hz=lambda _weight, _seed: 33.0,
    )
    with pytest.raises(ValueError, match="freeze screen missing"):
        collect_t3e_freeze([(out, tasks)])
    record = collect_t3e_freeze([(out, tasks)], candidate_weights=(1.0,))
    passer = "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
    assert record["partial"] is True
    assert record["candidate_weights"] == [1.0]
    assert record["ranked"] == [passer]
    assert record["p2_partial_b"] is False
    assert record["failed_stage"] is None


def test_collect_freeze_partial_fail_does_not_close_p2(tmp_path: Path) -> None:
    """A 1.0-only miss cannot close the search; 0.9 and 1.1 are still not scored."""
    def sugar_hz(weight: float, seed: int) -> float:
        if round(float(weight), 8) == 1.0 and seed == 20:
            return 22.0
        return 33.0

    out, tasks = _pair_only_job(tmp_path, candidate=1.0, sugar_hz=sugar_hz)
    record = collect_t3e_freeze([(out, tasks)], candidate_weights=(1.0,))
    passer = "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
    assert record["partial"] is True
    assert passer not in record["ranked"]
    assert record["p2_partial_b"] is False
    row = next(r for r in record["weights"] if r["candidate_id"] == passer)
    assert min(row["b_hz"]) < 22.4
    assert row["ranked_here"] is False


def test_t3e_freeze_unit_has_no_mechanism_section() -> None:
    """T3e is lif. The arm is applied in _maybe_apply_arm, not BLOCK_NAME."""
    from flyonenomics.drive.rest_tier3 import resolve_unit_mechanisms, section_for_unit

    unit = t3e_freeze_unit()
    assert unit["sub_tier"] == "T3e"
    assert unit.get("setting")
    assert section_for_unit(unit) is None
    mechs, section = resolve_unit_mechanisms(unit)
    assert mechs is None
    assert section is None
