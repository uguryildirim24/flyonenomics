"""Stage 2 of the ring-neuron dopamine experiment.

Two jobs on item 122's declared substrate, canonical v0.2 files, class
``development``. Job A isolates the dopamine field from ``CX_DAN``'s fast
synapses with a ``dan_fast_synapses: "disconnect"`` arm; Job B asks whether
the dopamine-transporter mutant ``fumin`` differs from wild type once the
field is driven. Every value is a model measurement, never a pass line.

``census`` extends stage 1's EB census with the connectome's ``CX_DAN``-to-ring
edges and the fumin/wild-type closed-form EB fixed points, no engine run.
``audit`` builds one engine and measures exactly what ``disconnect`` removes
and what it leaves. ``plan`` fixes the trace set and the five paired arms.
``run`` executes the paired 1000-brain-second probe on the box. ``summarize``
reduces the raw runs into the compact committed record.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import multiprocessing
import os
from pathlib import Path
import platform
import time
from types import SimpleNamespace
from typing import Any

import numpy as np

import ring_dopamine_stage1 as s1

ROOT = Path(__file__).resolve().parents[1]
MASTER = s1.MASTER
SEEDS = s1.SEEDS
SETTLE_S = s1.SETTLE_S
PROBE_S = s1.PROBE_S
TUBU_MAX_HZ = s1.TUBU_MAX_HZ
SIGMA_DEG = s1.SIGMA_DEG
STRIPE_AZ_DEG = s1.STRIPE_AZ_DEG
SOURCE_POPULATION = s1.SOURCE_POPULATION
DOPAMINE_POPULATION = s1.DOPAMINE_POPULATION
DA_DRIVE_HZ = s1.DA_DRIVE_HZ
DEFAULT_FIXTURE = Path("data/experiments/p2/ring-dopamine-stage2.json")
DEFAULT_PLAN = Path("camber-runs/ring-dopamine-stage2/plan.json")
DEFAULT_RAW = Path("camber-runs/ring-dopamine-stage2/raw")
DEFAULT_AUDIT = Path("camber-runs/ring-dopamine-stage2/audit.json")
DEFAULT_RECORD = Path("validation/records/p2/ring-dopamine-stage2.json")
SOURCE_COMMIT_ENV = s1.SOURCE_COMMIT_ENV
DECLARED_SUBSTRATE_ID = s1.DECLARED_SUBSTRATE_ID
REACHED_RECORD = s1.REACHED_RECORD
# Item 135: d_v peaks at 0.16219 uM and crosses zero at 1.849999 uM.
DV_PEAK_DA_UM = 0.16219
DV_CROSSOVER_DA_UM = 1.849999
# Stage 1 measured 36.44 to 37.09 Hz under the 50 Hz input; the closed-form
# scenario rate is the nominal drive, both reported as arithmetic only.
NOMINAL_DRIVE_HZ = DA_DRIVE_HZ
STAGE1_MEASURED_DRIVE_HZ = 36.7

# Five paired arms. Job A is the first three; Job B adds the fumin pair.
ARMS: tuple[dict[str, Any], ...] = (
    {"label": "dark", "genotype": "wild_type", "drive_hz": 0.0, "dan_fast_synapses": "retain"},
    {"label": "driven-retain", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain"},
    {"label": "driven-disconnect", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "disconnect"},
    {"label": "fumin-retain", "genotype": "fumin", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain"},
    {"label": "fumin-disconnect", "genotype": "fumin", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "disconnect"},
)
ARM_LABELS = tuple(arm["label"] for arm in ARMS)
JOB_A_CONTRASTS = (
    ("retain_minus_dark", "driven-retain", "dark"),
    ("disconnect_minus_dark", "driven-disconnect", "dark"),
    ("retain_minus_disconnect", "driven-retain", "driven-disconnect"),
)
JOB_B_CONTRASTS = (
    ("fumin_retain_minus_wild_type_retain", "fumin-retain", "driven-retain"),
    ("fumin_disconnect_minus_wild_type_disconnect", "fumin-disconnect", "driven-disconnect"),
)


def dump(path: Path, value: Any) -> None:
    s1.dump(path, value)


def read(path: Path) -> dict[str, Any]:
    return s1.read(path)


def digest(array: np.ndarray, dtype: Any | None = None) -> str:
    return s1.digest(array, dtype)


def _paired_interval(values: list[float]) -> dict[str, Any]:
    return s1._paired_interval(values)


def _distribution(values: list[float]) -> dict[str, Any]:
    return s1._distribution(values)


def _field(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    return s1._field(rows, key)


def probe(label: str) -> Any:
    return s1.probe(label)


def identity(platform_name: str) -> dict[str, Any]:
    from flyonenomics.connectome_arrays import connectome_source_paths
    from flyonenomics.io import hash_file

    source_commit = os.environ.get(SOURCE_COMMIT_ENV)
    if not source_commit:
        raise ValueError(f"{SOURCE_COMMIT_ENV} must bind the executed source commit")
    completeness, connectivity = connectome_source_paths("783")
    data_names = (
        "params-v0.2.yaml", "drive-v0.2.yaml", "dopamine-v0.2.yaml",
        "populations-v0.2.yaml", "transmitters-v0.2.yaml",
        "receptors-v0.1.yaml", "compartments-v0.1.yaml",
    )
    return {
        "platform": platform_name,
        "engine": "lif",
        "source_commit": source_commit,
        "source_sha256": {
            str(path.relative_to(ROOT)): hash_file(path)
            for path in sorted((ROOT / "src").rglob("*.py"))
        },
        "runner_sha256": hash_file(Path(__file__)),
        "reused_stage1_runner_sha256": hash_file(Path(s1.__file__)),
        "inputs_sha256": {name: hash_file(ROOT / "data" / name) for name in data_names},
        "connectome_sha256": {
            completeness.name: hash_file(completeness),
            connectivity.name: hash_file(connectivity),
        },
    }


def _er_targets() -> np.ndarray:
    reached = read(ROOT / REACHED_RECORD)
    er_cells = [cell for cell in reached["cells"] if "ring_ER" in cell["classes"]]
    return np.asarray(sorted(int(cell["engine_index"]) for cell in er_cells), dtype=np.int32)


def dan_synapse_census() -> dict[str, Any]:
    """Count the connectome edges and raw weights that disconnect removes.

    No engine build: the raw arrays are the same inputs the engine builds
    from, so the counts are exact. ``effective`` weights carry ``w_syn`` but
    not the substrate scale; scale is a per-neuron factor and does not change
    which edges the disconnect zeroes.
    """
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.registry import build_registry
    from flyonenomics.types import load_params

    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    dan = np.union1d(registry.population("DAN").idx, registry.population("CX_DAN").idx).astype(np.int32)
    cx_dan = np.asarray(registry.population("CX_DAN").idx, dtype=np.int32)
    er = _er_targets()
    completeness, connectivity = connectome_source_paths("783")
    roots, pre, post, raw = load_connectome_arrays(completeness, connectivity)
    w_syn = float(params.get("lif.w_syn"))
    pre = np.asarray(pre, dtype=np.int32)
    post = np.asarray(post, dtype=np.int32)
    raw = np.asarray(raw, dtype=np.float64)

    def summarize(mask: np.ndarray) -> dict[str, Any]:
        weight = raw[mask] * w_syn
        # raw is 'Excitatory x Connectivity', so its magnitude is the parquet
        # 'Connectivity' count and its sign is the transmitter sign.
        return {
            "edges": int(np.sum(mask)),
            "synapses": int(round(float(np.abs(raw[mask]).sum()))),
            "excitatory_edges": int(np.sum(raw[mask] > 0)),
            "inhibitory_edges": int(np.sum(raw[mask] < 0)),
            "abs_weight_mv": float(np.abs(weight).sum()),
            "weight_mv": float(weight.sum()),
        }

    return {
        "n_connectome_neurons": int(registry.n),
        "n_connectome_edges": int(pre.shape[0]),
        "n_er_targets": int(er.size),
        "w_syn": w_syn,
        "dan_population_n": int(dan.size),
        "cx_dan_population_n": int(cx_dan.size),
        "all_edges": summarize(np.ones(pre.shape[0], dtype=bool)),
        "from_dan_or_cx_dan": summarize(np.isin(pre, dan)),
        "from_cx_dan": summarize(np.isin(pre, cx_dan)),
        "from_cx_dan_to_er": summarize(np.isin(pre, cx_dan) & np.isin(post, er)),
        "from_dan_or_cx_dan_to_er": summarize(np.isin(pre, dan) & np.isin(post, er)),
        "from_tubu_to_er": summarize(
            np.isin(pre, registry.population(SOURCE_POPULATION).idx) & np.isin(post, er)),
        "er_targets_sha256": digest(er, np.int32),
    }


def _closed_form_fixed_point(q: float, vmax: float, km: float, k_ns: float) -> float:
    b = vmax + k_ns * km - q
    if b >= 0:
        return 2.0 * q * km / (b + float(np.sqrt(b * b + 4.0 * k_ns * q * km)))
    return (float(np.sqrt(b * b + 4.0 * k_ns * q * km)) - b) / (2.0 * k_ns)


def _fumin_reachability() -> dict[str, Any]:
    """Closed-form EB fixed point for wild type and fumin at two rates."""
    from flyonenomics.io import read_yaml

    table = read_yaml(ROOT / "data/dopamine-v0.2.yaml")
    eb = table["compartments"].index("EB")
    alpha = float(table["alpha_c"][eb])
    source = float(table["S_c"][eb])
    constants = {key: float(value) for key, value in table["constants"].items()}
    eb_weight_sum = s1.eb_innervation()["cx_dan"]["eb_weight_sum"]
    scenarios: dict[str, Any] = {}
    for rate_label, rate_hz in (("nominal_drive", NOMINAL_DRIVE_HZ),
                                ("stage1_measured_drive", STAGE1_MEASURED_DRIVE_HZ)):
        weighted = rate_hz * eb_weight_sum
        q = alpha * weighted + source
        scenarios[rate_label] = {
            "drive_hz_per_neuron": float(rate_hz),
            "weighted_eb_hz": float(weighted),
            "q_um_per_s": float(q),
            "wild_type_fixed_point_um": float(
                _closed_form_fixed_point(q, constants["Vmax"], constants["Km"], constants["k_ns"])),
            "fumin_fixed_point_um": float(_closed_form_fixed_point(q, 0.0, constants["Km"], constants["k_ns"])),
        }
    return {
        "alpha_um_per_spike": alpha,
        "s_um_per_s": source,
        "eb_weight_sum": float(eb_weight_sum),
        "scenarios": scenarios,
        "note": (
            "closed form of the item-129 pool balance with the committed alpha_c and S_c; "
            "wild type keeps Vmax, fumin sets it to zero. The measured run values are separate."
        ),
    }


def build_census(destination: Path) -> None:
    """Write the census part of the record; the probe key stays null until summarize."""
    started = time.monotonic()
    census = {
        "eb_innervation": s1.eb_innervation(),
        "ring_receptors": s1.ring_receptors(ROOT / REACHED_RECORD),
    }
    census["reachability"] = s1.reachability(census["eb_innervation"])
    census["fumin_reachability"] = _fumin_reachability()
    census["dan_synapse_census"] = dan_synapse_census()
    record = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 2: isolate the dopamine field from CX_DAN's fast "
            "synapses, then ask whether fumin differs from wild type"
        ),
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "census": census,
        "probe": None,
        "wall_seconds": time.monotonic() - started,
    }
    dump(destination, record)
    print(json.dumps({
        "cx_dan_to_er_edges": census["dan_synapse_census"]["from_cx_dan_to_er"]["edges"],
        "cx_dan_to_er_abs_weight_mv": census["dan_synapse_census"]["from_cx_dan_to_er"]["abs_weight_mv"],
        "fumin_fixed_point_nominal_um": census["fumin_reachability"]["scenarios"]["nominal_drive"]["fumin_fixed_point_um"],
        "wild_type_fixed_point_nominal_um": census["fumin_reachability"]["scenarios"]["nominal_drive"]["wild_type_fixed_point_um"],
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def build_plan(destination: Path) -> None:
    """Fix the trace set (228 ER) and the five paired arms."""
    from flyonenomics.registry import build_registry
    from flyonenomics.registry.compartments import compartment_index

    reached = read(ROOT / REACHED_RECORD)
    er_cells = [cell for cell in reached["cells"] if "ring_ER" in cell["classes"]]
    trace_indices = sorted(int(cell["engine_index"]) for cell in er_cells)
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    compartment = compartment_index()
    fixture = read(ROOT / DEFAULT_FIXTURE)
    fixture_arms = [
        {
            "label": arm["label"],
            "genotype": arm["genotype"]["named"],
            "drive_hz": float(next(
                (hook["rate_hz"] for hook in arm["genotype"].get("manipulations", [])
                 if hook["type"] == "activate"), 0.0)),
            "dan_fast_synapses": (arm.get("layers") or {}).get(
                "dan_fast_synapses", fixture["layers"]["dan_fast_synapses"]),
        }
        for arm in fixture["arms"]
    ]
    if tuple(arm["label"] for arm in fixture_arms) != ARM_LABELS:
        raise ValueError("fixture arms do not match the runner's arm order")
    output = {
        "class": "development",
        "purpose": "ring-neuron dopamine stage 2 five-arm paired probe plan",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "protocol": {
            "master_seed": MASTER,
            "seeds": list(SEEDS),
            "arms": fixture_arms,
            "settle_s": SETTLE_S,
            "probe_s": PROBE_S,
            "brain_seconds": PROBE_S * len(ARMS) * len(SEEDS),
            "inject_at": SOURCE_POPULATION,
            "dopamine_population": DOPAMINE_POPULATION,
            "dopamine_drive_hz": float(DA_DRIVE_HZ),
            "stripe_azimuth_deg": STRIPE_AZ_DEG,
            "stripe_width_deg": 5.0,
            "TuBu_max_hz": TUBU_MAX_HZ,
            "TuBu_sigma_deg": SIGMA_DEG,
            "eb_compartment_index": int(compartment["EB"]),
            "source_event_definition": (
                "sum over a source population's spike counts times its effective substrate weight "
                "times the live postsynaptic gain in the measurement window"
            ),
            "disconnect_definition": (
                "Neuromod.apply_genotype with dan_fast_synapses='disconnect' zeroes every recurrent "
                "synapse whose presynaptic cell is in DAN or CX_DAN; it does not silence those cells, "
                "change their extended input rates, or change the innervation matrix or kinetics"
            ),
        },
        "fixture": str(DEFAULT_FIXTURE),
        "trace_indices": trace_indices,
        "trace_n": len(trace_indices),
        "cells": [{"engine_index": int(cell["engine_index"]), "root_id": int(cell["root_id"]),
                   "hemibrain_type": cell["hemibrain_type"], "side": cell["side"]} for cell in er_cells],
    }
    dump(destination, output)
    print(f"wrote {destination} ({len(trace_indices)} traced ER cells, {len(ARMS)} arms)", flush=True)


def _prepare_declared(trace_indices: np.ndarray, *, with_traces: bool) -> dict[str, Any]:
    """Build one engine on the declared substrate and snap it under ``declared``."""
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.rest import apply_rest_substrate, load_drive_rest, rest_background_weights
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.io import read_yaml
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.registry import build_registry
    from flyonenomics.types import load_params

    params = load_params(ROOT / "data/params-v0.2.yaml")
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    groups = group_indices(registry)
    drive = load_drive_rest(ROOT / "data/drive-v0.2.yaml")
    dopamine = read_yaml(ROOT / "data/dopamine-v0.2.yaml")
    source = np.asarray(registry.population(SOURCE_POPULATION).idx, dtype=np.int32)
    dopamine_neurons = np.asarray(registry.population(DOPAMINE_POPULATION).idx, dtype=np.int32)
    targets = np.asarray(trace_indices, dtype=np.int32)
    extended = np.union1d(np.sort(source), np.sort(dopamine_neurons)).astype(np.int32)
    topology = InputTopology(background=True, extended_idx=extended,
                             trace_idx=targets if with_traces else np.zeros(0, dtype=np.int32))
    engine = BrianEngine()
    engine.seed(MASTER)
    engine.build(connectome_files("783"), params, topology, mechanisms=None)
    base_threshold, scale = apply_rest_substrate(engine, params, drive)
    background = rest_background_weights(registry, drive, params)
    engine.set_background(background)
    engine.store("declared")
    completeness, connectivity = connectome_source_paths("783")
    roots, pre, post, raw = load_connectome_arrays(completeness, connectivity)
    effective = np.asarray(raw, dtype=np.float64) * float(params.get("lif.w_syn")) * scale
    return {
        "engine": engine, "params": params, "registry": registry, "groups": groups,
        "drive": drive, "dopamine": dopamine, "source": source,
        "dopamine_neurons": dopamine_neurons, "targets": targets,
        "extended": extended, "topology": topology, "base_threshold": base_threshold,
        "scale": scale, "background": background, "roots": roots, "pre": pre, "post": post,
        "effective": effective,
    }


def build_audit(destination: Path) -> None:
    """Build one engine and measure exactly what ``disconnect`` removes and leaves."""
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags

    started = time.monotonic()
    targets = _er_targets()
    ctx = _prepare_declared(targets, with_traces=False)
    engine, registry = ctx["engine"], ctx["registry"]
    dan = np.union1d(registry.population("DAN").idx, registry.population("CX_DAN").idx).astype(np.int32)
    er = targets

    def weights() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        # Copy: engine.disconnect writes _syn.w in place, so a view would show
        # the post-disconnect zeros as the "before" measurement too.
        pre = np.asarray(engine._syn.i[:], dtype=np.int32).copy()
        post = np.asarray(engine._syn.j[:], dtype=np.int32).copy()
        # _syn.w is a Brian2 quantity in volts; report mV.
        w = np.asarray(engine._syn.w[:], dtype=np.float64).copy() * 1000.0
        return pre, post, w

    pre_before, post_before, w_before = weights()
    mod = Neuromod(
        registry, ctx["params"],
        LayerFlags(background=True, dopamine_A=True, transporter_C=True, dan_fast_synapses="disconnect"),
        ctx["dopamine"], base_v_th=ctx["base_threshold"], schema_version="1.3", drive_groups=ctx["groups"],
    )
    from flyonenomics.registry.compartments import compartment_index

    eb = compartment_index()["EB"]
    m_before = np.asarray(mod.m.tocsr().getrow(eb).toarray()).ravel()
    fixed_before = mod.fixed_point()

    mod.apply_genotype(named_manipulations("wild_type"), engine)
    pre_after, post_after, w_after = weights()
    m_after = np.asarray(mod.m.tocsr().getrow(eb).toarray()).ravel()
    fixed_after = mod.fixed_point()

    def group(pre: np.ndarray, w: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
        return {
            "edges": int(np.sum(mask)),
            "abs_weight_mv": float(np.abs(w[mask]).sum()),
            "nonzero_edges": int(np.sum(np.abs(w[mask]) > 0)),
        }

    to_er = np.isin(post_before, er)
    from_dan = np.isin(pre_before, dan)
    cx_dan = np.asarray(registry.population("CX_DAN").idx, dtype=np.int32)
    from_cx = np.isin(pre_before, cx_dan)
    record = {
        "class": "development",
        "purpose": "verify the dan_fast_synapses disconnect layer removes only DAN/CX_DAN fast synapses",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "platform": f"{platform.system().lower()}-{platform.machine()}",
        "dan_population_n": int(dan.size),
        "cx_dan_population_n": int(cx_dan.size),
        "n_synapses": int(pre_before.size),
        "before": {
            "from_dan_or_cx_dan": group(pre_before, w_before, from_dan),
            "from_dan_or_cx_dan_to_er": group(pre_before, w_before, from_dan & to_er),
            "from_cx_dan": group(pre_before, w_before, from_cx),
            "from_cx_dan_to_er": group(pre_before, w_before, from_cx & to_er),
            "not_dan_or_cx_dan": group(pre_before, w_before, ~from_dan),
        },
        "after": {
            "from_dan_or_cx_dan": group(pre_after, w_after, from_dan),
            "from_dan_or_cx_dan_to_er": group(pre_after, w_after, from_dan & to_er),
            "from_cx_dan": group(pre_after, w_after, from_cx),
            "from_cx_dan_to_er": group(pre_after, w_after, from_cx & to_er),
            "not_dan_or_cx_dan": group(pre_after, w_after, ~from_dan),
        },
        "presynaptic_indices_unchanged": bool(np.array_equal(pre_before, pre_after)),
        "postsynaptic_indices_unchanged": bool(np.array_equal(post_before, post_after)),
        "innervation_eb_row_unchanged": bool(np.array_equal(m_before, m_after)),
        "innervation_eb_weight_sum": float(m_before.sum()),
        "wild_type_fixed_point_eb_before_um": float(fixed_before[eb]),
        "wild_type_fixed_point_eb_after_um": float(fixed_after[eb]),
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination, record)
    print(json.dumps({
        "from_dan_or_cx_dan_edges_before": record["before"]["from_dan_or_cx_dan"]["edges"],
        "from_dan_or_cx_dan_nonzero_edges_after": record["after"]["from_dan_or_cx_dan"]["nonzero_edges"],
        "not_dan_or_cx_dan_abs_weight_before": record["before"]["not_dan_or_cx_dan"]["abs_weight_mv"],
        "not_dan_or_cx_dan_abs_weight_after": record["after"]["not_dan_or_cx_dan"]["abs_weight_mv"],
        "presynaptic_indices_unchanged": record["presynaptic_indices_unchanged"],
        "innervation_eb_row_unchanged": record["innervation_eb_row_unchanged"],
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def run_seed(job: tuple[int, str, str]) -> str:
    """Run all five arms for one seed in one built engine, paired on the same stream."""
    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.io import read_yaml
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags

    seed, plan_path, destination = job
    destination_path = Path(destination)
    plan = read(Path(plan_path))
    probe_s = float(plan["protocol"]["probe_s"])
    settle_s = float(plan["protocol"]["settle_s"])
    eb_index = int(plan["protocol"]["eb_compartment_index"])
    targets = np.asarray(plan["trace_indices"], dtype=np.int32)
    if not len(targets) or len(np.unique(targets)) != len(targets):
        raise ValueError("plan supplied an invalid trace target set")
    started = time.monotonic()
    ctx = _prepare_declared(targets, with_traces=True)
    engine, params, registry = ctx["engine"], ctx["params"], ctx["registry"]
    source = ctx["source"]
    dopamine_neurons = ctx["dopamine_neurons"]
    extended = ctx["extended"]
    dopamine = ctx["dopamine"]
    drive = ctx["drive"]
    effective = ctx["effective"]
    roots = ctx["roots"]
    pre, post = ctx["pre"], ctx["post"]
    targets = ctx["targets"]
    base_threshold = ctx["base_threshold"]
    groups = ctx["groups"]
    dopamine_positions = np.searchsorted(extended, dopamine_neurons)
    target_position = np.full(registry.n, -1, dtype=np.int32)
    target_position[targets] = np.arange(len(targets), dtype=np.int32)

    def incoming(source_idx: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        mask = np.isin(pre, source_idx) & np.isin(post, targets)
        return (np.asarray(pre[mask], dtype=np.int32), target_position[np.asarray(post[mask], dtype=np.int32)],
                effective[mask])

    tubu_pre, tubu_post, tubu_w = incoming(np.asarray(source, dtype=np.int32))
    da_pre, da_post, da_w = incoming(dopamine_neurons)
    rows = []
    chunk_ms = float(params.get("engine.chunk_ms"))
    settle_chunks = int(round(settle_s * 1000.0 / chunk_ms))
    total_chunks = int(round(probe_s * 1000.0 / chunk_ms))
    n_comp = len(registry.compartments())
    for arm in plan["protocol"]["arms"]:
        label = arm["label"]
        engine.restore("declared")
        engine.seed(brian_seed(MASTER, seed, 0))
        mod = Neuromod(
            registry, params,
            LayerFlags(background=True, dopamine_A=True, transporter_C=True,
                       dan_fast_synapses=arm["dan_fast_synapses"]),
            dopamine, base_v_th=base_threshold, schema_version="1.3", drive_groups=groups,
        )
        mod.apply_genotype(named_manipulations(arm["genotype"]), engine)
        mod.reset_fast()
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        engine.compose_refractory()
        arena = Behaviour(
            SimpleNamespace(topology=ctx["topology"]), registry, params, probe(label),
            v_fwd=0.0, sign_steer=1, K_steer=0.0, r_vis_max=TUBU_MAX_HZ, sigma_vis=SIGMA_DEG,
        )
        arena.reset(np.random.default_rng(seed))
        count = np.zeros(registry.n, dtype=np.int64)
        source_events = np.zeros(len(targets), dtype=np.float64)
        da_events = np.zeros(len(targets), dtype=np.float64)
        threshold_sum = np.zeros(len(targets), dtype=np.float64)
        threshold_min = np.full(len(targets), np.inf)
        threshold_max = np.full(len(targets), -np.inf)
        da_sum = np.zeros(n_comp, dtype=np.float64)
        da_min = np.full(n_comp, np.inf)
        da_max = np.full(n_comp, -np.inf)
        measurement_chunks = 0
        measure_tick = None
        input_min = np.inf
        input_max = -np.inf
        drive_hz = float(arm["drive_hz"])
        for step in range(total_chunks):
            rate = arena.rates(arena.view(), step * chunk_ms / 1000.0)
            if drive_hz:
                rate[dopamine_positions] += drive_hz
            input_min = min(input_min, float(rate.min(initial=0.0)))
            input_max = max(input_max, float(rate.max(initial=0.0)))
            engine.set_input_rates(rate)
            if step == settle_chunks:
                measure_tick = engine.tick()
            gain_before = np.asarray(composed.gain[targets], dtype=np.float64)
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_ms / 1000.0)
            if step >= settle_chunks:
                count += result.counts
                amplitude = result.counts[tubu_pre] * tubu_w * gain_before[tubu_post]
                source_events += np.bincount(tubu_post, weights=amplitude, minlength=len(targets))
                # The fast CX_DAN route: intended from the raw connectome, delivered
                # zero when the disconnect layer removed it.
                intended = result.counts[da_pre] * da_w * gain_before[da_post]
                if arm["dan_fast_synapses"] == "retain":
                    da_events += np.bincount(da_post, weights=intended, minlength=len(targets))
                threshold = np.asarray(composed.v_th[targets], dtype=np.float64)
                threshold_sum += threshold
                np.minimum(threshold_min, threshold, out=threshold_min)
                np.maximum(threshold_max, threshold, out=threshold_max)
                da_sum += mod.da_c
                np.minimum(da_min, mod.da_c, out=da_min)
                np.maximum(da_max, mod.da_c, out=da_max)
                measurement_chunks += 1
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
        if measure_tick is None:
            raise RuntimeError("measurement tick was not set")
        traces = engine.traces(measure_tick)
        if not np.array_equal(traces.idx, targets) or traces.v_mv.shape[1] == 0:
            raise ValueError("trace target order or measurement window is wrong")
        target_rows = []
        for position, target in enumerate(targets):
            values = traces.v_mv[position]
            threshold_mean = float(threshold_sum[position] / measurement_chunks)
            target_rows.append({
                "engine_index": int(target),
                "root_id": int(roots[target]),
                "spike_count": int(count[target]),
                "spike_rate_hz": float(count[target] / (probe_s - settle_s)),
                "source_event_amplitude_mV": float(source_events[position]),
                "cx_dan_event_amplitude_mV": float(da_events[position]),
                "sampled_mean_v_mV": float(values.mean()),
                "sampled_min_v_mV": float(values.min()),
                "sampled_max_v_mV": float(values.max()),
                "threshold_mean_mV": threshold_mean,
                "threshold_min_mV": float(threshold_min[position]),
                "threshold_max_mV": float(threshold_max[position]),
                "mean_distance_to_threshold_mV": float(threshold_mean - values.mean()),
                "nearest_sampled_distance_to_threshold_mV": float(threshold_min[position] - values.max()),
            })
        rows.append({
            "condition": label,
            "genotype": arm["genotype"],
            "dan_fast_synapses": arm["dan_fast_synapses"],
            "dopamine_drive_hz": drive_hz,
            "source_population": SOURCE_POPULATION,
            "source_n": int(len(source)),
            "source_spikes": int(count[source].sum()),
            "source_rate_hz": float(count[source].sum() / (len(source) * (probe_s - settle_s))),
            "dopamine_population": DOPAMINE_POPULATION,
            "dopamine_n": int(len(dopamine_neurons)),
            "dopamine_spikes": int(count[dopamine_neurons].sum()),
            "dopamine_rate_hz": float(count[dopamine_neurons].sum() / (len(dopamine_neurons) * (probe_s - settle_s))),
            "input_rate_min_hz": float(input_min),
            "input_rate_max_hz": float(input_max),
            "targets": target_rows,
            "eb_da_mean_um": float(da_sum[eb_index] / measurement_chunks),
            "eb_da_min_um": float(da_min[eb_index]),
            "eb_da_max_um": float(da_max[eb_index]),
            "da_mean_um": (da_sum / measurement_chunks).tolist(),
            "da_min_um": da_min.tolist(),
            "da_max_um": da_max.tolist(),
            "compartments": [compartment.name for compartment in registry.compartments()],
            "trace_samples": int(traces.v_mv.shape[1]),
        })
        print("seed", seed, label, "complete", flush=True)
    dump(destination_path / f"seed-{seed}.json", {
        "identity": {
            **plan["identity"],
            "platform": f"{platform.system().lower()}-{platform.machine()}",
            "scale_sha256": digest(ctx["scale"], np.float32),
            "background_sha256": digest(ctx["background"]),
        },
        "seed": seed,
        "brian_seed": brian_seed(MASTER, seed, 0),
        "settle_s": settle_s,
        "probe_s": probe_s,
        "brain_seconds": probe_s * len(plan["protocol"]["arms"]),
        "rows": rows,
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    })
    return f"seed-{seed}.json"


def run_dynamic(plan_path: Path, destination: Path, workers: int, seeds: tuple[int, ...]) -> None:
    plan = read(plan_path)
    plan["identity"] = identity(f"{platform.system().lower()}-{platform.machine()}")
    dump(plan_path, plan)
    destination.mkdir(parents=True, exist_ok=True)
    jobs = [(seed, str(plan_path.resolve()), str(destination.resolve())) for seed in seeds]
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn"),
        max_tasks_per_child=1,
    ) as pool:
        print(list(pool.map(run_seed, jobs)), flush=True)


def _seed_aggregate(run: dict[str, Any], label: str) -> dict[str, Any]:
    row = next(item for item in run["rows"] if item["condition"] == label)
    targets = row["targets"]
    spikes = [int(item["spike_count"]) for item in targets]
    mean_v = [float(item["sampled_mean_v_mV"]) for item in targets]
    max_v = [float(item["sampled_max_v_mV"]) for item in targets]
    threshold = [float(item["threshold_mean_mV"]) for item in targets]
    mean_distance = [float(item["mean_distance_to_threshold_mV"]) for item in targets]
    nearest_distance = [float(item["nearest_sampled_distance_to_threshold_mV"]) for item in targets]
    cx_event = [float(item["cx_dan_event_amplitude_mV"]) for item in targets]
    return {
        "er_spikes": int(sum(spikes)),
        "responders": int(sum(value > 0 for value in spikes)),
        "mean_v_mV": float(np.mean(mean_v)),
        "max_v_mV": float(np.max(max_v)),
        "threshold_mV": float(np.mean(threshold)),
        "mean_distance_mV": float(np.mean(mean_distance)),
        "nearest_distance_mV": float(np.mean(nearest_distance)),
        "cx_dan_event_total_mV": float(np.sum(cx_event)),
        "source_rate_hz": float(row["source_rate_hz"]),
        "dopamine_rate_hz": float(row["dopamine_rate_hz"]),
        "eb_da_mean_um": float(row["eb_da_mean_um"]),
        "eb_da_max_um": float(row["eb_da_max_um"]),
    }


def _contrast(paired_runs: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    """Paired left-minus-right over seeds for the seed-level aggregate fields."""
    keys = (
        "er_spikes", "responders", "mean_v_mV", "max_v_mV", "threshold_mV",
        "mean_distance_mV", "nearest_distance_mV", "cx_dan_event_total_mV",
        "source_rate_hz", "dopamine_rate_hz", "eb_da_mean_um", "eb_da_max_um",
    )
    values: dict[str, list[float]] = {key: [] for key in keys}
    for run in paired_runs:
        a = _seed_aggregate(run, left)
        b = _seed_aggregate(run, right)
        for key in keys:
            values[key].append(float(a[key]) - float(b[key]))
    output = {
        "left": left,
        "right": right,
        "unit": "paired difference is left minus right over the ten seeds; interval is mean +/- 1.96 SE",
    }
    for key in keys:
        output[key] = _paired_interval(values[key])
    output["seed_values"] = values
    return output


def summarize(raw: Path, plan_path: Path, destination: Path, seeds: tuple[int, ...]) -> None:
    from flyonenomics.io import hash_file

    plan = read(plan_path)
    record = read(destination)
    runs = [read(raw / f"seed-{seed}.json") for seed in seeds]
    probe_s = float(plan["protocol"]["probe_s"])
    n_arms = len(plan["protocol"]["arms"])
    if sum(float(run["brain_seconds"]) for run in runs) != probe_s * n_arms * len(seeds):
        raise ValueError("paired probe brain-second total differs from the plan")
    identities = [run["identity"] for run in runs]
    if any(value != identities[0] for value in identities[1:]):
        raise ValueError("seed execution identities differ")
    cells = plan["cells"]
    paired_runs = [{"seed": run["seed"], "arms": {label: _seed_aggregate(run, label) for label in ARM_LABELS}}
                   for run in runs]

    per_cell = []
    for cell in cells:
        index = int(cell["engine_index"])
        arm_values: dict[str, dict[str, list[float]]] = {}
        for run in runs:
            for label in ARM_LABELS:
                row = next(item for item in run["rows"] if item["condition"] == label)
                target = next(item for item in row["targets"] if int(item["engine_index"]) == index)
                bucket = arm_values.setdefault(label, {
                    "spike": [], "mean_v_mV": [], "max_v_mV": [], "threshold_mV": [],
                    "mean_distance_mV": [], "nearest_distance_mV": [], "cx_dan_event_mV": [],
                })
                bucket["spike"].append(int(target["spike_count"]))
                bucket["mean_v_mV"].append(float(target["sampled_mean_v_mV"]))
                bucket["max_v_mV"].append(float(target["sampled_max_v_mV"]))
                bucket["threshold_mV"].append(float(target["threshold_mean_mV"]))
                bucket["mean_distance_mV"].append(float(target["mean_distance_to_threshold_mV"]))
                bucket["nearest_distance_mV"].append(float(target["nearest_sampled_distance_to_threshold_mV"]))
                bucket["cx_dan_event_mV"].append(float(target["cx_dan_event_amplitude_mV"]))
        arms_out: dict[str, Any] = {}
        for label in ARM_LABELS:
            bucket = arm_values[label]
            arms_out[label] = {
                "spike_values": bucket["spike"],
                "mean_spike": float(np.mean(bucket["spike"])),
                "responder_seeds": int(sum(value > 0 for value in bucket["spike"])),
                "mean_v_values_mV": bucket["mean_v_mV"],
                "max_v_values_mV": bucket["max_v_mV"],
                "threshold_values_mV": bucket["threshold_mV"],
                "mean_distance_values_mV": bucket["mean_distance_mV"],
                "nearest_distance_values_mV": bucket["nearest_distance_mV"],
                "cx_dan_event_values_mV": bucket["cx_dan_event_mV"],
            }
        deltas: dict[str, Any] = {}
        for name, left, right in JOB_A_CONTRASTS + JOB_B_CONTRASTS:
            a, b = arm_values[left], arm_values[right]
            deltas[name] = {
                "spike_delta_values": [x - y for x, y in zip(a["spike"], b["spike"], strict=True)],
                "spike_delta": _paired_interval([x - y for x, y in zip(a["spike"], b["spike"], strict=True)]),
                "mean_v_delta_values_mV": [x - y for x, y in zip(a["mean_v_mV"], b["mean_v_mV"], strict=True)],
                "mean_v_delta_mV": _paired_interval(
                    [x - y for x, y in zip(a["mean_v_mV"], b["mean_v_mV"], strict=True)]),
                "max_v_delta_mV": _paired_interval(
                    [x - y for x, y in zip(a["max_v_mV"], b["max_v_mV"], strict=True)]),
                "threshold_delta_mV": _paired_interval(
                    [x - y for x, y in zip(a["threshold_mV"], b["threshold_mV"], strict=True)]),
                "mean_distance_delta_mV": _paired_interval(
                    [x - y for x, y in zip(a["mean_distance_mV"], b["mean_distance_mV"], strict=True)]),
                "nearest_distance_delta_mV": _paired_interval(
                    [x - y for x, y in zip(a["nearest_distance_mV"], b["nearest_distance_mV"], strict=True)]),
                "cx_dan_event_delta_mV": _paired_interval(
                    [x - y for x, y in zip(a["cx_dan_event_mV"], b["cx_dan_event_mV"], strict=True)]),
            }
        per_cell.append({**cell, "arms": arms_out, "deltas": deltas})

    def arm_distribution(label: str, key: str, scale: float = 1.0) -> dict[str, Any]:
        values = [float(cell["arms"][label][key]) for cell in per_cell]
        return _distribution([value * scale for value in values])

    seed_spikes = {label: [run["arms"][label]["er_spikes"] for run in paired_runs] for label in ARM_LABELS}
    retain_delta = [x - y for x, y in zip(seed_spikes["driven-retain"], seed_spikes["dark"], strict=True)]
    disconnect_delta = [x - y for x, y in zip(seed_spikes["driven-disconnect"], seed_spikes["dark"], strict=True)]
    field_fraction = [d / r for d, r in zip(disconnect_delta, retain_delta, strict=True)]
    job_a = {name: _contrast(runs, left, right) for name, left, right in JOB_A_CONTRASTS}
    job_b = {name: _contrast(runs, left, right) for name, left, right in JOB_B_CONTRASTS}
    field_fraction_block = {
        "unit": (
            "per seed, (driven-disconnect minus dark) divided by (driven-retain minus dark) over the "
            "same ten seeds; the interval is mean +/- 1.96 SE and the ratio is undefined in sign if the "
            "denominator straddles zero, so the absolute spike counts are reported beside it"
        ),
        "retain_minus_dark_spikes": _paired_interval([float(value) for value in retain_delta]),
        "disconnect_minus_dark_spikes": _paired_interval([float(value) for value in disconnect_delta]),
        "field_fraction_of_retain": _paired_interval(field_fraction),
        "retain_minus_dark_values": [float(value) for value in retain_delta],
        "disconnect_minus_dark_values": [float(value) for value in disconnect_delta],
        "field_fraction_values": [float(value) for value in field_fraction],
    }
    genotype_da = {
        "wild_type_retain_eb_da_um": _paired_interval(
            [float(run["arms"]["driven-retain"]["eb_da_mean_um"]) for run in paired_runs]),
        "wild_type_disconnect_eb_da_um": _paired_interval(
            [float(run["arms"]["driven-disconnect"]["eb_da_mean_um"]) for run in paired_runs]),
        "fumin_retain_eb_da_um": _paired_interval(
            [float(run["arms"]["fumin-retain"]["eb_da_mean_um"]) for run in paired_runs]),
        "fumin_disconnect_eb_da_um": _paired_interval(
            [float(run["arms"]["fumin-disconnect"]["eb_da_mean_um"]) for run in paired_runs]),
        "dark_eb_da_um": _paired_interval(
            [float(run["arms"]["dark"]["eb_da_mean_um"]) for run in paired_runs]),
        "crossover_um": DV_CROSSOVER_DA_UM,
    }
    summary = {
        "n_cells": len(per_cell),
        "n_arms": n_arms,
        "n_seeds": len(runs),
        "arms": {label: {"seed_er_spikes": seed_spikes[label]} for label in ARM_LABELS},
        "wild_type_retain_fires_any_seed": int(sum(
            cell["arms"]["driven-retain"]["responder_seeds"] > 0 for cell in per_cell)),
        "wild_type_dark_fires_any_seed": int(sum(
            cell["arms"]["dark"]["responder_seeds"] > 0 for cell in per_cell)),
        "wild_type_disconnect_fires_any_seed": int(sum(
            cell["arms"]["driven-disconnect"]["responder_seeds"] > 0 for cell in per_cell)),
        "fumin_retain_fires_any_seed": int(sum(
            cell["arms"]["fumin-retain"]["responder_seeds"] > 0 for cell in per_cell)),
        "fumin_disconnect_fires_any_seed": int(sum(
            cell["arms"]["fumin-disconnect"]["responder_seeds"] > 0 for cell in per_cell)),
        "cell_distribution_spikes": {
            label: arm_distribution(label, "mean_spike") for label in ARM_LABELS
        },
        "key_field_isolated_spikes": field_fraction_block,
        "genotype_eb_da": genotype_da,
    }
    output = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 2: per-cell measurement of the ER response with the dopamine "
            "field driven and CX_DAN fast synapses retained or disconnected; wild type versus fumin. "
            "A null here is a real null."
        ),
        "declared_substrate_id": plan["declared_substrate_id"],
        "protocol": plan["protocol"],
        "identity": identities[0],
        "plan_sha256": hash_file(plan_path),
        "fixture": plan["fixture"],
        "fixture_sha256": hash_file(ROOT / plan["fixture"]),
        "trace_n": plan["trace_n"],
        "summary": summary,
        "job_a": job_a,
        "job_b": job_b,
        "paired_runs": paired_runs,
        "cells": per_cell,
        "raw_directory": str(raw),
        "raw_sha256": {f"seed-{seed}.json": hash_file(raw / f"seed-{seed}.json") for seed in seeds},
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    record["probe"] = output
    record["disconnect_audit"] = read(DEFAULT_AUDIT) if DEFAULT_AUDIT.is_file() else None
    record["provenance_note"] = {
        "executed_runner_sha256": output["identity"]["runner_sha256"],
        "summarizing_runner_sha256": hash_file(Path(__file__)),
        "note": (
            "The probe ran under the executed runner whose SHA-256 is recorded in identity. "
            "The committed runner differs only in the summarize function, where a KeyError was "
            "fixed to read the raw per-seed runs instead of the aggregated paired rows; the engine, "
            "probe and per-cell arithmetic are unchanged. identity.runner_sha256 is the honest "
            "run-time binding; summarizing_runner_sha256 is the file that produced this record."
        ),
    }
    record["limitation"] = (
        "The disconnection removes the fast route only for the arms that declare it. It zeroes every "
        "recurrent synapse whose presynaptic cell is in DAN or CX_DAN; it does not silence those cells, "
        "change their extended input, the innervation matrix or the kinetics. The dopamine field is "
        "therefore identical in a retain/disconnect pair, which the audit and the per-seed EB "
        "concentrations verify. The probe still injects at TuBu, downstream of a visual pathway that "
        "does not conduct: the fly does not see."
    )
    record["reading_note"] = (
        "The ring threshold term d_v is non-monotonic in dopamine (item 135): it peaks at "
        f"{DV_PEAK_DA_UM:.5f} uM and crosses zero at {DV_CROSSOVER_DA_UM:.5f} uM. A genotype difference "
        "is read only beside the measured EB concentration of each arm and the side of the crossover it "
        "sits on. Every interval that includes zero is reported as including zero; no pass floor or "
        "threshold is applied. Per-cell values are never collapsed into a population mean to stand in "
        "for a directly reached subset."
    )
    record["generated_utc"] = datetime.now(timezone.utc).isoformat()
    dump(destination, record)
    print(json.dumps({
        "retain_minus_dark_spikes": field_fraction_block["retain_minus_dark_spikes"],
        "disconnect_minus_dark_spikes": field_fraction_block["disconnect_minus_dark_spikes"],
        "field_fraction": field_fraction_block["field_fraction_of_retain"],
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def _parse_seeds(text: str) -> tuple[int, ...]:
    if "-" in text:
        lo, hi = text.split("-")
        return tuple(range(int(lo), int(hi) + 1))
    return tuple(int(value) for value in text.split(","))


def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    census_parser = sub.add_parser("census")
    census_parser.add_argument("--out", type=Path, default=DEFAULT_RECORD)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--out", type=Path, default=DEFAULT_AUDIT)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--out", type=Path, default=DEFAULT_PLAN)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    run_parser.add_argument("--out", type=Path, default=DEFAULT_RAW)
    run_parser.add_argument("--workers", type=int, choices=range(1, 17), default=8)
    run_parser.add_argument("--seeds", default="1-10")
    run_parser.add_argument("--identity-only", action="store_true")
    summary_parser = sub.add_parser("summarize")
    summary_parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    summary_parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    summary_parser.add_argument("--out", type=Path, default=DEFAULT_RECORD)
    summary_parser.add_argument("--seeds", default="1-10")
    args = parser.parse_args()

    if args.command == "census":
        build_census(args.out)
        return
    if args.command == "audit":
        build_audit(args.out)
        return
    if args.command == "plan":
        build_plan(args.out)
        return
    if args.command == "run":
        seeds = _parse_seeds(args.seeds)
        plan = read(args.plan)
        plan["identity"] = identity(f"{platform.system().lower()}-{platform.machine()}")
        dump(args.plan, plan)
        if args.identity_only:
            print(json.dumps(plan["identity"], indent=2), flush=True)
            return
        run_dynamic(args.plan, args.out, args.workers, seeds)
        return
    summarize(args.raw, args.plan, args.out, _parse_seeds(args.seeds))


if __name__ == "__main__":
    main()
