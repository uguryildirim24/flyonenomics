"""CUDA replay of the frozen rest/tour designs; Brian2 analysis format unchanged."""
from __future__ import annotations

import json
import time
from pathlib import Path
import numpy as np

from scripts.circuit_tour import (COURTSHIP, DRIVE_HZ, GROUPS, MASTER_SEED, SEEDS,
                                  build, conditions, dose_conditions, pins)
from flyonenomics.drive.rest import load_dopamine_v02
from flyonenomics.engine.cuda_engine import CUDAEngine
from flyonenomics.neuromod.state import Neuromod
from flyonenomics.orchestrator.seeds import brian_seed
from flyonenomics.registry import annotations as ann
from flyonenomics.types import LayerFlags
from flyonenomics.io import hash_file
from flyonenomics.validation.artefacts import FanoAccumulator

ROOT = Path(__file__).resolve().parents[1]


def run(tasks: list[tuple[int, str]], dest: Path, *, seconds: float | None = None,
        rest: bool = False, chunk_ms: float | None = None, check_modulation: bool = False) -> dict:
    allowed_seeds = range(1, 11) if rest else SEEDS
    if not tasks or any(s not in allowed_seeds or c not in (*conditions(), *dose_conditions()) for s, c in tasks):
        raise ValueError('unplanned condition or seed')
    dose = any(c in dose_conditions() for _, c in tasks)
    if dose and len({c for _, c in tasks}) != 1:
        raise ValueError('dose weights are shared: one condition per batch required')
    if rest and any(c != 'control' for _, c in tasks):
        raise ValueError('item 155 is clamped control only')
    if seconds is not None and not 0 < seconds <= 12:
        raise ValueError('pilot seconds must be in (0,12]')
    started = time.perf_counter()
    # Reuse the Brian2 dose builder's exact baseline/row-class composition.
    # It sets shared weights before the per-member disconnections below.
    gpu, initial, registry, groups, targets, params = build(tasks[0][1] if dose else 'control', CUDAEngine(len(tasks)))
    dopamine = load_dopamine_v02(ROOT / 'data/dopamine-male-cns-v1.0.yaml',
                                 [c.name for c in registry.compartments()])
    table = ann.load_dataset_annotations('male-cns:v1.0').set_index('root_id')
    labels = table.loc[ann.load_engine_order('male-cns:v1.0'), 'top_nt'].fillna('unclear').to_numpy()
    mods, disconnected = [], []
    for _, condition in tasks:
        on = condition != 'off-dopamine'
        mod = Neuromod(registry, params, LayerFlags(background=True, dopamine_A=on, transporter_C=on),
                       dopamine if on else None, base_v_th=initial.base_v_th,
                       schema_version='1.3', drive_groups=groups)
        mod.clamp_pools(rest)
        mod.reset_fast()
        mods.append(mod)
        disconnected.append(np.flatnonzero(labels == condition.removeprefix('off-')).astype(np.int32)
                            if condition.startswith('off-') else np.zeros(0, dtype=np.int32))
    gpu.set_disconnections(disconnected)
    gpu.seed([brian_seed(MASTER_SEED, seed, 0) for seed, _ in tasks])
    composed = [m.compose() for m in mods]
    gpu.set_threshold(np.stack([c.v_th for c in composed]))
    gpu.set_gain(np.stack([c.gain for c in composed]))
    indices = {**groups, **{g: registry.population(g).idx for g in GROUPS}}
    indices['outside_sensory'] = np.setdiff1d(np.arange(registry.n), groups['sensory'])
    indices['outside_targets'] = np.setdiff1d(np.arange(registry.n), np.concatenate([indices[g] for g in GROUPS]))
    pool_ms = float(params.get('engine.chunk_ms'))
    chunk_ms = pool_ms if chunk_ms is None else chunk_ms
    if chunk_ms <= 0 or abs(round(pool_ms / chunk_ms) * chunk_ms - pool_ms) > 1e-9:
        raise ValueError('engine chunks must divide the frozen dopamine cadence')
    if seconds is None and chunk_ms != pool_ms:
        raise ValueError('outcome recording cadence is frozen at engine.chunk_ms')
    chunks_per_pool = round(pool_ms / chunk_ms)
    pool_counts = np.zeros((len(tasks), registry.n), dtype=np.int32) if check_modulation and chunks_per_pool > 1 else None
    chunk_number = 0
    modulation_errors = dict(pool_um=0., threshold_mv=0., gain=0.)
    if not rest:
        from flyonenomics.engine.cuda_dopamine import CUDADopamine
        gpu.modulator = CUDADopamine(gpu, mods, params)
    chunk_s = chunk_ms / 1000
    windows = [('settle', 2.), ('on', 5.), ('off', 5.)]
    if rest or dose:
        windows = [('settle', 2.), ('measure', 10.)]
    if seconds is not None:
        windows = [('pilot', seconds)]
    if any(abs(round(d / chunk_s) * chunk_s - d) > 1e-9 for _, d in windows):
        raise ValueError('windows must contain whole chunks')
    counts = {w: np.zeros((len(tasks), registry.n), dtype=np.int32) for w, _ in windows if w != 'settle'}
    fanos = [FanoAccumulator(registry.n, params) for _ in tasks]
    first = [{g: None for g in GROUPS} for _ in tasks]
    on_bins = [{g: [] for g in GROUPS} for _ in tasks]
    gpu.cp.cuda.get_current_stream().synchronize()
    built_s = time.perf_counter() - started
    print(json.dumps({'event': 'built', 'seconds': built_s, 'batch': len(tasks), 'synapses': gpu.n_syn}), flush=True)
    kernel_s, mod_s, collect_s = 0., 0., 0.
    for window, duration in windows:
        rates = np.zeros((len(tasks), len(targets)), dtype=np.float64)
        if window == 'on':
            for b, (_, condition) in enumerate(tasks):
                if condition in COURTSHIP:
                    population = 'P1' if condition.startswith('P1-') else condition
                    hz = DRIVE_HZ[('P1-low', 'P1-medium', 'P1-high').index(condition)] if condition.startswith('P1-') else DRIVE_HZ[1]
                    rates[b, np.isin(targets, registry.population(population).idx)] = hz
        gpu.set_input_rates(rates)
        for _ in range(round(duration / chunk_s)):
            t = time.perf_counter()
            result = gpu.run_chunk(chunk_ms)
            kernel_s += time.perf_counter() - t
            t = time.perf_counter()
            chunk_number += 1
            if check_modulation and not rest:
                if pool_counts is not None:
                    pool_counts += result.counts
                if chunk_number % chunks_per_pool == 0:
                    mod_counts = result.counts if pool_counts is None else pool_counts
                    for b, mod in enumerate(mods):
                        mod.on_chunk(mod_counts[b], pool_ms / 1000)
                    composed = [m.compose() for m in mods]
                    for key, actual, expected in (
                        ('pool_um', gpu.modulator.pools_host(), np.stack([m.da_c for m in mods])),
                        ('threshold_mv', gpu.cp.asnumpy(gpu.threshold), np.stack([c.v_th for c in composed])),
                        ('gain', gpu.cp.asnumpy(gpu.gain), np.stack([c.gain for c in composed]))):
                        modulation_errors[key] = max(modulation_errors[key], float(np.max(np.abs(actual - expected))))
                    if pool_counts is not None:
                        pool_counts.fill(0)
            mod_s += time.perf_counter() - t
            t = time.perf_counter()
            if window != 'settle':
                counts[window] += result.counts
                for b, fano in enumerate(fanos):
                    fano.add(result.hist_1ms[b])
            if window == 'on':
                for b in range(len(tasks)):
                    for g in GROUPS:
                        ticks = result.first[b, indices[g]]
                        if first[b][g] is None and np.any(ticks >= 0):
                            first[b][g] = int(np.floor(ticks[ticks >= 0].min() * gpu.dt_ms - 2000))
                        on_bins[b][g].append(int(result.counts[b, indices[g]].sum()))
            collect_s += time.perf_counter() - t
        print(json.dumps({'event': 'window', 'window': window, 'elapsed_s': time.perf_counter()-started,
                          'spikes': int(sum(x.sum() for x in counts.values()))}), flush=True)
    gpu.cp.cuda.get_current_stream().synchronize()
    stepping_s = time.perf_counter() - started - built_s
    dest.mkdir(parents=True, exist_ok=True)
    summaries = []
    for b, (seed, condition) in enumerate(tasks):
        if rest or dose or seconds is not None:
            named = {w: c[b] for w, c in counts.items()}
        else:
            named = {'measure': counts['on'][b] + counts['off'][b]} if condition.startswith('off-') else {
                'on': counts['on'][b], 'off': counts['off'][b]}
        suffix = f'-member-{b}' if seconds is not None else ''
        path = dest / f'seed-{seed}-{condition}{suffix}.npz'
        np.savez_compressed(path, **{f'counts_{k}': v for k, v in named.items()})
        summary = {}
        for w, c in named.items():
            duration = seconds if w == 'pilot' else 10 if w == 'measure' else 5
            rates = c / duration
            summary[w] = {'group_hz': {k: float(rates[idx].mean()) for k, idx in indices.items()},
                          'silent_fraction': float(np.mean(c == 0)), 'median_hz': float(np.median(rates)),
                          'p99_hz': float(np.percentile(rates, 99)), 'max_hz': float(rates.max())}
        fano = fanos[b].report()
        summary['synchrony'] = {'F': fano['F'], 'b': fano['max_bin_fraction']}
        actual_windows = [('settle', 2.), ('measure', 10.)] if condition.startswith('off-') and seconds is None else windows
        row = {'schema': 'circuit-tour-v1', 'seed': seed, 'condition': condition, 'provenance': pins(),
               'windows': actual_windows, 'group_sizes': {k: len(v) for k, v in indices.items()},
               'summary': summary, 'first_spike_latency_ms': first[b], 'on_group_chunk_counts': on_bins[b],
               'chunk_s': chunk_s, 'counts_file': path.name,
               'counts_sha256': hash_file(path),
               'backend': 'cuda-cooperative-f64', 'dopamine': 'clamped' if rest else 'free',
               'cuda_source_sha256': {str(p.relative_to(ROOT)): hash_file(p)
                                      for p in (Path(__file__), ROOT / 'src/flyonenomics/engine/cuda_engine.py',
                                                ROOT / 'src/flyonenomics/engine/cuda_tick.cu',
                                                ROOT / 'src/flyonenomics/engine/cuda_dopamine.py',
                                                ROOT / 'src/flyonenomics/engine/cuda_dopamine.cu')},
               'wall_s': time.perf_counter()-started}
        path.with_suffix('.json').write_text(json.dumps(row, indent=2, allow_nan=False) + '\n')
        summaries.append(summary)
    simulated_s = sum(x[1] for x in windows)
    result = {'batch': len(tasks), 'simulated_s': simulated_s, 'build_s': built_s,
              'stepping_s': stepping_s, 'kernel_and_transfer_s': kernel_s, 'neuromod_s': mod_s,
              'collection_s': collect_s, 'wall_s': time.perf_counter()-started,
              'wall_s_per_sim_s': stepping_s / simulated_s,
              'per_brain_wall_s_per_sim_s': stepping_s / (len(tasks) * simulated_s),
              'gpu': gpu.cp.cuda.runtime.getDeviceProperties(0)['name'].decode(),
              'blocks': gpu.blocks, 'registers': gpu.kernel.num_regs, 'chunk_ms': chunk_ms,
              'dopamine_chunk_ms': pool_ms,
              'modulation_check_max_abs': modulation_errors if check_modulation else None,
              'gpu_memory_pool_bytes': gpu.cp.get_default_memory_pool().total_bytes(),
              'summaries': summaries}
    (dest / 'timing.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
