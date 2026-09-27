"""Importable validation execution for parallel workers (SPEC item 69(c)).

scripts/run_validation.py keeps the CLI and the serial path that tests patch.
Spawned workers import this module so they are not __main__.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
_SKIP = {
    "flyonenomics.validation.binding",
    "flyonenomics.validation.execute",
    "flyonenomics.validation.runner",
}


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


def bind_entry(entry: Any, root: Path | None = None) -> Any:
    """Apply the section 7 compatibility check to one returned entry."""
    from flyonenomics.types import LayerFlags
    from flyonenomics.validation.binding import ValidationEntry, build_identity, is_compatible

    repo = ROOT if root is None else root
    if not isinstance(entry, ValidationEntry):
        raise TypeError("suite did not return a ValidationEntry")
    substrate_id = None
    if entry.identity.substrate_id != "bare":
        # Rest-bound suites share the item 122 reader. Bare entries remain
        # bare instead of being relabelled when the declared drive exists.
        from flyonenomics.behaviour.visual_calibration import declared_substrate_id

        substrate_id = declared_substrate_id()
    current = build_identity(
        repo, connectome_version=entry.identity.connectome_version,
        layers=LayerFlags(**entry.identity.layer_flags), assay=entry.identity.assay,
        fixture=entry.fixture_path, protocol_hash=entry.identity.protocol_hash,
        run_code_hash=entry.identity.run_code_hash,
        declared_inputs=entry.declared_inputs or None,
        substrate_id=substrate_id,
    )
    valid, reason = is_compatible(entry, current, repo=repo)
    if not valid and entry.compatibility != "development":
        entry = entry.model_copy(update={
            "outcome": "stale", "measured": {**entry.measured, "binding_reason": reason},
        })
    return entry


def run_one_suite(test_id: str) -> dict[str, Any]:
    """Run one suite in this process. Units: none. Shapes: a result or error mapping."""
    try:
        suites = discover_suites()
        if test_id not in suites:
            raise KeyError(f"unknown suite test id: {test_id}")
        entry = bind_entry(suites[test_id]())
        if entry.test_id != test_id:
            raise ValueError(f"suite returned test id {entry.test_id}, expected {test_id}")
        return {"test_id": test_id, "entry": entry.model_dump(), "error": None}
    except Exception as exc:
        return {"test_id": test_id, "entry": None, "error": f"{type(exc).__name__}: {exc}"}
