"""Versioned connectome dataset adapters.

The numerical engine consumes one canonical neuron-order CSV and one canonical
edge parquet.  Adapters are the only code that knows a release's source paths
and column names.  FlyWire keeps its historical files unchanged; MaleCNS is
converted from the official v1.0 flat tables into the same engine boundary.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from flyonenomics.io import (
    exclusive_file_lock,
    hash_file,
    parquet_file,
    read_feather,
    read_json,
    read_parquet,
)
from flyonenomics.types import ConnectomeFiles, ProvenanceRecord

ConnectomeVersion = Literal["630", "783", "male-cns:v1.0"]
AnnotationVersion = Literal["v2.1.0", "v1.1.0", "male-cns:v1.0"]

MALE_VERSION = "male-cns:v1.0"
MALE_POLICY_VERSION = "male-cns-adapter-v3"
MALE_ENGINE_SOURCES = (
    "body-annotations-male-cns-v1.0-minconf-0.5.feather",
    "body-neurotransmitters-male-cns-v1.0.feather",
    "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
    "syn-partners-male-cns-v1.0-minconf-0.5.feather",
    "tbar-neurotransmitters-male-cns-v1.0.feather",
)
MALE_NT_SIGN = {
    "acetylcholine": 1,
    "dopamine": 1,
    "serotonin": 1,
    "octopamine": 1,
    "tyramine": 1,
    "gaba": -1,
    "glutamate": -1,
    "histamine": -1,
}

# Common names consumed by the current registry. Male-specific source fields
# remain alongside them in the canonical MaleCNS annotation table.
CANONICAL_ANNOTATION_COLUMNS: tuple[str, ...] = (
    "supervoxel_id", "root_id", "pos_x", "pos_y", "pos_z", "soma_x",
    "soma_y", "soma_z", "nucleus_id", "flow", "super_class",
    "cell_class", "cell_sub_class", "cell_type", "hemibrain_type",
    "ito_lee_hemilineage", "hartenstein_hemilineage", "morphology_group",
    "top_nt", "top_nt_conf", "known_nt", "known_nt_source", "side",
    "nerve", "vfb_id", "fbbt_id", "status",
)


def repo_root() -> Path:
    """Return the repository root. Units: none. Shapes: one path."""
    return Path(__file__).resolve().parents[2]


def cache_dir() -> Path:
    """Return the shared data cache. Units: none. Shapes: one path."""
    override = os.environ.get("FLYONENOMICS_CACHE_DIR", "").strip()
    return Path(override) if override else repo_root() / ".cache"


def _provenance_records() -> dict[str, ProvenanceRecord]:
    raw = read_json(repo_root() / "data" / "provenance.json")
    records = [ProvenanceRecord.model_validate(row) for row in raw["records"]]
    return {record.item: record for record in records}


def _cached_path(record: ProvenanceRecord) -> Path:
    if record.path is None:
        raise ValueError(f"provenance record has no path: {record.item}")
    relative = Path(record.path)
    if relative.parts and relative.parts[0] == ".cache":
        return cache_dir().joinpath(*relative.parts[1:])
    return repo_root() / relative


def _verified_record(item: str) -> Path:
    record = _provenance_records()[item]
    path = _cached_path(record)
    if record.status != "fetched" or record.sha256 is None:
        raise ValueError(f"cannot verify unfetched record: {item}")
    if hash_file(path) != record.sha256:
        raise ValueError(f"checksum mismatch: {path}")
    return path


class DatasetAdapter(ABC):
    """Interface between a released connectome and canonical project tables."""

    version: ConnectomeVersion

    @abstractmethod
    def connectome_files(self) -> ConnectomeFiles:
        """Return canonical engine-order and edge files."""

    @abstractmethod
    def load_annotations(self, annotation_version: str | None = None) -> pd.DataFrame:
        """Return canonical annotations, one row per released neuron."""

    @abstractmethod
    def load_engine_order(self) -> NDArray[np.int64]:
        """Return neuron IDs in canonical engine order."""

    @abstractmethod
    def load_connectivity_edges(self, presynaptic_roots: NDArray[np.int64] | None) -> pd.DataFrame:
        """Return canonical ID-level weighted edges."""

    def auxiliary_table_path(self, role: str) -> Path | None:
        """Return an optional release table by semantic role."""
        return None

    def roi_connectivity_path(self) -> Path | None:
        """Return a release's per-synapse ROI table, if present."""
        return self.auxiliary_table_path("roi_partners")

    def population_registry_path(self) -> Path | None:
        """Return the dataset-specific population registry, if one is required."""
        return None

    def compartment_table_path(self) -> Path | None:
        """Return the dataset-specific compartment table, if one is required."""
        return None

    def receptor_table_path(self) -> Path | None:
        """Return the dataset-specific receptor table, if one is required."""
        return None


class FlyWireAdapter(DatasetAdapter):
    """Adapter preserving the project's pinned Shiu/FlyWire files exactly."""

    _NAMES = {
        "630": ("2023_03_23_completeness_630_final.csv", "2023_03_23_connectivity_630_final.parquet"),
        "783": ("Completeness_783.csv", "Connectivity_783.parquet"),
    }
    _COMPLETENESS_ITEMS = {
        "630": "Shiu clone 2023_03_23_completeness_630_final.csv",
        "783": "Shiu clone Completeness_783.csv",
    }
    _CONNECTIVITY_ITEMS = {
        "630": "Shiu clone 2023_03_23_connectivity_630_final.parquet",
        "783": "Shiu clone Connectivity_783.parquet",
    }
    _ANNOTATION_ITEMS = {
        "v2.1.0": "annotations-v2.1.0.tsv",
        "v1.1.0": "annotations-v1.1.0.tsv",
    }

    def __init__(self, version: Literal["630", "783"]):
        self.version = version

    def connectome_files(self) -> ConnectomeFiles:
        root = cache_dir() / "Drosophila_brain_model"
        completeness, connectivity = self._NAMES[self.version]
        return ConnectomeFiles(root / completeness, root / connectivity, version=self.version)

    def load_annotations(self, annotation_version: str | None = None) -> pd.DataFrame:
        selected = annotation_version or "v2.1.0"
        if selected not in self._ANNOTATION_ITEMS:
            raise KeyError(selected)
        path = _verified_record(self._ANNOTATION_ITEMS[selected])
        frame = pd.read_csv(path, sep="\t", low_memory=False)
        absent = {"known_nt", "known_nt_source", "vfb_id", "fbbt_id"} if selected == "v1.1.0" else set()
        missing = [name for name in CANONICAL_ANNOTATION_COLUMNS if name not in absent and name not in frame.columns]
        if missing:
            raise KeyError(f"annotation {selected} is missing columns: {missing}")
        return frame

    def load_engine_order(self) -> NDArray[np.int64]:
        path = _verified_record(self._COMPLETENESS_ITEMS[self.version])
        return np.asarray(pd.read_csv(path).iloc[:, 0].to_numpy(), dtype=np.int64)

    def load_connectivity_edges(self, presynaptic_roots: NDArray[np.int64] | None) -> pd.DataFrame:
        path = _verified_record(self._CONNECTIVITY_ITEMS[self.version])
        columns = ["Presynaptic_ID", "Postsynaptic_ID", "Connectivity"]
        if presynaptic_roots is None:
            return parquet_file(path).read(columns=columns).to_pandas()
        wanted = [int(value) for value in presynaptic_roots]
        frame = read_parquet(path, columns=columns, filters=[("Presynaptic_ID", "in", wanted)]).to_pandas()
        if frame.empty:
            return pd.DataFrame({name: pd.Series(dtype="int64") for name in columns})
        return frame


class MaleCNSAdapter(DatasetAdapter):
    """MaleCNS v1.0 adapter with explicit node, edge, sign and side rules."""

    version: ConnectomeVersion = MALE_VERSION

    def _manifest(self) -> dict[str, object]:
        return read_json(repo_root() / "data" / "malecns-v1.0-manifest.json")

    def _source(self, name: str) -> Path:
        manifest = self._manifest()
        records = {row["name"]: row for row in manifest["files"]}  # type: ignore[index]
        row = records[name]
        path = cache_dir() / "malecns-v1.0" / name
        if path.stat().st_size != int(row["bytes"]) or hash_file(path) != row["sha256"]:
            raise ValueError(f"MaleCNS source checksum mismatch: {path}")
        return path

    def _derived_dir(self) -> Path:
        return cache_dir() / "malecns-v1.0" / "derived"

    def _derived_valid(self) -> bool:
        directory = self._derived_dir()
        metadata_path = directory / "provenance.json"
        if not metadata_path.is_file():
            return False
        metadata = read_json(metadata_path)
        manifest = self._manifest()
        if metadata.get("policy_version") != MALE_POLICY_VERSION:
            return False
        all_sources = {row["name"]: row["sha256"] for row in manifest["files"]}  # type: ignore[index]
        expected_sources = {name: all_sources[name] for name in MALE_ENGINE_SOURCES}
        if metadata.get("source_sha256") != expected_sources:
            return False
        # A cached conversion is valid only while every consumed source still
        # matches the release manifest. Auxiliary tables are verified on access.
        for name in MALE_ENGINE_SOURCES:
            self._source(name)
        expected_derived = {"annotations.feather", "engine-order.csv", "connectivity.parquet"}
        derived_sha256 = metadata.get("derived_sha256", {})
        if set(derived_sha256) != expected_derived:
            return False
        for name, digest in derived_sha256.items():
            path = directory / name
            if not path.is_file() or hash_file(path) != digest:
                return False
        return True

    def ensure_derived(self) -> None:
        """Create canonical annotation, order and signed-edge tables atomically."""
        directory = self._derived_dir()
        directory.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(directory / "build.lock"):
            if self._derived_valid():
                return
            result = subprocess.run(
                [sys.executable, "-m", "flyonenomics.datasets", "build-male"],
                env=os.environ.copy(), capture_output=True, text=True, check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                raise RuntimeError(f"MaleCNS conversion child failed ({result.returncode}): {detail}")
            if not self._derived_valid():
                raise RuntimeError("MaleCNS conversion child did not produce verified tables")

    def _unknown_neuron_signs(
        self,
        unknown_roots: NDArray[np.int64],
        retained_roots: NDArray[np.int64],
    ) -> tuple[dict[int, int], dict[str, int]]:
        """Derive signs for unknown-consensus neurons from T-bar predictions.

        FlyWire first takes the largest transmitter probability at each
        presynaptic site, then calls a neuron inhibitory only when more than
        half of all its sites are GABAergic or glutamatergic. MaleCNS applies
        that same per-neuron rule. The partner table is scanned only to audit
        how this rule differs from the superseded per-directed-pair rule.
        """
        import pyarrow as pa
        import pyarrow.ipc as ipc

        unknown = np.sort(np.asarray(unknown_roots, dtype=np.int64))
        retained = np.sort(np.asarray(retained_roots, dtype=np.int64))
        probability_columns = (
            "nt_acetylcholine_prob", "nt_dopamine_prob", "nt_gaba_prob",
            "nt_glutamate_prob", "nt_histamine_prob", "nt_octopamine_prob",
            "nt_serotonin_prob",
        )

        def membership(sorted_values: NDArray[np.int64], values: NDArray[np.int64]) -> NDArray[np.bool_]:
            positions = np.searchsorted(sorted_values, values)
            found = positions < sorted_values.size
            result = np.zeros(values.size, dtype=bool)
            result[found] = sorted_values[positions[found]] == values[found]
            return result

        def coordinate_keys(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> NDArray[np.uint64]:
            # MaleCNS coordinates are non-negative int32 values below 2**21.
            # Packing makes the 311-million-row partner join bounded in memory.
            limit = 1 << 21
            if any(np.any((axis < 0) | (axis >= limit)) for axis in (x, y, z)):
                raise ValueError("MaleCNS T-bar coordinate is outside the 21-bit join range")
            return (
                (x.astype(np.uint64) << np.uint64(42))
                | (y.astype(np.uint64) << np.uint64(21))
                | z.astype(np.uint64)
            )

        tbar_path = self._source("tbar-neurotransmitters-male-cns-v1.0.feather")
        site_signs: dict[int, int] = {}
        neuron_totals: dict[int, int] = {}
        neuron_inhibitory: dict[int, int] = {}
        with pa.memory_map(str(tbar_path), "r") as mapped:
            reader = ipc.open_file(mapped)
            indices = {name: reader.schema.get_field_index(name) for name in (
                "body", "x", "y", "z", *probability_columns,
            )}
            for batch_number in range(reader.num_record_batches):
                batch = reader.get_batch(batch_number)
                bodies = batch.column(indices["body"]).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
                keep = membership(unknown, bodies)
                if not keep.any():
                    continue
                x = batch.column(indices["x"]).to_numpy(zero_copy_only=False)[keep]
                y = batch.column(indices["y"]).to_numpy(zero_copy_only=False)[keep]
                z = batch.column(indices["z"]).to_numpy(zero_copy_only=False)[keep]
                probabilities = np.column_stack([
                    batch.column(indices[name]).to_numpy(zero_copy_only=False)[keep]
                    for name in probability_columns
                ])
                winner = np.argmax(probabilities, axis=1)
                # FlyWire's pinned site rule treats only GABA and glutamate as inhibitory.
                signs = np.where(np.isin(winner, (2, 3)), -1, 1).astype(np.int8)
                kept_bodies = bodies[keep]
                unique_bodies, total_counts = np.unique(kept_bodies, return_counts=True)
                inhibitory_bodies, inhibitory_counts = np.unique(
                    kept_bodies[signs < 0], return_counts=True
                )
                for body, count in zip(unique_bodies.tolist(), total_counts.tolist()):
                    neuron_totals[int(body)] = neuron_totals.get(int(body), 0) + int(count)
                for body, count in zip(inhibitory_bodies.tolist(), inhibitory_counts.tolist()):
                    neuron_inhibitory[int(body)] = neuron_inhibitory.get(int(body), 0) + int(count)
                keys = coordinate_keys(x, y, z)
                for key, sign in zip(keys.tolist(), signs.tolist()):
                    previous = site_signs.setdefault(int(key), int(sign))
                    if previous != sign:
                        raise ValueError(f"conflicting predictions for MaleCNS T-bar coordinate {key}")

        neuron_signs = {
            body: (-1 if 2 * neuron_inhibitory.get(body, 0) > total else 1)
            for body, total in neuron_totals.items()
        }

        partner_path = self._source("syn-partners-male-cns-v1.0-minconf-0.5.feather")
        totals: dict[tuple[int, int], int] = {}
        inhibitory: dict[tuple[int, int], int] = {}
        joined_rows = 0
        with pa.memory_map(str(partner_path), "r") as mapped:
            reader = ipc.open_file(mapped)
            indices = {name: reader.schema.get_field_index(name) for name in (
                "body_pre", "body_post", "x_pre", "y_pre", "z_pre",
            )}
            for batch_number in range(reader.num_record_batches):
                batch = reader.get_batch(batch_number)
                pre = batch.column(indices["body_pre"]).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
                post = batch.column(indices["body_post"]).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
                keep = membership(unknown, pre) & membership(retained, post)
                if not keep.any():
                    continue
                x = batch.column(indices["x_pre"]).to_numpy(zero_copy_only=False)[keep]
                y = batch.column(indices["y_pre"]).to_numpy(zero_copy_only=False)[keep]
                z = batch.column(indices["z_pre"]).to_numpy(zero_copy_only=False)[keep]
                keys = coordinate_keys(x, y, z)
                try:
                    signs = [site_signs[int(key)] for key in keys]
                except KeyError as exc:
                    raise ValueError(f"MaleCNS partner has no T-bar transmitter prediction: {exc.args[0]}") from exc
                for source, target, sign in zip(pre[keep].tolist(), post[keep].tolist(), signs):
                    pair = (int(source), int(target))
                    totals[pair] = totals.get(pair, 0) + 1
                    if sign < 0:
                        inhibitory[pair] = inhibitory.get(pair, 0) + 1
                joined_rows += int(keep.sum())

        pair_signs = {
            pair: (-1 if 2 * inhibitory.get(pair, 0) > total else 1)
            for pair, total in totals.items()
        }
        missing_pair_neurons = sorted(
            {source for source, _target in pair_signs} - set(neuron_signs)
        )
        if missing_pair_neurons:
            raise ValueError(
                "unknown-consensus MaleCNS neurons with retained output have no T-bar "
                f"prediction: {missing_pair_neurons[:5]}"
            )
        mixed_pair_neurons: dict[int, set[int]] = {}
        changed_pairs = 0
        for (source, _target), pair_sign in pair_signs.items():
            mixed_pair_neurons.setdefault(source, set()).add(pair_sign)
            changed_pairs += int(pair_sign != neuron_signs[source])
        metrics = {
            "unknown_consensus_neurons": int(unknown.size),
            "unknown_tbar_sites": len(site_signs),
            "unknown_neurons_without_tbars": int(unknown.size - len(neuron_signs)),
            "unknown_neurons_positive": sum(sign > 0 for sign in neuron_signs.values()),
            "unknown_neurons_negative": sum(sign < 0 for sign in neuron_signs.values()),
            "unknown_partner_rows": joined_rows,
            "unknown_neurons_with_connections": len(mixed_pair_neurons),
            "unknown_connections": len(pair_signs),
            "connections_changed_from_superseded_pair_rule": changed_pairs,
            "neurons_mixed_under_superseded_pair_rule": sum(
                len(pair_polarities) > 1 for pair_polarities in mixed_pair_neurons.values()
            ),
        }
        return neuron_signs, metrics

    def _build_derived(self, directory: Path) -> None:
        import pyarrow as pa
        import pyarrow.feather as feather
        import pyarrow.ipc as ipc
        import pyarrow.parquet as pq

        annotations_path = self._source("body-annotations-male-cns-v1.0-minconf-0.5.feather")
        transmitters_path = self._source("body-neurotransmitters-male-cns-v1.0.feather")
        connections_path = self._source("connectome-weights-male-cns-v1.0-minconf-0.5.feather")
        annotations = read_feather(annotations_path).to_pandas()
        transmitters = read_feather(transmitters_path).to_pandas()
        nodes = annotations.loc[(annotations["status"] == "Traced") & annotations["type"].notna()].copy()
        nodes = nodes.merge(
            transmitters[[
                "body", "consensus_nt", "ground_truth", "predicted_nt_confidence",
                "celltype_predicted_nt_confidence",
            ]],
            left_on="bodyId", right_on="body", how="left", validate="one_to_one",
        )
        roots = nodes["bodyId"].to_numpy(dtype=np.int64)
        soma = nodes["somaLocation"]
        side = nodes["somaSide"].fillna(nodes["rootSide"]).map({"L": "left", "R": "right"})
        canonical = pd.DataFrame(index=nodes.index)
        for column in CANONICAL_ANNOTATION_COLUMNS:
            canonical[column] = pd.NA
        canonical["root_id"] = roots
        canonical["soma_x"] = soma.map(lambda value: value[0] if isinstance(value, (list, np.ndarray)) and len(value) == 3 else pd.NA)
        canonical["soma_y"] = soma.map(lambda value: value[1] if isinstance(value, (list, np.ndarray)) and len(value) == 3 else pd.NA)
        canonical["soma_z"] = soma.map(lambda value: value[2] if isinstance(value, (list, np.ndarray)) and len(value) == 3 else pd.NA)
        canonical["super_class"] = nodes["superclass"].to_numpy()
        canonical["cell_class"] = nodes["class"].to_numpy()
        canonical["cell_sub_class"] = nodes["subclass"].to_numpy()
        canonical["cell_type"] = nodes["flywireType"].to_numpy()
        canonical["hemibrain_type"] = nodes["type"].to_numpy()
        canonical["ito_lee_hemilineage"] = nodes["itoleeHl"].to_numpy()
        canonical["hartenstein_hemilineage"] = nodes["trumanHl"].to_numpy()
        canonical["top_nt"] = nodes["consensus_nt"].to_numpy()
        # consensus_nt is an official reconciled label and has no scalar confidence.
        canonical["top_nt_conf"] = np.nan
        canonical["known_nt"] = nodes["ground_truth"].to_numpy()
        canonical["known_nt_source"] = np.where(nodes["ground_truth"].notna(), "MaleCNS ground_truth", pd.NA)
        canonical["side"] = side.to_numpy()
        canonical["nerve"] = nodes["entryNerve"].fillna(nodes["exitNerve"]).to_numpy()
        canonical["vfb_id"] = nodes["vfbId"].to_numpy()
        canonical["status"] = nodes["status"].to_numpy()
        for source_name in (
            "bodyId", "type", "flywireType", "somaSide", "rootSide",
            "assignedOlHex1", "assignedOlHex2", "consensus_nt", "ground_truth",
            "predicted_nt_confidence", "celltype_predicted_nt_confidence",
        ):
            canonical[source_name] = nodes[source_name].to_numpy()
        canonical = canonical.reset_index(drop=True)

        annotation_tmp = directory / "annotations.feather.tmp"
        feather.write_feather(pa.Table.from_pandas(canonical, preserve_index=False), annotation_tmp)
        annotation_tmp.replace(directory / "annotations.feather")
        order_tmp = directory / "engine-order.csv.tmp"
        pd.DataFrame({"root_id": roots}).to_csv(order_tmp, index=False)
        order_tmp.replace(directory / "engine-order.csv")

        signs = nodes["consensus_nt"].astype("string").str.lower().map(MALE_NT_SIGN).fillna(0).to_numpy(dtype=np.int8)
        unknown_roots = roots[signs == 0]
        unknown_neuron_signs, unknown_metrics = self._unknown_neuron_signs(unknown_roots, roots)
        sorted_positions = np.argsort(roots)
        sorted_roots = roots[sorted_positions]
        edge_path = directory / "connectivity.parquet"
        edge_tmp = directory / "connectivity.parquet.tmp"
        schema = pa.schema([
            ("Presynaptic_ID", pa.int64()), ("Postsynaptic_ID", pa.int64()),
            ("Connectivity", pa.int64()), ("Presynaptic_Index", pa.int32()),
            ("Postsynaptic_Index", pa.int32()), ("Excitatory x Connectivity", pa.float64()),
        ])
        writer = pq.ParquetWriter(edge_tmp, schema, compression="zstd")
        edge_rows = 0
        nonzero_rows = 0
        zero_rows = 0
        synapses = 0
        before_edge_rows = 0
        before_nonzero_rows = 0
        before_zero_rows = 0
        before_synapses = 0
        with pa.memory_map(str(connections_path), "r") as mapped:
            reader = ipc.open_file(mapped)
            for batch_number in range(reader.num_record_batches):
                batch = reader.get_batch(batch_number)
                pre_id = batch.column("body_pre").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
                post_id = batch.column("body_post").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
                weight = batch.column("weight").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
                pre_sorted = np.searchsorted(sorted_roots, pre_id)
                post_sorted = np.searchsorted(sorted_roots, post_id)
                pre_ok = pre_sorted < sorted_roots.size
                post_ok = post_sorted < sorted_roots.size
                pre_match = np.zeros(pre_id.size, dtype=bool)
                post_match = np.zeros(post_id.size, dtype=bool)
                pre_match[pre_ok] = sorted_roots[pre_sorted[pre_ok]] == pre_id[pre_ok]
                post_match[post_ok] = sorted_roots[post_sorted[post_ok]] == post_id[post_ok]
                keep = pre_match & post_match
                if not keep.any():
                    continue
                kept_pre_id = pre_id[keep]
                kept_post_id = post_id[keep]
                pre = sorted_positions[pre_sorted[keep]].astype(np.int32, copy=False)
                post = sorted_positions[post_sorted[keep]].astype(np.int32, copy=False)
                counts = weight[keep]
                edge_signs = signs[pre].copy()
                unresolved = edge_signs == 0
                if unresolved.any():
                    try:
                        edge_signs[unresolved] = np.fromiter(
                            (unknown_neuron_signs[int(source)] for source in kept_pre_id[unresolved]),
                            dtype=np.int8,
                            count=int(unresolved.sum()),
                        )
                    except KeyError as exc:
                        raise ValueError(
                            f"unknown-consensus MaleCNS neuron has no derived sign: {exc.args[0]}"
                        ) from exc
                signed = counts.astype(np.float64) * edge_signs
                table = pa.Table.from_arrays(
                    [kept_pre_id, kept_post_id, counts, pre, post, signed], schema=schema
                )
                writer.write_table(table)
                edge_rows += len(pre)
                nonzero_rows += int(np.count_nonzero(signed))
                zero_rows += int(np.count_nonzero(signed == 0))
                synapses += int(counts.sum())
                before = counts >= 5
                before_edge_rows += int(before.sum())
                before_signed = signed[before]
                # Step 1 zeroed unknown-consensus rows rather than applying
                # their now-derived connection signs.
                before_nonzero_rows += int(np.count_nonzero(before_signed) - np.count_nonzero(unresolved[before]))
                before_zero_rows += int(np.count_nonzero(unresolved[before]))
                before_synapses += int(counts[before].sum())
        writer.close()
        edge_tmp.replace(edge_path)

        derived = ("annotations.feather", "engine-order.csv", "connectivity.parquet")
        manifest = self._manifest()
        metadata = {
            "dataset": MALE_VERSION,
            "policy_version": MALE_POLICY_VERSION,
            "license": "CC BY 4.0",
            "attribution": manifest["attribution"],
            "node_rule": "status == Traced and type is non-null",
            "edge_rule": "both endpoints are retained; every globally aggregated directed pair is kept with no weight cut",
            "confidence_rule": "official minconf-0.5 source tables; no second threshold on official consensus_nt",
            "sign_rule": "presynaptic consensus_nt under the Shiu/FlyWire polarity convention, including positive tyramine",
            "unknown_transmitter_rule": (
                "for each unclear/missing-consensus neuron, take the largest probability at every "
                "released T-bar and use a negative sign for all its output only when more than half "
                "of all its sites are GABA or glutamate; ties are positive"
            ),
            "laterality_rule": "somaSide, then rootSide; L/R become left/right and missing stays missing",
            "nodes": int(roots.size),
            "edges": edge_rows,
            "edges_nonzero_signed": nonzero_rows,
            "edges_zero_weight": zero_rows,
            "synapses": synapses,
            "step1_before_counts": {
                "edges": before_edge_rows,
                "edges_nonzero_signed": before_nonzero_rows,
                "edges_zero_weight": before_zero_rows,
                "synapses": before_synapses,
            },
            "item150_after_counts": {
                "edges": edge_rows,
                "edges_nonzero_signed": nonzero_rows,
                "edges_zero_weight": zero_rows,
                "synapses": synapses,
            },
            "unknown_neuron_signs": unknown_metrics,
            "source_sha256": {
                row["name"]: row["sha256"]
                for row in manifest["files"] if row["name"] in MALE_ENGINE_SOURCES
            },
            "available_source_sha256": {
                row["name"]: row["sha256"] for row in manifest["files"]
            },
            "derived_sha256": {name: hash_file(directory / name) for name in derived},
        }
        metadata_tmp = directory / "provenance.json.tmp"
        metadata_tmp.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        metadata_tmp.replace(directory / "provenance.json")

    def connectome_files(self) -> ConnectomeFiles:
        self.ensure_derived()
        directory = self._derived_dir()
        return ConnectomeFiles(
            directory / "engine-order.csv", directory / "connectivity.parquet", version=MALE_VERSION
        )

    def load_annotations(self, annotation_version: str | None = None) -> pd.DataFrame:
        if annotation_version not in (None, MALE_VERSION):
            raise ValueError(f"MaleCNS does not provide annotation version {annotation_version}")
        self.ensure_derived()
        return read_feather(self._derived_dir() / "annotations.feather").to_pandas()

    def load_engine_order(self) -> NDArray[np.int64]:
        self.ensure_derived()
        return pd.read_csv(self._derived_dir() / "engine-order.csv")["root_id"].to_numpy(dtype=np.int64)

    def load_connectivity_edges(self, presynaptic_roots: NDArray[np.int64] | None) -> pd.DataFrame:
        self.ensure_derived()
        path = self._derived_dir() / "connectivity.parquet"
        columns = ["Presynaptic_ID", "Postsynaptic_ID", "Connectivity"]
        if presynaptic_roots is None:
            return parquet_file(path).read(columns=columns).to_pandas()
        wanted = [int(value) for value in presynaptic_roots]
        frame = read_parquet(path, columns=columns, filters=[("Presynaptic_ID", "in", wanted)]).to_pandas()
        if frame.empty:
            return pd.DataFrame({name: pd.Series(dtype="int64") for name in columns})
        return frame

    def population_registry_path(self) -> Path | None:
        """Return the MaleCNS registry; FlyWire registries must never be selected."""
        return repo_root() / "data" / "populations-male-cns-v1.0.yaml"

    def compartment_table_path(self) -> Path | None:
        """Return the MaleCNS compartment table."""
        return repo_root() / "data" / "compartments-male-cns-v1.0.yaml"

    def receptor_table_path(self) -> Path | None:
        """Return the MaleCNS receptor table."""
        return repo_root() / "data" / "receptors-male-cns-v1.0.yaml"

    def auxiliary_table_path(self, role: str) -> Path | None:
        names = {
            "body_stats": "body-stats-male-cns-v1.0-minconf-0.5.feather",
            "roi_partners": "syn-partners-male-cns-v1.0-minconf-0.5.feather",
            "synapse_points": "syn-points-male-cns-v1.0-minconf-0.5.feather",
            "tbar_transmitters": "tbar-neurotransmitters-male-cns-v1.0.feather",
        }
        name = names.get(role)
        return None if name is None else self._source(name)


def get_dataset_adapter(version: str) -> DatasetAdapter:
    """Return the one adapter registered for a first-class connectome version."""
    if version in ("630", "783"):
        return FlyWireAdapter(version)  # type: ignore[arg-type]
    if version == MALE_VERSION:
        return MaleCNSAdapter()
    raise KeyError(f"unknown connectome version: {version}")


def main(argv: list[str] | None = None) -> int:
    """Run the short-lived MaleCNS conversion child."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args != ["build-male"]:
        raise SystemExit("usage: python -m flyonenomics.datasets build-male")
    adapter = MaleCNSAdapter()
    directory = adapter._derived_dir()
    directory.mkdir(parents=True, exist_ok=True)
    adapter._build_derived(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
