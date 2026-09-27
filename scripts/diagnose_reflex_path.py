#!/usr/bin/env python3
"""Why inhibitory scaling abolishes the sugar reflex (WP17 escalation evidence, no engine runs).

Measured part: feed-forward R-reflex rows (background off, base thresholds), group rate
responses sugar minus silent for the bare reference and every scaled candidate, by scale pair
and mode. Structural part: MN9's direct inputs by transmitter class, and a flow proxy for
sugar-recruited input into MN9. Flow is the product of per-synapse input fractions along
sugar GRN -> x -> pre -> MN9 paths, split by the class of the last presynaptic neuron and
multiplied by g_gaba or g_glu. It ignores thresholds, timing and recurrence: an ordering
proxy, not a rate prediction.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import glob
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from flyonenomics.io import read_text

GROUPS = ('sensory', 'ascending', 'central', 'descending', 'motor')
SCALES = ((1, 1), (1.25, 1.25), (1.5, 1.5), (2, 2), (2, 6), (2, 8), (3, 1), (3, 3), (3, 6), (3, 8),
          (4, 1), (4, 2), (4, 3), (4, 4))


def ff_rows(patterns):
    rows = []
    for pattern in patterns:
        for f in sorted(glob.glob(pattern)):
            for line in read_text(f).splitlines():
                r = json.loads(line)
                if r.get('kind') == 'evaluation' and r.get('feedforward'):
                    rows.append(r)
    return rows


def responses(rows):
    """Mean sugar-minus-silent group rates and MN9, per network and mode. Units: Hz."""
    by = defaultdict(list)
    for r in rows:
        net = 'bare' if r.get('bare') else f"({r['g_gaba']:g},{r['g_glu']:g}) optic {'on' if r['optic_exemption'] else 'off'}"
        by[(net, r['mode'])].append(r)
    out = {}
    for (net, mode), rs in sorted(by.items()):
        seeds = sorted({r['seed'] for r in rs})
        first = {s: next(r for r in rs if r['seed'] == s) for s in seeds}
        delta = lambda g: float(np.mean([first[s]['sugar']['rates_hz'][g] - first[s]['silent']['rates_hz'][g] for s in seeds]))
        out[f'{net} {mode}'] = {'network': net, 'mode': mode, 'seeds': len(seeds),
                                'mn9_sugar_hz': float(np.mean([first[s]['sugar']['mn9_hz'] for s in seeds])),
                                'mn9_silent_hz': float(np.mean([first[s]['silent']['mn9_hz'] for s in seeds])),
                                'group_delta_hz': {g: delta(g) for g in GROUPS},
                                'identical_duplicates': all(r['difference_hz'] == first[r['seed']]['difference_hz'] for r in rs)}
    for key, v in out.items():
        bare = out.get(f"bare {v['mode']}")
        if bare and v['network'] != 'bare':
            v['fraction_of_bare'] = {g: v['group_delta_hz'][g] / bare['group_delta_hz'][g] for g in GROUPS}
            v['fraction_of_bare']['MN9'] = (v['mn9_sugar_hz'] - v['mn9_silent_hz']) / (bare['mn9_sugar_hz'] - bare['mn9_silent_hz'])
    return out


def structure():
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.registry import build_registry
    from flyonenomics.substrate.transmitters import annotations_in_engine, load_transmitters
    registry = build_registry('783')
    classes = np.asarray(load_transmitters()['class_array']).astype(str)
    _roots, i, j, w = load_connectome_arrays(*connectome_source_paths('783'))
    i, j = np.asarray(i, dtype=np.int64), np.asarray(j, dtype=np.int64)
    w = np.asarray(w, dtype=np.float64)
    syn = np.abs(w)
    n = classes.shape[0]
    sugar = registry.population('sugar_GRN_R').idx
    mn9 = int(registry.population('MN9').idx[0])
    frame, _ = annotations_in_engine()
    frac = syn / np.maximum(np.bincount(j, weights=syn, minlength=n)[j], 1)
    source = np.zeros(n)
    source[sugar] = 1
    v1 = np.bincount(j, weights=frac * source[i], minlength=n)
    v2 = np.bincount(j, weights=frac * v1[i], minlength=n)
    into = np.flatnonzero(j == mn9)
    pre, cls = i[into], classes[i[into]]
    direct = {c: int(syn[into][cls == c].sum()) for c in sorted(set(cls))}
    curated = np.where(np.isin(cls, ['GABA', 'Glu', 'His']), -1, np.where(np.isin(cls, ['ACh', 'mod']), 1, np.sign(w[into])))
    flow = frac[into] * v2[pre]
    exc = float(flow[np.isin(cls, ['ACh', 'mod'])].sum() + flow[(cls == 'unk') & (w[into] > 0)].sum())
    gaba = float(flow[cls == 'GABA'].sum() + flow[(cls == 'unk') & (w[into] < 0)].sum())
    glu = float(flow[cls == 'Glu'].sum())
    balance = {f'({a:g},{b:g})': (gaba * a + glu * b) / exc for a, b in SCALES}
    top = []
    for k in np.argsort(-flow)[:16]:
        p = int(pre[k])
        top.append({'cell_type': str(frame['cell_type'].iloc[p]), 'super_class': str(frame['super_class'].iloc[p]),
                    'side': str(frame['side'].iloc[p]), 'class': str(cls[k]), 'synapses_onto_mn9': int(syn[into][k]),
                    'flow': float(flow[k])})
    return {'mn9_direct_input_synapses_by_class': direct,
            'mn9_input_rows_with_curated_sign_differing_from_file': int((curated != np.sign(w[into])).sum()),
            'sugar_grn_count': int(len(sugar)),
            'flow_into_mn9': {'excitatory': exc, 'gaba': gaba, 'glu': glu},
            'inhibitory_over_excitatory_flow': balance,
            'parity_diagonal_g': exc / (gaba + glu), 'parity_g_gaba_at_g_glu_1': (exc - glu) / gaba,
            'top_flow_inputs': top}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', nargs='+', required=True, help='glob patterns of R-reflex ndjson rows')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    record = {'class': 'development', 'measured': responses(ff_rows(args.rows)), 'structure': structure(),
              'row_patterns': args.rows}
    args.out.write_text(json.dumps(record, indent=1) + '\n')
    print(json.dumps({k: {kk: round(vv, 3) for kk, vv in v.get('fraction_of_bare', {}).items()}
                      for k, v in record['measured'].items()}, indent=1))
    print(json.dumps({k: round(v, 2) for k, v in record['structure']['inhibitory_over_excitatory_flow'].items()}))


if __name__ == '__main__':
    main()
