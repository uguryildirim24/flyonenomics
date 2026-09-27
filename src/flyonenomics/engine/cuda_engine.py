"""Batched CUDA LIF engine alongside (not a replacement for) BrianEngine.

CuPy is a GPU-only optional dependency. State/weights use float64. A cooperative
CUDA kernel performs an entire chunk, with no host synchronization per tick.
Only plain LIF, per-neuron background, and extended PoissonGroup input are
supported. Spike recording is chunk-local and opt-in; counts are always kept.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple
import math

import numpy as np

from flyonenomics.connectome_arrays import base_weight_memmap, load_connectome_arrays
from flyonenomics.engine.brian_engine import resolve_connectome_path
from flyonenomics.engine.models import resolve_engine_model
from flyonenomics.types import SpikeTable
from flyonenomics.io import read_text


class CUDAChunk(NamedTuple):
    tick0: int
    tick1: int
    counts: np.ndarray  # int32 (batch, n)
    hist_1ms: np.ndarray  # int32 (batch, chunk_ms)
    first: np.ndarray  # first tick in this chunk per neuron, -1 if absent


class CUDAEngine:
    def __init__(self, batch: int = 1, *, record_spikes: bool = False):
        import cupy as cp
        if batch < 1:
            raise ValueError('batch must be positive')
        self.cp, self.batch, self.record_spikes = cp, batch, record_spikes
        self.tick_index = 0
        self.modulator = None
        self.seed(0)

    def seed(self, seeds: int | list[int]) -> None:
        values = [seeds] * self.batch if isinstance(seeds, (int, np.integer)) else seeds
        if len(values) != self.batch or any(not 0 <= int(s) < 2**32 for s in values):
            raise ValueError('one uint32 seed per batch member required')
        self.seeds = self.cp.asarray(values, dtype=self.cp.uint32)

    def build(self, connectome, params, topology, mechanisms=None) -> None:
        cp = self.cp
        if (resolve_engine_model(mechanisms) != 'lif' or topology.upstream_banks
                or topology.spikelist_idx.size or topology.trace_idx.size):
            raise ValueError('CUDA supports plain LIF, background and extended input only')
        comp = resolve_connectome_path(connectome.completeness)
        con = resolve_connectome_path(connectome.connectivity)
        roots, pre, post, exc = load_connectome_arrays(comp, con)
        self.root_ids, self.n, self.n_syn = roots, len(roots), len(pre)
        self.order = np.argsort(pre, kind='stable')
        self.base_w = base_weight_memmap(exc, float(params.get('lif.w_syn')), comp, con)
        self.offsets = cp.asarray(np.r_[0, np.cumsum(np.bincount(pre, minlength=self.n))].astype(np.int32))
        self.post = cp.asarray(np.asarray(post[self.order], dtype=np.int32))
        self.set_weight_scale(np.ones(self.n_syn, dtype=np.float32))
        self.dt_ms = float(params.get('lif.dt'))
        self.ticks_per_ms = round(1 / self.dt_ms)
        self.delay = round(float(params.get('lif.t_dly')) / self.dt_ms)
        self.refractory = int((float(params.get('lif.t_rfc')) + 1e-3 * self.dt_ms) / self.dt_ms)
        if self.delay < 1 or self.refractory < 1 or abs(self.ticks_per_ms * self.dt_ms - 1) > 1e-12:
            raise ValueError('CUDA requires positive tick-grid delay/refractory and dt dividing 1 ms')
        self.v0, self.vreset = float(params.get('lif.v_0')), float(params.get('lif.v_rst'))
        tm, tg = float(params.get('lif.t_mbr')), float(params.get('lif.tau'))
        self.dv, self.dg = np.exp(-self.dt_ms / tm), np.exp(-self.dt_ms / tg)
        self.coupling = tg / (tm - tg) * (self.dv - self.dg)
        self.bg_n = int(params.get('bg.n_bg')) if topology.background else 0
        self.bg_p = float(params.get('bg.r_bg')) * self.dt_ms / 1000
        if not 0 <= self.bg_p < 1 or self.bg_n * self.bg_p > 5:
            raise ValueError('CUDA background supports the exact small-mean Brian binomial path')
        self.ext_weight = float(params.get('lif.w_syn')) * float(params.get('input.f_poi'))
        self.ext_idx = np.asarray(topology.extended_idx, dtype=np.int32)
        shape = (self.batch, self.n)
        self.v = cp.full(shape, self.v0, dtype=cp.float64)
        self.g = cp.zeros(shape, dtype=cp.float64)
        self.incoming = cp.zeros_like(self.g)
        self.last = cp.full(shape, -1000000, dtype=cp.int32)
        self.threshold = cp.full(shape, float(params.get('lif.v_th')), dtype=cp.float64)
        self.gain = cp.ones_like(self.g)
        self.bg = cp.zeros(self.n, dtype=cp.float64)
        self.bg_event_index = cp.full(self.n, -1, dtype=cp.int32)
        self.bg_events = cp.zeros(1, dtype=cp.uint8)
        self.bg_event_start = self.bg_event_end = self.bg_event_width = 0
        self.rates = cp.zeros_like(self.g)
        self.keep = cp.ones(shape, dtype=cp.uint8)
        self.module = cp.RawModule(code=read_text(Path(__file__).with_name('cuda_tick.cu')),
                                   options=('--std=c++17', '--fmad=false'),
                                   enable_cooperative_groups=True)
        self.kernel = self.module.get_function('advance')
        from cupy.cuda import driver
        self.threads = 256
        occupancy = driver.occupancyMaxActiveBlocksPerMultiprocessor(self.kernel.kernel.ptr, self.threads, 0)
        self.blocks = cp.cuda.Device().attributes['MultiProcessorCount'] * occupancy
        self.capacity = math.ceil(self.batch * self.n / (self.blocks * self.threads)) * self.threads
        self.ring_ids = cp.empty((self.delay + 1, self.blocks, self.capacity), dtype=cp.int32)
        self.ring_counts = cp.zeros((self.delay + 1, self.blocks), dtype=cp.int32)
        self.background_path = 'per-neuron-string' if topology.background else 'absent'
        self._chunk = None
        cp.cuda.get_current_stream().synchronize()

    def engine_model(self):
        return 'lif'

    def _per_neuron(self, values):
        a = np.broadcast_to(np.asarray(values, dtype=np.float64), (self.batch, self.n))
        if not np.isfinite(a).all():
            raise ValueError('per-neuron values must be finite')
        return self.cp.asarray(np.ascontiguousarray(a))

    def set_threshold(self, values):
        self.threshold = self._per_neuron(values)

    def set_gain(self, values):
        self.gain = self._per_neuron(values)

    def set_background(self, values):
        a = np.asarray(values, dtype=np.float64)
        if a.shape != (self.n,) or not np.isfinite(a).all():
            raise ValueError('background must be finite with shape (n,)')
        self.bg = self.cp.asarray(a)

    def set_background_events(self, targets, counts, tick0: int):
        """Replace random background with a shared, explicit tick-by-target stream.

        Counts are uint8 binomial multiplicities, not currents. Each event adds
        count * the existing per-target background weight at the synapses stage,
        subject to the same refractory rejection as random input. All batch
        members receive this stream. Every subsequent chunk must be covered;
        there is no random fallback at the end of the uploaded window.
        """
        idx, values = np.asarray(targets), np.asarray(counts)
        if (idx.ndim != 1 or not np.issubdtype(idx.dtype, np.integer)
                or len(idx) == 0 or np.any(idx < 0) or np.any(idx >= self.n)
                or np.any(np.diff(idx.astype(np.int64)) <= 0)):
            raise ValueError('background event targets must be sorted unique neuron indices')
        if values.dtype != np.uint8 or values.ndim != 2 or values.shape[1] != len(idx) or not len(values):
            raise ValueError('background event counts must be nonempty uint8 (ticks, targets)')
        if not isinstance(tick0, (int, np.integer)) or tick0 < 0:
            raise ValueError('background event start must be a nonnegative integer tick')
        mapping = np.full(self.n, -1, dtype=np.int32)
        mapping[idx] = np.arange(len(idx), dtype=np.int32)
        self.bg_event_index = self.cp.asarray(mapping)
        self.bg_events = self.cp.asarray(np.ascontiguousarray(values))
        self.bg_event_start, self.bg_event_end = int(tick0), int(tick0) + len(values)
        self.bg_event_width = len(idx)

    def set_weight_scale(self, scale):
        a = np.asarray(scale, dtype=np.float32)
        if a.shape != (self.n_syn,) or not np.isfinite(a).all():
            raise ValueError('scale must be finite with shape (n_syn,)')
        self.weights = self.cp.asarray((self.base_w * a.astype(np.float64))[self.order])
        if hasattr(self, 'keep'):
            self.keep.fill(1)  # Brian rewrites all weights, including disconnected edges.

    def disconnect(self, idx):
        self.keep[:, np.asarray(idx, dtype=np.int32)] = 0

    def set_disconnections(self, indices):
        if len(indices) != self.batch:
            raise ValueError('one disconnect index array per batch member')
        self.keep.fill(1)
        for b, idx in enumerate(indices):
            self.keep[b, np.asarray(idx, dtype=np.int32)] = 0

    def compose_refractory(self):
        # No upstream banks: the unchanged rest refractory applies everywhere.
        return None

    def set_input_rates(self, rates):
        a = np.broadcast_to(np.asarray(rates, dtype=np.float64), (self.batch, len(self.ext_idx)))
        if not np.isfinite(a).all() or np.any(a < 0):
            raise ValueError('input rates must be finite and nonnegative')
        self.rates.fill(0)
        self.rates[:, self.ext_idx] = self.cp.asarray(np.ascontiguousarray(a))

    def run_chunk(self, ms: float) -> CUDAChunk:
        cp = self.cp
        steps = round(ms / self.dt_ms)
        if steps <= 0 or abs(steps * self.dt_ms - ms) > 1e-9 or steps % self.ticks_per_ms:
            raise ValueError('chunk duration must contain whole milliseconds')
        if self.modulator is not None and (ms > self.modulator.period_ms or
                abs(round(self.modulator.period_ms / ms) * ms - self.modulator.period_ms) > 1e-9):
            raise ValueError('chunk duration must divide the dopamine update period')
        if self.bg_event_width and not (self.bg_event_start <= self.tick_index and
                                       self.tick_index + steps <= self.bg_event_end):
            raise ValueError('chunk is not covered by the explicit background event window')
        shape = (self.batch, self.n)
        # One transfer/synchronization for the three always-returned arrays.
        count_size, hist_size = self.batch * self.n, self.batch * (steps // self.ticks_per_ms)
        packed = cp.empty(2 * count_size + hist_size, dtype=cp.int32)
        counts = packed[:count_size].reshape(shape)
        hist = packed[count_size:count_size + hist_size].reshape(self.batch, -1)
        first = packed[count_size + hist_size:].reshape(shape)
        counts.fill(0)
        hist.fill(0)
        first.fill(-1)
        spike_ticks = cp.empty((math.ceil(steps / self.refractory), *shape) if self.record_spikes else (1,), dtype=cp.int32)
        args = (self.v, self.g, self.incoming, self.last, self.threshold, self.gain, self.bg,
                self.rates, self.keep, self.seeds, self.offsets, self.post, self.weights,
                self.ring_ids, self.ring_counts, counts, hist, first, spike_ticks,
                self.bg_event_index, self.bg_events,
                np.int32(self.bg_event_width), np.int32(self.bg_event_start),
                *(np.int32(x) for x in (self.record_spikes, self.n, self.batch, self.delay + 1,
                                       self.capacity, self.tick_index, steps, self.ticks_per_ms, self.refractory)),
                *(np.float64(x) for x in (self.dv, self.dg, self.coupling, self.v0, self.vreset)),
                np.int32(self.bg_n), *(np.float64(x) for x in (self.bg_p, (1-self.bg_p)**self.bg_n,
                                                             self.dt_ms / 1000, self.ext_weight)))
        self.kernel((self.blocks,), (self.threads,), args)
        if self.modulator is not None:
            self.modulator.advance(counts, ms)
        start = self.tick_index
        self.tick_index += steps
        host = cp.asnumpy(packed)
        result = CUDAChunk(start, self.tick_index, host[:count_size].reshape(shape),
                           host[count_size:count_size + hist_size].reshape(self.batch, -1),
                           host[count_size + hist_size:].reshape(shape))
        self._chunk = result
        self._spike_ticks = cp.asnumpy(spike_ticks) if self.record_spikes else None
        return result

    def tick(self):
        return self.tick_index

    def spikes(self, since_tick: int, batch: int = 0) -> SpikeTable:
        if self._chunk is None or self._spike_ticks is None:
            raise RuntimeError('enable record_spikes before building; recording is chunk-local')
        if since_tick < self._chunk.tick0:
            raise ValueError('spikes before the most recent chunk are not retained')
        k, idx = np.nonzero(np.arange(len(self._spike_ticks))[:, None] < self._chunk.counts[batch])
        ticks = self._spike_ticks[k, batch, idx].astype(np.int64)
        order = np.argsort(ticks, kind='stable')
        order = order[ticks[order] >= since_tick]
        return SpikeTable(idx=idx[order].astype(np.int32), tick=ticks[order])
