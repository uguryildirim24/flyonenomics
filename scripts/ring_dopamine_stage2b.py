"""Stage 2b of the ring-neuron dopamine experiment.

Stage 2 measured that about 95 percent of stage 1's ring-neuron spike effect
survives disconnecting ``CX_DAN``'s fast synapses.  That bounds the dopamine
field's contribution but does not show that the surviving effect acts through
the ring cells' own dopamine receptors, because driving ``CX_DAN`` also raises
dopamine in other compartments whose cells can feed ``ER``.  This stage adds
the two missing cells of the two-by-two: fast synapses retained or
disconnected, crossed with the ring threshold term ``d_v`` dynamic or clamped
to its dark reference.  In all four intervention cells ``CX_DAN`` is driven at
50 Hz and the TuBu stripe is on.

``census`` computes the constant dark reference from the code, no engine run.
``audit`` proves what the clamp replaces, that the pool stays live and that no
later update overwrites the applied value.  ``plan`` fixes the trace set and
the five paired arms.  ``run`` executes the paired 1000-brain-second probe on
the box.  ``summarize`` reduces the raw runs into the compact committed record.

Every value is a model measurement, never a pass line.  A null is the result.
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
import ring_dopamine_stage2 as s2
from flyonenomics.neuromod.state import Neuromod

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
DEFAULT_FIXTURE = Path("data/experiments/p2/ring-dopamine-stage2b.json")
DEFAULT_PLAN = Path("camber-runs/ring-dopamine-stage2b/plan.json")
DEFAULT_RAW = Path("camber-runs/ring-dopamine-stage2b/raw")
DEFAULT_AUDIT = Path("camber-runs/ring-dopamine-stage2b/audit.json")
DEFAULT_DISCONNECT_AUDIT = Path("camber-runs/ring-dopamine-stage2b/disconnect-audit.json")
DEFAULT_RECORD = Path("validation/records/p2/ring-dopamine-stage2b.json")
STAGE2_RECORD = Path("validation/records/p2/ring-dopamine-stage2.json")
SOURCE_COMMIT_ENV = s1.SOURCE_COMMIT_ENV
DECLARED_SUBSTRATE_ID = s1.DECLARED_SUBSTRATE_ID
REACHED_RECORD = s1.REACHED_RECORD

# Five paired arms.  ``dark`` is the reference for the clamp and the only arm
# that records the non-CX_DAN DAN count.  The four intervention cells all
# drive CX_DAN; ``dv_clamp`` names the dark reference for the two clamped cells.
ARMS: tuple[dict[str, Any], ...] = (
    {"label": "dark", "genotype": "wild_type", "drive_hz": 0.0,
     "dan_fast_synapses": "retain", "dv_clamp": None},
    {"label": "driven-retain", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "dv_clamp": None},
    {"label": "driven-retain-clamped", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "dv_clamp": "dark_reference"},
    {"label": "driven-disconnect", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "disconnect", "dv_clamp": None},
    {"label": "driven-disconnect-clamped", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "disconnect", "dv_clamp": "dark_reference"},
)
ARM_LABELS = tuple(arm["label"] for arm in ARMS)
# The two conditional clamp effects.  The interaction is (R1-R0) - (D1-D0).
MODULATION_CONTRASTS = (
    ("retain_modulation", "driven-retain", "driven-retain-clamped"),
    ("disconnect_modulation", "driven-disconnect", "driven-disconnect-clamped"),
)
INTERACTION_LABEL = "interaction"


class InstrumentedNeuromod(Neuromod):
    """``Neuromod`` that records d_v and can replace the ER term with a constant.

    The only override is ``receptor_terms``: it is the single source of the
    threshold term ``d_v`` and the input gain.  The clamp replaces ``d_v`` on
    the traced ER cells only; the gain, the pool, the innervation, the source
    term and the occupancies are untouched.  With ``dv_dark_mv is None`` the
    returned vector is a copy of the natural one, so the unclamped arms take a
    mathematically identical path to the base class.
    """

    def __init__(self, *args: Any, er_idx: np.ndarray | None = None,
                 dv_dark_mv: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.er_idx = (np.asarray(er_idx, dtype=np.int32) if er_idx is not None
                       else np.zeros(0, dtype=np.int32))
        self.dv_dark_mv = None if dv_dark_mv is None else float(dv_dark_mv)
        self.last_natural_dv: np.ndarray | None = None
        self.last_applied_dv: np.ndarray | None = None

    def receptor_terms(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        d_v, gain, occ1, occ2 = super().receptor_terms()
        natural = np.array(d_v, dtype=np.float64, copy=True)
        if self.dv_dark_mv is None:
            applied = natural
        else:
            applied = np.array(d_v, dtype=np.float64, copy=True)
            applied[self.er_idx] = self.dv_dark_mv
        self.last_natural_dv = natural
        self.last_applied_dv = applied
        return applied, gain, occ1, occ2


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


def probe(label: str) -> Any:
    return s1.probe(label)


def dark_reference() -> dict[str, Any]:
    """Return the ER dark reference d_v, computed from the code.

    All 228 traced ER cells read exposure from EB at weight 1.0 with the same
    receptor row, so the dark reference is one number.  It is the ``d_v`` at
    the 0.02 uM dopamine fixed point, not zero and not the base -45 mV
    threshold.
    """
    from flyonenomics.neuromod.receptors import receptor_effect
    from flyonenomics.registry import build_registry
    from flyonenomics.types import load_params

    reached = read(ROOT / REACHED_RECORD)
    er_cells = [cell for cell in reached["cells"] if "ring_ER" in cell["classes"]]
    er_idx = np.asarray(sorted(int(cell["engine_index"]) for cell in er_cells), dtype=np.int32)
    registry = build_registry("783", populations_path=ROOT / "data/populations-v0.2.yaml")
    params = load_params(ROOT / "data/params-v0.2.yaml")
    da_ref = float(params.get("da.DA_ref"))
    da_c = np.full(len(registry.compartments()), da_ref)
    d_v, gain, occ1, occ2 = receptor_effect(
        da_c, registry.exposure().tocsr(), registry.exposed_mask(),
        np.asarray(registry.receptors().r1), np.asarray(registry.receptors().r2), params)
    values = np.unique(np.asarray(d_v[er_idx], dtype=np.float64))
    if values.size != 1:
        raise ValueError("traced ER cells do not share one dark d_v")
    census = s1.ring_receptors(ROOT / REACHED_RECORD)
    return {
        "da_ref_um": da_ref,
        "dv_mv": float(values[0]),
        "er_n": int(er_idx.size),
        "er_index_sha256": digest(er_idx, np.int32),
        "occ1": float(np.unique(np.asarray(occ1[er_idx], dtype=np.float64))[0]),
        "occ2": float(np.unique(np.asarray(occ2[er_idx], dtype=np.float64))[0]),
        "gain": float(np.unique(np.asarray(gain[er_idx], dtype=np.float64))[0]),
        "stage1_ring_receptors_dv_baseline_mv": float(census["dv_baseline_mv"]),
        "matches_stage1_census": bool(abs(float(values[0]) - float(census["dv_baseline_mv"])) < 1e-12),
        "note": (
            "d_v = -dV_D1*r1*occ1 + dV_D2*r2*occ2 at da = DA_ref; the clamp uses this "
            "constant, not zero and not the base threshold"
        ),
    }


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
        "reused_stage2_runner_sha256": hash_file(Path(s2.__file__)),
        "reused_stage1_runner_sha256": hash_file(Path(s1.__file__)),
        "inputs_sha256": {name: hash_file(ROOT / "data" / name) for name in data_names},
        "connectome_sha256": {
            completeness.name: hash_file(completeness),
            connectivity.name: hash_file(connectivity),
        },
    }


def _er_targets() -> np.ndarray:
    return s2._er_targets()


def build_census(destination: Path) -> None:
    """Write the census part of the record; the probe key stays null until summarize."""
    started = time.monotonic()
    census = {
        "eb_innervation": s1.eb_innervation(),
        "ring_receptors": s1.ring_receptors(ROOT / REACHED_RECORD),
        "dark_reference": dark_reference(),
        "dan_synapse_census": s2.dan_synapse_census(),
    }
    record = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 2b: clamp the ring threshold term to its dark "
            "reference and cross that with the CX_DAN fast disconnect"
        ),
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "census": census,
        "probe": None,
        "wall_seconds": time.monotonic() - started,
    }
    dump(destination, record)
    print(json.dumps({
        "dark_reference_dv_mv": census["dark_reference"]["dv_mv"],
        "dark_reference_matches_stage1": census["dark_reference"]["matches_stage1_census"],
        "cx_dan_to_er_edges": census["dan_synapse_census"]["from_cx_dan_to_er"]["edges"],
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
    clamp_arms = set((fixture.get("meta") or {}).get("dv_clamp_arms") or [])
    fixture_arms = [
        {
            "label": arm["label"],
            "genotype": arm["genotype"]["named"],
            "drive_hz": float(next(
                (hook["rate_hz"] for hook in arm["genotype"].get("manipulations", [])
                 if hook["type"] == "activate"), 0.0)),
            "dan_fast_synapses": (arm.get("layers") or {}).get(
                "dan_fast_synapses", fixture["layers"]["dan_fast_synapses"]),
            "dv_clamp": ("dark_reference" if arm["label"] in clamp_arms else None),
        }
        for arm in fixture["arms"]
    ]
    if tuple(arm["label"] for arm in fixture_arms) != ARM_LABELS:
        raise ValueError("fixture arms do not match the runner's arm order")
    reference = dark_reference()
    output = {
        "class": "development",
        "purpose": "ring-neuron dopamine stage 2b five-arm paired probe plan",
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
            "dv_dark_reference_mv": float(reference["dv_mv"]),
            "clamp_definition": (
                "InstrumentedNeuromod.receptor_terms replaces d_v on the 228 traced ER cells "
                "with the constant dark reference; the dopamine pool, innervation, source term, "
                "occupancies and the input gain are untouched"
            ),
            "disconnect_definition": (
                "Neuromod.apply_genotype with dan_fast_synapses='disconnect' zeroes every "
                "recurrent synapse whose presynaptic cell is in DAN or CX_DAN; it does not "
                "silence those cells, change their extended input rates, or change the "
                "innervation matrix or kinetics"
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
    return s2._prepare_declared(trace_indices, with_traces=with_traces)


def build_clamp_audit(ctx: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """Prove what the clamp replaces and that nothing overwrites it.

    One declared engine, two neuromod instances on the same driven pool: the
    base class and the instrumented one.  The audit shows the natural ER d_v
    is driven, the applied ER d_v is exactly the dark reference, the gain,
    occupancies and pool are untouched, and setting the threshold twice (after
    a pool step) leaves the clamp in place.
    """
    from flyonenomics.registry.compartments import compartment_index
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags

    engine = ctx["engine"]
    registry = ctx["registry"]
    params = ctx["params"]
    targets = np.asarray(ctx["targets"], dtype=np.int32)
    base_threshold = np.asarray(ctx["base_threshold"], dtype=np.float64)
    eb = compartment_index()["EB"]
    dv_dark = float(reference["dv_mv"])

    layers = LayerFlags(background=True, dopamine_A=True, transporter_C=True,
                        dan_fast_synapses="retain")
    plain = Neuromod(registry, params, layers, ctx["dopamine"], base_v_th=base_threshold,
                     schema_version="1.3", drive_groups=ctx["groups"])
    clamped = InstrumentedNeuromod(registry, params, layers, ctx["dopamine"], base_v_th=base_threshold,
                                   schema_version="1.3", drive_groups=ctx["groups"],
                                   er_idx=targets, dv_dark_mv=dv_dark)
    plain.apply_genotype(named_manipulations("wild_type"), engine)
    clamped.apply_genotype(named_manipulations("wild_type"), engine)
    plain.reset_fast()
    clamped.reset_fast()
    # Drive the pool to a representative driven concentration without touching
    # the dopamine source terms: the clamp must not depend on the pool value.
    for mod in (plain, clamped):
        mod.da_c[eb] = 3.4
    plain_dv, plain_gain, plain_occ1, plain_occ2 = plain.receptor_terms()
    applied_dv, clamped_gain, clamped_occ1, clamped_occ2 = clamped.receptor_terms()
    natural_dv = np.array(clamped.last_natural_dv, dtype=np.float64)
    applied = np.array(clamped.last_applied_dv, dtype=np.float64)
    if clamped.last_applied_dv is None or clamped.last_natural_dv is None:
        raise RuntimeError("instrumented neuromod did not record receptor terms")
    non_er = np.setdiff1d(np.arange(registry.n), targets)
    er_natural = np.unique(natural_dv[targets])
    er_applied = np.unique(applied[targets])
    if er_natural.size != 1 or er_applied.size != 1:
        raise RuntimeError("ER d_v is not uniform across the traced cells")
    if abs(float(er_applied[0]) - dv_dark) > 1e-12:
        raise RuntimeError("applied ER d_v differs from the dark reference")
    if abs(float(er_natural[0]) - dv_dark) < 1e-9:
        raise RuntimeError("driven ER d_v did not move off the dark reference")
    non_er_clamped_equals_natural = bool(np.array_equal(applied[non_er], natural_dv[non_er]))
    gain_unchanged = bool(np.array_equal(clamped_gain, plain_gain))
    occ_live = bool(np.all(np.isfinite(clamped_occ1)) and np.all(np.isfinite(clamped_occ2))
                    and float(er_applied[0]) == dv_dark)

    composed = clamped.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)
    expected_er = np.clip(base_threshold[targets] + clamped.shift[targets] + dv_dark,
                          *params.get("rec.vth_clip"))
    engine_after_set = np.asarray(engine.thresholds_mv()[targets], dtype=np.float64)
    set_matches = bool(np.max(np.abs(engine_after_set - expected_er)) < 1e-9)
    # One pool step must not overwrite the applied threshold.
    synthetic = np.zeros(registry.n, dtype=np.int32)
    da_idx = np.asarray(ctx["dopamine_neurons"], dtype=np.int32)
    synthetic[da_idx] = 1
    da_before = float(clamped.da_c[eb])
    clamped.on_chunk(synthetic, 0.001)
    da_after = float(clamped.da_c[eb])
    composed2 = clamped.compose()
    engine.set_threshold(composed2.v_th)
    engine.set_gain(composed2.gain)
    engine_after_step = np.asarray(engine.thresholds_mv()[targets], dtype=np.float64)
    step_matches = bool(np.max(np.abs(engine_after_step - expected_er)) < 1e-9)
    applied_after_step = float(np.unique(np.asarray(clamped.last_applied_dv[targets]))[0])
    return {
        "class": "development",
        "purpose": "prove the ER d_v clamp replaces only the threshold term and survives a pool step",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "platform": f"{platform.system().lower()}-{platform.machine()}",
        "er_n": int(targets.size),
        "da_ref_um": float(reference["da_ref_um"]),
        "dv_dark_reference_mv": dv_dark,
        "driven_da_eb_um": 3.4,
        "natural_er_dv_mv": float(er_natural[0]),
        "applied_er_dv_mv": float(er_applied[0]),
        "applied_equals_dark_reference": bool(abs(float(er_applied[0]) - dv_dark) < 1e-12),
        "natural_differs_from_dark_reference": bool(abs(float(er_natural[0]) - dv_dark) > 1e-9),
        "non_er_clamped_equals_natural": non_er_clamped_equals_natural,
        "gain_unchanged_by_clamp": gain_unchanged,
        "er_gain": float(np.unique(np.asarray(clamped_gain[targets], dtype=np.float64))[0]),
        "er_occ1": float(np.unique(np.asarray(clamped_occ1[targets], dtype=np.float64))[0]),
        "er_occ2": float(np.unique(np.asarray(clamped_occ2[targets], dtype=np.float64))[0]),
        "occupancies_finite": occ_live,
        "pool_unchanged_by_compose": bool(abs(da_before - 3.4) < 1e-12),
        "da_eb_before_pool_step_um": da_before,
        "da_eb_after_pool_step_um": da_after,
        "pool_is_live": bool(abs(da_after - da_before) > 0.0),
        "engine_threshold_matches_expected_after_set": set_matches,
        "engine_threshold_matches_expected_after_pool_step": step_matches,
        "applied_after_pool_step_mv": applied_after_step,
        "threshold_expected_er_mv": float(expected_er[0]),
        "threshold_engine_after_set_er_mv": float(engine_after_set[0]),
        "threshold_engine_after_step_er_mv": float(engine_after_step[0]),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_audit(destination: Path) -> None:
    """Write the disconnect audit (reused) plus the clamp audit."""
    started = time.monotonic()
    targets = _er_targets()
    ctx = _prepare_declared(targets, with_traces=False)
    reference = dark_reference()
    # Reuse stage 2's disconnect audit verbatim: the same layer, same mask.
    s2.build_audit(DEFAULT_DISCONNECT_AUDIT)
    output = {
        "class": "development",
        "purpose": "stage 2b clamp audit and the reused stage 2 disconnect audit",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "reference": reference,
        "clamp": build_clamp_audit(ctx, reference),
        "disconnect": read(DEFAULT_DISCONNECT_AUDIT),
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination, output)
    print(json.dumps({
        "applied_equals_dark_reference": output["clamp"]["applied_equals_dark_reference"],
        "natural_differs_from_dark_reference": output["clamp"]["natural_differs_from_dark_reference"],
        "gain_unchanged_by_clamp": output["clamp"]["gain_unchanged_by_clamp"],
        "engine_threshold_matches_expected_after_pool_step":
            output["clamp"]["engine_threshold_matches_expected_after_pool_step"],
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def run_seed(job: tuple[int, str, str]) -> str:
    """Run all five arms for one seed in one built engine, paired on the same stream."""
    from flyonenomics.behaviour.arena import Behaviour
    from flyonenomics.io import read_yaml
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags

    seed, plan_path, destination = job
    destination_path = Path(destination)
    plan = read(Path(plan_path))
    probe_s = float(plan["protocol"]["probe_s"])
    settle_s = float(plan["protocol"]["settle_s"])
    eb_index = int(plan["protocol"]["eb_compartment_index"])
    dv_dark = float(plan["protocol"]["dv_dark_reference_mv"])
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
    dan_neurons = np.asarray(registry.population("DAN").idx, dtype=np.int32)
    rows = []
    chunk_ms = float(params.get("engine.chunk_ms"))
    settle_chunks = int(round(settle_s * 1000.0 / chunk_ms))
    total_chunks = int(round(probe_s * 1000.0 / chunk_ms))
    n_comp = len(registry.compartments())
    for arm in plan["protocol"]["arms"]:
        label = arm["label"]
        clamped = arm.get("dv_clamp") == "dark_reference"
        engine.restore("declared")
        engine.seed(brian_seed(MASTER, seed, 0))
        mod = InstrumentedNeuromod(
            registry, params,
            LayerFlags(background=True, dopamine_A=True, transporter_C=True,
                       dan_fast_synapses=arm["dan_fast_synapses"]),
            dopamine, base_v_th=base_threshold, schema_version="1.3", drive_groups=groups,
            er_idx=targets, dv_dark_mv=(dv_dark if clamped else None),
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
        natural_dv_sum = np.zeros(len(targets), dtype=np.float64)
        natural_dv_min = np.full(len(targets), np.inf)
        natural_dv_max = np.full(len(targets), -np.inf)
        applied_dv_sum = np.zeros(len(targets), dtype=np.float64)
        applied_dv_min = np.full(len(targets), np.inf)
        applied_dv_max = np.full(len(targets), -np.inf)
        natural_dv_chunks: list[float] = []
        applied_dv_chunks: list[float] = []
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
                natural = np.asarray(mod.last_natural_dv[targets], dtype=np.float64)
                applied = np.asarray(mod.last_applied_dv[targets], dtype=np.float64)
                natural_dv_sum += natural
                np.minimum(natural_dv_min, natural, out=natural_dv_min)
                np.maximum(natural_dv_max, natural, out=natural_dv_max)
                applied_dv_sum += applied
                np.minimum(applied_dv_min, applied, out=applied_dv_min)
                np.maximum(applied_dv_max, applied, out=applied_dv_max)
                natural_dv_chunks.append(float(natural[0]))
                applied_dv_chunks.append(float(applied[0]))
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
                "natural_dv_mean_mV": float(natural_dv_sum[position] / measurement_chunks),
                "natural_dv_min_mV": float(natural_dv_min[position]),
                "natural_dv_max_mV": float(natural_dv_max[position]),
                "applied_dv_mean_mV": float(applied_dv_sum[position] / measurement_chunks),
                "applied_dv_min_mV": float(applied_dv_min[position]),
                "applied_dv_max_mV": float(applied_dv_max[position]),
            })
        rows.append({
            "condition": label,
            "genotype": arm["genotype"],
            "dan_fast_synapses": arm["dan_fast_synapses"],
            "dv_clamp": arm.get("dv_clamp"),
            "dopamine_drive_hz": drive_hz,
            "source_population": SOURCE_POPULATION,
            "source_n": int(len(source)),
            "source_spikes": int(count[source].sum()),
            "source_rate_hz": float(count[source].sum() / (len(source) * (probe_s - settle_s))),
            "dopamine_population": DOPAMINE_POPULATION,
            "dopamine_n": int(len(dopamine_neurons)),
            "dopamine_spikes": int(count[dopamine_neurons].sum()),
            "dopamine_rate_hz": float(count[dopamine_neurons].sum() / (len(dopamine_neurons) * (probe_s - settle_s))),
            "dan_population": "DAN",
            "dan_n": int(len(dan_neurons)),
            "dan_spikes": int(count[dan_neurons].sum()),
            "dan_rate_hz": float(count[dan_neurons].sum() / (len(dan_neurons) * (probe_s - settle_s))),
            "input_rate_min_hz": float(input_min),
            "input_rate_max_hz": float(input_max),
            "targets": target_rows,
            "eb_da_mean_um": float(da_sum[eb_index] / measurement_chunks),
            "eb_da_min_um": float(da_min[eb_index]),
            "eb_da_max_um": float(da_max[eb_index]),
            "da_mean_um": (da_sum / measurement_chunks).tolist(),
            "da_min_um": da_min.tolist(),
            "da_max_um": da_max.tolist(),
            "natural_dv_chunks_mV": natural_dv_chunks,
            "applied_dv_chunks_mV": applied_dv_chunks,
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
    natural_dv = [float(item["natural_dv_mean_mV"]) for item in targets]
    applied_dv = [float(item["applied_dv_mean_mV"]) for item in targets]
    return {
        "er_spikes": int(sum(spikes)),
        "active_cells": int(sum(value > 0 for value in spikes)),
        "mean_v_mV": float(np.mean(mean_v)),
        "max_v_mV": float(np.max(max_v)),
        "threshold_mV": float(np.mean(threshold)),
        "mean_distance_mV": float(np.mean(mean_distance)),
        "nearest_distance_mV": float(np.mean(nearest_distance)),
        "cx_dan_event_total_mV": float(np.sum(cx_event)),
        "natural_dv_mV": float(np.mean(natural_dv)),
        "applied_dv_mV": float(np.mean(applied_dv)),
        "source_rate_hz": float(row["source_rate_hz"]),
        "dopamine_rate_hz": float(row["dopamine_rate_hz"]),
        "dopamine_spikes": int(row["dopamine_spikes"]),
        "dan_spikes": int(row["dan_spikes"]),
        "dan_rate_hz": float(row["dan_rate_hz"]),
        "eb_da_mean_um": float(row["eb_da_mean_um"]),
        "eb_da_max_um": float(row["eb_da_max_um"]),
    }


AGGREGATE_KEYS = (
    "er_spikes", "active_cells", "mean_v_mV", "max_v_mV", "threshold_mV",
    "mean_distance_mV", "nearest_distance_mV", "cx_dan_event_total_mV",
    "natural_dv_mV", "applied_dv_mV", "source_rate_hz", "dopamine_rate_hz",
    "dopamine_spikes", "dan_spikes", "dan_rate_hz", "eb_da_mean_um", "eb_da_max_um",
)


def _contrast(paired_runs: list[dict[str, Any]], left: str, right: str) -> dict[str, Any]:
    """Paired left-minus-right over seeds for the seed-level aggregate fields."""
    values: dict[str, list[float]] = {key: [] for key in AGGREGATE_KEYS}
    for run in paired_runs:
        a = _seed_aggregate(run, left)
        b = _seed_aggregate(run, right)
        for key in AGGREGATE_KEYS:
            values[key].append(float(a[key]) - float(b[key]))
    output = {
        "left": left,
        "right": right,
        "unit": "paired difference is left minus right over the ten seeds; interval is mean +/- 1.96 SE",
    }
    for key in AGGREGATE_KEYS:
        output[key] = _paired_interval(values[key])
    output["seed_values"] = values
    return output


def _interaction(paired_runs: list[dict[str, Any]], retain: dict[str, Any],
                 disconnect: dict[str, Any]) -> dict[str, Any]:
    """(R1-R0) - (D1-D0) per seed, with its paired interval and resolution."""
    values: dict[str, list[float]] = {key: [] for key in AGGREGATE_KEYS}
    for run in paired_runs:
        r1 = _seed_aggregate(run, "driven-retain")
        r0 = _seed_aggregate(run, "driven-retain-clamped")
        d1 = _seed_aggregate(run, "driven-disconnect")
        d0 = _seed_aggregate(run, "driven-disconnect-clamped")
        for key in AGGREGATE_KEYS:
            values[key].append(float(r1[key]) - float(r0[key]) - (float(d1[key]) - float(d0[key])))
    output = {
        "unit": (
            "per seed, (driven-retain minus driven-retain-clamped) minus "
            "(driven-disconnect minus driven-disconnect-clamped); interval is mean +/- 1.96 SE"
        ),
        "retain_modulation": retain["er_spikes"],
        "disconnect_modulation": disconnect["er_spikes"],
    }
    for key in AGGREGATE_KEYS:
        output[key] = _paired_interval(values[key])
    output["seed_values"] = values
    spikes = output["er_spikes"]
    output["resolution"] = {
        "unit": (
            "smallest spike effect this design could resolve from the measured standard error; "
            "1.96 SE is the project's interval convention and 2.262 SE is the paired-t "
            "multiplier at n=10. Neither is a pass line."
        ),
        "interaction_spikes_1.96_se": float(1.96 * spikes["se"]),
        "interaction_spikes_2.262_se": float(2.262 * spikes["se"]),
        "interaction_spikes_se": float(spikes["se"]),
        "interaction_spikes_mean": float(spikes["mean"]),
        "includes_zero": bool(spikes["includes_zero"]),
    }
    return output


def _arm_hits(runs: list[dict[str, Any]]) -> dict[str, int]:
    """Number of cells that fire at least once in any seed for each arm."""
    labels = {label: 0 for label in ARM_LABELS}
    fire = {label: set() for label in ARM_LABELS}
    for run in runs:
        for label in ARM_LABELS:
            row = next(item for item in run["rows"] if item["condition"] == label)
            for target in row["targets"]:
                if int(target["spike_count"]) > 0:
                    fire[label].add(int(target["engine_index"]))
    for label in ARM_LABELS:
        labels[label] = len(fire[label])
    return labels


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
                    "natural_dv_mV": [], "applied_dv_mV": [], "eb_da_um": [],
                })
                bucket["spike"].append(int(target["spike_count"]))
                bucket["mean_v_mV"].append(float(target["sampled_mean_v_mV"]))
                bucket["max_v_mV"].append(float(target["sampled_max_v_mV"]))
                bucket["threshold_mV"].append(float(target["threshold_mean_mV"]))
                bucket["mean_distance_mV"].append(float(target["mean_distance_to_threshold_mV"]))
                bucket["nearest_distance_mV"].append(float(target["nearest_sampled_distance_to_threshold_mV"]))
                bucket["cx_dan_event_mV"].append(float(target["cx_dan_event_amplitude_mV"]))
                bucket["natural_dv_mV"].append(float(target["natural_dv_mean_mV"]))
                bucket["applied_dv_mV"].append(float(target["applied_dv_mean_mV"]))
                bucket["eb_da_um"].append(float(row["eb_da_mean_um"]))
        arms_out: dict[str, Any] = {}
        for label in ARM_LABELS:
            bucket = arm_values[label]
            arms_out[label] = {
                "spike_values": bucket["spike"],
                "mean_spike": float(np.mean(bucket["spike"])),
                "active_seeds": int(sum(value > 0 for value in bucket["spike"])),
                "mean_v_values_mV": bucket["mean_v_mV"],
                "max_v_values_mV": bucket["max_v_mV"],
                "threshold_values_mV": bucket["threshold_mV"],
                "mean_distance_values_mV": bucket["mean_distance_mV"],
                "nearest_distance_values_mV": bucket["nearest_distance_mV"],
                "cx_dan_event_values_mV": bucket["cx_dan_event_mV"],
                "natural_dv_values_mV": bucket["natural_dv_mV"],
                "applied_dv_values_mV": bucket["applied_dv_mV"],
                "eb_da_values_um": bucket["eb_da_um"],
            }
        deltas: dict[str, Any] = {}
        for name, left, right in MODULATION_CONTRASTS:
            a, b = arm_values[left], arm_values[right]
            deltas[name] = {
                "spike_delta_values": [x - y for x, y in zip(a["spike"], b["spike"], strict=True)],
                "spike_delta": _paired_interval([x - y for x, y in zip(a["spike"], b["spike"], strict=True)]),
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
                "natural_dv_delta_mV": _paired_interval(
                    [x - y for x, y in zip(a["natural_dv_mV"], b["natural_dv_mV"], strict=True)]),
                "applied_dv_delta_mV": _paired_interval(
                    [x - y for x, y in zip(a["applied_dv_mV"], b["applied_dv_mV"], strict=True)]),
                "eb_da_delta_um": _paired_interval(
                    [x - y for x, y in zip(a["eb_da_um"], b["eb_da_um"], strict=True)]),
            }
        # Interaction per cell: (R1-R0) - (D1-D0) elementwise on the seed vectors.
        r1, r0 = arm_values["driven-retain"], arm_values["driven-retain-clamped"]
        d1, d0 = arm_values["driven-disconnect"], arm_values["driven-disconnect-clamped"]

        def interaction_values(key: str) -> list[float]:
            return [a - b - (c - d) for a, b, c, d in
                    zip(r1[key], r0[key], d1[key], d0[key], strict=True)]

        deltas[INTERACTION_LABEL] = {
            "spike_delta_values": interaction_values("spike"),
            "spike_delta": _paired_interval(interaction_values("spike")),
            "mean_v_delta_mV": _paired_interval(interaction_values("mean_v_mV")),
            "max_v_delta_mV": _paired_interval(interaction_values("max_v_mV")),
            "threshold_delta_mV": _paired_interval(interaction_values("threshold_mV")),
            "mean_distance_delta_mV": _paired_interval(interaction_values("mean_distance_mV")),
            "nearest_distance_delta_mV": _paired_interval(interaction_values("nearest_distance_mV")),
            "natural_dv_delta_mV": _paired_interval(interaction_values("natural_dv_mV")),
            "applied_dv_delta_mV": _paired_interval(interaction_values("applied_dv_mV")),
            "eb_da_delta_um": _paired_interval(interaction_values("eb_da_um")),
        }
        per_cell.append({**cell, "arms": arms_out, "deltas": deltas})

    def arm_distribution(label: str, key: str, scale: float = 1.0) -> dict[str, Any]:
        values = [float(cell["arms"][label][key]) for cell in per_cell]
        return _distribution([value * scale for value in values])

    seed_spikes = {label: [run["arms"][label]["er_spikes"] for run in paired_runs] for label in ARM_LABELS}
    retain = _contrast(runs, "driven-retain", "driven-retain-clamped")
    disconnect = _contrast(runs, "driven-disconnect", "driven-disconnect-clamped")
    interaction = _interaction(runs, retain, disconnect)
    hits = _arm_hits(runs)
    # Dark reference constancy check over the probe, per seed.
    dark_dv_check = []
    for run in runs:
        row = next(item for item in run["rows"] if item["condition"] == "dark")
        chunks = [float(value) for value in row["natural_dv_chunks_mV"]]
        dark_dv_check.append({
            "seed": int(run["seed"]),
            "natural_dv_min_mV": float(min(chunks)),
            "natural_dv_max_mV": float(max(chunks)),
            "natural_dv_mean_mV": float(np.mean(chunks)),
            "spread_mV": float(max(chunks) - min(chunks)),
            "eb_da_mean_um": float(row["eb_da_mean_um"]),
            "eb_da_max_um": float(row["eb_da_max_um"]),
        })
    spreads = [item["spread_mV"] for item in dark_dv_check]
    # Anchor reproduction against the committed stage 2 record.
    stage2 = read(ROOT / STAGE2_RECORD)
    stage2_arms = stage2["probe"]["summary"]["arms"]
    anchors = {}
    for label in ("dark", "driven-retain", "driven-disconnect"):
        mine = [int(value) for value in seed_spikes[label]]
        theirs = [int(value) for value in stage2_arms[label]["seed_er_spikes"]]
        if len(mine) != len(theirs):
            anchors[label] = {
                "fresh_seed_er_spikes": mine,
                "stage2_seed_er_spikes": theirs,
                "differences": None,
                "identical": False,
                "max_abs_difference": None,
                "note": "seed count differs; reproduction not compared",
            }
            continue
        differences = [a - b for a, b in zip(mine, theirs, strict=True)]
        anchors[label] = {
            "fresh_seed_er_spikes": mine,
            "stage2_seed_er_spikes": theirs,
            "differences": differences,
            "identical": bool(all(value == 0 for value in differences)),
            "max_abs_difference": int(max(abs(value) for value in differences)),
        }
    summary = {
        "n_cells": len(per_cell),
        "n_arms": n_arms,
        "n_seeds": len(runs),
        "arms": {label: {"seed_er_spikes": seed_spikes[label]} for label in ARM_LABELS},
        "active_cells_any_seed": hits,
        "cell_distribution_spikes": {
            label: arm_distribution(label, "mean_spike") for label in ARM_LABELS
        },
        "dark_reference_check": {
            "unit": "dark arm natural ER d_v over the 18 s window, per seed, in mV",
            "per_seed": dark_dv_check,
            "max_spread_mV": float(max(spreads)),
            "constant_to_1e-3_mV": bool(max(spreads) < 1e-3),
            "constant_to_exact": bool(max(spreads) == 0.0),
            "note": (
                "stage 1 recorded a 5e-6 uM stray-spike transient on two dark seeds; the "
                "clamp uses the constant dark reference and this is the size of the departure"
            ),
        },
        "anchors": anchors,
        "clamp_audit": read(DEFAULT_AUDIT) if DEFAULT_AUDIT.is_file() else None,
    }
    output = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 2b: the two-by-two of CX_DAN fast synapses present or "
            "absent crossed with the ER threshold term dynamic or clamped to its dark reference. "
            "Per cell, never a population mean. A null is a result."
        ),
        "declared_substrate_id": plan["declared_substrate_id"],
        "protocol": plan["protocol"],
        "identity": identities[0],
        "plan_sha256": hash_file(plan_path),
        "fixture": plan["fixture"],
        "fixture_sha256": hash_file(ROOT / plan["fixture"]),
        "trace_n": plan["trace_n"],
        "summary": summary,
        "retain_modulation": retain,
        "disconnect_modulation": disconnect,
        "interaction": interaction,
        "paired_runs": paired_runs,
        "cells": per_cell,
        "raw_directory": str(raw),
        "raw_sha256": {f"seed-{seed}.json": hash_file(raw / f"seed-{seed}.json") for seed in seeds},
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    record["probe"] = output
    record["disconnect_audit"] = (read(DEFAULT_AUDIT).get("disconnect")
                                  if DEFAULT_AUDIT.is_file() else None)
    record["provenance_note"] = {
        "executed_runner_sha256": output["identity"]["runner_sha256"],
        "summarizing_runner_sha256": hash_file(Path(__file__)),
        "note": (
            "The probe ran under the executed runner whose SHA-256 is recorded in identity and in the "
            "raw seed files. The committed runner differs only in summarize: per-cell EB dopamine "
            "recording and this note were added after the run. The engine, the probe, the clamp and "
            "the per-cell arithmetic are unchanged, and the raw seed files are the run evidence."
        ),
    }
    record["limitation"] = (
        "This is a threshold-modulation test, not an all-dopamine test. The clamp replaces only "
        "the ER threshold term d_v; the dopamine pool, innervation, source activity, the "
        "occ1/occ2 calculation and the receptor input gain all stay live, so any dopamine effect "
        "that does not act through d_v is still present in the clamped arms. The probe injects at "
        "TuBu, downstream of a visual pathway that does not conduct: the fly does not see. A "
        "clamped arm is not the same condition as the dark arm, which removes source activation "
        "and leaves EB dopamine at its fixed point rather than driving it."
    )
    record["reading_note"] = (
        "An interval that includes zero is no detected difference, not equivalence, and an interval "
        "containing zero does not establish additivity. Neither the interaction interval nor its "
        "resolution is a pass line (item 121). Both arms carry the stripe, so a firing cell is an "
        "active cell, not a demonstrated stripe response."
    )
    record["generated_utc"] = datetime.now(timezone.utc).isoformat()
    dump(destination, record)
    print(json.dumps({
        "retain_modulation_spikes": retain["er_spikes"],
        "disconnect_modulation_spikes": disconnect["er_spikes"],
        "interaction_spikes": interaction["er_spikes"],
        "interaction_resolution": interaction["resolution"],
        "anchors_identical": {label: anchors[label]["identical"] for label in anchors},
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
    run_parser.add_argument("--workers", type=int, choices=range(1, 17), default=10)
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
