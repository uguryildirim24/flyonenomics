#!/usr/bin/env python3
"""Hash-bound exact ticks plus Eon's own active/rate and tolerant timing metrics."""
from __future__ import annotations

import argparse
import importlib
from pathlib import Path

import numpy as np
import pandas as pd

from common import canonical_spikes, load_eon, read_json, save_json, sha, validate_bundle


def exact_metrics(a, b):
    shared = int(len(np.intersect1d(a, b, assume_unique=True)))
    return dict(matches=shared, cpu_spikes=len(a), candidate_spikes=len(b),
                precision=shared / len(b) if len(b) else None,
                recall=shared / len(a) if len(a) else None,
                f1=2 * shared / (len(a) + len(b)) if len(a) + len(b) else None,
                symmetric_difference=len(a) + len(b) - 2 * shared,
                all_spikes_identical=bool(np.array_equal(a, b)),
                definition='one-to-one identical (trial, neuron_index, integer dt tick); F1 is exact spike match rate')


def finite_json(value):
    if isinstance(value, dict):
        return {k: finite_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [finite_json(v) for v in value]
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return None
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--eon-repo', type=Path, required=True)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--tolerance-ms', type=float, default=1.0)
    a = p.parse_args()
    if a.tolerance_ms < 0 or not np.isfinite(a.tolerance_ms):
        p.error('tolerance must be finite and nonnegative')
    load_eon(a.eon_repo)
    m = validate_bundle(a.inputs, a.eon_repo)
    cpu = read_json(a.inputs / 'cpu-run.json')
    other = read_json(a.candidate / 'run.json')
    for run in (cpu, other):
        if run['input_manifest_sha256'] != sha(a.inputs / 'manifest.json'):
            raise ValueError('candidate/reference uses a different input manifest')
        if run['simulated_s'] != m['duration_s']:
            raise ValueError('duration differs')
    paths = [a.inputs / cpu['spike_file'], a.candidate / other['spike_file']]
    for path, run in zip(paths, (cpu, other)):
        if sha(path) != run['spike_sha256']:
            raise ValueError(f'spike checksum mismatch: {path}')
    dfs = [pd.read_parquet(path) for path in paths]
    roots = pd.read_csv(a.eon_repo / 'data/2025_Completeness_783.csv', index_col=0).index.to_numpy(dtype=np.int64)
    keys = []
    for df in dfs:
        keys.append(canonical_spikes(df, m['n_neurons'], m['dt_ms']))
        if not np.array_equal(roots[df.neuron_index.to_numpy(dtype=np.int64)], df.flywire_id.to_numpy(dtype=np.int64)):
            raise ValueError('root ID/index mapping differs')
        if not df.trial.between(0, m['n_run'] - 1).all() or not df.time_ms.between(0, m['duration_s'] * 1000, inclusive='left').all():
            raise ValueError('spike outside configured trial/duration')
    gt_module = importlib.import_module('compare_ground_truth')
    pair_module = importlib.import_module('compare_spike_outputs')
    candidate_key = 'rolf_cuda' if other['backend'] == 'rolf_cuda' else 'adapter_cpu_check'
    pair_module.FRAMEWORKS[candidate_key] = other['backend']
    prepared = []
    for df in dfs:
        df = df.copy()
        df['time_s'] = df.time_ms / 1000
        prepared.append(pair_module.prepare_metrics(df, m['duration_s'], m['n_run']))
    eon_gt = gt_module.compare(*dfs, m['duration_s'], m['n_run'])
    eon_pair = pair_module.compare_pair('brian2cpp', prepared[0], candidate_key, prepared[1],
                                        m['duration_s'], m['n_run'], a.tolerance_ms)
    actual_gpu = other['backend'] == 'rolf_cuda'
    speed = dict(cpu_wall_s_per_simulated_s=cpu['sim_time_s'] / m['duration_s'],
                 cuda_wall_s_per_simulated_s=other['sim_time_s'] / m['duration_s'] if actual_gpu else None,
                 cpu_over_cuda=cpu['sim_time_s'] / other['sim_time_s'] if actual_gpu and other['sim_time_s'] > 0 else None,
                 note='Cross-machine/backend wall-time ratio, not same-hardware speedup. CPU includes executable initialization and internal result writes; CUDA includes per-chunk allocations and host transfers. Build and parquet export excluded from both.')
    output = dict(schema='eon-comparison-v1', input_manifest_sha256=sha(a.inputs / 'manifest.json'),
                  candidate_backend=other['backend'], eon_commit=m['eon_commit'],
                  eon_metric_source_sha256={p: sha(a.eon_repo / 'code' / p) for p in
                                           ('compare_ground_truth.py', 'compare_spike_outputs.py')},
                  exact=exact_metrics(*keys), eon_ground_truth=eon_gt,
                  eon_pairwise=eon_pair, speed=speed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    save_json(a.out, finite_json(output))
    print(a.out.read_text())


if __name__ == '__main__':
    main()
