#!/usr/bin/env python3
"""One-way MaleCNS motor spike playback into two articulated NeuroMechFly bodies.

Requires the isolated scripts/courtship_body/.venv; never imports the brain engine.
Plays the recorded exact-tick wing motor spikes of a matched control run and a
P1-high run through the same transfer function, one body each.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import flygym
from flygym.preprogrammed import get_preprogrammed_pose
import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MJCF = Path(flygym.__file__).parent / 'data/mjcf/neuromechfly_seqik_kinorder_ypr.xml'
TYPES = ('ps1 MN', 'hg1 MN')
SIDES = ('L', 'R')
SECONDS, FPS, DT = 10., 60, .0001
ON_START, OFF_START, WINDOW_TICKS = 20000, 70000, 50000  # settle 2 s, ON 5 s, OFF 5 s
LEGS = ('LF', 'LM', 'LH', 'RF', 'RM', 'RH')
# Leg display rule: a full lift raises the femur and folds the tibia by 30
# degrees each, which lifts the foot. Chosen direction, not a muscle action.
LIFT = {'Femur': -math.radians(30), 'Tibia': math.radians(30)}
LIFT_HZ = 30.  # extra spikes/s per pool neuron that give a full lift
WING_HZ = 40.  # extra ps1+hg1 spikes/s per side that give the full 70 degree wing


def neurons():
    inventory = json.loads((ROOT / 'validation/records/p2/malecns-populations.json').read_text())
    rows = inventory['motor_neurons']['typed_wing']
    ids = {r['instance']: int(r['bodyId']) for r in rows if r['type'] in TYPES}
    names = [f'{typ}_{side}' for side in SIDES for typ in TYPES]
    if not all(name in ids for name in names):
        raise ValueError(f'wing motor identities missing: {set(names) - ids.keys()}')
    return {name: ids[name] for name in names}


def engine_index(engine_order):
    with open(engine_order, newline='') as file:
        return {int(row['root_id']): i for i, row in enumerate(csv.DictReader(file))}


def load_outcome(path):
    path = Path(path)
    metadata = json.loads(path.with_suffix('.json').read_text())
    if metadata.get('schema') != 'circuit-tour-v1':
        raise ValueError('expected circuit-tour-v1 outcome archive')
    if [list(w) for w in metadata['windows']] != [['settle', 2.0], ['on', 5.0], ['off', 5.0]]:
        raise ValueError('expected settle 2 s, ON 5 s, OFF 5 s windows')
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['counts_sha256']:
        raise ValueError('archive hash differs from run record')
    return metadata


def on_rates(path, index):
    """Per-cell mean rate over the recorded ON window (control: spontaneous baseline)."""
    with np.load(path, allow_pickle=False) as arr:
        counts = arr['counts_on']
        if len(counts) != len(index):
            raise ValueError('engine order length does not match count vector')
        return {name: float(counts[index[root]]) / 5. for name, root in neurons().items()}


def load_spikes(path, counts_path, index):
    """Per-neuron event ticks from 0 (ON onset), totals checked against the outcome."""
    path, counts_path = Path(path), Path(counts_path)
    meta = json.loads(path.with_suffix('.json').read_text())
    outcome = load_outcome(counts_path)
    if (meta.get('kind') != 'visualisation-aid-not-new-outcome'
            or meta.get('condition') != outcome['condition'] or meta.get('seed') != outcome['seed']
            or meta.get('dt_ms') != 0.1 or not meta.get('recorded_full_neuron_on_off_counts_equal')
            or meta.get('source_outcome_sha256') != outcome['counts_sha256']
            or hashlib.sha256(path.read_bytes()).hexdigest() != meta['spike_sha256']):
        raise ValueError('spike replay provenance does not match the selected outcome')
    with np.load(path, allow_pickle=False) as arr, np.load(counts_path, allow_pickle=False) as counts:
        events = {}
        for name, root in neurons().items():
            idx = index[root]
            parts = []
            for window, start in (('on', ON_START), ('off', OFF_START)):
                times = arr[f'{window}_tick'][arr[f'{window}_idx'] == idx]
                if len(times) != int(counts[f'counts_{window}'][idx]):
                    raise ValueError(f'spike/outcome count mismatch: {name}, {window}')
                if len(times) and (times.min() < start or times.max() >= start + WINDOW_TICKS):
                    raise ValueError('spike times outside ON/OFF window')
                parts.append(times - ON_START)
            events[name] = np.concatenate(parts).astype(np.int64)
    return outcome, events


def model():
    # FlyGym 1.1.0's NeuroMechFly v2 mesh has R/L wing BODIES but no wing
    # JOINTS. Add two single-axis abduction hinges and position actuators in
    # memory; do not alter the upstream MJCF or the brain simulation.
    tree = ET.parse(MJCF)
    root = tree.getroot()
    for side in SIDES:
        wing = root.find(f".//body[@name='{side}Wing']")
        ET.SubElement(wing, 'joint', name=f'courtship_{side}', type='hinge', axis='0 0 1',
                      limited='true', range='-1.4 1.4', damping='0.01')
        actuator = root.find('actuator')
        if actuator is None:
            actuator = ET.SubElement(root, 'actuator')
        ET.SubElement(actuator, 'position', name=f'courtship_{side}', joint=f'courtship_{side}',
                      kp='2', kv='0.03', ctrlrange='-1.4 1.4', ctrllimited='true')
    assets = {f'../mesh/{p.name}': p.read_bytes() for p in (MJCF.parent.parent / 'mesh').glob('*.stl')}
    m = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'), assets=assets)
    # The body is fixed at the thorax and its legs are unactuated. Hold FlyGym's
    # standing tripod pose by switching gravity off; the wing angles are
    # identical to a gravity-on run of the same replay.
    m.opt.gravity[:] = 0
    return m


def geometry(m):
    result = {}
    for i in range(m.nmesh):
        v, n = int(m.mesh_vertadr[i]), int(m.mesh_vertnum[i])
        f, nf = int(m.mesh_faceadr[i]), int(m.mesh_facenum[i])
        result[f'vert_{i}'] = m.mesh_vert[v:v+n].copy()
        result[f'face_{i}'] = m.mesh_face[f:f+nf].copy()
    result['mesh_ids'] = m.geom_dataid.copy()
    result['names'] = np.array([mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) for i in range(m.ngeom)])
    return result


def leg_lift(ticks, pool_size, rest_hz, nsteps):
    """0..1 lift of one leg: its pool's causal 200 ms rate per neuron, above rest."""
    sums = np.cumsum(np.r_[0, np.bincount(ticks, minlength=nsteps)[:nsteps]])
    steps = np.arange(1, nsteps + 1)
    rate = (sums[steps] - sums[np.maximum(0, steps - 2000)]) / .2 / pool_size
    return np.minimum(1., np.maximum(0., rate - rest_hz) / LIFT_HZ)


def simulate(m, events, baseline, lift=None, wing_hz=WING_HZ):
    d = mujoco.MjData(m)
    pose = get_preprogrammed_pose('tripod').joint_pos
    for joint, angle in pose.items():
        if mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, joint) >= 0:
            d.qpos[m.joint(joint).qposadr[0]] = angle
    if lift is not None:  # (legs, steps) array from leg_lift, rows in LEGS order
        # Legs are posed through their joint angles, not driven by forces:
        # the thorax is fixed, so leg motion cannot move the wings or body.
        posed = [(leg, joint) for leg in LEGS for joint in LIFT]
        leg_qpos = np.array([m.joint(f'joint_{leg}{joint}').qposadr[0] for leg, joint in posed])
        leg_dof = np.array([m.joint(f'joint_{leg}{joint}').dofadr[0] for leg, joint in posed])
        leg_rest = np.array([pose[f'joint_{leg}{joint}'] for leg, joint in posed])
        leg_row = np.array([LEGS.index(leg) for leg, _ in posed])
        leg_gain = np.array([LIFT[joint] for _, joint in posed])
    # MuJoCo body simulation at its native 0.1 ms step. 60 fps exports only
    # display poses: sub-frame vibration cannot be resolved in 60 fps video.
    if m.opt.timestep != DT:
        raise ValueError('recorded windows require 0.1 ms ticks')
    frames, nsteps = round(SECONDS * FPS), round(SECONDS / DT)
    positions = np.empty((frames, m.ngeom, 3), dtype=np.float32)
    rotations = np.empty((frames, m.ngeom, 3, 3), dtype=np.float32)
    angles = np.empty((frames, 2), dtype=np.float32)
    targets = np.empty_like(angles)
    impulses = {name: np.bincount(ticks, minlength=nsteps)[:nsteps] for name, ticks in events.items()}
    # Causal 200 ms window for posture. Matched control mean removes
    # spontaneous motor firing; no subtraction of unmatched spike times.
    sums = {side: np.cumsum(np.r_[0, impulses[f'ps1 MN_{side}'] + impulses[f'hg1 MN_{side}']])
            for side in SIDES}
    jitter = np.zeros(2)
    decay = math.exp(-DT / .02)  # chosen 20 ms visible mechanical response
    frame = 0
    for step in range(nsteps):
        for j, side in enumerate(SIDES):
            recent = sums[side][step + 1] - sums[side][max(0, step + 1 - 2000)]
            rate = recent / .2  # zero-padded start, no first-spike singularity
            excess = max(0., rate - baseline[f'ps1 MN_{side}'] - baseline[f'hg1 MN_{side}'])
            extension = math.radians(70) * min(1., excess / wing_hz)
            # Exact recorded ps1/hg1 spike ticks cause opposing short
            # displacement impulses, with NO invented sine wave/carrier.
            jitter[j] = (jitter[j] * decay + math.radians(2.) * impulses[f'ps1 MN_{side}'][step]
                         - math.radians(1.) * impulses[f'hg1 MN_{side}'][step])
            target = (1 if side == 'L' else -1) * max(0., min(1.4, extension +
                                                   max(-math.radians(4), min(math.radians(4), jitter[j]))))
            d.ctrl[m.actuator(f'courtship_{side}').id] = target
        if lift is not None:
            d.qpos[leg_qpos] = leg_rest + leg_gain * lift[leg_row, step]
            d.qvel[leg_dof] = 0
        mujoco.mj_step(m, d)
        # Export a pose at the nearest physics step to each 60 fps frame.
        if frame < frames and step + 1 >= round((frame + 1) * SECONDS / frames / DT):
            for j, side in enumerate(SIDES):
                angles[frame, j] = d.qpos[m.joint(f'courtship_{side}').qposadr[0]]
                targets[frame, j] = d.ctrl[m.actuator(f'courtship_{side}').id]
            positions[frame] = d.geom_xpos
            rotations[frame] = d.geom_xmat.reshape(m.ngeom, 3, 3)
            frame += 1
    return positions, rotations, angles, targets


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--counts', type=Path, required=True, help='recorded P1 circuit-tour-v1 per-neuron NPZ')
    p.add_argument('--spikes', type=Path, required=True, help='matching seed/condition -spikes.npz replay')
    p.add_argument('--control-counts', type=Path, required=True, help='matched-seed control NPZ')
    p.add_argument('--control-spikes', type=Path, required=True, help='matched-seed control -spikes.npz')
    p.add_argument('--engine-order', type=Path, required=True)
    p.add_argument('--poses', type=Path, required=True, help='output geometry trajectories for render.py')
    p.add_argument('--csv', type=Path, required=True, help='output wing joint angles for both bodies')
    a = p.parse_args()
    index = engine_index(a.engine_order)
    courtship, courtship_events = load_spikes(a.spikes, a.counts, index)
    resting, resting_events = load_spikes(a.control_spikes, a.control_counts, index)
    if courtship['condition'] != 'P1-high' or resting['condition'] != 'control' or courtship['seed'] != resting['seed']:
        p.error('need a P1-high run and the control run of the same seed')
    baseline = on_rates(a.control_counts, index)
    m = model()
    runs = {'resting': simulate(m, resting_events, baseline),
            'courtship': simulate(m, courtship_events, baseline)}
    a.csv.parent.mkdir(parents=True, exist_ok=True)
    with a.csv.open('w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(('time_s', *(f'{fly}_{col}' for fly in runs for col in
                                     ('left_deg', 'right_deg', 'left_target_deg', 'right_target_deg'))))
        for frame in range(round(SECONDS * FPS)):
            row = [f'{(frame + 1) / FPS:.6f}']
            for _, _, angles, targets in runs.values():
                row += [f'{x:.4f}' for x in (*np.degrees(angles[frame]), *np.degrees(targets[frame]))]
            writer.writerow(row)
    a.poses.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.poses, fps=np.array(FPS), on_seconds=np.array(5.), **geometry(m),
                        bodies=np.array(list(runs)), offsets=np.array([-3.2, 3.2]),
                        labels_on=np.array(['Resting brain', 'Courtship neurons on']),
                        labels_off=np.array(['Resting brain', 'Courtship neurons off']),
                        label_size=np.array(.0185),
                        **{f'{fly}_{key}': value for fly, run in runs.items()
                           for key, value in zip(('positions', 'rotations'), run[:2])})
    for fly, (_, _, angles, _) in runs.items():
        print(f'{fly}: wing range {np.degrees(angles.min(axis=0))} to {np.degrees(angles.max(axis=0))} degrees')


if __name__ == '__main__':
    main()
