"""Provisional v783 background dynamics (development class only)."""

from __future__ import annotations

import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

from flyonenomics.drive.background import DEFAULT_SEED, _connection_signs, background_weights, group_indices, load_drive, weight_scale
from flyonenomics.io import read_yaml
from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
if TYPE_CHECKING:
    from flyonenomics.engine import BrianEngine
from flyonenomics.registry import build_registry
from flyonenomics.types import LayerFlags, load_params
from flyonenomics.validation.artefacts import FanoAccumulator, weight_jitter_detector
from flyonenomics.validation.binding import ValidationEntry, build_identity, sha256_file


ROOT = Path(__file__).resolve().parents[3]
STUB = "neuromod: none (base arrays, drive-dev map-level candidate; not a resting calibration)"
FIXTURE = "tests/fixtures/drive/level2.yaml"


@lru_cache(maxsize=2)
def _drive_scale(g_inh: float) -> np.ndarray:
    """Expand the pinned inhibitory ratio in parquet order; float32 (n_syn,)."""
    from flyonenomics.validation.level0 import connectome
    return weight_scale(_connection_signs(connectome("783").connectivity), g_inh)


def _entry(test_id: str, category: str, result: dict[str, Any]) -> ValidationEntry:
    """Wrap provisional result; units per measured key, shapes scalars/mappings."""
    identity = build_identity(ROOT, connectome_version="783",
        layers=LayerFlags(background=True, dopamine_A=False, transporter_C=False),
        assay="spontaneous", fixture=FIXTURE)
    return ValidationEntry(test_id=test_id, category=category, outcome=result["outcome"],
        compatibility="development", identity=identity, measured=result["measured"],
        data_dependencies=["params-v0.1.yaml", "drive-dev.yaml"],
        fixture_path=FIXTURE, stub=STUB)


def _engine(extended_idx: np.ndarray | None = None) -> tuple[BrianEngine, Any, Any]:
    """Build one v783 network; units indices, shape (n_inputs,) and n neurons."""
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.validation.level0 import connectome
    registry = build_registry("783")
    params = load_params()
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params,
                 InputTopology(background=True, extended_idx=extended_idx if extended_idx is not None else np.array([], dtype=np.int32)))
    drive = load_drive()
    if drive.g_inh > 1:
        engine.set_weight_scale(_drive_scale(drive.g_inh))
    engine.set_threshold(np.full(engine.n, float(params.get("lif.v_th"))))
    engine.set_gain(np.ones(engine.n))
    engine.set_background(background_weights(registry, drive))
    engine.store("initial")
    return engine, registry, params


def _prepare(engine: BrianEngine, registry: Any, params: Any, seed_id: int,
             scale: np.ndarray | None = None) -> None:
    """Restore base arrays and drive; units mV, shape (n,), scales (n_syn,)."""
    engine.restore("initial")
    engine.seed(_brian_seed(DEFAULT_SEED, seed_id, 0))
    engine.set_threshold(np.full(engine.n, float(params.get("lif.v_th"))))
    engine.set_gain(np.ones(engine.n))
    engine.set_background(background_weights(registry, load_drive()))
    if scale is not None:
        engine.set_weight_scale(np.asarray(_drive_scale(load_drive().g_inh) * scale, dtype=np.float32))


def _run(engine: BrianEngine, params: Any, seconds: float,
         detector: FanoAccumulator | None = None) -> np.ndarray:
    """Step engine and count spikes; units seconds/neurons, shape (n,)."""
    chunk_ms = float(params.get("engine.chunk_ms"))
    counts = np.zeros(engine.n, dtype=np.int64)
    for _ in range(round(seconds * 1000 / chunk_ms)):
        result = engine.run_chunk(chunk_ms)
        counts += result.counts
        if detector is not None:
            detector.add(result.hist_1ms)
    return counts


def _measure_2_1() -> dict[str, Any]:
    """Fresh 2 s settle and 5 s group-rate check; units Hz, groups mapping."""
    engine, registry, params = _engine()
    drive = load_drive()
    _prepare(engine, registry, params, 0)
    _run(engine, params, float(params.get("settle.min_s")))
    counts = _run(engine, params, 5.0)
    indices = group_indices(registry)
    rates = {name: float(counts[idx].mean() / 5) for name, idx in indices.items()}
    checks = {name: (0.5 * group.target_hz <= rates[name] <= 2 * group.target_hz)
              for name, group in drive.groups.items() if group.target_hz is not None}
    dan_ok = 2 <= rates["DAN"] <= 10
    return {"measured": {"k1_record": {"weights_mv": {n: g.w_bg for n, g in drive.groups.items()},
                                       "rates_hz": {n: g.measured_hz for n, g in drive.groups.items()},
                                       "targets_hz": {n: g.target_hz for n, g in drive.groups.items()},
                                       "objective": drive.objective, "evaluations": drive.evaluation_count,
                                       "g_inh": drive.g_inh},
                         "fresh_rates_hz": rates, "factor_two": checks, "DAN_2_to_10_hz": dan_ok},
            "outcome": "passed" if all(checks.values()) and dan_ok else "failed"}


def _measure_2_2() -> dict[str, Any]:
    """Per-neuron spontaneous distribution over 10 s; units Hz, shape (n,)."""
    engine, registry, params = _engine()
    _prepare(engine, registry, params, 0)
    _run(engine, params, float(params.get("settle.min_s")))
    rates = _run(engine, params, 10.0) / 10.0
    median = float(np.median(rates))
    high = float(np.mean(rates > 50))
    return {"measured": {"median_hz": median, "fraction_above_50_hz": high,
                         "g_inh": load_drive().g_inh,
                         "settle_s": float(params.get("settle.min_s")), "record_s": 10.0,
                         "n_neurons": engine.n,
                         "quantiles_hz": {str(q): float(np.quantile(rates, q))
                                          for q in (0, 0.25, 0.5, 0.75, 0.9, 0.99, 1)}},
            "outcome": "passed" if 0.2 <= median <= 5 and high < 0.01 else "failed"}


def _measure_2_3() -> dict[str, Any]:
    """Synchrony over 10 s; units F and neuron fraction, shape bin stream."""
    engine, registry, params = _engine()
    _prepare(engine, registry, params, 0)
    _run(engine, params, float(params.get("settle.min_s")))
    fano = FanoAccumulator(engine.n, params)
    _run(engine, params, 10.0, fano)
    report = fano.report()
    return {"measured": {**report, "g_inh": load_drive().g_inh,
                         "settle_s": float(params.get("settle.min_s")), "record_s": 10.0,
                         "fano_max": float(params.get("artefact.sync_fano_max")),
                         "bin_fraction_max": float(params.get("artefact.sync_bin_fraction_max"))},
            "outcome": "passed" if report["status"] == "clear" else "failed"}


def _measure_2_4() -> dict[str, Any]:
    """Five jittered paired MN9 and group-rate reruns; units Hz, shape five records."""
    registry = build_registry("783")
    sugar = np.sort(registry.population("sugar_GRN_R").idx)
    engine, registry, params = _engine(sugar)
    indices = group_indices(registry)
    mn9 = int(registry.population("MN9").idx[0])
    rate_hz = float(params.get("input.r_poi"))
    seed_id = 0

    def rerun(scale: np.ndarray) -> dict[str, float]:
        """One paired rerun; units Hz, shape group headline mapping."""
        _prepare(engine, registry, params, seed_id, scale)
        engine.set_input_rates(np.zeros(sugar.size))
        _run(engine, params, float(params.get("settle.min_s")))
        counts = _run(engine, params, 5.0)
        rates = {name: float(counts[idx].mean() / 5) for name, idx in indices.items() if name != "sensory"}
        pair: list[float] = []
        for active in (False, True):
            _prepare(engine, registry, params, seed_id, scale)
            engine.set_input_rates(np.full(sugar.size, rate_hz if active else 0.0))
            pair.append(float(_run(engine, params, 1.0)[mn9]))
        return {"mn9_difference_hz": pair[1] - pair[0], **{f"group.{name}": value for name, value in rates.items()}}

    baseline = rerun(np.ones(engine.n_syn, dtype=np.float32))
    report = weight_jitter_detector(rerun, engine.n_syn, baseline, DEFAULT_SEED, params)
    differences_ok = all(abs(row["mn9_difference_hz"] - baseline["mn9_difference_hz"]) <
                         0.25 * abs(baseline["mn9_difference_hz"]) for row in report["reruns"])
    groups_ok = all((row[key] == 0 if value == 0 else 1 / 1.5 < row[key] / value < 1.5)
                    for row in report["reruns"] for key, value in baseline.items()
                    if key.startswith("group."))
    return {"measured": {**report, "seed_id": seed_id, "g_inh": load_drive().g_inh,
                         "mn9_within_25_percent": differences_ok,
                         "groups_within_factor_1_5": groups_ok},
            "outcome": "passed" if differences_ok and groups_ok and report["status"] == "clear" else "failed"}


def _measure_2_5() -> dict[str, Any]:
    """Cold and warm B1 under real drive; units wall s/brain s, shape two legs."""
    proc = subprocess.run([sys.executable, "scripts/bench.py", "--b1", "--drive", "data/drive-dev.yaml"],
                          cwd=ROOT, text=True, capture_output=True, timeout=3600, check=False)
    if proc.returncode:
        raise RuntimeError(f"B1 failed: {proc.stderr[-2000:]}")
    result = json.loads(proc.stdout)
    q1 = float(result["warm"]["q1"])
    return {"measured": {"B1": result, "q1": q1, "q1_target": 15,
                         "B2": "not measured; WP9"},
            "outcome": "passed" if q1 <= 15 else "failed"}


def test_2_1() -> ValidationEntry:
    """Record development K1 remeasurement; units Hz, groups mapping."""
    from flyonenomics.validation.level0 import run_isolated
    return _entry("2.1", "calibration", run_isolated("level2", "_measure_2_1"))


def test_2_2() -> ValidationEntry:
    """Record development rate distribution; units Hz, scalars."""
    from flyonenomics.validation.level0 import run_isolated
    return _entry("2.2", "consistency", run_isolated("level2", "_measure_2_2"))


BARE_2_2_MEDIAN_MAX_HZ = 5.0  # SPEC 7.2 test 2.2, item 60
BARE_2_2_FRACTION_ABOVE_50_HZ = 0.01  # SPEC 7.2 test 2.2, item 60


def test_2_2_bare() -> ValidationEntry:
    """Replay bare-substrate 2.2 from the qualified Q record; Hz, never re-executed."""
    record_path = ROOT / "data" / "dopamine-v0.1.yaml"
    table = read_yaml(record_path)
    check = (table.get("qualification") or {}).get("2.2")
    checksum = sha256_file(record_path)
    identity = build_identity(ROOT, connectome_version="783",
        layers=LayerFlags(background=False, dopamine_A=True, transporter_C=True),
        assay="sugar_reflex", fixture="data/dopamine-v0.1.yaml")
    if not isinstance(check, dict):
        return ValidationEntry(test_id="2.2-bare", category="consistency", outcome="unavailable",
            compatibility="canonical", identity=identity,
            measured={"reason": "qualified Q record has no 2.2 block", "record_sha256": checksum},
            data_dependencies=["params-v0.1.yaml", "dopamine-v0.1.yaml"],
            fixture_path="data/dopamine-v0.1.yaml")
    median_hz = float(check["median_hz"])
    fraction_above_50 = float(check["fraction_above_50_hz"])
    percent_above_50 = 100.0 * fraction_above_50
    # Item 60 rule re-evaluated from the record's own values: all-neuron median at
    # most 5 Hz and fewer than 1 percent above 50 Hz; the frozen record must be qualified.
    rule_holds = median_hz <= BARE_2_2_MEDIAN_MAX_HZ and fraction_above_50 < BARE_2_2_FRACTION_ABOVE_50_HZ
    passed = table.get("qualified") is True and check.get("passed") is True and rule_holds
    return ValidationEntry(test_id="2.2-bare", category="consistency",
        outcome="passed" if passed else "failed", compatibility="canonical", identity=identity,
        measured={**check, "percent_above_50_hz": percent_above_50, "record_sha256": checksum,
                  "record_qualified": table.get("qualified"), "rule_holds": rule_holds,
                  "replayed": True, "never_reexecuted": True},
        data_dependencies=["params-v0.1.yaml", "dopamine-v0.1.yaml"],
        fixture_path="data/dopamine-v0.1.yaml")


def test_2_3() -> ValidationEntry:
    """Record development synchrony; units dimensionless, scalars."""
    from flyonenomics.validation.level0 import run_isolated
    return _entry("2.3", "consistency", run_isolated("level2", "_measure_2_3"))


def test_2_4() -> ValidationEntry:
    """Record development jitter; units Hz, five mappings."""
    from flyonenomics.validation.level0 import run_isolated
    return _entry("2.4", "consistency", run_isolated("level2", "_measure_2_4"))


def test_2_5() -> ValidationEntry:
    """Record development B1; units wall s/brain s, two mappings."""
    from flyonenomics.validation.level0 import run_isolated
    return _entry("2.5", "consistency", _measure_2_5())


SUITE = {"2.1": test_2_1, "2.2": test_2_2, "2.2-bare": test_2_2_bare, "2.3": test_2_3,
         "2.4": test_2_4, "2.5": test_2_5}
