"""Flushed NDJSON live windows sampled only from the independent LIVE stream."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np
from flyonenomics.types import Params, SpikeTable

# SPEC-P2 section 7: additive fields under live_version 2.
LIVE_VERSION = 2


def open_loop_block(probe_params: Any, t_s: float, params: Params) -> tuple[int | None, str | None]:
    """Current open-loop block index and stimulus label at recording time t_s; (None, None) otherwise.

    Mirrors the arena's chunk-start block rule (behaviour/arena.py): the blocks
    walk picks the first block whose cumulative transition_s + dwell_s exceeds
    t_s, else the last block; the azimuths form steps one period per azimuth.
    Units: seconds. Shapes: scalars.
    """
    blocks = getattr(probe_params, "blocks", None)
    if blocks:
        elapsed = 0.0
        for index, block in enumerate(blocks):
            elapsed += block.transition_s + block.dwell_s
            if t_s < elapsed:
                return index, block.stimulus
        return len(blocks) - 1, blocks[-1].stimulus
    from flyonenomics.schema.experiment import OpenLoopParams

    if not isinstance(probe_params, OpenLoopParams):
        return None, None
    # Same fallback as the arena: an empty or omitted list uses openloop.azimuths.
    azimuths = probe_params.azimuths or params.get("openloop.azimuths")
    if azimuths:
        period = params.get("openloop.transition_s") + params.get("openloop.dwell_s")
        return min(int(t_s / period), len(azimuths) - 1), "stripe"
    return None, None


class LiveStream:
    """One probe's live writer; relative ticks/ms, whole-network and per-population counts."""
    def __init__(self, path: Path, rng: np.random.Generator, params: Params, populations: dict[str, np.ndarray], start_tick: int, dt_ms: float, enabled: bool = True) -> None:
        """Open a probe stream; ticks/ms, population indices (m,), RNG LIVE only."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("w")
        self.rng, self.populations, self.start_tick, self.dt_ms = rng, populations, start_tick, dt_ms
        self.every_ms = params.get("live.every_ms")
        self.sample = params.get("live.spike_sample")
        self.enabled = enabled
        self.counts = dict.fromkeys(populations, 0)
        self.sizes = {name: int(len(idx)) for name, idx in populations.items()}
        self.all_count = 0
        self.last_tick = start_tick
        self.window_ms = 0.0
        self.pending: tuple[int, Any, np.ndarray, dict[str, float], int | None, str | None] | None = None

    def maybe_emit(self, counts: np.ndarray, tick: int, spikes: Any, da: np.ndarray, arena: dict[str, float],
                   block: int | None = None, stimulus: str | None = None) -> bool:
        """Accumulate counts (n,) and flush a due window; ticks/ms, DA (0,) in WP4."""
        if not self.enabled:
            return False
        for name, idx in self.populations.items():
            self.counts[name] += int(counts[idx].sum())
        self.all_count += int(counts.sum())
        self.window_ms = (tick - self.last_tick) * self.dt_ms
        self.pending = (tick, spikes, da, arena, block, stimulus)
        if self.window_ms < self.every_ms:
            return False
        return self._emit()

    def _emit(self) -> bool:
        """Write one window line from the pending chunk; units ticks/ms/counts."""
        tick, spikes, da, arena, block, stimulus = self.pending
        events: SpikeTable = spikes(self.last_tick)
        n = min(self.sample, len(events.idx))
        take = np.sort(self.rng.choice(len(events.idx), size=n, replace=False)) if n else np.zeros(0, dtype=np.int64)
        line = {"live_version": LIVE_VERSION, "tick": tick - self.start_tick, "t_ms": (tick - self.start_tick) * self.dt_ms,
                "window_ms": self.window_ms, "counts": self.counts, "all_count": self.all_count, "sizes": self.sizes,
                "block": block, "stimulus": stimulus,
                "spikes": [[int(events.idx[i]), int(events.tick[i] - self.start_tick)] for i in take],
                "da": da.tolist(), "arena": arena}
        self.handle.write(json.dumps(line, allow_nan=False) + "\n")
        self.handle.flush()
        self.counts = dict.fromkeys(self.populations, 0)
        self.all_count = 0
        self.window_ms = 0.0
        self.last_tick = tick
        return True

    def close(self, flush: bool = True) -> None:
        """Flush a short final window when one is pending, then close; units none.

        flush False (a failed probe) writes no final window. The handle is
        closed even when the flush raises.
        """
        try:
            if flush and self.enabled and self.pending is not None and self.window_ms > 0:
                self._emit()
        finally:
            self.handle.close()
