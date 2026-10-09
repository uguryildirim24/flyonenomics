"""CPU-only tests; nothing in this module submits a GPU job."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import PIN, ROOT, canonical_spikes, load_eon, read_json, sha, validate_bundle
from compare import exact_metrics, finite_json
from reference import advance_reference


def frame(ticks=(1, 2), idx=(0, 1)):
    return pd.DataFrame(dict(trial=0, neuron_index=idx, flywire_id=np.asarray(idx) + 100,
                             time_ms=np.asarray(ticks) * .1))


def test_exact_is_not_rate_agreement():
    a = canonical_spikes(frame(), 2, .1)
    b = canonical_spikes(frame(ticks=(2, 3)), 2, .1)
    assert exact_metrics(a, b)['f1'] == 0
    assert np.array_equal(frame().groupby('flywire_id').size(), frame(ticks=(2, 3)).groupby('flywire_id').size())


def test_precision_recall_and_extras():
    m = exact_metrics(np.array([1, 2, 3]), np.array([1, 2, 4, 5]))
    assert m['matches'] == 2
    assert m['recall'] == 2/3
    assert m['precision'] == 1/2
    assert m['f1'] == 4/7
    assert m['symmetric_difference'] == 3
    assert not m['all_spikes_identical']


def test_empty_is_not_perfect_measured_agreement():
    m = exact_metrics(np.zeros(0, dtype=int), np.zeros(0, dtype=int))
    assert m['f1'] is None and m['all_spikes_identical']


def test_duplicate_tick_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        canonical_spikes(frame(ticks=(1, 1), idx=(0, 0)), 2, .1)


def test_off_grid_rejected():
    df = frame()
    df.loc[0, 'time_ms'] = .15
    with pytest.raises(ValueError, match='grid'):
        canonical_spikes(df, 2, .1)


def test_trial_is_part_of_exact_key():
    a = frame()
    b = frame()
    b['trial'] = 1
    assert exact_metrics(canonical_spikes(a, 2, .1), canonical_spikes(b, 2, .1))['matches'] == 0


def test_nan_not_exported_as_valid_correlation():
    assert finite_json({'pearson': float('nan')}) == {'pearson': None}


def test_adapter_changes_only_mit_kernel(tmp_path, monkeypatch):
    monkeypatch.setenv('FLYONENOMICS_CACHE_DIR', str(tmp_path))
    from adapter import KERNEL_PATH, kernel_source
    before = sha(KERNEL_PATH)
    source = kernel_source()
    assert 'const int* refractory_ticks, double v_bias' in source
    assert 'bool active = tick - last[j] >= refractory_ticks[i];' in source
    assert 'vn += bg_events' in source
    assert 'gn += bg_events' not in source
    assert 'vn = v_bias + (oldg * coupling + vn * dv);' in source
    assert 'refractory_ticks[post[e]]' in source
    assert before == sha(KERNEL_PATH)


def test_kernel_change_fails_closed(tmp_path, monkeypatch):
    import adapter
    path = tmp_path / 'changed.cu'
    path.write_text(adapter.KERNEL_PATH.read_text().replace('bool active = tick - last[j] >= refractory;', 'bool active = true;'))
    monkeypatch.setattr(adapter, 'KERNEL_PATH', path)
    with pytest.raises(ValueError, match='MIT CUDA kernel changed'):
        adapter.kernel_source()


def test_zero_refractory_and_input_after_threshold():
    si = dict(v_0=0., v_rst=0., v_th=.5, kick=1.)
    linear = dict(bias=0., coupling=1., dv=1., dg=1.)
    # Every tick gets a kick. The kick on each firing tick is reset away.
    idx, tick = advance_reference(1, np.array([], dtype=int), np.array([], dtype=int),
                                 np.array([]), np.array([0]), np.ones((6, 1), dtype=np.uint8),
                                 np.array([0]), 1, si, linear)
    assert tick.tolist() == [1, 3, 5]
    assert idx.tolist() == [0, 0, 0]


def test_recurrent_delay_includes_next_state_update():
    si = dict(v_0=0., v_rst=0., v_th=.5, kick=1.)
    linear = dict(bias=0., coupling=1., dv=1., dg=1.)
    events = np.zeros((7, 1), dtype=np.uint8)
    events[0, 0] = 1
    idx, tick = advance_reference(2, np.array([0]), np.array([1]), np.array([1.]),
                                 np.array([0]), events, np.array([0, 2]), 2, si, linear)
    # Source fires tick 1, synapse arrives tick 3, destination updates tick 4.
    assert idx.tolist() == [0, 1]
    assert tick.tolist() == [1, 4]


def test_saved_capture_and_semantic_check_are_identical():
    bundle = HERE / 'artifacts/sugar-0.1s-n1-seed501'
    m = read_json(bundle / 'manifest.json')
    assert m['eon_commit'] == PIN and m['capture_verified_exact_spikes']
    for name, digest in m['files_sha256'].items():
        assert sha(bundle / name) == digest
    a = pd.read_parquet(bundle / 'cpu-unobserved.parquet')
    b = pd.read_parquet(HERE / 'artifacts/adapter-cpu-check/spikes.parquet')
    assert exact_metrics(canonical_spikes(a, m['n_neurons'], .1),
                         canonical_spikes(b, m['n_neurons'], .1))['f1'] == 1
    assert len(a) == 1711


def test_modified_inputs_rejected(tmp_path):
    source = HERE / 'artifacts/sugar-0.1s-n1-seed501'
    bundle = tmp_path / 'bundle'
    shutil.copytree(source, bundle)
    repo = tmp_path / 'eon'
    (repo / 'data').mkdir(parents=True)
    m = read_json(bundle / 'manifest.json')
    for name in m['data_sha256']:
        (repo / 'data' / name).write_bytes(b'fake connectome')
        m['data_sha256'][name] = sha(repo / 'data' / name)
    (bundle / 'manifest.json').write_text(json.dumps(m))
    (bundle / 'stimulus.npz').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='bundle hash mismatch'):
        validate_bundle(bundle, repo)


def test_upstream_cannot_be_inside_mit_repository():
    with pytest.raises(ValueError, match='outside the MIT repository'):
        load_eon(ROOT / 'vendor/fly-brain')


def test_wrong_upstream_pin_rejected(tmp_path):
    repo = tmp_path / 'upstream'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    'commit', '-q', '--allow-empty', '-m', 'not Eon'], check=True)
    with pytest.raises(ValueError, match='expected Eon'):
        load_eon(repo)


def test_modal_paid_guard(tmp_path):
    # The guard runs after `import modal`, so give the script a local-launch stub of it.
    (tmp_path / 'modal.py').write_text('def is_local():\n    return True\n')
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    env.pop('EON_BENCH_ALLOW_PAID_GPU', None)
    result = subprocess.run([sys.executable, str(HERE / 'modal_run.py')], env=env,
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Paid GPU launch disabled' in result.stderr
