"""Tier-3 rest search: T0 to T2, admission, order key, decision (SPEC-P2 2.6 step 6).

Pure decisions import no engine. Rates are Hz, strengths in the sub-tier's
units, windows seconds.
"""

from __future__ import annotations

import itertools
import json
import math
import statistics
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from flyonenomics.drive.mechanisms import (
    engine_model_of,
    mechanisms_from_unit,
    mechanisms_section,
)
from flyonenomics.drive.rest_map import (
    CAP,
    SEEDS,
    Setting,
    WEIGHTS,
    long_decision,
    number,
    reflex_decision,
    screen_candidate,
    violation,
)
from flyonenomics.io import load_npy, read_text, read_yaml
from flyonenomics.types import load_params

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "data" / "rest-tier3-v0.2.yaml"
Q_PLAN = 27.0
T2_BRAIN_S = 9760.0
T2_REFLEX_BRAIN_S = 6.0
T2_LONG_BRAIN_S = 32.0
T2_TASKS_PER_CANDIDATE = 36
T2_BARE_PER_JOB = 10
T2_CANDIDATE_BRAIN_S = 476.0
T1_BRAIN_S_PER_UNIT = 19 * 3 * 12
T0_BRAIN_S_PER_TASK = 60.0
# T1 10 s probes on IBM t3b-t1-00 ran near 75 wall-s per brain-s. Packing
# still uses the T0 smoke 45.75. Slice width uses this so one T1 task fits
# REST_TIMEOUT_S 9000.
T3D_T1_SLICE_WORKER_S = 75.0
T0_TASK_KINDS = frozenset({"unit", "bare", "baseline"})
LONG_SEEDS = tuple(range(1, 11))
SUB_TIERS = ("T3a", "T3b", "T3c", "T3d")
ENGINE_MODEL = {"T3a": "lif+sfa", "T3b": "lif+std", "T3c": "lif+cbi", "T3d": "lif", "T3e": "lif"}
BLOCK_NAME = {"T3a": "adaptation", "T3b": "depression", "T3c": "conductance_inhibition"}
STAGE_DEPTH = {"T0": 1, "T1": 2, "T2": 3, "Q-rest": 4}
ORIGINAL_REFLEX_MEAN_HZ = 50.0
ORIGINAL_REFLEX_SEED_MIN_HZ = 40.0
HARMONISED_REFLEX_MEAN_HZ = 28.0
HARMONISED_REFLEX_SEED_MIN_HZ = 22.0
HARMONISED_REFLEX_MEAN_FRAC = 0.5
HARMONISED_REFLEX_SEED_FRAC = 0.4
FF_RETENTION_MIN = 0.5
SFA_RHO_FALLBACK = 1.4863463034318214
T3C_CONVERGENCE_REQUIRED_ID = "1.0-1.0-cbi--72.0-all"
T3C_CONVERGENCE_SEED = 1
T3C_CONVERGENCE_N_UNITS = 5
T3C_DT_RETENTION_TOL = 0.05
T3C_DT_DIFF_TOL_HZ = 2.0
T3C_T1_DT_MS = 0.05
# dt=0.05 T0 measured ~59 wall-s/brain-s; pack T1 slices so one task fits IBM timeout.
T3C_T1_PACK_RATE = 150.0
T3C_T1_RECORD = "validation/records/p2/rest-T3c-T1.json"
T3C_T2_RECORD = "validation/records/p2/rest-T3c-T2.json"
T3C_T0_RECORD = "validation/records/p2/rest-T3c-T0.json"
T3C_DECISION_RECORD = "validation/records/p2/rest-T3c-decision.json"
WP27_PACK_RATE = 75.0
WP27_LONG_RATE = 90.0
WP27_USD_PER_H = 2.2
WP27_CAP_USD = 15.0
WP27_MAX_JOBS = 2
WP27_FREEZE_CAP_USD = 10.0
WP27_FREEZE_MAX_JOBS = 1
DIAG_LONG_S = 32.0
DIAG_SUGAR_MEASURE_S = 3.0
DIAG_SUGAR_ENGINE_S = 5.0
DIAG_PAIR_WEIGHTS = (0.85, 0.90)
SIGMA_TH_GRID = (0.0, 0.5, 1.0, 2.0)
SIGMA_WEIGHTS = (0.75, 0.80, 0.85, 0.90, 0.95, 1.00)
CLOSEST_3D_ID = "1.0-4.0-0.0-False-100-0.85-kc-6.0"
FREEZE_ID = "1.0-4.0-1.0-False-100-0.75-kc-6.0"
FREEZE_SIGMA_TH = 1.0
FREEZE_W_BG = 0.75
FREEZE_PAIR_WEIGHTS = (0.75, 0.80)
FREEZE_SEEDS = tuple(range(11, 21))
FREEZE_PERTURB_SEEDS = (11, 12, 13)
FREEZE_PERTURB_WEIGHTS = (0.70, 0.75, 0.80)
WP27_SCORED_WINDOW = "[2, 12)"
WP27_SCORED_START_MS = 2000
WP27_SCORED_STOP_MS = 12000


@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> dict[str, Any]:
    """Load rest-tier3-v0.2.yaml. Units: per row."""
    record = read_yaml(path or CONFIG_PATH)
    if not isinstance(record, dict):
        raise ValueError("tier-3 configuration must be a mapping")
    return record


def _v0() -> float:
    return float(load_params().get("lif.v_0"))


def pairs() -> list[tuple[float, float]]:
    """P3 scale pairs. Units: ratios."""
    return [(float(a), float(b)) for a, b in load_config()["tier3"]["pairs"]]


def baseline_pairs() -> list[tuple[float, float]]:
    """P3 pairs with g_gaba <= 2. Units: ratios."""
    return [(float(a), float(b)) for a, b in load_config()["tier3"]["baseline_pairs"]]


def sfa_grid() -> list[dict[str, Any]]:
    """3a settings. Units: b_mv mV, tau_ms ms."""
    row = load_config()["tier3"]["sfa"]
    return [
        {"b_mv": float(b), "tau_ms": float(tau), "scope": str(row["scope"])}
        for b, tau in itertools.product(row["b_mv"], row["tau_ms"])
    ]


def std_grid() -> list[dict[str, Any]]:
    """3b settings. Units: U dimensionless, tau_ms ms."""
    row = load_config()["tier3"]["std"]
    return [
        {"scope": str(scope), "U": float(u), "tau_ms": float(tau)}
        for scope, u, tau in itertools.product(row["scope"], row["U"], row["tau_ms"])
    ]


def cbi_grid() -> list[dict[str, Any]]:
    """3c settings. Units: E_inh_mv mV."""
    row = load_config()["tier3"]["cbi"]
    return [{"E_inh_mv": float(e), "scope": str(row["scope"])} for e in row["E_inh_mv"]]


def gaba_kc_pairs() -> list[tuple[float, float]]:
    """3d scale pairs. Units: ratios."""
    return [(float(a), float(b)) for a, b in load_config()["tier3"]["gaba_kc"]["pairs"]]


def gaba_kc_grid() -> list[dict[str, Any]]:
    """3d settings: g_gaba_kc and optional 3a block. Units: ratio, mV, ms."""
    row = load_config()["tier3"]["gaba_kc"]
    out: list[dict[str, Any]] = []
    for sfa in row["sfa"]:
        for g_kc in row["g_gaba_kc"]:
            setting: dict[str, Any] = {"g_gaba_kc": float(g_kc)}
            if sfa is not None:
                setting["b_mv"] = float(sfa["b_mv"])
                setting["tau_ms"] = float(sfa["tau_ms"])
                setting["scope"] = str(sfa["scope"])
            out.append(setting)
    return out


def grid_of(sub_tier: str) -> list[dict[str, Any]]:
    """Mechanism settings of one sub-tier."""
    if sub_tier == "T3a":
        return sfa_grid()
    if sub_tier == "T3b":
        return std_grid()
    if sub_tier == "T3c":
        return cbi_grid()
    if sub_tier == "T3d":
        return gaba_kc_grid()
    raise ValueError(f"unknown sub-tier {sub_tier}")


def grid_extremes(sub_tier: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Weakest then strongest grid settings by M, then parameter order."""
    ordered = sorted(
        grid_of(sub_tier),
        key=lambda setting: (mechanism_strength(sub_tier, setting), *parameter_tuple(sub_tier, setting)),
    )
    return ordered[0], ordered[-1]


def mechanism_strength(sub_tier: str, setting: dict[str, Any]) -> float:
    """M of section 2.6. Units: mV·s (3a), s (3b), 1/mV (3c), 1 (3d/3e)."""
    if sub_tier == "T3a":
        return float(setting["b_mv"]) * float(setting["tau_ms"]) / 1000.0
    if sub_tier == "T3b":
        return float(setting["U"]) * float(setting["tau_ms"]) / 1000.0
    if sub_tier in {"T3d", "T3e"}:
        return float(setting["g_gaba_kc"])
    return 1.0 / (_v0() - float(setting["E_inh_mv"]))


def parameter_tuple(sub_tier: str, setting: dict[str, Any]) -> tuple:
    """Sub-tier parameter order for the tier-3 key."""
    if sub_tier == "T3a":
        return (float(setting["tau_ms"]), float(setting["b_mv"]))
    if sub_tier == "T3b":
        scope_rank = 0 if setting["scope"] == "non_sensory_excitatory" else 1
        return (scope_rank, float(setting["U"]), float(setting["tau_ms"]))
    if sub_tier == "T3d":
        sfa_on = 0 if setting.get("b_mv") is None else 1
        return (
            float(setting["g_gaba_kc"]),
            sfa_on,
            float(setting.get("tau_ms") or 0.0),
            float(setting.get("b_mv") or 0.0),
        )
    if sub_tier == "T3e":
        return (
            float(setting.get("g_gaba_kc") or 0.0),
            str(setting.get("arm_id") or ""),
            float(setting.get("beta") or 0.0),
            float(setting.get("hub_factor") or 0.0),
        )
    return (float(setting["E_inh_mv"]),)


def parsimony(g_gaba: float, g_glu: float) -> float:
    return abs(math.log(g_gaba)) + abs(math.log(g_glu))


def tier3_order_key(row: dict[str, Any]) -> tuple:
    """Ascending total order of section 2.6 step 6."""
    s = row.get("S")
    j = row.get("J", 0.0)
    if j is None:
        j = 0.0
    w = row.get("w_bg")
    if s is None or w is None or not all(math.isfinite(float(x)) for x in (s, j, w)):
        raise ValueError("tier-3 order key needs finite S, J and w_bg")
    sub = row.get("sub_tier", "T3a")
    setting = row.get("setting") or {}
    m = row.get("M")
    if m is None:
        m = mechanism_strength(sub, setting) if setting else 0.0
    j_bin = float(load_config().get("rest", {}).get("j_bin", 0.25))
    return (
        float(s),
        math.floor(float(j) / j_bin),
        parsimony(float(row["g_gaba"]), float(row["g_glu"])),
        float(m),
        float(row["g_gaba"]),
        float(row["g_glu"]),
        * (parameter_tuple(sub, setting) if setting else ()),
        float(w),
    )


def t0_retention(candidate_mean: float, job_bare_mean: float) -> float | None:
    """Extended retention against the same-job bare mean."""
    if not math.isfinite(job_bare_mean) or job_bare_mean == 0:
        return None
    return float(candidate_mean) / float(job_bare_mean)


def t0_passed(retention: float | None, floor: float = 0.5) -> bool:
    return retention is not None and retention >= floor


def t0_flags(
    *,
    job_bare_seeds: list[float] | None = None,
    first_job_bare_seeds: list[float] | None = None,
    bg_off_difference_hz: float | None = None,
    h_max: float | None = None,
    dt_ms: float | None = None,
) -> list[str]:
    """T0 flags. bare-mismatch and t2-b-unreachable are recorded only.
    cbi-stiff makes that evaluation's metrics not computable, so T0 cannot pass.
    """
    flags: list[str] = []
    if job_bare_seeds is not None and first_job_bare_seeds is not None:
        if list(job_bare_seeds) != list(first_job_bare_seeds):
            flags.append("bare-mismatch")
    if bg_off_difference_hz is not None and bg_off_difference_hz < 50:
        flags.append("t2-b-unreachable")
    if h_max is not None and cbi_stiff(h_max, dt_ms=dt_ms):
        flags.append("cbi-stiff")
    return flags


def read_t0_task_rows(path: Path) -> list[dict[str, Any]]:
    """Fail-closed T0 NDJSON reader. Incomplete or error tasks raise."""
    records = [json.loads(line) for line in read_text(path).splitlines() if line.strip()]
    if not records or records[-1].get("kind") != "task-complete":
        raise ValueError(f"incomplete task {path.name}")
    if any(row.get("kind") == "task-error" for row in records):
        raise ValueError(f"task error in {path.name}")
    return records


def task_ndjson_path(out: Path | None, task: dict[str, Any]) -> Path:
    """Prefer the payload path; fall back to the pulled job directory."""
    path = Path(task["path"])
    if path.exists():
        return path
    if out is not None:
        alt = Path(out) / path.name
        if alt.exists():
            return alt
    return path


def _is_t0_task(task: dict[str, Any]) -> bool:
    kind = task.get("kind")
    return kind is None or kind in T0_TASK_KINDS


def collect_t0(
    out: Path,
    tasks: list[dict[str, Any]],
    first_job_bare_seeds: list[float] | None = None,
) -> dict[str, Any]:
    """Same-job retention and T0 flags from one job's NDJSON files.

    When first_job_bare_seeds is omitted, this job is the launch-order first
    job: its bare seeds are the global reference and bare-mismatch cannot fire.
    A later job must pass the first job's per-seed bare differences.
    Mixed T0+T1 wave jobs skip non-T0 kinds.
    """
    evals: list[dict[str, Any]] = []
    rates: list[float] = []
    bare_by_seed: dict[int, float] = {}
    for task in tasks:
        if not _is_t0_task(task):
            continue
        path = task_ndjson_path(out, task)
        rows = read_t0_task_rows(path)
        complete = rows[-1]
        if complete.get("wall_per_brain_s") is not None:
            rates.append(float(complete["wall_per_brain_s"]))
        for row in rows:
            if row.get("kind") != "evaluation":
                continue
            if task["kind"] == "bare":
                bare_by_seed[int(row["seed"])] = float(row["difference_hz"])
            else:
                evals.append(row)
    job_bare = [bare_by_seed[seed] for seed in sorted(bare_by_seed)]
    job_bare_mean = sum(job_bare) / len(job_bare) if job_bare else None
    global_seeds = list(first_job_bare_seeds) if first_job_bare_seeds is not None else list(job_bare)
    global_bare_mean = sum(global_seeds) / len(global_seeds) if global_seeds else None
    units: dict[str, dict[str, Any]] = {}
    for row in evals:
        unit = row.get("unit") or {}
        key = json.dumps(
            {"g_gaba": unit.get("g_gaba"), "g_glu": unit.get("g_glu"),
             "setting": unit.get("setting"), "baseline": unit.get("baseline")},
            sort_keys=True,
        )
        bucket = units.setdefault(key, {"unit": unit, "diffs": [], "a_sfa": [], "h_max": [], "job_id": row.get("job_id")})
        bucket["diffs"].append(float(row["difference_hz"]))
        if row.get("mn9_a_sfa_mv") is not None:
            bucket["a_sfa"].append(float(row["mn9_a_sfa_mv"]))
        if row.get("h_max") is not None:
            bucket["h_max"].append(float(row["h_max"]))
    lines = []
    for bucket in units.values():
        mean = sum(bucket["diffs"]) / len(bucket["diffs"])
        retention = t0_retention(mean, job_bare_mean) if job_bare_mean is not None else None
        h_max = max(bucket["h_max"]) if bucket["h_max"] else None
        flags = t0_flags(
            job_bare_seeds=job_bare or None,
            first_job_bare_seeds=global_seeds or None,
            bg_off_difference_hz=mean,
            h_max=h_max,
        )
        passed = t0_passed(retention) and not bucket["unit"].get("baseline") and "cbi-stiff" not in flags
        lines.append({
            **bucket["unit"],
            "difference_hz": mean,
            "retention": retention,
            "t0_passed": passed,
            "job_bare_mean": job_bare_mean,
            "global_bare_mean": global_bare_mean,
            "job_id": bucket["job_id"],
            "mn9_a_sfa_mv": (sum(bucket["a_sfa"]) / len(bucket["a_sfa"])) if bucket["a_sfa"] else None,
            "h_max": h_max,
            "flags": flags,
            "seeds": len(bucket["diffs"]),
        })
    return {
        "job_bare_mean": job_bare_mean,
        "global_bare_mean": global_bare_mean,
        "job_bare_seeds": job_bare,
        "wall_per_brain_s": rates,
        "units": lines,
    }


def collect_packed_t0(
    jobs: list[tuple[Path, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    """Collect packed T0 jobs in launch order against the first job's bare seeds."""
    summaries: list[dict[str, Any]] = []
    first_seeds: list[float] | None = None
    for out, tasks in jobs:
        summary = collect_t0(out, tasks, first_job_bare_seeds=first_seeds)
        if first_seeds is None:
            first_seeds = list(summary["job_bare_seeds"])
        summaries.append(summary)
    return summaries


def collect_t1(
    jobs: list[tuple[Path, list[dict[str, Any]]]],
    t0_units: list[dict[str, Any]] | None = None,
    *,
    dt_ms: float | None = None,
) -> dict[str, Any]:
    """Score R-screen from packed T1 jobs. Fail-closed. Units: Hz, mV.

    When t0_units is given, T1 rows for a unit that failed T0 are stored
    on disk but not scored. Item 89 scores a T0 failure: omit t0_units.
    dt_ms is the stiffness-cut step (item 89: 0.05 ms).
    """
    allowed = None
    if t0_units is not None:
        allowed = {
            _t1_identity_key(unit)
            for unit in t0_units
            if unit.get("t0_passed") and not unit.get("baseline")
        }
    by_unit: dict[str, dict[str, Any]] = {}
    rates: list[float] = []
    n_tasks = 0
    for out, tasks in jobs:
        for task in tasks:
            if task.get("kind") not in (None, "t1"):
                continue
            n_tasks += 1
            path = task_ndjson_path(out, task)
            rows = read_t0_task_rows(path)
            complete = rows[-1]
            if complete.get("wall_per_brain_s") is not None:
                rates.append(float(complete["wall_per_brain_s"]))
            for row in rows:
                if row.get("kind") != "evaluation":
                    continue
                unit = row.get("unit") or task.get("unit") or {}
                key = json.dumps(_t1_unit(unit), sort_keys=True)
                bucket = by_unit.setdefault(
                    key, {"unit": _t1_unit(unit), "rows": [], "job_ids": set()},
                )
                bucket["rows"].append({
                    "w_bg": row["w_bg"],
                    "seed": row["seed"],
                    "F": row.get("F"),
                    "b": row.get("b"),
                    "stability_ratio": row.get("stability_ratio"),
                    "rates_hz": row.get("rates_hz") or {},
                    "h_max": row.get("h_max"),
                })
                if row.get("job_id") is not None:
                    bucket["job_ids"].add(str(row["job_id"]))
    units_out: list[dict[str, Any]] = []
    all_cands: list[dict[str, Any]] = []
    all_scored: list[dict[str, Any]] = []
    n_edge = 0
    for bucket in by_unit.values():
        if allowed is not None and _t1_identity_key(bucket["unit"]) not in allowed:
            continue
        rows = bucket["rows"]
        expected = len(WEIGHTS) * len(SEEDS)
        if len(rows) != expected:
            raise ValueError(f"unit has {len(rows)} T1 rows, expected {expected}")
        setting = Setting(
            g_gaba=float(bucket["unit"]["g_gaba"]),
            g_glu=float(bucket["unit"]["g_glu"]),
            sigma_th=float(bucket["unit"].get("sigma_th", 0.0)),
            optic_exemption=bool(bucket["unit"].get("optic_exemption", False)),
            n_bg=int(bucket["unit"].get("n_bg", 100)),
            g_gaba_kc=float(bucket["unit"].get("g_gaba_kc", 1.0)),
        )
        scored = []
        for weight in setting.weights[:-2]:
            cand = screen_candidate(setting, weight, rows, dt_ms=dt_ms)
            scored.append({**bucket["unit"], **cand, "w_bg": weight, "deepest": "T1"})
        cands = [row for row in scored if row["screen_passed"]]
        flags = list(bucket["unit"].get("flags") or [])
        if not cands and t1_grid_edge(bucket["unit"], rows, dt_ms=dt_ms):
            if "grid edge" not in flags:
                flags.append("grid edge")
            n_edge += 1
        for row in scored:
            merged: list[str] = []
            for flag in (*flags, *(row.get("flags") or [])):
                if flag not in merged:
                    merged.append(flag)
            row["flags"] = merged
        units_out.append({
            **bucket["unit"],
            "n_rows": len(rows),
            "n_candidates": len(cands),
            "screen_passed": bool(cands),
            "flags": flags,
            "job_ids": sorted(bucket["job_ids"]),
            "deepest": "T1",
            "lowest_S": min(row["S"] for row in scored) if scored else None,
        })
        all_scored.extend(scored)
        all_cands.extend(cands)
    admitted, excluded = admit_t2(all_cands)
    miss = closest_miss(all_scored)
    return {
        "units": units_out,
        "candidates": [_t2_candidate(c) for c in all_cands],
        "scored": [_t2_candidate(c) for c in all_scored],
        "admitted": [_t2_candidate(c) for c in admitted],
        "excluded": [{**_t2_candidate(c), "status": "not tested (cap)"} for c in excluded],
        "closest_miss": _t2_candidate(miss) if miss is not None else None,
        "n_units": len(units_out),
        "n_tasks": n_tasks,
        "n_screen_passers": len(all_cands),
        "n_t2_admitted": len(admitted),
        "grid_edge": n_edge,
        "wall_per_brain_s": rates,
        "t2_b_unreachable": sum(
            1 for unit in units_out if "t2-b-unreachable" in (unit.get("flags") or [])
        ),
        "dt_ms": dt_ms,
    }


def cbi_stiff(h_max: float, *, dt_ms: float | None = None, t_mbr_ms: float | None = None) -> bool:
    """Whether h_max flags cbi-stiff (SPEC-P2 2.2.4). Metrics then not computable."""
    cfg = load_config()["tier3"]
    limit = float(cfg["cbi_stiff_limit"])
    params = load_params()
    dt = float(params.get("lif.dt") if dt_ms is None else dt_ms)
    t_mbr = float(params.get("lif.t_mbr") if t_mbr_ms is None else t_mbr_ms)
    return dt * (1.0 + float(h_max)) / t_mbr > limit


def score_not_computable() -> float:
    return CAP


def _finite_hz(values: Any, size: int) -> bool:
    return (
        isinstance(values, list)
        and len(values) == size
        and all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in values)
    )


def harmonised_reflex_floors(job_bare_mean: float | None = None) -> tuple[float, float]:
    """Item 74 (a)/(b) floors: 0.5 and 0.4 of same-job bare, else 28 Hz and 22 Hz."""
    if job_bare_mean is not None and math.isfinite(float(job_bare_mean)) and float(job_bare_mean) > 0:
        bare = float(job_bare_mean)
        return HARMONISED_REFLEX_MEAN_FRAC * bare, HARMONISED_REFLEX_SEED_FRAC * bare
    return HARMONISED_REFLEX_MEAN_HZ, HARMONISED_REFLEX_SEED_MIN_HZ


def _ab_pass(a: list[Any], b: list[Any], *, mean_hz: float, seed_min_hz: float) -> bool:
    return (
        _finite_hz(a, 6)
        and _finite_hz(b, 10)
        and min(float(v) for v in a) >= seed_min_hz
        and min(float(v) for v in b) >= seed_min_hz
        and sum(float(v) for v in b) / 10 > mean_hz
    )


def fails_only_reflex_ab(result: dict[str, Any]) -> bool:
    """True when (c) and provenance hold and only (a) or (b) miss the 40/50 Hz floors."""
    if result.get("reflex_passed"):
        return False
    if "cbi-stiff" in (result.get("flags") or []):
        return False
    ret = (result.get("retention") or {}).get("extended")
    if ret is None or not math.isfinite(float(ret)) or float(ret) < FF_RETENTION_MIN:
        return False
    cand = result.get("candidate_ff_hz") or {}
    bare = result.get("bare_ff_hz") or {}
    if not _finite_hz(cand.get("upstream") or [], 10) or not _finite_hz(bare.get("upstream") or [], 10):
        return False
    a, b = result.get("a_hz") or [], result.get("b_hz") or []
    if not _finite_hz(a, 6) or not _finite_hz(b, 10):
        return False
    return not _ab_pass(
        a, b, mean_hz=ORIGINAL_REFLEX_MEAN_HZ, seed_min_hz=ORIGINAL_REFLEX_SEED_MIN_HZ,
    )


def t2_reflex_probe(
    a: list[Any],
    b: list[Any],
    candidate: dict[str, list[Any]],
    bare: dict[str, list[Any]],
    *,
    h_max: float | None = None,
    sub_tier: str | None = None,
    job_bare_mean: float | None = None,
    dt_ms: float | None = None,
) -> dict[str, Any]:
    """T2 R-reflex: item 69 cbi-stiff, then item 74 (a)/(b) harmonisation.

    Missing h_max is computable. Harmonisation applies to every tier-3 sub-tier
    that fails only (a) or (b). A fail of (c), provenance, or cbi-stiff is not rescued.
    """
    result = reflex_decision(a, b, candidate, bare)
    flags: list[str] = []
    result["reflex_harmonised"] = False
    if h_max is not None and cbi_stiff(h_max, dt_ms=dt_ms):
        flags.append("cbi-stiff")
        cap = score_not_computable()
        result["reflex_passed"] = False
        result["reflex_violations"] = {"a": cap, "b": cap, "c": cap}
        result["reflex_violation"] = 3 * cap
        result["flags"] = flags
        result["h_max"] = h_max
        return result
    if (sub_tier in SUB_TIERS or sub_tier == "T3e") and fails_only_reflex_ab(result):
        mean_hz, seed_min_hz = harmonised_reflex_floors(job_bare_mean)
        harm_pass = _ab_pass(a, b, mean_hz=mean_hz, seed_min_hz=seed_min_hz)
        va = violation(max(1, min(float(v) for v in a)), lower=seed_min_hz)
        vb = violation(max(1, sum(float(v) for v in b) / 10), lower=mean_hz)
        vc = float((result.get("reflex_violations") or {}).get("c", CAP))
        result["reflex_verdicts"] = {
            "original": {
                "reflex_passed": False,
                "mean_hz": ORIGINAL_REFLEX_MEAN_HZ,
                "seed_min_hz": ORIGINAL_REFLEX_SEED_MIN_HZ,
                "reflex_violations": dict(result.get("reflex_violations") or {}),
            },
            "harmonised": {
                "reflex_passed": harm_pass,
                "mean_hz": mean_hz,
                "seed_min_hz": seed_min_hz,
                "job_bare_mean": job_bare_mean,
                "reflex_violations": {"a": va, "b": vb, "c": vc},
            },
        }
        if harm_pass:
            result["reflex_passed"] = True
            result["reflex_harmonised"] = True
            flags.append("reflex-harmonised")
    result["flags"] = flags
    result["h_max"] = h_max
    return result


def projection_engine_hours(
    *,
    t0_brain_s: float,
    admitted_units: int,
    rho_mech: float,
    q_plan: float = Q_PLAN,
    t1_brain_s: float = T1_BRAIN_S_PER_UNIT,
    t2_brain_s: float = T2_BRAIN_S,
) -> float:
    """Section 2.6 T1 cap projection. Units: engine-hours."""
    return (t0_brain_s + admitted_units * t1_brain_s + t2_brain_s) * q_plan * rho_mech / 3600.0


def admit_t1(
    passers: list[dict[str, Any]],
    *,
    rho_mech: float,
    t0_brain_s: float,
    t1_max_units: int | None = None,
    cap_engine_hours: float | None = None,
    q_plan: float = Q_PLAN,
) -> dict[str, Any]:
    """Admit T0 passers in rounds. Baseline rows are never admitted."""
    cfg = load_config()["tier3"]
    t1_max = int(cfg["t1_max_units"] if t1_max_units is None else t1_max_units)
    cap = float(cfg["cap_engine_hours"] if cap_engine_hours is None else cap_engine_hours)
    real = [u for u in passers if not u.get("baseline")]
    if projection_engine_hours(t0_brain_s=t0_brain_s, admitted_units=0, rho_mech=rho_mech, q_plan=q_plan) > cap:
        excluded = [{**u, "status": "not tested (cap)"} for u in real]
        return {
            "admitted": [],
            "excluded": excluded,
            "failed_stage": "R-screen",
            "reason": "cap",
        }
    by_pair: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
    for unit in real:
        by_pair[(float(unit["g_gaba"]), float(unit["g_glu"]))].append(unit)
    for pair_units in by_pair.values():
        pair_units.sort(key=lambda u: (-float(u.get("M", mechanism_strength(u["sub_tier"], u["setting"]))),
                                       *parameter_tuple(u["sub_tier"], u["setting"])))
    pairs_ordered = sorted(by_pair, key=lambda p: (parsimony(*p), p[0], p[1]))
    admitted: list[dict[str, Any]] = []
    leftover: list[dict[str, Any]] = []
    round_i = 0
    stop = False
    while not stop:
        batch: list[dict[str, Any]] = []
        for pair in pairs_ordered:
            units = by_pair[pair]
            if round_i < len(units):
                batch.append(units[round_i])
        if not batch:
            break
        for unit in batch:
            if stop:
                leftover.append(unit)
                continue
            if len(admitted) >= t1_max:
                leftover.append(unit)
                stop = True
                continue
            if projection_engine_hours(
                t0_brain_s=t0_brain_s, admitted_units=len(admitted) + 1,
                rho_mech=rho_mech, q_plan=q_plan,
            ) > cap:
                leftover.append(unit)
                stop = True
                continue
            admitted.append(unit)
        round_i += 1
        if stop:
            while True:
                extra: list[dict[str, Any]] = []
                for pair in pairs_ordered:
                    units = by_pair[pair]
                    if round_i < len(units):
                        extra.append(units[round_i])
                if not extra:
                    break
                leftover.extend(extra)
                round_i += 1
    excluded = [{**u, "status": "not tested (cap)"} for u in leftover]
    return {"admitted": admitted, "excluded": excluded, "failed_stage": None, "reason": None}


def grid_edge_flag(rows: list[dict[str, Any]]) -> bool:
    """T1 unit with no R-screen passer and lowest-S pair (1.55, 1.60) under the floor."""
    if any(r.get("screen_passed") for r in rows):
        return False
    pair = [r for r in rows if round(float(r.get("w_bg", 0)), 2) in (1.55, 1.60)]
    if len(pair) < 2:
        return False
    at_160 = [r for r in pair if round(float(r["w_bg"]), 2) == 1.60]
    if not at_160:
        return False
    centrals = [
        r.get("rates_hz", {}).get("central")
        for r in at_160
        if r.get("rates_hz", {}).get("central") is not None
    ]
    if not centrals:
        return False
    return (sum(centrals) / len(centrals)) < 0.5


def t1_grid_edge(
    unit: dict[str, Any],
    screen_rows: list[dict[str, Any]],
    *,
    dt_ms: float | None = None,
) -> bool:
    """grid edge: no passer, lowest-S pair is (1.55, 1.60), central mean under the floor."""
    setting = Setting(
        g_gaba=float(unit["g_gaba"]),
        g_glu=float(unit["g_glu"]),
        sigma_th=float(unit.get("sigma_th", 0.0)),
        optic_exemption=bool(unit.get("optic_exemption", False)),
        n_bg=int(unit.get("n_bg", 100)),
    )
    scored = [screen_candidate(setting, w, screen_rows, dt_ms=dt_ms) for w in setting.weights[:-2]]
    if not scored or any(row["screen_passed"] for row in scored):
        return False
    lowest = min(scored, key=lambda row: (row["S"], float(row["w_bg"])))
    if round(float(lowest["w_bg"]), 2) != 1.55:
        return False
    collapsed = []
    by_w: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for row in screen_rows:
        by_w[round(float(row["w_bg"]), 2)].append(row)
    for weight, rows in by_w.items():
        centrals = [
            r.get("rates_hz", {}).get("central")
            for r in rows
            if r.get("rates_hz", {}).get("central") is not None
        ]
        mean = (sum(centrals) / len(centrals)) if centrals else None
        collapsed.append({"w_bg": weight, "rates_hz": {"central": mean}, "screen_passed": False})
    return grid_edge_flag(collapsed)


def candidate_id(row: dict[str, Any]) -> str:
    """Tier-3 ranked-list identifier (SPEC-P2 2.6 Records)."""
    base = "-".join((
        str(float(row["g_gaba"])),
        str(float(row["g_glu"])),
        str(float(row.get("sigma_th", 0.0))),
        str(bool(row.get("optic_exemption", False))),
        str(int(row.get("n_bg", 100))),
        str(float(row["w_bg"])),
    ))
    setting = row.get("setting") or {}
    model = row.get("engine_model") or unit_engine_model(row)
    parts = [base]
    if model == "lif+sfa" or (row.get("sub_tier") == "T3a"):
        parts.append(f"sfa-{float(setting['b_mv'])}-{float(setting['tau_ms'])}-{setting['scope']}")
    elif model == "lif+std" or row.get("sub_tier") == "T3b":
        parts.append(f"std-{float(setting['U'])}-{float(setting['tau_ms'])}-{setting['scope']}")
    elif model == "lif+cbi" or row.get("sub_tier") == "T3c":
        parts.append(f"cbi-{float(setting['E_inh_mv'])}-{setting['scope']}")
    g_kc = setting.get("g_gaba_kc", row.get("g_gaba_kc"))
    if g_kc is not None:
        parts.append(f"kc-{float(g_kc)}")
    from flyonenomics.drive.rest_nonuniform import arm_id
    tag = arm_id(row.get("arm") if isinstance(row.get("arm"), dict) else None)
    if not tag:
        tag = str(setting.get("arm_id") or row.get("arm_id") or "")
    if tag:
        parts.append(tag)
    return "-".join(parts)


def unit_engine_model(unit: dict[str, Any] | None) -> str:
    """Engine model of one unit. 3d is lif, or lif+sfa when 3a is on."""
    if unit is None or unit.get("baseline"):
        return "lif"
    if unit.get("engine_model"):
        return str(unit["engine_model"])
    sub = unit.get("sub_tier")
    if sub == "T3d":
        setting = unit.get("setting") or {}
        return "lif+sfa" if setting.get("b_mv") is not None else "lif"
    if sub == "T3e":
        return "lif"
    return ENGINE_MODEL[sub]


def ranked_list_row(
    unit: dict[str, Any],
    *,
    w_bg: float,
    mechanisms: dict[str, Any] | None,
    mask_sha256: str | None = None,
) -> dict[str, Any]:
    """One R3/R4 input row. Units: as section 2.6 Records."""
    sub = unit["sub_tier"]
    setting = dict(unit.get("setting") or {})
    section = {name: None for name in ("adaptation", "depression", "conductance_inhibition")}
    if sub == "T3d":
        model = unit_engine_model(unit)
        block = {key: value for key, value in setting.items() if key != "g_gaba_kc"}
        if block.get("b_mv") is not None:
            if mask_sha256 is not None:
                block["mask_sha256"] = mask_sha256
            section["adaptation"] = block
    else:
        model = ENGINE_MODEL[sub]
        block_name = BLOCK_NAME[sub]
        block = dict(setting)
        if mask_sha256 is not None and block_name != "conductance_inhibition":
            block["mask_sha256"] = mask_sha256
        section[block_name] = block
    row = {
        **unit,
        "w_bg": w_bg,
        "engine_model": model,
        "mechanisms": section,
        "sigma_th": unit.get("sigma_th", 0.0),
        "optic_exemption": unit.get("optic_exemption", False),
        "n_bg": unit.get("n_bg", 100),
        "scope": unit.get("scope", "brain"),
    }
    row["candidate_id"] = candidate_id(row)
    return row


def candidates_from_unit(
    unit: dict[str, Any],
    screen_rows: list[dict[str, Any]],
    *,
    dt_ms: float | None = None,
) -> list[dict[str, Any]]:
    """Adjacent passing weights of one admitted unit, at the lower weight."""
    from flyonenomics.drive.rest_map import Setting

    setting = Setting(
        g_gaba=float(unit["g_gaba"]), g_glu=float(unit["g_glu"]),
        sigma_th=float(unit.get("sigma_th", 0.0)),
        optic_exemption=bool(unit.get("optic_exemption", False)),
        n_bg=int(unit.get("n_bg", 100)),
    )
    out: list[dict[str, Any]] = []
    for w in setting.weights[:-2]:
        cand = screen_candidate(setting, w, screen_rows, dt_ms=dt_ms)
        if cand["screen_passed"]:
            out.append({**unit, **cand, "w_bg": w})
    return out


def admit_t2(
    candidates: list[dict[str, Any]],
    cap: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """R-screen passers in tier-3 order-key order, capped at rest.max_candidates 20."""
    if cap is None:
        cap = int(load_params(ROOT / "data" / "params-v0.2.yaml").get("rest.max_candidates"))
    ordered = sorted((c for c in candidates if c.get("screen_passed")), key=tier3_order_key)
    return ordered[:cap], [{**c, "status": "not tested (cap)"} for c in ordered[cap:]]


def closest_miss_key(row: dict[str, Any]) -> tuple:
    """Deepest stage first, then the tier-3 order key."""
    depth = STAGE_DEPTH.get(row.get("deepest", "T0"), 0)
    return (-depth,) + tier3_order_key(row)


def closest_miss(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return min(rows, key=closest_miss_key)


def decide_subtier(
    *,
    sub_tier: str,
    t0_units: list[dict[str, Any]],
    t1_candidates: list[dict[str, Any]] | None = None,
    t2_results: list[dict[str, Any]] | None = None,
    qrest_exhausted: bool = False,
    t1_admission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rank a sub-tier or record the failed stage and closest miss."""
    t1_candidates = t1_candidates or []
    t2_results = t2_results or []
    t0_passers = [u for u in t0_units if u.get("t0_passed") and not u.get("baseline")]

    def pack(
        failed_stage: str | None,
        closest: dict[str, Any] | None,
        ranked: list[dict[str, Any]] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        ranked = ranked or []
        out = {
            "ranked": ranked,
            "shortlist": ranked[:3] if ranked else [],
            "failed_stage": failed_stage,
            "closest_miss": closest,
            "p2_partial_b": p2_partial_b(sub_tier, failed_stage, ranked),
        }
        out.update(extra)
        return out

    if not t0_passers:
        return pack("T0", closest_miss(t0_units))
    if t1_admission and t1_admission.get("failed_stage") == "R-screen":
        return pack("R-screen", closest_miss(t0_passers), reason=t1_admission.get("reason"))
    screen_passers = [c for c in t1_candidates if c.get("screen_passed")]
    if t1_admission is not None and not screen_passers:
        return pack("R-screen", closest_miss(t1_candidates or t0_passers))
    if t2_results:
        reflex_ok = [c for c in t2_results if c.get("reflex_passed")]
        if not reflex_ok:
            return pack("R-reflex", closest_miss(t2_results))
        long_ok = [c for c in reflex_ok if c.get("long_passed")]
        if not long_ok:
            return pack("R-long", closest_miss(reflex_ok))
        if qrest_exhausted:
            return pack("Q-rest", closest_miss(long_ok))
        ranked = sorted(long_ok, key=tier3_order_key)
        return pack(None, None, ranked=ranked)
    return pack(None, closest_miss(screen_passers or t0_passers))


def next_sub_tier(sub_tier: str, failed_stage: str | None, ranked: list) -> str | None:
    """Empty 3a starts 3b, empty 3b starts 3c, empty 3c starts 3d; empty 3d is P2-partial-B."""
    if ranked:
        return None
    if failed_stage is None:
        return None
    if sub_tier == "T3a":
        return "T3b"
    if sub_tier == "T3b":
        return "T3c"
    if sub_tier == "T3c":
        return "T3d"
    return None


def p2_partial_b(sub_tier: str, failed_stage: str | None, ranked: list) -> bool:
    return not ranked and sub_tier == "T3d" and failed_stage is not None


def makespan_s(cfg: dict[str, Any] | None = None) -> float:
    camber = (cfg or load_config())["camber"]
    return (float(camber["running_max_s"]) - float(camber["setup_s"])) / float(camber["margin"])


def max_task_brain_s(
    rho_mech: float,
    cfg: dict[str, Any] | None = None,
    *,
    worker_s_per_brain_s: float | None = None,
    makespan: float | None = None,
) -> int:
    camber = (cfg or load_config())["camber"]
    build_s = float(camber["build_s"])
    rate = (
        float(camber["worker_s_per_brain_s"]) * rho_mech
        if worker_s_per_brain_s is None
        else float(worker_s_per_brain_s)
    )
    span = makespan_s(cfg) if makespan is None else float(makespan)
    return int(math.floor((span - build_s) / rate))


def task_worker_s(
    brain_s: float,
    rho_mech: float,
    cfg: dict[str, Any] | None = None,
    *,
    worker_s_per_brain_s: float | None = None,
) -> float:
    camber = (cfg or load_config())["camber"]
    rate = (
        float(camber["worker_s_per_brain_s"]) * rho_mech
        if worker_s_per_brain_s is None
        else float(worker_s_per_brain_s)
    )
    return float(camber["build_s"]) + rate * brain_s


def pack_tasks(
    tasks: list[dict[str, Any]],
    rho_mech: float,
    cfg: dict[str, Any] | None = None,
    *,
    reserve_s: float = 0.0,
    worker_s_per_brain_s: float | None = None,
    job_cap_s: float | None = None,
    makespan: float | None = None,
) -> list[list[dict[str, Any]]]:
    """Fill jobs in admission order under workers × makespan worker-seconds."""
    camber = (cfg or load_config())["camber"]
    span = makespan_s(cfg) if makespan is None else float(makespan)
    cap = (float(job_cap_s) if job_cap_s is not None else float(camber["workers"]) * span) - float(reserve_s)
    if cap <= 0:
        raise ValueError("job cap after reserve is not positive")
    jobs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    cost = 0.0
    for task in tasks:
        add = task_worker_s(
            float(task["brain_s"]), rho_mech, cfg, worker_s_per_brain_s=worker_s_per_brain_s,
        )
        if add > cap:
            raise ValueError("one task exceeds the job cap")
        if current and cost + add > cap:
            jobs.append(current)
            current = []
            cost = 0.0
        current.append(task)
        cost += add
    if current:
        jobs.append(current)
    return jobs


def pack_task_groups(
    groups: list[list[dict[str, Any]]],
    rho_mech: float,
    cfg: dict[str, Any] | None = None,
    *,
    reserve_s: float = 0.0,
    worker_s_per_brain_s: float | None = None,
) -> list[list[dict[str, Any]]]:
    """Fill jobs with whole groups in admission order under workers × 5,280 worker-seconds."""
    camber = (cfg or load_config())["camber"]
    cap = float(camber["workers"]) * makespan_s(cfg) - float(reserve_s)
    if cap <= 0:
        raise ValueError("job cap after reserve is not positive")
    jobs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    cost = 0.0
    for group in groups:
        add = sum(
            task_worker_s(
                float(task["brain_s"]), rho_mech, cfg, worker_s_per_brain_s=worker_s_per_brain_s,
            )
            for task in group
        )
        if add > cap:
            raise ValueError("one T2 candidate exceeds the job cap")
        if current and cost + add > cap:
            jobs.append(current)
            current = []
            cost = 0.0
        current.extend(group)
        cost += add
    if current:
        jobs.append(current)
    return jobs


def shaping_rate(rho_mech: float, rates: list[float] | None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Section 6.5 measured-rate replacement for T1/T2 shaping."""
    camber = (cfg or load_config())["camber"]
    planned = float(camber["worker_s_per_brain_s"]) * rho_mech
    median = statistics.median(rates) if rates else None
    replaced = median is not None and median > planned * float(camber["margin"])
    return {
        "planned_worker_s_per_brain_s": planned,
        "median_wall_per_brain_s": median,
        "replaced": replaced,
        "worker_s_per_brain_s": float(median) if replaced else planned,
    }


def t1_weight_slices(
    rho_mech: float,
    cfg: dict[str, Any] | None = None,
    *,
    worker_s_per_brain_s: float | None = None,
    makespan: float | None = None,
) -> tuple[list[tuple[int, int]], int]:
    """Adjacent-weight slices of at most floor(B / 12), section 6.5."""
    b = max_task_brain_s(rho_mech, cfg, worker_s_per_brain_s=worker_s_per_brain_s, makespan=makespan)
    width = int(math.floor(b / 12))
    if width < 1:
        raise ValueError("one-weight T1 task exceeds B")
    slices: list[tuple[int, int]] = []
    start = 0
    n_w = len(WEIGHTS)
    while start < n_w:
        stop = min(start + width, n_w)
        slices.append((start, stop))
        start = stop
    return slices, b


def _t1_identity_key(unit: dict[str, Any]) -> str:
    """Stable T0/T1 unit key: pair plus mechanism setting."""
    setting = unit.get("setting") or {}
    if not isinstance(setting, dict):
        setting = {}
    compact: dict[str, Any] = {}
    for key in sorted(setting):
        value = setting[key]
        if isinstance(value, bool) or value is None:
            compact[key] = value
        elif isinstance(value, (int, float)):
            compact[key] = float(value)
        else:
            compact[key] = value
    return json.dumps(
        {
            "g_gaba": float(unit["g_gaba"]),
            "g_glu": float(unit["g_glu"]),
            "setting": compact,
        },
        sort_keys=True,
    )


def _t1_unit(unit: dict[str, Any]) -> dict[str, Any]:
    """Fields T1 needs to build and score one admitted unit."""
    setting = unit.get("setting")
    compact = {
        "sub_tier": unit["sub_tier"],
        "engine_model": unit.get("engine_model") or unit_engine_model(unit),
        "g_gaba": float(unit["g_gaba"]),
        "g_glu": float(unit["g_glu"]),
        "setting": dict(setting) if setting else None,
        "M": float(unit["M"]) if unit.get("M") is not None else mechanism_strength(unit["sub_tier"], setting),
        "sigma_th": float(unit.get("sigma_th", 0.0)),
        "optic_exemption": bool(unit.get("optic_exemption", False)),
        "n_bg": int(unit.get("n_bg", 100)),
        "job_id": unit.get("job_id"),
        "retention": unit.get("retention"),
        "difference_hz": unit.get("difference_hz"),
        "flags": list(unit.get("flags") or []),
    }
    g_kc = None if setting is None else setting.get("g_gaba_kc", unit.get("g_gaba_kc"))
    if g_kc is not None:
        compact["g_gaba_kc"] = float(g_kc)
    if unit.get("arm"):
        compact["arm"] = dict(unit["arm"])
    return compact


def _maybe_apply_arm(built: dict[str, Any], unit: dict[str, Any] | None) -> dict[str, Any]:
    """Apply a 3e per-neuron arm when the unit carries one. No-op otherwise."""
    if not isinstance(unit, dict):
        return built
    arm = unit.get("arm")
    if not arm:
        return built
    from flyonenomics.drive.rest_nonuniform import apply_arm

    return apply_arm(built, arm)


def t1_tasks(
    admitted: list[dict[str, Any]],
    rho_mech: float,
    identity: dict[str, Any] | None = None,
    *,
    worker_s_per_brain_s: float | None = None,
    makespan: float | None = None,
    job_cap_s: float | None = None,
) -> dict[str, Any]:
    """T1 R-screen tasks packed under section 6.5. One task per unit/seed/slice."""
    cfg = load_config()
    try:
        slices, b = t1_weight_slices(
            rho_mech, cfg, worker_s_per_brain_s=worker_s_per_brain_s, makespan=makespan,
        )
    except ValueError as exc:
        return {
            "launch": False,
            "reason": str(exc),
            "B": max_task_brain_s(
                rho_mech, cfg, worker_s_per_brain_s=worker_s_per_brain_s, makespan=makespan,
            ),
            "jobs": [],
        }
    tasks: list[dict[str, Any]] = []
    for index, unit in enumerate(admitted):
        compact = _t1_unit(unit)
        setting = Setting(
            g_gaba=compact["g_gaba"],
            g_glu=compact["g_glu"],
            sigma_th=compact["sigma_th"],
            optic_exemption=compact["optic_exemption"],
            n_bg=compact["n_bg"],
            g_gaba_kc=float(compact.get("g_gaba_kc", 1.0)),
        )
        weights = setting.weights
        for seed in SEEDS:
            for start, stop in slices:
                n_w = stop - start
                tasks.append({
                    "kind": "t1",
                    "unit_index": index,
                    "unit": compact,
                    "seed": int(seed),
                    "slice": [start, stop],
                    "probes": [(float(weights[i]), int(seed)) for i in range(start, stop)],
                    "brain_s": n_w * 12,
                    "identity": identity or {},
                })
    try:
        jobs = pack_tasks(
            tasks, rho_mech, cfg,
            worker_s_per_brain_s=worker_s_per_brain_s,
            makespan=makespan,
            job_cap_s=job_cap_s,
        )
    except ValueError:
        return {"launch": False, "reason": "one T1 task exceeds the job cap", "B": b, "jobs": []}
    t1_brain = sum(t["brain_s"] for job in jobs for t in job)
    return {
        "launch": True,
        "B": b,
        "rho_mech": rho_mech,
        "slices": [list(s) for s in slices],
        "tasks": [t for job in jobs for t in job],
        "jobs": jobs,
        "t1_brain_s": t1_brain,
        "n_jobs": len(jobs),
        "n_tasks": sum(len(job) for job in jobs),
        "n_units": len(admitted),
    }


def t1_record(
    admitted: list[dict[str, Any]],
    rho_mech: float,
    *,
    t0_brain_s: float,
    rates: list[float] | None = None,
    engine_model: str | None = None,
) -> dict[str, Any]:
    """rest-T3X-T1.json body: admission, measured rate, and packed jobs."""
    cfg = load_config()
    shaped = shaping_rate(rho_mech, rates, cfg)
    override = shaped["worker_s_per_brain_s"] if shaped["replaced"] else None
    packed = t1_tasks(admitted, rho_mech, worker_s_per_brain_s=override)
    model = engine_model or (admitted[0].get("engine_model") if admitted else ENGINE_MODEL["T3a"])
    return {
        "class": "development",
        "sub_tier": admitted[0]["sub_tier"] if admitted else "T3a",
        "stage": "T1",
        "engine_model": model,
        "rho_mech": rho_mech,
        "q_plan": Q_PLAN,
        "t0_brain_s": t0_brain_s,
        "measured_rate": shaped,
        "admitted": [_t1_unit(u) for u in admitted],
        "camber": cfg["camber"],
        "job_shapes": {
            "B_brain_s": packed.get("B"),
            "slices": packed.get("slices"),
            "n_jobs": packed.get("n_jobs"),
            "n_tasks": packed.get("n_tasks"),
            "t1_brain_s": packed.get("t1_brain_s"),
            "n_units": packed.get("n_units"),
            "launch": packed.get("launch"),
            "reason": packed.get("reason"),
        },
        "cap_projection_engine_hours": projection_engine_hours(
            t0_brain_s=t0_brain_s, admitted_units=len(admitted), rho_mech=rho_mech,
        ),
        "t1_max_units": cfg["tier3"]["t1_max_units"],
        "cap_engine_hours": cfg["tier3"]["cap_engine_hours"],
    }


def _t2_candidate(row: dict[str, Any]) -> dict[str, Any]:
    """Fields T2 needs to build and score one R-screen passer."""
    compact = _t1_unit(row)
    w_bg = float(row["w_bg"])
    pair = row.get("pair_weights") or [w_bg]
    compact.update({
        "w_bg": w_bg,
        "pair_weights": [float(x) for x in pair],
        "S": float(row["S"]),
        "J": float(row["J"]) if row.get("J") is not None else 0.0,
        "screen_passed": bool(row.get("screen_passed")),
        "violations": {str(k): float(v) for k, v in (row.get("violations") or {}).items()},
        "candidate_id": candidate_id({**compact, "w_bg": w_bg}),
        "deepest": row.get("deepest", "T1"),
    })
    return compact


def t2_candidate_tasks(
    index: int,
    candidate: dict[str, Any],
    identity: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """36 T2 tasks of one candidate: (a) 6, (b) 10, (c) 10, R-long 10."""
    compact = _t2_candidate(candidate)
    w_low = float(compact["w_bg"])
    weights = compact["pair_weights"]
    w_high = float(weights[1]) if len(weights) > 1 else w_low
    ident = identity or {}
    tasks: list[dict[str, Any]] = []
    for weight in (w_low, w_high):
        for seed in SEEDS:
            tasks.append({
                "kind": "reflex-a",
                "candidate_index": index,
                "candidate": compact,
                "w_bg": float(weight),
                "seed": int(seed),
                "brain_s": T2_REFLEX_BRAIN_S,
                "identity": ident,
            })
    for seed in LONG_SEEDS:
        tasks.append({
            "kind": "reflex-b",
            "candidate_index": index,
            "candidate": compact,
            "w_bg": w_low,
            "seed": int(seed),
            "brain_s": T2_REFLEX_BRAIN_S,
            "identity": ident,
        })
    for seed in LONG_SEEDS:
        tasks.append({
            "kind": "reflex-c",
            "candidate_index": index,
            "candidate": compact,
            "w_bg": 0.0,
            "seed": int(seed),
            "brain_s": T2_REFLEX_BRAIN_S,
            "identity": ident,
        })
    for seed in LONG_SEEDS:
        tasks.append({
            "kind": "long",
            "candidate_index": index,
            "candidate": compact,
            "w_bg": w_low,
            "seed": int(seed),
            "brain_s": T2_LONG_BRAIN_S,
            "identity": ident,
        })
    if len(tasks) != T2_TASKS_PER_CANDIDATE:
        raise ValueError(f"T2 candidate has {len(tasks)} tasks, expected {T2_TASKS_PER_CANDIDATE}")
    return tasks


def t2_bare_tasks(job_index: int, identity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Ten upstream bare-reference tasks of 6 brain s, one per seed."""
    ident = identity or {}
    return [
        {
            "kind": "bare",
            "candidate_index": None,
            "candidate": None,
            "w_bg": 0.0,
            "seed": int(seed),
            "brain_s": T2_REFLEX_BRAIN_S,
            "identity": ident,
            "job_index": job_index,
        }
        for seed in LONG_SEEDS
    ]


def t2_tasks(
    admitted: list[dict[str, Any]],
    rho_mech: float,
    identity: dict[str, Any] | None = None,
    *,
    worker_s_per_brain_s: float | None = None,
) -> dict[str, Any]:
    """T2 R-reflex and R-long tasks packed under section 6.5. Whole candidates, 10 bare/job."""
    cfg = load_config()
    b = max_task_brain_s(rho_mech, cfg, worker_s_per_brain_s=worker_s_per_brain_s)
    if not admitted:
        return {
            "launch": False, "reason": "no R-screen passer", "B": b, "jobs": [],
            "n_jobs": 0, "n_tasks": 0, "t2_brain_s": 0, "n_candidates": 0,
        }
    if b < T2_LONG_BRAIN_S:
        return {
            "launch": False, "reason": "one-seed task exceeds B", "B": b, "jobs": [],
            "n_jobs": 0, "n_tasks": 0, "t2_brain_s": 0, "n_candidates": 0,
        }
    groups = [t2_candidate_tasks(i, cand, identity) for i, cand in enumerate(admitted)]
    reserve = T2_BARE_PER_JOB * task_worker_s(
        T2_REFLEX_BRAIN_S, rho_mech, cfg, worker_s_per_brain_s=worker_s_per_brain_s,
    )
    try:
        packed_groups = pack_task_groups(
            groups, rho_mech, cfg, reserve_s=reserve, worker_s_per_brain_s=worker_s_per_brain_s,
        )
    except ValueError:
        return {
            "launch": False, "reason": "one T2 candidate exceeds the job cap", "B": b, "jobs": [],
            "n_jobs": 0, "n_tasks": 0, "t2_brain_s": 0, "n_candidates": 0,
        }
    packed: list[list[dict[str, Any]]] = []
    for index, job_tasks in enumerate(packed_groups):
        packed.append(job_tasks + t2_bare_tasks(index, identity))
    t2_brain = sum(float(t["brain_s"]) for job in packed for t in job)
    return {
        "launch": True,
        "B": b,
        "rho_mech": rho_mech,
        "tasks": [t for job in packed for t in job],
        "jobs": packed,
        "t2_brain_s": t2_brain,
        "n_jobs": len(packed),
        "n_tasks": sum(len(job) for job in packed),
        "n_candidates": len(admitted),
    }


def t2_record(
    admitted: list[dict[str, Any]],
    rho_mech: float,
    *,
    t0_brain_s: float,
    t1_brain_s: float,
    rates: list[float] | None = None,
    engine_model: str | None = None,
    excluded: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """rest-T3X-T2.json body: T2 admission, measured rate, and packed jobs."""
    cfg = load_config()
    shaped = shaping_rate(rho_mech, rates, cfg)
    override = shaped["worker_s_per_brain_s"] if shaped["replaced"] else None
    packed = t2_tasks(admitted, rho_mech, worker_s_per_brain_s=override)
    model = engine_model or (admitted[0].get("engine_model") if admitted else ENGINE_MODEL["T3a"])
    return {
        "class": "development",
        "sub_tier": admitted[0]["sub_tier"] if admitted else "T3a",
        "stage": "T2",
        "engine_model": model,
        "rho_mech": rho_mech,
        "q_plan": Q_PLAN,
        "t0_brain_s": t0_brain_s,
        "t1_brain_s": t1_brain_s,
        "measured_rate": shaped,
        "admitted": [_t2_candidate(c) for c in admitted],
        "excluded": list(excluded or []),
        "camber": cfg["camber"],
        "job_shapes": {
            "B_brain_s": packed.get("B"),
            "n_jobs": packed.get("n_jobs"),
            "n_tasks": packed.get("n_tasks"),
            "t2_brain_s": packed.get("t2_brain_s"),
            "n_candidates": packed.get("n_candidates"),
            "launch": packed.get("launch"),
            "reason": packed.get("reason"),
        },
        "cap_projection_engine_hours": projection_engine_hours(
            t0_brain_s=t0_brain_s,
            admitted_units=int(round(t1_brain_s / T1_BRAIN_S_PER_UNIT)) if t1_brain_s else 0,
            rho_mech=rho_mech,
        ),
        "max_candidates": int(load_params(ROOT / "data" / "params-v0.2.yaml").get("rest.max_candidates")),
    }


def collect_t2(
    jobs: list[tuple[Path, list[dict[str, Any]]]],
    *,
    dt_ms: float | None = None,
) -> dict[str, Any]:
    """Score T2 R-reflex and R-long. Item 74 rejudges only (a)/(b)."""
    by_index: dict[int, dict[str, Any]] = {}
    bares: dict[int, list[dict[str, Any]]] = defaultdict(list)
    rates: list[float] = []
    n_tasks = 0
    for job_i, (out, tasks) in enumerate(jobs):
        for task in tasks:
            n_tasks += 1
            path = task_ndjson_path(out, task)
            rows = read_t0_task_rows(path)
            complete = rows[-1]
            if complete.get("wall_per_brain_s") is not None:
                rates.append(float(complete["wall_per_brain_s"]))
            evals = [row for row in rows if row.get("kind") == "evaluation"]
            kind = task.get("kind")
            if kind == "bare":
                bares[job_i].extend(evals)
                continue
            idx = int(task["candidate_index"])
            bucket = by_index.setdefault(idx, {
                "candidate": dict(task.get("candidate") or {}),
                "a": [],
                "b": [],
                "c": [],
                "long": [],
                "h_max": [],
                "job_index": job_i,
            })
            bucket["job_index"] = job_i
            for row in evals:
                if row.get("h_max") is not None:
                    bucket["h_max"].append(float(row["h_max"]))
                if kind == "reflex-a":
                    bucket["a"].append(float(row["difference_hz"]))
                elif kind == "reflex-b":
                    bucket["b"].append(float(row["difference_hz"]))
                elif kind == "reflex-c":
                    bucket["c"].append(float(row["difference_hz"]))
                elif kind == "long":
                    bucket["long"].append(row)
    results: list[dict[str, Any]] = []
    for idx in sorted(by_index):
        bucket = by_index[idx]
        if len(bucket["a"]) != 6:
            raise ValueError(f"candidate {idx} has {len(bucket['a'])} (a) rows, expected 6")
        if len(bucket["b"]) != 10:
            raise ValueError(f"candidate {idx} has {len(bucket['b'])} (b) rows, expected 10")
        if len(bucket["c"]) != 10:
            raise ValueError(f"candidate {idx} has {len(bucket['c'])} (c) rows, expected 10")
        if len(bucket["long"]) != 10:
            raise ValueError(f"candidate {idx} has {len(bucket['long'])} R-long rows, expected 10")
        job_i = int(bucket["job_index"])
        bare_rows = bares.get(job_i) or []
        if len(bare_rows) != 10:
            raise ValueError(f"job {job_i} has {len(bare_rows)} T2 bare rows, expected 10")
        a = bucket["a"]
        b = bucket["b"]
        upstream_c = bucket["c"]
        upstream_bare = [float(row["difference_hz"]) for row in bare_rows]
        job_bare_mean = sum(upstream_bare) / len(upstream_bare)
        cand = dict(bucket["candidate"])
        t0_ret = cand.get("retention")
        if t0_ret is None:
            raise ValueError(f"candidate {idx} has no T0 extended retention")
        t0_ret_f = float(t0_ret)
        candidate_ff = {
            "upstream": upstream_c,
            "extended": [t0_ret_f * 56.0] * 10,
        }
        bare_ff = {
            "upstream": upstream_bare,
            "extended": [56.0] * 10,
        }
        h_max = max(bucket["h_max"]) if bucket["h_max"] else None
        scored = t2_reflex_probe(
            a, b, candidate_ff, bare_ff,
            h_max=h_max,
            sub_tier=cand.get("sub_tier"),
            job_bare_mean=job_bare_mean,
            dt_ms=dt_ms,
        )
        long = long_decision(bucket["long"], dt_ms=dt_ms)
        flags = list(scored.get("flags") or [])
        for flag in long.get("flags") or []:
            if flag not in flags:
                flags.append(flag)
        results.append({
            **cand,
            **scored,
            "candidate_index": idx,
            "long_passed": bool(long["long_passed"]),
            "long_rows": long.get("long_rows"),
            "job_bare_mean": job_bare_mean,
            "flags": flags,
            "deepest": "T2",
        })
    return {
        "candidates": results,
        "n_candidates": len(results),
        "n_tasks": n_tasks,
        "n_reflex_passed": sum(1 for row in results if row.get("reflex_passed")),
        "n_reflex_harmonised": sum(
            1 for row in results if "reflex-harmonised" in (row.get("flags") or [])
        ),
        "n_long_passed": sum(1 for row in results if row.get("long_passed")),
        "wall_per_brain_s": rates,
        "dt_ms": dt_ms,
    }


def t0_unit_list(sub_tier: str) -> list[dict[str, Any]]:
    """Every T0 unit, plus 3a baseline rows. Not including bare references."""
    units: list[dict[str, Any]] = []
    pair_list = gaba_kc_pairs() if sub_tier == "T3d" else pairs()
    for g_gaba, g_glu in pair_list:
        for setting in grid_of(sub_tier):
            row = {
                "sub_tier": sub_tier,
                "g_gaba": g_gaba,
                "g_glu": g_glu,
                "setting": setting,
                "M": mechanism_strength(sub_tier, setting),
                "baseline": False,
                "sigma_th": 0.0,
                "optic_exemption": False,
                "n_bg": 100,
            }
            row["engine_model"] = unit_engine_model(row)
            if sub_tier == "T3d":
                row["g_gaba_kc"] = float(setting["g_gaba_kc"])
            units.append(row)
    if sub_tier == "T3a":
        for g_gaba, g_glu in baseline_pairs():
            units.append({
                "sub_tier": sub_tier,
                "engine_model": "lif",
                "g_gaba": g_gaba,
                "g_glu": g_glu,
                "setting": None,
                "M": 0.0,
                "baseline": True,
                "sigma_th": 0.0,
                "optic_exemption": False,
                "n_bg": 100,
            })
    return units


def t0_tasks(sub_tier: str, rho_mech: float, identity: dict[str, Any] | None = None) -> dict[str, Any]:
    """T0 tasks and jobs under section 6.5. Units: brain s and worker-seconds."""
    cfg = load_config()
    b = max_task_brain_s(rho_mech, cfg)
    if b < 6:
        return {"launch": False, "reason": "one-seed task exceeds B", "B": b, "jobs": []}
    units = t0_unit_list(sub_tier)
    seed_chunk = 10
    if b < T0_BRAIN_S_PER_TASK:
        seed_chunk = max(1, b // 6)
    tasks: list[dict[str, Any]] = []
    seeds = list(range(1, 11))
    for unit in units:
        for start in range(0, 10, seed_chunk):
            chunk = seeds[start:start + seed_chunk]
            tasks.append({
                "kind": "unit" if not unit["baseline"] else "baseline",
                "unit": unit,
                "seeds": chunk,
                "brain_s": 6 * len(chunk),
                "identity": identity or {},
            })
    bare_brain = 6 * (10 if seed_chunk == 10 else seed_chunk)
    reserve = task_worker_s(bare_brain, rho_mech, cfg)
    try:
        jobs = pack_tasks(tasks, rho_mech, cfg, reserve_s=reserve)
    except ValueError:
        return {"launch": False, "reason": "one-seed task exceeds B", "B": b, "jobs": []}
    packed: list[list[dict[str, Any]]] = []
    for index, job_tasks in enumerate(jobs):
        bare = {
            "kind": "bare",
            "unit": None,
            "seeds": seeds if seed_chunk == 10 else seeds[:seed_chunk],
            "brain_s": bare_brain,
            "identity": identity or {},
            "job_index": index,
        }
        packed.append(job_tasks + [bare])
    t0_brain = sum(t["brain_s"] for job in packed for t in job)
    return {
        "launch": True,
        "B": b,
        "rho_mech": rho_mech,
        "tasks": [t for job in packed for t in job],
        "jobs": packed,
        "t0_brain_s": t0_brain,
        "n_jobs": len(packed),
        "n_tasks": sum(len(job) for job in packed),
    }


def t3d_wave_tasks(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    """T0 and T1 of all 24 3d units in one IBM wave, three boxes at most.

    Packing uses the IBM T0 smoke rate 45.75. T1 slice width uses
    T3D_T1_SLICE_WORKER_S so one 10 s-probe task fits REST_TIMEOUT_S 9000.
    """
    cfg = load_config()
    ibm = ibm_config(cfg)
    pack_rate = ibm["worker_s_per_brain_s"]
    slice_rate = max(pack_rate, T3D_T1_SLICE_WORKER_S)
    rate = pack_rate
    makespan = ibm_makespan_s(cfg)
    workers = ibm["workers"]
    job_cap = workers * makespan
    units = t0_unit_list("T3d")
    t0: list[dict[str, Any]] = []
    seeds = list(range(1, 11))
    for unit in units:
        t0.append({
            "kind": "unit",
            "unit": unit,
            "seeds": seeds,
            "brain_s": T0_BRAIN_S_PER_TASK,
            "identity": identity or {},
        })
    t1 = t1_tasks(
        units, 1.0, identity,
        worker_s_per_brain_s=slice_rate,
        makespan=makespan,
        job_cap_s=job_cap * 100.0,
    )
    if not t1.get("launch"):
        return {
            "launch": False,
            "reason": t1.get("reason") or "T1 packing failed",
            "B": t1.get("B"),
            "jobs": [],
            "n_jobs": 0,
            "n_tasks": 0,
            "t0_brain_s": 0,
            "t1_brain_s": 0,
        }
    combined = list(t0) + list(t1["tasks"])
    n_bare = 2
    bare_cost = task_worker_s(T0_BRAIN_S_PER_TASK, 1.0, cfg, worker_s_per_brain_s=rate)
    try:
        packed = pack_tasks(
            combined, 1.0, cfg,
            reserve_s=bare_cost,
            worker_s_per_brain_s=rate,
            makespan=makespan,
            job_cap_s=job_cap,
        )
    except ValueError as exc:
        return {"launch": False, "reason": str(exc), "B": t1.get("B"), "jobs": []}
    jobs: list[list[dict[str, Any]]] = []
    for index, job_tasks in enumerate(packed):
        if index < n_bare:
            job_tasks = list(job_tasks) + [{
                "kind": "bare",
                "unit": None,
                "seeds": seeds,
                "brain_s": T0_BRAIN_S_PER_TASK,
                "identity": identity or {},
                "job_index": index,
            }]
        jobs.append(job_tasks)
    t0_brain = sum(float(t["brain_s"]) for job in jobs for t in job if t["kind"] in ("unit", "bare"))
    t1_brain = sum(float(t["brain_s"]) for job in jobs for t in job if t["kind"] == "t1")
    n_jobs = len(jobs)
    launch = n_jobs <= 3
    for job in jobs:
        has_unit = any(t["kind"] == "unit" for t in job)
        has_bare = any(t["kind"] == "bare" for t in job)
        if has_unit and not has_bare:
            launch = False
    return {
        "launch": launch,
        "reason": None if launch else (
            f"{n_jobs} jobs exceeds three boxes"
            if n_jobs > 3
            else "a T0 unit job has no same-job bare"
        ),
        "B": t1.get("B"),
        "rho_mech": 1.0,
        "slices": t1.get("slices"),
        "t1_slice_worker_s_per_brain_s": slice_rate,
        "pack_worker_s_per_brain_s": pack_rate,
        "tasks": [t for job in jobs for t in job],
        "jobs": jobs,
        "t0_brain_s": t0_brain,
        "t1_brain_s": t1_brain,
        "n_jobs": n_jobs,
        "n_tasks": sum(len(job) for job in jobs),
        "n_units": len(units),
        "ibm": ibm,
        "makespan_s": makespan,
    }


def t3d_plan_record() -> dict[str, Any]:
    """rest-T3d-plan.json body. T0 and T1 in one IBM wave. No B-mech."""
    packed = t3d_wave_tasks()
    cfg = load_config()
    rho_sfa = sfa_rho_mech()
    rho_blend = (1.0 + rho_sfa) / 2.0
    t0_brain = float(packed.get("t0_brain_s") or 0)
    t1_brain = float(packed.get("t1_brain_s") or 0)
    admitted = int(round(t1_brain / T1_BRAIN_S_PER_UNIT)) if t1_brain else 0
    projection = projection_engine_hours(
        t0_brain_s=t0_brain,
        admitted_units=admitted,
        rho_mech=rho_blend,
    )
    ibm_engine_h = (t0_brain + t1_brain + T2_BRAIN_S) * ibm_config()["worker_s_per_brain_s"] / 3600.0
    return {
        "class": "development",
        "sub_tier": "T3d",
        "engine_model": "lif",
        "rho_mech": 1.0,
        "rho_sfa": rho_sfa,
        "rho_blend": rho_blend,
        "q_plan": Q_PLAN,
        "pairs": gaba_kc_pairs(),
        "grid": gaba_kc_grid(),
        "units": t0_unit_list("T3d"),
        "baseline": False,
        "camber": cfg["camber"],
        "ibm": packed.get("ibm") or ibm_config(cfg),
        "job_shapes": {
            "B_brain_s": packed.get("B"),
            "n_jobs": packed.get("n_jobs"),
            "n_tasks": packed.get("n_tasks"),
            "t0_brain_s": packed.get("t0_brain_s"),
            "t1_brain_s": packed.get("t1_brain_s"),
            "n_units": packed.get("n_units"),
            "slices": packed.get("slices"),
            "t1_slice_worker_s_per_brain_s": packed.get("t1_slice_worker_s_per_brain_s"),
            "pack_worker_s_per_brain_s": packed.get("pack_worker_s_per_brain_s"),
            "launch": packed.get("launch"),
            "reason": packed.get("reason"),
            "wave": "T0+T1",
            "max_boxes": 3,
            "makespan_s": packed.get("makespan_s"),
        },
        "brain_s_at_caps": t0_brain + t1_brain + T2_BRAIN_S,
        "ibm_engine_hours_at_caps": ibm_engine_h,
        "cap_projection_engine_hours": projection,
        "t1_max_units": cfg["tier3"]["t1_max_units"],
        "cap_engine_hours": cfg["tier3"]["cap_engine_hours"],
    }


def plan_record(sub_tier: str, rho_mech: float, *, engine_model: str | None = None) -> dict[str, Any]:
    """rest-T3X-plan.json body. Invalid if rho_mech is not the recorded B-mech value."""
    if sub_tier == "T3d":
        return t3d_plan_record()
    packed = t0_tasks(sub_tier, rho_mech)
    cfg = load_config()
    model = engine_model or ENGINE_MODEL[sub_tier]
    projection_t0 = projection_engine_hours(
        t0_brain_s=float(packed.get("t0_brain_s") or 0),
        admitted_units=0,
        rho_mech=rho_mech,
    )
    return {
        "class": "development",
        "sub_tier": sub_tier,
        "engine_model": model,
        "rho_mech": rho_mech,
        "q_plan": Q_PLAN,
        "pairs": pairs(),
        "grid": grid_of(sub_tier),
        "units": t0_unit_list(sub_tier),
        "baseline": sub_tier == "T3a",
        "camber": cfg["camber"],
        "job_shapes": {
            "B_brain_s": packed.get("B"),
            "n_jobs": packed.get("n_jobs"),
            "n_tasks": packed.get("n_tasks"),
            "t0_brain_s": packed.get("t0_brain_s"),
            "launch": packed.get("launch"),
            "reason": packed.get("reason"),
        },
        "cap_projection_t0_engine_hours": projection_t0,
        "t1_max_units": cfg["tier3"]["t1_max_units"],
        "cap_engine_hours": cfg["tier3"]["cap_engine_hours"],
    }


def run_t3a() -> dict[str, Any]:
    """STAGE T3a: decision record is written by the Camber driver."""
    return {"status": "recorded", "class": "development", "note": "T3a runs on Camber"}


def run_t3b() -> dict[str, Any]:
    return {"status": "recorded", "class": "development", "note": "T3b runs on Camber"}


def run_t3c() -> dict[str, Any]:
    return {"status": "recorded", "class": "development", "note": "T3c runs on Camber"}


def run_t3d() -> dict[str, Any]:
    return {"status": "recorded", "class": "development", "note": "T3d runs on IBM after GO WP26"}


STAGE = {"T3a": run_t3a, "T3b": run_t3b, "T3c": run_t3c, "T3d": run_t3d}


def setting_from_unit(unit: dict[str, Any] | None, *, bare: bool = False):
    """Rest-map Setting for a unit, including g_gaba_kc (default 1)."""
    from flyonenomics.drive.rest_map import Setting

    if bare or unit is None:
        return Setting(1.0, 1.0)
    setting = unit.get("setting") or {}
    return Setting(
        g_gaba=float(unit["g_gaba"]),
        g_glu=float(unit["g_glu"]),
        sigma_th=float(unit.get("sigma_th", 0.0)),
        optic_exemption=bool(unit.get("optic_exemption", False)),
        n_bg=int(unit.get("n_bg", 100)),
        g_gaba_kc=float(setting.get("g_gaba_kc", unit.get("g_gaba_kc", 1.0))),
    )


def ibm_config(cfg: dict[str, Any] | None = None) -> dict[str, float]:
    """IBM shaping constants (SPEC-P2 8.2). Units: workers, s, worker-s/brain-s."""
    record = cfg or load_config()
    camber = record["camber"]
    ibm = record.get("ibm") or {}
    return {
        "workers": float(ibm.get("workers", camber["workers"])),
        "worker_s_per_brain_s": float(ibm.get("worker_s_per_brain_s", 45.75)),
        "setup_s": float(ibm.get("setup_s", camber["setup_s"])),
        "timeout_s": float(ibm.get("timeout_s", camber["timeout_s"])),
        "build_s": float(camber["build_s"]),
    }


def ibm_makespan_s(cfg: dict[str, Any] | None = None) -> float:
    """IBM box makespan: timeout minus setup, no Camber 1.25 margin."""
    ibm = ibm_config(cfg)
    return ibm["timeout_s"] - ibm["setup_s"]


def sfa_rho_mech() -> float:
    """Recorded B-mech ρ for lif+sfa, used in the 3d cap blend."""
    path = ROOT / "validation/records/p2/bench-mech-sfa.json"
    if path.is_file():
        return float(json.loads(read_text(path))["rho_mech"])
    return SFA_RHO_FALLBACK


def section_for_unit(unit: dict[str, Any] | None, *, mask_digest: str | None = None) -> dict[str, Any] | None:
    """Drive-file mechanisms section for a T0 unit, or null for lif / baseline."""
    if unit is None or unit.get("baseline") or not unit.get("setting"):
        return None
    sub = unit["sub_tier"]
    if sub == "T3e":
        return None
    setting = dict(unit["setting"])
    if sub == "T3d":
        block = {key: value for key, value in setting.items() if key != "g_gaba_kc"}
        if block.get("b_mv") is None:
            return None
        if mask_digest is not None:
            block["mask_sha256"] = mask_digest
        section = {name: None for name in ("adaptation", "depression", "conductance_inhibition")}
        section["adaptation"] = block
        return section
    block_name = BLOCK_NAME[sub]
    if mask_digest is not None and block_name != "conductance_inhibition":
        setting["mask_sha256"] = mask_digest
    section = {name: None for name in ("adaptation", "depression", "conductance_inhibition")}
    section[block_name] = setting
    return section


def resolve_unit_mechanisms(unit: dict[str, Any] | None):
    """Mechanisms object and drive section for one T0 unit, or both None."""
    from flyonenomics.drive.mechanisms import mask_sha256, mechanisms_from_section, real_scope_mask

    section = section_for_unit(unit)
    if section is None or unit is None:
        return None, None
    sub = unit["sub_tier"]
    block_name = "adaptation" if sub == "T3d" else BLOCK_NAME[sub]
    n = 1
    if block_name != "conductance_inhibition":
        block = section[block_name]
        if block is None:
            return None, None
        mask = real_scope_mask(block["scope"])
        block["mask_sha256"] = mask_sha256(mask)
        n = int(mask.shape[0])
    return mechanisms_from_section(section, n=n), section


def t0_worker(payload: dict[str, Any]) -> str:
    """One T0 child: one build, then its seeds of silent and sugar, 1 s each."""
    import json
    import time
    from pathlib import Path

    from flyonenomics.drive.rest_map import _build_engine, _probe

    path = Path(payload["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite evaluation evidence: {path}")
    deadline = time.monotonic() + payload["wall_cap_s"]
    unit = payload.get("unit")
    bare = payload["kind"] == "bare"
    setting = setting_from_unit(unit, bare=bare)
    mechs, section = (None, None) if bare else resolve_unit_mechanisms(unit)
    identity = payload["identity"]
    dt_ms = payload.get("dt_ms")
    meta = {
        **identity,
        "stage": "T0",
        "kind": payload["kind"],
        "task_id": path.stem,
        "plan_sha256": payload["plan_sha256"],
        "engine_model": "lif" if bare or not unit or unit.get("baseline") else unit_engine_model(unit),
        "setting": None if (bare or not unit) else unit.get("setting"),
        "unit": unit,
        "dt_ms": dt_ms,
    }
    t_build = time.monotonic()
    with path.open("x") as handle:
        def emit(row: dict[str, Any]) -> None:
            handle.write(json.dumps({**meta, **row}, allow_nan=False) + "\n")
            handle.flush()

        try:
            built = _build_engine(
                setting, mode="extended", bare=bare, feedforward=True,
                mechanisms=mechs, mechanisms_section=section,
                dt_ms=dt_ms,
            )
            build_s = time.monotonic() - t_build
            emit({"kind": "task-build", "build_s": build_s})
            brain_s = 0.0
            for seed in payload["seeds"]:
                silent = _probe(built, 0.0, int(seed), seconds=1.0, deadline=deadline)
                sugar = _probe(built, 0.0, int(seed), seconds=1.0, active=True, deadline=deadline)
                brain_s += 6.0
                a_sfa = None
                engine = built["engine"]
                if engine.engine_model() == "lif+sfa":
                    since = int(round(2000.0 / engine.dt_ms))
                    traces = engine.mechanism_traces(since)
                    if traces.a_sfa_mv is not None:
                        a_sfa = float(traces.a_sfa_mv.mean())
                h_vals = [p.get("h_max") for p in (silent, sugar) if p.get("h_max") is not None]
                emit({
                    "kind": "evaluation",
                    "seed": int(seed),
                    "silent": silent,
                    "sugar": sugar,
                    "difference_hz": sugar["mn9_hz"] - silent["mn9_hz"],
                    "mn9_a_sfa_mv": a_sfa,
                    "h_max": max(h_vals) if h_vals else None,
                })
            wall_s = time.monotonic() - t_build - build_s
            emit({
                "kind": "task-complete",
                "evaluations": len(payload["seeds"]),
                "build_s": build_s,
                "wall_s": wall_s,
                "brain_s": brain_s,
                "wall_per_brain_s": wall_s / brain_s if brain_s else None,
            })
        except Exception as exc:
            emit({"kind": "task-error", "error": f"{type(exc).__name__}: {exc}"})
            raise
    return str(path)


def t1_worker(payload: dict[str, Any]) -> str:
    """One T1 child: one build, then one seed's slice of R-screen weights."""
    import json
    import time
    from pathlib import Path

    from flyonenomics.drive.rest_map import _build_engine, _probe

    path = Path(payload["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite evaluation evidence: {path}")
    deadline = time.monotonic() + payload["wall_cap_s"]
    unit = payload["unit"]
    setting = setting_from_unit(unit)
    mechs, section = resolve_unit_mechanisms(unit)
    identity = payload["identity"]
    dt_ms = payload.get("dt_ms")
    meta = {
        **identity,
        "stage": "T1",
        "kind": "t1",
        "task_id": path.stem,
        "plan_sha256": payload["plan_sha256"],
        "engine_model": unit_engine_model(unit),
        "setting": unit.get("setting"),
        "unit": unit,
        "seed": payload["seed"],
        "slice": payload["slice"],
        "dt_ms": dt_ms,
    }
    t_build = time.monotonic()
    with path.open("x") as handle:
        def emit(row: dict[str, Any]) -> None:
            handle.write(json.dumps({**meta, **row}, allow_nan=False) + "\n")
            handle.flush()

        try:
            built = _build_engine(
                setting, mode="dark", bare=False, feedforward=False,
                mechanisms=mechs, mechanisms_section=section,
                dt_ms=dt_ms,
            )
            built = _maybe_apply_arm(built, unit)
            build_s = time.monotonic() - t_build
            emit({"kind": "task-build", "build_s": build_s})
            brain_s = 0.0
            for weight, seed in payload["probes"]:
                row = _probe(built, float(weight), int(seed), seconds=10.0, edge_s=1.0, deadline=deadline)
                brain_s += 12.0
                emit({"kind": "evaluation", **row})
            wall_s = time.monotonic() - t_build - build_s
            emit({
                "kind": "task-complete",
                "evaluations": len(payload["probes"]),
                "build_s": build_s,
                "wall_s": wall_s,
                "brain_s": brain_s,
                "wall_per_brain_s": wall_s / brain_s if brain_s else None,
            })
        except Exception as exc:
            emit({"kind": "task-error", "error": f"{type(exc).__name__}: {exc}"})
            raise
    return str(path)


def t2_worker(payload: dict[str, Any]) -> str:
    """One T2 child: one build, then one seed of R-reflex (a)/(b)/(c), R-long, or bare."""
    import json
    import time
    from pathlib import Path

    from flyonenomics.drive.rest_map import _build_engine, _probe

    path = Path(payload["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite evaluation evidence: {path}")
    deadline = time.monotonic() + payload["wall_cap_s"]
    kind = payload["kind"]
    candidate = payload.get("candidate")
    bare = kind == "bare"
    if bare or candidate is None:
        setting = setting_from_unit(None, bare=True)
        mechs, section = None, None
        engine_model = "lif"
        setting_row = None
    else:
        setting = setting_from_unit(candidate)
        mechs, section = resolve_unit_mechanisms(candidate)
        engine_model = unit_engine_model(candidate)
        setting_row = candidate.get("setting")
    if kind in ("reflex-a", "reflex-b"):
        mode, feedforward = "extended", False
    elif kind in ("reflex-c", "bare"):
        mode, feedforward = "upstream", True
    elif kind == "long":
        mode, feedforward = "dark", False
    else:
        raise ValueError(f"unknown T2 kind {kind}")
    identity = payload["identity"]
    dt_ms = payload.get("dt_ms")
    meta = {
        **identity,
        "stage": "T2",
        "kind": kind,
        "task_id": path.stem,
        "plan_sha256": payload["plan_sha256"],
        "engine_model": engine_model,
        "setting": setting_row,
        "candidate": candidate,
        "candidate_index": payload.get("candidate_index"),
        "seed": payload["seed"],
        "w_bg": payload.get("w_bg"),
        "dt_ms": dt_ms,
    }
    t_build = time.monotonic()
    with path.open("x") as handle:
        def emit(row: dict[str, Any]) -> None:
            handle.write(json.dumps({**meta, **row}, allow_nan=False) + "\n")
            handle.flush()

        try:
            built = _build_engine(
                setting, mode=mode, bare=bare, feedforward=feedforward,
                mechanisms=mechs, mechanisms_section=section,
                dt_ms=dt_ms,
            )
            build_s = time.monotonic() - t_build
            emit({"kind": "task-build", "build_s": build_s})
            weight = float(payload.get("w_bg") or 0.0)
            seed = int(payload["seed"])
            if kind == "long":
                row = _probe(
                    built, weight, seed, seconds=30.0, edge_s=5.0, deadline=deadline,
                )
                brain_s = T2_LONG_BRAIN_S
                emit({"kind": "evaluation", **row})
                n_eval = 1
            else:
                silent = _probe(built, weight, seed, seconds=1.0, deadline=deadline)
                sugar = _probe(
                    built, weight, seed, seconds=1.0, active=True, deadline=deadline,
                )
                brain_s = T2_REFLEX_BRAIN_S
                h_vals = [p.get("h_max") for p in (silent, sugar) if p.get("h_max") is not None]
                emit({
                    "kind": "evaluation",
                    "seed": seed,
                    "w_bg": weight,
                    "silent": silent,
                    "sugar": sugar,
                    "difference_hz": sugar["mn9_hz"] - silent["mn9_hz"],
                    "h_max": max(h_vals) if h_vals else None,
                })
                n_eval = 1
            wall_s = time.monotonic() - t_build - build_s
            emit({
                "kind": "task-complete",
                "evaluations": n_eval,
                "build_s": build_s,
                "wall_s": wall_s,
                "brain_s": brain_s,
                "wall_per_brain_s": wall_s / brain_s if brain_s else None,
            })
        except Exception as exc:
            emit({"kind": "task-error", "error": f"{type(exc).__name__}: {exc}"})
            raise
    return str(path)


def closest_3d_unit(*, sigma_th: float = 0.0) -> dict[str, Any]:
    """T3d closest miss substrate. Units: mV, ratios. Item 86 unit."""
    return {
        "sub_tier": "T3d",
        "engine_model": "lif",
        "g_gaba": 1.0,
        "g_glu": 4.0,
        "setting": {"g_gaba_kc": 6.0},
        "M": 6.0,
        "sigma_th": float(sigma_th),
        "optic_exemption": False,
        "n_bg": 100,
        "g_gaba_kc": 6.0,
        "w_bg": 0.85,
        "pair_weights": [0.85, 0.9],
        "flags": [],
        "retention": None,
        "difference_hz": None,
        "job_id": None,
        "baseline": False,
    }


def freeze_unit() -> dict[str, Any]:
    """Item 90 sigma_th 1 R-screen passer. Units: mV, ratios."""
    unit = closest_3d_unit(sigma_th=FREEZE_SIGMA_TH)
    unit["w_bg"] = FREEZE_W_BG
    unit["pair_weights"] = list(FREEZE_PAIR_WEIGHTS)
    return unit


def task_pack_cost(task: dict[str, Any], cfg: dict[str, Any] | None = None) -> float:
    """Worker-seconds of one mixed-rate task. Units: s."""
    rate = float(task.get("pack_rate") or WP27_PACK_RATE)
    return task_worker_s(float(task["brain_s"]), 1.0, cfg, worker_s_per_brain_s=rate)


def pack_mixed_rate(
    tasks: list[dict[str, Any]],
    cap: float,
    cfg: dict[str, Any] | None = None,
) -> list[list[dict[str, Any]]]:
    """Fill jobs under a worker-second cap with per-task pack rates."""
    if cap <= 0:
        raise ValueError("job cap is not positive")
    jobs: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    cost = 0.0
    for task in tasks:
        add = task_pack_cost(task, cfg)
        if add > cap:
            raise ValueError("one task exceeds the job cap")
        if current and cost + add > cap:
            jobs.append(current)
            current = []
            cost = 0.0
        current.append(task)
        cost += add
    if current:
        jobs.append(current)
    return jobs


def wp27_list_usd(jobs: list[list[dict[str, Any]]], cfg: dict[str, Any] | None = None) -> float:
    """List dollars of packed jobs at the IBM profile rate. Units: USD."""
    ibm = ibm_config(cfg)
    workers = float(ibm["workers"])
    setup = float(ibm["setup_s"])
    hours = 0.0
    for job in jobs:
        worker_s = sum(task_pack_cost(task, cfg) for task in job)
        hours += (worker_s / workers + setup) / 3600.0
    return hours * WP27_USD_PER_H


def diag_exp1_tasks(identity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Experiment 1 tasks: 12 long, paired sugar, FF (c), and ten-seed bare."""
    ident = identity or {}
    unit = closest_3d_unit()
    tasks: list[dict[str, Any]] = []
    for clamp in (True, False):
        pools = "clamped" if clamp else "free"
        for weight in DIAG_PAIR_WEIGHTS:
            for seed in SEEDS:
                tasks.append({
                    "kind": "diag-long",
                    "unit": unit,
                    "w_bg": float(weight),
                    "seed": int(seed),
                    "clamp": bool(clamp),
                    "pools": pools,
                    "brain_s": DIAG_LONG_S,
                    "pack_rate": WP27_LONG_RATE,
                    "identity": ident,
                })
    sugar_s = 10 * 2 * DIAG_SUGAR_ENGINE_S
    for weight in DIAG_PAIR_WEIGHTS:
        tasks.append({
            "kind": "diag-sugar",
            "unit": unit,
            "w_bg": float(weight),
            "seeds": list(LONG_SEEDS),
            "measure_s": DIAG_SUGAR_MEASURE_S,
            "clamp": True,
            "brain_s": sugar_s,
            "pack_rate": WP27_PACK_RATE,
            "identity": ident,
        })
    tasks.append({
        "kind": "diag-ff",
        "unit": unit,
        "w_bg": 0.0,
        "seeds": list(LONG_SEEDS),
        "clamp": True,
        "brain_s": T0_BRAIN_S_PER_TASK,
        "pack_rate": WP27_PACK_RATE,
        "identity": ident,
    })
    tasks.append({
        "kind": "bare",
        "unit": None,
        "seeds": list(LONG_SEEDS),
        "brain_s": T0_BRAIN_S_PER_TASK,
        "pack_rate": WP27_PACK_RATE,
        "identity": ident,
        "job_index": 0,
    })
    return tasks


def sigma_exp2_tasks(identity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Experiment 2: sigma grid R-screen, T0 per sigma, sugar at reference weights."""
    ident = identity or {}
    tasks: list[dict[str, Any]] = []
    screen_weights = list(SIGMA_WEIGHTS)
    for sigma in SIGMA_TH_GRID:
        unit = closest_3d_unit(sigma_th=sigma)
        compact = _t1_unit(unit)
        for seed in SEEDS:
            tasks.append({
                "kind": "t1",
                "unit_index": 0,
                "unit": compact,
                "seed": int(seed),
                "slice": [0, len(screen_weights)],
                "probes": [(float(w), int(seed)) for w in screen_weights],
                "brain_s": 12 * len(screen_weights),
                "pack_rate": WP27_PACK_RATE,
                "identity": ident,
                "sigma_th": float(sigma),
            })
        tasks.append({
            "kind": "unit",
            "unit": compact,
            "seeds": list(LONG_SEEDS),
            "brain_s": T0_BRAIN_S_PER_TASK,
            "pack_rate": WP27_PACK_RATE,
            "identity": ident,
            "sigma_th": float(sigma),
        })
        for weight in SIGMA_WEIGHTS[:-1]:
            tasks.append({
                "kind": "sigma-sugar",
                "unit": compact,
                "w_bg": float(weight),
                "seeds": list(LONG_SEEDS),
                "measure_s": 1.0,
                "clamp": True,
                "brain_s": T0_BRAIN_S_PER_TASK,
                "pack_rate": WP27_PACK_RATE,
                "identity": ident,
                "sigma_th": float(sigma),
            })
    tasks.append({
        "kind": "bare",
        "unit": None,
        "seeds": list(LONG_SEEDS),
        "brain_s": T0_BRAIN_S_PER_TASK,
        "pack_rate": WP27_PACK_RATE,
        "identity": ident,
        "job_index": 1,
    })
    return tasks


def wp27_wave_tasks(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    """One IBM wave: experiment 1 then experiment 2. At most two boxes, $15 list."""
    cfg = load_config()
    ibm = ibm_config(cfg)
    makespan = ibm_makespan_s(cfg)
    cap = float(ibm["workers"]) * makespan
    exp1 = diag_exp1_tasks(identity)
    exp2 = sigma_exp2_tasks(identity)
    try:
        job0 = pack_mixed_rate(exp1, cap, cfg)
        job1 = pack_mixed_rate(exp2, cap, cfg)
    except ValueError as exc:
        return {"launch": False, "reason": str(exc), "jobs": [], "n_jobs": 0, "list_usd": 0.0}
    jobs = job0 + job1
    list_usd = wp27_list_usd(jobs, cfg)
    n_jobs = len(jobs)
    launch = n_jobs <= WP27_MAX_JOBS and list_usd <= WP27_CAP_USD
    reason = None
    if n_jobs > WP27_MAX_JOBS:
        reason = f"{n_jobs} jobs exceeds two boxes"
    elif list_usd > WP27_CAP_USD:
        reason = f"list ${list_usd:.2f} exceeds ${WP27_CAP_USD:.0f}"
    brain_s = sum(float(t["brain_s"]) for job in jobs for t in job)
    return {
        "launch": launch,
        "reason": reason,
        "jobs": jobs,
        "n_jobs": n_jobs,
        "n_tasks": sum(len(job) for job in jobs),
        "brain_s": brain_s,
        "list_usd": list_usd,
        "pack_worker_s_per_brain_s": WP27_PACK_RATE,
        "long_worker_s_per_brain_s": WP27_LONG_RATE,
        "max_instances": WP27_MAX_JOBS,
        "candidate_id": CLOSEST_3D_ID,
        "diagnostic": True,
    }


def wp27_plan_record() -> dict[str, Any]:
    """Launch plan for the WP27 diagnostic wave. Units: s, USD. No task payloads."""
    packed = wp27_wave_tasks()
    shapes = []
    for index, job in enumerate(packed["jobs"]):
        kinds: dict[str, int] = {}
        for task in job:
            kinds[task["kind"]] = kinds.get(task["kind"], 0) + 1
        shapes.append({
            "job_index": index,
            "n_tasks": len(job),
            "brain_s": sum(float(task["brain_s"]) for task in job),
            "kinds": kinds,
        })
    return {
        "class": "development",
        "sub_tier": "T3d",
        "stage": "diag",
        "wave": "wp27",
        "candidate_id": CLOSEST_3D_ID,
        "flags": ["diagnostic"],
        "admitted_t1": False,
        "admitted_t2": False,
        "diagnostic": True,
        "launch": packed["launch"],
        "reason": packed["reason"],
        "n_jobs": packed["n_jobs"],
        "n_tasks": packed["n_tasks"],
        "brain_s": packed["brain_s"],
        "list_usd": packed["list_usd"],
        "list_cap_usd": WP27_CAP_USD,
        "pack_worker_s_per_brain_s": packed["pack_worker_s_per_brain_s"],
        "long_worker_s_per_brain_s": packed["long_worker_s_per_brain_s"],
        "max_instances": packed["max_instances"],
        "sigma_th": list(SIGMA_TH_GRID),
        "sigma_weights": list(SIGMA_WEIGHTS),
        "pair_weights": list(DIAG_PAIR_WEIGHTS),
        "job_shapes": shapes,
        "ibm": ibm_config(),
    }


def freeze_exp4_tasks(identity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Experiment 4: freeze the sigma_th 1 passer. Item 90. Seeds 11-20."""
    ident = {**(identity or {}), "stage": "freeze"}
    compact = _t1_unit(freeze_unit())
    compact["w_bg"] = FREEZE_W_BG
    compact["pair_weights"] = list(FREEZE_PAIR_WEIGHTS)
    tasks: list[dict[str, Any]] = []
    for clamp in (True, False):
        pools = "clamped" if clamp else "free"
        for weight in FREEZE_PAIR_WEIGHTS:
            for seed in FREEZE_SEEDS:
                tasks.append({
                    "kind": "diag-long",
                    "unit": compact,
                    "w_bg": float(weight),
                    "seed": int(seed),
                    "clamp": bool(clamp),
                    "pools": pools,
                    "brain_s": DIAG_LONG_S,
                    "pack_rate": WP27_LONG_RATE,
                    "identity": ident,
                    "stage": "freeze",
                })
    sugar_s = len(FREEZE_SEEDS) * 2 * DIAG_SUGAR_ENGINE_S
    for weight in FREEZE_PAIR_WEIGHTS:
        tasks.append({
            "kind": "diag-sugar",
            "unit": compact,
            "w_bg": float(weight),
            "seeds": list(FREEZE_SEEDS),
            "measure_s": DIAG_SUGAR_MEASURE_S,
            "clamp": True,
            "brain_s": sugar_s,
            "pack_rate": WP27_PACK_RATE,
            "identity": ident,
            "stage": "freeze",
        })
    tasks.append({
        "kind": "diag-ff",
        "unit": compact,
        "w_bg": 0.0,
        "seeds": list(FREEZE_SEEDS),
        "clamp": True,
        "brain_s": T0_BRAIN_S_PER_TASK,
        "pack_rate": WP27_PACK_RATE,
        "identity": ident,
        "stage": "freeze",
    })
    tasks.append({
        "kind": "bare",
        "unit": None,
        "seeds": list(FREEZE_SEEDS),
        "brain_s": T0_BRAIN_S_PER_TASK,
        "pack_rate": WP27_PACK_RATE,
        "identity": ident,
        "job_index": 0,
        "stage": "freeze",
    })
    for seed in FREEZE_PERTURB_SEEDS:
        tasks.append({
            "kind": "t1",
            "unit_index": 0,
            "unit": compact,
            "seed": int(seed),
            "slice": [0, len(FREEZE_PERTURB_WEIGHTS)],
            "probes": [(float(weight), int(seed)) for weight in FREEZE_PERTURB_WEIGHTS],
            "brain_s": 12 * len(FREEZE_PERTURB_WEIGHTS),
            "pack_rate": WP27_PACK_RATE,
            "identity": ident,
            "stage": "freeze",
            "sigma_th": FREEZE_SIGMA_TH,
        })
    return tasks


def wp27_freeze_wave_tasks(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    """One IBM box for experiment 4. Cap $10 list."""
    cfg = load_config()
    ibm = ibm_config(cfg)
    makespan = ibm_makespan_s(cfg)
    cap = float(ibm["workers"]) * makespan
    tasks = freeze_exp4_tasks(identity)
    try:
        jobs = pack_mixed_rate(tasks, cap, cfg)
    except ValueError as exc:
        return {"launch": False, "reason": str(exc), "jobs": [], "n_jobs": 0, "list_usd": 0.0}
    list_usd = wp27_list_usd(jobs, cfg)
    n_jobs = len(jobs)
    launch = n_jobs <= WP27_FREEZE_MAX_JOBS and list_usd <= WP27_FREEZE_CAP_USD
    reason = None
    if n_jobs > WP27_FREEZE_MAX_JOBS:
        reason = f"{n_jobs} jobs exceeds one box"
    elif list_usd > WP27_FREEZE_CAP_USD:
        reason = f"list ${list_usd:.2f} exceeds ${WP27_FREEZE_CAP_USD:.0f}"
    brain_s = sum(float(task["brain_s"]) for job in jobs for task in job)
    return {
        "launch": launch,
        "reason": reason,
        "jobs": jobs,
        "n_jobs": n_jobs,
        "n_tasks": sum(len(job) for job in jobs),
        "brain_s": brain_s,
        "list_usd": list_usd,
        "pack_worker_s_per_brain_s": WP27_PACK_RATE,
        "long_worker_s_per_brain_s": WP27_LONG_RATE,
        "max_instances": WP27_FREEZE_MAX_JOBS,
        "candidate_id": FREEZE_ID,
        "diagnostic": True,
    }


def wp27_freeze_plan_record() -> dict[str, Any]:
    """Launch plan for the WP27 freeze wave. Units: s, USD. No task payloads."""
    packed = wp27_freeze_wave_tasks()
    shapes = []
    for index, job in enumerate(packed["jobs"]):
        kinds: dict[str, int] = {}
        for task in job:
            kinds[task["kind"]] = kinds.get(task["kind"], 0) + 1
        shapes.append({
            "job_index": index,
            "n_tasks": len(job),
            "brain_s": sum(float(task["brain_s"]) for task in job),
            "kinds": kinds,
        })
    return {
        "class": "development",
        "sub_tier": "T3d",
        "stage": "freeze",
        "wave": "wp27",
        "candidate_id": FREEZE_ID,
        "flags": ["diagnostic"],
        "admitted_t1": False,
        "admitted_t2": False,
        "diagnostic": True,
        "launch": packed["launch"],
        "reason": packed["reason"],
        "n_jobs": packed["n_jobs"],
        "n_tasks": packed["n_tasks"],
        "brain_s": packed["brain_s"],
        "list_usd": packed["list_usd"],
        "list_cap_usd": WP27_FREEZE_CAP_USD,
        "pack_worker_s_per_brain_s": packed["pack_worker_s_per_brain_s"],
        "long_worker_s_per_brain_s": packed["long_worker_s_per_brain_s"],
        "max_instances": packed["max_instances"],
        "sigma_th": FREEZE_SIGMA_TH,
        "pair_weights": list(FREEZE_PAIR_WEIGHTS),
        "seeds": list(FREEZE_SEEDS),
        "perturb_weights": list(FREEZE_PERTURB_WEIGHTS),
        "perturb_seeds": list(FREEZE_PERTURB_SEEDS),
        "job_shapes": shapes,
        "ibm": ibm_config(),
    }


def wp27_packed_wave(plan: dict[str, Any], identity: dict[str, Any] | None = None) -> dict[str, Any]:
    """Packed jobs for a WP27 plan: diag wave or freeze wave."""
    if plan.get("stage") == "freeze":
        return wp27_freeze_wave_tasks(identity)
    return wp27_wave_tasks(identity)


def _closest_3d_t0_retention() -> tuple[float, float]:
    """Recorded T3d T0 extended retention of the closest unit. Units: fraction, Hz."""
    record = json.loads(read_text(ROOT / "validation/records/p2/rest-T3d-T0.json"))
    for unit in record["units"]:
        setting = unit.get("setting") or {}
        if (float(unit["g_gaba"]) == 1.0 and float(unit["g_glu"]) == 4.0
                and float(unit.get("g_gaba_kc", setting.get("g_gaba_kc", 1.0))) == 6.0
                and unit.get("engine_model") == "lif" and setting.get("b_mv") is None):
            return float(unit["retention"]), float(unit["difference_hz"])
    raise ValueError("closest 3d T0 unit is missing")


def _diag_eval_rows(path: Path) -> list[dict[str, Any]]:
    rows = read_t0_task_rows(path)
    if not rows or rows[-1].get("kind") != "task-complete":
        raise ValueError(f"incomplete diagnostic task {path}")
    if any(row.get("kind") == "task-error" for row in rows):
        raise ValueError(f"errored diagnostic task {path}")
    return [row for row in rows if row.get("kind") == "evaluation"]


def collect_diag(
    jobs: list[tuple[Path, list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Score experiment 1. Diagnostic only: admits nothing to T1 or T2."""
    long_rows: list[dict[str, Any]] = []
    sugar: dict[float, list[dict[str, Any]]] = defaultdict(list)
    ff: list[dict[str, Any]] = []
    bare: list[dict[str, Any]] = []
    rates: list[float] = []
    n_tasks = 0
    for out, tasks in jobs:
        for task in tasks:
            n_tasks += 1
            path = task_ndjson_path(out, task)
            rows = read_t0_task_rows(path)
            complete = rows[-1]
            if complete.get("wall_per_brain_s") is not None:
                rates.append(float(complete["wall_per_brain_s"]))
            evals = [row for row in rows if row.get("kind") == "evaluation"]
            kind = task.get("kind")
            if kind == "diag-long":
                long_rows.extend(evals)
            elif kind == "diag-sugar":
                sugar[round(float(task["w_bg"]), 8)].extend(evals)
            elif kind == "diag-ff":
                ff.extend(evals)
            elif kind == "bare":
                if int(task.get("job_index", 0)) == 0:
                    bare.extend(evals)
    a: list[float] = []
    b: list[float] = []
    for weight in DIAG_PAIR_WEIGHTS:
        rows = sorted(sugar.get(round(float(weight), 8), []), key=lambda r: int(r["seed"]))
        diffs = [float(row["difference_hz"]) for row in rows]
        if weight == DIAG_PAIR_WEIGHTS[0]:
            b = diffs
        a.extend(diffs[:3])
    if len(a) != 6:
        raise ValueError(f"diagnostic (a) has {len(a)} rows, expected 6")
    if len(b) != 10:
        raise ValueError(f"diagnostic (b) has {len(b)} rows, expected 10")
    if len(ff) != 10:
        raise ValueError(f"diagnostic (c) has {len(ff)} rows, expected 10")
    if len(bare) != 10:
        raise ValueError(f"diagnostic bare has {len(bare)} rows, expected 10")
    t0_ret, t0_diff = _closest_3d_t0_retention()
    upstream_c = [float(row["difference_hz"]) for row in ff]
    upstream_bare = [float(row["difference_hz"]) for row in bare]
    job_bare_mean = sum(upstream_bare) / len(upstream_bare)
    candidate_ff = {
        "upstream": upstream_c,
        "extended": [t0_ret * 56.0] * 10,
    }
    bare_ff = {
        "upstream": upstream_bare,
        "extended": [56.0] * 10,
    }
    h_vals = [float(row["h_max"]) for row in (*long_rows, *ff, *bare) if row.get("h_max") is not None]
    for rows in sugar.values():
        h_vals.extend(float(row["h_max"]) for row in rows if row.get("h_max") is not None)
    scored = t2_reflex_probe(
        a, b, candidate_ff, bare_ff,
        h_max=max(h_vals) if h_vals else None,
        sub_tier="T3d",
        job_bare_mean=job_bare_mean,
    )
    flags = ["diagnostic", *(scored.get("flags") or [])]
    free_22r = []
    for row in long_rows:
        if row.get("pools") != "free":
            continue
        windows = row.get("windows") or {}
        for name, window in windows.items():
            gate = dict(window.get("median_22r") or {})
            free_22r.append({"seed": row.get("seed"), "w_bg": row.get("w_bg"), "window": name, **gate})
    median_passed = bool(free_22r) and all(bool(item.get("passed")) for item in free_22r)
    return {
        "class": "development",
        "sub_tier": "T3d",
        "stage": "diag",
        "candidate_id": CLOSEST_3D_ID,
        "flags": flags,
        "admitted_t1": False,
        "admitted_t2": False,
        "diagnostic": True,
        "n_tasks": n_tasks,
        "n_long": len(long_rows),
        "long": long_rows,
        "median_22r": {
            "rule": "2.2r: all-neuron median in [0.2, 5] Hz and <1 percent above 50 Hz",
            "free_pool_windows": free_22r,
            "passed": median_passed,
        },
        "reflex": {**scored, "flags": flags, "diagnostic": True},
        "job_bare_mean": job_bare_mean,
        "t0_retention": t0_ret,
        "t0_difference_hz": t0_diff,
        "mean_wall_per_brain_s": (sum(rates) / len(rates)) if rates else None,
    }


def collect_sigma(
    jobs: list[tuple[Path, list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Score experiment 2. Diagnostic: no T1/T2 admission from this record."""
    by_sigma: dict[float, list[dict[str, Any]]] = defaultdict(list)
    t0_by_sigma: dict[float, list[dict[str, Any]]] = defaultdict(list)
    sugar_by_key: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
    bare: list[dict[str, Any]] = []
    n_tasks = 0
    for out, tasks in jobs:
        for task in tasks:
            n_tasks += 1
            path = task_ndjson_path(out, task)
            evals = _diag_eval_rows(path)
            kind = task.get("kind")
            sigma = float((task.get("unit") or {}).get("sigma_th", task.get("sigma_th") or 0.0))
            if kind == "t1":
                by_sigma[sigma].extend(evals)
            elif kind == "unit":
                t0_by_sigma[sigma].extend(evals)
            elif kind == "sigma-sugar":
                sugar_by_key[(sigma, round(float(task["w_bg"]), 8))].extend(evals)
            elif kind == "bare":
                if int(task.get("job_index", 1)) == 1:
                    bare.extend(evals)
    setting = Setting(1.0, 4.0, sigma_th=0.0, optic_exemption=False, n_bg=100, g_gaba_kc=6.0)
    ranked: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    t0_rows: list[dict[str, Any]] = []
    upstream_bare = [float(row["difference_hz"]) for row in bare]
    job_bare_mean = (sum(upstream_bare) / len(upstream_bare)) if upstream_bare else None
    for sigma in SIGMA_TH_GRID:
        unit = closest_3d_unit(sigma_th=sigma)
        compact = _t1_unit(unit)
        rows = list(by_sigma.get(float(sigma), []))
        t0 = t0_by_sigma.get(float(sigma), [])
        diffs = [float(row["difference_hz"]) for row in t0]
        retention = t0_retention(sum(diffs) / len(diffs), job_bare_mean) if diffs and job_bare_mean else None
        t0_rows.append({
            **compact,
            "sigma_th": float(sigma),
            "difference_hz": (sum(diffs) / len(diffs)) if diffs else None,
            "retention": retention,
            "t0_passed": t0_passed(retention) if retention is not None else False,
            "seeds": len(diffs),
        })
        for weight in SIGMA_WEIGHTS[:-1]:
            scored = screen_candidate(setting, float(weight), rows)
            scored.update({
                **compact,
                "sigma_th": float(sigma),
                "w_bg": float(weight),
                "candidate_id": candidate_id({**compact, "w_bg": float(weight), "sigma_th": float(sigma)}),
            })
            if scored["screen_passed"]:
                a: list[float] = []
                pair = scored["pair_weights"]
                for w in pair:
                    sugar_rows = sorted(
                        sugar_by_key.get((float(sigma), round(float(w), 8)), []),
                        key=lambda r: int(r["seed"]),
                    )
                    a.extend(float(r["difference_hz"]) for r in sugar_rows[:3])
                low = round(float(pair[0]), 8)
                b_rows = sorted(sugar_by_key.get((float(sigma), low), []), key=lambda r: int(r["seed"]))
                b = [float(r["difference_hz"]) for r in b_rows]
                if len(a) == 6 and len(b) == 10 and len(diffs) == 10 and job_bare_mean is not None:
                    reflex = t2_reflex_probe(
                        a, b,
                        {"upstream": diffs, "extended": diffs},
                        {"upstream": upstream_bare, "extended": upstream_bare},
                        sub_tier="T3d",
                        job_bare_mean=job_bare_mean,
                    )
                    scored["reflex"] = {**reflex, "diagnostic": True}
                    scored["flags"] = ["diagnostic", *(reflex.get("flags") or [])]
                ranked.append(_sigma_screen_metrics(scored, rows))
            else:
                misses.append(_sigma_screen_metrics(scored, rows))
    closest = closest_miss(misses)
    failed_stage = None if ranked else "R-screen"
    return {
        "class": "development",
        "sub_tier": "T3d",
        "stage": "sigma",
        "engine_model": "lif",
        "flags": ["diagnostic"],
        "admitted_t1": False,
        "admitted_t2": False,
        "diagnostic": True,
        "n_tasks": n_tasks,
        "ranked": ranked,
        "failed_stage": failed_stage,
        "closest_miss": closest,
        "n_screen_passers": len(ranked),
        "t0": t0_rows,
        "job_bare_mean": job_bare_mean,
    }


def _sigma_screen_metrics(scored: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Attach pair F, KC and central means for RANKED WP27-sigma. Units: Hz."""
    pair = {round(float(w), 8) for w in (scored.get("pair_weights") or [])}
    pair_rows = [row for row in rows if round(float(row["w_bg"]), 8) in pair]
    f_vals = [v for v in (number(row.get("F")) for row in pair_rows) if v is not None]
    low = round(float(scored["w_bg"]), 8)
    low_rows = [row for row in rows if round(float(row["w_bg"]), 8) == low]
    kc = [v for v in (number((row.get("rates_hz") or {}).get("KC")) for row in low_rows) if v is not None]
    central = [v for v in (number((row.get("rates_hz") or {}).get("central")) for row in low_rows) if v is not None]
    scored["measured_F_max_pair"] = max(f_vals) if f_vals else None
    scored["measured_F_mean"] = (sum(f_vals) / len(f_vals)) if f_vals else None
    scored["measured_kc_hz_mean"] = (sum(kc) / len(kc)) if kc else None
    scored["measured_central_hz_mean"] = (sum(central) / len(central)) if central else None
    scored["deepest"] = "T1"
    return scored


def _sidecar_path(name: str | None, out: Path | None) -> Path | None:
    """Resolve a pulled npz next to the ndjson when the job path is gone."""
    if not name:
        return None
    path = Path(name)
    if path.exists():
        return path
    if out is not None:
        alt = Path(out) / path.name
        if alt.exists():
            return alt
    return None


def _f_mn9_from_npz(path: Path) -> tuple[float | None, float | None]:
    """FanoAccumulator F and MN9 Hz on [2, 12) from saved 1 ms counts."""
    import numpy as np

    from flyonenomics.drive.rest_map import fano_from_counts

    start, stop = WP27_SCORED_START_MS, WP27_SCORED_STOP_MS
    seconds = (stop - start) / 1000.0
    with load_npy(path) as data:
        pop = np.asarray(data["block_1ms"], dtype=np.int64)[:, start:stop].sum(axis=0)
        f_val = fano_from_counts(pop)
        mn9 = np.asarray(data["mn9_1ms"], dtype=np.float64)[start:stop]
        mn9_hz = float(mn9.sum() / seconds) if seconds > 0 else None
    return f_val, mn9_hz


def overlay_window_f_mn9(row: dict[str, Any], out: Path | None = None) -> dict[str, Any]:
    """Score T1-comparable F and MN9 on [2, 12) from the raw row (decision 95).

    flyo-11 staged `0fd2aed` still wrote `F` and `mn9_hz` on [1, 11). The 32 s
    rows already carry `windows.early` on [2, 12); the npz is the fallback.
    """
    scored = dict(row)
    early = (row.get("windows") or {}).get("early") or {}
    f_new = number((early.get("F_bins") or {}).get("1"))
    mn9_new = number(early.get("mn9_hz"))
    source = "windows.early" if (f_new is not None or mn9_new is not None) else None
    if f_new is None or mn9_new is None:
        npz_path = _sidecar_path(row.get("npz"), out)
        if npz_path is not None:
            f_npz, mn9_npz = _f_mn9_from_npz(npz_path)
            if f_new is None:
                f_new = f_npz
            if mn9_new is None:
                mn9_new = mn9_npz
            source = "npz" if source is None else source
    if f_new is not None:
        scored["F_recorded"] = row.get("F")
        scored["F"] = f_new
        scored["F_scored_window"] = WP27_SCORED_WINDOW
    if mn9_new is not None:
        scored["mn9_hz_recorded"] = row.get("mn9_hz")
        scored["mn9_hz"] = mn9_new
        scored["mn9_scored_window"] = WP27_SCORED_WINDOW
    if source is not None:
        scored["f_mn9_rescore_source"] = source
    return scored


def freeze_pair_screen(
    rows: list[dict[str, Any]],
    *,
    pair_weights: tuple[float, ...] | list[float] = FREEZE_PAIR_WEIGHTS,
    seeds: tuple[int, ...] | list[int] = FREEZE_SEEDS,
    gradedness_note: str = "item 90 freeze task list has no 0.85 mV gradedness point",
) -> dict[str, Any]:
    """Pair 2.3 gates on freeze seeds. No gradedness point."""
    lookup: dict[tuple[float, int], dict[str, Any]] = {}
    pair = tuple(round(float(w), 8) for w in pair_weights)
    seed_list = tuple(int(s) for s in seeds)
    for row in rows:
        key = (round(float(row["w_bg"]), 8), int(row["seed"]))
        if key in lookup:
            raise ValueError(f"duplicate freeze evaluation {key}")
        lookup[key] = row
    missing = [
        (weight, seed)
        for weight in pair
        for seed in seed_list
        if (round(float(weight), 8), int(seed)) not in lookup
    ]
    if missing:
        raise ValueError(f"freeze screen missing {missing}")
    pair_rows = [
        lookup[(round(float(weight), 8), int(seed))]
        for weight in pair
        for seed in seed_list
    ]

    def field_of(row: dict[str, Any], field: str) -> float | None:
        return number(row.get(field))

    def rate_of(row: dict[str, Any], group: str) -> float | None:
        return number((row.get("rates_hz") or {}).get(group))

    checks: dict[str, bool] = {}
    violations: dict[str, float] = {}
    for field, lo, hi, strict in (("F", None, 3, True), ("b", None, .05, True),
                                   ("stability_ratio", .5, 2, False)):
        vals = [field_of(row, field) for row in pair_rows]
        violations[field] = max(violation(v, lo, hi) for v in vals)
        checks[field] = all(
            v is not None and (lo is None or v >= lo) and (v < hi if strict else v <= hi)
            for v in vals
        )
    means: dict[float, dict[str, float | None]] = {}
    for weight in pair:
        w_rows = [lookup[(round(float(weight), 8), int(seed))] for seed in seed_list]
        means[float(weight)] = {
            group: (
                sum(v for v in (rate_of(row, group) for row in w_rows) if v is not None)
                / max(1, sum(1 for row in w_rows if rate_of(row, group) is not None))
            ) if any(rate_of(row, group) is not None for row in w_rows) else None
            for group in ("central", "DAN", "KC")
        }
    for group, lo, hi in (("central", .5, 8), ("DAN", .5, 10), ("KC", None, 2)):
        vals = [means[float(weight)][group] for weight in pair]
        violations[group] = max(violation(v, lo, hi, floor=.01) for v in vals)
        checks[group] = all(
            v is not None and (lo is None or v >= lo) and v <= hi for v in vals
        )
    f_vals = [v for v in (field_of(row, "F") for row in pair_rows) if v is not None]
    kc_low = [
        v for v in (
            rate_of(lookup[(round(float(pair[0]), 8), int(seed))], "KC")
            for seed in seed_list
        ) if v is not None
    ]
    central_low = [
        v for v in (
            rate_of(lookup[(round(float(pair[0]), 8), int(seed))], "central")
            for seed in seed_list
        ) if v is not None
    ]
    return {
        "screen_passed": all(checks.values()),
        "screen_checks": checks,
        "violations": violations,
        "S": sum(violations.values()),
        "pair_weights": list(pair),
        "n_seeds": len(seed_list),
        "measured_F_max_pair": max(f_vals) if f_vals else None,
        "measured_F_mean": (sum(f_vals) / len(f_vals)) if f_vals else None,
        "measured_kc_hz_mean": (sum(kc_low) / len(kc_low)) if kc_low else None,
        "measured_central_hz_mean": (sum(central_low) / len(central_low)) if central_low else None,
        "weight_means": {str(weight): means[float(weight)] for weight in pair},
        "gradedness": None,
        "gradedness_note": gradedness_note,
    }


def freeze_perturbation(
    rows: list[dict[str, Any]],
    *,
    weights: tuple[float, ...] | list[float] = FREEZE_PERTURB_WEIGHTS,
    seeds: tuple[int, ...] | list[int] = FREEZE_PERTURB_SEEDS,
) -> dict[str, Any]:
    """Configured-weight ±0.05 probes on freeze perturb seeds. Units: mV, Hz."""
    by_key: dict[tuple[float, int], dict[str, Any]] = {}
    perturb = tuple(round(float(w), 8) for w in weights)
    seed_list = tuple(int(s) for s in seeds)
    for row in rows:
        by_key[(round(float(row["w_bg"]), 8), int(row["seed"]))] = row
    missing = [
        (weight, seed)
        for weight in perturb
        for seed in seed_list
        if (round(float(weight), 8), int(seed)) not in by_key
    ]
    if missing:
        raise ValueError(f"freeze perturbation missing {missing}")
    points = []
    holds = True
    for weight in perturb:
        w_rows = [by_key[(round(float(weight), 8), int(seed))] for seed in seed_list]
        f_vals = [v for v in (number(row.get("F")) for row in w_rows) if v is not None]
        kc_vals = [
            v for v in (number((row.get("rates_hz") or {}).get("KC")) for row in w_rows)
            if v is not None
        ]
        central_vals = [
            v for v in (number((row.get("rates_hz") or {}).get("central")) for row in w_rows)
            if v is not None
        ]
        f_max = max(f_vals) if f_vals else None
        kc_mean = (sum(kc_vals) / len(kc_vals)) if kc_vals else None
        central_mean = (sum(central_vals) / len(central_vals)) if central_vals else None
        ok = (
            f_max is not None and f_max < 3
            and kc_mean is not None and kc_mean <= 2
            and central_mean is not None and 0.5 <= central_mean <= 8
        )
        holds = holds and ok
        points.append({
            "w_bg": float(weight),
            "seeds": list(seed_list),
            "F_max": f_max,
            "kc_hz_mean": kc_mean,
            "central_hz_mean": central_mean,
            "holds": ok,
        })
    return {"holds": holds, "weights": points}


def collect_freeze(
    jobs: list[tuple[Path, list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Score experiment 4. Diagnostic only: admits nothing to T1 or T2."""
    long_rows: list[dict[str, Any]] = []
    sugar: dict[float, list[dict[str, Any]]] = defaultdict(list)
    ff: list[dict[str, Any]] = []
    bare: list[dict[str, Any]] = []
    pert: list[dict[str, Any]] = []
    rates: list[float] = []
    n_tasks = 0
    for out, tasks in jobs:
        for task in tasks:
            n_tasks += 1
            path = task_ndjson_path(out, task)
            rows = read_t0_task_rows(path)
            complete = rows[-1]
            if complete.get("wall_per_brain_s") is not None:
                rates.append(float(complete["wall_per_brain_s"]))
            evals = [row for row in rows if row.get("kind") == "evaluation"]
            kind = task.get("kind")
            if kind == "diag-long":
                long_rows.extend(overlay_window_f_mn9(row, out) for row in evals)
            elif kind == "diag-sugar":
                sugar[round(float(task["w_bg"]), 8)].extend(evals)
            elif kind == "diag-ff":
                ff.extend(evals)
            elif kind == "bare":
                bare.extend(evals)
            elif kind == "t1":
                pert.extend(evals)
    a: list[float] = []
    b: list[float] = []
    for weight in FREEZE_PAIR_WEIGHTS:
        rows = sorted(sugar.get(round(float(weight), 8), []), key=lambda r: int(r["seed"]))
        diffs = [float(row["difference_hz"]) for row in rows]
        if weight == FREEZE_PAIR_WEIGHTS[0]:
            b = diffs
        a.extend(diffs[:3])
    if len(a) != 6:
        raise ValueError(f"freeze (a) has {len(a)} rows, expected 6")
    if len(b) != 10:
        raise ValueError(f"freeze (b) has {len(b)} rows, expected 10")
    if len(ff) != 10:
        raise ValueError(f"freeze (c) has {len(ff)} rows, expected 10")
    if len(bare) != 10:
        raise ValueError(f"freeze bare has {len(bare)} rows, expected 10")
    t0_ret, t0_diff = _closest_3d_t0_retention()
    upstream_c = [float(row["difference_hz"]) for row in ff]
    upstream_bare = [float(row["difference_hz"]) for row in bare]
    job_bare_mean = sum(upstream_bare) / len(upstream_bare)
    candidate_ff = {
        "upstream": upstream_c,
        "extended": [t0_ret * 56.0] * 10,
    }
    bare_ff = {
        "upstream": upstream_bare,
        "extended": [56.0] * 10,
    }
    h_vals = [float(row["h_max"]) for row in (*long_rows, *ff, *bare, *pert) if row.get("h_max") is not None]
    for rows in sugar.values():
        h_vals.extend(float(row["h_max"]) for row in rows if row.get("h_max") is not None)
    scored = t2_reflex_probe(
        a, b, candidate_ff, bare_ff,
        h_max=max(h_vals) if h_vals else None,
        sub_tier="T3d",
        job_bare_mean=job_bare_mean,
    )
    flags = ["diagnostic", *(scored.get("flags") or [])]
    clamped = [
        row for row in long_rows
        if row.get("pools") == "clamped" or row.get("clamp") is True
    ]
    screen = freeze_pair_screen(clamped)
    perturbation = freeze_perturbation(pert)
    free_22r = []
    for row in long_rows:
        if row.get("pools") != "free":
            continue
        windows = row.get("windows") or {}
        for name, window in windows.items():
            gate = dict(window.get("median_22r") or {})
            free_22r.append({"seed": row.get("seed"), "w_bg": row.get("w_bg"), "window": name, **gate})
    median_passed = bool(free_22r) and all(bool(item.get("passed")) for item in free_22r)
    return {
        "class": "development",
        "sub_tier": "T3d",
        "stage": "freeze",
        "candidate_id": FREEZE_ID,
        "flags": flags,
        "admitted_t1": False,
        "admitted_t2": False,
        "diagnostic": True,
        "n_tasks": n_tasks,
        "n_long": len(long_rows),
        "long": long_rows,
        "screen": screen,
        "screen_holds": bool(screen["screen_passed"]),
        "perturbation": perturbation,
        "median_22r": {
            "rule": "2.2r: all-neuron median in [0.2, 5] Hz and <1 percent above 50 Hz",
            "free_pool_windows": free_22r,
            "passed": median_passed,
        },
        "reflex": {**scored, "flags": flags, "diagnostic": True},
        "a_hz": a,
        "b_hz": b,
        "job_bare_mean": job_bare_mean,
        "t0_retention": t0_ret,
        "t0_difference_hz": t0_diff,
        "mean_wall_per_brain_s": (sum(rates) / len(rates)) if rates else None,
        "scored_window": WP27_SCORED_WINDOW,
        "live_probe_window": "[1, 11)",
        "live_probe_note": (
            "flyo-11 staged 0fd2aed before 92704fa; recorded F and mn9_hz are [1, 11). "
            "Screen F and dark MN9 use windows.early [2, 12) (item 95)."
        ),
    }


def diag_worker(payload: dict[str, Any]) -> str:
    """One diagnostic child: instrumented long, sugar, FF, or sigma sugar."""
    import json
    import time
    from pathlib import Path

    from flyonenomics.drive.rest_map import (
        _build_engine,
        _instrumented_probe,
        _json_safe,
        _probe,
        diag_sample_indices,
        disjoint_diag_blocks,
    )
    from flyonenomics.registry import build_registry

    path = Path(payload["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite evaluation evidence: {path}")
    deadline = time.monotonic() + payload["wall_cap_s"]
    kind = payload["kind"]
    unit = payload.get("unit")
    bare = kind == "diag-bare"
    setting = setting_from_unit(unit, bare=bare)
    mechs, section = (None, None) if bare else resolve_unit_mechanisms(unit)
    clamp = payload.get("clamp")
    identity = payload["identity"]
    meta = {
        **identity,
        "stage": payload.get("stage") or (payload.get("identity") or {}).get("stage") or "diag",
        "kind": kind,
        "task_id": path.stem,
        "plan_sha256": payload["plan_sha256"],
        "engine_model": "lif" if bare or not unit else unit_engine_model(unit),
        "setting": None if (bare or not unit) else unit.get("setting"),
        "unit": unit,
        "flags": ["diagnostic"],
        "w_bg": payload.get("w_bg"),
        "clamp": clamp,
    }
    t_build = time.monotonic()
    with path.open("x") as handle:
        def emit(row: dict[str, Any]) -> None:
            handle.write(json.dumps({**meta, **_json_safe(row)}, allow_nan=False) + "\n")
            handle.flush()

        try:
            if kind == "diag-long":
                registry = build_registry("783")
                blocks = disjoint_diag_blocks(registry)
                samples = diag_sample_indices(blocks, registry.n)
                built = _build_engine(
                    setting, mode="dark", bare=False, feedforward=False,
                    mechanisms=mechs, mechanisms_section=section,
                    clamp=bool(clamp), trace_idx=samples["trace_idx"],
                )
                built = _maybe_apply_arm(built, unit)
                build_s = time.monotonic() - t_build
                emit({"kind": "task-build", "build_s": build_s})
                npz = path.with_suffix(".npz")
                row = _instrumented_probe(
                    built, float(payload["w_bg"]), int(payload["seed"]),
                    seconds=DIAG_LONG_S, deadline=deadline, dest=npz,
                    raster_idx=samples["raster_idx"], blocks=blocks,
                )
                emit({"kind": "evaluation", **row})
                n_eval = 1
                brain_s = DIAG_LONG_S
            else:
                if kind == "diag-sugar" or kind == "sigma-sugar":
                    mode, feedforward, hold = "extended", False, True
                    seconds = float(payload.get("measure_s") or DIAG_SUGAR_MEASURE_S)
                    weight = float(payload["w_bg"])
                elif kind == "diag-ff":
                    mode, feedforward, hold = "upstream", True, True
                    seconds = 1.0
                    weight = 0.0
                elif kind == "diag-bare":
                    mode, feedforward, hold = "upstream", True, True
                    seconds = 1.0
                    weight = 0.0
                else:
                    raise ValueError(f"unknown diagnostic kind {kind}")
                built = _build_engine(
                    setting, mode=mode, bare=bare, feedforward=feedforward,
                    mechanisms=mechs, mechanisms_section=section,
                    clamp=hold,
                )
                built = _maybe_apply_arm(built, unit)
                build_s = time.monotonic() - t_build
                emit({"kind": "task-build", "build_s": build_s})
                n_eval = 0
                brain_s = 0.0
                for seed in payload["seeds"]:
                    silent = _probe(built, weight, int(seed), seconds=seconds, deadline=deadline)
                    sugar = _probe(
                        built, weight, int(seed), seconds=seconds, active=True, deadline=deadline,
                    )
                    brain_s += 2.0 * (2.0 + seconds)
                    h_vals = [p.get("h_max") for p in (silent, sugar) if p.get("h_max") is not None]
                    emit({
                        "kind": "evaluation",
                        "seed": int(seed),
                        "w_bg": weight,
                        "silent": silent,
                        "sugar": sugar,
                        "difference_hz": sugar["mn9_hz"] - silent["mn9_hz"],
                        "h_max": max(h_vals) if h_vals else None,
                        "measure_s": seconds,
                    })
                    n_eval += 1
            wall_s = time.monotonic() - t_build - build_s
            emit({
                "kind": "task-complete",
                "evaluations": n_eval,
                "build_s": build_s,
                "wall_s": wall_s,
                "brain_s": brain_s,
                "wall_per_brain_s": wall_s / brain_s if brain_s else None,
            })
        except Exception as exc:
            emit({"kind": "task-error", "error": f"{type(exc).__name__}: {exc}"})
            raise
    return str(path)


def wave_worker(payload: dict[str, Any]) -> str:
    """One mixed child. Routes diagnostic, T1, and T0 payloads."""
    kind = payload.get("kind")
    if kind in {"diag-long", "diag-sugar", "diag-ff", "diag-bare", "sigma-sugar"}:
        return diag_worker(payload)
    if kind == "t1":
        return t1_worker(payload)
    return t0_worker(payload)


def t0_unit_id(unit: dict[str, Any]) -> str:
    """T0 identity used in rest-T3c-decision.json: g_gaba-g_glu-tag-params-scope."""
    g_gaba = float(unit["g_gaba"])
    g_glu = float(unit["g_glu"])
    setting = unit.get("setting") or {}
    model = unit.get("engine_model") or unit_engine_model(unit)
    if model == "lif+cbi" or unit.get("sub_tier") == "T3c":
        return f"{g_gaba}-{g_glu}-cbi-{float(setting['E_inh_mv'])}-{setting['scope']}"
    if model == "lif+sfa" or unit.get("sub_tier") == "T3a":
        return f"{g_gaba}-{g_glu}-sfa-{float(setting['b_mv'])}-{float(setting['tau_ms'])}-{setting['scope']}"
    if model == "lif+std" or unit.get("sub_tier") == "T3b":
        return f"{g_gaba}-{g_glu}-std-{float(setting['U'])}-{float(setting['tau_ms'])}-{setting['scope']}"
    g_kc = setting.get("g_gaba_kc", unit.get("g_gaba_kc"))
    if g_kc is not None:
        return f"{g_gaba}-{g_glu}-kc-{float(g_kc)}"
    return f"{g_gaba}-{g_glu}"


def dt_ms_tag(dt_ms: float) -> str:
    """File-safe tag for a millisecond step. 0.1 ms -> dt100."""
    return f"dt{int(round(float(dt_ms) * 1000.0)):03d}"


def _convergence_why(unit: dict[str, Any], *, required: bool, lo: float, hi: float) -> str:
    uid = t0_unit_id(unit)
    h_max = float(unit["h_max"])
    ret = unit.get("retention")
    setting = unit.get("setting") or {}
    if required:
        return (
            f"{uid} is the T0 closest miss (retention {ret}, h_max {h_max:.2f}); "
            "it is the low end of the recorded h_max range and the only unit that kept the reflex"
        )
    return (
        f"{uid} sits on the log-h_max span {lo:.2f} to {hi:.2f} at h_max {h_max:.2f}; "
        f"pair ({float(unit['g_gaba'])}, {float(unit['g_glu'])}), "
        f"E_inh {float(setting['E_inh_mv'])} mV, recorded retention {ret}"
    )


def select_t3c_convergence_units(
    t0_record: dict[str, Any], *, n: int = T3C_CONVERGENCE_N_UNITS,
) -> list[dict[str, Any]]:
    """Required closest miss plus log-spaced h_max companions (item 88)."""
    units = [u for u in t0_record["units"] if not u.get("baseline")]
    by_id = {t0_unit_id(u): u for u in units}
    if T3C_CONVERGENCE_REQUIRED_ID not in by_id:
        raise ValueError(f"required unit {T3C_CONVERGENCE_REQUIRED_ID} missing from T0 record")
    ranked = sorted(units, key=lambda u: float(u["h_max"]))
    lo = math.log(float(ranked[0]["h_max"]))
    hi = math.log(float(ranked[-1]["h_max"]))
    targets = [math.exp(lo + (hi - lo) * t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    picked: list[dict[str, Any]] = []
    used = {T3C_CONVERGENCE_REQUIRED_ID}
    picked.append(by_id[T3C_CONVERGENCE_REQUIRED_ID])
    for target in targets[1:n]:
        remaining = [u for u in units if t0_unit_id(u) not in used]
        if not remaining:
            break
        best = min(remaining, key=lambda u: abs(float(u["h_max"]) - target))
        picked.append(best)
        used.add(t0_unit_id(best))
    h_lo = float(ranked[0]["h_max"])
    h_hi = float(ranked[-1]["h_max"])
    out = []
    for unit in picked:
        uid = t0_unit_id(unit)
        row = {
            "unit_id": uid,
            "sub_tier": "T3c",
            "engine_model": "lif+cbi",
            "g_gaba": unit["g_gaba"],
            "g_glu": unit["g_glu"],
            "setting": unit["setting"],
            "M": unit.get("M"),
            "baseline": False,
            "sigma_th": unit.get("sigma_th", 0.0),
            "optic_exemption": unit.get("optic_exemption", False),
            "n_bg": unit.get("n_bg", 100),
            "recorded_h_max": unit.get("h_max"),
            "recorded_retention": unit.get("retention"),
            "recorded_difference_hz": unit.get("difference_hz"),
            "why": _convergence_why(
                unit, required=(uid == T3C_CONVERGENCE_REQUIRED_ID), lo=h_lo, hi=h_hi,
            ),
        }
        out.append(row)
    return out


def recorded_lif_dt_ms() -> float:
    return float(load_params(ROOT / "data" / "params-v0.2.yaml").get("lif.dt"))


def t3c_convergence_steps(recorded_dt_ms: float | None = None) -> list[float]:
    dt = recorded_lif_dt_ms() if recorded_dt_ms is None else float(recorded_dt_ms)
    return [dt, dt / 2.0, dt / 4.0]


def t3c_convergence_plan(t0_record: dict[str, Any] | None = None) -> dict[str, Any]:
    """Item 88 diagnostic plan: five 3c units, one seed, dt, dt/2, dt/4, same-job bare."""
    if t0_record is None:
        t0_record = json.loads(read_text(ROOT / "validation" / "records" / "p2" / "rest-T3c-T0.json"))
    units = select_t3c_convergence_units(t0_record)
    recorded_dt = recorded_lif_dt_ms()
    steps = t3c_convergence_steps(recorded_dt)
    rho = float(t0_record.get("rho_mech") or 1.2336139268858282)
    tasks: list[dict[str, Any]] = []
    for dt in steps:
        for unit in units:
            tasks.append({
                "kind": "unit",
                "unit": unit,
                "seeds": [T3C_CONVERGENCE_SEED],
                "dt_ms": dt,
                "brain_s": 6,
            })
        tasks.append({
            "kind": "bare",
            "unit": None,
            "seeds": [T3C_CONVERGENCE_SEED],
            "dt_ms": dt,
            "brain_s": 6,
        })
    t0_brain = sum(float(t["brain_s"]) for t in tasks)
    return {
        "class": "development",
        "sub_tier": "T3c",
        "stage": "T0-dt-convergence",
        "engine_model": "lif+cbi",
        "item": 88,
        "recorded_dt_ms": recorded_dt,
        "steps_ms": steps,
        "seed": T3C_CONVERGENCE_SEED,
        "rho_mech": rho,
        "n_units": len(units),
        "units": units,
        "selection": (
            "required closest miss 1.0-1.0-cbi--72.0-all, then four companions at "
            "roughly 25/50/75/100 percent of log h_max from 19.65 to 256.53"
        ),
        "jobs": [tasks],
        "n_jobs": 1,
        "n_tasks": len(tasks),
        "t0_brain_s": t0_brain,
        "cap_list_usd": 8.0,
        "note": "T0 background off, one seed, same-job bare at each step. No T0 readmission.",
    }


def t3c_dt_verdict(rows: list[dict[str, Any]]) -> str:
    """numerical: finer steps agree and retention holds; physical: retention stays below 0.5."""
    if len(rows) < 2:
        return "mixed"
    ordered = sorted(rows, key=lambda row: -float(row["dt_ms"]))
    rets = [row.get("retention") for row in ordered]
    holds = all(r is not None and float(r) >= 0.5 for r in rets)
    collapses = all(r is None or float(r) < 0.5 for r in rets)
    fine = ordered[-2:]
    conv = (
        fine[0].get("retention") is not None
        and fine[1].get("retention") is not None
        and abs(float(fine[0]["retention"]) - float(fine[1]["retention"])) <= T3C_DT_RETENTION_TOL
        and fine[0].get("difference_hz") is not None
        and fine[1].get("difference_hz") is not None
        and abs(float(fine[0]["difference_hz"]) - float(fine[1]["difference_hz"])) <= T3C_DT_DIFF_TOL_HZ
    )
    if conv and holds:
        return "numerical"
    if collapses:
        return "physical"
    return "mixed"


def collect_t3c_convergence(out: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-unit per-dt T0 retention against the same-job, same-dt bare seed."""
    bare_by_dt: dict[str, dict[str, Any]] = {}
    unit_rows: list[dict[str, Any]] = []
    rates: list[float] = []
    for task in tasks:
        path = task_ndjson_path(out, task)
        rows = read_t0_task_rows(path)
        complete = rows[-1]
        if complete.get("wall_per_brain_s") is not None:
            rates.append(float(complete["wall_per_brain_s"]))
        evals = [row for row in rows if row.get("kind") == "evaluation"]
        if not evals:
            raise ValueError(f"no evaluations in {path.name}")
        row = evals[0]
        dt = float(row.get("dt_ms") if row.get("dt_ms") is not None else task["dt_ms"])
        tag = dt_ms_tag(dt)
        wall_s = complete.get("wall_s")
        if task["kind"] == "bare":
            bare_by_dt[tag] = {
                "dt_ms": dt,
                "difference_hz": float(row["difference_hz"]),
                "wall_s": wall_s,
                "wall_per_brain_s": complete.get("wall_per_brain_s"),
                "h_max": row.get("h_max"),
                "job_id": row.get("job_id"),
            }
            continue
        unit = row.get("unit") or task.get("unit") or {}
        unit_rows.append({
            "unit": unit,
            "unit_id": unit.get("unit_id") or t0_unit_id(unit),
            "dt_ms": dt,
            "seed": int(row["seed"]),
            "difference_hz": float(row["difference_hz"]),
            "h_max": row.get("h_max"),
            "wall_s": wall_s,
            "wall_per_brain_s": complete.get("wall_per_brain_s"),
            "cbi_stiff": bool(row.get("h_max") is not None and cbi_stiff(float(row["h_max"]), dt_ms=dt)),
            "job_id": row.get("job_id"),
            "recorded_h_max": unit.get("recorded_h_max"),
            "recorded_retention": unit.get("recorded_retention"),
            "recorded_difference_hz": unit.get("recorded_difference_hz"),
            "why": unit.get("why"),
        })
    by_unit: dict[str, list[dict[str, Any]]] = {}
    for row in unit_rows:
        tag = dt_ms_tag(float(row["dt_ms"]))
        bare = bare_by_dt.get(tag)
        if bare is None:
            raise ValueError(f"missing same-job bare at dt_ms={row['dt_ms']}")
        retention = t0_retention(row["difference_hz"], bare["difference_hz"])
        flags = t0_flags(
            bg_off_difference_hz=row["difference_hz"],
            h_max=row["h_max"],
            dt_ms=float(row["dt_ms"]),
        )
        scored = {
            **row,
            "retention": retention,
            "bare_difference_hz": bare["difference_hz"],
            "flags": flags,
        }
        by_unit.setdefault(row["unit_id"], []).append(scored)
    units_out = []
    for uid, rows in by_unit.items():
        ordered = sorted(rows, key=lambda r: -float(r["dt_ms"]))
        units_out.append({
            "unit_id": uid,
            "why": ordered[0].get("why"),
            "recorded_h_max": ordered[0].get("recorded_h_max"),
            "recorded_retention": ordered[0].get("recorded_retention"),
            "recorded_difference_hz": ordered[0].get("recorded_difference_hz"),
            "verdict": t3c_dt_verdict(ordered),
            "steps": ordered,
        })
    units_out.sort(key=lambda u: (0 if u["unit_id"] == T3C_CONVERGENCE_REQUIRED_ID else 1, u["unit_id"]))
    labels = {u["verdict"] for u in units_out}
    overall = labels.pop() if len(labels) == 1 else "mixed"
    return {
        "class": "development",
        "sub_tier": "T3c",
        "stage": "T0-dt-convergence",
        "item": 88,
        "seed": T3C_CONVERGENCE_SEED,
        "n_units": len(units_out),
        "n_rows": len(unit_rows),
        "overall_verdict": overall,
        "readmission": False,
        "wall_per_brain_s": rates,
        "bare": {tag: bare_by_dt[tag] for tag in sorted(bare_by_dt, key=lambda t: -int(t[2:]))},
        "units": units_out,
    }


def t3c_t1_unit(t0_record: dict[str, Any] | None = None) -> dict[str, Any]:
    """Item 89 unit: T0 closest miss, cbi-stiff stripped so T1 can score at dt 0.05."""
    if t0_record is None:
        t0_record = json.loads(read_text(ROOT / T3C_T0_RECORD))
    closest = t0_record["closest_t0"]
    if t0_unit_id(closest) != T3C_CONVERGENCE_REQUIRED_ID:
        raise ValueError(f"T0 closest miss is {t0_unit_id(closest)}, not {T3C_CONVERGENCE_REQUIRED_ID}")
    unit = _t1_unit(closest)
    unit["flags"] = [f for f in (unit.get("flags") or []) if f != "cbi-stiff"]
    unit["unit_id"] = T3C_CONVERGENCE_REQUIRED_ID
    return unit


def t3c_t1_plan(t0_record: dict[str, Any] | None = None) -> dict[str, Any]:
    """Item 89 plan: one 3c unit, ordinary T1 at dt 0.05 ms, IBM packing."""
    if t0_record is None:
        t0_record = json.loads(read_text(ROOT / T3C_T0_RECORD))
    unit = t3c_t1_unit(t0_record)
    rho = float(t0_record["rho_mech"])
    makespan = ibm_makespan_s()
    packed = t1_tasks(
        [unit], rho,
        worker_s_per_brain_s=T3C_T1_PACK_RATE,
        makespan=makespan,
    )
    if not packed["launch"]:
        raise ValueError(packed.get("reason") or "item 89 T1 plan is not launchable")
    cfg = load_config()
    return {
        "class": "development",
        "sub_tier": "T3c",
        "stage": "T1",
        "engine_model": "lif+cbi",
        "item": 89,
        "dt_ms": T3C_T1_DT_MS,
        "recorded_dt_ms": recorded_lif_dt_ms(),
        "rho_mech": rho,
        "q_plan": Q_PLAN,
        "t0_brain_s": float(t0_record.get("t0_brain_s") or 0.0),
        "pack_worker_s_per_brain_s": T3C_T1_PACK_RATE,
        "makespan_s": makespan,
        "admitted": [_t1_unit(unit)],
        "n_units": 1,
        "unit_id": T3C_CONVERGENCE_REQUIRED_ID,
        "camber": cfg["camber"],
        "ibm": ibm_config(cfg),
        "job_shapes": {
            "B_brain_s": packed.get("B"),
            "slices": packed.get("slices"),
            "n_jobs": packed.get("n_jobs"),
            "n_tasks": packed.get("n_tasks"),
            "t1_brain_s": packed.get("t1_brain_s"),
            "n_units": packed.get("n_units"),
            "launch": packed.get("launch"),
            "reason": packed.get("reason"),
        },
        "cap_list_usd": 5.0,
        "t0_record": T3C_T0_RECORD,
        "note": (
            "item 89: T1 R-screen for 1.0-1.0-cbi--72.0-all alone at dt 0.05 ms "
            "rk4; other 44 stay closed; T0 record not rewritten"
        ),
    }


def t3c_t1_record(
    plan: dict[str, Any],
    t1: dict[str, Any],
    *,
    jobs: list[str] | None = None,
    ibm: dict[str, Any] | None = None,
    t2: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """rest-T3c-T1.json body. dt_ms is recorded. T0 file is not written."""
    out = {
        "class": "development",
        "sub_tier": "T3c",
        "stage": "T1",
        "engine_model": "lif+cbi",
        "item": 89,
        "dt_ms": float(plan["dt_ms"]),
        "recorded_dt_ms": plan.get("recorded_dt_ms"),
        "rho_mech": plan["rho_mech"],
        "unit_id": plan.get("unit_id") or T3C_CONVERGENCE_REQUIRED_ID,
        "note": plan.get("note"),
        "t0_record": T3C_T0_RECORD,
        "collect": "collect-t1",
        "backend": "ibm-vpc",
        "admitted_units": plan.get("admitted") or [],
        "job_shapes": plan.get("job_shapes") or {},
        "units": t1.get("units") or [],
        "candidates": t1.get("candidates") or [],
        "scored": t1.get("scored") or [],
        "admitted": t1.get("admitted") or [],
        "excluded": t1.get("excluded") or [],
        "closest_miss": t1.get("closest_miss"),
        "n_units": t1.get("n_units"),
        "n_tasks": t1.get("n_tasks"),
        "n_screen_passers": t1.get("n_screen_passers"),
        "n_t2_admitted": t1.get("n_t2_admitted"),
        "grid_edge": t1.get("grid_edge"),
        "t2_b_unreachable": t1.get("t2_b_unreachable"),
        "wall_per_brain_s": t1.get("wall_per_brain_s") or [],
        "jobs": jobs or [],
    }
    if ibm is not None:
        out["ibm"] = ibm
    if t2 is not None:
        out["t2"] = {
            "n_candidates": t2.get("n_candidates"),
            "n_reflex_passed": t2.get("n_reflex_passed"),
            "n_reflex_harmonised": t2.get("n_reflex_harmonised"),
            "n_long_passed": t2.get("n_long_passed"),
            "record": T3C_T2_RECORD,
        }
    return out


def t3c_t2_record(
    plan: dict[str, Any],
    t2: dict[str, Any],
    *,
    jobs: list[str] | None = None,
    ibm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """rest-T3c-T2.json body when item 89 T1 admits a candidate."""
    out = {
        "class": "development",
        "sub_tier": "T3c",
        "stage": "T2",
        "engine_model": "lif+cbi",
        "item": 89,
        "dt_ms": float(plan["dt_ms"]),
        "rho_mech": plan["rho_mech"],
        "unit_id": plan.get("unit_id") or T3C_CONVERGENCE_REQUIRED_ID,
        "collect": "collect-t2",
        "backend": "ibm-vpc",
        "candidates": t2.get("candidates") or [],
        "n_candidates": t2.get("n_candidates"),
        "n_tasks": t2.get("n_tasks"),
        "n_reflex_passed": t2.get("n_reflex_passed"),
        "n_reflex_harmonised": t2.get("n_reflex_harmonised"),
        "n_long_passed": t2.get("n_long_passed"),
        "wall_per_brain_s": t2.get("wall_per_brain_s") or [],
        "jobs": jobs or [],
    }
    if ibm is not None:
        out["ibm"] = ibm
    return out


def decide_t3c_item89(
    existing: dict[str, Any],
    t1: dict[str, Any],
    t2: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update the 3c decision from item 89 T1/T2. Does not write the T0 record."""
    out = json.loads(json.dumps(existing))
    out["item"] = 89
    out["dt_ms"] = T3C_T1_DT_MS
    out["t1_record"] = T3C_T1_RECORD
    out["t1_launch"] = True
    out["n_t1_units"] = t1.get("n_units")
    out["n_screen_passers"] = t1.get("n_screen_passers")
    out["n_t2_admitted"] = t1.get("n_t2_admitted")
    out["t0_closest_miss"] = existing.get("t0_closest_miss") or existing.get("closest_miss")
    if t2 is not None:
        out["t2_launch"] = True
        out["t2_record"] = T3C_T2_RECORD
        results = t2.get("candidates") or []
        reflex_ok = [c for c in results if c.get("reflex_passed")]
        long_ok = [c for c in reflex_ok if c.get("long_passed")]
        if long_ok:
            ranked = sorted(long_ok, key=tier3_order_key)
            out["ranked"] = ranked
            out["shortlist"] = ranked[:3]
            out["failed_stage"] = None
            out["closest_miss"] = None
            out["p2_partial_b"] = False
            out["reason"] = "item 89: T2 R-long passed at dt 0.05 ms"
            return out
        out["ranked"] = []
        out["shortlist"] = []
        out["p2_partial_b"] = True
        if reflex_ok:
            out["failed_stage"] = "R-long"
            out["closest_miss"] = closest_miss(reflex_ok)
            out["reason"] = "item 89: T2 R-reflex passed, R-long failed at dt 0.05 ms"
        else:
            out["failed_stage"] = "R-reflex"
            out["closest_miss"] = closest_miss(results)
            out["reason"] = "item 89: T2 R-reflex failed at dt 0.05 ms"
        return out
    out["t2_launch"] = False
    out["ranked"] = []
    out["shortlist"] = []
    out["p2_partial_b"] = True
    if t1.get("n_t2_admitted"):
        out["failed_stage"] = None
        out["closest_miss"] = t1.get("closest_miss")
        out["reason"] = "item 89: T1 R-screen passed at dt 0.05 ms; T2 not in this record"
        return out
    out["failed_stage"] = "R-screen"
    out["closest_miss"] = t1.get("closest_miss")
    out["reason"] = (
        "item 89: T1 R-screen failed at dt 0.05 ms; other 44 units stay closed"
    )
    return out


def round_trip_row(row: dict[str, Any], *, n: int, super_class, s_cur=None) -> None:
    """engine_model_of, mechanisms_section and mechanisms_from_unit agree."""
    section = mechanisms_section(row)
    if engine_model_of(section) != row["engine_model"]:
        raise ValueError("engine_model_of does not round-trip")
    resolved = mechanisms_from_unit(row, n=n, super_class=super_class, s_cur=s_cur)
    if row["engine_model"] != "lif" and resolved is None:
        raise ValueError("mechanisms_from_unit dropped a non-null section")
