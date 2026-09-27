#!/usr/bin/env python3
"""Adopt item 155's male starting brain; no outcome-based setting selection."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

import malecns_rest as rest

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "validation/records/p2"


def array_sha(array: np.ndarray, dtype: str) -> str:
    return hashlib.sha256(np.ascontiguousarray(array, dtype=dtype).tobytes()).hexdigest()


def seed_check() -> None:
    """Compare actual initial spike trains through the unmodified male runner."""
    from flyonenomics.io import hash_file
    from flyonenomics.orchestrator.seeds import brian_seed

    started = time.perf_counter()
    seeds = {str(s): brian_seed(rest.MASTER_SEED, s, 0) for s in rest.SEEDS}
    built = rest._build(1.0)
    engine = built["engine"]
    rows = []
    trains = []
    for seed in (1, 5, 1):
        rest._reset(built, seed, 1.0)
        engine.run_chunk(100.0)
        spikes = engine.spikes(0)
        trains.append((spikes.idx.copy(), spikes.tick.copy()))
        rows.append({
            "seed_index": seed, "brian_seed": seeds[str(seed)],
            "spike_count": len(spikes.idx),
            "idx_i32le_sha256": array_sha(spikes.idx, "<i4"),
            "tick_i64le_sha256": array_sha(spikes.tick, "<i8"),
            "first_20_spikes_idx_tick": np.column_stack((spikes.idx, spikes.tick))[:20].tolist(),
        })
    equal = lambda a, b: all(np.array_equal(x, y) for x, y in zip(a, b))
    distinct = not equal(trains[0], trains[1])
    repeat = equal(trains[0], trains[2])
    paths = ["scripts/malecns_substrate.py", "scripts/malecns_rest.py", "src/flyonenomics/orchestrator/seeds.py",
             "src/flyonenomics/engine/brian_engine.py", "data/params-v0.1.yaml", "data/params-v0.2.yaml", "uv.lock",
             "data/malecns-v1.0-manifest.json", "data/populations-male-cns-v1.0.yaml",
             "data/compartments-male-cns-v1.0.yaml", "data/receptors-male-cns-v1.0.yaml",
             "data/transmitters-male-cns-v1.0.yaml"]
    payload = {
        "dataset": rest.MALE_VERSION, "master_seed": rest.MASTER_SEED,
        "probe_index": 0, "derived_brian_seeds": seeds,
        "all_ten_uint32_seeds_distinct": len(set(seeds.values())) == 10,
        "duration_ms_per_run": 100.0, "dt_ms": engine.dt_ms,
        "sensory_weight_mv": 1.0, "runs": rows,
        "seeds_1_and_5_spike_trains_distinct": distinct,
        "seed_1_replay_exact": repeat,
        "path": "malecns_rest._reset: restore(initial), then seed(brian_seed(20260912,s,0)); SeedSequence spawn_key=(s,0,ENGINE=1); BrianEngine.seed -> brian2.seed; cython PoissonInput",
        "inputs_sha256": {path: hash_file(ROOT / path) for path in paths},
        "platform": rest._platform(), "wall_s": time.perf_counter() - started,
        "peak_rss_bytes": rest._peak_rss_bytes(),
    }
    rest._atomic_json(RECORDS / "malecns-seed-check.json", payload)
    if not (distinct and repeat and payload["all_ten_uint32_seeds_distinct"]):
        raise RuntimeError("male seed check failed; stop before adopting any table")
    print("Seeds 1 and 5 have distinct spike trains; seed 1 replays exactly.", flush=True)


def import_k2r(directory: Path) -> None:
    """Extract the three existing K2r rows after checking their recorded hashes."""
    from flyonenomics.io import hash_file, read_json

    record_path = RECORDS / "malecns-rest.json"
    measured = read_json(record_path)
    rows, sources = [], {}
    for seed in (1, 2, 3):
        name = f"seed-{seed}.json"
        path = directory / name
        digest = hash_file(path)
        if digest != measured["raw"]["files_sha256"][name]:
            raise ValueError(f"recorded raw measurement hash mismatch: {name}")
        payload = read_json(path)
        if payload["dataset"] != rest.MALE_VERSION or payload["seed"] != seed:
            raise ValueError(f"wrong dataset or seed: {name}")
        rows.append(payload["k2"])
        sources[name] = digest
    rest._atomic_json(RECORDS / "malecns-k2r-measurement.json", {
        "dataset": rest.MALE_VERSION, "rows": rows,
        "source_record": "validation/records/p2/malecns-rest.json",
        "source_record_sha256": hash_file(record_path),
        "source_raw_sha256": sources,
        "method": "Unchanged k2 rows extracted after verifying the raw seed-file SHA-256s in t-0069's committed record; no new measurement.",
    })


def _model_manifest_sha256() -> str:
    """Hash only source rows that build model arrays, excluding visual assets."""
    from flyonenomics.datasets import MALE_ENGINE_SOURCES
    from flyonenomics.io import read_json

    manifest = read_json(ROOT / "data/malecns-v1.0-manifest.json")
    rows = {
        row["name"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
        for row in manifest["files"]
        if row["name"] in MALE_ENGINE_SOURCES
    }
    if set(rows) != set(MALE_ENGINE_SOURCES):
        raise ValueError("MaleCNS manifest is missing a model source")
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def pinned_inputs() -> dict[str, str]:
    from flyonenomics.io import hash_file, read_json

    pins = read_json(RECORDS / "malecns-substrate-inputs.json")["inputs_sha256"]
    for path, expected in pins.items():
        if path == "data/malecns-v1.0-manifest.json#male-engine-sources":
            actual = _model_manifest_sha256()
        else:
            actual = hash_file(ROOT / path)
        if actual != expected:
            raise ValueError(f"pinned input changed: {path}")
    return pins


def male_inputs() -> dict:
    """Resolve the same male arrays as the rest runner, without building an engine."""
    from flyonenomics.connectome_arrays import load_connectome_arrays
    from flyonenomics.datasets import get_dataset_adapter
    from flyonenomics.drive.background import group_indices
    from flyonenomics.registry import build_registry
    from flyonenomics.substrate.transmitters import load_transmitters
    from flyonenomics.types import load_params

    registry = build_registry(rest.MALE_VERSION)
    files = get_dataset_adapter(rest.MALE_VERSION).connectome_files()
    roots, pre, post, weights = load_connectome_arrays(files.completeness, files.connectivity)
    if not np.array_equal(roots, registry.root_ids):
        raise ValueError("male registry and engine order differ")
    transmitter = load_transmitters(ROOT / "data/transmitters-male-cns-v1.0.yaml")
    if transmitter["connectome_version"] != rest.MALE_VERSION:
        raise ValueError("transmitter table does not name the male graph")
    kc_mask = np.zeros(registry.n, dtype=np.uint8)
    kc_mask[registry.population("KC").idx] = 1
    return {
        "registry": registry, "groups": group_indices(registry), "files": files,
        "params": load_params(ROOT / "data/params-v0.2.yaml"),
        "scale_inputs": {"classes": np.asarray(transmitter["class_array"]),
                         "s_pq": np.sign(np.asarray(weights, dtype=np.float64)),
                         "pre": np.asarray(pre, dtype=np.int32), "post": np.asarray(post, dtype=np.int32),
                         "kc_mask": kc_mask, "n": registry.n, "connectome_version": rest.MALE_VERSION},
        "engine_arrays_sha256": {
            "roots_i64le": array_sha(roots, "<i8"), "pre_i32le": array_sha(pre, "<i4"),
            "post_i32le": array_sha(post, "<i4"), "signed_weights_f64le": array_sha(weights, "<f8"),
        },
    }


def release_table(params, names: list[str]) -> dict:
    """WP19 run_k2r's mean and release law on recorded seeds 1--3, no rerun."""
    from flyonenomics.io import hash_file, read_json
    from flyonenomics.neuromod.calibration import rest_release_constants

    measurement = read_json(RECORDS / "malecns-k2r-measurement.json")
    original_path = RECORDS / "malecns-rest.json"
    original = read_json(original_path)
    if (measurement["dataset"] != rest.MALE_VERSION
            or measurement["source_record_sha256"] != hash_file(original_path)):
        raise ValueError("K2r measurement binding differs")
    for name, digest in measurement["source_raw_sha256"].items():
        if original["raw"]["files_sha256"][name] != digest:
            raise ValueError(f"K2r raw source binding differs: {name}")
    rows = measurement["rows"]
    if [row["seed"] for row in rows] != [1, 2, 3]:
        raise ValueError("K2r requires seeds 1, 2, 3 in order")
    for row in rows:
        if (row["compartments"] != names or row["stage"] != "K2r-chain"
                or row["weight_mv"] != 1.0 or row["settle_s"] != 2.0 or row["measure_s"] != 5.0):
            raise ValueError("K2r row differs from the recorded protocol")
    rates = np.asarray([row["weighted_DAN_rates_by_compartment_hz"] for row in rows], dtype=float)
    if rates.shape != (3, len(names)) or not np.isfinite(rates).all() or np.any(rates < 0):
        raise ValueError("invalid measured K2r rates")
    r_c = rates.mean(axis=0)
    alpha, source, mode = rest_release_constants(r_c, params)
    result = {"R_c": r_c.tolist(), "alpha_c": alpha.tolist(), "S_c": source.tolist(), "mode": mode}
    chain = original["dopamine_calibration_chain"]
    for key, original_key in (("R_c", "R_c_weighted_spikes_per_s"),
                              ("alpha_c", "alpha_c_um_per_weighted_spike"),
                              ("S_c", "S_c_um_per_s"), ("mode", "mode")):
        if result[key] != chain[original_key]:
            raise ValueError(f"recomputed {key} differs from t-0069's recorded chain")
    return result


def regenerate() -> None:
    """Mint both numeric documents and identity, exclusively from pinned inputs."""
    from flyonenomics.drive.mechanisms import substrate_id_for
    from flyonenomics.drive.rest import apply_rest_substrate, blob_id, load_drive_rest, load_dopamine_v02
    from flyonenomics.io import hash_file
    from flyonenomics.neuromod.calibration import write_record

    pins = pinned_inputs()
    inputs = male_inputs()
    registry, params, groups = inputs["registry"], inputs["params"], inputs["groups"]
    drive = rest.ruled_drive(registry, 1.0)

    # WP19 _candidate_drive's scale-capture path, with explicitly male arrays.
    class ScaleTarget:
        def set_weight_scale(self, value):
            self.scale = value

    target = ScaleTarget()
    apply_rest_substrate(target, params, drive, **inputs["scale_inputs"])
    scale_sha = array_sha(target.scale, "<f4")
    names = [comp.name for comp in registry.compartments()]
    release = release_table(params, names)
    document = {
        "version": "male-cns-v1.0",
        "transmitter_rule": {"blob_id": blob_id(ROOT / "data/transmitters-male-cns-v1.0.yaml"), "scope": drive["scope"]},
        "scales": {key: drive[key] for key in ("g_gaba", "g_glu", "g_his", "g_gaba_kc")},
        "background": {"n_bg": int(drive["n_bg"]), "r_bg": drive["r_bg"],
                       "groups": {name: {"size": len(idx), "w_bg": drive["w_bg"][name]} for name, idx in groups.items()}},
        "threshold": None, "optic_exemption": drive["optic_exemption"], "mechanisms": None,
        "provenance": {"item": 155, "connectome_version": rest.MALE_VERSION,
                       "item_ruling": "Item 122 settings applied unchanged; no setting selected by a male firing outcome.",
                       "record": "validation/records/p2/malecns-rest.json",
                       "record_sha256": pins["validation/records/p2/malecns-rest.json"],
                       "inputs_record_sha256": hash_file(RECORDS / "malecns-substrate-inputs.json")},
    }
    document["scales"].update({"unk": "positive:1; negative:g_gaba", "sha256": scale_sha})
    drive_path = ROOT / "data/drive-male-cns-v1.0.yaml"
    dopamine_path = ROOT / "data/dopamine-male-cns-v1.0.yaml"
    write_record(drive_path, document)
    load_drive_rest(drive_path)
    dopamine = {
        "version": "male-cns-v1.0", "params_version": "v0.2",
        "receptor_map_version": "male-cns-v1.0", "connectome_version": rest.MALE_VERSION,
        "compartments": names, **release,
        "constants": {key: float(params.get(f"da.{key}")) for key in ("DA_ref", "Vmax", "Km", "k_ns", "R_min", "alpha_max")},
        "drive_blob_id": blob_id(drive_path),
        "provenance": {"source_method": "SPEC-P2 2.5 / WP19 K2r: mean of clamped seeds 1--3; rest_release_constants",
                       "K2r_record": "validation/records/p2/malecns-k2r-measurement.json",
                       "K2r_record_sha256": pins["validation/records/p2/malecns-k2r-measurement.json"],
                       "iteration": 1, "item": 155,
                       "upstream_blobs": {"data/drive-male-cns-v1.0.yaml": blob_id(drive_path)}},
    }
    write_record(dopamine_path, dopamine)
    load_dopamine_v02(dopamine_path, names)
    substrate = substrate_id_for(drive_path)
    if substrate == "rest:379cc4cc9030cdd1":
        raise ValueError("male identity must not reuse FlyWire's identity")
    record = {
        "dataset": rest.MALE_VERSION, "item": 155, "substrate_id": substrate, "engine_model": "lif",
        "inputs_sha256": pins, "engine_arrays_sha256": inputs["engine_arrays_sha256"],
        "outputs_sha256": {str(path.relative_to(ROOT)): hash_file(path) for path in (drive_path, dopamine_path)},
        "scale_f32le_sha256": scale_sha,
        "dopamine_chain_exactly_equals_recorded_chain": True,
        "regenerate": "FLYONENOMICS_CACHE_DIR=$HOME/flyo-cache .venv/bin/python scripts/malecns_substrate.py --regenerate",
        "interpretation": "Declared starting configuration, not a fitted male outcome or a biological claim; no free-pool calibration iteration or behavioural gate.",
    }
    rest._atomic_json(RECORDS / "malecns-substrate.json", record)
    print(substrate, flush=True)


def probe() -> None:
    """Build from the minted files and run 1 s with free dopamine pools."""
    from flyonenomics.drive.mechanisms import mechanisms_from_drive, substrate_id_for
    from flyonenomics.drive.rest import apply_rest_substrate, blob_id, load_drive_rest, load_dopamine_v02, rest_background_weights
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.io import hash_file, read_json
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.types import LayerFlags

    started = time.perf_counter()
    pins = pinned_inputs()
    record = read_json(RECORDS / "malecns-substrate.json")
    for path, expected in record["outputs_sha256"].items():
        if hash_file(ROOT / path) != expected:
            raise ValueError(f"minted table changed: {path}")
    inputs = male_inputs()
    registry, params = inputs["registry"], inputs["params"]
    drive_path = ROOT / "data/drive-male-cns-v1.0.yaml"
    dopamine_path = ROOT / "data/dopamine-male-cns-v1.0.yaml"
    drive = load_drive_rest(drive_path)
    dopamine = load_dopamine_v02(dopamine_path, [c.name for c in registry.compartments()])
    if dopamine["drive_blob_id"] != blob_id(drive_path):
        raise ValueError("dopamine binding differs from the male drive")
    if drive["transmitters_blob_id"] != blob_id(ROOT / "data/transmitters-male-cns-v1.0.yaml"):
        raise ValueError("drive binding differs from the male transmitter table")
    engine = BrianEngine()
    engine.seed(brian_seed(rest.MASTER_SEED, 1, 0))
    engine.build(inputs["files"], params, InputTopology(background=True),
                 mechanisms=mechanisms_from_drive(drive, registry=registry))
    base, _scale = apply_rest_substrate(engine, params, drive, **inputs["scale_inputs"])
    engine.set_background(rest_background_weights(registry, drive, params))
    mod = Neuromod(registry, params, LayerFlags(background=True, dopamine_A=True, transporter_C=True),
                  dopamine, base_v_th=base, schema_version="1.3", drive_groups=inputs["groups"])
    mod.clamp_pools(False)
    mod.reset_fast()
    initial_da = mod.da_c.tolist()
    composed = mod.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)
    engine.compose_refractory()
    build_wall = time.perf_counter() - started
    engine.seed(brian_seed(rest.MASTER_SEED, 1, 0))
    run_started = time.perf_counter()
    counts = np.zeros(registry.n, dtype=np.int64)
    chunk_ms = float(params.get("engine.chunk_ms"))
    for _ in range(round(1000.0 / chunk_ms)):
        result = engine.run_chunk(chunk_ms)
        counts += result.counts
        mod.on_chunk(result.counts, chunk_ms / 1000.0)
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
    run_wall = time.perf_counter() - run_started
    files = inputs["files"]
    payload = {
        "dataset": rest.MALE_VERSION, "substrate_id": substrate_id_for(drive_path),
        "engine_model": engine.engine_model(), "neurons": engine.n, "edges": engine.n_syn,
        "master_seed": rest.MASTER_SEED, "seed_index": 1, "brian_seed": brian_seed(rest.MASTER_SEED, 1, 0),
        "duration_s": 1.0, "settle_s": 0.0,
        "state": "wild type; sensory-only 1.0 mV; background and layers A/C on; free pools; no drug",
        "inputs_sha256": {**pins, **record["outputs_sha256"]},
        "connectome_files_sha256": {files.completeness.name: hash_file(files.completeness),
                                    files.connectivity.name: hash_file(files.connectivity)},
        "engine_arrays_sha256": inputs["engine_arrays_sha256"],
        "spikes": int(counts.sum()), "counts_i64le_sha256": array_sha(counts, "<i8"),
        "initial_da_um": initial_da, "final_da_um": mod.da_c.tolist(),
        "build_wall_s": build_wall, "run_wall_s": run_wall, "total_wall_s": time.perf_counter() - started,
        "peak_rss_bytes": rest._peak_rss_bytes(), "platform": rest._platform(),
        "interpretation": "One-second execution check only; not a rest, free-pool stability, visual or behavioural outcome.",
    }
    rest._atomic_json(RECORDS / "malecns-substrate-probe.json", payload)
    print(f"{payload['substrate_id']}: 1 s ran in {run_wall:.3f} wall s", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--seed-check", action="store_true")
    modes.add_argument("--import-k2r", type=Path, metavar="RAW_DIRECTORY")
    modes.add_argument("--regenerate", action="store_true")
    modes.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.seed_check:
        seed_check()
    elif args.import_k2r:
        import_k2r(args.import_k2r)
    elif args.regenerate:
        regenerate()
    else:
        probe()


if __name__ == "__main__":
    main()
