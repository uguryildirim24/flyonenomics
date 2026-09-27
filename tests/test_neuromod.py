"""Constructed numerical and layer-identity checks for WP5."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
import yaml
from hypothesis import given, strategies as st
from scipy.integrate import solve_ivp
from scipy.optimize import brentq
from scipy.sparse import csr_matrix

from flyonenomics.neuromod.pools import euler_step, fixed_point, tonic_source
from flyonenomics.neuromod.drugs import NotImplementedInPhase1, check_drug
from flyonenomics.neuromod.calibration import ChunkQualification, _plain, bare_rate_safety, bitwise_equal, measure_3_1b, modulation_discrepancy, reflex_rule, release_constants, run_k1
from flyonenomics.neuromod import calibration as calibration_module
from flyonenomics.neuromod.state import Neuromod
from flyonenomics.neuromod.pk import SECONDS_PER_HOUR
from flyonenomics.validation.level3 import ablation_contrasts, depletion_response, paired_prediction, sensitivity_grid
from flyonenomics.registry.receptors import ReceptorMap
from flyonenomics.schema.experiment import ScaleDat, ScaleReceptor, Silence
from flyonenomics.types import LayerFlags, load_params

# SPEC 7.2 test 3.5 and section 6.3: fixed food concentration and wait.
DEPLETION_FOOD_MM = 3.0
DOSE_WAIT_HOURS = 2


@dataclass
class Pop:
    idx: np.ndarray


@dataclass
class Comp:
    name: str


class Registry:
    n = 4

    def __init__(self, exposure: csr_matrix | None = None) -> None:
        self._w = exposure if exposure is not None else csr_matrix(np.array([[1, 0], [0, 1], [0, 0], [0, 1]], dtype=np.float32))
        self._m = csr_matrix(np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32))

    def exposure(self) -> csr_matrix:
        return self._w

    def innervation(self) -> csr_matrix:
        return self._m

    def exposed_mask(self) -> np.ndarray:
        return np.asarray(self._w.getnnz(axis=1) > 0)

    def receptors(self) -> ReceptorMap:
        return ReceptorMap(np.array([1, 0.5, 1, 1], dtype=np.float32),
                           np.array([0.5, 1, 1, 0], dtype=np.float32), np.zeros(4, dtype=np.float32), "fixture")

    def compartments(self) -> list[Comp]:
        return [Comp("a"), Comp("b")]

    def population(self, name: str) -> Pop:
        return Pop(np.array([0, 1], dtype=np.int32))


class Engine:
    def set_threshold(self, values: np.ndarray) -> None:
        self.threshold = values.copy()

    def set_gain(self, values: np.ndarray) -> None:
        self.gain = values.copy()

    def disconnect(self, idx: np.ndarray) -> None:
        self.disconnected = idx.copy()


@given(st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False))
def test_zero_exposure_is_identity_at_any_da(value: float) -> None:
    mod = Neuromod(Registry(csr_matrix((4, 2), dtype=np.float32)), load_params(), LayerFlags())
    mod.da_c.fill(value)
    composed = mod.compose()
    assert np.array_equal(composed.v_th, np.full(4, load_params().get("lif.v_th")))
    assert np.array_equal(composed.gain, np.ones(4))


def test_all_layer_flag_combinations_and_clamp() -> None:
    for dopamine_a, transporter_c, fast in product((False, True), (False, True), ("retain", "disconnect")):
        flags = LayerFlags(dopamine_A=dopamine_a, transporter_C=transporter_c, dan_fast_synapses=fast)
        mod = Neuromod(Registry(), load_params(), flags, {"alpha_c": [0.01, 0.02], "R_c": [1, 2]})
        engine = Engine()
        mod.apply_genotype([], engine)
        if fast == "disconnect":
            assert len(engine.disconnected) == 2
        mod.clamp_pools(True)
        mod.reset_fast()
        assert np.array_equal(mod.da_c, np.full(2, mod.da_ref))
        clamped = mod.compose()
        mod.clamp_pools(False)
        mod.da_c.fill(mod.da_ref)
        free_at_reference = mod.compose()
        np.testing.assert_array_equal(clamped.v_th, free_at_reference.v_th)
        np.testing.assert_array_equal(clamped.gain, free_at_reference.gain)
        mod.clamp_pools(True)
        mod.on_chunk(np.array([10, 10, 0, 0], dtype=np.int32), 0.01)
        assert np.array_equal(mod.da_c, np.full(2, mod.da_ref))
        if not dopamine_a:
            assert np.array_equal(mod.compose().v_th, np.full(4, load_params().get("lif.v_th")))
            assert np.array_equal(mod.compose().gain, np.ones(4))
        if not transporter_c:
            assert np.array_equal(mod.state().Km_eff, mod.km0)
            assert np.array_equal(mod.state().rel, np.ones(2))


def test_d1_null_removes_exact_tonic_term() -> None:
    params = load_params()
    for da in (0, params.get("da.DA_ref"), 5 * params.get("da.DA_ref")):
        wild = Neuromod(Registry(), params, LayerFlags())
        null = Neuromod(Registry(), params, LayerFlags())
        null.apply_genotype([ScaleReceptor(type="scale_receptor", receptor="D1", population="all", factor=0)], Engine())
        wild.da_c.fill(da)
        null.da_c.fill(da)
        wt_v, wt_g = wild.compose().v_th, wild.compose().gain
        null_v, null_g = null.compose().v_th, null.compose().gain
        occ = da / (da + params.get("rec.Kd_D1"))
        expected_v = -params.get("rec.dV_D1") * wild.r1 * occ * wild.exposed
        expected_g = params.get("rec.gamma_D1") * wild.r1 * occ * wild.exposed
        np.testing.assert_allclose(wt_v - null_v, expected_v, atol=1e-13)
        np.testing.assert_allclose(wt_g - null_g, expected_g, atol=1e-13)
        if da == params.get("da.DA_ref"):
            assert np.any(wt_v != null_v)
        off_wt = Neuromod(Registry(), params, LayerFlags(dopamine_A=False))
        off_null = Neuromod(Registry(), params, LayerFlags(dopamine_A=False))
        off_null.r1.fill(0)  # Constructed 3.7 identity; schema forbids a scale_receptor hook with A off.
        off_wt.da_c.fill(da)
        off_null.da_c.fill(da)
        np.testing.assert_array_equal(off_wt.compose().v_th, off_null.compose().v_th)
        np.testing.assert_array_equal(off_wt.compose().gain, off_null.compose().gain)


def test_fixed_point_matches_numerical_root() -> None:
    params = load_params()
    for dat_factor, mph_um, release_factor in product((0, 1), (0, params.get("drug.mph.Ki")), (0.5, 1.0)):
        mod = Neuromod(Registry(), params, LayerFlags(), {"alpha_c": [0.01, 0.02], "R_c": [1, 2]})
        mod.dat_geno.fill(dat_factor)
        mod.slow.concentrations["methylphenidate"] = mph_um
        mod.rel_geno = release_factor
        analytical = mod.fixed_point()
        vmax, km, rel = mod._kinetics()
        for i in range(2):
            source = rel * (mod.alpha[i] * mod.r_tonic[i] + mod.tonic_source[i])
            numeric = brentq(lambda x: vmax[i] * x / (km[i] + x) + mod.k_ns * x - source, 0, 10)
            assert abs(analytical[i] - numeric) < 1e-9


def test_silenced_dan_compartment_has_zero_fixed_point() -> None:
    params = load_params()
    mod = Neuromod(Registry(), params, LayerFlags(), {"alpha_c": [0.01, 0.02], "R_c": [1, 2]})
    assert np.all(mod.fixed_point() > 0)
    mod.apply_genotype([Silence(type="silence", population="DAN")], Engine())
    np.testing.assert_array_equal(mod.fixed_point(), np.zeros(2))


def test_tonic_source_rest_and_partial_dan_silencing() -> None:
    params = load_params()
    registry = Registry()
    registry._m = csr_matrix(np.array([[0.5, 0.5, 0, 0], [0, 0, 0, 0]], dtype=np.float32))
    registry.population = lambda name: Pop(np.array([0], dtype=np.int32))
    mod = Neuromod(registry, params, LayerFlags(), {"R_c": [0, 0], "alpha_c": [params.get("da.alpha_max")] * 2})
    expected = tonic_source(mod.da_ref, mod.vmax0, mod.km0, mod.k_ns, mod.mask)
    np.testing.assert_array_equal(mod.tonic_source, expected)
    assert expected[1] == 0
    np.testing.assert_allclose(mod.fixed_point(), [mod.da_ref, mod.da_ref], atol=1e-12)
    mod.apply_genotype([Silence(type="silence", population="DAN")], Engine())
    assert mod._retained_dan_fraction()[0] == 0.5
    assert 0 < mod.fixed_point()[0] < mod.da_ref
    mod.reset_fast()
    before = mod.da_c.copy()
    mod.on_chunk(np.zeros(4, dtype=np.int32), params.get("engine.chunk_ms") / 1000)
    np.testing.assert_allclose(mod.da_c, before, atol=1e-8)


def test_pool_euler_against_scipy_spike_train() -> None:
    params = load_params()
    dt = params.get("engine.chunk_ms") / 1000
    duration = 5.0
    n = round(duration / dt)
    counts = np.zeros((n, 4), dtype=np.int32)
    counts[::17, 0] = 1
    counts[::23, 1] = 1
    reg = Registry()
    mask = np.array([True, True])
    alpha = np.full(2, params.get("da.alpha_max"))
    vmax = np.array([params.get("da.Vmax")] * 2)
    km = np.array([params.get("da.Km")] * 2)
    k_ns = params.get("da.k_ns")
    da = np.array([params.get("da.DA_ref")] * 2)
    ref = da.copy()
    for row in counts:
        da = euler_step(da, row, dt, reg.innervation(), mask, alpha, 1, vmax, km, k_ns, da[0])
        impulse = alpha * np.asarray(reg.innervation() @ row).ravel()
        ref += impulse
        for i in range(2):
            solution = solve_ivp(lambda _t, y: -vmax[i] * y / (km[i] + y) - k_ns * y,
                                 (0, dt), [ref[i]], rtol=1e-11, atol=1e-13)
            ref[i] = solution.y[0, -1]
    assert np.all(np.abs(da - ref) / np.maximum(ref, 1e-9) < 0.01)


def test_pool_euler_with_tonic_source_against_reference() -> None:
    params = load_params()
    dt = params.get("engine.chunk_ms") / 1000
    n = round(5.0 / dt)
    registry = Registry()
    mask = np.array([True, True])
    vmax = np.full(2, params.get("da.Vmax"))
    km = np.full(2, params.get("da.Km"))
    source = tonic_source(params.get("da.DA_ref"), vmax, km, params.get("da.k_ns"), mask)
    alpha = np.full(2, params.get("da.alpha_max"))
    da = np.full(2, params.get("da.DA_ref"))
    ref = da.copy()
    for step in range(n):
        counts = np.array([int(step % 17 == 0), int(step % 23 == 0), 0, 0], dtype=np.int32)
        da = euler_step(da, counts, dt, registry.innervation(), mask, alpha, 1.0,
                        vmax, km, params.get("da.k_ns"), params.get("da.DA_ref"), source)
        ref += alpha * np.asarray(registry.innervation() @ counts).ravel()
        for i in range(2):
            solution = solve_ivp(lambda _t, y: source[i] - vmax[i] * y / (km[i] + y) - params.get("da.k_ns") * y,
                                 (0, dt), [ref[i]], rtol=1e-11, atol=1e-13)
            ref[i] = solution.y[0, -1]
    assert np.all(np.abs(da - ref) / np.maximum(ref, 1e-9) < 0.01)


def test_absolute_tonic_effect_and_uninnervated_hold() -> None:
    params = load_params()
    mod = Neuromod(Registry(), params, LayerFlags())
    mod.da_c.fill(params.get("da.DA_ref"))
    dv, gain, occ1, occ2 = mod.receptor_terms()
    assert occ1[0] == params.get("da.DA_ref") / (params.get("da.DA_ref") + params.get("rec.Kd_D1"))
    assert occ2[0] == params.get("da.DA_ref") / (params.get("da.DA_ref") + params.get("rec.Kd_D2"))
    assert dv[0] != 0 and gain[0] != 1
    assert dv[2] == 0 and gain[2] == 1
    m = csr_matrix(np.array([[1, 0, 0, 0], [0, 0, 0, 0]], dtype=np.float32))
    next_da = euler_step(np.array([0.1, 5.0]), np.array([1, 0, 0, 0], dtype=np.int32), 0.01,
                         m, np.array([True, False]), np.array([0.01, 0.01]), 1.0,
                         np.full(2, params.get("da.Vmax")), np.full(2, params.get("da.Km")),
                         params.get("da.k_ns"), params.get("da.DA_ref"))
    assert next_da[1] == params.get("da.DA_ref")


def test_drug_and_genotype_identities() -> None:
    params = load_params()
    wt = Neuromod(Registry(), params, LayerFlags(), {"alpha_c": [0.01, 0.01], "R_c": [2, 2]})
    fumin = Neuromod(Registry(), params, LayerFlags(), {"alpha_c": [0.01, 0.01], "R_c": [2, 2]})
    fumin.apply_genotype([ScaleDat(type="scale_dat", compartments="all", factor=0)], Engine())
    assert np.all(fumin.fixed_point() > wt.fixed_point())
    before = fumin.fixed_point().copy()
    fumin.slow.concentrations["methylphenidate"] = 1
    np.testing.assert_array_equal(fumin.fixed_point(), before)
    wt.slow.concentrations["methylphenidate"] = 1
    assert np.all(wt.fixed_point() > before * 0)
    assert np.all(wt.fixed_point() > Neuromod(Registry(), params, LayerFlags(), {"alpha_c": [0.01, 0.01], "R_c": [2, 2]}).fixed_point())
    off = Neuromod(Registry(), params, LayerFlags(transporter_C=False))
    off.slow.concentrations["methylphenidate"] = 1
    np.testing.assert_array_equal(off.state().Km_eff, off.km0)
    for drug in ("amphetamine", "atomoxetine", "caffeine", "cocaine"):
        try:
            check_drug(drug)
        except NotImplementedInPhase1:
            pass
        else:
            raise AssertionError(drug)


def test_two_drugs_compose_and_transport_layer_off_is_identity() -> None:
    params = load_params()
    mod = Neuromod(Registry(), params, LayerFlags())
    mod.start_dose("methylphenidate", params.get("dose.mph.default"))
    mod.start_dose("3-iodotyrosine", DEPLETION_FOOD_MM)
    mod.advance_slow(DOSE_WAIT_HOURS * SECONDS_PER_HOUR)
    state = mod.state()
    assert np.all(state.Km_eff > mod.km0)
    assert np.all(state.rel < 1)
    assert state.concentrations["methylphenidate"] > 0
    assert state.concentrations["3-iodotyrosine"] > 0
    off = Neuromod(Registry(), params, LayerFlags(transporter_C=False))
    off.advance_slow(DOSE_WAIT_HOURS * SECONDS_PER_HOUR)
    np.testing.assert_array_equal(off.state().Km_eff, off.km0)
    np.testing.assert_array_equal(off.state().rel, np.ones(2))


def test_settle_window_and_tick_on_constructed_engine() -> None:
    from types import SimpleNamespace
    mod = Neuromod(Registry(), load_params(), LayerFlags())
    mod.clamp_pools(True)
    mod.reset_fast()
    class FakeEngine(Engine):
        ticks = 0
        dt_ms = 0.1
        def run_chunk(self, ms: float) -> Any:
            self.ticks += round(ms / self.dt_ms)
            return SimpleNamespace(counts=np.zeros(4, dtype=np.int32))
        def tick(self) -> int:
            return self.ticks
    engine = FakeEngine()
    record = mod.settle(engine, lambda: None, [Pop(np.array([0, 1], dtype=np.int32))])
    assert record.converged and record.settle_s == load_params().get("settle.min_s")
    assert record.record_start_tick == engine.tick()
    np.testing.assert_array_equal(record.final_da_c, record.fixed_point_da_c)
    assert record.final_rates_hz.shape == (1,)


def test_unsettled_max_duration_and_tonic_fixed_point() -> None:
    from types import SimpleNamespace
    params = load_params()
    mod = Neuromod(Registry(), params, LayerFlags())
    np.testing.assert_allclose(mod.fixed_point(), np.full(2, params.get("da.DA_ref")), atol=1e-12)
    class FakeEngine(Engine):
        ticks = 0
        dt_ms = 0.1
        def run_chunk(self, ms: float) -> Any:
            self.ticks += round(ms / self.dt_ms)
            return SimpleNamespace(counts=np.array([1, 1, 0, 0], dtype=np.int32))
        def tick(self) -> int:
            return self.ticks
    engine = FakeEngine()
    mod.reset_fast()
    record = mod.settle(engine, lambda: None, [Pop(np.array([0, 1], dtype=np.int32))])
    assert not record.converged
    assert record.settle_s == params.get("settle.max_s")
    assert record.record_start_tick == engine.tick()
    try:
        Neuromod(Registry(), params, LayerFlags(), {"qualified": True, "alpha_c": [], "R_c": []})
    except ValueError:
        pass
    else:
        raise AssertionError("malformed qualified table accepted")


def test_ablation_contrasts_on_constructed_cells() -> None:
    values = {(False, "disconnect"): 1.0, (False, "retain"): 2.0,
              (True, "disconnect"): 3.0, (True, "retain"): 5.0}
    cells = {}
    for (pools, fast), difference in values.items():
        cells[(pools, fast, "wt")] = {1: 10.0, 2: 20.0}
        cells[(pools, fast, "fumin")] = {1: 10.0 + difference, 2: 20.0 + difference}
    result = ablation_contrasts(cells, (1, 2), 100, np.random.default_rng(2))
    assert result["pools_main"]["mean"] == 2.5
    assert result["fast_main"]["mean"] == 1.5
    assert result["interaction"]["mean"] == 1.0
    assert result["interaction"]["ci95"] == [1.0, 1.0]


def test_k2_balance_and_q_modulation_bounds() -> None:
    params = load_params()
    rates = np.array([0.0, params.get("da.R_min"), 2.0])
    alpha, under = release_constants(rates, params)
    assert under.tolist() == [True, False, False]
    assert alpha[0] == params.get("da.alpha_max")
    balance = params.get("da.DA_ref") * (params.get("da.Vmax") / (params.get("da.Km") + params.get("da.DA_ref")) + params.get("da.k_ns"))
    np.testing.assert_allclose(alpha[1:] * rates[1:], balance)
    tonic_dv = np.array([-0.03, 0.6])
    tonic_gain = np.array([1.006, 0.91])
    good = modulation_discrepancy(np.full(3, params.get("da.DA_ref")), tonic_dv, tonic_gain,
                                  tonic_dv, tonic_gain, np.array([True, True, True]),
                                  np.array([True, True]), params)
    assert good["passed"]
    bad = modulation_discrepancy(np.array([0.05, 0.02, 0.02]), tonic_dv, tonic_gain,
                                 tonic_dv, tonic_gain, np.array([True, True, True]),
                                 np.array([True, True]), params)
    assert not bad["passed"] and bad["max_da_error_um"] > bad["da_bound_um"]


def test_level3_saved_table_analysis_without_engine(tmp_path: Any, monkeypatch: Any) -> None:
    import json
    import pandas as pd
    from flyonenomics.validation import level3
    manifest = {"compartments": ["a", "b"], "uninnervated_compartments": [],
                "stubs": ["IdentityBehaviour"], "dopamine_qualified": False}
    dose_values = {"vehicle": [0.02, 0.02, 0.02], "mph": [0.03, 0.04, 0.05],
                   "fumin": [0.08, 0.08, 0.08], "fumin-mph": [0.08, 0.08, 0.08]}
    for arm, values in dose_values.items():
        for seed in (1, 2, 3):
            directory = tmp_path / f"arm-{arm}" / f"seed-{seed}"
            directory.mkdir(parents=True)
            for probe, da in zip((2, 7, 12), values, strict=True):
                pd.DataFrame({"a": [da, da], "b": [da, da]}).to_parquet(directory / f"probe-{probe}-dopamine.parquet")
    monkeypatch.setattr(level3, "_completed_run", lambda _fixture: (tmp_path, manifest))
    dose = level3.test_3_3()
    null = level3.test_3_4()
    assert dose.outcome == "passed" and dose.compatibility == "development"
    assert null.outcome == "passed" and null.measured["ci95_um"] == [0.0, 0.0]
    for seed in (1, 2, 3):
        pd.DataFrame({"a": [0.01], "b": [0.01]}).to_parquet(
            tmp_path / "arm-mph" / f"seed-{seed}" / "probe-12-dopamine.parquet")
        pd.DataFrame({"a": [0.09], "b": [0.09]}).to_parquet(
            tmp_path / "arm-fumin-mph" / f"seed-{seed}" / "probe-7-dopamine.parquet")
    assert level3.test_3_3().outcome == "failed"
    assert level3.test_3_4().outcome == "failed"

    for genotype, da in (("wt", 0.02), ("fumin", 0.08)):
        for seed in range(1, 11):
            directory = tmp_path / f"arm-on-retain-{genotype}" / f"seed-{seed}"
            directory.mkdir(parents=True, exist_ok=True)
            pd.DataFrame({"a": [da], "b": [da]}).to_parquet(directory / "probe-0-dopamine.parquet")
            if genotype == "fumin":
                (directory / "probe-0-settle.json").write_text(json.dumps({"fixed_point_da_c": [da, da]}))
    fumin = level3.test_3_2()
    assert fumin.outcome == "passed" and fumin.compatibility == "development"
    pd.DataFrame({"a": [0.03], "b": [0.03]}).to_parquet(
        tmp_path / "arm-on-retain-fumin" / "seed-1" / "probe-0-dopamine.parquet")
    assert level3.test_3_2().outcome == "failed"
    for genotype in ("wt", "fumin"):
        pd.DataFrame({"a": [0.0], "b": [0.0]}).to_parquet(
            tmp_path / f"arm-on-retain-{genotype}" / "seed-1" / "probe-0-dopamine.parquet")
    assert not level3.test_3_2().measured["per_seed"]["1"]["a"]["at_least_2x"]


def test_3_2_uses_current_tonic_dose_series(tmp_path: Any, monkeypatch: Any) -> None:
    import json
    import pandas as pd
    from flyonenomics.validation import level3
    manifest = {"compartments": ["a", "b"], "uninnervated_compartments": [],
                "stubs": ["IdentityBehaviour"], "dopamine_qualified": False,
                "da.tonic_source": [0.002, 0.002]}
    for seed in (1, 2, 3):
        for arm, value in (("vehicle", 0.02), ("fumin", 0.06)):
            directory = tmp_path / f"arm-{arm}" / f"seed-{seed}"
            directory.mkdir(parents=True, exist_ok=True)
            pd.DataFrame({"a": [value], "b": [value]}).to_parquet(directory / "probe-2-dopamine.parquet")
            if arm == "fumin":
                (directory / "probe-2-settle.json").write_text(json.dumps({"fixed_point_da_c": [value, value]}))
    monkeypatch.setattr(level3, "_completed_run", lambda fixture: (tmp_path, manifest))
    result = level3.test_3_2()
    assert result.outcome == "passed" and result.compatibility == "development"
    assert result.fixture_path == level3.DOSE_FIXTURE


def test_level3_depletion_prediction_and_sensitivity_plan() -> None:
    vehicle = {"wild_type": np.array([0.02, 0.021]), "fumin": np.array([0.08, 0.075])}
    treated = {"wild_type": np.array([0.01, 0.015]), "fumin": np.array([0.04, 0.05])}
    assert depletion_response(vehicle, treated)["passed"]
    treated["fumin"][0] = 0.09
    assert not depletion_response(vehicle, treated)["passed"]
    prediction = paired_prediction(np.array([1.0, 2.0, 3.0]), 100, np.random.default_rng(5))
    assert prediction["mean_hz"] == 2.0
    assert prediction["ci95_hz"][0] <= 2.0 <= prediction["ci95_hz"][1]
    grid = sensitivity_grid(load_params())
    assert len(grid) == 27
    assert len({(row["group"], row["level"]) for row in grid}) == 27
    assert all(row["overrides"] for row in grid)


def test_q_chunkwise_bitwise_and_mean_checks() -> None:
    mod = Neuromod(Registry(), load_params(), LayerFlags())
    mod.clamp_pools(True)
    mod.reset_fast()
    composed = mod.compose()
    accumulator = ChunkQualification(2, 4)
    for _ in range(3):
        accumulator.observe(mod, composed.v_th, composed.gain)
    assert accumulator.summary(mod)["passed"]
    assert not bitwise_equal(np.array([0.0]), np.array([-0.0]))
    changed = composed.v_th.copy()
    changed[0] = np.nextafter(changed[0], np.inf)
    accumulator.observe(mod, changed, composed.gain)
    summary = accumulator.summary(mod)
    assert not summary["passed"] and not summary["per_chunk_arrays_bitwise"]


def test_bare_substrate_k1_skip_and_free_pool_3_1b() -> None:
    from types import SimpleNamespace
    assert run_k1() == {"status": "skipped", "reason": "item 47: no frozen drive on the bare substrate"}
    mod = Neuromod(Registry(), load_params(), LayerFlags(background=False))
    mod.reset_fast()
    class FakeEngine:
        _neu = SimpleNamespace(v_th_i=np.zeros(4), gain_i=np.ones(4))
        def run_chunk(self, ms: int) -> Any:
            return SimpleNamespace(counts=np.zeros(4, dtype=np.int32))
        def set_threshold(self, values: np.ndarray) -> None:
            self._neu.v_th_i = values.copy()
        def set_gain(self, values: np.ndarray) -> None:
            self._neu.gain_i = values.copy()
        def thresholds_mv(self) -> np.ndarray:
            return self._neu.v_th_i.copy()
        def gains(self) -> np.ndarray:
            return self._neu.gain_i.copy()
    result = measure_3_1b(FakeEngine(), mod, load_params().get("engine.chunk_ms") / 1000)
    assert result["passed"] and result["per_chunk_arrays_bitwise"]
    np.testing.assert_allclose(result["mean_da_c_um"], np.full(2, mod.da_ref), atol=1e-12)


def test_q_record_accepts_numpy_group_names_and_scalars() -> None:
    import json
    import yaml
    raw = {np.str_("DAN"): {"observed_hz": np.float64(0), "passed": np.bool_(False)},
           "per_seed": {np.int64(1): np.array([0.02, 0.02])}}
    record = _plain(raw)
    assert yaml.safe_load(yaml.safe_dump(record))["DAN"] == {"observed_hz": 0.0, "passed": False}
    assert json.loads(json.dumps(record))["per_seed"]["1"] == [0.02, 0.02]


def test_item_60_bare_rate_safety_has_no_median_floor() -> None:
    silent = np.zeros(100)
    assert bare_rate_safety(silent, True)["passed"]
    assert bare_rate_safety(silent, True)["median_lower_hz"] is None
    assert not bare_rate_safety(np.full(100, 6.0), True)["passed"]
    hot = silent.copy()
    hot[0] = 51.0
    assert not bare_rate_safety(hot, True)["passed"]
    assert not bare_rate_safety(silent, False)["passed"]


def test_item_61_reflex_mean_and_seed_floor() -> None:
    params = load_params()
    measured = np.array([56, 50, 58, 58, 63, 48, 59, 61, 53, 62], dtype=np.float64)
    result = reflex_rule(measured, params)
    assert result["passed"] and result["mean_hz"] == 56.8 and result["minimum_hz"] == 48
    below_floor = measured.copy()
    below_floor[5] = 39
    assert not reflex_rule(below_floor, params)["passed"]
    low_mean = np.full(10, 50.0)
    assert not reflex_rule(low_mean, params)["passed"]


def test_item_61_rescores_saved_q_without_discarding_diagnostics(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.setattr(calibration_module, "REPO", tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    path = data / "dopamine-v0.1.yaml"
    values = [56, 50, 58, 58, 63, 48, 59, 61, 53, 62]
    rows = {seed: {"difference_hz": value, "silent": {"settled": True},
                   "sugar": {"settled": True}} for seed, value in enumerate(values)}
    path.write_text(yaml.safe_dump({"qualified": False, "qualification": {
        "status": "failed", "3.1b": {"passed": True}, "2.2": {"passed": True},
        "1.4": {"passed": False, "per_seed": rows},
        "escalation": {"Fano": {"F": 2.2}}}}))
    first = calibration_module.requalify_item_61()
    second = calibration_module.requalify_item_61()
    saved = yaml.safe_load(path.read_text())
    assert first == second
    assert saved["qualified"] and saved["qualification"]["status"] == "passed"
    assert saved["qualification"]["1.4"]["previous_rule"]["failed_seeds"] == [1, 5]
    assert saved["qualification"]["diagnostics"]["Fano"]["F"] == 2.2
    assert "SPEC item 60" in saved["qualification_rule"] and "SPEC item 61" in saved["qualification_rule"]


def test_manifest_names_real_neuromod_and_qualified_data() -> None:
    from types import SimpleNamespace
    from flyonenomics.orchestrator.runner import _manifest
    from flyonenomics.schema import load_experiment
    experiment = load_experiment("data/experiments/dose-series.json")
    reg = SimpleNamespace(compartments=lambda: [Comp("a"), Comp("b")], provenance_record={},
                          innervation=lambda: csr_matrix(np.array([[1, 0], [0, 0]], dtype=np.float32)))
    manifest = _manifest(experiment, reg, [], "done", 0.0, 0.0, 0.0, {})
    assert manifest["stubs"] == []
    assert manifest["compatibility"] == "matching-layers"
    assert manifest["dopamine_qualified"] is True
    assert manifest["uninnervated_compartments"] == ["b"]
    for key in ("rec.formulation", "receptor_map_version", "dopamine_version", "drive_version", "pk.kappa", "lif.w_syn"):
        assert key in manifest["free_parameters"]


def test_k2_q_stages_on_fixture_engine(tmp_path, monkeypatch):
    """Exercise real stage loops, writer and replay without building Brian2."""
    from types import SimpleNamespace
    import sys
    from types import ModuleType
    import flyonenomics.registry as registry_module
    import flyonenomics.orchestrator.workers as workers_module
    import flyonenomics.drive.background as drive_module
    params = load_params()
    registry = Registry()
    registry.population = lambda name: Pop(np.array([3] if name == "MN9" else [0, 1], dtype=np.int32))
    class StageEngine(Engine):
        n = 4
        dt_ms = 0.1
        ticks = 0
        active = False
        chunks = 0
        def seed(self, seed):
            pass
        def build(self, *args):
            self.chunks = 0
        def restore(self, name):
            self.ticks = 0
            self.active = False
        def compose_refractory(self):
            pass
        def set_input_rates(self, rates):
            self.active = bool(np.any(rates))
        def run_chunk(self, ms):
            self.ticks += round(ms / self.dt_ms)
            self.chunks += 1
            # MN9 is not a DAN: 60 Hz response with constant source-only pools.
            counts = np.array([0, 0, 0, int(self.active and self.chunks % 5 < 3)], dtype=np.int32)
            return SimpleNamespace(counts=counts, hist_1ms=np.zeros(round(ms), dtype=np.int32))
        def thresholds_mv(self):
            return self.threshold.copy()
        def gains(self):
            return self.gain.copy()
        def tick(self):
            return self.ticks
    engine_package = ModuleType("flyonenomics.engine")
    engine_package.__path__ = []
    engine_base = ModuleType("flyonenomics.engine.base")
    engine_base.InputTopology = lambda **kwargs: SimpleNamespace(**kwargs)
    engine_module = ModuleType("flyonenomics.engine.brian_engine")
    engine_module.BrianEngine = StageEngine
    monkeypatch.setitem(sys.modules, "flyonenomics.engine", engine_package)
    monkeypatch.setitem(sys.modules, "flyonenomics.engine.base", engine_base)
    monkeypatch.setitem(sys.modules, "flyonenomics.engine.brian_engine", engine_module)
    monkeypatch.setattr(registry_module, "build_registry", lambda version: registry)
    monkeypatch.setattr(workers_module, "connectome_files", lambda version: None)
    monkeypatch.setattr(drive_module, "group_indices", lambda reg: {np.str_("DAN"): np.array([0, 1])})
    monkeypatch.setattr(calibration_module, "REPO", tmp_path)
    (tmp_path / "data").mkdir()
    stages = []
    def isolated(name):
        stages.append(name)
        return getattr(calibration_module, name)()
    monkeypatch.setattr(calibration_module, "_isolated_stage", isolated)
    # Tiny fixture cannot satisfy the whole-brain high-rate fraction; failure
    # must still write every bound and prevent a successful stage replay.
    result = calibration_module.run_k2()
    assert stages == ["measure_k2", "run_q"]
    assert result["status"] == "failed"
    path = tmp_path / "data/dopamine-v0.1.yaml"
    record = yaml.safe_load(path.read_text())
    assert record["per_seed_R_c"] == {seed: [0.0, 0.0] for seed in (1, 2, 3)}
    assert record["alpha_c"] == [params.get("da.alpha_max")] * 2
    assert record["date"] and record["receptor_map_version"] == "fixture"
    assert record["qualification"]["3.1b"]["passed"]
    assert record["qualification"]["windows_s"]["3.1b"] == 10
    assert len(record["qualification"]["1.4"]["per_seed"]) == 10
    assert "DAN" in record["qualification"]["escalation"]["free_pool_rates_per_group"]
    assert calibration_module.run_k2()["status"] == "failed"
    assert stages == ["measure_k2", "run_q"]
    before = path.read_bytes()
    failed_refresh = calibration_module.run_q(refresh_3_1b=True)
    assert not failed_refresh["record_refreshed"] and path.read_bytes() == before


def test_record_writer_numpy_keys_and_atomic_failure(tmp_path, monkeypatch):
    import pytest
    from pathlib import Path
    path = tmp_path / "dopamine.yaml"
    record = {np.str_("DAN"): {np.int64(2): np.float64(1.25)}, "qualified": np.bool_(False)}
    calibration_module.write_record(path, record)
    assert yaml.safe_load(path.read_text()) == {"DAN": {2: 1.25}, "qualified": False}
    before = path.read_bytes()
    def fail_replace(self, destination):
        raise OSError("interrupted")
    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted"):
        calibration_module.write_record(path, {"new": True})
    assert path.read_bytes() == before
    assert not path.with_suffix(".yaml.tmp").exists()


@given(st.floats(min_value=0, max_value=1e10, allow_nan=False, allow_infinity=False))
def test_fixed_point_stable_over_release_range(source):
    params = load_params()
    source = np.array([source, source])
    vmax = np.array([params.get("da.Vmax"), 0])
    km = np.full(2, params.get("da.Km"))
    root = fixed_point(source, vmax, km, params.get("da.k_ns"))
    np.testing.assert_allclose(vmax * root / (km + root) + params.get("da.k_ns") * root,
                               source, rtol=1e-13, atol=1e-14)
    assert np.all(np.isfinite(root)) and np.all(root >= 0)


def test_rejects_misordered_or_nonphysical_calibration_arrays():
    import pytest
    params = load_params()
    for table in ({'compartments': ['b', 'a']}, {'R_c': [-1, 0]}, {'alpha_c': [float('nan'), 0.1]}):
        with pytest.raises(ValueError):
            Neuromod(Registry(), params, LayerFlags(), table)


@given(st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False),
       st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False))
def test_receptor_monotonicity_and_independent_known_equations(left, right):
    from flyonenomics.neuromod.receptors import receptor_effect
    params = load_params()
    low, high = sorted((left, right))
    exposure = csr_matrix(np.eye(4))
    exposed = np.array([True, True, False, True])
    r1, r2 = np.array([1, 0, 1, 0.0]), np.array([0, 1, 1, 0.0])
    values = []
    for da in (low, high):
        dv, gain, o1, o2 = receptor_effect(np.full(4, da), exposure, exposed, r1, r2, params)
        assert dv[2] == dv[3] == 0 and gain[2] == gain[3] == 1
        np.testing.assert_allclose(dv[0], -params.get("rec.dV_D1") * da / (da + params.get("rec.Kd_D1")))
        np.testing.assert_allclose(dv[1], params.get("rec.dV_D2") * da / (da + params.get("rec.Kd_D2")))
        values.append((dv, gain))
    assert values[1][0][0] <= values[0][0][0] and values[1][1][0] >= values[0][1][0]
    assert values[1][0][1] >= values[0][0][1] and values[1][1][1] <= values[0][1][1]



def test_pool_single_step_known_value_and_nonnegative_clip():
    next_da = euler_step(np.array([2.0, 0.0, 99.0]), np.array([3, 2], dtype=np.int32), 0.01,
        csr_matrix([[0.5, 0.5], [1., 0.], [0., 0.]]), np.array([True, True, False]),
        np.array([0.2, 0.1, 0.1]), 0.5, np.array([0.3, 0.2, 0.1]),
        np.ones(3), 0.1, 0.02, np.array([0.4, 0.2, 0.]))
    np.testing.assert_allclose(next_da, [2 + 0.5 * (0.004 + 0.2 * 2.5) - (0.3 * 2 / 3 + 0.1 * 2) * 0.01,
                                       0.5 * (0.002 + 0.1 * 3), 0.02])
    clipped = euler_step(np.array([1.]), np.array([0], dtype=np.int32), 1., csr_matrix([[1.]]),
        np.array([True]), np.array([0.1]), 1., np.array([100.]), np.array([1.]), 1., 0.02)
    assert clipped[0] == 0



def test_analytic_washout_keeps_exact_equation_and_resets_next_dose():
    import math
    params = load_params()
    mod = Neuromod(Registry(), params, LayerFlags())
    mod.start_dose("methylphenidate", 0.1)
    mod.advance_slow(2 * SECONDS_PER_HOUR)
    before = mod.slow.concentrations["methylphenidate"]
    mod.stop_dose("methylphenidate")
    mod.advance_slow(100 * SECONDS_PER_HOUR)
    residual = before * math.exp(-params.get("pk.k_e") * 100)
    assert mod.slow.concentrations["methylphenidate"] == residual
    assert "methylphenidate" not in mod.slow.food
    assert residual < 1e-14
    mod.start_dose("methylphenidate", 0.5)
    mod.advance_slow(2 * SECONDS_PER_HOUR)
    expected = residual + (params.get("pk.kappa") * 1000 * 0.5 - residual) * -math.expm1(-params.get("pk.k_a") * 2)
    assert mod.slow.concentrations["methylphenidate"] == expected


def test_frozen_q_gate_rescores_all_ten_values_and_ignores_historical_diagnostics(tmp_path, monkeypatch):
    path = tmp_path / "data/dopamine-v0.1.yaml"
    path.parent.mkdir()
    monkeypatch.setattr(calibration_module, "REPO", tmp_path)
    rows = {seed: {"difference_hz": 60., "silent": {"settled": True}, "sugar": {"settled": True}} for seed in range(10)}
    record = {"qualified": True, "qualification": {"status": "passed", "3.1b": {"passed": True},
              "2.2": {"passed": True}, "1.4": {"passed": True, "per_seed": rows},
              "diagnostics": {"qualified": False, "status": "failed"}}}
    calibration_module.write_record(path, record)
    assert calibration_module.run_k2()["status"] == "passed"
    rows[5]["difference_hz"] = 39
    calibration_module.write_record(path, record)
    assert calibration_module.run_k2()["status"] == "failed"
    rows.pop(5)
    calibration_module.write_record(path, record)
    assert calibration_module.run_k2()["status"] == "failed"


def test_unexecuted_protocol_builders_are_schema_valid_and_matched():
    from flyonenomics.neuromod.protocols import depletion_protocol, prediction_protocols, sensitivity_protocols
    depletion = depletion_protocol()
    assert len(depletion.arms) == 4 and len(depletion.seeds) == 3
    for arm in depletion.arms:
        assert arm.protocol[0].c_food_mm == 3
        assert arm.protocol[0].drug == ("3-iodotyrosine" if "3iy" in arm.label else "vehicle")
        assert arm.protocol[2].assay == "buridan"
    predictions = prediction_protocols()
    for experiment in predictions.values():
        assert experiment.seeds == list(range(10)) and experiment.record.rates == ["DN_all"]
        assert not experiment.layers.background
    assert predictions["pam"].arms[1].genotype.manipulations[0].rate_hz == 50
    sweep = sensitivity_protocols(load_params())
    assert len(sweep) == 27
    assert all(len(experiment.seeds) == 3 for experiment, overrides in sweep)
    assert all(overrides for experiment, overrides in sweep)


def test_saved_run_requires_current_inputs_and_settled_probes(tmp_path, monkeypatch):
    import json
    from flyonenomics.validation import level3
    from flyonenomics.validation.binding import sha256_file
    from flyonenomics.schema import load_experiment
    source = calibration_module.REPO
    experiment = load_experiment(source / level3.DOSE_FIXTURE).model_dump(mode="json")
    (tmp_path / "data/experiments").mkdir(parents=True)
    (tmp_path / level3.DOSE_FIXTURE).write_text(json.dumps(experiment))
    names = ["params", "receptors", "dopamine", "compartments", "populations"]
    for name in names:
        (tmp_path / f"data/{name}-v0.1.yaml").write_bytes((source / f"data/{name}-v0.1.yaml").read_bytes())
    run = tmp_path / "runs/candidate"
    run.mkdir(parents=True)
    (run / "experiment.json").write_text(json.dumps(experiment))
    manifest = {"state": "done", "unsettled": [], "checksums": {
        f"{name}-v0.1.yaml": sha256_file(tmp_path / f"data/{name}-v0.1.yaml") for name in names}}
    path = run / "manifest.json"
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(level3, "REPO", tmp_path)
    assert level3._completed_run(level3.DOSE_FIXTURE)[0] == run
    manifest["unsettled"] = [{"probe": 2}]
    path.write_text(json.dumps(manifest))
    assert level3._completed_run(level3.DOSE_FIXTURE) is None
    manifest["unsettled"] = []
    manifest["checksums"]["receptors-v0.1.yaml"] = "old"
    path.write_text(json.dumps(manifest))
    assert level3._completed_run(level3.DOSE_FIXTURE) is None


def test_behaviour_factory_and_stub_inventory_share_fallback(monkeypatch):
    import pytest
    from types import SimpleNamespace
    from flyonenomics.orchestrator import components
    def missing(name):
        raise ModuleNotFoundError(name=name)
    monkeypatch.setattr(components.importlib, "import_module", missing)
    plan = SimpleNamespace(topology=SimpleNamespace(extended_idx=np.array([0])))
    assert type(components.make_behaviour(plan, None, load_params(), None)).__name__ == "IdentityBehaviour"
    assert components.active_stubs(["buridan"]) == ["IdentityBehaviour"]
    def dependency_missing(name):
        raise ModuleNotFoundError(name="required_dependency")
    monkeypatch.setattr(components.importlib, "import_module", dependency_missing)
    with pytest.raises(ModuleNotFoundError):
        components.active_stubs(["buridan"])


def _assert_full_0_7_procedure_summary_serializes(monkeypatch):
    import json
    from types import SimpleNamespace
    from flyonenomics.validation import level0
    class FixtureEngine(Engine):
        n = 3
        def build(self, *args): pass
        def seed(self, value): pass
        def restore(self, name): pass
        def set_upstream_active(self, bank, active): pass
        def compose_refractory(self): pass
        def run_chunk(self, ms):
            return SimpleNamespace(counts=np.array([1, 0, 0], dtype=np.int32))
        def thresholds_mv(self):
            return self.threshold.copy()
    monkeypatch.setitem(level0.__dict__, "BrianEngine", FixtureEngine)
    monkeypatch.setitem(level0.__dict__, "InputTopology", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setitem(level0.__dict__, "UpstreamBank", lambda **kwargs: SimpleNamespace(**kwargs))
    monkeypatch.setattr(level0, "read_fixture", lambda name: {"sugar_roots": [10, 11], "mn9_root": 12,
        "seed": 2, "rate_hz": 150, "shift_mv": 3, "chunks": 200, "chunk_ms": 10})
    monkeypatch.setattr(level0, "root_lookup", lambda version: {10: 0, 11: 1, 12: 2})
    monkeypatch.setattr(level0, "connectome", lambda version: None)
    result = level0._measure_0_7()
    decoded = json.loads(json.dumps(result))
    assert decoded["outcome"] == "passed"
    assert decoded["measured"]["threshold_shift_readback_exact"] is True
    assert decoded["measured"]["neuromod_flag_combinations"] == 8
    monkeypatch.setattr(level0, "run_isolated", lambda *args: result)
    identity = level0.test_0_7().identity.layer_flags
    assert identity["dopamine_A"] and identity["transporter_C"] and not identity["background"]


def test_full_0_7_procedure_summary_serializes_on_fixture_engine():
    import subprocess
    import sys
    from pathlib import Path
    code = "import runpy, pytest; ns=runpy.run_path('tests/test_neuromod.py'); mp=pytest.MonkeyPatch(); ns['_assert_full_0_7_procedure_summary_serializes'](mp); mp.undo()"
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_known_genotype_drug_composition_and_clip_precedence():
    from flyonenomics.schema.experiment import ScaleGain, ScaleRelease, ShiftThreshold
    mod = Neuromod(Registry(), load_params(), LayerFlags())
    mod.apply_genotype([
        ShiftThreshold(type="shift_threshold", population="DAN", delta_mv=3),
        ScaleGain(type="scale_gain", population="DAN", factor=2),
        ScaleRelease(type="scale_release", factor=0.5),
        ScaleDat(type="scale_dat", compartments=["a"], factor=2),
    ], Engine())
    mod.da_c[:] = [1., 0.]
    mod.slow.concentrations.update({"methylphenidate": 0.2, "3-iodotyrosine": 10.})
    composed = mod.compose()
    # At neuron 0, occupancy is 1/2 (D1) and 20/21 (D2),
    # yielding dV=17/84 mV and receptor gain 141/140.
    np.testing.assert_allclose(composed.v_th, [-42 + 17/84, -42, -45, -45], rtol=0, atol=1e-13)
    np.testing.assert_allclose(composed.gain, [141/70, 2, 1, 1], rtol=0, atol=1e-13)
    vmax, km, rel = mod._kinetics()
    np.testing.assert_array_equal(vmax, [0.22, 0.11])
    np.testing.assert_array_equal(km, [2.6, 2.6])
    assert rel == 0.25
    mod.shift[0] = 20
    mod.shift[2] = -20
    mod.geno_gain[0] = 10
    mod.geno_gain[2] = 0.1
    mod.silenced[1] = True
    clipped = mod.compose()
    np.testing.assert_array_equal(clipped.v_th, [-30, 1e6, -52, -45])
    np.testing.assert_array_equal(clipped.gain, [3, 2, 0.2, 1])
