"""Engine interface of SPEC section 3.1 (WP1).

Units and array shapes are stated in every public docstring.
Every array argument is full length n unless the docstring says indexed.
Tables cross the file boundary as pandas only outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from flyonenomics.engine.models import Mechanisms
from flyonenomics.types import ChunkResult, ConnectomeFiles, Params, SpikeTable, TraceTable


@dataclass(eq=False, frozen=True)
class UpstreamBank:
    """One upstream-exact Poisson input bank, part of the run-wide topology.

    Units: rate_hz in Hz. Shapes: idx is int32 with shape (n_bank,)
    in the authoritative source order, never sorted.
    """

    idx: NDArray[np.int32]
    rate_hz: float

    def __post_init__(self) -> None:
        """Freeze a validated bank copy. Units: Hz. Shapes: idx (n_bank,)."""
        if not isinstance(self.idx, np.ndarray) or self.idx.ndim != 1 or self.idx.dtype != np.int32:
            raise ValueError("bank idx must be one-dimensional int32")
        if np.any(self.idx < 0) or len(np.unique(self.idx)) != len(self.idx):
            raise ValueError("bank indices must be nonnegative and unique")
        if not np.isfinite(self.rate_hz) or self.rate_hz < 0:
            raise ValueError("bank rate_hz must be finite and >= 0")
        copied = self.idx.copy()
        copied.flags.writeable = False
        object.__setattr__(self, "idx", copied)


@dataclass(eq=False)
class InputTopology:
    """Run-wide input topology, fixed before the first snapshot.

    Units: none. Shapes: extended_idx, spikelist_idx, and trace_idx
    are int32 index arrays; banks hold full neuron indices.
    """

    upstream_banks: list[UpstreamBank] = field(default_factory=list)
    extended_idx: NDArray[np.int32] = field(
        default_factory=lambda: np.zeros(0, dtype=np.int32)
    )
    spikelist_idx: NDArray[np.int32] = field(
        default_factory=lambda: np.zeros(0, dtype=np.int32)
    )
    trace_idx: NDArray[np.int32] = field(
        default_factory=lambda: np.zeros(0, dtype=np.int32)
    )
    background: bool = False


@dataclass
class MechanismTraceTable:
    """Mechanism traces on the tick grid of traces(since_tick) (SPEC-P2 2.2.4).

    Units: a_sfa_mv in mV; x_std and xr_std dimensionless; h_inh
    dimensionless. Shapes: each present column is (len(idx), n_ticks).
    Under lif every mechanism column is absent and no monitor exists
    for it.
    """

    idx: NDArray[np.int32]
    tick: NDArray[np.int64]
    a_sfa_mv: NDArray[np.float64] | None = None
    x_std: NDArray[np.float64] | None = None
    xr_std: NDArray[np.float64] | None = None
    h_inh: NDArray[np.float64] | None = None

    def columns(self) -> tuple[str, ...]:
        """Return the names of present mechanism columns. Units: none."""
        names: list[str] = []
        if self.a_sfa_mv is not None:
            names.append("a_sfa_mv")
        if self.x_std is not None:
            names.append("x_std")
        if self.xr_std is not None:
            names.append("xr_std")
        if self.h_inh is not None:
            names.append("h_inh")
        return tuple(names)


class Engine(Protocol):
    """Brian2 whole-brain engine wrapper (SPEC section 3.1).

    Units: thresholds in mV, rates in Hz, ticks in engine ticks,
    refractory periods in ms. Shapes: per-neuron arrays have shape
    (n,) unless stated; per-connection arrays have shape (n_syn,).
    """

    n: int
    n_syn: int
    root_ids: NDArray[np.int64]
    dt_ms: float
    ticks_per_ms: int

    def build(
        self,
        connectome: ConnectomeFiles,
        params: Params,
        topology: InputTopology,
        mechanisms: Mechanisms | None = None,
    ) -> None:
        """Build the network and store("initial"). Units: params carry units. Shapes: none.

        The variant is chosen from mechanisms before any Brian2 object
        exists. None, an omitted argument, or all-null blocks build lif.
        """
        ...

    def seed(self, seed: int) -> None:
        """Seed Brian2 with a uint32 seed. Units: none. Shapes: scalar."""
        ...

    def set_upstream_active(self, bank: int, active: bool) -> None:
        """Switch one bank through the public active flag. Units: none. Shapes: scalars."""
        ...

    def set_input_rates(self, rate_hz: NDArray[np.floating]) -> None:
        """Write extended-mode rates. Units: Hz. Shapes: float array with shape (len(extended_idx),)."""
        ...

    def set_spike_list(
        self, idx: NDArray[np.int32], tick: NDArray[np.int64]
    ) -> None:
        """Write deterministic spike lists. Units: engine ticks. Shapes: idx int32
        with shape (n_events,) subset of spikelist_idx; tick int64 same shape."""
        ...

    def set_threshold(self, v_th_mv: NDArray[np.floating]) -> None:
        """Write per-neuron thresholds. Units: mV. Shapes: float array with shape (n,)."""
        ...

    def set_gain(self, gain: NDArray[np.floating]) -> None:
        """Write per-neuron gains. Units: dimensionless. Shapes: float array with shape (n,)."""
        ...

    def thresholds_mv(self) -> NDArray[np.float64]:
        """Read a copy of current thresholds. Units: mV. Shapes: (n,) float64."""
        ...

    def gains(self) -> NDArray[np.float64]:
        """Read a copy of current gains. Units: dimensionless. Shapes: (n,) float64."""
        ...

    def set_background(self, w_bg_mv: NDArray[np.floating]) -> None:
        """Write per-neuron background weights. Units: mV. Shapes: float array with shape (n,)."""
        ...

    def set_refractory(
        self, idx: NDArray[np.int32], rfc_ms: NDArray[np.floating]
    ) -> None:
        """Write refractory periods of indexed neurons. Units: ms. Shapes: idx int32
        with shape (k,); rfc_ms float with shape (k,)."""
        ...

    def compose_refractory(self) -> None:
        """Write rfc_base everywhere and 0 on active bank targets. Units: ms. Shapes: none."""
        ...

    def disconnect(self, idx: NDArray[np.int32]) -> None:
        """Zero all outgoing weights of indexed neurons. Units: none. Shapes: idx int32 with shape (k,)."""
        ...

    def set_weight_scale(self, scale: NDArray[np.floating]) -> None:
        """Scale every connection weight. Units: dimensionless, 1 is unchanged. Shapes:
        float32 array with shape (n_syn,) in connection file order."""
        ...

    def run_chunk(self, ms: float) -> ChunkResult:
        """Advance the network and return per-chunk counts. Units: ms in, counts in spikes.
        Shapes: ChunkResult with counts shape (n,) and hist_1ms shape ((tick1-tick0)//ticks_per_ms,)."""
        ...

    def tick(self) -> int:
        """Return engine ticks since the last build or restore. Units: ticks. Shapes: scalar."""
        ...

    def store(self, key: str) -> None:
        """Store full state including RNG and monitors. Units: none. Shapes: scalar key."""
        ...

    def restore(self, key: str) -> None:
        """Restore state with RNG and reapply bank activity. Units: none. Shapes: scalar key."""
        ...

    def spikes(self, since_tick: int) -> SpikeTable:
        """Return all spikes at engine ticks >= since_tick. Units: engine ticks.
        Shapes: SpikeTable with idx shape (n_spikes,) and tick shape (n_spikes,)."""
        ...

    def traces(self, since_tick: int) -> TraceTable:
        """Return membrane traces at engine ticks >= since_tick. Units: mV and engine
        ticks. Shapes: TraceTable with idx shape (m,), tick shape (n_time,), v_mv (m, n_time)."""
        ...

    def engine_model(self) -> str:
        """Return the built variant name. Units: none. Shapes: one of lif, lif+sfa, lif+std, lif+cbi."""
        ...

    def model_strings(self) -> tuple[str, str, str, str]:
        """Return the model, threshold, reset and on_pre strings passed to Brian2.

        Units: none. Shapes: four strings.
        """
        ...

    def method(self) -> str:
        """Return the Brian2 integration method. Units: none. Shapes: linear or rk4."""
        ...

    def mechanism_traces(self, since_tick: int) -> MechanismTraceTable:
        """Return mechanism traces on the tick grid of traces(since_tick).

        Units: as MechanismTraceTable. Shapes: columns (len(trace_idx), n_ticks).
        Under lif the table has no columns.
        """
        ...
