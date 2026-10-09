"""MIT benchmark utilities; upstream GPL implementation stays in a separate checkout."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

PIN = 'a3db62f9436074e485c0278290c2164ed6150808'
ROOT = Path(__file__).resolve().parents[2]
DATA_FILES = ('2025_Completeness_783.csv', '2025_Connectivity_783.parquet')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def read_json(path):
    return json.loads(Path(path).read_text())


def load_eon(repo):
    repo = Path(repo).resolve()
    if repo == ROOT or ROOT in repo.parents:
        raise ValueError('GPL checkout must be outside the MIT repository')
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != PIN:
        raise ValueError(f'expected Eon {PIN}, found {commit}')
    subprocess.run(['git', '-C', str(repo), 'diff', '--exit-code', 'HEAD', '--',
                    'code', 'main.py', *(f'data/{p}' for p in DATA_FILES)], check=True,
                   stdout=subprocess.DEVNULL)
    # The generated builds and result CSV are deliberately not treated as source.
    sys.path.insert(0, str(repo / 'code'))
    modules = tuple(importlib.import_module(name) for name in ('benchmark', 'run_brian2_cuda'))
    for module in modules:
        if Path(module.__file__).resolve().parent != repo / 'code':
            raise ValueError('cached upstream module comes from a different checkout')
    return modules


def environment():
    return dict(platform=platform.platform(), machine=platform.machine(),
                python=platform.python_version(), numpy=np.__version__,
                omp_num_threads=os.environ.get('OMP_NUM_THREADS'),
                hostname=platform.node())


def validate_bundle(bundle, repo):
    bundle, repo = Path(bundle), Path(repo)
    manifest = read_json(bundle / 'manifest.json')
    if manifest['eon_commit'] != PIN:
        raise ValueError('input bundle upstream pin differs')
    if (manifest['schema'] != 'eon-identical-input-v1' or manifest['dt_ms'] != .1
            or manifest['duration_s'] not in (.1, 1.) or manifest['n_run'] != 1
            or manifest['connectome'] != 'FlyWire v783'
            or manifest['experiment']['key'] != 'sugar'):
        raise ValueError('input bundle is outside the first standard configuration')
    for name, digest in manifest['data_sha256'].items():
        if sha(repo / 'data' / name) != digest:
            raise ValueError(f'connectome mismatch: {name}')
    for name, digest in manifest['files_sha256'].items():
        if sha(bundle / name) != digest:
            raise ValueError(f'bundle hash mismatch: {name}')
    return manifest


def canonical_spikes(df, n, dt_ms):
    if not {'trial', 'neuron_index', 'time_ms', 'flywire_id'} <= set(df.columns):
        raise ValueError('expected Eon canonical spike schema')
    ticks_f = df.time_ms.to_numpy(dtype=float) / dt_ms
    ticks = np.rint(ticks_f).astype(np.int64)
    if not np.allclose(ticks_f, ticks, atol=1e-7, rtol=0):
        raise ValueError('spikes not on timestep grid')
    idx = df.neuron_index.to_numpy(dtype=np.int64)
    if np.any(idx < 0) or np.any(idx >= n):
        raise ValueError('invalid neuron index')
    keys = (df.trial.to_numpy(dtype=np.int64) * (2**32) + ticks) * n + idx
    if len(np.unique(keys)) != len(keys):
        raise ValueError('duplicate trial/neuron/tick spike')
    return np.sort(keys)
