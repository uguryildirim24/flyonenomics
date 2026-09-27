"""Item 88 3c timestep-convergence: selection, plan, verdict, collect. No engine."""

from __future__ import annotations

import json
from pathlib import Path

from flyonenomics.drive.rest_tier3 import (
    T3C_CONVERGENCE_REQUIRED_ID,
    T3C_CONVERGENCE_SEED,
    cbi_stiff,
    collect_t3c_convergence,
    dt_ms_tag,
    recorded_lif_dt_ms,
    select_t3c_convergence_units,
    t0_flags,
    t0_unit_id,
    t3c_convergence_plan,
    t3c_dt_verdict,
)

ROOT = Path(__file__).resolve().parents[1]
T0_PATH = ROOT / "validation" / "records" / "p2" / "rest-T3c-T0.json"


def _t0() -> dict:
    return json.loads(T0_PATH.read_text())


def _write_task(path: Path, *, kind: str, dt_ms: float, difference_hz: float,
                unit: dict | None = None, h_max: float | None = None, wall_s: float = 1.0) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "kind": "evaluation",
            "seed": T3C_CONVERGENCE_SEED,
            "difference_hz": difference_hz,
            "dt_ms": dt_ms,
            "unit": unit,
            "job_id": "t3c-dt-test",
            **({"h_max": h_max} if h_max is not None else {}),
        },
        {"kind": "task-complete", "wall_s": wall_s, "wall_per_brain_s": wall_s / 6.0, "brain_s": 6.0},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return {"path": str(path), "kind": kind, "dt_ms": dt_ms, "unit": unit}


def test_required_unit_id_matches_t0_closest_miss() -> None:
    closest = _t0()["closest_t0"]
    assert t0_unit_id(closest) == T3C_CONVERGENCE_REQUIRED_ID
    assert T3C_CONVERGENCE_REQUIRED_ID == "1.0-1.0-cbi--72.0-all"


def test_selects_five_units_spanning_recorded_h_max() -> None:
    units = select_t3c_convergence_units(_t0())
    assert len(units) == 5
    assert units[0]["unit_id"] == T3C_CONVERGENCE_REQUIRED_ID
    h_vals = [float(u["recorded_h_max"]) for u in units]
    all_h = [float(u["h_max"]) for u in _t0()["units"] if not u.get("baseline")]
    assert min(h_vals) == min(all_h)
    assert max(h_vals) == max(all_h)
    assert units[0]["recorded_retention"] == _t0()["closest_t0"]["retention"]
    ids = [u["unit_id"] for u in units]
    assert len(set(ids)) == 5
    assert all("why" in u and u["why"] for u in units)


def test_plan_is_one_seed_three_steps_same_job_bare() -> None:
    plan = t3c_convergence_plan(_t0())
    dt = recorded_lif_dt_ms()
    assert dt == 0.1
    assert plan["steps_ms"] == [dt, dt / 2.0, dt / 4.0]
    assert plan["seed"] == 1
    assert plan["n_units"] == 5
    assert plan["n_tasks"] == 18
    assert plan["t0_brain_s"] == 108
    assert plan["item"] == 88
    assert "No T0 readmission" in plan["note"]
    tasks = plan["jobs"][0]
    bares = [t for t in tasks if t["kind"] == "bare"]
    units = [t for t in tasks if t["kind"] == "unit"]
    assert len(bares) == 3
    assert len(units) == 15
    assert {t["dt_ms"] for t in bares} == set(plan["steps_ms"])
    assert all(t["seeds"] == [1] for t in tasks)
    assert all(t["unit"] is None for t in bares)
    assert all(t["unit"]["unit_id"] for t in units)


def test_cbi_stiff_clears_at_half_step_for_closest_miss() -> None:
    h_max = 19.65
    assert cbi_stiff(h_max)
    assert "cbi-stiff" in t0_flags(h_max=h_max)
    assert not cbi_stiff(h_max, dt_ms=0.05)
    assert "cbi-stiff" not in t0_flags(h_max=h_max, dt_ms=0.05)
    assert not cbi_stiff(h_max, dt_ms=0.025)


def test_verdict_numerical_physical_mixed() -> None:
    numerical = [
        {"dt_ms": 0.1, "retention": 0.60, "difference_hz": 34.0},
        {"dt_ms": 0.05, "retention": 0.61, "difference_hz": 34.2},
        {"dt_ms": 0.025, "retention": 0.62, "difference_hz": 34.4},
    ]
    physical = [
        {"dt_ms": 0.1, "retention": 0.04, "difference_hz": 2.0},
        {"dt_ms": 0.05, "retention": 0.03, "difference_hz": 8.0},
        {"dt_ms": 0.025, "retention": 0.02, "difference_hz": 20.0},
    ]
    mixed = [
        {"dt_ms": 0.1, "retention": 0.61, "difference_hz": 34.0},
        {"dt_ms": 0.05, "retention": 0.04, "difference_hz": 2.0},
        {"dt_ms": 0.025, "retention": 0.04, "difference_hz": 2.1},
    ]
    assert t3c_dt_verdict(numerical) == "numerical"
    assert t3c_dt_verdict(physical) == "physical"
    assert t3c_dt_verdict(mixed) == "mixed"


def test_collect_uses_same_dt_bare_and_does_not_readmit(tmp_path: Path) -> None:
    unit = select_t3c_convergence_units(_t0())[0]
    tasks = []
    for dt, diff, h_max, wall in (
        (0.1, 34.1, 19.65, 10.0),
        (0.05, 34.2, 19.65, 20.0),
        (0.025, 34.4, 19.65, 40.0),
    ):
        tasks.append(_write_task(
            tmp_path / f"unit-{dt_ms_tag(dt)}.ndjson",
            kind="unit", dt_ms=dt, difference_hz=diff, unit=unit, h_max=h_max, wall_s=wall,
        ))
        tasks.append(_write_task(
            tmp_path / f"bare-{dt_ms_tag(dt)}.ndjson",
            kind="bare", dt_ms=dt, difference_hz=56.0, wall_s=wall * 0.5,
        ))
    summary = collect_t3c_convergence(tmp_path, tasks)
    assert summary["readmission"] is False
    assert summary["n_units"] == 1
    assert summary["n_rows"] == 3
    assert summary["overall_verdict"] == "numerical"
    row = summary["units"][0]
    assert row["unit_id"] == T3C_CONVERGENCE_REQUIRED_ID
    assert row["verdict"] == "numerical"
    steps = {float(s["dt_ms"]): s for s in row["steps"]}
    assert steps[0.1]["retention"] == 34.1 / 56.0
    assert "cbi-stiff" in steps[0.1]["flags"]
    assert "cbi-stiff" not in steps[0.05]["flags"]
    assert steps[0.1]["wall_s"] == 10.0
    assert steps[0.025]["wall_s"] == 40.0


def test_dt_ms_tag() -> None:
    assert dt_ms_tag(0.1) == "dt100"
    assert dt_ms_tag(0.05) == "dt050"
    assert dt_ms_tag(0.025) == "dt025"
