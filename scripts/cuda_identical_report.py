#!/usr/bin/env python3
"""Render measured identical-input counts, distributions, means and timing."""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flyonenomics.io import read_json


def main():
    folder = ROOT / 'validation/records/p2'
    data = read_json(folder / 'male-cuda-identical-comparison.json')
    total_spikes = sum(f['spikes'] for r in data['rows'] for f in r['runs'][0]['spike_files'])
    lines = ['# Identical-input CUDA / Brian2 comparison', '',
             'Signed differences are CUDA minus Brian2. Every count comparison includes all 162,517 neurons. '
             'ON is [2,7) s and OFF is [7,12) s; no stimulus changes between these windows. '
             'Both intact rest and GABA removal use clamped dopamine. Two seconds of settling precede counting, '
             'but first divergence includes settling. The reference engine, model and substrate are unchanged.', '',
             'Input events are Binomial(100, 0.001) multiplicities at each 0.1 ms tick for each of 15,016 sensory targets. '
             'Both engines read the same hashed saved events; random inputs are disabled. The virtual sources in '
             'Brian2 preserve simultaneous-event multiplicity. GPU background draws are replaced, not added.', '',
             '## Per-neuron counts', '',
             '| Seed | Condition | Window | Exactly matching | Mean difference | Mean absolute | RMS | Signed range | Absolute p50 / p90 / p99 |',
             '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for r in data['rows']:
        for w in ('on', 'off', 'measure'):
            d = r['windows'][w]
            q = d['abs_quantiles']
            lines.append(f"| {r['seed']} | {r['condition']} | {w} | {d['exact']:,} | {d['mean']:.6f} | {d['mean_abs']:.6f} | {d['rms']:.6f} | {d['min']} to {d['max']} | {q['50']:g} / {q['90']:g} / {q['99']:g} |")
    lines += ['', 'The complete signed integer histograms, settling counts and all requested absolute quantiles are in the companion JSON. '
              'Equal window counts do not imply equal spike times; silent neurons contribute exact count matches.', '',
              '## First unequal output spike', '',
              '| Seed | Condition | First tick | Time from initialization, ms | Brian2-only neurons at that tick | CUDA-only neurons at that tick | Unequal neuron/tick pairs over 12 s |',
              '|---|---|---:|---:|---|---|---:|']
    for r in data['rows']:
        d = r['first_spike_divergence']
        if d is None:
            lines.append(f"| {r['seed']} | {r['condition']} | none | none | — | — | 0 |")
        else:
            lines.append(f"| {r['seed']} | {r['condition']} | {d['tick']} | {d['ms']:.1f} | {d['brian_only_idx']} | {d['cuda_only_idx']} | {r['spike_symmetric_difference']:,} |")
    lines += ['', 'This is the first spike divergence at the 0.1 ms resolution, not the first floating-point state difference. '
              'Neuron IDs in this table are zero-based engine indices. All spike archives were hash checked and compared as sorted neuron/tick pairs.', '',
              '## Group rates, Hz', '',
              'Arithmetic means over the two seeds; full per-seed rates and group sizes are in the JSON. '
              'Columns give Brian2 / CUDA. The ten-second mean is the average of the two five-second windows.']
    for condition in ('control', 'off-gaba'):
        rows = [r for r in data['rows'] if r['condition'] == condition]
        lines += ['', f'### {condition}', '', '| Group | Neurons | ON Brian2 / CUDA | OFF Brian2 / CUDA | 10 s Brian2 / CUDA |', '|---|---:|---:|---:|---:|']
        for g, size in rows[0]['runs'][0]['group_sizes'].items():
            cells = []
            for w in ('on', 'off', 'measure'):
                vals = [np.mean([r['runs'][b]['group_hz'][w][g] for r in rows]) for b in (0, 1)]
                cells.append(f'{vals[0]:.6f} / {vals[1]:.6f}')
            lines.append(f"| {g} | {size:,} | " + ' | '.join(cells) + ' |')
    lines += ['', '## Paired GABA-minus-intact count effects', '',
              'Here the compared arrays are each engine\'s per-neuron knockout-minus-control count differences, not its absolute counts.', '',
              '| Seed | Window | Exactly matching effect | Mean cross-engine difference | Mean absolute | RMS | Signed range |',
              '|---|---|---:|---:|---:|---:|---:|']
    for r in data['paired_gaba_effect']:
        for w, d in r['windows'].items():
            lines.append(f"| {r['seed']} | {w} | {d['exact']:,} | {d['mean']:.6f} | {d['mean_abs']:.6f} | {d['rms']:.6f} | {d['min']} to {d['max']} |")
    lines += ['', '## Replay timing', '',
              'Replay timing is not the standard stochastic-input benchmark: Brian2 uses one-second network runs with clamped parameters, '
              'while CUDA uses 10 ms full-spike-output chunks. Input decoding/upload and archive compression are separately timed. '
              'Neither engine draws background random numbers during replay; disabling Brian2 PoissonInput removes its runtime RNG cost. '
              'Brian2 compilation on the first network run is included in its stepping column. '
              'Do not derive an original-engine speedup from this differently instrumented harness.', '',
              '| Backend | Seed | Condition | Build s | Input load s | Step and spike extraction s | Archive s | Total s |',
              '|---|---|---|---:|---:|---:|---:|---:|']
    for r in data['rows']:
        for m in r['runs']:
            lines.append(f"| {m['backend']} | {m['seed']} | {m['condition']} | {m['build_s']:.3f} | {m['input_load_s']:.3f} | {m['stepping_s']:.3f} | {m['archive_s']:.3f} | {m['total_s']:.3f} |")
    lines += ['', '## Interpretation', '',
              ('Output spike trains differ despite identical external events. The engines are **not numerically equivalent at the spike-train level**. '
               'The count and group-rate tables quantify how much their outputs differ without an invented acceptance threshold. '
               'This removes random-stream mismatch as the explanation for these replay discrepancies. '
               'It does not decompose rounding into update arithmetic, unit scaling and atomic addition order, or establish equivalence across untested conditions.'
               if any(r['first_spike_divergence'] for r in data['rows']) else
               f'All {total_spikes:,} saved neuron/tick pairs match in these four runs: the engines are numerically equivalent in observed spike output for these inputs. No spike divergence was observed during any 12-second run. This does not establish bitwise state equivalence or agreement in every condition.'), '',
              'The model receives injected input; the fly does not see. Visual input elsewhere is injected at TuBu; these runs use dark sensory-background input.', '',
              'Sources: `male-cuda-identical-plan.md`, `male-cuda-identical-inputs.json`, '
              '`male-cuda-identical-comparison.json` and `male-cuda-identical-receipts.json`. '
              'Raw Brian2 outputs are under `camber-runs/cuda-identical/brian/`; CUDA outputs are under '
              '`camber-runs/cuda-identical/downloads/` with a `cuda` symlink. The receipt names the Modal archive.']
    (folder / 'male-cuda-identical-comparison.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
