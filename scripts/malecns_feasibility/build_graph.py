#!/usr/bin/env python3
"""Build the typed, traced MaleCNS graph and the array cache used by BrianEngine.

The node rule follows fly-afterlife's pinned MaleCNS build: status == Traced and a
non-null type. Connection pairs retain both endpoints and weight >= 5. Each pair's
synapse count gets the presynaptic neuron's recommended consensusNt sign. An unclear
or absent consensus has weight zero; it is retained so graph-size accounting stays
separate from sign coverage.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pyarrow.ipc as ipc

from common import (
    ANNOTATIONS,
    COMPLETENESS,
    CONNECTIONS,
    DERIVED,
    METADATA,
    NT_SIGN,
    TRANSMITTERS,
    graph_dir,
    load_tables,
    sha256,
    write_json,
)

MIN_WEIGHT = 5


def save(path: Path, array: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, array)
    temporary.replace(path)


def main() -> int:
    started = time.perf_counter()
    annotations, transmitters = load_tables()
    nodes = annotations.loc[(annotations["status"] == "Traced") & annotations["type"].notna()].copy()
    nodes = nodes.merge(
        transmitters[["body", "consensus_nt", "celltype_predicted_nt_confidence"]],
        left_on="bodyId",
        right_on="body",
        how="left",
        validate="one_to_one",
    )
    roots = nodes["bodyId"].to_numpy(dtype=np.int64)
    signs = nodes["consensus_nt"].map(NT_SIGN).fillna(0).to_numpy(dtype=np.int8)
    order = np.argsort(roots)
    sorted_roots = roots[order]

    DERIVED.mkdir(parents=True, exist_ok=True)
    # Existing loader reads the first CSV column as the engine order.
    COMPLETENESS.write_text("bodyId\n" + "\n".join(str(int(v)) for v in roots) + "\n")
    directory = graph_dir()
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / "lock"
    lock.touch(exist_ok=True)

    pre_parts: list[np.ndarray] = []
    post_parts: list[np.ndarray] = []
    weight_parts: list[np.ndarray] = []
    reader = ipc.open_file(CONNECTIONS)
    input_rows = 0
    input_synapses = 0
    for batch_no in range(reader.num_record_batches):
        batch = reader.get_batch(batch_no)
        pre_id = batch.column("body_pre").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        post_id = batch.column("body_post").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        weight = batch.column("weight").to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
        input_rows += len(weight)
        input_synapses += int(weight.sum())
        pre_pos = np.searchsorted(sorted_roots, pre_id)
        post_pos = np.searchsorted(sorted_roots, post_id)
        pre_ok = pre_pos < len(sorted_roots)
        post_ok = post_pos < len(sorted_roots)
        pre_match = np.zeros(len(pre_id), dtype=bool)
        post_match = np.zeros(len(post_id), dtype=bool)
        pre_match[pre_ok] = sorted_roots[pre_pos[pre_ok]] == pre_id[pre_ok]
        post_match[post_ok] = sorted_roots[post_pos[post_ok]] == post_id[post_ok]
        keep = pre_match & post_match & (weight >= MIN_WEIGHT)
        if keep.any():
            pre_parts.append(order[pre_pos[keep]].astype(np.int32, copy=False))
            post_parts.append(order[post_pos[keep]].astype(np.int32, copy=False))
            weight_parts.append(weight[keep].astype(np.int32, copy=False))

    pre = np.concatenate(pre_parts)
    post = np.concatenate(post_parts)
    weight = np.concatenate(weight_parts)
    signed = (weight.astype(np.float64) * signs[pre]).astype(np.float64)
    save(directory / "root_ids.npy", roots)
    save(directory / "i.npy", pre)
    save(directory / "j.npy", post)
    save(directory / "w_exc.npy", signed)
    save(directory / "weight.npy", weight)
    (directory / "ready").write_text("ok\n")

    clear = signs != 0
    payload = {
        "dataset": "male-cns:v1.0",
        "node_rule": "status == Traced and type is non-null",
        "edge_rule": f"both endpoints in node set and weight >= {MIN_WEIGHT}",
        "sign_rule": "presynaptic consensus_nt under Shiu fast-sign convention; unclear/missing = zero",
        "nodes": int(len(roots)),
        "nodes_with_signed_consensus": int(clear.sum()),
        "nodes_without_signed_consensus": int((~clear).sum()),
        "edges": int(len(pre)),
        "edges_nonzero_signed": int(np.count_nonzero(signed)),
        "synapses": int(weight.sum()),
        "input_connection_rows": int(input_rows),
        "input_synapses": int(input_synapses),
        "min_weight": MIN_WEIGHT,
        "array_cache": str(directory),
        "build_wall_s": time.perf_counter() - started,
        "sources_sha256": {
            ANNOTATIONS.name: sha256(ANNOTATIONS),
            TRANSMITTERS.name: sha256(TRANSMITTERS),
            CONNECTIONS.name: sha256(CONNECTIONS),
        },
    }
    write_json(METADATA, payload)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
