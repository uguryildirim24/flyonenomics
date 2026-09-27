"""Static flyvis/FlyWire seam feasibility analysis on the pinned v783 substrate."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_signal_transfer as transfer  # noqa: E402


def clean(value: object) -> str | None:
    return None if pd.isna(value) else str(value)


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--flyvis-connectome", type=Path, required=True)
    parser.add_argument("--flyvis-run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from flyonenomics.io import read_json
    spec = read_json(args.flyvis_connectome)
    run = read_json(args.flyvis_run)
    flyvis_types = sorted(str(row["name"]) for row in spec["nodes"])
    activity = run["conditions"][0]["graded_activity"]
    flyvis_cells = {name: int(row["columns"]) for name, row in activity.items()}
    if set(flyvis_cells) != set(flyvis_types):
        raise ValueError("flyvis run and connectome contain different cell types")
    if sum(flyvis_cells.values()) != int(run["network"]["cells"]):
        raise ValueError("flyvis per-type counts do not sum to the network cell count")
    registry, params, drive, roots, pre, post, raw, effective = transfer.substrate_arrays()
    from flyonenomics.substrate.transmitters import annotations_in_engine
    annotations, annotation_roots = annotations_in_engine()
    if not np.array_equal(roots, annotation_roots):
        raise ValueError("annotation and engine root orders differ")
    cell_type = annotations.cell_type.fillna("").astype(str).to_numpy()
    hemibrain = annotations.hemibrain_type.fillna("").astype(str).to_numpy()
    super_class = annotations.super_class.fillna("").astype(str).to_numpy()
    side = annotations.side.fillna("").astype(str).to_numpy()

    aliases = {f"R{i}": "R1-6" for i in range(1, 7)}
    aliases.update({"CT1(M10)": "CT1", "CT1(Lo1)": "CT1"})
    coverage = []
    for flyvis_type in flyvis_types:
        matched_name = aliases.get(flyvis_type, flyvis_type)
        idx = np.flatnonzero(cell_type == matched_name)
        coverage.append({
            "flyvis_type": flyvis_type,
            "flywire_type_query": matched_name,
            "flyvis_cells": flyvis_cells[flyvis_type],
            "flywire_v783_engine_candidates": int(len(idx)),
            "unique_type_and_hex_matches": 0,
            "reason_unique_zero": "pinned project annotation has no optic-lobe hex/column field; external column sources were not joined",
        })
    modelled_type_names = {aliases.get(value, value) for value in flyvis_types}
    modelled_source = np.isin(cell_type, sorted(modelled_type_names))

    reached = read_json(ROOT / "validation/records/p2/tubu-reached-subset.json")
    ring_roots = {
        int(row["root_id"]) for row in reached["cells"] if "ring_ER" in row["classes"]
    }
    ring_idx = np.flatnonzero(np.isin(roots, list(ring_roots)))
    tubu_idx = np.asarray(registry.population("TuBu").idx, dtype=np.int32)
    to_ring = np.isin(pre, tubu_idx) & np.isin(post, ring_idx)
    relevant_tubu = np.unique(pre[to_ring]).astype(np.int32)
    into_tubu = np.isin(post, relevant_tubu)
    upstream = np.unique(pre[into_tubu]).astype(np.int32)
    metu = upstream[np.char.startswith(cell_type[upstream].astype(str), "MeTu")]
    medulla_edges = np.isin(post, metu) & (super_class[pre] == "optic")
    medulla_source = pre[medulla_edges]
    medulla_modelled = modelled_source[medulla_source]
    abs_count = np.abs(raw[medulla_edges]).astype(np.float64)
    abs_weight = np.abs(effective[medulla_edges]).astype(np.float64)

    medulla_by_type = []
    labels = np.where(cell_type[medulla_source] != "", cell_type[medulla_source], hemibrain[medulla_source])
    for label in sorted(set(labels.tolist())):
        mask = labels == label
        medulla_by_type.append({
            "type": str(label),
            "modelled_by_flyvis": bool(label in modelled_type_names),
            "source_cells": int(len(np.unique(medulla_source[mask]))),
            "connection_pairs": int(mask.sum()),
            "synapses": float(abs_count[mask].sum()),
            "absolute_composed_weight_mV": float(abs_weight[mask].sum()),
        })
    medulla_by_type.sort(key=lambda row: row["synapses"], reverse=True)

    metu_rows = []
    for idx in metu:
        edges = medulla_edges & (post == idx)
        counts = np.abs(raw[edges]).astype(float)
        weights = np.abs(effective[edges]).astype(float)
        src = pre[edges]
        keep = modelled_source[src]
        metu_rows.append({
            "engine_index": int(idx), "root_id": int(roots[idx]),
            "cell_type": clean(cell_type[idx]), "side": clean(side[idx]),
            "relevant_tubu_targets": int(len(np.unique(post[(pre == idx) & np.isin(post, relevant_tubu)]))),
            "input_synapses": float(counts.sum()),
            "flyvis_type_input_synapses": float(counts[keep].sum()),
            "flyvis_synapse_fraction": float(counts[keep].sum() / counts.sum()) if counts.sum() else None,
            "absolute_composed_weight_mV": float(weights.sum()),
            "flyvis_absolute_composed_weight_mV": float(weights[keep].sum()),
            "flyvis_absolute_weight_fraction": float(weights[keep].sum() / weights.sum()) if weights.sum() else None,
        })

    # Lobula-plate tangential candidates are named LPT*, HS*, VS*, H1 or H2.
    combined = np.where(cell_type != "", cell_type, hemibrain)
    lptc_named = np.array([
        bool(re.match(r"^(?:LPT|HS|VS|H1$|H2$)", value)) for value in combined
    ])
    t4t5 = np.array([bool(re.fullmatch(r"T[45][abcd]", value)) for value in cell_type])
    t4_edges = t4t5[pre] & lptc_named[post]
    driven_lptc = np.unique(post[t4_edges]).astype(np.int32)
    descending = super_class == "descending"
    lptc_dn_edges = np.isin(pre, driven_lptc) & descending[post]

    def aggregate_edges(mask: np.ndarray) -> list[dict]:
        frame = pd.DataFrame({
            "source_type": combined[pre[mask]], "target_type": combined[post[mask]],
            "synapses": np.abs(raw[mask]).astype(float),
            "weight": effective[mask].astype(float),
        })
        if frame.empty:
            return []
        grouped = frame.groupby(["source_type", "target_type"], dropna=False).agg(
            connection_pairs=("synapses", "size"), synapses=("synapses", "sum"),
            composed_weight_mV=("weight", "sum"),
            absolute_composed_weight_mV=("weight", lambda x: x.abs().sum()),
        ).reset_index()
        grouped = grouped.sort_values("absolute_composed_weight_mV", ascending=False)
        return grouped.to_dict("records")

    # Shortest paths from T4/T5-fed LPTCs to the four steering endpoints.
    keep = effective != 0
    graph = csr_matrix((np.ones(int(keep.sum()), np.uint8), (pre[keep], post[keep])), shape=(len(roots), len(roots)))
    distance, predecessor, origin = dijkstra(
        graph, directed=True, indices=driven_lptc, unweighted=True,
        min_only=True, return_predecessors=True,
    )
    endpoint_indices = sorted(set().union(*(
        set(map(int, registry.population(name).idx))
        for name in ("DNa02_L", "DNa02_R", "steering_L", "steering_R")
    )))

    def edge(u: int, v: int) -> dict:
        rows = np.flatnonzero((pre == u) & (post == v))
        if len(rows) != 1:
            raise ValueError(f"expected one edge {u}->{v}, got {len(rows)}")
        r = int(rows[0])
        return {"synapses": float(abs(raw[r])), "composed_weight_mV": float(effective[r])}

    endpoint_paths = []
    for endpoint in endpoint_indices:
        if not np.isfinite(distance[endpoint]):
            endpoint_paths.append({"endpoint_engine_index": endpoint, "reachable": False})
            continue
        nodes = [endpoint]
        while int(predecessor[nodes[-1]]) >= 0:
            nodes.append(int(predecessor[nodes[-1]]))
        nodes.reverse()
        lptc = nodes[0]
        source_rows = np.flatnonzero(t4_edges & (post == lptc))
        best = int(source_rows[np.argmax(np.abs(effective[source_rows]))])
        nodes.insert(0, int(pre[best]))
        edges = [edge(u, v) for u, v in zip(nodes[:-1], nodes[1:], strict=True)]
        endpoint_paths.append({
            "endpoint_engine_index": endpoint, "endpoint_root_id": int(roots[endpoint]),
            "endpoint_type": clean(combined[endpoint]), "endpoint_side": clean(side[endpoint]),
            "reachable": True, "hops": len(edges),
            "engine_indices": nodes, "root_ids": [int(roots[x]) for x in nodes],
            "types": [clean(combined[x]) for x in nodes],
            "super_classes": [clean(super_class[x]) for x in nodes],
            "edges": edges,
            "composed_path_product_mV_power_hops": float(np.prod([row["composed_weight_mV"] for row in edges])),
        })

    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "declared_substrate_id": "rest:379cc4cc9030cdd1",
        "connectome": {"materialization": 783, "engine_neurons": int(len(roots)), "connection_pairs": int(len(pre))},
        "mapping": {
            "annotation_columns": list(annotations.columns),
            "flyvis_types": len(flyvis_types),
            "types_with_candidates": int(sum(row["flywire_v783_engine_candidates"] > 0 for row in coverage)),
            "flyvis_cells_total": int(sum(flyvis_cells.values())),
            "unique_type_and_hex_matches_total": 0,
            "scope": "direct join to the pinned project annotation only; excludes published v783 column assignments",
            "coverage_by_type": coverage,
        },
        "ring_path": {
            "reached_ER_cells": len(ring_roots),
            "relevant_TuBu_cells": int(len(relevant_tubu)),
            "relevant_TuBu": [{
                "engine_index": int(i), "root_id": int(roots[i]),
                "type": clean(combined[i]), "side": clean(side[i]),
            } for i in relevant_tubu],
            "presynaptic_neurons": int(len(upstream)),
            "presynaptic_MeTu_cells": int(len(metu)),
            "presynaptic_MeTu": metu_rows,
            "medulla_input": {
                "connection_pairs": int(medulla_edges.sum()),
                "synapses": float(abs_count.sum()),
                "flyvis_type_synapses": float(abs_count[medulla_modelled].sum()),
                "flyvis_type_synapse_fraction": float(abs_count[medulla_modelled].sum() / abs_count.sum()),
                "absolute_composed_weight_mV": float(abs_weight.sum()),
                "flyvis_type_absolute_composed_weight_mV": float(abs_weight[medulla_modelled].sum()),
                "flyvis_type_absolute_weight_fraction": float(abs_weight[medulla_modelled].sum() / abs_weight.sum()),
                "by_type": medulla_by_type,
            },
        },
        "motion_path": {
            "T4_T5_cells": int(t4t5.sum()),
            "T4_T5_to_named_LPTC_connection_pairs": int(t4_edges.sum()),
            "T4_T5_fed_named_LPTC_cells": int(len(driven_lptc)),
            "T4_T5_to_LPTC_by_type": aggregate_edges(t4_edges),
            "LPTC_to_descending_connection_pairs": int(lptc_dn_edges.sum()),
            "LPTC_to_descending_by_type": aggregate_edges(lptc_dn_edges),
            "steering_endpoint_paths": endpoint_paths,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "out": str(args.out), "mapping_types": output["mapping"]["types_with_candidates"],
        "metu": len(metu), "medulla_fraction": output["ring_path"]["medulla_input"]["flyvis_type_synapse_fraction"],
        "lptc": len(driven_lptc), "endpoint_paths": endpoint_paths,
    }, indent=2))


if __name__ == "__main__":
    main()
