#!/usr/bin/env python3
"""Extract measured speed/cost records from completed CUDA receipts; no simulations."""
import json
from pathlib import Path
from flyonenomics.io import read_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    receipts = read_json(ROOT / 'validation/records/p2/male-cuda-receipts.json')
    budget = read_json(ROOT / 'validation/records/p2/male-cuda-budget-update.json')
    charged = [r for r in receipts if r['label'] in budget['carry_in_labels']
               or r['submitted_at'] >= budget['recorded_at']]
    rows = []
    for r in receipts:
        if 'result' not in r:
            continue
        x = r['result']
        rows.append({'label': r['label'], 'app_id': r['app_id'], 'mode': r['mode'], 'tasks': r['tasks'],
                     'implementation': ('clamped rest' if r['mode'] == 'rest' else
                                        'CUDA LIF + CUDA dopamine' if 'modulation_check_max_abs' in x
                                        else 'CUDA LIF + CPU dopamine'),
                     'diagnostic_cpu_comparison': r.get('check_modulation', False),
                     **x,
                     'function_wall_s_per_brain_sim_s': x['wall_s'] / (x['batch'] * x['simulated_s']),
                     'client_elapsed_s': r['completed_at'] - r['submitted_at'],
                     'client_wall_s_per_brain_sim_s': (r['completed_at'] - r['submitted_at']) / (x['batch'] * x['simulated_s']),
                     'projected_usd': r['projected_usd'], 'actual_metered_usd': r.get('actual_metered_usd'),
                     'source_sha': r['source_sha']})
    record = {'schema': 'cuda-speed-v1',
              'units': 'wall seconds; simulated seconds per batch member; rates normalized by batch where stated',
              'note': 'One measured run per configuration. Pilot timings start from initialized state, without a settling window. Full tour timings include the frozen settle/on/off windows. No pass criterion.',
              'baseline_context': 'The task brief reports about 30 wall s / simulated s for Brian2 on this Mac; not a new same-hardware benchmark.',
              'measurements': rows,
              'total_modal_metered_usd': sum(r.get('actual_metered_usd') or 0 for r in receipts),
              'billing_pending': [r.get('app_id') for r in receipts if r.get('actual_metered_usd') is None],
              'conservative_accounted_usd': sum(r.get('accounted_usd', r['reserved_usd']) for r in receipts),
              'remaining_budget_update': {
                  'cap_usd': budget['remaining_metered_cap_usd'],
                  'metered_usd': sum(r.get('actual_metered_usd') or 0 for r in charged),
                  'conservative_accounted_usd': sum(r.get('accounted_usd', r['reserved_usd']) for r in charged),
                  'labels': [r['label'] for r in charged],
                  'note': 'Counts entire carry-in calls, including their pre-update portions.'}}
    dest = ROOT / 'validation/records/p2/male-cuda-speed.json'
    dest.write_text(json.dumps(record, indent=2) + '\n')
    lines = ['# Measured CUDA speed', '', record['note'], '',
             'Stepping includes device work, output transfers and host result collection, but excludes build and archive writing. Function total includes both; it excludes Modal startup, queueing and downloads. Full client elapsed times are in the JSON. Diagnostic CPU comparisons are not speed benchmarks.', '',
             '| GPU | Batch | Duration (s) | Chunk (ms) | Mode | Build (s) | Step (s) | Step / brain-s | Function total / brain-s |',
             '|---|---:|---:|---:|---|---:|---:|---:|---:|']
    for r in rows:
        if r['implementation'] == 'CUDA LIF + CPU dopamine' or r['diagnostic_cpu_comparison']:
            continue
        lines.append(f'| {r["gpu"]} | {r["batch"]} | {r["simulated_s"]:g} | {r["chunk_ms"]:g} | {r["mode"]} | '
                     f'{r["build_s"]:.2f} | {r["stepping_s"]:.3f} | {r["per_brain_wall_s_per_sim_s"]:.4f} | '
                     f'{r["function_wall_s_per_brain_sim_s"]:.4f} |')
    lines += ['', f'Modal metered cost across all submits (including failed builds/diagnostics): ${record["total_modal_metered_usd"]:.6f}.',
              f'Conservative elapsed-time budget accounting: ${record["conservative_accounted_usd"]:.6f} of the $15 cap.',
              f'Apps awaiting billing: {record["billing_pending"]}.',
              f'Counted against the later $8 remaining cap: ${record["remaining_budget_update"]["metered_usd"]:.6f} metered, '
              f'${record["remaining_budget_update"]["conservative_accounted_usd"]:.6f} conservative. Entire carry-in calls are counted.',
              '', record['baseline_context'], '']
    dest.with_suffix('.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    main()
