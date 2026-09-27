"""Hand-curated receptor map with precedence (WP2).

Densities r1 (Dop1R1), r2 (Dop2R), rq (Dop1R2) are relative values
in [0, 1] per population with a source per row; rq is carried and
reported but has no Phase 1 effect. Values live in
data/receptors-v0.1.yaml; this module validates the table and
expands it to per-neuron arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from pydantic import Field

from flyonenomics.registry.populations import StrictModel


@dataclass(frozen=True)
class ReceptorMap:
    """Per-neuron relative receptor densities.

    Units: dimensionless densities in [0, 1]. Shapes: (n,) float32
    each, in engine order.
    """

    r1: NDArray[np.float32]
    r2: NDArray[np.float32]
    rq: NDArray[np.float32]
    version: str


class ReceptorRow(StrictModel):
    """One hand-curated receptor row.

    Units: densities are dimensionless in [0, 1]. Shapes: scalars.
    """

    population: str = Field(min_length=1)
    r1: float = Field(ge=0, le=1)
    r2: float = Field(ge=0, le=1)
    rq: float = Field(ge=0, le=1)
    source: str = Field(min_length=1)


class ReceptorTable(StrictModel):
    """The curated content of data/receptors-v0.1.yaml.

    Units: densities dimensionless. Shapes: one row per listed
    population. precedence runs from the most specific population
    to the least; a neuron's densities come from the earliest
    listed population it belongs to.
    """

    version: str = Field(min_length=1)
    map_version: str = ""
    note: str = ""
    precedence: list[str] = Field(min_length=1)
    rows: list[ReceptorRow] = Field(min_length=1)


def default_receptors_path() -> Path:
    """Return the repo-relative path of the receptors file.

    Units: none. Shapes: a single path.
    """
    return Path(__file__).resolve().parents[3] / "data" / "receptors-v0.1.yaml"


def load_receptor_table(path: str | Path | None = None) -> ReceptorTable:
    """Load the receptors YAML into a validated table.

    Units: densities dimensionless in [0, 1]. Shapes: one row per
    listed population.
    """
    from flyonenomics.io import read_yaml

    resolved = Path(path) if path is not None else default_receptors_path()
    return ReceptorTable.model_validate(read_yaml(resolved))


def check_precedence(
    table: ReceptorTable, populations: dict[str, NDArray[np.int64]]
) -> dict[str, list[str]]:
    """Check the precedence order is total over overlapping populations.

    Units: none. Shapes: one overlap list per population. Raises if
    the precedence names differ from the row populations, if a row
    names an unknown population, or if two overlapping row
    populations were unresolvable. Returns the measured pairwise
    overlaps between row populations (informational; overlap
    itself is resolved by the order, never an error).
    """
    row_names = [row.population for row in table.rows]
    if len(set(row_names)) != len(row_names):
        raise ValueError("duplicate receptor rows")
    if set(table.precedence) != set(row_names) or len(table.precedence) != len(row_names):
        raise ValueError("precedence must name each row population exactly once")
    for name in row_names:
        if name not in populations:
            raise ValueError(f"receptor row names unknown population: {name}")
    overlaps: dict[str, list[str]] = {name: [] for name in row_names}
    for position, first in enumerate(row_names):
        first_roots = set(int(value) for value in populations[first])
        for second in row_names[position + 1:]:
            if first_roots & set(int(value) for value in populations[second]):
                overlaps[first].append(second)
                overlaps[second].append(first)
    return overlaps


def build_receptor_arrays(
    table: ReceptorTable,
    populations: dict[str, NDArray[np.int64]],
    engine_index: dict[int, int],
    n: int,
) -> ReceptorMap:
    """Expand the receptor table to per-neuron density arrays.

    Units: dimensionless densities in [0, 1]. Shapes: (n,) float32
    each in engine order. Each neuron takes the densities of the
    earliest precedence population it belongs to; neurons in no
    listed population get zeros.
    """
    values = {row.population: (row.r1, row.r2, row.rq) for row in table.rows}
    assigned = np.full(n, -1, dtype=np.int32)
    for rank, name in enumerate(table.precedence):
        for root in populations[name]:
            engine = engine_index.get(int(root))
            if engine is not None and assigned[engine] < 0:
                assigned[engine] = rank
    r1 = np.zeros(n, dtype=np.float32)
    r2 = np.zeros(n, dtype=np.float32)
    rq = np.zeros(n, dtype=np.float32)
    for rank, name in enumerate(table.precedence):
        mask = assigned == rank
        if np.any(mask):
            dens = values[name]
            r1[mask] = dens[0]
            r2[mask] = dens[1]
            rq[mask] = dens[2]
    return ReceptorMap(r1=r1, r2=r2, rq=rq, version=table.version)
