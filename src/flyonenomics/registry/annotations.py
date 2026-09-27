"""Annotation artefact loading and cross-version root mapping (WP2).

Tables are pandas only at the file boundary; everything past the
loader is NumPy arrays. Paths are read from data/provenance.json
(validated with types.ProvenanceRecord), never as literals. The cache
directory honours FLYONENOMICS_CACHE_DIR and falls back to .cache
under the repository root.
"""

from __future__ import annotations

from functools import lru_cache
import os
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from numpy.typing import NDArray

from flyonenomics.datasets import (
    AnnotationVersion,
    CANONICAL_ANNOTATION_COLUMNS,
    ConnectomeVersion,
    get_dataset_adapter,
)
from flyonenomics.types import ProvenanceRecord

#: Canonical names shared by FlyWire and MaleCNS adapters.
INTERNAL_COLUMNS = CANONICAL_ANNOTATION_COLUMNS

#: Columns absent from the v1.1.0 file. Units: none. Shapes: names only.
V110_ABSENT_COLUMNS: tuple[str, ...] = ("known_nt", "known_nt_source", "vfb_id", "fbbt_id")

#: Provenance items holding the annotation artefacts. Units: none. Shapes: names only.
ANNOTATION_ITEMS: dict[str, str] = {
    "v2.1.0": "annotations-v2.1.0.tsv",
    "v1.1.0": "annotations-v1.1.0.tsv",
}

#: Provenance items holding the completeness (engine-order neuron list)
#: per connectome version. Units: none. Shapes: names only.
COMPLETENESS_ITEMS: dict[str, str] = {
    "783": "Shiu clone Completeness_783.csv",
    "630": "Shiu clone 2023_03_23_completeness_630_final.csv",
}

#: Provenance items holding the weighted connectivity per connectome
#: version. Units: none. Shapes: names only.
CONNECTIVITY_ITEMS: dict[str, str] = {
    "783": "Shiu clone Connectivity_783.parquet",
    "630": "Shiu clone 2023_03_23_connectivity_630_final.parquet",
}


def repo_root() -> Path:
    """Return the repository root (the directory holding data/).

    Units: none. Shapes: a single path.
    """
    return Path(__file__).resolve().parents[3]


def cache_dir() -> Path:
    """Return the download cache directory.

    Units: none. Shapes: a single path. Honours
    FLYONENOMICS_CACHE_DIR, else .cache under the repository root.
    """
    override = os.environ.get("FLYONENOMICS_CACHE_DIR")
    if override:
        return Path(override)
    return repo_root() / ".cache"


def provenance_records() -> dict[str, ProvenanceRecord]:
    """Load data/provenance.json validated as ProvenanceRecord rows.

    Units: none. Shapes: a mapping of item name to record.
    """
    from flyonenomics.io import read_json

    raw = read_json(repo_root() / "data" / "provenance.json")
    records = [ProvenanceRecord.model_validate(row) for row in raw["records"]]
    return {record.item: record for record in records}


def cached_path(record: ProvenanceRecord) -> Path:
    """Resolve a provenance record's canonical path to the filesystem.

    Units: none. Shapes: a single path. Paths under .cache/ are
    rebased onto cache_dir(); every other path is relative to the
    repository root.
    """
    if record.path is None:
        raise ValueError(f"provenance record has no path: {record.item}")
    relative = Path(record.path)
    if relative.parts and relative.parts[0] == ".cache":
        return cache_dir().joinpath(*relative.parts[1:])
    return repo_root() / relative


def verify_file(path: Path, record: ProvenanceRecord) -> None:
    """Verify a cached file's SHA-256 against its provenance record.

    Units: bytes hashed. Shapes: one path in, nothing out. Raises
    ValueError on mismatch (a hard error; the caller must not read
    the file).
    """
    if record.status != "fetched" or record.sha256 is None:
        raise ValueError(f"cannot verify unfetched record: {record.item}")
    from flyonenomics.io import hash_file

    if hash_file(path) != record.sha256:
        raise ValueError(f"checksum mismatch: {path}")


def load_annotations(version: AnnotationVersion) -> pd.DataFrame:
    """Load one versioned annotation table through its dataset adapter."""
    if version == "male-cns:v1.0":
        return get_dataset_adapter(version).load_annotations(version)
    return get_dataset_adapter("783").load_annotations(version)


def load_dataset_annotations(connectome_version: ConnectomeVersion) -> pd.DataFrame:
    """Load the canonical annotation table selected by connectome version."""
    if connectome_version in ("630", "783"):
        return load_annotations("v2.1.0")
    return get_dataset_adapter(connectome_version).load_annotations()


def load_engine_order(connectome_version: ConnectomeVersion) -> NDArray[np.int64]:
    """Load the engine's root-ID order from the completeness file.

    Units: root IDs are dimensionless 64-bit integers. Shapes: (n,)
    with n = 138,639 for v783. Order is the file's row order, which
    the engine uses as its index order.
    """
    return get_dataset_adapter(connectome_version).load_engine_order()


@dataclass(frozen=True)
class MapResult:
    """Outcome of a cross-version root mapping.

    Units: root IDs and supervoxel IDs are dimensionless integers.
    Shapes: mapped has one entry per input root (None where
    unmapped); unmapped lists the input roots with no counterpart,
    in input order.
    """

    mapped: tuple[int | None, ...]
    unmapped: tuple[int, ...]

    @property
    def unmapped_count(self) -> int:
        """Return the number of unmapped input roots.

        Units: count. Shapes: scalar.
        """
        return len(self.unmapped)


def map_roots(
    root_ids: NDArray[np.int64],
    from_version: AnnotationVersion,
    to_version: AnnotationVersion,
) -> MapResult:
    """Map root IDs across annotation versions through supervoxel IDs.

    Units: root IDs are dimensionless 64-bit integers. Shapes:
    (n_inputs,) in, one mapped entry per input out, order
    preserved; sorting is never applied. Supervoxel IDs are stable
    across materialisations; both files carry them.
    """
    source = load_annotations(from_version)[["supervoxel_id", "root_id"]]
    target = load_annotations(to_version)[["supervoxel_id", "root_id"]]
    supervoxel_of = dict(zip(source["root_id"].to_numpy(), source["supervoxel_id"].to_numpy()))
    root_of = dict(zip(target["supervoxel_id"].to_numpy(), target["root_id"].to_numpy()))
    mapped: list[int | None] = []
    unmapped: list[int] = []
    for root in (int(value) for value in root_ids):
        supervoxel = supervoxel_of.get(root)
        counterpart = root_of.get(supervoxel) if supervoxel is not None else None
        if counterpart is None:
            mapped.append(None)
            unmapped.append(root)
        else:
            mapped.append(int(counterpart))
    return MapResult(mapped=tuple(mapped), unmapped=tuple(unmapped))


def load_connectivity_edges(
    presynaptic_roots: NDArray[np.int64] | None,
    connectome_version: ConnectomeVersion = "783",
) -> pd.DataFrame:
    """Load weighted connectivity edges, optionally filtered presynaptically.

    Units: Connectivity is a synapse count (dimensionless). Shapes:
    one row per presynaptic/postsynaptic pair with columns
    Presynaptic_ID (int64), Postsynaptic_ID (int64), Connectivity
    (int64). A None filter loads the full table (about 15 million
    rows for v783); pass the candidate roots to keep memory small.
    """
    return get_dataset_adapter(connectome_version).load_connectivity_edges(presynaptic_roots)


POST_COUNT_ITEM = "Zenodo per-neuron post-synapse counts, FlyWire v783"


def load_input_counts(engine_order: NDArray[np.int64]) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.bool_]] | None:
    """Load in-model and total input counts in v783 engine order.

    Units: synapses. Shapes: three (n,) arrays: numerator, denominator,
    denominator-present mask; None if the approved denominator is unfetched.
    Sum lowercase count over neuropils. Stream connectivity batches and
    count only presynaptic roots in the model. Verify both source hashes.
    """
    records = provenance_records()
    record = records.get(POST_COUNT_ITEM)
    if record is None or record.status != "fetched":
        return None
    path = cached_path(record)
    verify_file(path, record)
    connectivity = records[CONNECTIVITY_ITEMS["783"]]
    connectivity_path = cached_path(connectivity)
    verify_file(connectivity_path, connectivity)
    counts = _reduce_input_counts(tuple(int(root) for root in engine_order),
        path, record.sha256, connectivity_path, connectivity.sha256)
    return tuple(array.copy() for array in counts)


@lru_cache(maxsize=1)
def _reduce_input_counts(
    roots: tuple[int, ...], path: Path, denominator_sha256: str,
    connectivity_path: Path, connectivity_sha256: str,
) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.bool_]]:
    """Cache reductions by engine order, paths and verified source hashes.

    Units: synapses. Shapes: three (n,) arrays; caller returns copies.
    Files are verified before every cache lookup, including cache hits.
    """
    import pyarrow as pa
    import pyarrow.compute as pc
    from flyonenomics.io import parquet_file, read_feather

    engine_order = np.asarray(roots, dtype=np.int64)
    table = read_feather(path, columns=["post_pt_root_id", "count"])
    # Discard non-model roots before grouping the 43-million-row source.
    table = table.filter(pc.is_in(table["post_pt_root_id"], value_set=pa.array(engine_order)))
    if table["count"].null_count or pc.any(pc.less(table["count"], 0)).as_py():
        raise ValueError("invalid external input synapse count")
    grouped = table.group_by("post_pt_root_id").aggregate([("count", "sum")])
    del table
    index = pd.Index(engine_order)
    positions = index.get_indexer(grouped["post_pt_root_id"].to_numpy())
    denominator = np.zeros(engine_order.size, dtype=np.int64)
    present = np.zeros(engine_order.size, dtype=np.bool_)
    denominator[positions] = grouped["count_sum"].to_numpy()
    present[positions] = True
    numerator = np.zeros(engine_order.size, dtype=np.int64)
    for batch in parquet_file(connectivity_path).iter_batches(columns=["Presynaptic_ID", "Postsynaptic_ID", "Connectivity"]):
        pre, post, counts = (batch.column(i).to_numpy() for i in range(3))
        post_idx = index.get_indexer(post)
        keep = (index.get_indexer(pre) >= 0) & (post_idx >= 0)
        if np.any(counts[keep] < 0):
            raise ValueError("invalid in-model input synapse count")
        np.add.at(numerator, post_idx[keep], counts[keep])
    if np.any(numerator[present] > denominator[present]):
        raise ValueError("in-model inputs exceed the external input totals")
    return numerator, denominator, present
