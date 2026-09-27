"""Machine-wide engine-worker budget (SPEC section 11 item 69(d)).

The budget lives outside Params. It sizes a shared slot count from the
measured per-worker footprint, free plus reclaimable memory, swap used,
and the performance-plus-super core count minus two. Every engine
command on the Mac acquires slots from one lock file under the cache
directory. An explicit integer still wins. Only ``auto`` asks the
budget; an omitted count keeps ``orchestrator.n_workers`` from Params
(item 76).
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flyonenomics.io import read_json, read_text

# WP9 / WP11 one-worker probe: phys_footprint 3050 MB before the memory cuts.
# A later probe may overwrite cache/engine-budget/footprint_bytes.
DEFAULT_FOOTPRINT_BYTES = 3050 * 1024 * 1024
RESERVE_BYTES = 8 * 1024 ** 3
SWAP_HARD_MIB = 4000.0
CORE_RESERVE = 2
LOCK_POLL_S = 0.05


def _cache_dir() -> Path:
    """Return the shared cache directory without importing Brian2.

    Units: none. Shapes: one path. Honours FLYONENOMICS_CACHE_DIR.
    """
    override = os.environ.get("FLYONENOMICS_CACHE_DIR", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / ".cache"


def budget_dir() -> Path:
    """Return the cache directory that holds the slot file. Units: none. Shapes: one path."""
    path = _cache_dir() / "engine-budget"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _lock_path() -> Path:
    """Return the lock file path. Units: none. Shapes: one path."""
    return budget_dir() / "slots.lock"


def _state_path() -> Path:
    """Return the JSON slot table path. Units: none. Shapes: one path."""
    return budget_dir() / "slots.json"


def _footprint_path() -> Path:
    """Return the measured-footprint file path. Units: none. Shapes: one path."""
    return budget_dir() / "footprint_bytes"


def record_footprint_bytes(nbytes: int) -> None:
    """Write the measured per-worker footprint. Units: bytes. Shapes: scalar."""
    if nbytes <= 0:
        raise ValueError("footprint must be positive")
    path = _footprint_path()
    path.write_text(str(int(nbytes)) + "\n")


def per_worker_footprint_bytes() -> int:
    """Return the measured or default per-worker footprint. Units: bytes. Shapes: scalar."""
    path = _footprint_path()
    if path.is_file():
        text = read_text(path).strip()
        if text.isdigit() and int(text) > 0:
            return int(text)
    return DEFAULT_FOOTPRINT_BYTES


def physical_cpus() -> int:
    """Return performance-plus-super physical cores. Units: cores. Shapes: scalar.

    Linux (the authorized aarch64 Oracle box) reports `os.cpu_count`.
    """
    if platform.system() != "Darwin":
        count = os.cpu_count()
        if not count or count < 1:
            raise RuntimeError("os.cpu_count is not a positive integer")
        return int(count)
    raw = subprocess.check_output(["sysctl", "-n", "hw.physicalcpu"], text=True).strip()
    count = int(raw)
    if count < 1:
        raise RuntimeError("hw.physicalcpu is not a positive integer")
    return count


def _proc_meminfo() -> dict[str, float]:
    """Parse /proc/meminfo into KiB per key; Linux only. Units: KiB. Shapes: mapping."""
    values: dict[str, float] = {}
    for line in read_text("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        token = rest.strip().split()
        if token and token[0].replace(".", "", 1).isdigit():
            values[key] = float(token[0])
    return values


def core_cap() -> int:
    """Return the core ceiling: physical cores minus two, at least one.

    Units: workers. Shapes: scalar.
    """
    return max(1, physical_cpus() - CORE_RESERVE)


def swap_used_mib() -> float:
    """Return used swap in MiB. Units: MiB. Shapes: scalar."""
    if platform.system() != "Darwin":
        info = _proc_meminfo()
        return max(0.0, (info.get("SwapTotal", 0.0) - info.get("SwapFree", 0.0)) / 1024.0)
    output = subprocess.check_output(["sysctl", "vm.swapusage"], text=True)
    match = re.search(r"used\s*=\s*([0-9.]+)([MG])", output)
    if match is None:
        raise RuntimeError("vm.swapusage used value missing")
    return float(match.group(1)) * (1024 if match.group(2) == "G" else 1)


def _vm_stat_pages() -> dict[str, int]:
    """Parse macOS vm_stat page counts. Units: pages. Shapes: name to count."""
    output = subprocess.check_output(["vm_stat"], text=True)
    page_size = 16384
    header = re.search(r"page size of (\d+) bytes", output)
    if header:
        page_size = int(header.group(1))
    counts: dict[str, int] = {"page_size": page_size}
    for line in output.splitlines()[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        digits = re.sub(r"[^0-9]", "", value)
        if digits:
            counts[name.strip()] = int(digits)
    return counts


def memory_bytes() -> int:
    """Return installed physical memory. Units: bytes. Shapes: scalar."""
    if platform.system() != "Darwin":
        return int(_proc_meminfo().get("MemTotal", 0.0) * 1024)
    raw = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise RuntimeError("hw.memsize is not a positive integer")
    return int(raw)


def memorystatus_level() -> int | None:
    """Return the kernel's available-memory percentage, or None off macOS. Units: percent."""
    try:
        raw = subprocess.check_output(["sysctl", "-n", "kern.memorystatus_level"], text=True,
                                      stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return int(raw) if raw.isdigit() and 0 <= int(raw) <= 100 else None


def available_bytes() -> int:
    """Return memory the kernel counts as available. Units: bytes. Shapes: scalar.

    macOS: hw.memsize times kern.memorystatus_level percent, the figure
    `memory_pressure` prints as free percentage. It counts file cache and
    compressible pages that vm_stat's free, speculative, inactive and
    purgeable pages leave out (review r12: 8.7 GiB by vm_stat against
    17.3 GiB by memorystatus on the idle 24 GiB Mac at 72 percent). Elsewhere the vm_stat
    sum is the fallback.
    """
    if platform.system() != "Darwin":
        return int(_proc_meminfo().get("MemAvailable", 0.0) * 1024)
    level = memorystatus_level()
    if level is not None:
        return memory_bytes() * level // 100
    counts = _vm_stat_pages()
    page = counts["page_size"]
    free = counts.get("Pages free", 0) + counts.get("Pages speculative", 0)
    reclaimable = counts.get("Pages purgeable", 0) + counts.get("Pages inactive", 0)
    return (free + reclaimable) * page


def memory_cap(footprint: int | None = None) -> int:
    """Return workers that fit in available memory after the 8 GiB reserve.

    Units: workers. Shapes: scalar. Swap used above 4000 MiB yields 0.
    """
    if swap_used_mib() > SWAP_HARD_MIB:
        return 0
    size = footprint if footprint is not None else per_worker_footprint_bytes()
    usable = available_bytes() - RESERVE_BYTES
    if usable <= 0 or size <= 0:
        return 0
    return int(usable // size)


def _pid_alive(pid: int) -> bool:
    """Return whether pid still exists. Units: none. Shapes: scalar."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _holder_pid(key: str) -> int | None:
    """Return the pid of a holder key "pid" or "pid:token". Units: none. Shapes: scalar."""
    head = key.split(":", 1)[0]
    return int(head) if head.isdigit() else None


def _with_lock(fn: Any) -> Any:
    """Run fn(state) under an exclusive file lock and write the returned state."""
    import fcntl

    lock_path = _lock_path()
    state_path = _state_path()
    with open(lock_path, "a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if state_path.is_file():
            try:
                state = read_json(state_path)
            except (OSError, ValueError):
                state = {"holders": {}}
        else:
            state = {"holders": {}}
        holders = {str(key): int(n) for key, n in state.get("holders", {}).items()
                   if _holder_pid(str(key)) is not None and _pid_alive(_holder_pid(str(key)))
                   and int(n) > 0}
        state = fn({"holders": holders})
        tmp = state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2) + "\n")
        tmp.replace(state_path)
        return state


def held_slots() -> int:
    """Return slots held by live processes. Units: workers. Shapes: scalar."""
    def read(state: dict[str, Any]) -> dict[str, Any]:
        return state

    return sum(_with_lock(read)["holders"].values())


def _auto_count(held: int, cores: int, memory: int) -> int:
    """Combine the ceilings for auto. Units: workers. Shapes: scalars.

    Held slots take cores. They are not subtracted from the memory term:
    running workers' pages are already missing from available memory.
    """
    return max(0, min(cores - held, memory))


def recommend_workers() -> int:
    """Return the auto worker count from cores, memory, swap and live holders.

    Units: workers. Shapes: scalar. Zero means the machine has no spare slot.
    """
    return _auto_count(held_slots(), core_cap(), memory_cap())


def params_n_workers() -> int:
    """Return orchestrator.n_workers from Params. Units: workers. Shapes: scalar.

    Item 76: this is the omitted-count default. It is not the auto budget.
    """
    from flyonenomics.types import load_params

    count = int(load_params().get("orchestrator.n_workers"))
    if count < 1:
        raise ValueError("orchestrator.n_workers must be a positive integer")
    return count


def resolve_worker_count(requested: int | str | None, n_jobs: int) -> int:
    """Resolve auto against the budget; None keeps Params; an integer still wins.

    Units: workers. Shapes: scalars. Never above n_jobs. Explicit values are
    still capped by the core ceiling so one command cannot oversubscribe
    the machine; they are not reduced for memory. Item 76: only ``auto``
    asks the budget.
    """
    if n_jobs < 1:
        raise ValueError("n_jobs must be a positive integer")
    if requested is None:
        requested = params_n_workers()
    if requested == "auto":
        recommended = recommend_workers()
        if recommended < 1:
            raise RuntimeError("engine budget is 0: swap used or free memory too low")
        return min(recommended, n_jobs)
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError("n_workers must be a positive integer or 'auto'")
    return min(requested, n_jobs, core_cap())


@dataclass
class SlotLease:
    """Held engine-worker slots for one command. Units: workers. Shapes: scalar count."""

    pid: int
    count: int
    released: bool = False
    key: str = ""

    def release(self) -> None:
        """Drop this process's slots. Units: none. Shapes: none."""
        if self.released:
            return

        def drop(state: dict[str, Any]) -> dict[str, Any]:
            state["holders"].pop(self.key or str(self.pid), None)
            return state

        _with_lock(drop)
        self.released = True

    def __enter__(self) -> SlotLease:
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def acquire_engine_slots(count: int, *, block: bool = True, timeout_s: float = 30.0) -> SlotLease:
    """Register count slots for this process. Units: workers and seconds. Shapes: scalar.

    Explicit callers pass the already-resolved count. The table records the
    pid so other auto commands see the load. block waits for a consistent
    write; it does not wait for other holders to finish.
    """
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("slot count must be a positive integer")
    return _register(lambda held: count, block=block, timeout_s=timeout_s)


def _register(size: Any, *, block: bool, timeout_s: float) -> SlotLease:
    """Size and record one lease inside a single lock hold. Units: workers, seconds.

    size(held) returns the slot count given slots already held. Keys are
    "pid:token", so two leases in one process do not overwrite each other.
    """
    import uuid

    pid = os.getpid()
    key = f"{pid}:{uuid.uuid4().hex[:12]}"
    deadline = time.monotonic() + timeout_s
    granted: list[int] = []

    def add(state: dict[str, Any]) -> dict[str, Any]:
        count = int(size(sum(state["holders"].values())))
        if count >= 1:
            state["holders"][key] = count
        granted.append(count)
        return state

    while True:
        try:
            _with_lock(add)
            return SlotLease(pid=pid, count=granted[-1], key=key)
        except OSError:
            if not block or time.monotonic() >= deadline:
                raise
            time.sleep(LOCK_POLL_S)


def lease_workers(requested: int | str | None, n_jobs: int, *, timeout_s: float = 30.0) -> SlotLease:
    """Resolve the worker count and register it under one lock hold. Units: workers.

    Shapes: scalars. Same rules as resolve_worker_count; two auto commands
    started together cannot both size against the same free slots. Item 76:
    None uses Params; only auto asks the budget.
    """
    if n_jobs < 1:
        raise ValueError("n_jobs must be a positive integer")
    cores = core_cap()
    if requested is None:
        requested = params_n_workers()
    if requested == "auto":
        memory = memory_cap()

        def size(held: int) -> int:
            return min(_auto_count(held, cores, memory), n_jobs)
    elif isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise ValueError("n_workers must be a positive integer or 'auto'")
    else:
        def size(held: int) -> int:
            return min(requested, n_jobs, cores)
    lease = _register(size, block=True, timeout_s=timeout_s)
    if lease.count < 1:
        raise RuntimeError("engine budget is 0: swap used or free memory too low")
    return lease
