"""GPU dopamine pool/parameter composition at the reference 10 ms cadence.

Initial state and all kinetic/receptor parameters come from existing Neuromod
objects. No new calibration, equations or manipulation semantics live here.
"""
from pathlib import Path
import numpy as np
from flyonenomics.io import read_text


class CUDADopamine:
    def __init__(self, engine, mods, params):
        cp = engine.cp
        self.engine, self.mods, self.cp = engine, mods, cp
        self.n, self.batch, self.nc = engine.n, engine.batch, len(mods[0].da_c)
        if len(mods) != self.batch:
            raise ValueError('one Neuromod per batch member')
        self.period_ms = float(params.get('engine.chunk_ms'))
        self.elapsed_ms = 0.
        self.accum = cp.zeros((self.batch, self.n), dtype=cp.int32)
        self.da = cp.asarray(np.stack([m.da_c for m in mods]))
        m, w = mods[0].m, mods[0].w
        self.m = tuple(cp.asarray(a) for a in (m.indptr.astype(np.int32), m.indices.astype(np.int32), m.data.astype(np.float64)))
        self.w = tuple(cp.asarray(a) for a in (w.indptr.astype(np.int32), w.indices.astype(np.int32), w.data.astype(np.float64)))
        self.mask = cp.asarray(mods[0].mask, dtype=cp.uint8)
        self.exposed = cp.asarray(mods[0].exposed, dtype=cp.uint8)
        self.refresh_parameters()
        self.pool_constants = tuple(np.float64(x) for x in (self.period_ms / 1000,
                                                            params.get('da.k_ns'), params.get('da.DA_ref')))
        self.compose_constants = tuple(np.float64(x) for x in (
            params.get('rec.Kd_D1'), params.get('rec.Kd_D2'), params.get('rec.dV_D1'), params.get('rec.dV_D2'),
            params.get('rec.gamma_D1'), params.get('rec.gamma_D2'), *params.get('rec.vth_clip'),
            *params.get('rec.gain_clip'), params.get('engine.silence_vth')))
        self.module = cp.RawModule(code=read_text(Path(__file__).with_suffix('.cu')),
                                   options=('--std=c++17', '--fmad=false'))
        self.pool_kernel = self.module.get_function('pools')
        self.compose_kernel = self.module.get_function('compose')
        # Compile both before build timing ends, not during the first chunk.
        self.pool_kernel.compile()
        self.compose_kernel.compile()

    def refresh_parameters(self):
        """Upload current genotype/drug parameters without resetting GPU pools.

        Call after changing the host Neuromod objects (e.g. advance_slow).
        Connectivity/exposure and all batch members' registries must be shared.
        """
        cp = self.cp
        def stack(name):
            return cp.asarray(np.stack([getattr(m, name) for m in self.mods]))
        self.alpha = stack('alpha')
        self.source = cp.asarray(np.stack([m.s_c * m._retained_dan_fraction() for m in self.mods]))
        kinetics = [m._kinetics() for m in self.mods]
        self.vmax = cp.asarray(np.stack([k[0] for k in kinetics]))
        self.km = cp.asarray(np.stack([k[1] for k in kinetics]))
        self.rel = cp.asarray([k[2] for k in kinetics], dtype=cp.float64)
        self.r1, self.r2, self.base = stack('r1'), stack('r2'), stack('base_v_th')
        self.shift, self.geno_gain = stack('shift'), stack('geno_gain')
        self.silenced = stack('silenced').astype(cp.uint8)
        self.enabled = cp.asarray([m.layers.dopamine_A for m in self.mods], dtype=cp.uint8)
        self.clamped = cp.asarray([m.clamped for m in self.mods], dtype=cp.uint8)

    def advance(self, counts, ms):
        if ms > self.period_ms or abs(round(self.period_ms / ms) * ms - self.period_ms) > 1e-9:
            raise ValueError('GPU chunks must divide the dopamine update period')
        if ms == self.period_ms:
            source = counts
        else:
            self.accum += counts
            source = self.accum
        self.elapsed_ms += ms
        if self.elapsed_ms + 1e-9 < self.period_ms:
            return
        self.elapsed_ms = 0.
        dims = tuple(np.int32(x) for x in (self.n, self.nc, self.batch))
        self.pool_kernel(((self.batch*self.nc+127)//128,), (128,),
                         (self.da, source, *self.m, self.alpha, self.source, self.vmax, self.km, self.rel,
                          self.mask, self.clamped, *dims, *self.pool_constants))
        self.compose_kernel(((self.batch*self.n+255)//256,), (256,),
                            (self.da, self.engine.threshold, self.engine.gain, *self.w, self.exposed,
                             self.r1, self.r2, self.base, self.shift, self.geno_gain, self.silenced,
                             self.enabled, *dims, *self.compose_constants))
        if ms != self.period_ms:
            self.accum.fill(0)

    def pools_host(self):
        """Return current batched dopamine pools in µM; synchronizes the stream."""
        return self.cp.asnumpy(self.da)
