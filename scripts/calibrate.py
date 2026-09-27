"""Run calibration stages K1, K2, sign check, K3 in order.

Stage registry: later packages register stages by defining STAGE in
their drive, neuromod, or behaviour module: STAGE maps names to
callables. Discovery imports those modules; register() also supports in-process callers. Each stage is a zero-argument function returning a mapping
with the stage record. Order: K1, K2, sign, K3.

`--phase 2` dispatches C0, R1, R2, R3, R4, K1r, drive, K2r, Q-rest
and writes resumable records under validation/records/p2/.

Units: stages state their own units. Shapes: scalars only.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

import importlib
import pkgutil

STAGES: dict[str, Callable[[], dict[str, Any]]] = {}

ORDER = ["K1", "K2", "sign", "K3"]
ORDER_P2 = ["C0", "R1", "R2", "R3", "R4", "K1r", "drive", "K2r", "Q-rest"]
ROOT = Path(__file__).resolve().parents[1]
RECORDS_P2 = ROOT / "validation" / "records" / "p2"


def register(name: str, func: Callable[[], dict[str, Any]]) -> None:
    """Register one calibration stage under its order name.

    Units: none. Shapes: one name and one callable.
    """
    if name not in ORDER and name not in ORDER_P2:
        raise ValueError(f"unknown calibration stage: {name}")
    if name in STAGES:
        raise ValueError(f"duplicate calibration stage: {name}")
    if not callable(func):
        raise TypeError(f"calibration stage is not callable: {name}")
    STAGES[name] = func


def discover_stages(phase: int = 1) -> dict[str, Callable[[], dict[str, Any]]]:
    """Discover STAGE mappings from calibration owners. Units: none. Shapes: name/callable mapping."""
    allowed = set(ORDER if phase == 1 else ORDER_P2)
    stages = {name: func for name, func in STAGES.items() if name in allowed}
    for owner in ("drive", "neuromod", "behaviour"):
        package = importlib.import_module(f"flyonenomics.{owner}")
        modules = [package] + [importlib.import_module(info.name) for info in
                   sorted(pkgutil.walk_packages(package.__path__, package.__name__ + "."), key=lambda item: item.name)]
        for module in modules:
            mapping = getattr(module, "STAGE", {})
            if not isinstance(mapping, Mapping):
                raise TypeError(f"{module.__name__}.STAGE must be a mapping")
            for name, func in mapping.items():
                if name not in allowed:
                    continue
                if not callable(func):
                    raise ValueError(f"invalid calibration stage: {name}")
                if name in stages:
                    raise ValueError(f"duplicate calibration stage: {name}")
                stages[name] = func
    return stages


def nonblocking(name: str, record: dict[str, Any], *, phase: int = 1) -> bool:
    """Only the item-47 K1 omission may be skipped in the calibration chain."""
    if record["status"] in ("recorded", "passed"):
        return True
    return phase == 1 and name == "K1" and record["status"] == "skipped" and "item 47" in record.get("reason", "")


def _record_path(name: str) -> Path:
    return RECORDS_P2 / f"{name}.json"


def _load_record(name: str) -> dict[str, Any] | None:
    path = _record_path(name)
    if not path.is_file():
        return None
    from flyonenomics.io import read_json
    return read_json(path)


def _write_record(name: str, record: dict[str, Any]) -> None:
    from flyonenomics.store.results import atomic_json
    RECORDS_P2.mkdir(parents=True, exist_ok=True)
    atomic_json(_record_path(name), record)


def run_stages(phase: int = 1) -> dict[str, dict[str, Any]]:
    """Run the Phase 1 or Phase 2 stage order, stopping on a failed predecessor.

    Units: per stage. Shapes: mapping of stage name to record.
    Each stage returns a mapping with status recorded, passed or skipped on success.
    Discovery does not execute stages. Later stages are blocked on failure.
    Phase 2 skips a passed record whose input_identity is unchanged. The
    identity comes from the stage callable's `input_identity()`; a stage
    without one always reruns.
    """
    order = ORDER if phase == 1 else ORDER_P2
    # Phase 1 keeps its exact call; a TypeError from a phase-2 discovery is a real error.
    stages = discover_stages() if phase == 1 else discover_stages(phase=phase)
    records: dict[str, dict[str, Any]] = {}
    blocked_by: str | None = None
    for name in order:
        if blocked_by:
            records[name] = {"status": "blocked", "reason": f"requires {blocked_by}"}
            continue
        func = stages.get(name)
        current_id = None
        if phase == 2 and func is not None:
            identity_fn = getattr(func, "input_identity", None)
            current_id = identity_fn() if callable(identity_fn) else None
            stored = _load_record(name)
            if (current_id is not None and stored and stored.get("status") == "passed"
                    and stored.get("input_identity") == current_id):
                records[name] = stored
                continue
        if func is None:
            records[name] = {"status": "not registered (later work package)"}
            blocked_by = name
            continue
        try:
            record = func()
            if not isinstance(record, dict) or record.get("status") not in ("recorded", "passed", "skipped", "failed", "unavailable", "blocked"):
                raise ValueError(f"{name} must return a stage record with an explicit status")
            records[name] = record
        except Exception as exc:
            records[name] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        if phase == 2:
            if current_id is not None:
                records[name]["input_identity"] = current_id
            _write_record(name, records[name])
        if not nonblocking(name, records[name], phase=phase):
            blocked_by = name
    return records


def main(argv: list[str] | None = None) -> None:
    """Entry point for scripts/calibrate.py.

    Units: per stage. Shapes: mapping of stage name to record.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=1, choices=(1, 2))
    args, _unknown = parser.parse_known_args(argv)
    records = run_stages(phase=args.phase)
    order = ORDER if args.phase == 1 else ORDER_P2
    for name in order:
        print(f"{name}: {json.dumps(records[name])}")
    if any(not nonblocking(name, record, phase=args.phase) for name, record in records.items()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
