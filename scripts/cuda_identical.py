#!/usr/bin/env python3
"""Frozen identical-event comparison; no changes to BrianEngine or model data."""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flyonenomics.io import hash_file, load_npy, read_json
from scripts.circuit_tour import build, GROUPS, pins

RAW = ROOT / 'camber-runs/cuda-identical'
RECORD = ROOT / 'validation/records/p2'


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def generate(dest):
    from flyonenomics.registry import build_registry
    from flyonenomics.drive.rest import load_drive_rest, rest_background_weights
    from flyonenomics.types import load_params
    registry = build_registry('male-cns:v1.0')
    params = load_params(ROOT / 'data/params-v0.2.yaml')
    weights = rest_background_weights(registry, load_drive_rest(ROOT / 'data/drive-male-cns-v1.0.yaml'), params)
    targets = np.flatnonzero(weights).astype(np.int32)
    dest.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(dest / 'targets.npz', targets=targets, weights_mv=weights[targets], root_ids=registry.root_ids[targets])
    dt = float(params.get('lif.dt'))
    ticks = round(1000 / dt)
    n, p = int(params.get('bg.n_bg')), float(params.get('bg.r_bg')) * dt / 1000
    rows = []
    for seed in (501, 502):
        rng = np.random.Generator(np.random.PCG64(seed))
        for second in range(12):
            # Fixed 10 ms generation blocks are part of the reproducible draw order.
            dense = np.concatenate([rng.binomial(n, p, (100, len(targets))).astype(np.uint8)
                                    for _ in range(ticks // 100)])
            flat = np.flatnonzero(dense.ravel()).astype(np.uint32)
            multiplicity = dense.ravel()[flat]
            name = f'seed-{seed}-second-{second:02d}.npz'
            np.savez_compressed(dest / name, flat=flat, multiplicity=multiplicity)
            row = dict(file=name, sha256=hash_file(dest / name), seed=seed, second=second,
                       nonzero_events=len(flat), elementary_spikes=int(multiplicity.sum()),
                       max_multiplicity=int(multiplicity.max()))
            rows.append(row)
            print(json.dumps(row), flush=True)
    manifest = dict(schema='cuda-identical-events-v1', numpy=np.__version__, generator='PCG64',
                    seeds=[501, 502], dt_ms=dt, ticks_per_file=ticks, targets=len(targets),
                    targets_sha256=hash_file(dest / 'targets.npz'), binomial_n=n, binomial_p=p,
                    provenance=pins(), files=rows)
    save_json(dest / 'manifest.json', manifest)
    save_json(RECORD / 'male-cuda-identical-inputs.json', manifest)


def input_file(inputs, manifest, seed, second):
    row = next(r for r in manifest['files'] if r['seed'] == seed and r['second'] == second)
    path = inputs / row['file']
    if hash_file(path) != row['sha256']:
        raise ValueError(f'input hash mismatch: {path}')
    with load_npy(path) as data:
        return data['flat'], data['multiplicity']


def replay(backend, seed, condition, inputs, dest):
    if seed not in (501, 502) or condition not in ('control', 'off-gaba'):
        raise ValueError('outside the frozen plan')
    import brian2 as b
    manifest = read_json(inputs / 'manifest.json')
    if manifest['provenance'] != pins() or hash_file(inputs / 'targets.npz') != manifest['targets_sha256']:
        raise ValueError('input binding changed')
    with load_npy(inputs / 'targets.npz') as data:
        targets, weights = data['targets'], data['weights_mv']
    started = time.perf_counter()
    if backend == 'cuda':
        from flyonenomics.engine.cuda_engine import CUDAEngine
        engine, mod, registry, groups, _, params = build(condition, CUDAEngine(record_spikes=True))
    else:
        engine, mod, registry, groups, _, params = build(condition)
    mod.clamp_pools(True)
    mod.reset_fast()
    composed = mod.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)
    indices = {**groups, **{g: registry.population(g).idx for g in GROUPS}}
    indices['outside_sensory'] = np.setdiff1d(np.arange(registry.n), groups['sensory'])
    maxk = max(r['max_multiplicity'] for r in manifest['files'])
    if backend == 'brian':
        disabled = []
        for obj in engine._net.objects:
            if isinstance(obj, (b.PoissonInput, b.PoissonGroup)):
                obj.active = False
                disabled.append(obj.name)
        gen = b.SpikeGeneratorGroup(len(targets) * maxk, np.zeros(0, dtype=np.int32), np.zeros(0)*b.ms,
                                    sorted=True, name='replay_background')
        syn = b.Synapses(gen, engine._neu, 'w : volt', on_pre='g += w', delay=0*b.ms,
                         name='replay_background_syn')
        syn.connect(i=np.arange(len(targets)*maxk), j=np.repeat(targets, maxk))
        syn.w = (np.repeat(weights, maxk) * np.tile(np.arange(1, maxk+1), len(targets))) * b.mV
        # PoissonInput defaults to order 0 in the synapses slot; recurrent pre is -1.
        syn.pre.order = 0
        engine._net.add(gen, syn)
    else:
        disabled = ['CUDA random background replaced; extended rates zero']
        engine.cp.cuda.get_current_stream().synchronize()
    built = time.perf_counter() - started
    print(json.dumps(dict(event='built', backend=backend, seed=seed, condition=condition, seconds=built)), flush=True)
    dest.mkdir(parents=True, exist_ok=False)
    counts = {w: np.zeros(registry.n, dtype=np.int64) for w in ('settle', 'on', 'off')}
    outputs, input_s, step_s, archive_s = [], 0., 0., 0.
    for second in range(12):
        t = time.perf_counter()
        flat, multiplicity = input_file(inputs, manifest, seed, second)
        if backend == 'brian':
            source = ((flat % len(targets)) * maxk + multiplicity - 1).astype(np.int32)
            ticks = flat // len(targets) + second * manifest['ticks_per_file']
            gen.set_spikes(source, ticks.astype(np.float64) * engine.dt_ms * b.ms, sorted=True)
        else:
            dense = np.zeros((manifest['ticks_per_file'], len(targets)), dtype=np.uint8)
            dense.ravel()[flat] = multiplicity
            engine.set_background_events(targets, dense, second * manifest['ticks_per_file'])
        input_s += time.perf_counter() - t
        t = time.perf_counter()
        if backend == 'brian':
            before = int(engine._spk.num_spikes)
            # Clamped pools and constant parameters: no host intervention required.
            engine._net.run(1000*b.ms)
            idx = np.asarray(engine._spk.i[before:], dtype=np.int32)
            tick = np.rint(np.asarray(engine._spk.t[before:] / b.ms) / engine.dt_ms).astype(np.int32)
        else:
            ids, ts = [], []
            for _ in range(100):
                result = engine.run_chunk(10)
                spikes = engine.spikes(result.tick0)
                ids.append(spikes.idx)
                ts.append(spikes.tick.astype(np.int32))
            idx, tick = np.concatenate(ids), np.concatenate(ts)
        step_s += time.perf_counter() - t
        t = time.perf_counter()
        order = np.lexsort((idx, tick))
        idx, tick = idx[order], tick[order]
        counts['settle' if second < 2 else 'on' if second < 7 else 'off'] += np.bincount(idx, minlength=registry.n)
        path = dest / f'spikes-{second:02d}.npz'
        np.savez_compressed(path, idx=idx, tick=tick)
        outputs.append(dict(file=path.name, sha256=hash_file(path), spikes=len(idx)))
        archive_s += time.perf_counter() - t
        print(json.dumps(dict(event='second', backend=backend, seed=seed, condition=condition,
                              second=second, spikes=len(idx), elapsed_s=time.perf_counter()-started)), flush=True)
    counts['measure'] = counts['on'] + counts['off']
    np.savez_compressed(dest / 'counts.npz', **counts)
    sources = ['scripts/cuda_identical.py', 'src/flyonenomics/engine/brian_engine.py',
               'src/flyonenomics/engine/cuda_engine.py', 'src/flyonenomics/engine/cuda_tick.cu']
    row = dict(backend=backend, seed=seed, condition=condition, n=registry.n, edges=engine.n_syn,
               input_manifest_sha256=hash_file(inputs / 'manifest.json'), dopamine='clamped',
               provenance=pins(), source_sha256={p: hash_file(ROOT / p) for p in sources},
               machine=platform.platform(), python=platform.python_version(), numpy=np.__version__, brian2=b.__version__,
               build_s=built, input_load_s=input_s, stepping_s=step_s, archive_s=archive_s,
               total_s=time.perf_counter()-started, disabled_random_objects=disabled,
               counts_sha256=hash_file(dest / 'counts.npz'), spike_files=outputs,
               group_sizes={g: len(i) for g, i in indices.items()},
               group_hz={w: {g: float(c[i].mean() / (2 if w == 'settle' else 10 if w == 'measure' else 5))
                             for g, i in indices.items()} for w, c in counts.items()})
    if backend == 'cuda':
        row['gpu'] = engine.cp.cuda.runtime.getDeviceProperties(0)['name'].decode()
    save_json(dest / 'run.json', row)
    return row


def differences(a, b):
    d = b.astype(np.int64) - a.astype(np.int64)
    values, freq = np.unique(d, return_counts=True)
    return dict(exact=int(np.sum(d == 0)), n=len(d), mean=float(d.mean()), mean_abs=float(np.abs(d).mean()),
                rms=float(np.sqrt(np.mean(d.astype(float)**2))), min=int(d.min()), max=int(d.max()),
                abs_quantiles={str(q): float(np.percentile(np.abs(d), q)) for q in (0, 25, 50, 75, 90, 95, 99, 100)},
                signed_histogram={str(v): int(f) for v, f in zip(values, freq)})


def compare(raw):
    rows, all_counts = [], {}
    for seed in (501, 502):
        for condition in ('control', 'off-gaba'):
            paths = [raw / backend / f'{seed}-{condition}' for backend in ('brian', 'cuda')]
            meta = [read_json(p / 'run.json') for p in paths]
            if meta[0]['input_manifest_sha256'] != meta[1]['input_manifest_sha256'] or meta[0]['provenance'] != meta[1]['provenance']:
                raise ValueError('cross-engine inputs differ')
            cs = []
            for p, m in zip(paths, meta):
                if hash_file(p / 'counts.npz') != m['counts_sha256']:
                    raise ValueError('count archive hash changed')
                with load_npy(p / 'counts.npz') as z:
                    cs.append({k: z[k] for k in z.files})
            all_counts[seed, condition] = cs
            first = None
            unequal_spikes = 0
            for second in range(12):
                keys = []
                for p, m in zip(paths, meta):
                    f = m['spike_files'][second]
                    if hash_file(p / f['file']) != f['sha256']:
                        raise ValueError('spike archive hash changed')
                    with load_npy(p / f['file']) as z:
                        keys.append(z['tick'].astype(np.int64) * m['n'] + z['idx'])
                only_b = np.setdiff1d(keys[0], keys[1], assume_unique=True)
                only_c = np.setdiff1d(keys[1], keys[0], assume_unique=True)
                unequal_spikes += len(only_b) + len(only_c)
                if first is None and (len(only_b) or len(only_c)):
                    key = min(x[0] for x in (only_b, only_c) if len(x))
                    tick = int(key // meta[0]['n'])
                    first = dict(tick=tick, ms=tick * .1,
                                 brian_only_idx=(only_b[only_b // meta[0]['n'] == tick] % meta[0]['n']).tolist(),
                                 cuda_only_idx=(only_c[only_c // meta[0]['n'] == tick] % meta[0]['n']).tolist())
            rows.append(dict(seed=seed, condition=condition,
                             windows={w: differences(cs[0][w], cs[1][w]) for w in cs[0]},
                             first_spike_divergence=first, spike_symmetric_difference=unequal_spikes,
                             runs=meta))
    paired = []
    for seed in (501, 502):
        control, off = all_counts[seed, 'control'], all_counts[seed, 'off-gaba']
        paired.append(dict(seed=seed, windows={w: differences(off[0][w]-control[0][w], off[1][w]-control[1][w])
                                              for w in ('on', 'off', 'measure')}))
    result = dict(schema='cuda-identical-comparison-v1', definition='signed differences = CUDA minus Brian2',
                  plan_sha256=hash_file(RECORD / 'male-cuda-identical-plan.md'), rows=rows, paired_gaba_effect=paired)
    save_json(RECORD / 'male-cuda-identical-comparison.json', result)
    print(json.dumps([{k: r[k] for k in ('seed', 'condition', 'first_spike_divergence')} for r in rows]), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('generate', 'brian', 'compare'))
    p.add_argument('--seed', type=int, default=501)
    p.add_argument('--condition', choices=('control', 'off-gaba'), default='control')
    p.add_argument('--root', type=Path, default=RAW)
    a = p.parse_args()
    if a.mode == 'generate':
        generate(a.root / 'inputs')
    elif a.mode == 'compare':
        compare(a.root)
    else:
        replay('brian', a.seed, a.condition, a.root / 'inputs', a.root / 'brian' / f'{a.seed}-{a.condition}')


if __name__ == '__main__':
    main()
