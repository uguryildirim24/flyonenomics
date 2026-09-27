#!/usr/bin/env python3
"""Spike-time visualisation replays; full per-neuron count equality is mandatory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scripts.circuit_tour import build, pins, MASTER_SEED

CONDITIONS = ('block-0.25', 'block-0.75', 'block-1.00', 'rescue-2.00')


def replay(condition: str, seed: int, outcomes: Path, target: Path, freeze_sha: str, runner_hash: str):
    if seed != 501 or condition not in CONDITIONS:
        raise ValueError('only the four frozen seed-501 dose visualisation replays are permitted')
    source = Path(__file__).with_name('circuit_tour.py')
    if hashlib.sha256(source.read_bytes()).hexdigest() != runner_hash or not freeze_sha:
        raise ValueError('runner differs from the frozen design')
    original = outcomes/f'seed-{seed}-{condition}'
    from flyonenomics.io import hash_file
    recorded = json.loads(Path(str(original)+'.json').read_text())
    if recorded['provenance'] != pins() or hash_file(Path(str(original)+'.npz')) != recorded['counts_sha256']:
        raise ValueError('outcome differs from the frozen state')
    from flyonenomics.orchestrator.seeds import brian_seed
    from flyonenomics.drive.background import group_indices
    from flyonenomics.registry import annotations
    from brian2 import ms
    start = time.perf_counter()
    engine, mod, registry, groups, targets, params = build(condition)
    engine.seed(brian_seed(MASTER_SEED, seed, 0))
    roots = annotations.load_engine_order('male-cns:v1.0')
    frame = annotations.load_dataset_annotations('male-cns:v1.0').set_index('root_id').loc[roots]
    leg = np.flatnonzero((frame['super_class']=='vnc_motor') & frame['cell_sub_class'].isin(('fl','ml','hl'))).astype(np.int32)
    wing = registry.population('wing_motor').idx
    descending = group_indices(registry)['descending']
    selected = np.unique(np.concatenate((wing, leg, descending))).astype(np.int32)
    chunk_ms = float(params.get('engine.chunk_ms'))
    chunk_s = chunk_ms/1000
    counts = np.zeros(registry.n, dtype=np.int32)
    events = []
    for window, duration in (('settle', 2.), ('measure', 10.)):
        engine.set_input_rates(np.zeros(len(targets)))
        for _ in range(round(duration/chunk_s)):
            before = int(engine._spk.num_spikes) if window == 'measure' else 0
            result = engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts,chunk_s)
            composed = mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            if window == 'measure':
                counts += result.counts
                idx = np.asarray(engine._spk.i[before:],dtype=np.int32)
                keep = np.isin(idx, selected)
                ticks = np.rint(np.asarray(engine._spk.t[before:]/ms,dtype=np.float64)[keep]/engine.dt_ms).astype(np.int64)
                events.append((idx[keep],ticks))
    with np.load(Path(str(original)+'.npz'),allow_pickle=False) as raw:
        if not np.array_equal(counts,raw['counts_measure']):
            raise ValueError(f'replay mismatches recorded full-neuron counts: {condition} {seed}')
    ids = np.concatenate([v[0] for v in events])
    ticks = np.concatenate([v[1] for v in events])
    if not np.array_equal(np.bincount(ids,minlength=registry.n)[selected],counts[selected]):
        raise ValueError('selected event totals differ from outcome counts')
    target.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(target, neuron_idx=ids, tick=ticks,
                        wing_idx=wing, leg_idx=leg, descending_idx=descending)
    row = {'kind':'visualisation-aid-not-new-outcome','seed':seed,'condition':condition,
           'freeze_sha':freeze_sha,'runner_sha256':runner_hash,
           'source_outcome_sha256':recorded['counts_sha256'],'spike_file':target.name,
           'spike_sha256':hash_file(target),'dt_ms':engine.dt_ms,
           'groups':{'wing_motor':len(wing),'typed_leg_motor':len(leg),'descending':len(descending)},
           'recorded_full_neuron_counts_equal':True,'selected_event_counts_equal':True,
           'selected_spikes':len(ids),'wall_s':time.perf_counter()-start}
    target.with_suffix('.json').write_text(json.dumps(row,indent=2,allow_nan=False)+'\n')
    return row
