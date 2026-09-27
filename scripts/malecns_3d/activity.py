"""Read recorded activity for display only. No engine or study-analysis imports."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import numpy as np

from flyonenomics.io import hash_file, load_npy, read_json, read_yaml

DATASET = "male-cns:v1.0"
ARTIFICIAL = "Model activity. Artificial input injected at TuBu; the fly does not see."
CALIBRATION = ARTIFICIAL + " Calibration run 5a, not the experiment's result."


def sha(path: Path) -> str:
    return hash_file(path)


def read(path: Path) -> dict:
    return read_json(path)


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n")


def array_sha(array: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(array, dtype="<i8").tobytes()).hexdigest()


def binned_rates(counts: np.ndarray, chunk_s: float, bin_s: float) -> np.ndarray:
    """Sum adjacent chunks, divide by bin duration; never smooth or interpolate."""
    ratio = bin_s / chunk_s
    width = round(ratio)
    if width < 1 or not np.isclose(ratio, width, rtol=0, atol=1e-9):
        raise ValueError("bin duration must be a positive integer number of recorded chunks")
    if counts.ndim not in (1, 2) or len(counts) % width:
        raise ValueError("count array must contain complete bins")
    if not np.issubdtype(counts.dtype, np.integer) or np.any(counts < 0):
        raise ValueError("recorded counts must be nonnegative integers")
    return counts.reshape(-1, width, *counts.shape[1:]).sum(axis=1, dtype=np.int64) / bin_s


def phases(stage: str, protocol: str | list[str], timing: dict) -> list[dict]:
    settle = timing["settle_s"]
    if stage == "5a":
        intervals = [(0, settle, "Settling · input off"),
                     (settle, settle + timing["5a_s"], f"TuBu input: {protocol}")]
    else:
        prefix_end = settle + timing["prefix_s"]
        test_start = prefix_end + timing["gap_s"]
        intervals = [(0, settle, "Settling · input off"),
                     (settle, prefix_end, f"History: {protocol[0]}"),
                     (prefix_end, test_start, "Gap · input off"),
                     (test_start, test_start + timing["test_s"], f"Test: {protocol[1]}")]
    return [dict(start_s=a, end_s=b, label=label) for a, b, label in intervals]


def extract_study(raw: Path, plan_path: Path, params_path: Path, roots: np.ndarray,
                  cells: list[dict], destination: Path, *, source: str,
                  pair_path: Path | None = None, bin_s: float = .1) -> Path:
    """Load complete-seed manifests + NPZs from 5a/5b; write only to destination.

    Historical 5a-01 manifests have reconstructed identity and no chunk_s.
    Use the hash-bound parameter table for timing; retain receipt caveats verbatim.
    The ER presynaptic array records all displayed ER cells, not just the 245-cell
    analysis subset. Root order must match the frozen engine-array digest.
    """
    raw, destination = raw.resolve(), destination.resolve()
    if destination == raw or raw in destination.parents:
        raise ValueError("activity cache must be outside the raw source directory")
    plan, params = read(plan_path), read_yaml(params_path)
    plan_hash, params_hash = sha(plan_path), sha(params_path)
    if plan["identity"]["sha256"]["data/params-v0.2.yaml"] != params_hash:
        raise ValueError("parameter table differs from frozen plan")
    chunk_s = float(params["engine"]["chunk_ms"]["value"]) / 1000
    if not np.isfinite(chunk_s) or chunk_s <= 0 or not np.isfinite(bin_s) or bin_s <= 0:
        raise ValueError("invalid chunk/bin duration")
    if array_sha(roots) != plan["engine_arrays_sha256"]["roots_i64le"]:
        raise ValueError("annotation-derived engine root order differs from frozen plan")
    if plan["male_array_binding"]["connectome_version"] != DATASET:
        raise ValueError("study is not MaleCNS v1.0")
    er_ids = [c["body_id"] for c in cells if c["group"] == "ER"]
    tubu_ids = [c["body_id"] for c in cells if c["group"] == "TuBu"]
    ids = er_ids + tubu_ids
    if not er_ids or not tubu_ids or len(set(ids)) != len(ids):
        raise ValueError("display needs distinct ER and TuBu body IDs")
    tubu_source_ids = list(map(str, plan["source_body_ids"]))
    if len(set(tubu_source_ids)) != len(tubu_source_ids) or set(tubu_source_ids) != set(tubu_ids):
        raise ValueError("recorded TuBu selection differs from displayed TuBu")
    if list(map(str, roots[plan["source_indices"]])) != tubu_source_ids:
        raise ValueError("TuBu body IDs disagree with engine indices")
    traced_indices = [c["engine_index"] for c in plan["cells"]]
    if list(map(int, roots[traced_indices])) != [c["body_id"] for c in plan["cells"]]:
        raise ValueError("ER body IDs disagree with engine indices")
    tubu_order = [tubu_source_ids.index(body) for body in tubu_ids]
    manifests = sorted(raw.glob("seed-*.json"))
    # Per-arm audit JSONs are not complete-seed manifests.
    manifests = [p for p in manifests if re.fullmatch(r"seed-\d+\.json", p.name)]
    if not manifests:
        raise ValueError("no complete-seed manifests")
    first = read(manifests[0])
    stage = first["stage"]
    if stage not in ("5a", "5b"):
        raise ValueError("only 5a and 5b study records are supported")
    expected_seeds = plan["seeds"][stage]
    if {p.name for p in manifests} != {f"seed-{s}.json" for s in expected_seeds}:
        raise ValueError("missing or unexpected seed manifests")
    if stage == "5b" and pair_path is None:
        raise ValueError("5b needs the frozen pair record")
    pair = read(pair_path) if pair_path else None
    pair_hash = sha(pair_path) if pair_path else None
    if pair and pair["plan_sha256"] != plan_hash:
        raise ValueError("pair/plan binding differs")
    # Real plans also contain a `synthetic` analysis-validation results object.
    # Only the explicit boolean marker identifies made-up playback records.
    synthetic = plan.get("synthetic") is True
    source_hashes = {"plan": plan_hash, "parameters": params_hash}
    if pair_hash:
        source_hashes["pair"] = pair_hash
    expected_arms = [(r["condition"], r["protocol"]) for r in first["rows"]]
    if not expected_arms or len({json.dumps(a) for a in expected_arms}) != len(expected_arms):
        raise ValueError("missing or duplicate study arms")
    rates, totals, provenance = [], [], []
    for seed in expected_seeds:
        path = raw / f"seed-{seed}.json"
        record = read(path)
        if (record["seed"] != seed or record["stage"] != stage
                or record["plan_sha256"] != plan_hash or record["pair_sha256"] != pair_hash
                or record["identity"] != first["identity"]
                or (record.get("synthetic") is True) != synthetic):
            raise ValueError(f"inconsistent seed identity or plan/pair binding: {path.name}")
        if record["identity"]["sha256"]["data/params-v0.2.yaml"] != params_hash:
            raise ValueError("recorded parameter hash differs")
        if [(r["condition"], r["protocol"]) for r in record["rows"]] != expected_arms:
            raise ValueError("missing or reordered arms")
        source_hashes[path.name] = sha(path)
        provenance.append({k: v for k, v in record.items() if k != "rows"})
        seed_rates, seed_totals = [], []
        for row in record["rows"]:
            if Path(row["file"]).name != row["file"]:
                raise ValueError("arm file must be a basename")
            file = raw / row["file"]
            if sha(file) != row["sha256"]:
                raise ValueError(f"raw arm checksum mismatch: {file.name}")
            source_hashes[file.name] = row["sha256"]
            if row["male_array_binding"] != plan["male_array_binding"]:
                raise ValueError("arm male-array binding differs from plan")
            if "chunk_s" in row and not np.isclose(row["chunk_s"], chunk_s, rtol=0, atol=1e-12):
                raise ValueError("arm chunk duration differs from frozen parameters")
            intervals = phases(stage, row["protocol"], plan["timing"])
            steps = round(intervals[-1]["end_s"] / chunk_s)
            with load_npy(file, allow_pickle=False) as arrays:
                er_idx = arrays["er_edge_presynaptic_indices"]
                if (er_idx.ndim != 1 or not np.issubdtype(er_idx.dtype, np.integer)
                        or len(set(er_idx)) != len(er_idx) or np.any(er_idx < 0) or np.any(er_idx >= len(roots))):
                    raise ValueError("invalid recorded ER indices")
                er_source_ids = list(map(str, roots[er_idx]))
                if set(er_source_ids) != set(er_ids):
                    raise ValueError("recorded ER selection differs from displayed ER")
                er = arrays["er_edge_presynaptic_counts"]
                tubu = arrays["tubu_counts"]
                aggregate = arrays["CX_DAN_counts"]
                if (er.shape != (steps, len(er_ids)) or tubu.shape != (steps, len(tubu_ids))
                        or aggregate.shape != (steps,)):
                    raise ValueError("unexpected count shape or duration (CX_DAN must be a population total)")
                # Check the duplicated trace columns against their explicit ID mapping.
                trace_order = [er_source_ids.index(str(c["body_id"])) for c in plan["cells"]]
                if not np.array_equal(er[:, trace_order], arrays["er_counts"]):
                    raise ValueError("ER trace and presynaptic per-cell counts disagree")
                er_order = [er_source_ids.index(body) for body in er_ids]
                per_cell = np.concatenate((er[:, er_order], tubu[:, tubu_order]), axis=1)
                seed_rates.append(binned_rates(per_cell, chunk_s, bin_s))
                seed_totals.append(binned_rates(aggregate, chunk_s, bin_s))
        rates.append(seed_rates)
        totals.append(seed_totals)
    rates, totals = np.asarray(rates), np.asarray(totals)
    times = (np.arange(rates.shape[2]) + .5) * bin_s
    edges = np.arange(rates.shape[2] + 1) * bin_s
    conditions = []
    for i, (condition, protocol) in enumerate(expected_arms):
        label = (f"Input {'off' if protocol == 'off' else str(protocol) + '°'} · {condition}" if stage == "5a"
                 else f"{condition} · history {protocol[0]} → test {protocol[1]}")
        conditions.append(dict(id=f"arm-{i:02}", label=label, condition=condition, protocol=protocol,
                               phases=phases(stage, protocol, plan["timing"]),
                               values=rates[:, i].mean(axis=0).tolist(),
                               aggregates={"CX_DAN": totals[:, i].mean(axis=0).tolist()}))
    label = CALIBRATION if stage == "5a" else ARTIFICIAL + " Experiment stage 5b playback, not an analysis."
    if synthetic:
        label = "SYNTHETIC · made-up test records, not a neural run. " + label
    note = f"Mean of {len(expected_seeds)} seeds · {bin_s * 1000:g} ms bins · time from run start (includes settling)."
    if pair:
        note += f" Imposed TuBu labels: A = {pair['pair'][0]}°, B = {pair['pair'][1]}°; AB = both."
    data = dict(dataset=DATASET, kind="synthetic" if synthetic else "model", label=label, unit="Hz",
                body_ids=ids, anatomy_only_groups=["CX_DAN", "MB_DAN", "KC"],
                times_s=times.tolist(), bin_edges_s=edges.tolist(), summary=note, conditions=conditions,
                aggregate_specs=[dict(id="CX_DAN", label="CX dopamine · population total, not per-cell",
                                      unit="spikes/s")])
    destination.mkdir(parents=True, exist_ok=True)
    per_seed = destination / "per-seed.npz"
    np.savez_compressed(per_seed, rates_hz=rates, cx_dan_total_spikes_s=totals,
                        seeds=np.asarray(expected_seeds), body_ids=np.asarray(ids),
                        condition_ids=np.asarray([c["id"] for c in conditions]), bin_edges_s=edges,
                        label=np.asarray(label))
    values = destination / "values.json"
    save(values, data)
    manifest = dict(label=label, source=source, stage=stage, substrate_id=plan["substrate_id"],
                    source_sha256=source_hashes, seed_receipts=provenance,
                    extractor_sha256=sha(Path(__file__)), chunk_s=chunk_s, bin_s=bin_s,
                    binning="Non-overlapping [left,right) bins from run start; counts/bin_s. Times are bin centres.",
                    averaging="Arithmetic mean across all frozen seeds; no smoothing, selection or analysis.",
                    per_seed_axes=["seed", "condition", "time_bin", "body_id"],
                    aggregate_axes=["seed", "condition", "time_bin"],
                    per_cell_groups=["ER", "TuBu"], anatomy_only_groups=data["anatomy_only_groups"],
                    aggregate="CX_DAN sum of emitted spikes/bin_s; NOT mean Hz per cell, dopamine concentration or injected input.",
                    outputs={p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in (values, per_seed)})
    save(destination / "manifest.json", manifest)
    return values


def extract_primary_5b(raw: Path, plan_path: Path, pair_path: Path, params_path: Path,
                       audit_path: Path, results_path: Path, roots: np.ndarray,
                       cells: list[dict], destination: Path) -> Path:
    """Extract one outcome-independent representative seed, four arms, first 2 s of test.

    Check each raw file against the independent 5b-02 audit BEFORE opening it.
    No other arm is read; nothing is written in the raw archive.
    """
    raw, destination = raw.resolve(), destination.resolve()
    if destination == raw or raw in destination.parents:
        raise ValueError("output must be outside the raw archive")
    audit = read(audit_path)
    if not audit["remote_local_artifact_maps_identical"] or not audit["remote_local_seed_audits_identical"]:
        raise ValueError("5b audit does not agree across machines")
    hashes = audit["remote_verification"]["artifacts_sha256"]

    def checked(name: str) -> Path:
        if not re.fullmatch(r"seed-\d+(?:-arm-\d+)?\.(?:json|npz)", name) or name not in hashes:
            raise ValueError(f"file missing from independent audit: {name}")
        path = raw / name
        if sha(path) != hashes[name]:
            raise ValueError(f"5b audit checksum mismatch: {name}")
        return path

    plan, pair, params, results = read(plan_path), read(pair_path), read_yaml(params_path), read(results_path)
    if sha(plan_path) != audit["remote_verification"]["plan_sha256"] or sha(pair_path) != audit["remote_verification"]["pair_sha256"]:
        raise ValueError("plan/pair differ from audited run")
    if pair["plan_sha256"] != audit["remote_verification"]["calibration_plan_sha256"] or plan["identity"]["sha256"]["data/params-v0.2.yaml"] != sha(params_path):
        raise ValueError("plan, pair or parameter binding differs")
    if array_sha(roots) != plan["engine_arrays_sha256"]["roots_i64le"]:
        raise ValueError("annotation engine order differs from frozen plan")
    seeds = plan["seeds"]["5b"]
    deltas = results["primary"][0]
    if deltas["name"] != "genotype" or len(deltas["per_seed"]) != len(seeds) or not np.isclose(np.mean(deltas["per_seed"]), deltas["mean"]):
        raise ValueError("invalid result record for seed selection")
    seed = min(zip(seeds, deltas["per_seed"]), key=lambda entry: (abs(entry[1] - deltas["mean"]), entry[0]))[0]
    record_path = checked(f"seed-{seed}.json")
    record = read(record_path)
    if (record["seed"] != seed or record["stage"] != "5b"
            or record["identity"]["sha256"] != plan["identity"]["sha256"]
            or record["plan_sha256"] != sha(plan_path) or record["pair_sha256"] != sha(pair_path)):
        raise ValueError("selected seed manifest does not bind to plan/pair")
    expected = [(condition, [history, "AB"]) for condition in ("wt-vehicle", "fumin-vehicle") for history in ("A", "B")]
    rows = {(r["condition"], tuple(r["protocol"])): r for r in record["rows"]}
    if len(rows) != len(record["rows"]) or any((c, tuple(p)) not in rows for c, p in expected):
        raise ValueError("missing or duplicated requested arms")
    chunk_s = float(params["engine"]["chunk_ms"]["value"]) / 1000
    bin_s = .1
    start = plan["timing"]["settle_s"] + plan["timing"]["prefix_s"] + plan["timing"]["gap_s"]
    primary = plan["timing"]["primary_s"]
    if primary != [0, 2.0] or not np.isclose(start / chunk_s, round(start / chunk_s)):
        raise ValueError("unexpected primary window or chunk alignment")
    lo, hi = round(start / chunk_s), round((start + primary[1]) / chunk_s)
    er_ids = [c["body_id"] for c in cells if c["group"] == "ER"]
    tubu_ids = [c["body_id"] for c in cells if c["group"] == "TuBu"]
    tubu_source_ids = list(map(str, plan["source_body_ids"]))
    if (not er_ids or not tubu_ids or set(tubu_ids) != set(tubu_source_ids)
            or list(map(str, roots[plan["source_indices"]])) != tubu_source_ids
            or list(map(int, roots[[c["engine_index"] for c in plan["cells"]]])) != [c["body_id"] for c in plan["cells"]]):
        raise ValueError("per-cell body ID binding differs from frozen plan")
    tubu_order = [tubu_source_ids.index(body) for body in tubu_ids]
    conditions, source_hashes = [], {record_path.name: hashes[record_path.name]}
    for condition, protocol in expected:
        row = rows[condition, tuple(protocol)]
        name = row["file"]
        path = checked(name)
        if (row["sha256"] != hashes[name] or row["male_array_binding"] != plan["male_array_binding"]
                or not np.isclose(row["chunk_s"], chunk_s)):
            raise ValueError(f"arm receipt binding differs: {name}")
        source_hashes[name] = hashes[name]
        with load_npy(path, allow_pickle=False) as arrays:
            indices = arrays["er_edge_presynaptic_indices"]
            if indices.ndim != 1 or not np.issubdtype(indices.dtype, np.integer) or np.any(indices < 0) or np.any(indices >= len(roots)):
                raise ValueError("invalid ER indices")
            er_source_ids = list(map(str, roots[indices]))
            if len(set(er_source_ids)) != len(er_ids) or set(er_source_ids) != set(er_ids):
                raise ValueError("ER indices differ from displayed cells")
            duration = round((start + plan["timing"]["test_s"]) / chunk_s)
            er, tubu, aggregate = (arrays[k] for k in ("er_edge_presynaptic_counts", "tubu_counts", "CX_DAN_counts"))
            if er.shape != (duration, len(er_ids)) or tubu.shape != (duration, len(tubu_ids)) or aggregate.shape != (duration,):
                raise ValueError("unexpected recorded shapes")
            trace_order = [er_source_ids.index(str(c["body_id"])) for c in plan["cells"]]
            if not np.array_equal(er[:, trace_order], arrays["er_counts"]):
                raise ValueError("duplicated ER traces disagree")
            ordered = np.concatenate((er[lo:hi, [er_source_ids.index(b) for b in er_ids]],
                                      tubu[lo:hi, tubu_order]), axis=1)
            values = binned_rates(ordered, chunk_s, bin_s)
            totals = binned_rates(aggregate[lo:hi], chunk_s, bin_s)
        history = protocol[0]
        conditions.append(dict(id=f"{'wt' if condition == 'wt-vehicle' else 'fumin'}-{history.lower()}",
                               label=f"{'Wild type' if condition == 'wt-vehicle' else 'Fumin'} (vehicle) · {history} → A+B",
                               condition=condition, protocol=protocol,
                               phases=[dict(start_s=0, end_s=2, label=f"Test: A+B · after {history} history")],
                               values=values.tolist(), aggregates={"CX_DAN": totals.tolist()}))
    edges = (np.arange(21) * bin_s).tolist()
    label = ARTIFICIAL + " Candidate neural signature, not ADHD or behaviour. Stage 5b, seed " + str(seed) + "."
    data = dict(dataset=DATASET, kind="model", label=label, unit="Hz",
                body_ids=er_ids + tubu_ids, anatomy_only_groups=["CX_DAN", "MB_DAN", "KC"],
                times_s=[(i + .5) * bin_s for i in range(20)], bin_edges_s=edges,
                summary=f"Seed {seed} · test-relative first 2 s · 100 ms non-overlapping bins; A={pair['pair'][0]:g}°, B={pair['pair'][1]:g}° injected TuBu labels (not seen). No smoothing.",
                conditions=conditions, aggregate_specs=[dict(id="CX_DAN", label="CX dopamine · population total, not per-cell", unit="spikes/s")])
    destination.mkdir(parents=True, exist_ok=True)
    values_path = destination / "values.json"
    save(values_path, data)
    manifest = dict(seed=seed, seed_rule="Smallest absolute distance of per-seed genotype ΔH_gen to ten-seed mean, ties by lowest seed; from frozen result record, not visual appearance.",
                    stage="5b-02", raw_source=str(raw), input_sha256={
                        **source_hashes, "plan": sha(plan_path), "pair": sha(pair_path),
                        "params": sha(params_path), "audit": sha(audit_path), "results": sha(results_path)},
                    extraction="Only four vehicle arms and first 2 s of test [8,10) s from run start; nonoverlapping 100 ms counts/bin_s. ER and TuBu per cell; CX_DAN group total only.",
                    output_sha256={"values.json": sha(values_path)}, extractor_sha256=sha(Path(__file__)))
    save(destination / "manifest.json", manifest)
    return values_path


def load_values(cells: list[dict], data: dict) -> dict:
    """Validate a value file and join columns by body ID; missing is never zero.

    The original single-array dummy JSON remains a supported display input.
    Multi-condition files explicitly name anatomy-only groups and aggregate units.
    Per-seed arrays remain in the extraction cache, not in the browser payload.
    """
    if data.get("dataset") != DATASET or not data.get("label", "").strip() or not data.get("unit", "").strip():
        raise ValueError("Playback needs dataset male-cns:v1.0, label and unit")
    bodies = data["body_ids"]
    if not bodies or not all(isinstance(b, str) for b in bodies) or len(set(bodies)) != len(bodies):
        raise ValueError("Playback needs unique string body_ids")
    times = np.asarray(data["times_s"], dtype=float)
    if times.ndim != 1 or len(times) < 2 or not np.isfinite(times).all() or not (np.diff(times) > 0).all():
        raise ValueError("Playback times_s must be finite and strictly increasing")
    anatomy_groups = data.get("anatomy_only_groups", [])
    wanted = [c["body_id"] for c in cells if c["group"] not in anatomy_groups]
    if not wanted or not set(wanted) <= set(bodies):
        raise ValueError("Missing per-cell values; explicitly declare anatomy-only groups")
    if any(c["body_id"] in bodies for c in cells if c["group"] in anatomy_groups):
        raise ValueError("Anatomy-only cells must not have per-cell values")
    index = {body: i for i, body in enumerate(bodies)}
    columns = [index[body] for body in wanted]
    inputs = data.get("conditions")
    if inputs is None:
        inputs = [dict(id="values", label=data["label"], values=data["values"], aggregates={})]
    names = [c["id"] for c in inputs]
    if not names or len(set(names)) != len(names) or not all(re.fullmatch(r"[a-zA-Z0-9_-]+", n) for n in names):
        raise ValueError("Condition IDs must be unique filename-safe names")
    specs = data.get("aggregate_specs", [])
    if len({s["id"] for s in specs}) != len(specs) or any(not s.get("label") or not s.get("unit") for s in specs):
        raise ValueError("Aggregates need distinct IDs, labels and units")
    conditions, minimum, maximum = [], float("inf"), -float("inf")
    aggregate_max = {s["id"]: 0.0 for s in specs}
    for entry in inputs:
        values = np.asarray(entry["values"], dtype=float)
        if values.shape != (len(times), len(bodies)) or not np.isfinite(values).all():
            raise ValueError("Playback values must be finite [time, body_id]")
        values = values[:, columns]
        minimum, maximum = min(minimum, float(values.min())), max(maximum, float(values.max()))
        aggregates = entry.get("aggregates", {})
        if set(aggregates) != set(aggregate_max):
            raise ValueError("Every condition must supply each labelled aggregate")
        for key, raw in aggregates.items():
            array = np.asarray(raw, dtype=float)
            if array.shape != times.shape or not np.isfinite(array).all() or (array < 0).any():
                raise ValueError("Population totals must be finite nonnegative [time]")
            aggregate_max[key] = max(aggregate_max[key], float(array.max()))
        for phase in entry.get("phases", []):
            if not (np.isfinite([phase["start_s"], phase["end_s"]]).all()
                    and phase["start_s"] < phase["end_s"] and phase.get("label")):
                raise ValueError("Invalid playback phase")
        conditions.append({**entry, "values": values.tolist(), "aggregates": aggregates})
    edges = data.get("bin_edges_s")
    if edges is not None:
        edges = np.asarray(edges, dtype=float)
        if (edges.shape != (len(times) + 1,) or not np.isfinite(edges).all()
                or not (np.diff(edges) > 0).all() or not ((times > edges[:-1]) & (times < edges[1:])).all()):
            raise ValueError("Bin centres must lie inside finite increasing bin edges")
    result = {**data, "body_ids": wanted, "conditions": conditions, "minimum": minimum, "maximum": maximum,
              "aggregate_specs": [{**s, "maximum": aggregate_max[s["id"]]} for s in specs],
              "anatomy_only_groups": anatomy_groups}
    result.pop("values", None)  # Single-array inputs are represented once, as one condition.
    return result
