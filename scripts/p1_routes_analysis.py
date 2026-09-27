#!/usr/bin/env python3
"""Re-analyse existing circuit-tour ON totals; never launches the engine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

SEEDS = range(501, 511)
ARMS = ('P1-low', 'P1-medium', 'P1-high', 'courtship_random')
WINDOW_S = 5
BOOTSTRAP_SEED = 20260925
DRAWS = 10000


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main(outcomes: Path, cache: Path, output: Path) -> None:
    order_path = cache / 'malecns-v1.0/derived/engine-order.csv'
    ann_path = cache / 'malecns-v1.0/derived/annotations.feather'
    roots = pd.read_csv(order_path).root_id.to_numpy()
    ann = pd.read_feather(ann_path)
    dn = ann.loc[(ann.super_class == 'descending_neuron') & ann.type.notna(),
                 ['root_id', 'type', 'side']].copy()
    dn = dn.set_index('root_id').loc[roots[np.isin(roots, dn.root_id)]].reset_index()
    if len(roots) != 162517 or len(dn) != 1310 or not np.array_equal(ann.root_id.to_numpy(), roots):
        raise ValueError('annotation/order or DN population changed')
    idx = np.flatnonzero(np.isin(roots, dn.root_id))
    # These arrays are differences within whole seeds, not seed-averaged maps.
    diffs = {arm: [] for arm in ARMS}
    provenance = None
    inputs = {}
    for seed in SEEDS:
        rates = {}
        for arm in ('control', *ARMS):
            base = outcomes / f'seed-{seed}-{arm}'
            meta = json.loads(base.with_suffix('.json').read_text())
            if meta['schema'] != 'circuit-tour-v1' or meta['seed'] != seed or meta['condition'] != arm:
                raise ValueError(f'wrong record: {base}')
            if provenance is not None and meta['provenance'] != provenance:
                raise ValueError(f'provenance mismatch: {base}')
            provenance = meta['provenance']
            checksum = digest(base.with_suffix('.npz'))
            if checksum != meta['counts_sha256']:
                raise ValueError(f'counts checksum mismatch: {base}')
            inputs[f'seed-{seed}-{arm}.npz'] = checksum
            with np.load(base.with_suffix('.npz'), allow_pickle=False) as z:
                rates[arm] = z['counts_on'][idx].astype(np.float64) / WINDOW_S
        for arm in ARMS:
            diffs[arm].append(rates[arm] - rates['control'])
    diffs = {k: np.stack(v) for k, v in diffs.items()}
    # Same whole-seed bootstrap convention as circuit_tour_analysis.interval:
    # fresh PCG64(20260925), 10,000 ten-seed draws and percentile 2.5/97.5.
    picks = np.random.default_rng(BOOTSTRAP_SEED).integers(0, len(SEEDS), size=(DRAWS, len(SEEDS)))
    weights = np.stack([(picks == i).sum(axis=1) for i in range(len(SEEDS))], axis=1) / len(SEEDS)

    def interval(matrix: np.ndarray) -> np.ndarray:
        means = matrix.mean(axis=0)
        boot = weights @ matrix
        bounds = np.percentile(boot, (2.5, 97.5), axis=0)
        return np.stack((means, *bounds), axis=1)

    def make_rows(matrices: dict[str, np.ndarray], labels: list[tuple]) -> list[dict]:
        results = {name: interval(mat) for name, mat in matrices.items()}
        rows = []
        for i, label in enumerate(labels):
            row = dict(zip(('root_id', 'type', 'side', 'n_cells'), label))
            for name, arr in results.items():
                row.update({f'{name}_{suffix}': round(float(v), 4)
                            for suffix, v in zip(('mean', 'lo', 'hi'), arr[i])})
            def up(name): return results[name][i, 1] > 0
            def unsure(name): return results[name][i, 1] <= 0 <= results[name][i, 2]
            # "Plateau" is only operational: non-detection of a difference is not equality.
            if all(unsure(a) for a in ARMS[:3]):
                shape = 'no detected difference'
            elif up('P1-low') and unsure('medium_minus_low') and unsure('high_minus_low'):
                shape = 'low rise; further change not detected'
            elif unsure('P1-low') and unsure('P1-medium') and up('P1-high') and up('high_minus_medium'):
                shape = 'high-only detected'
            elif up('P1-low') and up('medium_minus_low') and up('high_minus_medium'):
                shape = 'rises at each step'
            else:
                shape = 'other/mixed (inspect intervals)'
            row['shape'] = shape
            rows.append(row)
        return rows

    def with_contrasts(data):
        return {**data,
                'medium_minus_low': data['P1-medium'] - data['P1-low'],
                'high_minus_medium': data['P1-high'] - data['P1-medium'],
                'high_minus_low': data['P1-high'] - data['P1-low'],
                'medium_minus_random': data['P1-medium'] - data['courtship_random']}

    cells = make_rows(with_contrasts(diffs), [(int(r.root_id), r.type, r.side, 1) for r in dn.itertuples()])
    types = sorted(dn.type.unique())
    grouped = {arm: np.stack([array[:, dn.type.to_numpy() == typ].mean(axis=1) for typ in types], axis=1)
               for arm, array in diffs.items()}
    type_rows = make_rows(with_contrasts(grouped), [('', typ, '', int((dn.type == typ).sum())) for typ in types])
    output.mkdir(parents=True, exist_ok=True)
    for filename, rows in [('p1-routes-cells.csv', cells), ('p1-routes-types.csv', type_rows)]:
        with (output / filename).open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    manifest = {'source': 'SPEC-P2 item 159 ON-window outcome records only', 'seeds': list(SEEDS),
                'arms': list(ARMS), 'window_s': WINDOW_S, 'bootstrap': f'{DRAWS} paired whole-seed draws; PCG64 {BOOTSTRAP_SEED}; 2.5/97.5 percentiles',
                'units': 'Hz difference in ON (first five seconds) from matched control ON',
                'cell_count': len(cells), 'type_count': len(type_rows), 'source_provenance': provenance,
                'engine_order_sha256': digest(order_path), 'annotations_sha256': digest(ann_path),
                'outcome_npz_sha256': inputs}
    (output / 'p1-routes-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('outcomes', type=Path)
    p.add_argument('--cache', type=Path, default=Path(os.environ['FLYONENOMICS_CACHE_DIR']) if 'FLYONENOMICS_CACHE_DIR' in os.environ else None, required='FLYONENOMICS_CACHE_DIR' not in os.environ)
    p.add_argument('--output', type=Path, default=Path('validation/records/p2'))
    args = p.parse_args()
    main(args.outcomes, args.cache, args.output)
