"""WP16 binding, dependency log, platform, and artefact-detector tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from flyonenomics.types import LayerFlags
from flyonenomics.validation import artefacts, binding
from flyonenomics.validation import level0_binding

ROOT = Path(__file__).resolve().parents[1]


def script(name: str):
    spec = importlib.util.spec_from_file_location(f"wp16_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0_12_frozen_hashes_match_835da84() -> None:
    """0.12 matches the pre-closure SHA-256 list. Units: none."""
    entry = level0_binding.test_0_12()
    assert entry.outcome == "passed"
    assert entry.measured["frozen_ok"] is True
    # params-v0.2.yaml is on this tree: the v0.2 half runs and passes.
    assert entry.measured["params_v0_2"]["status"] == "compared"
    assert entry.measured["params_v0_2"]["drifted"] == []


def test_static_read_call_check_is_clean() -> None:
    """Every remaining src/scripts read is allowlisted. Units: none."""
    report = level0_binding.static_read_call_check(ROOT)
    assert report["passed"], report["hits"]


def test_0_9r_parts_pass() -> None:
    """0.9r (a) to (d) pass, including the constructed freeze protocol."""
    entry = level0_binding.test_0_9r()
    assert entry.measured["a"]["passed"]
    assert entry.measured["b"]["passed"], entry.measured["b"]
    assert entry.measured["c"]["passed"], entry.measured["c"]
    assert entry.measured["d"]["passed"], entry.measured["d"]
    assert entry.measured["static"]["passed"], entry.measured["static"]["hits"]
    assert entry.outcome == "passed"


def test_qualification_of_follows_required_passed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """qualification_of is true only when required entries are passed and valid."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/params-v0.1.yaml").write_text("version: v0.1\n")
    (tmp_path / "data/provenance.json").write_text("{}")
    (tmp_path / "uv.lock").write_text("lock")
    (tmp_path / "fixture.json").write_text("{}")
    monkeypatch.setattr(binding, "repo_commit", lambda root: "commit")
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    identity = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="q",
        fixture="fixture.json",
    )
    entry = binding.ValidationEntry(
        test_id="freeze", category="verification", identity=identity,
        data_dependencies=["params-v0.1.yaml"], fixture_path="fixture.json",
    )
    ok, reasons = binding.qualification_of(
        "freeze", identity, results=[entry], repo=tmp_path, required_passed=["freeze"],
    )
    assert ok and reasons["freeze"] == "valid"
    missing, _ = binding.qualification_of(
        "freeze", identity, results=[], repo=tmp_path, required_passed=["freeze"],
    )
    assert missing is False


def test_artefact_detectors_constructed_cases() -> None:
    """New section 9.2 detectors flag constructed positives and stay quiet otherwise."""
    assert artefacts.ignition_detector() == "not run"
    hot = artefacts.ignition_detector(np.array([1.0, 10.0]), settled_central_mean=2.0)
    assert hot["status"] == "ignited"
    cool = artefacts.ignition_detector(np.array([1.0, 1.5]), settled_central_mean=2.0)
    assert cool["status"] == "clear"
    off = artefacts.off_rest_detector({"central": 8.0}, {"central": 2.0})
    assert off["status"] == "off-rest" and off["tripped"] is False
    gap = artefacts.da_gap_detector({"MB": 0.5}, {"MB": 1.0})
    assert gap["status"] == "da-gap" and gap["tripped"] is False
    bias = artefacts.bias_dominated_detector(3.0, np.array([0.0, 4.0]))
    assert bias["status"] == "bias-dominated"
    photo = artefacts.photoreceptor_sign_detector("left", "right")
    assert photo["status"] == "depends on photoreceptor sign"
    agree = artefacts.platform_agreement_detector(
        {"central_hz": 1.0, "passed": True}, {"central_hz": 2.0, "passed": True},
    )
    assert agree["status"] == "platform-sensitive"
    sides = np.array(["left", "left", "right", "right"])
    azimuths = np.array([1.0, 2.0, 3.0, 4.0])
    perm = artefacts.encoder_permutation_detector(
        lambda order: {"effect": float(order[0])}, baseline={"effect": 1.0},
        seed=20260912, azimuths=azimuths, sides=sides,
    )
    assert len(perm["reruns"]) == 3
    assert perm["within_eye"] is True
    report = artefacts.label_check()
    assert "sign_disagreement_fraction" in report
    assert "sign_disagreement_flagged" in report


def test_one_use_executes_only_under_holdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A constructed one-use entry is carried forward and runs only with --holdout."""
    module = script("run_validation")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(binding, "repo_commit", lambda root: "code")
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/params-v0.1.yaml").write_text("version: v0.1\n")
    (tmp_path / "data/provenance.json").write_text("{}")
    (tmp_path / "uv.lock").write_text("locked")
    (tmp_path / "fixture.json").write_text("fixture")
    identity = binding.build_identity(
        tmp_path, layers=LayerFlags(), connectome_version="630", assay="sugar_reflex",
        fixture="fixture.json",
    )
    entry = binding.ValidationEntry(
        test_id="hold-1", category="verification", identity=identity,
        fixture_path="fixture.json", data_dependencies=["params-v0.1.yaml"], one_use=True,
    )
    calls = {"n": 0}

    def suite() -> binding.ValidationEntry:
        calls["n"] += 1
        return entry

    suite.one_use = True
    monkeypatch.setattr(module, "discover_suites", lambda: {"hold-1": suite})
    monkeypatch.setattr(module, "check_holdout_ready", lambda *args, **kwargs: (True, "ok"))
    first = module.run_all(ids=["hold-1"], holdout="hold-1")
    assert calls["n"] == 1
    assert first["errors"] == []
    assert first["results"][0]["test_id"] == "hold-1"
    carried = module.run_all(ids=["hold-1"])
    assert calls["n"] == 1
    assert carried["errors"] == []
    assert carried["results"][0]["measured"]["one_use_carried"] is True
    again = module.run_all(ids=["hold-1"], holdout="hold-1")
    assert calls["n"] == 1
    assert again["results"][0]["measured"]["one_use_carried"] is True
    monkeypatch.setattr(module, "check_holdout_ready", lambda *args, **kwargs: (False, "not ready"))
    dest = tmp_path / "validation" / "fresh.json"
    fresh_entry = entry.model_copy(update={"test_id": "hold-2"})

    def suite2() -> binding.ValidationEntry:
        calls["n"] += 1
        return fresh_entry

    suite2.one_use = True
    monkeypatch.setattr(module, "discover_suites", lambda: {"hold-2": suite2})
    blocked = module.run_all(ids=["hold-2"], holdout="hold-2", output=dest)
    assert calls["n"] == 1
    assert blocked["errors"] and "hold-2" in blocked["errors"][0]["error"]


def _tiny_repo(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (root / "data").mkdir(exist_ok=True)
    (root / "data/params-v0.1.yaml").write_text("version: v0.1\n")
    (root / "data/provenance.json").write_text("{}")
    (root / "uv.lock").write_text("locked")
    (root / "fixture.json").write_text("fixture")
    monkeypatch.setattr(binding, "repo_commit", lambda root: "code")
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")


def test_entry_without_inputs_stales_on_data_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """code_scope omits data/ only for entries that record inputs; others keep code_hash."""
    _tiny_repo(tmp_path, monkeypatch)
    hashes = {"code": "git:one", "scope": "git:scope"}
    monkeypatch.setattr(binding, "code_content_hash", lambda root: hashes["code"])
    monkeypatch.setattr(binding, "code_scope_hash", lambda root: hashes["scope"])
    identity = binding.build_identity(tmp_path, connectome_version="783", layers=LayerFlags(), assay="q",
                                      fixture="fixture.json")
    entry = binding.ValidationEntry(test_id="p", category="verification", identity=identity,
                                    fixture_path="fixture.json")
    assert binding.is_compatible(entry, identity, repo=tmp_path) == (True, "valid")
    hashes["code"] = "git:data-changed"  # data/ bytes changed, src/ and scripts/ did not
    run = binding.build_identity(tmp_path, connectome_version="783", layers=LayerFlags(), assay="q",
                                 fixture="fixture.json")
    valid, reason = binding.is_compatible(entry, run, repo=tmp_path)
    assert not valid and "code hash" in reason
    with_inputs = entry.model_copy(update={"identity": identity.model_copy(update={
        "inputs": binding.input_blobs(tmp_path, ["data/params-v0.1.yaml"])})})
    assert binding.is_compatible(with_inputs, run, repo=tmp_path) == (True, "valid")


def test_engine_row_requires_both_0_10_ids() -> None:
    """SPEC-P2 section 10 question 16: 0.10 and 0.10-engine are both required."""
    ids = binding.required_passed_ids("engine")
    assert "0.10" in ids and "0.10-engine" in ids
    with_sigma = binding.required_passed_ids("engine", include_sigma_th=True)
    assert with_sigma.index("0.11") == with_sigma.index("0.10-engine") + 1


def test_holdout_is_spent_by_either_form_and_by_a_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """4.3r-T cannot run after 4.3r; a crashed 4.3r counts; partial runs keep the ledger."""
    module = script("run_validation")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    _tiny_repo(tmp_path, monkeypatch)
    identity = binding.build_identity(tmp_path, layers=LayerFlags(), connectome_version="783", assay="h",
                                      fixture="fixture.json")
    calls = {"4.3r": 0, "4.3r-T": 0, "other": 0}

    def make(test_id: str, crash: bool = False):
        def suite() -> binding.ValidationEntry:
            calls[test_id] += 1
            if crash:
                raise RuntimeError("engine died after reading the holdout")
            return binding.ValidationEntry(test_id=test_id, category="verification", identity=identity,
                                           fixture_path="fixture.json", one_use=test_id != "other")
        suite.one_use = test_id != "other"
        return suite

    monkeypatch.setattr(module, "check_holdout_ready", lambda *args, **kwargs: (True, "ok"))
    monkeypatch.setattr(module, "discover_suites", lambda: {"4.3r": make("4.3r", crash=True), "4.3r-T": make("4.3r-T"),
                                                           "other": make("other")})
    crashed = module.run_all(ids=["4.3r"], holdout="4.3r")
    assert calls["4.3r"] == 1 and crashed["one_use_attempts"][0]["test_id"] == "4.3r"
    partial = module.run_all(ids=["other"])
    assert partial["one_use_attempts"][0]["test_id"] == "4.3r"  # a partial run keeps the attempt
    retry = module.run_all(ids=["4.3r"], holdout="4.3r")
    assert calls["4.3r"] == 1 and retry["errors"]
    tubu = module.run_all(ids=["4.3r-T"], holdout="4.3r-T")
    assert calls["4.3r-T"] == 0 and "spent" in tubu["errors"][0]["error"]


def test_carried_one_use_keeps_its_outcome_when_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Carrying a stale one-use record stores validity beside the recorded outcome."""
    module = script("run_validation")
    _tiny_repo(tmp_path, monkeypatch)
    identity = binding.build_identity(tmp_path, layers=LayerFlags(), connectome_version="783", assay="h",
                                      fixture="fixture.json")
    row = binding.ValidationEntry(test_id="4.3r", category="consistency", outcome="failed", identity=identity,
                                  fixture_path="fixture.json", one_use=True).model_dump()
    (tmp_path / "fixture.json").write_text("changed")
    carried = module._rebind_carried(row, tmp_path)
    assert carried["outcome"] == "failed"
    assert carried["measured"]["binding"] == "stale"


def test_detector_edges() -> None:
    """A silent group is off rest; platform agreement keeps its Mac denominator."""
    silent = artefacts.off_rest_detector({"central": 0.0}, {"central": 2.0})
    assert silent["status"] == "off-rest"
    agree = artefacts.platform_agreement_detector({"central_hz": 10.0, "passed": True},
                                                  {"central_hz": 13.0, "passed": True})
    assert agree["relative_central_difference"] == pytest.approx(0.3)
    assert agree["status"] == "platform-sensitive"
