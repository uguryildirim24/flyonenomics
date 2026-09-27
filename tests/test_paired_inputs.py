"""d-0025: exact keyed injection and draw-before-gate background regressions."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from flyonenomics.drive.paired_inputs import SEGMENTS, STIMULI, segment_events, trial_events


def test_clocked_poisson_events_have_exact_bernoulli_law_and_no_global_rng_use():
    rates = np.array([0., 250., 1000.])
    np.random.seed(991)
    before = np.random.get_state()
    ticks, cells = segment_events(20260912, 201, 'test', 'AB', rates, 10000, .1)
    after = np.random.get_state()
    assert before[0] == after[0] and before[2:] == after[2:]
    np.testing.assert_array_equal(before[1], after[1])
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        20260912, spawn_key=(25, 201, SEGMENTS['test'], STIMULI['AB']))))
    expected_tick, expected_cell = np.nonzero(rng.random((10000, 3)) < rates*.0001)
    np.testing.assert_array_equal(ticks, expected_tick)
    np.testing.assert_array_equal(cells, expected_cell)
    assert ticks.dtype == np.int64 and cells.dtype == np.int32
    assert not np.any(cells == 0) and len(ticks) > 0
    short = segment_events(20260912, 201, 'test', 'AB', rates, 4120, .1)
    np.testing.assert_array_equal(short[0], ticks[ticks < 4120])
    np.testing.assert_array_equal(short[1], cells[ticks < 4120])
    other = segment_events(20260912, 202, 'test', 'AB', rates, 10000, .1)
    assert not np.array_equal(other[0], ticks)
    with pytest.raises(ValueError, match='probabilities'):
        segment_events(1, 2, 'test', 'AB', np.array([10001.]), 2, .1)


def test_final_event_arrays_ignore_prefix_and_keep_segment_streams_separate():
    timing = dict(settle_s=.02, prefix_s=.04, gap_s=.02, test_s=.12)
    patterns = {'off':np.zeros(3), 'A':np.array([400.,0,0]),
                'B':np.array([0,400.,0]), 'AB':np.array([400.,400.,0])}
    events = [trial_events(20260912, 201, '5b', (prefix,'AB'), patterns, timing, .1)
              for prefix in ('off','A','B')]
    final = [np.column_stack((t[t>=800], i[t>=800])) for t,i in events]
    assert len(final[0]) > 0
    for other in final[1:]: np.testing.assert_array_equal(final[0], other)
    assert len(events[0][0]) < len(events[1][0])
    assert not np.array_equal(events[1][1], events[2][1])


# A fresh interpreter starts native RNG buffers empty, just like each worker.
BACKGROUND_CHECK = r'''
import sys,json,hashlib
import numpy as np
import brian2 as b
from flyonenomics.drive.paired_inputs import state_independent_background
sys.path.insert(0, sys.argv[2])
import adhd_study as study
b.prefs.codegen.target='cython'
g=b.NeuronGroup(8, 'dg/dt=-g/(5*ms):volt (unless refractory)\nv:1\nw_bg_i:volt\nstim:1 (shared)',
                threshold='v>0.5', reset='v=0', refractory=1*b.ms, method='linear')
g.w_bg_i=1*b.mV
set_v=g.run_regularly('v=stim', when='start')
if sys.argv[1]=='new':
    bg=state_independent_background(g,100,10.)
    assert g.variables['study_bg_draw'].conditional_write is None
    assert g.variables['g'].conditional_write is g.variables['not_refractory']
    names=['g','study_bg_draw','not_refractory']
else:
    bg=b.PoissonInput(g,'g',100,10*b.Hz,'w_bg_i')
    names=['g','not_refractory']
before=b.StateMonitor(g,'g',record=True,when='before_synapses')
after=b.StateMonitor(g,names,record=True,when='after_synapses')
spikes=b.SpikeMonitor(g)
net=b.Network(g,bg,before,after,spikes)
net.store('initial')
records=[]
for drive in (0,1):
    net.restore('initial',restore_random_state=True)
    b.seed(101);g.stim=drive
    start=study.rng_hash()
    net.run(20*b.ms)
    end=study.rng_hash()
    old=np.asarray(before.g/b.volt);new=np.asarray(after.g/b.volt)
    active=np.asarray(after.not_refractory,dtype=bool)
    np.testing.assert_array_equal(new[~active],old[~active])
    record={'initial':start,'final':end,'g_sha256':hashlib.sha256(new.tobytes()).hexdigest(),
            'spikes':int(spikes.num_spikes)}
    if sys.argv[1]=='new':
        draw=np.asarray(after.study_bg_draw)
        np.testing.assert_allclose(new,old+np.where(active,draw*.001,0),rtol=1e-14,atol=1e-18)
        if drive: assert np.any(draw[~active]>0)  # discarded draws really occur
        record['draw_sha256']=hashlib.sha256(draw.tobytes()).hexdigest()
    records.append(record)
assert records[0]['spikes']==0 and records[1]['spikes']>0
print(json.dumps(records))
'''


def test_background_draws_all_targets_then_keeps_existing_refractory_gating():
    scripts = str(Path(__file__).resolve().parents[1]/'scripts')
    records = []
    for mode in ('old','new'):
        run = subprocess.run([sys.executable, '-c', BACKGROUND_CHECK, mode, scripts],
                             check=True, capture_output=True, text=True)
        records.append(json.loads(run.stdout.splitlines()[-1]))
    old, new = records
    # Reproduce the original named defect, then check the full mechanism repair.
    assert old[0]['final'] != old[1]['final']
    assert new[0]['initial'] == new[1]['initial']
    assert new[0]['final'] == new[1]['final']
    assert new[0]['draw_sha256'] == new[1]['draw_sha256']
    # With no refractory skipping, the exact original sampler/dynamics survive.
    assert old[0]['g_sha256'] == new[0]['g_sha256']
    assert old[0]['final'] == new[0]['final']
