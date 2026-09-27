"""WP19 constructed boundary and fail-closed qualification tables."""
from copy import deepcopy
from pathlib import Path
import json

import numpy as np
import pytest

from flyonenomics.validation import levelrest as rest


def rows(n=3):
    return [dict(seed=s, settled=True, F=2.6, b=.01, stability_ratio=1., central=1., DAN=1., KC=1., edge_ratio=1., ignited=False) for s in range(1,n+1)]


def test_reflex_boundaries():
    assert rest.reflex([50]*10)['outcome']=='failed'
    assert rest.reflex([40]+[52]*9)['outcome']=='passed'
    assert rest.reflex([39]+[60]*9)['outcome']=='failed'
    with pytest.raises(ValueError): rest.reflex([60]*9)
    with pytest.raises(ValueError): rest.reflex([float('nan')]*10)


def test_ff_retention_and_fixture_contract(tmp_path,monkeypatch):
    bare={m:[80]*10 for m in ('upstream','extended')}
    candidate={m:[40]*10 for m in bare}
    assert rest.feedforward(bare,candidate)['outcome']=='passed'
    candidate['extended'][0]=39
    assert rest.feedforward(bare,candidate)['outcome']=='failed'
    root=Path(__file__).resolve().parents[1]/'data/experiments/p2'
    rest.validate_ff_fixtures(root/'ff-bare.json', root/'ff-candidate.json')
    with pytest.raises(ValueError): rest.validate_ff_fixtures(root/'ff-bare.json',tmp_path/'ff-candidate.json')
    target=tmp_path/'data/experiments/p2';target.mkdir(parents=True)
    for file in ('ff-bare.json','ff-candidate.json'):
        (target/file).write_text((root/file).read_text())
    doc=json.loads((target/'ff-candidate.json').read_text());doc['seeds']=[1]
    (target/'ff-candidate.json').write_text(json.dumps(doc))
    monkeypatch.setattr(rest,'ROOT',tmp_path)
    with pytest.raises(ValueError): rest.validate_ff_fixtures(target/'ff-bare.json',target/'ff-candidate.json')


def test_screen_means_and_strict_edges():
    r=rows();r[0]['DAN']=0;r[1]['DAN']=2
    assert rest.screen(r)['outcome']=='passed' # group bands are seed means
    for key,value in [('F',3),('b',.05),('stability_ratio',2.01),('settled',False)]:
        bad=deepcopy(r);bad[0][key]=value
        assert rest.screen(bad)['outcome']=='failed'
    r[0]['F']=None
    with pytest.raises(ValueError): rest.screen(r)
    with pytest.raises(ValueError): rest.screen(rows()[:2])


def test_rate_safety_long_margin_jitter():
    assert rest.rate_safety([0]*100)['outcome']=='failed'
    assert rest.rate_safety([0]*100,stimulated=True)['outcome']=='passed'
    assert rest.rate_safety([1]*99+[51])['outcome']=='failed'
    r=rows(10);assert rest.long_window(r)['outcome']=='passed'
    r[9]['ignited']=True;assert rest.long_window(r)['outcome']=='failed'
    assert rest.margin(rows(),rows(),rows())['outcome']=='passed'
    plus=rows();plus[0]['central']=3;assert rest.margin(rows(),plus,rows())['outcome']=='failed'
    base={'difference_hz':60,'groups':{'central':1,'silent':0}}
    jit=[dict(base,stream=i,F=2.6,settled=True) for i in range(5)]
    assert rest.jitter(base,jit)['outcome']=='passed'
    jit[0]=dict(jit[0],difference_hz=75)
    assert rest.jitter(base,jit)['outcome']=='failed'


def test_release_algebra_and_phase1_separation():
    from flyonenomics.neuromod.calibration import release_constants,rest_release_constants
    from flyonenomics.types import load_params
    p=load_params(rest.ROOT/'data/params-v0.2.yaml')
    assert rest.algebra()['outcome']=='passed'
    a,s,m=rest_release_constants(np.array([0.,.49,.5,10.]),p)
    assert m==['source','source','derived','derived']
    assert a[0]==a[1]==a[2] and s[0]>s[1]>s[2]==s[3]==0
    old,_=release_constants(np.array([0.]),p)
    assert old[0]==p.get('da.alpha_max') and a[0]!=old[0]


def fixture_documents(path):
    """Yield each single-experiment document in a fixture file; units none.

    Most `data/experiments/p2/*.json` files are one experiment. WP20's
    `buridan-controls.json` is a mapping of three named experiments, which
    cannot share one paired Experiment because their probes differ.
    """
    document = json.loads(path.read_text())
    if 'schema_version' in document:
        yield document
    else:
        yield from document.values()


def test_owned_fixtures_validate():
    from flyonenomics.schema.experiment import Experiment
    for p in (rest.ROOT/'data/experiments/p2').glob('*.json'):
        for document in fixture_documents(p):
            Experiment.model_validate(document)


def test_bitter_is_recorded_and_retains_failed_comparison():
    result=rest.bitter_suppression([80,80],[39,40])
    assert result['outcome']=='recorded' and result['below_half'] is False


def test_decision_22_owned_fixtures_are_schema_13_only():
    """SPEC-P2 decision 22: a v0.2 pin reaches the rest substrate only through 1.3."""
    from flyonenomics.schema.experiment import Experiment
    for p in sorted((rest.ROOT/'data/experiments/p2').glob('*.json')):
        for loaded in fixture_documents(p):
            doc=deepcopy(loaded)
            assert doc['schema_version']=='1.3', p.name
            pins=doc['substrate']
            if 'v0.2' in (pins.get('params_version'),pins.get('drive_version')):
                doc['schema_version']='1.2'
                for key in ('populations_version','transmitters_version','visual_version','apply_scales_without_background'):
                    pins.pop(key,None);doc.pop(key,None)
                with pytest.raises(ValueError,match='schema 1.3 is the only route'):
                    Experiment.model_validate(doc)


def test_decision_24_entries_declare_every_data_dependency(tmp_path,monkeypatch):
    """SPEC-P2 decision 24: any data_dependencies name is a declared data/ input."""
    from flyonenomics.drive import rest_calibration as rc
    from flyonenomics.types import LayerFlags
    from flyonenomics.validation.binding import build_identity, is_compatible
    for test_id in rest.IDS:
        e=rest.entry(test_id)
        assert {f'data/{n}' for n in e.data_dependencies} <= set(e.declared_inputs), test_id
    alg=rest.entry('3.1r-alg')
    assert alg.data_dependencies==[] and alg.declared_inputs==['data/params-v0.2.yaml']
    assert is_compatible(alg,alg.identity,current_fixture_hash=alg.identity.fixture_hash)==(True,'valid')
    monkeypatch.setattr(rc,'RECORDS',tmp_path)
    inputs=['data/params-v0.2.yaml','data/experiments/p2/rest-short.json']
    ident=build_identity(rest.ROOT,connectome_version='783',layers=LayerFlags(background=True),assay='spontaneous',
                         fixture='data/experiments/p2/rest-short.json',declared_inputs=inputs)
    rc.publish_entry('2.2r',{'outcome':'passed'},ident,'rest-short.json',inputs=inputs)
    stored=json.loads((tmp_path/'entry-2.2r.json').read_text())
    assert stored['data_dependencies']==[] and stored['declared_inputs']==inputs
