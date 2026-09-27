#!/usr/bin/env python3
"""Measure MaleCNS signs, population matches, eye coverage, and motor routes."""
from __future__ import annotations

import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.ipc as ipc

from flyonenomics.io import read_json

from common import (
    ANNOTATIONS,
    CACHE,
    CONNECTIONS,
    DOWNLOADS,
    FLYVIS_TYPES,
    METADATA,
    NT_SIGN,
    ROOT,
    TRANSMITTERS,
    file_record,
    load_graph,
    load_tables,
    write_json,
)

OUT = CACHE / "analysis.json"
T4T5 = ("T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d")


def counts(frame: pd.DataFrame, column: str, pattern: str) -> dict[str, int]:
    subset = frame[frame[column].fillna("").str.match(pattern)]
    return {str(k): int(v) for k, v in subset["type"].fillna("(missing)").value_counts().items()}


def scan_relevant(annotations: pd.DataFrame) -> dict[str, Any]:
    metu = set(int(v) for v in annotations.loc[annotations.type.fillna("").str.match(r"^MeTu"), "bodyId"])
    tubu = set(int(v) for v in annotations.loc[annotations.type.fillna("").str.match(r"^TuBu"), "bodyId"])
    er = set(int(v) for v in annotations.loc[annotations.type.fillna("").str.match(r"^ER\d"), "bodyId"])
    te: list[tuple[int, int, int]] = []
    mt: list[tuple[int, int, int]] = []
    reader = ipc.open_file(CONNECTIONS)
    for i in range(reader.num_record_batches):
        batch = reader.get_batch(i)
        pre = batch.column("body_pre").to_numpy(zero_copy_only=False)
        post = batch.column("body_post").to_numpy(zero_copy_only=False)
        weight = batch.column("weight").to_numpy(zero_copy_only=False)
        m1 = np.isin(pre, list(tubu)) & np.isin(post, list(er))
        m2 = np.isin(pre, list(metu)) & np.isin(post, list(tubu))
        te.extend((int(a), int(b), int(w)) for a, b, w in zip(pre[m1], post[m1], weight[m1]))
        mt.extend((int(a), int(b), int(w)) for a, b, w in zip(pre[m2], post[m2], weight[m2]))
    relevant_tubu = {a for a, _, _ in te}
    relevant_metu = {a for a, b, _ in mt if b in relevant_tubu}
    return {
        "ER_all": len(er),
        "TuBu_all": len(tubu),
        "TuBu_with_edge_to_ER": len(relevant_tubu),
        "TuBu_to_ER_pairs": len(te),
        "TuBu_to_ER_synapses": sum(w for _, _, w in te),
        "MeTu_all": len(metu),
        "MeTu_with_edge_to_relevant_TuBu": len(relevant_metu),
        "MeTu_to_relevant_TuBu_pairs": sum(b in relevant_tubu for _, b, _ in mt),
        "MeTu_to_relevant_TuBu_synapses": sum(w for _, b, w in mt if b in relevant_tubu),
    }


def best_columns(
    node: pd.DataFrame, pre: np.ndarray, post: np.ndarray, weight: np.ndarray
) -> pd.DataFrame:
    """Replicate fly-afterlife columns_all placement, with explicit aliases."""
    node = node.reset_index(drop=True)
    h1 = node.assignedOlHex1.to_numpy(dtype=float)
    h2 = node.assignedOlHex2.to_numpy(dtype=float)
    has = np.isfinite(h1) & np.isfinite(h2)
    typ = node.type.fillna("").astype(str).to_numpy(dtype=str)
    side = node.somaSide.fillna(node.rootSide).fillna("").astype(str).to_numpy(dtype=str)

    exact_types = set(FLYVIS_TYPES) - {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "CT1(Lo1)", "CT1(M10)"}
    candidate = np.isin(typ, list(exact_types)) | np.char.startswith(typ, "R7") | np.char.startswith(typ, "R8") | (typ == "R1-R6")
    cells = np.flatnonzero(candidate)
    out_h1 = np.full(len(node), -1, dtype=np.int16)
    out_h2 = np.full(len(node), -1, dtype=np.int16)
    how = np.full(len(node), "", dtype="U4")
    own = candidate & has
    out_h1[own] = h1[own].astype(np.int16)
    out_h2[own] = h2[own].astype(np.int16)
    how[own] = "self"

    def apply(direction: str) -> None:
        need = candidate & (out_h1 < 0)
        me, other = (post, pre) if direction == "in" else (pre, post)
        mask = need[me] & has[other]
        frame = pd.DataFrame({
            "me": me[mask], "h1": h1[other[mask]].astype(np.int16),
            "h2": h2[other[mask]].astype(np.int16), "weight": weight[mask],
        })
        if frame.empty:
            return
        grouped = frame.groupby(["me", "h1", "h2"], as_index=False).weight.sum()
        picked = grouped.sort_values(
            ["me", "weight", "h1", "h2"],
            ascending=[True, False, True, True],
            kind="mergesort",
        ).drop_duplicates("me")
        idx = picked.me.to_numpy(dtype=np.int32)
        out_h1[idx] = picked.h1.to_numpy(dtype=np.int16)
        out_h2[idx] = picked.h2.to_numpy(dtype=np.int16)
        how[idx] = direction

    apply("in")
    apply("out")
    placed = cells[out_h1[cells] >= 0]
    rows: list[dict[str, Any]] = []
    for idx in placed:
        male_type = typ[idx]
        if male_type == "R1-R6":
            fvtypes = ("R1", "R2", "R3", "R4", "R5", "R6")
            ambiguous = True
        elif male_type.startswith("R7"):
            fvtypes = ("R7",)
            ambiguous = False
        elif male_type.startswith("R8"):
            fvtypes = ("R8",)
            ambiguous = False
        else:
            fvtypes = (male_type,)
            ambiguous = False
        for fvtype in fvtypes:
            rows.append({
                "idx": int(idx), "male_type": male_type, "fvtype": fvtype, "side": side[idx],
                "hex1": int(out_h1[idx]), "hex2": int(out_h2[idx]), "how": how[idx],
                "ambiguous_alias": ambiguous,
            })
    return pd.DataFrame(rows)


def eye_coverage(node: pd.DataFrame, pre: np.ndarray, post: np.ndarray, weight: np.ndarray) -> dict[str, Any]:
    placed = best_columns(node, pre, post, weight)
    t45 = placed[placed.fvtype.isin(T4T5)]
    physical_columns = sorted(set(zip(t45.side, t45.hex1, t45.hex2)))
    geometry = pd.DataFrame(physical_columns, columns=["side", "hex1", "hex2"])

    # Axial (q,r) = (hex1,-hex2), then the same DRA-derived orientation as the pin.
    geometry["x"] = geometry.hex1 - geometry.hex2 / 2.0
    geometry["y"] = -geometry.hex2 * math.sqrt(3) / 2.0
    typ = node.type.fillna("").astype(str).to_numpy(dtype=str)
    side = node.somaSide.fillna(node.rootSide).fillna("").astype(str).to_numpy(dtype=str)
    h1 = node.assignedOlHex1.to_numpy(dtype=float)
    h2 = node.assignedOlHex2.to_numpy(dtype=float)
    has = np.isfinite(h1) & np.isfinite(h2)
    dra = np.flatnonzero(np.isin(typ, ["R7d", "R8d"]))
    mask = np.isin(pre, dra) & has[post]
    dra_frame = pd.DataFrame({
        "cell": pre[mask], "weight": weight[mask], "hex1": h1[post[mask]].astype(int),
        "hex2": h2[post[mask]].astype(int),
    })
    grouped = dra_frame.groupby(["cell", "hex1", "hex2"], as_index=False).weight.sum()
    chosen = grouped.sort_values(["cell", "weight"], ascending=[True, False]).drop_duplicates("cell")
    chosen["side"] = side[chosen.cell.to_numpy(dtype=np.int32)]

    column_to_uv: dict[tuple[str, int, int], tuple[int, int] | None] = {}
    lattice = {(u, v) for u in range(-15, 16) for v in range(max(-15, -15 - u), min(15, 15 - u) + 1)}
    eye_columns: dict[str, int] = {}
    for eye in ("L", "R"):
        g = geometry[geometry.side == eye].copy()
        cx, cy = g.x.mean(), g.y.mean()
        d = chosen[chosen.side == eye]
        dx = d.hex1 - d.hex2 / 2.0
        dy = -d.hex2 * math.sqrt(3) / 2.0
        vector = np.array([dx.mean() - cx, dy.mean() - cy])
        vector /= np.linalg.norm(vector)
        rotation = math.pi / 2 - math.atan2(vector[1], vector[0])
        xs, ys = g.x.to_numpy() - cx, g.y.to_numpy() - cy
        sy = xs * math.sin(rotation) + ys * math.cos(rotation)
        sx = -(xs * math.cos(rotation) - ys * math.sin(rotation))  # pinned FRONT_SIGN=-1
        v = np.rint(sx).astype(int)
        u = np.rint(-sy - v / 2.0).astype(int)
        inside = 0
        for h1v, h2v, uv in zip(g.hex1, g.hex2, zip(u, v)):
            key = (eye, int(h1v), int(h2v))
            column_to_uv[key] = uv if uv in lattice else None
            inside += int(uv in lattice)
        eye_columns[eye] = inside

    placed["uv"] = [column_to_uv.get((r.side, int(r.hex1), int(r.hex2))) for r in placed.itertuples()]

    # Raw assignedOlHex coverage is distinct from graph-derived seam placement.
    direct_fields: dict[str, Any] = {}
    direct_totals = {"left": 0, "right": 0}
    node_side = node.somaSide.fillna(node.rootSide).fillna("").astype(str)
    for fvtype in FLYVIS_TYPES:
        if fvtype in {"R1", "R2", "R3", "R4", "R5", "R6"}:
            mask = node.type.eq("R1-R6")
            ambiguous = True
        elif fvtype == "R7":
            mask = node.type.fillna("").str.startswith("R7")
            ambiguous = False
        elif fvtype == "R8":
            mask = node.type.fillna("").str.startswith("R8")
            ambiguous = False
        else:
            mask = node.type.eq(fvtype)
            ambiguous = False
        subset = node[mask & node.assignedOlHex1.notna() & node.assignedOlHex2.notna()].copy()
        subset["_side"] = node_side[subset.index]
        coordinate_sets = {
            label: set(zip(subset.loc[subset._side == eye, "assignedOlHex1"].astype(int), subset.loc[subset._side == eye, "assignedOlHex2"].astype(int)))
            for eye, label in (("L", "left"), ("R", "right"))
        }
        direct_fields[fvtype] = {
            "rows_left": int((subset._side == "L").sum()),
            "rows_right": int((subset._side == "R").sum()),
            "distinct_hex_left": len(coordinate_sets["left"]),
            "distinct_hex_right": len(coordinate_sets["right"]),
            "hex_present_both_eyes": len(coordinate_sets["left"] & coordinate_sets["right"]),
            "ambiguous_shared_R1_R6_type": ambiguous,
        }
        direct_totals["left"] += int((subset._side == "L").sum())
        direct_totals["right"] += int((subset._side == "R").sum())

    per_type: dict[str, Any] = {}
    totals = {"left": 0, "right": 0, "both": 0}
    for fvtype in FLYVIS_TYPES:
        expected_uv = {(u, v) for u, v in lattice if fvtype not in {"Lawf1", "Lawf2"} or (u % 3 == 0 and v % 2 == 0)}
        expected = len(expected_uv)
        sets: dict[str, set[tuple[int, int]]] = {}
        how_counts: dict[str, dict[str, int]] = {}
        for eye, label in (("L", "left"), ("R", "right")):
            subset = placed[(placed.fvtype == fvtype) & (placed.side == eye) & placed.uv.notna()]
            # R1-R6 is one unresolved Male type reused six times, not six unique identities.
            if subset.ambiguous_alias.any():
                unique: set[tuple[int, int]] = set()
            else:
                multiplicity = Counter(tuple(v) for v in subset.uv)
                unique = {uv for uv, n in multiplicity.items() if n == 1 and uv in expected_uv}
            sets[label] = unique
            how_counts[label] = {str(k): int(v) for k, v in subset.how.value_counts().items()}
        both = sets["left"] & sets["right"]
        per_type[fvtype] = {
            "flyvis_cells": expected,
            "unique_left": len(sets["left"]),
            "unique_right": len(sets["right"]),
            "unique_both_eyes": len(both),
            "placement_methods": how_counts,
        }
        totals["left"] += len(sets["left"])
        totals["right"] += len(sets["right"])
        totals["both"] += len(both)
    return {
        "flyvis_cells": sum(123 if t in {"Lawf1", "Lawf2"} else 721 for t in FLYVIS_TYPES),
        "male_placed_rows_including_R1_R6_alias_reuse": int(len(placed)),
        "male_physical_columns_inside_flyvis_lattice": eye_columns,
        "raw_assignedOlHex_rows_all_types": int(node.assignedOlHex1.notna().sum()),
        "raw_fields_per_flyvis_type": direct_fields,
        "raw_field_row_totals_over_flyvis_aliases": direct_totals,
        "unique_matches": totals,
        "per_type": per_type,
        "method": "own direct hex, else strongest aggregate hex-tagged input, else output; ties use lowest (hex1, hex2); DRA/front orientation; no soma/centroid XYZ; R1-R6 alias rejected as non-unique",
    }


def motor_routes(node: pd.DataFrame, pre: np.ndarray, post: np.ndarray, signed_count: np.ndarray) -> dict[str, Any]:
    typ = node.type.fillna("").astype(str).to_numpy(dtype=str)
    side = node.somaSide.fillna(node.rootSide).fillna("").astype(str).to_numpy(dtype=str)
    sources = np.flatnonzero(np.isin(typ, ["DNa02", "DNae001"]))
    motor = node.superclass.fillna("").eq("vnc_motor")
    categories = {
        "leg": np.flatnonzero(motor & node.subclass.fillna("").isin(["fl", "ml", "hl"])),
        "wing": np.flatnonzero(motor & node.subclass.fillna("").eq("wm")),
    }
    edge_mv = signed_count.astype(np.float64) * 0.275
    result: dict[str, Any] = {}
    n = len(node)
    for source in sources:
        state = np.full(n, -1.0)
        state[source] = 1.0
        predecessors: list[np.ndarray] = []
        incoming_weights: list[np.ndarray] = []
        state_signs: list[np.ndarray] = []
        routes: dict[str, Any] = {}
        for depth in range(1, 4):
            mask = (state[pre] >= 0) & (edge_mv != 0)
            edge_slots = np.flatnonzero(mask)
            cand = state[pre[edge_slots]] * np.abs(edge_mv[edge_slots])
            # Sort strongest first; retain one incoming candidate per target.
            order = np.argsort(cand)[::-1]
            target_sorted = post[edge_slots[order]]
            _, first = np.unique(target_sorted, return_index=True)
            picked_slots = edge_slots[order[first]]
            new_state = np.full(n, -1.0)
            new_state[post[picked_slots]] = state[pre[picked_slots]] * np.abs(edge_mv[picked_slots])
            pred = np.full(n, -1, dtype=np.int32)
            pred[post[picked_slots]] = pre[picked_slots]
            sign = np.zeros(n, dtype=np.int8)
            prior_sign = np.ones(n, dtype=np.int8) if depth == 1 else state_signs[-1]
            sign[post[picked_slots]] = prior_sign[pre[picked_slots]] * np.sign(edge_mv[picked_slots]).astype(np.int8)
            incoming = np.zeros(n, dtype=np.float64)
            incoming[post[picked_slots]] = edge_mv[picked_slots]
            predecessors.append(pred)
            incoming_weights.append(incoming)
            state_signs.append(sign)
            state = new_state
            for category, targets in categories.items():
                alive = targets[state[targets] >= 0]
                if not len(alive):
                    continue
                best = int(alive[np.argmax(state[alive])])
                path = [best]
                path_edge_weights: list[float] = []
                cur = best
                for d in range(depth - 1, -1, -1):
                    path_edge_weights.append(float(incoming_weights[d][cur]))
                    cur = int(predecessors[d][cur])
                    path.append(cur)
                path.reverse()
                path_edge_weights.reverse()
                candidate = {
                    "hops": depth,
                    "path_body_ids": [int(node.bodyId.iloc[v]) for v in path],
                    "path_types": [str(typ[v] or node.superclass.iloc[v]) for v in path],
                    "path_sides": [str(side[v]) for v in path],
                    "edge_composed_weights_mV": path_edge_weights,
                    "composed_weight_product_mV_power_hops": float(state[best] * state_signs[-1][best]),
                    "target_type": str(typ[best]),
                    "reachable_motor_neurons_at_exact_hops": int(len(alive)),
                }
                key = f"{category}_strongest_at_{depth}_hops"
                routes[key] = candidate
        label = f"{typ[source]}_{side[source]}_{int(node.bodyId.iloc[source])}"
        result[label] = routes
    result["motor_denominators"] = {k: int(len(v)) for k, v in categories.items()}
    result["note"] = "Products are topology bookkeeping, not biological gains; each edge is sign*synapse_count*0.275 mV."
    return result


def main() -> int:
    annotations, transmitters = load_tables()
    traced = annotations[annotations.status == "Traced"].copy()
    node = annotations.loc[(annotations.status == "Traced") & annotations.type.notna()].copy().reset_index(drop=True)
    nt = node.merge(transmitters, left_on="bodyId", right_on="body", how="left", validate="one_to_one")
    roots, pre, post, signed_count, weight = load_graph()
    if not np.array_equal(roots, node.bodyId.to_numpy(dtype=np.int64)):
        raise RuntimeError("node order does not match graph")

    clear = nt.consensus_nt.isin(NT_SIGN)
    confidence = nt.celltype_predicted_nt_confidence
    signs = {
        "traced_neurons": int(len(traced)),
        "typed_traced_graph_neurons": int(len(node)),
        "typed_with_recommended_signed_consensus": int(clear.sum()),
        "typed_without_signed_consensus": int((~clear).sum()),
        "coverage_fraction": float(clear.mean()),
        "consensus_counts": {str(k): int(v) for k, v in nt.consensus_nt.fillna("missing").value_counts().items()},
        "celltype_confidence_quantiles": {str(q): float(confidence.quantile(q)) for q in (0, .05, .25, .5, .75, .95, 1)},
        "clear_consensus_confidence_ge": {str(q): int((clear & (confidence >= q)).sum()) for q in (.5, .7, .8, .9)},
        "ground_truth_rows": int(nt.ground_truth.notna().sum()),
    }

    er = traced[traced.type.fillna("").str.match(r"^ER\d")]
    cx_pattern = traced.type.fillna("").str.match(r"^(ExR2|FB1C|FB1H|FB2A|FB4L|FB4M|FB5H|PPM120[1-5])$")
    cx = traced[cx_pattern].merge(transmitters[["body", "consensus_nt"]], left_on="bodyId", right_on="body", how="left")
    populations = {
        "ER": {
            "flywire_result": 228,
            "flywire_result_by_broad_subtype": {"ER2": 38, "ER3d": 51, "ER3w": 25, "ER4d": 25, "ER3a": 24, "ER5": 21, "ER3p": 17, "ER3m": 14, "ER4m": 11, "ER6": 2},
            "male_all_ER": int(len(er)),
            "male_by_type": counts(traced, "type", r"^ER\d"),
        },
        "CX_DAN": {
            "flywire": 30,
            "male_named_central_complex_candidates": int(len(cx)),
            "male_candidates_with_dopamine_consensus": int(cx.consensus_nt.eq("dopamine").sum()),
            "note": "candidate type bridge only; EB innervation requires the ROI table and is not a clean match",
        },
        "TuBu": {"flywire": 150, "male": int(traced.type.fillna("").str.match(r"^TuBu").sum()), "male_by_type": counts(traced, "type", r"^TuBu")},
        "MeTu": {"flywire_all": 896, "flywire_relevant": 886, "male": int(traced.type.fillna("").str.match(r"^MeTu").sum()), "male_by_type": counts(traced, "type", r"^MeTu")},
        "T4_T5": {"flywire": {t: n for t, n in zip(T4T5, (1463,1507,1692,1578,1482,1520,1529,1467))}, "male": {t: int(traced.type.eq(t).sum()) for t in T4T5}},
        "lobula_plate_tangentials": {
            "flywire": {"H2": 2, "HS_family": 6, "VS_family": 32},
            "male": {"H2": int(traced.type.eq("H2").sum()), "HS_family": int(traced.type.fillna("").str.match(r"^HS").sum()), "VS_family": int(traced.type.fillna("").str.match(r"^VS").sum())},
        },
        "descending": {"flywire": {"DNa02": 2, "DNae001": 2}, "male": {"DNa02": int(traced.type.eq("DNa02").sum()), "DNae001": int(traced.type.eq("DNae001").sum())}},
        "sugar_reflex": {
            "flywire_sugar_GRN_R": 21, "male_taste_peg_GRN": int(traced.type.fillna("").isin(["claw_tpGRN", "dorsal_tpGRN"]).sum()),
            "male_note": "no sugar modality label, so the 21-cell source has no clean match",
            "flywire_MN9": 1, "male_MN9": int(traced.type.eq("MN9").sum()),
        },
        "photoreceptors": {
            "flywire": {"R1-R6": 7932, "R7": 1337, "R8": 1314},
            "male": {str(k): int(v) for k, v in traced[traced.flywireType.isin(["R1-6", "R7", "R8"])].flywireType.value_counts().items()},
            "male_by_eye": {eye: {str(k): int(v) for k, v in traced[(traced.flywireType.isin(["R1-6", "R7", "R8"])) & (traced.rootSide == eye)].flywireType.value_counts().items()} for eye in ("L", "R")},
        },
    }

    payload = {
        "dataset": "male-cns:v1.0",
        "downloads": [file_record(CACHE / name, url) for name, url in DOWNLOADS.items()],
        "graph": read_json(METADATA),
        "signs": signs,
        "populations": populations,
        "ring_route_relevance": scan_relevant(traced),
        "eye_columns": eye_coverage(node, pre, post, weight),
        "motor_routes": motor_routes(node, pre, post, signed_count),
    }
    write_json(OUT, payload)
    print(json.dumps({
        "sign_coverage": signs["coverage_fraction"],
        "eye_unique": payload["eye_columns"]["unique_matches"],
        "ring_route": payload["ring_route_relevance"],
        "motor_sources": len(payload["motor_routes"]) - 2,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
