"""WAL run index, crash reconciliation and file-boundary validation."""
from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from flyonenomics.io import read_parquet
from flyonenomics.schema import Experiment
from flyonenomics.schema.experiment import Probe
from flyonenomics.store.results import MS_PER_SECOND, TABLE_SUFFIXES, read_json, read_settle, table_schemas

SQLITE_TIMEOUT_S = 30
CLOCK_REL_TOL = 1e-6
CLOCK_ABS_TOL_MS = 1e-6


def process_alive(pid: int | None) -> bool:
    """Check one process without changing it; units none, scalar PID."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class RunIndex:
    """One SQLite row per run, visible from queued onward; scalar JSON columns."""
    def __init__(self, root: str | Path = "runs") -> None:
        """Create the WAL database; units none, one path."""
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "index.sqlite"
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, name TEXT, created TEXT, state TEXT, arms TEXT, seeds TEXT, assay TEXT, headline_metrics TEXT, artefact_flags TEXT)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=SQLITE_TIMEOUT_S)
        connection.row_factory = sqlite3.Row
        return connection

    def upsert(self, run_id: str, experiment: dict[str, Any], status: dict[str, Any], metrics: dict[str, Any] | None = None, flags: Any = None) -> None:
        """Insert/update one lifecycle row; units per metrics, scalar columns."""
        assays = sorted({p.assay for arm in Experiment.model_validate(experiment).arms for p in arm.expanded() if isinstance(p, Probe)})
        values = (run_id, experiment["name"], status.get("created", run_id.rsplit("-", 1)[0]), status["state"],
                  json.dumps([a["label"] for a in experiment["arms"]]), json.dumps(experiment["seeds"]), json.dumps(assays),
                  json.dumps(metrics or {}), json.dumps(flags or []))
        with self._connect() as connection:
            connection.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET name=excluded.name, created=excluded.created, state=excluded.state, arms=excluded.arms, seeds=excluded.seeds, assay=excluded.assay, headline_metrics=excluded.headline_metrics, artefact_flags=excluded.artefact_flags", values)

    def rows(self) -> list[dict[str, Any]]:
        """Return index rows ordered by creation; units per metrics, list of mappings."""
        with self._connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM runs ORDER BY created, run_id")]

    def rebuild(self) -> list[dict[str, Any]]:
        """Reconcile directories; missing manifest means incomplete unless running/alive."""
        for directory in sorted(self.root.iterdir()):
            if not directory.is_dir() or not (directory / "experiment.json").exists():
                continue
            try:
                experiment = read_json(directory / "experiment.json")
                status = read_json(directory / "status.json") if (directory / "status.json").exists() else {}
                manifest = read_json(directory / "manifest.json") if (directory / "manifest.json").exists() else None
                if manifest is None:
                    state = "running" if status.get("state") == "running" and process_alive(status.get("pid")) else "incomplete"
                else:
                    state = manifest.get("state", status.get("state", "incomplete"))
                self.upsert(directory.name, experiment, {**status, "state": state},
                            read_json(directory / "metrics.json") if manifest and (directory / "metrics.json").exists() else None,
                            manifest.get("artefact_flags", []) if manifest else [])
            except (ValueError, OSError, KeyError):
                # Preserve the existing row but never retain a false done state.
                with self._connect() as connection:
                    connection.execute("UPDATE runs SET state='incomplete' WHERE run_id=?", (directory.name,))
        existing = {p.name for p in self.root.iterdir() if p.is_dir()}
        with self._connect() as connection:
            for row in connection.execute("SELECT run_id FROM runs").fetchall():
                if row[0] not in existing:
                    connection.execute("DELETE FROM runs WHERE run_id=?", (row[0],))
        return self.rows()


def rebuild(root: str | Path = "runs") -> list[dict[str, Any]]:
    """Rebuild a store index; units none, list of index rows."""
    return RunIndex(root).rebuild()


def validate_run(run_id: str | Path, runs_dir: str | Path = "runs") -> list[str]:
    """Check implied files, dtypes and relative clocks; errors list empty on success."""
    path = Path(run_id)
    if not path.is_dir():
        path = Path(runs_dir) / path
    errors: list[str] = []
    for name in ("experiment.json", "status.json", "manifest.json", "metrics.json", "log.txt"):
        if not (path / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        return errors
    try:
        experiment = Experiment.model_validate(read_json(path / "experiment.json"))
        manifest = read_json(path / "manifest.json")
        status = read_json(path / "status.json")
        read_json(path / "metrics.json")
        if manifest["protocol_hash"] != experiment.protocol_hash():
            errors.append("manifest protocol_hash differs from validated experiment")
        if manifest["state"] != status["state"]:
            errors.append("manifest/status state mismatch")
        schemas = table_schemas(experiment.record, manifest["compartments"])
        partial = status["state"] == "cancelled"
        expected: list[tuple[Path, str]] = []
        clocks: dict[Path, np.ndarray] = {}
        probe_limits: dict[Path, int] = {}
        for arm in experiment.arms:
            for seed in experiment.seeds:
                directory = path / f"arm-{arm.label}" / f"seed-{seed}"
                if partial and not directory.exists():
                    continue
                expected.extend((directory / f"{name}.parquet", name) for name in ("index", "slow-state"))
                if not (directory / "metrics.json").exists():
                    errors.append(f"missing {directory.relative_to(path)}/metrics.json")
                    seed_metrics = {"probes": {}}
                else:
                    seed_metrics = read_json(directory / "metrics.json")
                for k, phase in enumerate(arm.expanded()):
                    if not isinstance(phase, Probe):
                        continue
                    settle_path = directory / f"probe-{k}-settle.json"
                    if partial and not settle_path.exists():
                        continue
                    try:
                        settle = read_settle(settle_path)
                        overlap = settle.upstream_extended_overlap_idx
                        if not np.array_equal(overlap, np.unique(overlap)) or np.any(overlap < 0):
                            errors.append(f"invalid overlap {settle_path.name}")
                    except (ValueError, OSError) as exc:
                        errors.append(f"invalid {settle_path}: {exc}")
                    metric = seed_metrics.get("probes", {}).get(str(k), {})
                    seconds = metric.get("duration_s")
                    if seconds is None or not np.isfinite(seconds) or seconds < 0:
                        errors.append(f"invalid duration in {directory.relative_to(path)}/metrics.json probe {k}")
                    elif not partial and not np.isclose(seconds, phase.duration_s, rtol=0, atol=CLOCK_ABS_TOL_MS / MS_PER_SECOND):
                        errors.append(f"incomplete recording for probe {k} in {directory.relative_to(path)}")
                    else:
                        duration_ms = int(round(seconds * MS_PER_SECOND))
                        prefix = directory / f"probe-{k}"
                        probe_limits[prefix] = round(duration_ms / manifest["dt_ms"])
                        clocks[directory / f"probe-{k}-popcount-1ms.parquet"] = (
                            np.arange(duration_ms, dtype=np.int64) * round(1 / manifest["dt_ms"])
                            if experiment.record.popcount else np.zeros(0, dtype=np.int64))
                        clocks[directory / f"probe-{k}-rates.parquet"] = (
                            np.arange(0, duration_ms, experiment.record.rate_bin_ms, dtype=np.int64) * round(1 / manifest["dt_ms"])
                            if experiment.record.rates else np.zeros(0, dtype=np.int64))
                    expected.extend((directory / f"probe-{k}-{name}.parquet", name) for name in TABLE_SUFFIXES)
                    if experiment.record.live and not (directory / "live" / f"probe-{k}.ndjson").is_file():
                        errors.append(f"missing live/probe-{k}.ndjson")
        for table_path, name in expected:
            if not table_path.exists():
                errors.append(f"missing {table_path.relative_to(path)}")
                continue
            try:
                frame = read_parquet(table_path).to_pandas()
                if list(frame.columns) != list(schemas[name]):
                    errors.append(f"wrong columns: {table_path.relative_to(path)}")
                    continue
                for column, dtype in schemas[name].items():
                    if dtype == "str":
                        if not pd.api.types.is_string_dtype(frame[column]):
                            errors.append(f"wrong dtype {table_path.name}:{column}")
                    elif str(frame[column].dtype) != dtype:
                        errors.append(f"wrong dtype {table_path.name}:{column}")
                if "tick" in frame:
                    ticks = frame["tick"].to_numpy()
                    if np.any(ticks < 0) or np.any(np.diff(ticks) < 0):
                        errors.append(f"invalid recording clock {table_path.name}")
                    if "t_ms" in frame and not np.allclose(frame.t_ms, ticks * manifest["dt_ms"], rtol=CLOCK_REL_TOL, atol=CLOCK_ABS_TOL_MS):
                        errors.append(f"t_ms mismatch {table_path.name}")
                    prefix = table_path.parent / table_path.name.removesuffix(f"-{name}.parquet")
                    if prefix in probe_limits and np.any(ticks >= probe_limits[prefix]):
                        errors.append(f"tick outside recording {table_path.name}")
                    if table_path in clocks and not np.array_equal(ticks, clocks[table_path]):
                        errors.append(f"missing or irregular bins {table_path.name}")
                if name == "popcount-1ms" and np.any(frame["count"] < 0):
                    errors.append(f"negative counts {table_path.name}")
                if name == "spikes":
                    index_path = table_path.parent / "index.parquet"
                    if index_path.exists():
                        size = len(read_parquet(index_path).to_pandas())
                        if np.any(frame.idx < 0) or np.any(frame.idx >= size):
                            errors.append(f"invalid neuron index {table_path.name}")
                if name == "index" and not np.array_equal(frame.idx, np.arange(len(frame))):
                    errors.append(f"invalid engine order {table_path.name}")
            except (ValueError, OSError) as exc:
                errors.append(f"unreadable {table_path.name}: {exc}")
    except (ValueError, KeyError, OSError) as exc:
        errors.append(str(exc))
    return errors
