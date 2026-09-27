"""Live line schema, independent sampling and immediate flush (SPEC-P2 section 7, live_version 2)."""
import json
from pathlib import Path
import numpy as np
import pytest
from flyonenomics.orchestrator.live import LiveStream, open_loop_block
from flyonenomics.orchestrator.seeds import stream,LIVE
from flyonenomics.schema.experiment import OpenLoopBlock, OpenLoopParams, SpontaneousParams
from flyonenomics.types import load_params,SpikeTable


def test_live_schema_sample_flush_and_off(tmp_path: Path) -> None:
    """Version 2 windows carry relative ticks/counts, all_count, window_ms, sizes, block and stimulus."""
    params=load_params();path=tmp_path/'live.ndjson';start=500
    live=LiveStream(path,stream(1,1,0,LIVE),params,{'p':np.array([0,1],dtype=np.int32)},start,0.1)
    events=SpikeTable(np.zeros(300,dtype=np.int32),np.arange(300,dtype=np.int64)+start)
    for i in range(1,11):
        emitted=live.maybe_emit(np.array([1,2],dtype=np.int32),start+i*100,lambda tick:events,np.zeros(0),{'x':0.0})
        assert emitted==(i==10)
    line=json.loads(path.read_text())  # Before close: flush is observable.
    assert set(line)=={'live_version','tick','t_ms','window_ms','counts','all_count','sizes','block','stimulus','spikes','da','arena'}
    assert line['live_version']==2
    assert line['tick']==1000 and line['t_ms']==100 and line['window_ms']==100.0
    assert line['counts']=={'p':30} and line['all_count']==30 and line['sizes']=={'p':2}
    assert line['block'] is None and line['stimulus'] is None
    assert len(line['spikes'])==params.get('live.spike_sample')
    assert all(0<=tick<300 for idx,tick in line['spikes'])
    live.close()
    assert len(path.read_text().splitlines())==1  # No pending window: close adds nothing.
    off=LiveStream(tmp_path/'off.ndjson',stream(1,1,0,LIVE),params,{},0,0.1,False)
    assert not off.maybe_emit(np.ones(2,dtype=np.int32),1000,lambda tick:events,np.zeros(0),{})
    off.close();assert (tmp_path/'off.ndjson').read_text()==''


def test_all_count_covers_overlap_and_unrecorded_neurons(tmp_path: Path) -> None:
    """all_count sums the full (n,) array once; overlapping recorded populations double-count, unrecorded neurons count only there."""
    params=load_params();path=tmp_path/'live.ndjson';start=0
    populations={'a':np.array([0,1],dtype=np.int32),'b':np.array([1,2,3],dtype=np.int32)}
    live=LiveStream(path,stream(1,1,0,LIVE),params,populations,start,0.1)
    events=SpikeTable(np.zeros(0,dtype=np.int32),np.zeros(0,dtype=np.int64))
    chunk=np.array([1,2,4,8,16],dtype=np.int32)  # Neuron 4 sits in no recorded population; neuron 1 sits in both.
    for i in range(1,11):
        live.maybe_emit(chunk,start+i*100,lambda tick:events,np.zeros(0),{})
    live.close()
    line=json.loads(path.read_text())
    assert line['counts']=={'a':30,'b':140}  # Overlap double-counts neuron 1.
    assert line['all_count']==310  # Every neuron exactly once, including unrecorded neuron 4.
    assert line['all_count']!=sum(line['counts'].values())
    assert line['sizes']=={'a':2,'b':3}  # Unequal sizes recorded per population.


def test_final_partial_window_flushed_at_close(tmp_path: Path) -> None:
    """A short final window is written at close with its actual window_ms, not dropped or padded."""
    params=load_params();path=tmp_path/'live.ndjson';start=500
    live=LiveStream(path,stream(1,1,0,LIVE),params,{'p':np.array([0,1],dtype=np.int32)},start,0.1)
    events=SpikeTable(np.zeros(0,dtype=np.int32),np.zeros(0,dtype=np.int64))
    for i in range(1,16):  # Ten 10 ms chunks fill one 100 ms window; five more leave a 50 ms tail.
        live.maybe_emit(np.array([1,2],dtype=np.int32),start+i*100,lambda tick:events,np.zeros(0),{})
    live.close()
    lines=[json.loads(raw) for raw in path.read_text().splitlines()]
    assert len(lines)==2
    assert lines[0]['window_ms']==100.0 and lines[0]['all_count']==30
    assert lines[1]['window_ms']==50.0 and lines[1]['all_count']==15 and lines[1]['counts']=={'p':15}
    assert lines[1]['tick']==1500 and lines[1]['t_ms']==150.0


def test_block_and_stimulus_pass_through(tmp_path: Path) -> None:
    """The runner's open-loop block index and stimulus label land on the line, null by default."""
    params=load_params();path=tmp_path/'live.ndjson';start=0
    live=LiveStream(path,stream(1,1,0,LIVE),params,{'p':np.array([0],dtype=np.int32)},start,0.1)
    events=SpikeTable(np.zeros(0,dtype=np.int32),np.zeros(0,dtype=np.int64))
    for i in range(1,11):
        live.maybe_emit(np.array([1],dtype=np.int32),start+i*100,lambda tick:events,np.zeros(0),{},block=2,stimulus='stripe')
    live.close()
    line=json.loads(path.read_text())
    assert line['block']==2 and line['stimulus']=='stripe'


def test_open_loop_block_matches_arena_rule() -> None:
    """open_loop_block walks blocks by transition_s + dwell_s; azimuths step one period; other assays null."""
    params=load_params()
    blocks=[OpenLoopBlock(stimulus='ambient',transition_s=1.0,dwell_s=2.0),
            OpenLoopBlock(stimulus='stripe',azimuth_deg=45.0,transition_s=1.0,dwell_s=2.0),
            OpenLoopBlock(stimulus='dark',transition_s=0.5,dwell_s=1.5)]
    probe=OpenLoopParams(blocks=blocks)
    assert open_loop_block(probe,0.0,params)==(0,'ambient')
    assert open_loop_block(probe,2.99,params)==(0,'ambient')
    assert open_loop_block(probe,3.0,params)==(1,'stripe')  # Boundary starts the next block.
    assert open_loop_block(probe,5.5,params)==(1,'stripe')
    assert open_loop_block(probe,6.0,params)==(2,'dark')
    assert open_loop_block(probe,100.0,params)==(2,'dark')  # Past the end: the last block holds.
    period=params.get('openloop.transition_s')+params.get('openloop.dwell_s')
    azimuths=OpenLoopParams(azimuths=[0.0,90.0,180.0])
    assert open_loop_block(azimuths,0.0,params)==(0,'stripe')
    assert open_loop_block(azimuths,period*2+0.1,params)==(2,'stripe')
    assert open_loop_block(azimuths,period*10,params)==(2,'stripe')  # Clamped to the last azimuth.
    assert open_loop_block(SpontaneousParams(),0.0,params)==(None,None)
    default=params.get('openloop.azimuths')  # The arena falls back to openloop.azimuths for {} and [].
    for omitted in (OpenLoopParams(),OpenLoopParams(azimuths=[])):
        assert open_loop_block(omitted,0.0,params)==(0,'stripe')
        assert open_loop_block(omitted,period*100,params)==(len(default)-1,'stripe')


def test_close_after_failure_writes_no_window_and_closes(tmp_path) -> None:
    """A failed probe closes the file without a final window, even if a flush would raise."""
    def broken_spikes(_start):
        raise RuntimeError("engine gone")
    live=LiveStream(tmp_path/'l.ndjson',np.random.default_rng(0),load_params(),{'a':np.array([0])},0,0.1)
    live.maybe_emit(np.array([1,0]),10,broken_spikes,np.zeros(0),{})
    live.close(flush=False)
    assert live.handle.closed and (tmp_path/'l.ndjson').read_text()==''
    live=LiveStream(tmp_path/'m.ndjson',np.random.default_rng(0),load_params(),{'a':np.array([0])},0,0.1)
    live.maybe_emit(np.array([1,0]),10,broken_spikes,np.zeros(0),{})
    with pytest.raises(RuntimeError):
        live.close()
    assert live.handle.closed
