"""Run every registered validation suite and write validation/status.json.

Suite discovery: imports every flyonenomics.validation submodule that
exposes SUITE (a mapping of test id to a zero-argument function
returning a ValidationEntry). Later work packages add suites without
editing this file. Binding comparison follows section 7.

Independent entries may run concurrently under the engine budget
(``--workers N|auto``). Default remains serial. Output classes, the
r9 exit rule, and status.json content match a serial run except
timing fields.

Units: none for the runner itself; suites state their own units.
Shapes: scalars only.
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import json
import multiprocessing as mp
import os
import pkgutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Callable

from flyonenomics.io import clear_log, flush, merge_logs, read_text, set_log_dir, set_repo_root

ROOT = Path(__file__).resolve().parents[1]
_SKIP = {
    "flyonenomics.validation.binding",
    "flyonenomics.validation.execute",
    "flyonenomics.validation.runner",
}
HOLDOUT_SPEND_IDS = frozenset({"4.3r", "4.3r-T"})


def today() -> str:
    """Return today's UTC date as YYYY-MM-DD.

    Units: none. Shapes: one string.
    """
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def discover_suites() -> dict[str, Callable[[], Any]]:
    """Import validation submodules and collect their SUITE entries.

    Units: none. Shapes: mapping of test id to callable.
    """
    import flyonenomics.validation as pkg

    found: dict[str, Callable[[], Any]] = {}
    for info in sorted(pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."), key=lambda item: item.name):
        if info.name in _SKIP:
            continue
        module = importlib.import_module(info.name)
        suite = getattr(module, "SUITE", None)
        if suite is not None:
            if not isinstance(suite, Mapping):
                raise TypeError(f"{info.name}.SUITE must be a mapping")
            for test_id, func in suite.items():
                if not isinstance(test_id, str) or not test_id or not callable(func):
                    raise TypeError(f"invalid suite registration in {info.name}: {test_id}")
                if test_id in found:
                    raise ValueError(f"duplicate suite test id: {test_id}")
                found[test_id] = func
    return found


def run_one_suite(test_id: str) -> dict[str, Any]:
    """Run one suite using this module's discover_suites and ROOT.

    Units: none. Shapes: a result or error mapping. Tests patch discover_suites
    on this module; look the name up at call time so the patch applies.
    Binding uses the same `bind_entry` as the parallel workers, so serial and
    parallel status agree.
    """
    from flyonenomics.validation.execute import bind_entry

    try:
        suites = discover_suites()
        if test_id not in suites:
            raise KeyError(f"unknown suite test id: {test_id}")
        entry = bind_entry(suites[test_id](), ROOT)
        if entry.test_id != test_id:
            raise ValueError(f"suite returned test id {entry.test_id}, expected {test_id}")
        return {"test_id": test_id, "entry": entry.model_dump(), "error": None}
    except Exception as exc:
        return {"test_id": test_id, "entry": None, "error": f"{type(exc).__name__}: {exc}"}


def _parse_workers(value: str) -> int | str:
    """Parse --workers N|auto. Units: workers. Shapes: scalar."""
    if value == "auto":
        return "auto"
    count = int(value)
    if count < 1:
        raise argparse.ArgumentTypeError("workers must be a positive integer or auto")
    return count


def _write_status(status: dict[str, Any], dest: Path) -> None:
    """Atomically write status.json. Units: none. Shapes: one mapping."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=dest.parent, delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(json.dumps(status, indent=2) + "\n")
        tmp.replace(dest)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def _previous_status(dest: Path) -> dict[str, Any]:
    """Load the prior status.json mapping, or an empty one. Units: none."""
    if not dest.is_file():
        return {}
    try:
        payload = json.loads(read_text(dest))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _previous_results(dest: Path) -> dict[str, dict[str, Any]]:
    """Load prior status.json results keyed by test id. Units: none."""
    rows = _previous_status(dest).get("results", [])
    return {row["test_id"]: row for row in rows if isinstance(row, dict) and "test_id" in row}


def _previous_one_use_attempts(dest: Path) -> dict[str, dict[str, str]]:
    """Recorded one-use executions that ended in an error. Units: none.

    A crashed holdout may already have read holdout data, so its attempt
    counts as an execution for the one-use rule.
    """
    rows = _previous_status(dest).get("one_use_attempts", [])
    return {row["test_id"]: row for row in rows if isinstance(row, dict) and "test_id" in row}


def check_holdout_ready(entry_id: str, repo: Path | None = None) -> tuple[bool, str]:
    """Run scripts/holdout_ready.py at HEAD. Units: none. Shapes: (ok, text)."""
    root = ROOT if repo is None else Path(repo)
    script = root / "scripts" / "holdout_ready.py"
    if not script.is_file():
        return False, "holdout_ready.py missing"
    proc = subprocess.run(
        [sys.executable, str(script), entry_id],
        cwd=str(root), capture_output=True, text=True, timeout=120,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, text


def _layer_flags(block: dict[str, Any]) -> Any:
    """Rebuild LayerFlags from a stored identity. Units: none."""
    from flyonenomics.types import LayerFlags

    flags = block.get("layer_flags") or {}
    known = {name: flags[name] for name in LayerFlags.__dataclass_fields__ if name in flags}
    return LayerFlags(**known)


def _rebind_carried(row: dict[str, Any], root: Path) -> dict[str, Any]:
    """Recompute validity of a carried one-use record. Units: none."""
    from flyonenomics.validation.binding import ValidationEntry, build_identity, is_compatible

    entry = ValidationEntry.model_validate(row)
    current = build_identity(
        root, connectome_version=entry.identity.connectome_version,
        layers=_layer_flags(entry.identity.model_dump()), assay=entry.identity.assay,
        fixture=entry.fixture_path, protocol_hash=entry.identity.protocol_hash,
        run_code_hash=entry.identity.run_code_hash,
    )
    valid, reason = is_compatible(entry, current, repo=root)
    # The recorded outcome is never overwritten: validity is stored beside it,
    # so a later tree where the record is valid again still has its outcome.
    measured = {**entry.measured, "one_use_carried": True, "binding": "valid" if valid else "stale"}
    if not valid:
        measured["binding_reason"] = reason
    else:
        measured.pop("binding_reason", None)
    return entry.model_copy(update={"measured": measured}).model_dump()


def _attach_log(entry_payload: dict[str, Any], dest: Path, root: Path) -> dict[str, Any]:
    """Merge worker logs into a P2 entry that declared inputs. Units: none."""
    from flyonenomics.validation.binding import ValidationEntry, apply_logged_inputs

    entry = ValidationEntry.model_validate(entry_payload)
    if not entry.declared_inputs:
        return entry.model_dump()
    logs = list(dest.glob("deps-*.json")) if dest.is_dir() else []
    logged = merge_logs(dest) if logs else []
    updated = apply_logged_inputs(entry, logged, root, log_present=bool(logs))
    return updated.model_dump()


def _holdout_allowed(test_id: str, holdout: str | None, previous: Mapping[str, dict[str, Any]]) -> tuple[bool, str]:
    """Return whether a one-use entry may execute. Units: none."""
    if holdout is None or test_id != holdout:
        return False, "one-use entries execute only under --holdout"
    if test_id == "4.3r-replay":
        if not any(name in previous for name in HOLDOUT_SPEND_IDS):
            return False, "4.3r-replay requires an existing 4.3r or 4.3r-T execution"
        if test_id in previous:
            return False, "earlier execution of 4.3r-replay is already recorded"
        return True, "replay"
    if test_id in previous:
        return False, f"earlier execution of {test_id} is already recorded"
    if test_id in HOLDOUT_SPEND_IDS:
        spent = sorted(name for name in HOLDOUT_SPEND_IDS if name in previous)
        if spent:
            return False, f"the holdout is spent: earlier execution of {spent[0]} is recorded"
    ok, text = check_holdout_ready(test_id)
    if not ok:
        return False, text or "holdout_ready.py failed"
    return True, "ready"


def run_all(
    output: str | Path | None = None,
    workers: int | str | None = 1,
    ids: list[str] | None = None,
    only: list[str] | None = None,
    holdout: str | None = None,
) -> dict[str, Any]:
    """Run discovered suites and write validation/status.json.

    Units: none. Shapes: scalars only. Returns the status mapping.
    workers 1 (the default) is serial. N or auto runs independent
    entries concurrently under the engine budget. --only and --ids
    select the same id list. one-use entries are carried forward
    unless --holdout names them.
    """
    from flyonenomics.orchestrator.budget import lease_workers
    from flyonenomics.validation.binding import code_content_hash, logged_suite, repo_commit, sha256_file

    selected = only if only is not None else ids
    dest = Path(output) if output is not None else ROOT / "validation" / "status.json"
    previous = _previous_results(dest)
    attempts = _previous_one_use_attempts(dest)
    # Error-ended one-use executions count as executions.
    spent_view = {**{name: row for name, row in attempts.items()}, **previous}
    suites = discover_suites()
    if selected is not None:
        missing = [test_id for test_id in selected if test_id not in suites]
        if missing:
            raise KeyError("unknown suite test id: " + ", ".join(missing))
        suites = {test_id: suites[test_id] for test_id in selected}
    test_ids = sorted(suites)
    execute_ids: list[str] = []
    collected: dict[str, dict[str, Any]] = {}
    for test_id in test_ids:
        func = suites[test_id]
        one_use = bool(getattr(func, "one_use", False) or (previous.get(test_id) or {}).get("one_use")
                       or test_id in attempts)
        if one_use:
            allowed, reason = _holdout_allowed(test_id, holdout, spent_view)
            if not allowed:
                if test_id in previous:
                    collected[test_id] = {
                        "test_id": test_id, "entry": _rebind_carried(previous[test_id], ROOT), "error": None,
                    }
                    print(f"{test_id}: carried ({reason})", flush=True)
                else:
                    collected[test_id] = {
                        "test_id": test_id, "entry": None,
                        "error": f"one-use entry {test_id} was not executed: {reason}",
                    }
                    print(f"{test_id}: error {collected[test_id]['error']}", flush=True)
                continue
        execute_ids.append(test_id)

    n_jobs = max(len(execute_ids), 1)
    requested = 1 if workers is None else workers
    lease = None if requested == 1 or len(execute_ids) <= 1 else lease_workers(requested, n_jobs=n_jobs)
    count = 1 if lease is None else lease.count
    set_repo_root(ROOT)
    with tempfile.TemporaryDirectory(prefix="validation-deps-") as raw_deps:
        deps_root = Path(raw_deps)
        os.environ["FLYONENOMICS_DEPS_ROOT"] = str(deps_root)
        if count <= 1:
            if lease is not None:
                lease.release()
            for test_id in execute_ids:
                entry_dir = deps_root / test_id
                entry_dir.mkdir(parents=True, exist_ok=True)
                set_log_dir(entry_dir)
                os.environ["FLYONENOMICS_DEPS_DIR"] = str(entry_dir)
                clear_log()
                collected[test_id] = run_one_suite(test_id)
                # The suite ran in this process: write its own log beside any worker logs.
                flush(entry_dir)
                row = collected[test_id]
                if row["error"] is None:
                    row["entry"] = _attach_log(row["entry"], entry_dir, ROOT)
                    print(f"{test_id}: {row['entry']['outcome']} ({row['entry']['compatibility']})", flush=True)
                else:
                    print(f"{test_id}: error {row['error']}", flush=True)
        else:
            assert lease is not None
            try:
                ctx = mp.get_context("spawn")
                with ProcessPoolExecutor(max_workers=count, mp_context=ctx) as pool:
                    for test_id, row in zip(execute_ids, pool.map(logged_suite, execute_ids)):
                        collected[test_id] = row
                        if row["error"] is None:
                            row["entry"] = _attach_log(row["entry"], deps_root / test_id, ROOT)
                            print(f"{test_id}: {row['entry']['outcome']} ({row['entry']['compatibility']})", flush=True)
                        else:
                            print(f"{test_id}: error {row['error']}", flush=True)
            finally:
                lease.release()
        set_log_dir(None)
        os.environ.pop("FLYONENOMICS_DEPS_DIR", None)
        os.environ.pop("FLYONENOMICS_DEPS_ROOT", None)

    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for test_id in test_ids:
        row = collected[test_id]
        if row["error"] is not None:
            errors.append({"test_id": test_id, "error": row["error"]})
        else:
            results.append(row["entry"])
    # The one-use ledger survives partial runs: records and error-ended attempts
    # of one-use entries outside the selection are carried as they were.
    written = {row["test_id"] for row in results}
    for test_id, row in previous.items():
        if row.get("one_use") and test_id not in written:
            results.append(row)
            written.add(test_id)
    one_use_attempts = [row for name, row in sorted(attempts.items()) if name not in written]
    for test_id in execute_ids:
        row = collected[test_id]
        func = suites[test_id]
        if row["error"] is not None and getattr(func, "one_use", False):
            one_use_attempts.append({"test_id": test_id, "error": row["error"]})

    uv_lock = ROOT / "uv.lock"
    prov = ROOT / "data" / "provenance.json"
    status = {
        "date": today(),
        "code_commit": repo_commit(ROOT),
        "code_hash": code_content_hash(ROOT),
        "uv_lock_hash": sha256_file(uv_lock) if uv_lock.exists() else "missing",
        "provenance_hash": sha256_file(prov) if prov.exists() else "missing",
        "results": results,
        "errors": errors,
        "one_use_attempts": one_use_attempts,
        "coverage": "registered suites only" if suites else "no suites registered",
    }
    _write_status(status, dest)
    print(f"suites run: {len(suites)}; infrastructure errors: {len(errors)}")
    print(f"status: {dest}")
    return status


def main() -> None:
    """Entry point used by tests: run_all with defaults, then the r9 exit rule.

    Units: none. Shapes: scalars only. CLI flags are parsed only when this
    file is the process entry point, so pytest's argv is not interpreted.
    """
    status = run_all()
    if status["errors"] or any(
        entry["compatibility"] != "development" and entry["outcome"] in ("failed", "stale", "unqualified")
        for entry in status["results"]
    ):
        raise SystemExit(1)


def _cli(argv: list[str] | None = None) -> None:
    """Parse --workers/--only/--ids/--holdout/--output and apply the r9 exit rule."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=_parse_workers, default=1,
                        help="independent entries in parallel under the engine budget; auto asks the budget")
    parser.add_argument("--only", help="comma-separated test ids (default: every registered suite)")
    parser.add_argument("--ids", help="alias of --only, kept for existing tests")
    parser.add_argument("--holdout", help="execute this one-use entry when holdout_ready.py passes")
    parser.add_argument("--output", type=Path, help="status.json path (default: validation/status.json)")
    args = parser.parse_args(argv)
    only = [item.strip() for item in args.only.split(",") if item.strip()] if args.only else None
    ids = [item.strip() for item in args.ids.split(",") if item.strip()] if args.ids else None
    status = run_all(output=args.output, workers=args.workers, ids=ids, only=only, holdout=args.holdout)
    if status["errors"] or any(
        entry["compatibility"] != "development" and entry["outcome"] in ("failed", "stale", "unqualified")
        for entry in status["results"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    _cli()
