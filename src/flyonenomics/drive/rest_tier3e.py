"""Sub-tier 3e packing, collect, and IBM worker. Units: s, USD, Hz, mV."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from flyonenomics.drive.rest_map import SEEDS, Setting, number
from flyonenomics.drive.rest_nonuniform import (
    COMMON_LADDER,
    HUB_FACTORS,
    SENS_LADDER,
    THDEG_BETAS,
    arm_id,
    apply_arm,
    engine_type_labels,
    resolve_hub_types,
    screen_ladder,
)
from flyonenomics.drive.rest_tier3 import (
    DIAG_LONG_S,
    DIAG_SUGAR_ENGINE_S,
    DIAG_SUGAR_MEASURE_S,
    LONG_SEEDS,
    T0_BRAIN_S_PER_TASK,
    WP27_PACK_RATE,
    WP27_USD_PER_H,
    _diag_eval_rows,
    _t1_unit,
    candidate_id,
    closest_3d_unit,
    closest_miss,
    freeze_exp4_tasks,
    freeze_pair_screen,
    freeze_perturbation,
    ibm_config,
    ibm_makespan_s,
    pack_mixed_rate,
    read_t0_task_rows,
    setting_from_unit,
    t0_passed,
    t0_retention,
    t2_reflex_probe,
    task_ndjson_path,
    wp27_list_usd,
)

WP29_CAP_USD = 20.0
WP29_MAX_JOBS = 2
WP29_PACK_RATE = WP27_PACK_RATE
WP30_CAP_USD = 8.0
WP30_MAX_JOBS = 1
WP30_PACK_RATE = WP27_PACK_RATE
WP30_CANDIDATE_WEIGHTS = (0.9, 1.0, 1.1)
WP30_SEEDS = tuple(range(11, 21))
WP30_PERTURB_SEEDS = (11, 12, 13)
WP30_PERTURB_DELTA = 0.05
WP30_PASSER_ID = "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
ROOT = Path(__file__).resolve().parents[3]


def t3e_unit(arm: dict[str, Any]) -> dict[str, Any]:
    """3d substrate plus one 3e arm. Units: mV, ratios."""
    unit = closest_3d_unit()
    unit["sub_tier"] = "T3e"
    unit["arm"] = dict(arm)
    setting = dict(unit.get("setting") or {})
    setting["arm_id"] = arm_id(arm)
    if arm.get("beta") is not None:
        setting["beta"] = float(arm["beta"])
    if arm.get("hub_factor") is not None:
        setting["hub_factor"] = float(arm["hub_factor"])
    unit["setting"] = setting
    return unit


def t3e_arms(*, include_hubs: bool = True) -> list[dict[str, Any]]:
    """Five arms. Hub arm omitted when types do not resolve."""
    arms: list[dict[str, Any]] = [
        {
            "id": "sens",
            "bg_policy": "sens",
            "ladder": list(SENS_LADDER),
            "why_ladder": (
                "sensory-only drive; central brain sees network-filtered input, "
                "so the ladder starts at 0.80 and steps 0.20 mV to 1.40"
            ),
        },
        {
            "id": "nomotor",
            "bg_policy": "nomotor",
            "ladder": list(COMMON_LADDER),
            "why_ladder": "common 0.05 mV ladder; item 42 relaxed for this arm only",
        },
        {
            "id": "indeg",
            "bg_policy": "default",
            "scale": "indeg",
            "ladder": list(COMMON_LADDER),
            "why_ladder": "common ladder; incoming gain 1/sqrt(K_i/K_median)",
        },
    ]
    for beta in THDEG_BETAS:
        arms.append({
            "id": f"thdeg-{beta}",
            "bg_policy": "default",
            "beta": float(beta),
            "ladder": list(COMMON_LADDER),
            "why_ladder": "common ladder; v_th_i = v_th0 + beta * K_i / 1000 mV",
        })
    if include_hubs:
        for factor in HUB_FACTORS:
            arms.append({
                "id": f"hubs-{int(factor) if float(factor).is_integer() else factor}",
                "bg_policy": "default",
                "hub_factor": float(factor),
                "ladder": list(COMMON_LADDER),
                "why_ladder": "common ladder; outgoing factor on hubs and reciprocal partners",
            })
    return arms


def try_resolve_hubs() -> dict[str, Any]:
    """Resolve MBON06/LPi13/LPi15. Missing types skip arm E."""
    try:
        from flyonenomics.registry import build_registry

        registry = build_registry("783")
        cell_type, hemibrain = engine_type_labels(registry)
        return resolve_hub_types(cell_type, hemibrain)
    except Exception as exc:
        return {
            "resolved": None,
            "missing": [],
            "skip_reason": None,
            "resolve_later": f"{type(exc).__name__}: {exc}",
            "counts": {},
            "idx": [],
        }


def hubs_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Hub payload for a stored plan. include_hubs False skips arm E."""
    hubs = dict(plan.get("hubs") or {})
    if plan.get("include_hubs") is False:
        hubs["resolved"] = False
    return hubs


def t3e_screen_tasks(
    identity: dict[str, Any] | None = None,
    *,
    include_hubs: bool = True,
    arms: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """R-screen, T0, 10-seed sugar. Per arm, four ladder weights."""
    ident = identity or {}
    tasks: list[dict[str, Any]] = []
    for arm in (arms if arms is not None else t3e_arms(include_hubs=include_hubs)):
        unit = t3e_unit(arm)
        compact = {**unit}
        ladder = [float(w) for w in arm["ladder"]]
        for seed in SEEDS:
            tasks.append({
                "kind": "t1",
                "unit": compact,
                "arm_id": arm_id(arm),
                "seed": int(seed),
                "slice": [0, len(ladder)],
                "probes": [(float(w), int(seed)) for w in ladder],
                "brain_s": 12 * len(ladder),
                "pack_rate": WP29_PACK_RATE,
                "identity": ident,
            })
        tasks.append({
            "kind": "unit",
            "unit": compact,
            "arm_id": arm_id(arm),
            "seeds": list(LONG_SEEDS),
            "brain_s": T0_BRAIN_S_PER_TASK,
            "pack_rate": WP29_PACK_RATE,
            "identity": ident,
        })
        for weight in ladder:
            tasks.append({
                "kind": "t3e-sugar",
                "unit": compact,
                "arm_id": arm_id(arm),
                "w_bg": float(weight),
                "seeds": list(LONG_SEEDS),
                "measure_s": 1.0,
                "clamp": True,
                "brain_s": T0_BRAIN_S_PER_TASK,
                "pack_rate": WP29_PACK_RATE,
                "identity": ident,
            })
    return tasks


def t3e_wave_tasks(
    identity: dict[str, Any] | None = None,
    *,
    hubs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Screen wave: at most two boxes, $20 list for the round."""
    hubs = dict(hubs) if hubs is not None else try_resolve_hubs()
    include_hubs = hubs.get("resolved") is not False
    cfg = None
    ibm = ibm_config(cfg)
    makespan = ibm_makespan_s(cfg)
    cap = float(ibm["workers"]) * makespan
    ident = {**(identity or {}), "stage": "T3e"}
    arms = t3e_arms(include_hubs=include_hubs)
    mid = (len(arms) + 1) // 2
    groups = [arms[:mid], arms[mid:]] if arms else []
    jobs: list[list[dict[str, Any]]] = []
    try:
        for index, group in enumerate(groups):
            job = t3e_screen_tasks(ident, arms=group)
            job.append({
                "kind": "bare",
                "unit": None,
                "seeds": list(LONG_SEEDS),
                "brain_s": T0_BRAIN_S_PER_TASK,
                "pack_rate": WP29_PACK_RATE,
                "identity": ident,
                "job_index": index,
            })
            packed = pack_mixed_rate(job, cap, cfg)
            if len(packed) != 1:
                raise ValueError(f"arm group {index} needs {len(packed)} boxes")
            jobs.append(packed[0])
    except ValueError as exc:
        return {
            "launch": False,
            "reason": str(exc),
            "jobs": [],
            "n_jobs": 0,
            "list_usd": 0.0,
            "hubs": hubs,
        }
    list_usd = wp27_list_usd(jobs, cfg)
    n_jobs = len(jobs)
    brain_s = sum(float(t["brain_s"]) for job in jobs for t in job)
    launch = n_jobs <= WP29_MAX_JOBS and list_usd <= WP29_CAP_USD
    reason = None
    if n_jobs > WP29_MAX_JOBS:
        reason = f"{n_jobs} jobs exceeds two boxes"
    elif list_usd > WP29_CAP_USD:
        reason = f"list ${list_usd:.2f} exceeds ${WP29_CAP_USD:.0f}"
    freeze_s = sum(float(t["brain_s"]) for t in freeze_exp4_tasks())
    reflex_s = 2.0 * len(LONG_SEEDS) * 2.0 * DIAG_SUGAR_ENGINE_S
    engine_usd = brain_s * WP29_PACK_RATE * 2.2 / (3600.0 * float(ibm["workers"]))
    return {
        "launch": launch,
        "reason": reason,
        "jobs": jobs,
        "n_jobs": n_jobs,
        "n_tasks": sum(len(job) for job in jobs),
        "brain_s": brain_s,
        "list_usd": list_usd,
        "engine_usd": engine_usd,
        "pack_worker_s_per_brain_s": WP29_PACK_RATE,
        "max_instances": WP29_MAX_JOBS,
        "include_hubs": include_hubs,
        "hubs": hubs,
        "n_arms": len(t3e_arms(include_hubs=include_hubs)),
        "passer_followup_brain_s": freeze_s + reflex_s,
        "diagnostic": False,
    }


def t3e_plan_record(*, hubs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Launch plan for the WP29 3e screen. Units: s, USD. No task payloads."""
    packed = t3e_wave_tasks(hubs=hubs)
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
    hubs = packed.get("hubs") or {}
    return {
        "class": "development",
        "sub_tier": "T3e",
        "stage": "screen",
        "wave": "wp29",
        "engine_model": "lif",
        "substrate": "1.0-4.0-0.0-False-100-<w>-kc-6.0",
        "flags": [],
        "admitted_t1": False,
        "admitted_t2": False,
        "launch": packed["launch"],
        "reason": packed["reason"],
        "n_jobs": packed["n_jobs"],
        "n_tasks": packed["n_tasks"],
        "n_arms": packed.get("n_arms"),
        "brain_s": packed["brain_s"],
        "list_usd": packed["list_usd"],
        "engine_usd": packed.get("engine_usd"),
        "list_cap_usd": WP29_CAP_USD,
        "pack_worker_s_per_brain_s": packed["pack_worker_s_per_brain_s"],
        "max_instances": packed["max_instances"],
        "common_ladder": list(COMMON_LADDER),
        "sens_ladder": list(SENS_LADDER),
        "thdeg_betas": list(THDEG_BETAS),
        "hub_factors": list(HUB_FACTORS),
        "include_hubs": packed.get("include_hubs"),
        "hubs": {
            "resolved": hubs.get("resolved"),
            "counts": hubs.get("counts"),
            "missing": hubs.get("missing"),
            "skip_reason": hubs.get("skip_reason"),
            "resolve_later": hubs.get("resolve_later"),
            "n_idx": len(hubs.get("idx") or []),
        },
        "k_choice": (
            "K_i is incoming synapse count (sum of |Excitatory x Connectivity| "
            "onto i); K_median over K_i > 0; K_i < 1 uses 1 in 1/sqrt(K_i/K_median)"
        ),
        "lab_measures": {
            "single_unit_fano_ms": 100,
            "central_fano_n": 2000,
            "pairwise_corr_ms": 50,
            "pair_n": 500,
            "pca_participation_ratio": True,
            "recorded_only": True,
        },
        "passer_followup_brain_s": packed.get("passer_followup_brain_s"),
        "job_shapes": shapes,
        "ibm": ibm_config(),
        "arms": [
            {
                "id": arm_id(arm),
                "bg_policy": arm.get("bg_policy"),
                "ladder": list(arm["ladder"]),
                "why_ladder": arm.get("why_ladder"),
                "scale": arm.get("scale"),
                "beta": arm.get("beta"),
                "hub_factor": arm.get("hub_factor"),
            }
            for arm in t3e_arms(include_hubs=bool(packed.get("include_hubs")))
        ],
        "note": (
            "Screen wave only. A passer then gets 10-seed reflex at rest and the "
            "experiment-4 freeze (seeds 11-20) before RANKED. No up.sh before GO wp29."
        ),
    }


def wp30_pair_step() -> float:
    """Arm A adjacent step. Units: mV. Item 110.1."""
    return round(float(SENS_LADDER[1]) - float(SENS_LADDER[0]), 8)


def wp30_pair_weights(weight: float) -> tuple[float, float]:
    """3e pair at one candidate weight: (w, w + 0.20 mV). Units: mV."""
    step = wp30_pair_step()
    low = round(float(weight), 8)
    return (low, round(low + step, 8))


def wp30_run_weights() -> tuple[float, ...]:
    """Long and sugar weights: candidates plus pair partners. Units: mV."""
    found: set[float] = set()
    for weight in WP30_CANDIDATE_WEIGHTS:
        for point in wp30_pair_weights(weight):
            found.add(round(float(point), 8))
    return tuple(sorted(found))


def wp30_perturb_weights(weight: float) -> tuple[float, float, float]:
    """±0.05 mV around one candidate. Units: mV."""
    w = round(float(weight), 8)
    delta = round(float(WP30_PERTURB_DELTA), 8)
    return (round(w - delta, 8), w, round(w + delta, 8))


def wp30_perturb_union() -> tuple[float, ...]:
    """Unique perturbation weights across the three candidates. Units: mV."""
    found: set[float] = set()
    for weight in WP30_CANDIDATE_WEIGHTS:
        for point in wp30_perturb_weights(weight):
            found.add(round(float(point), 8))
    return tuple(sorted(found))


def t3e_freeze_unit() -> dict[str, Any]:
    """Sensory-only 3e passer substrate. Units: mV, ratios."""
    arm = {
        "id": "sens",
        "bg_policy": "sens",
        "ladder": list(WP30_CANDIDATE_WEIGHTS),
        "why_ladder": (
            "item 120: 0.9, 1.0, 1.1 mV around the arm A passer; "
            "pair step is the 3e sens ladder 0.20 mV"
        ),
    }
    unit = t3e_unit(arm)
    compact = _t1_unit(unit)
    compact["arm"] = dict(arm)
    compact["sub_tier"] = "T3e"
    compact["w_bg"] = 1.0
    compact["pair_weights"] = list(wp30_pair_weights(1.0))
    return compact


def t3e_freeze_tasks(identity: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Experiment-4 freeze of arm A at 0.9, 1.0, 1.1 mV. Item 120. Seeds 11-20."""
    ident = {**(identity or {}), "stage": "freeze"}
    compact = t3e_freeze_unit()
    tasks: list[dict[str, Any]] = []
    run_weights = wp30_run_weights()
    for weight in run_weights:
        for seed in WP30_SEEDS:
            tasks.append({
                "kind": "diag-long",
                "unit": compact,
                "arm_id": "sens",
                "w_bg": float(weight),
                "seed": int(seed),
                "clamp": True,
                "pools": "clamped",
                "brain_s": DIAG_LONG_S,
                "pack_rate": WP30_PACK_RATE,
                "identity": ident,
                "stage": "freeze",
            })
    sugar_s = len(WP30_SEEDS) * 2 * DIAG_SUGAR_ENGINE_S
    for weight in run_weights:
        tasks.append({
            "kind": "diag-sugar",
            "unit": compact,
            "arm_id": "sens",
            "w_bg": float(weight),
            "seeds": list(WP30_SEEDS),
            "measure_s": DIAG_SUGAR_MEASURE_S,
            "clamp": True,
            "brain_s": sugar_s,
            "pack_rate": WP30_PACK_RATE,
            "identity": ident,
            "stage": "freeze",
        })
    tasks.append({
        "kind": "diag-ff",
        "unit": compact,
        "arm_id": "sens",
        "w_bg": 0.0,
        "seeds": list(WP30_SEEDS),
        "clamp": True,
        "brain_s": T0_BRAIN_S_PER_TASK,
        "pack_rate": WP30_PACK_RATE,
        "identity": ident,
        "stage": "freeze",
    })
    tasks.append({
        "kind": "bare",
        "unit": None,
        "seeds": list(WP30_SEEDS),
        "brain_s": T0_BRAIN_S_PER_TASK,
        "pack_rate": WP30_PACK_RATE,
        "identity": ident,
        "job_index": 0,
        "stage": "freeze",
    })
    perturb = wp30_perturb_union()
    for seed in WP30_PERTURB_SEEDS:
        tasks.append({
            "kind": "t1",
            "unit_index": 0,
            "unit": compact,
            "arm_id": "sens",
            "seed": int(seed),
            "slice": [0, len(perturb)],
            "probes": [(float(weight), int(seed)) for weight in perturb],
            "brain_s": 12 * len(perturb),
            "pack_rate": WP30_PACK_RATE,
            "identity": ident,
            "stage": "freeze",
        })
    return tasks


def t3e_freeze_wave_tasks(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    """One IBM box for the WP30 freeze. Cap $8 list. Item 120."""
    cfg = None
    ibm = ibm_config(cfg)
    makespan = ibm_makespan_s(cfg)
    cap = float(ibm["workers"]) * makespan
    tasks = t3e_freeze_tasks(identity)
    try:
        jobs = pack_mixed_rate(tasks, cap, cfg)
    except ValueError as exc:
        return {"launch": False, "reason": str(exc), "jobs": [], "n_jobs": 0, "list_usd": 0.0}
    list_usd = wp27_list_usd(jobs, cfg)
    n_jobs = len(jobs)
    brain_s = sum(float(task["brain_s"]) for job in jobs for task in job)
    engine_usd = brain_s * WP30_PACK_RATE * WP27_USD_PER_H / (3600.0 * float(ibm["workers"]))
    launch = n_jobs <= WP30_MAX_JOBS and list_usd <= WP30_CAP_USD
    reason = None
    if n_jobs > WP30_MAX_JOBS:
        reason = f"{n_jobs} jobs exceeds one box"
    elif list_usd > WP30_CAP_USD:
        reason = f"list ${list_usd:.2f} exceeds ${WP30_CAP_USD:.0f}"
    return {
        "launch": launch,
        "reason": reason,
        "jobs": jobs,
        "n_jobs": n_jobs,
        "n_tasks": sum(len(job) for job in jobs),
        "brain_s": brain_s,
        "list_usd": list_usd,
        "engine_usd": engine_usd,
        "pack_worker_s_per_brain_s": WP30_PACK_RATE,
        "max_instances": WP30_MAX_JOBS,
        "candidate_id": WP30_PASSER_ID,
        "arm_id": "sens",
        "diagnostic": False,
    }


def t3e_freeze_plan_record() -> dict[str, Any]:
    """Launch plan for the WP30 freeze wave. Units: s, USD. No task payloads."""
    packed = t3e_freeze_wave_tasks()
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
    run_weights = list(wp30_run_weights())
    pairs = {str(w): list(wp30_pair_weights(w)) for w in WP30_CANDIDATE_WEIGHTS}
    return {
        "class": "development",
        "sub_tier": "T3e",
        "stage": "freeze",
        "wave": "wp30",
        "item": 120,
        "engine_model": "lif",
        "substrate": "1.0-4.0-0.0-False-100-<w>-kc-6.0-sens",
        "candidate_id": WP30_PASSER_ID,
        "arm_id": "sens",
        "bg_policy": "sens",
        "flags": [],
        "admitted_t1": False,
        "admitted_t2": False,
        "diagnostic": False,
        "launch": packed["launch"],
        "reason": packed["reason"],
        "n_jobs": packed["n_jobs"],
        "n_tasks": packed["n_tasks"],
        "brain_s": packed["brain_s"],
        "list_usd": packed["list_usd"],
        "engine_usd": packed.get("engine_usd"),
        "list_cap_usd": WP30_CAP_USD,
        "pack_worker_s_per_brain_s": packed["pack_worker_s_per_brain_s"],
        "max_instances": packed["max_instances"],
        "candidate_weights": list(WP30_CANDIDATE_WEIGHTS),
        "pair_step_mv": wp30_pair_step(),
        "pair_weights": pairs,
        "run_weights": run_weights,
        "seeds": list(WP30_SEEDS),
        "perturb_delta_mv": WP30_PERTURB_DELTA,
        "perturb_seeds": list(WP30_PERTURB_SEEDS),
        "perturb_weights": list(wp30_perturb_union()),
        "perturb_by_candidate": {
            str(w): list(wp30_perturb_weights(w)) for w in WP30_CANDIDATE_WEIGHTS
        },
        "pools": ["clamped"],
        "lab_measures": {
            "single_unit_fano_ms": 100,
            "central_fano_n": 2000,
            "pairwise_corr_ms": 50,
            "pair_n": 500,
            "pca_participation_ratio": True,
            "recorded_only": True,
            "on": "diag-long [2, 12)",
        },
        "ranking": (
            "A weight ranks if the R-screen holds on every seed at both pair weights, "
            "dark MN9 stays under 5 Hz in every seed, and item 74 floors "
            "(decision 91 min-of-differences form; decision 113 min(b) at 0.4 of "
            "the same-job bare) are met on the ten seeds. "
            "No gradedness point (experiment 4). Pair step 0.20 mV as item 110.1."
        ),
        "job_shapes": shapes,
        "ibm": ibm_config(),
        "note": "No up.sh before GO wp30.",
    }


def _arm_key(unit: dict[str, Any] | None, fallback: str | None = None) -> str:
    if unit and unit.get("arm"):
        return arm_id(unit["arm"])
    if unit:
        setting = unit.get("setting") or {}
        if setting.get("arm_id"):
            return str(setting["arm_id"])
    return str(fallback or "")


def collect_t3e(
    jobs: list[tuple[Path, list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Score the 3e screen. No T1/T2 admission from this record."""
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    t0_by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sugar_by_key: dict[tuple[str, float], list[dict[str, Any]]] = defaultdict(list)
    units_by_arm: dict[str, dict[str, Any]] = {}
    ladders: dict[str, list[float]] = {}
    arm_job: dict[str, int] = {}
    bare_by_job: dict[int, list[dict[str, Any]]] = defaultdict(list)
    n_tasks = 0
    for job_i, (out, tasks) in enumerate(jobs):
        for task in tasks:
            n_tasks += 1
            path = task_ndjson_path(out, task)
            evals = _diag_eval_rows(path)
            kind = task.get("kind")
            unit = task.get("unit") or {}
            key = _arm_key(unit, task.get("arm_id"))
            job_index = int(task.get("job_index", job_i))
            if key:
                arm_job.setdefault(key, job_index)
            if unit:
                units_by_arm.setdefault(key, unit)
                arm = unit.get("arm") or {}
                if arm.get("ladder"):
                    ladders[key] = [float(w) for w in arm["ladder"]]
            if kind == "t1":
                by_arm[key].extend(evals)
            elif kind == "unit":
                t0_by_arm[key].extend(evals)
            elif kind == "t3e-sugar":
                sugar_by_key[(key, round(float(task["w_bg"]), 8))].extend(evals)
            elif kind == "bare":
                bare_by_job[job_index].extend(evals)
    ranked: list[dict[str, Any]] = []
    misses: list[dict[str, Any]] = []
    t0_rows: list[dict[str, Any]] = []
    global_bare = [float(row["difference_hz"]) for row in bare_by_job.get(0, [])]
    if not global_bare:
        global_bare = [float(row["difference_hz"]) for rows in bare_by_job.values() for row in rows][:10]
    job_bare_mean = (sum(global_bare) / len(global_bare)) if global_bare else None
    setting = Setting(1.0, 4.0, sigma_th=0.0, optic_exemption=False, n_bg=100, g_gaba_kc=6.0)
    for key, unit in units_by_arm.items():
        compact = dict(unit)
        ladder = tuple(ladders.get(key) or COMMON_LADDER)
        rows = list(by_arm.get(key, []))
        t0 = t0_by_arm.get(key, [])
        diffs = [float(row["difference_hz"]) for row in t0]
        job_i = int(arm_job.get(key, 0))
        job_bare = [float(row["difference_hz"]) for row in bare_by_job.get(job_i, [])]
        if len(job_bare) != 10:
            job_bare = list(global_bare)
        same_job_mean = (sum(job_bare) / len(job_bare)) if job_bare else None
        retention = t0_retention(sum(diffs) / len(diffs), same_job_mean) if diffs and same_job_mean else None
        t0_rows.append({
            **compact,
            "arm_id": key,
            "difference_hz": (sum(diffs) / len(diffs)) if diffs else None,
            "retention": retention,
            "t0_passed": t0_passed(retention) if retention is not None else False,
            "seeds": len(diffs),
            "job_index": job_i,
            "same_job_bare_mean": same_job_mean,
        })
        for weight in ladder[:-2]:
            screened = screen_ladder(setting, float(weight), rows, ladder)
            scored = {
                **compact,
                **screened,
                "arm_id": key,
                "w_bg": float(weight),
                "candidate_id": candidate_id({**compact, "w_bg": float(weight), "arm": compact.get("arm")}),
                "deepest": "T1",
            }
            pair_rows = [
                row for row in rows
                if round(float(row["w_bg"]), 8) in {round(float(w), 8) for w in scored["pair_weights"]}
            ]
            mn9_rows = [
                {
                    "w_bg": float(row["w_bg"]),
                    "seed": int(row["seed"]),
                    "hz": number(row.get("mn9_hz")),
                }
                for row in pair_rows
            ]
            mn9 = [v["hz"] for v in mn9_rows if v["hz"] is not None]
            scored["mn9_dark"] = mn9_rows
            scored["mn9_dark_max_hz"] = max(mn9) if mn9 else None
            scored["mn9_dark_every_seed_under_5"] = bool(mn9) and len(mn9) == len(pair_rows) and all(v < 5.0 for v in mn9)
            f_vals = [v for v in (number(row.get("F")) for row in pair_rows) if v is not None]
            low = round(float(scored["w_bg"]), 8)
            low_rows = [row for row in rows if round(float(row["w_bg"]), 8) == low]
            kc = [v for v in (number((row.get("rates_hz") or {}).get("KC")) for row in low_rows) if v is not None]
            central = [v for v in (number((row.get("rates_hz") or {}).get("central")) for row in low_rows) if v is not None]
            scored["measured_F_max_pair"] = max(f_vals) if f_vals else None
            scored["measured_kc_hz_mean"] = (sum(kc) / len(kc)) if kc else None
            scored["measured_central_hz_mean"] = (sum(central) / len(central)) if central else None
            labs = [row.get("lab") for row in low_rows if row.get("lab")]
            scored["lab"] = labs[0] if labs else None
            a: list[float] = []
            sugar_dark: list[dict[str, Any]] = []
            for w in scored["pair_weights"]:
                sugar_rows = sorted(
                    sugar_by_key.get((key, round(float(w), 8)), []),
                    key=lambda r: int(r["seed"]),
                )
                a.extend(float(r["difference_hz"]) for r in sugar_rows[:3])
                for row in sugar_rows:
                    sugar_dark.append({
                        "w_bg": float(w),
                        "seed": int(row["seed"]),
                        "hz": number(row.get("mn9_dark_hz")),
                    })
            b_rows = sorted(sugar_by_key.get((key, low), []), key=lambda r: int(r["seed"]))
            b = [float(r["difference_hz"]) for r in b_rows]
            sugar_hz = [v["hz"] for v in sugar_dark if v["hz"] is not None]
            scored["mn9_dark_sugar"] = sugar_dark
            scored["mn9_dark_sugar_max_hz"] = max(sugar_hz) if sugar_hz else None
            scored["mn9_dark_sugar_every_seed_under_5"] = (
                bool(sugar_hz) and len(sugar_hz) == len(sugar_dark) and all(v < 5.0 for v in sugar_hz)
            )
            scored["a_hz"] = a
            scored["b_hz"] = b
            if (
                scored["screen_passed"]
                and len(a) == 6 and len(b) == 10 and len(diffs) == 10
                and len(job_bare) == 10 and same_job_mean is not None
            ):
                reflex = t2_reflex_probe(
                    a, b,
                    {"upstream": diffs, "extended": diffs},
                    {"upstream": job_bare, "extended": job_bare},
                    sub_tier="T3e",
                    job_bare_mean=same_job_mean,
                )
                scored["reflex"] = reflex
                scored["deepest"] = "T2"
            if scored["screen_passed"]:
                ranked.append(scored)
            else:
                misses.append(scored)
    qualified = [
        row for row in ranked
        if bool((row.get("reflex") or {}).get("reflex_passed"))
        and bool(row.get("mn9_dark_every_seed_under_5"))
        and bool(row.get("mn9_dark_sugar_every_seed_under_5"))
    ]
    unranked = [row for row in ranked + misses if row not in qualified]
    closest = closest_miss(unranked) if unranked else closest_miss(qualified)
    failed_stage = None if qualified else ("R-reflex" if ranked else "R-screen")
    return {
        "class": "development",
        "sub_tier": "T3e",
        "stage": "screen",
        "engine_model": "lif",
        "flags": [],
        "admitted_t1": False,
        "admitted_t2": False,
        "n_tasks": n_tasks,
        "ranked": ranked,
        "misses": misses,
        "qualified": [row["candidate_id"] for row in qualified],
        "failed_stage": failed_stage,
        "closest_miss": closest,
        "n_screen_passers": len(ranked),
        "n_qualified": len(qualified),
        "t0": t0_rows,
        "job_bare_mean": job_bare_mean,
    }


def wp30_score_weights(
    candidate_weights: tuple[float, ...] | list[float] | None = None,
) -> tuple[float, ...]:
    """Candidate weights to score. Default is the full item 120 ladder. Units: mV."""
    raw = WP30_CANDIDATE_WEIGHTS if candidate_weights is None else tuple(candidate_weights)
    if not raw:
        raise ValueError("freeze candidate_weights is empty")
    allowed = {round(float(w), 8) for w in WP30_CANDIDATE_WEIGHTS}
    weights = tuple(round(float(w), 8) for w in raw)
    unknown = [w for w in weights if w not in allowed]
    if unknown:
        raise ValueError(f"freeze candidate_weights {unknown} not in {WP30_CANDIDATE_WEIGHTS}")
    return weights


def collect_t3e_freeze(
    jobs: list[tuple[Path, list[dict[str, Any]]]],
    *,
    candidate_weights: tuple[float, ...] | list[float] | None = None,
) -> dict[str, Any]:
    """Score the WP30 freeze. Ranking is item 120; no T1/T2 admission.

    candidate_weights scores a subset of 0.9, 1.0, 1.1. Omit it to score all three.
    A subset cannot close the rest search: p2_partial_b stays false while other
    weights remain not scored.
    """
    weights = wp30_score_weights(candidate_weights)
    full = tuple(round(float(w), 8) for w in WP30_CANDIDATE_WEIGHTS)
    partial = weights != full
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
                long_rows.extend(evals)
            elif kind == "diag-sugar":
                sugar[round(float(task["w_bg"]), 8)].extend(evals)
            elif kind == "diag-ff":
                ff.extend(evals)
            elif kind == "bare":
                bare.extend(evals)
            elif kind == "t1":
                pert.extend(evals)
    if len(ff) != 10:
        raise ValueError(f"freeze (c) has {len(ff)} rows, expected 10")
    if len(bare) != 10:
        raise ValueError(f"freeze bare has {len(bare)} rows, expected 10")
    upstream_c = [float(row["difference_hz"]) for row in ff]
    upstream_bare = [float(row["difference_hz"]) for row in bare]
    job_bare_mean = sum(upstream_bare) / len(upstream_bare)
    retention = t0_retention(sum(upstream_c) / len(upstream_c), job_bare_mean)
    candidate_ff = {"upstream": upstream_c, "extended": upstream_c}
    bare_ff = {"upstream": upstream_bare, "extended": [job_bare_mean] * 10}
    ranked: list[dict[str, Any]] = []
    scored_weights: list[dict[str, Any]] = []
    for weight in weights:
        pair = wp30_pair_weights(weight)
        pair_long = [
            row for row in long_rows
            if round(float(row["w_bg"]), 8) in {round(float(p), 8) for p in pair}
        ]
        screen = freeze_pair_screen(
            pair_long,
            pair_weights=pair,
            seeds=WP30_SEEDS,
            gradedness_note="item 120 freeze has no gradedness point (experiment 4)",
        )
        a: list[float] = []
        b: list[float] = []
        sugar_dark: list[dict[str, Any]] = []
        for point in pair:
            rows = sorted(
                sugar.get(round(float(point), 8), []),
                key=lambda r: int(r["seed"]),
            )
            diffs = [float(row["difference_hz"]) for row in rows]
            a.extend(diffs[:3])
            if round(float(point), 8) == round(float(weight), 8):
                b = diffs
            for row in rows:
                sugar_dark.append({
                    "w_bg": float(point),
                    "seed": int(row["seed"]),
                    "hz": number(
                        row.get("mn9_dark_hz")
                        if row.get("mn9_dark_hz") is not None
                        else (row.get("silent") or {}).get("mn9_hz")
                    ),
                })
        if len(a) != 6:
            raise ValueError(f"freeze (a) at {weight} has {len(a)} rows, expected 6")
        if len(b) != 10:
            raise ValueError(f"freeze (b) at {weight} has {len(b)} rows, expected 10")
        mn9_rows = [
            {
                "w_bg": float(row["w_bg"]),
                "seed": int(row["seed"]),
                "hz": number(row.get("mn9_hz")),
            }
            for row in pair_long
        ]
        mn9 = [v["hz"] for v in mn9_rows if v["hz"] is not None]
        mn9_under_5 = bool(mn9) and len(mn9) == len(pair_long) and all(v < 5.0 for v in mn9)
        sugar_hz = [v["hz"] for v in sugar_dark if v["hz"] is not None]
        sugar_under_5 = (
            bool(sugar_hz) and len(sugar_hz) == len(sugar_dark) and all(v < 5.0 for v in sugar_hz)
        )
        h_vals = [
            float(row["h_max"])
            for row in (*pair_long, *ff, *bare, *pert)
            if row.get("h_max") is not None
        ]
        for rows in (sugar.get(round(float(p), 8), []) for p in pair):
            h_vals.extend(float(row["h_max"]) for row in rows if row.get("h_max") is not None)
        reflex = t2_reflex_probe(
            a, b, candidate_ff, bare_ff,
            h_max=max(h_vals) if h_vals else None,
            sub_tier="T3e",
            job_bare_mean=job_bare_mean,
        )
        perturb_w = wp30_perturb_weights(weight)
        perturbation = freeze_perturbation(pert, weights=perturb_w, seeds=WP30_PERTURB_SEEDS)
        labs = [row.get("lab") for row in pair_long if round(float(row["w_bg"]), 8) == round(float(weight), 8) and row.get("lab")]
        unit = t3e_freeze_unit()
        unit["w_bg"] = float(weight)
        unit["pair_weights"] = list(pair)
        cid = candidate_id(unit)
        row = {
            **unit,
            "candidate_id": cid,
            **screen,
            "w_bg": float(weight),
            "mn9_dark": mn9_rows,
            "mn9_dark_max_hz": max(mn9) if mn9 else None,
            "mn9_dark_every_seed_under_5": mn9_under_5,
            "mn9_dark_sugar": sugar_dark,
            "mn9_dark_sugar_max_hz": max(sugar_hz) if sugar_hz else None,
            "mn9_dark_sugar_every_seed_under_5": sugar_under_5,
            "a_hz": a,
            "b_hz": b,
            "reflex": reflex,
            "reflex_passed": bool(reflex.get("reflex_passed")),
            "reflex_harmonised": bool(reflex.get("reflex_harmonised")),
            "reflex_verdicts": reflex.get("reflex_verdicts"),
            "perturbation": perturbation,
            "retention": {"upstream": retention, "extended": retention},
            "lab": labs[0] if labs else None,
            "J": 0.0,
            "deepest": "T2",
            "ranked_here": bool(
                screen.get("screen_passed")
                and mn9_under_5
                and sugar_under_5
                and reflex.get("reflex_passed")
            ),
        }
        scored_weights.append(row)
        if row["ranked_here"]:
            ranked.append(row)
    unranked = [row for row in scored_weights if not row["ranked_here"]]
    closest = closest_miss(unranked) if unranked else closest_miss(ranked)
    failed_stage = None if ranked else (
        "R-reflex" if any(r.get("screen_passed") for r in scored_weights) else "R-screen"
    )
    return {
        "class": "development",
        "sub_tier": "T3e",
        "stage": "freeze",
        "wave": "wp30",
        "item": 120,
        "engine_model": "lif",
        "candidate_id": WP30_PASSER_ID,
        "arm_id": "sens",
        "flags": [],
        "admitted_t1": False,
        "admitted_t2": False,
        "diagnostic": False,
        "n_tasks": n_tasks,
        "n_jobs": len(jobs),
        "partial": partial,
        "candidate_weights": [float(w) for w in weights],
        "ranked": [row["candidate_id"] for row in ranked],
        "ranked_rows": ranked,
        "weights": scored_weights,
        "closest_miss": closest,
        "failed_stage": failed_stage,
        "job_bare_mean": job_bare_mean,
        "t0": {
            "difference_hz": (sum(upstream_c) / len(upstream_c)) if upstream_c else None,
            "retention": retention,
            "t0_passed": t0_passed(retention) if retention is not None else False,
            "seeds": len(upstream_c),
            "same_job_bare_mean": job_bare_mean,
        },
        "mean_wall_per_brain_s": (sum(rates) / len(rates)) if rates else None,
        "p2_partial_b": False if partial else (not bool(ranked)),
    }


def t3e_task_name(task: dict[str, Any], job_index: int, i: int) -> str:
    """File-safe task name. Units: none."""
    kind = task["kind"]
    arm = _arm_key(task.get("unit"), task.get("arm_id")) or "none"
    if kind == "diag-long":
        pools = "clamped" if task.get("clamp") else "free"
        return f"long-{pools}-w{int(round(float(task['w_bg']) * 100)):03d}-s{int(task['seed'])}"
    if kind == "diag-sugar":
        return f"sugar-w{int(round(float(task['w_bg']) * 100)):03d}"
    if kind == "diag-ff":
        return "ff-c"
    if kind == "t1":
        if task.get("stage") == "freeze":
            return f"pert-s{int(task['seed'])}"
        return f"t3e-{arm}-s{int(task['seed'])}"
    if kind == "unit":
        return f"t3e-{arm}-t0"
    if kind == "t3e-sugar":
        return f"t3e-{arm}-sugar-w{int(round(float(task['w_bg']) * 100)):03d}"
    if kind == "bare":
        return f"bare-{job_index:02d}"
    return f"{kind}-{job_index:02d}-{i:03d}"


def t3e_worker(payload: dict[str, Any]) -> str:
    """One 3e child: apply the arm, then T0, T1, sugar, or bare."""
    import json as json_mod
    import time
    from pathlib import Path as PathType

    from flyonenomics.drive.rest_map import _build_engine, _json_safe, _probe

    path = PathType(payload["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite evaluation evidence: {path}")
    deadline = time.monotonic() + payload["wall_cap_s"]
    kind = payload["kind"]
    unit = payload.get("unit")
    bare = kind == "bare"
    setting = setting_from_unit(unit, bare=bare)
    identity = payload["identity"]
    meta = {
        **identity,
        "stage": "T3e",
        "kind": kind,
        "task_id": path.stem,
        "plan_sha256": payload["plan_sha256"],
        "engine_model": "lif",
        "setting": None if (bare or not unit) else unit.get("setting"),
        "unit": unit,
        "arm_id": _arm_key(unit, payload.get("arm_id")),
        "w_bg": payload.get("w_bg"),
    }
    t_build = time.monotonic()
    with path.open("x") as handle:
        def emit(row: dict[str, Any]) -> None:
            handle.write(json_mod.dumps({**meta, **_json_safe(row)}, allow_nan=False) + "\n")
            handle.flush()

        try:
            feedforward = kind in {"unit", "bare"}
            mode = "extended" if kind in {"unit", "t3e-sugar", "bare"} else "dark"
            if kind == "bare":
                mode, feedforward = "extended", True
            built = _build_engine(
                setting, mode=mode, bare=bare, feedforward=feedforward,
                mechanisms=None, mechanisms_section=None,
                clamp=True if kind in {"t3e-sugar", "unit", "bare"} else None,
            )
            if unit and unit.get("arm"):
                apply_arm(built, unit["arm"])
            if kind != "t1":
                built.pop("lab_sample", None)
            build_s = time.monotonic() - t_build
            emit({"kind": "task-build", "build_s": build_s, "k_distribution": built.get("k_distribution"),
                  "hubs": built.get("hubs")})
            brain_s = 0.0
            n_eval = 0
            if kind == "t1":
                for weight, seed in payload["probes"]:
                    row = _probe(built, float(weight), int(seed), seconds=10.0, edge_s=1.0, deadline=deadline)
                    brain_s += 12.0
                    n_eval += 1
                    emit({"kind": "evaluation", **row})
            else:
                seconds = 1.0 if kind in {"unit", "bare"} else float(payload.get("measure_s") or 1.0)
                weight = 0.0 if kind in {"unit", "bare"} else float(payload["w_bg"])
                for seed in payload["seeds"]:
                    silent = _probe(built, weight, int(seed), seconds=seconds, deadline=deadline)
                    sugar = _probe(
                        built, weight, int(seed), seconds=seconds, active=True, deadline=deadline,
                    )
                    brain_s += 2.0 * (2.0 + seconds)
                    n_eval += 1
                    h_vals = [p.get("h_max") for p in (silent, sugar) if p.get("h_max") is not None]
                    emit({
                        "kind": "evaluation",
                        "seed": int(seed),
                        "w_bg": weight,
                        "silent": silent,
                        "sugar": sugar,
                        "difference_hz": sugar["mn9_hz"] - silent["mn9_hz"],
                        "mn9_dark_hz": silent["mn9_hz"],
                        "h_max": max(h_vals) if h_vals else None,
                    })
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
