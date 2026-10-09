#!/usr/bin/env python3
"""CPU-only semantic check of the adapted CUDA tick algorithm (not a GPU run).

An independent NumPy implementation checks voltage drive placement, zero
stimulus refractory, delay, SI units, and resets against the actual Eon CPU
spikes. It is neither a replacement ground truth nor a speed benchmark.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import time

import numpy as np
import pandas as pd

from common import environment, load_eon, save_json, sha, validate_bundle


def advance_reference(n, pre, post, weights, targets, events, rfc, delay, si, linear):
    order = np.argsort(pre, kind='stable')
    posts, w = post[order], weights[order]
    offsets = np.r_[0, np.cumsum(np.bincount(pre, minlength=n))]
    v = np.full(n, si['v_0'], dtype=np.float64)
    g = np.zeros(n, dtype=np.float64)
    last = np.full(n, -1000000, dtype=np.int64)
    pending = np.zeros(n, dtype=np.float64)
    ring = [np.zeros(0, dtype=np.int32) for _ in range(delay + 1)]
    ids, ticks = [], []
    for tick, event in enumerate(events):
        oldg = g + pending
        pending.fill(0)
        active = tick - last >= rfc
        v[active] = linear['bias'] + (oldg[active] * linear['coupling'] + v[active] * linear['dv'])
        g = np.where(active, oldg * linear['dg'], oldg)
        fire = active & (v > si['v_th'])
        # PoissonInput runs after thresholds but before reset. Input on a
        # firing neuron is discarded by reset; it cannot fire in the same tick.
        accepted = active[targets] & ~fire[targets]
        v[targets[accepted]] += event[accepted] * si['kick']
        firing = np.flatnonzero(fire).astype(np.int32)
        v[fire], g[fire], last[fire] = si['v_rst'], 0, tick
        ids.append(firing)
        ticks.append(np.full(len(firing), tick, dtype=np.int64))
        ring[tick % len(ring)] = firing
        delayed = ring[(tick + 1) % len(ring)]
        for src in delayed:
            left, right = offsets[src:src + 2]
            dst = posts[left:right]
            allowed = active[dst] & ~fire[dst]
            np.add.at(pending, dst[allowed], w[left:right][allowed])
    return np.concatenate(ids), np.concatenate(ticks)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--eon-repo', required=True, type=Path)
    p.add_argument('--inputs', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    load_eon(a.eon_repo)
    m = validate_bundle(a.inputs, a.eon_repo)
    a.out.mkdir(parents=True, exist_ok=False)
    con = pd.read_parquet(a.eon_repo / 'data/2025_Connectivity_783.parquet')
    comp = pd.read_csv(a.eon_repo / 'data/2025_Completeness_783.csv', index_col=0)
    with np.load(a.inputs / 'stimulus.npz', allow_pickle=False) as z:
        targets, events = z['targets'], z['counts']
    rfc = np.full(len(comp), round(m['neuron_parameters']['t_rfc'] / m['dt_ms']), dtype=np.int32)
    rfc[targets] = 0
    si = {**m['neuron_parameters_si'], 'kick': m['neuron_parameters_si']['w_syn'] * m['neuron_parameters']['f_poi']}
    start = time.perf_counter()
    idx, tick = advance_reference(len(comp), con.Presynaptic_Index.to_numpy(dtype=np.int32),
                                   con.Postsynaptic_Index.to_numpy(dtype=np.int32),
                                   con['Excitatory x Connectivity'].to_numpy(dtype=float) * si['w_syn'],
                                   targets, events, rfc, round(m['neuron_parameters']['t_dly'] / m['dt_ms']),
                                   si, m['linear_coefficients'])
    sim_s = time.perf_counter() - start
    df = pd.DataFrame(dict(trial=0, neuron_index=idx, flywire_id=comp.index.to_numpy(dtype=np.int64)[idx],
                           time_ms=tick * m['dt_ms']))
    df.to_parquet(a.out / 'spikes.parquet', index=False)
    save_json(a.out / 'run.json', dict(backend='numpy_adapter_semantics_only',
                                      input_manifest_sha256=sha(a.inputs / 'manifest.json'),
                                      simulated_s=m['duration_s'], sim_time_s=sim_s,
                                      environment=environment(), spike_file='spikes.parquet',
                                      spike_sha256=sha(a.out / 'spikes.parquet'),
                                      source_sha256=sha(Path(__file__)),
                                      note='Serial accumulation; does not test CUDA compilation, cooperative launch, transfers or atomic reduction ordering. Not a GPU speed result.'))
    print(f'{len(idx)} spikes; {sim_s:.3f}s NumPy semantic check')


if __name__ == '__main__':
    main()
