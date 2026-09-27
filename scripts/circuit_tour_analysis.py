#!/usr/bin/env python3
"""Paired whole-seed analysis and per-cell MaleCNS 3D value arrays; never runs the engine."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from scripts.circuit_tour import SEEDS, GROUPS, KNOCKOUTS, COURTSHIP, conditions  # noqa: E402


def interval(delta):
    """Resample paired entire seeds, never neurons or time bins."""
    x = np.asarray(delta, dtype=np.float64)
    rng = np.random.default_rng(20260925)
    draws = x[rng.integers(0, len(x), size=(10000, len(x)))].mean(axis=1)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(x.mean()), float(lo), float(hi)


def phrase(result, expectation):
    mean, lo, hi = result
    if lo <= 0 <= hi:
        return 'unclear (no detected difference)'
    if expectation == 'up':
        return 'matching' if lo > 0 else 'opposite'
    if expectation == 'down':
        return 'matching' if hi < 0 else 'opposite'
    return 'unclear'  # An expectation of small/local is not a signed pass line.


def analyse(raw: Path, out: Path):
    from flyonenomics.registry import annotations
    raw, out = raw.resolve(), out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows, counts = {}, {}
    provenance = None
    for c in conditions():
        for seed in SEEDS:
            base = raw / f'seed-{seed}-{c}'
            record = json.loads(base.with_suffix('.json').read_text())
            if (record['schema'] != 'circuit-tour-v1' or record['seed'] != seed or record['condition'] != c
                    or (provenance is not None and record['provenance'] != provenance)):
                raise ValueError(f'inconsistent or missing complete result: {base}')
            provenance = record['provenance']
            from flyonenomics.io import hash_file
            if hash_file(base.with_suffix('.npz')) != record['counts_sha256']:
                raise ValueError(f'counts checksum mismatch: {base}')
            with np.load(base.with_suffix('.npz'), allow_pickle=False) as z:
                data = {k.removeprefix('counts_'): z[k] for k in z.files}
            if c == 'control':
                data['measure'] = data['on']+data['off']
            rows[seed,c] = record
            counts[seed,c] = data
    def rates(seed, condition, window):
        return counts[seed,condition][window] / (10 if window=='measure' else 5)
    from flyonenomics.drive.background import group_indices
    from flyonenomics.registry import build_registry
    registry = build_registry('male-cns:v1.0')
    groups = group_indices(registry)
    indices = {**groups, **{g:registry.population(g).idx for g in GROUPS}}
    indices['outside_sensory'] = np.setdiff1d(np.arange(registry.n),groups['sensory'])
    indices['outside_targets'] = np.setdiff1d(np.arange(registry.n),np.concatenate([indices[g] for g in GROUPS]))
    analysis = {'provenance':provenance,'seeds':list(SEEDS),'bootstrap':'10000 paired whole-seed draws; PCG64 seed 20260925','rows':{}}
    lines = ['# Chemical knockout and courtship circuit', '',
             'The model receives injected input; the fly does not see or produce song. Firing in song neurons is not singing.',
             'Differences are paired by whole seed; brackets are 95% bootstrap intervals. A bracket containing zero means no detected difference.',
             '', '## Chemical knockout tour', '', '| Switched off | Outside sensory Δ Hz [95%] | Optic Δ Hz [95%] | Reading |', '|---|---:|---:|---|']
    expectations = {'acetylcholine':'down','gaba':'up','glutamate':'up','histamine':None,
                    'dopamine':None,'octopamine':None,'serotonin':None,'unclear':None}
    for nt in KNOCKOUTS:
        c='off-'+nt
        entry={}
        for k,idx in indices.items():
            delta=[rates(s,c,'measure')[idx].mean()-rates(s,'control','measure')[idx].mean() for s in SEEDS]
            entry[k]=interval(delta)
        # Whole-brain rate distribution, paired silent fraction, median, 99th percentile and max.
        for metric in ('silent_fraction','median_hz','p99_hz','max_hz'):
            entry[metric]=interval([float({'silent_fraction':lambda a:np.mean(a==0),'median_hz':np.median,
                                    'p99_hz':lambda a:np.percentile(a,99),'max_hz':np.max}[metric](rates(s,c,'measure')))
                                    -float({'silent_fraction':lambda a:np.mean(a==0),'median_hz':np.median,
                                    'p99_hz':lambda a:np.percentile(a,99),'max_hz':np.max}[metric](rates(s,'control','measure')))
                                    for s in SEEDS])
        for metric in ('F','b'):
            if all(rows[s,c]['summary']['synchrony'][metric] is not None and rows[s,'control']['summary']['synchrony'][metric] is not None for s in SEEDS):
                entry[metric]=interval([rows[s,c]['summary']['synchrony'][metric]-rows[s,'control']['summary']['synchrony'][metric] for s in SEEDS])
            else:
                entry[metric]=None
        analysis['rows'][c]=entry
        target = 'optic' if nt=='histamine' else 'outside_sensory'
        label=phrase(entry[target],expectations[nt])
        if nt=='histamine':
            label='unclear (no detected difference)' if entry['optic'][1]<=0<=entry['optic'][2] else 'unclear (optic-local response; no signed prediction)'
        if expectations[nt] is None and nt!='histamine':
            label='unclear (no detected difference)' if entry[target][1]<=0<=entry[target][2] else 'unclear (small/local prediction has no signed threshold)'
        def fmt(v): return f'{v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]'
        lines.append(f'| {nt} | {fmt(entry["outside_sensory"])} | {fmt(entry["optic"])} | {label} |')
    lines += ['', '### Whole-brain rate distribution and synchrony', '',
              '| Block | Silent-fraction Δ [95%] | Median Δ Hz [95%] | 99th-percentile Δ Hz [95%] | Maximum Δ Hz [95%] | Fano Δ [95%] | Largest 1 ms spike fraction Δ [95%] |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for nt in KNOCKOUTS:
        e=analysis['rows']['off-'+nt]
        lines.append('| '+nt+' | '+' | '.join(fmt(e[k]) if e[k] is not None else 'not available'
                     for k in ('silent_fraction','median_hz','p99_hz','max_hz','F','b'))+' |')
    lines += ['', '### Twelve drive groups', '',
              '| Block | Group | Rate change Δ Hz [95%] |', '|---|---|---:|']
    for nt in KNOCKOUTS:
        for group in groups:
            lines.append(f'| {nt} | {group} | {fmt(analysis["rows"]["off-"+nt][group])} |')
    lines += ['', '## Courtship circuit', '', '| Drive | Readout ON Δ Hz [95%] | OFF Δ Hz [95%] | Reading |', '|---|---:|---:|---|']
    for c in COURTSHIP:
        entry={}
        for window in ('on','off'):
            entry[window]={k:interval([rates(s,c,window)[idx].mean()-rates(s,'control',window)[idx].mean() for s in SEEDS]) for k,idx in indices.items()}
        entry['first_spike_latency_ms']={g:[rows[s,c]['first_spike_latency_ms'][g] for s in SEEDS] for g in GROUPS}
        analysis['rows'][c]=entry
        song=entry['on']['dPR1']; label=phrase(song,'up' if c!='courtship_random' else None)
        lines.append(f'| {c}: dPR1 | {fmt(song)} | {fmt(entry["off"]["dPR1"])} | {label} |')
        for group in ('P1','pIP10','vPR6','TN1a','TN1c','wing_motor','outside_targets'):
            predicted = 'up' if c.startswith('P1-') or (c=='pIP10' and group in ('pIP10','vPR6','TN1a','TN1c','wing_motor')) else None
            lines.append(f'| {c}: {group} | {fmt(entry["on"][group])} | {fmt(entry["off"][group])} | {phrase(entry["on"][group],predicted)} |')
        latency={k:float(np.median([v for v in entry['first_spike_latency_ms'][k] if v is not None])) if any(v is not None for v in entry['first_spike_latency_ms'][k]) else None for k in GROUPS}
        lines.append(f'First-spike median after ON, 1 ms bins ({c}): '+', '.join(f'{k}={v}' for k,v in latency.items())+'.')
        if c.startswith('P1-'):
            order=[latency[g] for g in ('P1','pIP10','dPR1','wing_motor')]
            lines.append('First-spike order P1 → pIP10 → dPR1 → wing motor: '+
                         ('matching' if all(v is not None for v in order) and order==sorted(order) else 'opposite or unclear (wing motor may fire spontaneously before P1)')+'.')
    # Pairwise specificity and drive ordering use seed-level differences-of-differences.
    for key,a,b in [('P1 medium minus random','P1-medium','courtship_random'),
                    ('P1 high minus low','P1-high','P1-low')]:
        idx=indices['dPR1']
        effect=interval([rates(s,a,'on')[idx].mean()-rates(s,b,'on')[idx].mean() for s in SEEDS])
        analysis['rows'][key]=effect
        lines.append(f'{key}, dPR1 ON: {fmt(effect)} Hz; {phrase(effect,"up")}.')
    lines.append('The five-second OFF mean is recorded; the predicted return **within about one second** is not resolved by these outcome records. Do not treat the full OFF-window mean as a one-second time-to-rest measurement.')
    # Per-neuron signed rate change for ALL simulated neurons; renderer picks its anatomical representatives.
    roots=annotations.load_engine_order('male-cns:v1.0')
    mean={c:np.mean([rates(s,c,'measure' if c.startswith('off-') else 'on')-rates(s,'control','measure' if c.startswith('off-') else 'on') for s in SEEDS],axis=0) for c in conditions() if c!='control'}
    np.savez_compressed(out/'per-neuron-delta-hz.npz',root_ids=roots,**mean)
    (out/'analysis.json').write_text(json.dumps(analysis,indent=2,allow_nan=False)+'\n')
    (out/'report.md').write_text('\n'.join(lines)+'\n')
    from scripts.render_malecns_3d import Assets, CIRCUIT_GROUPS, GROUPS as DISPLAY_GROUPS, main_cache, selected_cells
    DISPLAY_GROUPS.extend(CIRCUIT_GROUPS)
    cells,_=selected_cells(Assets(main_cache()))
    selected=[c['body_id'] for c in cells]
    position={str(root):i for i,root in enumerate(roots)}
    values={'dataset':'male-cns:v1.0','kind':'model','label':'Change in model firing after a chemical block or injected courtship drive',
            'unit':'Hz change from control','summary':'Paired seed mean · model firing, not behaviour',
            'body_ids':selected,'times_s':[0.,1.],
            'conditions':[{'id':c,'label':c.replace('off-','')+' off' if c.startswith('off-') else c.replace('-',' '),
                           'values':[np.round(mean[c][[position[x] for x in selected]],4).tolist()]*2} for c in mean]}
    (out/'paint-values.json').write_text(json.dumps(values,allow_nan=False)+'\n')
    return analysis


if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('usage: circuit_tour_analysis.py <outcomes> <summary>')
    analyse(Path(sys.argv[1]),Path(sys.argv[2]))
