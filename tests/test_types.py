"""Shared types checks: params rows, dataclasses, strict models."""

import hashlib
import json
import pytest
import yaml
from pathlib import Path

from flyonenomics.types import (
    LayerFlags,
    Params,
    ProvenanceRecord,
    SpikeTable,
    load_params,
)

ROOT = Path(__file__).resolve().parents[1]

# SPEC item 63: exclusions concern SPEC value prose or absent YAML rows,
# never unit checking. Common placeholder values remain pinned exactly here.
PARAMETER_EXCLUSIONS = {
    "lif.g_inh": {
        "kind": "SPEC-only",
        "reason": "Free parameter: drive table and every manifest free-parameter block; default 1.",
    },
    "da.tonic_source": {
        "kind": "SPEC-only",
        "reason": "Derived K2 output: da.tonic_source in frozen dopamine-v0.1.yaml.",
    },
    "vis.r_max": {
        "kind": "SPEC-only",
        "reason": "Params class default until WP9 freezes behaviour-v0.1.yaml.",
    },
    "da.alpha_c": {
        "kind": "derived",
        "reason": "K2 array: alpha_c in frozen dopamine-v0.1.yaml; YAML retains its placeholder.",
        "frozen_value": "calibrated (K2)",
    },
    "bg.w_bg": {
        "kind": "placeholder",
        "reason": "K1 calibration placeholder; current development candidate is in drive-dev.yaml.",
        "frozen_value": "calibrated (K1)",
    },
    "arena.v_fwd": {
        "kind": "placeholder",
        "reason": "Ingestion placeholder; calibration-half speed is in behaviour-dev.yaml pending WP9.",
        "frozen_value": "set at ingestion",
    },
}


def test_params_holds_every_section5_row() -> None:
    """params YAML holds every SPEC section 5 key.

    Units: per key. Shapes: scalars or small lists.
    """
    params = load_params()
    keys = [
        "lif.v_0", "lif.v_rst", "lif.v_th", "lif.t_mbr", "lif.tau",
        "lif.t_rfc", "lif.t_dly", "lif.w_syn", "lif.dt",
        "engine.chunk_ms", "engine.silence_vth",
        "input.r_poi", "input.f_poi", "input.w_in",
        "bg.n_bg", "bg.r_bg",
        "bg.target.central", "bg.target.DAN", "bg.target.KC", "bg.target.ER",
        "bg.target.descending", "bg.target.motor", "bg.target.other",
        "bg.k1_max_evals",
        "settle.min_s", "settle.max_s", "settle.window_s",
        "settle.tol_abs_da", "settle.tol_rel_da",
        "settle.tol_rate", "settle.tol_abs_rate",
        "da.DA_ref", "da.alpha_max", "da.R_min", "da.Km", "da.Vmax", "da.k_ns",
        "rec.Kd_D1", "rec.Kd_D2", "rec.gamma_D1", "rec.gamma_D2",
        "rec.dV_D1", "rec.dV_D2", "rec.gain_clip", "rec.vth_clip",
        "drug.mph.Ki", "drug.3iy.EC50",
        "pk.kappa", "pk.k_a", "pk.k_e",
        "dose.mph.default",
        "arena.R_platform", "arena.R_wall", "arena.stripe_width",
        "arena.stripe_azimuths", "arena.edge_margin", "arena.v_fwd",
        "arena.sigma_h", "arena.sigma_edge",
        "steer.sign_steer", "steer.K_steer", "steer.tau_rate",
        "vis.r_vis_max", "vis.sigma_vis", "vis.pref_range", "vis.inject_at",
        "distractor.azimuth", "distractor.flicker_hz", "distractor.contrast",
        "distractor.onset_s", "distractor.duration_s",
        "buridan.duration_s",
        "openloop.azimuths", "openloop.dwell_s", "openloop.transition_s",
        "metrics.fix_angle", "metrics.resample_hz", "metrics.step_min_mm",
        "metrics.step_max_mm", "metrics.walk_area_fraction",
        "metrics.switch_angle", "metrics.switch_window_s",
        "metrics.min_window_fraction",
        "metrics.cetran_tol_deg", "metrics.cetran_tol_walks",
        "rate_bin_ms",
        "live.every_ms", "live.spike_sample",
        "artefact.sync_bin_ms", "artefact.sync_fano_max",
        "artefact.sync_bin_fraction_max", "artefact.jitter_sigma",
        "artefact.jitter_seeds", "artefact.completeness_min",
        "artefact.encoder_perms",
        "cxdan.min_cx_output_fraction",
        "stats.bootstrap_n", "stats.equivalence_margin",
        "budget_margin",
        "validation.seeds",
        "orchestrator.n_workers",
    ]
    for key in keys:
        row = params.row(key)
        assert {"value", "unit", "source", "range", "level"} <= set(row), key


def test_params_values_match_spec() -> None:
    """Spot values equal the SPEC section 5 table.

    Units: per key. Shapes: scalars.
    """
    params = load_params()
    assert params.get("lif.v_th") == -45
    assert params.get("input.r_poi") == 150
    assert params.get("input.w_in") == 68.75
    assert params.get("da.DA_ref") == 0.02
    assert params.get("pk.kappa") == 0.01
    assert params.get("orchestrator.n_workers") == 4


def test_params_unknown_key_raises() -> None:
    """Unknown dot keys raise KeyError.

    Units: none. Shapes: scalars.
    """
    params = load_params()
    with pytest.raises(KeyError):
        params.get("lif.nope")


def test_layer_flags_defaults() -> None:
    """LayerFlags defaults match the schema defaults.

    Units: none. Shapes: scalars.
    """
    flags = LayerFlags()
    assert (flags.background, flags.dopamine_A, flags.transporter_C) == (False, True, True)
    assert flags.dan_fast_synapses == "retain"
    assert flags.receptor_kinetics_B is False
    assert flags.learning_D is False


def test_strict_model_forbids_unknown_fields() -> None:
    """Pydantic models forbid unknown fields.

    Units: none. Shapes: scalars.
    """
    with pytest.raises(Exception):
        ProvenanceRecord(
            item="x", version="v", source="s", license="l",
            used_for="u", bogus_field=1,
        )


def test_spike_table_shapes() -> None:
    """SpikeTable carries index and tick arrays.

    Units: ticks are engine ticks. Shapes: (n_spikes,) each.
    """
    import numpy as np

    table = SpikeTable(idx=np.zeros(3, dtype=np.int32), tick=np.zeros(3, dtype=np.int64))
    assert table.idx.shape == (3,)
    assert table.tick.shape == (3,)


def _section5_rows() -> dict[str, dict]:
    import re

    section = (ROOT / "docs/SPEC.md").read_text().split("## 5. Parameters", 1)[1].split("## 6.", 1)[0]
    section = section.split("### 5.1", 1)[0]
    rows = {}
    for line in section.splitlines():
        if not line.startswith("| ") or line.startswith("| key |"):
            continue
        keys, values, units, source, sensitivity, level = [x.strip() for x in line.strip("|").split("|")]
        keys = keys.split(", ")
        prefix = keys[0].rsplit(".", 1)[0]
        keys = [key if "." in key else f"{prefix}.{key}" for key in keys] if len(keys) > 1 else keys
        values = [values] if len(keys) == 1 else values.split(", ")
        units = units.split(", ") if len(keys) > 1 and ", " in units else [units] * len(keys)
        for key, value, unit in zip(keys, values, units, strict=True):
            value = value.replace("−", "-").replace("`", "")
            if ".." in value:
                start, end, step = map(int, re.fullmatch(r"(-?\d+)\.\.(-?\d+) step (\d+)", value).groups())
                value = list(range(start, end + 1, step))
            else:
                try:
                    value = float(value)
                except ValueError:
                    value = yaml.safe_load(value)
            rows[key.replace("[group]", "")] = dict(value=value, unit=unit, source=source, range=sensitivity, level=level)
    return rows


def test_frozen_parameter_values_and_units_against_spec() -> None:
    """Compare every common value and unit under the explicit item-63 exclusions."""
    import unicodedata

    def normal(key: str, text: str) -> str:
        text = text.replace("uM", "µM")
        if key.startswith("da."):
            text = text.replace("per spike", "per weighted DAN spike")
        text = text.replace("√s", "sqrt(s)").replace("σ", "sigma").replace("±", "+-").replace("×", "x").replace("°", " deg").replace("`", "")
        return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))

    def flatten(node: dict, prefix: str = "") -> dict:
        out = {}
        for key, value in node.items():
            name = f"{prefix}.{key}" if prefix else key
            if "value" in value:
                out[name] = value
            else:
                out.update(flatten(value, name))
        return out

    expected = _section5_rows()
    actual = flatten(load_params().data)
    spec_only = {key for key, exclusion in PARAMETER_EXCLUSIONS.items()
                 if exclusion["kind"] == "SPEC-only"}
    assert spec_only == {"lif.g_inh", "da.tonic_source", "vis.r_max"}
    assert spec_only.isdisjoint(actual), "item 63 freezes the YAML without these rows"
    assert load_params().get("vis.r_max") == expected["vis.r_max"]["value"]
    assert expected.keys() - actual.keys() == spec_only
    assert actual.keys() == expected.keys() - spec_only
    assert PARAMETER_EXCLUSIONS.keys() <= expected.keys()
    assert all(exclusion["reason"] for exclusion in PARAMETER_EXCLUSIONS.values())
    for key in actual:
        row = expected[key]
        exclusion = PARAMETER_EXCLUSIONS.get(key)
        value = exclusion["frozen_value"] if exclusion else row["value"]
        assert actual[key]["value"] == value, key
        assert normal(key, actual[key]["unit"]) == normal(key, row["unit"]), (key, "unit")
        assert all(actual[key][field] for field in ("unit", "source", "range", "level")), key


def test_seed_identifiers_and_domains() -> None:
    from pydantic import ValidationError
    from flyonenomics import types

    assert [getattr(types, name) for name in ("ENGINE", "BEHAVIOUR", "ENCODER", "JITTER", "LIVE", "ANALYSIS")] == [1, 2, 3, 4, 5, 6]
    for kwargs in ({"S": -1, "s": 0, "k": 0}, {"S": 0, "s": 2**32, "k": 0}, {"S": 0, "s": 0, "k": -1}):
        with pytest.raises(ValidationError):
            types.SeedSpec(**kwargs)


@pytest.mark.parametrize("cls", ["ConnectomeFiles", "LayerFlags", "SeedSpec", "SpikeTable", "ChunkResult", "ComposedParams", "SettleRecord", "Params"])
def test_all_dataclasses_reject_unknown_fields(cls: str) -> None:
    from pydantic import TypeAdapter, ValidationError
    from flyonenomics import types

    with pytest.raises(ValidationError) as error:
        TypeAdapter(getattr(types, cls)).validate_python({"bogus": 1})
    assert any(item["loc"] == ("bogus",) for item in error.value.errors())


@pytest.mark.parametrize("flags", [{"learning_D": True}, {"receptor_kinetics_B": True}, {"dan_fast_synapses": "typo"}])
def test_unsupported_layers_rejected(flags: dict) -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        LayerFlags(**flags)


def test_shared_array_contracts_and_settle_clock() -> None:
    import numpy as np
    from pydantic import ValidationError
    from flyonenomics.types import ChunkResult, ComposedParams, SettleRecord

    with pytest.raises(ValidationError):
        SpikeTable(idx=np.zeros(2, dtype=np.int64), tick=np.zeros(2, dtype=np.int64))
    with pytest.raises(ValidationError):
        SpikeTable(idx=np.zeros(2, dtype=np.int32), tick=np.zeros(1, dtype=np.int64))
    with pytest.raises(ValidationError):
        ChunkResult(tick0=2, tick1=1, counts=np.zeros(1, dtype=np.int32), hist_1ms=np.zeros(1, dtype=np.int32))
    with pytest.raises(ValidationError):
        ComposedParams(v_th=np.zeros(2), gain=np.zeros(3), layers=LayerFlags())
    record = SettleRecord(converged=True, settle_s=2, fixed_point_da_c=np.zeros(2), final_da_c=np.zeros(2), final_rates_hz=np.zeros(3), record_start_tick=20000)
    assert record.record_start_tick == 20000
    assert ComposedParams(v_th=np.zeros(2), gain=np.ones(2), layers=LayerFlags()).layers.dopamine_A


@pytest.mark.parametrize("contents", ["[]", "lif: {}", "version: v0.1\nlif:\n  dt: {value: 0.1}"])
def test_params_rejects_malformed_rows(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(contents)
    with pytest.raises(ValueError):
        load_params(path)


def test_isolated_sensitivity_override_preserves_frozen_params(monkeypatch: pytest.MonkeyPatch) -> None:
    frozen = ROOT / "data/params-v0.1.yaml"
    original_hash = hashlib.sha256(frozen.read_bytes()).hexdigest()
    baseline = load_params().get("rec.Kd_D1")
    monkeypatch.setenv("FLYONENOMICS_PARAM_OVERRIDES_JSON", json.dumps({"rec.Kd_D1": 0.3}))
    assert load_params().get("rec.Kd_D1") == 0.3
    assert load_params(frozen).get("rec.Kd_D1") == baseline
    assert hashlib.sha256(frozen.read_bytes()).hexdigest() == original_hash
    monkeypatch.setenv("FLYONENOMICS_PARAM_OVERRIDES_JSON", json.dumps({"rec.Kd_D1": 100.0}))
    with pytest.raises(ValueError, match="outside declared range"):
        load_params()
