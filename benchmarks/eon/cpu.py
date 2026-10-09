#!/usr/bin/env python3
"""Call pinned Eon CPU runner, then observe and save its actual Poisson drive.

No upstream code is copied, rewritten or vendored. The only runtime hook seeds
Brian and adds two read-only voltage monitors around PoissonInput. A separate
unobserved run verifies that observation has not changed any spike.
"""
from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
import pandas as pd

from common import DATA_FILES, PIN, canonical_spikes, environment, load_eon, save_json, sha


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--eon-repo', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--seed', type=int, default=501)
    p.add_argument('--duration', type=float, choices=(0.1, 1.0), default=0.1)
    p.add_argument('--compile-jobs', type=int, default=2)
    a = p.parse_args()
    if not 0 <= a.seed < 2**32 or a.compile_jobs < 1:
        p.error('seed must be uint32 and compile-jobs positive')
    a.out.mkdir(parents=True, exist_ok=False)
    import brian2 as b
    if b.__version__ != '2.8.0':
        raise ValueError('CPU ground truth requires Eon Brian2 2.8.0')
    bench, runner = load_eon(a.eon_repo)
    b.defaultclock.dt = 0.1 * b.ms
    b.prefs.devices.cpp_standalone.extra_make_args_unix = [f'-j{a.compile_jobs}']
    original = runner.add_poisson_inputs
    captured = {}
    logger = bench.BenchmarkLogger()
    config = bench.get_experiment('sugar')
    os_env = __import__('os').environ
    os_env.pop('FLY_BRAIN_DISABLE_SPIKE_IO', None)
    started = time.perf_counter()
    runs = {}
    for observed in (False, True):
        def inputs(neu, exc, exc2, params):
            b.seed(a.seed)  # after standalone reinit; before run/code generation
            pois = original(neu, exc, exc2, params)
            if not observed:
                return pois
            before = b.StateMonitor(neu, 'v', record=exc, when='synapses', order=-2,
                                    name='capture_before')
            after = b.StateMonitor(neu, 'v', record=exc, when='synapses', order=2,
                                   name='capture_after')
            captured.update(before=before, after=after, targets=np.asarray(exc, dtype=np.int32))
            return [*pois, before, after]
        runner.add_poisson_inputs = inputs
        label = 'captured' if observed else 'unobserved'
        # Distinct scratch build/output labels; no upstream source edits.
        runner.output_dir = a.out.resolve() / f'build-{label}'
        result = runner.run_single_benchmark(a.duration, 1, False, config, logger,
                                            run_label=f'eon-mit-{a.seed}-{label}', round_idx=1)
        if result['status'] != 'success':
            save_json(a.out / f'failure-{label}.json', result)
            raise RuntimeError(result['status'])
        shutil.copyfile(result['spike_path'], a.out / f'cpu-{label}.parquet')
        runs[label] = result
    runner.add_poisson_inputs = original
    comp = pd.read_csv(bench.path_comp, index_col=0)
    n = len(comp)
    plain = pd.read_parquet(a.out / 'cpu-unobserved.parquet')
    observed = pd.read_parquet(a.out / 'cpu-captured.parquet')
    equal = np.array_equal(canonical_spikes(plain, n, .1), canonical_spikes(observed, n, .1))
    if not equal:
        raise RuntimeError('capture monitors changed CPU output')
    kick = float(runner.default_params['w_syn'] * runner.default_params['f_poi'] / b.mV)
    increments = np.asarray((captured['after'].v - captured['before'].v) / b.mV).T
    counts = np.rint(increments / kick).astype(np.uint8)
    if np.any(counts > 1) or not np.allclose(increments, counts * kick, atol=1e-9, rtol=0):
        raise RuntimeError('unexpected voltage increment: not N=1 PoissonInput')
    expected_ticks = round(a.duration * 1000 / .1)
    if counts.shape != (expected_ticks, len(config['neu_exc'])):
        raise RuntimeError('stimulus capture shape differs')
    np.savez_compressed(a.out / 'stimulus.npz', counts=counts, targets=captured['targets'],
                        flywire_ids=comp.index.to_numpy(dtype=np.int64)[captured['targets']])
    numeric = {k: float(runner.default_params[k] / unit) for k, unit in
               [('v_0', b.mV), ('v_rst', b.mV), ('v_th', b.mV), ('t_mbr', b.ms),
                ('tau', b.ms), ('t_rfc', b.ms), ('t_dly', b.ms), ('w_syn', b.mV)]}
    numeric['f_poi'] = float(runner.default_params['f_poi'])
    # Store SI values without a divide/multiply round trip through mV/ms.
    si = {k: float(runner.default_params[k]) for k in numeric if k != 'f_poi'}
    dt_s = float(b.defaultclock.dt)
    tm, tg = si['t_mbr'], si['tau']
    dv, dg = math.exp(-dt_s / tm), math.exp(-dt_s / tg)
    # Exact integral of the decaying synaptic drive, factored to align with
    # Brian's linear solver; these are numeric model facts, not upstream code.
    coupling = ((tg / (tm - tg) * (math.exp(dt_s / tg) - math.exp(dt_s / tm))) * dv) * dg
    linear = dict(dv=dv, dg=dg, coupling=coupling, bias=si['v_0'] - si['v_0'] * dv)
    manifest = dict(schema='eon-identical-input-v1', created_utc=datetime.now(timezone.utc).isoformat(),
                    eon_commit=PIN, connectome='FlyWire v783', experiment=config,
                    dt_ms=.1, duration_s=a.duration, n_run=1, seed=a.seed,
                    seed_note='Brian seed set after device reinit; CUDA replays actual draws, not another RNG',
                    neuron_parameters=numeric, neuron_parameters_si=si, linear_coefficients=linear,
                    n_neurons=n,
                    n_edges=len(pd.read_parquet(bench.path_con)),
                    stimulus_events=int(counts.sum()), kick_mv=kick,
                    capture_verified_exact_spikes=equal,
                    data_sha256={name: sha(a.eon_repo / 'data' / name) for name in DATA_FILES},
                    files_sha256={name: sha(a.out / name) for name in
                                  ('stimulus.npz', 'cpu-unobserved.parquet', 'cpu-captured.parquet')})
    save_json(a.out / 'manifest.json', manifest)
    meta = dict(backend='brian2cpp', input_manifest_sha256=sha(a.out / 'manifest.json'),
                environment={**environment(), 'brian2': b.__version__},
                spikes=len(plain), active_neurons=int(plain.flywire_id.nunique()),
                simulated_s=a.duration, sim_time_s=runs['unobserved']['timings']['simulation_total'],
                capture_sim_time_s=runs['captured']['timings']['simulation_total'],
                wall_s_per_simulated_s=runs['unobserved']['timings']['simulation_total'] / a.duration,
                timing_note='Eon device.run wall time; includes executable initialization and internal result writes',
                runs=runs, total_harness_s=time.perf_counter()-started,
                spike_file='cpu-unobserved.parquet', spike_sha256=sha(a.out / 'cpu-unobserved.parquet'))
    save_json(a.out / 'cpu-run.json', meta)
    from importlib.metadata import distributions
    import sysconfig
    # setuptools can expose vendored dist-info on sys.path after Brian imports;
    # only actual environment packages belong in a reinstallable freeze.
    installed = distributions(path=[sysconfig.get_path('purelib')])
    lock = '\n'.join(sorted(f'{d.metadata["Name"]}=={d.version}' for d in installed)) + '\n'
    (a.out / 'environment.txt').write_text(lock)
    print(meta)


if __name__ == '__main__':
    main()
