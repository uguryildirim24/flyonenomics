"""MIT adapter for the existing cooperative CUDAEngine (no Eon code).

Only the benchmark subclass changes semantics. Production CUDAEngine and its
kernel remain untouched. Source substitutions target Rolf's own MIT kernel
and fail closed if it changes.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

from common import ROOT
sys.path.insert(0, str(ROOT / 'src'))
from flyonenomics.engine.cuda_engine import CUDAEngine
from flyonenomics.types import ConnectomeFiles, Params
from flyonenomics.engine.base import InputTopology
from flyonenomics.connectome_arrays import load_connectome_arrays

KERNEL_PATH = ROOT / 'src/flyonenomics/engine/cuda_tick.cu'


def kernel_source():
    source = KERNEL_PATH.read_text()
    replacements = [
        ('double dt_s, double ext_weight) {',
         'double dt_s, double ext_weight, const int* refractory_ticks, double v_bias) {'),
        ('bool active = tick - last[j] >= refractory;',
         'bool active = tick - last[j] >= refractory_ticks[i];'),
        ('vn = v0 + (vn - v0) * dv + oldg * coupling;',
         'vn = v_bias + (oldg * coupling + vn * dv);'),
        ('gn += bg_events[(long long)(tick - bg_event_start) * bg_event_width + target] * bg[i];',
         'vn += bg_events[(long long)(tick - bg_event_start) * bg_event_width + target] * ext_weight;'),
        ('tick - last[dst] >= refractory)',
         'tick - last[dst] >= refractory_ticks[post[e]])'),
    ]
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError(f'MIT CUDA kernel changed: expected unique {old!r}')
        source = source.replace(old, new)
    return source


class _Kernel:
    def __init__(self, raw, engine):
        self.raw, self.engine = raw, engine

    def __call__(self, grid, block, args):
        self.raw(grid, block, (*args, self.engine.eon_refractory, np.float64(self.engine.eon_bias)))


class EonCUDAEngine(CUDAEngine):
    def build_eon(self, repo: Path, manifest, targets, events):
        p = manifest['neuron_parameters']
        params = Params(version='eon-bench', data=dict(
            lif={**{k: p[k] for k in ('v_0', 'v_rst', 'v_th', 't_mbr', 'tau', 't_rfc', 't_dly', 'w_syn')},
                 'dt': manifest['dt_ms']}, input={'f_poi': p['f_poi']},
            # CUDAEngine.build reads bg.r_bg even when background is disabled.
            bg={'n_bg': 0, 'r_bg': 0.0}))
        empty = np.zeros(0, dtype=np.int32)
        topology = InputTopology(extended_idx=empty)
        files = ConnectomeFiles(repo / 'data/2025_Completeness_783.csv',
                               repo / 'data/2025_Connectivity_783.parquet', '783')
        super().build(files, params, topology)
        si = manifest['neuron_parameters_si']
        linear = manifest['linear_coefficients']
        # Brian2 works in SI volts. Recompute from raw edge weights rather than
        # scaling mV products, which would change float64 rounding.
        _, _, _, raw = load_connectome_arrays(files.completeness, files.connectivity)
        cp = self.cp
        self.weights = cp.asarray((np.asarray(raw) * si['w_syn'])[self.order])
        self.v0, self.vreset = si['v_0'], si['v_rst']
        self.v.fill(self.v0)
        self.threshold.fill(si['v_th'])
        self.ext_weight = si['w_syn'] * p['f_poi']
        self.dv, self.dg, self.coupling = (linear[k] for k in ('dv', 'dg', 'coupling'))
        self.eon_bias = linear['bias']
        rfc = np.full(self.n, round(p['t_rfc'] / self.dt_ms), dtype=np.int32)
        rfc[targets] = 0
        self.eon_refractory = cp.asarray(rfc)
        # Safe recording bound: stimulated neurons can spike on every tick.
        self.refractory = 1
        order = np.argsort(targets)
        self.set_background_events(np.asarray(targets)[order], np.asarray(events)[:, order], 0)
        source = kernel_source()
        self.module = cp.RawModule(code=source, options=('--std=c++17', '--fmad=false'),
                                   enable_cooperative_groups=True)
        raw_kernel = self.module.get_function('advance')
        from cupy.cuda import driver
        occupancy = driver.occupancyMaxActiveBlocksPerMultiprocessor(raw_kernel.kernel.ptr, self.threads, 0)
        if occupancy < 1:
            raise RuntimeError('cooperative kernel cannot be resident')
        self.blocks = cp.cuda.Device().attributes['MultiProcessorCount'] * occupancy
        self.capacity = __import__('math').ceil(self.batch * self.n / (self.blocks * self.threads)) * self.threads
        self.ring_ids = cp.empty((self.delay + 1, self.blocks, self.capacity), dtype=cp.int32)
        self.ring_counts = cp.zeros((self.delay + 1, self.blocks), dtype=cp.int32)
        self.kernel = _Kernel(raw_kernel, self)
        cp.cuda.get_current_stream().synchronize()
