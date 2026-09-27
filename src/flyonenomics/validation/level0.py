"""Level 0 engine numerics suites (WP1).

Units and array shapes follow the engine docstrings. Tests 0.1 to 0.4,
0.3b, and full 0.7 live here. Test 0.5 (pool integrator) was added by
WP5 neuromodulation; tests 0.6, 0.8, and 0.9 (orchestrator
replay, stream invariance, binding drill) belong to WP4.

Isolation rule: Brian2's Cython RNG heap corrupts (SIGABRT in __rand)
when more than one built network lives in one process, so every suite
measurement runs in a fresh subprocess that builds at most one engine
(test 0.2 uses two leaf processes, one per dt). The suite functions
below never build engines and never call seed or restore; they only
parse the leaf's JSON and attach the identity block.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from flyonenomics.io import read_json, read_parquet
from flyonenomics.types import ConnectomeFiles, LayerFlags, load_params
from flyonenomics.engine import BrianEngine, InputTopology, UpstreamBank
from flyonenomics.engine.brian_engine import cache_dir
from flyonenomics.validation.binding import (
    ValidationEntry,
    build_identity,
)

REPO = Path(__file__).resolve().parents[3]
FIX = REPO / "tests" / "fixtures" / "engine"

_LOOKUP: dict[str, dict[int, int]] = {}
# SPEC 7.2 test 0.5: fixed five-second numerical comparison.
POOL_REF_DURATION_S = 5.0
POOL_SPIKE_PERIOD_CHUNKS = (17, 23)


def run_isolated(module: str, measure: str) -> dict[str, Any]:
    """Run one _measure_* helper in a fresh interpreter and return its mapping.

    Units: none. Shapes: mapping with measured and outcome (or, for the
    0.2 legs, per-neuron spike lists). The child builds at most one
    engine; the caller never touches Brian2 state.
    """
    code = (
        "import json; "
        f"from flyonenomics.validation.{module} import {measure} as m; "
        'print("ENTRY-BEGIN"); print(json.dumps(m()))'
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=2400,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"isolated suite {module}.{measure} failed: {proc.stderr[-3000:]}"
        )
    marker = "ENTRY-BEGIN\n"
    if marker not in proc.stdout:
        raise RuntimeError(
            f"isolated suite {module}.{measure} printed no entry: "
            f"{proc.stdout[-1000:]} {proc.stderr[-2000:]}"
        )
    return json.loads(proc.stdout.rsplit(marker, 1)[1])


def read_fixture(name: str) -> dict[str, Any]:
    """Load one canonical engine fixture. Units: per file. Shapes: mapping."""
    return read_json(FIX / name)


def grn() -> dict[str, Any]:
    """Load the sugar, bitter, and MN9 root lists. Units: none. Shapes: mapping."""
    return read_json(FIX / "grn.json")


def root_lookup(version: str) -> dict[int, int]:
    """Map root ID to engine index for one connectome version.

    Units: none. Shapes: mapping of int to int.
    """
    if version not in _LOOKUP:
        name = (
            "2023_03_23_completeness_630_final.csv"
            if version == "630"
            else "Completeness_783.csv"
        )
        comp = pd.read_csv(
            cache_dir() / "Drosophila_brain_model" / name, index_col=0
        )
        ids = comp.index.to_numpy()
        _LOOKUP[version] = {int(v): i for i, v in enumerate(ids)}
    return _LOOKUP[version]


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


def make_entry(
    test_id: str,
    category: str,
    connectome_version: str,
    assay: str,
    fixture_name: str,
    measured: dict[str, Any],
    outcome: str,
) -> ValidationEntry:
    """Build a canonical ValidationEntry with its identity block.

    Units: per measured value. Shapes: scalars unless measured says
    otherwise. Data dependencies are the params file version; the
    connectome files enter through the provenance hash.
    """
    fixture = read_fixture(fixture_name)
    identity = build_identity(
        REPO,
        connectome_version=connectome_version,
        layers=LayerFlags(
            background=bool(fixture.get("background", False))
            and float(fixture.get("background_weights_mv", 0.0)) != 0.0,
            dopamine_A=False,
            transporter_C=False,
        ),
        assay=assay,
        fixture=f"tests/fixtures/engine/{fixture_name}",
    )
    return ValidationEntry(
        test_id=test_id,
        category=category,
        outcome=outcome,  # type: ignore[arg-type]
        compatibility="canonical",
        identity=identity,
        measured=measured,
        data_dependencies=["params-v0.1.yaml"],
        fixture_path=f"tests/fixtures/engine/{fixture_name}",
    )


def prepare(engine: BrianEngine) -> None:
    """Restore the initial snapshot and rewrite base thresholds and gains.

    Units: mV and dimensionless. Shapes: arrays with shape (n,). Bank
    activity, input rates, background, refractory composition, and seed
    are set explicitly by each leg after this call.
    """
    params = load_params()
    engine.restore("initial")
    engine.set_threshold(np.full(engine.n, float(params.get("lif.v_th"))))
    engine.set_gain(np.ones(engine.n))


def run_chunks(engine: BrianEngine, duration_ms: float, chunk_ms: float = 10.0) -> None:
    """Run duration_ms in chunk_ms pieces. Units: ms. Shapes: scalars."""
    remaining = duration_ms
    while remaining > 0:
        step = min(chunk_ms, remaining)
        engine.run_chunk(step)
        remaining -= step


def reference_stream(version: str) -> tuple[np.ndarray, np.ndarray]:
    """Return the proof-run reference as (idx, tick) in engine order.

    Units: engine ticks at dt 0.1 ms. Shapes: idx int32 with shape
    (n_spikes,), tick int64 with shape (n_spikes,).
    """
    lookup = root_lookup(version)
    ref = read_parquet(REPO / "data" / "reference" / "l5-baseline-spikes.parquet").to_pandas()
    idx = np.array(
        [lookup[int(v)] for v in ref["flywire_id"].to_numpy()], dtype=np.int32
    )
    tick = np.round(ref["t_seconds"].to_numpy() * 1000.0 / 0.1).astype(np.int64)
    return idx, tick


def stream_match(
    mine_idx: np.ndarray, mine_tick: np.ndarray, ref_idx: np.ndarray, ref_tick: np.ndarray
) -> dict[str, Any]:
    """Compare two spike streams exactly and statistically. Units: spikes
    and engine ticks. Shapes: four index/tick arrays."""
    mine = set(zip(mine_idx.tolist(), mine_tick.tolist()))
    theirs = set(zip(ref_idx.tolist(), ref_tick.tolist()))
    total = len(mine)
    ref_total = len(theirs)
    mine_active = set(mine_idx.tolist())
    ref_active = set(ref_idx.tolist())
    active_jaccard = (
        len(mine_active & ref_active) / len(mine_active | ref_active)
        if (mine_active | ref_active)
        else 1.0
    )
    return {
        "exact_events": bool(
            np.array_equal(mine_idx[np.lexsort((mine_tick, mine_idx))], ref_idx[np.lexsort((ref_tick, ref_idx))])
            and np.array_equal(mine_tick[np.lexsort((mine_tick, mine_idx))], ref_tick[np.lexsort((ref_tick, ref_idx))])
        ),
        "total_spikes": len(mine_idx),
        "reference_total_spikes": len(ref_idx),
        "active_neurons": len(mine_active),
        "reference_active_neurons": len(ref_active),
        "missing": len(theirs - mine),
        "extra": len(mine - theirs),
        "active_jaccard": active_jaccard,
        "event_jaccard": (
            len(mine & theirs) / len(mine | theirs) if (mine | theirs) else 1.0
        ),
    }


def tiny_engine() -> BrianEngine:
    """Build the tiny engine for test 0.1. Units: none. Shapes: n == 4."""
    engine = BrianEngine()
    engine.seed(11)
    engine.build(
        ConnectomeFiles(
            completeness=FIX / "tiny_completeness.csv",
            connectivity=FIX / "tiny_connectivity.parquet",
            version="630",
        ),
        load_params(),
        InputTopology(
            spikelist_idx=np.array([0], dtype=np.int32),
            trace_idx=np.array([0, 1], dtype=np.int32),
        ),
    )
    return engine


def _measure_0_1() -> dict[str, Any]:
    """Single neuron trace against the closed-form LIF solution.

    Units: mV and engine ticks. Shapes: trace of shape (2, n_time).
    Runs in a leaf process with one engine.
    """
    fix = read_fixture("fixture-0-1.json")
    params = load_params()
    dt = float(fix["dt_ms"])
    w_in = float(params.get("input.w_in"))
    t_mbr = float(params.get("lif.t_mbr"))
    tau = float(params.get("lif.tau"))
    engine = tiny_engine()
    prepare(engine)
    engine.set_threshold(
        np.where(
            np.arange(engine.n) == fix["recorded"], float(params.get("engine.silence_vth")), float(params.get("lif.v_th"))
        )
    )
    engine.set_spike_list(
        np.array([fix["driver"]], dtype=np.int32),
        np.array(fix["spike_tick"], dtype=np.int64),
    )
    engine.seed(int(fix["seed"]))
    run_chunks(engine, float(fix["duration_ms"]))
    trace = engine.traces(0)
    spikes = engine.spikes(0)
    arrival_ms = (np.asarray(fix["spike_tick"]) + 1) * dt
    time_ms = trace.tick.astype(np.float64) * dt
    expected = np.full(time_ms.shape, float(params.get("lif.v_0")))
    for ta in arrival_ms:
        mask = time_ms >= float(ta) - 1e-12
        tp = time_ms[mask] - float(ta)
        expected[mask] += w_in * (np.exp(-tp / tau) - np.exp(-tp / t_mbr)) / (
            1.0 - t_mbr / tau
        )
    recorded = trace.v_mv[0]
    rel = np.abs(recorded - expected) / np.abs(expected)
    max_rel = float(rel.max())
    outcome = "passed" if bool(np.all(rel < fix["tolerance_relative"])) else "failed"
    return {
        "measured": {
            "max_relative_error": max_rel,
            "tolerance": fix["tolerance_relative"],
            "n_ticks": int(time_ms.shape[0]),
            "n_spikes": int(spikes.tick.shape[0]),
        },
        "outcome": outcome,
    }


def test_0_1() -> ValidationEntry:
    """Single neuron trace against the closed-form LIF solution.

    Units: mV and engine ticks. Shapes: trace of shape (2, n_time).
    """
    result = run_isolated("level0", "_measure_0_1")
    return make_entry(
        "0.1",
        "verification",
        "630",
        "deterministic",
        "fixture-0-1.json",
        result["measured"],
        result["outcome"],
    )


def _run_0_2_at(dt_ms: float) -> dict[str, Any]:
    """Run the 0.2 fixed spike list at one dt in a leaf process with one engine.

    Units: ms and engine ticks. Shapes: per-neuron spike lists over 1 s.
    """
    fix = read_fixture("fixture-0-2.json")
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in fix["sugar_roots"]], dtype=np.int32)
    rng = np.random.default_rng(int(fix["list_seed"]))
    per_neuron = int(fix["spikes_per_neuron"])
    idx_list: list[int] = []
    tick_list: list[int] = []
    for neuron in sugar.tolist():
        # Unique ticks on the dt 0.1 grid: at most one spike per neuron
        # per timestep at either dt, as SpikeGeneratorGroup requires.
        times = rng.choice(10000, size=per_neuron, replace=False)
        idx_list.extend([neuron] * per_neuron)
        tick_list.extend(int(t) for t in times)
    params = load_params()
    params.data["lif"]["dt"]["value"] = dt_ms
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    engine.build(
        connectome("630"),
        params,
        InputTopology(spikelist_idx=np.sort(np.unique(sugar))),
    )
    scale = int(round(float(fix["dt_a_ms"]) / dt_ms))
    engine.set_spike_list(
        np.array(idx_list, dtype=np.int32), np.array(tick_list, dtype=np.int64) * scale
    )
    engine.seed(int(fix["seed"]))
    run_chunks(engine, float(fix["duration_ms"]))
    table = engine.spikes(0)
    out: dict[str, list[int]] = {}
    for i, t in zip(table.idx.tolist(), table.tick.tolist()):
        out.setdefault(str(i), []).append(t)
    return {"spikes": out, "dt_ms": dt_ms}


def _measure_0_2() -> dict[str, Any]:
    """Time-step convergence at dt 0.1 ms against dt 0.05 ms. Units: ms,
    engine ticks. Shapes: per-neuron spike lists over 1 s. Runs one leaf
    process per dt, each with one engine, and matches here (no engine).
    """
    fix = read_fixture("fixture-0-2.json")
    coarse_run = run_isolated("level0", "_run_0_2_dt01")
    fine_run = run_isolated("level0", "_run_0_2_dt005")
    coarse = {int(k): v for k, v in coarse_run["spikes"].items()}
    fine = {int(k): v for k, v in fine_run["spikes"].items()}
    fine_dt_ms = float(fix["dt_b_ms"])
    coarse_to_fine = int(round(float(fix["dt_a_ms"]) / fine_dt_ms))
    window_ticks = int(round(float(fix["match_window_ms"]) / fine_dt_ms))
    matched = 0
    total_coarse = 0
    total_fine = 0
    max_offset = 0
    for neuron in set(coarse) | set(fine):
        a = sorted(coarse.get(neuron, []))
        fb = sorted(fine.get(neuron, []))
        total_coarse += len(a)
        total_fine += len(fb)
        # Match each coarse event to its nearest unused fine event.
        available = fb.copy()
        for t in a:
            target = t * coarse_to_fine
            if not available:
                break
            j = min(range(len(available)), key=lambda k: abs(available[k] - target))
            if abs(available[j] - target) <= window_ticks:
                matched += 1
                max_offset = max(max_offset, abs(available[j] - target))
                available.pop(j)
    frac_coarse = matched / total_coarse if total_coarse else 1.0
    frac_fine = matched / total_fine if total_fine else 1.0
    needed = float(fix["min_match_fraction"])
    outcome = "passed" if min(frac_coarse, frac_fine) >= needed else "failed"
    return {
        "measured": {
            "unmatched_fraction_coarse": 1.0 - frac_coarse,
            "unmatched_fraction_fine": 1.0 - frac_fine,
            "matched_fraction_coarse": frac_coarse,
            "matched_fraction_fine": frac_fine,
            "required": needed,
            "max_offset_ms": max_offset * fine_dt_ms,
            "n_coarse": total_coarse,
            "n_fine": total_fine,
        },
        "outcome": outcome,
    }


def _run_0_2_dt01() -> dict[str, Any]:
    """0.2 leg at dt 0.1 ms. Units: ms. Shapes: per-neuron spike lists."""
    return _run_0_2_at(0.1)


def _run_0_2_dt005() -> dict[str, Any]:
    """0.2 leg at dt 0.05 ms. Units: ms. Shapes: per-neuron spike lists."""
    return _run_0_2_at(0.05)


def test_0_2() -> ValidationEntry:
    """Time-step convergence at dt 0.1 ms against dt 0.05 ms. Units: ms,
    Hz, engine ticks. Shapes: per-neuron spike lists over 1 s."""
    result = run_isolated("level0", "_measure_0_2")
    return make_entry(
        "0.2",
        "verification",
        "630",
        "deterministic",
        "fixture-0-2.json",
        result["measured"],
        result["outcome"],
    )


def _measure_0_3() -> dict[str, Any]:
    """Exact replay of the proof run on the bare v630 path. Units: spikes
    and engine ticks. Shapes: full spike tables over 1 s. One engine."""
    fix = read_fixture("fixture-0-3.json")
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in fix["sugar_roots"]], dtype=np.int32)
    mn9 = lookup[int(fix["mn9_root"])]
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    engine.build(
        connectome("630"),
        load_params(),
        InputTopology(
            upstream_banks=[UpstreamBank(idx=sugar, rate_hz=float(fix["rate_hz"]))]
        ),
    )
    prepare(engine)
    engine.set_upstream_active(0, True)
    engine.compose_refractory()
    run_chunks(engine, float(fix["duration_ms"]), float(fix["chunk_ms"]))
    table = engine.spikes(0)
    mn9_spikes = int((table.idx == mn9).sum())
    ref_idx, ref_tick = reference_stream("630")
    comparison = stream_match(table.idx, table.tick, ref_idx, ref_tick)
    comparison["mn9_spikes"] = mn9_spikes
    exact = comparison["exact_events"]
    if exact:
        outcome = "passed"
        comparison["replay_form"] = "exact"
    else:
        ref_mn9 = int((ref_idx == mn9).sum())
        ref_total = comparison["reference_total_spikes"]
        stat = (
            abs(comparison["total_spikes"] - ref_total) / ref_total <= 0.05
            and abs(mn9_spikes - ref_mn9) / ref_mn9 <= 0.10
            and comparison["active_jaccard"] >= 0.9
        )
        outcome = "failed"
        comparison["statistical_criteria_met"] = stat
        comparison["replay_form"] = "exact-replay-failed"
        comparison["reason"] = "Pinned-environment suite requires exact replay; statistical agreement is diagnostic only."
        comparison["reference_mn9_spikes"] = ref_mn9
    return {"measured": comparison, "outcome": outcome}


def test_0_3() -> ValidationEntry:
    """Exact replay of the proof run on the bare v630 path. Units: spikes
    and engine ticks. Shapes: full spike tables over 1 s."""
    result = run_isolated("level0", "_measure_0_3")
    return make_entry(
        "0.3",
        "empirical replay",
        "630",
        "sugar_reflex",
        "fixture-0-3.json",
        result["measured"],
        result["outcome"],
    )


def _measure_0_3b() -> dict[str, Any]:
    """Replay with the extended acceptance topology present. Units: spikes
    and engine ticks. Shapes: full spike tables over 1 s. One engine."""
    fix = read_fixture("fixture-0-3b.json")
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in fix["sugar_roots"]], dtype=np.int32)
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    engine.build(
        connectome("630"),
        load_params(),
        InputTopology(
            upstream_banks=[UpstreamBank(idx=sugar, rate_hz=float(fix["rate_hz"]))],
            extended_idx=np.array(fix["extended_idx"], dtype=np.int32),
            background=bool(fix["background"]),
        ),
    )
    prepare(engine)
    engine.set_upstream_active(0, True)
    engine.compose_refractory()
    engine.set_input_rates(np.zeros(len(fix["extended_idx"])))
    engine.set_background(np.full(engine.n, float(fix["background_weights_mv"])))
    engine.seed(int(fix["seed"]))
    run_chunks(engine, float(fix["duration_ms"]), float(fix["chunk_ms"]))
    table = engine.spikes(0)
    ref_idx, ref_tick = reference_stream("630")
    comparison = stream_match(table.idx, table.tick, ref_idx, ref_tick)
    if comparison["exact_events"]:
        outcome = "passed"
        comparison["replay_form"] = "exact-with-acceptance-topology"
    else:
        outcome = "recorded"
        comparison["replay_form"] = "bare-path-required"
        comparison["note"] = (
            "exact replay requires the bare reference path; level 1 runs on that path"
        )
    return {"measured": comparison, "outcome": outcome}


def test_0_3b() -> ValidationEntry:
    """Replay with the extended acceptance topology present. Units: spikes
    and engine ticks. Shapes: full spike tables over 1 s."""
    result = run_isolated("level0", "_measure_0_3b")
    return make_entry(
        "0.3b",
        "empirical replay",
        "630",
        "sugar_reflex",
        "fixture-0-3b.json",
        result["measured"],
        result["outcome"],
    )


def _measure_0_4() -> dict[str, Any]:
    """One hundred chunks equal one run bit for bit. Units: engine ticks.
    Shapes: count arrays with shape (n,) over 1 s. One engine, two legs."""
    fix = read_fixture("fixture-0-4.json")
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    engine.build(
        connectome("630"),
        load_params(),
        InputTopology(
            extended_idx=np.array(fix["extended_idx"], dtype=np.int32),
            background=bool(fix["background"]),
        ),
    )

    def leg() -> None:
        prepare(engine)
        engine.set_input_rates(
            np.full(len(fix["extended_idx"]), float(fix["extended_rate_hz"]))
        )
        engine.set_background(np.full(engine.n, float(fix["background_weights_mv"])))
        engine.seed(int(fix["seed"]))

    leg()
    total = np.zeros(engine.n, dtype=np.int64)
    histograms = []
    n_chunks = int(fix["duration_ms"] // fix["chunk_ms"])
    for _ in range(n_chunks):
        chunk = engine.run_chunk(float(fix["chunk_ms"]))
        total += chunk.counts.astype(np.int64)
        histograms.append(chunk.hist_1ms)
    chunked = engine.spikes(0)
    leg()
    single = engine.run_chunk(float(fix["duration_ms"]))
    listed = engine.spikes(0)
    counts_equal = bool(np.array_equal(single.counts.astype(np.int64), total))
    idx_equal = bool(np.array_equal(listed.idx, chunked.idx))
    tick_equal = bool(np.array_equal(listed.tick, chunked.tick))
    hist_equal = bool(np.array_equal(np.concatenate(histograms), single.hist_1ms))
    outcome = "passed" if counts_equal and idx_equal and tick_equal and hist_equal else "failed"
    return {
        "measured": {
            "background_weights_mv": fix["background_weights_mv"],
            "histograms_equal": hist_equal,
            "histogram_bins": len(single.hist_1ms),
            "counts_equal": counts_equal,
            "idx_equal": idx_equal,
            "tick_equal": tick_equal,
            "n": engine.n,
            "n_chunks": n_chunks,
        },
        "outcome": outcome,
    }


def test_0_4() -> ValidationEntry:
    """One hundred chunks equal one run bit for bit. Units: engine ticks.
    Shapes: count arrays with shape (n,) over 1 s."""
    result = run_isolated("level0", "_measure_0_4")
    return make_entry(
        "0.4",
        "verification",
        "630",
        "spontaneous",
        "fixture-0-4.json",
        result["measured"],
        result["outcome"],
    )


def _measure_0_7() -> dict[str, Any]:
    """Intervention persistence plus all eight neuromod flag identities;
    engine silence over 200 chunks and threshold-shift readback. Units: mV and spikes.
    Shapes: threshold array with shape (n,); MN9 counts over 2 s."""
    fix = read_fixture("fixture-0-7.json")
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in fix["sugar_roots"]], dtype=np.int32)
    mn9 = lookup[int(fix["mn9_root"])]
    params = load_params()
    silence_vth = float(params.get("engine.silence_vth"))
    base_vth = float(params.get("lif.v_th"))
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    engine.build(
        connectome("630"),
        params,
        InputTopology(
            upstream_banks=[UpstreamBank(idx=sugar, rate_hz=float(fix["rate_hz"]))]
        ),
    )
    prepare(engine)
    engine.set_upstream_active(0, True)
    engine.compose_refractory()
    from itertools import product
    from types import SimpleNamespace
    from scipy.sparse import csr_matrix
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.registry.receptors import ReceptorMap
    from flyonenomics.schema.experiment import ShiftThreshold, Silence
    # Constructed receptor fixture over the engine index: modulation evolves
    # on every chunk while the two persistent interventions remain in force.
    all_idx = np.arange(engine.n, dtype=np.int32)
    full_w = csr_matrix((np.ones(engine.n, dtype=np.float32), (all_idx, np.zeros(engine.n, dtype=np.int32))), shape=(engine.n, 1))
    full_m = csr_matrix(([1.], ([0], [int(sugar[0])])), shape=(1, engine.n))
    receptors = ReceptorMap(np.ones(engine.n, dtype=np.float32), np.ones(engine.n, dtype=np.float32),
                             np.zeros(engine.n, dtype=np.float32), "constructed")
    registry = SimpleNamespace(n=engine.n, exposure=lambda: full_w, innervation=lambda: full_m,
        exposed_mask=lambda: np.ones(engine.n, dtype=bool), receptors=lambda: receptors,
        compartments=lambda: [SimpleNamespace(name="constructed")],
        population=lambda name: SimpleNamespace(idx=sugar if name == "sugar" else np.array([mn9], dtype=np.int32)))
    mod = Neuromod(registry, params, LayerFlags(background=False))
    mod.apply_genotype([ShiftThreshold(type="shift_threshold", population="sugar", delta_mv=fix["shift_mv"]),
                        Silence(type="silence", population="MN9")], engine)
    mod.reset_fast()
    engine.set_threshold(mod.compose().v_th)
    engine.set_gain(mod.compose().gain)
    engine.seed(int(fix["seed"]))
    mn9_counts = 0
    shift_ok = True
    for _ in range(int(fix["chunks"])):
        result = engine.run_chunk(float(fix["chunk_ms"]))
        mn9_counts += int(result.counts[mn9])
        mod.on_chunk(result.counts, float(fix["chunk_ms"]) / 1000)
        composed = mod.compose()
        engine.set_threshold(composed.v_th)
        engine.set_gain(composed.gain)
        shift_ok &= bool(np.array_equal(engine.thresholds_mv(), composed.v_th))
        mod.shift[sugar] = 0
        no_shift = mod.compose().v_th[sugar]
        mod.shift[sugar] = fix["shift_mv"]
        shift_ok &= bool(np.allclose(composed.v_th[sugar] - no_shift, fix["shift_mv"], rtol=0, atol=1e-12))
        shift_ok &= bool(composed.v_th[mn9] == silence_vth)
    silence_ok = mn9_counts == 0
    w = csr_matrix(np.array([[1, 0], [0, 1], [0, 0]], dtype=np.float32))
    m = csr_matrix(np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32))
    tiny = SimpleNamespace(n=3, exposure=lambda: w, innervation=lambda: m,
                           exposed_mask=lambda: np.array([True, True, False]),
                           receptors=lambda: ReceptorMap(np.array([1, 0.5, 1], dtype=np.float32),
                                                          np.array([0.5, 1, 1], dtype=np.float32), np.zeros(3, dtype=np.float32), "fixture"),
                           compartments=lambda: [SimpleNamespace(name="a"), SimpleNamespace(name="b")],
                           population=lambda _name: SimpleNamespace(idx=np.array([0, 1], dtype=np.int32)))
    combinations_checked = 0
    flags_ok = True
    for dopamine_a, transporter_c, fast in product((False, True), (False, True), ("retain", "disconnect")):
        mod = Neuromod(tiny, params, LayerFlags(dopamine_A=dopamine_a, transporter_C=transporter_c, dan_fast_synapses=fast))
        calls: list[np.ndarray] = []
        fake_engine = SimpleNamespace(disconnect=lambda idx: calls.append(idx.copy()),
                                      set_threshold=lambda _values: None, set_gain=lambda _values: None)
        mod.apply_genotype([], fake_engine)
        flags_ok &= (len(calls) == (1 if fast == "disconnect" else 0))
        mod.da_c.fill(5 * params.get("da.DA_ref"))
        mod.slow.concentrations["methylphenidate"] = 1.0
        composed_flags = mod.compose()
        if not dopamine_a:
            flags_ok &= bool(np.array_equal(composed_flags.v_th, np.full(3, base_vth)) and np.array_equal(composed_flags.gain, np.ones(3)))
        if not transporter_c:
            flags_ok &= bool(np.array_equal(mod.state().Km_eff, mod.km0) and np.array_equal(mod.state().rel, np.ones(2)))
        else:
            flags_ok &= bool(np.all(mod.state().Km_eff > mod.km0))
        mod.dat_geno.fill(0)
        mod.rel_geno = 0.5
        mod.slow.concentrations["3-iodotyrosine"] = params.get("drug.3iy.EC50")
        vmax, km, rel = mod._kinetics()
        flags_ok &= bool(np.array_equal(vmax, mod.vmax0 * (0 if transporter_c else 1)))
        flags_ok &= rel == (0.25 if transporter_c else 1)
        for concentration in (0., params.get("da.DA_ref"), 5 * params.get("da.DA_ref")):
            mod.da_c.fill(concentration)
            occ1 = concentration / (concentration + params.get("rec.Kd_D1")) * tiny.exposed_mask()
            occ2 = concentration / (concentration + params.get("rec.Kd_D2")) * tiny.exposed_mask()
            expected_dv = (-params.get("rec.dV_D1") * mod.r1 * occ1 + params.get("rec.dV_D2") * mod.r2 * occ2) if dopamine_a else np.zeros(3)
            expected_gain = (1 + params.get("rec.gamma_D1") * mod.r1 * occ1 - params.get("rec.gamma_D2") * mod.r2 * occ2) if dopamine_a else np.ones(3)
            composed_flags = mod.compose()
            flags_ok &= bool(np.array_equal(composed_flags.v_th, np.clip(base_vth + expected_dv, *params.get("rec.vth_clip"))))
            flags_ok &= bool(np.array_equal(composed_flags.gain, np.clip(expected_gain, *params.get("rec.gain_clip"))))
        mod.da_c.fill(params.get("da.DA_ref"))
        free = mod.compose()
        mod.clamp_pools(True)
        clamped = mod.compose()
        flags_ok &= bool(np.array_equal(free.v_th, clamped.v_th) and np.array_equal(free.gain, clamped.gain))
        flags_ok &= composed_flags.layers.dan_fast_synapses == fast
        combinations_checked += 1
    outcome = "passed" if shift_ok and silence_ok and flags_ok and combinations_checked == 8 else "failed"
    return {
        "measured": {
            "silenced_spikes_200_chunks": mn9_counts,
            "threshold_shift_readback_exact": shift_ok,
            "silence_vth_mv": silence_vth,
            "shift_mv": fix["shift_mv"],
            "n_chunks": fix["chunks"],
            "neuromod_flag_combinations": combinations_checked,
            "neuromod_flags_ok": flags_ok,
        },
        "outcome": outcome,
    }


def test_0_7() -> ValidationEntry:
    """Full intervention persistence and eight layer-flag identities;
    silence over 200 chunks and threshold-shift readback. Units: mV and spikes.
    Shapes: threshold array with shape (n,); MN9 counts over 2 s."""
    result = run_isolated("level0", "_measure_0_7")
    entry = make_entry(
        "0.7",
        "verification",
        "630",
        "sugar_reflex",
        "fixture-0-7.json",
        result["measured"],
        result["outcome"],
    )
    # The real engine leg now exercises active A/C; the eight constructed
    # combinations are reported separately in its measured block.
    identity = entry.identity.model_copy(update={"layer_flags": {
        **entry.identity.layer_flags, "dopamine_A": True, "transporter_C": True}})
    return entry.model_copy(update={"identity": identity})


SUITE = {
    "0.1": test_0_1,
    "0.2": test_0_2,
    "0.3": test_0_3,
    "0.3b": test_0_3b,
    "0.4": test_0_4,
    "0.7": test_0_7,
}


# WP4 entries are additive; the WP1 engine suites above are unchanged.
def test_0_6_lite() -> ValidationEntry:
    """Replay both production experiments twice; Hz/ticks, exact recorded tables.

    The intended run-bound check is development evidence until the named stubs
    are replaced, as required by SPEC section 7's development override.
    """
    from flyonenomics.orchestrator.verification import check_replay
    from flyonenomics.schema import load_experiment
    measured = check_replay(REPO / "runs" / "validation-0.6-lite", n_workers=1)
    experiment = load_experiment(REPO / "data/experiments/sugar-reflex.json")
    experiment.seeds = experiment.seeds[:1]
    identity = build_identity(REPO, connectome_version="783", layers=experiment.layers,
                              assay="sugar_reflex,spontaneous", protocol_hash=measured["sugar-reflex"]["protocol_hash"])
    return ValidationEntry(test_id="0.6-lite", category="verification", outcome="passed", compatibility="development",
                           identity=identity, measured={"intended_class": "run-bound", "experiments": measured},
                           stub="IdentityBehaviour", data_dependencies=["params-v0.1.yaml"])


def test_0_8() -> ValidationEntry:
    """Check worker/arm/live invariance and probe reset; ticks/Hz, every parquet table."""
    from flyonenomics.orchestrator.verification import check_invariance, INVARIANCE_FIXTURE
    from flyonenomics.schema import Experiment
    from flyonenomics.schema.experiment import Probe
    import os
    from flyonenomics.orchestrator.verification import replay_invariance_evidence
    evidence = os.environ.get("FLYONENOMICS_INVARIANCE_EVIDENCE")
    measured = (replay_invariance_evidence(Path(evidence)) if evidence else
                check_invariance(REPO / "runs" / "validation-0.8"))
    fixture = read_json(REPO / INVARIANCE_FIXTURE)
    experiment = Experiment.model_validate(fixture["experiment"])
    assays = sorted({p.assay for arm in experiment.arms for p in arm.expanded() if isinstance(p, Probe)})
    identity = build_identity(REPO, connectome_version="783", layers=experiment.layers,
                              assay=",".join(assays), fixture=INVARIANCE_FIXTURE, protocol_hash=experiment.protocol_hash())
    runs = measured.get("runs") or []
    if not runs or any(not isinstance(row.get("stubs"), list) for row in runs):
        raise ValueError("0.8 class needs the stubs list of every executed manifest")
    stubs = sorted({name for row in runs for name in row["stubs"]})
    compatibility = "development" if stubs else "canonical"
    return ValidationEntry(test_id="0.8", category="verification", outcome="passed", compatibility=compatibility,
                           identity=identity, measured={"intended_class": "canonical", **measured},
                           stub=stubs[0] if stubs else None, fixture_path=INVARIANCE_FIXTURE,
                           data_dependencies=["params-v0.1.yaml", "receptors-v0.1.yaml", "dopamine-v0.1.yaml",
                                              "compartments-v0.1.yaml", "populations-v0.1.yaml", "behaviour-v0.1.yaml"])


def test_0_9() -> ValidationEntry:
    """Exercise the four compatibility cases; units none, constructed identity blocks."""
    from flyonenomics.validation.binding import is_compatible
    fixture_path = "tests/fixtures/experiments/binding.json"
    fixture = read_json(REPO / fixture_path)
    identity = build_identity(REPO, connectome_version="783", layers=LayerFlags(), assay="binding", fixture=fixture_path,
                              protocol_hash="acceptance")
    bare = identity.model_copy(update={"connectome_version":"630", "layer_flags": {**identity.layer_flags, "background":False}, "protocol_hash":"bare"})
    canonical = ValidationEntry(test_id="0.3", category="empirical replay", identity=bare, fixture_path=fixture_path)
    off = identity.model_copy(update={"layer_flags":{**identity.layer_flags,"dopamine_A":False}})
    matching = ValidationEntry(test_id="4.3", category="verification", identity=off, compatibility="matching-layers", fixture_path=fixture_path)
    different = identity.model_copy(update={"protocol_hash":"different"})
    bound = ValidationEntry(test_id="0.6", category="verification", identity=different, compatibility="run-bound")
    entries = [canonical, matching, bound]
    outcomes = [is_compatible(entry, identity, repo=REPO)[0] for entry in entries]
    changed = identity.model_copy(update={"uv_lock_hash":"changed"})
    # Each class must be compatible before changing only uv.lock. Reusing
    # the deliberately mismatched cases above would make two checks vacuous.
    controls = [canonical, matching.model_copy(update={"identity": identity}),
                bound.model_copy(update={"identity": identity})]
    lock_baseline = [is_compatible(entry, identity, repo=REPO)[0] for entry in controls]
    lock_drift = [is_compatible(entry, changed, repo=REPO)[0] for entry in controls]
    passed = outcomes == fixture["compatible"] and all(lock_baseline) and not any(lock_drift)
    return ValidationEntry(test_id="0.9", category="verification", outcome="passed" if passed else "failed", compatibility="canonical",
                           identity=identity, fixture_path=fixture_path,
                           measured={"bare_v630_for_v783": outcomes[0], "layers_off_for_on": outcomes[1], "other_protocol": outcomes[2],
                                     "uv_lock_baseline": lock_baseline, "uv_lock_drift":lock_drift})


SUITE.update({"0.6-lite": test_0_6_lite, "0.8": test_0_8, "0.9": test_0_9})


def test_0_5() -> ValidationEntry:
    """Compare five-second Euler pools against SciPy on fixed spike impulses; µM (3,)."""
    from scipy.integrate import solve_ivp
    from scipy.sparse import csr_matrix
    from scipy.optimize import brentq
    from flyonenomics.neuromod.pools import euler_step, fixed_point, tonic_source
    params = load_params()
    dt_s = params.get("engine.chunk_ms") / 1000
    steps = round(POOL_REF_DURATION_S / dt_s)
    m = csr_matrix(np.eye(3, dtype=np.float32))
    mask = np.ones(3, dtype=bool)
    # Three independently checked states: wild type, fumin, MPH at Ki brain µM.
    vmax0 = np.full(3, params.get("da.Vmax"))
    km0 = np.full(3, params.get("da.Km"))
    vmax = vmax0 * np.array([1, 0, 1])
    km = km0 * np.array([1, 1, 2])
    k_ns = params.get("da.k_ns")
    source = tonic_source(params.get("da.DA_ref"), vmax0, km0, k_ns, mask)
    alpha = np.full(3, params.get("da.alpha_max"))
    analytic = fixed_point(source, vmax, km, k_ns)
    numeric = np.array([brentq(lambda x: vmax[c] * x / (km[c] + x) + k_ns * x - source[c],
                               0, source[c] / k_ns + params.get("da.DA_ref"), xtol=1e-14)
                        for c in range(3)])
    euler = analytic.copy()
    reference = numeric.copy()
    maximum = np.zeros(3)
    for step in range(steps):
        counts = np.array([step % POOL_SPIKE_PERIOD_CHUNKS[c % len(POOL_SPIKE_PERIOD_CHUNKS)] == 0
                           for c in range(3)], dtype=np.int32)
        euler = euler_step(euler, counts, dt_s, m, mask, alpha, 1.0,
                           vmax, km, k_ns, params.get("da.DA_ref"), source)
        reference += alpha * counts
        solved = solve_ivp(lambda _t, y: source - vmax * y / (km + y) - k_ns * y,
                           (0, dt_s), reference, rtol=1e-11, atol=1e-13)
        reference = solved.y[:, -1]
        maximum = np.maximum(maximum, np.abs(euler - reference) / np.maximum(reference, np.finfo(float).tiny))
    root_error = float(np.max(np.abs(analytic - numeric)))
    fixture = "tests/fixtures/engine/fixture-0-7.json"
    identity = build_identity(REPO, connectome_version="783", layers=LayerFlags(background=False),
                              assay="pool_integrator", fixture=fixture)
    passed = bool(np.max(maximum) < 0.01 and root_error < 1e-9 and
                  analytic[1] > analytic[0] and analytic[2] > analytic[0])
    return ValidationEntry(test_id="0.5", category="verification", outcome="passed" if passed else "failed",
                           compatibility="canonical", identity=identity, fixture_path=fixture,
                           data_dependencies=["params-v0.1.yaml"],
                           measured={"duration_s": POOL_REF_DURATION_S,
                                     "states": ["wild_type", "fumin", "methylphenidate_at_Ki"],
                                     "reference": "SciPy solve_ivp between exact impulses, including tonic source",
                                     "final_euler_um": euler.tolist(), "final_reference_um": reference.tolist(),
                                     "max_relative_error": float(np.max(maximum)), "per_state_max_relative_error": maximum.tolist(),
                                     "fixed_points_um": analytic.tolist(), "numeric_roots_um": numeric.tolist(),
                                     "max_fixed_point_error_um": root_error})


SUITE["0.5"] = test_0_5
