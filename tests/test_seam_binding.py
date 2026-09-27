"""P2 identity binding seam: metadata reads must not demote declared entries."""

from __future__ import annotations

import json
import multiprocessing as mp
import subprocess
import threading
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from flyonenomics import io
from flyonenomics.io import (
    clear_log, flush, logged_paths, merge_logs, read_text, set_log_dir, set_repo_root, suspended_depth, unlogged,
)
from flyonenomics.types import LayerFlags
from flyonenomics.validation import binding
from flyonenomics.validation.execute import bind_entry


@pytest.fixture(autouse=True)
def _restore_io_state(monkeypatch: pytest.MonkeyPatch):
    """Restore the process-global repo root, log directory and log after each test."""
    monkeypatch.delenv("FLYONENOMICS_DEPS_DIR", raising=False)
    root, directory = io.repo_root(), io.log_dir()
    yield
    set_repo_root(None if root == io._REPO else root)
    set_log_dir(directory)
    clear_log()
    assert suspended_depth() == 0


def test_unlogged_read_is_absent_from_the_log(tmp_path: Path) -> None:
    """A read inside unlogged() is not charged. Units: none."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/a.yaml").write_text("x: 1\n")
    set_repo_root(tmp_path)
    clear_log()
    with unlogged():
        read_text(tmp_path / "data/a.yaml")
    assert logged_paths() == []


def test_unlogged_restores_logging_after_exit(tmp_path: Path) -> None:
    """A read after unlogged() is logged again. Units: none."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/a.yaml").write_text("x: 1\n")
    (tmp_path / "data/b.yaml").write_text("y: 2\n")
    set_repo_root(tmp_path)
    clear_log()
    with unlogged():
        read_text(tmp_path / "data/a.yaml")
        with unlogged():
            read_text(tmp_path / "data/a.yaml")
    read_text(tmp_path / "data/b.yaml")
    assert logged_paths() == ["data/b.yaml"]


def test_unlogged_restores_logging_after_exception(tmp_path: Path) -> None:
    """An exception inside unlogged() still restores logging. Units: none."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/a.yaml").write_text("x: 1\n")
    (tmp_path / "data/b.yaml").write_text("y: 2\n")
    set_repo_root(tmp_path)
    clear_log()
    with pytest.raises(RuntimeError, match="boom"):
        with unlogged():
            read_text(tmp_path / "data/a.yaml")
            raise RuntimeError("boom")
    read_text(tmp_path / "data/b.yaml")
    assert "data/a.yaml" not in logged_paths()
    assert logged_paths() == ["data/b.yaml"]


def test_nested_exception_restores_depth_and_logging(tmp_path: Path) -> None:
    """An exception in an inner unlogged() leaves the outer one suspended, then logging resumes."""
    (tmp_path / "data").mkdir()
    for name in ("a", "b", "c"):
        (tmp_path / f"data/{name}.yaml").write_text("x: 1\n")
    set_repo_root(tmp_path)
    clear_log()
    with unlogged():
        with pytest.raises(RuntimeError):
            with unlogged():
                assert suspended_depth() == 2
                raise RuntimeError("inner")
        assert suspended_depth() == 1
        read_text(tmp_path / "data/a.yaml")
    assert suspended_depth() == 0
    read_text(tmp_path / "data/b.yaml")
    assert logged_paths() == ["data/b.yaml"]
    read_text(tmp_path / "data/a.yaml")
    assert logged_paths() == ["data/b.yaml", "data/a.yaml"]


def test_unlogged_does_not_hide_another_threads_read(tmp_path: Path) -> None:
    """Suspension is per thread: a concurrent read on another thread is still logged."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/a.yaml").write_text("x: 1\n")
    set_repo_root(tmp_path)
    clear_log()
    inside, done = threading.Event(), threading.Event()
    seen: list[int] = []

    def worker() -> None:
        inside.wait(5)
        seen.append(suspended_depth())
        read_text(tmp_path / "data/a.yaml")
        done.set()

    thread = threading.Thread(target=worker)
    thread.start()
    with unlogged():
        inside.set()
        assert done.wait(5)
    thread.join()
    assert seen == [0]
    assert logged_paths() == ["data/a.yaml"]


def test_suspended_read_is_absent_from_the_flushed_log(tmp_path: Path) -> None:
    """A read made while suspended is not in deps-<pid>.json or the merged log."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data/a.yaml").write_text("x: 1\n")
    (tmp_path / "data/b.yaml").write_text("y: 2\n")
    deps = tmp_path / "deps"
    set_repo_root(tmp_path)
    clear_log()
    with unlogged():
        read_text(tmp_path / "data/a.yaml")
        written = flush(deps)
    read_text(tmp_path / "data/b.yaml")
    assert written is not None
    assert json.loads(written.read_text())["paths"] == []
    flush(deps)
    assert merge_logs(deps) == ["data/b.yaml"]


def test_parent_suspension_does_not_reach_a_spawned_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A spawned worker started while the parent is suspended still logs its reads (run_validation --workers N)."""
    root = Path(__file__).resolve().parents[1]
    set_repo_root(None)
    deps = tmp_path / "deps"
    monkeypatch.setenv("FLYONENOMICS_DEPS_DIR", str(deps))
    clear_log()
    with unlogged():
        with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn")) as pool:
            assert pool.submit(suspended_depth).result() == 0
            pool.submit(read_text, root / "data/params-v0.1.yaml").result()
            pool.submit(flush, deps).result()
        read_text(root / "data/params-v0.1.yaml")
    assert logged_paths() == []
    assert "data/params-v0.1.yaml" in merge_logs(deps)


def test_build_identity_error_leaves_logging_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing data version raised inside build_identity's unlogged() does not leave the log suspended."""
    _git_repo(tmp_path)
    (tmp_path / "data/params-v0.2.yaml").write_text("other: 1\n")
    _commit(tmp_path, "unversioned")
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    set_repo_root(tmp_path)
    clear_log()
    with pytest.raises(ValueError, match="missing data version"):
        binding.build_identity(
            tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
            declared_inputs=["data/params-v0.2.yaml"],
        )
    assert suspended_depth() == 0
    read_text(tmp_path / "data/params-v0.2.yaml")
    assert logged_paths() == ["data/params-v0.2.yaml"]


def _git_repo(root: Path) -> None:
    """Create a committed repository with versioned data files. Units: none."""
    files = {
        "src/pkg/a.py": "x = 1\n",
        "scripts/run.py": "print(1)\n",
        "uv.lock": "lock\n",
        "data/params-v0.1.yaml": "version: v0.1\n",
        "data/params-v0.2.yaml": "version: v0.2\n",
        "data/behaviour-v0.1.yaml": "version: v0.1\n",
        "data/provenance.json": "{}\n",
        "tests/fixtures/f.json": "{}\n",
        ".gitignore": "__pycache__/\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"]):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _commit(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message],
        cwd=root, check=True, capture_output=True,
    )


def _p2_entry(root: Path, monkeypatch: pytest.MonkeyPatch) -> binding.ValidationEntry:
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    set_repo_root(root)
    identity = binding.build_identity(
        root, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        declared_inputs=["data/params-v0.2.yaml"], fixture="data/params-v0.2.yaml",
    )
    return binding.ValidationEntry(
        test_id="3.1r-alg", category="verification", identity=identity,
        declared_inputs=["data/params-v0.2.yaml"], fixture_path="data/params-v0.2.yaml",
        data_dependencies=["params-v0.2.yaml"],
    )


def test_p2_version_collection_is_scoped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A P2 identity records versions of declared numeric files only."""
    _git_repo(tmp_path)
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    identity = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        declared_inputs=["data/params-v0.2.yaml"],
    )
    assert identity.data_versions == {"params-v0.2.yaml": "v0.2"}
    phase1 = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
    )
    assert phase1.data_versions == {
        "behaviour-v0.1.yaml": "v0.1",
        "params-v0.1.yaml": "v0.1",
        "params-v0.2.yaml": "v0.2",
    }


def test_metadata_reads_are_not_logged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Version collection and provenance hashing do not charge the log."""
    _git_repo(tmp_path)
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    set_repo_root(tmp_path)
    clear_log()
    set_log_dir(tmp_path)
    binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        declared_inputs=["data/params-v0.2.yaml"],
    )
    logged = logged_paths()
    assert "data/behaviour-v0.1.yaml" not in logged
    assert "data/params-v0.1.yaml" not in logged
    assert "data/provenance.json" not in logged


def test_provenance_is_common_identity_dependency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A logged provenance.json path does not demote a declared P2 entry."""
    _git_repo(tmp_path)
    entry = _p2_entry(tmp_path, monkeypatch)
    updated = binding.apply_logged_inputs(
        entry, ["data/params-v0.2.yaml", "data/provenance.json"], tmp_path,
    )
    assert updated.compatibility == "canonical"
    assert "undeclared_inputs" not in updated.measured
    assert "data/provenance.json" not in updated.identity.inputs
    assert "data/params-v0.2.yaml" in updated.identity.inputs


def test_undeclared_numeric_read_still_demotes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuine undeclared numeric read still demotes to development."""
    _git_repo(tmp_path)
    entry = _p2_entry(tmp_path, monkeypatch)
    updated = binding.apply_logged_inputs(
        entry, ["data/params-v0.2.yaml", "data/params-v0.1.yaml"], tmp_path,
    )
    assert updated.compatibility == "development"
    assert updated.measured.get("binding_reason") == "undeclared input"
    assert updated.measured.get("undeclared_inputs") == ["data/params-v0.1.yaml"]


def test_unrelated_versioned_file_keeps_p2_entry_valid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrelated behaviour YAML change leaves a declared P2 entry valid."""
    _git_repo(tmp_path)
    entry = _p2_entry(tmp_path, monkeypatch)
    bound = binding.apply_logged_inputs(entry, ["data/params-v0.2.yaml"], tmp_path)
    (tmp_path / "data/behaviour-v0.1.yaml").write_text("version: v0.1\nchanged: true\n")
    _commit(tmp_path, "unrelated behaviour")
    run = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        declared_inputs=["data/params-v0.2.yaml"], fixture="data/params-v0.2.yaml",
    )
    valid, reason = binding.is_compatible(bound, run, repo=tmp_path)
    assert valid
    assert reason == "valid"
    assert bound.compatibility == "canonical"


def test_phase1_identity_still_records_every_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 1 identities keep the all-versions map and ignore the P2 log union."""
    _git_repo(tmp_path)
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    identity = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex",
        fixture="tests/fixtures/f.json",
    )
    assert identity.data_versions == {
        "behaviour-v0.1.yaml": "v0.1",
        "params-v0.1.yaml": "v0.1",
        "params-v0.2.yaml": "v0.2",
    }
    entry = binding.ValidationEntry(
        test_id="0.9", category="verification", identity=identity,
        fixture_path="tests/fixtures/f.json", data_dependencies=["params-v0.1.yaml"],
    )
    run = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex",
    )
    assert binding.is_compatible(entry, run, repo=tmp_path) == (True, "valid")
    unchanged = binding.apply_logged_inputs(
        entry, ["data/behaviour-v0.1.yaml", "data/provenance.json"], tmp_path,
    )
    assert unchanged.compatibility == "canonical"
    assert unchanged is entry
    (tmp_path / "data/params-v0.1.yaml").write_text("version: v0.9\n")
    _commit(tmp_path, "params version")
    later = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="sugar_reflex",
    )
    valid, reason = binding.is_compatible(entry, later, repo=tmp_path)
    assert not valid
    assert "differs" in reason


def test_bind_entry_passes_declared_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bind_entry constructs the current identity from the entry's declared inputs."""
    _git_repo(tmp_path)
    entry = _p2_entry(tmp_path, monkeypatch)
    set_repo_root(tmp_path)
    clear_log()
    set_log_dir(tmp_path)
    bound = bind_entry(entry, root=tmp_path)
    assert bound.outcome == "passed"
    assert bound.compatibility == "canonical"
    logged = logged_paths()
    assert "data/behaviour-v0.1.yaml" not in logged
    assert "data/provenance.json" not in logged


def test_undeclared_or_mistyped_data_dependency_is_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A P2 data_dependencies name outside declared_inputs fails binding instead of passing silently."""
    _git_repo(tmp_path)
    entry = _p2_entry(tmp_path, monkeypatch)
    run = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        declared_inputs=["data/params-v0.2.yaml"], fixture="data/params-v0.2.yaml",
    )
    assert binding.is_compatible(entry, run, repo=tmp_path) == (True, "valid")
    for name in ("params-v0.1.yaml", "params-v0.2.yml"):
        wrong = entry.model_copy(update={"data_dependencies": [name]})
        assert binding.is_compatible(wrong, run, repo=tmp_path) == (False, f"data dependency not declared: {name}")
        stale = bind_entry(wrong, root=tmp_path)
        assert stale.outcome == "stale"
        assert stale.measured["binding_reason"] == f"data dependency not declared: {name}"
    # The runner's run identity records every version; a declared dependency agrees there too.
    full = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        fixture="data/params-v0.2.yaml",
    )
    assert binding.is_compatible(entry, full, repo=tmp_path) == (True, "valid")


def test_declared_unversioned_dependency_is_bound_by_its_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared file without -vX.Y has no version string; its blob still stales the entry."""
    _git_repo(tmp_path)
    (tmp_path / "data/config.yaml").write_text("value: 1\n")
    _commit(tmp_path, "config")
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    set_repo_root(tmp_path)
    kwargs = dict(connectome_version="783", layers=LayerFlags(), assay="binding",
                  declared_inputs=["data/config.yaml"], fixture="tests/fixtures/f.json")
    identity = binding.build_identity(tmp_path, **kwargs)
    entry = binding.ValidationEntry(
        test_id="c", category="verification", identity=identity, declared_inputs=["data/config.yaml"],
        data_dependencies=["config.yaml"], fixture_path="tests/fixtures/f.json",
    )
    assert binding.is_compatible(entry, binding.build_identity(tmp_path, **kwargs), repo=tmp_path) == (True, "valid")
    (tmp_path / "data/config.yaml").write_text("value: 2\n")
    _commit(tmp_path, "config byte")
    valid, reason = binding.is_compatible(entry, binding.build_identity(tmp_path, **kwargs), repo=tmp_path)
    assert not valid and reason == "input blob differs: data/config.yaml"


def test_declared_numeric_file_change_stales_p2_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing the declared data/params-v0.2.yaml, bytes or version, stales the P2 entry."""
    _git_repo(tmp_path)
    entry = binding.apply_logged_inputs(_p2_entry(tmp_path, monkeypatch), ["data/params-v0.2.yaml"], tmp_path)
    before = entry.identity.model_dump()
    for text in ("version: v0.2\nchanged: 1\n", "version: v0.3\n"):
        (tmp_path / "data/params-v0.2.yaml").write_text(text)
        _commit(tmp_path, "declared change")
        run = binding.build_identity(
            tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
            declared_inputs=["data/params-v0.2.yaml"], fixture="data/params-v0.2.yaml",
        )
        valid, reason = binding.is_compatible(entry, run, repo=tmp_path)
        assert not valid
        assert reason in ("canonical fixture missing or hash differs", "input blob differs: data/params-v0.2.yaml")
        assert run.model_dump() != before
    (tmp_path / "data/params-v0.2.yaml").write_text("version: v0.2\n")
    _commit(tmp_path, "restore")
    moved = entry.model_copy(update={"fixture_path": "tests/fixtures/f.json",
                                     "identity": entry.identity.model_copy(update={
                                         "fixture_hash": binding.sha256_file(tmp_path / "tests/fixtures/f.json")})})
    (tmp_path / "data/params-v0.2.yaml").write_text("version: v0.2\nchanged: 2\n")
    _commit(tmp_path, "declared bytes only")
    run = binding.build_identity(
        tmp_path, connectome_version="783", layers=LayerFlags(), assay="spontaneous",
        declared_inputs=["data/params-v0.2.yaml"], fixture="tests/fixtures/f.json",
    )
    assert binding.is_compatible(moved, run, repo=tmp_path) == (False, "input blob differs: data/params-v0.2.yaml")


def test_provenance_change_stales_p2_entry_through_provenance_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """data/provenance.json is not an undeclared input, but a change to it still stales the entry."""
    _git_repo(tmp_path)
    entry = binding.apply_logged_inputs(
        _p2_entry(tmp_path, monkeypatch), ["data/params-v0.2.yaml", "data/provenance.json"], tmp_path,
    )
    assert entry.compatibility == "canonical"
    assert "data/provenance.json" not in entry.identity.inputs
    kwargs = dict(connectome_version="783", layers=LayerFlags(), assay="spontaneous",
                  declared_inputs=["data/params-v0.2.yaml"], fixture="data/params-v0.2.yaml")
    assert binding.is_compatible(entry, binding.build_identity(tmp_path, **kwargs), repo=tmp_path) == (True, "valid")
    (tmp_path / "data/provenance.json").write_text('{"changed": true}\n')
    _commit(tmp_path, "provenance")
    run = binding.build_identity(tmp_path, **kwargs)
    assert run.provenance_hash != entry.identity.provenance_hash
    assert binding.is_compatible(entry, run, repo=tmp_path) == (False, "provenance hash differs")
    assert bind_entry(entry, root=tmp_path).measured["binding_reason"] == "provenance hash differs"


_WP19_METADATA_FILES = (
    "behaviour-base-v0.2.yaml", "behaviour-v0.1.yaml", "compartments-v0.1.yaml", "dopamine-v0.1.yaml",
    "params-v0.1.yaml", "populations-v0.1.yaml", "populations-v0.2.yaml", "receptors-v0.1.yaml",
    "transmitters-v0.2.yaml",
)


def _rest_alg_repo(root: Path) -> None:
    """A committed repository holding every versioned file WP19's before-run charged. Units: none."""
    _git_repo(root)
    for name in _WP19_METADATA_FILES:
        version = name.rsplit("-", 1)[1].removesuffix(".yaml")
        (root / "data" / name).write_text(f"version: {version}\n")
    (root / "data/params-v0.2.yaml").write_text("version: v0.2\nda.R_min: 0.5\n")
    _commit(root, "versioned data")


@pytest.mark.parametrize("extra_read", [None, "data/params-v0.1.yaml"])
def test_rest_alg_shaped_entry_binds_canonical_through_run_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra_read: str | None,
) -> None:
    """The 3.1r-alg gate without lane/w19 code: suite, bind_entry, merged log and _attach_log.

    The suite mirrors levelrest.entry("3.1r-alg"): it reads data/params-v0.2.yaml through io and
    declares only that path. The result is canonical with declared-inputs-only identity and no
    binding_reason; one extra numeric read still demotes it.
    """
    import importlib.util

    from flyonenomics.io import read_yaml

    _rest_alg_repo(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "seam_run_validation", Path(__file__).resolve().parents[1] / "scripts/run_validation.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    inputs = ["data/params-v0.2.yaml"]

    def suite() -> binding.ValidationEntry:
        assert read_yaml(tmp_path / "data/params-v0.2.yaml")["da.R_min"] == 0.5
        if extra_read is not None:
            read_yaml(tmp_path / extra_read)
        identity = binding.build_identity(
            tmp_path, connectome_version="783", layers=LayerFlags(background=True), assay="spontaneous",
            declared_inputs=inputs, fixture="data/params-v0.2.yaml",
        )
        return binding.ValidationEntry(
            test_id="3.1r-alg", category="verification", outcome="passed", identity=identity,
            measured={"checks": {"fixed_point": True}}, declared_inputs=inputs,
            fixture_path="data/params-v0.2.yaml",
        )

    monkeypatch.setattr(module, "discover_suites", lambda: {"3.1r-alg": suite})
    status = module.run_all(output=tmp_path / "out/status.json", ids=["3.1r-alg"], workers=1)
    assert status["errors"] == []
    (row,) = status["results"]
    assert row["outcome"] == "passed"
    assert row["identity"]["data_versions"] == {"params-v0.2.yaml": "v0.2"}
    if extra_read is None:
        assert row["compatibility"] == "canonical"
        assert "binding_reason" not in row["measured"]
        assert list(row["identity"]["inputs"]) == inputs
    else:
        assert row["compatibility"] == "development"
        assert row["measured"]["binding_reason"] == "undeclared input"
        assert row["measured"]["undeclared_inputs"] == [extra_read]
