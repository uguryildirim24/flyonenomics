"""Constructed R4, K1r, freeze and dispatcher tests; no engine built."""
from pathlib import Path
import json
import subprocess

import pytest

from flyonenomics.drive import rest_calibration as rest


def test_r4_priority_timeout_and_exhaustion():
    ranked=[{'id':'a'},{'id':'b'},{'id':'c'}]
    assert rest.select_candidate(ranked,{},elapsed_hours=11)['status']=='blocked'
    assert rest.select_candidate(ranked,{},elapsed_hours=12)['candidate']['id']=='a'
    visual={'candidates':[{'candidate_id':'c','passed':True},{'candidate_id':'b','passed':True}]}
    assert rest.select_candidate(ranked,visual,elapsed_hours=1)['candidate']['id']=='b'
    assert rest.select_candidate(ranked,visual,elapsed_hours=1,excluded={'b'})['candidate']['id']=='c'
    assert rest.select_candidate([],{},elapsed_hours=0)['outcome']=='P2-partial-B'


def test_k1_bound_rejection_and_improvement():
    def measure(w):
        return {'F':2,'b':.01,'central':1,'groups':{'central':10**(10*(w['central']-1.05))}}
    common={'sensory':0.,'central':1.}
    result=rest.coordinate_descent(common,{'central':1.},measure)
    assert result['table']=='T' and result['weights']['central']==pytest.approx(1.05)
    assert len(result['evaluations'])<=40
    assert all(abs(e['weights']['central']-1)<=.1+1e-10 and e['weights']['sensory']==0 for e in result['evaluations'])
    def reject(w):return {**measure(w),'F':3}
    assert rest.coordinate_descent(common,{'central':1.},reject)['table']=='C'
    assert rest.coordinate_descent(common,{'central':1.},measure,max_evals=1)['table']=='C'


def test_configuration_commit_is_isolated_and_evidence_does_not_change_it(tmp_path,monkeypatch):
    def git(*args):return subprocess.check_output(['git',*args],cwd=tmp_path,text=True).strip()
    git('init','-q');git('config','user.email','tests@example.test');git('config','user.name','WP19 test')
    (tmp_path/'src').mkdir();(tmp_path/'src/base.py').write_text('x=1\n')
    (tmp_path/'data').mkdir();git('add','.');git('commit','-qm','baseline')
    drive=tmp_path/'data/drive-v0.2.yaml';da=tmp_path/'data/dopamine-v0.2.yaml'
    monkeypatch.setattr(rest,'ROOT',tmp_path);monkeypatch.setattr(rest,'DRIVE',drive);monkeypatch.setattr(rest,'DOPAMINE',da)
    monkeypatch.setattr(rest,'RECORDS',tmp_path/'validation/records/p2')
    sha=rest.freeze_configuration(drive,{'version':'v0.2','provenance':{},'number':1})
    assert git('show','--format=','--name-only',sha)=='data/drive-v0.2.yaml'
    blob=git('hash-object',str(drive))
    rest.RECORDS.mkdir(parents=True);(rest.RECORDS/'wp19-test.json').write_text('{}\n')
    rest.commit_records('test evidence')
    assert git('hash-object',str(drive))==blob and git('status','--porcelain')==''
    # A tracked modification starts with a leading space in porcelain output.
    (rest.RECORDS/'wp19-test.json').write_text('{"changed":true}\n')
    rest.commit_records('test evidence modification')
    (tmp_path/'src/base.py').write_text('x=2\n')
    with pytest.raises(RuntimeError):rest.freeze_configuration(da,{'provenance':{}})
    assert not da.exists()


def test_owned_stage_imports_are_engine_free_and_discovered():
    # A separate interpreter makes this an actual import-side-effect check.
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([str(root/'.venv/bin/python'),'-c',
      "import runpy,sys; from flyonenomics.drive import rest_calibration; from flyonenomics.neuromod import calibration; "
      "assert 'flyonenomics.engine.brian_engine' not in sys.modules; m=runpy.run_path('scripts/calibrate.py'); s=m['discover_stages'](2); "
      "assert {'C0','R4','K1r','drive','K2r','Q-rest'} <= s.keys(); "
      "assert all(callable(s[k].input_identity) for k in ('C0','R4','K1r','drive','K2r','Q-rest'))"],cwd=root,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_fallthrough_enforces_common_then_three_candidate_cap():
    f=rest.fall_through
    assert f('T','a',[],['a','b'])['required']=='common table C'
    assert f('C','a',[],['a','b'])['remaining']==['b']
    assert f('C','b',['a'],['a','b'])['outcome']=='P2-partial-B'
    assert f('C','c',['a','b'],['a','b','c','d'])['outcome']=='P2-partial-B'


def test_qrest_full_order_on_constructed_worker_tables(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from flyonenomics.store.results import atomic_json
    params=rest._params()
    records=tmp_path/'validation/records/p2';records.mkdir(parents=True)
    atomic_json(records/'K1r.json',{'evaluations':[]})
    monkeypatch.setattr(rest,'RECORDS',records)
    monkeypatch.setattr(rest,'_params',lambda:params)
    monkeypatch.setattr(rest,'require_clean',lambda:None)
    monkeypatch.setattr(rest,'commit_records',lambda message:'evidence-sha')
    monkeypatch.setattr(rest,'_sha',lambda p:'a'*64)
    monkeypatch.setattr(rest,'_entry_identity',lambda f:SimpleNamespace(inputs={},code_commit='configuration-sha'))
    recorded=[]
    monkeypatch.setattr(rest,'publish_entry',lambda test_id,*args,**kw:recorded.append(test_id))
    def jobs(js,**kwargs):
        out=[]
        for j in js:
            r={'seed':j['seed'],'settled':True,'F':2.6,'b':.01,'central':1,'DAN':1,'KC':1,
               'stability_ratio':1,'edge_ratio':1,'ignited':False,'groups':{'central':1,'DAN':1,'KC':1},
               'rate_safety':{'outcome':'passed'},'stimulated_safety':{'outcome':'passed'},
               'qualification':{'passed':True},'difference_hz':60,'logged_inputs':[],
               'sugar_hz':80,'sugar_bitter_hz':20}
            if 'jitter_stream' in j:r['stream']=j['jitter_stream']
            out.append(r)
        return {'rows':out,'benchmark':{'workers':3,'brain_s':1,'probe_wall_s':2}}
    monkeypatch.setattr(rest,'run_jobs',jobs)
    result=rest.run_qrest_once()
    assert result['status']=='passed'
    assert recorded[:8]==list(rest.levelrest.Q_ORDER)
    assert recorded[8:]==['1.3r','2.1r','2.5r']


def test_qrest_stops_at_failed_first_entry(tmp_path,monkeypatch):
    # The ordered loop must not advance neural qualification after a failed
    # first criterion; use the same entry point with constructed failed rows.
    from types import SimpleNamespace
    from flyonenomics.store.results import atomic_json
    params=rest._params();records=tmp_path/'p2';records.mkdir()
    atomic_json(records/'K1r.json',{})
    monkeypatch.setattr(rest,'RECORDS',records);monkeypatch.setattr(rest,'_params',lambda:params)
    monkeypatch.setattr(rest,'require_clean',lambda:None);monkeypatch.setattr(rest,'commit_records',lambda m:'sha')
    monkeypatch.setattr(rest,'_sha',lambda p:'a'*64)
    monkeypatch.setattr(rest,'_entry_identity',lambda f:SimpleNamespace(inputs={},code_commit='sha'))
    observed=[];monkeypatch.setattr(rest,'publish_entry',lambda k,*a,**kw:observed.append(k))
    calls=[]
    def jobs(js,**kw):
        calls.append(js)
        return {'rows':[{'seed':s,'settled':False,'qualification':{'passed':True},'logged_inputs':[],
                         'groups':{'central':1}} for s in (1,2,3)],
                'benchmark':{'workers':3,'brain_s':1,'probe_wall_s':2}}
    monkeypatch.setattr(rest,'run_jobs',jobs)
    assert rest.run_qrest_once()['status']=='failed'
    assert len(calls)==1 and observed==['3.1br','2.1r','2.5r']


def test_output_guard_invalidates_missing_or_changed_config(tmp_path,monkeypatch):
    from flyonenomics.store.results import atomic_json
    monkeypatch.setattr(rest,'ROOT',tmp_path);monkeypatch.setattr(rest,'RECORDS',tmp_path/'records')
    path=tmp_path/'drive.yaml';path.write_text('value: 1\n')
    atomic_json(rest.RECORDS/'drive.json',{'sha256':rest._sha(path)})
    assert rest.output_guard({'input':'same'},'drive',path)=={'input':'same'}
    path.write_text('value: 2\n')
    assert 'changed_output' in rest.output_guard({'input':'same'},'drive',path)
    path.unlink()
    assert rest.output_guard({},'drive',path)['changed_output']['sha256'] is None


def test_wp17_committed_producer_shape_and_parameter_ids():
    candidate={'g_gaba':3.,'g_glu':4.,'sigma_th':0.,'optic_exemption':False,'n_bg':100,'w_bg':1.15,
               'provenance':[{'job_id':123,'platform':'linux-x86_64'}]}
    record={'status':'passed','decision_status':'ranked','decision':{'status':'ranked','ranked':[candidate]}}
    ranked=rest.ranked_candidates(record)
    assert ranked[0]['id']=='3.0-4.0-0.0-False-100-1.15'
    assert ranked[0]['provenance']==candidate['provenance']
    assert rest.ranked_candidates({'status':'failed','decision':{'status':'P2-partial-B','ranked':[]}})==[]
    with pytest.raises(ValueError):rest.ranked_candidates({'status':'passed','decision':{'status':'pending','ranked':[]}})
    from flyonenomics.io import read_json
    assert rest.ranked_candidates(read_json(rest.r2_path()))==[]
    assert rest.r2_path().name=='rest-tier2-stage2.json'


def test_jitter_matches_existing_seed_axes_and_float32():
    import numpy as np
    p=rest._params()
    for j in range(5):
        expected=np.random.default_rng(np.random.SeedSequence(20260912,spawn_key=(0,j,4))).lognormal(-.3*.3/2,.3,12).astype(np.float32)
        assert np.array_equal(rest.jitter_scale(12,j,p),expected)


def test_unmodified_dispatcher_reaches_r1_from_fresh_discovery(tmp_path,monkeypatch):
    """C0 is registered through discovery, runs no engine, resumes, and R1 is next."""
    import importlib.util
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('wp19_calibrate',root/'scripts/calibrate.py')
    calibrate=importlib.util.module_from_spec(spec);spec.loader.exec_module(calibrate)
    monkeypatch.setattr(calibrate,'RECORDS_P2',tmp_path/'p2');monkeypatch.setattr(calibrate,'STAGES',{})
    # lane/w17 registers R1 and R2; with no imported Camber summary R1 blocks, deterministically.
    monkeypatch.setenv('FLYONENOMICS_REST_RESULTS',str(tmp_path/'no-rest-results'))
    assert calibrate.discover_stages(phase=2)['C0'] is rest.run_c0
    first=calibrate.run_stages(phase=2)
    assert list(first)==calibrate.ORDER_P2
    assert first['C0']['status']=='passed' and first['C0']['test_0_10']=='passed' and first['C0']['engine'] is False
    assert first['R1']['status']=='blocked' and first['R1']['reason'].startswith('missing ')
    assert all(first[n]=={'status':'blocked','reason':'requires R1'} for n in calibrate.ORDER_P2[2:])
    stored=json.loads((tmp_path/'p2/C0.json').read_text())
    assert stored['input_identity']==rest.run_c0.input_identity()
    assert set(stored['outputs'])=={'data/transmitters-v0.2.yaml','data/populations-v0.2.yaml','docs/transmitter-census.md'}
    # A passed C0 with unchanged inputs resumes from its record without rerunning 0.10.
    import flyonenomics.validation.level0_substrate as substrate
    monkeypatch.setattr(substrate,'test_0_10',lambda:(_ for _ in ()).throw(AssertionError('C0 reran')))
    second=calibrate.run_stages(phase=2)
    assert second['C0']==stored and second['R1']['status']=='blocked'


def test_development_switch_selects_step5_substrate_and_refuses_ranked(tmp_path,monkeypatch):
    from flyonenomics.drive.rest import load_drive_rest
    monkeypatch.setenv(rest.SUBSTRATE_ENV,'bogus')
    with pytest.raises(ValueError):rest.development()
    monkeypatch.delenv(rest.SUBSTRATE_ENV)
    assert not rest.development() and rest._rec()==rest.RECORDS and rest._drive()==rest.DRIVE
    monkeypatch.setenv(rest.SUBSTRATE_ENV,'development')
    assert rest._rec()==rest.RECORDS/'dev' and rest._drive()==rest.DEV_DRIVE and rest._dopamine()==rest.DEV_DOPAMINE
    chosen=rest.development_candidate()
    drive=load_drive_rest(rest.DEV_SOURCE)
    raw=__import__('yaml').safe_load(rest.DEV_SOURCE.read_text())
    weights={w for g,w in drive['w_bg'].items() if g!='sensory'}
    assert chosen['candidate']['id']==str(raw['candidate_id'])
    assert chosen['candidate']['n_bg']==int(drive['n_bg'])
    assert chosen['candidate']['w_bg']==weights.pop()
    assert chosen['candidate']['seed']==int(drive['seed'])
    assert '2.6 step 5' in chosen['reason'] and 'ranked []' in chosen['reason']
    ranked=tmp_path/'decision.json';ranked.write_text(json.dumps({'status':'passed','decision':{'status':'ranked','ranked':[{'id':'x'}]}}))
    monkeypatch.setattr(rest,'r2_path',lambda:ranked)
    with pytest.raises(ValueError,match='ranked candidate exists'):rest.development_candidate()


def test_development_records_entries_and_overrides_never_canonical(tmp_path,monkeypatch):
    from flyonenomics.types import LayerFlags
    from flyonenomics.validation.binding import ValidationEntry, build_identity
    from flyonenomics.validation.execute import bind_entry
    from flyonenomics.validation import levelrest
    monkeypatch.setattr(rest,'RECORDS',tmp_path/'p2')
    monkeypatch.setenv(rest.SUBSTRATE_ENV,'development')
    saved=rest.save_stage('R4',{'status':'passed'},{'inputs':{}})
    assert saved['configuration_class']=='development' and saved['qualifies']=='nothing'
    assert (tmp_path/'p2/dev/R4.json').is_file() and not (tmp_path/'p2/R4.json').exists()
    inputs=['data/params-v0.2.yaml']
    ident=build_identity(rest.ROOT,connectome_version='783',layers=LayerFlags(background=True),assay='spontaneous',declared_inputs=inputs)
    rest.publish_entry('2.3r',{'outcome':'passed'},ident,'rest-short.json',inputs=inputs)
    stored=ValidationEntry.model_validate(json.loads((tmp_path/'p2/dev/entry-2.3r.json').read_text()))
    assert stored.compatibility=='development' and 'qualifies nothing' in stored.stub
    assert stored.measured['configuration_class']=='development'
    assert bind_entry(stored,rest.ROOT).compatibility=='development'
    assert levelrest.entry('2.3r').outcome=='unavailable'
    background=rest.development_overrides({'kind':'K1r','drive_document':{'background':{'n_bg':25}}})
    assert background['overrides']=={'bg.n_bg':25}
    assert 'overrides' not in rest.development_overrides({'kind':'ff','bare':True})
    with pytest.raises(ValueError,match='development'):
        rest.freeze_configuration(rest.DEV_DRIVE,{'provenance':{}})
    monkeypatch.delenv(rest.SUBSTRATE_ENV)
    assert rest.development_overrides({'kind':'K1r','drive_document':{'background':{'n_bg':25}}}).get('overrides') is None
    with pytest.raises(ValueError,match='only'):
        rest.freeze_configuration(rest.DEV_DRIVE,{'provenance':{},'configuration_class':'development'})
    with pytest.raises(ValueError,match='development'):
        rest.freeze_configuration(rest.DRIVE,{'provenance':{},'configuration_class':'development'})


def test_drive_threshold_seed_comes_from_the_candidate_not_a_constant():
    """Decision 45: make_drive and _candidate_drive re-materialise from the recorded seed."""
    import numpy as np
    groups={"sensory":[0],"central":[1,2]}
    weights={"sensory":0.,"central":1.15}
    candidate={"g_gaba":3.,"g_glu":6.,"sigma_th":1.,"n_bg":25,"optic_exemption":False,
               "seed":20260912,"scope":"brain","w_bg":1.15}
    doc=rest.make_drive(candidate,groups,weights,scale_sha="a"*64,threshold_sha="b"*64,evidence={})
    assert doc["threshold"]["seed"]==20260912
    other=rest.make_drive({**candidate,"seed":20260914},groups,weights,scale_sha="a"*64,threshold_sha="b"*64,evidence={})
    assert other["threshold"]["seed"]==20260914
    with pytest.raises(ValueError,match="seed"):
        rest.make_drive({k:v for k,v in candidate.items() if k!="seed"},groups,weights,
                        scale_sha="a"*64,threshold_sha="b"*64,evidence={})
    seen=[]
    class FakeReg:
        n=4
    def fake_apply(target,params,settings,**kwargs):
        seen.append(settings.get("seed"))
        target.scale=np.ones(3,dtype=np.float32)
    monkeypatch=pytest.MonkeyPatch()
    monkeypatch.setattr("flyonenomics.registry.build_registry",lambda *a,**k:FakeReg())
    monkeypatch.setattr("flyonenomics.drive.background.group_indices",
                        lambda r:{"sensory":[0],"central":[1]})
    monkeypatch.setattr("flyonenomics.types.load_params",
                        lambda p:type("P",(),{"get":lambda self,k:100 if k=="bg.n_bg" else 10.})())
    monkeypatch.setattr("flyonenomics.drive.rest.apply_rest_substrate",fake_apply)
    monkeypatch.setattr("flyonenomics.drive.rest.draw_threshold_z",
                        lambda seed,n:(seen.append(("z",seed)) or np.zeros(n)))
    monkeypatch.setattr("flyonenomics.drive.rest.z_sha256",lambda z:"zdigest")
    try:
        drive,_,_=rest._candidate_drive(candidate)
    finally:
        monkeypatch.undo()
    assert drive["threshold"]["seed"]==20260912
    assert 20260912 in seen and ("z",20260912) in seen
    assert 20260914 not in seen


def test_k1r_speculative_replay_equals_serial_descent():
    """The cached replay requests points in serial order and ends on the serial result."""
    params=rest._params()
    common={'sensory':0.,'central':1.,'KC':1.,'DAN':1.}
    targets={'central':2.,'KC':1.,'DAN':1.5}
    def measure(w):
        return {'F':2,'b':.01,'central':1,'groups':{'central':10**(10*(w['central']-1.04)),'KC':1.+.3*(w['KC']-1),
                                                    'DAN':1.5*10**(3*(w['DAN']-.97))}}
    serial=rest.coordinate_descent(common,targets,measure,bound=params.get('k1r.bound_mv'),min_improvement=params.get('k1r.min_improvement'))
    for batch in (1,3,8,40):
        cache={};rounds=0
        while True:
            result,pending=rest.replay_descent(common,targets,cache,params)
            if not pending:break
            first=pending[0]
            for w in pending[:batch]:cache[rest._weights_key(w)]=measure(w)
            rounds+=1
            assert rest._weights_key(first) in cache
        assert result['weights']==serial['weights'] and result['table']==serial['table']
        assert result['evaluations']==serial['evaluations']
        if batch==1:assert rounds==len(serial['evaluations'])


def test_r4_without_development_switch_refuses_drive_dev_p2(monkeypatch):
    """Without FLYONENOMICS_REST_SUBSTRATE, R4 must not select the development file."""
    monkeypatch.delenv(rest.SUBSTRATE_ENV,raising=False)
    captured=[]
    monkeypatch.setattr(rest,'save_stage',lambda name,record,identity=None:captured.append((name,record)) or record)
    result=rest.run_r4()
    dumped=json.dumps(result)
    assert 'drive-dev-p2' not in dumped
    assert result.get('source',{}).get('path')!='data/drive-dev-p2.yaml'
    assert captured and captured[0][0]=='R4'
    assert result['status'] in ('blocked','failed')
    if result['status']=='failed':
        assert result.get('outcome')=='P2-partial-B'


def test_committed_dev_records_never_bind_canonical():
    """Historical dev records qualify nothing after canonical calibration is committed."""
    from flyonenomics.validation.binding import ValidationEntry
    from flyonenomics.validation.execute import bind_entry
    root=Path(__file__).resolve().parents[1]
    bad=[]
    for path in sorted((root/'validation/records/p2/dev').rglob('*.json')):
        def walk(obj,name=path.name):
            if isinstance(obj,dict):
                if obj.get('configuration_class') not in (None,'development'):
                    bad.append((name,'class',obj.get('configuration_class')))
                if obj.get('qualifies') not in (None,'nothing'):
                    bad.append((name,'qualifies',obj.get('qualifies')))
                if obj.get('compatibility') not in (None,'development'):
                    bad.append((name,'compatibility',obj.get('compatibility')))
                for value in obj.values():
                    walk(value)
            elif isinstance(obj,list):
                for value in obj:
                    walk(value)
        walk(json.loads(path.read_text()))
    assert bad==[]
    # Item 125: K2r on the declared unit publishes the one canonical 3.1r entry.
    assert {p.name for p in (root/'validation/records/p2').glob('entry-*.json')} == {'entry-3.1r.json'}
    assert not (root/'validation/records/p2'/'R4.json').exists()
    for test_id in rest.levelrest.IDS:
        if test_id in ('3.1r-alg', '3.1r'):
            continue
        entry=rest.levelrest.entry(test_id)
        assert entry.outcome=='unavailable' and entry.compatibility=='development'
    measured=rest.levelrest.entry('3.1r')
    assert measured.outcome=='recorded' and measured.compatibility=='canonical'
    stored=root/'validation/records/p2/dev/entry-3.1br.json'
    bound=bind_entry(ValidationEntry.model_validate(json.loads(stored.read_text())),root)
    assert bound.compatibility=='development' and bound.outcome=='failed'


def test_both_k2r_records_bind_when_only_the_execution_platform_differs(monkeypatch):
    """Item 147 makes platform provenance: both stored K2r identities bind across platforms."""
    from flyonenomics.validation import binding

    root=Path(__file__).resolve().parents[1]
    paths=(root/'validation/records/p2/entry-3.1r.json',
           root/'validation/records/p2/wp19-entry-3.1r-c8e958eb36bbaa7b.json')
    assert paths[0].read_bytes() == paths[1].read_bytes()
    for path in paths:
        entry=binding.ValidationEntry.model_validate(json.loads(path.read_text()))
        stored_inputs=entry.identity.inputs
        monkeypatch.setattr(binding,'blob_id',lambda _root,rel,inputs=stored_inputs:inputs[rel])
        other_platform=entry.identity.model_copy(update={'platform':'darwin-arm64'})
        assert binding.is_compatible(
            entry,other_platform,current_fixture_hash=entry.identity.fixture_hash,repo=root,
        ) == (True,'valid')
        assert binding.binding_of(
            entry,other_platform,current_fixture_hash=entry.identity.fixture_hash,repo=root,
        ) == 'valid'


def test_qrest_exercise_runs_every_batch_past_failure_and_publishes_nothing(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from flyonenomics.store.results import atomic_json
    params=rest._params();records=tmp_path/'p2'
    monkeypatch.setattr(rest,'RECORDS',records)
    with pytest.raises(ValueError,match='development'):rest.run_qrest_once(exercise=True)
    monkeypatch.setenv(rest.SUBSTRATE_ENV,'development')
    atomic_json(records/'dev/K1r.json',{})
    monkeypatch.setattr(rest,'_params',lambda:params)
    monkeypatch.setattr(rest,'require_clean',lambda:None);monkeypatch.setattr(rest,'commit_records',lambda m:'sha')
    monkeypatch.setattr(rest,'_sha',lambda p:'a'*64)
    monkeypatch.setattr(rest,'_entry_identity',lambda f:SimpleNamespace(inputs={},code_commit='sha',model_dump=lambda mode:{}))
    monkeypatch.setattr(rest.levelrest,'validate_ff_fixtures',lambda *a:None)
    published=[];monkeypatch.setattr(rest,'publish_entry',lambda k,*a,**kw:published.append(k))
    kinds=[]
    def jobs(js,**kw):
        kinds.append(js[0]['kind'])
        rows=[]
        for j in js:
            r={'seed':j['seed'],'settled':False,'qualification':{'passed':False},'logged_inputs':[],'F':2.,'b':.01,
               'stability_ratio':1.,'edge_ratio':1.,'ignited':False,'central':1.,'DAN':1.,'KC':1.,'groups':{'central':1.},
               'rate_safety':{'outcome':'passed'},'stimulated_safety':{'outcome':'passed'},'difference_hz':1.,
               'sugar_hz':80.,'sugar_bitter_hz':20.}
            if 'jitter_stream' in j:r['stream']=j['jitter_stream']
            rows.append(r)
        return {'rows':rows,'benchmark':{'workers':3,'brain_s':1,'probe_wall_s':2}}
    monkeypatch.setattr(rest,'run_jobs',jobs)
    result=rest.run_qrest_once(exercise=True)
    assert result['status']=='exercised' and published==[]
    assert result['entries']['3.1br']['outcome']=='failed'
    assert kinds==['short','long','margin','margin','safety','reflex','ff','ff','ff','ff','jitter','bitter']
    assert set(result['entries'])=={*rest.levelrest.Q_ORDER,'1.3r','2.1r','2.5r'}
    assert (records/'dev/wp19-exercise-2.4r.json').is_file() and not (records/'dev/B2-rest.json').exists()


def test_bare_feedforward_windows_skip_rest_ignition_rows(monkeypatch):
    """ff bare and scales-only windows load params v0.1, which has no ign rows (found by the dev exercise)."""
    import numpy as np
    from flyonenomics.types import load_params
    v01=load_params(rest.ROOT/'data/params-v0.1.yaml');v02=load_params(rest.ROOT/'data/params-v0.2.yaml')
    one_s=np.full(10,4.)
    with pytest.raises(KeyError):v01.get('ign.factor')
    assert rest.window_ignited(one_s,4.,v01,False) is None
    assert rest.window_ignited(one_s,4.,v02,True) is False
    monkeypatch.setenv(rest.SUBSTRATE_ENV,'development')
    assert 'overrides' not in rest.development_overrides({'kind':'ff','bare':True,'scales_only':True})
    assert rest.development_overrides({'kind':'reflex','drive_path':str(rest.DEV_SOURCE)})['overrides']=={'bg.n_bg':25}
