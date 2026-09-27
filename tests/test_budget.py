"""Engine-worker budget: cores, memory, swap, shared slot file."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from flyonenomics.orchestrator import budget


@pytest.fixture
def budget_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FLYONENOMICS_CACHE_DIR", str(tmp_path))
    return tmp_path


def test_explicit_integer_wins_over_auto(budget_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "recommend_workers", lambda: 1)
    monkeypatch.setattr(budget, "core_cap", lambda: 16)
    assert budget.resolve_worker_count(4, n_jobs=10) == 4
    assert budget.resolve_worker_count("auto", n_jobs=10) == 1
    assert budget.resolve_worker_count(None, n_jobs=3) == 3
    assert budget.resolve_worker_count(None, n_jobs=10) == 4
    assert budget.resolve_worker_count(8, n_jobs=2) == 2


def test_omitted_workers_use_params_not_the_budget(budget_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Item 76: None is Params orchestrator.n_workers; only auto asks the budget."""
    monkeypatch.setattr(budget, "recommend_workers", lambda: 12)
    monkeypatch.setattr(budget, "core_cap", lambda: 16)
    monkeypatch.setattr(budget, "memory_cap", lambda: 20)
    monkeypatch.setattr(budget, "params_n_workers", lambda: 4)
    assert budget.resolve_worker_count(None, n_jobs=20) == 4
    assert budget.resolve_worker_count("auto", n_jobs=20) == 12
    first = budget.lease_workers("auto", n_jobs=8)
    omitted = budget.lease_workers(None, n_jobs=12)
    assert (first.count, omitted.count) == (8, 4)
    for lease in (first, omitted):
        lease.release()


def test_auto_raises_when_budget_is_zero(budget_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "recommend_workers", lambda: 0)
    with pytest.raises(RuntimeError, match="engine budget is 0"):
        budget.resolve_worker_count("auto", n_jobs=4)


def test_slot_lease_is_visible_then_released(budget_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "physical_cpus", lambda: 18)
    monkeypatch.setattr(budget, "available_bytes", lambda: 24 * 1024 ** 3)
    monkeypatch.setattr(budget, "swap_used_mib", lambda: 100.0)
    budget.record_footprint_bytes(1024 ** 3)
    with budget.acquire_engine_slots(2) as lease:
        assert lease.count == 2
        assert budget.held_slots() == 2
        state = json.loads((budget_home / "engine-budget" / "slots.json").read_text())
        assert state["holders"][lease.key] == 2
        assert lease.key.split(":")[0] == str(os.getpid())
    assert budget.held_slots() == 0


def test_dead_holder_is_pruned(budget_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "_pid_alive", lambda pid: pid == os.getpid())
    path = budget._state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"holders": {"1": 6, str(os.getpid()): 1}}) + "\n")
    assert budget.held_slots() == 1


def test_swap_hard_gate_zeroes_memory_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "swap_used_mib", lambda: 4000.1)
    assert budget.memory_cap(1024 ** 3) == 0


def test_core_cap_is_physical_minus_two(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "physical_cpus", lambda: 18)
    assert budget.core_cap() == 16


def test_available_memory_is_the_kernel_memorystatus_figure(monkeypatch: pytest.MonkeyPatch) -> None:
    """24 GiB at 69 percent available is 16.56 GiB, not the vm_stat page sum."""
    monkeypatch.setattr(budget.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(budget, "memorystatus_level", lambda: 69)
    monkeypatch.setattr(budget, "memory_bytes", lambda: 24 * 1024 ** 3)
    monkeypatch.setattr(budget, "_vm_stat_pages", lambda: pytest.fail("vm_stat is only the fallback"))
    assert budget.available_bytes() == 24 * 1024 ** 3 * 69 // 100
    monkeypatch.setattr(budget, "swap_used_mib", lambda: 100.0)
    assert budget.memory_cap(789 * 1024 ** 2) == int((24 * 1024 ** 3 * 69 // 100 - 8 * 1024 ** 3) // (789 * 1024 ** 2))


def test_memorystatus_level_reads_the_real_sysctl() -> None:
    """On this Mac the sysctl exists and is a percentage."""
    level = budget.memorystatus_level()
    assert level is None or 0 <= level <= 100


def test_held_slots_take_cores_not_memory(budget_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running workers are already missing from available memory; only cores are subtracted."""
    assert budget._auto_count(held=4, cores=16, memory=11) == 11
    assert budget._auto_count(held=12, cores=16, memory=11) == 4
    assert budget._auto_count(held=16, cores=16, memory=11) == 0
    assert budget._auto_count(held=0, cores=16, memory=0) == 0


def test_two_leases_in_one_process_do_not_overwrite(budget_home: Path) -> None:
    first = budget.acquire_engine_slots(2)
    second = budget.acquire_engine_slots(3)
    assert budget.held_slots() == 5
    first.release()
    assert budget.held_slots() == 3
    second.release()
    assert budget.held_slots() == 0


def test_lease_workers_sizes_auto_inside_the_lock(budget_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Back-to-back auto leases see each other's slots; explicit still wins but is core-capped."""
    monkeypatch.setattr(budget, "core_cap", lambda: 16)
    monkeypatch.setattr(budget, "memory_cap", lambda: 20)
    first = budget.lease_workers("auto", n_jobs=12)
    second = budget.lease_workers("auto", n_jobs=12)
    assert (first.count, second.count) == (12, 4)
    with pytest.raises(RuntimeError, match="engine budget is 0"):
        budget.lease_workers("auto", n_jobs=12)
    explicit = budget.lease_workers(40, n_jobs=24)
    assert explicit.count == 16
    for lease in (first, second, explicit):
        lease.release()
    assert budget.held_slots() == 0
    with pytest.raises(ValueError):
        budget.lease_workers(0, n_jobs=4)


def test_legacy_pid_keys_and_dead_token_keys_are_pruned(budget_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "_pid_alive", lambda pid: pid == os.getpid())
    path = budget._state_path()
    path.write_text(json.dumps({"holders": {"1": 6, "1:abc": 2, f"{os.getpid()}:def": 1, "junk": 3}}) + "\n")
    assert budget.held_slots() == 1
