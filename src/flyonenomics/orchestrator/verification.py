"""Shared real-engine replay checks for pytest and the validation runner."""
from __future__ import annotations
import itertools
import os
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from flyonenomics.io import read_parquet
from flyonenomics.schema import Experiment, load_experiment
from flyonenomics.orchestrator import run
from flyonenomics.store import ResultsStore
from flyonenomics.store.results import read_json, atomic_json
from flyonenomics.validation.binding import repo_commit, sha256_file

REPO = Path(__file__).resolve().parents[3]
INVARIANCE_FIXTURE = "tests/fixtures/experiments/invariance.json"
INVARIANCE_WORKERS = (1, 2)
ARENA_RESET_KEYS = ("x", "y", "h", "omega", "r_L", "r_R")
BEHAVIOUR_ASSAYS = frozenset({"buridan", "open_loop_steering"})
# These two modules execute/check verification procedures; neither is imported
# by a simulation worker. Their recorded hashes remain in the audit, but a
# reporting-only edit need not rerun the scientific eight-case fixture.
VERIFICATION_DRIVERS = frozenset({
    "src/flyonenomics/orchestrator/verification.py",
    "src/flyonenomics/validation/level0.py",
})


def compare_runs(left: Path, right: Path, *, metrics: bool = True) -> int:
    """Assert exact parquet values and optional metrics; ticks/Hz/µM, tables (r,c)."""
    left_files = {p.relative_to(left) for p in left.rglob("*.parquet")}
    right_files = {p.relative_to(right) for p in right.rglob("*.parquet")}
    if left_files != right_files:
        raise AssertionError(f"table file sets differ: {left_files ^ right_files}")
    for name in sorted(left_files):
        pd.testing.assert_frame_equal(read_parquet(left / name).to_pandas(), read_parquet(right / name).to_pandas(), check_exact=True)
    if metrics:
        left_metrics = {p.relative_to(left) for p in left.rglob("metrics.json")}
        right_metrics = {p.relative_to(right) for p in right.rglob("metrics.json")}
        if left_metrics != right_metrics:
            raise AssertionError("metric file sets differ")
        for name in left_metrics:
            if read_json(left / name) != read_json(right / name):
                raise AssertionError(f"metrics differ: {name}")
    return len(left_files)


def _probe_assays(experiment: dict[str, Any]) -> set[str]:
    """Collect probe assays from a dumped experiment; names, one set."""
    return {phase["assay"] for arm in experiment["arms"] for phase in arm["protocol"]
            if phase.get("type") == "probe"}


def _assert_arena_reset(manifest: dict[str, Any], experiment: dict[str, Any]) -> None:
    """Require a behaviour probe and reset kinematics at recording tick 0; mm/deg/Hz."""
    if not BEHAVIOUR_ASSAYS & _probe_assays(experiment):
        raise AssertionError("0.8 fixture has no behaviour probe")
    for probe in manifest["probe_offsets"]:
        state = probe["arena_at_recording_start"]
        if any(key not in state or state[key] != 0 for key in ARENA_RESET_KEYS):
            raise AssertionError("arena did not reset at recording tick zero")


def check_invariance(root: Path) -> dict[str, Any]:
    """Run all 8 order/worker/live combinations; seconds, exact tables and reset states."""
    fixture = read_json(REPO / INVARIANCE_FIXTURE)
    store = ResultsStore(root)
    baseline: Path | None = None
    runs = []
    table_count = 0
    for reverse, workers, live in itertools.product((False, True), INVARIANCE_WORKERS, (False, True)):
        experiment = Experiment.model_validate(fixture["experiment"])
        if reverse:
            experiment.arms.reverse()
        experiment.record.live = live
        run_id = run(experiment, store, workers, fixture_settle_s={int(k): v for k, v in fixture["settle_s"].items()})
        path = store.run_path(run_id)
        errors = store.validate_run(run_id)
        if errors:
            raise AssertionError(errors)
        manifest = read_json(path / "manifest.json")
        saved = read_json(path / "experiment.json")
        _assert_arena_reset(manifest, saved)
        durations = {probe["settle_s"] for probe in manifest["probe_offsets"]}
        if durations != set(fixture["settle_s"].values()):
            raise AssertionError("fixture settle durations were not exercised")
        if baseline is None:
            baseline = path
        else:
            table_count = compare_runs(baseline, path)
        runs.append({"run_id": run_id, "reverse": reverse, "workers": workers, "live": live,
                     "stubs": list(manifest["stubs"])})
    measured = {"runs": runs, "tables_per_run": table_count, "all_tables_and_metrics_identical": True,
                "arena_reset": True, "settle_s": fixture["settle_s"]}
    evidence = os.environ.get("FLYONENOMICS_INVARIANCE_EVIDENCE")
    if evidence:
        atomic_json(evidence, {"identity": _invariance_identity(), "root": str(root.resolve()), "measured": measured})
    return measured


def _invariance_identity() -> dict[str, Any]:
    """Fingerprint the code, lock and inputs of an invariance execution; no scientific units."""
    files = [REPO / "uv.lock", REPO / "data/provenance.json", REPO / INVARIANCE_FIXTURE,
             *sorted((REPO / "data").glob("*.yaml")), *sorted((REPO / "src").rglob("*.py"))]
    return {"code_commit": repo_commit(REPO),
            "hashes": {str(p.relative_to(REPO)): sha256_file(p) for p in files}}


def compare_invariance_identity(recorded: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Require identical model/data/fixture bytes; disclose verification-driver and commit changes."""
    old = {key: value for key, value in recorded["hashes"].items() if key not in VERIFICATION_DRIVERS}
    new = {key: value for key, value in current["hashes"].items() if key not in VERIFICATION_DRIVERS}
    if old != new:
        raise ValueError("invariance evidence model or input identity changed")
    changed = {key: {"recorded": recorded["hashes"].get(key), "current": current["hashes"].get(key)}
               for key in sorted(VERIFICATION_DRIVERS)
               if recorded["hashes"].get(key) != current["hashes"].get(key)}
    return {"model_and_input_hashes_equal": True, "verification_driver_changes": changed,
            "recorded_code_commit": recorded["code_commit"], "analysis_code_commit": current["code_commit"]}


def replay_invariance_evidence(path: Path) -> dict[str, Any]:
    """Recheck saved current-code eight-way evidence without rerunning networks; table units unchanged."""
    evidence = read_json(path)
    identity_check = compare_invariance_identity(evidence["identity"], _invariance_identity())
    measured = evidence["measured"]
    fixture = read_json(REPO / INVARIANCE_FIXTURE)
    expected = set(itertools.product((False, True), INVARIANCE_WORKERS, (False, True)))
    cases = {(r["reverse"], r["workers"], r["live"]) for r in measured["runs"]}
    if len(measured["runs"]) != 8 or cases != expected:
        raise ValueError("invariance evidence must contain all eight cases")
    root = Path(evidence["root"])
    baseline = root / measured["runs"][0]["run_id"]
    store = ResultsStore(root)
    replayed_runs = []
    for row in measured["runs"]:
        run = root / row["run_id"]
        if store.validate_run(row["run_id"]):
            raise ValueError("invalid saved invariance run")
        saved = read_json(run / "experiment.json")
        expected_exp = Experiment.model_validate(fixture["experiment"])
        if row["reverse"]:
            expected_exp.arms.reverse()
        expected_exp.record.live = row["live"]
        saved.get("meta", {}).pop("_resolved_populations", None)
        if saved != expected_exp.model_dump(mode="json"):
            raise ValueError("invariance evidence protocol changed")
        manifest = read_json(run / "manifest.json")
        _assert_arena_reset(manifest, saved)
        if set(p["settle_s"] for p in manifest["probe_offsets"]) != set(fixture["settle_s"].values()):
            raise ValueError("invariance reset evidence changed")
        compare_runs(baseline, run)
        # 0.8's class reads the executed manifests, never the evidence file's own claim.
        replayed_runs.append({**row, "stubs": list(manifest["stubs"])})
    return {**measured, "runs": replayed_runs, "replayed_from": str(path),
            "recorded_code_commit": evidence["identity"]["code_commit"], "identity_check": identity_check}


def check_replay(root: Path, n_workers: int = 2) -> dict[str, Any]:
    """Replay both production files twice; seconds/Hz, exact tables, worker count scalar."""
    store = ResultsStore(root)
    results = {}
    for name in ("sugar-reflex", "spontaneous"):
        experiment = load_experiment(REPO / "data/experiments" / f"{name}.json")
        experiment.seeds = experiment.seeds[:1]
        paths = []
        for _ in range(2):
            run_id = run(experiment, store, n_workers)
            errors = store.validate_run(run_id)
            if errors:
                raise AssertionError(errors)
            paths.append(store.run_path(run_id))
        results[name] = {"protocol_hash": read_json(paths[0] / "manifest.json")["protocol_hash"],
                         "n_workers": n_workers, "run_ids": [p.name for p in paths],
                         "identical_tables": compare_runs(*paths), "identical_metrics": True}
    return results
