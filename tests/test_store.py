"""Atomic JSON, empty parquet schemas, settle round trip and crash reconciliation."""
import os
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from flyonenomics.schema import load_experiment
from flyonenomics.store import ResultsStore
from flyonenomics.store.results import atomic_json,read_json,read_settle,write_settle,table_schemas,write_table
from flyonenomics.types import SettleRecord

ROOT=Path(__file__).resolve().parents[1]


def test_atomic_json_failure_preserves_original(tmp_path: Path,monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed rename preserves the previous JSON; units none, one mapping."""
    path=tmp_path/'status.json';atomic_json(path,{'state':'running'})
    original=Path.replace
    def broken(source: Path,target: Path) -> Path:
        if target==path:
            assert source.parent==path.parent and read_json(source)['state']=='done'
            raise OSError('rename failed')
        return original(source,target)
    monkeypatch.setattr(Path,'replace',broken)
    with pytest.raises(OSError,match='rename'):atomic_json(path,{'state':'done'})
    assert read_json(path)=={'state':'running'} and list(tmp_path.iterdir())==[path]


def test_settle_overlap_roundtrip_and_default(tmp_path: Path) -> None:
    """Settle overlap remains int32 and engine ordered; seconds/µM/Hz, arrays (m,)."""
    record=SettleRecord(True,0.02,np.zeros(0),np.zeros(0),np.array([1.,2.]),200,upstream_extended_overlap_idx=np.array([0,2],dtype=np.int32))
    path=tmp_path/'settle.json';write_settle(path,record);got=read_settle(path)
    np.testing.assert_array_equal(got.upstream_extended_overlap_idx,record.upstream_extended_overlap_idx)
    assert got.upstream_extended_overlap_idx.dtype==np.int32
    raw=read_json(path);del raw['upstream_extended_overlap_idx'];atomic_json(path,raw)
    assert read_settle(path).upstream_extended_overlap_idx.shape==(0,)


def test_empty_schemas(tmp_path: Path) -> None:
    """Every empty table preserves full column names/dtypes; table shape (0,c)."""
    e=load_experiment(ROOT/'data/experiments/sugar-reflex.json')
    for name,schema in table_schemas(e.record,['MB','CX']).items():
        path=tmp_path/f'{name}.parquet';write_table(path,schema,[]);frame=pd.read_parquet(path)
        assert list(frame.columns)==list(schema) and len(frame)==0
        assert all(str(frame[k].dtype)==v for k,v in schema.items())


def test_index_queued_and_rebuild(tmp_path: Path) -> None:
    """Queued rows exist immediately; absent manifest/live PID controls reconciliation."""
    store=ResultsStore(tmp_path);e=load_experiment(ROOT/'data/experiments/sugar-reflex.json')
    directory=tmp_path/'run';directory.mkdir();atomic_json(directory/'experiment.json',e.model_dump(mode='json'))
    status={'state':'queued','pid':os.getpid()};atomic_json(directory/'status.json',status)
    store.index.upsert('run',e.model_dump(mode='json'),status)
    assert store.index.rows()[0]['state']=='queued'
    assert store.index.rebuild()[0]['state']=='incomplete'
    atomic_json(directory/'status.json',{'state':'running','pid':os.getpid()})
    assert store.index.rebuild()[0]['state']=='running'
    atomic_json(directory/'status.json',{'state':'running','pid':-1})
    assert store.index.rebuild()[0]['state']=='incomplete'
    with store.index._connect() as conn:assert conn.execute('PRAGMA journal_mode').fetchone()[0]=='wal'


@pytest.mark.parametrize('overlap',[[1.5],[True],[-1],[2**32],[2,1],[1,1]])
def test_settle_rejects_invalid_indices(tmp_path: Path, overlap: list) -> None:
    record=SettleRecord(True,0,np.zeros(0),np.zeros(0),np.zeros(0),0)
    path=tmp_path/'settle.json';write_settle(path,record)
    raw=read_json(path);raw['upstream_extended_overlap_idx']=overlap;atomic_json(path,raw)
    with pytest.raises(ValueError):read_settle(path)


def synthetic_run(tmp_path: Path) -> tuple[ResultsStore, Path]:
    """Write a complete 20 ms fixture without a network; ticks 0..199, one neuron."""
    store=ResultsStore(tmp_path);root=store.run_path('fixture');root.mkdir()
    raw=load_experiment(ROOT/'data/experiments/sugar-reflex.json').model_dump(mode='json')
    raw['arms']=raw['arms'][:1];raw['seeds']=[1]
    raw['arms'][0]['protocol']=raw['arms'][0]['protocol'][:1]
    raw['arms'][0]['protocol'][0]['duration_s']=0.02
    raw['record']['rate_bin_ms']=10;raw['record']['live']=False
    from flyonenomics.schema import Experiment
    e=Experiment.model_validate(raw)
    atomic_json(root/'experiment.json',e.model_dump(mode='json'))
    atomic_json(root/'status.json',{'state':'done'})
    atomic_json(root/'manifest.json',{'protocol_hash':e.protocol_hash(),'state':'done','compartments':[],'dt_ms':0.1})
    atomic_json(root/'metrics.json',{});(root/'log.txt').touch()
    directory=root/f'arm-{e.arms[0].label}'/'seed-1';directory.mkdir(parents=True)
    schemas=table_schemas(e.record,[])
    for name,schema in schemas.items():
        file=directory/(f'{name}.parquet' if name in ('index','slow-state') else f'probe-0-{name}.parquet')
        write_table(file,schema,[])
    write_table(directory/'index.parquet',schemas['index'],[{'idx':0,'root_id':100}])
    write_table(directory/'probe-0-popcount-1ms.parquet',schemas['popcount-1ms'],{'tick':np.arange(20)*10,'count':np.zeros(20)})
    write_table(directory/'probe-0-rates.parquet',schemas['rates'],[{'tick':t,'t_ms':t*0.1,**dict.fromkeys(e.record.rates,0.)} for t in (0,100)])
    write_settle(directory/'probe-0-settle.json',SettleRecord(True,0,np.zeros(0),np.zeros(0),np.zeros(2),0))
    atomic_json(directory/'metrics.json',{'probes':{'0':{'duration_s':0.02}}})
    assert store.validate_run('fixture')==[]
    return store,directory


@pytest.mark.parametrize('damage',['missing-bin','empty-popcount','missing-rate','outside-tick','invalid-idx','short-probe'])
def test_validate_run_rejects_corrupt_recordings(tmp_path: Path, damage: str) -> None:
    store,directory=synthetic_run(tmp_path)
    if damage in ('missing-bin','empty-popcount','missing-rate'):
        suffix='rates' if damage=='missing-rate' else 'popcount-1ms'
        path=directory/f'probe-0-{suffix}.parquet';frame=pd.read_parquet(path)
        frame.iloc[:0 if damage=='empty-popcount' else -1].to_parquet(path,index=False)
    elif damage in ('outside-tick','invalid-idx'):
        schema={'idx':'int32','tick':'int64','t_ms':'float32'}
        tick=200 if damage=='outside-tick' else 0
        write_table(directory/'probe-0-spikes.parquet',schema,[{'idx':2 if damage=='invalid-idx' else 0,'tick':tick,'t_ms':tick*0.1}])
    else:
        atomic_json(directory/'metrics.json',{'probes':{'0':{'duration_s':0.01}}})
    assert store.validate_run('fixture'),damage
