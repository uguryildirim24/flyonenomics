"""Population selectors and resolution against the annotation artefact (WP2).

Tables are pandas only at the file boundary; resolved populations
are NumPy arrays. Selectors live in data/populations-v0.1.yaml; the
selector tolerance percent lives there too (file level), and every
other numeric threshold comes from data/params-v0.1.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    import pandas as pd


class StrictModel(BaseModel):
    """Forbid unknown fields. Units: per field. Shapes: per model."""

    model_config = ConfigDict(extra="forbid")


class ValuesSelector(StrictModel):
    """Equality filter on one annotation column.

    Units: values are column values (dimensionless). Shapes: a list
    of accepted values.
    """

    kind: Literal["values"] = "values"
    column: str = Field(min_length=1)
    values: list[str | int] = Field(min_length=1)


class RegexSelector(StrictModel):
    """Regular-expression filter on one annotation column.

    Units: none. Shapes: scalar strings. Optional second-column
    union (or_*), conjunction (and_*) and exclusion (not_*) express the CX/EB
    selector; side is filtered separately.
    """

    kind: Literal["regex"] = "regex"
    column: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    or_column: str | None = None
    or_pattern: str | None = None
    and_column: str | None = None
    and_pattern: str | None = None
    not_column: str | None = None
    not_pattern: str | None = None


class ExplicitSelector(StrictModel):
    """Explicit root list with its connectome version and mapping record.

    Units: root IDs are dimensionless 64-bit integers. Shapes: one
    list per version, order authoritative (never sorted).
    """

    kind: Literal["explicit"] = "explicit"
    source: str = Field(min_length=1)
    source_version: Literal["630", "783", "male-cns:v1.0"] = "630"
    source_roots: list[int] = Field(min_length=1)
    v783_roots: list[int] | None = None
    mapping_date: str = Field(min_length=1)
    unmapped_count: int = Field(ge=0)

    @model_validator(mode="after")
    def require_flywire_mapping(self) -> "ExplicitSelector":
        """Require v783 roots only for FlyWire source lists."""
        if self.source_version != "male-cns:v1.0" and not self.v783_roots:
            raise ValueError("FlyWire explicit selectors require v783_roots")
        return self


Selector = ValuesSelector | RegexSelector | ExplicitSelector


class PopulationEntry(StrictModel):
    """One population row of data/populations-v0.1.yaml.

    Units: inventory_count is a neuron count. Shapes: scalars and
    small lists. expected_nt names the transmitter the label check
    compares top_nt against (None where no single transmitter
    applies); exclude names populations whose members are removed;
    overlaps_with declares set overlap with sibling populations.
    """

    name: str = Field(min_length=1)
    selector: Selector
    required: bool = False
    exclude: list[str] = Field(default_factory=list)
    inventory_count: int = Field(ge=0)
    inventory_tolerance: Literal["exact", "percent"] = "percent"
    tolerance_percent: int = Field(default=10, ge=0, le=100)
    overlaps_with: list[str] = Field(default_factory=list)
    expected_nt: str | None = None
    side: Literal["left", "right"] | None = None
    note: str = ""


@dataclass(frozen=True)
class Population:
    """One resolved population.

    Units: root IDs are dimensionless int64; idx positions the
    members in engine order (int32). Shapes: root_ids (count,),
    idx (count,), side (count,) with entries left/right/center/na.
    """

    name: str
    root_ids: NDArray[np.int64]
    idx: NDArray[np.int32]
    side: NDArray[np.str_]
    selector: str
    count: int
    inventory_range: tuple[int, int]


def default_populations_path() -> Path:
    """Return the repo-relative path of the populations file.

    Units: none. Shapes: a single path.
    """
    return Path(__file__).resolve().parents[3] / "data" / "populations-v0.1.yaml"


def load_population_table(path: str | Path | None = None) -> tuple[str, list[PopulationEntry]]:
    """Load the populations YAML into validated entries.

    Units: inventory counts are neuron counts. Shapes: one entry
    per population. Returns the file version and the entries. The
    file-level selector_tolerance_percent sets every entry's
    tolerance_percent.
    """
    from flyonenomics.io import read_yaml

    resolved = Path(path) if path is not None else default_populations_path()
    raw = read_yaml(resolved)
    version = raw["version"]
    tolerance = int(raw.get("selector_tolerance_percent", 10))
    entries = [PopulationEntry.model_validate(row) for row in raw["populations"]]
    for entry in entries:
        entry.tolerance_percent = tolerance
    names = [entry.name for entry in entries]
    if len(set(names)) != len(names):
        raise ValueError("duplicate population names")
    return str(version), entries


def selector_description(selector: Selector) -> str:
    """Render a selector as a short human string.

    Units: none. Shapes: one string.
    """
    if isinstance(selector, ValuesSelector):
        return f"{selector.column} in {list(selector.values)}"
    if isinstance(selector, RegexSelector):
        text = f"{selector.column} ~ {selector.pattern}"
        if selector.or_column is not None:
            text = f"({text} or {selector.or_column} ~ {selector.or_pattern})"
        if selector.and_column is not None:
            text += f" and {selector.and_column} ~ {selector.and_pattern}"
        if selector.not_column is not None:
            text += f" and not {selector.not_column} ~ {selector.not_pattern}"
        return text
    return f"explicit list ({selector.source})"


def _engine_index(engine_order: NDArray[np.int64]) -> dict[int, int]:
    """Map root ID to engine index.

    Units: root IDs dimensionless; indices are row positions.
    Shapes: n entries.
    """
    return {int(root): position for position, root in enumerate(engine_order)}


def resolve_population(
    entry: PopulationEntry,
    annotations: pd.DataFrame,
    engine_order: NDArray[np.int64],
    resolved: dict[str, Population] | None = None,
) -> Population:
    """Resolve one population entry to root IDs and engine indices.

    Units: root IDs dimensionless int64; idx int32 engine positions.
    Shapes: (count,) each. Excludes members of the entry's exclude
    list, drops roots absent from the engine order (recorded on the
    population's note by the caller), and filters by side.
    """
    import pandas as pd

    finished = resolved or {}
    selector = entry.selector
    if isinstance(selector, ExplicitSelector):
        selected_roots = (
            selector.source_roots
            if selector.source_version == "male-cns:v1.0"
            else selector.v783_roots
        )
        roots = np.asarray(selected_roots, dtype=np.int64)
        frame = annotations.set_index("root_id")
        sides = []
        for root in roots:
            try:
                sides.append(str(frame.loc[int(root), "side"]))
            except KeyError:
                sides.append("na")
        side = np.asarray(sides)
    else:
        mask = pd.Series(True, index=annotations.index)
        if isinstance(selector, ValuesSelector):
            mask &= annotations[selector.column].isin(list(selector.values))
        else:
            column = annotations[selector.column].fillna("").astype(str)
            selected = column.str.match(selector.pattern, na=False)
            if selector.or_column is not None:
                other = annotations[selector.or_column].fillna("").astype(str)
                selected |= other.str.match(selector.or_pattern or "", na=False)
            mask &= selected
            if selector.and_column is not None:
                other = annotations[selector.and_column].fillna("").astype(str)
                mask &= other.str.match(selector.and_pattern or "", na=False)
            if selector.not_column is not None:
                other = annotations[selector.not_column].fillna("").astype(str)
                mask &= ~other.str.match(selector.not_pattern or "", na=False)
        if entry.side is not None:
            mask &= annotations["side"] == entry.side
        subset = annotations.loc[mask]
        roots = np.asarray(subset["root_id"].to_numpy(), dtype=np.int64)
        side = np.asarray(subset["side"].fillna("na").astype(str).to_numpy())
    for excluded_name in entry.exclude:
        excluded = set(int(value) for value in finished[excluded_name].root_ids)
        keep = np.array([int(value) not in excluded for value in roots])
        roots = roots[keep]
        side = side[keep]
    index_of = _engine_index(engine_order)
    positions = [index_of.get(int(root)) for root in roots]
    kept = np.asarray([position is not None for position in positions], dtype=bool)
    roots = roots[kept]
    side = side[kept]
    idx = np.asarray([positions[i] for i, flag in enumerate(kept) if flag], dtype=np.int32)
    if isinstance(selector, ExplicitSelector):
        order = np.arange(idx.size)
    else:
        order = np.argsort(idx, kind="stable")
    return Population(
        name=entry.name,
        root_ids=np.asarray(roots[order], dtype=np.int64),
        idx=np.asarray(idx[order], dtype=np.int32),
        side=np.asarray(side[order]),
        selector=selector_description(selector),
        count=int(order.size),
        inventory_range=inventory_range(entry),
    )


def inventory_range(entry: PopulationEntry) -> tuple[int, int]:
    """Return the accepted (low, high) inventory interval of an entry.

    Units: neuron counts. Shapes: two scalars. Exact for explicit
    lists, +-tolerance_percent (from the YAML file) for selectors.
    """
    expected = entry.inventory_count
    if entry.inventory_tolerance == "exact":
        return (expected, expected)
    delta = int(round(expected * entry.tolerance_percent / 100))
    return (max(0, expected - delta), expected + delta)


def check_inventory(population: Population, entry: PopulationEntry) -> None:
    """Raise if a population misses its inventory interval.

    Units: neuron counts. Shapes: scalars. Required populations must
    also be nonempty; registry construction fails on either breach.
    """
    low, high = inventory_range(entry)
    if entry.required and population.count == 0:
        raise ValueError(f"required population is empty: {entry.name}")
    if not (low <= population.count <= high):
        raise ValueError(
            f"inventory breach: {entry.name} has {population.count}, "
            f"expected {low}..{high} (YAML carries {entry.inventory_count})"
        )


def check_overlaps(populations: dict[str, Population], entries: dict[str, PopulationEntry]) -> None:
    """Raise on undeclared set overlap between two populations.

    Units: counts of intersecting roots. Shapes: scalars. Declared
    overlap is symmetric: naming it on either side suffices.
    """
    names = list(populations.keys())
    declared: set[frozenset[str]] = set()
    for name, entry in entries.items():
        for other in entry.overlaps_with:
            if other not in populations:
                raise ValueError(f"{name} declares overlap with unknown population {other}")
            declared.add(frozenset((name, other)))
    for position, first in enumerate(names):
        first_roots = set(int(value) for value in populations[first].root_ids)
        if not first_roots:
            continue
        for second in names[position + 1:]:
            second_roots = set(int(value) for value in populations[second].root_ids)
            if first_roots & second_roots and frozenset((first, second)) not in declared:
                raise ValueError(f"undeclared overlap: {first} x {second}")
