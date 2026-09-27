"""Run a validated experiment or request cooperative cancellation (gate I1)."""
from __future__ import annotations
import argparse
import os
import subprocess
from pathlib import Path
from flyonenomics.schema import load_experiment
from flyonenomics.orchestrator import run
from flyonenomics.store import ResultsStore
from flyonenomics.store.results import read_json

CAFFEINATE_ARGS = ("caffeinate", "-ims")
CAFFEINATE_STOP_TIMEOUT_S = 5.0


def is_acceptance_experiment(path: Path) -> bool:
    """True for the section 1.3 acceptance files; filename prefix, no JSON parse."""
    return path.name.startswith("acceptance-")


def resolve_caffeinate(path: Path, flag: bool | None) -> bool:
    """Default caffeinate on for acceptance experiments; an explicit flag wins."""
    return is_acceptance_experiment(path) if flag is None else flag


def hold_caffeinate(pid: int | None = None) -> subprocess.Popen[bytes]:
    """Hold caffeinate -ims for the run's life; pid scalar.

    `-w pid` makes caffeinate exit with this process even when it is killed
    without running `finally` (SIGKILL, SIGTERM), so no assertion is orphaned.
    """
    return subprocess.Popen((*CAFFEINATE_ARGS, "-w", str(os.getpid() if pid is None else pid)))


def release_caffeinate(holder: subprocess.Popen[bytes]) -> None:
    """Stop a caffeinate holder; seconds timeout, never raises over the run's own error."""
    holder.terminate()
    try:
        holder.wait(timeout=CAFFEINATE_STOP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        holder.kill()
        holder.wait()


def _parse_workers(value: str) -> int | str:
    """Parse --workers N|auto. Units: workers. Shapes: scalar."""
    if value == "auto":
        return "auto"
    count = int(value)
    if count < 1:
        raise argparse.ArgumentTypeError("workers must be a positive integer or auto")
    return count


def main() -> None:
    """CLI entry; worker count dimensionless, durations from JSON in seconds/hours."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", nargs="?", type=Path)
    parser.add_argument("--workers", type=_parse_workers, default=None,
                        help="engine workers (default: Params orchestrator.n_workers); auto asks the machine budget")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument("--cancel", metavar="RUN_ID")
    parser.add_argument("--run-id", default=None, help="preassigned run id (WP7 tool server); runner insert stays idempotent")
    parser.add_argument("--caffeinate", action=argparse.BooleanOptionalAction, default=None,
                        help="hold caffeinate -ims for the run (default on for acceptance experiments)")
    args = parser.parse_args()
    store = ResultsStore(args.runs_dir)
    if args.cancel:
        store.cancel(args.cancel)
        print(store.run_path(args.cancel))
        return
    if args.experiment is None:
        parser.error("experiment path required unless --cancel is used")
    holder = hold_caffeinate() if resolve_caffeinate(args.experiment, args.caffeinate) else None
    try:
        if args.run_id is None:
            run_id = run(load_experiment(args.experiment), store, args.workers)
        else:
            try:
                run_id = run(load_experiment(args.experiment), store, args.workers, run_id=args.run_id)
            except Exception:
                # Publish failures before the runner has entered its lifecycle loop.
                import traceback
                from flyonenomics.store.results import atomic_json
                directory = store.run_path(args.run_id)
                status = read_json(directory / "status.json")
                status.update(state="failed", traceback=traceback.format_exc())
                atomic_json(directory / "status.json", status)
                store.index.upsert(args.run_id, read_json(directory / "experiment.json"), status)
                raise
        errors = store.validate_run(run_id)
        if errors:
            raise RuntimeError("validate_run failed: " + "; ".join(errors))
        print(store.run_path(run_id), flush=True)
        if read_json(store.run_path(run_id) / "status.json")["state"] != "done":
            raise SystemExit(2)
    finally:
        if holder is not None:
            release_caffeinate(holder)


if __name__ == "__main__":
    main()
