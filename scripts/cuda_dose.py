#!/usr/bin/env python3
"""Item 163 archive binding and unchanged item 162 analysis; no model fitting here."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flyonenomics.io import hash_file, read_json
from scripts.circuit_tour import SEEDS, dose_conditions, pins
from scripts.circuit_tour_dose import analyse, load
from scripts.cuda_compare import link_outcomes

RECEIPTS = ROOT / 'validation/records/p2/male-cuda-dose-receipts.json'
WORK = ROOT / 'camber-runs/cuda-dose'
REFERENCE = Path('<local-project-root>/<reference-checkout>/camber-runs/cuda-circuit/outcomes')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def arrays(raw, condition, seed):
    path = raw / f'seed-{seed}-{condition}.npz'
    row = read_json(path.with_suffix('.json'))
    if (row['provenance'] != pins() or row['seed'] != seed or row['condition'] != condition
            or row['counts_sha256'] != hash_file(path)):
        raise ValueError(f'invalid archive: {path}')
    with np.load(path, allow_pickle=False) as data:
        return {k: data[k].copy() for k in data.files}


def prefreeze(reference):
    rows = [r for r in read_json(RECEIPTS) if r['mode'] == 'reproduce' and 'local_output' in r and 'error' not in r]
    checks = {}
    for condition, target in (('control', 'control'), ('block-1.00', 'off-gaba')):
        matches = [r for r in rows if r['tasks'] == [[501, condition]]]
        if len(matches) != 1:
            raise ValueError(f'expected exactly one completed reproduction for {condition}')
        row = matches[0]
        raw = ROOT / row['local_output']
        actual, expected = arrays(raw, condition, 501), arrays(reference, target, 501)
        deltas = {k: actual[k].astype(np.int64) - expected[k] for k in expected}
        checks[condition] = {
            'reference_condition': target, 'seed': 501, 'app_id': row['app_id'],
            'archive': str(raw.relative_to(ROOT)), 'reference': str(reference),
            'counts': {k: {'actual_total': int(actual[k].sum()), 'reference_total': int(expected[k].sum()),
                           'differing_neurons': int(np.count_nonzero(d)), 'max_abs_difference': int(np.abs(d).max())}
                       for k, d in deltas.items()},
            'sha256': {str(p): hash_file(p) for base, c in ((raw, condition), (reference, target))
                       for p in (base / f'seed-501-{c}.npz', base / f'seed-501-{c}.json')},
        }
    write(WORK / 'prefreeze.json', checks)
    print(json.dumps(checks, indent=2))
    return checks


def comparison(reference, brian_analysis):
    receipts = read_json(RECEIPTS)
    rows = [r for r in receipts if r['mode'] == 'dose' and 'local_output' in r and 'error' not in r]
    tasks = [tuple(task) for row in rows for task in row['tasks']]
    expected = {(s, c) for c in dose_conditions() for s in SEEDS}
    if len(tasks) != 130 or set(tasks) != expected or any(len(r['tasks']) != 10 for r in rows):
        raise ValueError('expected 13 complete single-condition batches, all 130 planned outcomes once')
    raw = WORK / 'outcomes'
    link_outcomes(receipts, 'dose', raw)
    gpu = analyse(raw=raw, out=WORK / 'summary', reference=reference)
    brian = read_json(brian_analysis)
    hashes = {}
    controls = []
    endpoints = []
    for c in ('control', *dose_conditions()):
        source = reference if c == 'control' else raw
        for seed in SEEDS:
            row, counts = load(source, c, seed)
            if row['backend'] != 'cuda-cooperative-f64' or row['dopamine'] != 'free' or row['chunk_s'] != .01:
                raise ValueError(f'unexpected GPU protocol for {seed}/{c}')
            for suffix in ('json', 'npz'):
                p = source / f'seed-{seed}-{c}.{suffix}'
                hashes[str(p)] = hash_file(p)
            if c == 'control':
                controls.append({g: (row['summary']['on']['group_hz'][g] + row['summary']['off']['group_hz'][g])/2
                                 for g in row['summary']['on']['group_hz']})
            if c == 'block-1.00':
                _, off = load(reference, 'off-gaba', seed)
                endpoints.append({'seed': seed, 'differing_neurons': int(np.count_nonzero(counts != off)),
                                  'total_difference': int(counts.sum() - off.sum())})
    overlap = {}
    for kind in ('block', 'boost'):
        overlap[kind] = {}
        a, b = brian['fits'][kind]['outside_sensory'], gpu['fits'][kind]['outside_sensory']
        for key in ('half_effect', 'slope', 'half_effect_extrapolated', 'slope_conditional', 'observed_endpoint_half'):
            if key in a and key in b:
                overlap[kind][key] = max(a[key][1], b[key][1]) <= min(a[key][2], b[key][2])
    overlap['rescue'] = {d: max(brian['rescue'][d]['interval'][0], gpu['rescue'][d]['interval'][0]) <=
                        min(brian['rescue'][d]['interval'][1], gpu['rescue'][d]['interval'][1]) for d in gpu['rescue']}
    output = {
        'schema': 'cuda-dose-comparison-v1',
        'note': 'Independent engine RNG streams; within-engine seed pairing only. Interval overlap is descriptive, not equivalence.',
        'prefreeze': read_json(WORK / 'prefreeze.json'), 'seeds': list(SEEDS),
        'conditions': list(dose_conditions()), 'control_source': str(reference),
        'gpu_control_mean_hz': {g: float(np.mean([r[g] for r in controls])) for g in controls[0]},
        'brian_analysis_source': str(brian_analysis), 'brian_analysis_sha256': hash_file(brian_analysis),
        'analysis_source_sha256': hash_file(ROOT / 'scripts/circuit_tour_dose.py'),
        'brian': brian, 'gpu': gpu, 'outside_sensory_interval_overlap': overlap,
        'full_block_vs_gpu_off_gaba': endpoints, 'raw_sha256': hashes,
        'outcome_source_commits': sorted({r['source_sha'] for r in rows}),
    }
    write(ROOT / 'validation/records/p2/male-cuda-dose-comparison.json', output)
    print(json.dumps({'gpu_fits': gpu['fits']['block']['outside_sensory'], 'rescue': gpu['rescue'],
                      'interval_overlap': overlap}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prefreeze', 'analyse'))
    p.add_argument('--reference', type=Path, default=REFERENCE)
    p.add_argument('--brian-analysis', type=Path)
    a = p.parse_args()
    if a.mode == 'prefreeze':
        prefreeze(a.reference)
    else:
        if a.brian_analysis is None:
            p.error('--brian-analysis is required')
        comparison(a.reference, a.brian_analysis)


if __name__ == '__main__':
    main()
