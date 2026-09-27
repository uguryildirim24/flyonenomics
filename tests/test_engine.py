"""Engine wrapper tests (WP1).

Units and array shapes follow the engine docstrings. Full-connectome
fixtures run short probes only; long brain-second executions live in
the validation suites, which pytest does not execute.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
ENGINE_GROUP = os.environ.get("WP1_ENGINE_TEST_GROUP")
if ENGINE_GROUP:
    from brian2 import mV

    from flyonenomics.types import ConnectomeFiles, load_params
    from flyonenomics.engine import BrianEngine, InputTopology, UpstreamBank
    from flyonenomics.engine.brian_engine import cache_dir

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "engine"


@pytest.fixture(autouse=True)
def isolate_engine_group(request: pytest.FixtureRequest) -> None:
    """Run each engine size in its own pytest process. Units: none. Shapes: none."""
    name = request.node.name
    if ENGINE_GROUP is None:
        if not name.startswith("test_engine_group_process"):
            pytest.skip("engine test runs in an isolated child process")
        return
    if name.startswith("test_engine_group_process"):
        pytest.skip("only the parent launches engine groups")
    if name == "test_optional_apis_on_bare_path" and ENGINE_GROUP != "tiny":
        pytest.skip("bare-path check runs with the tiny engine group")


@pytest.mark.parametrize("group", ("630", "783", "tiny"))
@pytest.mark.slow
def test_engine_group_process(group: str) -> None:
    """Execute one engine size in a child pytest process.

    Units: none. Shapes: one process per connectome version or tiny fixture.
    """
    env = os.environ.copy()
    env["WP1_ENGINE_TEST_GROUP"] = group
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_engine.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def load_fixture(name: str) -> dict:
    """Load one canonical engine fixture. Units: per file. Shapes: mapping."""
    return json.loads((FIX / name).read_text())


def grn() -> dict:
    """Load the sugar, bitter, and MN9 root lists. Units: none. Shapes: mapping."""
    return json.loads((FIX / "grn.json").read_text())


def root_lookup(version: str) -> dict[int, int]:
    """Map root ID to engine index for one connectome version.

    Units: none. Shapes: mapping of int to int.
    """
    name = (
        "2023_03_23_completeness_630_final.csv"
        if version == "630"
        else "Completeness_783.csv"
    )
    comp = pd.read_csv(cache_dir() / "Drosophila_brain_model" / name, index_col=0)
    ids = comp.index.to_numpy()
    return {int(v): i for i, v in enumerate(ids)}


def connectome(version: str) -> ConnectomeFiles:
    """Return the ConnectomeFiles of one version. Units: none. Shapes: paths only."""
    base = cache_dir() / "Drosophila_brain_model"
    if version == "630":
        return ConnectomeFiles(
            completeness=base / "2023_03_23_completeness_630_final.csv",
            connectivity=base / "2023_03_23_connectivity_630_final.parquet",
            version="630",
        )
    return ConnectomeFiles(
        completeness=base / "Completeness_783.csv",
        connectivity=base / "Connectivity_783.parquet",
        version="783",
    )


def tiny_connectome() -> ConnectomeFiles:
    """Return the tiny synthetic connectome. Units: none. Shapes: paths only."""
    return ConnectomeFiles(
        completeness=FIX / "tiny_completeness.csv",
        connectivity=FIX / "tiny_connectivity.parquet",
        version="630",
    )


@pytest.fixture(scope="session")
def eng630() -> BrianEngine:
    """Session engine on v630 with a sugar bank and small extra sets.

    Units: Hz for bank rates. Shapes: bank (21,), extended (8,),
    spikelist (4,), trace (2,).
    """
    if ENGINE_GROUP != "630":
        pytest.skip("v630 engine runs in its own process")
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in grn()["sugar_roots"]], dtype=np.int32)
    engine = BrianEngine()
    engine.build(
        connectome("630"),
        load_params(),
        InputTopology(
            upstream_banks=[UpstreamBank(idx=sugar, rate_hz=150.0)],
            extended_idx=np.arange(8, dtype=np.int32),
            spikelist_idx=np.array([10, 11, 12, 13], dtype=np.int32),
            trace_idx=np.array([0, 1], dtype=np.int32),
            background=True,
        ),
    )
    return engine


@pytest.fixture(scope="session")
def eng783() -> BrianEngine:
    """Session engine on v783 with index-based inputs. Units: Hz. Shapes:
    bank (21,), extended (8,), spikelist (4,), trace (2,)."""
    if ENGINE_GROUP != "783":
        pytest.skip("v783 engine runs in its own process")
    engine = BrianEngine()
    engine.build(
        connectome("783"),
        load_params(),
        InputTopology(
            upstream_banks=[
                UpstreamBank(idx=np.arange(21, dtype=np.int32), rate_hz=150.0)
            ],
            extended_idx=np.arange(8, dtype=np.int32),
            spikelist_idx=np.array([10, 11, 12, 13], dtype=np.int32),
            trace_idx=np.array([0, 1], dtype=np.int32),
            background=True,
        ),
    )
    return engine


@pytest.fixture(scope="session")
def tiny_eng() -> BrianEngine:
    """Session tiny engine with every input object. Units: Hz. Shapes:
    bank (1,), extended (2,), spikelist (1,), trace (2,)."""
    if ENGINE_GROUP != "tiny":
        pytest.skip("tiny engine runs in its own process")
    engine = BrianEngine()
    topology = InputTopology(
        upstream_banks=[UpstreamBank(np.array([1], dtype=np.int32), 150.0)],
        extended_idx=np.array([1, 2], dtype=np.int32),
        spikelist_idx=np.array([0], dtype=np.int32),
        trace_idx=np.array([1, 0], dtype=np.int32),
        background=True,
    )
    engine.build(
        tiny_connectome(),
        load_params(),
        topology,
    )
    topology.extended_idx[:] = 0
    topology.spikelist_idx[:] = 1
    topology.trace_idx[:] = 0
    np.testing.assert_array_equal(engine._ext_idx, [1, 2])
    np.testing.assert_array_equal(engine._gen_idx, [0])
    np.testing.assert_array_equal(engine._trace_idx, [1, 0])
    return engine


def reset_inputs(engine: BrianEngine, n_extended: int) -> None:
    """Restore the snapshot and silence every input source. Units: Hz and
    mV. Shapes: rate array with shape (n_extended,). Each test sets its
    own inputs after this call so fixture sharing stays order-free."""
    engine.restore("initial")
    for bank in range(len(engine._bank_idx)):
        engine.set_upstream_active(bank, False)
    engine.compose_refractory()
    if n_extended:
        engine.set_input_rates(np.zeros(n_extended))
    engine.set_background(np.zeros(engine.n))
    engine.set_threshold(np.full(engine.n, float(load_params().get("lif.v_th"))))
    engine.set_gain(np.ones(engine.n))


def test_bank_order_matches_source(eng630: BrianEngine) -> None:
    """Bank indices keep the notebook declaration order, never sorted.

    Units: none. Shapes: bank index array with shape (21,).
    """
    order = eng630._bank_idx[0]
    assert order.shape == (21,)
    assert not bool(np.all(order[:-1] <= order[1:])), "bank order must not be sorted"
    lookup = root_lookup("630")
    expected = np.array([lookup[r] for r in grn()["sugar_roots"]], dtype=np.int32)
    np.testing.assert_array_equal(order, expected)


def test_seed_determinism(eng630: BrianEngine) -> None:
    """Restore plus seed gives identical short streams. Units: engine
    ticks. Shapes: spike tables of equal length."""
    eng630.restore("initial")
    eng630.set_upstream_active(0, True)
    eng630.compose_refractory()
    eng630.set_input_rates(np.zeros(8))
    eng630.set_background(np.zeros(eng630.n))
    eng630.seed(7)
    for _ in range(10):
        eng630.run_chunk(10.0)
    first = eng630.spikes(0)
    eng630.restore("initial")
    eng630.set_upstream_active(0, True)
    eng630.compose_refractory()
    eng630.set_input_rates(np.zeros(8))
    eng630.set_background(np.zeros(eng630.n))
    eng630.seed(7)
    for _ in range(10):
        eng630.run_chunk(10.0)
    second = eng630.spikes(0)
    np.testing.assert_array_equal(first.idx, second.idx)
    np.testing.assert_array_equal(first.tick, second.tick)


def test_bank_activity_survives_restore(eng630: BrianEngine) -> None:
    """Bank activity persists across a restore. Units: none. Shapes: one
    flag per bank. Restore never touches activity: the engine keeps the
    activity it was last told and reapplies it to the objects."""
    eng630.restore("initial")
    eng630.set_upstream_active(0, True)
    eng630.restore("initial")
    assert eng630.bank_active_flags() == [True]
    assert all(poi.active for poi in eng630._bank_pois[0])
    eng630.compose_refractory()
    targets = eng630._bank_idx[0]
    assert bool(np.all(eng630.refractory_ms()[targets] == 0.0))


def test_threshold_gain_roundtrip(eng630: BrianEngine) -> None:
    """Written thresholds and gains read back exactly. Units: mV and
    dimensionless. Shapes: arrays with shape (n,)."""
    eng630.restore("initial")
    base = np.full(eng630.n, float(load_params().get("lif.v_th")))
    base[100:200] += 3.0
    eng630.set_threshold(base)
    np.testing.assert_array_equal(eng630.thresholds_mv(), base)
    gain = np.ones(eng630.n)
    gain[300:400] = 1.5
    eng630.set_gain(gain)
    np.testing.assert_array_equal(eng630.gains(), gain)
    np.testing.assert_array_equal(eng630.thresholds_mv(), base)


def test_compose_refractory(eng630: BrianEngine) -> None:
    """Inactive banks leave rfc at base; active banks zero their targets.

    Units: ms. Shapes: array with shape (n,).
    """
    params = load_params()
    base_ms = float(params.get("lif.t_rfc"))
    eng630.restore("initial")
    eng630.set_upstream_active(0, False)
    eng630.compose_refractory()
    np.testing.assert_array_equal(
        eng630.refractory_ms(), np.full(eng630.n, base_ms)
    )
    eng630.set_upstream_active(0, True)
    eng630.compose_refractory()
    rfc = eng630.refractory_ms()
    targets = eng630._bank_idx[0]
    assert bool(np.all(rfc[targets] == 0.0))
    mask = np.ones(eng630.n, dtype=bool)
    mask[targets] = False
    assert bool(np.all(rfc[mask] == base_ms))


def test_refractory_base_survives_store_restore(tiny_eng: BrianEngine) -> None:
    """Restoring a snapshot also restores the refractory composition base.

    Units: ms. Shapes: full refractory array with shape (n,).
    """
    base_ms = float(load_params().get("lif.t_rfc"))
    tiny_eng.restore("initial")
    tiny_eng.set_upstream_active(0, False)
    tiny_eng.set_refractory(np.array([1], dtype=np.int32), np.array([5.0]))
    tiny_eng.store("refractory-five")
    tiny_eng.set_refractory(np.array([1], dtype=np.int32), np.array([7.0]))
    tiny_eng.restore("refractory-five")
    tiny_eng.compose_refractory()
    assert tiny_eng.refractory_ms()[1] == 5.0
    tiny_eng.restore("initial")
    tiny_eng.compose_refractory()
    assert tiny_eng.refractory_ms()[1] == base_ms


def test_snapshot_files_leave_with_their_engine() -> None:
    """A collected engine deletes its snapshot pickle and weight sidecar. Units: none."""
    import gc

    if ENGINE_GROUP != "tiny":
        pytest.skip("tiny engine runs in its own process")
    engine = BrianEngine()
    engine.build(tiny_connectome(), load_params(), InputTopology(
        upstream_banks=[], extended_idx=np.array([], dtype=np.int32),
        spikelist_idx=np.array([], dtype=np.int32), trace_idx=np.array([], dtype=np.int32)))
    engine.store("kept")
    paths = [engine._snapshot_path("kept"), engine._snapshot_weight_path("kept")]
    assert all(path.is_file() for path in paths)
    del engine
    gc.collect()
    assert not any(path.exists() for path in paths)


def test_disconnect_and_weight_scale(tiny_eng: BrianEngine) -> None:
    """Disconnect zeroes outgoing rows; scale restores from base. Units:
    mV for weights. Shapes: weight arrays with shape (n_syn,)."""
    tiny_eng.restore("initial")
    rows = np.where(np.asarray(tiny_eng._syn.i[:]) == 0)[0]
    assert rows.shape[0] > 0
    before = np.asarray(tiny_eng._syn.w[:] / mV)
    assert bool(np.all(before[rows] != 0.0))
    tiny_eng.disconnect(np.array([0], dtype=np.int32))
    after = np.asarray(tiny_eng._syn.w[:] / mV)
    assert bool(np.all(after[rows] == 0.0))
    np.testing.assert_array_equal(after[np.setdiff1d(np.arange(tiny_eng.n_syn), rows)],
                                  before[np.setdiff1d(np.arange(tiny_eng.n_syn), rows)])
    tiny_eng.set_weight_scale(np.ones(tiny_eng.n_syn, dtype=np.float32))
    restored = np.asarray(tiny_eng._syn.w[:] / mV)
    np.testing.assert_allclose(restored, before, rtol=1e-12)


def test_background_path_and_effect(tiny_eng: BrianEngine) -> None:
    """Background uses the per-neuron weight string and drives spikes.

    Units: mV and spike counts. Shapes: weight array with shape (n,)."""
    assert tiny_eng.background_path == "per-neuron-string"
    tiny_eng.restore("initial")
    tiny_eng.set_upstream_active(0, False)
    tiny_eng.compose_refractory()
    tiny_eng.set_input_rates(np.zeros(2))
    tiny_eng.set_background(np.zeros(tiny_eng.n))
    tiny_eng.seed(3)
    quiet = tiny_eng.run_chunk(50.0).counts.sum()
    tiny_eng.restore("initial")
    tiny_eng.set_upstream_active(0, False)
    tiny_eng.compose_refractory()
    tiny_eng.set_input_rates(np.zeros(2))
    tiny_eng.set_background(np.full(tiny_eng.n, 2.0))
    tiny_eng.seed(3)
    driven = tiny_eng.run_chunk(50.0).counts.sum()
    assert quiet == 0
    assert driven > 0


def test_chunk_boundaries_rejected(tiny_eng: BrianEngine) -> None:
    """Non-millisecond chunk boundaries raise. Units: ms. Shapes: scalars."""
    tiny_eng.restore("initial")
    with pytest.raises(ValueError):
        tiny_eng.run_chunk(10.5)
    with pytest.raises(ValueError):
        tiny_eng.run_chunk(0.05)


def test_single_neuron_analytic(tiny_eng: BrianEngine) -> None:
    """The recorded trace matches the closed-form LIF solution under 1e-9.

    Units: mV and engine ticks. Shapes: trace of shape (1, n_time).
    The deterministic input at tick s acts from tick s+1: Brian applies
    threshold and input events after the state update of the same step.
    """
    fix = load_fixture("fixture-0-1.json")
    params = load_params()
    dt = float(fix["dt_ms"])
    w_in = float(params.get("input.w_in"))
    t_mbr = float(params.get("lif.t_mbr"))
    tau = float(params.get("lif.tau"))
    reset_inputs(tiny_eng, 2)
    tiny_eng.set_threshold(
        np.where(
            np.arange(tiny_eng.n) == fix["recorded"], float(params.get("engine.silence_vth")), float(params.get("lif.v_th"))
        )
    )
    tiny_eng.set_spike_list(
        np.array([fix["driver"]], dtype=np.int32),
        np.array(fix["spike_tick"], dtype=np.int64),
    )
    tiny_eng.seed(fix["seed"])
    n_chunks = int(fix["duration_ms"] // 10)
    for _ in range(n_chunks):
        tiny_eng.run_chunk(10.0)
    trace = tiny_eng.traces(0)
    assert trace.v_mv.shape[0] == 2
    assert tiny_eng.spikes(0).tick.shape[0] == 0
    ticks = trace.tick
    arrival_ms = (np.asarray(fix["spike_tick"]) + 1) * dt
    time_ms = ticks.astype(np.float64) * dt
    expected = np.full(time_ms.shape, float(params.get("lif.v_0")))
    for ta in arrival_ms:
        mask = time_ms >= ta - 1e-12
        tp = time_ms[mask] - ta
        expected[mask] += w_in * (np.exp(-tp / tau) - np.exp(-tp / t_mbr)) / (
            1.0 - t_mbr / tau
        )
    recorded = trace.v_mv[np.flatnonzero(trace.idx == fix["recorded"])[0]]
    rel = np.abs(recorded - expected) / np.abs(expected)
    assert bool(np.all(rel < fix["tolerance_relative"])), rel.max()


def test_chunks_equal_single_run(tiny_eng: BrianEngine) -> None:
    """Ten chunks equal one run bit for bit. Units: engine ticks. Shapes:
    count arrays with shape (n,)."""
    tiny_eng.restore("initial")
    tiny_eng.set_upstream_active(0, True)
    tiny_eng.compose_refractory()
    tiny_eng.set_input_rates(np.array([50.0, 0.0]))
    tiny_eng.set_background(np.zeros(tiny_eng.n))
    tiny_eng.seed(5)
    total = np.zeros(tiny_eng.n, dtype=np.int64)
    for _ in range(10):
        total += tiny_eng.run_chunk(10.0).counts.astype(np.int64)
    chunked = tiny_eng.spikes(0)
    tiny_eng.restore("initial")
    tiny_eng.set_upstream_active(0, True)
    tiny_eng.compose_refractory()
    tiny_eng.set_input_rates(np.array([50.0, 0.0]))
    tiny_eng.set_background(np.zeros(tiny_eng.n))
    tiny_eng.seed(5)
    single = tiny_eng.run_chunk(100.0)
    np.testing.assert_array_equal(single.counts.astype(np.int64), total)
    listed = tiny_eng.spikes(0)
    np.testing.assert_array_equal(listed.idx, chunked.idx)
    np.testing.assert_array_equal(listed.tick, chunked.tick)


def test_mixed_mode_history_invariance(tiny_eng: BrianEngine) -> None:
    """Mode history leaves nothing behind in snapshot-restored state.

    Units: Hz and engine ticks. Shapes: spike tables of equal length.
    Histories E; U,E; E,U,E share the last-E table, and U; E,U; U,E,U
    share the last-U table.
    """

    def probe(extended_rate: float, bank_active: bool) -> tuple[np.ndarray, np.ndarray]:
        tiny_eng.restore("initial")
        tiny_eng.set_upstream_active(0, bank_active)
        tiny_eng.compose_refractory()
        expected = np.full(tiny_eng.n, float(load_params().get("lif.t_rfc")))
        if bank_active:
            expected[1] = 0.0
        np.testing.assert_array_equal(tiny_eng.refractory_ms(), expected)
        tiny_eng.seed(7)
        tiny_eng.set_input_rates(np.array([extended_rate, 0.0]))
        tiny_eng.set_background(np.zeros(tiny_eng.n))
        tiny_eng.run_chunk(100.0)
        table = tiny_eng.spikes(0)
        return table.idx.copy(), table.tick.copy()

    for history in (("U",), ("E", "U"), ("U", "E", "U")):
        for mode in history:
            last = probe(50.0 if mode == "E" else 0.0, bank_active=mode == "U")
        if history == ("U",):
            first_u = last
        else:
            np.testing.assert_array_equal(last[0], first_u[0])
            np.testing.assert_array_equal(last[1], first_u[1])

    last_e: tuple[np.ndarray, np.ndarray] | None = None
    first_e: tuple[np.ndarray, np.ndarray] | None = None
    for history in (("E",), ("U", "E"), ("E", "U", "E")):
        for mode in history:
            if mode == "E":
                last_e = probe(50.0, bank_active=False)
            else:
                last_e = probe(0.0, bank_active=True)
        assert last_e is not None
        if first_e is None:
            first_e = last_e
        else:
            np.testing.assert_array_equal(last_e[0], first_e[0])
            np.testing.assert_array_equal(last_e[1], first_e[1])


def test_trace_shapes(tiny_eng: BrianEngine) -> None:
    """Traces report one row per trace neuron. Units: mV and engine
    ticks. Shapes: v_mv with shape (2, n_time)."""
    tiny_eng.restore("initial")
    tiny_eng.seed(11)
    tiny_eng.run_chunk(10.0)
    trace = tiny_eng.traces(0)
    assert trace.tick.shape == (100,)
    assert trace.v_mv.shape == (2, 100)
    assert trace.tick[0] == 0


def test_v783_build_and_step(eng783: BrianEngine) -> None:
    """The v783 engine builds and steps. Units: engine ticks. Shapes:
    count array with shape (n,) and n == 138639."""
    assert eng783.n == 138639
    eng783.restore("initial")
    eng783.set_upstream_active(0, True)
    eng783.compose_refractory()
    eng783.set_input_rates(np.zeros(8))
    eng783.set_background(np.zeros(eng783.n))
    eng783.seed(1)
    result = eng783.run_chunk(10.0)
    assert result.tick0 == 0
    assert result.tick1 == 100
    assert result.counts.shape == (eng783.n,)
    assert result.hist_1ms.shape == (10,)


def test_input_validation(eng630: BrianEngine) -> None:
    """Wrong shapes and unknown keys raise. Units: mixed. Shapes: mixed."""
    eng630.restore("initial")
    with pytest.raises(ValueError):
        eng630.set_input_rates(np.zeros(7))
    with pytest.raises(ValueError):
        eng630.set_threshold(np.zeros(eng630.n - 1))
    with pytest.raises(ValueError):
        eng630.set_gain(np.zeros(eng630.n + 1))
    with pytest.raises(ValueError):
        eng630.set_background(np.zeros(10))
    with pytest.raises(ValueError):
        eng630.set_weight_scale(np.ones(10, dtype=np.float32))
    with pytest.raises(ValueError):
        eng630.set_upstream_active(99, True)
    with pytest.raises(ValueError):
        eng630.seed(2**32)


def test_spike_list_input_validation(tiny_eng: BrianEngine) -> None:
    """Unknown deterministic input indices raise. Units: engine ticks.
    Shapes: one indexed event."""
    with pytest.raises(ValueError):
        tiny_eng.set_spike_list(
            np.array([99], dtype=np.int32), np.array([5], dtype=np.int64)
        )


def test_optional_apis_on_bare_path() -> None:
    """A bare engine rejects absent optional inputs in its own process.

    Units: engine ticks. Shapes: one indexed event and no trace array.
    """
    code = """
import numpy as np
from pathlib import Path
from flyonenomics.engine import BrianEngine, InputTopology
from flyonenomics.types import ConnectomeFiles, load_params
fix = Path.cwd() / 'tests' / 'fixtures' / 'engine'
connectome = ConnectomeFiles(
    completeness=fix / 'tiny_completeness.csv',
    connectivity=fix / 'tiny_connectivity.parquet',
    version='630',
)
engine = BrianEngine()
engine.seed(0)
engine.build(connectome, load_params(), InputTopology())
for call in (
    lambda: engine.set_spike_list(np.array([0], dtype=np.int32), np.array([5], dtype=np.int64)),
    lambda: engine.traces(0),
):
    try:
        call()
    except RuntimeError:
        continue
    raise AssertionError('bare engine accepted an absent optional input')
"""
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_spike_list_clears(tiny_eng: BrianEngine) -> None:
    """An empty spike list clears the generator. Units: engine ticks.
    Shapes: empty index and tick arrays."""
    reset_inputs(tiny_eng, 2)
    tiny_eng.set_spike_list(
        np.array([0], dtype=np.int32), np.array([50], dtype=np.int64)
    )
    tiny_eng.set_spike_list(
        np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.int64)
    )
    tiny_eng.seed(11)
    tiny_eng.run_chunk(10.0)
    assert tiny_eng.spikes(0).tick.shape[0] == 0


def test_topology_contracts() -> None:
    """Reject lossy topology input and immutable-rate edits. Units: Hz. Shapes: (k,)."""
    from dataclasses import FrozenInstanceError

    source = np.array([2, 0], dtype=np.int32)
    bank = UpstreamBank(source, 150.0)
    source[:] = 1
    np.testing.assert_array_equal(bank.idx, [2, 0])
    with pytest.raises(FrozenInstanceError):
        bank.rate_hz = 1.0
    with pytest.raises(ValueError):
        bank.idx[0] = 1
    for idx in (np.array([1.5]), np.array([[1]], dtype=np.int32),
                np.array([-1], dtype=np.int32), np.array([1, 1], dtype=np.int32)):
        with pytest.raises(ValueError):
            UpstreamBank(idx, 150.0)
        with pytest.raises(ValueError):
            BrianEngine().build(tiny_connectome(), load_params(), InputTopology(extended_idx=idx))
    with pytest.raises(ValueError, match="outside the connectome"):
        BrianEngine().build(tiny_connectome(), load_params(),
                            InputTopology(trace_idx=np.array([4], dtype=np.int32)))
    params = load_params()
    params.data["lif"]["dt"]["value"] = 0.3
    with pytest.raises(ValueError, match="divide 1 ms"):
        BrianEngine().build(tiny_connectome(), params, InputTopology())


def test_build_detaches_topology(tiny_eng: BrianEngine) -> None:
    """Index copies and public bank flags agree. Units: none. Shapes: (k,)."""
    tiny_eng.restore("initial")
    assert all(p.active == tiny_eng.bank_active_flags()[0] for p in tiny_eng._bank_pois[0])


def test_nonzero_restore_rng_and_histograms(tiny_eng: BrianEngine) -> None:
    """Restore RNG/queued events at nonzero time and compare chunk bins.

    Units: ms, ticks and spike counts. Shapes: 100 bins and n-neuron counts.
    """
    reset_inputs(tiny_eng, 2)
    tiny_eng.set_input_rates(np.array([150.0, 50.0]))
    tiny_eng.set_background(np.full(tiny_eng.n, 2.0))
    tiny_eng.seed(37)
    tiny_eng.run_chunk(13.0)
    tiny_eng.store("at-thirteen")
    tiny_eng.restore("at-thirteen")
    assert tiny_eng.tick() == 0
    chunks = [tiny_eng.run_chunk(10.0) for _ in range(10)]
    first = tiny_eng.spikes(0)
    trace = tiny_eng.traces(0)
    assert trace.tick[0] == 0 and trace.tick[-1] == 999
    tiny_eng.seed(99)  # Restore must recover the snapshot RNG, without reseeding.
    tiny_eng.restore("at-thirteen")
    whole = tiny_eng.run_chunk(100.0)
    replay = tiny_eng.spikes(0)
    assert whole.tick0 == 0 and whole.tick1 == 1000
    np.testing.assert_array_equal(first.idx, replay.idx)
    np.testing.assert_array_equal(first.tick, replay.tick)
    np.testing.assert_array_equal(np.concatenate([c.hist_1ms for c in chunks]), whole.hist_1ms)
    np.testing.assert_array_equal(np.sum([c.counts for c in chunks], axis=0), whole.counts)
    assert whole.hist_1ms.sum() == whole.counts.sum() == len(replay.tick)


def test_active_upstream_wins_overlap(tiny_eng: BrianEngine) -> None:
    """Simultaneous extended and upstream drive keeps zero refractory. Units: Hz/ms. Shapes: (n,)."""
    reset_inputs(tiny_eng, 2)
    tiny_eng.set_input_rates(np.array([150.0, 0.0]))
    tiny_eng.set_upstream_active(0, True)
    tiny_eng.compose_refractory()
    expected = np.full(tiny_eng.n, float(load_params().get("lif.t_rfc")))
    expected[1] = 0.0
    np.testing.assert_array_equal(tiny_eng.refractory_ms(), expected)


def test_replay_rejects_duplicate_events() -> None:
    """Exact replay compares event multiplicity. Units: ticks. Shapes: (k,)."""
    from flyonenomics.validation.level0 import stream_match
    result = stream_match(np.array([1, 1]), np.array([2, 2]), np.array([1]), np.array([2]))
    assert not result["exact_events"]
    assert result["total_spikes"] == 2


def test_primary_reference_is_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A secondary sugar file cannot qualify 1.2 alone. Units: none. Shapes: scalar outcome."""
    from flyonenomics.validation import level1
    (tmp_path / "sugarR.parquet").touch()
    monkeypatch.setattr(level1, "archive_dir", lambda: tmp_path)
    assert level1._measure_1_2()["outcome"] == "unavailable"


def test_engine_identity_names_executed_layers() -> None:
    """Canonical identity reports actual engine-only flags. Units: none. Shapes: flags mapping."""
    from flyonenomics.validation.level0 import make_entry
    for name, background in (("fixture-0-3.json", False), ("fixture-0-4.json", True)):
        entry = make_entry("fixture", "verification", "630", "spontaneous", name, {}, "passed")
        assert entry.identity.layer_flags["background"] is background
        assert entry.identity.layer_flags["dopamine_A"] is False
        assert entry.identity.layer_flags["transporter_C"] is False


def test_setters_reject_lossy_indices(tiny_eng: BrianEngine) -> None:
    """Fractional ticks/indices cannot silently target another event or neuron.

    Units: ticks/ms. Shapes: indexed arrays of length one.
    """
    with pytest.raises(ValueError, match="int64"):
        tiny_eng.set_spike_list(np.array([0], dtype=np.int32), np.array([1.5]))
    with pytest.raises(ValueError, match="int32"):
        tiny_eng.set_spike_list(np.array([0.5]), np.array([1], dtype=np.int64))
    with pytest.raises(ValueError, match="int32"):
        tiny_eng.disconnect(np.array([0.5]))
    with pytest.raises(ValueError, match="int32"):
        tiny_eng.set_refractory(np.array([0.5]), np.array([2.0]))
    tiny_eng.restore("initial")
    gains = tiny_eng.gains()
    gains[:] = 5.0
    np.testing.assert_array_equal(tiny_eng.gains(), np.ones(tiny_eng.n))
