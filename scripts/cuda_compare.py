#!/usr/bin/env python3
"""Measured CUDA/Brian2 side-by-side comparisons; never fits model parameters."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.circuit_tour import SEEDS, GROUPS, KNOCKOUTS, COURTSHIP, conditions
from scripts.circuit_tour_analysis import interval
from flyonenomics.io import read_json, hash_file


def read(path):
    return read_json(path)


def sha(path):
    return hash_file(path)


def distribution(values):
    a = np.asarray(values, dtype=float)
    return {'values': a.tolist(), 'mean': float(a.mean()), 'sd': float(a.std(ddof=1)),
            'min': float(a.min()), 'max': float(a.max()), 'mean_95_bootstrap': interval(a)[1:]}


def link_outcomes(receipts, mode, out):
    out.mkdir(parents=True, exist_ok=True)
    for receipt in receipts:
        if receipt['mode'] != mode or 'local_output' not in receipt or 'error' in receipt:
            continue
        for path in (ROOT / receipt['local_output']).glob('seed-*.*'):
            target = out / path.name
            if target.exists():
                if sha(target) != sha(path):
                    raise ValueError(f'multiple outcomes for {path.name}; select the intended run explicitly')
            else:
                target.symlink_to(path.resolve())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference-tour', type=Path, required=True)
    p.add_argument('--reference-rest', type=Path, required=True)
    a = p.parse_args()
    receipts = read(ROOT / 'validation/records/p2/male-cuda-receipts.json')
    work = ROOT / 'camber-runs/cuda-circuit'
    link_outcomes(receipts, 'rest', work / 'rest')
    link_outcomes(receipts, 'tour', work / 'outcomes')
    # Invoke the existing analysis byte-for-byte, in separate processes because
    # its optional renderer builds a mutable global list of display populations.
    for name, raw in [('brian', a.reference_tour), ('cuda', work / 'outcomes')]:
        subprocess.run([sys.executable, str(ROOT / 'scripts/circuit_tour_analysis.py'),
                        str(raw), str(work / f'{name}-analysis')], check=True)
    analyses = {name: read(work / f'{name}-analysis/analysis.json') for name in ('brian', 'cuda')}
    if analyses['brian']['provenance'] != analyses['cuda']['provenance']:
        raise ValueError('GPU/reference substrate bindings differ')
    rest_pin = read(ROOT / 'validation/records/p2/malecns-rest.json')['raw']['files_sha256']
    rest = {'brian': [], 'cuda': []}
    hashes = {}
    for seed in range(1, 11):
        source = a.reference_rest / f'seed-{seed}.json'
        if sha(source) != rest_pin[source.name]:
            raise ValueError(f'reference rest hash mismatch: {source}')
        ref = next(r for r in read(source)['screen'] if r['weight_mv'] == 1.)
        gpu = read(work / 'rest' / f'seed-{seed}-control.json')
        if sha(work / 'rest' / gpu['counts_file']) != gpu['counts_sha256']:
            raise ValueError(f'GPU rest counts checksum mismatch: seed {seed}')
        rest['brian'].append({**ref['rates_hz'], 'F': ref['F'], 'b': ref['b']})
        rest['cuda'].append({**gpu['summary']['measure']['group_hz'], **gpu['summary']['synchrony']})
        hashes[str(source)] = sha(source)
    rates = {g: {name: distribution([row[g] for row in rows]) for name, rows in rest.items()}
             for g in rest['brian'][0]}
    raw_rows = {name: {(s, c): read(raw / f'seed-{s}-{c}.json') for c in conditions() for s in SEEDS}
                for name, raw in [('brian', a.reference_tour), ('cuda', work / 'outcomes')]}
    absolute = {}
    for c in conditions():
        windows = ['measure'] if c.startswith('off-') else ['on', 'off']
        absolute[c] = {w: {g: {name: distribution([rows[s, c]['summary'][w]['group_hz'][g] for s in SEEDS])
                               for name, rows in raw_rows.items()}
                           for g in raw_rows['brian'][501, c]['summary'][w]['group_hz']}
                       for w in windows}
    effects = {c: {name: data['rows'][c] for name, data in analyses.items()}
               for c in analyses['brian']['rows']}
    for name, raw in [('brian', a.reference_tour), ('cuda', work / 'outcomes'), ('cuda-rest', work / 'rest')]:
        for path in sorted(raw.glob('seed-*.*')):
            hashes[f'{name}/{path.name}'] = sha(path)
    output = {'schema': 'cuda-reference-comparison-v1',
              'note': 'Different RNG streams: compare distributions and paired effects, not spike trains. No pass line.',
              'rest_seeds': list(range(1, 11)), 'tour_seeds': list(SEEDS),
              'rest_state': '2 s settle + 10 s record, clamped at DA_ref; 1.0 mV sensory only',
              'tour_state': '2 s settle + 10 s record, free dopamine except off-dopamine A/C disabled',
              'rest': rates, 'absolute_tour_rates': absolute, 'paired_effects': effects,
              'group_sizes': raw_rows['cuda'][501, 'control']['group_sizes'],
              'outside_sensory_effect_difference_contributions_hz': {
                  'off-' + nt: {g: (effects['off-' + nt]['cuda'][g][0] - effects['off-' + nt]['brian'][g][0])
                               * raw_rows['cuda'][501, 'control']['group_sizes'][g]
                               / raw_rows['cuda'][501, 'control']['group_sizes']['outside_sensory']
                               for g in rest['brian'][0] if g not in ('sensory', 'F', 'b')}
                  for nt in KNOCKOUTS},
              'analysis_sha256': sha(ROOT / 'scripts/circuit_tour_analysis.py'), 'raw_sha256': hashes}
    dest = ROOT / 'validation/records/p2/male-cuda-comparison.json'
    dest.write_text(json.dumps(output, indent=2, allow_nan=False) + '\n')
    lines = ['# GPU and Brian2: measured comparison', '',
             'Different random streams; distributions and paired effects, not matching spike trains. No pass line.',
             'The model receives injected input; the fly does not see or sing. Visual input is normally injected at TuBu; this tour injects the named courtship populations.', '',
             '## Item 155 rest (clamped dopamine; seeds 1–10)', '',
             '| Group / measure | Brian2 mean [seed range] | CUDA mean [seed range] |', '|---|---:|---:|']
    def dist(x): return f'{x["mean"]:.6g} [{x["min"]:.6g}, {x["max"]:.6g}]'
    def effect(x): return '—' if x is None else f'{x[0]:+.5g} [{x[1]:+.5g}, {x[2]:+.5g}]'
    for group, data in rates.items():
        lines.append(f'| {group} | {dist(data["brian"])} | {dist(data["cuda"])} |')
    lines += ['', '## Item 158 knockout effects (Hz, paired 95% whole-seed bootstrap)', '',
              '| Block | Readout | Brian2 Δ [95%] | CUDA Δ [95%] |', '|---|---|---:|---:|']
    for nt in KNOCKOUTS:
        e = effects['off-' + nt]
        for g in ('outside_sensory', 'optic', 'central', 'DAN', 'KC'):
            lines.append(f'| {nt} | {g} | {effect(e["brian"][g])} | {effect(e["cuda"][g])} |')
    lines += ['', '## Item 159 courtship effects (Hz, paired 95% whole-seed bootstrap)', '',
              '| Injected drive | Window / readout | Brian2 Δ [95%] | CUDA Δ [95%] |', '|---|---|---:|---:|']
    for c in COURTSHIP:
        for w in ('on', 'off'):
            for g in GROUPS:
                e = effects[c]
                lines.append(f'| {c} | {w} / {g} | {effect(e["brian"][w][g])} | {effect(e["cuda"][w][g])} |')
    lines += ['', 'The JSON includes every group, seed-level absolute rates, synchrony and distribution effects, first-spike latencies, raw hashes and specificity contrasts. Intervals containing zero mean **no detected difference**, not equality.', '']
    dest.with_suffix('.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
