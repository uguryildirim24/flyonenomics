"""Fetch every external file, verify checksums, write data/provenance.json.

Cache rule: uses FLYONENOMICS_CACHE_DIR when set, else .cache under
the project root. Never edits the Shiu clone except by reading it.
Per-invocation download guard: read once from download_limit_bytes();
larger assets are recorded with status "not fetched" with URL and size.

Units: sizes in bytes, hashes hex. Shapes: scalars only.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
import zipfile
import tempfile
from typing import Any

from flyonenomics.io import read_bytes, read_json, read_text
from flyonenomics.types import ProvenanceRecord
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DOWNLOAD_LIMIT_BYTES = 30 * 1000**3


def download_limit_bytes() -> int:
    """Return the per-invocation download guard in bytes.

    Units: bytes. Shapes: one scalar. Reads
    FLYONENOMICS_DOWNLOAD_LIMIT_BYTES when set; defaults to
    DEFAULT_DOWNLOAD_LIMIT_BYTES, which admits the Shiu results
    archive and the Codex per-neuron table in one invocation.
    This is the single place the guard is read from.
    """
    raw = os.environ.get("FLYONENOMICS_DOWNLOAD_LIMIT_BYTES", "").strip()
    if raw:
        return int(raw)
    return DEFAULT_DOWNLOAD_LIMIT_BYTES

SHIU_COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
SHIU_FILES = {
    "2023_03_23_completeness_630_final.csv": {
        "bytes": 3057611,
        "sha256": "e6b71e17671a9bdb05f55e4bc6774640a1418cb7a05125e0fc994ad40f9bfdfb",
    },
    "2023_03_23_connectivity_630_final.parquet": {
        "bytes": 86630944,
        "sha256": "94db8c650533bc36ffa3223f2e62325d5648b8d6bd31c3a4e1c804628c7557b3",
    },
    "Completeness_783.csv": {
        "bytes": 3327347,
        "sha256": "bbb847a4cc2caaa7a16349722d220c087317b946d148d4d592d94d250617a311",
    },
    "Connectivity_783.parquet": {
        "bytes": 100804642,
        "sha256": "efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347",
    },
    "sez_neurons.pickle": {
        "bytes": 5114,
        "sha256": "2bc5a2a8289924f2de39a8e68bdc07025cb6d6c6c6ddc83a973c0cace7cec2ce",
    },
}

ANNOT_V211_COMMIT = "ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0"
ANNOT_V211_BYTES = 27015208
ANNOT_V110_COMMIT = "df6bb136f5b3d91c3992df4e8de2642329e2a384"
ANNOT_V110_BYTES = 21714061
ANNOT_V110_SHA256 = "55c99c61eecf8db6cc36f1a684b35e4c4208afbab02197d753ccc8dc2a6e2e76"

FIGSHARE_URL = "https://ndownloader.figshare.com/files/3178193"
FIGSHARE_BYTES = 6728585
FIGSHARE_MD5 = "c9e8e9c72fc04a694fb24e4f84b9699d"

CETRAN_COMMIT = "1f98ddd83366db53d4aabfa6f42b1153f8e1553d"
CETRAN_FILES = [
    "CeTrAn/functions/functions.r",
    "CeTrAn/functions/utils.r",
    "CeTrAn/scripts/angledev.r",
    "CeTrAn/CeTrAn_fromxml_4.rgg",
]

SHIU_ARCHIVE_DOI = "https://doi.org/10.17617/3.CZODIW"
SHIU_ARCHIVE_FILE_ID = 223847
SHIU_ARCHIVE_NAME = "results.zip"
SHIU_ARCHIVE_URL = f"https://edmond.mpg.de/api/access/datafile/{SHIU_ARCHIVE_FILE_ID}"
SHIU_ARCHIVE_BYTES = 4499610373
SHIU_ARCHIVE_MD5 = "f6f2e314821fa6a4196214e3b2b14bc4"
SHIU_SUGAR_MEMBERS = (
    "results/example/sugarR.parquet",
    "results/figure_1/data/sugarR_150Hz.parquet",
)
CODEX_URL = "https://codex.flywire.ai/api/download"
CODEX_SYNAPSE_BYTES = 9492998242
ZENODO_RECORD = "10676866"
ZENODO_POST_NAME = "per_neuron_neuropil_count_post_783.feather"
ZENODO_POST_URL = ("https://zenodo.org/api/records/10676866/files/"
                   "per_neuron_neuropil_count_post_783.feather/content")
ZENODO_POST_BYTES = 233843050
ZENODO_POST_MD5 = "bb5999f10920ade803d9f37097a43a56"


def cache_dir() -> Path:
    """Return the download cache directory.

    Units: none. Shapes: one path. Uses FLYONENOMICS_CACHE_DIR
    when set, else .cache under the project root.
    """
    override = os.environ.get("FLYONENOMICS_CACHE_DIR", "").strip()
    if override:
        return Path(override)
    return ROOT / ".cache"


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex of one file.

    Units: none. Shapes: one path in, one hex string out.
    """
    from flyonenomics.io import hash_file

    return hash_file(path)


def md5_file(path: Path) -> str:
    """Return the MD5 hex of one file.

    Units: none. Shapes: one path in, one hex string out.
    """
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path, cap_left: int) -> int:
    """Download one URL to dest, honouring the byte cap.

    Units: cap_left and the return value are bytes. Shapes: scalars.
    Returns the downloaded byte count. Raises on cap breach.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "flyonenomics-wp0"})
    total = 0
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as out:
            tmp = Path(out.name)
            with urllib.request.urlopen(req, timeout=120) as resp:
                while block := resp.read(1 << 20):
                    total += len(block)
                    if total > cap_left:
                        raise RuntimeError(f"download cap breached by {url}")
                    out.write(block)
        tmp.replace(dest)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return total


def today() -> str:
    """Return today's UTC date as YYYY-MM-DD.

    Units: none. Shapes: one string.
    """
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def verify_file(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    """Compare bytes and recorded checksums before use. Units: bytes. Shapes: scalars."""
    actual = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    if expected.get("md5"):
        actual["md5"] = md5_file(path)
    for field in ("bytes", "sha256", "md5"):
        if expected.get(field) is not None and actual.get(field) != expected[field]:
            raise ValueError(f"checksum mismatch on {path}: {field} expected {expected[field]}, got {actual.get(field)}")
    return actual


def figshare_inventory(path: Path) -> dict[str, int]:
    """Count actual archive members. Units: file counts. Shapes: two scalar counts."""
    with zipfile.ZipFile(path) as archive:
        names = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
    inventory = {suffix: sum(name.endswith(suffix) for name in names) for suffix in (".dat", ".xml")}
    if inventory != {".dat": 135, ".xml": 134}:
        raise ValueError(f"figshare inventory mismatch: {inventory}")
    return inventory


def shiu_archive_inventory(path: Path) -> dict[str, int]:
    """Count archive members by file suffix. Units: file counts. Shapes: scalar counts."""
    with zipfile.ZipFile(path) as archive:
        names = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
    inventory: dict[str, int] = {"files": len(names)}
    for name in names:
        leaf = name.rsplit("/", 1)[-1]
        suffix = "." + leaf.rsplit(".", 1)[-1].lower() if "." in leaf else "<none>"
        inventory[suffix] = inventory.get(suffix, 0) + 1
    return dict(sorted(inventory.items()))


def codex_table_shape(path: Path) -> tuple[int, list[str]]:
    """Return the row count and column names of a feather table.

    Units: rows count. Shapes: one scalar and one list of names.
    """
    from flyonenomics.io import read_feather

    table = read_feather(path)
    expected = {"post_pt_root_id", "neuropil", "count"}
    if set(table.column_names) != expected:
        raise ValueError(f"Zenodo post-count columns mismatch: {table.column_names}")
    return table.num_rows, table.column_names


def extract_members(archive: Path, members: tuple[str, ...], dest_dir: Path) -> list[Path]:
    """Extract listed archive members into dest_dir, never overwriting drift.

    Units: bytes. Shapes: one path per member. Writes a member only
    when its destination is missing; an existing destination with
    different bytes raises instead of being replaced. Returns the
    destination paths in member order.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with zipfile.ZipFile(archive) as bundle:
        for member in members:
            data = bundle.read(member)
            dest = dest_dir / Path(member).name
            if dest.exists():
                if read_bytes(dest) != data:
                    raise ValueError(f"extracted file drifted: {dest}")
            else:
                tmp: Path | None = None
                try:
                    with tempfile.NamedTemporaryFile(dir=dest_dir, delete=False) as handle:
                        tmp = Path(handle.name)
                        handle.write(data)
                    tmp.replace(dest)
                finally:
                    if tmp is not None:
                        tmp.unlink(missing_ok=True)
            paths.append(dest)
    return paths


def _write_json(dest: Path, data: dict[str, Any]) -> None:
    text = json.dumps(data, indent=2) + "\n"
    if dest.exists() and read_text(dest) == text:
        return
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=dest.parent, delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(text)
        tmp.replace(dest)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def fetch() -> dict[str, Any]:
    """Verify existing assets or fetch missing ones, preserving the provenance baseline.

    Units: sizes and the invocation's transfer count in bytes. Shapes: records list.
    A .cache/ path is relative to cache_dir(), including when the cache is shared.
    Other recorded paths are relative to the repository root.
    """
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    provenance = ROOT / "data/provenance.json"
    previous = read_json(provenance) if provenance.exists() else {}
    old = {record["item"]: record for record in previous.get("records", [])}
    limit = download_limit_bytes()
    spent = 0
    records: list[dict[str, Any]] = []

    def asset(item: str, path: Path, *, version: str, source: str, license: str,
              used_for: str, url: str | None = None, commit: str | None = None,
              expected: dict[str, Any] | None = None, note: str | None = None) -> dict[str, Any]:
        """Verify one file and append its record. Units: bytes. Shapes: scalars."""
        nonlocal spent
        prior = old.get(item, {})
        if not path.exists():
            if url is None:
                raise FileNotFoundError(f"missing local asset: {path}")
            spent += download(url, path, limit - spent)
        actual = verify_file(path, expected or {})
        verify_file(path, prior)
        canonical = ".cache/" + path.relative_to(cache).as_posix() if path.is_relative_to(cache) else path.relative_to(ROOT).as_posix()
        record = dict(item=item, path=canonical, version=version, source=source,
                      license=license, used_for=used_for, status="fetched", **actual,
                      date=prior.get("date", today()))
        if url:
            record["url"] = url
        if commit:
            record["commit"] = commit
        if note:
            record["note"] = note
        records.append(record)
        return record

    shiu = cache / "Drosophila_brain_model"
    head = subprocess.run(["git", "-C", str(shiu), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()
    if head != SHIU_COMMIT:
        raise ValueError(f"Shiu commit mismatch: expected {SHIU_COMMIT}, got {head}")
    shiu_source = "https://github.com/philshiu/Drosophila_brain_model"
    for name, expected in SHIU_FILES.items():
        asset(f"Shiu clone {name}", shiu / name, version=f"commit {SHIU_COMMIT}",
              source=shiu_source, license="MIT (repo); underlying FlyWire data CC-BY 4.0",
              used_for="v630/v783 connectivity and neuron inventories", commit=head, expected=expected)
    for name in ("model.py", "utils.py", "example.ipynb", "figures.ipynb"):
        pinned = subprocess.run(["git", "-C", str(shiu), "show", f"{SHIU_COMMIT}:{name}"],
                                check=True, capture_output=True).stdout
        asset(f"Shiu clone {name}", shiu / name, version=f"commit {SHIU_COMMIT}",
              source=shiu_source, license="MIT", used_for="default params, create_model, poi, notebook root lists",
              commit=head, expected={"bytes": len(pinned), "sha256": hashlib.sha256(pinned).hexdigest()})

    refdir = ROOT / "data/reference"
    refdir.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name in (("baseline-spikes.parquet", "l5-baseline-spikes.parquet"),
                               ("baseline-results.json", "l5-baseline-results.json")):
        src, dest = cache / "l5-proof" / src_name, refdir / dst_name
        item = f"data/reference/{dst_name}"
        if src.exists():
            verify_file(src, old.get(item, {}))
        if not dest.exists():
            shutil.copyfile(src, dest)
        record = asset(item, dest, version="proof run seed 20260912, v630, 21 right sugar GRNs at 150 Hz, upstream-exact mode",
                       source="this repository (copy of proof run output)", license="project license", used_for="test 0.3")
        if src.exists():
            verify_file(src, record)

    annot_source = "https://github.com/flyconnectome/flywire_annotations"
    annot_specs = [
        ("annotations-v2.1.0.tsv", ANNOT_V211_COMMIT, "Supplemental_file1_neuron_annotations.tsv",
         {"bytes": ANNOT_V211_BYTES}, "registry for v783"),
        ("annotations-v1.1.0.tsv", ANNOT_V110_COMMIT, "Supplemental_file1_annotations.tsv",
         {"bytes": ANNOT_V110_BYTES, "sha256": ANNOT_V110_SHA256}, "registry for v630; supervoxel bridge"),
        ("annotations-v2.1.0-columns.md", ANNOT_V211_COMMIT, "Supplemental_files_columns.md",
         {"bytes": 6674}, "annotation column definitions for v783"),
    ]
    for name, commit, remote, expected, used_for in annot_specs:
        asset(name, cache / name, version=f"flywire_annotations commit {commit}",
              source=annot_source, license="CC-BY 4.0", used_for=used_for, commit=commit,
              url=f"https://raw.githubusercontent.com/flyconnectome/flywire_annotations/{commit}/supplemental_files/{remote}",
              expected=expected)

    zip_dest = cache / "github-importJnx5V7.zip"
    rec = asset(zip_dest.name, zip_dest, version="figshare article 1014264 v2, DOI 10.6084/m9.figshare.1014264.v2, Colomb and Brembs 2014",
                source=FIGSHARE_URL, license="CC BY 4.0", used_for="K3 calibration half; test 4.3 holdout; test 4.0b",
                url=FIGSHARE_URL, expected={"bytes": FIGSHARE_BYTES, "md5": FIGSHARE_MD5})
    rec["inventory"] = figshare_inventory(zip_dest)
    rec["note"] = "inventory 135 .dat and 134 .xml files"

    for relative in CETRAN_FILES:
        dest = cache / "CeTrAn" / CETRAN_COMMIT / Path(relative).name
        # Migrate the worker's aggregate record without discarding its sole hash.
        legacy = old.get("CeTrAn source", {})
        expected = {"sha256": legacy["sha256"]} if relative == CETRAN_FILES[0] and legacy.get("sha256") else {}
        asset(f"CeTrAn {relative}", dest, version=f"tag v.4, commit {CETRAN_COMMIT}",
              source="https://github.com/jcolomb/CeTrAn", license="Creative Commons Attribution 3.0 Unported License",
              used_for="normative metric definitions (section 3.5); test 4.0b", commit=CETRAN_COMMIT,
              url=f"https://raw.githubusercontent.com/jcolomb/CeTrAn/{CETRAN_COMMIT}/{relative}", expected=expected,
              note=f"License stated in README.md at commit {CETRAN_COMMIT}")

    archive_dest = cache / "shiu-archive" / SHIU_ARCHIVE_NAME
    rec = asset("Shiu 2024 simulation archive, sugar-activation results", archive_dest,
                version="Edmond dataset 10.17617/3.CZODIW version 3, file id 223847, results.zip",
                source=SHIU_ARCHIVE_DOI, license="MIT",
                used_for="test 1.2 source; holds every figure simulation including the v630 sugar run",
                url=SHIU_ARCHIVE_URL,
                expected={"bytes": SHIU_ARCHIVE_BYTES, "md5": SHIU_ARCHIVE_MD5})
    rec["inventory"] = shiu_archive_inventory(archive_dest)
    rec["note"] = ("Edmond record 10.17617/3.CZODIW offers no separate sugar file; "
                   "results.zip holds .parquet spike outputs for every simulation in figures.ipynb")
    for member, dest in zip(SHIU_SUGAR_MEMBERS, extract_members(archive_dest, SHIU_SUGAR_MEMBERS, archive_dest.parent), strict=True):
        asset(f"Shiu archive {member}", dest,
              version="Edmond dataset 10.17617/3.CZODIW version 3, file id 223847, results.zip",
              source=SHIU_ARCHIVE_DOI, license="MIT",
              used_for="test 1.2 per-neuron rate correlation with the published v630 sugar run",
              url=SHIU_ARCHIVE_URL,
              note="30 one-second trials of the published right-sugar-GRN stimulation; per-neuron rates derive via utils.get_rate")

    zenodo_dest = cache / f"zenodo-{ZENODO_RECORD}" / ZENODO_POST_NAME
    rec = asset("Zenodo per-neuron post-synapse counts, FlyWire v783", zenodo_dest,
                version=f"Zenodo record {ZENODO_RECORD}, FlyWire whole-brain connectome connectivity data",
                source=f"https://doi.org/10.5281/zenodo.{ZENODO_RECORD}", license="CC-BY 4.0",
                used_for="completeness denominator; sums over neuropils give per-neuron input totals",
                url=ZENODO_POST_URL,
                expected={"bytes": ZENODO_POST_BYTES, "md5": ZENODO_POST_MD5})
    rows, columns = codex_table_shape(zenodo_dest)
    rec["inventory"] = {"rows": rows, "columns": len(columns)}
    rec["note"] = (f"per-neuron post-synapse counts by neuropil; rows {rows}; "
                   f"columns {', '.join(columns)}; summing count over neuropils per "
                   "post_pt_root_id gives the per-neuron input total the completeness "
                   "detector needs (SPEC section 11, item 12); open Zenodo copy of the "
                   "Codex v783 release, no login needed")
    records.append(dict(item="FlyWire Codex per-neuron synapse counts", version="v783",
                        source=CODEX_URL, license="CC-BY 4.0",
                        used_for="completeness denominator; unknown when absent",
                        status="not fetched", bytes=CODEX_SYNAPSE_BYTES, url=CODEX_URL,
                        date=old.get("FlyWire Codex per-neuron synapse counts", {}).get("date", today()),
                        note=("Not fetched: Codex Download Data runs server-side and needs "
                              "a Google sign-in, which this fetch cannot provide; the Zenodo "
                              "per-neuron export above stands in for completeness.")))

    for record in records:
        ProvenanceRecord.model_validate(record)
    out = {"download_cap_bytes": limit,
           "downloaded_bytes": previous.get("downloaded_bytes", 0) + spent,
           "records": records}
    _write_json(provenance, out)
    print(f"cache: {cache}")
    print(f"downloaded bytes this run: {spent}")
    print(f"records: {len(records)}")
    return out


def main() -> None:
    """Run the fetch and write data/provenance.json. Units: bytes. Shapes: scalars."""
    fetch()


if __name__ == "__main__":
    main()
