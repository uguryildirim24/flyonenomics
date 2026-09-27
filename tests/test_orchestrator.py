"""Slow state, intervention persistence, lifecycle, real replay and crash recovery."""
from __future__ import annotations
import json
import math
import os
import signal
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
import pytest
from flyonenomics.orchestrator.runner import background_weights
from flyonenomics.orchestrator.slowstate import SlowState
from flyonenomics.orchestrator.stubs import IdentityNeuromod
from flyonenomics.schema import load_experiment, Experiment
from flyonenomics.schema.experiment import Genotype
from flyonenomics.store import ResultsStore
from flyonenomics.store.results import read_json,atomic_json
from flyonenomics.types import ChunkResult,LayerFlags,load_params

ROOT=Path(__file__).resolve().parents[1]
PROCESS_TIMEOUT_S=180
POLL_S=0.05


def test_analytical_pk_and_probe_hold() -> None:
    """Exposure/washout equations and clock; mM food, µM brain, seconds."""
    p=load_params();state=SlowState(p)
    dose=p.get('dose.mph.default');state.start_dose('methylphenidate',dose)
    state.advance(7200)
    expected=p.get('pk.kappa')*1000*dose*(1-math.exp(-p.get('pk.k_a')*2))
    assert state.concentrations['methylphenidate']==pytest.approx(expected)
    before=state.concentrations.copy();row=state.row('probe')
    assert state.concentrations==before and row['t_brain_s']==7200
    state.advance(22)
    assert state.concentrations['methylphenidate']>before['methylphenidate']
    state.stop_dose('methylphenidate');before=state.concentrations['methylphenidate'];state.advance(3600)
    assert state.concentrations['methylphenidate']==pytest.approx(before*math.exp(-p.get('pk.k_e')))
    assert state.t_brain_s==10822
    split=SlowState(p);whole=SlowState(p)
    for s in (split,whole):s.start_dose('3-iodotyrosine',1)
    split.advance(10);split.advance(20);whole.advance(30)
    assert split.concentrations['3-iodotyrosine']==pytest.approx(whole.concentrations['3-iodotyrosine'])
    disabled=SlowState(p,False);disabled.start_dose('vehicle',dose);disabled.advance(3600)
    assert all(v==0 for v in disabled.concentrations.values())


def test_stub_interventions_persist() -> None:
    """Silence wins shifts, gains multiply and disconnect executes; arrays (4,), mV."""
    pops={'MN9':types.SimpleNamespace(idx=np.array([0],dtype=np.int32)), 'DAN':types.SimpleNamespace(idx=np.array([1],dtype=np.int32)), 'CX_DAN':types.SimpleNamespace(idx=np.array([2],dtype=np.int32))}
    registry=types.SimpleNamespace(n=4,population=lambda n:pops[n]);calls=[]
    engine=types.SimpleNamespace(disconnect=lambda i:calls.append(i.tolist()),set_threshold=lambda v:None,set_gain=lambda g:None)
    mod=IdentityNeuromod(registry,load_params(),LayerFlags(dan_fast_synapses='disconnect'))
    genotype=Genotype.model_validate({'named':'fumin','manipulations':[{'type':'shift_threshold','population':'MN9','delta_mv':3},{'type':'scale_gain','population':'MN9','factor':2},{'type':'silence','population':'MN9'},{'type':'disconnect','population':'MN9'}]})
    mod.apply_genotype(genotype.expanded(),engine)
    for _ in range(20):
        mod.on_chunk(np.ones(4,dtype=np.int32),0.01)
        composed=mod.compose();assert composed.v_th[0]==load_params().get('engine.silence_vth') and composed.gain[0]==2
    assert calls==[[0],[1,2]] and mod.state().da_c.shape==(0,)
    assert mod.fixed_point().shape==(0,)


def test_background_lazy_hook_and_missing_path(tmp_path: Path,monkeypatch: pytest.MonkeyPatch) -> None:
    """Call WP3's public hook only when enabled; mV weights (3,), YAML scalar fields."""
    e=load_experiment(ROOT/'data/experiments/sugar-reflex.json');reg=types.SimpleNamespace(n=3)
    assert background_weights(reg,e,tmp_path) is None
    e.layers=LayerFlags(background=True)
    e.substrate.drive_version='dev'
    module=types.ModuleType('flyonenomics.drive.background');seen=[]
    def weights(registry: object,table: dict) -> np.ndarray:
        seen.append((registry,table));return np.arange(3,dtype=float)
    module.background_weights=weights
    monkeypatch.setitem(sys.modules,'flyonenomics.drive.background',module)
    with pytest.raises(RuntimeError,match=r'flyonenomics.drive.background.*drive-dev.yaml'):
        background_weights(reg,e,tmp_path)
    (tmp_path/'data').mkdir();(tmp_path/'data/drive-dev.yaml').write_text('version: dev\n')
    np.testing.assert_array_equal(background_weights(reg,e,tmp_path),[0,1,2]);assert seen==[(reg,{'version':'dev'})]


def test_behaviour_accepted_and_manifest_names_only_remaining_stubs(tmp_path: Path,monkeypatch: pytest.MonkeyPatch) -> None:
    """WP6 reaches population resolution; WP5 and WP6 remove their real-component stubs."""
    import flyonenomics.registry
    from flyonenomics.orchestrator import run
    from flyonenomics.orchestrator.runner import _manifest
    class ResolutionReached(Exception):
        pass
    def reached(version, **kwargs):
        raise ResolutionReached(version)
    monkeypatch.setattr(flyonenomics.registry,'build_registry',reached)
    e=load_experiment(ROOT/'data/experiments/open-loop-steering.json')
    with pytest.raises(ResolutionReached, match='783'):
        run(e,ResultsStore(tmp_path),1)
    reg=types.SimpleNamespace(provenance_record={}, compartments=lambda: [])
    manifest=_manifest(e,reg,[],'done',0,0,0,{})
    development_ids = {entry['test_id'] for entry in
                       read_json(ROOT/'validation/status.json')['results']
                       if entry['compatibility'] == 'development'}
    assert development_ids.isdisjoint({entry['test_id'] for entry in manifest['validation']})
    assert next(entry for entry in manifest['validation'] if entry['test_id'] == '4.1')['outcome'] == 'failed'
    assert 'IdentityBehaviour' not in manifest['stubs']
    assert 'IdentityNeuromod' not in manifest['stubs']
    assert 'behaviour-v0.1.yaml' in manifest['checksums']
    sugar=load_experiment(ROOT/'data/experiments/sugar-reflex.json')
    assert 'IdentityBehaviour' in _manifest(sugar,reg,[],'done',0,0,0,{})['stubs']


@pytest.mark.slow
def test_real_stream_invariance() -> None:
    """Run 8 combinations on short real probes; ticks/Hz, exact authoritative tables."""
    code = "import os; from pathlib import Path; from flyonenomics.orchestrator.verification import check_invariance, replay_invariance_evidence; evidence=os.environ.get('FLYONENOMICS_INVARIANCE_EVIDENCE'); r=replay_invariance_evidence(Path(evidence)) if evidence and Path(evidence).is_file() else check_invariance(Path('runs/pytest-invariance')); assert r['all_tables_and_metrics_identical'] and r['arena_reset'] and len(r['runs'])==8"
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def _interrupt_run(root: Path, kill: bool) -> tuple[Path,subprocess.CompletedProcess]:
    code='''
from flyonenomics.schema import Experiment
from flyonenomics.orchestrator import run
from flyonenomics.store import ResultsStore
from flyonenomics.store.results import read_json
from pathlib import Path
fixture=read_json(Path("tests/fixtures/experiments/invariance.json"))
e=Experiment.model_validate(fixture["experiment"])
e.arms=e.arms[:1];e.seeds=[1]
for p in e.arms[0].protocol:p.duration_s=2
s=ResultsStore(RUN_ROOT)
print(run(e,s,1,fixture_settle_s={int(k):v for k,v in fixture["settle_s"].items()}),flush=True)
'''.replace('RUN_ROOT',repr(str(root)))
    process=subprocess.Popen([sys.executable,'-c',code],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    deadline=time.monotonic()+PROCESS_TIMEOUT_S;directory=None
    try:
        while time.monotonic()<deadline:
            for status_path in root.glob('*/status.json'):
                status=read_json(status_path);candidate=status_path.parent
                live=list(candidate.glob('arm-*/seed-*/live/probe-0.ndjson'))
                if status['state']=='running' and live and live[0].stat().st_size:
                    directory=candidate
                    if kill:os.kill(status['worker_pids'][0],signal.SIGKILL)
                    else:(candidate/'CANCEL').touch()
                    break
            if directory is not None:break
            if process.poll() is not None:break
            time.sleep(POLL_S)
        stdout,stderr=process.communicate(timeout=PROCESS_TIMEOUT_S)
        assert directory is not None,(stdout,stderr)
        return directory,subprocess.CompletedProcess(process.args,process.returncode,stdout,stderr)
    finally:
        if process.poll() is None:
            process.terminate();process.wait(timeout=10)


@pytest.mark.slow
def test_cancel_mid_probe_finalises_valid_partial_tables() -> None:
    """Cancel after a live window; partial tables remain valid with manifest last."""
    root=ROOT/'runs/pytest-cancel';directory,result=_interrupt_run(root,False)
    assert result.returncode==0,result.stderr
    store=ResultsStore(root)
    assert read_json(directory/'status.json')['state']=='cancelled'
    assert store.validate_run(directory.name)==[]
    metrics=read_json(directory/'arm-wild-type/seed-1/metrics.json')
    assert 0<metrics['probes']['0']['duration_s']<2
    assert read_json(directory/'manifest.json')['state']=='cancelled'
    assert (directory/'manifest.json').stat().st_mtime_ns>=max(p.stat().st_mtime_ns for p in directory.rglob('*') if p.is_file() and p.name!='manifest.json')


@pytest.mark.slow
def test_killed_worker_rebuilds_incomplete() -> None:
    """SIGKILL a recording worker; traceback persists and rebuild says incomplete."""
    root=ROOT/'runs/pytest-killed';directory,result=_interrupt_run(root,True)
    assert result.returncode!=0
    status=read_json(directory/'status.json')
    assert status['state']=='failed' and 'worker killed' in status['traceback']
    assert not (directory/'manifest.json').exists()
    rows=ResultsStore(root).index.rebuild()
    assert next(row for row in rows if row['run_id']==directory.name)['state']=='incomplete'


def test_binding_four_cases() -> None:
    """Canonical/flags/protocol/lock drill; units none, scalar compatibility results."""
    code = "from flyonenomics.validation.level0 import test_0_9; e=test_0_9(); assert e.outcome=='passed' and e.compatibility=='canonical'"
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("background", [False, True])
def test_worker_background_precedes_initial_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, background: bool) -> None:
    """Background, scaled weights, snapshot; off ignores even a stale ratio-4 context."""
    from flyonenomics.drive import background as drive_background
    from flyonenomics.orchestrator import workers
    calls = []
    class Engine:
        def seed(self, seed): calls.append("seed")
        def build(self, *args, mechanisms=None):
            calls.append("build")
            self.scale = [1., 1.]
        def set_background(self, weights): calls.append(("background", weights.tolist()))
        def set_weight_scale(self, weights):
            calls.append(("scale", weights.tolist()))
            self.scale = weights.tolist()
        def store(self, key):
            assert self.scale == ([4., 1.] if background else [1., 1.])
            calls.append(("store", key))
    module = types.ModuleType("flyonenomics.engine.brian_engine")
    module.BrianEngine = Engine
    monkeypatch.setitem(sys.modules, "flyonenomics.engine.brian_engine", module)
    monkeypatch.setattr(workers, "connectome_files", lambda version: types.SimpleNamespace(connectivity=Path("fixture.parquet")))
    monkeypatch.setattr(drive_background, "_connection_signs", lambda path: np.array([-1., 1.]))
    def job(*args):
        expected = ["seed", "build"]
        if background:
            expected += [("background", [.2, .3]), ("scale", [4., 1.])]
        expected.append(("store", "initial"))
        assert calls == expected
        return {"cancelled": False}
    monkeypatch.setattr(workers, "execute_job", job)
    raw = load_experiment(ROOT / "data/experiments/sugar-reflex.json").model_dump(mode="json")
    raw["layers"]["background"] = background
    if background:
        raw["substrate"]["drive_version"] = "dev"
    e = Experiment.model_validate(raw)
    context = workers.WorkerContext(e, None, types.SimpleNamespace(topology=None), tmp_path,
                                    np.array([.2, .3]), g_inh=4.)
    messages = []
    workers.worker_main(context, [(0, 1), (0, 2)], types.SimpleNamespace(put=messages.append))
    assert [m["event"] for m in messages] == ["built", "result", "result", "finished"], messages


@pytest.mark.slow
def test_real_repeated_probe_interventions(tmp_path: Path) -> None:
    """Exercise real silencing, shifts, ablation, repeated seeds and analytical waits."""
    code="import sys;sys.path.insert(0,'tests');from test_orchestrator import _review_protocol;_review_protocol(sys.argv[1])"
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path)],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def _review_protocol(destination: str) -> None:
    """One real network, two 200 ms probes and a 2 h analytical gap; mV/Hz/seconds."""
    from flyonenomics.engine.brian_engine import BrianEngine
    from flyonenomics.registry import build_registry
    from flyonenomics.orchestrator.phases import build_topology
    from flyonenomics.orchestrator.workers import WorkerContext,execute_job,connectome_files
    from flyonenomics.orchestrator.seeds import brian_seed
    e=load_experiment(ROOT/'data/experiments/sugar-reflex.json');raw=e.model_dump(mode='json')
    raw['arms']=raw['arms'][:1];raw['seeds']=[1];raw['comparison']='ablation'
    arm=raw['arms'][0];arm['layers']={'dan_fast_synapses':'disconnect'}
    arm['genotype']['manipulations']=[{'type':'silence','population':'MN9'},{'type':'shift_threshold','population':'sugar_GRN_R','delta_mv':3}]
    probe=arm['protocol'][0];probe['duration_s']=0.2
    arm['protocol']=[{'type':'dose','drug':'methylphenidate','c_food_mm':0.5},
                     {'type':'repeat','n':2,'spacing_hours':2,'body':[probe]}]
    e=Experiment.model_validate(raw);reg=build_registry('783');e.resolve(reg)
    params=load_params();plan=build_topology(e,reg);seed_calls=[];disconnect_calls=[];chunks=[]
    sugar=reg.population('sugar_GRN_R').idx;mn9=reg.population('MN9').idx
    class CheckedEngine(BrianEngine):
        def seed(self,value: int) -> None:seed_calls.append(value);super().seed(value)
        def disconnect(self,idx: np.ndarray) -> None:disconnect_calls.append(idx.copy());super().disconnect(idx)
        def run_chunk(self,ms: float) -> ChunkResult:
            assert np.all(self.thresholds_mv()[sugar]==params.get('lif.v_th')+3)
            assert np.all(self.thresholds_mv()[mn9]==params.get('engine.silence_vth'))
            assert self.bank_active_flags()==[True]
            result=super().run_chunk(ms);assert result.counts[mn9].sum()==0
            chunks.append(result);return result
    engine=CheckedEngine();engine.build(connectome_files('783'),params,plan.topology)
    directory=Path(destination)
    context=WorkerContext(e,reg,plan,directory,None,{1:0.02,3:0.04})
    started=time.monotonic();result=execute_job(context,engine,params,0,1,lambda event:None)
    assert seed_calls==[brian_seed(e.seed,1,k) for k in (1,3)]
    assert len(disconnect_calls)==1
    np.testing.assert_array_equal(disconnect_calls[0],np.union1d(reg.population('DAN').idx,reg.population('CX_DAN').idx))
    assert len(chunks)==46
    assert [p['settle_s'] for p in result['offsets']]==[0.02,0.04]
    assert [p['t_brain_s'] for p in result['offsets']]==[0,7200.22]
    assert all(p['MN9']['spikes']==0 for p in result['metrics']['probes'].values())
    slow=pd.read_parquet(directory/f'arm-{arm["label"]}'/'seed-1'/'slow-state.parquet')
    np.testing.assert_allclose(slow.t_brain_s,[0,0.22,7200.22,7200.46])
    target=params.get('pk.kappa')*1000*0.5
    expected=target*-np.expm1(-params.get('pk.k_a')*slow.t_brain_s.to_numpy()/3600)
    np.testing.assert_allclose(slow['C_b_methylphenidate'],expected)
    # Time the wait alone: this is independent of the expensive neural simulation.
    state=SlowState(params);state.start_dose('methylphenidate',0.5)
    started=time.monotonic();state.advance(7200);assert time.monotonic()-started<1


def test_summary_reports_layer_off_and_repeat() -> None:
    """The metrics summary exposes both interpretive limits; flags and text, no arrays."""
    from flyonenomics.orchestrator.runner import aggregate
    e=load_experiment(ROOT/'data/experiments/sugar-reflex.json');raw=e.model_dump(mode='json')
    raw['layers']['dopamine_A']=False
    for arm in raw['arms']:
        arm['protocol']=[{'type':'repeat','n':2,'spacing_hours':0,'body':arm['protocol']}]
    summary=aggregate(Experiment.model_validate(raw),[])
    assert 'not the wild-type calibration state' in summary['layer_note']
    assert 'pharmacokinetic differences only' in summary['repeat_note']


def test_manifest_and_summary_include_active_free_parameters() -> None:
    """Bare inhibitory ratio is reported with background off; scalar units."""
    from flyonenomics.orchestrator.runner import _manifest,aggregate,pinned_drive_ratio
    e=load_experiment(ROOT/'data/experiments/sugar-reflex.json')
    assert not e.layers.background
    reg=types.SimpleNamespace(compartments=lambda:[],provenance_record={})
    manifest=_manifest(e,reg,[],'done',0,0,0,{})
    expected={key:load_params().get(key) for key in ('lif.w_syn','pk.kappa')}
    expected['lif.g_inh']=pinned_drive_ratio(e)
    assert aggregate(e,[])['free_parameters']==expected
    assert all(manifest['free_parameters'][key] == value for key, value in expected.items())
    assert manifest['free_parameters']['rec.formulation'] == load_params().get('rec.formulation')
    assert manifest['free_parameters']['receptor_map_version'] == e.substrate.receptor_map_version
    assert manifest['free_parameters']['dopamine_version'] == e.substrate.dopamine_version
    assert manifest['free_parameters']['drive_version'] == e.substrate.drive_version
    assert 'drive-dev.yaml' not in manifest['checksums']
    assert manifest['compatibility']=='development'
    assert set(manifest['stubs'])=={'IdentityBehaviour'}
    assert manifest['artefacts']['fano']=='not run'
    assert manifest['slow_state']=='phase1-drug-only'
    for record in read_json(ROOT/'data/provenance.json')['records']:
        if record.get('sha256'):
            assert manifest['checksums'][record['path'] or record['item']]==record['sha256']


def test_binding_lock_drift_detects_broken_class_checks() -> None:
    """A lock-check bypass in either noncanonical class must fail 0.9; scalar booleans."""
    code='''
from unittest.mock import patch
from flyonenomics.validation.level0 import test_0_9
from flyonenomics.validation.binding import is_compatible
assert test_0_9().measured['uv_lock_baseline']==[True,True,True]
for compatibility in ('matching-layers','run-bound'):
    def broken(entry,current,**kwargs):
        if entry.compatibility==compatibility:
            current=current.model_copy(update={'uv_lock_hash':entry.identity.uv_lock_hash})
        return is_compatible(entry,current,**kwargs)
    with patch('flyonenomics.validation.binding.is_compatible',side_effect=broken):
        assert test_0_9().outcome=='failed',compatibility
'''
    result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize("background", [False, True])
def test_drive_ratio_and_hash_follow_background(background: bool) -> None:
    from flyonenomics.orchestrator.runner import _manifest, pinned_drive_ratio
    from flyonenomics.validation.binding import sha256_file
    raw = load_experiment(ROOT / "data/experiments/sugar-reflex.json").model_dump(mode="json")
    raw["layers"]["background"] = background
    if background:
        raw["substrate"]["drive_version"] = "dev"
    e = Experiment.model_validate(raw)
    registry = types.SimpleNamespace(provenance_record={}, compartments=lambda: [])
    manifest = _manifest(e, registry, [], "done", 0, 0, 0, {})
    assert pinned_drive_ratio(e) == (4 if background else 1)
    assert manifest["free_parameters"]["lif.g_inh"] == (4 if background else 1)
    drive_keys = [key for key in manifest["checksums"] if Path(key).name.startswith("drive-")]
    assert drive_keys == (["drive-dev.yaml"] if background else [])
    if background:
        assert manifest["checksums"]["drive-dev.yaml"] == sha256_file(ROOT / "data/drive-dev.yaml")
        assert manifest["compatibility"] == "development"
        assert manifest["drive_calibration"]["qualified"] is False
        assert "map-level candidate" in manifest["drive_calibration"]["state"]


def test_v630_refused_before_registry_or_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import flyonenomics.registry as registry
    from flyonenomics.orchestrator.runner import run
    monkeypatch.setattr(registry, "build_registry", lambda *args: pytest.fail("registry built"))
    raw = load_experiment(ROOT / "data/experiments/sugar-reflex.json").model_dump(mode="json")
    raw["substrate"]["connectome_version"] = "630"
    with pytest.raises(ValueError, match="item 22"):
        run(Experiment.model_validate(raw), None, 1)


def test_invariance_replay_rejects_stale_or_partial_evidence(tmp_path, monkeypatch):
    from flyonenomics.orchestrator import verification
    from flyonenomics.store.results import atomic_json
    path = tmp_path / "evidence.json"
    monkeypatch.setattr(verification, "_invariance_identity", lambda: {"code_commit": "current", "hashes": {"model": "new"}})
    atomic_json(path, {"identity": {"code_commit": "old", "hashes": {"model": "old"}}, "measured": {}})
    with pytest.raises(ValueError, match="identity changed"):
        verification.replay_invariance_evidence(path)
    atomic_json(path, {"identity": {"code_commit": "current", "hashes": {"model": "new"}}, "measured": {"runs": []}})
    with pytest.raises(ValueError, match="eight cases"):
        verification.replay_invariance_evidence(path)


def test_invariance_reanalysis_never_relaxes_model_data_or_fixture_hashes():
    from flyonenomics.orchestrator.verification import compare_invariance_identity
    old = {"code_commit": "execution", "hashes": {"src/flyonenomics/engine/brian_engine.py": "engine",
        "data/dopamine-v0.1.yaml": "data", "tests/fixtures/experiments/invariance.json": "fixture",
        "src/flyonenomics/validation/level0.py": "old-driver"}}
    new = {"code_commit": "analysis", "hashes": {**old["hashes"],
        "src/flyonenomics/validation/level0.py": "new-driver"}}
    audit = compare_invariance_identity(old, new)
    assert audit["recorded_code_commit"] == "execution" and audit["analysis_code_commit"] == "analysis"
    assert list(audit["verification_driver_changes"]) == ["src/flyonenomics/validation/level0.py"]
    for key in ("src/flyonenomics/engine/brian_engine.py", "data/dopamine-v0.1.yaml", "tests/fixtures/experiments/invariance.json"):
        changed = {"code_commit": "analysis", "hashes": {**new["hashes"], key: "changed"}}
        with pytest.raises(ValueError, match="identity changed"):
            compare_invariance_identity(old, changed)


def test_wall_times_name_clocks_and_flag_one_percent_mismatch() -> None:
    """Clause 1 reads awake time; a >1 percent real/awake gap is flagged."""
    from flyonenomics.orchestrator.runner import _manifest, _wall_times
    e = load_experiment(ROOT / "data/experiments/sugar-reflex.json")
    reg = types.SimpleNamespace(provenance_record={}, compartments=lambda: [])
    equal = _wall_times(100.0, 100.0, 1.0, 0.1, 0.2)
    assert equal["total_s"] == equal["awake_s"] == 100.0
    assert equal["real_s"] == 100.0
    assert equal["awake_clock"] == "time.monotonic"
    assert equal["real_clock"] == "time.time"
    assert equal["mismatch_gt_1pct"] is False
    assert _wall_times(100.0, 101.0, 0, 0, 0)["mismatch_gt_1pct"] is False
    assert _wall_times(100.0, 102.0, 0, 0, 0)["mismatch_gt_1pct"] is True
    manifest = _manifest(e, reg, [], "done", 5.0, 1.0, 0.5, {}, wall_real_s=5.2)
    assert manifest["wall_times"]["awake_s"] == 5.0
    assert manifest["wall_times"]["real_s"] == 5.2
    assert manifest["wall_times"]["mismatch_gt_1pct"] is True
    # The 1 percent is of awake time, the time clause 1 reads.
    assert _wall_times(100.0, 101.005, 0, 0, 0)["mismatch_gt_1pct"] is True


def test_clause_1_reader_uses_awake_time_and_flags_mismatch_or_missing_real_time() -> None:
    """Item 71: clause 1 reads awake time; a >1 percent gap or no real time means re-execute."""
    from flyonenomics.orchestrator.runner import _wall_times, clause_1_wall
    budget = 5965.871
    clean = {"a": {"wall_times": _wall_times(5000.0, 5010.0, 0, 0, 0)},
             "b": {"wall_times": _wall_times(4700.0, 4700.5, 0, 0, 0)}}
    result = clause_1_wall(clean, budget)
    assert result["holds"] is True and result["rerun_for_clause_1"] == []
    assert [row["awake_s"] for row in result["runs"]] == [5000.0, 4700.0]
    slept = {"bbb00c2-run-1": {"wall_times": _wall_times(5844.634, 7524.774, 0, 0, 0)}, **clean}
    result = clause_1_wall(slept, budget)
    assert result["holds"] is False and result["rerun_for_clause_1"] == ["bbb00c2-run-1"]
    assert result["runs"][0]["within_budget"] is True
    legacy = {"old": {"wall_times": {"total_s": 4613.864}}}
    assert clause_1_wall(legacy, budget)["rerun_for_clause_1"] == ["old"]
    over = {"slow": {"wall_times": _wall_times(6000.0, 6000.0, 0, 0, 0)}}
    result = clause_1_wall(over, budget)
    assert result["holds"] is False and result["rerun_for_clause_1"] == []
    assert clause_1_wall({}, budget)["holds"] is False


def test_manifests_quote_canonical_matching_layers_and_run_bound_only() -> None:
    """Item 72: run manifests omit development entries (bbb00c2 behaviour)."""
    from flyonenomics.orchestrator.runner import _manifest
    e = load_experiment(ROOT / "data/experiments/open-loop-steering.json")
    reg = types.SimpleNamespace(provenance_record={}, compartments=lambda: [])
    manifest = _manifest(e, reg, [], "done", 0, 0, 0, {})
    status = {entry["test_id"]: entry for entry in read_json(ROOT / "validation/status.json")["results"]}
    quoted = [status[row["test_id"]]["compatibility"] for row in manifest["validation"]]
    assert quoted
    assert set(quoted) <= {"canonical", "matching-layers", "run-bound"}
    assert "development" not in quoted
    development_ids = {test_id for test_id, entry in status.items() if entry["compatibility"] == "development"}
    assert development_ids
    assert development_ids.isdisjoint({row["test_id"] for row in manifest["validation"]})
    # Every canonical, matching-layers and run-bound entry is quoted, in status order.
    assert [row["test_id"] for row in manifest["validation"]] == [
        test_id for test_id, entry in status.items() if entry["compatibility"] != "development"]


def test_invariance_fixture_uses_real_behaviour_and_empty_stubs() -> None:
    """A behaviour probe beside the sugar probes leaves the behaviour component unstubbed."""
    from flyonenomics.orchestrator.runner import _manifest
    from flyonenomics.orchestrator.verification import BEHAVIOUR_ASSAYS
    fixture = read_json(ROOT / "tests/fixtures/experiments/invariance.json")
    e = Experiment.model_validate(fixture["experiment"])
    assays = {p.assay for arm in e.arms for p in arm.protocol}
    assert "sugar_reflex" in assays
    assert assays & BEHAVIOUR_ASSAYS
    reg = types.SimpleNamespace(provenance_record={}, compartments=lambda: [])
    assert _manifest(e, reg, [], "done", 0, 0, 0, {})["stubs"] == []
