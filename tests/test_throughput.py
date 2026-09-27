"""Throughput helpers: registry share, connectome memmap, parallel status."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from flyonenomics.orchestrator.workers import (
    RegistrySnapshot, load_registry_share, registry_share_key, save_registry_share,
)
from flyonenomics.registry import Compartment
from flyonenomics.registry.populations import Population
from flyonenomics.registry.receptors import ReceptorMap


def _share_snapshot() -> RegistrySnapshot:
    """Small registry snapshot. Units: none. Shapes: roots (4,), CSR (4, 2) and (2, 4)."""
    import scipy.sparse as sparse

    selected = {
        "MN9": Population(
            name="MN9",
            root_ids=np.array([10, 11], dtype=np.int64),
            idx=np.array([0, 1], dtype=np.int32),
            side=np.array(["left", "right"], dtype="U"),
            selector="explicit",
            count=2,
            inventory_range=(2, 2),
        )
    }
    exposure = sparse.csr_matrix(np.array([[1, 0], [0, 1], [0, 0], [0.5, 0.5]], dtype=np.float32))
    innervation = sparse.csr_matrix(np.array([[1, 0, 0, 0], [0, 1, 0, 1]], dtype=np.float32))
    receptors = ReceptorMap(
        r1=np.zeros(4, dtype=np.float32),
        r2=np.ones(4, dtype=np.float32),
        rq=np.zeros(4, dtype=np.float32),
        version="v0.1",
    )
    return RegistrySnapshot(
        np.arange(4, dtype=np.int64),
        selected,
        [Compartment(name="a", side="left", id=0), Compartment(name="b", side="right", id=1)],
        {"note": "share"},
        exposure,
        innervation,
        receptors,
    )


def test_registry_share_roundtrip(tmp_path: Path) -> None:
    """Spilled arrays reload with equal values. Units: none. Shapes: (4,), CSR (4, 2)."""
    snapshot = _share_snapshot()
    selected, exposure, innervation, receptors = (
        snapshot.selected, snapshot.exposure_matrix, snapshot.innervation_matrix, snapshot.receptor_map)
    directory = save_registry_share(snapshot, tmp_path / "share")
    loaded = load_registry_share(directory)
    np.testing.assert_array_equal(loaded.root_ids, snapshot.root_ids)
    np.testing.assert_array_equal(loaded.population("MN9").idx, selected["MN9"].idx)
    assert loaded.compartments()[0].name == "a"
    np.testing.assert_allclose(loaded.exposure().toarray(), exposure.toarray())
    np.testing.assert_allclose(loaded.innervation().toarray(), innervation.toarray())
    np.testing.assert_array_equal(loaded.receptors().r2, receptors.r2)


def test_registry_share_key_covers_every_written_input() -> None:
    """Same roots, changed population, compartment, receptor or annotation: new share key."""
    import dataclasses
    import scipy.sparse as sparse

    base = registry_share_key(_share_snapshot())
    assert registry_share_key(_share_snapshot()) == base

    changed = []
    snapshot = _share_snapshot()
    population = snapshot.selected["MN9"]
    snapshot.selected["MN9"] = dataclasses.replace(population, idx=np.array([0, 2], dtype=np.int32))
    changed.append(snapshot)
    snapshot = _share_snapshot()
    snapshot.selected["MN9"] = dataclasses.replace(snapshot.selected["MN9"], selector="class:MN9")
    changed.append(snapshot)
    snapshot = _share_snapshot()
    snapshot.compartment_list[1] = dataclasses.replace(snapshot.compartment_list[1], name="c")
    changed.append(snapshot)
    snapshot = _share_snapshot()
    snapshot.receptor_map = dataclasses.replace(snapshot.receptor_map, r1=np.full(4, 0.5, dtype=np.float32))
    changed.append(snapshot)
    snapshot = _share_snapshot()
    snapshot.receptor_map = dataclasses.replace(snapshot.receptor_map, version="v0.2")
    changed.append(snapshot)
    snapshot = _share_snapshot()
    snapshot.exposure_matrix = sparse.csr_matrix(np.array([[1, 0], [0, 1], [0, 0], [0.25, 0.75]], dtype=np.float32))
    changed.append(snapshot)
    snapshot = _share_snapshot()
    snapshot.innervation_matrix = None
    changed.append(snapshot)
    snapshot = _share_snapshot()
    snapshot.provenance_record = {"note": "other"}
    changed.append(snapshot)
    keys = [registry_share_key(item) for item in changed]
    assert base not in keys
    assert len(set(keys)) == len(keys)


def test_load_registry_share_does_not_import_pandas(tmp_path: Path) -> None:
    """Worker share load must not pull pandas or pyarrow. Units: none."""
    import subprocess
    import sys

    import scipy.sparse as sparse

    return RegistrySnapshot(
        np.arange(4, dtype=np.int64),
        {"MN9": Population(
            name="MN9",
            root_ids=np.array([10, 11], dtype=np.int64),
            idx=np.array([0, 1], dtype=np.int32),
            side=np.array(["left", "right"], dtype="U"),
            selector="explicit",
            count=2,
            inventory_range=(2, 2),
        )},
        [Compartment(name="a", side="left", id=0), Compartment(name="b", side="right", id=1)],
        {"note": "share"},
        sparse.csr_matrix(np.array([[1, 0], [0, 1], [0, 0], [0.5, 0.5]], dtype=np.float32)),
        sparse.csr_matrix(np.array([[1, 0, 0, 0], [0, 1, 0, 1]], dtype=np.float32)),
        ReceptorMap(
            r1=np.zeros(4, dtype=np.float32),
            r2=np.ones(4, dtype=np.float32),
            rq=np.zeros(4, dtype=np.float32),
            version="v0.1",
        ),
    )
    directory = save_registry_share(snapshot, tmp_path / "share")
    script = (
        "import sys\n"
        "from flyonenomics.orchestrator.workers import load_registry_share\n"
        f"load_registry_share({str(directory)!r})\n"
        "assert 'pandas' not in sys.modules\n"
        "assert 'pyarrow' not in sys.modules\n"
        "print('ok')\n"
    )
    subprocess.check_call([sys.executable, "-c", script], cwd=str(Path(__file__).resolve().parents[1]))


def test_timing_fields_are_the_only_status_diff(tmp_path: Path) -> None:
    """Document the fields stripped when comparing serial and parallel status."""
    left = {"date": "2026-09-14", "code_commit": "a", "results": [
        {"test_id": "0.9", "identity": {"date": "t1", "code_hash": "h"}, "outcome": "passed"}]}
    right = {"date": "2026-09-15", "code_commit": "a", "results": [
        {"test_id": "0.9", "identity": {"date": "t2", "code_hash": "h"}, "outcome": "passed"}]}
    assert _strip_timing(left) == _strip_timing(right)


def test_connectome_loaders_select_the_version_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both engine entry points use the dataset adapter rather than filename switches."""
    from flyonenomics import datasets
    from flyonenomics.connectome_arrays import connectome_source_paths
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.types import ConnectomeFiles

    expected = ConnectomeFiles(
        tmp_path / "order.csv", tmp_path / "edges.parquet", version="male-cns:v1.0"
    )

    class Selected:
        def connectome_files(self) -> ConnectomeFiles:
            return expected

    seen: list[str] = []
    monkeypatch.setattr(
        datasets,
        "get_dataset_adapter",
        lambda version: seen.append(version) or Selected(),
    )
    assert connectome_files("male-cns:v1.0") == expected
    assert connectome_source_paths("male-cns:v1.0") == (expected.completeness, expected.connectivity)
    assert seen == ["male-cns:v1.0", "male-cns:v1.0"]


def test_connectome_cache_miss_does_not_read_parquet_in_caller(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Child writes npy; caller never calls pandas.read_parquet. Units: none."""
    import pandas as pd

    from flyonenomics.connectome_arrays import load_connectome_arrays

    monkeypatch.setenv("FLYONENOMICS_CACHE_DIR", str(tmp_path / "cache"))
    completeness = tmp_path / "comp.csv"
    connectivity = tmp_path / "conn.parquet"
    completeness.write_text(",x\n100,1.0\n101,1.0\n")
    expected_i = np.array([0, 1], dtype=np.int32)
    expected_j = np.array([1, 0], dtype=np.int32)
    expected_w = np.array([1.25, 0.5], dtype=np.float64)
    pd.DataFrame({
        "Presynaptic_Index": expected_i,
        "Postsynaptic_Index": expected_j,
        "Excitatory x Connectivity": expected_w,
    }).to_parquet(connectivity, index=False)

    def boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("read_parquet in caller")

    monkeypatch.setattr(pd, "read_parquet", boom)
    root_ids, i_pre, j_post, w_exc = load_connectome_arrays(completeness, connectivity)
    np.testing.assert_array_equal(root_ids, np.array([100, 101], dtype=np.int64))
    np.testing.assert_array_equal(i_pre, expected_i)
    np.testing.assert_array_equal(j_post, expected_j)
    np.testing.assert_array_equal(w_exc, expected_w)
    # Second call uses the npy cache; still no parquet in this process.
    root_ids2, i2, j2, w2 = load_connectome_arrays(completeness, connectivity)
    np.testing.assert_array_equal(i2, expected_i)
    np.testing.assert_array_equal(w2, expected_w)
    del root_ids2, i2, j2, w2


def test_connectome_child_module_does_not_import_brian2() -> None:
    """The cache child entry lives outside engine.brian_engine. Units: none."""
    import flyonenomics.connectome_arrays as module

    source = Path(module.__file__).read_text()
    assert "brian2" not in source
    assert "import pandas" not in source.split("def write_connectome_cache")[0]


def _strip_timing(status: dict) -> dict:
    payload = json.loads(json.dumps(status))
    payload.pop("date", None)
    for entry in payload.get("results", []):
        identity = entry.get("identity") or {}
        identity.pop("date", None)
        identity.pop("machine", None)
    return payload


def test_engine_store_is_swept_and_removed_at_exit(tmp_path: Path) -> None:
    """Dead-pid snapshot dirs go on the next store; a clean exit removes its own dir."""
    import subprocess
    import sys

    root = tmp_path / "engine-store"
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    (root / str(dead.pid)).mkdir(parents=True)
    (root / str(dead.pid) / "1_initial.pkl").write_bytes(b"stale")
    live = root / str(os.getppid())
    live.mkdir()
    (root / "notes").mkdir()
    script = (
        "from pathlib import Path\n"
        "from flyonenomics.engine.brian_engine import engine_store_dir\n"
        "d = engine_store_dir()\n"
        "assert engine_store_dir() == d\n"
        "(d / '1_initial.pkl').write_bytes(b'x')\n"
        "print(d)\n"
    )
    env = {**os.environ, "FLYONENOMICS_CACHE_DIR": str(tmp_path)}
    proc = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True)
    own = Path(proc.stdout.strip().splitlines()[-1])
    assert own.parent == root
    assert not own.exists()
    assert not (root / str(dead.pid)).exists()
    assert live.is_dir() and (root / "notes").is_dir()
