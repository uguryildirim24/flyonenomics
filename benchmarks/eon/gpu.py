#!/usr/bin/env python3
"""Replay captured Eon drive on Rolf's CUDA engine. Requires a CUDA GPU."""
from __future__ import annotations

import argparse
from pathlib import Path
import time

import numpy as np
import pandas as pd

from common import ROOT, environment, load_eon, save_json, sha, validate_bundle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--eon-repo', required=True, type=Path)
    p.add_argument('--inputs', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--chunk-ms', type=int, default=10)
    a = p.parse_args()
    load_eon(a.eon_repo)
    m = validate_bundle(a.inputs, a.eon_repo)
    if m['experiment']['key'] != 'sugar' or m['n_run'] != 1 or m['experiment']['neu_slnc']:
        raise ValueError('first adapter supports sugar, one trial, no silencing only')
    duration_ms = round(m['duration_s'] * 1000)
    if a.chunk_ms < 1 or duration_ms % a.chunk_ms:
        p.error('chunk-ms must be positive and divide the duration')
    with np.load(a.inputs / 'stimulus.npz', allow_pickle=False) as z:
        targets, events = z['targets'], z['counts']
        target_ids = z['flywire_ids']
    a.out.mkdir(parents=True, exist_ok=False)
    from adapter import EonCUDAEngine, KERNEL_PATH, kernel_source
    start = time.perf_counter()
    engine = EonCUDAEngine(record_spikes=True)
    engine.seed(m['seed'])
    engine.build_eon(a.eon_repo.resolve(), m, targets, events)
    if engine.n != m['n_neurons'] or engine.n_syn != m['n_edges']:
        raise ValueError('network size changed')
    if not np.array_equal(engine.root_ids[targets], target_ids):
        raise ValueError('stimulus neuron order differs')
    build_s = time.perf_counter() - start
    cp = engine.cp
    frames = []
    stepping_s, extraction_s, device_s = 0., 0., 0.
    for _ in range(duration_ms // a.chunk_ms):
        begin, end = cp.cuda.Event(), cp.cuda.Event()
        before = time.perf_counter()
        begin.record()
        chunk = engine.run_chunk(a.chunk_ms)
        end.record()
        end.synchronize()
        stepping_s += time.perf_counter() - before
        device_s += cp.cuda.get_elapsed_time(begin, end) / 1000
        before = time.perf_counter()
        spikes = engine.spikes(chunk.tick0)
        frames.append((spikes.idx, spikes.tick))
        extraction_s += time.perf_counter() - before
    idx = np.concatenate([x[0] for x in frames])
    tick = np.concatenate([x[1] for x in frames])
    df = pd.DataFrame(dict(trial=np.zeros(len(idx), dtype=np.int32), neuron_index=idx,
                           flywire_id=engine.root_ids[idx], time_ms=tick * engine.dt_ms,
                           t=tick * engine.dt_ms / 1000, exp_name='rolf_cuda_eon'))
    before = time.perf_counter()
    df.to_parquet(a.out / 'spikes.parquet', index=False, compression='brotli')
    save_s = time.perf_counter() - before
    import hashlib
    sources = ['benchmarks/eon/adapter.py', 'benchmarks/eon/gpu.py',
               'src/flyonenomics/engine/cuda_engine.py', 'src/flyonenomics/engine/cuda_tick.cu']
    result = dict(backend='rolf_cuda', input_manifest_sha256=sha(a.inputs / 'manifest.json'),
                  eon_commit=m['eon_commit'], simulated_s=m['duration_s'],
                  spikes=len(df), active_neurons=int(df.flywire_id.nunique()),
                  sim_time_s=stepping_s, wall_s_per_simulated_s=stepping_s / m['duration_s'],
                  build_s=build_s, extraction_s=extraction_s, parquet_save_s=save_s,
                  total_harness_s=time.perf_counter()-start, cuda_event_interval_s=device_s,
                  timing_note='sim_time includes run_chunk allocations, kernel and device-to-host transfers; excludes spikes() sorting and parquet writes. CUDA event interval is not kernel-only.',
                  chunk_ms=a.chunk_ms, spike_file='spikes.parquet', spike_sha256=sha(a.out / 'spikes.parquet'),
                  source_sha256={s: sha(ROOT / s) for s in sources},
                  adapted_kernel_sha256=hashlib.sha256(kernel_source().encode()).hexdigest(),
                  environment={**environment(), 'cupy': cp.__version__,
                               'gpu': cp.cuda.runtime.getDeviceProperties(0)['name'].decode(),
                               'cuda_runtime': cp.cuda.runtime.runtimeGetVersion(),
                               'cuda_driver': cp.cuda.runtime.driverGetVersion()})
    save_json(a.out / 'run.json', result)
    print(result)


if __name__ == '__main__':
    main()
