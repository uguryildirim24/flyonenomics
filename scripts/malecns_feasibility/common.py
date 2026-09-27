"""Shared constants and helpers for the MaleCNS v1.0 feasibility check."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.feather as feather

from flyonenomics.io import hash_file, load_npy

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "malecns-v1.0"
ANNOTATIONS = CACHE / "body-annotations-male-cns-v1.0-minconf-0.5.feather"
TRANSMITTERS = CACHE / "body-neurotransmitters-male-cns-v1.0.feather"
CONNECTIONS = CACHE / "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
DERIVED = CACHE / "derived"
COMPLETENESS = DERIVED / "completeness.csv"
METADATA = DERIVED / "graph-metadata.json"

DOWNLOADS = {
    "body-annotations-male-cns-v1.0-minconf-0.5.feather": (
        "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/"
        "body-annotations-male-cns-v1.0-minconf-0.5.feather"
    ),
    "body-neurotransmitters-male-cns-v1.0.feather": (
        "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/"
        "body-neurotransmitters-male-cns-v1.0.feather"
    ),
    "connectome-weights-male-cns-v1.0-minconf-0.5.feather": (
        "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/"
        "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
    ),
}

SHA256 = {
    "body-annotations-male-cns-v1.0-minconf-0.5.feather": "2177e246113e4cfbf1e7772ec37c6da1955ff22e8063d0b1f833101f99a9a3b2",
    "body-neurotransmitters-male-cns-v1.0.feather": "95c9289220663abeb3409f3ad9e5a7f8a53f8093f5139d15502cd08da8879621",
    "connectome-weights-male-cns-v1.0-minconf-0.5.feather": "e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1",
}

# Same fast-sign reading as Shiu 2024 and this project's FlyWire substrate.
NT_SIGN = {
    "acetylcholine": 1,
    "dopamine": 1,
    "serotonin": 1,
    "octopamine": 1,
    "gaba": -1,
    "glutamate": -1,
    "histamine": -1,
}

FLYVIS_TYPES = (
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
    "L1", "L2", "L3", "L4", "L5", "Lawf1", "Lawf2", "Am", "C2", "C3",
    "CT1(Lo1)", "CT1(M10)", "Mi1", "Mi2", "Mi3", "Mi4", "Mi9", "Mi10",
    "Mi11", "Mi12", "Mi13", "Mi14", "Mi15", "T1", "T2", "T2a", "T3",
    "T4a", "T4b", "T4c", "T4d", "T5a", "T5b", "T5c", "T5d", "Tm1",
    "Tm2", "Tm3", "Tm4", "Tm5Y", "Tm5a", "Tm5b", "Tm5c", "Tm9", "Tm16",
    "Tm20", "Tm28", "Tm30", "TmY3", "TmY4", "TmY5a", "TmY9", "TmY10",
    "TmY13", "TmY14", "TmY15", "TmY18",
)


def sha256(path: Path) -> str:
    return hash_file(path)


def load_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    annotations = feather.read_feather(ANNOTATIONS)
    transmitters = feather.read_feather(TRANSMITTERS)
    return annotations, transmitters


def graph_dir() -> Path:
    """Return the exact array-cache directory consumed by BrianEngine."""
    from flyonenomics.connectome_arrays import connectome_array_dir

    return connectome_array_dir(COMPLETENESS, CONNECTIONS)


def load_graph() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    directory = graph_dir()
    return tuple(
        load_npy(directory / name, mmap_mode="r")
        for name in ("root_ids.npy", "i.npy", "j.npy", "w_exc.npy", "weight.npy")
    )  # type: ignore[return-value]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def file_record(path: Path, url: str) -> dict[str, object]:
    return {
        "path": str(path.relative_to(ROOT)),
        "source": url,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
