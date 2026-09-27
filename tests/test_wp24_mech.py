"""WP24 0.15 recording checks and later mechanism tests."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from flyonenomics.io import read_json

ROOT = Path(__file__).resolve().parents[1]
OFF = ROOT / "tests" / "fixtures" / "wp24-off-reference.json"
FIX_016 = ROOT / "tests" / "fixtures" / "engine" / "fixture-0-16.json"
FIX_017 = ROOT / "tests" / "fixtures" / "engine" / "fixture-0-17.json"
FIX_018 = ROOT / "tests" / "fixtures" / "engine" / "fixture-0-18.json"


def test_fixture_0_16_lists() -> None:
    """0.16 spike list matches SPEC-P2 5.3: 100 Hz then 1 kHz trains."""
    fixture = read_json(FIX_016)
    ticks = [100 + 100 * k for k in range(50)] + [6000 + 10 * k for k in range(50)]
    assert fixture["spike_tick"] == ticks
    assert fixture["duration_ticks"] == 8000
    assert fixture["dt_ms"] == 0.1
    assert fixture["spikelist_idx"] == [0]
    assert fixture["trace_idx"] == [0]


def test_build_mechanisms_default_is_none() -> None:
    """build's mechanisms argument defaults to None (SPEC-P2 2.2.4)."""
    import numpy as np

    from flyonenomics.engine import BrianEngine
    from flyonenomics.engine.models import Adaptation, ConductanceInhibition, Depression, Mechanisms, resolve_engine_model

    assert inspect.signature(BrianEngine.build).parameters["mechanisms"].default is None
    assert resolve_engine_model(None) == "lif"
    assert resolve_engine_model(Mechanisms()) == "lif"
    assert resolve_engine_model(
        Mechanisms(adaptation=Adaptation(b_mv=np.zeros(1), tau_ms=np.ones(1)))
    ) == "lif+sfa"
    assert resolve_engine_model(
        Mechanisms(depression=Depression(U=np.zeros(1), tau_ms=np.ones(1)))
    ) == "lif+std"
    assert resolve_engine_model(
        Mechanisms(conductance_inhibition=ConductanceInhibition(E_inh_mv=-62.0))
    ) == "lif+cbi"
    with pytest.raises(TypeError, match="depression"):
        resolve_engine_model(Mechanisms(depression={}))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at most one"):
        resolve_engine_model(Mechanisms(adaptation=Adaptation(b_mv=np.zeros(1), tau_ms=np.ones(1)), depression={}))


def test_0_15_a_lif_strings_and_empty_traces() -> None:
    """0.15 (a): omitted, None, and all-null Mechanisms build lif."""
    from flyonenomics.validation.level0_mech import check_0_15_a

    result = check_0_15_a()
    assert result["passed"], result["mismatches"]


def test_0_15_b_i_matches_off_reference() -> None:
    """Re-run 0.15 (b)(i) against the committed off-path fixture."""
    from flyonenomics.validation.level0_mech import check_0_15_b

    result = check_0_15_b(parts=("i",))
    assert result["passed"], result["mismatches"]


def test_fixture_0_17_lists() -> None:
    """0.17 spike list matches SPEC-P2 5.3: 50 Hz train, gap, five more events."""
    fixture = read_json(FIX_017)
    ticks = [100 + 200 * k for k in range(50)] + [12100 + 200 * k for k in range(5)]
    assert fixture["spike_tick"] == ticks
    assert fixture["duration_ticks"] == 14000
    assert fixture["dt_ms"] == 0.1
    assert fixture["spikelist_idx"] == [0]
    assert fixture["trace_idx"] == [0, 1]


def test_fixture_0_18_lists() -> None:
    """0.18 spike lists match SPEC-P2 5.3 at lif.dt 0.1 ms."""
    fixture = read_json(FIX_018)
    ticks0 = [round((10 + 20 * k) / 0.1) for k in range(50)]
    ticks1 = [round((10 + 12.5 * k) / 0.1) for k in range(80)]
    assert fixture["spike_tick_0"] == ticks0
    assert fixture["spike_tick_1"] == ticks1
    assert fixture["duration_ms"] == 1100
    assert fixture["dt_ms"] == 0.1
    assert fixture["spikelist_idx"] == [0, 1]
    assert fixture["trace_idx"] == [2]


def test_0_16_adaptation_closed_form() -> None:
    """0.16: lif+sfa matches the exact one-tick solution."""
    from flyonenomics.validation.level0_mech import check_0_16

    result = check_0_16()
    assert result["passed"], result


def test_0_17_depression_closed_form() -> None:
    """0.17: lif+std matches the closed form of one depressed connection."""
    from flyonenomics.validation.level0_mech import check_0_17

    result = check_0_17()
    assert result["passed"], result


def test_0_18_cbi_reference() -> None:
    """0.18: lif+cbi matches DOP853 and the 0.1 kernel."""
    from flyonenomics.validation.level0_mech import check_0_18

    result = check_0_18()
    assert result["passed"], result


def test_cbi_h_max_from_state_after_run_chunk() -> None:
    """ChunkResult.h_max is max(h_inh) from neuron state after run_chunk, else None."""
    import numpy as np

    from flyonenomics.validation.level0 import prepare
    from flyonenomics.validation.level0_mech import _cbi_mechanisms, _tiny_018_engine

    lif = _tiny_018_engine()
    prepare(lif)
    assert lif.run_chunk(10.0).h_max is None

    cbi = _tiny_018_engine(mechanisms=_cbi_mechanisms(-62.0))
    prepare(cbi)
    result = cbi.run_chunk(10.0)
    state = np.asarray(cbi._neu.h_inh[:], dtype=np.float64)
    assert result.h_max == float(np.max(state))
    assert result.h_max is not None
    assert result.h_max >= 0.0


@pytest.mark.slow
def test_0_15_b_full_engine_hashes() -> None:
    """Re-run 0.15 (b)(ii) to (iv) against the committed off-path fixture."""
    from flyonenomics.validation.level0_mech import check_0_15_b

    result = check_0_15_b(parts=("ii", "iii", "iv"))
    assert result["passed"], result["mismatches"]
