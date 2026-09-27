"""Provenance checks: every SPEC section 4 row is recorded and verified."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_provenance() -> dict:
    """Load data/provenance.json.

    Units: none. Shapes: mapping.
    """
    return json.loads((ROOT / "data" / "provenance.json").read_text())


def test_provenance_file_exists() -> None:
    """data/provenance.json exists with records.

    Units: none. Shapes: scalars.
    """
    prov = load_provenance()
    assert prov["records"], "no provenance records"


def test_shiu_hashes_match_proof_run() -> None:
    """The five Shiu files match the proof run sizes and SHA-256.

    Units: bytes. Shapes: scalars.
    """
    expected = {
        "2023_03_23_completeness_630_final.csv": (
            3057611, "e6b71e17671a9bdb05f55e4bc6774640a1418cb7a05125e0fc994ad40f9bfdfb"),
        "2023_03_23_connectivity_630_final.parquet": (
            86630944, "94db8c650533bc36ffa3223f2e62325d5648b8d6bd31c3a4e1c804628c7557b3"),
        "Completeness_783.csv": (
            3327347, "bbb847a4cc2caaa7a16349722d220c087317b946d148d4d592d94d250617a311"),
        "Connectivity_783.parquet": (
            100804642, "efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347"),
        "sez_neurons.pickle": (
            5114, "2bc5a2a8289924f2de39a8e68bdc07025cb6d6c6c6ddc83a973c0cace7cec2ce"),
    }
    by_item = {r["item"]: r for r in load_provenance()["records"]}
    for name, (size, digest) in expected.items():
        rec = by_item[f"Shiu clone {name}"]
        assert rec["bytes"] == size, name
        assert rec["sha256"] == digest, name
        assert rec["status"] == "fetched", name


def test_annotations_recorded() -> None:
    """Both annotation releases carry commit hashes.

    Units: bytes. Shapes: scalars.
    """
    by_item = {r["item"]: r for r in load_provenance()["records"]}
    v211 = by_item["annotations-v2.1.0.tsv"]
    assert v211["commit"] == "ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0"
    assert v211["bytes"] == 27015208
    v110 = by_item["annotations-v1.1.0.tsv"]
    assert v110["commit"] == "df6bb136f5b3d91c3992df4e8de2642329e2a384"
    assert v110["sha256"] == "55c99c61eecf8db6cc36f1a684b35e4c4208afbab02197d753ccc8dc2a6e2e76"


def test_figshare_inventory() -> None:
    """The figshare zip carries its MD5 and the 135/134 inventory.

    Units: bytes. Shapes: scalars.
    """
    by_item = {r["item"]: r for r in load_provenance()["records"]}
    rec = by_item["github-importJnx5V7.zip"]
    assert rec["md5"] == "c9e8e9c72fc04a694fb24e4f84b9699d"
    assert rec["bytes"] == 6728585
    assert "135" in rec["note"] and "134" in rec["note"]


def test_cetran_shiu_codex_recorded() -> None:
    """CeTrAn commit, Shiu archive fetch, and Codex absence are recorded.

    Units: none. Shapes: scalars.
    """
    by_item = {r["item"]: r for r in load_provenance()["records"]}
    assert len([r for r in by_item.values() if r["item"].startswith("CeTrAn ") and r["commit"] == "1f98ddd83366db53d4aabfa6f42b1153f8e1553d"]) == 4
    assert by_item["Shiu 2024 simulation archive, sugar-activation results"]["status"] == "fetched"
    codex = by_item["FlyWire Codex per-neuron synapse counts"]
    assert codex["status"] == "not fetched"
    assert "Google sign-in" in codex["note"]
    assert by_item["Zenodo per-neuron post-synapse counts, FlyWire v783"]["status"] == "fetched"


def test_shiu_archive_record_carries_size_inventory_and_license() -> None:
    """The archive record holds its bytes, member inventory, and license.

    Units: bytes. Shapes: scalars.
    """
    by_item = {r["item"]: r for r in load_provenance()["records"]}
    rec = by_item["Shiu 2024 simulation archive, sugar-activation results"]
    assert rec["bytes"] == 4499610373
    assert rec["path"] == ".cache/shiu-archive/results.zip"
    assert rec["license"] == "MIT"
    assert rec["inventory"]["files"] >= 1
    assert rec["sha256"] and rec["md5"] == "f6f2e314821fa6a4196214e3b2b14bc4"


def test_codex_record_carries_rows_and_columns() -> None:
    """The Zenodo record holds its bytes, row count, and column names.

    Units: bytes and rows. Shapes: scalars.
    """
    by_item = {r["item"]: r for r in load_provenance()["records"]}
    rec = by_item["Zenodo per-neuron post-synapse counts, FlyWire v783"]
    assert rec["bytes"] == 233843050
    assert rec["path"] == ".cache/zenodo-10676866/per_neuron_neuropil_count_post_783.feather"
    assert rec["inventory"]["rows"] >= 1
    assert rec["inventory"]["columns"] == 3
    assert "post_pt_root_id" in rec["note"]


def test_reference_artefacts_exist() -> None:
    """Reference copies of the proof run outputs exist.

    Units: none. Shapes: scalars.
    """
    assert (ROOT / "data" / "reference" / "l5-baseline-spikes.parquet").exists()
    assert (ROOT / "data" / "reference" / "l5-baseline-results.json").exists()


import hashlib
import importlib.util
import io
import subprocess
import zipfile
import pytest
from pydantic import ValidationError
from flyonenomics.types import ProvenanceRecord


def fetch_module():
    spec = importlib.util.spec_from_file_location("fetch_data_test", ROOT / "scripts/fetch_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_records_have_individual_checksums_and_canonical_paths() -> None:
    records = [ProvenanceRecord.model_validate(r) for r in load_provenance()["records"]]
    fetched = [r for r in records if r.status == "fetched"]
    assert len({r.path for r in fetched}) == len(fetched)
    assert next(r for r in records if r.item == "annotations-v1.1.0.tsv").path == ".cache/annotations-v1.1.0.tsv"
    assert {r.item for r in fetched} >= {"annotations-v2.1.0-columns.md", "Shiu clone model.py", "Shiu clone utils.py", "Shiu clone example.ipynb"}
    assert len([r for r in fetched if r.item.startswith("CeTrAn ")]) == 4


def test_absence_is_a_valid_distinct_status() -> None:
    record = dict(item="optional", version="v783", source="source", license="unknown", used_for="completeness", status="not fetched", bytes=9000000000, url="https://example.test", note="exceeds cap")
    assert ProvenanceRecord(**record).sha256 is None
    for update in ({"status": "typo"}, {"url": None}, {"note": None}, {"status": "fetched"}):
        with pytest.raises(ValidationError):
            ProvenanceRecord(**(record | update))


@pytest.mark.parametrize("field,value", [("bytes", 4), ("sha256", "wrong"), ("md5", "wrong")])
def test_wrong_checksum_fails_loudly(tmp_path: Path, field: str, value: object) -> None:
    fetch = fetch_module()
    path = tmp_path / "file"
    path.write_bytes(b"abc")
    with pytest.raises(ValueError, match="checksum mismatch"):
        fetch.verify_file(path, {field: value})
    assert path.read_bytes() == b"abc"


def test_inventory_counts_archive_members(tmp_path: Path) -> None:
    fetch = fetch_module()
    path = tmp_path / "trajectories.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for i in range(135):
            archive.writestr(f"nested/{i}.dat", "trajectory")
        for i in range(134):
            archive.writestr(f"nested/{i}.xml", "header")
        archive.writestr("fake.dat/", "")
    assert fetch.figshare_inventory(path) == {".dat": 135, ".xml": 134}
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("extra.xml", "header")
    with pytest.raises(ValueError, match="inventory mismatch"):
        fetch.figshare_inventory(path)


def test_download_cap_and_interruption_preserve_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fetch = fetch_module()
    path = tmp_path / "download"
    path.write_bytes(b"original")
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b"too large"))
    with pytest.raises(RuntimeError, match="cap breached"):
        fetch.download("https://example.test", path, 2)
    assert list(tmp_path.iterdir()) == [path]
    assert path.read_bytes() == b"original"
    class Interrupted(io.BytesIO):
        def read(self, size: int) -> bytes:
            raise OSError("interrupted")
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: Interrupted())
    with pytest.raises(OSError, match="interrupted"):
        fetch.download("https://example.test", path, 100)
    assert list(tmp_path.iterdir()) == [path]
    assert path.read_bytes() == b"original"


@pytest.fixture
def synthetic_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Tiny isolated assets exercise fetch end to end; no real cache writes."""
    fetch = fetch_module()
    root = tmp_path / "repo"
    root.mkdir()
    (root / "data").mkdir()
    cache = tmp_path / "cache"
    shiu = cache / "Drosophila_brain_model"
    shiu.mkdir(parents=True)
    monkeypatch.setattr(fetch, "ROOT", root)
    monkeypatch.setenv("FLYONENOMICS_CACHE_DIR", str(cache))
    monkeypatch.setattr(fetch, "SHIU_FILES", {"tiny.csv": {"bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}})
    (shiu / "tiny.csv").write_bytes(b"abc")
    for name in ("model.py", "utils.py", "example.ipynb", "figures.ipynb"):
        (shiu / name).write_text("pinned")
    for args in (["git", "init", "-q", str(shiu)], ["git", "-C", str(shiu), "add", "."], ["git", "-C", str(shiu), "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-qm", "fixture"]):
        subprocess.run(args, check=True)
    head = subprocess.check_output(["git", "-C", str(shiu), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setattr(fetch, "SHIU_COMMIT", head)
    (cache / "l5-proof").mkdir()
    for name in ("baseline-spikes.parquet", "baseline-results.json"):
        (cache / "l5-proof" / name).write_bytes(b"proof")
    for name in ("annotations-v2.1.0.tsv", "annotations-v1.1.0.tsv"):
        (cache / name).write_bytes(b"abc")
    monkeypatch.setattr(fetch, "ANNOT_V211_BYTES", 3)
    monkeypatch.setattr(fetch, "ANNOT_V110_BYTES", 3)
    monkeypatch.setattr(fetch, "ANNOT_V110_SHA256", hashlib.sha256(b"abc").hexdigest())
    (cache / "annotations-v2.1.0-columns.md").write_bytes(b"c" * 6674)
    cetran = cache / "CeTrAn" / fetch.CETRAN_COMMIT
    cetran.mkdir(parents=True)
    for relative in fetch.CETRAN_FILES:
        (cetran / Path(relative).name).write_bytes(b"source")
    path = cache / "github-importJnx5V7.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for suffix, count in (("dat", 135), ("xml", 134)):
            for index in range(count):
                archive.writestr(f"{index}.{suffix}", "data")
    monkeypatch.setattr(fetch, "FIGSHARE_BYTES", path.stat().st_size)
    monkeypatch.setattr(fetch, "FIGSHARE_MD5", fetch.md5_file(path))
    archive_path = cache / "shiu-archive" / fetch.SHIU_ARCHIVE_NAME
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w") as archive:
        for member in fetch.SHIU_SUGAR_MEMBERS:
            archive.writestr(member, f"spikes for {member}")
        archive.writestr("other.parquet", "other spikes")
    monkeypatch.setattr(fetch, "SHIU_ARCHIVE_BYTES", archive_path.stat().st_size)
    monkeypatch.setattr(fetch, "SHIU_ARCHIVE_MD5", fetch.md5_file(archive_path))
    codex_path = cache / f"zenodo-{fetch.ZENODO_RECORD}" / fetch.ZENODO_POST_NAME
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_bytes(b"codex")
    monkeypatch.setattr(fetch, "ZENODO_POST_BYTES", 5)
    monkeypatch.setattr(fetch, "ZENODO_POST_MD5", fetch.md5_file(codex_path))
    monkeypatch.setattr(fetch, "codex_table_shape", lambda path: (7, ["post_pt_root_id", "neuropil", "count"]))
    def no_network(*args, **kwargs):
        pytest.fail("existing cache must not download")
    monkeypatch.setattr(fetch, "download", no_network)
    fetch.fetch()
    return fetch, root, cache


def test_fetch_verification_is_offline_and_byte_stable(synthetic_cache) -> None:
    fetch, root, cache = synthetic_cache
    path = root / "data/provenance.json"
    before = path.read_bytes()
    fetch.fetch()
    assert path.read_bytes() == before


@pytest.mark.parametrize("relative", ["annotations-v2.1.0.tsv", "annotations-v1.1.0.tsv", "annotations-v2.1.0-columns.md", "github-importJnx5V7.zip", "Drosophila_brain_model/tiny.csv", "Drosophila_brain_model/model.py", "Drosophila_brain_model/figures.ipynb", "l5-proof/baseline-spikes.parquet", "shiu-archive/results.zip", "zenodo-10676866/per_neuron_neuropil_count_post_783.feather", "CeTrAn/{commit}/functions.r", "CeTrAn/{commit}/utils.r", "CeTrAn/{commit}/angledev.r", "CeTrAn/{commit}/CeTrAn_fromxml_4.rgg"])
def test_fetch_rejects_cached_corruption_without_rewriting_provenance(synthetic_cache, relative: str) -> None:
    fetch, root, cache = synthetic_cache
    path = cache / relative.format(commit=fetch.CETRAN_COMMIT)
    original = path.read_bytes()
    path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    before = (root / "data/provenance.json").read_bytes()
    with pytest.raises(ValueError, match="checksum mismatch"):
        fetch.fetch()
    assert (root / "data/provenance.json").read_bytes() == before


def test_reference_destination_corruption_is_not_silently_repaired(synthetic_cache) -> None:
    fetch, root, cache = synthetic_cache
    dest = root / "data/reference/l5-baseline-spikes.parquet"
    dest.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="checksum mismatch"):
        fetch.fetch()
    assert dest.read_bytes() == b"wrong"


def test_wrong_shiu_commit_rejected(synthetic_cache, monkeypatch: pytest.MonkeyPatch) -> None:
    fetch, root, cache = synthetic_cache
    monkeypatch.setattr(fetch, "SHIU_COMMIT", "wrong")
    with pytest.raises(ValueError, match="Shiu commit mismatch"):
        fetch.fetch()


def test_synthetic_archive_and_codex_records(synthetic_cache) -> None:
    """The synthetic archive and Codex table are fetched with inventory.

    Units: none. Shapes: scalars. Never touches the shared cache.
    """
    fetch, root, cache = synthetic_cache
    by_item = {r["item"]: r for r in json.loads((root / "data/provenance.json").read_text())["records"]}
    rec = by_item["Shiu 2024 simulation archive, sugar-activation results"]
    assert rec["status"] == "fetched"
    assert rec["inventory"] == {".parquet": 3, "files": 3}
    codex = by_item["Zenodo per-neuron post-synapse counts, FlyWire v783"]
    assert codex["status"] == "fetched"
    assert codex["inventory"] == {"rows": 7, "columns": 3}
    extracts = [by_item[f"Shiu archive {member}"] for member in fetch.SHIU_SUGAR_MEMBERS]
    assert {r["status"] for r in extracts} == {"fetched"}
    assert {r["path"] for r in extracts} == {".cache/shiu-archive/sugarR.parquet", ".cache/shiu-archive/sugarR_150Hz.parquet"}


def test_synthetic_sugar_extract_recreated_when_missing(synthetic_cache) -> None:
    """A deleted sugar extract is re-extracted without any download.

    Units: none. Shapes: scalars. Never touches the shared cache.
    """
    fetch, root, cache = synthetic_cache
    dest = cache / "shiu-archive" / "sugarR.parquet"
    assert dest.exists()
    dest.unlink()
    fetch.fetch()
    assert dest.exists()


def test_synthetic_sugar_extract_drift_raises(synthetic_cache) -> None:
    """A modified sugar extract raises without rewriting provenance.

    Units: none. Shapes: scalars. Never touches the shared cache.
    """
    fetch, root, cache = synthetic_cache
    dest = cache / "shiu-archive" / "sugarR.parquet"
    dest.write_bytes(b"drifted")
    before = (root / "data/provenance.json").read_bytes()
    with pytest.raises(ValueError, match="drifted"):
        fetch.fetch()
    assert (root / "data/provenance.json").read_bytes() == before


def test_extract_members_writes_only_missing(tmp_path: Path) -> None:
    """Extraction writes missing members and rejects drifted ones.

    Units: bytes. Shapes: scalars. Never touches the shared cache.
    """
    fetch = fetch_module()
    archive = tmp_path / "results.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("a/sugarR.parquet", "spikes")
    dest_dir = tmp_path / "out"
    first = fetch.extract_members(archive, ("a/sugarR.parquet",), dest_dir)
    assert first[0].read_bytes() == b"spikes"
    assert fetch.extract_members(archive, ("a/sugarR.parquet",), dest_dir) == first
    first[0].write_bytes(b"other")
    with pytest.raises(ValueError, match="drifted"):
        fetch.extract_members(archive, ("a/sugarR.parquet",), dest_dir)


@pytest.mark.parametrize("name_attr,url_attr", [("SHIU_ARCHIVE_NAME", "SHIU_ARCHIVE_URL"), ("ZENODO_POST_NAME", "ZENODO_POST_URL")])
def test_missing_asset_triggers_download(synthetic_cache, monkeypatch: pytest.MonkeyPatch, name_attr: str, url_attr: str) -> None:
    """A missing archive or Zenodo file triggers a download of its URL.

    Units: none. Shapes: scalars. Never touches the shared cache.
    """
    fetch, root, cache = synthetic_cache
    parent = cache / ("shiu-archive" if name_attr == "SHIU_ARCHIVE_NAME" else f"zenodo-{fetch.ZENODO_RECORD}")
    (parent / getattr(fetch, name_attr)).unlink()
    calls: list[str] = []

    def fake_download(url: str, dest: Path, cap_left: int) -> int:
        calls.append(url)
        raise RuntimeError("no network in test")

    monkeypatch.setattr(fetch, "download", fake_download)
    with pytest.raises(RuntimeError, match="no network in test"):
        fetch.fetch()
    assert calls == [getattr(fetch, url_attr)]


def test_fetch_preserves_other_writers_temporary_files(synthetic_cache) -> None:
    fetch, root, cache = synthetic_cache
    paths = [cache / directory / "tmp-active-download" for directory in
             ("shiu-archive", "zenodo-10676866")]
    for path in paths:
        path.write_bytes(b"another writer's partial transfer")
    fetch.fetch()
    for path in paths:
        assert path.read_bytes() == b"another writer's partial transfer"


def test_extract_cleans_own_temp_on_failure(tmp_path, monkeypatch):
    fetch = fetch_module()
    archive = tmp_path / "input.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("sugar.parquet", "spikes")
    dest = tmp_path / "out"
    def interrupted(*args):
        raise OSError("interrupted replace")
    monkeypatch.setattr(Path, "replace", interrupted)
    with pytest.raises(OSError, match="interrupted"):
        fetch.extract_members(archive, ("sugar.parquet",), dest)
    assert list(dest.iterdir()) == []


def test_cache_env_and_default(monkeypatch: pytest.MonkeyPatch) -> None:
    fetch = fetch_module()
    monkeypatch.delenv("FLYONENOMICS_CACHE_DIR", raising=False)
    assert fetch.cache_dir() == fetch.ROOT / ".cache"
    monkeypatch.setenv("FLYONENOMICS_CACHE_DIR", "/tmp/custom-cache")
    assert fetch.cache_dir() == Path("/tmp/custom-cache")


def test_zenodo_shape_uses_actual_lowercase_count(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.feather as feather

    fetch = fetch_module()
    path = tmp_path / "counts.feather"
    feather.write_feather(pa.table({"post_pt_root_id": [1], "neuropil": ["EB"], "count": [5]}), path)
    assert fetch.codex_table_shape(path) == (1, ["post_pt_root_id", "neuropil", "count"])
    feather.write_feather(pa.table({"post_pt_root_id": [1], "neuropil": ["EB"], "Count": [5]}), path)
    with pytest.raises(ValueError, match="columns mismatch"):
        fetch.codex_table_shape(path)
