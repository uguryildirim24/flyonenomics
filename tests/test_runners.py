"""Exercise suite discovery, binding, process results, atomic writes, and calibration order."""

import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import MappingProxyType
from unittest.mock import Mock

import pytest

from flyonenomics.types import LayerFlags
from flyonenomics.validation import binding

ROOT = Path(__file__).resolve().parents[1]


def script(name: str):
    spec = importlib.util.spec_from_file_location(f"review_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = script("run_validation")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(binding, "repo_commit", lambda root: "code")
    monkeypatch.setattr(binding, "machine_id", lambda: "model / chip")
    (tmp_path / "data").mkdir()
    (tmp_path / "data/params-v0.1.yaml").write_text("version: v0.1\n")
    (tmp_path / "data/provenance.json").write_text("{}")
    (tmp_path / "uv.lock").write_text("locked")
    (tmp_path / "fixture.json").write_text("fixture")
    identity = binding.build_identity(tmp_path, layers=LayerFlags(), connectome_version="630", assay="sugar_reflex", fixture="fixture.json")
    entry = binding.ValidationEntry(test_id="0.3", category="empirical replay", identity=identity, fixture_path="fixture.json", data_dependencies=["params-v0.1.yaml"])
    return module, entry


@pytest.fixture
def discovery_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import flyonenomics.validation
    monkeypatch.setattr(flyonenomics.validation, "__path__", [str(tmp_path)])
    (tmp_path / "r1nested").mkdir()
    (tmp_path / "r1nested/__init__.py").write_text("")
    (tmp_path / "r1nested/level.py").write_text("from types import MappingProxyType\nSUITE = MappingProxyType({'nested': lambda: None})\n")
    (tmp_path / "r1top.py").write_text("SUITE = {'top': lambda: None}\n")
    importlib.invalidate_caches()
    yield tmp_path
    for name in list(sys.modules):
        if name.startswith("flyonenomics.validation.r1"):
            del sys.modules[name]


def test_discovers_nested_suites_and_general_mappings(discovery_tree: Path) -> None:
    assert set(script("run_validation").discover_suites()) == {"top", "nested"}


@pytest.mark.parametrize("suite,exception", [({"nested": lambda: None}, ValueError), ({"bad": 1}, TypeError), (["invalid"], TypeError)])
def test_discovery_rejects_duplicates_and_invalid_registrations(discovery_tree: Path, suite: object, exception: type[Exception]) -> None:
    top = importlib.import_module("flyonenomics.validation.r1top")
    top.SUITE = suite
    with pytest.raises(exception):
        script("run_validation").discover_suites()


def test_runner_keeps_typed_results_and_continues_after_infrastructure_errors(runner, monkeypatch: pytest.MonkeyPatch) -> None:
    module, entry = runner
    def broken():
        raise RuntimeError("boom")
    monkeypatch.setattr(module, "discover_suites", lambda: {"0.3": lambda: entry, "broken": broken, "invalid": lambda: None, "wrong-id": lambda: entry})
    status = module.run_all()
    assert len(status["results"]) == 1
    assert status["results"][0]["outcome"] == "passed"
    assert {error["test_id"] for error in status["errors"]} == {"broken", "invalid", "wrong-id"}
    stored = json.loads((module.ROOT / "validation/status.json").read_text())
    assert stored == status
    binding.ValidationEntry.model_validate(stored["results"][0])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 1


def test_runner_marks_drift_stale(runner, monkeypatch: pytest.MonkeyPatch) -> None:
    module, entry = runner
    monkeypatch.setattr(module, "discover_suites", lambda: {"0.3": lambda: entry})
    (module.ROOT / "fixture.json").write_text("changed")
    status = module.run_all()
    assert status["results"][0]["outcome"] == "stale"
    assert "fixture" in status["results"][0]["measured"]["binding_reason"]


def test_development_is_recorded_without_becoming_component_evidence(runner, monkeypatch: pytest.MonkeyPatch) -> None:
    module, entry = runner
    entry = entry.model_copy(update={"compatibility": "development", "stub": "behaviour", "outcome": "recorded"})
    monkeypatch.setattr(module, "discover_suites", lambda: {"0.3": lambda: entry})
    assert module.run_all()["results"][0]["outcome"] == "recorded"
    assert binding.binding_of(entry, entry.identity, repo=module.ROOT) == "stale"


def test_zero_suite_status_explicitly_disclaims_coverage(runner, monkeypatch: pytest.MonkeyPatch) -> None:
    module, entry = runner
    monkeypatch.setattr(module, "discover_suites", lambda: {})
    status = module.run_all()
    assert status["results"] == [] and status["errors"] == []
    assert status["coverage"] == "no suites registered"
    module.main()


def test_atomic_status_failure_leaves_old_file_and_cleans_temp(runner, monkeypatch: pytest.MonkeyPatch) -> None:
    module, entry = runner
    monkeypatch.setattr(module, "discover_suites", lambda: {"0.3": lambda: entry})
    dest = module.ROOT / "status.json"
    dest.write_text("previous status")
    original_replace = Path.replace
    def fail_replace(source: Path, target: Path):
        if target == dest:
            assert source.parent == dest.parent
            assert json.loads(source.read_text())["results"][0]["test_id"] == "0.3"
            raise OSError("interrupted rename")
        return original_replace(source, target)
    before = set(module.ROOT.iterdir())
    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted rename"):
        module.run_all(dest)
    assert dest.read_text() == "previous status"
    assert set(module.ROOT.iterdir()) == before


def test_calibration_executes_fixed_order(monkeypatch: pytest.MonkeyPatch) -> None:
    module = script("calibrate")
    monkeypatch.setattr(module, "discover_stages", lambda: dict(module.STAGES))
    calls = []
    for name in reversed(module.ORDER):
        module.register(name, lambda name=name: calls.append(name) or {"status": "recorded"})
    assert list(module.run_stages()) == ["K1", "K2", "sign", "K3"]
    assert calls == ["K1", "K2", "sign", "K3"]
    with pytest.raises(ValueError, match="duplicate"):
        module.register("K1", lambda: {})
    with pytest.raises(ValueError, match="unknown"):
        module.register("K4", lambda: {})


def test_calibration_skipped_k1_does_not_block_k2(monkeypatch: pytest.MonkeyPatch) -> None:
    module = script("calibrate")
    called: list[str] = []
    stages = {"K1": lambda: {"status": "skipped", "reason": "item 47"},
              "K2": lambda: called.append("K2") or {"status": "recorded"},
              "sign": lambda: {"status": "blocked", "reason": "waits for qualified K2"}}
    monkeypatch.setattr(module, "discover_stages", lambda: stages)
    result = module.run_stages()
    assert result["K1"]["status"] == "skipped"
    assert result["K2"]["status"] == "recorded" and called == ["K2"]
    assert result["sign"]["status"] == "blocked"
    assert result["K3"] == {"status": "blocked", "reason": "requires sign"}


@pytest.mark.parametrize("failure", ["missing", "raises", "failed", "unavailable", "invalid", "blocked"])
def test_calibration_never_skips_failed_predecessor(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    module = script("calibrate")
    monkeypatch.setattr(module, "discover_stages", lambda: dict(module.STAGES))
    module.register("K1", lambda: {"status": "recorded"})
    if failure != "missing":
        def k2():
            if failure == "raises":
                raise RuntimeError("failed K2")
            return {"status": failure}
        module.register("K2", k2)
    later = Mock(return_value={"status": "recorded"})
    module.register("sign", later)
    module.register("K3", later)
    result = module.run_stages()
    if failure == "blocked":
        assert result["K2"] == {"status": "blocked"}
    assert result["sign"]["status"] == "blocked"
    assert result["K3"]["status"] == "blocked"
    later.assert_not_called()
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 1


def test_real_behaviour_stages_register_final_functions() -> None:
    from flyonenomics.behaviour import buridan

    module = script("calibrate")
    discovered = module.discover_stages()
    assert discovered["sign"] is buridan.final_sign_check
    assert discovered["K3"] is buridan.final_k3
    assert discovered["sign"] is not buridan.DEV_STAGE["sign"]
    assert discovered["K3"] is not buridan.DEV_STAGE["K3"]


def test_calibration_discovers_owner_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import flyonenomics.drive
    from flyonenomics.neuromod import calibration
    monkeypatch.setattr(flyonenomics.drive, "__path__", [str(tmp_path)])
    monkeypatch.setattr(calibration, "STAGE", {})
    (tmp_path / "r1calibration.py").write_text("STAGE = {'K1': lambda: {'status': 'recorded', 'objective': 1}}\n")
    importlib.invalidate_caches()
    try:
        module = script("calibrate")
        assert module.run_stages()["K1"] == {"status": "recorded", "objective": 1}
    finally:
        sys.modules.pop("flyonenomics.drive.r1calibration", None)


@pytest.mark.parametrize("configuration", ["canonical", "matching-layers", "run-bound", "development"])
@pytest.mark.parametrize("outcome", ["failed", "stale", "unqualified"])
def test_validation_exit_respects_configuration_class(monkeypatch, configuration, outcome):
    module = script("run_validation")
    monkeypatch.setattr(module, "run_all", lambda: {"errors": [], "results": [
        {"compatibility": configuration, "outcome": outcome}]})
    if configuration == "development":
        module.main()
    else:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == 1


@pytest.mark.parametrize("skipped", ["K2", "sign", "K3"])
def test_only_item47_k1_can_skip_without_blocking(monkeypatch, skipped):
    module = script("calibrate")
    stages = {name: (lambda name=name: {"status": "skipped" if name == skipped else "passed", "reason": "item 47"})
              for name in module.ORDER}
    monkeypatch.setattr(module, "discover_stages", lambda: stages)
    results = module.run_stages()
    for name in module.ORDER[module.ORDER.index(skipped) + 1:]:
        assert results[name]["status"] == "blocked"
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 1
    assert not module.nonblocking("K1", {"status": "skipped", "reason": "not run"})


def test_bare_replay_entries_read_q_record_without_an_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """1.4-bare and 2.2-bare replay the qualified Q record; Hz, checksum, never re-executed."""
    from flyonenomics.engine import brian_engine
    from flyonenomics.validation import level0
    from flyonenomics.validation.binding import sha256_file
    from flyonenomics.validation.level1 import test_1_4_bare
    from flyonenomics.validation.level2 import test_2_2_bare

    def no_engine(*args, **kwargs):
        raise AssertionError("bare replay entries must not build an engine or an isolated measurement")

    monkeypatch.setattr(brian_engine.BrianEngine, "__init__", no_engine)
    monkeypatch.setattr(level0, "run_isolated", no_engine)
    checksum = sha256_file(ROOT / "data" / "dopamine-v0.1.yaml")
    bare_14 = test_1_4_bare()
    assert bare_14.test_id == "1.4-bare"
    assert bare_14.compatibility == "canonical" and bare_14.stub is None
    assert bare_14.outcome == "passed"
    assert bare_14.measured["mean_hz"] == 56.8
    assert bare_14.measured["minimum_hz"] == 48.0
    assert bare_14.measured["record_sha256"] == checksum
    assert bare_14.measured["never_reexecuted"] is True
    bare_22 = test_2_2_bare()
    assert bare_22.test_id == "2.2-bare"
    assert bare_22.compatibility == "canonical" and bare_22.stub is None
    assert bare_22.outcome == "passed"
    assert bare_22.measured["median_hz"] == 0.0
    assert round(bare_22.measured["percent_above_50_hz"], 4) == 0.0325
    assert bare_22.measured["record_sha256"] == checksum
    assert bare_22.measured["never_reexecuted"] is True
    suites = script("run_validation").discover_suites()
    assert suites["1.4-bare"] is test_1_4_bare
    assert suites["2.2-bare"] is test_2_2_bare


@pytest.mark.parametrize("edit, failing", [
    (lambda table: table.update(qualified=False), ("1.4-bare", "2.2-bare")),
    (lambda table: table["qualification"]["1.4"].update(mean_hz=50.0), ("1.4-bare",)),
    (lambda table: table["qualification"]["1.4"].update(minimum_hz=39.9), ("1.4-bare",)),
    (lambda table: table["qualification"]["2.2"].update(median_hz=5.1), ("2.2-bare",)),
    (lambda table: table["qualification"]["2.2"].update(fraction_above_50_hz=0.01), ("2.2-bare",)),
])
def test_bare_replay_entries_apply_items_60_and_61_to_the_record(monkeypatch: pytest.MonkeyPatch, edit, failing) -> None:
    """The replayed outcome follows the SPEC rule on the record's values, not fixed numbers."""
    import copy
    import yaml
    from flyonenomics.validation.level1 import test_1_4_bare
    from flyonenomics.validation.level2 import test_2_2_bare
    record = yaml.safe_load((ROOT / "data/dopamine-v0.1.yaml").read_text())
    real_load = yaml.safe_load

    def doctored(text):
        table = real_load(text)
        if isinstance(table, dict) and table.get("qualification") == record["qualification"]:
            table = copy.deepcopy(table)
            edit(table)
        return table

    monkeypatch.setattr(yaml, "safe_load", doctored)
    outcomes = {"1.4-bare": test_1_4_bare().outcome, "2.2-bare": test_2_2_bare().outcome}
    assert outcomes == {test_id: "failed" if test_id in failing else "passed" for test_id in outcomes}


def test_0_8_class_follows_executed_manifest_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """0.8 is canonical when the invariance manifests name no stubs."""
    from flyonenomics.orchestrator import verification
    from flyonenomics.validation.level0 import test_0_8
    measured = {"runs": [{"run_id": "r", "reverse": False, "workers": 1, "live": False, "stubs": []}],
                "arena_reset": True, "all_tables_and_metrics_identical": True, "tables_per_run": 1,
                "settle_s": {"0": 0.02, "1": 0.04, "2": 0.03}}
    monkeypatch.delenv("FLYONENOMICS_INVARIANCE_EVIDENCE", raising=False)
    monkeypatch.setattr(verification, "check_invariance", lambda root: measured)
    entry = test_0_8()
    assert entry.compatibility == "canonical" and entry.stub is None
    measured["runs"][0]["stubs"] = ["IdentityBehaviour"]
    development = test_0_8()
    assert development.compatibility == "development" and development.stub == "IdentityBehaviour"
    # A run row without its manifest's stubs list cannot default to canonical.
    del measured["runs"][0]["stubs"]
    with pytest.raises(ValueError, match="stubs list"):
        test_0_8()
    measured["runs"] = []
    with pytest.raises(ValueError, match="stubs list"):
        test_0_8()


def test_caffeinate_defaults_on_for_acceptance_and_holds_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance runs hold caffeinate -ims; other files stay off unless flagged."""
    from unittest.mock import Mock
    module = script("run_experiment")
    acceptance = Path("data/experiments/acceptance-wt-mph-open-loop.json")
    sugar = Path("data/experiments/sugar-reflex.json")
    assert module.is_acceptance_experiment(acceptance)
    assert not module.is_acceptance_experiment(sugar)
    assert module.resolve_caffeinate(acceptance, None) is True
    assert module.resolve_caffeinate(sugar, None) is False
    assert module.resolve_caffeinate(sugar, True) is True
    assert module.resolve_caffeinate(acceptance, False) is False
    holder = Mock()
    popen = Mock(return_value=holder)
    monkeypatch.setattr(module.subprocess, "Popen", popen)
    assert module.hold_caffeinate(4321) is holder
    popen.assert_called_once_with(("caffeinate", "-ims", "-w", "4321"))


def test_omitted_workers_flag_passes_none_auto_passes_auto(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Item 76: omitted --workers is None (Params); only --workers auto asks the budget."""
    module = script("run_experiment")
    seen: dict[str, object] = {}

    def fake_run(experiment, store, n_workers=None, **kwargs):
        seen["n_workers"] = n_workers
        return "run-id"

    store = Mock()
    store.validate_run.return_value = []
    store.run_path.return_value = tmp_path
    (tmp_path / "status.json").write_text(json.dumps({"state": "done"}) + "\n")
    monkeypatch.setattr(module, "load_experiment", lambda path: object())
    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module, "ResultsStore", lambda root: store)
    monkeypatch.setattr(module, "read_json", lambda path: {"state": "done"})
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "data/experiments/sugar-reflex.json",
                                      "--runs-dir", str(tmp_path)])
    module.main()
    assert seen["n_workers"] is None
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "data/experiments/sugar-reflex.json",
                                      "--workers", "auto", "--runs-dir", str(tmp_path)])
    module.main()
    assert seen["n_workers"] == "auto"
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "data/experiments/sugar-reflex.json",
                                      "--workers", "12", "--runs-dir", str(tmp_path)])
    module.main()
    assert seen["n_workers"] == 12


def _pid_alive(pid: int) -> bool:
    import os
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_gone(pid: int, timeout_s: float = 10.0) -> bool:
    import time
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return False


CAFFEINATE = pytest.mark.skipif(sys.platform != "darwin" or not Path("/usr/bin/caffeinate").exists(),
                                reason="caffeinate is macOS only")


@CAFFEINATE
@pytest.mark.parametrize("error", [RuntimeError("engine failed"), KeyboardInterrupt()])
def test_caffeinate_released_when_run_raises_or_is_interrupted(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    """An error or Ctrl-C inside the run stops the real caffeinate holder; no orphan."""
    module = script("run_experiment")
    holders = []
    real_hold = module.hold_caffeinate

    def hold(pid: int | None = None):
        holders.append(real_hold(pid))
        return holders[-1]

    def failing_run(*args, **kwargs):
        assert holders and holders[0].poll() is None, "caffeinate must be held while the run executes"
        raise error

    monkeypatch.setattr(module, "hold_caffeinate", hold)
    monkeypatch.setattr(module, "load_experiment", lambda path: object())
    monkeypatch.setattr(module, "run", failing_run)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "data/experiments/acceptance-wt-mph-open-loop.json",
                                      "--runs-dir", str(ROOT / ".never-created")])
    monkeypatch.setattr(module, "ResultsStore", lambda root: Mock())
    with pytest.raises(type(error)):
        module.main()
    assert len(holders) == 1
    assert holders[0].poll() is not None
    assert _wait_gone(holders[0].pid)


@CAFFEINATE
def test_caffeinate_exits_with_a_killed_runner() -> None:
    """SIGKILL skips `finally`; caffeinate -w still exits with the run process."""
    import signal
    import subprocess
    code = ("import importlib.util,sys,time;"
            f"spec=importlib.util.spec_from_file_location('r', {str(ROOT / 'scripts/run_experiment.py')!r});"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
            "h=m.hold_caffeinate();print(h.pid,flush=True);time.sleep(60)")
    runner = subprocess.Popen([sys.executable, "-c", code], cwd=ROOT, stdout=subprocess.PIPE, text=True,
                              start_new_session=True)
    try:
        holder_pid = int(runner.stdout.readline())
        assert _pid_alive(holder_pid)
        runner.send_signal(signal.SIGKILL)
        runner.wait(timeout=10)
        assert _wait_gone(holder_pid), "caffeinate outlived the killed run"
    finally:
        if runner.poll() is None:
            runner.kill()


def test_serial_and_parallel_binders_agree_on_analysed_run_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A level-3 style entry whose analysed run hash differs binds the same serially and in a pool worker."""
    from flyonenomics.validation import execute
    module = script("run_validation")
    identity = binding.build_identity(ROOT, connectome_version="783", layers=LayerFlags(background=False),
                                      assay="buridan", fixture="data/experiments/dose-series.json",
                                      run_code_hash="git:analysed-run")
    entry = binding.ValidationEntry(test_id="3.x", category="consistency", outcome="passed", identity=identity,
                                    fixture_path="data/experiments/dose-series.json",
                                    data_dependencies=["params-v0.1.yaml"])
    monkeypatch.setattr(module, "discover_suites", lambda: {"3.x": lambda: entry})
    monkeypatch.setattr(execute, "discover_suites", lambda: {"3.x": lambda: entry})
    serial = module.run_one_suite("3.x")
    pooled = execute.run_one_suite("3.x")
    assert serial["error"] is None and pooled["error"] is None
    for row in (serial, pooled):
        row["entry"]["identity"].pop("date")
    assert serial == pooled
    assert serial["entry"]["outcome"] == "passed"
