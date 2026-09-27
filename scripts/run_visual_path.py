"""Run WP18 through orchestrator.run, keeping run trees and execution identities.

Oracle: FLYONENOMICS_CACHE_DIR=~/flyo-cache uv run python scripts/run_visual_path.py \
    --protocol vcal --workers 12 --out camber-runs/wp18/vcal
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing as mp
import os
from pathlib import Path
import time
from typing import Any

from flyonenomics.behaviour import visual_run as vr
from flyonenomics.io import read_json
from flyonenomics.store.results import atomic_json


def experiment_for(protocol: str, rate: float, seeds: tuple[int, ...], *, frozen: bool = False) -> Any:
    """Resolve one declared rate to an executable, pinned open-loop fixture."""
    from flyonenomics.schema.experiment import Experiment

    source = vr.V3_FIXTURE if protocol == "v3" else vr.V1_FIXTURE
    raw = read_json(vr.REPO / source)
    raw["seeds"] = list(seeds)
    raw["name"] = f"wp18-{protocol}-{rate:g}" + ("-frozen" if frozen else "-grid")
    raw["meta"]["visual_path_protocol"] = protocol
    raw["meta"]["source_fixture"] = source
    raw["meta"]["settle_rule"] = "SPEC-P2 3.4: fixed 2 s ambient"
    if frozen:
        raw["substrate"]["visual_version"] = "v0.2"
    else:
        raw["substrate"]["visual_version"] = None
        raw["meta"].update({"encoder_grid": True, "r_light": rate,
                             "grid": {"r_light": list(vr.V_CAL_STAGE1_HZ + vr.V_CAL_STAGE2_HZ)}})
    for arm in raw["arms"]:
        for phase in arm["protocol"]:
            phase["params"]["inject_at"] = "photoreceptors"
    # The chunk observer records all stages, including those not in the old
    # fixture's spike subset. Keep the raw spike evidence complete as well.
    if protocol == "v1":
        raw["record"]["spikes"] = list(vr.V1_POPULATIONS)
    return Experiment.model_validate(raw)


def _execute(job: tuple) -> dict:
    """One orchestrator run per rate; spawned engine workers share its build."""
    protocol, rate, seeds, workers, destination, frozen = job
    from flyonenomics import io
    from flyonenomics.orchestrator import run
    from flyonenomics.store import ResultsStore
    from flyonenomics.validation.binding import input_blobs, sha256_file

    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    deps = destination / "deps"
    os.environ["FLYONENOMICS_DEPS_DIR"] = str(deps)
    io.set_log_dir(deps)
    io.clear_log()
    exp = experiment_for(protocol, rate, seeds, frozen=frozen)
    store = ResultsStore(destination / "runs")
    began = time.monotonic()
    run_id = run(exp, store, n_workers=workers)
    directory = store.run_path(run_id)
    manifest = read_json(directory / "manifest.json")
    if manifest["state"] != "done":
        raise RuntimeError(f"incomplete visual execution: {directory}")
    io.flush()
    inputs = input_blobs(vr.REPO, sorted(set(vr.DECLARED_INPUTS) | set(io.merge_logs(deps))))
    source_fixture = vr.V3_FIXTURE if protocol == "v3" else vr.V1_FIXTURE
    source_fixture_sha256 = sha256_file(vr.REPO / source_fixture)
    identity = {**manifest["identity"], "inputs": inputs,
                "fixture_hash": source_fixture_sha256}
    # The identity comes from the actual orchestrator run, never a new Mac build.
    # fixture_hash binds the tracked fixture; protocol_hash and experiment_sha256
    # bind the resolved per-rate experiment that actually ran.
    rows = []
    for seed in seeds:
        metrics = read_json(directory / f"arm-wild-type/seed-{seed}/metrics.json")
        row = metrics["probes"]["0"]["visual_path"]
        row.update({"protocol": protocol, "r_light_hz": rate,
                    "run_path": str(directory.relative_to(vr.REPO))})
        rows.append(row)
    record = {"protocol": protocol, "r_light_hz": rate, "rows": rows,
              "identity": identity, "run_path": str(directory.relative_to(vr.REPO)),
              "experiment_sha256": sha256_file(directory / "experiment.json"),
              "manifest_sha256": sha256_file(directory / "manifest.json"),
              "source_fixture": source_fixture,
              "source_fixture_sha256": source_fixture_sha256,
              "wall_s": time.monotonic() - began,
              "brain_s": len(seeds) * (12 if protocol == "v3" else 18),
              "frozen": frozen}
    atomic_json(destination / "execution.json", record)
    print(f"{protocol} {rate:g} Hz complete ({len(seeds)} seeds)", flush=True)
    return record


def _wave(protocol: str, rates: list | tuple, seeds: tuple, workers: int, out: Path,
          *, frozen: bool = False) -> list[dict]:
    if not rates:
        return []
    parallel = min(len(rates), max(1, workers // len(seeds)))
    per_run = min(len(seeds), max(1, workers // parallel))
    jobs = [(protocol, float(rate), seeds, per_run, str(out / f"{protocol}-{rate:g}"), frozen) for rate in rates]
    with ProcessPoolExecutor(max_workers=parallel, mp_context=mp.get_context("spawn")) as pool:
        return list(pool.map(_execute, jobs))


def _evidence(execution: dict) -> dict:
    return {k: v for k, v in execution.items() if k != "rows"}


def _record_execution(record: dict, execution: dict) -> dict:
    record.update({"identity": execution["identity"], "execution": _evidence(execution),
                   "compatibility": "matching-layers" if execution["frozen"] else "development",
                   "qualification_note": "Grid screens are not post-freeze V entries"})
    return record


def run_vcal(out: Path, workers: int, rates=vr.V_CAL_STAGE1_HZ, extension=vr.V_CAL_STAGE2_HZ) -> dict:
    began = time.monotonic()
    v3_runs = _wave("v3", rates, vr.V3_SEEDS, workers, out / "stage1")
    v3 = {e["r_light_hz"]: vr.v3_passed(e["rows"]) for e in v3_runs}
    v1_runs = _wave("v1", [r for r in rates if v3[r]["passed"]], vr.V1_THREE_SEEDS, workers, out / "stage1")
    stage2_ran = vr.vcal_stage2_needed({r: v3[r]["passed"] for r in rates}, rates)
    if stage2_ran:
        ext = _wave("v3", extension, vr.V3_SEEDS, workers, out / "stage2")
        v3_runs += ext
        v3.update({e["r_light_hz"]: vr.v3_passed(e["rows"]) for e in ext})
        v1_runs += _wave("v1", [r for r in extension if v3[r]["passed"]], vr.V1_THREE_SEEDS, workers, out / "stage2")
    v1 = {e["r_light_hz"]: vr.v1_passed(e["rows"]) for e in v1_runs}
    all_rates = list(rates) + (list(extension) if stage2_ran else [])
    outcomes = [{"rate_hz": r, "v3": v3[r], "v1": v1.get(r, {"passed": False, "reason": "V3 failed; V1 not run"})} for r in all_rates]
    candidate = vr.vcal_candidate(all_rates, v3, v1)
    selected, ten_seed = None, None
    ten_runs = []
    if candidate is not None:
        ten_runs = _wave("v1", [candidate], vr.V1_SEEDS, workers, out / "selection")
        ten_seed = vr.v1_passed(ten_runs[0]["rows"])
        if ten_seed["passed"]:
            selected = candidate
    failed_rate = None if selected is not None else vr.vcal_v1_failed_rate(outcomes)
    # With no V3 pass, still record a real failed V3 rather than leaving old bytes.
    recorded_rate = selected if selected is not None else (failed_rate if failed_rate is not None else min(all_rates))
    executions = v3_runs + v1_runs + ten_runs
    from flyonenomics.drive.mechanisms import substrate_id_for
    summary = {
        "item": 122, "protocol": "vcal", "substrate_id": substrate_id_for(vr.DRIVE_PATH),
        "stage1_hz": list(rates), "stage2_hz": list(extension), "stage2_ran": stage2_ran,
        "outcomes": outcomes, "candidate_r_light_hz": candidate, "selected_r_light_hz": selected,
        "recorded_rate_hz": recorded_rate, "v1_failed_rate_hz": failed_rate, "ten_seed_v1": ten_seed,
        "v1_screen": "ten_seed_selection" if selected is not None else "vcal_three_seed",
        "executions": [_evidence(e) for e in executions], "wall_s": time.monotonic() - began,
        "brain_s": sum(e["brain_s"] for e in executions),
        "compatibility": "development", "qualification_note": "V-cal grid screens are not post-freeze matching-layers entries",
        "section_3_7": None if selected is not None else "No selection; item 126 sends the declared substrate to TuBu (section 3.7 step 2)",
    }
    selected_v3 = next(e for e in v3_runs if e["r_light_hz"] == recorded_rate)
    vr.write_record(vr.V3_RECORD, _record_execution(vr.record_v3(selected_v3["rows"], r_light=recorded_rate), selected_v3))
    selected_v1 = ten_runs[0] if selected is not None else next((e for e in v1_runs if e["r_light_hz"] == failed_rate), None)
    if selected_v1 is not None:
        # A failed ten-seed selection remains fully recorded in executions and ten_seed_v1;
        # it can never be turned into a selected configuration by the three-seed screen.
        v1_record = _record_execution(vr.record_v1(
            selected_v1["rows"], r_light=selected_v1["r_light_hz"],
            screen="ten_seed_selection" if selected is not None else "vcal_three_seed"), selected_v1)
        if selected is None:
            v1_record.update({"screen_passed": v1_record["passed"], "passed": False,
                              "status": "failed", "reason": "V-cal made no selection"})
        vr.write_record(vr.V1_RECORD, v1_record)
    else:
        vr.write_record(vr.V1_RECORD, {"status": "unavailable", "passed": False,
            "reason": "No V3-passing rate; V1 not executed", "screen": "not_run"})
    # V-cal is a multi-execution record, not an invented single execution.
    record = vr.record_vcal(summary, identity=executions[0]["identity"])
    record["identity_role"] = "first constituent execution; all rate identities are in executions"
    digest = vr.write_record(vr.VCAL_RECORD, record)
    from flyonenomics.behaviour.visual_calibration import r3_record

    cells = {str(float(o["rate_hz"])): {"v3": o["v3"], "v1_three_seed": o["v1"]} for o in outcomes}
    r3 = r3_record(cells)
    r3["executions"] = [_evidence(e) for e in v3_runs + v1_runs]
    vr.write_record(vr.REPO / "validation/records/p2/R3.json", r3)
    if selected is not None:
        import yaml
        vr.VISUAL_PATH.write_text(yaml.safe_dump(vr.visual_document(selected, vr.load_params(vr.PARAMS_PATH), digest), sort_keys=False))
        summary["next"] = "Commit visual bytes, then rerun --protocol v1 and v3 --frozen"
    atomic_json(out / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "executions"}), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", choices=("v1", "v3", "vcal"), required=True)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rate", type=float, default=50.0)
    parser.add_argument("--frozen", action="store_true", help="Execute against committed visual-v0.2.yaml")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("workers must be positive")
    args.out.mkdir(parents=True, exist_ok=True)
    if args.protocol == "vcal":
        run_vcal(args.out, args.workers)
        return
    rate = args.rate
    if args.frozen:
        from flyonenomics.io import read_yaml
        rate = float(read_yaml(vr.VISUAL_PATH)["r_light"])
    execution = _wave(args.protocol, [rate], vr.V3_SEEDS if args.protocol == "v3" else vr.V1_SEEDS,
                      args.workers, args.out, frozen=args.frozen)[0]
    record = (vr.record_v3(execution["rows"], r_light=rate) if args.protocol == "v3" else
              vr.record_v1(execution["rows"], r_light=rate, screen="ten_seed"))
    vr.write_record(vr.V3_RECORD if args.protocol == "v3" else vr.V1_RECORD, _record_execution(record, execution))
    atomic_json(args.out / "summary.json", execution)


if __name__ == "__main__":
    main()
