"""Shared connectome npy cache. The parquet reader runs in a child process.

pandas.read_parquet on Connectivity_783.parquet maps about 1.9 GB of
IOAccelerator (Metal) memory that stays in the process after the frame
is deleted. Workers and the engine process only memory-map the npy files.
"""
from __future__ import annotations

import fcntl
import gc
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from flyonenomics.io import load_npy, read_parquet


def cache_dir() -> Path:
    """Return the shared download cache directory.

    Units: none. Shapes: a single path. Honours FLYONENOMICS_CACHE_DIR
    and falls back to .cache under the repository root.
    """
    override = os.environ.get("FLYONENOMICS_CACHE_DIR", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / ".cache"


def connectome_array_dir(completeness: Path, connectivity: Path) -> Path:
    """Return the memmap directory for one connectome pair. Units: none. Shapes: one path."""
    stamp = (
        f"{completeness.resolve()}|{completeness.stat().st_mtime_ns}|{completeness.stat().st_size}|"
        f"{connectivity.resolve()}|{connectivity.stat().st_mtime_ns}|{connectivity.stat().st_size}"
    )
    digest = hashlib.sha256(stamp.encode()).hexdigest()[:16]
    return cache_dir() / "connectome-arrays" / digest


def _atomic_save_npy(path: Path, array: np.ndarray) -> None:
    """Write one array through a temporary file. Units: none. Shapes: array shape."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as handle:
        np.save(handle, array)
    tmp.replace(path)


def _memmap_arrays(directory: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return cached root ids and synapse arrays as memmaps."""
    return (
        load_npy(directory / "root_ids.npy", mmap_mode="r"),
        load_npy(directory / "i.npy", mmap_mode="r"),
        load_npy(directory / "j.npy", mmap_mode="r"),
        load_npy(directory / "w_exc.npy", mmap_mode="r"),
    )


def write_connectome_cache(completeness: Path, connectivity: Path) -> Path:
    """Read CSV/parquet once and write npy files. Units: none. Shapes: per array.

    Call this only from the short-lived child. The caller process must not
    import pandas for the v783 connectivity table.
    """
    import pandas as pd

    completeness = Path(completeness)
    connectivity = Path(connectivity)
    directory = connectome_array_dir(completeness, connectivity)
    directory.mkdir(parents=True, exist_ok=True)
    ready = directory / "ready"
    lock_path = directory / "lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if ready.is_file():
            return directory
        df_comp = pd.read_csv(completeness, index_col=0)
        root_ids = df_comp.index.to_numpy(dtype=np.int64)
        del df_comp
        df_con = read_parquet(connectivity).to_pandas()
        i_pre = df_con.loc[:, "Presynaptic_Index"].to_numpy(dtype=np.int32)
        j_post = df_con.loc[:, "Postsynaptic_Index"].to_numpy(dtype=np.int32)
        w_exc = df_con.loc[:, "Excitatory x Connectivity"].to_numpy(dtype=np.float64)
        del df_con
        gc.collect()
        _atomic_save_npy(directory / "root_ids.npy", np.ascontiguousarray(root_ids, dtype=np.int64))
        _atomic_save_npy(directory / "i.npy", np.ascontiguousarray(i_pre, dtype=np.int32))
        _atomic_save_npy(directory / "j.npy", np.ascontiguousarray(j_post, dtype=np.int32))
        _atomic_save_npy(directory / "w_exc.npy", np.ascontiguousarray(w_exc, dtype=np.float64))
        ready.write_text("ok\n")
        del root_ids, i_pre, j_post, w_exc
        gc.collect()
        return directory


def _spawn_writer(completeness: Path, connectivity: Path) -> None:
    """Run write_connectome_cache in a child that exits and drops Metal maps."""
    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "-m", "flyonenomics.connectome_arrays",
         str(Path(completeness)), str(Path(connectivity))],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"connectome cache child failed ({result.returncode}): {detail}"
        )


def load_connectome_arrays(
    completeness: Path, connectivity: Path
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load root ids and synapse i, j, raw weights as memmaps when cached.

    Units: indices dimensionless, weights the parquet 'Excitatory x Connectivity'
    column (dimensionless). Shapes: root_ids (n,) int64; i, j, w_exc (n_syn,).
    A cache miss spawns a child; this process never reads the parquet.
    """
    completeness = Path(completeness)
    connectivity = Path(connectivity)
    directory = connectome_array_dir(completeness, connectivity)
    ready = directory / "ready"
    if not ready.is_file():
        _spawn_writer(completeness, connectivity)
    if not ready.is_file():
        raise RuntimeError(f"connectome cache was not written: {directory}")
    return _memmap_arrays(directory)


def base_weight_memmap(
    w_exc: np.ndarray, w_syn_mv: float, completeness: Path, connectivity: Path
) -> np.ndarray:
    """Return file-backed base weights in mV. Units: mV. Shapes: (n_syn,) float64.

    The file is shared across workers. Values equal parquet weight times w_syn.
    """
    directory = connectome_array_dir(completeness, connectivity)
    directory.mkdir(parents=True, exist_ok=True)
    key = f"{w_syn_mv:.17g}"
    path = directory / f"base_w_mv_{key}.npy"
    ready = directory / f"base_w_mv_{key}.ready"
    lock_path = directory / "lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if ready.is_file() and path.is_file():
            return load_npy(path, mmap_mode="r")
        base = np.multiply(np.asarray(w_exc, dtype=np.float64), float(w_syn_mv), dtype=np.float64)
        _atomic_save_npy(path, np.ascontiguousarray(base, dtype=np.float64))
        ready.write_text("ok\n")
        del base
        gc.collect()
        return load_npy(path, mmap_mode="r")


def connectome_source_paths(version: str) -> tuple[Path, Path]:
    """Return canonical engine-order and edge paths from the version adapter."""
    from flyonenomics.datasets import get_dataset_adapter

    files = get_dataset_adapter(version).connectome_files()
    return files.completeness, files.connectivity


def ensure_connectome_for_version(version: str, w_syn_mv: float | None = None) -> None:
    """Populate the npy cache in a child, then map it. Units: w_syn_mv in mV."""
    completeness, connectivity = connectome_source_paths(version)
    root_ids, i_pre, j_post, w_exc = load_connectome_arrays(completeness, connectivity)
    if w_syn_mv is not None:
        base_weight_memmap(w_exc, float(w_syn_mv), completeness, connectivity)
    del root_ids, i_pre, j_post, w_exc


def main(argv: list[str] | None = None) -> int:
    """Child entry: write npy cache for one completeness/connectivity pair."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit("usage: python -m flyonenomics.connectome_arrays COMPLETENESS CONNECTIVITY")
    write_connectome_cache(Path(args[0]), Path(args[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
