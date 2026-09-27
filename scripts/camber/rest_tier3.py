#!/usr/bin/env python3
"""WP24 Camber driver: T0/T1/T2 packing of SPEC-P2 section 6.5."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from flyonenomics.drive import rest_map as rest
from flyonenomics.drive.rest_tier3 import (
    T3C_T1_DT_MS,
    T3D_T1_SLICE_WORKER_S,
    WP27_PACK_RATE,
    collect_diag,
    collect_freeze,
    collect_packed_t0,
    collect_sigma,
    collect_t0,
    collect_t1,
    collect_t2,
    collect_t3c_convergence,
    decide_t3c_item89,
    dt_ms_tag,
    ibm_config,
    plan_record,
    t0_tasks,
    t0_worker,
    t1_tasks,
    t1_worker,
    t2_tasks,
    t2_worker,
    t3c_convergence_plan,
    t3c_t1_plan,
    t3c_t1_record,
    t3c_t2_record,
    t3d_wave_tasks,
    task_ndjson_path,
    task_worker_s,
    wave_worker,
    wp27_freeze_plan_record,
    wp27_packed_wave,
    wp27_plan_record,
)
from flyonenomics.drive.rest_tier3e import (
    collect_t3e,
    collect_t3e_freeze,
    hubs_from_plan,
    t3e_freeze_plan_record,
    t3e_freeze_wave_tasks,
    t3e_plan_record,
    t3e_task_name,
    t3e_wave_tasks,
    t3e_worker,
)
from flyonenomics.io import read_json


def save(path: Path, data: Any) -> None:
    rest._write_json(path, data)


def load(path: Path) -> Any:
    return read_json(path)


def execute_payloads(tasks: list[dict[str, Any]], workers: str | int, worker) -> None:
    """Spawn isolation; Mac uses the shared slot lease, Camber an explicit bound."""
    import multiprocessing as mp
    import platform
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from contextlib import nullcontext
    from flyonenomics.orchestrator.budget import lease_workers, swap_used_mib

    if not tasks:
        return
    if platform.system() == "Darwin":
        if workers != "auto":
            raise ValueError("Mac rest runs require --workers auto")
        if swap_used_mib() > 4000:
            raise RuntimeError("Mac swap exceeds 4000 MiB")
        lease = lease_workers("auto", len(tasks))
    else:
        ceiling = max(62, os.cpu_count() or 0)
        if workers == "auto" or not 1 <= int(workers) <= ceiling:
            raise ValueError(f"Camber needs an explicit worker count in 1..{ceiling}")
        lease = nullcontext(None)
    with lease as held:
        count = held.count if held is not None else min(int(workers), len(tasks))
        with ProcessPoolExecutor(
            max_workers=count, mp_context=mp.get_context("spawn"), max_tasks_per_child=1,
        ) as pool:
            futures = [pool.submit(worker, payload) for payload in tasks]
            for future in as_completed(futures):
                print(json.dumps({"completed": future.result()}), flush=True)


def execute_t0(tasks: list[dict[str, Any]], workers: str | int) -> None:
    execute_payloads(tasks, workers, t0_worker)


def job_payloads(plan: dict[str, Any], job_index: int, out: Path, identity: dict[str, Any], rho_mech: float) -> list[dict[str, Any]]:
    """Executable T0 tasks of one packed job under section 6.5."""
    packed = t0_tasks(plan["sub_tier"], rho_mech, identity=identity)
    if not packed["launch"]:
        raise ValueError(packed.get("reason") or "T0 plan is not launchable")
    if job_index < 0 or job_index >= len(packed["jobs"]):
        raise ValueError(f"job-index {job_index} outside 0..{len(packed['jobs']) - 1}")
    plan_sha = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    tasks = []
    for i, task in enumerate(packed["jobs"][job_index]):
        brain = float(task["brain_s"])
        worker_s = task_worker_s(brain, rho_mech)
        name = f"{task['kind']}-{job_index:02d}-{i:03d}"
        tasks.append({
            "path": str(out / f"{name}.ndjson"),
            "kind": task["kind"],
            "unit": task["unit"],
            "seeds": task["seeds"],
            "identity": identity,
            "plan_sha256": plan_sha,
            "wall_cap_s": 2.0 * worker_s,
            "brain_s": brain,
        })
    return tasks


def _plan_pack_rate(plan: dict[str, Any]) -> float | None:
    if plan.get("pack_worker_s_per_brain_s") is not None:
        return float(plan["pack_worker_s_per_brain_s"])
    shaped = plan.get("measured_rate") or {}
    if shaped.get("replaced"):
        return float(shaped["worker_s_per_brain_s"])
    return None


def t1_job_payloads(plan: dict[str, Any], job_index: int, out: Path, identity: dict[str, Any]) -> list[dict[str, Any]]:
    """Executable T1 tasks of one packed job under section 6.5."""
    rho_mech = float(plan["rho_mech"])
    override = _plan_pack_rate(plan)
    makespan = float(plan["makespan_s"]) if plan.get("makespan_s") is not None else None
    packed = t1_tasks(
        plan["admitted"], rho_mech, identity=identity,
        worker_s_per_brain_s=override, makespan=makespan,
    )
    if not packed["launch"]:
        raise ValueError(packed.get("reason") or "T1 plan is not launchable")
    if job_index < 0 or job_index >= len(packed["jobs"]):
        raise ValueError(f"job-index {job_index} outside 0..{len(packed['jobs']) - 1}")
    plan_sha = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    dt_ms = plan.get("dt_ms")
    tasks = []
    for task in packed["jobs"][job_index]:
        brain = float(task["brain_s"])
        worker_s = task_worker_s(brain, rho_mech, worker_s_per_brain_s=override)
        start, stop = task["slice"]
        name = f"u{task['unit_index']:02d}-s{task['seed']}-w{start:02d}-{stop:02d}"
        payload = {
            **task,
            "path": str(out / f"{name}.ndjson"),
            "identity": identity,
            "plan_sha256": plan_sha,
            "wall_cap_s": 2.0 * worker_s,
        }
        if dt_ms is not None:
            payload["dt_ms"] = float(dt_ms)
        tasks.append(payload)
    return tasks


def wave_job_payloads(plan: dict[str, Any], job_index: int, out: Path, identity: dict[str, Any]) -> list[dict[str, Any]]:
    """Executable mixed T0+T1 tasks of one T3d IBM wave job."""
    packed = t3d_wave_tasks(identity=identity)
    if not packed["launch"]:
        raise ValueError(packed.get("reason") or "T3d wave is not launchable")
    if job_index < 0 or job_index >= len(packed["jobs"]):
        raise ValueError(f"job-index {job_index} outside 0..{len(packed['jobs']) - 1}")
    plan_sha = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    pack_rate = float(packed.get("pack_worker_s_per_brain_s") or ibm_config()["worker_s_per_brain_s"])
    slice_rate = float(packed.get("t1_slice_worker_s_per_brain_s") or T3D_T1_SLICE_WORKER_S)
    tasks = []
    for i, task in enumerate(packed["jobs"][job_index]):
        brain = float(task["brain_s"])
        kind = task["kind"]
        rate = slice_rate if kind == "t1" else pack_rate
        worker_s = task_worker_s(brain, 1.0, worker_s_per_brain_s=rate)
        if kind == "t1":
            start, stop = task["slice"]
            name = f"u{task['unit_index']:02d}-s{task['seed']}-w{start:02d}-{stop:02d}"
            tasks.append({
                **task,
                "path": str(out / f"{name}.ndjson"),
                "identity": identity,
                "plan_sha256": plan_sha,
                "wall_cap_s": 2.0 * worker_s,
            })
        else:
            name = f"{kind}-{job_index:02d}-{i:03d}"
            tasks.append({
                "path": str(out / f"{name}.ndjson"),
                "kind": kind,
                "unit": task["unit"],
                "seeds": task["seeds"],
                "identity": identity,
                "plan_sha256": plan_sha,
                "wall_cap_s": 2.0 * worker_s,
                "brain_s": brain,
            })
    return tasks


def t2_task_name(task: dict[str, Any]) -> str:
    if task["kind"] == "bare":
        return f"bare-s{int(task['seed']):02d}"
    weight = task.get("w_bg")
    wtag = f"-w{int(round(float(weight) * 100)):03d}" if weight is not None else ""
    return f"c{int(task['candidate_index']):02d}-{task['kind']}{wtag}-s{int(task['seed']):02d}"


def t2_job_payloads(plan: dict[str, Any], job_index: int, out: Path, identity: dict[str, Any]) -> list[dict[str, Any]]:
    """Executable T2 tasks of one packed job under section 6.5."""
    rho_mech = float(plan["rho_mech"])
    override = _plan_pack_rate(plan)
    packed = t2_tasks(plan["admitted"], rho_mech, identity=identity, worker_s_per_brain_s=override)
    if not packed["launch"]:
        raise ValueError(packed.get("reason") or "T2 plan is not launchable")
    if job_index < 0 or job_index >= len(packed["jobs"]):
        raise ValueError(f"job-index {job_index} outside 0..{len(packed['jobs']) - 1}")
    plan_sha = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    dt_ms = plan.get("dt_ms")
    tasks = []
    for task in packed["jobs"][job_index]:
        brain = float(task["brain_s"])
        worker_s = task_worker_s(brain, rho_mech, worker_s_per_brain_s=override)
        name = t2_task_name(task)
        payload = {
            **task,
            "path": str(out / f"{name}.ndjson"),
            "identity": identity,
            "plan_sha256": plan_sha,
            "wall_cap_s": 2.0 * worker_s,
        }
        if dt_ms is not None:
            payload["dt_ms"] = float(dt_ms)
        tasks.append(payload)
    return tasks


def wp27_task_name(task: dict[str, Any], job_index: int, i: int) -> str:
    kind = task["kind"]
    if kind == "diag-long":
        pools = "clamped" if task.get("clamp") else "free"
        return f"long-{pools}-w{int(round(float(task['w_bg']) * 100)):03d}-s{int(task['seed'])}"
    if kind == "diag-sugar":
        return f"sugar-w{int(round(float(task['w_bg']) * 100)):03d}"
    if kind == "diag-ff":
        return "ff-c"
    if kind == "sigma-sugar":
        sigma = task.get("sigma_th", (task.get("unit") or {}).get("sigma_th", 0.0))
        return f"sigma{sigma}-sugar-w{int(round(float(task['w_bg']) * 100)):03d}"
    if kind == "t1":
        sigma = task.get("sigma_th", (task.get("unit") or {}).get("sigma_th", 0.0))
        return f"sigma{sigma}-s{int(task['seed'])}"
    if kind == "unit":
        sigma = task.get("sigma_th", (task.get("unit") or {}).get("sigma_th", 0.0))
        return f"sigma{sigma}-t0"
    if kind == "bare":
        return f"bare-{job_index:02d}"
    return f"{kind}-{job_index:02d}-{i:03d}"


def wp27_job_payloads(plan: dict[str, Any], job_index: int, out: Path, identity: dict[str, Any]) -> list[dict[str, Any]]:
    """Executable WP27 diagnostic or freeze tasks of one packed job."""
    packed = wp27_packed_wave(plan, identity)
    if not packed["launch"]:
        raise ValueError(packed.get("reason") or "WP27 wave is not launchable")
    if job_index < 0 or job_index >= len(packed["jobs"]):
        raise ValueError(f"job-index {job_index} outside 0..{len(packed['jobs']) - 1}")
    plan_sha = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    tasks = []
    for i, task in enumerate(packed["jobs"][job_index]):
        brain = float(task["brain_s"])
        rate = float(task.get("pack_rate") or packed.get("pack_worker_s_per_brain_s") or WP27_PACK_RATE)
        worker_s = task_worker_s(brain, 1.0, worker_s_per_brain_s=rate)
        name = wp27_task_name(task, job_index, i)
        tasks.append({
            **task,
            "path": str(out / f"{name}.ndjson"),
            "identity": identity,
            "plan_sha256": plan_sha,
            "wall_cap_s": 2.0 * worker_s,
        })
    return tasks


def cmd_plan_diag(args: argparse.Namespace) -> None:
    record = wp27_plan_record()
    dest = Path(args.out)
    save(dest, record)
    print(json.dumps({
        "path": str(dest),
        "n_jobs": record["n_jobs"],
        "launch": record["launch"],
        "list_usd": record["list_usd"],
        "brain_s": record["brain_s"],
    }, indent=2))


def cmd_plan_freeze(args: argparse.Namespace) -> None:
    record = wp27_freeze_plan_record()
    dest = Path(args.out)
    save(dest, record)
    print(json.dumps({
        "path": str(dest),
        "n_jobs": record["n_jobs"],
        "launch": record["launch"],
        "list_usd": record["list_usd"],
        "brain_s": record["brain_s"],
        "candidate_id": record["candidate_id"],
    }, indent=2))


def cmd_plan(args: argparse.Namespace) -> None:
    record = plan_record(args.sub_tier, args.rho)
    dest = Path(args.out)
    save(dest, record)
    print(json.dumps({"path": str(dest), "n_jobs": record["job_shapes"]["n_jobs"],
                      "launch": record["job_shapes"]["launch"]}, indent=2))


def cmd_t0(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    identity = rest.execution_identity(args.job_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = job_payloads(plan, args.job_index, out, identity, float(plan["rho_mech"]))
    save(out / "tasks.json", tasks)
    pending = [task for task in tasks if not Path(task["path"]).exists()]
    execute_t0(pending, args.workers)
    summary = collect_t0(out, tasks)
    save(out / "summary.json", summary)
    print(json.dumps({"units": len(summary["units"]), "job_bare_mean": summary["job_bare_mean"]}, indent=2))


def cmd_t1(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    identity = rest.execution_identity(args.job_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = t1_job_payloads(plan, args.job_index, out, identity)
    save(out / "tasks.json", tasks)
    pending = [task for task in tasks if not Path(task["path"]).exists()]
    execute_payloads(pending, args.workers, t1_worker)
    print(json.dumps({"tasks": len(tasks), "pending": len(pending)}, indent=2))


def cmd_t2(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    identity = rest.execution_identity(args.job_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = t2_job_payloads(plan, args.job_index, out, identity)
    save(out / "tasks.json", tasks)
    pending = [task for task in tasks if not Path(task["path"]).exists()]
    execute_payloads(pending, args.workers, t2_worker)
    print(json.dumps({"tasks": len(tasks), "pending": len(pending)}, indent=2))


def cmd_wave(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    if plan.get("sub_tier") != "T3d":
        raise SystemExit("wave runs the T3d T0+T1 plan")
    identity = rest.execution_identity(args.job_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = wave_job_payloads(plan, args.job_index, out, identity)
    save(out / "tasks.json", tasks)
    pending = [task for task in tasks if not Path(task["path"]).exists()]
    execute_payloads(pending, args.workers, wave_worker)
    print(json.dumps({"tasks": len(tasks), "pending": len(pending)}, indent=2))


def cmd_collect(args: argparse.Namespace) -> None:
    tasks = load(Path(args.tasks))
    summary = collect_t0(Path(args.out), tasks)
    dest = Path(args.summary) if args.summary else Path(args.out) / "summary.json"
    save(dest, summary)
    print(json.dumps({"path": str(dest), "units": len(summary["units"])}, indent=2))


def cmd_collect_packed(args: argparse.Namespace) -> None:
    spec = load(Path(args.jobs))
    jobs = [(Path(row["out"]), load(Path(row["tasks"]))) for row in spec]
    summaries = collect_packed_t0(jobs)
    dest = Path(args.summary)
    save(dest, summaries)
    print(json.dumps({"path": str(dest), "n_jobs": len(summaries)}, indent=2))


def cmd_collect_t1(args: argparse.Namespace) -> None:
    spec = load(Path(args.jobs))
    jobs = [(Path(row["out"]), load(Path(row["tasks"]))) for row in spec]
    t0_units = None
    if args.t0:
        record = load(Path(args.t0))
        t0_units = record.get("units") if isinstance(record, dict) else record
    dt_ms = float(args.dt_ms) if getattr(args, "dt_ms", None) not in (None, "") else None
    summary = collect_t1(jobs, t0_units=t0_units, dt_ms=dt_ms)
    dest = Path(args.summary)
    save(dest, summary)
    print(json.dumps({
        "path": str(dest),
        "n_units": summary["n_units"],
        "n_screen_passers": summary["n_screen_passers"],
        "n_t2_admitted": summary["n_t2_admitted"],
        "grid_edge": summary["grid_edge"],
        "t2_b_unreachable": summary["t2_b_unreachable"],
    }, indent=2))


def t3c_dt_job_payloads(plan: dict[str, Any], out: Path, identity: dict[str, Any]) -> list[dict[str, Any]]:
    """One-seed T0 payloads at recorded dt, dt/2, dt/4. Wall cap scales with 1/dt."""
    recorded = float(plan["recorded_dt_ms"])
    rho = float(plan["rho_mech"])
    rate0 = ibm_config()["worker_s_per_brain_s"] * rho
    plan_sha = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    jobs = plan["jobs"]
    if len(jobs) != 1:
        raise ValueError("t3c-dt plan has one job")
    tasks = []
    for i, task in enumerate(jobs[0]):
        dt = float(task["dt_ms"])
        brain = float(task["brain_s"])
        scale = recorded / dt
        worker_s = task_worker_s(brain, 1.0, worker_s_per_brain_s=rate0 * scale)
        name = f"{task['kind']}-{dt_ms_tag(dt)}-{i:03d}"
        tasks.append({
            "path": str(out / f"{name}.ndjson"),
            "kind": task["kind"],
            "unit": task["unit"],
            "seeds": task["seeds"],
            "dt_ms": dt,
            "identity": identity,
            "plan_sha256": plan_sha,
            "wall_cap_s": 2.0 * worker_s,
            "brain_s": brain,
        })
    return tasks


def cmd_t3c_dt_plan(args: argparse.Namespace) -> None:
    t0_record = load(Path(args.t0)) if args.t0 else None
    record = t3c_convergence_plan(t0_record)
    dest = Path(args.out)
    save(dest, record)
    print(json.dumps({
        "path": str(dest),
        "n_units": record["n_units"],
        "n_tasks": record["n_tasks"],
        "steps_ms": record["steps_ms"],
        "t0_brain_s": record["t0_brain_s"],
    }, indent=2))


def cmd_t3c_dt(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    identity = rest.execution_identity(args.job_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = t3c_dt_job_payloads(plan, out, identity)
    save(out / "tasks.json", tasks)
    pending = [task for task in tasks if not Path(task["path"]).exists()]
    execute_payloads(pending, args.workers, t0_worker)
    summary = collect_t3c_convergence(out, tasks)
    save(out / "summary.json", summary)
    print(json.dumps({
        "n_units": summary["n_units"],
        "n_rows": summary["n_rows"],
        "overall_verdict": summary["overall_verdict"],
        "readmission": summary["readmission"],
    }, indent=2))


def cmd_collect_t3c_dt(args: argparse.Namespace) -> None:
    tasks = load(Path(args.tasks))
    summary = collect_t3c_convergence(Path(args.out), tasks)
    dest = Path(args.summary) if args.summary else Path(args.out) / "summary.json"
    save(dest, summary)
    print(json.dumps({
        "path": str(dest),
        "n_units": summary["n_units"],
        "n_rows": summary["n_rows"],
        "overall_verdict": summary["overall_verdict"],
    }, indent=2))


def cmd_t3c_t1_plan(args: argparse.Namespace) -> None:
    t0_record = load(Path(args.t0)) if args.t0 else None
    record = t3c_t1_plan(t0_record)
    dest = Path(args.out)
    save(dest, record)
    shapes = record["job_shapes"]
    print(json.dumps({
        "path": str(dest),
        "n_units": record["n_units"],
        "n_tasks": shapes["n_tasks"],
        "n_jobs": shapes["n_jobs"],
        "dt_ms": record["dt_ms"],
        "t1_brain_s": shapes["t1_brain_s"],
        "launch": shapes["launch"],
    }, indent=2))


def cmd_t3c_t1(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    identity = rest.execution_identity(args.job_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dt_ms = float(plan.get("dt_ms") or T3C_T1_DT_MS)
    n_jobs = int(plan["job_shapes"]["n_jobs"])
    all_t1: list[dict[str, Any]] = []
    for job_index in range(n_jobs):
        all_t1.extend(t1_job_payloads(plan, job_index, out, identity))
    save(out / "tasks.json", all_t1)
    pending = [task for task in all_t1 if not Path(task["path"]).exists()]
    execute_payloads(pending, args.workers, t1_worker)
    t1_summary = collect_t1([(out, all_t1)], dt_ms=dt_ms)
    save(out / "summary.json", t1_summary)
    result: dict[str, Any] = {
        "n_units": t1_summary["n_units"],
        "n_screen_passers": t1_summary["n_screen_passers"],
        "n_t2_admitted": t1_summary["n_t2_admitted"],
        "dt_ms": dt_ms,
        "t2": False,
    }
    if t1_summary["n_t2_admitted"]:
        t2_plan = {
            "rho_mech": plan["rho_mech"],
            "admitted": t1_summary["admitted"],
            "pack_worker_s_per_brain_s": plan.get("pack_worker_s_per_brain_s"),
            "dt_ms": dt_ms,
        }
        packed = t2_tasks(
            t2_plan["admitted"], float(t2_plan["rho_mech"]),
            worker_s_per_brain_s=_plan_pack_rate(t2_plan),
        )
        if not packed["launch"]:
            raise ValueError(packed.get("reason") or "item 89 T2 plan is not launchable")
        t2_jobs: list[list[dict[str, Any]]] = []
        for job_index in range(packed["n_jobs"]):
            t2_jobs.append(t2_job_payloads(t2_plan, job_index, out, identity))
        flat = [task for job in t2_jobs for task in job]
        save(out / "t2-tasks.json", flat)
        pending_t2 = [task for task in flat if not Path(task["path"]).exists()]
        execute_payloads(pending_t2, args.workers, t2_worker)
        t2_summary = collect_t2(
            [(out, job) for job in t2_jobs], dt_ms=dt_ms,
        )
        save(out / "t2-summary.json", t2_summary)
        result["t2"] = True
        result["n_reflex_passed"] = t2_summary["n_reflex_passed"]
        result["n_long_passed"] = t2_summary["n_long_passed"]
        result["n_reflex_harmonised"] = t2_summary["n_reflex_harmonised"]
    print(json.dumps(result, indent=2))


def cmd_collect_t3c_t1(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    out = Path(args.out)
    t1_tasks_path = Path(args.tasks) if args.tasks else out / "tasks.json"
    t1_payloads = load(t1_tasks_path)
    dt_ms = float(plan.get("dt_ms") or T3C_T1_DT_MS)
    t1_summary = collect_t1([(out, t1_payloads)], dt_ms=dt_ms)
    t2_summary = None
    t2_path = out / "t2-summary.json"
    t2_tasks_path = out / "t2-tasks.json"
    if t2_path.is_file():
        t2_summary = load(t2_path)
    elif t2_tasks_path.is_file():
        t2_payloads = load(t2_tasks_path)
        t2_summary = collect_t2([(out, t2_payloads)], dt_ms=dt_ms)
    record = t3c_t1_record(
        plan, t1_summary, jobs=args.jobs.split(",") if args.jobs else [], t2=t2_summary,
    )
    dest = Path(args.summary) if args.summary else out / "rest-T3c-T1.json"
    save(dest, record)
    printed: dict[str, Any] = {
        "path": str(dest),
        "n_units": record["n_units"],
        "n_screen_passers": record["n_screen_passers"],
        "n_t2_admitted": record["n_t2_admitted"],
        "dt_ms": record["dt_ms"],
        "t2": t2_summary is not None,
    }
    if t2_summary is not None and args.t2_summary:
        t2_record = t3c_t2_record(plan, t2_summary, jobs=args.jobs.split(",") if args.jobs else [])
        t2_dest = Path(args.t2_summary)
        save(t2_dest, t2_record)
        printed["t2_path"] = str(t2_dest)
        printed["n_reflex_passed"] = t2_summary["n_reflex_passed"]
        printed["n_long_passed"] = t2_summary["n_long_passed"]
    if args.decision:
        existing = load(Path(args.decision_in) if args.decision_in else Path("validation/records/p2/rest-T3c-decision.json"))
        updated = decide_t3c_item89(existing, t1_summary, t2_summary)
        save(Path(args.decision), updated)
        printed["decision"] = args.decision
        printed["failed_stage"] = updated["failed_stage"]
    print(json.dumps(printed, indent=2))


def cmd_diag(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    identity = rest.execution_identity(args.job_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = wp27_job_payloads(plan, args.job_index, out, identity)
    save(out / "tasks.json", tasks)
    pending = [task for task in tasks if not Path(task["path"]).exists()]
    execute_payloads(pending, args.workers, wave_worker)
    print(json.dumps({"tasks": len(tasks), "pending": len(pending)}, indent=2))


def cmd_collect_diag(args: argparse.Namespace) -> None:
    spec = load(Path(args.jobs))
    jobs = [(Path(row["out"]), load(Path(row["tasks"]))) for row in spec]
    summary = collect_diag(jobs)
    dest = Path(args.summary)
    save(dest, summary)
    print(json.dumps({
        "path": str(dest),
        "n_long": summary["n_long"],
        "admitted_t1": summary["admitted_t1"],
        "admitted_t2": summary["admitted_t2"],
        "median_22r": summary["median_22r"]["passed"],
        "reflex_passed": summary["reflex"]["reflex_passed"],
    }, indent=2))


def cmd_collect_sigma(args: argparse.Namespace) -> None:
    spec = load(Path(args.jobs))
    jobs = [(Path(row["out"]), load(Path(row["tasks"]))) for row in spec]
    summary = collect_sigma(jobs)
    dest = Path(args.summary)
    save(dest, summary)
    print(json.dumps({
        "path": str(dest),
        "n_screen_passers": summary["n_screen_passers"],
        "failed_stage": summary["failed_stage"],
        "admitted_t1": summary["admitted_t1"],
        "admitted_t2": summary["admitted_t2"],
    }, indent=2))


def cmd_collect_freeze(args: argparse.Namespace) -> None:
    spec = load(Path(args.jobs))
    jobs = [(Path(row["out"]), load(Path(row["tasks"]))) for row in spec]
    summary = collect_freeze(jobs)
    dest = Path(args.summary)
    save(dest, summary)
    print(json.dumps({
        "path": str(dest),
        "screen_holds": summary["screen_holds"],
        "admitted_t1": summary["admitted_t1"],
        "admitted_t2": summary["admitted_t2"],
        "reflex_passed": summary["reflex"]["reflex_passed"],
        "perturbation_holds": summary["perturbation"]["holds"],
    }, indent=2))


def cmd_plan_t3e(args: argparse.Namespace) -> None:
    record = t3e_plan_record()
    dest = Path(args.out)
    save(dest, record)
    print(json.dumps({
        "path": str(dest),
        "n_jobs": record["n_jobs"],
        "launch": record["launch"],
        "list_usd": record["list_usd"],
        "engine_usd": record.get("engine_usd"),
        "brain_s": record["brain_s"],
        "include_hubs": record.get("include_hubs"),
        "reason": record.get("reason"),
    }, indent=2))


def cmd_plan_t3e_freeze(args: argparse.Namespace) -> None:
    record = t3e_freeze_plan_record()
    dest = Path(args.out)
    save(dest, record)
    print(json.dumps({
        "path": str(dest),
        "n_jobs": record["n_jobs"],
        "launch": record["launch"],
        "list_usd": record["list_usd"],
        "engine_usd": record.get("engine_usd"),
        "brain_s": record["brain_s"],
        "candidate_id": record.get("candidate_id"),
        "reason": record.get("reason"),
    }, indent=2))


def cmd_collect_t3e_freeze(args: argparse.Namespace) -> None:
    spec = load(Path(args.jobs))
    jobs = []
    for row in spec:
        out = Path(row["out"])
        tasks = load(Path(row["tasks"]))
        if args.skip_missing:
            tasks = [task for task in tasks if task_ndjson_path(out, task).exists()]
        jobs.append((out, tasks))
    weights = None
    if args.weights:
        weights = [float(part.strip()) for part in args.weights.split(",") if part.strip()]
    summary = collect_t3e_freeze(jobs, candidate_weights=weights)
    restriction = None
    if weights == [1.0]:
        restriction = (
            "item 120 weight 1.0; pair 1.0/1.2 mV; "
            "shared same-job bare, T0 feed-forward, and perturbation"
        )
    elif weights:
        restriction = f"candidate weights {weights}"
    summary["input"] = {
        "pulled": [str(Path(row["out"])) for row in spec],
        "n_tasks": summary["n_tasks"],
        "skip_missing": bool(args.skip_missing),
        "weights": args.weights,
        "restriction": restriction,
        "read_only": True,
    }
    dest = Path(args.summary)
    save(dest, summary)
    print(json.dumps({
        "path": str(dest),
        "ranked": summary["ranked"],
        "failed_stage": summary["failed_stage"],
        "partial": summary["partial"],
        "candidate_weights": summary["candidate_weights"],
        "admitted_t1": summary["admitted_t1"],
        "admitted_t2": summary["admitted_t2"],
    }, indent=2))


def t3e_job_payloads(plan: dict[str, Any], job_index: int, out: Path, identity: dict[str, Any]) -> list[dict[str, Any]]:
    if plan.get("stage") == "freeze":
        packed = t3e_freeze_wave_tasks(identity)
        fail = "T3e freeze wave is not launchable"
    else:
        packed = t3e_wave_tasks(identity, hubs=hubs_from_plan(plan))
        fail = "T3e wave is not launchable"
    if not packed["launch"]:
        raise ValueError(packed.get("reason") or fail)
    if job_index < 0 or job_index >= len(packed["jobs"]):
        raise ValueError(f"job-index {job_index} outside 0..{len(packed['jobs']) - 1}")
    plan_sha = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    tasks = []
    for i, task in enumerate(packed["jobs"][job_index]):
        brain = float(task["brain_s"])
        rate = float(task.get("pack_rate") or packed.get("pack_worker_s_per_brain_s") or WP27_PACK_RATE)
        worker_s = task_worker_s(brain, 1.0, worker_s_per_brain_s=rate)
        name = t3e_task_name(task, job_index, i)
        tasks.append({
            **task,
            "path": str(out / f"{name}.ndjson"),
            "identity": identity,
            "plan_sha256": plan_sha,
            "wall_cap_s": 2.0 * worker_s,
        })
    return tasks


def cmd_t3e(args: argparse.Namespace) -> None:
    plan = load(Path(args.plan))
    identity = rest.execution_identity(args.job_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = t3e_job_payloads(plan, args.job_index, out, identity)
    save(out / "tasks.json", tasks)
    pending = [task for task in tasks if not Path(task["path"]).exists()]
    execute_payloads(pending, args.workers, wave_worker if plan.get("stage") == "freeze" else t3e_worker)
    print(json.dumps({"tasks": len(tasks), "pending": len(pending)}, indent=2))


def cmd_collect_t3e(args: argparse.Namespace) -> None:
    spec = load(Path(args.jobs))
    jobs = [(Path(row["out"]), load(Path(row["tasks"]))) for row in spec]
    summary = collect_t3e(jobs)
    dest = Path(args.summary)
    save(dest, summary)
    print(json.dumps({
        "path": str(dest),
        "n_screen_passers": summary["n_screen_passers"],
        "failed_stage": summary["failed_stage"],
        "admitted_t1": summary["admitted_t1"],
        "admitted_t2": summary["admitted_t2"],
    }, indent=2))


def cmd_collect_t2(args: argparse.Namespace) -> None:
    spec = load(Path(args.jobs))
    jobs = [(Path(row["out"]), load(Path(row["tasks"]))) for row in spec]
    dt_ms = float(args.dt_ms) if getattr(args, "dt_ms", None) not in (None, "") else None
    summary = collect_t2(jobs, dt_ms=dt_ms)
    dest = Path(args.summary)
    save(dest, summary)
    print(json.dumps({
        "path": str(dest),
        "n_candidates": summary["n_candidates"],
        "n_reflex_passed": summary["n_reflex_passed"],
        "n_reflex_harmonised": summary["n_reflex_harmonised"],
        "n_long_passed": summary["n_long_passed"],
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="WP24 tier-3 Camber driver")
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--sub-tier", required=True, choices=("T3a", "T3b", "T3c", "T3d"))
    plan.add_argument("--rho", type=float, required=True)
    plan.add_argument("--out", required=True)
    plan.set_defaults(func=cmd_plan)
    diag_plan = sub.add_parser("plan-diag")
    diag_plan.add_argument("--out", required=True)
    diag_plan.set_defaults(func=cmd_plan_diag)
    freeze_plan = sub.add_parser("plan-freeze")
    freeze_plan.add_argument("--out", required=True)
    freeze_plan.set_defaults(func=cmd_plan_freeze)
    t0 = sub.add_parser("t0")
    t0.add_argument("--plan", required=True)
    t0.add_argument("--job-index", type=int, required=True)
    t0.add_argument("--out", required=True)
    t0.add_argument("--workers", required=True)
    t0.add_argument("--job-id", default=os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID"))
    t0.set_defaults(func=cmd_t0)
    collect = sub.add_parser("collect-t0")
    collect.add_argument("--tasks", required=True)
    collect.add_argument("--out", required=True)
    collect.add_argument("--summary")
    collect.set_defaults(func=cmd_collect)
    packed = sub.add_parser("collect-t0-packed")
    packed.add_argument("--jobs", required=True, help="JSON list of {out, tasks} in launch order")
    packed.add_argument("--summary", required=True)
    packed.set_defaults(func=cmd_collect_packed)
    t1 = sub.add_parser("t1")
    t1.add_argument("--plan", required=True)
    t1.add_argument("--job-index", type=int, required=True)
    t1.add_argument("--out", required=True)
    t1.add_argument("--workers", required=True)
    t1.add_argument("--job-id", default=os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID"))
    t1.set_defaults(func=cmd_t1)
    collect_t1_cmd = sub.add_parser("collect-t1")
    collect_t1_cmd.add_argument("--jobs", required=True, help="JSON list of {out, tasks} in launch order")
    collect_t1_cmd.add_argument("--summary", required=True)
    collect_t1_cmd.add_argument("--t0", help="T0 record JSON; T1 rows of T0 failures are not scored")
    collect_t1_cmd.add_argument("--dt-ms", dest="dt_ms", type=float, help="stiffness-cut dt_ms")
    collect_t1_cmd.set_defaults(func=cmd_collect_t1)
    t2 = sub.add_parser("t2")
    t2.add_argument("--plan", required=True)
    t2.add_argument("--job-index", type=int, required=True)
    t2.add_argument("--out", required=True)
    t2.add_argument("--workers", required=True)
    t2.add_argument("--job-id", default=os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID"))
    t2.set_defaults(func=cmd_t2)
    wave = sub.add_parser("wave")
    wave.add_argument("--plan", required=True)
    wave.add_argument("--job-index", type=int, required=True)
    wave.add_argument("--out", required=True)
    wave.add_argument("--workers", required=True)
    wave.add_argument("--job-id", default=os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID"))
    wave.set_defaults(func=cmd_wave)
    diag = sub.add_parser("diag")
    diag.add_argument("--plan", required=True)
    diag.add_argument("--job-index", type=int, required=True)
    diag.add_argument("--out", required=True)
    diag.add_argument("--workers", required=True)
    diag.add_argument("--job-id", default=os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID"))
    diag.set_defaults(func=cmd_diag)
    collect_t2_cmd = sub.add_parser("collect-t2")
    collect_t2_cmd.add_argument("--jobs", required=True, help="JSON list of {out, tasks} in launch order")
    collect_t2_cmd.add_argument("--summary", required=True)
    collect_t2_cmd.add_argument("--dt-ms", dest="dt_ms", type=float, help="stiffness-cut dt_ms")
    collect_t2_cmd.set_defaults(func=cmd_collect_t2)
    t3c_plan = sub.add_parser("t3c-dt-plan")
    t3c_plan.add_argument("--out", required=True)
    t3c_plan.add_argument("--t0", help="T0 record JSON; default rest-T3c-T0.json")
    t3c_plan.set_defaults(func=cmd_t3c_dt_plan)
    t3c_dt = sub.add_parser("t3c-dt")
    t3c_dt.add_argument("--plan", required=True)
    t3c_dt.add_argument("--out", required=True)
    t3c_dt.add_argument("--workers", required=True)
    t3c_dt.add_argument("--job-id", default=os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID"))
    t3c_dt.set_defaults(func=cmd_t3c_dt)
    collect_t3c = sub.add_parser("collect-t3c-dt")
    collect_t3c.add_argument("--tasks", required=True)
    collect_t3c.add_argument("--out", required=True)
    collect_t3c.add_argument("--summary")
    collect_t3c.set_defaults(func=cmd_collect_t3c_dt)
    t3c_t1_plan = sub.add_parser("t3c-t1-plan")
    t3c_t1_plan.add_argument("--out", required=True)
    t3c_t1_plan.add_argument("--t0", help="T0 record JSON; default rest-T3c-T0.json")
    t3c_t1_plan.set_defaults(func=cmd_t3c_t1_plan)
    t3c_t1 = sub.add_parser("t3c-t1")
    t3c_t1.add_argument("--plan", required=True)
    t3c_t1.add_argument("--out", required=True)
    t3c_t1.add_argument("--workers", required=True)
    t3c_t1.add_argument("--job-id", default=os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID"))
    t3c_t1.set_defaults(func=cmd_t3c_t1)
    collect_t3c_t1 = sub.add_parser("collect-t3c-t1")
    collect_t3c_t1.add_argument("--plan", required=True)
    collect_t3c_t1.add_argument("--out", required=True)
    collect_t3c_t1.add_argument("--tasks")
    collect_t3c_t1.add_argument("--summary")
    collect_t3c_t1.add_argument("--t2-summary")
    collect_t3c_t1.add_argument("--jobs", default="")
    collect_t3c_t1.add_argument("--decision")
    collect_t3c_t1.add_argument("--decision-in")
    collect_t3c_t1.set_defaults(func=cmd_collect_t3c_t1)
    collect_diag_cmd = sub.add_parser("collect-diag")
    collect_diag_cmd.add_argument("--jobs", required=True, help="JSON list of {out, tasks} in launch order")
    collect_diag_cmd.add_argument("--summary", required=True)
    collect_diag_cmd.set_defaults(func=cmd_collect_diag)
    collect_sigma_cmd = sub.add_parser("collect-sigma")
    collect_sigma_cmd.add_argument("--jobs", required=True, help="JSON list of {out, tasks} in launch order")
    collect_sigma_cmd.add_argument("--summary", required=True)
    collect_sigma_cmd.set_defaults(func=cmd_collect_sigma)
    collect_freeze_cmd = sub.add_parser("collect-freeze")
    collect_freeze_cmd.add_argument("--jobs", required=True, help="JSON list of {out, tasks} in launch order")
    collect_freeze_cmd.add_argument("--summary", required=True)
    collect_freeze_cmd.set_defaults(func=cmd_collect_freeze)
    t3e_plan = sub.add_parser("plan-t3e")
    t3e_plan.add_argument("--out", required=True)
    t3e_plan.set_defaults(func=cmd_plan_t3e)
    t3e = sub.add_parser("t3e")
    t3e.add_argument("--plan", required=True)
    t3e.add_argument("--job-index", type=int, required=True)
    t3e.add_argument("--out", required=True)
    t3e.add_argument("--workers", required=True)
    t3e.add_argument("--job-id", default=os.environ.get("CAMBER_JOB_ID") or os.environ.get("JOB_ID"))
    t3e.set_defaults(func=cmd_t3e)
    collect_t3e_cmd = sub.add_parser("collect-t3e")
    collect_t3e_cmd.add_argument("--jobs", required=True, help="JSON list of {out, tasks} in launch order")
    collect_t3e_cmd.add_argument("--summary", required=True)
    collect_t3e_cmd.set_defaults(func=cmd_collect_t3e)
    t3e_freeze_plan = sub.add_parser("plan-t3e-freeze")
    t3e_freeze_plan.add_argument("--out", required=True)
    t3e_freeze_plan.set_defaults(func=cmd_plan_t3e_freeze)
    collect_t3e_freeze_cmd = sub.add_parser("collect-t3e-freeze")
    collect_t3e_freeze_cmd.add_argument("--jobs", required=True, help="JSON list of {out, tasks} in launch order")
    collect_t3e_freeze_cmd.add_argument("--summary", required=True)
    collect_t3e_freeze_cmd.add_argument(
        "--weights",
        default=None,
        help="comma-separated candidate weights to score (default: 0.9,1.0,1.1)",
    )
    collect_t3e_freeze_cmd.add_argument(
        "--skip-missing",
        action="store_true",
        help="skip tasks whose ndjson is not on disk (partial collect)",
    )
    collect_t3e_freeze_cmd.set_defaults(func=cmd_collect_t3e_freeze)
    args = parser.parse_args()
    if args.cmd in ("t0", "t1", "t2", "wave", "diag", "t3c-dt", "t3c-t1", "t3e") and not args.job_id:
        raise SystemExit(f"{args.cmd} needs --job-id or CAMBER_JOB_ID")
    if args.cmd in ("t0", "t1", "t2", "wave", "diag", "t3c-dt", "t3c-t1", "t3e") and args.workers != "auto":
        args.workers = int(args.workers)
    args.func(args)


if __name__ == "__main__":
    main()
