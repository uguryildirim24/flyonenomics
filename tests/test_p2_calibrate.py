"""Phase 2 calibrate.py dispatcher and resume (WP15)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def script(name: str):
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(f"p2_{name}", root / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase1_order_unchanged() -> None:
    module = script("calibrate")
    assert module.ORDER == ["K1", "K2", "sign", "K3"]


def test_phase2_dispatch_and_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = script("calibrate")
    monkeypatch.setattr(module, "RECORDS_P2", tmp_path / "p2")
    monkeypatch.setattr(module, "STAGES", {})
    calls: list[str] = []
    identity = {"C0": "c0-a"}

    def c0():
        calls.append("C0")
        return {"status": "passed"}

    c0.input_identity = lambda: identity["C0"]

    def r1():
        calls.append("R1")
        return {"status": "passed"}

    module.register("C0", c0)
    module.register("R1", r1)
    monkeypatch.setattr(module, "discover_stages", lambda phase=2: dict(module.STAGES))
    first = module.run_stages(phase=2)
    assert first["C0"]["status"] == "passed"
    assert (tmp_path / "p2" / "C0.json").is_file()
    assert calls == ["C0", "R1"]
    stored = json.loads((tmp_path / "p2" / "C0.json").read_text())
    assert stored["input_identity"] == "c0-a"
    # C0 resumes from its record; R1 declares no input identity, so it reruns.
    second = module.run_stages(phase=2)
    assert second["C0"]["status"] == "passed"
    assert calls == ["C0", "R1", "R1"]
    identity["C0"] = "c0-b"
    module.run_stages(phase=2)
    assert calls == ["C0", "R1", "R1", "C0", "R1"]
    assert json.loads((tmp_path / "p2" / "C0.json").read_text())["input_identity"] == "c0-b"
