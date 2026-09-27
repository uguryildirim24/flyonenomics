#!/usr/bin/env python3
"""MaleCNS history experiment. Part A only until coordinator authorises 5a.

See docs/adhd-study-design.md. No inherited FlyWire dynamic preparation.
Raw per-arm NPZs and complete-seed JSON manifests are written atomically.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import ctypes
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import resource
import subprocess
import time
from typing import Any

import numpy as np

import adhd_analysis as analysis

ROOT = Path(__file__).resolve().parents[1]
MASTER = 20260912
SETTLE = 2.0
PREFIX, GAP, TEST = 5.0, 1.0, 14.0
PRIMARY = 2.0
DURATION = SETTLE + PREFIX + GAP + TEST
VERSION = "male-cns:v1.0"
PLAN = ROOT / "validation/records/p2/adhd-study-plan.json"
CONFIRM_PLAN = ROOT / "validation/records/p2/adhd-confirm-plan.json"
CALIBRATION_PLAN = ROOT / "validation/records/p2/adhd-study-calibration-plan.json"
PAIR = ROOT / "validation/records/p2/adhd-study-pair.json"
RUNS = ROOT / "camber-runs/adhd-study"


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def read(path: Path) -> Any:
    from flyonenomics.io import read_json
    return read_json(path)


def sha(path: Path) -> str:
    from flyonenomics.io import hash_file
    return hash_file(path)


def digest(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def code_identity() -> dict[str, Any]:
    """Bind imports, data and the actual git tree; never take a caller's SHA on trust."""
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT, check=True)
    upstream_record = ROOT / "validation/records/p2/malecns-substrate-inputs.json"
    import malecns_substrate as male

    # The adopted pin includes a semantic manifest section, not a pathname.
    # Verify through its defining loader and carry the verified hashes verbatim.
    upstream = male.pinned_inputs()
    paths = [upstream_record, CALIBRATION_PLAN, ROOT / "validation/records/p2/malecns-substrate.json",
             *sorted((ROOT / "src").rglob("*.py")),
             ROOT / "scripts/adhd_study.py", ROOT / "scripts/adhd_analysis.py",
             ROOT / "scripts/malecns_substrate.py", ROOT / "scripts/malecns_rest.py",
             ROOT / "uv.lock", ROOT / "docs/adhd-study-design.md", ROOT / "docs/adhd-confirm-design.md",
             ROOT / "data/params-v0.2.yaml", *sorted((ROOT / "data").glob("*-male-cns-v1.0.yaml"))]
    return {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "sha256": {**upstream, **{str(p.relative_to(ROOT)): sha(p) for p in sorted(set(paths))}},
            "platform": f"{platform.system().lower()}-{platform.machine()}",
            "python": platform.python_version()}


def load_inputs() -> dict[str, Any]:
    import malecns_substrate as male
    from flyonenomics.drive.mechanisms import substrate_id_for
    from flyonenomics.drive.rest import blob_id, load_drive_rest, load_dopamine_v02

    male.pinned_inputs()
    ctx = male.male_inputs()
    registry = ctx["registry"]
    drive_path = ROOT / "data/drive-male-cns-v1.0.yaml"
    dopamine_path = ROOT / "data/dopamine-male-cns-v1.0.yaml"
    record = read(ROOT / "validation/records/p2/malecns-substrate.json")
    for path, expected in record["outputs_sha256"].items():
        if sha(ROOT / path) != expected:
            raise ValueError(f"adopted male table changed: {path}")
    ctx["drive"] = load_drive_rest(drive_path)
    ctx["dopamine"] = load_dopamine_v02(dopamine_path, [c.name for c in registry.compartments()])
    if ctx["dopamine"]["drive_blob_id"] != blob_id(drive_path):
        raise ValueError("dopamine/drive binding differs")
    if ctx["drive"]["transmitters_blob_id"] != blob_id(ROOT / "data/transmitters-male-cns-v1.0.yaml"):
        raise ValueError("drive/transmitter binding differs")
    ctx["substrate_id"] = substrate_id_for(drive_path)
    if ctx["substrate_id"] != record["substrate_id"] or ctx["substrate_id"] == "rest:379cc4cc9030cdd1":
        raise ValueError("not the adopted male substrate")
    if ctx["engine_arrays_sha256"] != record["engine_arrays_sha256"]:
        raise ValueError("male graph changed")
    ctx["source"] = np.asarray(registry.population("TuBu").idx, dtype=np.int32)
    er = registry.population("ER").idx
    pre, post = (ctx["scale_inputs"][key] for key in ("pre", "post"))
    ctx["targets"] = np.intersect1d(post[np.isin(pre, ctx["source"])], er).astype(np.int32)
    if len(ctx["targets"]) != 245:
        raise ValueError("male anatomy trace set is not 245 cells")
    return ctx


def neuromod(ctx: dict[str, Any], condition: str, fraction: float, engine: Any) -> Any:
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.schema.experiment import ScaleRelease
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags

    mod = Neuromod(ctx["registry"], ctx["params"],
                  LayerFlags(background=True, dopamine_A=True, transporter_C=True, dan_fast_synapses="retain"),
                  ctx["dopamine"], base_v_th=ctx.get("base_threshold"), schema_version="1.3",
                  drive_groups=ctx["groups"])
    hooks = named_manipulations("fumin" if condition.startswith("fumin") else "wild_type")
    if condition.endswith("release"):
        hooks = [*hooks, ScaleRelease(type="scale_release", factor=fraction)]
    mod.apply_genotype(hooks, engine)
    mod.reset_fast()
    return mod


def encoder_patterns(ctx: dict[str, Any]) -> dict[str, Any]:
    """Stage-4 encoder-only matching, recalculated on male cells; common cap for pairs."""
    from flyonenomics.behaviour.encoder import VisualEncoder

    source = ctx["source"]
    encoder = VisualEncoder(ctx["registry"], source, ctx["params"], "TuBu")
    grid = tuple(float(v) for v in range(-150, 151, 25))
    unit = {theta: encoder.rates([{"az_fly": theta, "contrast": 1.0}], maximum_hz=1, sigma_deg=20)
            for theta in grid}
    mass = min(float(v.sum()) for v in unit.values()) * 70
    contrast = {str(theta): mass / (70 * float(v.sum())) for theta, v in unit.items()}
    singles = {str(theta): encoder.rates([{"az_fly": theta, "contrast": contrast[str(theta)]}],
                                        maximum_hz=70, sigma_deg=20).tolist() for theta in analysis.POSITIONS}
    pairs = {}
    for a, b in analysis.PAIR_ORDER:
        rates = encoder.rates([{"az_fly": v, "contrast": contrast[str(v)]} for v in (a, b)],
                              maximum_hz=70, sigma_deg=20)
        summed = np.asarray(singles[str(a)]) + singles[str(b)]
        pairs[f"{a},{b}"] = {"rates_hz": rates.tolist(), "summed_single_rates_hz": float(summed.sum()),
                               "actual_total_rate_hz": float(rates.sum()),
                               "lost_to_cap_hz": float((summed - rates).sum()),
                               "equals_a": bool(np.array_equal(rates, singles[str(a)])),
                               "equals_b": bool(np.array_equal(rates, singles[str(b)]))}
    return {"mapping": "ascending body-ID grid by side; imposed TuBu labels, not seen coordinates",
            "preferred_deg": encoder.preferred.tolist(), "sigma_deg": 20, "cap_hz": 70,
            "single_total_rate_hz": mass, "contrast": contrast, "single_rates_hz": singles, "pairs": pairs}


def male_array_binding(ctx: dict[str, Any], scale: np.ndarray) -> dict[str, Any]:
    """Evidence for the explicitly supplied male arrays, shared by every arm."""
    inputs = ctx["scale_inputs"]
    return {"connectome_version": inputs["connectome_version"],
            "n_neurons": inputs["n"], "n_edges": int(len(inputs["pre"])),
            "classes_S4_sha256": digest(np.asarray(inputs["classes"], dtype="S4")),
            "kc_mask_u8_sha256": digest(np.asarray(inputs["kc_mask"], dtype=np.uint8)),
            "edge_sign_f64le_sha256": digest(np.asarray(inputs["s_pq"], dtype="<f8")),
            "scale_f32le_sha256": digest(np.asarray(scale, dtype="<f4")),
            "engine_arrays_sha256": ctx["engine_arrays_sha256"],
            "path": "male_inputs -> explicit scale_inputs -> apply_rest_substrate -> study_initial snapshot",
            "arm_path": "restore study_initial; no weight, edge, transmitter or KC-mask manipulation"}


def freeze(destination: Path) -> None:
    """Static chemistry/anatomy and synthetic validation; does not instantiate BrianEngine."""
    from flyonenomics.datasets import get_dataset_adapter
    from flyonenomics.drive.rest import apply_rest_substrate

    ctx = load_inputs()
    params, registry = ctx["params"], ctx["registry"]
    constants = {key: float(params.get("da." + key)) for key in ("DA_ref", "Vmax", "Km", "k_ns")}
    for key, value in constants.items():
        if value != ctx["dopamine"]["constants"][key]:
            raise ValueError(f"runtime chemistry differs from adopted table: {key}")
    ref, vmax, km, kns = (constants[key] for key in ("DA_ref", "Vmax", "Km", "k_ns"))
    fraction = kns * ref / (vmax * ref / (km + ref) + kns * ref)

    class Sink:
        def set_threshold(self, value): pass
        def set_gain(self, value): pass
        def set_weight_scale(self, value): self.scale = value

    sink = Sink()
    ctx["base_threshold"], scale = apply_rest_substrate(sink, params, ctx["drive"], **ctx["scale_inputs"])
    chemistry = {}
    for condition in analysis.CONDITIONS:
        mod = neuromod(ctx, condition, fraction, sink)
        vm, effective_km, release = mod._kinetics()
        chemistry[condition] = {"initial_pools_um": mod.da_c.tolist(), "vmax_um_s": vm.tolist(),
                                "km_um": effective_km.tolist(), "release_fraction": release,
                                "source_um_s": (release * (mod.alpha * mod.r_tonic + mod.s_c)).tolist(),
                                "innervated": mod.mask.tolist()}
    pre, post = (ctx["scale_inputs"][key] for key in ("pre", "post"))
    # Audit all ER->ER, including ER1 cells excluded from the TuBu-reached readout.
    all_er = np.asarray(registry.population("ER").idx)
    edge_mask = np.isin(pre, all_er) & np.isin(post, all_er)
    from flyonenomics.connectome_arrays import load_connectome_arrays
    _, _, _, raw = load_connectome_arrays(ctx["files"].completeness, ctx["files"].connectivity)
    weights = np.asarray(raw[edge_mask]) * float(params.get("lif.w_syn")) * scale[edge_mask]
    annotations = get_dataset_adapter(VERSION).load_annotations().set_index("root_id")
    cells = []
    for index in ctx["targets"]:
        root = int(registry.root_ids[index])
        row = annotations.loc[root]
        cells.append({"engine_index": int(index), "body_id": root, "side": str(row["side"]),
                      "type": str(row["hemibrain_type"])})
    result = {"analysis_version": analysis.VERSION, "identity": code_identity(),
              "substrate_id": ctx["substrate_id"], "engine_arrays_sha256": ctx["engine_arrays_sha256"],
              "male_array_binding": male_array_binding(ctx, scale),
              "constants": constants, "release_fraction": fraction, "chemistry": chemistry,
              "compartments": [c.name for c in registry.compartments()], "cells": cells,
              "source_indices": ctx["source"].tolist(),
              "source_body_ids": registry.root_ids[ctx["source"]].tolist(),
              "encoder": encoder_patterns(ctx),
              "er_edges": {"pre": pre[edge_mask].tolist(), "post": post[edge_mask].tolist(),
                           "composed_weight_mv": weights.tolist()},
              "timing": {"settle_s": SETTLE, "5a_s": 20, "prefix_s": PREFIX, "gap_s": GAP,
                         "test_s": TEST, "primary_s": [0, PRIMARY]},
              "seeds": {"master": MASTER, "5a": list(range(101, 111)), "5b": list(range(201, 211)), "probe": 901},
              "synthetic": analysis.synthetic_validation()}
    # d-0025 retains the existing calibration/pair only under the same per-arm
    # model law. Bind the immutable old plan explicitly, never relabel its runs.
    from flyonenomics.drive.paired_inputs import VERSION as input_version
    calibration, pair = read(CALIBRATION_PLAN), read(PAIR)
    for name, value in calibration.items():
        if name != "identity" and result[name] != value:
            raise ValueError(f"calibration model/design field changed: {name}")
    for name, expected in calibration["identity"]["sha256"].items():
        if name != "scripts/adhd_study.py" and result["identity"]["sha256"].get(name) != expected:
            raise ValueError(f"existing non-plumbing source changed: {name}")
    if pair["plan_sha256"] != sha(CALIBRATION_PLAN) or pair["prerequisite"] != "represented":
        raise ValueError("original calibration/pair binding differs")
    result["random_inputs"] = {"version": input_version, "decision": "d-0025",
        "tubu": "PCG64 SeedSequence(master, spawn_key=(25,seed,segment,stimulus)); fixed per-tick Bernoulli event lists",
        "background": "unchanged Brian2 BinomialFunction; draw for all targets before unchanged refractory-gated g application",
        "engine_defaults_and_flywire_reference_unchanged": True}
    result["calibration_reference"] = {"plan_sha256": sha(CALIBRATION_PLAN), "pair_sha256": sha(PAIR),
        "decision": "d-0025", "basis": "same per-arm model/input law; old plumbing and committed pair retained",
        "original_plan_identity": calibration["identity"], "byte_verified_seeds": [101, 102],
        "remaining_old_plumbing_replay": "not required; skipped by coordinator"}
    dump(destination, result)
    print(json.dumps({"substrate_id": result["substrate_id"], "release_fraction": fraction,
                      "initial_pool_ranges_um": {k: [min(v["initial_pools_um"]), max(v["initial_pools_um"])]
                                                 for k, v in chemistry.items()}}, indent=2), flush=True)


def freeze_confirm(destination: Path) -> None:
    """Bind the already adopted 5b substrate and pair; no neural run or outcome read."""
    old = read(PLAN)
    identity = code_identity()
    pair = read(PAIR)
    if old["substrate_id"] != "rest:ed9b0a469d7a6b77" or pair["pair"] != [-50.0, 50.0]:
        raise ValueError("reviewed substrate or calibration pair differs")
    if sha(PAIR) != old["calibration_reference"]["pair_sha256"]:
        raise ValueError("reviewed pair hash differs")
    from flyonenomics.drive.paired_inputs import VERSION as input_version
    if old["random_inputs"]["version"] != input_version:
        raise ValueError("input plumbing changed")
    for name, expected in old["identity"]["sha256"].items():
        if name not in ("scripts/adhd_study.py", "scripts/adhd_analysis.py") and identity["sha256"].get(name) != expected:
            raise ValueError(f"reviewed model changed: {name}")
    plan = {**old, "identity": identity, "analysis_version": "male-history-confirm-v1",
            "confirmation": {"seeds": list(range(301, 341)), "conditions": list(analysis.CONFIRM_CONDITIONS),
                "protocols": [list(p) for p in analysis.CONFIRM_PROTOCOLS],
                "bootstrap_seed": analysis.CONFIRM_BOOTSTRAP_SEED, "bootstraps": analysis.BOOTSTRAPS,
                "sign_seed": analysis.CONFIRM_SIGN_SEED, "sign_draws": analysis.CONFIRM_SIGNS,
                "alpha_two_sided": 0.05, "direction": "negative", "pilot_plan_sha256": sha(PLAN),
                "pilot_result_sha256": sha(ROOT / "validation/records/p2/adhd-study-results.json"),
                "calibration_plan_sha256": old["calibration_reference"]["plan_sha256"]}}
    dump(destination, plan)


def confirm_identity(plan: dict[str, Any]) -> dict[str, Any]:
    """The plan commit is the preceding code commit; hash each pinned file instead."""
    identity = code_identity()
    if identity["sha256"] != plan["identity"]["sha256"]:
        raise ValueError("frozen confirmation source/input hashes differ")
    return identity


def build(plan: dict[str, Any]) -> dict[str, Any]:
    import brian2 as b
    from flyonenomics.drive.rest import apply_rest_substrate, rest_background_weights
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.drive.paired_inputs import state_independent_background

    start = time.perf_counter()
    ctx = load_inputs()
    if ctx["substrate_id"] != plan["substrate_id"] or ctx["engine_arrays_sha256"] != plan["engine_arrays_sha256"]:
        raise ValueError("plan substrate mismatch")
    if ctx["targets"].tolist() != [c["engine_index"] for c in plan["cells"]]:
        raise ValueError("trace order mismatch")
    engine = BrianEngine()
    engine.seed(MASTER)
    # Opt-in study plumbing only: ordinary engine/FlyWire defaults are untouched.
    engine.build(ctx["files"], ctx["params"], InputTopology(spikelist_idx=ctx["source"]), mechanisms=None)
    background = state_independent_background(engine._neu, int(ctx["params"].get("bg.n_bg")),
                                              float(ctx["params"].get("bg.r_bg")))
    engine._net.add(background)
    ctx["base_threshold"], scale = apply_rest_substrate(engine, ctx["params"], ctx["drive"], **ctx["scale_inputs"])
    ctx["male_array_binding"] = male_array_binding(ctx, scale)
    if ctx["male_array_binding"] != plan["male_array_binding"]:
        raise ValueError("explicit male arrays differ from the frozen plan")
    engine.set_background(rest_background_weights(ctx["registry"], ctx["drive"], ctx["params"]))
    # Record injected events independently of emitted TuBu events. Added before snapshot.
    monitor = b.SpikeMonitor(engine._gen, name="study_injected_events")
    engine._net.add(monitor)
    engine.store("study_initial")
    ctx.update(engine=engine, injected=monitor, build_wall_s=time.perf_counter() - start)
    return ctx


def rng_state_hash(state: dict[str, Any], buffer_size: int) -> str:
    """Hash future random draws, not Brian's process-local buffer addresses.

    RuntimeDevice.get_random_state stores pointers for rand/randn buffers.
    Cython refills a buffer at index zero; otherwise only its unread suffix
    affects subsequent draws. Hash that suffix, the index and NumPy's state.
    """
    algorithm, keys, position, has_gauss, cached_gauss = state["numpy_state"]
    logical: dict[str, Any] = {"method": "brian-runtime-next-draws-v1", "algorithm": algorithm,
               "keys_u32le_sha256": digest(np.asarray(keys, dtype="<u4")),
               "position": int(position), "has_gauss": int(has_gauss),
               "cached_gauss": float(cached_gauss) if has_gauss else None,
               "cython_buffer_size": buffer_size, "buffers": {}}
    for name in ("rand", "randn"):
        index = int(state[name + "_buffer_index"][0])
        if not 0 <= index < buffer_size:
            raise ValueError("invalid Brian random-buffer index")
        remaining = None
        if index:
            address = int(state[name + "_buffer"][0])
            if address == 0:
                raise ValueError("active Brian random buffer has no storage")
            values = np.ctypeslib.as_array((ctypes.c_double * buffer_size).from_address(address))
            remaining = digest(np.asarray(values[index:], dtype="<f8"))
        logical["buffers"][name] = {"index": index, "remaining_f64le_sha256": remaining}
    return hashlib.sha256(json.dumps(logical, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def rng_hash() -> str:
    import brian2 as b
    from brian2.codegen.generators.cython_generator import _BUFFER_SIZE
    return rng_state_hash(b.get_device().get_random_state(), _BUFFER_SIZE)


def atomic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
    temporary.replace(path)


def arm(ctx: dict[str, Any], plan: dict[str, Any], seed: int, stage: str, condition: str,
        protocol: Any, patterns: dict[str, np.ndarray], path: Path, *,
        diagnostic_timing: dict[str, Any] | None = None) -> dict[str, Any]:
    import brian2 as b
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.drive.paired_inputs import VERSION as input_version, trial_events, trial_segments

    if diagnostic_timing is not None and stage != "diagnostic":
        raise ValueError("short timing is diagnostic-only; never a scientific arm")
    timing = plan["timing"] if diagnostic_timing is None else diagnostic_timing

    engine, registry, targets = ctx["engine"], ctx["registry"], ctx["targets"]
    source = ctx["source"]
    engine.restore("study_initial")
    engine.seed(brian_seed(MASTER, seed, 0))
    mod = neuromod(ctx, condition, plan["release_fraction"], engine)
    if mod.da_c.tolist() != plan["chemistry"][condition]["initial_pools_um"]:
        raise ValueError("initial chemical pools changed")
    engine.compose_refractory()
    chunk_s = float(ctx["params"].get("engine.chunk_ms")) / 1000
    duration = sum(segment[2] for segment in trial_segments(stage, protocol, timing))
    steps = round(duration / chunk_s)
    settle_end = round(timing["settle_s"] / chunk_s)
    test_start = timing["settle_s"] if stage in ("5a", "probe") else sum(timing[k] for k in ("settle_s", "prefix_s", "gap_s"))
    response_s = timing["5a_s"] if stage in ("5a", "probe") else timing["primary_s"][1]
    planned_ticks, planned_indices = trial_events(MASTER, seed, stage, protocol, patterns, timing, engine.dt_ms)
    engine.set_spike_list(np.asarray(source[planned_indices], dtype=np.int32), planned_ticks)
    arrays = {"er_counts": np.empty((steps, len(targets)), np.int32),
              "tubu_counts": np.empty((steps, len(source)), np.int32),
              "pool_um": np.empty((steps + 1, len(mod.mask))),
              "er_dv_mv": np.empty((steps, len(targets))), "er_gain": np.empty((steps, len(targets))),
              "er_occ1": np.empty((steps, len(targets))), "er_occ2": np.empty((steps, len(targets)))}
    groups = {"DAN": np.union1d(registry.population("DAN").idx, registry.population("CX_DAN").idx),
              "CX_DAN": registry.population("CX_DAN").idx, "central": ctx["groups"]["central"]}
    for name in groups:
        arrays[name + "_counts"] = np.empty(steps, np.int64)
    pre_er = np.unique(np.asarray(plan["er_edges"]["pre"], dtype=np.int32))
    arrays["er_edge_presynaptic_counts"] = np.empty((steps, len(pre_er)), np.int32)
    arrays["er_edge_presynaptic_indices"] = pre_er
    arrays["pool_um"][0] = mod.da_c
    rng_initial = rng_hash()
    start = time.perf_counter()
    for step in range(steps):
        dv, gain, occ1, occ2 = mod.receptor_terms()
        # Same composition as Neuromod.compose; record the actually clipped application.
        engine.set_threshold(np.clip(mod.base_v_th + mod.shift + dv, *ctx["params"].get("rec.vth_clip")))
        applied_gain = np.clip(mod.geno_gain * gain, *ctx["params"].get("rec.gain_clip"))
        engine.set_gain(applied_gain)
        arrays["er_dv_mv"][step] = engine.thresholds_mv()[targets] - mod.base_v_th[targets]
        arrays["er_gain"][step] = applied_gain[targets]
        arrays["er_occ1"][step], arrays["er_occ2"][step] = occ1[targets], occ2[targets]
        result = engine.run_chunk(chunk_s * 1000)
        arrays["er_counts"][step], arrays["tubu_counts"][step] = result.counts[targets], result.counts[source]
        arrays["er_edge_presynaptic_counts"][step] = result.counts[pre_er]
        for name, indices in groups.items():
            arrays[name + "_counts"][step] = result.counts[indices].sum()
        mod.on_chunk(result.counts, chunk_s)
        arrays["pool_um"][step + 1] = mod.da_c
    wall = time.perf_counter() - start
    rng_final = rng_hash()
    monitor = ctx["injected"]
    ticks = np.rint(np.asarray(monitor.t[:] / b.ms) / engine.dt_ms).astype(np.int64)
    indices = np.asarray(monitor.i[:], dtype=np.int32)
    if not np.array_equal(ticks, planned_ticks) or not np.array_equal(indices, planned_indices):
        raise ValueError("actual injected events differ from pre-generated fixed list")
    arrays["injected_ticks"], arrays["injected_tubu_positions"] = ticks, indices
    for key in ("D1", "D2"):
        arrays["pool_occ_" + key] = arrays["pool_um"] / (arrays["pool_um"] + ctx["params"].get("rec.Kd_" + key))
    begin, end = round(test_start / chunk_s), round((test_start + response_s) / chunk_s)
    arrays["response_er_hz"] = arrays["er_counts"][begin:end].sum(axis=0) / response_s
    arrays["response_tubu_hz"] = arrays["tubu_counts"][begin:end].sum(axis=0) / response_s
    test_mask = ticks >= round(test_start * 1000 / engine.dt_ms)
    event_hash = digest(np.column_stack((ticks[test_mask], indices[test_mask])))
    atomic_npz(path, arrays)
    return {"condition": condition, "protocol": protocol, "file": path.name, "sha256": sha(path),
            "male_array_binding": ctx["male_array_binding"],
            "wall_s": wall, "chunk_s": chunk_s, "dt_ms": engine.dt_ms,
            "response_window_s": [test_start, test_start + response_s],
            "input_plumbing_version": input_version,
            "planned_injected_events_sha256": digest(np.column_stack((planned_ticks, planned_indices))),
            "actual_events_equal_fixed_list": True,
            "rng_hash_method": "brian-runtime-next-draws-v1",
            "rng_initial_sha256": rng_initial, "rng_final_sha256": rng_final,
            "injected_test_events_sha256": event_hash, "group_n": {k: len(v) for k, v in groups.items()},
            "settle_pool_drift_um": (arrays["pool_um"][settle_end] - arrays["pool_um"][0]).tolist(),
            "initial_pool_um": arrays["pool_um"][0].tolist(), "end_settle_pool_um": arrays["pool_um"][settle_end].tolist()}


def audit_rows(rows: list[dict[str, Any]], *, history: bool) -> None:
    if len({r["rng_initial_sha256"] for r in rows}) != 1 or len({r["rng_final_sha256"] for r in rows}) != 1:
        raise ValueError("external random stream consumption differs across arms")
    if history:
        for test in sorted({r["protocol"][1] for r in rows}):
            hashes = {r["injected_test_events_sha256"] for r in rows if r["protocol"][1] == test}
            if len(hashes) != 1:
                raise ValueError("identical final stimuli did not receive identical external events")


def diagnostic_seed(job: tuple[int, str, str, str, dict[str, Any]]) -> str:
    """d-0025 short, non-inferential check using the actual full male engine."""
    seed, plan_path, output, pair_path, identity = job
    plan, pair = read(Path(plan_path)), read(Path(pair_path))
    if (confirm_identity(plan) if "confirmation" in plan else code_identity()) != identity:
        raise ValueError("diagnostic source changed after launch")
    if sha(Path(pair_path)) != plan["calibration_reference"]["pair_sha256"]:
        raise ValueError("diagnostic pair differs from frozen reference")
    ctx = build(plan)
    a, b = pair["pair"]
    patterns = {"off": np.zeros(len(ctx["source"])),
                "A": np.asarray(plan["encoder"]["single_rates_hz"][str(a)]),
                "B": np.asarray(plan["encoder"]["single_rates_hz"][str(b)]),
                "AB": np.asarray(plan["encoder"]["pairs"][f"{a},{b}"]["rates_hz"])}
    timing = dict(settle_s=.02, prefix_s=.04, gap_s=.02, test_s=.12, primary_s=[0, .12])
    rows = []
    arms = ([(c, p) for c in analysis.CONFIRM_CONDITIONS for p in analysis.CONFIRM_PROTOCOLS]
            if "confirmation" in plan else [("wt-vehicle", (p, "AB")) for p in ("off", "A", "B")])
    for i, (condition, protocol) in enumerate(arms):
        path = Path(output) / f"seed-{seed}-arm-{i:02}.npz"
        row = arm(ctx, plan, seed, "diagnostic", condition, protocol, patterns, path,
                  diagnostic_timing=timing)
        dump(path.with_suffix(".json"), {"seed": seed, "stage": "diagnostic", "identity": identity,
                                       "plan_sha256": sha(Path(plan_path)), "pair_sha256": sha(Path(pair_path)),
                                       "timing": timing, "row": row})
        rows.append(row)
        print(f"diagnostic seed {seed} {condition} {protocol} complete", flush=True)
    audit_rows(rows, history=True)
    file = Path(output) / f"seed-{seed}.json"
    dump(file, {"seed": seed, "stage": "diagnostic", "not_for_inference": True, "identity": identity,
                "timing": timing, "plan_sha256": sha(Path(plan_path)), "pair_sha256": sha(Path(pair_path)),
                "rows": rows, "exact_rng_and_injected_event_audits_passed": True})
    return str(file)


def run_diagnostic(plan_path: Path, output: Path, workers: int, pair: Path) -> None:
    if not 1 <= workers <= 2:
        raise ValueError("diagnostic uses at most two workers")
    plan = read(plan_path)
    identity = confirm_identity(plan) if "confirmation" in plan else code_identity()
    for name, expected in plan["identity"]["sha256"].items():
        if identity["sha256"].get(name) != expected:
            raise ValueError(f"frozen diagnostic source differs: {name}")
    output.mkdir(parents=True, exist_ok=False)
    jobs = [(seed, str(plan_path.resolve()), str(output.resolve()), str(pair.resolve()), identity)
            for seed in ((291, 292) if "confirmation" in plan else (201, 202))]
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
                             max_tasks_per_child=1) as pool:
        print(list(pool.map(diagnostic_seed, jobs)), flush=True)


def run_seed(job: tuple[int, str, str, str, str | None, dict[str, Any]]) -> str:
    seed, stage, plan_path, output, pair_path, identity = job
    start = time.perf_counter()
    if code_identity() != identity:
        raise ValueError("worker source changed after launch")
    plan_hash = sha(Path(plan_path))
    pair_hash = sha(Path(pair_path)) if pair_path else None
    plan = read(Path(plan_path))
    destination = Path(output)
    ctx = build(plan)
    zero = np.zeros(len(ctx["source"]))
    patterns = {"off": zero, **{key: np.asarray(v) for key, v in plan["encoder"]["single_rates_hz"].items()}}
    if stage in ("5b", "confirm"):
        pair_record = read(Path(pair_path))
        if (pair_hash != plan["calibration_reference"]["pair_sha256"]
                or pair_record["plan_sha256"] != plan["calibration_reference"]["plan_sha256"]):
            raise ValueError("pair differs from the retained calibration reference")
        a, b = pair_record["pair"]
        pair_rates = plan["encoder"]["pairs"][f"{a},{b}"]
        if pair_rates["equals_a"] or pair_rates["equals_b"]:
            raise ValueError("prerequisite failure: encoder removed a pair member")
        patterns.update(A=patterns[str(a)], B=patterns[str(b)], AB=np.asarray(pair_rates["rates_hz"]))
        conditions = analysis.CONFIRM_CONDITIONS if stage == "confirm" else analysis.CONDITIONS
        protocols = analysis.CONFIRM_PROTOCOLS if stage == "confirm" else analysis.PROTOCOLS
        arms = [(condition, protocol) for condition in conditions for protocol in protocols]
    else:
        positions = ("-50.0",) if stage == "probe" else ("off", *map(str, analysis.POSITIONS))
        arms = [("wt-vehicle", position) for position in positions]
    rows = []
    for i, (condition, protocol) in enumerate(arms):
        path = destination / f"seed-{seed}-arm-{i:02}.npz"
        row = arm(ctx, plan, seed, stage, condition, protocol, patterns, path)
        # Preserve actual audit metadata even when a later whole-seed check fails.
        dump(path.with_suffix(".json"), {"seed": seed, "stage": stage, "identity": identity,
                                       "plan_sha256": plan_hash, "pair_sha256": pair_hash, "row": row})
        rows.append(row)
        print(f"{stage} seed {seed} arm {i + 1}/{len(arms)} complete", flush=True)
    audit_rows(rows, history=stage in ("5b", "confirm"))
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sha(Path(plan_path)) != plan_hash or (pair_path and sha(Path(pair_path)) != pair_hash):
        raise ValueError("plan or pair changed during the run")
    result = {"seed": seed, "stage": stage, "identity": identity, "plan_sha256": plan_hash,
              "pair_sha256": pair_hash,
              "brain_seconds": len(arms) * DURATION, "rows": rows,
              "build_wall_s": ctx["build_wall_s"], "total_wall_s": time.perf_counter() - start,
              "peak_rss_bytes": int(rss * (1024 if platform.system() == "Linux" else 1))}
    file = destination / f"seed-{seed}.json"
    dump(file, result)
    return str(file)


def run(stage: str, plan_path: Path, output: Path, workers: int, pair: Path | None, *, resume: bool = False) -> None:
    if not 1 <= workers <= (12 if stage == "confirm" else 10):
        raise ValueError("worker count outside stage limit")
    plan = read(plan_path)
    identity = confirm_identity(plan) if stage == "confirm" else code_identity()
    for name, expected in plan["identity"]["sha256"].items():
        if identity["sha256"].get(name) != expected:
            raise ValueError(f"frozen input or code differs: {name}; freeze before any new run")
    if stage in ("5b", "confirm") and (pair is None or read(pair)["prerequisite"] != "represented"):
        raise ValueError("history run requires a frozen represented pair")
    seeds = ([901] if stage == "probe" else list(range(101, 111)) if stage == "5a"
             else plan["confirmation"]["seeds"] if stage == "confirm" else list(range(201, 211)))
    if stage == "confirm" and (seeds != list(range(301, 341)) or
                               plan["confirmation"]["conditions"] != list(analysis.CONFIRM_CONDITIONS) or
                               plan["confirmation"]["protocols"] != [list(p) for p in analysis.CONFIRM_PROTOCOLS]):
        raise ValueError("confirmation design differs from frozen arm/seed set")
    if resume and stage != "confirm":
        raise ValueError("only confirmation can resume incomplete seeds")
    output.mkdir(parents=True, exist_ok=resume)
    # Never inspect a neural result for a resume decision: an absent complete
    # manifest causes an identical full-seed replay, including any crashed arm.
    if resume:
        seeds = [s for s in seeds if not (output / f"seed-{s}.json").exists()]
    jobs = [(seed, stage, str(plan_path.resolve()), str(output.resolve()),
             str(pair.resolve()) if pair else None, identity) for seed in seeds]
    if not jobs:
        print("all confirmation seed manifests present; run the independent exact audit", flush=True)
        return
    with ProcessPoolExecutor(max_workers=min(workers, len(jobs)), mp_context=multiprocessing.get_context("spawn"),
                             max_tasks_per_child=1) as pool:
        print(list(pool.map(run_seed, jobs)), flush=True)


def load_rates(raw: Path, stage: str, *, field: str = "response_er_hz",
               plan_hash: str | None = None, pair_hash: str | None = None) -> tuple[np.ndarray, dict[str, str]]:
    from flyonenomics.io import load_npy

    seeds = range(101, 111) if stage == "5a" else range(301, 341) if stage == "confirm" else range(201, 211)
    result, hashes = [], {}
    identity = None
    for seed in seeds:
        manifest = raw / f"seed-{seed}.json"
        run = read(manifest)
        key = (run["identity"], run["plan_sha256"], run["pair_sha256"])
        if plan_hash is not None and run["plan_sha256"] != plan_hash:
            raise ValueError("raw run plan differs")
        if pair_hash is not None and run["pair_sha256"] != pair_hash:
            raise ValueError("raw run pair differs")
        if identity is None: identity = key
        if key != identity or run["seed"] != seed or run["stage"] != stage:
            raise ValueError("seed identities differ")
        conditions = analysis.CONFIRM_CONDITIONS if stage == "confirm" else analysis.CONDITIONS
        protocols = analysis.CONFIRM_PROTOCOLS if stage == "confirm" else analysis.PROTOCOLS
        expected = [("wt-vehicle", p) for p in ("off", *map(str, analysis.POSITIONS))] if stage == "5a" else [
            (c, list(p)) for c in conditions for p in protocols]
        if stage == "confirm":
            audit_rows(run["rows"], history=True)
        if [(r["condition"], r["protocol"]) for r in run["rows"]] != expected:
            raise ValueError("missing or reordered arms")
        hashes[manifest.name] = sha(manifest)
        rows = []
        for row in run["rows"]:
            if row["male_array_binding"]["connectome_version"] != VERSION:
                raise ValueError("arm did not use male arrays")
            file = raw / row["file"]
            if sha(file) != row["sha256"]:
                raise ValueError(f"raw arm hash mismatch: {file}")
            hashes[file.name] = row["sha256"]
            with load_npy(file, allow_pickle=False) as arrays:
                rows.append(arrays[field])
        result.append(rows)
    data = np.asarray(result)
    return (data if stage == "5a" else data.reshape(40, 2, 4, -1) if stage == "confirm"
            else data.reshape(10, 4, 8, -1)), hashes


def audit_confirm(raw: Path, plan_path: Path, pair_path: Path, out: Path,
                  calibration: Path | None, pilot: Path | None, *, analyse: bool) -> None:
    """Complete-seed audit before reading any outcome; analysis requires all 40."""
    from flyonenomics.io import load_npy
    plan = read(plan_path)
    conf = plan["confirmation"]
    if sha(PLAN) != conf["pilot_plan_sha256"] or sha(ROOT / "validation/records/p2/adhd-study-results.json") != conf["pilot_result_sha256"]:
        raise ValueError("reviewed study provenance changed")
    if sha(pair_path) != plan["calibration_reference"]["pair_sha256"]:
        raise ValueError("frozen pair changed")
    if sorted(raw.iterdir()) != sorted(raw / name for name in [
        *(f"seed-{s}.json" for s in conf["seeds"]),
        *(f"seed-{s}-arm-{i:02}.{suffix}" for s in conf["seeds"] for i in range(8)
          for suffix in ("npz", "json"))]):
        raise ValueError("missing or unexpected confirmation run file")
    hashes: dict[str, str] = {}
    # Preflight completeness and every file receipt before opening any NPZ.
    for seed in conf["seeds"]:
        manifest = raw / f"seed-{seed}.json"
        run = read(manifest)
        hashes[manifest.name] = sha(manifest)
        if (run["seed"] != seed or run["stage"] != "confirm" or
            run["plan_sha256"] != sha(plan_path) or run["pair_sha256"] != sha(pair_path) or
            run["identity"]["sha256"] != plan["identity"]["sha256"] or len(run["rows"]) != 8):
            raise ValueError("seed manifest differs from frozen plan")
        if [(r["condition"], r["protocol"]) for r in run["rows"]] != [
            (c, list(p)) for c in analysis.CONFIRM_CONDITIONS for p in analysis.CONFIRM_PROTOCOLS]:
            raise ValueError("arm ordering differs")
        for i, row in enumerate(run["rows"]):
            path = raw / f"seed-{seed}-arm-{i:02}.npz"
            if row["file"] != path.name or sha(path) != row["sha256"]:
                raise ValueError("arm hash differs")
            hashes[path.name] = row["sha256"]
    for seed in conf["seeds"]:
        run = read(raw / f"seed-{seed}.json")
        event_lists: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for i, row in enumerate(run["rows"]):
            journal_path = raw / f"seed-{seed}-arm-{i:02}.json"
            journal = read(journal_path)
            if (journal["row"] != row or journal["seed"] != seed or
                journal["plan_sha256"] != sha(plan_path) or journal["pair_sha256"] != sha(pair_path)):
                raise ValueError("arm journal disagrees with complete seed")
            hashes[journal_path.name] = sha(journal_path)
            if row["male_array_binding"] != plan["male_array_binding"] or not row["actual_events_equal_fixed_list"]:
                raise ValueError("male array binding or actual event audit differs")
            if row["response_window_s"] != [8.0, 10.0]:
                raise ValueError("primary response window changed")
            with load_npy(raw / row["file"], allow_pickle=False) as data:
                ticks, indices = data["injected_ticks"], data["injected_tubu_positions"]
                full_hash = digest(np.column_stack((ticks, indices)))
                if full_hash != row["planned_injected_events_sha256"]:
                    raise ValueError("fixed event list differs")
                final = (ticks[ticks >= round(8_000 / row["dt_ms"])],
                         indices[ticks >= round(8_000 / row["dt_ms"])])
                if digest(np.column_stack(final)) != row["injected_test_events_sha256"]:
                    raise ValueError("final event hash differs")
                stimulus = row["protocol"][1]
                if stimulus in event_lists and not all(np.array_equal(x, y) for x, y in zip(final, event_lists[stimulus])):
                    raise ValueError("final stimulus event arrays differ")
                event_lists[stimulus] = final
        audit_rows(run["rows"], history=True)
    audit = {"stage": "confirm", "seeds": conf["seeds"], "arm_count": 320,
             "exact_rng_and_event_arrays": True, "plan_sha256": sha(plan_path),
             "pair_sha256": sha(pair_path), "raw_sha256": hashes}
    if not analyse:
        dump(out, audit)
        return
    if calibration is None or pilot is None:
        raise ValueError("analysis needs --calibration and --pilot")
    rates, checked_hashes = load_rates(raw, "confirm", plan_hash=sha(plan_path), pair_hash=sha(pair_path))
    if any(checked_hashes[k] != hashes[k] for k in checked_hashes):
        raise ValueError("rates differ from audited receipts")
    for seed in conf["seeds"]:
        for row in read(raw / f"seed-{seed}.json")["rows"]:
            with load_npy(raw / row["file"], allow_pickle=False) as data:
                np.testing.assert_array_equal(data["response_er_hz"],
                    data["er_counts"][800:1000].sum(axis=0) / 2)
    cal, cal_hashes = load_rates(calibration, "5a", plan_hash=conf["calibration_plan_sha256"])
    pilot_rates, pilot_hashes = load_rates(pilot, "5b", plan_hash=conf["pilot_plan_sha256"],
                                         pair_hash=sha(pair_path))
    if cal_hashes != read(pair_path)["raw_sha256"] or pilot_hashes != read(ROOT / "validation/records/p2/adhd-study-results.json")["raw_sha256"]:
        raise ValueError("old raw file receipts differ")
    result = analysis.confirm_analyse(rates, cal, tuple(read(pair_path)["pair"]), pilot_rates,
                replicates=conf["bootstraps"], draws=conf["sign_draws"])
    # 100 ms projected H, descriptive only; two genotypes x two histories.
    _, axis = analysis.templates(cal, tuple(read(pair_path)["pair"]))
    course = []
    for seed in conf["seeds"]:
        rows = read(raw / f"seed-{seed}.json")["rows"]
        per_arm = []
        for row in rows:
            with load_npy(raw / row["file"], allow_pickle=False) as data:
                per_arm.append(data["er_counts"][800:2200].reshape(140, 10, -1).sum(axis=1) @ axis / .1)
        projected = np.asarray(per_arm).reshape(2, 4, 140)
        course.append(projected[:, 1] - projected[:, 0] - projected[:, 3] + projected[:, 2])
    course = np.asarray(course)
    h = result["secondaries"]["H_per_seed_condition"]
    result["secondaries"]["four_prefix_group_means_ranges"] = [
        {"condition": condition, "prefix": prefix,
         "mean": float(values.mean()), "range": [float(values.min()), float(values.max())]}
        for j, condition in enumerate(analysis.CONFIRM_CONDITIONS)
        for prefix, values in (("A", rates[:, j, 1] @ axis - rates[:, j, 0] @ axis),
                               ("B", rates[:, j, 3] @ axis - rates[:, j, 2] @ axis))]
    result["secondaries"]["time_course_100ms_H_per_seed"] = course.tolist()
    result.update(audit=audit, calibration_sha256=cal_hashes, pilot_sha256=pilot_hashes,
                  primary_window_s=[8, 10], time_course_window_s=[8, 22])
    dump(out, result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "freeze-confirm", "synthetic", "probe", "5a", "pair", "5b", "confirm", "resume-confirm", "diagnostic", "analyse", "analyse-confirm", "audit-confirm"))
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--pilot", type=Path)
    parser.add_argument("--pair", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.out or args.plan)
    elif args.command == "freeze-confirm":
        freeze_confirm(args.out or CONFIRM_PLAN)
    elif args.command == "synthetic":
        dump(args.out or RUNS / "synthetic.json", analysis.synthetic_validation())
    elif args.command in ("probe", "5a", "5b", "confirm", "resume-confirm"):
        if args.out is None: parser.error("--out directory is required")
        run("confirm" if args.command == "resume-confirm" else args.command,
            args.plan, args.out, args.workers, args.pair, resume=args.command == "resume-confirm")
    elif args.command == "diagnostic":
        if args.out is None or args.pair is None: parser.error("--out and --pair required")
        run_diagnostic(args.plan, args.out, args.workers, args.pair)
    elif args.command == "pair":
        if args.raw is None or args.out is None: parser.error("--raw and --out required")
        calibration, hashes = load_rates(args.raw, "5a", plan_hash=sha(args.plan))
        source, _ = load_rates(args.raw, "5a", field="response_tubu_hz", plan_hash=sha(args.plan))
        record = analysis.choose_pair(calibration)
        record["tubu_decoder_four_way"] = analysis.decoder(source[:, 1:])
        record["tubu_decoder_five_way"] = analysis.decoder(source)
        record.update(raw=str(args.raw.resolve()), raw_sha256=hashes, plan_sha256=sha(args.plan),
                      analysis_sha256=sha(ROOT / "scripts/adhd_analysis.py"))
        dump(args.out, record)
        if record["prerequisite"] == "failure":
            raise SystemExit("PREREQUISITE FAILURE: report via ha waiting; no 5b")
    elif args.command in ("audit-confirm", "analyse-confirm"):
        if any(x is None for x in (args.raw, args.pair, args.out)):
            parser.error("--raw, --pair and --out required")
        audit_confirm(args.raw, args.plan, args.pair, args.out, args.calibration,
                      args.pilot, analyse=args.command == "analyse-confirm")
    else:
        if any(x is None for x in (args.raw, args.calibration, args.pair, args.out)):
            parser.error("--raw, --calibration, --pair and --out required")
        rates, hashes = load_rates(args.raw, "5b", plan_hash=sha(args.plan), pair_hash=sha(args.pair))
        reference = read(args.plan)["calibration_reference"]
        if sha(args.pair) != reference["pair_sha256"]:
            raise ValueError("pair differs from the retained calibration reference")
        calibration, cal_hashes = load_rates(args.calibration, "5a", plan_hash=reference["plan_sha256"])
        pair = read(args.pair)
        if pair["raw_sha256"] != cal_hashes or pair["analysis_sha256"] != sha(ROOT / "scripts/adhd_analysis.py"):
            raise ValueError("calibration or frozen analysis changed")
        result = analysis.analyse(rates, calibration, tuple(pair["pair"]))
        result.update(raw_sha256=hashes, calibration_sha256=cal_hashes, pair_sha256=sha(args.pair))
        dump(args.out, result)


if __name__ == "__main__":
    main()
