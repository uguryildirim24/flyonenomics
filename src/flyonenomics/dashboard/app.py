"""FlyOnenomics Dashboard FastAPI application and API routes (WP8).

Provides run picker, manifest summary, raster with spike cap, population rates,
dopamine and receptor occupancies, arena trajectory, metrics table, compare view,
and websocket live tail streaming.
Units and shapes stated in every public docstring.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pyarrow.parquet as pq
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from flyonenomics.dashboard.index_snapshot import sqlite_snapshot
from flyonenomics.schema import Experiment
from flyonenomics.schema.experiment import Probe
from flyonenomics.io import read_text, read_yaml
from flyonenomics.store.index import RunIndex, read_json
from flyonenomics.store.results import TABLE_SUFFIXES
from flyonenomics.types import ANALYSIS, load_params
from flyonenomics.orchestrator.seeds import stream

# Constants named per WP8 brief and SPEC.
# WP8 brief / SPEC section 5 row da.DA_ref: reference line in dopamine panel (µM).
DA_REF: float = float(load_params().get("da.DA_ref"))

# WP8 brief: maximum spikes returned for raster view to prevent browser overload.
SPIKE_CAP: int = 20_000

# WP8 brief: maximum rate of websocket live packet forwarding (Hz / messages per second).
LIVE_FORWARD_HZ: float = 10.0

# WP8 brief: poll interval for live stream and status checks (seconds).
LIVE_POLL_INTERVAL_S: float = 0.05

# WP8 brief: default page size for run listings.
PAGE_SIZE: int = 50

# WP8 brief: default server port.
DEFAULT_PORT: int = 8765

# WP8 brief: FlyWire Codex link-out pattern for neuron root IDs.
# SPEC 3.8 / WP8: endpoints of the required bootstrap 95 percent interval.
COMPARE_CI_QUANTILES: tuple[float, float] = (0.025, 0.975)

CODEX_BASE_URL: str = "https://codex.flywire.ai/app/cell_details?root_id="


def phase1_status() -> str:
    """First line of docs/phase1-results.md; SPEC 1.3 status sentence."""
    path = Path(__file__).resolve().parents[3] / "docs" / "phase1-results.md"
    return read_text(path, encoding="utf-8").splitlines()[0]


PHASE1_STATUS = phase1_status()


def component(value: str) -> str:
    """Accept one literal path component; units none, scalar string."""
    if not value or value in (".", "..") or any(c in value for c in ("/", "\\", "%", "\x00")):
        raise HTTPException(status_code=400, detail="Invalid path component")
    return value


def contained(root: Path, *parts: str) -> Path:
    """Resolve symlinks and require a strict descendant; units none, one path."""
    target = root.joinpath(*parts).resolve()
    if target == root or not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Path escapes run directory")
    return target


def resolve_run_directory(runs_dir: Path, run_id: str) -> Path:
    """Resolve a run strictly inside runs_dir; units none, one directory."""
    target = contained(runs_dir, component(run_id))
    if not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Run directory not found: {run_id}")
    return target


class _ScanRoot(type(Path())):
    """Path view excluding unsafe runs before store rebuild opens any JSON files."""

    def iterdir(self) -> Iterator[Path]:
        for directory in super().iterdir():
            if directory.name.startswith(".") or not directory.is_dir():
                continue
            try:
                run = resolve_run_directory(Path(self), directory.name)
                for name in ("experiment.json", "status.json", "manifest.json", "metrics.json"):
                    contained(run, name)
            except (HTTPException, OSError, RuntimeError):
                continue
            yield run


class _MemoryIndex(RunIndex):
    """Run the store's reconciliation algorithm entirely in memory, without WAL writes."""

    def __init__(self, root: Path) -> None:
        self.root = _ScanRoot(root)
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, name TEXT, created TEXT, state TEXT, arms TEXT, seeds TEXT, assay TEXT, headline_metrics TEXT, artefact_flags TEXT)")
        database = contained(root, "index.sqlite")
        if database.is_file():
            # Include committed WAL-only rows without opening any on-disk SQLite
            # connection (even read-only SQLite can create or modify SHM files).
            wal = contained(root, "index.sqlite-wal")
            try:
                snapshot = sqlite_snapshot(database, wal)
                with closing(sqlite3.connect(":memory:")) as source:
                    source.deserialize(snapshot)
                    rows = source.execute("SELECT run_id,name,created,state,arms,seeds,assay,headline_metrics,artefact_flags FROM runs").fetchall()
                self.connection.executemany("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)", rows)
            except (sqlite3.Error, ValueError, OSError):
                pass  # Directory reconciliation also works without an index.

    def _connect(self) -> sqlite3.Connection:
        return self.connection


def list_runs_reconciled(runs_dir: Path) -> list[dict[str, Any]]:
    """Reuse RunIndex.rebuild with an in-memory index; units none, run rows."""
    if not runs_dir.is_dir():
        return []
    index = _MemoryIndex(runs_dir)
    try:
        rows = index.rebuild()
    finally:
        index.connection.close()
    for row in rows:
        for key in ("arms", "seeds", "assay", "headline_metrics", "artefact_flags"):
            if isinstance(row.get(key), str):
                row[key] = json.loads(row[key])
    return rows


def seed_directory(run_path: Path, arm: str, seed: str) -> Path:
    """Resolve canonical arm/seed directory; units none, one path."""
    arm = component(arm)
    seed = component(seed).removeprefix("seed-")
    if not seed.isdecimal():
        raise HTTPException(status_code=400, detail="Invalid seed")
    # Labels may themselves start with arm-: first prefer their canonical path.
    candidates = [f"arm-{arm}", arm] if arm.startswith("arm-") else [f"arm-{arm}"]
    for label in candidates:
        directory = contained(run_path, label, f"seed-{seed}")
        if directory.is_dir():
            return directory
    return contained(run_path, candidates[0], f"seed-{seed}")


def probe_number(probe: str) -> str:
    """Validate expanded phase index; units none, decimal string."""
    number = component(probe).removeprefix("probe-")
    if not number.isdecimal():
        raise HTTPException(status_code=400, detail="Invalid probe")
    return number


def find_parquet_table(run_path: Path, arm: str, seed: str, probe: str | None, table: str) -> Path | None:
    """Locate a contained section 3.8 table; units per schema, one path or None."""
    component(table)
    allowed = TABLE_SUFFIXES if probe is not None else ("index", "slow-state")
    if table not in allowed:
        raise HTTPException(status_code=404, detail="Unknown table")
    directory = seed_directory(run_path, arm, seed)
    filename = f"probe-{probe_number(probe)}-{table}.parquet" if probe is not None else f"{table}.parquet"
    candidate = contained(run_path, str(directory.relative_to(run_path)), filename)
    return candidate if candidate.is_file() else None


def table_payload(run_path: Path, path: Path, name: str) -> dict[str, Any]:
    """Read Arrow types; ticks stay numeric, root identifiers are exact decimal text."""
    arrow = pq.read_table(path)
    schema = {field.name: str(field.type) for field in arrow.schema}
    total = len(arrow)
    subsampled = name == "spikes" and total > SPIKE_CAP
    if subsampled:
        # WP8 mechanics: deterministic evenly spaced row indices, endpoints included.
        arrow = arrow.take(np.linspace(0, total - 1, SPIKE_CAP, dtype=np.int64))
    columns = arrow.to_pydict()
    if "root_id" in columns:
        columns["root_id"] = [str(value) for value in columns["root_id"]]
    notice = "No subsampling applied"
    roots: dict[str, str] = {}
    if name == "spikes":
        notice = (f"Subsampled {SPIKE_CAP} spikes from {total} total spikes "
                  "(deterministic evenly spaced row indices, endpoints included)" if subsampled else
                  f"Complete raster: {total} spikes (under cap {SPIKE_CAP})")
        index_path = contained(run_path, str(path.parent.relative_to(run_path)), "index.parquet")
        if index_path.is_file():
            index = pq.read_table(index_path, columns=["idx", "root_id"]).to_pydict()
            shown = set(columns["idx"])
            roots = {str(idx): str(root) for idx, root in zip(index["idx"], index["root_id"]) if idx in shown}
    return {"table": name, "columns": columns, "schema": schema,
            "json_encodings": {"root_id": "decimal string"} if name == "index" else {},
            "subsampled": subsampled, "total_rows": total, "returned_rows": len(arrow),
            "subsampling_stated": notice, "neuron_roots": roots, "da_ref": DA_REF,
            "arena_radius_mm": load_params().get("arena.R_platform"),
            "openloop": {key: load_params().get(f"openloop.{key}") for key in ("transition_s", "dwell_s")}}


def comparison_payload(a: str, b: str, exp_a: dict[str, Any], exp_b: dict[str, Any],
                       data_a: dict[str, Any], data_b: dict[str, Any], metric: str | None) -> dict[str, Any]:
    """Compare run B minus A by matched seed; units per metric, explicit pairing status."""
    def filtered(data: dict[str, Any]) -> dict[str, Any]:
        selected = json.loads(json.dumps(data))
        for arm in selected.get("arms", {}).values():
            arm["summary"] = {key: value for key, value in arm.get("summary", {}).items() if metric is None or key == metric}
            arm["per_seed"] = [{key: value for key, value in row.items() if key == "seed" or metric is None or key == metric}
                               for row in arm.get("per_seed", [])]
        selected["paired_differences"] = {label: {key: value for key, value in values.items() if metric is None or key == metric}
                                           for label, values in selected.get("paired_differences", {}).items()}
        return selected

    data_a, data_b = filtered(data_a), filtered(data_b)
    reasons: list[str] = []
    if exp_a.get("seed") is None or exp_a.get("seed") != exp_b.get("seed"):
        reasons.append("different S")
    seeds = sorted(exp_a.get("seeds", []))
    if not seeds or seeds != sorted(exp_b.get("seeds", [])):
        reasons.append("different seed lists")
    labels_a = sorted(arm["label"] for arm in exp_a.get("arms", []))
    labels_b = sorted(arm["label"] for arm in exp_b.get("arms", []))
    if not labels_a or labels_a != labels_b:
        reasons.append("different arms")

    differences: dict[str, Any] = {}
    if not reasons:
        for label in labels_a:
            arms = [data.get("arms", {}).get(label, {}) for data in (data_a, data_b)]
            rows = [{row["seed"]: row for row in arm.get("per_seed", [])} for arm in arms]
            keys = sorted(set(arms[0].get("summary", {})) & set(arms[1].get("summary", {})))
            if any(sorted(row) != seeds for row in rows):
                reasons.append("incomplete per-seed metrics")
                break
            rng = stream(exp_a["seed"], 0, 0, ANALYSIS)
            pair: dict[str, Any] = {}
            for key in keys:
                if any(key not in row[seed] for row in rows for seed in seeds):
                    reasons.append("incomplete per-seed metrics")
                    break
                values = np.array([rows[1][seed][key] - rows[0][seed][key] for seed in seeds], dtype=float)
                draws = rng.choice(values, size=(load_params().get("stats.bootstrap_n"), len(values)), replace=True).mean(axis=1)
                pair[key] = {"mean": float(values.mean()), "sd": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                             "n": len(values), "seeds": seeds, "per_seed": values.tolist(),
                             "ci95": np.quantile(draws, COMPARE_CI_QUANTILES).tolist()}
            differences[label] = pair
    return {"run_a": {"run_id": a, "metrics": data_a}, "run_b": {"run_id": b, "metrics": data_b},
            "filter_metric": metric, "paired": not reasons, "reason": "; ".join(dict.fromkeys(reasons)) or None,
            "difference_direction": "run_b minus run_a", "paired_differences": {} if reasons else differences}


def create_app(runs_dir: str | Path = "runs") -> FastAPI:
    """Create and configure the FastAPI dashboard application.

    Units: none. Shapes: FastAPI instance.
    """
    app = FastAPI(title="FlyOnenomics Dashboard", version="0.1.0")
    app.state.runs_dir = Path(runs_dir).resolve()

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def index() -> FileResponse:
        """Serve the dashboard single page application.

        Units: none. Shapes: HTML FileResponse.
        """
        html_file = static_dir / "index.html"
        if not html_file.is_file():
            raise HTTPException(status_code=404, detail="index.html not found")
        return FileResponse(html_file)

    @app.get("/api/runs")
    def list_runs() -> list[dict[str, Any]]:
        """Return run picker entries merged from index and directory scan.

        Units: none. Shapes: list of run summary objects.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        return list_runs_reconciled(r_dir)

    @app.get("/api/runs/{run_id}/manifest")
    def get_manifest(run_id: str) -> dict[str, Any]:
        """Return run manifest summary JSON.

        Units: none. Shapes: manifest mapping.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        run_path = resolve_run_directory(r_dir, run_id)
        manifest_path = contained(run_path, "manifest.json")
        if not manifest_path.is_file():
            raise HTTPException(status_code=404, detail=f"manifest.json not found for run {run_id}")
        manifest = read_json(manifest_path)
        from flyonenomics.server.mcp_server import validation_summary

        layers = manifest.get("layers", {})
        summary = validation_summary(layers)
        manifest["layer_validation"], manifest["behaviour_component"] = summary
        if manifest.get("behaviour_settings"):
            record = read_yaml(Path(__file__).resolve().parents[3] / "data/behaviour-v0.1.yaml")
            if record.get("qualified") is False and record.get("sign_check", {}).get("flat") is True:
                manifest["phase1_status"] = phase1_status()
        return manifest

    @app.get("/api/runs/{run_id}/experiment")
    def get_experiment(run_id: str) -> dict[str, Any]:
        """Return validated experiment specification JSON.

        Units: none. Shapes: experiment mapping.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        run_path = resolve_run_directory(r_dir, run_id)
        experiment_path = contained(run_path, "experiment.json")
        if not experiment_path.is_file():
            raise HTTPException(status_code=404, detail=f"experiment.json not found for run {run_id}")
        data = read_json(experiment_path)
        experiment = Experiment.model_validate(data)
        data["_dashboard_probes"] = {
            arm.label: [{"index": k, "assay": phase.assay, "label": phase.label}
                        for k, phase in enumerate(arm.expanded()) if isinstance(phase, Probe)]
            for arm in experiment.arms}
        return data

    @app.get("/api/runs/{run_id}/metrics")
    def get_metrics(run_id: str) -> dict[str, Any]:
        """Return run-level metrics JSON with paired differences.

        Units: per metric. Shapes: metrics mapping.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        run_path = resolve_run_directory(r_dir, run_id)
        metrics_path = contained(run_path, "metrics.json")
        if not metrics_path.is_file():
            raise HTTPException(status_code=404, detail=f"metrics.json not found for run {run_id}")
        return read_json(metrics_path)

    @app.get("/api/runs/{run_id}/status")
    def get_status(run_id: str) -> dict[str, Any]:
        """Return run lifecycle status JSON.

        Units: none. Shapes: status mapping.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        run_path = resolve_run_directory(r_dir, run_id)
        status_path = contained(run_path, "status.json")
        if not status_path.is_file():
            raise HTTPException(status_code=404, detail=f"status.json not found for run {run_id}")
        return read_json(status_path)

    @app.get("/api/runs/{run_id}/tables/{arm}/{seed}/{probe}/{table}")
    def get_probe_table(run_id: str, arm: str, seed: str, probe: str, table: str) -> dict[str, Any]:
        """Read typed parquet table as column dictionary with spike cap subsampling.

        Units: ticks/ms/Hz/µM per table schema. Shapes: columns mapping of arrays.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        run_path = resolve_run_directory(r_dir, run_id)
        parquet_file = find_parquet_table(run_path, arm, seed, probe, table)
        if parquet_file is None or not parquet_file.is_file():
            raise HTTPException(status_code=404, detail=f"Table {table} not found for {arm}/{seed}/probe-{probe}")

        return table_payload(run_path, parquet_file, table)

    @app.get("/api/runs/{run_id}/tables/{arm}/{seed}/{table}")
    def get_seed_table(run_id: str, arm: str, seed: str, table: str) -> dict[str, Any]:
        """Read non-probe seed-level parquet table (index or slow-state).

        Units: per schema. Shapes: columns mapping of arrays.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        run_path = resolve_run_directory(r_dir, run_id)
        parquet_file = find_parquet_table(run_path, arm, seed, None, table)
        if parquet_file is None or not parquet_file.is_file():
            raise HTTPException(status_code=404, detail=f"Table {table} not found for {arm}/{seed}")

        return table_payload(run_path, parquet_file, table)

    @app.get("/api/runs/{run_id}/live/{arm}/{seed}/{probe}")
    def get_live_windows(run_id: str, arm: str, seed: str, probe: str) -> dict[str, Any]:
        """Read one probe's flushed live NDJSON windows exactly as recorded.

        WP13 (SPEC item 66): measured values only; no smoothing, no interpolation.
        Units: ticks/ms/counts per live stream schema. Shapes: list of window mappings.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        run_path = resolve_run_directory(r_dir, run_id)
        directory = seed_directory(run_path, arm, seed)
        live_file = contained(run_path, str(directory.relative_to(run_path)), "live", f"probe-{probe_number(probe)}.ndjson")
        windows: list[dict[str, Any]] = []
        malformed = 0
        if live_file.is_file():
            with live_file.open("rb") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        parsed = json.loads(raw)
                    except (ValueError, UnicodeDecodeError):
                        malformed += 1
                        continue
                    if isinstance(parsed, dict):
                        windows.append(parsed)
                    else:
                        malformed += 1
        return {"run_id": run_id, "arm": arm, "seed": seed, "probe": int(probe_number(probe)),
                "windows": windows, "n_windows": len(windows), "malformed_lines": malformed,
                "no_data": len(windows) == 0,
                "note": "Measured live windows as recorded; no smoothing, no interpolation."}

    @app.get("/api/compare")
    def compare_runs(a: str = Query(...), b: str = Query(...), metric: str | None = Query(default=None)) -> dict[str, Any]:
        """Compare two runs by loading their metrics and paired differences.

        Units: per metric. Shapes: comparison mapping.
        """
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))
        path_a = resolve_run_directory(r_dir, a)
        path_b = resolve_run_directory(r_dir, b)

        metrics_a_file = contained(path_a, "metrics.json")
        metrics_b_file = contained(path_b, "metrics.json")
        if not metrics_a_file.is_file():
            raise HTTPException(status_code=404, detail=f"metrics.json not found for run {a}")
        if not metrics_b_file.is_file():
            raise HTTPException(status_code=404, detail=f"metrics.json not found for run {b}")

        data_a = read_json(metrics_a_file)
        data_b = read_json(metrics_b_file)

        exp_a = read_json(contained(path_a, "experiment.json"))
        exp_b = read_json(contained(path_b, "experiment.json"))
        return comparison_payload(a, b, exp_a, exp_b, data_a, data_b, metric)

    @app.websocket("/ws/{run_id}/{arm}/{seed}/{probe}")
    async def websocket_live_stream(websocket: WebSocket, run_id: str, arm: str, seed: str, probe: str) -> None:
        """Tail status.json and probe live NDJSON stream forwarding at most 10 messages/s.

        Units: ticks/ms/Hz/µM per live stream schema. Shapes: streaming JSON messages.
        """
        await websocket.accept()
        r_dir: Path = getattr(app.state, "runs_dir", Path("runs"))

        try:
            run_path = resolve_run_directory(r_dir, run_id)
            directory = seed_directory(run_path, arm, seed)
            live_file = contained(run_path, str(directory.relative_to(run_path)), "live", f"probe-{probe_number(probe)}.ndjson")
            status_file = contained(run_path, "status.json")
        except HTTPException:
            await websocket.close(code=1008)
            return

        min_interval_s = 1.0 / LIVE_FORWARD_HZ
        last_send_time = 0.0
        file_pos = 0
        last_status: dict[str, Any] | None = None

        async def send(message: dict[str, Any]) -> None:
            nonlocal last_send_time
            await asyncio.sleep(max(0.0, min_interval_s - (time.monotonic() - last_send_time)))
            await websocket.send_json(message)
            last_send_time = time.monotonic()

        async def disconnected() -> None:
            while (await websocket.receive())["type"] != "websocket.disconnect":
                pass

        disconnect = asyncio.create_task(disconnected())
        try:
            while not disconnect.done():
                # Recheck containment on each poll, including files created later.
                contained(run_path, str(live_file.relative_to(run_path)))
                contained(run_path, "status.json")
                status: dict[str, Any] = {}
                try:
                    status = read_json(status_file)
                except (OSError, ValueError):
                    status = last_status or {}
                if not status and (run_path / "manifest.json").is_file():
                    status = read_json(contained(run_path, "manifest.json"))

                item: dict[str, Any] | None = None
                partial = False
                if live_file.is_file():
                    with live_file.open("rb") as handle:
                        handle.seek(file_pos)
                        raw = handle.readline()
                        if raw.endswith(b"\n"):
                            file_pos = handle.tell()
                            try:
                                parsed = json.loads(raw)
                                if isinstance(parsed, dict):
                                    item = parsed
                            except (ValueError, UnicodeDecodeError):
                                pass
                        else:
                            # Never consume an incomplete append: retry after newline.
                            partial = bool(raw)

                if item is not None:
                    await send({**item, "type": "live", "line": item, "status": status})
                    last_status = status
                    continue

                state = status.get("state")
                if state in ("done", "failed", "cancelled"):
                    pending = live_file.is_file() and live_file.stat().st_size > file_pos
                    if not pending or partial:
                        await send({"type": "final", "state": state, "status": status,
                                    "truncated_line": partial,
                                    "message": f"Run finished with state {state}"})
                        await websocket.close()
                        break
                elif status != last_status:
                    await send({"type": "status", "status": status})
                    last_status = status

                # Also pause after malformed lines; an idle/disconnected client
                # must not leave a busy loop or an orphaned tail task.
                await asyncio.wait({disconnect}, timeout=LIVE_POLL_INTERVAL_S)
        except (WebSocketDisconnect, OSError, HTTPException):
            if not disconnect.done():
                await websocket.close(code=1008)
        finally:
            disconnect.cancel()
            await asyncio.gather(disconnect, return_exceptions=True)

    return app


app = create_app()


def main() -> None:
    """Entry point for flyonenomics-dash CLI.

    Units: none. Shapes: none.
    """
    parser = argparse.ArgumentParser(description="FlyOnenomics Dashboard server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"), help="Path to runs directory")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host IP to bind to")
    args = parser.parse_args()

    import uvicorn

    server_app = create_app(runs_dir=args.runs_dir)
    uvicorn.run(server_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
