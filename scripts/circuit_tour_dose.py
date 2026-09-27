#!/usr/bin/env python3
"""Analyse frozen GABA-class dose runs against the item 158 paired control."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from scripts.circuit_tour import SEEDS, BLOCK, BOOST, RESCUE, dose_conditions, pins  # noqa: E402
from scripts.circuit_tour_analysis import interval  # noqa: E402

REFERENCE = Path('<local-project-root>/.worktrees/t-0114/camber-runs/circuit-tour/outcomes')
OUTCOMES = ROOT / 'camber-runs/circuit-tour/dose-outcomes'
SUMMARY = ROOT / 'camber-runs/circuit-tour/dose-summary'


def fit(x, y, baseline):
    """Fit signed saturating Hill response; return None if parameters hit limits."""
    x = np.asarray(x, dtype=float)
    d = np.asarray(y, dtype=float) - baseline
    sign = 1 if d[-1] >= 0 else -1
    maximum = max(float(np.max(np.abs(d))), 1.e-8)
    try:
        result = least_squares(lambda p: sign*p[0]*x**p[2]/(p[1]**p[2]+x**p[2])-d,
                               [maximum*1.5, float(np.median(x)), 1.],
                               bounds=([0, .005, .15], [maximum*100, 40., 8.]),
                               max_nfev=150)
    except (ValueError, FloatingPointError):
        return None
    a, half, slope = result.x
    if (not result.success or a < 1e-5 or half <= .0051 or half >= 39.9
            or slope <= .151 or slope >= 7.99):
        return None
    return float(half), float(slope), float(a*sign)


def curve(x, baseline, p):
    if p is None:
        return None
    half, slope, amplitude = p
    return baseline + amplitude * x**slope/(half**slope+x**slope)


def bootstrap_fits(x, matrix, baseline):
    """Resample whole seed columns across all doses, including control."""
    observed = fit(x, matrix.mean(axis=1), baseline.mean())
    rng = np.random.default_rng(20260926)
    draws = []
    for _ in range(500):
        sample = rng.integers(0, len(SEEDS), len(SEEDS))
        p = fit(x, matrix[:,sample].mean(axis=1), baseline[sample].mean())
        if p is not None:
            draws.append(p)
    if observed is None or len(draws) < 475:
        return {'identifiable': False, 'reason':'fit at boundary or unstable across whole-seed resamples',
                'valid_draws': len(draws)}
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    if hi[0] > x.max():
        return {'identifiable': False, 'reason':'half-effect interval extends beyond sampled occupancy range',
                'half_effect_extrapolated':[observed[0],lo[0],hi[0]],
                'slope_conditional':[observed[1],lo[1],hi[1]],'valid_draws':len(draws)}
    return {'identifiable': True, 'half_effect': [observed[0], lo[0], hi[0]],
            'slope': [observed[1], lo[1], hi[1]],
            'amplitude': [observed[2], lo[2], hi[2]], 'valid_draws':len(draws)}


def empirical_half(x, y, baseline):
    """Interpolate the half-change to the measured last dose, not a Hill EC50."""
    effect = np.asarray(y, dtype=float) - baseline
    if abs(effect[-1]) < 1.e-9:
        return None
    scaled = effect/effect[-1]
    x0, y0 = 0., 0.
    for xx, yy in zip(x, scaled):
        if yy >= .5 and yy != y0:
            return float(x0+(.5-y0)*(xx-x0)/(yy-y0))
        x0,y0=xx,yy
    return None


def load(raw, condition, seed):
    from flyonenomics.io import hash_file
    base = raw/f'seed-{seed}-{condition}'
    row = json.loads(Path(str(base)+'.json').read_text())
    if row['seed'] != seed or row['condition'] != condition or row['provenance'] != pins():
        raise ValueError(f'invalid record: {base}')
    if hash_file(Path(str(base)+'.npz')) != row['counts_sha256']:
        raise ValueError(f'checksum mismatch: {base}')
    with np.load(Path(str(base)+'.npz'), allow_pickle=False) as arrays:
        counts = (arrays['counts_on']+arrays['counts_off'] if condition == 'control'
                  else arrays['counts_measure']).copy()
    return row, counts


def analyse(raw=OUTCOMES, out=SUMMARY, reference=REFERENCE):
    from flyonenomics.registry import build_registry, annotations
    from flyonenomics.drive.background import group_indices
    from scripts.circuit_tour import GROUPS
    from scripts.render_malecns_3d import Assets, CIRCUIT_GROUPS, GROUPS as DISPLAY_GROUPS, main_cache, selected_cells
    raw, out, reference = map(lambda p: Path(p).resolve(), (raw, out, reference))
    out.mkdir(parents=True, exist_ok=True)
    registry = build_registry('male-cns:v1.0')
    groups = group_indices(registry)
    indices = {**groups, **{g: registry.population(g).idx for g in GROUPS}}
    indices['outside_sensory'] = np.setdiff1d(np.arange(registry.n), groups['sensory'])
    records = {}; counts = {}; rates = {}
    for condition in ('control', *dose_conditions()):
        for seed in SEEDS:
            row, c = load(reference if condition == 'control' else raw, condition, seed)
            records[condition,seed] = row
            counts[condition,seed] = c
            rates[condition,seed] = c/10.
    data = {'bootstrap': '10000 whole-seed paired rate draws; 500 whole-seed Hill draws',
            'groups': {k:len(v) for k,v in indices.items()}, 'conditions': {}, 'fits':{}, 'rescue':{}}
    baseline = np.array([rates['control',s][indices['outside_sensory']].mean() for s in SEEDS])
    control_metrics = {}
    for seed in SEEDS:
        control_metrics[seed] = {k:records['control',seed]['summary']['synchrony'][k] for k in ('F','b')}
    per_neuron = {}
    for condition in dose_conditions():
        entry = {'paired_delta':{}, 'absolute_mean':{}, 'metrics':{}}
        for group, idx in indices.items():
            absolute = np.array([rates[condition,s][idx].mean() for s in SEEDS])
            base = np.array([rates['control',s][idx].mean() for s in SEEDS])
            entry['paired_delta'][group] = interval(absolute-base)
            entry['absolute_mean'][group] = float(absolute.mean())
        for metric in ('silent_fraction','median_hz','p99_hz'):
            def measure(a):
                return {'silent_fraction':lambda x:np.mean(x==0), 'median_hz':np.median,
                        'p99_hz':lambda x:np.percentile(x,99)}[metric](a)
            entry['metrics'][metric] = interval([measure(rates[condition,s])-measure(rates['control',s]) for s in SEEDS])
        for metric in ('F','b'):
            entry['metrics'][metric] = interval([records[condition,s]['summary']['synchrony'][metric]-control_metrics[s][metric] for s in SEEDS])
        data['conditions'][condition] = entry
        per_neuron[condition] = np.mean([rates[condition,s]-rates['control',s] for s in SEEDS],axis=0)
    for kind, doses in (('block',BLOCK), ('boost',BOOST)):
        x = np.array([float(d) for d in doses])
        data['fits'][kind] = {}
        for group, idx in indices.items():
            matrix = np.array([[rates[f'{kind}-{v}',s][idx].mean() for s in SEEDS] for v in doses])
            base = np.array([rates['control',s][idx].mean() for s in SEEDS])
            result = bootstrap_fits(x,matrix,base)
            point = empirical_half(x,matrix.mean(axis=1),base.mean())
            rng_half = np.random.default_rng(20260928)
            halves = []
            for _ in range(500):
                sample = rng_half.integers(0,len(SEEDS),len(SEEDS))
                h = empirical_half(x,matrix[:,sample].mean(axis=1),base[sample].mean())
                if h is not None: halves.append(h)
            if point is not None and len(halves) >= 475:
                lo,hi = np.percentile(halves,[2.5,97.5])
                result['observed_endpoint_half']=[point,float(lo),float(hi)]
            data['fits'][kind][group] = result
    rng = np.random.default_rng(20260927)
    blocked = np.array([rates['block-0.75',s][indices['outside_sensory']].mean() for s in SEEDS])
    for dose in RESCUE:
        rescued = np.array([rates[f'rescue-{dose}',s][indices['outside_sensory']].mean() for s in SEEDS])
        denom = (blocked-baseline).mean()
        draws = rng.integers(0,len(SEEDS),(10000,len(SEEDS)))
        effects = (blocked[draws]-baseline[draws]).mean(axis=1)
        fractions = np.divide((blocked[draws]-rescued[draws]).mean(axis=1),effects,
                              out=np.full(len(draws),np.nan),where=np.abs(effects)>1.e-9)
        data['rescue'][dose] = {'fraction':float((blocked-rescued).mean()/denom),
                               'interval':np.nanpercentile(fractions,[2.5,97.5]).tolist(),
                               'effect_hz':interval(rescued-blocked)}
    roots=annotations.load_engine_order('male-cns:v1.0')
    np.savez_compressed(out/'per-neuron-delta-hz.npz',root_ids=roots,**per_neuron)
    if not CIRCUIT_GROUPS[0] in DISPLAY_GROUPS:
        DISPLAY_GROUPS.extend(CIRCUIT_GROUPS)
    cells,_=selected_cells(Assets(main_cache()))
    selected=[c['body_id'] for c in cells]
    position={str(root):i for i,root in enumerate(roots)}
    labels = {**{f'block-{v}': f'GABA blocked {int(float(v)*100)}%' for v in BLOCK},
              **{f'boost-{v}': f'GABA strengthened ×{1+float(v):g}' for v in BOOST},
              **{f'rescue-{v}':f'GABA blocked 75% · GluCl ×{1+float(v):g}' for v in RESCUE}}
    values={'dataset':'male-cns:v1.0','kind':'model','label':'Change in model firing with GABA and GluCl conductance',
            'unit':'Hz change from control','summary':'Paired whole-seed mean · model firing, not behaviour',
            'body_ids':selected,'times_s':[0.,1.],
            'conditions':[{'id':c.replace('.', '_'),'label':labels[c],
                           'values':[np.round(per_neuron[c][[position[str(x)] for x in selected]],4).tolist()]*2}
                          for c in dose_conditions()]}
    (out/'paint-values.json').write_text(json.dumps(values,allow_nan=False)+'\n')
    (out/'analysis.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    return data


if __name__=='__main__':
    analyse()
