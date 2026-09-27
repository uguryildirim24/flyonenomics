"""Experiment orchestration with lazy engine imports."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from flyonenomics.schema import Experiment
    from flyonenomics.store import ResultsStore


def run(experiment: Experiment, store: ResultsStore, n_workers: int | str | None = None, *, fixture_settle_s: dict[int, float] | None = None, run_id: str | None = None) -> str:
    """Run with spawned workers; units seconds/Hz per experiment, scalar run ID."""
    from flyonenomics.orchestrator.runner import run as execute
    return execute(experiment, store, n_workers, fixture_settle_s=fixture_settle_s, run_id=run_id)

__all__ = ["run"]
