"""Explicit opt-in, single L4 replay. A local launch without approval fails closed.

Run only after Rolf approves paid GPU use; see README for the command.
No persistent deployment, volume, retries, or parallel paid runs.
"""
from pathlib import Path
import os

import modal

# The container re-imports this file without the local env, so gate only the local launch.
if modal.is_local() and os.environ.get('EON_BENCH_ALLOW_PAID_GPU') != 'YES':
    raise RuntimeError('Paid GPU launch disabled. Set EON_BENCH_ALLOW_PAID_GPU=YES only with approval.')

ROOT = Path(__file__).resolve().parents[2] if modal.is_local() else Path('/')
PIN = 'a3db62f9436074e485c0278290c2164ed6150808'
app = modal.App('flyonenomics-eon-bench')
image = (modal.Image.from_registry('nvidia/cuda:12.6.3-devel-ubuntu22.04', add_python='3.12')
         .apt_install('git', 'gcc', 'g++')
         .pip_install('numpy==1.26.4', 'brian2==2.8.0', 'pandas==2.2.3', 'pyarrow==19.0.1',
                      'joblib==1.4.2', 'pydantic==2.12.4', 'pyyaml==6.0.3', 'cupy-cuda12x==13.6.0')
         .run_commands('git clone https://github.com/eonsystemspbc/fly-brain.git /opt/eon-fly-brain',
                       f'git -C /opt/eon-fly-brain checkout --detach {PIN}')
         .add_local_dir(str(ROOT / 'src'), '/mit/src', copy=True,
                        ignore=lambda p: '__pycache__' in Path(p).parts)
         .add_local_dir(str(ROOT / 'benchmarks/eon'), '/mit/benchmarks/eon', copy=True,
                        ignore=lambda p: any(x in {'artifacts', '__pycache__', '.pytest_cache'} for x in Path(p).parts))
         .env({'PYTHONPATH': '/mit/src', 'FLYONENOMICS_CACHE_DIR': '/scratch/cache',
               'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'}))


@app.function(image=image, gpu='L4', cpu=2, memory=16384, timeout=900,
              retries=0, max_containers=1, scaledown_window=2)
def replay(files: dict[str, bytes]):
    import subprocess
    import sys
    inputs, output = Path('/scratch/inputs'), Path('/scratch/cuda')
    inputs.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        if Path(name).name != name:
            raise ValueError('input basename required')
        (inputs / name).write_bytes(data)
    subprocess.run([sys.executable, '/mit/benchmarks/eon/gpu.py', '--eon-repo', '/opt/eon-fly-brain',
                    '--inputs', str(inputs), '--out', str(output), '--chunk-ms', '10'], check=True)
    subprocess.run([sys.executable, '/mit/benchmarks/eon/compare.py', '--eon-repo', '/opt/eon-fly-brain',
                    '--inputs', str(inputs), '--candidate', str(output),
                    '--out', '/scratch/comparison.json'], check=True)
    return {'spikes.parquet': (output / 'spikes.parquet').read_bytes(),
            'run.json': (output / 'run.json').read_bytes(),
            'comparison.json': Path('/scratch/comparison.json').read_bytes()}


@app.local_entrypoint()
def main(inputs: str, out: str):
    import json
    bundle = Path(inputs)
    m = json.loads((bundle / 'manifest.json').read_text())
    names = {'manifest.json', 'cpu-run.json', *m['files_sha256']}
    output = Path(out)
    output.mkdir(parents=True, exist_ok=False)
    # Exactly one paid call; all outputs returned to the caller before exit.
    results = replay.remote({name: (bundle / name).read_bytes() for name in names})
    for name, data in results.items():
        (output / name).write_bytes(data)
    print((output / 'comparison.json').read_text())
