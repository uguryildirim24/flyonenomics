#!/usr/bin/env python3
"""Build the versioned MaleCNS-to-flyvis eye-column assignment.

This is a data conversion, not a visual response or calibration.  It reads the
released MaleCNS v1.0 annotation and aggregate connection tables directly.  All
aggregated pairs whose endpoints are typed, traced neurons are eligible; there
is no connection-weight cut.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json
import math
import os

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.feather as feather
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

from flyonenomics.io import hash_file, read_json

ROOT = Path(__file__).resolve().parents[1]
CACHE_NAMES = {
    "annotations": "body-annotations-male-cns-v1.0-minconf-0.5.feather",
    "connections": "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
}
FLYVIS_TYPES = (
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
    "L1", "L2", "L3", "L4", "L5", "Lawf1", "Lawf2", "Am", "C2", "C3",
    "CT1(Lo1)", "CT1(M10)", "Mi1", "Mi2", "Mi3", "Mi4", "Mi9", "Mi10",
    "Mi11", "Mi12", "Mi13", "Mi14", "Mi15", "T1", "T2", "T2a", "T3",
    "T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d", "Tm1",
    "Tm2", "Tm3", "Tm4", "Tm5Y", "Tm5a", "Tm5b", "Tm5c", "Tm9", "Tm16",
    "Tm20", "Tm28", "Tm30", "TmY3", "TmY4", "TmY5a", "TmY9", "TmY10",
    "TmY13", "TmY14", "TmY15", "TmY18",
)
T4T5 = ("T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d")
R1_R6 = ("R1", "R2", "R3", "R4", "R5", "R6")
CT1_TYPES = ("CT1(Lo1)", "CT1(M10)")
EXACT_TYPES = set(FLYVIS_TYPES) - set(R1_R6) - {"R7", "R8", *CT1_TYPES}
LATTICE = {
    (u, v)
    for u in range(-15, 16)
    for v in range(max(-15, -15 - u), min(15, 15 - u) + 1)
}


@dataclass(frozen=True)
class Evidence:
    hex1: int
    hex2: int
    winner_weight: int
    eligible_weight: int
    top_tie_count: int


def sha256(path: Path) -> str:
    return hash_file(path)


def cache_root() -> Path:
    base = Path(os.environ.get("FLYONENOMICS_CACHE_DIR", ROOT / ".cache"))
    return base / "malecns-v1.0"


def alias(male_type: str) -> tuple[str | None, str | None]:
    """Return a concrete flyvis type or a shared unresolved identity label."""
    if male_type in EXACT_TYPES:
        return male_type, None
    if male_type.startswith("R7"):
        return "R7", None
    if male_type.startswith("R8"):
        return "R8", None
    if male_type == "R1-R6":
        return "R1-R6", "shared_R1_R6_identity"
    if male_type == "CT1":
        return "CT1", "shared_CT1_compartment_identity"
    return None, "not_in_flyvis_65_type_set"


def _node_positions(ids: np.ndarray, sorted_roots: np.ndarray, order: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pos = np.searchsorted(sorted_roots, ids)
    valid = pos < sorted_roots.size
    matched = np.zeros(ids.size, dtype=bool)
    matched[valid] = sorted_roots[pos[valid]] == ids[valid]
    result = np.full(ids.size, -1, dtype=np.int32)
    result[matched] = order[pos[matched]].astype(np.int32, copy=False)
    return result, matched


def collect_evidence(
    connections: Path,
    roots: np.ndarray,
    candidate: np.ndarray,
    has_direct: np.ndarray,
    direct_h1: np.ndarray,
    direct_h2: np.ndarray,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Aggregate labelled-partner evidence over every retained directed pair."""
    order = np.argsort(roots)
    sorted_roots = roots[order]
    incoming: list[pd.DataFrame] = []
    outgoing: list[pd.DataFrame] = []
    source_rows = retained_rows = 0
    source_weight = retained_weight = 0
    with pa.memory_map(str(connections), "r") as mapped:
        reader = ipc.open_file(mapped)
        for batch_number in range(reader.num_record_batches):
            batch = reader.get_batch(batch_number)
            pre_id = batch.column("body_pre").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
            post_id = batch.column("body_post").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
            weight = batch.column("weight").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
            source_rows += weight.size
            source_weight += int(weight.sum())
            pre, pre_ok = _node_positions(pre_id, sorted_roots, order)
            post, post_ok = _node_positions(post_id, sorted_roots, order)
            retained = pre_ok & post_ok
            retained_rows += int(retained.sum())
            retained_weight += int(weight[retained].sum())

            for me, partner, mask, target in (
                (post, pre, retained & candidate[post.clip(min=0)] & has_direct[pre.clip(min=0)], incoming),
                (pre, post, retained & candidate[pre.clip(min=0)] & has_direct[post.clip(min=0)], outgoing),
            ):
                if not mask.any():
                    continue
                frame = pd.DataFrame({
                    "idx": me[mask],
                    "hex1": direct_h1[partner[mask]].astype(np.int16, copy=False),
                    "hex2": direct_h2[partner[mask]].astype(np.int16, copy=False),
                    "weight": weight[mask],
                })
                target.append(frame.groupby(["idx", "hex1", "hex2"], as_index=False, sort=False).weight.sum())

    def finish(parts: list[pd.DataFrame]) -> pd.DataFrame:
        if not parts:
            return pd.DataFrame(columns=["idx", "hex1", "hex2", "weight"])
        return pd.concat(parts, ignore_index=True).groupby(
            ["idx", "hex1", "hex2"], as_index=False, sort=False
        ).weight.sum()

    return finish(incoming), finish(outgoing), {
        "source_aggregate_pairs": source_rows,
        "source_synapses": source_weight,
        "retained_aggregate_pairs": retained_rows,
        "retained_synapses": retained_weight,
        "minimum_weight": 1,
    }


def pick_evidence(grouped: pd.DataFrame) -> dict[int, Evidence]:
    if grouped.empty:
        return {}
    totals = grouped.groupby("idx", sort=False).weight.sum()
    maximum = grouped.groupby("idx", sort=False).weight.max()
    selected = grouped.sort_values(
        ["idx", "weight", "hex1", "hex2"],
        ascending=[True, False, True, True],
        kind="mergesort",
    ).drop_duplicates("idx")
    ties = grouped.join(maximum.rename("maximum"), on="idx")
    tie_counts = ties.loc[ties.weight == ties.maximum].groupby("idx").size()
    return {
        int(row.idx): Evidence(
            int(row.hex1), int(row.hex2), int(row.weight),
            int(totals.loc[row.idx]), int(tie_counts.loc[row.idx]),
        )
        for row in selected.itertuples()
    }


def dra_vectors(
    nodes: pd.DataFrame,
    outgoing: dict[int, Evidence],
) -> dict[str, tuple[float, float]]:
    side = nodes.somaSide.fillna(nodes.rootSide).fillna("").astype(str).to_numpy()
    typ = nodes.type.astype(str).to_numpy()
    points: dict[str, list[tuple[int, int]]] = {"left": [], "right": []}
    for idx in np.flatnonzero(np.isin(typ, ["R7d", "R8d"])):
        evidence = outgoing.get(int(idx))
        eye = {"L": "left", "R": "right"}.get(side[idx])
        if evidence is not None and eye is not None:
            points[eye].append((evidence.hex1, evidence.hex2))
    return {
        eye: (float(np.mean([p[0] for p in values])), float(np.mean([p[1] for p in values])))
        for eye, values in points.items() if values
    }


def transform_columns(assignments: pd.DataFrame, dra: dict[str, tuple[float, float]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply the outcome-blind DRA/centroid transform proposed by the feasibility review."""
    result = assignments.copy()
    result["flyvis_u"] = pd.Series(pd.NA, index=result.index, dtype="Int16")
    result["flyvis_v"] = pd.Series(pd.NA, index=result.index, dtype="Int16")
    transforms: dict[str, Any] = {}
    motion = result[
        result.flyvis_type.isin(T4T5) & result.hex1.notna() & result.hex2.notna()
    ]
    for eye in ("left", "right"):
        physical = motion.loc[motion.eye == eye, ["hex1", "hex2"]].drop_duplicates()
        if physical.empty or eye not in dra:
            continue
        h1 = physical.hex1.to_numpy(dtype=float)
        h2 = physical.hex2.to_numpy(dtype=float)
        x = h1 - h2 / 2.0
        y = -h2 * math.sqrt(3.0) / 2.0
        cx, cy = float(x.mean()), float(y.mean())
        dh1, dh2 = dra[eye]
        dx = dh1 - dh2 / 2.0
        dy = -dh2 * math.sqrt(3.0) / 2.0
        vector = np.asarray([dx - cx, dy - cy], dtype=float)
        vector /= np.linalg.norm(vector)
        rotation = math.pi / 2.0 - math.atan2(vector[1], vector[0])

        mask = (result.eye == eye) & result.hex1.notna() & result.hex2.notna()
        rh1 = result.loc[mask, "hex1"].to_numpy(dtype=float)
        rh2 = result.loc[mask, "hex2"].to_numpy(dtype=float)
        rx = rh1 - rh2 / 2.0 - cx
        ry = -rh2 * math.sqrt(3.0) / 2.0 - cy
        sy = rx * math.sin(rotation) + ry * math.cos(rotation)
        sx = -(rx * math.cos(rotation) - ry * math.sin(rotation))
        v = np.rint(sx).astype(np.int16)
        u = np.rint(-sy - v / 2.0).astype(np.int16)
        result.loc[mask, "flyvis_u"] = u
        result.loc[mask, "flyvis_v"] = v

        px, py = x - cx, y - cy
        pv = np.rint(-(px * math.cos(rotation) - py * math.sin(rotation))).astype(int)
        psy = px * math.sin(rotation) + py * math.cos(rotation)
        pu = np.rint(-psy - pv / 2.0).astype(int)
        transformed = set(zip(pu.tolist(), pv.tolist()))
        native = set(zip(h1.astype(int).tolist(), h2.astype(int).tolist()))
        inside_native_count = sum(uv in LATTICE for uv in zip(pu.tolist(), pv.tolist()))
        inside = transformed & LATTICE
        nearest = physical.assign(distance=(x - cx) ** 2 + (y - cy) ** 2).sort_values(
            ["distance", "hex1", "hex2"], kind="mergesort"
        ).iloc[0]
        transforms[eye] = {
            "native_motion_columns": len(native),
            "native_motion_columns_mapped_inside_721_lattice": inside_native_count,
            "distinct_transformed_motion_positions": len(transformed),
            "distinct_transformed_positions_inside_721_lattice": len(inside),
            "centroid_xy": [cx, cy],
            "reference_native_column_nearest_centroid": [int(nearest.hex1), int(nearest.hex2)],
            "dra_mean_native_hex": [dh1, dh2],
            "rotation_radians": rotation,
            "front_sign": -1,
            "handedness": "same axial formula in each eye; the left eye is not mirrored",
        }
    return result, transforms


def expected_slots(flyvis_type: str) -> set[tuple[int, int]]:
    if flyvis_type in {"Lawf1", "Lawf2"}:
        return {(u, v) for u, v in LATTICE if u % 3 == 0 and v % 2 == 0}
    return LATTICE


def finalise_rows(rows: pd.DataFrame) -> pd.DataFrame:
    concrete = rows.flyvis_type.isin(FLYVIS_TYPES)
    inside = pd.Series(False, index=rows.index)
    for flyvis_type in FLYVIS_TYPES:
        mask = concrete & rows.flyvis_type.eq(flyvis_type) & rows.flyvis_u.notna() & rows.flyvis_v.notna()
        if not mask.any():
            continue
        allowed = expected_slots(flyvis_type)
        inside.loc[mask] = [
            (int(u), int(v)) in allowed
            for u, v in zip(rows.loc[mask, "flyvis_u"], rows.loc[mask, "flyvis_v"])
        ]
    rows["inside_type_lattice"] = inside

    usable = concrete & inside
    native_count = rows.loc[concrete & rows.hex1.notna()].groupby(
        ["flyvis_type", "eye", "hex1", "hex2"], dropna=False
    ).male_body_id.transform("size")
    rows["native_collision_count"] = pd.Series(0, index=rows.index, dtype="int32")
    rows.loc[native_count.index, "native_collision_count"] = native_count.astype("int32")
    mapped_count = rows.loc[usable].groupby(
        ["flyvis_type", "eye", "flyvis_u", "flyvis_v"], dropna=False
    ).male_body_id.transform("size")
    rows["collision_count"] = pd.Series(0, index=rows.index, dtype="int32")
    rows.loc[mapped_count.index, "collision_count"] = mapped_count.astype("int32")

    unresolved = []
    for row in rows.itertuples():
        if pd.notna(row.alias_problem):
            reason = row.alias_problem
        elif row.eye not in {"left", "right"}:
            reason = "eye_side_missing"
        elif pd.isna(row.method):
            reason = "no_direct_or_hex_labelled_wiring_partner"
        elif row.top_tie_count > 1:
            reason = "top_coordinate_tie"
        elif not row.inside_type_lattice:
            reason = "outside_proposed_flyvis_type_lattice"
        elif row.collision_count != 1:
            reason = "transformed_slot_collision"
        else:
            reason = None
        unresolved.append(reason)
    rows["unresolved"] = [reason is not None for reason in unresolved]
    rows["unresolved_reason"] = unresolved
    rows.drop(columns=["alias_problem"], inplace=True)
    return rows


def summarise(rows: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary: list[dict[str, Any]] = []
    motion: list[dict[str, Any]] = []
    for flyvis_type in FLYVIS_TYPES:
        aliases = [flyvis_type]
        if flyvis_type in R1_R6:
            aliases = ["R1-R6"]
        elif flyvis_type in CT1_TYPES:
            aliases = ["CT1"]
        for eye in ("left", "right"):
            subset = rows[rows.flyvis_type.isin(aliases) & rows.eye.eq(eye)]
            concrete = subset[subset.flyvis_type.eq(flyvis_type)]
            unique = concrete.loc[~concrete.unresolved, ["flyvis_u", "flyvis_v"]].drop_duplicates()
            colliding = concrete[
                concrete.inside_type_lattice & concrete.collision_count.ne(1)
            ]
            expected = len(expected_slots(flyvis_type))
            row = {
                "flyvis_type": flyvis_type,
                "eye": eye,
                "flyvis_slots": expected,
                "male_candidates": int(len(subset)),
                "direct_male_cells": int(subset.method.eq("direct").sum()),
                "inferred_male_cells": int(subset.method.eq("wiring-inferred").sum()),
                "unique_drivable_slots": int(len(unique)),
                "colliding_male_cells": int(len(colliding)),
                "colliding_slots": int(colliding[["flyvis_u", "flyvis_v"]].drop_duplicates().shape[0]),
                "unresolved_male_cells": int(subset.unresolved.sum()),
                "unresolved_flyvis_slots": expected - int(len(unique)),
                "drivable_fraction": len(unique) / expected,
            }
            summary.append(row)
            if flyvis_type in T4T5:
                motion.append(row.copy())
    return summary, motion


def baseline_changes(summary: list[dict[str, Any]]) -> dict[str, Any]:
    path = ROOT / "validation" / "records" / "p2" / "malecns-feasibility.json"
    if not path.is_file():
        return {}
    old = read_json(path)["eye_columns"]
    current = {(r["flyvis_type"], r["eye"]): r["unique_drivable_slots"] for r in summary}
    old_per = old["per_type"]
    totals = {"left": 0, "right": 0, "both": 0}
    changes: dict[str, Any] = {}
    rows = []
    for flyvis_type in FLYVIS_TYPES:
        left = current[(flyvis_type, "left")]
        right = current[(flyvis_type, "right")]
        old_left = int(old_per[flyvis_type]["unique_left"])
        old_right = int(old_per[flyvis_type]["unique_right"])
        totals["left"] += left
        totals["right"] += right
        # Bilateral is recomputed by callers from the artifact; retain the old
        # figure only in the comparison block to avoid pretending cell identity.
        rows.append({
            "flyvis_type": flyvis_type,
            "left_before": old_left, "left_after": left, "left_change": left - old_left,
            "right_before": old_right, "right_after": right, "right_change": right - old_right,
        })
    before = old["unique_matches"]
    changes["totals"] = {
        "left_before": int(before["left"]), "left_after": totals["left"],
        "left_change": totals["left"] - int(before["left"]),
        "right_before": int(before["right"]), "right_after": totals["right"],
        "right_change": totals["right"] - int(before["right"]),
        "bilateral_before": int(before["both"]),
    }
    changes["per_type"] = rows
    changes["cause"] = (
        "The feasibility graph discarded aggregate pairs of weights 1-4. This build keeps every pair "
        "between typed, traced nodes. Added weak pairs can supply evidence to previously unresolved cells, "
        "change the aggregate winning hex, and create or remove transformed-slot collisions."
    )
    return changes


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build(output: Path, record_path: Path) -> dict[str, Any]:
    cache = cache_root()
    annotation_path = cache / CACHE_NAMES["annotations"]
    connections_path = cache / CACHE_NAMES["connections"]
    columns = ["bodyId", "status", "type", "somaSide", "rootSide", "assignedOlHex1", "assignedOlHex2"]
    annotations = feather.read_table(annotation_path, columns=columns).to_pandas()
    nodes = annotations.loc[(annotations.status == "Traced") & annotations.type.notna()].copy().reset_index(drop=True)
    roots = nodes.bodyId.to_numpy(dtype=np.int64)
    male_type = nodes.type.astype(str).to_numpy()
    aliases = [alias(value) for value in male_type]
    flyvis_type = np.asarray([value[0] for value in aliases], dtype=object)
    alias_problem = np.asarray([value[1] for value in aliases], dtype=object)
    candidate = np.asarray([value is not None for value in flyvis_type], dtype=bool)
    direct_h1_float = nodes.assignedOlHex1.to_numpy(dtype=float)
    direct_h2_float = nodes.assignedOlHex2.to_numpy(dtype=float)
    has_direct = np.isfinite(direct_h1_float) & np.isfinite(direct_h2_float)
    direct_h1 = np.where(has_direct, direct_h1_float, -1).astype(np.int16)
    direct_h2 = np.where(has_direct, direct_h2_float, -1).astype(np.int16)

    incoming_frame, outgoing_frame, graph = collect_evidence(
        connections_path, roots, candidate, has_direct, direct_h1, direct_h2
    )
    incoming = pick_evidence(incoming_frame)
    outgoing = pick_evidence(outgoing_frame)
    side = nodes.somaSide.fillna(nodes.rootSide).map({"L": "left", "R": "right"})
    records: list[dict[str, Any]] = []
    for idx in range(len(nodes)):
        method: str | None = None
        direction: str | None = None
        confidence: float | None = None
        evidence: Evidence | None = None
        if candidate[idx] and has_direct[idx]:
            method = "direct"
            direction = "self"
            confidence = 1.0
            evidence = Evidence(int(direct_h1[idx]), int(direct_h2[idx]), 0, 0, 1)
        elif candidate[idx] and idx in incoming:
            method = "wiring-inferred"
            direction = "incoming"
            evidence = incoming[idx]
            confidence = evidence.winner_weight / evidence.eligible_weight
        elif candidate[idx] and idx in outgoing:
            method = "wiring-inferred"
            direction = "outgoing"
            evidence = outgoing[idx]
            confidence = evidence.winner_weight / evidence.eligible_weight
        records.append({
            "male_body_id": int(roots[idx]),
            "male_type": male_type[idx],
            "flyvis_type": flyvis_type[idx],
            "eye": side.iloc[idx] if pd.notna(side.iloc[idx]) else None,
            "hex1": evidence.hex1 if evidence else None,
            "hex2": evidence.hex2 if evidence else None,
            "method": method,
            "evidence_direction": direction,
            "confidence": confidence,
            "winner_synapse_weight": evidence.winner_weight if evidence else 0,
            "eligible_synapse_weight": evidence.eligible_weight if evidence else 0,
            "top_tie_count": evidence.top_tie_count if evidence else 0,
            "alias_problem": alias_problem[idx],
        })
    rows = pd.DataFrame.from_records(records)
    rows, transforms = transform_columns(rows, dra_vectors(nodes, outgoing))
    rows = finalise_rows(rows)
    summary, motion = summarise(rows)

    # Bilateral counts compare type-position slots, not neuron identities.
    bilateral: dict[str, int] = {}
    for flyvis_type in FLYVIS_TYPES:
        left = rows[(rows.flyvis_type == flyvis_type) & (rows.eye == "left") & ~rows.unresolved]
        right = rows[(rows.flyvis_type == flyvis_type) & (rows.eye == "right") & ~rows.unresolved]
        bilateral[flyvis_type] = len(
            set(zip(left.flyvis_u.astype(int), left.flyvis_v.astype(int)))
            & set(zip(right.flyvis_u.astype(int), right.flyvis_v.astype(int)))
        )
    changes = baseline_changes(summary)
    current_bilateral = sum(bilateral.values())
    if changes:
        changes["totals"]["bilateral_after"] = current_bilateral
        changes["totals"]["bilateral_change"] = current_bilateral - changes["totals"]["bilateral_before"]
        for row in changes["per_type"]:
            row["bilateral_after"] = bilateral[row["flyvis_type"]]
            row["bilateral_before"] = int(
                read_json(ROOT / "validation/records/p2/malecns-feasibility.json")
                ["eye_columns"]["per_type"][row["flyvis_type"]]["unique_both_eyes"]
            )
            row["bilateral_change"] = row["bilateral_after"] - row["bilateral_before"]

    output.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(rows, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    metadata[b"flyonenomics.dataset"] = b"male-cns:v1.0"
    metadata[b"flyonenomics.assignment_version"] = b"eye-assignment-male-cns-v1.0"
    metadata[b"flyonenomics.license"] = b"CC BY 4.0"
    metadata[b"flyonenomics.attribution"] = b"MaleCNS v1.0; Berg et al., Cell (2026), doi:10.1016/j.cell.2026.08.015"
    metadata[b"flyonenomics.confidence"] = (
        b"direct=1; inferred=winning-coordinate synapse weight / all eligible directly-hex-labelled partner weight in the selected direction"
    )
    table = table.replace_schema_metadata(metadata)
    pq.write_table(table, output, compression="zstd")

    total_slots = sum(len(expected_slots(t)) for t in FLYVIS_TYPES)
    total_left = sum(r["unique_drivable_slots"] for r in summary if r["eye"] == "left")
    total_right = sum(r["unique_drivable_slots"] for r in summary if r["eye"] == "right")
    record = {
        "class": "development",
        "dataset": "male-cns:v1.0",
        "assignment_version": "eye-assignment-male-cns-v1.0",
        "license": "CC BY 4.0",
        "attribution": "MaleCNS v1.0; Berg et al., Cell (2026), doi:10.1016/j.cell.2026.08.015",
        "purpose": "versioned MaleCNS cell-to-flyvis eye-column assignment",
        "verdict": "partial provisional assignment; nothing is calibrated and the fly does not see",
        "artifact": {
            "path": str(output.relative_to(ROOT)),
            "format": "Parquet, one row per typed traced MaleCNS graph cell",
            "rows": len(rows),
            "sha256": sha256(output),
        },
        "sources": {
            "annotations": {"path": CACHE_NAMES["annotations"], "sha256": sha256(annotation_path)},
            "connections": {"path": CACHE_NAMES["connections"], "sha256": sha256(connections_path)},
        },
        "rules_named_before_outcomes": {
            "node": "status == Traced and type is non-null, in official annotation order",
            "edge": "every released aggregate pair whose endpoints pass the node rule; no model-weight cut",
            "type_alias": "exact flyvis type; R7*/R8* collapse to R7/R8; R1-R6 and CT1 shared labels remain unresolved",
            "placement": "own direct hex; else greatest aggregate incoming weight from directly hex-labelled partners; else greatest aggregate outgoing weight",
            "tie": (
                "record the lowest (hex1, hex2) deterministically, but keep every inference with more than "
                "one greatest-weight coordinate unresolved"
            ),
            "coordinates_excluded": "never use soma or centroid XYZ; somaSide then rootSide selects only the eye",
            "collision": "a flyvis type-position is usable only when exactly one concrete MaleCNS cell occupies it",
        },
        "confidence": {
            "range": [0.0, 1.0],
            "direct": 1.0,
            "wiring_inferred": "winning coordinate aggregate synapse weight divided by all eligible directly-hex-labelled partner weight in the selected direction",
            "tie_field": (
                "top_tie_count reports equally weighted winning coordinates; a count above one is unresolved, "
                "while the recorded lowest pair makes the artifact deterministic"
            ),
            "meaning": "support concentration for this release and rule, not a calibrated biological probability",
        },
        "graph": graph,
        "lattice": {
            "flyvis_radius": 15,
            "flyvis_columns_per_dense_type": 721,
            "flyvis_columns_per_Lawf_type": 123,
            "flyvis_type_position_slots": total_slots,
            "transform_status": "provisional geometry-only proposal; not selected or adjusted from a neural or behavioural outcome",
            "proposal": "native axial hex -> Cartesian; center on the eye's inferred T4/T5-column centroid; rotate the mean R7d/R8d wiring-derived DRA vector upward; use FRONT_SIGN=-1; round back to axial radius 15",
            "per_eye": transforms,
            "free_choices": {
                "orientation": "DRA-up and FRONT_SIGN=-1 are the prior fly-afterlife convention; an anatomy source may replace them, never a transfer outcome",
                "reference_column": "the proposal uses a fractional T4/T5 centroid and records the nearest released column; no biological reference column is yet frozen",
                "left_eye_handedness": "the proposal does not mirror the left eye; mirroring remains a declared alternative until anatomy, not downstream performance, settles it",
            },
        },
        "coverage": {
            "unique_left": total_left,
            "unique_right": total_right,
            "unique_bilateral_type_positions": current_bilateral,
            "tied_inferences_unresolved": int(
                ((rows.top_tie_count > 1) & rows.method.eq("wiring-inferred")).sum()
            ),
            "fraction_left": total_left / total_slots,
            "fraction_right": total_right / total_slots,
            "fraction_bilateral": current_bilateral / total_slots,
            "interpretation": "fraction of flyvis type-position slots that this provisional transform could drive with one and only one MaleCNS cell",
        },
        "per_type_eye": summary,
        "motion_T4_T5": motion,
        "change_from_feasibility_weight_ge_5_graph": changes,
        "limitations": [
            "R1-R6 is one shared MaleCNS identity and cannot identify six separate flyvis photoreceptor types.",
            "MaleCNS CT1 does not distinguish the two flyvis CT1 compartments and remains unresolved.",
            "Wiring inference and collision resolution are release- and transform-dependent.",
            "Connection signs are not read; adapter-v3 sign changes cannot affect this assignment.",
            "No visual stimulus, engine response, steering response or behavioural result was used to choose a rule.",
            "This artifact assigns cells and columns only. It does not make the eye conduct or calibrate the male substrate.",
        ],
        "reproduction": "FLYONENOMICS_CACHE_DIR=<cache> uv run python scripts/malecns_eye_assignment.py",
    }
    write_json(record_path, record)
    return record


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data/eye-assignment-male-cns-v1.0.parquet")
    parser.add_argument("--record", type=Path, default=ROOT / "validation/records/p2/malecns-eye-assignment.json")
    args = parser.parse_args(argv)
    record = build(args.output.resolve(), args.record.resolve())
    print(json.dumps({
        "artifact": record["artifact"],
        "graph": record["graph"],
        "coverage": record["coverage"],
        "change": record["change_from_feasibility_weight_ge_5_graph"].get("totals", {}),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
