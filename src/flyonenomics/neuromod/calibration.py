"""Bare-substrate K2 measurement and free-pool qualification helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml
import datetime as dt
import json
import time
import subprocess
import sys
from numpy.typing import NDArray

from flyonenomics.io import read_yaml
from flyonenomics.neuromod.pools import innervated_mask, tonic_source
from flyonenomics.types import LayerFlags, Params, load_params

REPO = Path(__file__).resolve().parents[3]
# SPEC item 48 / test 3.1: three independent seeds, 2 s settle and 5 s measure.
K2_SEEDS = (1, 2, 3)
K2_MASTER_SEED = 20260912
K2_SETTLE_S = 2.0
K2_MEASURE_S = 5.0
# SPEC 7.2 tests 3.1b, 1.4, 2.2; item 48 keeps this order on bare substrate.
Q_3_1B_MEASURE_S = 10.0
Q_REFLEX_MEASURE_S = 1.0
Q_2_2_MEASURE_S = 10.0
Q_2_2_SEED = 0
Q_REFLEX_MEAN_MIN_HZ = 50.0
Q_REFLEX_SEED_FLOOR_HZ = 40.0
Q_2_2_MEDIAN_MAX_HZ = 5.0
Q_2_2_HIGH_RATE_HZ = 50.0
Q_2_2_HIGH_FRACTION_MAX = 0.01
# SPEC 7.2 test 3.1b: compartment window-mean DA must be within 20% of DA_ref.
Q_DA_REL_BOUND = 0.20


def _plain(value: Any) -> Any:
    """Convert NumPy scalar keys/values to native YAML/JSON types; units and shapes unchanged."""
    if isinstance(value, dict):
        return {_plain(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, np.ndarray):
        return _plain(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def release_constants(rates_hz: NDArray[np.float64], params: Params) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Map tonic weighted DAN rates (n_comp,) Hz to alpha (n_comp,) µM/spike and under-innervation flags."""
    rates = np.asarray(rates_hz, dtype=np.float64)
    low = rates < params.get("da.R_min")
    balance = params.get("da.DA_ref") * (params.get("da.Vmax") / (params.get("da.Km") + params.get("da.DA_ref")) + params.get("da.k_ns"))
    alpha = np.full_like(rates, float(params.get("da.alpha_max")))
    alpha[~low] = balance / rates[~low]
    return alpha, low


def modulation_discrepancy(mean_da_c: NDArray[np.float64], mean_dv: NDArray[np.float64],
                           mean_gain: NDArray[np.float64], tonic_dv: NDArray[np.float64],
                           tonic_gain: NDArray[np.float64], innervated: NDArray[np.bool_],
                           exposed: NDArray[np.bool_], params: Params) -> dict[str, Any]:
    """Compare 3.1b window means: DA (n_comp,) µM, dV/gain (n,) mV/dimensionless."""
    da_delta = np.abs(mean_da_c[innervated] - params.get("da.DA_ref"))
    da_bound = params.get("da.DA_ref") * Q_DA_REL_BOUND
    dv_delta = np.abs(mean_dv[exposed] - tonic_dv[exposed])
    dv_bound = np.maximum(params.get("qual.tol_rel_mod") * np.abs(tonic_dv[exposed]), params.get("qual.tol_abs_dV"))
    gain_delta = np.abs(mean_gain[exposed] - tonic_gain[exposed])
    gain_bound = np.maximum(params.get("qual.tol_rel_mod") * np.abs(tonic_gain[exposed] - 1), params.get("qual.tol_abs_g"))
    return {"passed": bool(np.all(da_delta <= da_bound) and np.all(dv_delta <= dv_bound) and np.all(gain_delta <= gain_bound)),
            "max_da_error_um": float(np.max(da_delta, initial=0)), "da_bound_um": float(da_bound),
            "max_dv_excess_mv": float(np.max(dv_delta - dv_bound, initial=0)),
            "max_gain_excess": float(np.max(gain_delta - gain_bound, initial=0))}


def bitwise_equal(left: NDArray[np.float64], right: NDArray[np.float64]) -> bool:
    """Compare float64 arrays bit for bit, including signed zero; arrays share one shape and units."""
    a, b = np.asarray(left, dtype=np.float64), np.asarray(right, dtype=np.float64)
    return a.shape == b.shape and bool(np.array_equal(a.view(np.uint64), b.view(np.uint64)))


@dataclass
class ChunkQualification:
    """Streaming 3.1b evidence; DA (n_comp,) µM, modulation (n,) mV/dimensionless."""
    n_comp: int
    n_neuron: int
    chunks: int = 0
    arrays_exact: bool = True
    da_sum: NDArray[np.float64] = field(init=False)
    dv_sum: NDArray[np.float64] = field(init=False)
    gain_sum: NDArray[np.float64] = field(init=False)

    def __post_init__(self) -> None:
        """Allocate streaming sums; DA (n_comp,) µM, modulation (n,) mV/dimensionless."""
        self.da_sum = np.zeros(self.n_comp)
        self.dv_sum = np.zeros(self.n_neuron)
        self.gain_sum = np.zeros(self.n_neuron)

    def observe(self, mod: Any, engine_threshold: NDArray[np.float64], engine_gain: NDArray[np.float64]) -> None:
        """Compare one chunk's engine arrays with its own DA composition; shapes (n,) and (n_comp,)."""
        composed = mod.compose()
        self.arrays_exact &= bitwise_equal(engine_threshold, composed.v_th) and bitwise_equal(engine_gain, composed.gain)
        dv, gain, _, _ = mod.receptor_terms()
        self.da_sum += mod.da_c
        self.dv_sum += dv
        self.gain_sum += gain
        self.chunks += 1

    def summary(self, mod: Any) -> dict[str, Any]:
        """Return Q's chunkwise and window-mean checks; µM/mV/dimensionless scalar diagnostics."""
        if self.chunks == 0:
            raise ValueError("3.1b requires at least one recorded chunk")
        current = mod.da_c.copy()
        try:
            mod.da_c.fill(mod.da_ref)
            tonic_dv, tonic_gain, _, _ = mod.receptor_terms()
        finally:
            mod.da_c = current
        discrepancy = modulation_discrepancy(self.da_sum / self.chunks, self.dv_sum / self.chunks,
                                              self.gain_sum / self.chunks, tonic_dv, tonic_gain,
                                              mod.mask, mod.exposed, mod.params)
        exposed_idx = np.flatnonzero(mod.exposed)
        dv_error = np.abs(self.dv_sum[exposed_idx] / self.chunks - tonic_dv[exposed_idx])
        dv_bound = np.maximum(mod.params.get("qual.tol_rel_mod") * np.abs(tonic_dv[exposed_idx]),
                              mod.params.get("qual.tol_abs_dV"))
        gain_error = np.abs(self.gain_sum[exposed_idx] / self.chunks - tonic_gain[exposed_idx])
        gain_bound = np.maximum(mod.params.get("qual.tol_rel_mod") * np.abs(tonic_gain[exposed_idx] - 1),
                                mod.params.get("qual.tol_abs_g"))
        def worst(error: NDArray[np.float64], bound: NDArray[np.float64]) -> dict[str, float | int] | None:
            """Return the largest per-neuron excess and its own bound; units inherited from input."""
            if not error.size:
                return None
            position = int(np.argmax(error - bound))
            return {"neuron_idx": int(exposed_idx[position]), "absolute_error": float(error[position]),
                    "bound": float(bound[position])}
        return {**discrepancy, "passed": self.arrays_exact and discrepancy["passed"], "chunks": self.chunks,
                "per_chunk_arrays_bitwise": self.arrays_exact,
                "mean_da_c_um": (self.da_sum / self.chunks).tolist(),
                "per_neuron_dv_mv": {"n_exceeded": int(np.count_nonzero(dv_error > dv_bound)),
                                     "worst": worst(dv_error, dv_bound)},
                "per_neuron_gain": {"n_exceeded": int(np.count_nonzero(gain_error > gain_bound)),
                                    "worst": worst(gain_error, gain_bound)}}


def run_k1() -> dict[str, Any]:
    """Record item-47 bare-substrate K1 omission; no rates or arrays."""
    return {"status": "skipped", "reason": "item 47: no frozen drive on the bare substrate"}


def measure_k2() -> dict[str, Any]:
    """Measure bare-substrate DAN rates; R (n_comp,) weighted spikes/s, source µM/s."""
    from flyonenomics.engine.base import InputTopology
    from flyonenomics.engine.brian_engine import BrianEngine
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.registry import build_registry

    destination = REPO / "data/dopamine-v0.1.yaml"
    params = load_params()
    registry = build_registry("783")
    mask = innervated_mask(registry.innervation())
    names = [comp.name for comp in registry.compartments()]
    engine = BrianEngine()
    engine.seed(brian_seed(K2_MASTER_SEED, K2_SEEDS[0], 0))
    engine.build(connectome_files("783"), params, InputTopology(background=False))
    chunk_ms = int(params.get("engine.chunk_ms"))
    settle_chunks = round(K2_SETTLE_S * 1000 / chunk_ms)
    measure_chunks = round(K2_MEASURE_S * 1000 / chunk_ms)
    if settle_chunks * chunk_ms != K2_SETTLE_S * 1000 or measure_chunks * chunk_ms != K2_MEASURE_S * 1000:
        raise ValueError("K2 windows must divide into engine chunks")
    per_seed: dict[int, list[float]] = {}
    for seed in K2_SEEDS:
        engine.restore("initial")
        engine.seed(brian_seed(K2_MASTER_SEED, seed, 0))
        mod = Neuromod(registry, params, LayerFlags(background=False))
        mod.clamp_pools(True)
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        engine.compose_refractory()
        for _ in range(settle_chunks):
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_ms / 1000)
        weighted_counts = np.zeros(len(mask), dtype=np.float64)
        for _ in range(measure_chunks):
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_ms / 1000)
            weighted_counts += np.asarray(registry.innervation() @ result.counts).ravel()
        per_seed[seed] = (weighted_counts / K2_MEASURE_S).tolist()
    rates = np.mean(np.asarray(list(per_seed.values()), dtype=np.float64), axis=0)
    alpha, low = release_constants(rates, params)
    source = tonic_source(float(params.get("da.DA_ref")),
                          np.full(len(mask), float(params.get("da.Vmax"))),
                          np.full(len(mask), float(params.get("da.Km"))),
                          float(params.get("da.k_ns")), mask)
    record: dict[str, Any] = {
        "version": "v0.1", "qualified": False, "status": "K2 measured; Q pending",
        "date": dt.date.today().isoformat(), "params_version": params.version,
        "receptor_map_version": registry.receptors().version, "connectome_version": "783",
        # Item 47 defines the bare (unscaled) substrate; the frozen Params
        # file predates the later development-only lif.g_inh SPEC row.
        "drive_version": None, "background": False, "lif.g_inh": 1.0,
        "calibration_state": "bare substrate, background off, layer A on, transporter C on without drug, pools clamped at DA_ref",
        "K1": run_k1(), "seed_master": K2_MASTER_SEED, "seeds": list(K2_SEEDS),
        "settle_s": K2_SETTLE_S, "measure_s": K2_MEASURE_S,
        "compartments": names, "R_c": rates.tolist(), "per_seed_R_c": per_seed,
        "alpha_c": alpha.tolist(),
        "under_innervated": [name for name, under in zip(names, low, strict=True) if under],
        "da.tonic_source": source.tolist(), "tonic_source_rule": "provisional item 24 / SPEC item 51",
        "qualification": {"status": "pending r5", "required": ["3.1b", "1.4", "2.2"]},
    }
    write_record(destination, record)
    return {"status": "recorded", "path": str(destination), "R_c": record["R_c"],
            "under_innervated": record["under_innervated"], "da.tonic_source": record["da.tonic_source"],
            "qualified": False}


def measure_3_1b(engine: Any, mod: Any, duration_s: float) -> dict[str, Any]:
    """Measure a settled free-pool probe; DA (n_comp,) µM and neuron modulation (n,)."""
    if mod.clamped:
        raise ValueError("3.1b requires free pools")
    chunk_ms = int(mod.params.get("engine.chunk_ms"))
    chunks = round(duration_s * 1000 / chunk_ms)
    if chunks < 1 or chunks * chunk_ms != duration_s * 1000:
        raise ValueError("3.1b duration must be a positive chunk multiple")
    accumulator = ChunkQualification(len(mod.mask), mod.registry.n)
    for _ in range(chunks):
        result = engine.run_chunk(chunk_ms)
        mod.on_chunk(result.counts, chunk_ms / 1000)
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        accumulator.observe(mod, engine.thresholds_mv(), engine.gains())
    return accumulator.summary(mod)


def bare_rate_safety(rates_hz: NDArray[np.float64], settled: bool) -> dict[str, Any]:
    """Apply item-60 stimulated 2.2 bounds; input neuron rates (n,) Hz, output scalars."""
    rates = np.asarray(rates_hz, dtype=np.float64)
    if rates.ndim != 1 or not rates.size or not np.all(np.isfinite(rates)):
        raise ValueError("2.2 requires finite per-neuron rates")
    median = float(np.median(rates))
    high = float(np.mean(rates > Q_2_2_HIGH_RATE_HZ))
    return {"median_hz": median, "median_upper_hz": Q_2_2_MEDIAN_MAX_HZ,
            "median_lower_hz": None, "fraction_above_50_hz": high,
            "fraction_bound": Q_2_2_HIGH_FRACTION_MAX,
            "rule": "SPEC item 60: stimulated sugar reflex, no median floor",
            "passed": bool(median <= Q_2_2_MEDIAN_MAX_HZ and high < Q_2_2_HIGH_FRACTION_MAX and settled)}


def reflex_rule(differences_hz: NDArray[np.float64], params: Params) -> dict[str, Any]:
    """Apply item-61 ten-seed reflex rule; input Hz (n_seed,), output mean/floor Hz."""
    values = np.asarray(differences_hz, dtype=np.float64)
    if values.ndim != 1 or values.size != int(params.get("validation.seeds")) or not np.all(np.isfinite(values)):
        raise ValueError("1.4 requires the configured finite seed vector")
    mean = float(values.mean())
    minimum = float(values.min())
    return {"mean_hz": mean, "minimum_hz": minimum,
            "mean_required_above_hz": Q_REFLEX_MEAN_MIN_HZ,
            "seed_floor_hz": Q_REFLEX_SEED_FLOOR_HZ,
            "rule": "SPEC item 61: ten-seed mean > 50 Hz and every seed >= 40 Hz",
            "passed": bool(mean > Q_REFLEX_MEAN_MIN_HZ and minimum >= Q_REFLEX_SEED_FLOOR_HZ)}


def run_q(*, refresh_3_1b: bool = False) -> dict[str, Any]:
    """Qualify free bare pools in 3.1b, 1.4, 2.2 order; Hz/µM/mV arrays per seed."""
    from flyonenomics.drive.background import group_indices
    from flyonenomics.engine.base import InputTopology
    from flyonenomics.engine.brian_engine import BrianEngine
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.registry import build_registry
    from flyonenomics.validation.artefacts import FanoAccumulator

    destination = REPO / "data/dopamine-v0.1.yaml"
    table: dict[str, Any] = read_yaml(destination)
    if (table.get("qualified") and not refresh_3_1b) or len(table.get("R_c", [])) == 0:
        raise ValueError("Q requires an unqualified, measured bare-substrate K2 record")
    params = load_params()
    registry = build_registry("783")
    sugar = np.sort(registry.population("sugar_GRN_R").idx)
    mn9 = int(registry.population("MN9").idx[0])
    recorded = [registry.population(name) for name in ("DAN", "KC", "DN_all")]
    engine = BrianEngine()
    engine.seed(brian_seed(K2_MASTER_SEED, Q_2_2_SEED, 0))
    engine.build(connectome_files("783"), params, InputTopology(extended_idx=sugar, background=False))
    chunk_ms = int(params.get("engine.chunk_ms"))

    def prepare(seed: int, active: bool) -> tuple[Neuromod, Any]:
        """Restore and settle one free-pool condition; rates Hz (n_sugar,), DA µM (n_comp,)."""
        engine.restore("initial")
        engine.seed(brian_seed(K2_MASTER_SEED, seed, 0))
        mod = Neuromod(registry, params, LayerFlags(background=False), table)
        mod.reset_fast()
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        engine.compose_refractory()
        rates = np.full(len(sugar), float(params.get("input.r_poi")) if active else 0.0)
        stimulus = lambda: engine.set_input_rates(rates)
        settle = mod.settle(engine, stimulus, recorded)
        return mod, settle

    def record(mod: Neuromod, seconds: float, fano: FanoAccumulator | None = None) -> NDArray[np.int64]:
        """Run one held probe; seconds in, neuron spike counts (n,) out."""
        chunks = round(seconds * 1000 / chunk_ms)
        if chunks * chunk_ms != seconds * 1000:
            raise ValueError("Q window must divide into engine chunks")
        counts = np.zeros(engine.n, dtype=np.int64)
        for _ in range(chunks):
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_ms / 1000)
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            counts += result.counts
            if fano is not None:
                fano.add(result.hist_1ms)
        return counts

    started = time.perf_counter()
    checks_3_1b: dict[int, dict[str, Any]] = {}
    for seed in K2_SEEDS:
        mod, settle = prepare(seed, False)
        check = measure_3_1b(engine, mod, Q_3_1B_MEASURE_S)
        checks_3_1b[seed] = {**check, "settle_s": settle.settle_s, "settled": settle.converged}
        print(json.dumps({"stage": "3.1b", "seed": seed, "passed": check["passed"],
                          "settled": settle.converged, "wall_s": round(time.perf_counter() - started, 3)}), flush=True)
    check_3_1b = all(row["passed"] and row["settled"] for row in checks_3_1b.values())
    da_means = np.mean([row["mean_da_c_um"] for row in checks_3_1b.values()], axis=0)
    da_lower = float(params.get("da.DA_ref")) * (1 - Q_DA_REL_BOUND)
    da_upper = float(params.get("da.DA_ref")) * (1 + Q_DA_REL_BOUND)
    da_table = {name: {"mean_um": float(value), "lower_um": da_lower, "upper_um": da_upper,
                       "inside": bool(da_lower <= value <= da_upper)}
                for name, value in zip(table["compartments"], da_means, strict=True)}

    reflex: dict[int, dict[str, Any]] = {}
    safety_counts: NDArray[np.int64] | None = None
    safety_fano: FanoAccumulator | None = None
    safety_settle: Any = None
    for seed in range(int(params.get("validation.seeds"))):
        pair: dict[str, Any] = {}
        for active in (False, True):
            mod, settle = prepare(seed, active)
            combined = active and seed == Q_2_2_SEED
            detector = FanoAccumulator(engine.n, params) if combined else None
            counts = record(mod, Q_REFLEX_MEASURE_S, detector)
            if combined:
                extra = record(mod, Q_2_2_MEASURE_S - Q_REFLEX_MEASURE_S, detector)
                safety_counts, safety_fano, safety_settle = counts + extra, detector, settle
            pair["sugar" if active else "silent"] = {"mn9_hz": float(counts[mn9] / Q_REFLEX_MEASURE_S),
                                                      "settle_s": settle.settle_s, "settled": settle.converged}
        difference = pair["sugar"]["mn9_hz"] - pair["silent"]["mn9_hz"]
        reflex[seed] = {**pair, "difference_hz": difference,
                        "floor_met": bool(difference >= Q_REFLEX_SEED_FLOOR_HZ),
                        "settled": bool(pair["sugar"]["settled"] and pair["silent"]["settled"])}
        print(json.dumps({"stage": "1.4", "seed": seed, "difference_hz": difference,
                          "floor_met": reflex[seed]["floor_met"], "wall_s": round(time.perf_counter() - started, 3)}), flush=True)
    reflex_summary = reflex_rule(np.array([row["difference_hz"] for row in reflex.values()]), params)
    check_1_4 = reflex_summary["passed"] and all(row["settled"] for row in reflex.values())

    if safety_counts is None or safety_fano is None or safety_settle is None:
        raise RuntimeError("2.2 requires the seed-0 stimulated 1.4 recording")
    rates = safety_counts / Q_2_2_MEASURE_S
    fano = safety_fano.report()
    safety = bare_rate_safety(rates, safety_settle.converged)
    median = safety["median_hz"]
    high = safety["fraction_above_50_hz"]
    group_rates: dict[str, dict[str, Any]] = {}
    for name, idx in group_indices(registry).items():
        observed = float(np.mean(rates[idx]))
        target_key = name if name in ("central", "DAN", "KC", "ER", "descending", "motor") else "other"
        target = float(params.get(f"bg.target.{target_key}")) if name != "sensory" else None
        group_rates[str(name)] = {"observed_hz": observed,
                             "placeholder_background_target_hz": target,
                             "diagnostic_lower_hz": target / 2 if target is not None else None,
                             "diagnostic_upper_hz": target * 2 if target is not None else None}
    check_2_2 = safety["passed"]
    print(json.dumps({"stage": "2.2", "median_hz": median, "fraction_above_50_hz": high,
                      "F": fano["F"], "passed": check_2_2,
                      "wall_s": round(time.perf_counter() - started, 3)}), flush=True)
    qualification = {
        "status": "passed" if check_3_1b and check_1_4 and check_2_2 else "failed",
        "date": dt.date.today().isoformat(), "background": False, "dopamine_A": True,
        "transporter_C": True, "master_seed": K2_MASTER_SEED,
        "order": ["3.1b", "1.4", "2.2"], "wall_s": time.perf_counter() - started,
        "windows_s": {"3.1b": Q_3_1B_MEASURE_S, "1.4": Q_REFLEX_MEASURE_S, "2.2": Q_2_2_MEASURE_S},
        "3.1b": {"passed": check_3_1b, "per_seed": checks_3_1b,
                 "mean_da_per_compartment": da_table},
        "1.4": {**reflex_summary, "passed": check_1_4, "per_seed": reflex},
        "2.2": {**safety, "seed": Q_2_2_SEED, "stimulus": "sugar_reflex",
                "settle_s": safety_settle.settle_s, "settled": safety_settle.converged,
                "Fano": {**fano, "F_bound": float(params.get("artefact.sync_fano_max")),
                          "bin_fraction_bound": float(params.get("artefact.sync_bin_fraction_max"))},
                "group_rates": group_rates,
                "quantiles_hz": {str(q): float(np.quantile(rates, q)) for q in (0, 0.25, 0.5, 0.75, 0.9, 0.99, 1)}},
    }
    passed = qualification["status"] == "passed"
    if not passed:
        qualification["escalation"] = {"free_pool_rates_per_group": group_rates,
                                        "Fano": qualification["2.2"]["Fano"],
                                        "mean_DA_per_compartment": da_table,
                                        "per_neuron_modulation_bounds": {
                                            seed: {"dV": row["per_neuron_dv_mv"], "gain": row["per_neuron_gain"],
                                                   "arrays_bitwise": row["per_chunk_arrays_bitwise"]}
                                            for seed, row in checks_3_1b.items()}}
    checkpoint = REPO / ".reports/wp5-q-qualification.json"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(json.dumps(_plain(qualification), indent=2))
    if refresh_3_1b:
        # The review authorizes replacing only 3.1b after a complete deterministic
        # Q replay passes. Keep accepted item-61 seed rows and historical escalation.
        previous = table["qualification"]
        same_reflex = previous["1.4"]["per_seed"].keys() == reflex.keys() and all(
            previous["1.4"]["per_seed"][seed]["difference_hz"] == row["difference_hz"]
            for seed, row in reflex.items())
        if passed and same_reflex:
            previous["3.1b"] = qualification["3.1b"]
            previous["windows_s"] = qualification["windows_s"]
            previous["review_3_1b"] = {"date": dt.date.today().isoformat(),
                "wall_s": qualification["wall_s"], "Q_replayed": True,
                "reflex_values_unchanged": True, "2.2": qualification["2.2"]}
            write_record(destination, table)
        return {"status": qualification["status"], "qualified": bool(table["qualified"]),
                "record_refreshed": bool(passed and same_reflex), "path": str(destination),
                "wall_s": qualification["wall_s"]}
    table["qualified"] = passed
    table["status"] = "Q passed; frozen" if passed else "Q failed; unqualified"
    table["qualification_rule"] = ("SPEC item 60: bare 2.2 uses stimulated sugar-reflex 10 s, median <= 5 Hz with no floor, fewer than 1% above 50 Hz; "
                                   "SPEC item 61: ten-seed mean MN9 difference > 50 Hz and no seed < 40 Hz")
    table["qualification"] = qualification
    write_record(destination, table)
    return {"status": qualification["status"], "qualified": passed,
            "3.1b": check_3_1b, "1.4": check_1_4, "2.2": check_2_2,
            "path": str(destination), "wall_s": qualification["wall_s"]}


def requalify_item_61() -> dict[str, Any]:
    """Rescore stored Q reflex seeds without rebuilding; Hz vector (n_seed,), YAML scalars."""
    destination = REPO / "data/dopamine-v0.1.yaml"
    table: dict[str, Any] = read_yaml(destination)
    qualification = table.get("qualification", {})
    if qualification.get("requalified_date") and "SPEC item 61" in table.get("qualification_rule", ""):
        reflex = qualification["1.4"]
        return {"status": qualification["status"], "qualified": bool(table["qualified"]),
                "mean_hz": reflex["mean_hz"], "minimum_hz": reflex["minimum_hz"],
                "previous_rule": reflex["previous_rule"], "path": str(destination)}
    if not all(isinstance(qualification.get(key), dict) for key in ("3.1b", "1.4", "2.2")):
        raise ValueError("item-61 requalification requires complete stored Q measurements")
    seed_rows = qualification["1.4"].get("per_seed", {})
    seeds = sorted(int(seed) for seed in seed_rows)
    if seeds != list(range(int(load_params().get("validation.seeds")))):
        raise ValueError("item-61 requalification requires every configured seed")
    prior = {"rule": "previous item-48 interpretation: each seed > 50 Hz",
             "passed": qualification["1.4"].get("passed", False),
             "failed_seeds": [seed for seed in seeds if seed_rows[seed]["difference_hz"] <= Q_REFLEX_MEAN_MIN_HZ]}
    score = reflex_rule(np.array([seed_rows[seed]["difference_hz"] for seed in seeds]), load_params())
    all_settled = all(row["silent"]["settled"] and row["sugar"]["settled"] for row in seed_rows.values())
    for row in seed_rows.values():
        row.pop("required_above_hz", None)
        row["floor_met"] = bool(row["difference_hz"] >= Q_REFLEX_SEED_FLOOR_HZ)
        row["settled"] = bool(row["silent"]["settled"] and row["sugar"]["settled"])
        row.pop("passed", None)
    qualification["1.4"].update({**score, "passed": bool(score["passed"] and all_settled),
                                  "previous_rule": prior})
    passed = bool(qualification["3.1b"]["passed"] and qualification["1.4"]["passed"] and qualification["2.2"]["passed"])
    qualification["status"] = "passed" if passed else "failed"
    qualification["requalified_date"] = dt.date.today().isoformat()
    diagnostics = qualification.pop("escalation", None)
    if diagnostics is not None:
        qualification["diagnostics"] = {"label": "historical strict-per-seed escalation, diagnostic under SPEC item 61",
                                          "qualified": False, "status": "failed",
                                          **diagnostics}
    table["qualified"] = passed
    table["status"] = "Q passed; frozen" if passed else "Q failed; unqualified"
    table["qualification_rule"] = ("SPEC item 60: stimulated bare 2.2, median <= 5 Hz with no floor, fewer than 1% above 50 Hz; "
                                   "SPEC item 61: ten-seed mean MN9 difference > 50 Hz and no seed < 40 Hz")
    table["qualification"] = qualification
    checkpoint = REPO / ".reports/wp5-q-item61-requalification.json"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(json.dumps(_plain(qualification), indent=2))
    write_record(destination, table)
    return {"status": qualification["status"], "qualified": passed,
            "mean_hz": score["mean_hz"], "minimum_hz": score["minimum_hz"],
            "previous_rule": prior, "path": str(destination)}


def write_record(destination: Path, record: dict[str, Any]) -> None:
    """Atomically write calibration YAML with native keys/scalars; units unchanged."""
    temporary = destination.with_suffix(".yaml.tmp")
    try:
        temporary.write_text(yaml.safe_dump(_plain(record), sort_keys=False))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _isolated_stage(name: str) -> dict[str, Any]:
    """Run one calibration engine in a fresh interpreter; result contains physical units."""
    if name not in ("measure_k2", "run_q"):
        raise ValueError("unknown isolated calibration stage")
    code = (f"import json; from flyonenomics.neuromod.calibration import {name}; "
            f"result = {name}(); print('STAGE-RESULT ' + json.dumps(result))")
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                            capture_output=True, text=True, check=True)
    print(result.stdout, end="", flush=True)
    return json.loads(result.stdout.rsplit("STAGE-RESULT ", 1)[1])


def run_k2() -> dict[str, Any]:
    """Run or replay K2 then Q; a measured but unqualified K2 cannot advance calibration."""
    destination = REPO / "data/dopamine-v0.1.yaml"
    previous = read_yaml(destination) if destination.is_file() else {}
    outcome = previous.get("qualification", {}).get("status")
    if outcome in ("passed", "failed"):
        passed = outcome == "passed" and bool(previous.get("qualified"))
        checks = previous.get("qualification", {})
        passed = passed and all(checks.get(key, {}).get("passed") is True for key in ("3.1b", "1.4", "2.2"))
        seed_rows = checks.get("1.4", {}).get("per_seed", {})
        expected_seeds = list(range(int(load_params().get("validation.seeds"))))
        if sorted(seed_rows) != expected_seeds:
            passed = False
        else:
            score = reflex_rule(np.array([seed_rows[seed]["difference_hz"] for seed in expected_seeds]), load_params())
            passed = passed and score["passed"] and all(
                row["silent"]["settled"] and row["sugar"]["settled"] for row in seed_rows.values())
        return {"status": "passed" if passed else "failed", "qualified": passed,
                "reason": "K2 and Q already measured; frozen record retained" if passed else
                          "K2/Q unqualified; escalation record retained", "path": str(destination)}
    if not previous.get("R_c"):
        measured = _isolated_stage("measure_k2")
        if measured["status"] != "recorded":
            return measured
    return _isolated_stage("run_q")


STAGE = {"K1": run_k1, "K2": run_k2}


def rest_release_constants(rates_hz: NDArray[np.float64], params: Params) -> tuple[NDArray[np.float64], NDArray[np.float64], list[str]]:
    """K2r continuous release law; (n_comp,) Hz -> µM/spike, µM/s, mode.

    Phase 1 release_constants intentionally retains its separate alpha_max rule.
    """
    rates = np.asarray(rates_hz, dtype=np.float64)
    if rates.ndim != 1 or not rates.size or not np.isfinite(rates).all() or np.any(rates < 0):
        raise ValueError("K2r requires finite nonnegative weighted DAN rates")
    rmin = float(params.get("da.R_min"))
    q = params.get("da.DA_ref") * (params.get("da.Vmax") / (params.get("da.Km") + params.get("da.DA_ref")) + params.get("da.k_ns"))
    if rmin <= 0 or q <= 0:
        raise ValueError("invalid dopamine reference constants")
    alpha = q / np.maximum(rates, rmin)
    source = np.where(rates >= rmin, 0.0, np.maximum(0.0, q-alpha*rates))
    return alpha, source, ["derived" if r >= rmin else "source" for r in rates]


def run_k2r(*, iteration: int = 1, free_rates: NDArray[np.float64] | None = None) -> dict[str, Any]:
    """Measure K2r on the Mac and make a dopamine-only configuration commit.

    First iteration uses three clamped 2+5 s seeds. Subsequent iterations use
    measured free-pool R_c from the preceding 3.1br, at most three iterations.
    Evidence is committed before the numeric file, keeping the freeze atomic.
    """
    from flyonenomics.drive import rest_calibration as rest
    from flyonenomics.drive.rest import load_dopamine_v02
    from flyonenomics.io import read_json
    from flyonenomics.validation.binding import blob_id
    from flyonenomics.store.results import atomic_json
    from flyonenomics.registry import build_registry
    if iteration not in range(1,4):
        raise ValueError("K2r permits at most three iterations")
    rest.commit_records("calibration(w19): checkpoint drive freeze evidence")
    rest.require_clean()
    identity=rest._entry_identity("rest-k2r.json",dopamine=False)
    drive_rel=rest._drive().relative_to(rest.ROOT).as_posix()
    dopamine_rel=rest._dopamine().relative_to(rest.ROOT).as_posix()
    if free_rates is None:
        measured=rest.run_jobs([{"kind":"K2r","seed":s,"clamped":True,"duration_s":5} for s in K2_SEEDS])
        rates=np.mean([r["R_c"] for r in measured["rows"]],axis=0)
        names=measured["rows"][0]["compartments"]
    else:
        if iteration==1:raise ValueError("first K2r iteration must measure clamped pools")
        rates=np.asarray(free_rates,dtype=float)
        names=[c.name for c in build_registry("783",populations_path=rest.ROOT/"data/populations-v0.2.yaml").compartments()]
        measured={"source":"preceding free-pool 3.1br", "R_c":rates.tolist(),
                  "previous_dopamine_blob":blob_id(rest.ROOT,dopamine_rel)}
    p=load_params(rest.ROOT/"data/params-v0.2.yaml")
    alpha,source,mode=rest_release_constants(rates,p)
    if len(names)!=len(rates):raise ValueError("K2r rate vector must match compartment order")
    evidence={"status":"passed",**rest._class_fields(),"iteration":iteration,"measurement":measured,
              "R_c":rates.tolist(),"alpha_c":alpha.tolist(),"S_c":source.tolist(),
              "mode":mode,"identity":identity.model_dump(mode="json")}
    evidence_tag=__import__("hashlib").sha256(json.dumps(evidence,sort_keys=True).encode()).hexdigest()[:16]
    evidence_path=rest._rec()/f"wp19-K2r-iteration-{iteration}-{evidence_tag}.json"
    atomic_json(evidence_path,evidence)
    rest.commit_records("calibration(w19): record K2r measured release constants")
    document={**({"configuration_class":"development","note":rest.DEV_NOTE} if rest.development() else {}),
              "version":"v0.2","params_version":"v0.2","receptor_map_version":"v0.1",
              "connectome_version":"783","compartments":names,"R_c":rates.tolist(),
              "alpha_c":alpha.tolist(),"S_c":source.tolist(),"mode":mode,
              "constants":{key:float(p.get(f"da.{key}")) for key in ("DA_ref","Vmax","Km","k_ns","R_min","alpha_max")},
              "drive_blob_id":blob_id(rest.ROOT,drive_rel),
              "provenance":{"K2r_record_sha256":rest._sha(evidence_path),"iteration":iteration,
                            "upstream_blobs":{drive_rel:blob_id(rest.ROOT,drive_rel)}}}
    commit=rest.freeze_configuration(rest._dopamine(),document)
    load_dopamine_v02(rest._dopamine(),names)
    rest.publish_entry("3.1r",{"outcome":"recorded",**evidence},identity,"rest-k2r.json",
                       inputs=rest.declared_inputs("rest-k2r.json",dopamine=False))
    result={"status":"passed","configuration_commit":commit,"iteration":iteration,
            "sha256":rest._sha(rest._dopamine()),"measurement_record":str(evidence_path.relative_to(rest.ROOT))}
    return rest.save_stage("K2r",result,run_k2r.input_identity())


def _k2r_identity() -> dict:
    from flyonenomics.drive import rest_calibration as rest
    return rest.output_guard(rest.stage_identity(rest._drive(),rest.ROOT/"data/params-v0.2.yaml",rest.FIXTURES/"rest-k2r.json"),"K2r",rest._dopamine())


run_k2r.input_identity = _k2r_identity
STAGE["K2r"] = run_k2r
