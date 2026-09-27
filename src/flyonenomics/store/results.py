"""Atomic run files, typed parquet boundaries and probe recording."""
from __future__ import annotations
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any
import numpy as np
from flyonenomics.orchestrator.slowstate import DRUGS
from flyonenomics.schema.experiment import Record
from flyonenomics.types import ChunkResult, SettleRecord, SpikeTable

MS_PER_SECOND = 1000
JSON_INDENT = 2
TABLE_SUFFIXES = ("spikes", "rates", "popcount-1ms", "dopamine", "receptors", "drug", "arena")
ARENA_FIELDS = ("x", "y", "h", "omega", "r_L", "r_R")
STIMULUS_FIELDS = ("az_arena", "az_fly", "width", "contrast")


def json_value(value: Any) -> Any:
    """Convert NumPy/dataclass values at the file boundary; units/shapes preserved."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot encode {type(value).__name__}")


def atomic_json(path: str | Path, value: Any) -> None:
    """Write JSON then atomically rename in the same directory; units/shapes preserved."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=JSON_INDENT, default=json_value, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def read_json(path: str | Path) -> Any:
    """Read one JSON file; units/shapes per stored schema."""
    from flyonenomics.io import read_json as read_logged_json

    return read_logged_json(path)


def table_schemas(record: Record, compartments: list[str]) -> dict[str, dict[str, str]]:
    """Return ordered columns and dtypes; ticks/ms/Hz/µM, tables (rows, columns)."""
    clock = {"tick": "int64", "t_ms": "float32"}
    return {
        "index": {"idx": "int32", "root_id": "int64"},
        "spikes": {"idx": "int32", **clock},
        "rates": {**clock, **dict.fromkeys(record.rates, "float64")},
        "popcount-1ms": {"tick": "int64", "count": "int32"},
        "dopamine": {**clock, **dict.fromkeys(compartments, "float64")},
        "receptors": {**clock, **{f"occ_{r}_{c}": "float64" for c in compartments for r in ("D1", "D2")}},
        "drug": {**clock, **{f"C_b_{d}": "float64" for d in DRUGS},
                 **{f"{key}_{c}": "float64" for c in compartments for key in ("rel", "Km_eff")}},
        "arena": {**clock, **dict.fromkeys(ARENA_FIELDS, "float64"),
                  **{f"{key}_{stimulus}": "float64" for stimulus in ("A", "B", "distractor") for key in STIMULUS_FIELDS}},
        "slow-state": {"t_brain_s": "float64", **{f"C_b_{d}": "float64" for d in DRUGS}, "rel": "float64", "phase_label": "str"},
    }


def write_table(path: str | Path, schema: dict[str, str], columns: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Write a typed parquet table atomically, including zero rows; units per schema."""
    import pandas as pd

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(columns, columns=list(schema)).astype(schema)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def write_settle(path: Path, record: SettleRecord) -> None:
    """Serialize settle including overlap indices; seconds/µM/Hz, arrays (m,)."""
    raw = asdict(record)
    for key in ("unresolved", "da_gap_um"):
        if raw[key] is None:
            del raw[key]  # Phase 1 settle files keep their Phase 1 keys.
    atomic_json(path, raw)


def read_settle(path: Path) -> SettleRecord:
    """Restore typed settle arrays; seconds/µM/Hz, overlap int32 (m,)."""
    raw = read_json(path)
    for key in ("fixed_point_da_c", "final_da_c", "final_rates_hz"):
        raw[key] = np.asarray(raw[key], dtype=np.float64)
    overlap = raw.get("upstream_extended_overlap_idx", [])
    if not isinstance(overlap, list) or any(
        type(idx) is not int or not 0 <= idx <= np.iinfo(np.int32).max for idx in overlap
    ):
        raise ValueError("overlap indices must be nonnegative int32 integers")
    raw["upstream_extended_overlap_idx"] = np.asarray(overlap, dtype=np.int32)
    return SettleRecord(**raw)


class ResultsStore:
    """Results root; units none, run directories and one SQLite index."""
    def __init__(self, root: str | Path = "runs") -> None:
        """Create the store root and WAL index; units none, one path."""
        from flyonenomics.store.index import RunIndex
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = RunIndex(self.root)

    def run_path(self, run_id: str) -> Path:
        """Resolve a run ID beneath the store; units none, one path."""
        if Path(run_id).name != run_id or run_id in (".", ".."):
            raise ValueError("invalid run_id")
        return self.root / run_id

    def cancel(self, run_id: str) -> None:
        """Request cancellation at the next boundary; units none, one run ID."""
        path = self.run_path(run_id)
        if not path.is_dir():
            raise FileNotFoundError(path)
        (path / "CANCEL").touch()

    def validate_run(self, run_id: str) -> list[str]:
        """Return schema/missing-file errors; units none, list empty on success."""
        from flyonenomics.store.index import validate_run
        return validate_run(self.run_path(run_id))


class ProbeRecorder:
    """NumPy-backed chunk accumulation; ticks relative to recording, Hz rates."""
    def __init__(self, directory: Path, k: int, record: Record, registry: Any, start_tick: int, dt_ms: float) -> None:
        """Prepare a probe recorder; ticks/ms, neuron indices (m,) per population."""
        self.directory, self.k, self.record, self.registry = directory, k, record, registry
        self.start_tick, self.dt_ms = start_tick, dt_ms
        self.schemas = table_schemas(record, [c.name for c in registry.compartments()])
        self.populations = {name: registry.population(name).idx for name in dict.fromkeys([*record.rates, "MN9"])}
        self.total = dict.fromkeys(self.populations, 0)
        self.bin_counts = dict.fromkeys(record.rates, 0)
        self.bin_ms = 0.0
        self.bin_tick = 0
        self.rates_rows: list[dict[str, Any]] = []
        self.histograms: list[np.ndarray] = []
        self.hist_ticks: list[np.ndarray] = []
        self.arena_rows: list[dict[str, Any]] = []
        self.dopamine_rows: list[dict[str, float]] = []
        self.receptor_rows: list[dict[str, float]] = []
        self.drug_rows: list[dict[str, float]] = []
        self.duration_ms = 0.0

    def chunk(self, result: ChunkResult, neuromod: Any, arena: dict[str, float], record_start_tick: int) -> None:
        """Accumulate one completed chunk; counts (n,), histogram (chunk_ms,), seconds in state."""
        if record_start_tick != self.start_tick:
            raise ValueError("record_start_tick changed")
        tick = result.tick0 - self.start_tick
        ms = (result.tick1 - result.tick0) * self.dt_ms
        for name, idx in self.populations.items():
            count = int(result.counts[idx].sum())
            self.total[name] += count
            if name in self.bin_counts:
                self.bin_counts[name] += count
        if not self.bin_ms:
            self.bin_tick = tick
        self.bin_ms += ms
        self.duration_ms += ms
        if self.bin_ms >= self.record.rate_bin_ms:
            self._flush_rates()
        self.histograms.append(result.hist_1ms.copy())
        self.hist_ticks.append(tick + np.arange(len(result.hist_1ms), dtype=np.int64) * round(1 / self.dt_ms))
        clock = {"tick": tick, "t_ms": tick * self.dt_ms}
        compartments = [c.name for c in self.registry.compartments()]
        if self.record.dopamine:
            self.dopamine_rows.append({**clock, **{name: float(neuromod.da_c[i]) for i, name in enumerate(compartments)}})
        if self.record.receptors:
            self.receptor_rows.append({**clock, **{f"occ_D1_{name}": float(neuromod.occ_D1[i]) for i, name in enumerate(compartments)},
                                       **{f"occ_D2_{name}": float(neuromod.occ_D2[i]) for i, name in enumerate(compartments)}})
        if self.record.drug:
            self.drug_rows.append({**clock, **{f"C_b_{drug}": float(value) for drug, value in neuromod.concentrations.items()},
                                   **{f"rel_{name}": float(neuromod.rel[i]) for i, name in enumerate(compartments)},
                                   **{f"Km_eff_{name}": float(neuromod.Km_eff[i]) for i, name in enumerate(compartments)}})
        if self.record.arena:
            self.arena_rows.append({**{key: 0.0 for key in self.schemas["arena"]},
                                   "tick": tick, "t_ms": tick * self.dt_ms, **arena})

    def _flush_rates(self) -> None:
        self.rates_rows.append({"tick": self.bin_tick, "t_ms": self.bin_tick * self.dt_ms,
                                **{name: self.bin_counts[name] / (len(self.populations[name]) * self.bin_ms / MS_PER_SECOND) for name in self.record.rates}})
        self.bin_counts = dict.fromkeys(self.record.rates, 0)
        self.bin_ms = 0.0

    def finalise(self, spikes: SpikeTable, assay: str) -> dict[str, Any]:
        """Write valid complete or partial tables; ticks/ms, spike arrays (events,)."""
        if self.bin_ms:
            self._flush_rates()
        if self.record.spikes == "all":
            mask = np.ones(len(spikes.idx), dtype=bool)
        else:
            selected = [self.registry.population(name).idx for name in self.record.spikes]
            idx = np.concatenate(selected) if selected else np.zeros(0, dtype=np.int32)
            mask = np.isin(spikes.idx, idx)
        ticks = spikes.tick[mask] - self.start_tick
        columns: dict[str, Any] = {
            "spikes": {"idx": spikes.idx[mask], "tick": ticks, "t_ms": ticks.astype(np.float32) * self.dt_ms},
            "rates": self.rates_rows,
            "popcount-1ms": {"tick": np.concatenate(self.hist_ticks) if self.hist_ticks else np.zeros(0, dtype=np.int64),
                             "count": np.concatenate(self.histograms) if self.histograms else np.zeros(0, dtype=np.int32)},
            "arena": self.arena_rows, "dopamine": self.dopamine_rows, "receptors": self.receptor_rows, "drug": self.drug_rows,
        }
        for suffix in TABLE_SUFFIXES:
            # Emit full empty schemas even for disabled tables, a valid superset.
            enabled = getattr(self.record, "popcount" if suffix == "popcount-1ms" else suffix)
            write_table(self.directory / f"probe-{self.k}-{suffix}.parquet", self.schemas[suffix], columns[suffix] if enabled else [])
        seconds = self.duration_ms / MS_PER_SECOND
        hist = columns["popcount-1ms"]["count"]
        metrics: dict[str, Any] = {
            "duration_s": seconds, "populations": {
                name: {"mean_rate_hz": self.total[name] / (len(self.populations[name]) * seconds) if seconds else None,
                       "spikes": self.total[name], "neuron_count": len(self.populations[name]), "seconds": seconds}
                for name in self.record.rates},
            "popcount": {"mean_per_1ms": float(hist.mean()) if len(hist) else None,
                         "max_per_1ms": int(hist.max()) if len(hist) else None, "bins": len(hist)},
        }
        if assay == "sugar_reflex":
            metrics["MN9"] = {"mean_rate_hz": self.total["MN9"] / (len(self.populations["MN9"]) * seconds) if seconds else None,
                              "spikes": self.total["MN9"], "neuron_count": len(self.populations["MN9"]), "seconds": seconds}
        return metrics
