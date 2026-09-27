"""Binding checks: the section 7 compatibility rule and test 0.9."""

from flyonenomics.validation.binding import (
    CompatibilityClass,
    IdentityBlock,
    ValidationEntry,
    binding_of,
    is_compatible,
)


def make_entry(compat: str, **overrides) -> ValidationEntry:
    """Build one ValidationEntry with a fixed identity.

    Units: none. Shapes: scalars.
    """
    identity = {
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
    }
    identity.update(overrides.pop("identity", {}))
    return ValidationEntry(
        test_id="t", category="verification", stub="behaviour" if compat == "development" else None, compatibility=compat, identity=IdentityBlock(**identity),
        data_dependencies=["params"], **overrides,
    )


def base_run(**overrides) -> IdentityBlock:
    """Build the run context matching make_entry defaults.

    Units: none. Shapes: scalars.
    """
    block = {
        "code_commit": "abc",
        "uv_lock_hash": "lock1",
        "provenance_hash": "prov1",
        "data_versions": {"params": "v0.1"},
        "connectome_version": "783",
        "layer_flags": {"background": True, "dopamine_A": True, "transporter_C": True, "dan_fast_synapses": "retain"},
        "fixture_hash": "fix1",
        "assay": "buridan",
        "machine": "m",
        "date": "2026-09-12",
    }
    block.update(overrides)
    return IdentityBlock(**block)


def test_canonical_valid_for_layers_on_v783_run() -> None:
    """Stored 0.3 bare v630 result is valid for the layers-on run.

    Units: none. Shapes: scalars. Test 0.9 case one.
    """
    entry = make_entry(CompatibilityClass.CANONICAL, identity={"connectome_version": "630", "layer_flags": {"dopamine_A": False}})
    run = base_run(layer_flags={"dopamine_A": True, "transporter_C": True},
                   protocol_hash="other")
    valid, _ = is_compatible(entry, run, current_fixture_hash="fix1")
    assert valid
    assert binding_of(entry, run, current_fixture_hash="fix1") == "valid"


def test_matching_layers_stale_on_flag_drift() -> None:
    """Stored 4.3 with dopamine_A false is stale for layers-on.

    Units: none. Shapes: scalars. Test 0.9 case two.
    """
    entry = make_entry(CompatibilityClass.MATCHING_LAYERS,
                       identity={"code_commit": "abc", "uv_lock_hash": "lock1",
                                 "provenance_hash": "prov1",
                                 "data_versions": {"params": "v0.1"},
                                 "layer_flags": {"dopamine_A": False},
                                 "fixture_hash": "fix1"})
    run = base_run(layer_flags={"dopamine_A": True})
    valid, reason = is_compatible(entry, run, current_fixture_hash="fix1")
    assert not valid
    assert "layer" in reason
    assert binding_of(entry, run, current_fixture_hash="fix1") == "stale"


def test_run_bound_stale_on_protocol_drift() -> None:
    """Stored 0.6 for another file is stale for this run.

    Units: none. Shapes: scalars. Test 0.9 case three.
    """
    entry = make_entry(CompatibilityClass.RUN_BOUND, identity={"protocol_hash": "fileA"})
    run = base_run(protocol_hash="fileB")
    valid, _ = is_compatible(entry, run, current_fixture_hash="fix1")
    assert not valid
    assert binding_of(entry, run, current_fixture_hash="fix1") == "stale"


def test_run_bound_valid_on_same_protocol() -> None:
    """Run-bound entries match their own protocol hash.

    Units: none. Shapes: scalars.
    """
    entry = make_entry(CompatibilityClass.RUN_BOUND, identity={"protocol_hash": "fileA"})
    run = base_run(protocol_hash="fileA")
    assert binding_of(entry, run, current_fixture_hash="fix1") == "valid"


def test_uv_lock_drift_stales_everything() -> None:
    """A uv.lock change stales every compatibility class.

    Units: none. Shapes: scalars. Test 0.9 case four.
    """
    run = base_run(uv_lock_hash="lock2")
    for compat in [CompatibilityClass.CANONICAL,
                   CompatibilityClass.MATCHING_LAYERS,
                   CompatibilityClass.RUN_BOUND]:
        entry = make_entry(compat, identity={"uv_lock_hash": "lock1",
                                             "protocol_hash": "acceptance"})
        assert binding_of(entry, run, current_fixture_hash="fix1") == "stale"


def test_development_never_valid() -> None:
    """Development entries are never valid.

    Units: none. Shapes: scalars.
    """
    entry = make_entry(CompatibilityClass.DEVELOPMENT)
    assert binding_of(entry, base_run()) == "stale"


import pytest
from pathlib import Path
from pydantic import ValidationError


@pytest.mark.parametrize("field,value", [("code_commit", "new"), ("provenance_hash", "new"), ("uv_lock_hash", "new")])
@pytest.mark.parametrize("compat", ["canonical", "matching-layers", "run-bound"])
def test_common_drift(field: str, value: str, compat: str) -> None:
    entry = make_entry(compat, identity={"protocol_hash": "protocol"})
    run = base_run(protocol_hash="protocol", **{field: value})
    assert binding_of(entry, run, current_fixture_hash="fix1") == "stale"


@pytest.mark.parametrize("versions", [{}, {"params": "v0.2"}])
def test_missing_or_changed_dependency_is_stale(versions: dict) -> None:
    entry = make_entry("canonical", identity={"data_versions": versions})
    assert binding_of(entry, base_run(data_versions=versions), current_fixture_hash="fix1") == ("stale" if not versions else "valid")
    assert binding_of(make_entry("canonical"), base_run(data_versions=versions), current_fixture_hash="fix1") == "stale"


def test_canonical_uses_its_current_fixture_not_acceptance_fixture(tmp_path: Path) -> None:
    from flyonenomics.validation.binding import sha256_file

    fixture = tmp_path / "bare-v630.json"
    fixture.write_text('{"background": false}')
    entry = make_entry("canonical", fixture_path=fixture.name, identity={"connectome_version": "630", "fixture_hash": sha256_file(fixture)})
    run = base_run(fixture_hash="different-acceptance-file", protocol_hash="different-protocol", machine="other", date="later", data_versions={"params": "v0.1", "unrelated": "changed"})
    assert binding_of(entry, run, repo=tmp_path) == "valid"
    fixture.write_text("changed")
    assert binding_of(entry, run, repo=tmp_path) == "stale"
    fixture.unlink()
    assert binding_of(entry, run, repo=tmp_path) == "stale"


@pytest.mark.parametrize("name,value", [("background", False), ("dopamine_A", False), ("transporter_C", False), ("dan_fast_synapses", "disconnect")])
def test_each_resolved_layer_drift(name: str, value: object) -> None:
    entry = make_entry("matching-layers")
    flags = dict(entry.identity.layer_flags, **{name: value})
    assert binding_of(entry, base_run(layer_flags=flags), current_fixture_hash="fix1") == "stale"


def test_absent_layers_do_not_match_and_absent_phase2_flags_do_not_stale() -> None:
    entry = make_entry("matching-layers")
    assert binding_of(entry, base_run(layer_flags={}), current_fixture_hash="fix1") == "stale"
    flags = dict(entry.identity.layer_flags, learning_D=False, receptor_kinetics_B=False)
    assert binding_of(entry, base_run(layer_flags=flags), current_fixture_hash="fix1") == "valid"


def test_run_bound_ignores_unrelated_fixture() -> None:
    entry = make_entry("run-bound", identity={"protocol_hash": "same"})
    assert binding_of(entry, base_run(protocol_hash="same", fixture_hash="another")) == "valid"


@pytest.mark.parametrize("overrides", [{"compatibility": "typo"}, {"outcome": "typo"}, {"compatibility": "development"}, {"compatibility": "run-bound"}, {"bogus": 1}])
def test_invalid_entry_metadata_rejected(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        ValidationEntry(test_id="x", category="verification", identity=base_run(), **overrides)


def test_build_identity_covers_every_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from flyonenomics.validation import binding
    from flyonenomics.types import LayerFlags

    (tmp_path / "data").mkdir()
    (tmp_path / "data/params-v0.1.yaml").write_text("version: v0.1\n")
    (tmp_path / "data/receptors-v0.1.yaml").write_text("version: r2\n")
    (tmp_path / "data/behaviour-dev.yaml").write_text("version: provisional\n")
    (tmp_path / "data/params-v0.2.yaml").write_text("version: v0.2\n")
    (tmp_path / "data/provenance.json").write_text("{}")
    (tmp_path / "uv.lock").write_text("pinned")
    (tmp_path / "fixture.json").write_text("fixture")
    monkeypatch.setattr(binding, "repo_commit", lambda root: "commit")
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    identity = binding.build_identity(tmp_path, connectome_version="630", layers=LayerFlags(), assay="sugar_reflex", fixture="fixture.json", protocol_hash="validated")
    assert set(identity.model_dump()) == {
        "code_commit", "code_hash", "run_code_hash", "code_scope", "run_code_scope",
        "uv_lock_hash", "provenance_hash", "data_versions", "connectome_version",
        "layer_flags", "fixture_hash", "protocol_hash", "assay", "machine", "date",
        "inputs", "overrides_hash", "platform", "substrate_id",
        "engine_model", "mechanisms",
    }
    assert identity.code_hash.startswith(("git:", "fs:"))
    assert identity.code_scope.startswith(("git:", "fs:"))
    assert identity.run_code_scope == identity.code_scope
    assert identity.platform
    assert identity.substrate_id == "bare"
    assert identity.run_code_hash == identity.code_hash
    # v0.2 files are recorded so an entry depending on them binds on its own run.
    assert identity.data_versions == {"params-v0.1.yaml": "v0.1", "params-v0.2.yaml": "v0.2", "receptors-v0.1.yaml": "r2"}
    assert identity.fixture_hash == binding.sha256_file(tmp_path / "fixture.json")
    assert identity.uv_lock_hash == binding.sha256_file(tmp_path / "uv.lock")
    assert identity.provenance_hash == binding.sha256_file(tmp_path / "data/provenance.json")
    assert identity.machine == "model / chip"
    assert identity.protocol_hash == "validated"
    reordered = identity.model_copy(update={"data_versions": dict(reversed(list(identity.data_versions.items())))})
    assert binding.identity_hash(identity) == binding.identity_hash(reordered)
    (tmp_path / "data/receptors-v0.1.yaml").write_text("{}")
    with pytest.raises(ValueError, match="missing data version"):
        binding.build_identity(tmp_path, connectome_version="630", layers=LayerFlags(), assay="sugar_reflex")


def test_mac_machine_identifier_uses_model_and_chip(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from flyonenomics.validation import binding

    monkeypatch.setattr(binding.platform, "system", lambda: "Darwin")
    calls = []
    def sysctl(args: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(stdout={"hw.model": "Mac17,1\n", "machdep.cpu.brand_string": "Apple M5 Pro\n"}[args[-1]])
    monkeypatch.setattr(binding.subprocess, "run", sysctl)
    assert binding.machine_id() == "Mac17,1 / Apple M5 Pro"
    assert [args[-1] for args in calls] == ["hw.model", "machdep.cpu.brand_string"]


@pytest.mark.parametrize("field", ["code_commit", "uv_lock_hash", "provenance_hash"])
def test_empty_identity_evidence_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        base_run(**{field: ""})


def test_docs_only_commit_keeps_code_hash_entry_valid() -> None:
    """A docs-adjacent commit does not stale a Phase 2 identity. Units: none."""
    entry = make_entry("canonical", identity={"code_hash": "tree:abc", "code_commit": "old"})
    run = base_run(code_hash="tree:abc", code_commit="new")
    assert binding_of(entry, run, current_fixture_hash="fix1") == "valid"


def test_src_content_change_stales_code_hash_entry() -> None:
    """A one-byte src/ change stales a new identity. Units: none."""
    entry = make_entry("canonical", identity={"code_hash": "tree:abc", "code_commit": "same"})
    run = base_run(code_hash="tree:xyz", code_commit="same")
    valid, reason = is_compatible(entry, run, current_fixture_hash="fix1")
    assert not valid
    assert "code hash" in reason
    assert binding_of(entry, run, current_fixture_hash="fix1") == "stale"


def test_phase1_identity_without_code_hash_stales_on_commit() -> None:
    """An identity block without code_hash keeps the code_commit rule. Units: none."""
    entry = make_entry("canonical")
    assert entry.identity.code_hash == ""
    assert entry.identity.run_code_hash == ""
    run = base_run(code_commit="other")
    valid, reason = is_compatible(entry, run, current_fixture_hash="fix1")
    assert not valid
    assert "code commit" in reason
    assert binding_of(entry, run, current_fixture_hash="fix1") == "stale"


def test_run_code_hash_mismatch_does_not_stale_while_code_hash_matches() -> None:
    """Item 77: run_code_hash is recorded beside code_hash but does not stale the entry."""
    entry = make_entry("canonical", identity={"code_hash": "tree:abc", "run_code_hash": "tree:run-a"})
    run = base_run(code_hash="tree:abc", run_code_hash="tree:run-b")
    valid, reason = is_compatible(entry, run, current_fixture_hash="fix1")
    assert valid
    assert reason == "valid"
    stale, why = is_compatible(entry, base_run(code_hash="tree:other", run_code_hash="tree:run-a"),
                               current_fixture_hash="fix1")
    assert not stale
    assert why == "code hash differs"


def test_empty_run_code_hash_keeps_phase1_entry_valid() -> None:
    """An analysed Phase 1 run without a content hash does not extra-stale."""
    entry = make_entry("canonical", identity={"code_hash": "tree:abc", "run_code_hash": ""})
    run = base_run(code_hash="tree:abc", run_code_hash="tree:now")
    valid, reason = is_compatible(entry, run, current_fixture_hash="fix1")
    assert valid
    assert reason == "valid"


def test_build_identity_records_analysed_run_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Level-3 style: run_code_hash can differ from code_hash. Units: none."""
    from flyonenomics.validation import binding
    from flyonenomics.types import LayerFlags

    (tmp_path / "data").mkdir()
    (tmp_path / "data/params-v0.1.yaml").write_text("version: v0.1\n")
    (tmp_path / "data/provenance.json").write_text("{}")
    (tmp_path / "uv.lock").write_text("pinned")
    monkeypatch.setattr(binding, "repo_commit", lambda root: "commit")
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    identity = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex",
        run_code_hash="tree:executed",
    )
    assert identity.run_code_hash == "tree:executed"
    assert identity.code_hash != "tree:executed"
    empty = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex",
        run_code_hash="",
    )
    assert empty.run_code_hash == ""


def test_code_content_hash_changes_when_src_byte_changes(tmp_path: Path) -> None:
    """Filesystem fallback hashes src/ content. Units: none. Shapes: files."""
    from flyonenomics.validation.binding import code_content_hash

    (tmp_path / "src").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "src/a.py").write_text("x")
    (tmp_path / "data/params-v0.1.yaml").write_text("version: v0.1\n")
    (tmp_path / "scripts/run.py").write_text("print(1)\n")
    (tmp_path / "uv.lock").write_text("lock")
    first = code_content_hash(tmp_path)
    assert first.startswith("fs:")
    (tmp_path / "src/a.py").write_text("y")
    second = code_content_hash(tmp_path)
    assert second != first
    (tmp_path / "src/a.py").write_text("x")
    assert code_content_hash(tmp_path) == first
    docs = code_content_hash(tmp_path)
    (tmp_path / "README.md").write_text("docs only")
    assert code_content_hash(tmp_path) == docs


def _git_repo(root: Path) -> None:
    """Create a committed repository with the code trees; units none."""
    import subprocess
    for rel, text in {"src/pkg/a.py": "x = 1\n", "data/params-v0.1.yaml": "version: v0.1\n",
                      "data/provenance.json": "{}", "scripts/run.py": "print(1)\n", "uv.lock": "lock\n",
                      "docs/notes.md": "notes\n", "tests/fixtures/f.json": "{}\n", ".gitignore": "__pycache__/\n"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"]):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _commit(root: Path, message: str) -> None:
    import subprocess
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message],
                   cwd=root, check=True, capture_output=True)


def test_code_hash_on_real_git_commits(tmp_path: Path) -> None:
    """Docs-only commits keep code_hash; a one-byte src/ change moves it; committed equals dirty."""
    from flyonenomics.validation.binding import code_content_hash
    _git_repo(tmp_path)
    clean = code_content_hash(tmp_path)
    assert clean.startswith("git:")
    (tmp_path / "docs/notes.md").write_text("notes, edited\n")
    _commit(tmp_path, "docs only")
    assert code_content_hash(tmp_path) == clean
    (tmp_path / "tests/fixtures/f.json").write_text('{"changed": true}\n')
    _commit(tmp_path, "fixture only: bound by fixture_hash, not code_hash")
    assert code_content_hash(tmp_path) == clean
    (tmp_path / "src/pkg/__pycache__").mkdir()
    (tmp_path / "src/pkg/__pycache__/a.pyc").write_bytes(b"ignored")
    assert code_content_hash(tmp_path) == clean
    (tmp_path / "src/pkg/a.py").write_text("x = 2\n")
    dirty = code_content_hash(tmp_path)
    assert dirty != clean
    _commit(tmp_path, "one byte in src")
    assert code_content_hash(tmp_path) == dirty, "the same bytes committed or not give one hash"
    (tmp_path / "src/pkg/a.py").write_text("x = 1\n")
    assert code_content_hash(tmp_path) == clean
    (tmp_path / "scripts/new.py").write_text("print(2)\n")
    assert code_content_hash(tmp_path) != clean


def test_entry_with_test_fixture_binds_to_a_run_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A canonical entry whose fixture sits under tests/ is valid for a run manifest's identity."""
    from flyonenomics.validation import binding
    from flyonenomics.types import LayerFlags
    _git_repo(tmp_path)
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    identity = binding.build_identity(tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex",
                                      fixture="tests/fixtures/f.json")
    entry = binding.ValidationEntry(test_id="0.8", category="verification", identity=identity,
                                    fixture_path="tests/fixtures/f.json", data_dependencies=["params-v0.1.yaml"])
    run = binding.build_identity(tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex",
                                 protocol_hash="run")
    assert run.code_hash == identity.code_hash
    assert binding.is_compatible(entry, run, repo=tmp_path) == (True, "valid")
    (tmp_path / "docs/notes.md").write_text("later docs\n")
    _commit(tmp_path, "docs")
    later = binding.build_identity(tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex")
    assert later.code_commit != identity.code_commit
    assert binding.is_compatible(entry, later, repo=tmp_path) == (True, "valid")
    (tmp_path / "src/pkg/a.py").write_text("x = 3\n")
    _commit(tmp_path, "src")
    moved = binding.build_identity(tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex")
    assert binding.is_compatible(entry, moved, repo=tmp_path) == (False, "code scope differs")


def test_code_scope_omits_data_tree(tmp_path: Path) -> None:
    """A data-only commit keeps code_scope and moves code_hash. Units: none."""
    from flyonenomics.validation.binding import code_content_hash, code_scope_hash

    _git_repo(tmp_path)
    scope = code_scope_hash(tmp_path)
    content = code_content_hash(tmp_path)
    (tmp_path / "data/params-v0.1.yaml").write_text("version: v0.2\n")
    _commit(tmp_path, "data only")
    assert code_scope_hash(tmp_path) == scope
    assert code_content_hash(tmp_path) != content
