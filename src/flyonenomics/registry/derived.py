"""Derived populations that are not YAML rows (SPEC-P2 section 4.2)."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from flyonenomics.registry.populations import Population


def da_exposed(registry: Any) -> Population:
    """Neurons with nonzero exposure and a nonzero receptor weight.

    Units: root IDs dimensionless; idx int32 engine positions.
    Shapes: (count,) each.
    """
    exposure = registry.exposure()
    exposed = np.asarray(exposure.getnnz(axis=1) > 0)
    receptors = registry.receptors()
    has_receptor = (
        (np.asarray(receptors.r1) != 0)
        | (np.asarray(receptors.r2) != 0)
        | (np.asarray(receptors.rq) != 0)
    )
    idx = np.flatnonzero(exposed & has_receptor).astype(np.int32)
    roots = np.asarray(registry.root_ids[idx], dtype=np.int64)
    count = int(idx.size)
    return Population(
        name="DA_exposed",
        root_ids=roots,
        idx=idx,
        side=np.array(["na"] * count),
        selector="derived:exposure+receptor",
        count=count,
        inventory_range=(count, count),
    )


def root_ids_sha256(root_ids: np.ndarray) -> str:
    """SHA-256 of root IDs in engine order. Units: none. Shapes: one hex."""
    payload = np.ascontiguousarray(np.asarray(root_ids, dtype=np.int64))
    return hashlib.sha256(payload.tobytes()).hexdigest()


def attach_derived(registry: Any) -> Any:
    """Insert DA_exposed into a built registry. Units: none."""
    population = da_exposed(registry)
    registry._populations["DA_exposed"] = population
    return registry
