#!/usr/bin/env python3
"""One-way GABA dose playback: five NeuroMechFly bodies, wings and legs from motor spikes.

Requires the isolated scripts/courtship_body/.venv; never imports the brain engine.
Plays the recorded exact-tick replays of the resting run and four dose runs of one
seed. Wings use playback.py's rule on a ten times wider scale (70 degrees at +400
spikes/s per side, not +40); legs lift by their motor pool's rate above rest. The
resting replay recorded no leg motor spikes, so its legs stand still.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

import playback
from playback import FPS, LEGS, LIFT, ON_START, ROOT, SECONDS, DT

# (condition, label); line breaks are where the label wraps under its body.
DOSES = (('block-0.25', 'Quarter of GABA\nreceptors blocked'),
         ('block-0.75', 'Three quarters blocked'),
         ('block-1.00', 'All blocked'),
         # rescue = GABA conductance x0.25 plus glutamate-gated chloride x3
         ('rescue-2.00', 'Three quarters blocked\nplus rescue drug'))
MEASURE_TICKS = 100000  # 10 s measure window after the 2 s settle
# Wing scale for all five bodies of this clip: the drugs drive the wing cells about
# ten times harder than courtship input, so the courtship scale (40) saturates.
WING_HZ = 400.


def leg_pools(index):
    """Engine indices of each leg's typed motor neurons, by soma side and leg subclass."""
    inventory = json.loads((ROOT / 'validation/records/p2/malecns-populations.json').read_text())
    pools = defaultdict(list)
    for row in inventory['motor_neurons']['typed_leg']:
        pools[row['somaSide'] + {'fl': 'F', 'ml': 'M', 'hl': 'H'}[row['subclass']]].append(
            index[int(row['bodyId'])])
    return {leg: np.array(sorted(pools[leg])) for leg in LEGS}


def load_dose(outcomes, seed, condition, index, pools):
    """Wing cell and leg pool event ticks from 0 (measure onset), checked against the outcome."""
    counts_path = outcomes / f'seed-{seed}-{condition}.npz'
    spikes_path = outcomes / f'seed-{seed}-{condition}-spikes.npz'
    outcome = json.loads(counts_path.with_suffix('.json').read_text())
    meta = json.loads(spikes_path.with_suffix('.json').read_text())
    if (outcome.get('schema') != 'circuit-tour-v1' or outcome['condition'] != condition
            or outcome['seed'] != seed
            or [list(w) for w in outcome['windows']] != [['settle', 2.0], ['measure', 10.0]]
            or hashlib.sha256(counts_path.read_bytes()).hexdigest() != outcome['counts_sha256']):
        raise ValueError(f'dose outcome differs from its run record: {condition}')
    if (meta.get('kind') != 'visualisation-aid-not-new-outcome' or meta.get('condition') != condition
            or meta.get('seed') != seed or meta.get('dt_ms') != 0.1
            or not meta.get('recorded_full_neuron_counts_equal')
            or not meta.get('selected_event_counts_equal')
            or meta.get('source_outcome_sha256') != outcome['counts_sha256']
            or hashlib.sha256(spikes_path.read_bytes()).hexdigest() != meta['spike_sha256']):
        raise ValueError(f'spike replay provenance does not match the outcome: {condition}')
    with np.load(spikes_path, allow_pickle=False) as arr, np.load(counts_path, allow_pickle=False) as raw:
        ids, ticks, counts = arr['neuron_idx'], arr['tick'], raw['counts_measure']
        if not np.array_equal(np.sort(arr['leg_idx']), np.sort(np.concatenate(list(pools.values())))):
            raise ValueError('replay leg motor neurons differ from the typed leg inventory')
    if len(counts) != len(index):
        raise ValueError('engine order length does not match count vector')
    if ticks.min() < ON_START or ticks.max() >= ON_START + MEASURE_TICKS:
        raise ValueError('spike times outside the measure window')
    selected = {name: np.array([index[root]]) for name, root in playback.neurons().items()}
    selected.update({f'leg_{leg}': pool for leg, pool in pools.items()})
    events = {}
    for name, cells in selected.items():
        keep = np.isin(ids, cells)
        if keep.sum() != counts[cells].sum():
            raise ValueError(f'spike/outcome count mismatch: {condition} {name}')
        events[name] = (ticks[keep] - ON_START).astype(np.int64)
    return events


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--outcomes', type=Path, required=True, help='dose outcome folder (*.npz, *-spikes.npz)')
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--control-counts', type=Path, required=True, help='same-seed resting NPZ')
    p.add_argument('--control-spikes', type=Path, required=True, help='same-seed resting -spikes.npz')
    p.add_argument('--engine-order', type=Path, required=True)
    p.add_argument('--poses', type=Path, required=True, help='output geometry trajectories for render.py')
    a = p.parse_args()
    index = playback.engine_index(a.engine_order)
    pools = leg_pools(index)
    resting, resting_events = playback.load_spikes(a.control_spikes, a.control_counts, index)
    if resting['condition'] != 'control' or resting['seed'] != a.seed:
        p.error('need the resting (control) run of the same seed')
    baseline = playback.on_rates(a.control_counts, index)  # the wing rule's rest rate, as in courtship
    with np.load(a.control_counts, allow_pickle=False) as raw:
        rest_counts = raw['counts_on'] + raw['counts_off']
    rest_hz = {leg: rest_counts[pool].sum() / SECONDS / len(pool) for leg, pool in pools.items()}
    nsteps = round(SECONDS / DT)
    m = playback.model()
    runs, lifts = {}, {}
    runs['resting'] = playback.simulate(m, resting_events, baseline, np.zeros((len(LEGS), nsteps)), WING_HZ)
    for condition, _ in DOSES:
        events = load_dose(a.outcomes, a.seed, condition, index, pools)
        lifts[condition] = np.stack([playback.leg_lift(events[f'leg_{leg}'], len(pools[leg]),
                                                       rest_hz[leg], nsteps) for leg in LEGS])
        runs[condition] = playback.simulate(m, events, baseline, lifts[condition], WING_HZ)
    a.poses.parent.mkdir(parents=True, exist_ok=True)
    labels = np.array(['Resting brain', *(label for _, label in DOSES)])
    np.savez_compressed(a.poses, fps=np.array(FPS), on_seconds=np.array(SECONDS), **playback.geometry(m),
                        bodies=np.array(list(runs)), offsets=np.linspace(-9.2, 9.2, len(runs)),
                        labels_on=labels, labels_off=labels, label_size=np.array(.0118),
                        **{f'{fly}_{key}': value for fly, run in runs.items()
                           for key, value in zip(('positions', 'rotations'), run[:2])})
    full = np.degrees(max(abs(v) for v in LIFT.values()))
    print('leg rest rate, spikes/s per neuron:', {leg: round(v, 2) for leg, v in rest_hz.items()})
    for fly, (_, _, angles, _) in runs.items():
        wing, top = np.degrees(np.abs(angles)).mean(axis=0), np.degrees(np.abs(angles)).max(axis=0)
        line = f'{fly}: wing angle mean/max L {wing[0]:.1f}/{top[0]:.1f} R {wing[1]:.1f}/{top[1]:.1f} deg'
        if fly in lifts:
            lift = lifts[fly] * full
            line += '; leg lift mean/max deg ' + ' '.join(
                f'{leg} {mean:.1f}/{top:.1f}' for leg, mean, top in zip(LEGS, lift.mean(1), lift.max(1)))
        print(line)


if __name__ == '__main__':
    main()
