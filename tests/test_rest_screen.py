"""Execution contracts for the WP17 rest driver without a whole-brain run."""
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
from flyonenomics.drive import rest_map as rest

ROOT = Path(__file__).resolve().parents[1]


def driver():
    spec = importlib.util.spec_from_file_location('rest_screen', ROOT / 'scripts/camber/rest_screen.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parent_import_does_not_load_brian():
    p = subprocess.run([sys.executable, '-c', "import sys; import flyonenomics.drive.rest_map; assert 'brian2' not in sys.modules"], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr


def test_grid_task_budget_and_coverage(tmp_path):
    plan = {'settings': [asdict(rest.Setting(3, 4))]}
    identity = dict(job_id='test', commit='sha', code_scope='scope', platform='fake')
    tasks = rest.screen_tasks(plan, tmp_path, identity)
    assert len(tasks) == 3
    assert sum(len(t['probes']) for t in tasks) == 57
    assert tasks[0]['wall_cap_s'] == 1.25 * 42.5 * 19 * 12 + 60
    for task in tasks:
        records = [{**identity, **task['setting'], 'plan_sha256': task['plan_sha256'],
                    'task_id': Path(task['path']).stem, 'stage': task['stage'], 'kind': 'evaluation',
                    'w_bg': w, 'seed': s} for w, s in task['probes']]
        records.append({**records[-1], 'kind': 'task-complete'})
        Path(task['path']).write_text('\n'.join(json.dumps(r) for r in records))
    assert len(rest.read_evaluations(tmp_path, tasks)) == 57
    path = Path(tasks[0]['path'])
    text = path.read_text()
    path.write_text(text.replace('scope', 'wrong'))
    with pytest.raises(ValueError, match='provenance'):
        rest.read_evaluations(tmp_path, tasks)
    path.write_text('\n'.join(text.splitlines()[:-1]))
    with pytest.raises(ValueError, match='incomplete'):
        rest.read_evaluations(tmp_path, tasks)


def test_sliced_screen_tasks_cover_the_same_probes(tmp_path):
    identity = dict(job_id='test', commit='sha', code_scope='scope', platform='fake')
    base = {'settings': [asdict(rest.Setting(3, 6)), asdict(rest.Setting(4, 2))]}
    whole = rest.screen_tasks(base, tmp_path, identity)
    slices = [[0, 2], [2, 4], [4, 6], [6, 8], [8, 10], [10, 12], [12, 14], [14, 16], [16, 18], [18, 19]]
    sliced = rest.screen_tasks({**base, 'slices': slices}, tmp_path, identity, q=100)
    assert len(sliced) == 2 * 3 * 10
    assert len({t['path'] for t in sliced}) == len(sliced)
    key = lambda tasks: sorted((json.dumps(t['setting'], sort_keys=True), tuple(p))
                               for t in tasks for p in t['probes'])
    assert key(sliced) == key(whole)
    assert max(len(t['probes']) for t in sliced) == 2
    assert sliced[0]['wall_cap_s'] == 1.25 * 100 * 2 * 12 + 60
    assert Path(sliced[0]['path']).name == 'setting-000-seed-1-w00-02.ndjson'
    for bad in ([[0, 10]], [[0, 10], [11, 19]], [[0, 10], [10, 10], [10, 19]], []):
        with pytest.raises(ValueError, match='slices'):
            rest.screen_tasks({**base, 'slices': bad}, tmp_path, identity)

def test_reflex_has_shared_bare_reference_and_matched_modes(tmp_path):
    c = {**asdict(rest.Setting(3., 4.)), 'w_bg': 1.2, 'pair_weights': [1.2, 1.25]}
    tasks = driver().reflex_tasks([c, {**c, 'w_bg': 1.25, 'pair_weights': [1.25, 1.3]}], tmp_path, {}, 42.5)
    assert len([t for t in tasks if t.get('bare')]) == 2
    assert len(tasks) == 8
    assert sum(len(t['probes']) for t in tasks) == 86
    for task in tasks:
        if task.get('feedforward'):
            assert task['probes'] == [(0., s) for s in rest.LONG_SEEDS]
            assert task['mode'] in ('upstream', 'extended')
        else:
            assert len(task['probes']) == 13


def test_stage_is_blocked_until_explicit_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv('FLYONENOMICS_REST_RESULTS', str(tmp_path))
    assert rest.STAGE['R1']()['status'] == 'blocked'
    assert rest.STAGE['R2']()['status'] == 'blocked'
    identity = rest.run_r1.input_identity()
    (tmp_path / 'R1').mkdir()
    (tmp_path / 'R1' / 'plan.json').write_text('{}')
    assert rest.run_r1.input_identity() != identity


def test_stage_record_binds_declared_inputs_not_whole_repo_code_scope(tmp_path, monkeypatch):
    """Decision 46: a later src/ change must not block R1 when declared inputs match."""
    monkeypatch.setenv('FLYONENOMICS_REST_RESULTS', str(tmp_path))
    r1 = tmp_path / 'R1'
    r1.mkdir()
    artifact = r1 / 'evaluations.ndjson'
    artifact.write_text('{}\n')
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    relative = 'data/params-v0.2.yaml'
    inp = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    summary = {
        'status': 'passed',
        'execution': {
            'code_scope': 'git:not-the-current-tree',
            'inputs': {relative: inp},
        },
        'artifact_sha256': {'evaluations.ndjson': digest},
    }
    (r1 / 'summary.json').write_text(json.dumps(summary))
    record = rest.run_r1()
    assert record['status'] == 'passed'
    assert record.get('reason') != 'rest evidence code scope is stale or absent'
    summary['execution']['inputs'][relative] = '0' * 64
    (r1 / 'summary.json').write_text(json.dumps(summary))
    blocked = rest.run_r1()
    assert blocked['status'] == 'blocked' and 'input changed' in blocked['reason']
    summary['execution']['inputs'] = {}
    summary['execution']['code_scope'] = 'git:not-the-current-tree'
    (r1 / 'summary.json').write_text(json.dumps(summary))
    absent = rest.run_r1()
    assert absent['status'] == 'blocked' and 'declared inputs' in absent['reason']


def test_mac_worker_and_swap_gate(monkeypatch, tmp_path):
    import platform
    from flyonenomics.orchestrator import budget
    monkeypatch.setattr(platform, 'system', lambda: 'Darwin')
    with pytest.raises(ValueError, match='auto'):
        rest.execute_tasks([{}], 2)
    monkeypatch.setattr(budget, 'swap_used_mib', lambda: 4001)
    with pytest.raises(RuntimeError, match='swap'):
        rest.execute_tasks([{}], 'auto')


def test_prepared_bare_reference_requires_matching_protocol_and_scope(tmp_path, monkeypatch):
    module = driver()
    identity = {'code_scope': 'new', 'inputs': {}, 'platform': 'darwin-arm64'}
    c = {**asdict(rest.Setting(3., 4.)), 'w_bg': 1.2, 'pair_weights': [1.2, 1.25]}
    reference = tmp_path / 'prepared'
    reference.mkdir()
    tasks = module.reflex_tasks([], reference, {**identity, 'code_scope': 'old'}, 42.5)
    (reference / 'tasks.json').write_text(json.dumps(tasks))
    with pytest.raises(ValueError, match='code_scope'):
        module.confirm({'admitted': [c], 'candidates': [c]}, tmp_path / 'R2', identity, 'auto', 42.5, reference)


def test_confirmation_reuses_bare_bytes_and_ranks_passing_candidates(tmp_path, monkeypatch):
    module = driver()
    identity = {'job_id': 'mac-test', 'commit': 'test-sha', 'code_scope': 'test-scope',
                'platform': 'darwin-arm64', 'inputs': {}}
    c = {**asdict(rest.Setting(3., 4.)), 'w_bg': 1.2, 'pair_weights': [1.2, 1.25],
         'screen_passed': True, 'reflex_passed': None, 'long_passed': None,
         'S': 0., 'J': 1., 'violations': {}}
    reference = tmp_path / 'prepared'
    reference.mkdir()
    reference_tasks = module.reflex_tasks([], reference, identity, 42.5)
    (reference / 'tasks.json').write_text(json.dumps(reference_tasks))
    for task in reference_tasks:
        rows = [{**identity, **task['setting'], 'plan_sha256': task['plan_sha256'],
                 'task_id': Path(task['path']).stem, 'stage': task['stage'],
                 'kind': 'evaluation', 'w_bg': w, 'seed': seed, 'difference_hz': 100.}
                for w, seed in task['probes']]
        rows.append({**rows[-1], 'kind': 'task-complete'})
        Path(task['path']).write_text('\n'.join(json.dumps(row) for row in rows))
    calls = []
    def fake_batch(tasks, out, workers):
        calls.extend(tasks)
        return [{**identity, **t['setting'], 'task_id': Path(t['path']).stem,
                 'stage': t['stage'], 'w_bg': w, 'seed': seed,
                 'difference_hz': 60., 'F': 2., 'ignited': False, 'stability_ratio': 1.}
                for t in tasks for w, seed in t['probes']]
    monkeypatch.setattr(module, 'run_batch', fake_batch)
    result = module.confirm({'admitted': [c], 'candidates': [c], 'tier': 1, 'excluded': []},
                            tmp_path / 'R2', identity, 'auto', 42.5, reference)
    assert result['status'] == 'passed'
    assert result['decision']['ranked'][0]['retention']['extended'] == .6
    assert not any(t.get('bare') for t in calls)
    assert len([t for t in calls if t['stage'] == 'R-long']) == 10
    for name in ('bare-upstream.ndjson', 'bare-extended.ndjson'):
        assert (tmp_path / 'R2' / 'bare-reference' / name).read_bytes() == (reference / name).read_bytes()


def _write_rows(tasks, identity, value):
    for task in tasks:
        rows = [{**identity, **task['setting'], 'plan_sha256': task['plan_sha256'],
                 'task_id': Path(task['path']).stem, 'stage': task['stage'], 'kind': 'evaluation',
                 'w_bg': w, 'seed': seed, 'difference_hz': value(task),
                 'F': 2., 'ignited': False, 'stability_ratio': 1.} for w, seed in task['probes']]
        rows.append({**rows[-1], 'kind': 'task-complete'})
        Path(task['path']).parent.mkdir(parents=True, exist_ok=True)
        Path(task['path']).write_text('\n'.join(json.dumps(row) for row in rows))
        (Path(task['path']).parent / 'tasks.json').write_text('[]')


def test_split_stage2_decision_matches_confirm(tmp_path, monkeypatch):
    module = driver()
    identity = {'job_id': 'cam-test', 'commit': 'sha', 'code_scope': 'scope',
                'platform': 'linux-x86_64', 'inputs': {}}
    good = {**asdict(rest.Setting(3., 4.)), 'w_bg': 1.2, 'pair_weights': [1.2, 1.25],
            'screen_passed': True, 'reflex_passed': None, 'long_passed': None,
            'S': 0., 'J': 1., 'violations': {}}
    weak = {**good, 'g_glu': 6., 'J': 2.}
    whole = module.reflex_tasks([good, weak], tmp_path / 'x', identity, 42.5)
    split = module.reflex_tasks([good, weak], tmp_path / 'y', identity, 42.5, split=True)
    key = lambda ts: sorted((t['candidate_id'], t.get('mode'), tuple(p)) for t in ts for p in t['probes'])
    assert key(split) == key(whole) and all(len(t['probes']) == 1 for t in split)
    assert {t['group'] for t in split} == {Path(t['path']).stem for t in whole}
    value = lambda t: 100. if t.get('bare') else (60. if t['candidate_id'] == rest.candidate_id(good) else 30.)
    def fake_batch(tasks, out, workers):
        return [{**identity, **t['setting'], 'task_id': Path(t['path']).stem, 'stage': t['stage'],
                 'w_bg': w, 'seed': seed, 'difference_hz': value(t), 'F': 2., 'ignited': False,
                 'stability_ratio': 1.} for t in tasks for w, seed in t['probes']]
    monkeypatch.setattr(module, 'run_batch', fake_batch)
    screen = {'admitted': [good, weak], 'candidates': [good, weak], 'tier': 2, 'excluded': []}
    expected = module.confirm(screen, tmp_path / 'R2', identity, 'auto', 42.5)
    bare = tmp_path / 'bare'
    bare_tasks = module.reflex_tasks([], bare, identity, 100, split=True)
    _write_rows(bare_tasks, identity, value)
    (bare / 'tasks.json').write_text(json.dumps(bare_tasks))
    dirs = []
    for n, c in enumerate((good, weak)):
        d = tmp_path / f'cand-{n}'
        reflex = [t for t in module.reflex_tasks([c], d / 'reflex', identity, 100, split=True) if not t.get('bare')]
        long = module.long_tasks_for(c, 0, d / 'long', identity, reflex[0]['plan_sha256'], 100)
        _write_rows(reflex + long, identity, value)
        (d / 'reflex' / 'tasks.json').write_text(json.dumps(reflex))
        (d / 'long' / 'tasks.json').write_text(json.dumps(long))
        dirs.append(d)
    result = module.stage2_decide({'candidates': [good, weak], 'tier': 2}, [bare], dirs)
    assert result['decision_status'] == expected['decision_status'] == 'ranked'
    strip = lambda rs: [{k: v for k, v in r.items() if k not in ('long_rows', 'stage2_dir', 'bare_dir')} for r in rs]
    assert strip(result['decision']['ranked']) == strip(expected['decision']['ranked'])
    assert [r['reflex_passed'] for r in result['admitted']] == [True, False]
    with pytest.raises(ValueError, match='without stage 2'):
        module.stage2_decide({'candidates': [good, weak], 'tier': 2}, [bare], dirs[:1])
    with pytest.raises(ValueError, match='unfinished settings'):
        module.stage2_decide({'candidates': [good, weak], 'tier': 2, 'settings_missing': [3]}, [bare], dirs)
    interim = module.stage2_decide({'candidates': [good, weak], 'tier': 2, 'settings_missing': [3]},
                                   [bare], dirs[:1], partial=True)
    assert interim['status'] == interim['decision_status'] == 'pending'
    assert interim['pending_stage2'] == [{'candidate_id': rest.candidate_id(weak), 'admission_order': 2}]
    assert strip(interim['admitted']) == strip(result['admitted'][:1])
    dropped = module.stage2_decide({'candidates': [good, {**weak, 'screen_passed': False}], 'tier': 2},
                                   [bare], dirs, partial=True)
    assert dropped['measured_beyond_cap'] == [rest.candidate_id(weak)]
    assert strip(dropped['beyond_cap_results']) == strip([{**result['admitted'][1], 'screen_passed': False}])
    unknown = module.stage2_decide({'candidates': [good], 'tier': 2}, [bare], dirs, partial=True)
    assert unknown['measured_beyond_cap'] == [rest.candidate_id(weak)] and unknown['beyond_cap_results'] == []
    other = tmp_path / 'other'
    other_tasks = module.reflex_tasks([], other, {**identity, 'code_scope': 'changed'}, 100, split=True)
    _write_rows(other_tasks, {**identity, 'code_scope': 'changed'}, value)
    (other / 'tasks.json').write_text(json.dumps(other_tasks))
    with pytest.raises(ValueError, match='code_scope'):
        module.stage2_decide({'candidates': [good, weak], 'tier': 2}, [other], dirs)

    # A packed batch (new code_scope) carries its own bare and decides identically.
    packed = tmp_path / 'packed'
    new_identity = {**identity, 'code_scope': 'packed-scope'}
    batches = module.pack_tasks({'candidates': [weak, good], 'with_bare': True}, packed, new_identity, 100)
    assert [out.name for _, out in batches] == ['long', 'reflex', 'bare']
    assert len(batches[0][0]) == 20 and len(batches[1][0]) == 66 and len(batches[2][0]) == 20
    for tasks, out in batches:
        _write_rows(tasks, new_identity, value)
        (out / 'tasks.json').write_text(json.dumps(tasks))
    with pytest.raises(ValueError, match='duplicate'):
        module.stage2_decide({'candidates': [good, weak], 'tier': 2}, [bare], [dirs[0], packed])
    weak_only = tmp_path / 'packed-weak'
    for tasks, out in module.pack_tasks({'candidates': [weak], 'with_bare': True}, weak_only, new_identity, 100):
        _write_rows(tasks, new_identity, value)
        (out / 'tasks.json').write_text(json.dumps(tasks))
    mixed = module.stage2_decide({'candidates': [good, weak], 'tier': 2}, [bare], [dirs[0], weak_only])
    assert strip(mixed['decision']['ranked']) == strip(expected['decision']['ranked'])
    assert mixed['admitted'][0]['bare_dir'] == str(bare)
    assert mixed['admitted'][1]['bare_dir'] == str(weak_only / 'bare')
    alone = module.stage2_decide({'candidates': [good, weak], 'tier': 2}, [], [packed])
    assert strip(alone['decision']['ranked']) == strip(expected['decision']['ranked'])
    assert [r['reflex_passed'] for r in alone['admitted']] == [True, False]
    # A bare reference pairs only within one node type (Brian2 builds with -march=native).
    (packed / 'pack.json').write_text(json.dumps({'node': 'large-gpu'}))
    cpu_pack = tmp_path / 'packed-cpu'
    for tasks, out in module.pack_tasks({'candidates': [weak], 'with_bare': False}, cpu_pack, new_identity, 100):
        _write_rows(tasks, new_identity, value)
        (out / 'tasks.json').write_text(json.dumps(tasks))
    (cpu_pack / 'pack.json').write_text(json.dumps({'node': 'large-cpu'}))
    with pytest.raises(ValueError, match='node'):
        module.stage2_decide({'candidates': [good, weak], 'tier': 2}, [], [packed, cpu_pack])

def test_combine_takes_each_setting_whole_from_a_complete_source(tmp_path):
    module = driver()
    identity = dict(job_id='j', commit='sha', code_scope='scope', platform='fake')
    parent = {'tier': 2, 'settings': [asdict(rest.Setting(3, 6)), asdict(rest.Setting(4, 2))]}
    parent_path = tmp_path / 'parent.json'
    parent_path.write_text(json.dumps(parent))
    import hashlib
    sha = hashlib.sha256(parent_path.read_bytes()).hexdigest()
    first = tmp_path / 'first'
    plan = {**parent, 'setting_offset': 0, 'parent_plan_sha256': sha}
    tasks = rest.screen_tasks(plan, first, {**identity, 'job_id': 'first'})
    _write_rows(tasks, {**identity, 'job_id': 'first'}, lambda t: 0.)
    broken = Path(tasks[-1]['path'])
    broken.write_text('\n'.join(broken.read_text().splitlines()[:-2]))
    (first / 'plan.json').write_text(json.dumps(plan))
    (first / 'tasks.json').write_text(json.dumps(tasks))
    with pytest.raises(ValueError, match=r'unfinished settings \[1\]'):
        module.combine(parent_path, [first])
    partial = module.combine(parent_path, [first], allow_partial=True)
    assert partial['settings_included'] == [0] and partial['evaluations'] == 57
    assert partial['decision']['status'] == 'pending'
    second = tmp_path / 'second'
    plan2 = {'tier': 2, 'settings': [parent['settings'][1]], 'slices': [[0, 10], [10, 19]],
             'parent_setting_indices': [1], 'parent_plan_sha256': sha}
    tasks2 = rest.screen_tasks(plan2, second, {**identity, 'job_id': 'second'})
    _write_rows(tasks2, {**identity, 'job_id': 'second'}, lambda t: 0.)
    (second / 'plan.json').write_text(json.dumps(plan2))
    (second / 'tasks.json').write_text(json.dumps(tasks2))
    full = module.combine(parent_path, [first, second])
    assert full['settings_included'] == [0, 1] and full['evaluations'] == 114
    assert full['sources']['0']['job_id'] == 'first' and full['sources']['1']['job_id'] == 'second'
