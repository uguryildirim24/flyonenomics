#!/usr/bin/env python3
"""Frozen chemical knockout and courtship run (SPEC-P2 158-159).

The simulation takes injected Poisson input; the fly does not see, sing, or move.
Only `check` may run before the dated design freeze. `worker` is called on Modal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
SEEDS = tuple(range(501, 511))
KNOCKOUTS = ('acetylcholine', 'gaba', 'glutamate', 'histamine', 'dopamine', 'octopamine', 'serotonin', 'unclear')
COURTSHIP = ('P1-low', 'P1-medium', 'P1-high', 'pIP10', 'courtship_random')
GROUPS = ('P1', 'pIP10', 'dPR1', 'vPR6', 'TN1a', 'TN1c', 'wing_motor')
# Populated by the P1-only manipulation check, before the design freeze.
DRIVE_HZ = (10.0, 30.0, 60.0)
MASTER_SEED = 20260912
BLOCK = ('0.10', '0.25', '0.50', '0.75', '0.90', '1.00')
BOOST = ('0.25', '0.50', '1.00', '2.00')
RESCUE = ('0.50', '1.00', '2.00')


def dose_conditions():
    return (*(f'block-{v}' for v in BLOCK), *(f'boost-{v}' for v in BOOST),
            *(f'rescue-{v}' for v in RESCUE))


def conditions():
    return ('control', *(f'off-{nt}' for nt in KNOCKOUTS), *COURTSHIP)


def dose_scales(condition):
    if condition.startswith('block-'):
        return 1.0 - float(condition.split('-')[1]), 1.0
    if condition.startswith('boost-'):
        return 1.0 + float(condition.split('-')[1]), 1.0
    if condition.startswith('rescue-'):
        return 0.25, 1.0 + float(condition.split('-')[1])
    return 1.0, 1.0


def pins():
    from flyonenomics.drive.mechanisms import substrate_id_for
    from flyonenomics.io import hash_file
    files = ('data/drive-male-cns-v1.0.yaml', 'data/dopamine-male-cns-v1.0.yaml',
             'data/params-v0.2.yaml', 'data/populations-male-cns-v1.0.yaml',
             'data/transmitters-male-cns-v1.0.yaml')
    substrate = substrate_id_for(ROOT / files[0])
    if substrate != 'rest:ed9b0a469d7a6b77':
        raise ValueError(f'rest substrate changed: {substrate}')
    return {'substrate': substrate, 'files_sha256': {f: hash_file(ROOT / f) for f in files}}


def build(condition, engine=None):
    from flyonenomics.connectome_arrays import load_connectome_arrays
    from flyonenomics.datasets import get_dataset_adapter
    from flyonenomics.drive.background import group_indices
    from flyonenomics.drive.mechanisms import mechanisms_from_drive
    from flyonenomics.drive.rest import apply_rest_substrate, load_drive_rest, load_dopamine_v02, rest_background_weights
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.registry import build_registry
    from flyonenomics.substrate.transmitters import load_transmitters
    from flyonenomics.types import LayerFlags, load_params

    registry = build_registry('male-cns:v1.0')
    params = load_params(ROOT / 'data/params-v0.2.yaml')
    drive = load_drive_rest(ROOT / 'data/drive-male-cns-v1.0.yaml')
    dopamine = load_dopamine_v02(ROOT / 'data/dopamine-male-cns-v1.0.yaml',
                                  [c.name for c in registry.compartments()])
    files = get_dataset_adapter('male-cns:v1.0').connectome_files()
    _, pre, post, signed = load_connectome_arrays(files.completeness, files.connectivity)
    classes = np.asarray(load_transmitters(ROOT / 'data/transmitters-male-cns-v1.0.yaml')['class_array'])
    kc = np.zeros(registry.n, dtype=np.uint8)
    kc[registry.population('KC').idx] = 1
    targets = np.unique(np.concatenate([registry.population(x).idx for x in ('P1', 'pIP10', 'courtship_random')])).astype(np.int32)
    engine = BrianEngine() if engine is None else engine
    engine.seed(MASTER_SEED)
    engine.build(files, params, InputTopology(background=True, extended_idx=targets),
                 mechanisms=mechanisms_from_drive(drive, registry=registry))
    base, baseline_scale = apply_rest_substrate(engine, params, drive, classes=classes,
                                    s_pq=np.sign(np.asarray(signed, dtype=np.float64)),
                                    pre=np.asarray(pre, dtype=np.int32), post=np.asarray(post, dtype=np.int32),
                                    kc_mask=kc, n=registry.n, connectome_version='male-cns:v1.0')
    if condition in dose_conditions():
        # Preserve the pinned rest substrate and its verified scale hash. Apply
        # receptor occupancy only after the baseline has been bound to the engine.
        gaba, glu = dose_scales(condition)
        modified = baseline_scale.copy()
        row_classes = classes[np.asarray(pre, dtype=np.int32)]
        modified[row_classes == 'GABA'] *= gaba
        modified[row_classes == 'Glu'] *= glu
        engine.set_weight_scale(modified)
    engine.set_background(rest_background_weights(registry, drive, params))
    dopamine_on = condition != 'off-dopamine'
    mod = Neuromod(registry, params,
                   LayerFlags(background=True, dopamine_A=dopamine_on, transporter_C=dopamine_on),
                   dopamine if dopamine_on else None, base_v_th=base, schema_version='1.3',
                   drive_groups=group_indices(registry))
    mod.clamp_pools(False)
    mod.reset_fast()
    composed = mod.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)
    engine.compose_refractory()
    if condition.startswith('off-'):
        label = condition.removeprefix('off-')
        # Consensus annotation, NOT the engine's grouped signed-weight class.
        from flyonenomics.registry import annotations as ann
        table = ann.load_dataset_annotations('male-cns:v1.0').set_index('root_id')
        roots = ann.load_engine_order('male-cns:v1.0')
        labels = table.loc[roots, 'top_nt'].fillna('unclear').to_numpy()
        idx = np.flatnonzero(labels == label).astype(np.int32)
        if not len(idx):
            raise ValueError(f'empty knockout {label}')
        engine.disconnect(idx)
    return engine, mod, registry, group_indices(registry), targets, params


def worker(condition: str, seed: int, dest: Path, *, check_s: float | None = None,
           reproduction: bool = False):
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.validation.artefacts import FanoAccumulator
    if condition not in (*conditions(), *dose_conditions()) or seed not in SEEDS:
        raise ValueError('unplanned seed or condition')
    if check_s is not None and condition != 'control':
        raise ValueError('short build check must be control only')
    if reproduction and (seed != 501 or condition not in ('control', 'block-1.00')):
        raise ValueError('pre-freeze reproduction is limited to control and zero GABA, seed 501')
    provenance = pins()
    started = time.perf_counter()
    engine, mod, registry, groups, targets, params = build(condition)
    engine.seed(brian_seed(MASTER_SEED, seed, 0))
    chunk_ms = float(params.get('engine.chunk_ms'))
    chunk_s = chunk_ms / 1000
    if check_s is not None:
        windows = (('check', check_s),)
    elif condition.startswith('off-') or condition in dose_conditions():
        windows = (('settle', 2.0), ('measure', 10.0))
    else:
        windows = (('settle', 2.0), ('on', 5.0), ('off', 5.0))
    names = list(groups) + list(GROUPS) + ['outside_sensory', 'outside_targets']
    indices = {k: np.asarray(v, dtype=np.int32) for k, v in groups.items()}
    indices.update({k: registry.population(k).idx for k in GROUPS})
    indices['outside_sensory'] = np.setdiff1d(np.arange(registry.n), groups['sensory']).astype(np.int32)
    indices['outside_targets'] = np.setdiff1d(np.arange(registry.n), np.concatenate([registry.population(k).idx for k in GROUPS])).astype(np.int32)
    counts = {w: np.zeros(registry.n, dtype=np.int32) for w, _ in windows if w != 'settle'}
    fano = FanoAccumulator(registry.n, params)
    first = {k: None for k in GROUPS}
    # Brian monitor is read only for the circuit's first spike in the ON window.
    first_indices = {k: set(map(int, indices[k])) for k in GROUPS}
    on_bins = {k: [] for k in GROUPS}
    for window, duration in windows:
        rates = np.zeros(len(targets), dtype=np.float64)
        if window == 'on' and condition in COURTSHIP:
            population = 'P1' if condition.startswith('P1-') else condition
            hz = DRIVE_HZ[('P1-low', 'P1-medium', 'P1-high').index(condition)] if condition.startswith('P1-') else DRIVE_HZ[1]
            rates[np.isin(targets, registry.population(population).idx)] = hz
        engine.set_input_rates(rates)
        for _ in range(round(duration / chunk_s)):
            before = int(engine._spk.num_spikes) if window == 'on' else 0
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts, chunk_s)
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            if window != 'settle':
                counts[window] += result.counts
                fano.add(result.hist_1ms)
            if window == 'on':
                spike_idx = np.asarray(engine._spk.i[before:], dtype=np.int32)
                spike_ms = np.asarray(engine._spk.t[before:] / __import__('brian2').ms, dtype=float)
                for group in GROUPS:
                    matching = np.fromiter((i in first_indices[group] for i in spike_idx), dtype=bool, count=len(spike_idx))
                    if matching.any() and first[group] is None:
                        first[group] = int(np.floor(spike_ms[matching].min() - 2000))
                    on_bins[group].append(int(result.counts[indices[group]].sum()))
    dest.parent.mkdir(parents=True, exist_ok=True)
    # One archive per seed/condition; never overwrite a completed task.
    arrays = {f'counts_{w}': v for w, v in counts.items()}
    np.savez_compressed(dest, **arrays)
    from flyonenomics.io import hash_file
    stats = {}
    for w, duration in windows:
        if w == 'settle':
            continue
        c = counts[w]
        rates = c / duration
        stats[w] = {'group_hz': {k: float(rates[idx].mean()) for k, idx in indices.items()},
                    'silent_fraction': float(np.mean(c == 0)), 'median_hz': float(np.median(rates)),
                    'p99_hz': float(np.percentile(rates, 99)), 'max_hz': float(rates.max())}
    sync = fano.report()
    stats['synchrony'] = dict(F=sync['F'], b=sync['max_bin_fraction'])
    row = dict(schema='circuit-tour-v1', seed=seed, condition=condition, provenance=provenance,
               windows=windows, group_sizes={k: len(idx) for k, idx in indices.items()},
               summary=stats, first_spike_latency_ms=first, on_group_chunk_counts=on_bins,
               chunk_s=chunk_s, counts_file=dest.name, counts_sha256=hash_file(dest),
               wall_s=time.perf_counter()-started)
    dest.with_suffix('.json').write_text(json.dumps(row, indent=2, allow_nan=False)+'\n')
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('check', 'worker', 'reproduce'))
    p.add_argument('--condition', default='control')
    p.add_argument('--seed', type=int, default=501)
    p.add_argument('--seconds', type=float, default=.2)
    p.add_argument('--dest', type=Path, required=True)
    a = p.parse_args()
    if a.mode == 'check' and (a.condition != 'control' or not (0 < a.seconds <= .2)):
        p.error('build checks are control-only, up to 0.2 brain-seconds')
    if a.mode == 'reproduce' and (a.seed != 501 or a.condition not in ('control', 'block-1.00')):
        p.error('reproduction is control/zero GABA on seed 501 only')
    print(json.dumps(worker(a.condition, a.seed, a.dest,
                            check_s=a.seconds if a.mode == 'check' else None,
                            reproduction=a.mode == 'reproduce')['summary']), flush=True)


if __name__ == '__main__':
    main()
