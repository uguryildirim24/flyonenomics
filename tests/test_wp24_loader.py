"""0.15 (d): mechanisms loader, masks, substrate_id_for, and identity (SPEC-P2 5.3)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import yaml

from flyonenomics.drive.mechanisms import (
    engine_model_of,
    mask_sha256,
    mechanisms_from_section,
    parse_mechanisms_section,
    real_scope_mask,
    scope_mask,
    substrate_engine_agree,
    substrate_id_for,
)
from flyonenomics.drive.rest import apply_rest_substrate, load_drive_rest
from flyonenomics.io import hash_file
from flyonenomics.types import load_params
from flyonenomics.validation.binding import CompatibilityClass, IdentityBlock, ValidationEntry, is_compatible

ROOT = Path(__file__).resolve().parents[1]
DEV_DRIVE = ROOT / "data" / "drive-dev-p2.yaml"


def _core_drive(**extra):
    record = {
        "transmitter_rule": {"blob_id": "a" * 40, "scope": "brain"},
        "scales": {"g_gaba": 2.0, "g_glu": 4.0, "g_his": 1, "unk": "g_gaba when s_pq < 0", "sha256": "b" * 64},
        "background": {
            "n_bg": 100,
            "r_bg": 10,
            "groups": {"central": {"size": 3, "w_bg": 1.1}, "sensory": {"size": 1, "w_bg": 0.0}},
        },
        "threshold": None,
        "optic_exemption": False,
        "provenance": {"R1": "c" * 64},
    }
    record.update(extra)
    return record


def _write_drive(tmp_path: Path, **extra) -> Path:
    path = tmp_path / "drive.yaml"
    path.write_text(yaml.safe_dump(_core_drive(**extra)))
    return path


def _sfa_block(mask_hex: str = "abc") -> dict:
    return {"b_mv": 1.0, "tau_ms": 150.0, "scope": "non_sensory", "mask_sha256": mask_hex}


def test_substrate_id_for_lif_and_tagged_files(tmp_path: Path) -> None:
    """substrate_id_for tags rest: for (ii)/(iii) and rest-<tag>: when a block is on."""
    digest = hash_file(DEV_DRIVE)
    assert substrate_id_for(DEV_DRIVE) == "rest:" + digest[:16]
    assert engine_model_of(None) == "lif"

    all_null = tmp_path / "all-null.yaml"
    all_null.write_text(yaml.safe_dump(_core_drive(mechanisms={
        "adaptation": None, "depression": None, "conductance_inhibition": None,
    })))
    assert substrate_id_for(all_null) == "rest:" + hash_file(all_null)[:16]
    assert engine_model_of(
        {"adaptation": None, "depression": None, "conductance_inhibition": None}
    ) == "lif"

    sfa = tmp_path / "sfa.yaml"
    sfa.write_text(yaml.safe_dump(_core_drive(mechanisms={
        "adaptation": _sfa_block(), "depression": None, "conductance_inhibition": None,
    })))
    std = tmp_path / "std.yaml"
    std.write_text(yaml.safe_dump(_core_drive(mechanisms={
        "adaptation": None,
        "depression": {"U": 0.2, "tau_ms": 100.0, "scope": "non_sensory_excitatory", "mask_sha256": "abc"},
        "conductance_inhibition": None,
    })))
    cbi = tmp_path / "cbi.yaml"
    cbi.write_text(yaml.safe_dump(_core_drive(mechanisms={
        "adaptation": None, "depression": None,
        "conductance_inhibition": {"E_inh_mv": -72.0, "scope": "all"},
    })))
    assert substrate_id_for(sfa) == "rest-sfa:" + hash_file(sfa)[:16]
    assert substrate_id_for(std) == "rest-std:" + hash_file(std)[:16]
    assert substrate_id_for(cbi) == "rest-cbi:" + hash_file(cbi)[:16]
    assert engine_model_of({"adaptation": _sfa_block()}) == "lif+sfa"
    assert engine_model_of({
        "depression": {"U": 0.2, "tau_ms": 100.0, "scope": "non_sensory", "mask_sha256": "abc"}
    }) == "lif+std"
    assert engine_model_of({"conductance_inhibition": {"E_inh_mv": -72.0, "scope": "all"}}) == "lif+cbi"


def test_loader_rejections_of_section_2_2_4() -> None:
    """Every section 2.2.4 loader rejection fires."""
    with pytest.raises(ValueError, match="unknown mechanisms key"):
        parse_mechanisms_section({"surprise": None})
    with pytest.raises(ValueError, match="unknown key in adaptation"):
        parse_mechanisms_section({"adaptation": {**_sfa_block(), "extra": 1}})
    with pytest.raises(ValueError, match="at most one"):
        parse_mechanisms_section({
            "adaptation": _sfa_block(),
            "depression": {"U": 0.2, "tau_ms": 100.0, "scope": "non_sensory", "mask_sha256": "abc"},
        })
    with pytest.raises(ValueError, match="zero strength"):
        parse_mechanisms_section({"adaptation": {**_sfa_block(), "b_mv": 0}})
    with pytest.raises(ValueError, match="zero strength"):
        parse_mechanisms_section({
            "depression": {"U": 0, "tau_ms": 100.0, "scope": "non_sensory", "mask_sha256": "abc"}
        })
    with pytest.raises(ValueError, match="finite"):
        parse_mechanisms_section({"adaptation": {**_sfa_block(), "b_mv": float("nan")}})
    with pytest.raises(ValueError, match="at least 40"):
        parse_mechanisms_section({"adaptation": {**_sfa_block(), "tau_ms": 39}})
    with pytest.raises(ValueError, match="in \\(0, 1\\]"):
        parse_mechanisms_section({
            "depression": {"U": 1.1, "tau_ms": 100.0, "scope": "non_sensory", "mask_sha256": "abc"}
        })
    with pytest.raises(ValueError, match="at least 10"):
        parse_mechanisms_section({
            "depression": {"U": 0.2, "tau_ms": 9.0, "scope": "non_sensory", "mask_sha256": "abc"}
        })
    with pytest.raises(ValueError, match="1 mV below"):
        parse_mechanisms_section({
            "conductance_inhibition": {"E_inh_mv": float(load_params().get("lif.v_0")), "scope": "all"}
        })
    with pytest.raises(ValueError, match="scope must be non_sensory"):
        parse_mechanisms_section({"adaptation": {**_sfa_block(), "scope": "all"}})
    super_class = np.array(["sensory", "central", "sensory", "central"], dtype=str)
    mask = scope_mask("non_sensory", super_class=super_class)
    wrong = {**_sfa_block(), "mask_sha256": "0" * 64}
    with pytest.raises(ValueError, match="mask_sha256 differs"):
        mechanisms_from_section({"adaptation": wrong}, n=4, super_class=super_class)


def test_load_drive_rest_keys(tmp_path: Path) -> None:
    """load_drive_rest accepts drive-dev-p2.yaml and v0.2; rejects closed-list violations."""
    drive = load_drive_rest(DEV_DRIVE)
    assert drive["mechanisms"] is None
    accepted = tmp_path / "v02.yaml"
    accepted.write_text(yaml.safe_dump(_core_drive(version="v0.2")))
    loaded = load_drive_rest(accepted)
    assert loaded["mechanisms"] is None
    bad_unknown = tmp_path / "unknown.yaml"
    bad_unknown.write_text(yaml.safe_dump(_core_drive(surprise=1)))
    with pytest.raises(ValueError, match="unknown top-level key"):
        load_drive_rest(bad_unknown)
    bad_version = tmp_path / "ver.yaml"
    bad_version.write_text(yaml.safe_dump(_core_drive(version="v0.1")))
    with pytest.raises(ValueError, match="version must be v0.2"):
        load_drive_rest(bad_version)
    bad_cid = tmp_path / "cid.yaml"
    bad_cid.write_text(yaml.safe_dump(_core_drive(candidate_id="x")))
    with pytest.raises(ValueError, match="configuration_class development"):
        load_drive_rest(bad_cid)
    for key in ("selection", "note"):
        path = tmp_path / f"{key}.yaml"
        path.write_text(yaml.safe_dump(_core_drive(**{key: "x"})))
        with pytest.raises(ValueError, match="configuration_class development"):
            load_drive_rest(path)
    bad_class = tmp_path / "class.yaml"
    bad_class.write_text(yaml.safe_dump(_core_drive(configuration_class="canonical")))
    with pytest.raises(ValueError, match="configuration_class must be development"):
        load_drive_rest(bad_class)


def test_constructed_and_real_scope_masks() -> None:
    """Four-neuron 00 01 00 01 hash; real masks follow root_ids and exclude sensory."""
    mask = np.array([0, 1, 0, 1], dtype=np.uint8)
    expected = hashlib.sha256(np.ascontiguousarray(mask).tobytes()).hexdigest()
    assert mask_sha256(mask) == expected
    super_class = np.array(["sensory", "central", "sensory", "central"], dtype=str)
    np.testing.assert_array_equal(scope_mask("non_sensory", super_class=super_class), mask)

    from flyonenomics.substrate.transmitters import annotations_in_engine, classify_engine

    _classes, frame, _census = classify_engine()
    super_real = frame["super_class"].fillna("").to_numpy(dtype=str)
    _ann, engine_order = annotations_in_engine()
    n = int(engine_order.shape[0])
    non_sensory = real_scope_mask("non_sensory")
    non_sensory_exc = real_scope_mask("non_sensory_excitatory")
    assert non_sensory.shape == (n,)
    assert non_sensory_exc.shape == (n,)
    sensory = super_real == "sensory"
    assert int(non_sensory[sensory].sum()) == 0
    assert int(non_sensory_exc[sensory].sum()) == 0
    from flyonenomics.drive.mechanisms import _engine_scope_inputs

    _super, s_cur, _n = _engine_scope_inputs()
    unk = _classes == "unk"
    if int(unk.sum()):
        assert np.all(non_sensory_exc[unk] == ((s_cur[unk] == 1.0) & (~sensory[unk])).astype(np.uint8))


class _ScaleSink:
    n = 4

    def set_weight_scale(self, scale):
        self.scale = scale


class _ModelEngine(_ScaleSink):
    def __init__(self, name: str) -> None:
        self._name = name

    def engine_model(self) -> str:
        return self._name


def test_apply_rest_substrate_requires_mechanisms_and_guards_model() -> None:
    """apply_rest_substrate raises without mechanisms and on a model mismatch."""
    params = load_params()
    args = dict(
        classes=np.array(["ACh", "Glu", "GABA", "unk"]),
        s_pq=np.array([1.0, 1.0, -1.0, -1.0]),
        pre=np.array([0, 1, 2, 3], dtype=np.int32),
        n=4,
    )
    drive = {"g_glu": 1.0, "g_gaba": 1.0, "g_his": 1.0, "sigma_th": 0.0, "seed": 1}
    with pytest.raises(ValueError, match="must state mechanisms"):
        apply_rest_substrate(_ScaleSink(), params, drive, **args)
    apply_rest_substrate(_ScaleSink(), params, {**drive, "mechanisms": None}, **args)
    with pytest.raises(ValueError, match="engine_model"):
        apply_rest_substrate(_ModelEngine("lif+sfa"), params, {**drive, "mechanisms": None}, **args)
    with pytest.raises(ValueError, match="engine_model"):
        apply_rest_substrate(
            _ModelEngine("lif"),
            params,
            {**drive, "mechanisms": {"adaptation": _sfa_block()}},
            **args,
        )


def test_schema_rejects_mechanism_pins_outside_feedforward(monkeypatch: pytest.MonkeyPatch) -> None:
    """Schema 1.2 and 1.3 background-off reject a mechanism pin outside 8.1."""
    import json

    from pydantic import ValidationError
    from flyonenomics.schema.experiment import Experiment
    import flyonenomics.schema.experiment as experiment_mod

    monkeypatch.setattr(experiment_mod, "_pinned_drive_has_mechanism", lambda version: True)
    raw_12 = json.loads((ROOT / "tests/fixtures/experiments/bare-twin-1.2.json").read_text())
    with pytest.raises(ValidationError, match="schema 1.2 rejects a drive pin with a mechanism"):
        Experiment.model_validate(raw_12)
    raw_13 = json.loads((ROOT / "tests/fixtures/experiments/bare-twin-1.3.json").read_text())
    with pytest.raises(ValidationError, match="background false rejects a drive pin with a mechanism"):
        Experiment.model_validate(raw_13)
    ff = {**raw_13, "substrate": {**raw_13["substrate"], "drive_version": "v0.2"},
          "apply_scales_without_background": True}
    Experiment.model_validate(ff)


def test_identity_without_engine_model_binds_to_lif_only() -> None:
    """Missing engine_model reads as lif; a tag/model disagreement is invalid."""
    ident = {
        "code_commit": "abc",
        "uv_lock_hash": "lock1",
        "provenance_hash": "prov1",
        "data_versions": {"params": "v0.1"},
        "connectome_version": "783",
        "layer_flags": {"background": True, "dopamine_A": True, "transporter_C": True, "dan_fast_synapses": "retain"},
        "fixture_hash": "fix1",
        "assay": "sugar_reflex",
        "machine": "m",
        "date": "2026-09-12",
        "substrate_id": "rest:0123456789abcdef",
    }
    entry = ValidationEntry(
        test_id="t", category="verification", compatibility=CompatibilityClass.MATCHING_LAYERS,
        identity=IdentityBlock(**ident), data_dependencies=["params"],
    )
    assert entry.identity.engine_model == "lif"
    assert entry.identity.mechanisms is None
    run_lif = IdentityBlock(**{**ident, "assay": "buridan", "engine_model": "lif"})
    valid, _reason = is_compatible(entry, run_lif, current_fixture_hash="fix1")
    assert valid
    run_sfa = IdentityBlock(**{
        **ident, "assay": "buridan",
        "substrate_id": "rest-sfa:0123456789abcdef", "engine_model": "lif+sfa",
    })
    valid_sfa, _reason_sfa = is_compatible(entry, run_sfa, current_fixture_hash="fix1")
    assert not valid_sfa
    disagree = ValidationEntry(
        test_id="t", category="verification", compatibility=CompatibilityClass.MATCHING_LAYERS,
        identity=IdentityBlock(**{**ident, "substrate_id": "rest-sfa:0123456789abcdef", "engine_model": "lif"}),
        data_dependencies=["params"],
    )
    valid_d, reason_d = is_compatible(disagree, run_sfa, current_fixture_hash="fix1")
    assert not valid_d
    assert "disagree" in reason_d
    assert substrate_engine_agree("bare", "lif")
    assert substrate_engine_agree("rest:abcd", "lif")
    assert substrate_engine_agree("rest-sfa:abcd", "lif+sfa")
    assert not substrate_engine_agree("rest-sfa:abcd", "lif")
    IdentityBlock(code_commit="abc", uv_lock_hash="lock1", provenance_hash="prov1")


def test_adaptation_tau_floor_is_computed_from_params() -> None:
    """SPEC-P2 8.2: adaptation tau is at least 2 × max(lif.t_mbr, lif.tau)."""
    from flyonenomics.drive.mechanisms import _adaptation_tau_floor_ms

    params = load_params()
    floor = 2.0 * max(float(params.get("lif.t_mbr")), float(params.get("lif.tau")))
    assert _adaptation_tau_floor_ms() == floor
    with pytest.raises(ValueError, match="at least"):
        parse_mechanisms_section({"adaptation": {**_sfa_block(), "tau_ms": floor - 0.001}})
    parse_mechanisms_section({"adaptation": {**_sfa_block(), "tau_ms": floor}})


def test_item_37_rest_calibration_substrate_id_uses_substrate_id_for(monkeypatch) -> None:
    """WP19's rest: literal is gone; both writers go through substrate_id_for."""
    import inspect
    from types import SimpleNamespace

    from flyonenomics.drive import rest_calibration as rest
    from flyonenomics.orchestrator.runner import substrate_id_of

    cal_source = Path(rest.__file__).read_text()
    assert "substrate_id_for" in cal_source
    assert '"rest:"+' not in cal_source.replace(" ", "")
    assert "'rest:'+" not in cal_source.replace(" ", "")
    drive = ROOT / "data/drive-dev-p2.yaml"
    expected = substrate_id_for(drive)
    monkeypatch.setattr(rest, "_drive", lambda: drive)
    seen: dict = {}

    def fake_identity(*_a, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(substrate_id=kwargs["substrate_id"])

    monkeypatch.setattr("flyonenomics.validation.binding.build_identity", fake_identity)
    ident = rest._entry_identity("rest-short.json")
    assert seen["substrate_id"] == expected
    assert ident.substrate_id == expected
    assert "substrate_id_for" in inspect.getsource(substrate_id_of)


def test_r4_and_drive_refuse_mechanism_not_in_force(tmp_path, monkeypatch) -> None:
    """R4 and the drive commit fail when named and observed models disagree."""
    import json

    from flyonenomics.drive import rest_calibration as rest

    mismatch = {"engine_model": "lif+sfa", "engine_model_observed": "lif"}
    agree = {"engine_model": "lif+sfa", "engine_model_observed": "lif+sfa"}
    assert rest._mechanism_not_in_force({"rows": [mismatch]})
    assert not rest._mechanism_not_in_force({"rows": [agree]})
    assert not rest._mechanism_not_in_force({})
    (tmp_path / "R3.json").write_text(json.dumps({"rows": [mismatch]}))
    (tmp_path / "K1r.json").write_text(json.dumps({
        "status": "passed", "evaluations": [mismatch],
    }))
    monkeypatch.setattr(rest, "r2_path", lambda: ROOT / "validation/records/p2/rest-tier2-stage2.json")
    monkeypatch.setattr(rest, "RECORDS", tmp_path)
    monkeypatch.setattr(rest, "_rec", lambda: tmp_path)
    monkeypatch.setattr(rest, "development", lambda: False)
    monkeypatch.setattr(rest, "_git", lambda *a, **k: "1000000000")
    refused = rest.run_r4()
    assert refused["status"] == "failed"
    assert refused["reason"] == "mechanism not in force"
    drive = rest.run_drive()
    assert drive["status"] == "failed"
    assert drive["reason"] == "mechanism not in force"
