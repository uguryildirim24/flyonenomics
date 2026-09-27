"""Persistent genotype/drug layers and fast compartment dopamine state."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from numpy.typing import NDArray

from flyonenomics.neuromod.drugs import check_drug, drug_effect
from flyonenomics.neuromod.pk import SlowState
from flyonenomics.neuromod.pools import euler_step, fixed_point, innervated_mask, tonic_source
from flyonenomics.neuromod.receptors import receptor_effect
from flyonenomics.schema.experiment import (Disconnect, Manipulation, ScaleDat, ScaleGain,
                                             ScaleReceptor, ScaleRelease, ShiftThreshold, Silence)
from flyonenomics.types import ComposedParams, LayerFlags, Params, SettleRecord

MS_PER_SECOND = 1000


def resolution_threshold(mean_hz: float, window_s: float, params: Params) -> float:
    """Return the spike-count floor that resolves one candidate. Units: spikes, Hz, s."""
    delta = max(float(params.get("settle.tol_abs_rate_13")), float(params.get("settle.tol_rate")) * float(mean_hz))
    if delta <= 0:
        return np.inf
    k_resolve = float(params.get("settle.k_resolve"))
    fano = float(params.get("settle.fano_ref"))
    return 2.0 * fano * (k_resolve * float(mean_hz) / delta) ** 2


def candidate_resolved(n_neurons: int, n_spikes: float, window_s: float, params: Params) -> bool:
    """Return whether candidate g is resolved from counts only. Units: spikes, s, Hz."""
    if n_neurons <= 0 or window_s <= 0 or float(n_spikes) <= 0:
        return False
    mean_hz = float(n_spikes) / (float(n_neurons) * float(window_s))
    return float(n_spikes) >= resolution_threshold(mean_hz, window_s, params)


def rate_equivalence(mean_prev: float, mean_last: float, std_prev: float, std_last: float,
                     n_blocks: int, params: Params) -> bool:
    """Return whether drift of g lies inside ±δ_g. Units: Hz."""
    delta = float(mean_last) - float(mean_prev)
    se = float(np.sqrt((std_last ** 2) / n_blocks + (std_prev ** 2) / n_blocks))
    bound = max(float(params.get("settle.tol_abs_rate_13")), float(params.get("settle.tol_rate")) * float(mean_prev))
    return abs(delta) + float(params.get("settle.t_quantile")) * se <= bound


def settle_13_from_windows(
    names: list[str],
    sizes: list[int],
    windows: list[dict[str, NDArray[np.floating]]],
    params: Params,
) -> dict[str, Any]:
    """Run the section 2.4 rule on synthetic or measured block counts.

    Units: window length s, block counts in spikes, rates Hz.
    Shapes: each windows[t][name] is float (n_blocks,).
    """
    window_s = float(params.get("settle.window_s_13"))
    n_blocks = int(params.get("settle.blocks"))
    min_s = float(params.get("settle.min_s"))
    max_s = float(params.get("settle.max_s"))
    first = int(round(min_s / window_s))
    max_windows = int(round(max_s / window_s))
    if first < 2:
        first = 2
    unresolved: list[str] = []
    decision: list[str] = []
    converged = False
    settle_s = min(len(windows) * window_s, max_s)
    if len(windows) < first:
        return {"converged": False, "unresolved": [name for name, size in zip(names, sizes)
                                                  if not candidate_resolved(size, 0.0, window_s, params)],
                "decision": [], "settle_s": settle_s, "comparisons": 0}
    first_window = windows[first - 1]
    for name, size in zip(names, sizes, strict=True):
        n_spikes = float(np.sum(first_window[name]))
        if candidate_resolved(size, n_spikes, window_s, params):
            decision.append(name)
        else:
            unresolved.append(name)
    comparisons = 0
    for index in range(first - 1, min(len(windows), max_windows)):
        if index == 0:
            continue
        prev, last = windows[index - 1], windows[index]
        comparisons += 1
        ok = True
        for name, size in zip(names, sizes, strict=True):
            if name not in decision:
                continue
            prev_blocks = np.asarray(prev[name], dtype=np.float64)
            last_blocks = np.asarray(last[name], dtype=np.float64)
            prev_rate = prev_blocks / (size * (window_s / n_blocks))
            last_rate = last_blocks / (size * (window_s / n_blocks))
            if not rate_equivalence(float(np.mean(prev_rate)), float(np.mean(last_rate)),
                                    float(np.std(prev_rate, ddof=1)) if n_blocks > 1 else 0.0,
                                    float(np.std(last_rate, ddof=1)) if n_blocks > 1 else 0.0,
                                    n_blocks, params):
                ok = False
                break
        if ok:
            converged = True
            settle_s = (index + 1) * window_s
            break
    else:
        settle_s = min(len(windows), max_windows) * window_s
    return {"converged": converged, "unresolved": unresolved, "decision": decision,
            "settle_s": settle_s, "comparisons": comparisons}


@dataclass(frozen=True)
class _Candidate:
    """One settle candidate. Units: none. Shapes: idx int32 (m,)."""
    name: str
    idx: NDArray[np.int32]


@dataclass
class NeuromodState:
    """Recorder state: pool, occupancy, Km and release vectors (n_comp,), concentrations in µM."""
    da_c: NDArray[np.float64]
    occ_D1: NDArray[np.float64]
    occ_D2: NDArray[np.float64]
    Km_eff: NDArray[np.float64]
    rel: NDArray[np.float64]
    concentrations: dict[str, float]


class Neuromod:
    """One arm/seed model: thresholds (n,) mV, pool concentrations (n_comp,) µM."""

    def __init__(self, registry: Any, params: Params, layers: LayerFlags, dopamine: dict[str, Any] | None = None,
                 *, base_v_th: NDArray[np.float64] | None = None, schema_version: str = "1.2",
                 drive_groups: dict[str, NDArray[np.int32]] | None = None) -> None:
        """Capture immutable M/W/map and layer state; arrays (n,), (n_comp,), units per field."""
        self.registry, self.params, self.layers = registry, params, layers
        self.m = registry.innervation().tocsr()
        self.w = registry.exposure().tocsr()
        self.exposed = np.asarray(registry.exposed_mask(), dtype=bool)
        receptor_map = registry.receptors()
        self.r1 = np.asarray(receptor_map.r1, dtype=np.float64).copy()
        self.r2 = np.asarray(receptor_map.r2, dtype=np.float64).copy()
        self.rq = np.asarray(receptor_map.rq, dtype=np.float64).copy()
        self.mask = innervated_mask(self.m)
        self.compartment_names = [c.name for c in registry.compartments()]
        self.uninnervated_compartments = [name for name, present in zip(self.compartment_names, self.mask, strict=True) if not present]
        nc = len(self.mask)
        table = dopamine or {}
        if table.get("qualified") and (not table.get("alpha_c") or not table.get("R_c")):
            raise ValueError("qualified dopamine table requires measured alpha_c and R_c")
        self.alpha = np.asarray(table.get("alpha_c") or [params.get("da.alpha_max")] * nc, dtype=np.float64)
        self.r_tonic = np.asarray(table.get("R_c") or [0.0] * nc, dtype=np.float64)
        if self.alpha.shape != (nc,) or self.r_tonic.shape != (nc,):
            raise ValueError("dopamine table shape does not match compartments")
        if table.get("compartments") is not None and table["compartments"] != self.compartment_names:
            raise ValueError("dopamine table compartment order does not match registry")
        if any(not np.all(np.isfinite(values)) or np.any(values < 0) for values in (self.alpha, self.r_tonic)):
            raise ValueError("dopamine alpha_c and R_c must be finite and nonnegative")
        self.da_ref = float(params.get("da.DA_ref"))
        self.vmax0 = np.full(nc, float(params.get("da.Vmax")))
        self.km0 = np.full(nc, float(params.get("da.Km")))
        self.k_ns = float(params.get("da.k_ns"))
        self.tonic_source = tonic_source(self.da_ref, self.vmax0, self.km0, self.k_ns, self.mask)
        source_c = table.get("S_c")
        self.s_c = np.asarray(source_c if source_c is not None else self.tonic_source, dtype=np.float64)
        if self.s_c.shape != (nc,):
            raise ValueError("dopamine S_c shape does not match compartments")
        if not np.all(np.isfinite(self.s_c)) or np.any(self.s_c < 0):
            raise ValueError("dopamine S_c must be finite and nonnegative")
        if base_v_th is None:
            base_v_th = table.get("base_v_th")
        self.base_v_th = np.full(registry.n, float(params.get("lif.v_th")), dtype=np.float64) if base_v_th is None else np.asarray(base_v_th, dtype=np.float64)
        if self.base_v_th.shape != (registry.n,):
            raise ValueError("base threshold must have shape (n,)")
        self.schema_version = schema_version
        # Section 2.4: every drive group is a settle candidate beside the recorded populations.
        self.drive_groups = [_Candidate(f"group:{name}", np.asarray(idx, dtype=np.int32))
                             for name, idx in sorted((drive_groups or {}).items())]
        self.dat_geno = np.ones(nc)
        self.rel_geno = 1.0
        self.shift = np.zeros(registry.n)
        self.geno_gain = np.ones(registry.n)
        self.silenced = np.zeros(registry.n, dtype=bool)
        self.slow = SlowState(params, enabled=layers.transporter_C)
        self.clamped = False
        self.da_c = np.full(nc, self.da_ref)
        self.fixture_settle_s: float | None = None
        self.check_cancel: Callable[[], None] = lambda: None
        self.overlap = np.zeros(0, dtype=np.int32)

    def apply_genotype(self, manipulations: list[Manipulation], engine: Any) -> None:
        """Apply persistent hooks once; thresholds mV, gain/DAT/release dimensionless, indices (m,)."""
        for hook in manipulations:
            if isinstance(hook, (Silence, Disconnect, ShiftThreshold, ScaleGain)):
                idx = self.registry.population(hook.population).idx
                if isinstance(hook, Silence):
                    self.silenced[idx] = True
                elif isinstance(hook, Disconnect):
                    engine.disconnect(idx)
                elif isinstance(hook, ShiftThreshold):
                    self.shift[idx] += hook.delta_mv
                else:
                    self.geno_gain[idx] *= hook.factor
            elif isinstance(hook, ScaleReceptor):
                if not self.layers.dopamine_A:
                    raise ValueError("scale_receptor: dopamine_A layer off")
                idx = np.arange(self.registry.n) if hook.population == "all" else self.registry.population(hook.population).idx
                {"D1": self.r1, "D2": self.r2, "Dq": self.rq}[hook.receptor][idx] *= hook.factor
            elif isinstance(hook, ScaleDat):
                if not self.layers.transporter_C:
                    raise ValueError("scale_dat: transporter_C layer off")
                comp = np.arange(len(self.mask)) if hook.compartments == "all" else np.asarray([self.compartment_names.index(name) for name in hook.compartments])
                self.dat_geno[comp] *= hook.factor
            elif isinstance(hook, ScaleRelease):
                if not self.layers.transporter_C:
                    raise ValueError("scale_release: transporter_C layer off")
                self.rel_geno *= hook.factor
        if self.layers.dan_fast_synapses == "disconnect":
            dan = np.union1d(self.registry.population("DAN").idx, self.registry.population("CX_DAN").idx).astype(np.int32)
            engine.disconnect(dan)
        composed = self.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)

    def start_dose(self, drug: str, c_food_mm: float) -> None:
        """Start a dose; food concentration mM, one drug name."""
        check_drug(drug)
        self.slow.start_dose(drug, c_food_mm)

    def stop_dose(self, drug: str) -> None:
        """Stop a dose; one drug name, no array."""
        check_drug(drug)
        self.slow.stop_dose(drug)

    def advance_slow(self, seconds: float) -> None:
        """Advance analytical brain drug concentrations; seconds, scalar."""
        self.slow.advance(seconds)

    def clamp_pools(self, on: bool) -> None:
        """Hold every compartment exactly at DA_ref when on; µM vector (n_comp,)."""
        self.clamped = on
        if on:
            self.da_c.fill(self.da_ref)

    def _kinetics(self) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
        km_factor, rel_drug = drug_effect(self.slow.concentrations, self.params) if self.layers.transporter_C else (1.0, 1.0)
        vmax = self.vmax0 * (self.dat_geno if self.layers.transporter_C else 1.0)
        return vmax, self.km0 * km_factor, self.rel_geno * rel_drug if self.layers.transporter_C else 1.0

    def _retained_dan_fraction(self) -> NDArray[np.float64]:
        """Return active fraction of each M row, dimensionless vector (n_comp,)."""
        if not np.any(self.silenced):
            return self.mask.astype(np.float64)
        total = np.asarray(self.m @ np.ones(self.registry.n)).ravel()
        active = np.asarray(self.m @ (~self.silenced).astype(np.float64)).ravel()
        return np.divide(active, total, out=np.zeros_like(active), where=total > 0)

    def fixed_point(self) -> NDArray[np.float64]:
        """Return analytic balance estimate in µM, vector (n_comp,); uninnervated rows stay DA_ref."""
        if self.clamped:
            return np.full(len(self.mask), self.da_ref)
        vmax, km, rel = self._kinetics()
        # Item 53: K2 stores compartment totals, so scale both tonic terms by
        # the retained fraction of that compartment's M weight after silencing.
        source = rel * (self.alpha * self.r_tonic + self.s_c) * self._retained_dan_fraction()
        answer = fixed_point(source, vmax, km, self.k_ns)
        answer[~self.mask] = self.da_ref
        return answer

    def da_gap(self, mean_da: NDArray[np.float64], dan_input_hz: NDArray[np.float64]) -> NDArray[np.float64]:
        """Section 2.4 fixed-point gap: window-mean dopamine minus the analytic point, µM (n_comp,).

        dan_input_hz is the recording's measured weighted DAN spike rate per
        compartment, M @ counts / T. Silenced DANs produce no counts, so the
        retained fraction multiplies only the source term, as in on_chunk.
        """
        if self.clamped:
            analytic = np.full(len(self.mask), self.da_ref)
        else:
            vmax, km, rel = self._kinetics()
            source = rel * (self.alpha * np.asarray(dan_input_hz, dtype=np.float64)
                            + self.s_c * self._retained_dan_fraction())
            analytic = fixed_point(source, vmax, km, self.k_ns)
            analytic[~self.mask] = self.da_ref
        return np.asarray(mean_da, dtype=np.float64) - analytic

    def reset_fast(self) -> None:
        """Reset pools to the current estimated fixed point; µM vector (n_comp,)."""
        self.da_c = self.fixed_point()

    def receptor_terms(self) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        """Return dV mV, gain and occupancies, each shape (n,); A-off gives identity."""
        if not self.layers.dopamine_A:
            z = np.zeros(self.registry.n)
            return z, np.ones(self.registry.n), z.copy(), z.copy()
        return receptor_effect(self.da_c, self.w, self.exposed, self.r1, self.r2, self.params)

    def compose(self) -> ComposedParams:
        """Compose threshold mV and gain dimensionless, vectors (n,), in layer order."""
        d_v, g_da, _, _ = self.receptor_terms()
        threshold = np.clip(self.base_v_th + self.shift + d_v, *self.params.get("rec.vth_clip"))
        threshold[self.silenced] = self.params.get("engine.silence_vth")
        gain = np.clip(self.geno_gain * g_da, *self.params.get("rec.gain_clip"))
        return ComposedParams(threshold, gain, self.layers)

    def on_chunk(self, counts: NDArray[np.int32], dt_s: float) -> None:
        """Apply one explicit Euler pool step; spike counts (n,), duration seconds."""
        if self.clamped:
            self.da_c.fill(self.da_ref)
            return
        vmax, km, rel = self._kinetics()
        self.da_c = euler_step(self.da_c, counts, dt_s, self.m, self.mask, self.alpha,
                               rel, vmax, km, self.k_ns, self.da_ref,
                               self.s_c * self._retained_dan_fraction())

    def settle(self, engine: Any, stimulus: Callable[[], None], recorded: list[Any]) -> SettleRecord:
        """Run unrecorded windows until the schema's settle rule passes; seconds/µM/Hz arrays."""
        if self.schema_version == "1.3" and self.fixture_settle_s is None:
            return self._settle_13(engine, stimulus, recorded)
        return self._settle_phase1(engine, stimulus, recorded)

    def _settle_phase1(self, engine: Any, stimulus: Callable[[], None], recorded: list[Any]) -> SettleRecord:
        """Phase 1 settle: DA and every recorded rate. Units: s, µM, Hz."""
        fixed = self.fixed_point()
        chunk_ms = int(self.params.get("engine.chunk_ms"))
        window_chunks = int(round(self.params.get("settle.window_s") * MS_PER_SECOND / chunk_ms))
        min_chunks = int(round(self.params.get("settle.min_s") * MS_PER_SECOND / chunk_ms))
        max_chunks = int(round(self.params.get("settle.max_s") * MS_PER_SECOND / chunk_ms))
        if self.fixture_settle_s is not None:
            max_chunks = min_chunks = int(round(self.fixture_settle_s * MS_PER_SECOND / chunk_ms))
        if max_chunks == 0:
            return SettleRecord(True, 0.0, fixed, self.da_c.copy(), np.zeros(len(recorded)),
                                engine.tick(), upstream_extended_overlap_idx=self.overlap.copy())
        da_windows: deque[NDArray[np.float64]] = deque(maxlen=2)
        rate_windows: deque[NDArray[np.float64]] = deque(maxlen=2)
        da_acc = np.zeros(len(self.mask))
        count_acc = np.zeros(len(recorded))
        converged = False
        rates = np.zeros(len(recorded))
        for step in range(1, max_chunks + 1):
            self.check_cancel()
            stimulus()
            result = engine.run_chunk(chunk_ms)
            self.on_chunk(result.counts, chunk_ms / MS_PER_SECOND)
            composed = self.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            da_acc += self.da_c
            count_acc += np.array([result.counts[p.idx].sum() / len(p.idx) for p in recorded])
            if step % window_chunks == 0:
                da_windows.append(da_acc / window_chunks)
                rates = count_acc / (window_chunks * chunk_ms / MS_PER_SECOND)
                rate_windows.append(rates.copy())
                da_acc.fill(0)
                count_acc.fill(0)
                if step >= min_chunks and len(da_windows) == 2:
                    prev, curr = da_windows
                    d_da = np.abs(curr[self.mask] - prev[self.mask])
                    da_ok = not len(d_da) or (np.max(d_da) < self.params.get("settle.tol_abs_da") and
                        np.max(d_da / np.maximum(np.abs(prev[self.mask]), np.finfo(np.float64).eps)) < self.params.get("settle.tol_rel_da"))
                    old, new = rate_windows
                    d_rate = np.abs(new - old)
                    rate_ok = np.all((d_rate < self.params.get("settle.tol_abs_rate")) |
                                     (d_rate / np.maximum(np.abs(old), self.params.get("settle.tol_abs_rate")) < self.params.get("settle.tol_rate")))
                    if da_ok and rate_ok:
                        converged = True
                        break
            self.check_cancel()
        duration = step * chunk_ms / MS_PER_SECOND
        if self.fixture_settle_s is not None:
            converged = True
        return SettleRecord(converged, duration, fixed, self.da_c.copy(), rates,
                            engine.tick(), upstream_extended_overlap_idx=self.overlap.copy())

    def _settle_13(self, engine: Any, stimulus: Callable[[], None], recorded: list[Any]) -> SettleRecord:
        """Schema 1.3 settle: resolved-set equivalence; DA is recorded, not a criterion."""
        fixed = self.fixed_point()
        chunk_ms = int(self.params.get("engine.chunk_ms"))
        window_s = float(self.params.get("settle.window_s_13"))
        n_blocks = int(self.params.get("settle.blocks"))
        window_chunks = int(round(window_s * MS_PER_SECOND / chunk_ms))
        block_chunks = max(1, window_chunks // n_blocks)
        min_chunks = int(round(self.params.get("settle.min_s") * MS_PER_SECOND / chunk_ms))
        max_chunks = int(round(self.params.get("settle.max_s") * MS_PER_SECOND / chunk_ms))
        candidates = list(recorded) + list(self.drive_groups)
        names = [getattr(pop, "name", f"recorded-{i}") for i, pop in enumerate(candidates)]
        sizes = [max(1, len(pop.idx)) for pop in candidates]
        if max_chunks == 0:
            return SettleRecord(True, 0.0, fixed, self.da_c.copy(), np.zeros(len(recorded)),
                                engine.tick(), upstream_extended_overlap_idx=self.overlap.copy(),
                                unresolved=[], da_gap_um=[])
        windows: list[dict[str, NDArray[np.floating]]] = []
        if len(set(names)) != len(names):
            raise ValueError("settle candidate names must be unique")
        block_acc = {name: np.zeros(n_blocks, dtype=np.float64) for name in names}
        count_acc = np.zeros(len(recorded))
        rates = np.zeros(len(recorded))
        unresolved: list[str] = []
        converged = False
        step = 0
        for step in range(1, max_chunks + 1):
            self.check_cancel()
            stimulus()
            result = engine.run_chunk(chunk_ms)
            self.on_chunk(result.counts, chunk_ms / MS_PER_SECOND)
            composed = self.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            count_acc += np.array([result.counts[p.idx].sum() / len(p.idx) for p in recorded])
            in_window = (step - 1) % window_chunks
            block = min(in_window // block_chunks, n_blocks - 1)
            for name, pop in zip(names, candidates, strict=True):
                block_acc[name][block] += float(result.counts[pop.idx].sum())
            if step % window_chunks == 0:
                windows.append({name: acc.copy() for name, acc in block_acc.items()})
                rates = count_acc / (window_chunks * chunk_ms / MS_PER_SECOND)
                for acc in block_acc.values():
                    acc.fill(0)
                count_acc.fill(0)
                if step >= min_chunks:
                    verdict = settle_13_from_windows(names, sizes, windows, self.params)
                    unresolved = list(verdict["unresolved"])
                    if verdict["converged"]:
                        converged = True
                        break
            self.check_cancel()
        duration = step * chunk_ms / MS_PER_SECOND
        # The dopamine gap belongs to the recording window; the worker fills it after recording.
        return SettleRecord(converged, duration, fixed, self.da_c.copy(), rates,
                            engine.tick(), upstream_extended_overlap_idx=self.overlap.copy(),
                            unresolved=unresolved, da_gap_um=[])

    def state(self) -> NeuromodState:
        """Return pool and mean compartment occupancy vectors (n_comp,), concentrations in brain µM."""
        # The wide recorder expects compartment columns; occupancy here is evaluated at each pool.
        occ_c1 = self.da_c / (self.da_c + self.params.get("rec.Kd_D1"))
        occ_c2 = self.da_c / (self.da_c + self.params.get("rec.Kd_D2"))
        _, km, rel = self._kinetics()
        return NeuromodState(self.da_c.copy(), occ_c1, occ_c2, km.copy(),
                            np.full(len(self.mask), rel), self.slow.concentrations.copy())
