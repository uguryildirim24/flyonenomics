#!/usr/bin/env python3
"""Four read-only visualisation replays, with exact full-neuron outcome count checks.

The run is identical to frozen circuit_tour.worker; only P1/pIP10/song/wing spike
indices and ticks are saved. Not a new outcome or a new design condition.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import numpy as np

from scripts.circuit_tour import build, pins, MASTER_SEED, GROUPS, DRIVE_HZ


def replay(condition: str, seed: int, outcomes: Path, target: Path, freeze_sha: str, runner_hash: str):
    if seed not in (501,502) or condition not in ('control','P1-high'):
        raise ValueError('only four frozen-condition visualisation replays are permitted')
    source = Path(__file__).with_name('circuit_tour.py')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=runner_hash:
        raise ValueError('simulation runner differs from the frozen code')
    if not freeze_sha or pins()['substrate']!='rest:ed9b0a469d7a6b77':
        raise ValueError('frozen state unavailable')
    original = outcomes/f'seed-{seed}-{condition}'
    from flyonenomics.io import hash_file
    recorded=json.loads(original.with_suffix('.json').read_text())
    if (recorded['provenance']!=pins() or hash_file(original.with_suffix('.npz'))!=recorded['counts_sha256']):
        raise ValueError('recorded outcome differs from frozen state')
    from flyonenomics.orchestrator.seeds import brian_seed
    from brian2 import ms
    start=time.perf_counter()
    engine,mod,registry,groups,targets,params=build(condition)
    engine.seed(brian_seed(MASTER_SEED,seed,0))
    selected=np.unique(np.concatenate([registry.population(g).idx for g in GROUPS])).astype(np.int32)
    chunk_ms=float(params.get('engine.chunk_ms'))
    chunk_s=chunk_ms/1000
    counts={'on':np.zeros(registry.n,dtype=np.int32),'off':np.zeros(registry.n,dtype=np.int32)}
    events={'on':[],'off':[]}
    for window,duration in (('settle',2.),('on',5.),('off',5.)):
        rates=np.zeros(len(targets))
        if window=='on' and condition=='P1-high':
            rates[np.isin(targets,registry.population('P1').idx)]=DRIVE_HZ[2]
        engine.set_input_rates(rates)
        for _ in range(round(duration/chunk_s)):
            before=int(engine._spk.num_spikes) if window!='settle' else 0
            result=engine.run_chunk(chunk_ms)
            mod.on_chunk(result.counts,chunk_s)
            composed=mod.compose()
            engine.set_threshold(composed.v_th)
            engine.set_gain(composed.gain)
            if window!='settle':
                counts[window]+=result.counts
                idx=np.asarray(engine._spk.i[before:],dtype=np.int32)
                keep=np.isin(idx,selected)
                ticks=np.rint(np.asarray(engine._spk.t[before:]/ms,dtype=np.float64)[keep]/engine.dt_ms).astype(np.int64)
                events[window].append((idx[keep],ticks))
    with np.load(original.with_suffix('.npz'),allow_pickle=False) as raw:
        for window in ('on','off'):
            if not np.array_equal(counts[window],raw[f'counts_{window}']):
                raise ValueError(f'replay mismatches recorded full-neuron {window} counts: {condition} {seed}')
    target.parent.mkdir(parents=True,exist_ok=True)
    data={}
    for window in ('on','off'):
        data[f'{window}_idx']=np.concatenate([v[0] for v in events[window]])
        data[f'{window}_tick']=np.concatenate([v[1] for v in events[window]])
        # In addition, every selected neuron's event total must agree with full-neuron counts.
        if not np.array_equal(np.bincount(data[f'{window}_idx'],minlength=registry.n)[selected],counts[window][selected]):
            raise ValueError(f'selected spike event total differs: {window}')
    np.savez_compressed(target,**data)
    row={'kind':'visualisation-aid-not-new-outcome','seed':seed,'condition':condition,'freeze_sha':freeze_sha,
         'runner_sha256':runner_hash,'source_outcome_sha256':recorded['counts_sha256'],
         'spike_file':target.name,'spike_sha256':hash_file(target),'dt_ms':engine.dt_ms,
         'populations':list(GROUPS),'recorded_full_neuron_on_off_counts_equal':True,
         'spike_counts':{w:int(len(data[f'{w}_idx'])) for w in ('on','off')},
         'wall_s':time.perf_counter()-start}
    target.with_suffix('.json').write_text(json.dumps(row,indent=2,allow_nan=False)+'\n')
    return row
