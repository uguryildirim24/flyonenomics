"""Explicit WP4 identities; engine interventions and analytical PK are real."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable
import numpy as np
from numpy.typing import NDArray
if TYPE_CHECKING:
    from flyonenomics.engine.base import Engine
from flyonenomics.orchestrator.slowstate import SlowState
from flyonenomics.schema.experiment import Manipulation, Silence, ShiftThreshold, ScaleGain, Disconnect
from flyonenomics.types import ComposedParams, LayerFlags, Params, SettleRecord

MS_PER_SECOND = 1000
# Package capabilities, used by server validation. Non-arena probes still use
# IdentityBehaviour; the runner records that per-experiment use separately.
STUB_NAMES: tuple[str, ...] = ()


class Cancelled(Exception):
    """Cooperative cancellation at a chunk or phase boundary."""


@dataclass
class NeuromodState:
    """Stub compartment state; µM/occupancy/rel, zero-length float vectors."""
    da_c: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))
    occ_D1: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))
    occ_D2: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))
    Km_eff: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))
    rel: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))
    concentrations: dict[str, float] = field(default_factory=dict)


class IdentityNeuromod:
    """Identity modulation with persistent engine hooks; arrays have shape (n,)."""
    def __init__(self, registry: Any, params: Params, layers: LayerFlags, dopamine: Any = None) -> None:
        """Create one arm/seed state; mV, dimensionless gains, arrays (n,)."""
        self.registry, self.params, self.layers = registry, params, layers
        self.slow = SlowState(params, enabled=layers.transporter_C)
        self.shift = np.zeros(registry.n)
        self.gain = np.ones(registry.n)
        self.silenced = np.zeros(registry.n, dtype=bool)
        self.fixture_settle_s: float | None = None
        self.check_cancel: Callable[[], None] = lambda: None
        self.overlap = np.zeros(0, dtype=np.int32)

    def apply_genotype(self, manipulations: list[Manipulation], engine: Engine) -> None:
        """Apply persistent engine hooks; delta mV, factor dimensionless, indices (m,)."""
        for hook in manipulations:
            if isinstance(hook, (Silence, ShiftThreshold, ScaleGain, Disconnect)):
                idx = self.registry.population(hook.population).idx
                if isinstance(hook, Silence):
                    self.silenced[idx] = True
                elif isinstance(hook, ShiftThreshold):
                    self.shift[idx] += hook.delta_mv
                elif isinstance(hook, ScaleGain):
                    self.gain[idx] *= hook.factor
                else:
                    engine.disconnect(idx)
        if self.layers.dan_fast_synapses == "disconnect":
            idx = np.union1d(self.registry.population("DAN").idx, self.registry.population("CX_DAN").idx).astype(np.int32)
            engine.disconnect(idx)
        self._write(engine)

    def start_dose(self, drug: str, c_food_mm: float) -> None:
        """Start analytical exposure; mM food, scalar."""
        self.slow.start_dose(drug, c_food_mm)

    def stop_dose(self, drug: str) -> None:
        """Stop analytical exposure; units none, scalar drug."""
        self.slow.stop_dose(drug)

    def advance_slow(self, seconds: float) -> None:
        """Advance drug concentrations after a phase; seconds, scalar per drug."""
        self.slow.advance(seconds)

    def clamp_pools(self, on: bool) -> None:
        """No-op pool clamp; units none, scalar flag."""

    def fixed_point(self) -> NDArray[np.float64]:
        """Return no modelled pools; µM, float array (0,)."""
        return np.zeros(0)

    def reset_fast(self) -> None:
        """No-op fast reset; units none, no arrays."""

    def compose(self) -> ComposedParams:
        """Compose persistent thresholds/gains; mV/dimensionless arrays (n,)."""
        threshold = np.clip(self.params.get("lif.v_th") + self.shift, *self.params.get("rec.vth_clip"))
        threshold[self.silenced] = self.params.get("engine.silence_vth")
        return ComposedParams(threshold, np.clip(self.gain, *self.params.get("rec.gain_clip")), self.layers)

    def _write(self, engine: Engine) -> None:
        composed = self.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)

    def settle(self, engine: Engine, stimulus: Callable[[], None], recorded: list[Any]) -> SettleRecord:
        """Run held-arena unrecorded chunks; seconds, rates (n_pop,), DA (0,)."""
        duration = self.params.get("settle.min_s") if self.fixture_settle_s is None else self.fixture_settle_s
        chunk_ms = self.params.get("engine.chunk_ms")
        remaining = int(round(duration * MS_PER_SECOND))
        final_rates = np.zeros(len(recorded))
        elapsed_ms = 0
        while remaining:
            self.check_cancel()
            step_ms = min(chunk_ms, remaining)
            stimulus()
            result = engine.run_chunk(step_ms)
            self.on_chunk(result.counts, step_ms / MS_PER_SECOND)
            self._write(engine)
            final_rates = np.array([result.counts[p.idx].sum() / (len(p.idx) * step_ms / MS_PER_SECOND) for p in recorded])
            elapsed_ms += step_ms
            remaining -= step_ms
            self.check_cancel()
        return SettleRecord(True, elapsed_ms / MS_PER_SECOND, self.fixed_point(), self.fixed_point(), final_rates,
                            engine.tick(), upstream_extended_overlap_idx=self.overlap.copy())

    def on_chunk(self, counts: NDArray[np.int32], dt_s: float) -> None:
        """Read but do not alter modulation or slow state; counts (n,), seconds."""

    def state(self) -> NeuromodState:
        """Expose zero-length pool state and held drug values; µM, vectors (0,)."""
        return NeuromodState(concentrations=self.slow.concentrations.copy())


class IdentityBehaviour:
    """Stationary arena and zero-rate encoder; no behavioural assay is implemented."""
    def __init__(self, n_extended: int = 0) -> None:
        """Create zero-rate encoder; Hz, vector (n_extended,)."""
        self.n_extended = n_extended
        self.encoder_stream: np.random.Generator | None = None

    def reset(self, stream: np.random.Generator) -> None:
        """Reset position, heading and filters; mm/degrees/Hz, scalar fields."""
        self.stream = stream

    def step(self, counts: NDArray[np.int32], dt_s: float) -> None:
        """Hold the reset state; counts (n,), duration seconds."""

    def state(self) -> dict[str, float]:
        """Return reset arena state; mm/degrees/degrees per second/Hz, scalars."""
        return dict.fromkeys(("x", "y", "h", "omega", "r_L", "r_R"), 0.0)

    def view(self) -> dict[str, Any]:
        """Return the empty stimulus view; degrees/contrast, zero stimuli."""
        return {"stimuli": []}

    def rates(self, view: dict[str, Any], t: float) -> NDArray[np.float64]:
        """Return zero encoder input; time seconds, Hz array (n_extended,)."""
        return np.zeros(self.n_extended)
