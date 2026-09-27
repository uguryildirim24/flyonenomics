#!/usr/bin/env python3
"""Explicit WP17 development launcher: map-plan, screen, aggregate, confirm, bare, tier2-plan,
combine, stage2-candidates, stage2-candidate, stage2-packs, stage2-pack, stage2-decide."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from flyonenomics.drive import rest_map as rest
from flyonenomics.io import read_json, read_bytes


def save(path, data):
    rest._write_json(Path(path), data)


def load(path):
    return read_json(path)


def run_batch(tasks, out, workers):
    """Persist launch contract before engines, then execute exactly the missing tasks."""
    return run_batches([(tasks, out)], workers)[0]


def run_batches(batches, workers):
    """run_batch over several output directories in one worker pool."""
    pending = []
    for tasks, out in batches:
        out.mkdir(parents=True, exist_ok=True)
        manifest = out / 'tasks.json'
        if manifest.exists():
            original = load(manifest)
            if original != json.loads(json.dumps(tasks)):
                raise ValueError('existing task manifest differs; use a new output directory')
        else:
            save(manifest, tasks)
        for task in tasks:
            path = Path(task['path'])
            if path.exists():
                rest.read_evaluations(out, [task])  # incomplete evidence must not be overwritten
            else:
                pending.append(task)
    rest.execute_tasks(pending, workers)
    return [rest.read_evaluations(out, tasks) for tasks, out in batches]


def artifacts(out):
    return {str(p.relative_to(out)): hashlib.sha256(read_bytes(p)).hexdigest()
            for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'summary.json'}


def aggregate(out):
    plan = load(out / 'plan.json')
    tasks = load(out / 'tasks.json')
    rows = rest.read_evaluations(out, tasks)
    candidates = rest.aggregate_screen(plan, rows)
    admitted, excluded = rest.capped_candidates(candidates)
    record = {'status': 'passed', 'class': 'development', 'tier': plan['tier'],
              'plan': plan, 'evaluations': len(rows), 'candidates': candidates,
              'execution': tasks[0]['identity'], 'artifact_sha256': artifacts(out),
              'admitted': admitted, 'excluded': excluded,
              'decision': rest.decide(candidates, tier=plan['tier'], complete=not admitted)}
    save(out / 'summary.json', record)
    return record


def reflex_tasks(candidates, out, identity, q, split=False):
    """Shared matched bare reference plus candidate background-on and FF tasks.

    split: one child per probe, file <label>-pNN, tagged with its group label; every probe
    restores and reseeds, so the rows are the same evaluations under shorter wall.
    """
    plan_hash = hashlib.sha256(json.dumps(candidates, sort_keys=True).encode()).hexdigest()
    tasks = []
    def task(label, setting, stage, probes, **extra):
        parts = [(f'{label}-p{j:02d}', [p]) for j, p in enumerate(probes)] if split else [(label, probes)]
        for name, subset in parts:
            tasks.append({'path': str(out / (name + '.ndjson')), 'setting': asdict(setting),
                          'stage': stage, 'probes': subset, 'identity': identity,
                          'plan_sha256': plan_hash, 'wall_cap_s': 1.25 * q * len(subset) * 6 + 60,
                          **extra, **({'group': label} if split else {})})
    for mode in ('upstream', 'extended'):
        task('bare-' + mode, rest.Setting(1., 1.), 'R-reflex', [(0., s) for s in rest.LONG_SEEDS],
             mode=mode, bare=True, feedforward=True, candidate_id='bare')
    for i, c in enumerate(candidates):
        setting = rest.Setting(**{k: c[k] for k in asdict(rest.Setting(1, 1))})
        cid = rest.candidate_id(c)
        task(f'candidate-{i:02d}-background', setting, 'R-reflex',
             [(c['w_bg'], s) for s in rest.LONG_SEEDS]
             + [(c['pair_weights'][1], s) for s in rest.SEEDS], mode='extended', candidate_id=cid)
        for mode in ('upstream', 'extended'):
            task(f'candidate-{i:02d}-ff-{mode}', setting, 'R-reflex',
                 [(0., s) for s in rest.LONG_SEEDS], mode=mode, feedforward=True, candidate_id=cid)
    return tasks


def row_sets(tasks, rows):
    """Rows per task group (a split task's group, else its file stem), each sorted by seed."""
    group = {Path(t['path']).stem: t.get('group', Path(t['path']).stem) for t in tasks}
    sets = {}
    for r in sorted(rows, key=lambda r: r['seed']):
        sets.setdefault(group[r['task_id']], []).append(r)
    return sets


def bare_values(sets):
    return {m: [r['difference_hz'] for r in sets.get('bare-' + m, [])] for m in ('upstream', 'extended')}


def reflex_result(c, i, sets, bare):
    """Section 2.3 R-reflex for admitted candidate i from grouped rows and a bare reference."""
    bg = sets.get(f'candidate-{i:02d}-background', [])
    low = sorted((r for r in bg if r['w_bg'] == c['w_bg']), key=lambda r: r['seed'])
    high = sorted((r for r in bg if r['w_bg'] == c['pair_weights'][1]), key=lambda r: r['seed'])
    a = [r['difference_hz'] for r in low[:3] + high]
    b = [r['difference_hz'] for r in low]
    ff = {m: [r['difference_hz'] for r in sets[f'candidate-{i:02d}-ff-{m}']]
          for m in ('upstream', 'extended') if f'candidate-{i:02d}-ff-{m}' in sets}
    return rest.attach_reflex(c, rest.reflex_decision(a, b, ff, bare))


def long_tasks_for(c, i, out, identity, plan_sha, q):
    setting = {k: c[k] for k in asdict(rest.Setting(1, 1))}
    return [{'path': str(out / f'candidate-{i:02d}-seed-{seed}.ndjson'),
             'setting': setting, 'stage': 'R-long', 'identity': identity,
             'probes': [(c['w_bg'], seed)], 'candidate_id': rest.candidate_id(c),
             'plan_sha256': plan_sha, 'wall_cap_s': 1.25 * q * 32 + 60} for seed in rest.LONG_SEEDS]


def confirm(screen, out, identity, workers, q, bare_dir=None):
    admitted = screen['admitted']
    candidates = screen['candidates']
    if not admitted:
        decision = rest.decide(candidates, tier=screen['tier'])
        record = {'status': 'failed', 'class': 'development', 'decision': decision,
                  'decision_status': decision['status'], 'execution': identity}
        save(out / 'summary.json', record)
        return record
    tasks = reflex_tasks(admitted, out / 'reflex', identity, q)
    if bare_dir is None:
        rows = run_batch(tasks, out / 'reflex', workers)
    else:
        reference_tasks = load(bare_dir / 'tasks.json')
        expected_bare = [t for t in tasks if t.get('bare')]
        if len(reference_tasks) != 2:
            raise ValueError('bare reference must contain both modes exactly once')
        for actual, expected in zip(reference_tasks, expected_bare, strict=True):
            for key in ('stage', 'setting', 'mode', 'bare', 'feedforward', 'probes'):
                if json.loads(json.dumps(actual[key])) != json.loads(json.dumps(expected[key])):
                    raise ValueError(f'bare reference protocol mismatch: {key}')
            for key in ('code_scope', 'inputs'):
                if actual['identity'][key] != identity[key]:
                    raise ValueError(f'bare reference execution mismatch: {key}')
        reference_rows = rest.read_evaluations(bare_dir, reference_tasks)
        candidate_tasks = [t for t in tasks if not t.get('bare')]
        rows = run_batch(candidate_tasks, out / 'reflex', workers) + reference_rows
        # Copy exact evidence bytes into the final stage; preserve original identities.
        import shutil
        destination = out / 'bare-reference'
        destination.mkdir(parents=True, exist_ok=True)
        for path in [bare_dir / 'tasks.json'] + [bare_dir / Path(t['path']).name for t in reference_tasks]:
            shutil.copyfile(path, destination / path.name)
    sets = row_sets(tasks, rows)
    bare = bare_values(sets)
    updated = [reflex_result(c, i, sets, bare) for i, c in enumerate(admitted)]
    save(out / 'reflex-summary.json', updated)
    long_tasks = []
    for i, c in enumerate(updated):
        if c['reflex_passed']:
            long_tasks += long_tasks_for(c, i, out / 'long', identity, tasks[0]['plan_sha256'], q)
    long_rows = run_batch(long_tasks, out / 'long', workers) if long_tasks else []
    for c in updated:
        owned = {Path(t['path']).stem for t in long_tasks if t['candidate_id'] == rest.candidate_id(c)}
        if owned:
            c.update(rest.long_decision([r for r in long_rows if r['task_id'] in owned]))
    by_id = {rest.candidate_id(c): c for c in updated}
    evaluated = [by_id.get(rest.candidate_id(c), c) for c in candidates]
    decision = rest.decide(evaluated, tier=screen['tier'])
    record = {'status': 'passed' if decision['status'] == 'ranked' else 'failed',
              'class': 'development', 'decision_status': decision['status'],
              'decision': decision, 'candidates': evaluated, 'excluded': screen['excluded'],
              'execution': identity, 'artifact_sha256': artifacts(out)}
    save(out / 'summary.json', record)
    return record


def submitted_ids(dirs):
    """Candidate ids already in stage-2 candidate files or pack files."""
    ids = set()
    for d in dirs:
        for p in sorted(Path(d).glob('*.json')):
            record = load(p)
            ids.update(record.get('candidate_ids', [record.get('candidate_id')]))
    ids.discard(None)
    return ids


def shard_setting_indices(plan):
    if 'parent_setting_indices' in plan:
        return list(plan['parent_setting_indices'])
    return [plan['setting_offset'] + i for i in range(len(plan['settings']))]


def combine(parent_path, shard_dirs, allow_partial=False):
    """Tier-wide R-screen over shard outputs; each setting whole from its first complete source.

    Fail closed per setting: a setting counts only when all its tasks in one shard directory
    pass read_evaluations and cover every weight and seed. Rows keep their own provenance.
    """
    parent = load(parent_path)
    parent_sha = hashlib.sha256(read_bytes(parent_path)).hexdigest()
    chosen = {}
    for d in shard_dirs:
        d = Path(d)
        plan, tasks = load(d / 'plan.json'), load(d / 'tasks.json')
        if plan.get('parent_plan_sha256') != parent_sha:
            raise ValueError(f'{d}: parent plan differs')
        indices = shard_setting_indices(plan)
        by_local = {}
        for task in tasks:
            by_local.setdefault(int(Path(task['path']).stem.split('-')[1]), []).append(task)
        for local, owned in sorted(by_local.items()):
            index = indices[local]
            config = parent['settings'][index]
            if plan['settings'][local] != config or any(t['setting'] != config for t in owned):
                raise ValueError(f'{d}: setting {local} is not parent setting {index}')
            if index in chosen:
                continue
            try:
                rows = rest.read_evaluations(d, owned)
            except ValueError:
                continue
            expected = sorted((w, s) for w in rest.Setting(**config).weights for s in rest.SEEDS)
            if sorted((r['w_bg'], r['seed']) for r in rows) != expected:
                continue
            chosen[index] = (d, owned, rows)
    missing = [i for i in range(len(parent['settings'])) if i not in chosen]
    if missing and not allow_partial:
        raise ValueError(f'unfinished settings {missing}')
    included = sorted(chosen)
    rows = [r for i in included for r in chosen[i][2]]
    candidates = rest.aggregate_screen({**parent, 'settings': [parent['settings'][i] for i in included]}, rows)
    admitted, excluded = rest.capped_candidates(candidates)
    sources = {}
    for i in included:
        d, owned, _ = chosen[i]
        ident = owned[0]['identity']
        sources[str(i)] = {'dir': str(d), **{k: ident[k] for k in ('job_id', 'commit', 'code_scope', 'platform')},
                           'artifact_sha256': {Path(t['path']).name: hashlib.sha256(read_bytes(d / Path(t['path']).name)).hexdigest()
                                               for t in owned}}
    passers = [c for c in candidates if c['screen_passed']]
    return {'status': 'passed', 'class': 'development', 'tier': 2, 'parent_plan_sha256': parent_sha,
            'settings_included': included, 'settings_missing': missing, 'evaluations': len(rows),
            'sources': sources, 'screen_passers': len(passers), 'candidates': candidates,
            'admitted': admitted, 'excluded': excluded,
            'decision': rest.decide(candidates, tier=2, complete=not (missing or admitted))}


def bare_means(bare_dir):
    tasks = load(Path(bare_dir) / 'tasks.json')
    values = bare_values(row_sets(tasks, rest.read_evaluations(Path(bare_dir), tasks)))
    return {m: sum(v) / len(v) for m, v in values.items()}, tasks


MATCH_KEYS = ('code_scope', 'inputs')


def node_of(d):
    """Camber node type a packed stage-2 directory ran on (pack.json), else None.

    Brian2 compiles with -march=native, so a bare reference pairs only within one node type.
    """
    path = Path(d) / 'pack.json'
    return load(path).get('node') if path.exists() else None


def stage2_decide(screen, bare_dirs, candidate_dirs, mac_bare_dir=None, partial=False):
    """Section 2.6 on split Camber stage-2 outputs.

    A stage-2 directory holds one or more candidates (reflex/ and long/) and, for a packed
    batch, its own bare/. Each directory pairs with the one bare reference whose code_scope,
    inputs and node type match (its own bare/ first). R-long rows were measured for every
    candidate; only R-reflex passers use them. Only the tier-wide admitted (cap 20) enter
    the decision; extra outputs are recorded. Partial (an interim screen or unfinished stage 2)
    evaluates what landed, lists admitted candidates still pending and never ranks.
    """
    if screen.get('settings_missing') and not partial:
        raise ValueError(f"screen has unfinished settings {screen['settings_missing']}")
    bares = []
    for b in [Path(b) for b in bare_dirs] + [Path(d) / 'bare' for d in candidate_dirs
                                             if (Path(d) / 'bare' / 'tasks.json').exists()]:
        tasks = load(b / 'tasks.json')
        values = bare_values(row_sets(tasks, rest.read_evaluations(b, tasks)))
        idents = {json.dumps({k: x['identity'][k] for k in MATCH_KEYS}, sort_keys=True) for x in tasks}
        if len(idents) != 1:
            raise ValueError(f'{b}: mixed bare reference identities')
        bares.append({'dir': b, 'identity': tasks[0]['identity'], 'values': values,
                      'node': node_of(b.parent) if b.name == 'bare' else None})
    measured = {}
    for d in candidate_dirs:
        d = Path(d)
        reflex = load(d / 'reflex' / 'tasks.json')
        long = load(d / 'long' / 'tasks.json')
        idents = {json.dumps({k: x['identity'][k] for k in MATCH_KEYS}, sort_keys=True) for x in reflex + long}
        if len(idents) != 1:
            raise ValueError(f'{d}: mixed execution identities')
        ident = json.loads(idents.pop())
        match = [b for b in bares if b['node'] == node_of(d)
                 and all(b['identity'][k] == ident[k] for k in MATCH_KEYS)]
        own = [b for b in match if b['dir'].parent == d]
        if own:
            bare = own[0]
        elif len(match) == 1:
            bare = match[0]
        elif not match:
            raise ValueError(f'{d}: no bare reference matches code_scope, inputs and node')
        else:
            raise ValueError(f'{d}: ambiguous bare reference')
        sets = row_sets(reflex, rest.read_evaluations(d / 'reflex', reflex))
        long_rows = rest.read_evaluations(d / 'long', long)
        stems = {}
        for task in long:
            stems.setdefault(task['candidate_id'], set()).add(Path(task['path']).stem)
        for task in reflex:
            cid = task['candidate_id']
            if cid in measured and measured[cid]['dir'] != d:
                raise ValueError(f'duplicate stage-2 candidate {cid}')
            index = int(task.get('group', Path(task['path']).stem).split('-')[1])
            measured[cid] = {'dir': d, 'index': index, 'sets': sets, 'bare': bare,
                             'long': [r for r in long_rows if r['task_id'] in stems.get(cid, set())]}
    admitted, excluded = rest.capped_candidates(screen['candidates'])

    def evaluate(c):
        m = measured[rest.candidate_id(c)]
        r = reflex_result(c, m['index'], m['sets'], m['bare']['values'])
        if r['reflex_passed']:
            r.update(rest.long_decision(m['long']))
        return {**r, 'stage2_dir': str(m['dir']), 'bare_dir': str(m['bare']['dir'])}

    updated, pending = [], []
    for n, c in enumerate(admitted, 1):
        cid = rest.candidate_id(c)
        if cid in measured:
            updated.append(evaluate(c))
        elif partial:
            pending.append({'candidate_id': cid, 'admission_order': n})
        else:
            raise ValueError(f'admitted candidate without stage 2: {cid}')
    by_id = {rest.candidate_id(c): c for c in updated}
    evaluated = [by_id.get(rest.candidate_id(c), c) for c in screen['candidates']]
    decision = rest.decide(evaluated, tier=screen['tier'], complete=not partial)
    means = lambda values: {k: sum(v) / len(v) for k, v in values.items() if v}
    beyond = sorted(set(measured) - set(by_id))
    screened = {rest.candidate_id(c): c for c in screen['candidates']}
    status = 'pending' if partial else 'passed' if decision['status'] == 'ranked' else 'failed'
    record = {'status': status, 'class': 'development',
              'decision_status': decision['status'], 'decision': decision, 'admitted': updated,
              'pending_stage2': pending, 'screen_settings_missing': screen.get('settings_missing', []),
              'excluded': excluded, 'measured_beyond_cap': beyond,
              'beyond_cap_results': [evaluate(screened[cid]) for cid in beyond if cid in screened],
              'bare_references': [{'dir': str(b['dir']), 'identity': b['identity'], 'means_hz': means(b['values'])}
                                  for b in bares]}
    for entry, b in zip(record['bare_references'], bares):
        entry['node'] = b['node']
    if mac_bare_dir is not None:
        mac, _ = bare_means(mac_bare_dir)
        checks = []
        for b in record['bare_references']:
            rel = {k: abs(b['means_hz'][k] - mac[k]) / abs(mac[k]) for k in mac}
            checks.append({'camber_dir': b['dir'], 'mac_means_hz': mac, 'camber_means_hz': b['means_hz'],
                           'relative_difference': rel, 'tolerance': .25,
                           'platform_sensitive': any(v > .25 for v in rel.values())})
        record['bare_platform_check'] = {'checks': checks, 'ranked_on': 'camber bare references'}
    return record


def pack_tasks(pack, out, identity, q):
    """One packed stage-2 job: R-long first (longest), split R-reflex, optional split bare."""
    cands = pack['candidates']
    reflex = [t for t in reflex_tasks(cands, out / 'reflex', identity, q, split=True) if not t.get('bare')]
    long = [t for i, c in enumerate(cands)
            for t in long_tasks_for(c, i, out / 'long', identity, reflex[0]['plan_sha256'], q)]
    batches = [(long, out / 'long'), (reflex, out / 'reflex')]
    if pack.get('with_bare'):
        batches.append((reflex_tasks([], out / 'bare', identity, q, split=True), out / 'bare'))
    return batches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('map-plan', 'screen', 'aggregate', 'confirm', 'bare', 'tier2-plan',
                                           'combine', 'stage2-candidates', 'stage2-candidate', 'stage2-decide',
                                           'stage2-packs', 'stage2-pack'))
    parser.add_argument('--input', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', default='auto')
    parser.add_argument('--bare-dir', type=Path, help='reuse a prepared matched bare reference')
    parser.add_argument('--job-id', default=os.environ.get('CAMBER_JOB_ID'))
    parser.add_argument('--q', type=float, default=42.5, help='measured wall s / brain s for task budgets')
    parser.add_argument('--split', action='store_true', help='one child per probe (bare)')
    parser.add_argument('--dirs', type=Path, nargs='*', default=[], help='shard or stage-2 output directories')
    parser.add_argument('--allow-partial', action='store_true')
    parser.add_argument('--mac-bare-dir', type=Path)
    parser.add_argument('--bare-dirs', type=Path, nargs='*', default=[])
    parser.add_argument('--per-job', type=int, default=8)
    parser.add_argument('--node', default='large-cpu', help='Camber node type a pack is sized for')
    parser.add_argument('--bare-every-pack', action='store_true', help='each pack measures its own bare reference')
    parser.add_argument('--prefix', default='s2')
    args = parser.parse_args()
    if args.action == 'map-plan':
        save(args.out, rest.map_plan(args.input))
    elif args.action == 'combine':
        record = combine(args.input, args.dirs, args.allow_partial)
        save(args.out, record)
        print(json.dumps({'settings': len(record['settings_included']), 'missing': record['settings_missing'],
                          'evaluations': record['evaluations'], 'screen_passers': record['screen_passers']}))
    elif args.action == 'stage2-candidates':
        # Tier-wide admissions (cap 20, order key); ids already written under --dirs are skipped.
        screen = load(args.input)
        source = hashlib.sha256(read_bytes(args.input)).hexdigest()
        done = submitted_ids(args.dirs)
        args.out.mkdir(parents=True, exist_ok=True)
        written = []
        for n, c in enumerate(screen['admitted'], 1):
            if rest.candidate_id(c) in done:
                continue
            path = args.out / f'{args.prefix}-{n:02d}.json'
            if path.exists():
                raise ValueError(f'refusing to overwrite {path}')
            save(path, {'candidate': c, 'candidate_id': rest.candidate_id(c),
                        'admission_order': n, 'screen_sha256': source})
            written.append(path.name)
        print(json.dumps({'admitted': len(screen['admitted']), 'written': written}))
    elif args.action == 'stage2-packs':
        # New tier-wide admissions packed into jobs of --per-job; the first pack (or every pack) carries a bare batch.
        screen = load(args.input)
        source = hashlib.sha256(read_bytes(args.input)).hexdigest()
        done = submitted_ids(args.dirs)
        new = [(n, c) for n, c in enumerate(screen['admitted'], 1) if rest.candidate_id(c) not in done]
        args.out.mkdir(parents=True, exist_ok=True)
        written = []
        for k in range(0, len(new), args.per_job):
            chunk = new[k:k + args.per_job]
            path = args.out / f'{args.prefix}-{k // args.per_job + 1:02d}.json'
            if path.exists():
                raise ValueError(f'refusing to overwrite {path}')
            save(path, {'candidates': [c for _, c in chunk], 'candidate_ids': [rest.candidate_id(c) for _, c in chunk],
                        'admission_orders': [n for n, _ in chunk], 'with_bare': k == 0 or args.bare_every_pack, 'screen_sha256': source,
                        'node': args.node})
            written.append(path.name)
        print(json.dumps({'admitted': len(screen['admitted']), 'new': len(new), 'written': written}))
    elif args.action == 'stage2-decide':
        record = stage2_decide(load(args.input), args.bare_dirs, args.dirs, args.mac_bare_dir, args.allow_partial)
        save(args.out, record)
        print(json.dumps({'decision': record['decision_status'], 'ranked': len(record['decision']['ranked'])}))
    elif args.action == 'aggregate':
        result = aggregate(args.out)
        print(json.dumps({'evaluations': result['evaluations'], 'admitted': len(result['admitted']),
                          'decision': result['decision']['status']}))
    elif args.action == 'tier2-plan':
        record = load(args.input)
        decision = record.get('decision', record)
        if decision['status'] != 'tier2':
            raise ValueError('tier 2 requires its recorded trigger')
        settings = rest.tier2_settings(decision['tier2_pairs'])
        save(args.out, {'tier': 2, 'class': 'development', 'settings': [asdict(s) for s in settings],
                        'source_sha256': hashlib.sha256(read_bytes(args.input)).hexdigest(),
                        'evaluations': len(settings) * 57, 'brain_s': len(settings) * 57 * 12})
    else:
        if not args.job_id:
            parser.error('--job-id is required (use a unique mac- label for local work)')
        identity = rest.execution_identity(args.job_id)
        if args.action == 'screen':
            plan = load(args.input)
            tasks = rest.screen_tasks(plan, args.out, identity, args.q)
            args.out.mkdir(parents=True, exist_ok=True)
            saved = args.out / 'plan.json'
            if saved.exists() and load(saved) != plan:
                raise ValueError('existing plan differs')
            save(saved, plan)
            run_batch(tasks, args.out, args.workers)
            aggregate(args.out)
        elif args.action == 'stage2-pack':
            pack = load(args.input)
            args.out.mkdir(parents=True, exist_ok=True)
            if (args.out / 'pack.json').exists() and load(args.out / 'pack.json') != pack:
                raise ValueError('existing pack differs; use a new output directory')
            save(args.out / 'pack.json', pack)
            batches = pack_tasks(pack, args.out, identity, args.q)
            rows = run_batches(batches, args.workers)
            print(json.dumps({'stage': 'stage2-pack', **{out.name: len(r) for (_, out), r in zip(batches, rows)}}))
        elif args.action == 'stage2-candidate':
            c = load(args.input)['candidate']
            tasks = [t for t in reflex_tasks([c], args.out / 'reflex', identity, args.q, split=True) if not t.get('bare')]
            long = long_tasks_for(c, 0, args.out / 'long', identity, tasks[0]['plan_sha256'], args.q)
            reflex_rows, long_rows = run_batches([(tasks, args.out / 'reflex'), (long, args.out / 'long')], args.workers)
            print(json.dumps({'stage': 'stage2-candidate', 'reflex': len(reflex_rows), 'long': len(long_rows)}))
        elif args.action == 'bare':
            tasks = reflex_tasks([], args.out, identity, args.q, split=args.split)
            rows = run_batch(tasks, args.out, args.workers)
            print(json.dumps({'stage': 'bare-reference', 'evaluations': len(rows), 'out': str(args.out)}))
        else:
            confirm(load(args.input), args.out, identity, args.workers, args.q, args.bare_dir)


if __name__ == '__main__':
    main()
