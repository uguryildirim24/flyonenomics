"""Level 1 reflex suites on v630 (WP1) and provisional v783 (WP3).

Units and array shapes follow the engine docstrings. Tests 1.0, 1.0b,
1.1 on v630, 1.2, and 1.3 live here. The v783 variants of 1.1 and test
1.4 (background on, base arrays, no neuromodulation) are WP3 development
checks; the free-pool qualification belongs to WP5.

Isolation rule: every suite measurement runs in a fresh subprocess
that builds at most one engine (see level0.run_isolated). The suite
functions below never build engines and never call seed or restore.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import numpy as np

from flyonenomics.io import read_parquet, read_yaml
from flyonenomics.types import load_params
from flyonenomics.engine import BrianEngine, InputTopology, UpstreamBank
from flyonenomics.engine.brian_engine import cache_dir
from flyonenomics.validation.level0 import (
    connectome,
    make_entry,
    prepare,
    read_fixture,
    root_lookup,
    run_chunks,
    run_isolated,
)
from flyonenomics.drive.background import DEFAULT_SEED, _connection_signs, background_weights, load_drive, weight_scale
from flyonenomics.orchestrator.seeds import brian_seed as _brian_seed
from flyonenomics.registry import build_registry
from flyonenomics.types import LayerFlags
from flyonenomics.validation.binding import ValidationEntry, build_identity, sha256_file

ARCHIVE_DIRNAME = "shiu-archive"


def archive_dir() -> Path:
    """Return the Shiu results archive directory.

    Units: none. Shapes: a single path. Lane w1 fetches the archive
    into $FLYONENOMICS_CACHE_DIR/shiu-archive; test 1.2 looks there.
    """
    return cache_dir() / ARCHIVE_DIRNAME


def two_bank_inputs() -> tuple[np.ndarray, np.ndarray, int, dict[str, Any]]:
    """Return sugar indices, bitter indices, MN9 index, and the fixture.

    Units: Hz for rates in the fixture. Shapes: index arrays with
    shape (21,) each. No engine is built here.
    """
    fix = read_fixture("fixture-1-0.json")
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in fix["sugar_roots"]], dtype=np.int32)
    bitter = np.array([lookup[r] for r in fix["bitter_roots"]], dtype=np.int32)
    return sugar, bitter, lookup[int(fix["mn9_root"])], fix


def _measure_1_0() -> dict[str, Any]:
    """Bank switching: none silent, sugar drives, bitter halves, restore
    repeats. Units: Hz and engine ticks. Shapes: full tables over 1 s.
    One engine with sugar and bitter banks."""
    sugar, bitter, mn9, fix = two_bank_inputs()
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    engine.build(
        connectome("630"),
        load_params(),
        InputTopology(
            upstream_banks=[
                UpstreamBank(idx=sugar, rate_hz=float(fix["sugar_rate_hz"])),
                UpstreamBank(idx=bitter, rate_hz=float(fix["bitter_rate_hz"])),
            ]
        ),
    )
    seed = int(fix["seed"])
    duration = float(fix["duration_ms"])

    refractory_checks: list[bool] = []

    def leg(active: list[bool]) -> Any:
        prepare(engine)
        for bank, flag in enumerate(active):
            engine.set_upstream_active(bank, flag)
        engine.compose_refractory()
        refractory_checks.append(rfc_ok(active))
        engine.seed(seed)
        run_chunks(engine, duration)
        return engine.spikes(0)

    def rfc_ok(active: list[bool]) -> bool:
        base_ms = float(load_params().get("lif.t_rfc"))
        rfc = engine.refractory_ms()
        expected = np.full(engine.n, base_ms)
        for flag, idx in zip(active, (sugar, bitter)):
            if flag:
                expected[idx] = 0.0
        return bool(np.array_equal(rfc, expected))

    none = leg([False, False])
    none_ok = int((none.idx == mn9).sum()) == 0 and rfc_ok([False, False])
    sug = leg([True, False])
    sug_mn9 = int((sug.idx == mn9).sum())
    sug_ok = sug_mn9 > float(read_fixture("fixture-1-1.json")["min_mn9_hz"]) and rfc_ok([True, False])
    both = leg([True, True])
    both_mn9 = int((both.idx == mn9).sum())
    reduction_ok = both_mn9 < float(read_fixture("fixture-1-3.json")["max_fraction"]) * sug_mn9
    again = leg([True, False])
    repeat_ok = bool(
        np.array_equal(again.idx, sug.idx) and np.array_equal(again.tick, sug.tick)
    )
    outcome = (
        "passed" if none_ok and sug_ok and reduction_ok and repeat_ok and all(refractory_checks) else "failed"
    )
    return {
        "measured": {
            "mn9_spikes_none": int((none.idx == mn9).sum()),
            "mn9_spikes_sugar": sug_mn9,
            "mn9_spikes_sugar_bitter": both_mn9,
            "reduction_fraction": (both_mn9 / sug_mn9) if sug_mn9 else None,
            "repeat_identical": repeat_ok,
            "rfc_composed": all(refractory_checks),
            "refractory_checks": refractory_checks,
        },
        "outcome": outcome,
    }


def test_1_0() -> ValidationEntry:
    """Bank switching: none silent, sugar drives, bitter halves, restore
    repeats. Units: Hz and engine ticks. Shapes: full tables over 1 s."""
    result = run_isolated("level1", "_measure_1_0")
    return make_entry(
        "1.0",
        "verification",
        "630",
        "sugar_reflex",
        "fixture-1-0.json",
        result["measured"],
        result["outcome"],
    )


def _measure_1_0b() -> dict[str, Any]:
    """Mixed-mode history invariance on the extended path. Units: Hz and
    engine ticks. Shapes: full tables over 1 s per probe. One engine;
    the fixture calls engine.seed directly, bypassing the production
    derivation."""
    fix = read_fixture("fixture-1-0b.json")
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in fix["sugar_roots"]], dtype=np.int32)
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    engine.build(
        connectome("630"),
        load_params(),
        InputTopology(
            upstream_banks=[
                UpstreamBank(idx=sugar, rate_hz=float(load_params().get("input.r_poi")))
            ],
            extended_idx=np.sort(sugar),
        ),
    )
    rate = float(fix["extended_rate_hz"])
    duration = float(fix["duration_ms"])

    def rfc_ok(active: list[bool]) -> bool:
        base_ms = float(load_params().get("lif.t_rfc"))
        rfc = engine.refractory_ms()
        expected = np.full(engine.n, base_ms)
        for flag, idx in zip(active, (sugar,)):
            if flag:
                expected[idx] = 0.0
        return bool(np.array_equal(rfc, expected))

    refractory_checks: list[bool] = []

    def probe(extended: bool) -> Any:
        prepare(engine)
        engine.set_upstream_active(0, not extended)
        engine.compose_refractory()
        refractory_checks.append(rfc_ok([not extended]))
        engine.seed(int(fix["seed"]))
        engine.set_input_rates(
            np.full(sugar.shape[0], rate) if extended else np.zeros(sugar.shape[0])
        )
        run_chunks(engine, duration)
        return engine.spikes(0)

    def key(table: Any) -> tuple[bytes, bytes]:
        return (table.idx.tobytes(), table.tick.tobytes())

    e_last = [key(probe(True))]
    for history in (("U", "E"), ("E", "U", "E")):
        last: tuple[bytes, bytes] | None = None
        for mode in history:
            last = key(probe(mode == "E"))
        assert last is not None
        e_last.append(last)
    u_last = [key(probe(False))]
    for history in (("E", "U"), ("U", "E", "U")):
        last = None
        for mode in history:
            last = key(probe(mode == "E"))
        assert last is not None
        u_last.append(last)
    e_ok = all(run == e_last[0] for run in e_last)
    u_ok = all(run == u_last[0] for run in u_last)
    outcome = "passed" if e_ok and u_ok and all(refractory_checks) else "failed"
    return {
        "measured": {
            "refractory_checks": refractory_checks,
            "extended_histories_identical": e_ok,
            "upstream_histories_identical": u_ok,
            "n_extended_histories": 3,
            "n_upstream_histories": 3,
            "seed_bypass": "engine.seed called directly per SPEC 3.1",
        },
        "outcome": outcome,
    }


def test_1_0b() -> ValidationEntry:
    """Mixed-mode history invariance on the extended path. Units: Hz and
    engine ticks. Shapes: full tables over 1 s per probe."""
    result = run_isolated("level1", "_measure_1_0b")
    return make_entry(
        "1.0b",
        "verification",
        "630",
        "sugar_reflex",
        "fixture-1-0b.json",
        result["measured"],
        result["outcome"],
    )


def _measure_1_1() -> dict[str, Any]:
    """Sugar drives MN9 above 50 Hz; MN9 is silent without input. Units:
    Hz. Shapes: full tables over 1 s. One bare engine with a sugar bank."""
    fix = read_fixture("fixture-1-1.json")
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

    def leg(active: bool) -> Any:
        prepare(engine)
        engine.set_upstream_active(0, active)
        engine.compose_refractory()
        engine.seed(int(fix["seed"]))
        run_chunks(engine, float(fix["duration_ms"]))
        return engine.spikes(0)

    driven = leg(True)
    driven_mn9 = int((driven.idx == mn9).sum())
    silent = leg(False)
    silent_mn9 = int((silent.idx == mn9).sum())
    outcome = (
        "passed"
        if driven_mn9 > float(fix["min_mn9_hz"]) and silent_mn9 == 0
        else "failed"
    )
    return {
        "measured": {
            "mn9_hz_sugar": float(driven_mn9) / (float(fix["duration_ms"]) / 1000.0),
            "mn9_spikes_sugar": driven_mn9,
            "mn9_spikes_silent": silent_mn9,
            "total_spikes_silent": int(silent.tick.shape[0]),
            "required_mn9_hz": fix["min_mn9_hz"],
        },
        "outcome": outcome,
    }


def test_1_1() -> ValidationEntry:
    """Sugar drives MN9 above 50 Hz; MN9 is silent without input. Units:
    Hz. Shapes: full tables over 1 s."""
    result = run_isolated("level1", "_measure_1_1")
    upstream = run_isolated("level1", "_measure_1_1_v783_upstream")
    extended = run_isolated("level1", "_measure_1_1_v783_extended")
    measured = {"v630_upstream": result["measured"],
                "v783_upstream": upstream["measured"],
                "v783_extended": extended["measured"]}
    outcome = "passed" if all(leg["outcome"] == "passed" for leg in (result, upstream, extended)) else "failed"
    return make_entry(
        "1.1",
        "consistency",
        "630",
        "sugar_reflex",
        "fixture-1-1.json",
        measured,
        outcome,
    )


def _measure_1_1_v783_upstream() -> dict[str, Any]:
    """v783 upstream sugar and silent legs; units Hz; shape two one-second probes."""
    registry = build_registry("783")
    sugar = registry.population("sugar_GRN_R").idx
    mn9 = int(registry.population("MN9").idx[0])
    params = load_params()
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params, InputTopology(
        upstream_banks=[UpstreamBank(idx=sugar, rate_hz=float(params.get("input.r_poi")))]))
    def leg(active: bool) -> int:
        engine.restore("initial")
        engine.set_upstream_active(0, active)
        engine.compose_refractory()
        engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
        return sum(int(engine.run_chunk(float(params.get("engine.chunk_ms"))).counts[mn9])
                   for _ in range(round(1000 / float(params.get("engine.chunk_ms")))))
    silent, driven = leg(False), leg(True)
    return {"measured": {"mn9_hz_silent": silent, "mn9_hz_sugar": driven},
            "outcome": "passed" if silent == 0 and driven > 50 else "failed"}


def _measure_1_1_v783_extended() -> dict[str, Any]:
    """v783 extended sugar and silent legs; units Hz; shape two one-second probes."""
    registry = build_registry("783")
    sugar = np.sort(registry.population("sugar_GRN_R").idx)
    mn9 = int(registry.population("MN9").idx[0])
    params = load_params()
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params, InputTopology(extended_idx=sugar))
    def leg(active: bool) -> int:
        engine.restore("initial")
        engine.set_input_rates(np.full(sugar.size, float(params.get("input.r_poi")) if active else 0.0))
        engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
        return sum(int(engine.run_chunk(float(params.get("engine.chunk_ms"))).counts[mn9])
                   for _ in range(round(1000 / float(params.get("engine.chunk_ms")))))
    silent, driven = leg(False), leg(True)
    return {"measured": {"mn9_hz_silent": silent, "mn9_hz_sugar": driven},
            "outcome": "passed" if silent == 0 and driven > 50 else "failed"}


def _measure_1_4() -> dict[str, Any]:
    """Ten paired v783 sugar differences on provisional drive; units Hz, shape (10,)."""
    registry = build_registry("783")
    sugar = np.sort(registry.population("sugar_GRN_R").idx)
    mn9 = int(registry.population("MN9").idx[0])
    params = load_params()
    engine = BrianEngine()
    engine.seed(_brian_seed(DEFAULT_SEED, 0, 0))
    engine.build(connectome("783"), params, InputTopology(extended_idx=sugar, background=True))
    drive = load_drive()
    weights = background_weights(registry, drive)
    threshold = np.full(engine.n, float(params.get("lif.v_th")))
    gain = np.ones(engine.n)
    if drive.g_inh > 1:
        engine.set_weight_scale(weight_scale(_connection_signs(connectome("783").connectivity), drive.g_inh))
    engine.set_threshold(threshold)
    engine.set_gain(gain)
    engine.set_background(weights)
    engine.store("initial")
    chunk_ms = float(params.get("engine.chunk_ms"))
    differences: list[int] = []
    for s in range(int(params.get("validation.seeds"))):
        pair: list[int] = []
        for active in (False, True):
            engine.restore("initial")
            engine.seed(_brian_seed(DEFAULT_SEED, s, 0))
            engine.set_threshold(threshold)
            engine.set_gain(gain)
            engine.set_background(weights)
            engine.set_input_rates(np.full(sugar.size, float(params.get("input.r_poi")) if active else 0.0))
            pair.append(sum(int(engine.run_chunk(chunk_ms).counts[mn9])
                            for _ in range(round(1000 / chunk_ms))))
        differences.append(pair[1] - pair[0])
    from flyonenomics.neuromod.calibration import reflex_rule
    score = reflex_rule(np.asarray(differences, dtype=np.float64), params)
    return {"measured": {"mn9_difference_hz": differences, **score,
                         "g_inh": drive.g_inh,
                         "seed_ids": list(range(int(params.get("validation.seeds"))))},
            "outcome": "passed" if score["passed"] else "failed"}


def test_1_4() -> ValidationEntry:
    """Record provisional sugar reflex; units Hz; shape ten paired differences."""
    result = run_isolated("level1", "_measure_1_4")
    identity = build_identity(Path(__file__).resolve().parents[3], connectome_version="783",
        layers=LayerFlags(background=True, dopamine_A=False, transporter_C=False),
        assay="sugar_reflex", fixture="tests/fixtures/drive/level1.yaml")
    return ValidationEntry(test_id="1.4", category="consistency", outcome=result["outcome"],
        compatibility="development", identity=identity, measured=result["measured"],
        data_dependencies=["params-v0.1.yaml", "drive-dev.yaml"],
        fixture_path="tests/fixtures/drive/level1.yaml",
        stub="neuromod: none (base arrays, drive-dev)")


BARE_1_4_MEAN_ABOVE_HZ = 50.0  # SPEC 7.2 test 1.4, item 61
BARE_1_4_SEED_FLOOR_HZ = 40.0  # SPEC 7.2 test 1.4, item 61


def test_1_4_bare() -> ValidationEntry:
    """Replay bare-substrate 1.4 from the qualified Q record; Hz, never re-executed."""
    import yaml
    repo = Path(__file__).resolve().parents[3]
    record_path = repo / "data" / "dopamine-v0.1.yaml"
    table = read_yaml(record_path)
    check = (table.get("qualification") or {}).get("1.4")
    checksum = sha256_file(record_path)
    identity = build_identity(repo, connectome_version="783",
        layers=LayerFlags(background=False, dopamine_A=True, transporter_C=True),
        assay="sugar_reflex", fixture="data/dopamine-v0.1.yaml")
    if not isinstance(check, dict):
        return ValidationEntry(test_id="1.4-bare", category="consistency", outcome="unavailable",
            compatibility="canonical", identity=identity,
            measured={"reason": "qualified Q record has no 1.4 block", "record_sha256": checksum},
            data_dependencies=["params-v0.1.yaml", "dopamine-v0.1.yaml"],
            fixture_path="data/dopamine-v0.1.yaml")
    mean_hz = float(check["mean_hz"])
    minimum_hz = float(check["minimum_hz"])
    # Item 61 rule re-evaluated from the record's own values: ten-seed mean above
    # 50 Hz and no seed below 40 Hz; the frozen record must also be qualified.
    rule_holds = mean_hz > BARE_1_4_MEAN_ABOVE_HZ and minimum_hz >= BARE_1_4_SEED_FLOOR_HZ
    passed = table.get("qualified") is True and check.get("passed") is True and rule_holds
    return ValidationEntry(test_id="1.4-bare", category="consistency",
        outcome="passed" if passed else "failed", compatibility="canonical", identity=identity,
        measured={**check, "record_sha256": checksum, "record_qualified": table.get("qualified"),
                  "rule_holds": rule_holds, "replayed": True, "never_reexecuted": True},
        data_dependencies=["params-v0.1.yaml", "dopamine-v0.1.yaml"],
        fixture_path="data/dopamine-v0.1.yaml")


def _measure_1_2() -> dict[str, Any]:
    """Per-neuron sugar rates against the Shiu archive over 30 trials.

    Units: Hz. Shapes: per-neuron rate vectors with shape (n,). The
    archive holds 30-trial spike tables (t in seconds); rates are
    computed with the pinned Shiu utils.get_rate helper.
    Engine trials use seed(trial) for trial in 0..29. One engine."""
    import pandas as pd

    fix = read_fixture("fixture-1-2.json")
    target = archive_dir()
    names = ("sugarR_150Hz.parquet", "sugarR.parquet")
    available = [target / name for name in names if (target / name).is_file()]
    if target / names[0] not in available:
        candidates: list[str] = []
        if target.is_dir():
            for pattern in ("*rate*", "*Rate*", "*.parquet", "*.csv"):
                candidates.extend(sorted(str(p) for p in target.glob(pattern)))
        return {
            "measured": {
                "lookup_dir": str(target),
                "trials": fix["trials"],
                "required_pearson_r": fix["min_pearson_r"],
                "reason": (
                    "Required primary sugarR_150Hz.parquet not present under "
                    "$FLYONENOMICS_CACHE_DIR/shiu-archive; no fetch performed "
                    "(SPEC section 11 item 3)"
                ),
                "candidates_found": candidates,
            },
            "outcome": "unavailable",
        }
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in fix["sugar_roots"]], dtype=np.int32)
    helper_path = cache_dir() / "Drosophila_brain_model" / "utils.py"
    helper_spec = importlib.util.spec_from_file_location("shiu_utils_pinned", helper_path)
    if helper_spec is None or helper_spec.loader is None:
        raise ImportError(f"cannot import Shiu utils.get_rate from {helper_path}")
    helper = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper)
    engine = BrianEngine()
    engine.seed(0)
    engine.build(
        connectome("630"),
        load_params(),
        InputTopology(
            upstream_banks=[UpstreamBank(idx=sugar, rate_hz=float(fix["rate_hz"]))]
        ),
    )
    engine_trials: list[pd.DataFrame] = []
    for trial in range(int(fix["trials"])):
        prepare(engine)
        engine.set_upstream_active(0, True)
        engine.compose_refractory()
        engine.seed(trial)
        run_chunks(engine, float(fix["duration_ms"]))
        spikes = engine.spikes(0)
        engine_trials.append(pd.DataFrame({
            "flywire_id": engine.root_ids[spikes.idx],
            "trial": trial,
            "exp_name": "sugarR_150Hz",
        }))
    engine_rate_table, _ = helper.get_rate(
        pd.concat(engine_trials, ignore_index=True),
        float(fix["duration_ms"]) / 1000.0, int(fix["trials"]),
    )
    engine_rates = engine_rate_table.iloc[:, 0].reindex(engine.root_ids, fill_value=0.0).to_numpy()
    comparisons: dict[str, dict[str, Any]] = {}
    for archive_file in available:
        table = read_parquet(archive_file).to_pandas()
        trials = sorted(int(t) for t in table["trial"].unique().tolist())
        if trials != list(range(int(fix["trials"]))):
            raise ValueError(f"{archive_file.name}: expected trials 0..29, got {trials}")
        rate_table, _ = helper.get_rate(
            table, float(fix["duration_ms"]) / 1000.0, int(fix["trials"])
        )
        archive_rates = np.zeros(engine.n, dtype=np.float64)
        unmapped = 0
        for flywire_id, rate in rate_table.iloc[:, 0].items():
            index = lookup.get(int(flywire_id))
            if index is None:
                unmapped += 1
            else:
                archive_rates[index] = float(rate)
        mask = (archive_rates >= float(fix["min_rate_hz"])) | (
            engine_rates >= float(fix["min_rate_hz"])
        )
        a = archive_rates[mask]
        e = engine_rates[mask]
        pearson_r = float(np.corrcoef(a, e)[0, 1]) if a.shape[0] > 2 else float("nan")
        comparisons[archive_file.name] = {
            "pearson_r": pearson_r,
            "n_neurons_compared": int(mask.sum()),
            "archive_trials": len(trials),
            "archive_unmapped_neurons": unmapped,
            "archive_spikes": int(len(table)),
            "archive_duration_s": float(fix["duration_ms"]) / 1000.0,
        }
    selected = "sugarR_150Hz.parquet"
    pearson_r = float(comparisons[selected]["pearson_r"])
    outcome = (
        "passed"
        if np.isfinite(pearson_r) and pearson_r >= float(fix["min_pearson_r"])
        else "failed"
    )
    return {
        "measured": {
            "pearson_r": pearson_r,
            "required_pearson_r": fix["min_pearson_r"],
            "n_neurons_compared": comparisons[selected]["n_neurons_compared"],
            "n_trials": int(fix["trials"]),
            "archive_file": selected,
            "archive_comparisons": comparisons,
            "rate_helper": "pinned Shiu utils.get_rate",
            "trial_seeds": "engine.seed(trial) for trial in 0..29",
        },
        "outcome": outcome,
    }


def test_1_2() -> ValidationEntry:
    """Per-neuron sugar rates against the Shiu archive over 30 trials.

    Units: Hz. Shapes: per-neuron rate vectors. Runs when the archive's
    results sit under $FLYONENOMICS_CACHE_DIR/shiu-archive and records
    unavailable otherwise.
    """
    result = run_isolated("level1", "_measure_1_2")
    return make_entry(
        "1.2",
        "empirical",
        "630",
        "sugar_reflex",
        "fixture-1-2.json",
        result["measured"],
        result["outcome"],
    )


def _measure_1_3() -> dict[str, Any]:
    """Bitter co-activation halves the MN9 rate. Units: Hz. Shapes: full
    tables over 1 s. One engine with sugar and bitter banks."""
    fix = read_fixture("fixture-1-3.json")
    lookup = root_lookup("630")
    sugar = np.array([lookup[r] for r in fix["sugar_roots"]], dtype=np.int32)
    bitter = np.array([lookup[r] for r in fix["bitter_roots"]], dtype=np.int32)
    mn9 = lookup[int(fix["mn9_root"])]
    engine = BrianEngine()
    engine.seed(int(fix["seed"]))
    engine.build(
        connectome("630"),
        load_params(),
        InputTopology(
            upstream_banks=[
                UpstreamBank(idx=sugar, rate_hz=float(fix["sugar_rate_hz"])),
                UpstreamBank(idx=bitter, rate_hz=float(fix["bitter_rate_hz"])),
            ]
        ),
    )
    seed = int(fix["seed"])
    duration = float(fix["duration_ms"])

    def leg(active: list[bool]) -> Any:
        prepare(engine)
        for bank, flag in enumerate(active):
            engine.set_upstream_active(bank, flag)
        engine.compose_refractory()
        engine.seed(seed)
        run_chunks(engine, duration)
        return engine.spikes(0)

    sug = leg([True, False])
    both = leg([True, True])
    sug_mn9 = int((sug.idx == mn9).sum())
    both_mn9 = int((both.idx == mn9).sum())
    fraction = (both_mn9 / sug_mn9) if sug_mn9 else None
    outcome = (
        "passed"
        if sug_mn9 > 0 and fraction is not None and fraction < float(fix["max_fraction"])
        else "failed"
    )
    return {
        "measured": {
            "mn9_spikes_sugar": sug_mn9,
            "mn9_spikes_sugar_bitter": both_mn9,
            "fraction": fraction,
            "max_fraction": fix["max_fraction"],
        },
        "outcome": outcome,
    }


def test_1_3() -> ValidationEntry:
    """Bitter co-activation halves the MN9 rate. Units: Hz. Shapes: full
    tables over 1 s."""
    result = run_isolated("level1", "_measure_1_3")
    return make_entry(
        "1.3",
        "consistency",
        "630",
        "sugar_reflex",
        "fixture-1-3.json",
        result["measured"],
        result["outcome"],
    )


SUITE = {
    "1.0": test_1_0,
    "1.0b": test_1_0b,
    "1.1": test_1_1,
    "1.2": test_1_2,
    "1.3": test_1_3,
    "1.4": test_1_4,
    "1.4-bare": test_1_4_bare,
}
