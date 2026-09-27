"""Section 8.1 configuration loaders and schema 1.3 bare twins (WP15)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from flyonenomics.drive.rest import (
    behaviour_dict,
    load_behaviour_v02,
    load_dopamine_v02,
    load_drive_rest,
    load_params_version,
    load_visual_v02,
    resolve_configurations,
)
from flyonenomics.schema import Experiment, load_experiment
from flyonenomics.validation.level0_rest import twin_resolution

ROOT = Path(__file__).resolve().parents[1]
SUGAR_HASH = "eb21d49755c3319441ff0c80de405a9d61490aecfc535ab24e9290945cd147db"
INVARIANCE_HASH = "60b21aa2d1aa86a3eb5c060e7638d08a2a1d22cd85d6a49c6a8cad154cc841eb"


def _write(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


def _blob(path: Path) -> str:
    """Git blob id of the file's bytes, as `git hash-object` prints it."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


@pytest.fixture(autouse=True)
def _no_validation_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Section 8.1: loaders run as if no validation/ directory were present."""
    import flyonenomics.io as io

    record = io._record

    def guarded(path):
        if (ROOT / "validation") in Path(path).resolve().parents:
            raise FileNotFoundError(f"validation/ is absent for the loader test: {path}")
        return record(path)

    monkeypatch.setattr(io, "_record", guarded)


def _base_behaviour() -> dict:
    return {
        "version": "base-v0.2",
        "v_fwd_mm_s": 15.251167474671366,
        "step_min_mm": 0.8,
        "r_max_hz": 300.0,
    }


def _visual_pr() -> dict:
    return {
        "inject_at": "photoreceptors",
        "r_light": 100.0,
        "r_dark": 0.0,
        "pr_acceptance_deg": 5.0,
    }


def _visual_tubu() -> dict:
    return {"inject_at": "TuBu", "r_vis_max": 70.0, "sigma_vis": 20.0}


def test_schema_12_protocol_hashes_unchanged() -> None:
    """Phase 1 files keep their protocol hashes. Units none."""
    sugar = load_experiment(ROOT / "data/experiments/sugar-reflex.json")
    assert sugar.protocol_hash() == SUGAR_HASH
    raw = json.loads((ROOT / "tests/fixtures/experiments/invariance.json").read_text())
    experiment = Experiment.model_validate(raw["experiment"])
    assert experiment.protocol_hash() == INVARIANCE_HASH


def test_params_v02_only_inject_at_changes() -> None:
    """v0.1 row values match v0.2 except vis.inject_at. Units per YAML."""
    old = load_params_version("v0.1")
    new = load_params_version("v0.2")
    assert new.get("vis.inject_at") == "photoreceptors"
    assert old.get("vis.inject_at") == "TuBu"
    assert new.get("lif.v_th") == old.get("lif.v_th")
    assert new.get("settle.window_s_13") == 1.0


def test_0_14_twins_resolve_apart_from_schema() -> None:
    """Bare twins match except schema_version, and bare 1.3 files reject 1.3-only features."""
    from flyonenomics.validation.level0_rest import bare_rejections

    measured = twin_resolution()
    assert measured["passed"]
    rejections = bare_rejections()
    assert rejections["passed"], rejections


def test_schema_12_rejects_keys_its_hash_would_drop() -> None:
    """A 1.2 file cannot set a 1.3-only key that model_dump removes from the protocol hash."""
    raw = json.loads((ROOT / "tests/fixtures/experiments/bare-twin-1.2.json").read_text())
    for change in (
        {"substrate": {**raw["substrate"], "visual_version": "v0.2"}},
        {"substrate": {**raw["substrate"], "drive_version": None}},
        {"apply_scales_without_background": False},
    ):
        with pytest.raises(ValidationError, match="schema 1.3 feature"):
            Experiment.model_validate({**raw, **change})
    probe = {"type": "probe", "duration_s": 0.01, "label": "p"}
    for assay, params in (("spontaneous", {"stimulus": "dark"}), ("buridan", {"initial_heading": "stripe_A"}),
                          ("open_loop_steering", {"inject_at": "TuBu"})):
        data = json.loads(json.dumps(raw))
        data["arms"][0]["protocol"] = [{**probe, "assay": assay, "params": params}]
        data["record"] = {"spikes": ["MN9"], "rates": ["MN9"], "popcount": True, "live": False}
        with pytest.raises(ValidationError, match="schema 1.3 feature"):
            Experiment.model_validate(data)


def test_schema_12_rejects_v02_params_and_drive_pins() -> None:
    """Decision 22: a 1.2 file cannot reach the rest substrate through a v0.2 pin."""
    from flyonenomics.validation.level0_rest import bare_rejections

    raw = json.loads((ROOT / "tests/fixtures/experiments/bare-twin-1.2.json").read_text())
    for key in ("params_version", "drive_version"):
        with pytest.raises(ValidationError, match=f"v0.2 {key} pin: schema 1.3 is the only route"):
            Experiment.model_validate({**raw, "substrate": {**raw["substrate"], key: "v0.2"}})
    measured = bare_rejections()
    assert measured["rejected"]["v0.2 params pin"] == {"schema_12": True, "schema_13": True}
    assert measured["rejected"]["v0.2 drive pin"] == {"schema_12": True, "schema_13": True}
    assert measured["schema_12_routes_to_13"] == {"v0.2 params pin": True, "v0.2 drive pin": True}


def test_schema_13_inject_at_defaults_from_the_visual_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Background-on 1.3 takes inject_at from visual-v0.2.yaml, else from the pinned params row."""
    import flyonenomics.schema.experiment as schema

    raw = {
        "schema_version": "1.3", "name": "inject", "seed": 1, "seeds": [1], "layers": {"background": True},
        "arms": [{"label": "wild-type", "protocol": [
            {"type": "probe", "assay": "buridan", "duration_s": 0.01, "label": "b", "params": {}},
            {"type": "probe", "assay": "open_loop_steering", "duration_s": 0.01, "label": "o", "params": {}},
        ]}],
    }
    fake = tmp_path / "src" / "flyonenomics" / "schema"
    fake.mkdir(parents=True)
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(schema, "__file__", str(fake / "experiment.py"))
    # Exercise absence in a constructed root, not by requiring calibration
    # never to publish the real visual configuration.
    assert not (tmp_path / "data/visual-v0.2.yaml").is_file()
    experiment = Experiment.model_validate(json.loads(json.dumps(raw)))
    assert [p.params.inject_at for p in experiment.arms[0].protocol] == ["photoreceptors", "photoreceptors"]
    (tmp_path / "data/visual-v0.2.yaml").write_text("inject_at: TuBu\n")
    experiment = Experiment.model_validate(json.loads(json.dumps(raw)))
    assert [p.params.inject_at for p in experiment.arms[0].protocol] == ["TuBu", "TuBu"]
    explicit = json.loads(json.dumps(raw))
    explicit["arms"][0]["protocol"][0]["params"] = {"inject_at": "ER"}
    assert Experiment.model_validate(explicit).arms[0].protocol[0].params.inject_at == "ER"


def test_new_named_genotype_expands_for_a_run() -> None:
    """A 1.3 named genotype validates and resolves its hooks now that WP21 is on main."""
    raw = {
        "schema_version": "1.3", "name": "named", "seed": 1, "seeds": [1], "layers": {"background": True},
        "arms": [{"label": "arm", "genotype": {"named": "pam_silenced"}, "protocol": [
            {"type": "probe", "assay": "spontaneous", "duration_s": 0.01, "label": "p", "params": {}},
        ]}],
    }
    experiment = Experiment.model_validate(raw)
    from flyonenomics.schema.named import named_manipulations
    assert experiment.arms[0].genotype.expanded() == named_manipulations("pam_silenced")
    assert experiment.arms[0].genotype.expanded()


def test_schema_13_background_defaults_and_bare_rejections() -> None:
    """1.3 pins v0.2 on background, and rejects 1.3-only features when bare."""
    proto = {
        "schema_version": "1.3",
        "name": "p2-rest",
        "seed": 1,
        "seeds": [1],
        "layers": {"background": True},
        "arms": [{"label": "wild-type", "protocol": [
            {"type": "probe", "assay": "spontaneous", "duration_s": 0.01, "label": "dark", "params": {}},
        ]}],
    }
    experiment = Experiment.model_validate(json.loads(json.dumps(proto)))
    assert experiment.substrate.params_version == "v0.2"
    assert experiment.substrate.visual_version == "v0.2"
    assert experiment.arms[0].protocol[0].params.stimulus == "dark"
    bare = json.loads(json.dumps(proto))
    bare["layers"] = {"background": False}
    bare["arms"][0]["protocol"][0]["params"] = {"stimulus": "ambient"}
    with pytest.raises(ValidationError, match="1.3-only"):
        Experiment.model_validate(bare)
    named = json.loads(json.dumps(proto))
    named["layers"] = {"background": False}
    named["arms"][0]["genotype"] = {"named": "dat_half", "manipulations": []}
    with pytest.raises(ValidationError, match="named genotype"):
        Experiment.model_validate(named)


def test_open_loop_blocks_duration() -> None:
    """1.3 open-loop blocks must sum to duration_s. Units: seconds."""
    blocks = [
        {"stimulus": "ambient", "transition_s": 1, "dwell_s": 1},
        {"stimulus": "stripe", "azimuth_deg": 45, "transition_s": 1, "dwell_s": 2},
    ]
    raw = {
        "schema_version": "1.3",
        "name": "blocks",
        "seed": 1,
        "seeds": [1],
        "layers": {"background": True},
        "arms": [{"label": "wild-type", "protocol": [
            {"type": "probe", "assay": "open_loop_steering", "duration_s": 5,
             "label": "ol", "params": {"blocks": blocks}},
        ]}],
    }
    Experiment.model_validate(raw)
    raw["arms"][0]["protocol"][0]["duration_s"] = 4
    with pytest.raises(ValidationError, match="duration_s"):
        Experiment.model_validate(raw)


def test_photoreceptor_closed_loop(tmp_path: Path) -> None:
    """Photoreceptor closed-loop files build matching settings. Units: Hz, mm/s."""
    params = load_params_version("v0.2")
    visual_path = _write(tmp_path / "visual-v0.2.yaml", _visual_pr())
    blob = _blob(visual_path)
    behaviour_path = _write(tmp_path / "behaviour-v0.2.yaml", {
        "version": "v0.2",
        **_base_behaviour(),
        "controller": "closed_loop",
        "sign_steer": 1,
        "bias_hz": 0.25,
        "K_steer": 4,
        "visual": blob,
    })
    resolved = resolve_configurations(
        params=params, behaviour_path=behaviour_path, behaviour_version="v0.2",
        assays={"buridan"}, visual_path=visual_path,
    )
    assert resolved.visual.inject_at == "photoreceptors"
    assert resolved.visual.r_light == 100.0
    assert resolved.behaviour.controller == "closed_loop"
    assert resolved.behaviour.sign_steer == 1
    assert resolved.behaviour.K_steer == 4
    assert resolved.behaviour.bias_hz == 0.25
    assert resolved.behaviour.v_fwd == pytest.approx(15.251167474671366)
    values = behaviour_dict(resolved.behaviour)
    assert values["sign_steer"] == 1


def test_visual_file_requires_its_encoder_settings(tmp_path: Path) -> None:
    """A photoreceptor file needs r_light; a TuBu file needs r_vis_max and sigma_vis (sections 3.2, 3.7)."""
    params = load_params_version("v0.2")
    pr = {key: value for key, value in _visual_pr().items() if key != "r_light"}
    with pytest.raises(ValueError, match="lacks r_light"):
        load_visual_v02(_write(tmp_path / "pr.yaml", pr), params)
    tubu = {key: value for key, value in _visual_tubu().items() if key != "sigma_vis"}
    with pytest.raises(ValueError, match="lacks sigma_vis"):
        load_visual_v02(_write(tmp_path / "tubu.yaml", tubu), params)


def test_tubu_closed_loop(tmp_path: Path) -> None:
    """TuBu closed-loop files take encoder settings from the visual pin."""
    params = load_params_version("v0.2")
    visual_path = _write(tmp_path / "visual-v0.2.yaml", _visual_tubu())
    blob = _blob(visual_path)
    behaviour_path = _write(tmp_path / "behaviour-v0.2.yaml", {
        **_base_behaviour(),
        "controller": "closed_loop",
        "sign_steer": -1,
        "bias_hz": 0.0,
        "K_steer": 8,
        "visual": blob,
    })
    resolved = resolve_configurations(
        params=params, behaviour_path=behaviour_path, behaviour_version="v0.2",
        assays={"buridan"}, visual_path=visual_path,
    )
    assert resolved.visual.inject_at == "TuBu"
    assert resolved.visual.r_vis_max == 70.0
    assert resolved.behaviour.sign_steer == -1
    assert resolved.behaviour.K_steer == 8


def test_open_loop_after_visual_failure(tmp_path: Path) -> None:
    """Open loop after V-cal and VT-cal failure uses only base, visual and open_loop."""
    params = load_params_version("v0.2")
    visual_path = _write(tmp_path / "visual-v0.2.yaml", _visual_pr())
    blob = _blob(visual_path)
    behaviour_path = _write(tmp_path / "behaviour-v0.2.yaml", {
        **_base_behaviour(),
        "controller": "open_loop",
        "bias_hz": 0.1,
        "sign_steer": None,
        "K_steer": None,
        "visual": blob,
    })
    resolved = resolve_configurations(
        params=params, behaviour_path=behaviour_path, behaviour_version="v0.2",
        assays={"open_loop_steering"}, visual_path=visual_path,
    )
    assert resolved.behaviour.controller == "open_loop"
    assert resolved.behaviour.sign_steer is None
    assert resolved.behaviour.K_steer is None
    with pytest.raises(ValueError, match="Buridan"):
        resolve_configurations(
            params=params, behaviour_path=behaviour_path, behaviour_version="v0.2",
            assays={"buridan"}, visual_path=visual_path,
        )


def test_pre_steering_base_and_encoder_grid(tmp_path: Path) -> None:
    """Pre-steering stages pin base-v0.2; V-cal supplies r_light with no visual file."""
    params = load_params_version("v0.2")
    base_path = _write(tmp_path / "behaviour-base-v0.2.yaml", _base_behaviour())
    resolved = resolve_configurations(
        params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
        assays={"open_loop_steering", "spontaneous"}, visual_path=None,
        meta={"r_light": 50}, encoder_grid=True,
    )
    assert resolved.visual.inject_at == "photoreceptors"
    assert resolved.visual.r_light == 50.0
    assert resolved.visual.pr_acceptance_deg == 5.0
    assert resolved.behaviour.kind == "encoder-grid"
    vt = resolve_configurations(
        params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
        assays={"open_loop_steering"}, visual_path=None,
        meta={"r_vis_max": 100}, encoder_grid=True,
    )
    assert vt.visual.inject_at == "TuBu"
    assert vt.visual.r_vis_max == 100.0
    visual_path = _write(tmp_path / "visual-v0.2.yaml", _visual_pr())
    with pytest.raises(ValueError, match="must not pin a visual file"):
        resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"open_loop_steering"}, visual_path=visual_path,
            meta={"r_light": 50}, encoder_grid=True,
        )
    with pytest.raises(ValueError, match="Buridan"):
        resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"buridan"}, visual_path=None, meta={"r_light": 50}, encoder_grid=True,
        )


def test_k3r_and_k3r_tubu_fixtures(tmp_path: Path) -> None:
    """K-grid fixtures build Buridan behaviour from metadata, grid, base and visual."""
    params = load_params_version("v0.2")
    base_path = _write(tmp_path / "behaviour-base-v0.2.yaml", {
        **_base_behaviour(),
        "grid": {"K_steer": [1, 2, 4, 8, 16]},
    })
    visual_pr = _write(tmp_path / "visual-pr.yaml", _visual_pr())
    visual_tu = _write(tmp_path / "visual-tu.yaml", _visual_tubu())
    for visual_path, inject, sign, bias, k_value in (
        (visual_pr, "photoreceptors", 1, 0.2, 4.0),
        (visual_tu, "TuBu", -1, -0.1, 8.0),
    ):
        resolved = resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"buridan"}, visual_path=visual_path,
            meta={"sign_steer": sign, "bias_hz": bias, "visual": _blob(visual_path)},
            grid={"K_steer": k_value}, k_grid=True,
        )
        assert resolved.visual.inject_at == inject
        assert resolved.behaviour.sign_steer == sign
        assert resolved.behaviour.bias_hz == pytest.approx(bias)
        assert resolved.behaviour.K_steer == k_value
        assert resolved.behaviour.v_fwd == pytest.approx(15.251167474671366)


def test_loader_rejections(tmp_path: Path) -> None:
    """Each section 8.1 rejection raises. Units per field."""
    params = load_params_version("v0.2")
    visual_path = _write(tmp_path / "visual-v0.2.yaml", _visual_pr())
    other_visual = _write(tmp_path / "visual-other.yaml", {**_visual_pr(), "r_light": 50})
    base_path = _write(tmp_path / "behaviour-base-v0.2.yaml", {
        **_base_behaviour(),
        "grid": {"K_steer": [1, 2, 4, 8, 16]},
    })
    closed = _write(tmp_path / "behaviour-v0.2.yaml", {
        **_base_behaviour(),
        "controller": "closed_loop",
        "sign_steer": 1,
        "bias_hz": 0.0,
        "K_steer": 4,
        "visual": _blob(other_visual),
    })
    with pytest.raises(ValueError, match="visual blob"):
        resolve_configurations(
            params=params, behaviour_path=closed, behaviour_version="v0.2",
            assays={"buridan"}, visual_path=visual_path,
        )
    with pytest.raises(ValueError, match="Buridan"):
        resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"buridan"}, visual_path=visual_path,
        )
    with pytest.raises(ValueError, match="visual pin"):
        resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"buridan"}, visual_path=None,
            meta={"sign_steer": 1, "bias_hz": 0.0}, grid={"K_steer": 4}, k_grid=True,
        )
    with pytest.raises(ValueError, match="sign_steer and bias_hz"):
        resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"buridan"}, visual_path=visual_path,
            grid={"K_steer": 4}, k_grid=True,
        )
    with pytest.raises(ValueError, match=r"\+1 or -1"):
        resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"buridan"}, visual_path=visual_path,
            meta={"sign_steer": 0, "bias_hz": 0.0}, grid={"K_steer": 4}, k_grid=True,
        )
    with pytest.raises(ValueError, match="declared grid"):
        resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"buridan"}, visual_path=visual_path,
            meta={"sign_steer": 1, "bias_hz": 0.0}, grid={"K_steer": 3}, k_grid=True,
        )
    with pytest.raises(ValueError, match="only K_steer"):
        resolve_configurations(
            params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
            assays={"buridan"}, visual_path=visual_path,
            meta={"sign_steer": 1, "bias_hz": 0.0}, grid={"K_steer": 4, "r_light": 1},
            k_grid=True,
        )
    missing = _write(tmp_path / "behaviour-missing.yaml", {"version": "base-v0.2", "step_min_mm": 0.8})
    with pytest.raises(ValueError, match="non-finite runtime value"):
        load_behaviour_v02(
            missing, params, version="base-v0.2", visual=load_visual_v02(visual_path, params),
            visual_path=visual_path, assays=set(),
        )
    no_step = _write(tmp_path / "behaviour-no-step.yaml", {"version": "base-v0.2", "v_fwd_mm_s": 15.0, "r_max_hz": 300.0})
    with pytest.raises(ValueError, match="step_min_mm"):
        resolve_configurations(params=params, behaviour_path=no_step, behaviour_version="base-v0.2",
                               assays={"open_loop_steering"})
    good = {**_base_behaviour(), "controller": "closed_loop", "sign_steer": 1, "bias_hz": 0.0,
            "K_steer": 4, "visual": _blob(visual_path)}
    for change, message in (
        ({"sign_steer": 1.5}, r"\+1 or -1"),
        ({"bias_hz": None}, "bias_hz"),
        ({"visual": None}, "visual blob id"),
    ):
        path = _write(tmp_path / "behaviour-bad.yaml", {**good, **change})
        with pytest.raises(ValueError, match=message):
            resolve_configurations(params=params, behaviour_path=path, behaviour_version="v0.2",
                                   assays={"buridan"}, visual_path=visual_path)
    good_path = _write(tmp_path / "behaviour-good.yaml", good)
    with pytest.raises(ValueError, match="visual pin"):
        resolve_configurations(params=params, behaviour_path=good_path, behaviour_version="v0.2",
                               assays={"buridan"}, visual_path=None)
    kgrid = {"sign_steer": 1, "bias_hz": 0.0}
    with pytest.raises(ValueError, match=r"\+1 or -1"):
        resolve_configurations(params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
                               assays={"buridan"}, visual_path=visual_path,
                               meta={**kgrid, "sign_steer": -1.5, "visual": _blob(visual_path)},
                               grid={"K_steer": 4}, k_grid=True)
    with pytest.raises(ValueError, match="visual blob id in its metadata"):
        resolve_configurations(params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
                               assays={"buridan"}, visual_path=visual_path, meta=kgrid,
                               grid={"K_steer": 4}, k_grid=True)
    with pytest.raises(ValueError, match="visual blob id differs"):
        resolve_configurations(params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
                               assays={"buridan"}, visual_path=visual_path,
                               meta={**kgrid, "visual": _blob(other_visual)}, grid={"K_steer": 4}, k_grid=True)
    with pytest.raises(ValueError, match="must pin base-v0.2"):
        resolve_configurations(params=params, behaviour_path=good_path, behaviour_version="v0.2",
                               assays={"buridan"}, visual_path=visual_path,
                               meta={**kgrid, "visual": _blob(visual_path)}, grid={"K_steer": 4}, k_grid=True)
    for meta in ({"r_light": 75}, {"r_vis_max": 60}, {"r_light": 50, "r_vis_max": 70}):
        with pytest.raises(ValueError, match="declared grid|not both"):
            resolve_configurations(params=params, behaviour_path=base_path, behaviour_version="base-v0.2",
                                   assays={"open_loop_steering"}, visual_path=None, meta=meta, encoder_grid=True)


def test_dopamine_v02_compartment_order(tmp_path: Path) -> None:
    """Dopamine v0.2 loader checks registry compartment order. Units: µM."""
    path = _write(tmp_path / "dopamine-v0.2.yaml", {
        "compartments": ["a", "b"],
        "R_c": [0.5, 0.5],
        "alpha_c": [0.001, 0.002],
        "S_c": [0.0, 0.0],
    })
    record = load_dopamine_v02(path, ["a", "b"])
    assert record["R_c"] == [0.5, 0.5]
    with pytest.raises(ValueError, match="compartment order"):
        load_dopamine_v02(path, ["b", "a"])


def test_male_calibrated_tables_load() -> None:
    """Item 155 fills the male files without changing the FlyWire version."""
    from flyonenomics.io import read_yaml

    drive_path = ROOT / "data/drive-male-cns-v1.0.yaml"
    dopamine_path = ROOT / "data/dopamine-male-cns-v1.0.yaml"
    names = read_yaml(dopamine_path)["compartments"]
    drive = load_drive_rest(drive_path)
    dopamine = load_dopamine_v02(dopamine_path, names)
    assert drive["raw"]["version"] == "male-cns-v1.0"
    assert drive["w_bg"]["sensory"] == 1.0
    assert dopamine["drive_blob_id"] == _blob(drive_path)


@pytest.mark.parametrize("section,key", [
    ("scales", "g_gaba"), ("scales", "g_glu"), ("scales", "g_his"),
    ("scales", "g_gaba_kc"), ("scales", "sha256"), ("scales", "unk"),
    ("background", "sensory"), ("background_size", "sensory"),
    ("threshold", "sigma_th"), ("provenance", "connectome_version"),
    ("provenance", "record"), ("provenance", "record_sha256"),
    ("provenance", "inputs_record_sha256"), (None, "optic_exemption"),
])
def test_male_drive_rejects_remaining_null(tmp_path: Path, section, key) -> None:
    """A partially filled male table must not silently become executable."""
    from flyonenomics.io import read_yaml

    raw = read_yaml(ROOT / "data/drive-male-cns-v1.0.yaml")
    if section == "background":
        raw[section]["groups"][key]["w_bg"] = None
    elif section == "background_size":
        raw["background"]["groups"][key]["size"] = None
    elif section == "threshold":
        raw[section] = {"sigma_th": None, "seed": None, "z_sha256": None}
    elif section is None:
        raw[key] = None
    else:
        raw[section][key] = None
    with pytest.raises(ValueError):
        load_drive_rest(_write(tmp_path / "male-drive.yaml", raw))


@pytest.mark.parametrize("key", [
    "R_c", "alpha_c", "S_c", "mode", "version", "params_version",
    "receptor_map_version", "connectome_version", "drive_blob_id", "constants",
])
def test_male_dopamine_rejects_remaining_null(tmp_path: Path, key: str) -> None:
    """Null calibrated entries and bindings never fall back to FlyWire."""
    from flyonenomics.io import read_yaml

    raw = read_yaml(ROOT / "data/dopamine-male-cns-v1.0.yaml")
    if isinstance(raw[key], list):
        raw[key][0] = None
    elif key == "constants":
        raw[key]["DA_ref"] = None
    else:
        raw[key] = None
    with pytest.raises(ValueError):
        load_dopamine_v02(_write(tmp_path / "male-dopamine.yaml", raw), raw["compartments"])


def test_male_substrate_manifest_pin_ignores_visual_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding a 3D asset must not invalidate the numerical MaleCNS source pin."""
    import importlib

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    substrate = importlib.import_module("malecns_substrate")
    manifest = json.loads((ROOT / "data/malecns-v1.0-manifest.json").read_text())
    expected = substrate._model_manifest_sha256()
    manifest["files"].append({"name": "visuals/example", "bytes": 1, "sha256": "0" * 64})
    data = tmp_path / "data"
    data.mkdir()
    (data / "malecns-v1.0-manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(substrate, "ROOT", tmp_path)
    assert substrate._model_manifest_sha256() == expected


def test_committed_base_behaviour_loads() -> None:
    """Committed behaviour-base-v0.2.yaml loads without a visual file."""
    params = load_params_version("v0.2")
    resolved = resolve_configurations(
        params=params,
        behaviour_path=ROOT / "data/behaviour-base-v0.2.yaml",
        behaviour_version="base-v0.2",
        assays={"open_loop_steering"},
    )
    assert resolved.behaviour.v_fwd == pytest.approx(15.251167474671366)
    assert resolved.behaviour.kind == "base-v0.2"


def test_schema_13_named_genotype_accepted_on_background() -> None:
    """Schema 1.3 with background accepts the new named genotypes."""
    raw = {
        "schema_version": "1.3",
        "name": "named-p2",
        "seed": 1,
        "seeds": [1],
        "layers": {"background": True},
        "arms": [{"label": "arm", "genotype": {"named": "dat_half"}, "protocol": [
            {"type": "probe", "assay": "spontaneous", "duration_s": 0.01, "label": "p", "params": {}},
        ]}],
    }
    experiment = Experiment.model_validate(raw)
    assert experiment.arms[0].genotype.named == "dat_half"
    from flyonenomics.schema.named import named_manipulations
    assert experiment.arms[0].genotype.expanded() == named_manipulations("dat_half")
