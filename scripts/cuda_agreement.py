#!/usr/bin/env python3
"""Describe Brian2/CUDA agreement from saved counts; no engine runs or pass line.

Run locally with FLYONENOMICS_CACHE_DIR pointing to the existing model cache:
    .venv/bin/python scripts/cuda_agreement.py
The four outcome directories are read in place. Only the JSON result is written.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flyonenomics.io import hash_file, read_json
from flyonenomics.registry import build_registry
from flyonenomics.drive.background import group_indices
from scripts.circuit_tour import COURTSHIP, GROUPS, SEEDS, conditions, dose_conditions, pins
from scripts.circuit_tour_analysis import interval

WORKTREES = Path('<local-project-root>/.worktrees')
SOURCES = {
    'tour': {
        'brian': WORKTREES / 't-0114/camber-runs/circuit-tour/outcomes',
        'cuda': WORKTREES / 't-0122/camber-runs/cuda-circuit/outcomes',
    },
    'dose': {
        'brian': WORKTREES / 't-0129/camber-runs/circuit-tour/dose-outcomes',
        'cuda': WORKTREES / 't-0138/camber-runs/cuda-dose/outcomes',
    },
}
COMPARISON = ROOT / 'validation/records/p2/male-cuda-comparison.json'
OUTPUT = ROOT / 'validation/records/p2/male-cuda-agreement.json'
N = len(SEEDS)
PAIR_I, PAIR_J = np.triu_indices(N, 1)
BOOTSTRAP_SEED = 20260929
BOOTSTRAP_DRAWS = 10000


def discover(raw):
    """Inventory count outcomes, excluding separate spike-event replays."""
    found = {}
    for path in sorted(raw.glob('seed-*.npz')):
        _, seed, condition = path.stem.split('-', 2)
        if not condition.endswith('-spikes'):
            found.setdefault(condition, []).append(int(seed))
    return found


def load_outcome(raw, condition, seed, indices, provenance, comparison_hashes=None):
    """Read only checksum-bound counts/receipts; preserve the engine's ordering."""
    base = raw / f'seed-{seed}-{condition}'
    receipt, archive = Path(str(base) + '.json'), Path(str(base) + '.npz')
    row = read_json(receipt)
    hashes = {p.name: hash_file(p) for p in (receipt, archive)}
    expected_windows = ([['settle', 2.0], ['on', 5.0], ['off', 5.0]]
                        if condition in ('control', *COURTSHIP)
                        else [['settle', 2.0], ['measure', 10.0]])
    if (row['schema'] != 'circuit-tour-v1' or row['seed'] != seed
            or row['condition'] != condition or row['provenance'] != provenance
            or row['windows'] != expected_windows or row['counts_file'] != archive.name
            or row['counts_sha256'] != hashes[archive.name]):
        raise ValueError(f'outcome binding mismatch: {base}')
    if comparison_hashes is not None:
        for name, digest in hashes.items():
            if comparison_hashes[name] != digest:
                raise ValueError(f'archived comparison binding mismatch: {base}')
    for group, idx in indices.items():
        if group != 'all' and row['group_sizes'][group] != len(idx):
            raise ValueError(f'group size mismatch: {base}, {group}')
    with np.load(archive, allow_pickle=False) as arrays:
        expected_keys = {f'counts_{w}' for w, _ in expected_windows[1:]}
        if set(arrays.files) != expected_keys:
            raise ValueError(f'unexpected count windows: {base}')
        counts = {key.removeprefix('counts_'): arrays[key].astype(np.int64)
                  for key in arrays.files}
        for key in arrays.files:
            a = arrays[key]
            if (a.shape != (len(indices['all']),) or not np.issubdtype(a.dtype, np.integer)
                    or np.any(a < 0)):
                raise ValueError(f'invalid per-neuron counts: {base}, {key}')
    if 'measure' not in counts:
        counts['measure'] = counts['on'] + counts['off']
    return row, counts, hashes


def summary(values):
    a = np.asarray(values, dtype=float)
    return {'mean': float(a.mean()), 'median': float(np.median(a)),
            'sd': float(a.std(ddof=1)), 'min': float(a.min()), 'max': float(a.max())}


def ratio_interval(numerator, denominator, boot_numerator, boot_denominator):
    """Retain zero-denominator draws, without NaN/Infinity JSON or epsilon floors.

    An interval is left unresolved if ANY draw has a zero denominator. The
    finite-draw interval is also retained, explicitly conditional, not a 95%
    interval for the unconditional ratio.
    """
    good = boot_denominator > 0
    finite = boot_numerator[good] / boot_denominator[good]
    bounds = np.percentile(finite, [2.5, 97.5]).tolist() if finite.size else None
    return {
        'estimate': float(numerator / denominator) if denominator > 0 else None,
        'status': 'defined' if denominator > 0 else 'zero_denominator',
        'bootstrap_95': bounds if good.all() else None,
        'finite_draws_conditional_95': bounds if not good.all() else None,
        'zero_denominator_draws': int((~good).sum()),
        'zero_over_zero_draws': int(((~good) & (boot_numerator == 0)).sum()),
    }


def rate_agreement(brian, cuda, draws):
    """Exact empirical W1 on the integer count lattice (0.1 Hz), no bin choice.

    W1 = sum_k |CDF_B(k)-CDF_C(k)| / 10. Integer cumulative frequencies
    keep exactly silent distributions exactly zero. All neurons are equally
    weighted; pooling concatenates the ten neuron distributions, not their
    per-neuron means. Shapes: counts (10, group size), draws (10000, 10).
    """
    size = brian.shape[1]
    support = int(max(brian.max(), cuda.max())) + 1
    cdfs = [np.stack([np.bincount(row, minlength=support).cumsum() for row in engine])
            for engine in (brian, cuda)]
    b, c = cdfs
    scale = size * 10.0
    cross = np.abs(b - c).sum(axis=1) / scale
    pooled = float(np.abs(b.sum(axis=0) - c.sum(axis=0)).sum() / (N * scale))
    cross_boot = cross[draws].mean(axis=1)
    within, within_boot, pair_values = {}, {}, []
    for name, cdf in zip(('brian', 'cuda'), cdfs):
        matrix = np.abs(cdf[:, None, :] - cdf[None, :, :]).sum(axis=2) / scale
        values = matrix[PAIR_I, PAIR_J]
        # Recompute all 45 pair distances on the resampled whole runs. Repeated
        # occurrences of the same original run have zero distance, as required
        # by the empirical bootstrap. Do not bootstrap the 45 dependent pairs.
        resampled = matrix[draws[:, PAIR_I], draws[:, PAIR_J]]
        within_boot[name] = np.median(resampled, axis=1)
        within[name] = {'pair_hz': values.tolist(), **summary(values),
                        'median_bootstrap_95': np.percentile(within_boot[name], [2.5, 97.5]).tolist()}
        pair_values.append(resampled)
    pooled_within = np.concatenate([within[name]['pair_hz'] for name in ('brian', 'cuda')])
    within['pooled_engines'] = summary(pooled_within)
    within_boot['pooled_engines'] = np.median(np.concatenate(pair_values, axis=1), axis=1)
    within['pooled_engines']['median_bootstrap_95'] = np.percentile(
        within_boot['pooled_engines'], [2.5, 97.5]).tolist()
    return {
        'paired_cross_hz': cross.tolist(),
        'paired_cross_summary_hz': summary(cross),
        'paired_cross_mean_bootstrap_95_hz': np.percentile(cross_boot, [2.5, 97.5]).tolist(),
        'pooled_cross_hz': pooled,
        'within_engine_hz': within,
        'mean_cross_over_median_within': {
            name: ratio_interval(float(cross.mean()), within[name]['median'], cross_boot, boot)
            for name, boot in within_boot.items()
        },
    }


def observables(row, counts, indices):
    """Reconstruct the previously reported effects, including their ON/OFF windows."""
    result = {}
    for window, a in counts.items():
        rates = a / (10.0 if window == 'measure' else 5.0)
        result[window] = {group: float(rates[idx].mean()) for group, idx in indices.items()}
        result[window].update(silent_fraction=float(np.mean(a == 0)), median_hz=float(np.median(rates)),
                              p99_hz=float(np.percentile(rates, 99)), max_hz=float(rates.max()))
    result['measure'].update(row['summary']['synchrony'])
    return result


def effect_agreement(observed, comparison, draws):
    """Standardise every existing paired effect by Brian2's whole-run effect SD.

    Pooled within-reference spread = sqrt(mean_{i<j}(delta_i-delta_j)^2/2),
    exactly the sample SD of the ten paired Brian2 effects, not a standard
    error and not a pooled Brian2/CUDA SD. Also retain the unscaled RMS
    pair difference and its corresponding ratio to remove any ambiguity.
    """
    output = []

    def add(condition, window, metric, left, right, published):
        effects = {}
        for engine in ('brian', 'cuda'):
            a = np.asarray([o[window][metric] for o in observed[left][engine]])
            b = np.asarray([o[window][metric] for o in observed[right][engine]])
            if any(v is None for v in (*a, *b)):
                raise ValueError(f'missing paired effect: {condition}/{window}/{metric}')
            delta = a.astype(float) - b.astype(float)
            # These are bindings to existing results, not scientific pass lines.
            if not np.allclose(interval(delta), published[engine], rtol=1e-10, atol=1e-10):
                raise ValueError(f'effect differs from saved analysis: {condition}/{window}/{metric}/{engine}')
            effects[engine] = delta
        b, c = effects['brian'], effects['cuda']
        difference = float(c.mean() - b.mean())
        pair_diff = b[PAIR_I] - b[PAIR_J]
        rms_pair = float(np.sqrt(np.mean(pair_diff ** 2)))
        spread = rms_pair / np.sqrt(2.0)
        boot_difference = (c[draws] - b[draws]).mean(axis=1)
        boot_spread = b[draws].std(axis=1, ddof=1)
        ratio = ratio_interval(difference, spread, boot_difference, boot_spread)
        output.append({
            'condition': condition, 'window': window, 'metric': metric,
            'unit': 'dimensionless' if metric in ('silent_fraction', 'F', 'b') else 'Hz',
            'left': left, 'right': right,
            'seed_effects': {engine: x.tolist() for engine, x in effects.items()},
            'published_effect_mean_95': published,
            'cuda_minus_brian_mean_effect': difference,
            'difference_bootstrap_95': np.percentile(boot_difference, [2.5, 97.5]).tolist(),
            'brian_effect_pair_differences': pair_diff.tolist(),
            'brian_pooled_within_effect_sd': float(spread),
            'brian_rms_effect_pair_difference': rms_pair,
            'difference_over_brian_effect_sd': ratio,
            'absolute_difference_over_brian_effect_sd': abs(ratio['estimate']) if spread > 0 else None,
            'difference_over_brian_rms_pair_difference': difference / rms_pair if rms_pair > 0 else None,
        })

    for condition, published in comparison['paired_effects'].items():
        if condition.startswith('off-'):
            for metric in published['brian']:
                add(condition, 'measure', metric, condition, 'control',
                    {engine: published[engine][metric] for engine in ('brian', 'cuda')})
        elif condition in COURTSHIP:
            for window in ('on', 'off'):
                for metric in published['brian'][window]:
                    add(condition, window, metric, condition, 'control',
                        {engine: published[engine][window][metric] for engine in ('brian', 'cuda')})
        else:
            left, right = {'P1 medium minus random': ('P1-medium', 'courtship_random'),
                           'P1 high minus low': ('P1-high', 'P1-low')}[condition]
            add(condition, 'on', 'dPR1', left, right, published)
    return output


def main():
    registry = build_registry('male-cns:v1.0')  # Existing annotation/engine-order loaders only.
    drive = group_indices(registry)
    indices = {'all': np.arange(registry.n),
               'outside_sensory': np.setdiff1d(np.arange(registry.n), drive['sensory']),
               **drive, **{g: registry.population(g).idx for g in GROUPS}}
    indices['outside_targets'] = np.setdiff1d(np.arange(registry.n),
                                             np.concatenate([indices[g] for g in GROUPS]))
    provenance = pins()
    comparison = read_json(COMPARISON)
    draws = np.random.default_rng(BOOTSTRAP_SEED).integers(0, N, (BOOTSTRAP_DRAWS, N))
    result = {
        'schema': 'cuda-agreement-v1',
        'note': 'Retrospective descriptive analysis of existing outcomes. No pass line or equivalence claim.',
        'command': 'FLYONENOMICS_CACHE_DIR=<local-project-root>/.cache .venv/bin/python scripts/cuda_agreement.py',
        'dataset': 'male-cns:v1.0', 'provenance': provenance,
        'analysis_sha256': hash_file(Path(__file__)),
        'comparison_sha256': hash_file(COMPARISON),
        'helper_sha256': {p: hash_file(ROOT / p) for p in (
            'scripts/circuit_tour.py', 'scripts/circuit_tour_analysis.py',
            'src/flyonenomics/drive/background.py', 'data/provenance.json')},
        'engine_order_int64_le_sha256': hashlib.sha256(np.asarray(registry.root_ids, dtype='<i8').tobytes()).hexdigest(),
        'groups': {g: {'n': len(idx), 'kind': 'drive' if g in drive else 'aggregate_or_courtship',
                        'indices_int64_le_sha256': hashlib.sha256(np.asarray(idx, dtype='<i8').tobytes()).hexdigest()}
                   for g, idx in indices.items()},
        'seeds': list(SEEDS),
        'within_pair_order': [[SEEDS[i], SEEDS[j]] for i, j in zip(PAIR_I, PAIR_J)],
        'method': {
            'rate_window_s': 10, 'settle_excluded_s': 2,
            'courtship_rate_window': 'counts_on + counts_off over 10 s; effects retain separate 5 s ON/OFF windows',
            'wasserstein': 'exact sum of absolute empirical CDF differences on the 0.1 Hz count lattice; equal neuron weights',
            'pooled_cross': 'concatenate all ten per-neuron rate samples per engine, NOT mean per-neuron rates',
            'ratio_numerator': 'mean of the ten paired-seed cross-engine W1 distances',
            'ratio_denominator': 'median of 45 distinct-seed W1 distances within the named engine; pooled_engines uses all 90',
            'paired_seeds': 'same numerical labels, different RNG streams; no identical-input assumption',
            'bootstrap': {'draws': BOOTSTRAP_DRAWS, 'generator': 'PCG64', 'seed': BOOTSTRAP_SEED,
                          'interval': '2.5/97.5 percentiles; descriptive, no multiplicity adjustment',
                          'unit': 'ten whole seed blocks sampled with replacement; same blocks across engines and conditions',
                          'within': 'all 45 pairs recomputed per draw; duplicate originals have zero distance; never resample pairs or neurons',
                          'zero_denominator': 'null estimate/interval; report zero draws and conditional finite bounds separately'},
            'effect_spread': 'sqrt(mean of all 45 squared Brian2 effect pair differences / 2) = sample SD of ten paired effects',
            'effect_sign': 'CUDA mean paired effect minus Brian2 mean paired effect; within each engine condition minus own control',
            'effect_scope': 'all published paired rate, distribution, synchrony and specificity effects; latencies are absolute, not paired effects',
        },
        'sources': {family: {engine: str(path) for engine, path in paths.items()}
                    for family, paths in SOURCES.items()},
        'inventory': {}, 'raw_sha256': {}, 'conditions': {},
    }
    observed = {}
    for family, paths in SOURCES.items():
        inventories = {engine: discover(path) for engine, path in paths.items()}
        result['inventory'][family] = inventories
        common = set(inventories['brian']) & set(inventories['cuda'])
        ordered = conditions() if family == 'tour' else dose_conditions()
        if common != set(ordered):
            raise ValueError(f'condition inventory differs from the recorded design: {family}, {common}')
        for condition in ordered:
            counts, observed[condition] = {}, {}
            for engine, path in paths.items():
                if sorted(inventories[engine][condition]) != list(SEEDS):
                    raise ValueError(f'incomplete seed cohort: {family}/{engine}/{condition}')
                counts[engine], observed[condition][engine] = [], []
                old_hashes = ({key.removeprefix(engine + '/'): value for key, value in comparison['raw_sha256'].items()
                               if key.startswith(engine + '/')} if family == 'tour' else None)
                for seed in SEEDS:
                    row, arrays, hashes = load_outcome(path, condition, seed, indices, provenance, old_hashes)
                    counts[engine].append(arrays['measure'])
                    observed[condition][engine].append(observables(row, arrays, indices))
                    result['raw_sha256'].update({f'{family}/{engine}/{name}': digest for name, digest in hashes.items()})
                counts[engine] = np.stack(counts[engine])
            result['conditions'][condition] = {
                'family': family,
                'groups': {group: rate_agreement(counts['brian'][:, idx], counts['cuda'][:, idx], draws)
                           for group, idx in indices.items()},
            }
            print(f'{family}/{condition}', flush=True)
    result['paired_effects'] = effect_agreement(observed, comparison, draws)
    OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(f'Wrote {OUTPUT}: {len(result["conditions"])} conditions, {len(result["paired_effects"])} paired effects')


if __name__ == '__main__':
    main()
