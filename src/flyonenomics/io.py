"""Logged reads of repository data and fixture files (SPEC-P2 section 5.1).

Every read of a file under data/ or tests/fixtures/ goes through this
module. Each call appends the repository-relative path to the process
dependency log. Reads of other paths still go through these helpers so
scanned modules do not call builtin open, Path.read_text, or parquet
loaders directly. Logging is in-memory unless a log directory is set.
Worker processes write deps-<pid>.json at each flush and at exit.

Units: none. Shapes: paths and small decoded mappings.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, TextIO

import yaml

_REPO = Path(__file__).resolve().parents[2]
_repo_root = _REPO
_logged: list[str] = []
_seen: set[str] = set()
_log_dir: Path | None = None
# Suspension is per thread: a read on another thread, or in another process,
# is still logged while one thread reads identity metadata.
_suspend = threading.local()


def set_repo_root(path: str | Path | None) -> None:
    """Set the repository root used to classify logged paths. Units: none."""
    global _repo_root
    _repo_root = _REPO if path is None else Path(path)


def repo_root() -> Path:
    """Return the repository root used for relative logged paths. Units: none."""
    return _repo_root


def logged_paths() -> list[str]:
    """Return the ordered unique logged paths of this process. Units: none."""
    return list(_logged)


def clear_log() -> None:
    """Drop the in-memory dependency log. Units: none. Shapes: empty log."""
    _logged.clear()
    _seen.clear()


@contextmanager
def unlogged() -> Iterator[None]:
    """Suspend dependency logging on this thread. Re-entrant and exception-safe. Units: none."""
    _suspend.depth = suspended_depth() + 1
    try:
        yield
    finally:
        _suspend.depth -= 1


def suspended_depth() -> int:
    """Return this thread's unlogged() nesting depth; 0 when logging. Units: none."""
    return getattr(_suspend, "depth", 0)


def set_log_dir(path: str | Path | None) -> None:
    """Set the directory that flush writes deps-<pid>.json into. Units: none."""
    global _log_dir
    _log_dir = None if path is None else Path(path)


def _active_log_dir() -> Path | None:
    """Return the log directory, honouring FLYONENOMICS_DEPS_DIR. Units: none."""
    global _log_dir
    if _log_dir is not None:
        return _log_dir
    env = os.environ.get("FLYONENOMICS_DEPS_DIR")
    if env:
        _log_dir = Path(env)
        return _log_dir
    return None


def log_dir() -> Path | None:
    """Return the current dependency-log directory, or None. Units: none."""
    return _log_dir


def _relative_to(root: Path, path: Path) -> Path | None:
    """Return path relative to root, or None when it is outside. Units: none."""
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return None


def _loggable(path: Path) -> str | None:
    """Return the repository-relative path when it is under data/ or tests/fixtures/.

    Units: none. Shapes: one posix string or None.
    """
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    candidates = [_repo_root]
    cwd = Path.cwd()
    if cwd.resolve() != _repo_root.resolve():
        candidates.append(cwd)
    for root in candidates:
        rel = _relative_to(root, resolved)
        if rel is None or not rel.parts:
            continue
        parts = rel.parts
        if parts[0] == "data" or (len(parts) >= 2 and parts[0] == "tests" and parts[1] == "fixtures"):
            return rel.as_posix()
    return None


def _record(path: str | Path) -> Path:
    """Append a loggable path once, in first-seen order. Units: none."""
    resolved = Path(path)
    if suspended_depth():
        return resolved
    rel = _loggable(resolved)
    if rel is not None and rel not in _seen:
        _seen.add(rel)
        _logged.append(rel)
    return resolved


def read_text(path: str | Path, encoding: str | None = None, errors: str = "strict") -> str:
    """Read one text file. Units: none. Shapes: the file's characters."""
    resolved = _record(path)
    if encoding is None:
        return resolved.read_text(errors=errors)
    return resolved.read_text(encoding=encoding, errors=errors)


def read_bytes(path: str | Path) -> bytes:
    """Read one binary file. Units: bytes. Shapes: the file's contents."""
    resolved = _record(path)
    return resolved.read_bytes()


def read_yaml(path: str | Path) -> Any:
    """Load one YAML document. Units: per file. Shapes: the decoded value."""
    return yaml.safe_load(read_text(path))


def read_json(path: str | Path) -> Any:
    """Load one JSON document. Units: per file. Shapes: the decoded value."""
    return json.loads(read_text(path))


def read_parquet(path: str | Path, columns: list[str] | None = None, **kwargs: Any) -> Any:
    """Read a parquet file through pyarrow. Units: per columns. Shapes: one table."""
    import pyarrow.parquet as parquet

    resolved = _record(path)
    return parquet.read_table(resolved, columns=columns, **kwargs)


def parquet_file(path: str | Path) -> Any:
    """Open a pyarrow ParquetFile after logging the path. Units: none."""
    import pyarrow.parquet as parquet

    resolved = _record(path)
    return parquet.ParquetFile(resolved)


def read_feather(path: str | Path, columns: list[str] | None = None) -> Any:
    """Read a feather file through pyarrow. Units: per columns. Shapes: one table."""
    import pyarrow.feather as feather

    resolved = _record(path)
    return feather.read_table(resolved, columns=columns)


def load_npy(path: str | Path, **kwargs: Any) -> Any:
    """Load a NumPy array file. Units: per array. Shapes: stored shape."""
    import numpy as np

    resolved = _record(path)
    return np.load(resolved, **kwargs)


def hash_file(path: str | Path) -> str:
    """Return the SHA-256 hex of one file's bytes. Units: none. Shapes: one hex."""
    resolved = _record(path)
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_bytes(path: str | Path, size: int = 1 << 20) -> Iterator[bytes]:
    """Yield successive chunks of one file. Units: bytes. Shapes: chunks."""
    resolved = _record(path)
    with resolved.open("rb") as handle:
        while True:
            chunk = handle.read(size)
            if not chunk:
                return
            yield chunk


@contextmanager
def exclusive_file_lock(path: str | Path) -> Iterator[TextIO]:
    """Hold an exclusive advisory lock on a small coordination file."""
    import fcntl

    resolved = Path(path)
    with resolved.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield handle


def flush(directory: str | Path | None = None) -> Path | None:
    """Write deps-<pid>.json into the log directory. Units: none. Shapes: one file.

    Returns the written path, or None when no directory is set.
    """
    dest_dir = Path(directory) if directory is not None else _active_log_dir()
    if dest_dir is None:
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"deps-{os.getpid()}.json"
    payload = {"pid": os.getpid(), "paths": logged_paths()}
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def merge_logs(directory: str | Path) -> list[str]:
    """Union deps-*.json files in directory, first-seen order. Units: none."""
    paths: list[str] = []
    seen: set[str] = set()
    for file in sorted(Path(directory).glob("deps-*.json")):
        payload = json.loads(file.read_text())
        for item in payload.get("paths", []):
            if not isinstance(item, str) or item in seen:
                continue
            seen.add(item)
            paths.append(item)
    return paths


def conservative_inputs(root: str | Path | None = None) -> list[str]:
    """Return every data/ and tests/fixtures/ relative path under root. Units: none."""
    base = _repo_root if root is None else Path(root)
    found: list[str] = []
    for folder in (base / "data", base / "tests" / "fixtures"):
        if not folder.is_dir():
            continue
        for child in sorted(folder.rglob("*")):
            if child.is_file():
                found.append(child.relative_to(base).as_posix())
    return found


def _flush_at_exit() -> None:
    """Write the log at process exit when a log directory is set. Units: none."""
    if _active_log_dir() is not None:
        flush()


atexit.register(_flush_at_exit)
