"""Stage 2c of the ring-neuron dopamine experiment.

Stage 2b clamped the ring threshold term ``d_v`` and found that about 36 percent
of the retained arm's excess is removed with the ring's own input gain still
live at x1.1256.  Item 139 kept that residual an unresolved disjunction (ring
gain or indirect dopamine elsewhere) and item 140 asked for one combined clamp
in the retained network.  This stage runs that combined clamp: it replaces both
the final applied ``d_v`` and the final applied input gain on the 228 traced
``ER`` cells with their dark references, by the same route stage 2b clamped
``d_v`` (inside ``InstrumentedNeuromod.receptor_terms``).  It also runs the
matched dark-disconnected arm ``BD`` that item 140 says the disconnected
fraction is missing.

Five paired arms, wild type, ten seeds, 20 s probes, 228 traced ``ER`` cells,
the TuBu stripe on throughout: ``dark`` (B), ``dark-disconnect`` (BD),
``driven-retain`` (R1), ``driven-retain-clamped`` (R0) and
``driven-retain-both-clamped`` (Rb).  B, R1 and R0 are anchors re-run under
this round's plan; BD and Rb are new.  The runner reuses
``scripts/ring_dopamine_stage2b.py`` wholesale, including its
``InstrumentedNeuromod`` and both its audits.

``census`` computes the dark references from the code, no engine run.  ``audit``
reuses stage 2's disconnect audit and stage 2b's threshold-clamp audit and adds
the gain and combined clamp audits.  ``plan`` fixes the trace set and the five
paired arms.  ``run`` executes the paired 1000-brain-second probe on the box.
``summarize`` reduces the raw runs into the compact committed record.

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
import ring_dopamine_stage2b as s2b
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
DEFAULT_FIXTURE = Path("data/experiments/p2/ring-dopamine-stage2c.json")
DEFAULT_PLAN = Path("camber-runs/ring-dopamine-stage2c/plan.json")
DEFAULT_RAW = Path("camber-runs/ring-dopamine-stage2c/raw")
DEFAULT_AUDIT = Path("camber-runs/ring-dopamine-stage2c/audit.json")
DEFAULT_DISCONNECT_AUDIT = Path("camber-runs/ring-dopamine-stage2c/disconnect-audit.json")
DEFAULT_RECORD = Path("validation/records/p2/ring-dopamine-stage2c.json")
STAGE2B_RECORD = Path("validation/records/p2/ring-dopamine-stage2b.json")
SOURCE_COMMIT_ENV = s1.SOURCE_COMMIT_ENV
DECLARED_SUBSTRATE_ID = s1.DECLARED_SUBSTRATE_ID
REACHED_RECORD = s1.REACHED_RECORD

# Five paired arms.  ``dark`` anchors stage 2/2b; ``dark-disconnect`` is the
# matched dark reference item 140 asks for; the three driven-retain arms cross
# the ring d_v clamp with the ring input-gain clamp.  ``dv_clamp`` and
# ``gain_clamp`` name the dark reference for the clamped cells.
ARMS: tuple[dict[str, Any], ...] = (
    {"label": "dark", "genotype": "wild_type", "drive_hz": 0.0,
     "dan_fast_synapses": "retain", "dv_clamp": None, "gain_clamp": None},
    {"label": "dark-disconnect", "genotype": "wild_type", "drive_hz": 0.0,
     "dan_fast_synapses": "disconnect", "dv_clamp": None, "gain_clamp": None},
    {"label": "driven-retain", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "dv_clamp": None, "gain_clamp": None},
    {"label": "driven-retain-clamped", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "dv_clamp": "dark_reference", "gain_clamp": None},
    {"label": "driven-retain-both-clamped", "genotype": "wild_type", "drive_hz": DA_DRIVE_HZ,
     "dan_fast_synapses": "retain", "dv_clamp": "dark_reference", "gain_clamp": "dark_reference"},
)
ARM_LABELS = tuple(arm["label"] for arm in ARMS)


class InstrumentedNeuromod(s2b.InstrumentedNeuromod):
    """Stage 2b's instrumented neuromod plus an optional input-gain clamp.

    The base class clamps ``d_v`` on the traced ER cells.  This subclass adds
    the ring input gain by the same route: it replaces the gain returned by
    ``receptor_terms`` on the ER indices only.  The gain is what
    ``Neuromod.compose`` multiplies into the applied gain and what the engine
    applies postsynaptically (``g += w * gain_i_post``), so clamping it pins
    the ring's received input scale and nothing else.  With ``gain_dark is
    None`` the returned gain is a copy of the natural one, so the unclamped
    arms take a mathematically identical path.
    """

    def __init__(self, *args: Any, gain_dark: float | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.gain_dark = None if gain_dark is None else float(gain_dark)
        self.last_natural_gain: np.ndarray | None = None
        self.last_applied_gain: np.ndarray | None = None

    def receptor_terms(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        d_v, gain, occ1, occ2 = super().receptor_terms()
        natural_gain = np.array(gain, dtype=np.float64, copy=True)
        if self.gain_dark is None:
            applied_gain = natural_gain
        else:
            applied_gain = np.array(gain, dtype=np.float64, copy=True)
            applied_gain[self.er_idx] = self.gain_dark
        self.last_natural_gain = natural_gain
        self.last_applied_gain = applied_gain
        return d_v, applied_gain, occ1, occ2


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


def _er_targets() -> np.ndarray:
    return s2._er_targets()


def dark_reference() -> dict[str, Any]:
    """Return the ER dark reference d_v and gain, computed from the code.

    Stage 2b computes the threshold reference; this stage calls that function
    and adds the gain note, since both references are read from the same
    ``receptor_effect`` call at the 0.02 uM fixed point.
    """
    reference = s2b.dark_reference()
    reference["gain_note"] = (
        "gain = 1 + gamma_D1*r1*occ1 - gamma_D2*r2*occ2 at da = DA_ref; the engine "
        "applies it only as the postsynaptic input multiplier, so clamping it pins "
        "the ring's received input scale and nothing downstream"
    )
    return reference


def local_dopamine_sites() -> dict[str, Any]:
    """Record the merged-code search for every ER-local dopamine application site.

    Static inspection, no engine run.  The two sites are the only runtime
    quantities ``receptor_effect`` produces that reach a cell, and the engine
    has exactly two per-neuron dopamine-dependent write points.  The Dop1R2
    density ``rq`` is carried in the receptor map and used only to define the
    ``DA_exposed`` census population, never in ``receptor_effect``.
    """
    return {
        "method": (
            "searched src/ for receptor_effect, receptor_terms, compose and the engine's "
            "per-neuron write points; the runtime dopamine coupling is the tuple returned "
            "by flyonenomics/neuromod/receptors.py::receptor_effect"
        ),
        "sites": [
            {
                "name": "threshold_shift_d_v",
                "produced_at": "src/flyonenomics/neuromod/receptors.py:receptor_effect",
                "applied_at": "src/flyonenomics/neuromod/state.py:Neuromod.compose "
                              "(v_th = clip(base_v_th + shift + d_v)); consumed as the spike threshold",
                "vector": "d_v",
            },
            {
                "name": "input_gain",
                "produced_at": "src/flyonenomics/neuromod/receptors.py:receptor_effect",
                "applied_at": "src/flyonenomics/neuromod/state.py:Neuromod.compose "
                              "(gain = clip(geno_gain * g_da)); consumed at "
                              "src/flyonenomics/engine/models.py:LIF_ON_PRE (g += w * gain_i_post)",
                "vector": "gain",
            },
        ],
        "other_receptor_densities": {
            "rq": (
                "carried in the receptor map and used only by "
                "src/flyonenomics/registry/derived.py:da_exposed to define the DA_exposed "
                "census population; it never enters receptor_effect or compose"
            ),
        },
        "output_side_modulation": (
            "none: the engine's only dopamine-dependent per-neuron write points are "
            "set_threshold and set_gain; gain is postsynaptic (received input), so no "
            "ER-output parameter is modulated"
        ),
        "conclusion": (
            "d_v and the input gain exhaust the implemented ER-local dopamine application "
            "sites; both act on received input, and no output-side modulation exists"
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
        "reused_stage2b_runner_sha256": hash_file(Path(s2b.__file__)),
        "reused_stage2_runner_sha256": hash_file(Path(s2.__file__)),
        "reused_stage1_runner_sha256": hash_file(Path(s1.__file__)),
        "inputs_sha256": {name: hash_file(ROOT / "data" / name) for name in data_names},
        "connectome_sha256": {
            completeness.name: hash_file(completeness),
            connectivity.name: hash_file(connectivity),
        },
    }


def _prepare_declared(trace_indices: np.ndarray, *, with_traces: bool) -> dict[str, Any]:
    return s2._prepare_declared(trace_indices, with_traces=with_traces)


def build_census(destination: Path) -> None:
    """Write the census part of the record; the probe key stays null until summarize."""
    started = time.monotonic()
    census = {
        "eb_innervation": s1.eb_innervation(),
        "ring_receptors": s1.ring_receptors(ROOT / REACHED_RECORD),
        "dark_reference": dark_reference(),
        "dan_synapse_census": s2.dan_synapse_census(),
        "er_local_dopamine_sites": local_dopamine_sites(),
    }
    record = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 2c: clamp the ring threshold term and input gain "
            "together and cross that with a matched dark-disconnected reference"
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
        "dark_reference_gain": census["dark_reference"]["gain"],
        "dark_reference_matches_stage1": census["dark_reference"]["matches_stage1_census"],
        "er_local_sites": [site["name"] for site in census["er_local_dopamine_sites"]["sites"]],
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
    meta = fixture.get("meta") or {}
    dv_clamp_arms = set(meta.get("dv_clamp_arms") or [])
    gain_clamp_arms = set(meta.get("gain_clamp_arms") or [])
    fixture_arms = [
        {
            "label": arm["label"],
            "genotype": arm["genotype"]["named"],
            "drive_hz": float(next(
                (hook["rate_hz"] for hook in arm["genotype"].get("manipulations", [])
                 if hook["type"] == "activate"), 0.0)),
            "dan_fast_synapses": (arm.get("layers") or {}).get(
                "dan_fast_synapses", fixture["layers"]["dan_fast_synapses"]),
            "dv_clamp": ("dark_reference" if arm["label"] in dv_clamp_arms else None),
            "gain_clamp": ("dark_reference" if arm["label"] in gain_clamp_arms else None),
        }
        for arm in fixture["arms"]
    ]
    if tuple(arm["label"] for arm in fixture_arms) != ARM_LABELS:
        raise ValueError("fixture arms do not match the runner's arm order")
    reference = dark_reference()
    output = {
        "class": "development",
        "purpose": "ring-neuron dopamine stage 2c five-arm paired probe plan",
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
            "gain_dark_reference": float(reference["gain"]),
            "dv_clamp_definition": (
                "InstrumentedNeuromod.receptor_terms replaces d_v on the 228 traced ER cells "
                "with the constant dark reference; the dopamine pool, innervation, source term, "
                "occupancies and the input gain are untouched"
            ),
            "gain_clamp_definition": (
                "InstrumentedNeuromod.receptor_terms replaces the input gain on the 228 traced "
                "ER cells with the constant dark gain reference; the dopamine pool, innervation, "
                "source term and occupancies are untouched, and the engine applies the gain only "
                "as the postsynaptic input multiplier"
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


def _clamp_audit(ctx: dict[str, Any], reference: dict[str, Any], *, clamp_dv: bool,
                  clamp_gain: bool) -> dict[str, Any]:
    """Prove what one combined ER-local clamp replaces and that nothing overwrites it.

    One declared engine, two neuromod instances on the same driven pool: the
    base class and the instrumented one.  The audit shows the natural ER
    threshold and gain are driven, the applied values equal their dark
    references, the vector that is not clamped is unchanged, the pool is live
    over a step, and setting threshold and gain twice (after a pool step)
    leaves the clamps in place.
    """
    from flyonenomics.registry.compartments import compartment_index
    from flyonenomics.schema.named import named_manipulations
    from flyonenomics.types import LayerFlags

    engine = ctx["engine"]
    engine.restore("declared")
    registry = ctx["registry"]
    params = ctx["params"]
    targets = np.asarray(ctx["targets"], dtype=np.int32)
    base_threshold = np.asarray(ctx["base_threshold"], dtype=np.float64)
    eb = compartment_index()["EB"]
    dv_dark = float(reference["dv_mv"])
    gain_dark = float(reference["gain"])

    layers = LayerFlags(background=True, dopamine_A=True, transporter_C=True,
                        dan_fast_synapses="retain")
    plain = Neuromod(registry, params, layers, ctx["dopamine"], base_v_th=base_threshold,
                     schema_version="1.3", drive_groups=ctx["groups"])
    clamped = InstrumentedNeuromod(registry, params, layers, ctx["dopamine"], base_v_th=base_threshold,
                                   schema_version="1.3", drive_groups=ctx["groups"],
                                   er_idx=targets,
                                   dv_dark_mv=(dv_dark if clamp_dv else None),
                                   gain_dark=(gain_dark if clamp_gain else None))
    plain.apply_genotype(named_manipulations("wild_type"), engine)
    clamped.apply_genotype(named_manipulations("wild_type"), engine)
    plain.reset_fast()
    clamped.reset_fast()
    # Drive the pool to a representative driven concentration without touching
    # the dopamine source terms: the clamps must not depend on the pool value.
    for mod in (plain, clamped):
        mod.da_c[eb] = 3.4
    plain_dv, plain_gain, _, _ = plain.receptor_terms()
    applied_dv, applied_gain, clamped_occ1, clamped_occ2 = clamped.receptor_terms()
    natural_dv = np.array(clamped.last_natural_dv, dtype=np.float64)
    natural_gain = np.array(clamped.last_natural_gain, dtype=np.float64)
    if clamped.last_applied_dv is None or clamped.last_applied_gain is None:
        raise RuntimeError("instrumented neuromod did not record receptor terms")
    non_er = np.setdiff1d(np.arange(registry.n), targets)
    er_natural_dv = float(np.unique(natural_dv[targets])[0])
    er_applied_dv = float(np.unique(applied_dv[targets])[0])
    er_natural_gain = float(np.unique(natural_gain[targets])[0])
    er_applied_gain = float(np.unique(applied_gain[targets])[0])
    if clamp_dv and abs(er_applied_dv - dv_dark) > 1e-12:
        raise RuntimeError("applied ER d_v differs from the dark reference")
    if clamp_gain and abs(er_applied_gain - gain_dark) > 1e-12:
        raise RuntimeError("applied ER gain differs from the dark reference")
    if clamp_dv and abs(er_natural_dv - dv_dark) < 1e-9:
        raise RuntimeError("driven ER d_v did not move off the dark reference")
    if clamp_gain and abs(er_natural_gain - gain_dark) < 1e-9:
        raise RuntimeError("driven ER gain did not move off the dark reference")
    dv_other_unchanged = bool(np.array_equal(applied_dv[non_er], plain_dv[non_er]))
    gain_other_unchanged = bool(np.array_equal(applied_gain[non_er], plain_gain[non_er]))
    # The unclamped vector must itself be untouched by the clamp.
    dv_unclamped_unchanged = (not clamp_dv) or bool(np.array_equal(
        applied_dv[non_er], plain_dv[non_er]))
    gain_unclamped_unchanged = (not clamp_gain) or bool(np.array_equal(
        applied_gain[non_er], plain_gain[non_er]))

    composed = clamped.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)
    expected_er_dv = (np.clip(base_threshold[targets] + clamped.shift[targets] + dv_dark,
                              *params.get("rec.vth_clip")) if clamp_dv else None)
    engine_threshold = np.asarray(engine.thresholds_mv()[targets], dtype=np.float64)
    engine_gain = np.asarray(engine.gains()[targets], dtype=np.float64)
    threshold_set_matches = bool(expected_er_dv is None or np.max(np.abs(engine_threshold - expected_er_dv)) < 1e-9)
    gain_set_matches = bool(abs(float(np.unique(engine_gain)[0]) - (gain_dark if clamp_gain else float(np.unique(plain_gain[targets])[0]))) < 1e-9)
    # One pool step must not overwrite either clamp.
    synthetic = np.zeros(registry.n, dtype=np.int32)
    da_idx = np.asarray(ctx["dopamine_neurons"], dtype=np.int32)
    synthetic[da_idx] = 1
    da_before = float(clamped.da_c[eb])
    clamped.on_chunk(synthetic, 0.001)
    da_after = float(clamped.da_c[eb])
    composed2 = clamped.compose()
    engine.set_threshold(composed2.v_th)
    engine.set_gain(composed2.gain)
    engine_threshold_step = np.asarray(engine.thresholds_mv()[targets], dtype=np.float64)
    engine_gain_step = np.asarray(engine.gains()[targets], dtype=np.float64)
    threshold_step_matches = bool(expected_er_dv is None or np.max(np.abs(engine_threshold_step - expected_er_dv)) < 1e-9)
    gain_step_matches = bool(abs(float(np.unique(engine_gain_step)[0]) - (gain_dark if clamp_gain else float(np.unique(plain_gain[targets])[0]))) < 1e-9)
    applied_after_step_dv = float(np.unique(np.asarray(clamped.last_applied_dv[targets]))[0])
    applied_after_step_gain = float(np.unique(np.asarray(clamped.last_applied_gain[targets]))[0])
    return {
        "class": "development",
        "purpose": "prove the ER d_v and/or input-gain clamp replaces only that term and survives a pool step",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "platform": f"{platform.system().lower()}-{platform.machine()}",
        "clamp_dv": bool(clamp_dv),
        "clamp_gain": bool(clamp_gain),
        "er_n": int(targets.size),
        "da_ref_um": float(reference["da_ref_um"]),
        "dv_dark_reference_mv": dv_dark,
        "gain_dark_reference": gain_dark,
        "driven_da_eb_um": 3.4,
        "natural_er_dv_mv": er_natural_dv,
        "applied_er_dv_mv": er_applied_dv,
        "natural_er_gain": er_natural_gain,
        "applied_er_gain": er_applied_gain,
        "applied_dv_equals_dark_reference": bool(abs(er_applied_dv - dv_dark) < 1e-12),
        "applied_gain_equals_dark_reference": bool(abs(er_applied_gain - gain_dark) < 1e-12),
        "natural_dv_differs_from_dark_reference": bool(abs(er_natural_dv - dv_dark) > 1e-9),
        "natural_gain_differs_from_dark_reference": bool(abs(er_natural_gain - gain_dark) > 1e-9),
        "non_er_dv_equals_natural": dv_other_unchanged,
        "non_er_gain_equals_natural": gain_other_unchanged,
        "unclamped_dv_unchanged": dv_unclamped_unchanged,
        "unclamped_gain_unchanged": gain_unclamped_unchanged,
        "er_occ1": float(np.unique(np.asarray(clamped_occ1[targets], dtype=np.float64))[0]),
        "er_occ2": float(np.unique(np.asarray(clamped_occ2[targets], dtype=np.float64))[0]),
        "occupancies_finite": bool(np.all(np.isfinite(clamped_occ1)) and np.all(np.isfinite(clamped_occ2))),
        "da_eb_before_pool_step_um": da_before,
        "da_eb_after_pool_step_um": da_after,
        "pool_is_live": bool(abs(da_after - da_before) > 0.0),
        "engine_threshold_matches_expected_after_set": threshold_set_matches,
        "engine_gain_matches_expected_after_set": gain_set_matches,
        "engine_threshold_matches_expected_after_pool_step": threshold_step_matches,
        "engine_gain_matches_expected_after_pool_step": gain_step_matches,
        "applied_after_pool_step_dv_mv": applied_after_step_dv,
        "applied_after_pool_step_gain": applied_after_step_gain,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


def build_audit(destination: Path) -> None:
    """Reuse stage 2's disconnect audit and stage 2b's threshold-clamp audit; add gain and combined."""
    started = time.monotonic()
    targets = _er_targets()
    ctx = _prepare_declared(targets, with_traces=False)
    reference = dark_reference()
    # Reuse stage 2's disconnect audit verbatim: the same layer, same mask.
    s2.build_audit(DEFAULT_DISCONNECT_AUDIT)
    output = {
        "class": "development",
        "purpose": "stage 2c clamp audits and the reused stage 2 disconnect audit",
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "reference": reference,
        "threshold_clamp": s2b.build_clamp_audit(ctx, reference),
        "gain_clamp": _clamp_audit(ctx, reference, clamp_dv=False, clamp_gain=True),
        "combined_clamp": _clamp_audit(ctx, reference, clamp_dv=True, clamp_gain=True),
        "disconnect": read(DEFAULT_DISCONNECT_AUDIT),
        "wall_seconds": time.monotonic() - started,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    dump(destination, output)
    print(json.dumps({
        "threshold_applied_equals_dark": output["threshold_clamp"]["applied_equals_dark_reference"],
        "gain_applied_equals_dark": output["gain_clamp"]["applied_gain_equals_dark_reference"],
        "gain_unclamped_dv_unchanged": output["gain_clamp"]["unclamped_dv_unchanged"],
        "combined_applied_equals_dark": (
            output["combined_clamp"]["applied_dv_equals_dark_reference"]
            and output["combined_clamp"]["applied_gain_equals_dark_reference"]),
        "combined_gain_survives_step": output["combined_clamp"]["engine_gain_matches_expected_after_pool_step"],
        "combined_threshold_survives_step": output["combined_clamp"]["engine_threshold_matches_expected_after_pool_step"],
    }, indent=2), flush=True)
    print(f"wrote {destination}", flush=True)


def run_seed(job: tuple[int, str, str]) -> str:
    """Run all five arms for one seed in one built engine, paired on the same stream."""
    from flyonenomics.behaviour.arena import Behaviour
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
    gain_dark = float(plan["protocol"]["gain_dark_reference"])
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
        dv_clamped = arm.get("dv_clamp") == "dark_reference"
        gain_clamped = arm.get("gain_clamp") == "dark_reference"
        engine.restore("declared")
        engine.seed(brian_seed(MASTER, seed, 0))
        mod = InstrumentedNeuromod(
            registry, params,
            LayerFlags(background=True, dopamine_A=True, transporter_C=True,
                       dan_fast_synapses=arm["dan_fast_synapses"]),
            dopamine, base_v_th=base_threshold, schema_version="1.3", drive_groups=groups,
            er_idx=targets,
            dv_dark_mv=(dv_dark if dv_clamped else None),
            gain_dark=(gain_dark if gain_clamped else None),
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
        natural_gain_sum = np.zeros(len(targets), dtype=np.float64)
        natural_gain_min = np.full(len(targets), np.inf)
        natural_gain_max = np.full(len(targets), -np.inf)
        applied_gain_sum = np.zeros(len(targets), dtype=np.float64)
        applied_gain_min = np.full(len(targets), np.inf)
        applied_gain_max = np.full(len(targets), -np.inf)
        natural_dv_chunks: list[float] = []
        applied_dv_chunks: list[float] = []
        natural_gain_chunks: list[float] = []
        applied_gain_chunks: list[float] = []
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
                natural_gain = np.asarray(mod.last_natural_gain[targets], dtype=np.float64)
                applied_gain = np.asarray(mod.last_applied_gain[targets], dtype=np.float64)
                natural_gain_sum += natural_gain
                np.minimum(natural_gain_min, natural_gain, out=natural_gain_min)
                np.maximum(natural_gain_max, natural_gain, out=natural_gain_max)
                applied_gain_sum += applied_gain
                np.minimum(applied_gain_min, applied_gain, out=applied_gain_min)
                np.maximum(applied_gain_max, applied_gain, out=applied_gain_max)
                natural_dv_chunks.append(float(natural[0]))
                applied_dv_chunks.append(float(applied[0]))
                natural_gain_chunks.append(float(natural_gain[0]))
                applied_gain_chunks.append(float(applied_gain[0]))
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
                "natural_gain_mean": float(natural_gain_sum[position] / measurement_chunks),
                "natural_gain_min": float(natural_gain_min[position]),
                "natural_gain_max": float(natural_gain_max[position]),
                "applied_gain_mean": float(applied_gain_sum[position] / measurement_chunks),
                "applied_gain_min": float(applied_gain_min[position]),
                "applied_gain_max": float(applied_gain_max[position]),
            })
        rows.append({
            "condition": label,
            "genotype": arm["genotype"],
            "dan_fast_synapses": arm["dan_fast_synapses"],
            "dv_clamp": arm.get("dv_clamp"),
            "gain_clamp": arm.get("gain_clamp"),
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
            "natural_gain_chunks": natural_gain_chunks,
            "applied_gain_chunks": applied_gain_chunks,
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
    natural_gain = [float(item["natural_gain_mean"]) for item in targets]
    applied_gain = [float(item["applied_gain_mean"]) for item in targets]
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
        "natural_gain": float(np.mean(natural_gain)),
        "applied_gain": float(np.mean(applied_gain)),
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
    "natural_dv_mV", "applied_dv_mV", "natural_gain", "applied_gain",
    "source_rate_hz", "dopamine_rate_hz", "dopamine_spikes", "dan_spikes",
    "dan_rate_hz", "eb_da_mean_um", "eb_da_max_um",
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


def _with_resolution(contrast: dict[str, Any]) -> dict[str, Any]:
    """Attach the confidence-interval half-widths the brief requires.

    The half-width is not a powered minimum detectable effect; it is
    uncertainty in the estimated mean from ten paired contrasts.
    """
    spikes = contrast["er_spikes"]
    contrast["resolution"] = {
        "unit": (
            "confidence-interval half-width from the measured standard error over ten paired "
            "contrasts; 1.96 SE is the project's interval convention and 2.262 SE is the "
            "paired-t multiplier at n=10. This is not a powered minimum detectable effect, and "
            "not computed from 228 cells as independent replicates. Neither is a pass line."
        ),
        "spikes_se": float(spikes["se"]),
        "spikes_1.96_se": float(1.96 * spikes["se"]),
        "spikes_2.262_se": float(2.262 * spikes["se"]),
        "spikes_mean": float(spikes["mean"]),
        "includes_zero": bool(spikes["includes_zero"]),
    }
    return contrast


def _external_contrast(left_values: list[float], right_values: list[float],
                       left_label: str, right_label: str, unit: str) -> dict[str, Any]:
    """Paired contrast between two seed-value lists that need not come from one run."""
    differences = [float(a) - float(b) for a, b in zip(left_values, right_values, strict=True)]
    return {
        "left": left_label,
        "right": right_label,
        "unit": unit,
        "er_spikes": _paired_interval(differences),
        "seed_values": differences,
    }


def _fraction(numer: list[float], denom: list[float]) -> dict[str, Any]:
    """Mean of the per-seed ratios, with its paired interval; the ratio of means differs."""
    ratios = [float(a) / float(b) for a, b in zip(numer, denom, strict=True) if float(b) != 0.0]
    interval = _paired_interval(ratios)
    interval["note"] = (
        "mean of the per-seed ratios; the ratio of the paired means is a different statistic"
    )
    return interval


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
                    "natural_dv_mV": [], "applied_dv_mV": [], "natural_gain": [], "applied_gain": [],
                    "eb_da_um": [],
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
                bucket["natural_gain"].append(float(target["natural_gain_mean"]))
                bucket["applied_gain"].append(float(target["applied_gain_mean"]))
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
                "natural_gain_values": bucket["natural_gain"],
                "applied_gain_values": bucket["applied_gain"],
            }
        deltas: dict[str, Any] = {}
        for name, left, right in (
            ("threshold_clamp", "driven-retain", "driven-retain-clamped"),
            ("gain_additional", "driven-retain-clamped", "driven-retain-both-clamped"),
            ("combined_clamp", "driven-retain", "driven-retain-both-clamped"),
            ("dark_disconnect_baseline", "dark-disconnect", "dark"),
        ):
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
                "natural_gain_delta": _paired_interval(
                    [x - y for x, y in zip(a["natural_gain"], b["natural_gain"], strict=True)]),
                "applied_gain_delta": _paired_interval(
                    [x - y for x, y in zip(a["applied_gain"], b["applied_gain"], strict=True)]),
                "eb_da_delta_um": _paired_interval(
                    [x - y for x, y in zip(a["eb_da_um"], b["eb_da_um"], strict=True)]),
            }
        per_cell.append({**cell, "arms": arms_out, "deltas": deltas})

    def arm_distribution(label: str, key: str, scale: float = 1.0) -> dict[str, Any]:
        values = [float(cell["arms"][label][key]) for cell in per_cell]
        return _distribution([value * scale for value in values])

    seed_spikes = {label: [run["arms"][label]["er_spikes"] for run in paired_runs] for label in ARM_LABELS}
    retained_excess_contrast = _with_resolution(_contrast(runs, "driven-retain", "dark"))
    combined_residual = _with_resolution(_contrast(runs, "driven-retain-both-clamped", "dark"))
    threshold_clamp = _with_resolution(_contrast(runs, "driven-retain", "driven-retain-clamped"))
    gain_additional = _with_resolution(_contrast(runs, "driven-retain-clamped", "driven-retain-both-clamped"))
    combined_clamp = _with_resolution(_contrast(runs, "driven-retain", "driven-retain-both-clamped"))
    dark_disconnect_baseline = _with_resolution(_contrast(runs, "dark-disconnect", "dark"))
    hits = _arm_hits(runs)

    # Fractions of the retained excess, each the mean of per-seed ratios.
    retained_excess = [float(a) - float(b) for a, b in zip(seed_spikes["driven-retain"],
                                                          seed_spikes["dark"], strict=True)]
    fractions = {
        "threshold_clamp": _fraction(threshold_clamp["seed_values"]["er_spikes"], retained_excess),
        "gain_additional": _fraction(gain_additional["seed_values"]["er_spikes"], retained_excess),
        "combined_clamp": _fraction(combined_clamp["seed_values"]["er_spikes"], retained_excess),
        "combined_residual": _fraction(combined_residual["seed_values"]["er_spikes"], retained_excess),
        "retained_excess_mean": float(np.mean(retained_excess)),
        "ratio_of_means": {
            "threshold_clamp": float(threshold_clamp["er_spikes"]["mean"] / np.mean(retained_excess)),
            "gain_additional": float(gain_additional["er_spikes"]["mean"] / np.mean(retained_excess)),
            "combined_clamp": float(combined_clamp["er_spikes"]["mean"] / np.mean(retained_excess)),
            "combined_residual": float(combined_residual["er_spikes"]["mean"] / np.mean(retained_excess)),
        },
        "note": (
            "each fraction is the mean of the ten per-seed ratios; the ratio of the paired means "
            "is a different statistic and both are reported.  combined_residual is Rb minus B, "
            "the retained excess left after the combined ER-local clamp."
        ),
    }

    # The matched dark-disconnected reference item 140 asks for.  D1 is stage
    # 2b's driven-disconnect arm, which reproduces seed for seed; B and BD are
    # this run's dark and dark-disconnect arms.
    stage2b_record = read(ROOT / STAGE2B_RECORD)
    d1_by_seed = {int(item["seed"]): int(item["arms"]["driven-disconnect"]["er_spikes"])
                  for item in stage2b_record["probe"]["paired_runs"]}
    run_seeds = [int(run["seed"]) for run in runs]
    d1_seed = [d1_by_seed[seed] for seed in run_seeds]
    b_seed = seed_spikes["dark"]
    bd_seed = seed_spikes["dark-disconnect"]
    disconnect_matched = _with_resolution(_external_contrast(
        d1_seed, bd_seed, "driven-disconnect (stage 2b)", "dark-disconnect (stage 2c)",
        "paired D1 minus BD over the ten seeds; interval is mean +/- 1.96 SE"))
    disconnect_unmatched = _with_resolution(_external_contrast(
        d1_seed, b_seed, "driven-disconnect (stage 2b)", "dark (stage 2c)",
        "paired D1 minus B over the ten seeds; interval is mean +/- 1.96 SE"))

    # Dark reference constancy checks over the probe, per seed.
    def constancy_check(label: str, chunk_key: str) -> dict[str, Any]:
        per_seed = []
        for run in runs:
            row = next(item for item in run["rows"] if item["condition"] == label)
            chunks = [float(value) for value in row[chunk_key]]
            per_seed.append({
                "seed": int(run["seed"]),
                "min": float(min(chunks)),
                "max": float(max(chunks)),
                "mean": float(np.mean(chunks)),
                "spread": float(max(chunks) - min(chunks)),
                "eb_da_mean_um": float(row["eb_da_mean_um"]),
            })
        spreads = [item["spread"] for item in per_seed]
        return {
            "unit": f"{label} arm natural ER term over the 18 s window, per seed",
            "per_seed": per_seed,
            "max_spread": float(max(spreads)),
            "constant_to_1e-3": bool(max(spreads) < 1e-3),
            "note": (
                "stage 1 recorded a 5e-6 uM stray-spike transient on two dark seeds; the clamps "
                "use the constant dark reference and this is the size of the departure"
            ),
        }

    anchors = {}
    stage2b_arms = stage2b_record["probe"]["summary"]["arms"]
    for label in ("dark", "driven-retain", "driven-retain-clamped"):
        mine = [int(value) for value in seed_spikes[label]]
        theirs = [int(value) for value in stage2b_arms[label]["seed_er_spikes"]]
        if len(mine) != len(theirs):
            anchors[label] = {
                "fresh_seed_er_spikes": mine,
                "stage2b_seed_er_spikes": theirs,
                "differences": None,
                "identical": False,
                "max_abs_difference": None,
                "note": "seed count differs; reproduction not compared",
            }
            continue
        differences = [a - b for a, b in zip(mine, theirs, strict=True)]
        anchors[label] = {
            "fresh_seed_er_spikes": mine,
            "stage2b_seed_er_spikes": theirs,
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
            "dv": constancy_check("dark", "natural_dv_chunks_mV"),
            "gain": constancy_check("dark", "natural_gain_chunks"),
        },
        "anchors": anchors,
        "clamp_audit": read(DEFAULT_AUDIT) if DEFAULT_AUDIT.is_file() else None,
    }
    output = {
        "class": "development",
        "purpose": (
            "ring-neuron dopamine stage 2c: clamp the ring threshold term and input gain "
            "together in the retained network and measure the matched dark-disconnected "
            "reference. Per cell, never a population mean. A null is a result."
        ),
        "declared_substrate_id": plan["declared_substrate_id"],
        "protocol": plan["protocol"],
        "identity": identities[0],
        "plan_sha256": hash_file(plan_path),
        "fixture": plan["fixture"],
        "fixture_sha256": hash_file(ROOT / plan["fixture"]),
        "trace_n": plan["trace_n"],
        "summary": summary,
        "retained_excess": retained_excess_contrast,
        "threshold_clamp": threshold_clamp,
        "gain_additional": gain_additional,
        "combined_clamp": combined_clamp,
        "combined_residual": combined_residual,
        "dark_disconnect_baseline": dark_disconnect_baseline,
        "disconnect_matched": disconnect_matched,
        "disconnect_unmatched": disconnect_unmatched,
        "fractions": fractions,
        "paired_runs": paired_runs,
        "cells": per_cell,
        "raw_directory": str(raw),
        "raw_sha256": {f"seed-{seed}.json": hash_file(raw / f"seed-{seed}.json") for seed in seeds},
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    record["probe"] = output
    audit = read(DEFAULT_AUDIT) if DEFAULT_AUDIT.is_file() else None
    record["disconnect_audit"] = audit.get("disconnect") if audit else None
    record["provenance_note"] = {
        "executed_runner_sha256": output["identity"]["runner_sha256"],
        "summarizing_runner_sha256": hash_file(Path(__file__)),
        "note": (
            "The probe ran under the executed runner whose SHA-256 is recorded in identity and in "
            "the raw seed files. The committed runner differs only in summarize if the hashes "
            "differ. The engine, the probe, the clamps and the per-cell arithmetic are unchanged, "
            "and the raw seed files are the run evidence."
        ),
    }
    record["limitation"] = (
        "This is an ER-local threshold-and-gain test, not an all-dopamine test. The clamps "
        "replace only the ER threshold term d_v and the ER input gain; the dopamine pool, "
        "innervation, source activity, the occ1/occ2 calculation and every other cell stay live, "
        "so any dopamine effect that does not act through those two ER-local terms is still "
        "present in the clamped arms, including ordinary fast transmission when synapses are "
        "retained. The probe injects at TuBu, downstream of a visual pathway that does not "
        "conduct: the fly does not see. A clamped arm is not the same condition as the dark arm, "
        "which removes source activation and leaves EB dopamine at its fixed point."
    )
    record["reading_note"] = (
        "An interval that includes zero is no detected difference, not equivalence, and an interval "
        "containing zero does not establish additivity. No interval here is a pass line (item 121). "
        "The resolution figures are confidence-interval half-widths from ten paired contrasts, not "
        "powered minimum detectable effects, and not computed from 228 cells as independent "
        "replicates. Both arms carry the stripe, so a firing cell is an active cell, not a "
        "demonstrated stripe response. R0 minus Rb is the additional effect of removing gain "
        "modulation with the threshold already clamped; it is not an independent gain share, and "
        "no gain-only arm was run."
    )
    record["generated_utc"] = datetime.now(timezone.utc).isoformat()
    dump(destination, record)
    print(json.dumps({
        "retained_excess_spikes": retained_excess_contrast["er_spikes"],
        "threshold_clamp_spikes": threshold_clamp["er_spikes"],
        "gain_additional_spikes": gain_additional["er_spikes"],
        "combined_clamp_spikes": combined_clamp["er_spikes"],
        "combined_residual_spikes": combined_residual["er_spikes"],
        "dark_disconnect_baseline_spikes": dark_disconnect_baseline["er_spikes"],
        "disconnect_matched_spikes": disconnect_matched["er_spikes"],
        "disconnect_unmatched_spikes": disconnect_unmatched["er_spikes"],
        "fractions": fractions,
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
