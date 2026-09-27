"""Population registry: map root IDs to indices (WP2).

The registry defines named populations from the pinned annotation
artefact through declared selectors, builds the weighted
neuron-to-compartment (W) and DAN-to-compartment (M) maps, and
carries the receptor map. It never imports the engine; root order
comes from the completeness file directly.
"""

from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import scipy.sparse as sparse
from numpy.typing import NDArray
from pydantic import Field

from flyonenomics.datasets import get_dataset_adapter
from flyonenomics.registry import annotations as ann
from flyonenomics.registry import compartments as comp
from flyonenomics.registry import receptors as rec
from flyonenomics.registry.compartment import Compartment
from flyonenomics.registry.populations import (
    Population,
    PopulationEntry,
    StrictModel,
    check_inventory,
    check_overlaps,
    inventory_range,
    load_population_table,
    resolve_population,
)
from flyonenomics.types import load_params


class ExplicitSpec(StrictModel):
    """An explicit root list with its connectome version.

    Units: root IDs are dimensionless 64-bit integers. Shapes:
    (n_roots,) in source order (never sorted).
    """

    roots: list[int] = Field(min_length=1)
    version: Literal["630", "783", "male-cns:v1.0"] = "783"


class QuerySpec(StrictModel):
    """An annotation query with equality or regex filters.

    Units: none. Shapes: scalar strings and value lists.
    """

    column: str = Field(min_length=1)
    values: list[str] | None = None
    pattern: str | None = None
    side: Literal["left", "right"] | None = None


class PopulationSpec(StrictModel):
    """A resolvable population reference.

    Units: per variant. Shapes: exactly one of name, explicit, or
    query is set.
    """

    name: str | None = None
    explicit: ExplicitSpec | None = None
    query: QuerySpec | None = None


def _compartment_side(name: str) -> Literal["left", "right", "center"]:
    """Split a compartment name into its side.

    Units: none. Shapes: one word.
    """
    if name.endswith("_L"):
        return "left"
    if name.endswith("_R"):
        return "right"
    return "center"


class Registry:
    """Named populations, compartment maps, and the receptor map.

    Units: root IDs are dimensionless int64; W/M weights are
    dimensionless; receptor densities are dimensionless in [0, 1].
    Shapes: root_ids (n,); W (n, 37); M (37, n); receptor arrays
    (n,); all in engine (completeness-file row) order.
    """

    def __init__(
        self,
        *,
        version: str,
        root_ids: NDArray[np.int64],
        populations: dict[str, Population],
        entries: dict[str, PopulationEntry],
        table: comp.CompartmentTable,
        exposure_w: sparse.csr_matrix,
        innervation_m: sparse.csr_matrix,
        receptor_map: rec.ReceptorMap,
        candidate_roots: NDArray[np.int64],
        candidate_fractions: NDArray[np.float32],
        cxdan_roots: NDArray[np.int64],
        provenance: dict[str, object],
    ) -> None:
        """Store a built registry. Units and shapes: see the class docstring."""
        self.version = version
        self.connectome_version = str(provenance["connectome_version"])
        self.n = int(root_ids.size)
        self.root_ids = np.asarray(root_ids, dtype=np.int64)
        self._populations = populations
        self._entries = entries
        self._table = table
        self._w = exposure_w.tocsr()
        self._m = innervation_m.tocsr()
        self._receptors = receptor_map
        self._candidate_roots = np.asarray(candidate_roots, dtype=np.int64)
        self._candidate_fractions = np.asarray(candidate_fractions, dtype=np.float32)
        self._cxdan_roots = np.asarray(cxdan_roots, dtype=np.int64)
        self._provenance = dict(provenance)
        self._index = {int(root): position for position, root in enumerate(self.root_ids)}

    def index_of(self, root_ids: NDArray[np.int64]) -> NDArray[np.int32]:
        """Map root IDs to engine indices.

        Units: root IDs dimensionless; indices are row positions.
        Shapes: (n_queries,) in and out. Raises KeyError listing
        unknown roots.
        """
        roots = np.asarray(root_ids, dtype=np.int64)
        positions: list[int] = []
        unknown: list[int] = []
        for root in roots:
            slot = self._index.get(int(root))
            if slot is None:
                unknown.append(int(root))
            else:
                positions.append(slot)
        if unknown:
            raise KeyError(f"unknown roots: {unknown}")
        return np.asarray(positions, dtype=np.int32)

    def population(self, name: str) -> Population:
        """Return one resolved population by name.

        Units: per Population fields. Shapes: (count,) member
        arrays. Raises KeyError for unknown names.
        """
        try:
            return self._populations[name]
        except KeyError:
            raise KeyError(f"unknown population: {name}") from None

    def populations(self) -> list[str]:
        """Return every population name in YAML order.

        Units: none. Shapes: (n_populations,) names.
        """
        return list(self._populations.keys())

    def resolve(self, spec: PopulationSpec) -> Population:
        """Resolve a population reference to root IDs and indices.

        Units: root IDs dimensionless int64; idx int32 positions.
        Shapes: (count,) member arrays. Names resolve to the stored
        population; explicit v630 lists map through supervoxel IDs
        (unmapped roots dropped); queries filter the annotation
        artefact. Ad-hoc resolves skip inventory checks.
        """
        if spec.name is not None and spec.explicit is None and spec.query is None:
            return self.population(spec.name)
        if spec.query is not None and spec.query.column == "top_nt":
            raise ValueError("top_nt is reserved for the label check, not population queries")
        annotations = ann.load_dataset_annotations(self.connectome_version)
        if spec.explicit is not None and spec.query is None and spec.name is None:
            wanted = np.asarray(spec.explicit.roots, dtype=np.int64)
            if spec.explicit.version == "630" and self.connectome_version == "783":
                result = ann.map_roots(wanted, "v1.1.0", "v2.1.0")
                wanted = np.asarray(
                    [value for value in result.mapped if value is not None], dtype=np.int64
                )
            wanted_ints = [int(value) for value in wanted]
            kept_ints = [root for root in wanted_ints if root in self._index]
            positions = [self._index[root] for root in kept_ints]
            frame = annotations.set_index("root_id")
            sides = [str(frame.loc[root, "side"]) if root in frame.index else "na" for root in kept_ints]
            roots = np.asarray(kept_ints, dtype=np.int64)
            return Population(
                name=spec.name or "ad-hoc",
                root_ids=roots,
                idx=np.asarray(positions, dtype=np.int32),
                side=np.asarray(sides) if sides else np.asarray([]),
                selector="ad-hoc",
                count=int(roots.size),
                inventory_range=(0, self.n),
            )
        if spec.query is not None and spec.name is None and spec.explicit is None:
            from flyonenomics.registry.populations import RegexSelector, ValuesSelector

            query = spec.query
            if query.values is not None and query.pattern is None:
                selector: RegexSelector | ValuesSelector = ValuesSelector(column=query.column, values=query.values)
            elif query.pattern is not None and query.values is None:
                selector = RegexSelector(column=query.column, pattern=query.pattern)
            else:
                raise ValueError("query needs exactly one of values or pattern")
            entry = PopulationEntry(
                name="ad-hoc",
                selector=selector,
                inventory_count=0,
                inventory_tolerance="exact",
                side=query.side,
            )
            resolved = resolve_population(entry, annotations, self.root_ids)
            return resolved
        raise ValueError("spec sets exactly one of name, explicit, or query")

    def compartments(self) -> list[Compartment]:
        """Return the 37 compartments with sides and ids.

        Units: ids dimensionless. Shapes: 37 rows in id order.
        """
        return [
            Compartment(name=name, side=_compartment_side(name), id=position)
            for position, name in enumerate(comp.compartment_names())
        ]

    def exposure(self) -> sparse.csr_matrix:
        """Return W, shape (n, 37), float32; rows sum to 1 or 0.

        Units: dimensionless exposure shares. Shapes: (n, 37).
        """
        return self._w.copy()

    def innervation(self) -> sparse.csr_matrix:
        """Return M, shape (37, n), float32; columns sum to 1 or 0.

        Units: dimensionless innervation shares. Shapes: (37, n).
        """
        return self._m.copy()

    def exposed_mask(self) -> NDArray[np.bool_]:
        """Return True where the W row is nonzero.

        Units: boolean. Shapes: (n,).
        """
        return np.asarray(self._w.getnnz(axis=1) > 0)

    def receptors(self) -> rec.ReceptorMap:
        """Return r1, r2, rq float32 arrays of length n in [0, 1].

        Units: dimensionless densities. Shapes: (n,) each.
        """
        return self._receptors

    def provenance(self) -> dict[str, object]:
        """Return the registry provenance record.

        Units: per field. Shapes: scalars and small lists.
        """
        return dict(self._provenance)

    def candidate_fractions(self) -> dict[int, float]:
        """Return each candidate's central-complex output fraction.

        Units: dimensionless fractions. Shapes: one entry per
        pre-filter candidate root.
        """
        return {int(root): float(frac) for root, frac in zip(self._candidate_roots, self._candidate_fractions, strict=True)}

    def inventory(self, name: str) -> tuple[int, tuple[int, int]]:
        """Return a population's count and accepted interval.

        Units: neuron counts. Shapes: two scalars.
        """
        pop = self.population(name)
        if name not in self._entries:
            return pop.count, pop.inventory_range
        return pop.count, inventory_range(self._entries[name])


def build_registry(
    connectome_version: ann.ConnectomeVersion = "783",
    populations_path: str | Path | None = None,
    compartments_path: str | Path | None = None,
    receptors_path: str | Path | None = None,
) -> Registry:
    """Build the registry through the five-step compartment construction.

    Units: weights and densities dimensionless; root IDs int64.
    Shapes: W (n, 37), M (37, n), receptor arrays (n,). Rebuilds from
    verified current files on every call. Raises on required-population
    breach, inventory breach, undeclared overlap, precedence breach,
    or CX_DAN filter mismatch against the compartments YAML.
    """
    params = load_params()
    threshold = float(params.get("cxdan.min_cx_output_fraction"))
    annotations = ann.load_dataset_annotations(connectome_version)
    engine_order = ann.load_engine_order(connectome_version)
    engine_index = {int(root): position for position, root in enumerate(engine_order)}
    n = int(engine_order.size)
    adapter = get_dataset_adapter(connectome_version)
    selected_populations = populations_path
    if selected_populations is None:
        selected_populations = adapter.population_registry_path()
    pop_version, entries = load_population_table(selected_populations)
    resolved: dict[str, Population] = {}
    entry_of: dict[str, PopulationEntry] = {}
    for entry in entries:
        try:
            population = resolve_population(entry, annotations, engine_order, resolved)
        except KeyError as exc:
            raise ValueError(f"{entry.name} excludes unknown population: {exc}") from None
        check_inventory(population, entry)
        resolved[entry.name] = population
        entry_of[entry.name] = entry
    check_overlaps(resolved, entry_of)
    selected_compartments = compartments_path
    if selected_compartments is None:
        selected_compartments = adapter.compartment_table_path()
    table = comp.load_compartment_table(selected_compartments)
    roots_of = {name: pop.root_ids for name, pop in resolved.items()}
    sides_of = {name: pop.side for name, pop in resolved.items()}
    dan = resolved["DAN"]
    dan_frame = annotations.set_index("root_id")
    dan_types = np.asarray([
        "na" if int(root) not in dan_frame.index or pd.isna(dan_frame.loc[int(root), "hemibrain_type"])
        else str(dan_frame.loc[int(root), "hemibrain_type"])
        for root in dan.root_ids
    ])
    mbon_frame_types = np.asarray([
        "na" if int(root) not in dan_frame.index or pd.isna(dan_frame.loc[int(root), "hemibrain_type"])
        else str(dan_frame.loc[int(root), "hemibrain_type"])
        for root in resolved["MBON"].root_ids
    ], dtype=object)
    if connectome_version == "male-cns:v1.0":
        # MaleCNS has four source-type ``MBON25-like`` cells. Three also
        # carry the exact released FlyWire type ``MBON25,MBON34``, which is
        # already a declared Aso/Li table key. Use that anatomical label when
        # the primary MaleCNS type is not a table key; do not infer an alias
        # for the fourth cell from model output.
        for slot, root in enumerate(resolved["MBON"].root_ids):
            if mbon_frame_types[slot] in table.mbon_compartments:
                continue
            fallback = dan_frame.loc[int(root), "cell_type"]
            if not pd.isna(fallback) and str(fallback) in table.mbon_compartments:
                mbon_frame_types[slot] = str(fallback)
    target_w = comp.build_target_rows(
        n, roots_of, sides_of, engine_index, dict(table.mbon_compartments), mbon_frame_types
    )
    candidates = resolved["CX_DAN_candidates"].root_ids
    if connectome_version == "male-cns:v1.0":
        partners_path = adapter.roi_connectivity_path()
        if partners_path is None:
            raise ValueError("MaleCNS adapter carries no per-synapse ROI partner table")
        post_sides = {
            int(root): ("na" if pd.isna(side) else str(side))
            for root, side in zip(annotations["root_id"], annotations["side"], strict=True)
        }
        sums, totals = comp.male_roi_candidate_sums(partners_path, candidates, post_sides)
    else:
        edges = ann.load_connectivity_edges(candidates, connectome_version)
        sums, totals = comp.candidate_sums(edges, engine_index, candidates, target_w)
    fractions = comp.cx_fractions(sums, totals)
    keep = comp.apply_cx_filter(fractions, threshold)
    computed_cxdan = np.asarray([int(root) for root, flag in zip(candidates, keep, strict=True) if flag])
    recorded = table.cxdan
    if recorded is None:
        raise ValueError("compartments YAML carries no cxdan record")
    if recorded.pre_count != int(candidates.size):
        raise ValueError("cxdan pre-filter count mismatches the YAML record")
    if recorded.post_count != int(computed_cxdan.size):
        raise ValueError("cxdan post-filter count mismatches the YAML record")
    recorded_excluded = {item.root for item in recorded.excluded}
    computed_excluded = {int(root) for root, flag in zip(candidates, keep, strict=True) if not flag}
    if recorded_excluded != computed_excluded:
        raise ValueError("cxdan excluded roots mismatch the YAML record")
    recorded_fractions = {item.root: item.fraction for item in recorded.excluded}
    for root, fraction in zip(candidates, fractions, strict=True):
        if int(root) in recorded_excluded and abs(recorded_fractions[int(root)] - float(fraction)) > 1e-4:
            raise ValueError(f"cxdan fraction mismatch for root {root}")
    passed = resolved["CX_DAN"]
    if set(int(value) for value in passed.root_ids) != set(int(value) for value in computed_cxdan):
        raise ValueError("CX_DAN membership mismatches the connectivity filter outcome")
    innervation = comp.build_innervation(
        n,
        dan.idx,
        dan_types,
        dan.side,
        dict(table.dan_compartments),
        tuple(table.bilateral_dan_prefixes),
        passed.idx,
        sums[:, np.asarray([slot for slot, flag in enumerate(keep) if flag])] if int(computed_cxdan.size) else np.zeros((len(comp.compartment_names()), 0), dtype=np.float32),
    )
    exposure = comp.build_exposure(target_w, innervation)
    selected_receptors = receptors_path
    if selected_receptors is None:
        selected_receptors = adapter.receptor_table_path()
    receptor_table = rec.load_receptor_table(selected_receptors)
    rec.check_precedence(receptor_table, roots_of)
    receptor_map = rec.build_receptor_arrays(receptor_table, roots_of, engine_index, n)
    exposed = int(exposure.getnnz(axis=1).astype(bool).sum())
    if connectome_version == "male-cns:v1.0":
        from flyonenomics.io import read_json

        manifest = read_json(Path(__file__).resolve().parents[3] / "data" / "malecns-v1.0-manifest.json")
        annotation_source = next(
            row for row in manifest["files"]
            if row["name"] == "body-annotations-male-cns-v1.0-minconf-0.5.feather"
        )
        annotation_name = "male-cns:v1.0"
        annotation_commit = None
        annotation_sha256 = annotation_source["sha256"]
    else:
        records = ann.provenance_records()
        annotation_record = next(
            value for value in records.values()
            if value.item == ann.ANNOTATION_ITEMS["v2.1.0"]
        )
        annotation_name = "v2.1.0"
        annotation_commit = annotation_record.commit
        annotation_sha256 = annotation_record.sha256
    provenance = {
        "registry_version": f"populations-{pop_version}+annotations-{annotation_name}+{connectome_version}",
        "annotation_commit": annotation_commit,
        "annotation_sha256": annotation_sha256,
        "connectome_version": connectome_version,
        "receptor_map_version": receptor_table.version,
        "compartments_version": table.version,
        "cxdan_threshold": threshold,
        "unmapped_neurons": int(n - exposed),
        "unmapped_fraction": float((n - exposed) / n),
    }
    if connectome_version == "male-cns:v1.0":
        provenance.update({
            "dataset_release": "MaleCNS v1.0 (2026-06-08)",
            "cxdan_rule": "per-synapse primary_post ROI; NO split by postsynaptic canonical side",
        })
    registry = Registry(
        version=str(provenance["registry_version"]),
        root_ids=engine_order,
        populations=resolved,
        entries=entry_of,
        table=table,
        exposure_w=exposure,
        innervation_m=innervation,
        receptor_map=receptor_map,
        candidate_roots=candidates,
        candidate_fractions=fractions,
        cxdan_roots=computed_cxdan,
        provenance=provenance,
    )
    if pop_version in ("v0.1", "dev"):
        return registry  # Phase 1 registries, manifests and detectors keep their population set.
    from flyonenomics.registry.derived import attach_derived
    return attach_derived(registry)
