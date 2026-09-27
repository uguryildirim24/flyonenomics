"""Unit and acceptance tests for the FlyOnenomics Dashboard (WP8).

Tests all endpoints, panel rendering against real and synthetic fixtures,
picker lifecycle states, WebSocket live streaming with 10 Hz rate limit cap,
subsampled raster spike cap, and 10-seed load time under 5 seconds.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from flyonenomics.dashboard.app import (
    CODEX_BASE_URL,
    DA_REF,
    DEFAULT_PORT,
    LIVE_FORWARD_HZ,
    LIVE_POLL_INTERVAL_S,
    PAGE_SIZE,
    SPIKE_CAP,
    create_app,
)
from flyonenomics.schema.experiment import Record
from flyonenomics.store.index import validate_run
from flyonenomics.store.results import atomic_json, table_schemas, write_table


@pytest.fixture
def fixtures_dir() -> Path:
    """Return repository tests/fixtures directory path.

    Units: none. Shapes: Path.
    """
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixture_client(fixtures_dir: Path) -> TestClient:
    """Provide TestClient pointed at tests/fixtures.

    Units: none. Shapes: TestClient.
    """
    app = create_app(runs_dir=fixtures_dir)
    return TestClient(app)


def test_constants_and_scientific_values() -> None:
    """Verify module-level constants match WP8 brief and SPEC definitions.

    Units: none / Hz / ms / µM. Shapes: scalars.
    """
    assert SPIKE_CAP == 20_000
    assert LIVE_FORWARD_HZ == 10.0
    assert LIVE_POLL_INTERVAL_S == 0.05
    assert PAGE_SIZE == 50
    assert DEFAULT_PORT == 8765
    assert CODEX_BASE_URL == "https://codex.flywire.ai/app/cell_details?root_id="
    assert DA_REF == 0.02


def test_html_page_references_every_panel_container(fixture_client: TestClient) -> None:
    """Verify GET / returns 200 and references every panel container.

    Units: none. Shapes: HTML document text.
    """
    response = fixture_client.get("/")
    assert response.status_code == 200
    html = response.text

    # Panel containers named in WP8 brief
    expected_containers = [
        'id="runs-picker"',
        'id="manifest-panel"',
        'id="raster-panel"',
        'id="rates-panel"',
        'id="dopamine-panel"',
        'id="arena-panel"',
        'id="metrics-panel"',
        'id="compare-panel"',
        'id="live-panel"',
        'id="codex-link-box"',
    ]
    for container in expected_containers:
        assert container in html, f"Missing expected panel container: {container}"

    # Codex link pattern
    assert CODEX_BASE_URL in html or "codex.flywire.ai" in html
    # 3D viewer rule: No 3D viewer in Phase 1
    assert "No 3D Viewer in Phase 1" in html


def test_run_fixture_validation_and_size(fixtures_dir: Path) -> None:
    """Verify committed run-fixture passes validate_run and is under 3 MB.

    Units: bytes. Shapes: single directory.
    """
    run_path = fixtures_dir / "run-fixture"
    assert run_path.is_dir(), f"run-fixture missing: {run_path}"

    errors = validate_run(run_path)
    assert errors == [], f"validate_run failed on run-fixture: {errors}"

    total_bytes = sum(f.stat().st_size for f in run_path.rglob("*") if f.is_file())
    max_bytes = 3 * 1024 * 1024  # 3 MB cap from WP8 brief
    assert total_bytes < max_bytes, f"run-fixture size {total_bytes} bytes exceeds 3 MB"


def test_fixture_api_routes(fixture_client: TestClient) -> None:
    """Verify all JSON API endpoints return 200 with documented shape on run-fixture.

    Units: none / ms / Hz / µM. Shapes: JSON mappings.
    """
    # 1. /api/runs
    res_runs = fixture_client.get("/api/runs")
    assert res_runs.status_code == 200
    runs_list = res_runs.json()
    fixture_entries = [r for r in runs_list if r["run_id"] == "run-fixture"]
    assert len(fixture_entries) == 1
    f_entry = fixture_entries[0]
    assert f_entry["state"] == "done"
    assert "wild-type" in f_entry["arms"]
    assert f_entry["seeds"] == [1]

    # 2. /api/runs/{run_id}/manifest
    res_man = fixture_client.get("/api/runs/run-fixture/manifest")
    assert res_man.status_code == 200
    man = res_man.json()
    assert man["versions"]["connectome_version"] == "783"
    assert "layers" in man
    assert "free_parameters" in man

    # 3. /api/runs/{run_id}/experiment
    res_exp = fixture_client.get("/api/runs/run-fixture/experiment")
    assert res_exp.status_code == 200
    exp = res_exp.json()
    assert exp["schema_version"] == "1.2"
    assert len(exp["arms"]) == 2

    # 4. /api/runs/{run_id}/metrics
    res_met = fixture_client.get("/api/runs/run-fixture/metrics")
    assert res_met.status_code == 200
    met = res_met.json()
    assert "arms" in met
    assert "paired_differences" in met

    # 5. /api/runs/{run_id}/status
    res_st = fixture_client.get("/api/runs/run-fixture/status")
    assert res_st.status_code == 200
    assert res_st.json()["state"] == "done"

    # 6. Tables - spikes
    res_spk = fixture_client.get("/api/runs/run-fixture/tables/wild-type/1/0/spikes")
    assert res_spk.status_code == 200
    spk_data = res_spk.json()
    assert spk_data["table"] == "spikes"
    assert "idx" in spk_data["columns"]
    assert "t_ms" in spk_data["columns"]
    assert "subsampled" in spk_data
    assert "subsampling_stated" in spk_data
    assert spk_data["da_ref"] == DA_REF

    # 7. Tables - rates
    res_rates = fixture_client.get("/api/runs/run-fixture/tables/wild-type/1/0/rates")
    assert res_rates.status_code == 200
    rates_data = res_rates.json()
    assert "t_ms" in rates_data["columns"]
    assert "sugar_GRN_R" in rates_data["columns"]
    assert "MN9" in rates_data["columns"]

    # 8. Tables - popcount-1ms
    res_pop = fixture_client.get("/api/runs/run-fixture/tables/wild-type/1/0/popcount-1ms")
    assert res_pop.status_code == 200
    assert "tick" in res_pop.json()["columns"]
    assert "count" in res_pop.json()["columns"]

    # 9. Tables - dopamine from the regenerated active-layer fixture
    res_da = fixture_client.get("/api/runs/run-fixture/tables/wild-type/1/0/dopamine")
    assert res_da.status_code == 200
    assert res_da.json()["total_rows"] > 0
    assert res_da.json()["da_ref"] == DA_REF

    # 10. Tables - receptors from the regenerated active-layer fixture
    res_rec = fixture_client.get("/api/runs/run-fixture/tables/wild-type/1/0/receptors")
    assert res_rec.status_code == 200
    assert res_rec.json()["total_rows"] > 0

    # 11. Tables - arena
    res_arena = fixture_client.get("/api/runs/run-fixture/tables/wild-type/1/0/arena")
    assert res_arena.status_code == 200
    assert "x" in res_arena.json()["columns"]
    assert "y" in res_arena.json()["columns"]
    assert "h" in res_arena.json()["columns"]

    # 12. Non-probe table - index
    res_idx = fixture_client.get("/api/runs/run-fixture/tables/wild-type/1/index")
    assert res_idx.status_code == 200
    assert "idx" in res_idx.json()["columns"]
    assert "root_id" in res_idx.json()["columns"]

    # 13. Compare route
    res_cmp = fixture_client.get("/api/compare?a=run-fixture&b=run-fixture")
    assert res_cmp.status_code == 200
    cmp_data = res_cmp.json()
    assert cmp_data["run_a"]["run_id"] == "run-fixture"
    assert cmp_data["run_b"]["run_id"] == "run-fixture"
    assert "paired_differences" in cmp_data

    # Error handling
    assert fixture_client.get("/api/runs/nonexistent/manifest").status_code == 404
    assert fixture_client.get("/api/runs/run-fixture/tables/wild-type/1/0/unknown_table").status_code == 404
    assert fixture_client.get("/api/compare?a=nonexistent&b=run-fixture").status_code == 404


def test_picker_states(fixtures_dir: Path) -> None:
    """Verify run picker correctly reconciles all run lifecycle states.

    Tests queued, running-dead (reported as incomplete), running-live,
    failed, cancelled, and incomplete per section 3.8.
    Units: none. Shapes: list of run mappings.
    """
    states_dir = fixtures_dir / "run-states"
    assert states_dir.is_dir(), f"run-states missing: {states_dir}"

    app = create_app(runs_dir=states_dir)
    client = TestClient(app)

    res = client.get("/api/runs")
    assert res.status_code == 200
    runs = {r["run_id"]: r["state"] for r in res.json()}

    assert runs.get("queued") == "incomplete"
    assert runs.get("running-dead") == "incomplete", "Dead-PID running run must be reported as incomplete"
    assert runs.get("running-live") == "running", "Live-PID running run must stay running"
    assert runs.get("failed") == "incomplete"
    assert runs.get("cancelled") == "incomplete"
    assert runs.get("incomplete") == "incomplete"


def test_live_websocket_and_rate_cap(fixtures_dir: Path) -> None:
    """Verify WebSocket live streaming order, closing message, and 10 Hz rate limit cap.

    Units: seconds / Hz. Shapes: streaming JSON messages.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        run_id = "test-live-run"
        target_dir = tmp_dir / run_id
        shutil.copytree(fixtures_dir / "run-fixture", target_dir)

        # Mark running initially
        status_file = target_dir / "status.json"
        status_file.write_text(json.dumps({"state": "running", "pid": os.getpid()}))

        # Reset probe-0 live ndjson
        live_dir = target_dir / "arm-wild-type" / "seed-1" / "live"
        live_dir.mkdir(parents=True, exist_ok=True)
        live_file = live_dir / "probe-0.ndjson"
        live_file.write_text("")

        app = create_app(runs_dir=tmp_dir)
        client = TestClient(app)

        with client.websocket_connect(f"/ws/{run_id}/wild-type/1/0") as ws:
            # 1. Append three lines and rewrite status
            lines_data = [
                {"tick": 100, "t_ms": 10.0, "counts": {"MN9": 1}, "spikes": [[0, 100]], "da": [0.02], "arena": {"x": 0.0}},
                {"tick": 200, "t_ms": 20.0, "counts": {"MN9": 2}, "spikes": [[0, 200]], "da": [0.02], "arena": {"x": 0.1}},
                {"tick": 300, "t_ms": 30.0, "counts": {"MN9": 3}, "spikes": [[0, 300]], "da": [0.02], "arena": {"x": 0.2}},
            ]
            with live_file.open("a") as handle:
                for line in lines_data:
                    handle.write(json.dumps(line) + "\n")
                    handle.flush()

            status_file.write_text(json.dumps({"state": "running", "step": "in_probe"}))

            # Receive 3 lines in order
            for expected in lines_data:
                msg = ws.receive_json()
                while msg["type"] == "status":
                    msg = ws.receive_json()
                assert msg["tick"] == expected["tick"]
                assert msg["counts"] == expected["counts"]

            # 2. Burst of 50 appended lines: confirm forwarding rate cap <= 10 messages/s
            burst_count = 50
            with live_file.open("a") as handle:
                for i in range(burst_count):
                    burst_line = {"tick": 400 + i * 10, "t_ms": 40.0 + i, "counts": {}, "spikes": []}
                    handle.write(json.dumps(burst_line) + "\n")
                    handle.flush()

            arrival_times: list[float] = []
            for _ in range(burst_count):
                msg = ws.receive_json()
                arrival_times.append(time.monotonic())
                assert "tick" in msg

            burst_duration = arrival_times[-1] - arrival_times[0]
            measured_rate = (burst_count - 1) / burst_duration
            print(f"\n[MEASUREMENT] Live burst rate: {measured_rate:.2f} msg/s over {burst_duration:.3f} s")
            # Assert rate is at most 10 messages per second (allow 5% timing tolerance on OS scheduler)
            assert measured_rate <= LIVE_FORWARD_HZ, f"Burst rate {measured_rate:.2f} msg/s exceeded 10 Hz cap"
            assert burst_duration >= (burst_count - 1) / LIVE_FORWARD_HZ, f"Burst duration {burst_duration:.3f} s too fast"

            # 3. Mark status done and receive closing message
            status_file.write_text(json.dumps({"state": "done"}))
            closing_msg = ws.receive_json()
            assert closing_msg["type"] == "final"
            assert closing_msg["state"] == "done"
            assert ws.receive()["type"] == "websocket.close"

    finally:
        shutil.rmtree(tmp_dir)


def test_synthetic_ten_seed_load_time(monkeypatch: pytest.MonkeyPatch, fixtures_dir: Path) -> None:
    """Verify synthetic 10-seed 2-arm 2-probe run loads all key panels in under 5 s.

    Builds 20 s probes with 20,000 popcount rows and 200,000 spikes rows per probe,
    fetches manifest, metrics, rates, subsampled raster, and compare view.
    Units: seconds. Shapes: scalars and response arrays.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        run_id = "synthetic-10seed"
        run_dir = tmp_dir / run_id
        run_dir.mkdir(parents=True)

        manifest = {
            "connectome_version": "783",
            "layers": {"background": False, "dopamine_A": True, "transporter_C": True},
            "free_parameters": {"pk.kappa": 0.01, "lif.w_syn": 0.275},
            "artefact_results": [],
            "slow_state": "analytical clearance",
            "unsettled_reports": [],
            "validation_entries": [{"test_id": "3.1", "binding": "valid", "identity_hash": "a1b2c3d4e5f6"}],
            "compartments": ["compartment_1", "compartment_2"],
            "state": "done",
            "created": "2026-09-13T00:00:00Z",
            "dt_ms": 0.1,
        }
        atomic_json(run_dir / "manifest.json", manifest)
        experiment = json.loads((fixtures_dir / "run-fixture/experiment.json").read_text())
        experiment["seeds"] = list(range(1, 11))
        for arm in experiment["arms"]:
            for probe in arm["protocol"]:
                probe["duration_s"] = 20.0
        atomic_json(run_dir / "experiment.json", experiment)
        atomic_json(run_dir / "status.json", {"state": "done"})
        # Match the real store's run-level metric shape, including per-seed rows.
        metric_key = "probe-0.MN9.mean_rate_hz"
        metrics = {"arms": {arm: {
            "summary": {metric_key: {"mean": 75., "sd": 0., "n": 10}},
            "per_seed": [{"seed": seed, metric_key: 75.} for seed in range(1, 11)]}
            for arm in ("wild-type", "mn9-threshold")}, "paired_differences": {}}
        atomic_json(run_dir / "metrics.json", metrics)
        rng = np.random.default_rng(20260913)  # Synthetic fixture RNG, no experiment stream.

        schemas = table_schemas(Record(spikes=["sugar_GRN_R", "MN9"], rates=["sugar_GRN_R", "MN9"]), ["compartment_1", "compartment_2"])

        for arm in ["wild-type", "mn9-threshold"]:
            for seed in range(1, 11):
                sdir = run_dir / f"arm-{arm}" / f"seed-{seed}"
                sdir.mkdir(parents=True)
                write_table(
                    sdir / "index.parquet",
                    schemas["index"],
                    {"idx": np.arange(500, dtype=np.int32), "root_id": np.arange(500, dtype=np.int64)},
                )
                for probe in (0, 1):
                    # 20,000 popcount rows per probe
                    write_table(
                        sdir / f"probe-{probe}-popcount-1ms.parquet",
                        schemas["popcount-1ms"],
                        {"tick": np.arange(20000, dtype=np.int64) * 10, "count": np.zeros(20000, dtype=np.int32)},
                    )
                    # 200,000 spikes rows per probe; both clocks refer to the same events.
                    ticks = np.sort(rng.integers(0, 200000, size=200000, dtype=np.int64))
                    write_table(
                        sdir / f"probe-{probe}-spikes.parquet",
                        schemas["spikes"],
                        {
                            "idx": rng.integers(0, 500, size=200000, dtype=np.int32),
                            "tick": ticks,
                            "t_ms": (ticks * manifest["dt_ms"]).astype(np.float32),
                        },
                    )
                    # rates
                    write_table(
                        sdir / f"probe-{probe}-rates.parquet",
                        schemas["rates"],
                        {
                            "tick": np.arange(400, dtype=np.int64) * 500,
                            "t_ms": np.arange(400, dtype=np.float32) * 50.0,
                            "sugar_GRN_R": np.ones(400, dtype=np.float64) * 150.0,
                            "MN9": np.ones(400, dtype=np.float64) * 75.0,
                        },
                    )
                    write_table(sdir / f"probe-{probe}-dopamine.parquet", schemas["dopamine"], [])
                    write_table(sdir / f"probe-{probe}-receptors.parquet", schemas["receptors"], [])
                    write_table(sdir / f"probe-{probe}-drug.parquet", schemas["drug"], [])
                    write_table(sdir / f"probe-{probe}-arena.parquet", schemas["arena"], [])

        import pyarrow.parquet as pq
        from flyonenomics.dashboard import app as dashboard_app
        spike_paths = list(run_dir.glob("arm-*/seed-*/probe-*-spikes.parquet"))
        assert len(spike_paths) == 40
        assert sum(pq.read_metadata(path).num_rows for path in spike_paths) == 8_000_000
        assert all(pq.read_metadata(path).num_rows == 20000 for path in run_dir.glob("arm-*/seed-*/probe-*-popcount-1ms.parquet"))
        read_paths: list[Path] = []
        original_read = pq.read_table
        def observed_read(path: Path, **kwargs: Any) -> Any:
            read_paths.append(Path(path))
            return original_read(path, **kwargs)
        monkeypatch.setattr(dashboard_app.pq, "read_table", observed_read)

        app = create_app(runs_dir=tmp_dir)
        client = TestClient(app)

        t_start = time.perf_counter()
        r_man = client.get(f"/api/runs/{run_id}/manifest")
        assert r_man.status_code == 200
        r_met = client.get(f"/api/runs/{run_id}/metrics")
        assert r_met.status_code == 200
        r_rat = client.get(f"/api/runs/{run_id}/tables/wild-type/1/0/rates")
        assert r_rat.status_code == 200
        r_spk = client.get(f"/api/runs/{run_id}/tables/wild-type/1/0/spikes")
        assert r_spk.status_code == 200
        spk_payload = r_spk.json()
        assert spk_payload["subsampled"] is True
        assert spk_payload["returned_rows"] == SPIKE_CAP
        assert spk_payload["total_rows"] == 200000
        assert f"Subsampled {SPIKE_CAP} spikes from 200000 total spikes" in spk_payload["subsampling_stated"]

        r_cmp = client.get(f"/api/compare?a={run_id}&b={run_id}")
        assert r_cmp.status_code == 200
        t_elapsed = time.perf_counter() - t_start
        print(f"\n[MEASUREMENT] Synthetic 10-seed load time: {t_elapsed:.4f} s")

        # This is a warm filesystem-cache measurement after writing, with no
        # application cache. Prove the real parquet reader and expected data ran.
        assert r_rat.json()["returned_rows"] == 400
        assert r_rat.json()["columns"]["MN9"] == [75.] * 400
        assert r_cmp.json()["paired"] is True
        assert all(item["mean"] == 0 for arm in r_cmp.json()["paired_differences"].values() for item in arm.values())
        assert [path.name for path in read_paths] == ["probe-0-rates.parquet", "probe-0-spikes.parquet", "index.parquet"]
        first = spk_payload["columns"]
        assert np.allclose(first["t_ms"], np.array(first["tick"]) * manifest["dt_ms"])
        again = client.get(f"/api/runs/{run_id}/tables/wild-type/1/0/spikes").json()
        assert again == spk_payload
        assert [path.name for path in read_paths].count("probe-0-spikes.parquet") == 2

        # Acceptance threshold: under 5 s
        assert t_elapsed < 5.0, f"Ten-seed load time {t_elapsed:.4f} s exceeded 5 s limit"

    finally:
        shutil.rmtree(tmp_dir)


def test_neuromod_and_arena_synthetic_non_empty_rendering() -> None:
    """Verify non-empty synthetic dopamine, receptor, and arena tables render correctly.

    Units: µM / fractions / mm / rad. Shapes: time series and trajectory arrays.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        run_id = "test-synthetic-tables"
        run_dir = tmp_dir / run_id
        run_dir.mkdir(parents=True)

        atomic_json(run_dir / "manifest.json", {"compartments": ["c1", "c2"], "state": "done"})
        atomic_json(run_dir / "status.json", {"state": "done"})

        sdir = run_dir / "arm-wild-type" / "seed-1"
        sdir.mkdir(parents=True)

        schemas = table_schemas(Record(), ["c1", "c2"])

        # Non-empty dopamine table
        dopamine_rows = {
            "tick": [0, 100, 200],
            "t_ms": [0.0, 10.0, 20.0],
            "c1": [0.02, 0.04, 0.06],
            "c2": [0.015, 0.025, 0.035],
        }
        write_table(sdir / "probe-0-dopamine.parquet", schemas["dopamine"], dopamine_rows)

        # Non-empty receptors table
        receptor_rows = {
            "tick": [0, 100, 200],
            "t_ms": [0.0, 10.0, 20.0],
            "occ_D1_c1": [0.1, 0.2, 0.3],
            "occ_D2_c1": [0.4, 0.5, 0.6],
            "occ_D1_c2": [0.15, 0.25, 0.35],
            "occ_D2_c2": [0.45, 0.55, 0.65],
        }
        write_table(sdir / "probe-0-receptors.parquet", schemas["receptors"], receptor_rows)

        # Non-empty arena table
        arena_rows = {
            "tick": [0, 100, 200],
            "t_ms": [0.0, 10.0, 20.0],
            "x": [0.0, 5.0, 10.0],
            "y": [0.0, 2.0, 4.0],
            "h": [0.0, 0.5, 1.0],
            "omega": [0.0, 0.1, 0.2],
            "r_L": [10.0, 10.0, 10.0],
            "r_R": [10.0, 10.0, 10.0],
            **{f"{k}_{s}": [0.0, 0.0, 0.0] for s in ("A", "B", "distractor") for k in ("az_arena", "az_fly", "width", "contrast")},
        }
        write_table(sdir / "probe-0-arena.parquet", schemas["arena"], arena_rows)

        app = create_app(runs_dir=tmp_dir)
        client = TestClient(app)

        res_da = client.get(f"/api/runs/{run_id}/tables/wild-type/1/0/dopamine")
        assert res_da.status_code == 200
        cols_da = res_da.json()["columns"]
        assert cols_da["c1"] == [0.02, 0.04, 0.06]
        assert res_da.json()["da_ref"] == DA_REF

        res_rec = client.get(f"/api/runs/{run_id}/tables/wild-type/1/0/receptors")
        assert res_rec.status_code == 200
        cols_rec = res_rec.json()["columns"]
        assert cols_rec["occ_D1_c1"] == [0.1, 0.2, 0.3]

        res_ar = client.get(f"/api/runs/{run_id}/tables/wild-type/1/0/arena")
        assert res_ar.status_code == 200
        cols_ar = res_ar.json()["columns"]
        assert cols_ar["x"] == [0.0, 5.0, 10.0]
        assert cols_ar["h"] == [0.0, 0.5, 1.0]

    finally:
        shutil.rmtree(tmp_dir)


@pytest.mark.parametrize("position", range(5))
@pytest.mark.parametrize("value", ["..", "/tmp", "../outside", "%2e%2e", "%2Ftmp", "..%2Foutside", "..%252Foutside"])
def test_table_parameters_contained(tmp_path: Path, position: int, value: str) -> None:
    """Every URL component rejects traversal, including encoded separators."""
    (tmp_path / "safe" / "arm-wild-type" / "seed-1").mkdir(parents=True)
    parts = ["safe", "wild-type", "1", "0", "spikes"]
    parts[position] = value
    run, arm, seed, probe, table = parts
    client = TestClient(create_app(tmp_path))
    response = client.get(f"/api/runs/{run}/tables/{arm}/{seed}/{probe}/{table}")
    assert response.status_code in (400, 404)


@pytest.mark.parametrize("target", ["run", "json", "arm", "seed", "table", "live"])
def test_symlink_containment(tmp_path: Path, target: str) -> None:
    """No route follows run, directory, JSON, parquet or live links out of the root."""
    root, outside = tmp_path / "runs", tmp_path / "outside"
    seed = root / "safe" / "arm-wild-type" / "seed-1"
    seed.mkdir(parents=True)
    outside.mkdir()
    atomic_json(outside / "manifest.json", {"secret": "must not be read"})
    schemas = table_schemas(Record(), [])
    write_table(outside / "probe-0-spikes.parquet", schemas["spikes"], [])
    (outside / "probe-0.ndjson").write_text('{"secret": true}\n')
    client = TestClient(create_app(root))
    url = "/api/runs/safe/tables/wild-type/1/0/spikes"
    if target == "run":
        (root / "escape").symlink_to(outside, target_is_directory=True)
        url = "/api/runs/escape/manifest"
        assert all(r["run_id"] != "escape" for r in client.get("/api/runs").json())
    elif target == "json":
        (root / "safe" / "manifest.json").symlink_to(outside / "manifest.json")
        url = "/api/runs/safe/manifest"
    elif target in ("arm", "seed"):
        link = seed.parent if target == "arm" else seed
        shutil.rmtree(link)
        link.symlink_to(outside, target_is_directory=True)
    elif target == "table":
        (seed / "probe-0-spikes.parquet").symlink_to(outside / "probe-0-spikes.parquet")
    else:
        (seed / "live").symlink_to(outside, target_is_directory=True)
        with client.websocket_connect("/ws/safe/wild-type/1/0") as ws:
            assert ws.receive() == {"type": "websocket.close", "code": 1008, "reason": ""}
        return
    assert client.get(url).status_code == 400


def test_picker_reuses_store_without_writes(fixtures_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use the real rebuild rule; freeze every input byte and mtime including SQLite."""
    from flyonenomics.store.index import RunIndex
    root = tmp_path / "states"
    shutil.copytree(fixtures_dir / "run-states", root)
    # This test owns the current process, which remains alive throughout the request.
    atomic_json(root / "running-live" / "status.json", {"state": "running", "pid": os.getpid()})
    (root / "no-manifest").mkdir()
    shutil.copy(root / "queued" / "experiment.json", root / "no-manifest" / "experiment.json")
    (root / "malformed").mkdir()
    (root / "malformed" / "experiment.json").write_text('{')
    original = RunIndex.rebuild
    called = []
    def rebuild(index: RunIndex) -> list[dict[str, Any]]:
        called.append(True)
        return original(index)
    monkeypatch.setattr(RunIndex, "rebuild", rebuild)
    def snapshot() -> dict[str, tuple[bytes, int]]:
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
    before = snapshot()
    rows = TestClient(create_app(root)).get("/api/runs").json()
    assert called == [True]
    states = {row["run_id"]: row["state"] for row in rows}
    assert states["running-live"] == "running"
    for name in ("queued", "failed", "cancelled", "running-dead", "no-manifest"):
        assert states[name] == "incomplete"
    assert snapshot() == before
    missing = tmp_path / "missing"
    assert TestClient(create_app(missing)).get("/api/runs").json() == []
    assert not missing.exists()


def test_index_lifecycle_rows_are_visible(fixtures_dir: Path, tmp_path: Path) -> None:
    """Rebuild preserves indexed states before experiment.json arrives on disk."""
    from flyonenomics.store.index import RunIndex
    experiment = json.loads((fixtures_dir / "run-fixture" / "experiment.json").read_text())
    index = RunIndex(tmp_path)
    for state in ("queued", "failed", "cancelled"):
        (tmp_path / state).mkdir()
        index.upsert(state, experiment, {"state": state})
    with index._connect() as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    rows = TestClient(create_app(tmp_path)).get("/api/runs").json()
    assert {r["run_id"]: r["state"] for r in rows} == {s: s for s in ("queued", "failed", "cancelled")}


@pytest.mark.parametrize("terminal", ["done", "failed", "cancelled"])
def test_live_status_without_probe_and_partial_append(tmp_path: Path, terminal: str) -> None:
    """Status-only updates arrive before a probe exists; split writes lose no packet."""
    root = tmp_path / "idle"
    root.mkdir()
    atomic_json(root / "status.json", {"state": "running", "pid": os.getpid()})
    client = TestClient(create_app(tmp_path))
    with client.websocket_connect("/ws/idle/wild-type/1/7") as ws:
        assert ws.receive_json()["type"] == "status"
        atomic_json(root / "status.json", {"state": "running", "phase": 7})
        assert ws.receive_json()["status"]["phase"] == 7
        live = root / "arm-wild-type" / "seed-1" / "live" / "probe-7.ndjson"
        live.parent.mkdir(parents=True)
        live.write_text('{"tick":123')
        # Synchronize on a status packet: the reader has polled the partial line.
        atomic_json(root / "status.json", {"state": "running", "phase": 8})
        assert ws.receive_json()["status"]["phase"] == 8
        with live.open("a") as handle:
            handle.write('}\n')
        packet = ws.receive_json()
        assert packet["type"] == "live" and packet["tick"] == 123
        atomic_json(root / "status.json", {"state": terminal})
        assert ws.receive_json()["state"] == terminal
        assert ws.receive()["type"] == "websocket.close"


def test_finished_run_without_live_file_closes(tmp_path: Path) -> None:
    """A terminal run with live disabled has exactly one closing message."""
    root = tmp_path / "finished"
    root.mkdir()
    atomic_json(root / "status.json", {"state": "done"})
    with TestClient(create_app(tmp_path)).websocket_connect("/ws/finished/wild-type/1/99") as ws:
        assert ws.receive_json()["type"] == "final"
        assert ws.receive()["type"] == "websocket.close"


def test_arrow_schema_deterministic_sample_and_exact_roots(tmp_path: Path) -> None:
    """Compare capped rows to Arrow input; clocks are numbers and root IDs lose no bits."""
    seed = tmp_path / "run" / "arm-wild-type" / "seed-1"
    schemas = table_schemas(Record(), [])
    n = SPIKE_CAP + 117
    ticks = np.arange(n, dtype=np.int64)
    write_table(seed / "probe-0-spikes.parquet", schemas["spikes"],
                {"idx": np.zeros(n, dtype=np.int32), "tick": ticks, "t_ms": ticks.astype(np.float32)})
    root = 720575940630000001
    write_table(seed / "index.parquet", schemas["index"], {"idx": [0], "root_id": [root]})
    write_table(seed / "slow-state.parquet", schemas["slow-state"], [])
    client = TestClient(create_app(tmp_path))
    url = "/api/runs/run/tables/wild-type/1/0/spikes"
    data = client.get(url).json()
    assert data == client.get(url).json()
    assert data["columns"]["tick"] == np.linspace(0, n-1, SPIKE_CAP, dtype=np.int64).tolist()
    assert all(type(tick) is int for tick in data["columns"]["tick"])
    assert data["schema"]["tick"] == "int64"
    assert "deterministic evenly spaced" in data["subsampling_stated"]
    assert data["neuron_roots"] == {"0": str(root)}
    index = client.get("/api/runs/run/tables/wild-type/1/index").json()
    assert index["columns"]["root_id"] == [str(root)]
    assert index["schema"]["root_id"] == "int64"
    assert index["json_encodings"] == {"root_id": "decimal string"}
    slow = client.get("/api/runs/run/tables/wild-type/1/slow-state").json()
    assert slow["returned_rows"] == slow["total_rows"] == 0
    assert set(slow["schema"]) == set(schemas["slow-state"])
    assert slow["columns"] == dict.fromkeys(schemas["slow-state"], [])


@pytest.mark.parametrize("table", ["dopamine", "receptors", "drug", "arena"])
def test_empty_table_schema(fixture_client: TestClient, table: str) -> None:
    """Stub emptiness retains every authoritative Arrow field and its dtype."""
    import pyarrow.parquet as pq
    path = Path(__file__).parent / "fixtures/run-fixture/arm-wild-type/seed-1" / f"probe-0-{table}.parquet"
    arrow = pq.read_table(path)
    data = fixture_client.get(f"/api/runs/run-fixture/tables/wild-type/1/0/{table}").json()
    assert data["schema"] == {f.name: str(f.type) for f in arrow.schema}
    assert data["returned_rows"] == len(arrow)
    assert data["columns"] == arrow.to_pydict()


@pytest.mark.parametrize("mismatch,reason", [(None, None), ("seed", "different S"), ("seeds", "different seed lists"), ("arms", "different arms")])
def test_compare_pairing_and_filter(tmp_path: Path, mismatch: str | None, reason: str | None) -> None:
    """Only fully matched runs get B-minus-A paired values and intervals (11.28)."""
    for name, values in (("a", [1., 4.]), ("b", [4., 8.])):
        run = tmp_path / name
        run.mkdir()
        exp = {"seed": 9, "seeds": [2, 7], "arms": [{"label": "control"}]}
        if name == "b" and mismatch:
            exp[mismatch] = {"seed": 10, "seeds": [2, 8], "arms": [{"label": "different"}]}[mismatch]
        label = exp["arms"][0]["label"]
        atomic_json(run / "experiment.json", exp)
        atomic_json(run / "metrics.json", {"arms": {label: {
            "summary": {"m": {"mean": sum(values)/2, "sd": 1., "n": 2}, "other": {"mean": 99.}},
            "per_seed": [{"seed": seed, "m": value, "other": 99.} for seed, value in zip(exp["seeds"], values)]}}})
    client = TestClient(create_app(tmp_path))
    result = client.get("/api/compare?a=a&b=b&metric=m").json()
    assert result["paired"] is (mismatch is None)
    assert result["reason"] == reason
    for run in ("run_a", "run_b"):
        for arm in result[run]["metrics"]["arms"].values():
            assert set(arm["summary"]) == {"m"}
            assert all(set(row) == {"seed", "m"} for row in arm["per_seed"])
    if mismatch:
        assert result["paired_differences"] == {}
        assert '"ci95"' not in json.dumps(result)
    else:
        stats = result["paired_differences"]["control"]["m"]
        assert stats["per_seed"] == [3., 4.]
        assert stats["seeds"] == [2, 7]
        assert stats["mean"] == 3.5
        assert stats["ci95"] == [3., 4.]
        assert client.get("/api/compare?a=a&b=b&metric=m").json() == result
    assert client.get("/api/compare", params={"a": "../outside", "b": "b"}).status_code == 400


# Execute the shipped script with a strict DOM/Canvas double. This complements the
# real-browser review; unlike the worker's API-only synthetic test it runs renderers.
FRONTEND_HARNESS = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert/strict");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const elements = new Map(), calls = [];
class Element {
  constructor(tag = "div") { this.tag = tag; this.children = []; this.style = {}; this.value = ""; this.width = 800; this.height = 400; this.hidden = false; this.text = ""; this.listeners = {}; }
  set innerHTML(value) { this.children = []; this.text = value; }
  get innerHTML() { return this.text; }
  set textContent(value) { this.children = []; this.text = String(value); }
  get textContent() { return this.text + this.children.map(c => c.textContent).join(" "); }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  cloneNode() { const clone = new Element(this.tag); clone.value = this.value; clone.text = this.text; return clone; }
  getContext() { return new Proxy({}, {get: (_, key) => (...args) => calls.push([key, ...args])}); }
}
for (const match of input.html.matchAll(/id="([^"]+)"/g)) elements.set(match[1], new Element());
function get(id) { assert(elements.has(id), `Missing DOM id: ${id}`); return elements.get(id); }
global.document = {
  getElementById: get,
  querySelector(selector) {
    const match = selector.match(/^#([\w-]+) tbody$/);
    assert(match, `Unexpected selector ${selector}`);
    const parent = get(match[1]);
    return parent.tbody ||= new Element("tbody");
  },
  createElement: tag => new Element(tag), addEventListener() {}
};
global.window = { addEventListener() {}, location: { protocol: "http:", host: "localhost" } };
global.fetch = async url => {
  assert(url.startsWith("/api/"), `External request: ${url}`);
  const data = input.routes[url];
  return {ok: data !== undefined, json: async () => data};
};
for (const match of input.script.matchAll(/getElementById\("([^"]+)"\)/g)) get(match[1]);
vm.runInThisContext(input.script + `
(async () => {
  initEventListeners();
  await selectRun("run-fixture");
  assert.equal(document.getElementById("dashboard-error").hidden, true);
  assert(document.getElementById("manifest-layers").textContent.includes("development"));
  assert(document.getElementById("manifest-layers").textContent.includes("Behaviour component:"));
  assert(document.getElementById("manifest-artefacts").textContent.includes("fano: not run"));
  assert(document.querySelector("#manifest-validation tbody").textContent.includes("stale"));
  assert(document.querySelector("#metrics-summary-table tbody").textContent.includes("79.000"));
  assert(document.querySelector("#metrics-diffs-table tbody").textContent.includes("11.000"));
  const links = document.getElementById("codex-links").children;
  assert(links.length > 10);
  assert(links.every(link => link.href.includes("root_id=720")));
  assert.equal(document.getElementById("dopamine-empty").style.display, "none");
  assert.equal(document.getElementById("arena-empty").style.display, "block");

  // Exercise a synthetic nonempty series and the receptor toggle through the
  // actual page function. Alter DA_ref to detect a hidden hard-coded baseline.
  cachedDopamineData = {da_ref: 0.037, columns: {tick:[0,100], t_ms:[0,10], c1:[0.01,0.05]}};
  cachedReceptorsData = {columns:{tick:[0,100], t_ms:[0,10], occ_D1_c1:[0.1,0.2], occ_D2_c1:[0.4,0.5]}};
  renderDopamineOrReceptors();
  assert.equal(document.getElementById("dopamine-chart-wrapper").style.display, "block");
  assert(calls.some(call => call[0] === "fillText" && call[1] === "DA_ref (0.037 µM)"));
  document.getElementById("dopamine-toggle").listeners.click();
  assert(calls.some(call => call[0] === "fillText" && call[1] === "occ_D1_c1"));

  // Zero position is a valid stationary animal; it is empty only for a declared stub.
  currentManifest = {};
  input.routes[probeUrl("arena")] = {arena_radius_mm: 58.5, columns: {x:[0],y:[0],h:[0],az_fly_A:[90],contrast_A:[1]}};
  await loadArenaData();
  assert.equal(document.getElementById("arena-chart-wrapper").style.display, "flex");
  assert(document.getElementById("arena-info").textContent.includes("az_fly=90.000"));
  const lines = calls.filter(call => call[0] === "lineTo");
  assert.deepEqual(lines.at(-1), ["lineTo",400,185]); // heading zero points +y
  input.routes[probeUrl("arena")].columns = {x:[0,10], y:[0,5], h:[0,90]};
  await loadArenaData();
  assert(document.getElementById("arena-info").textContent.includes("Heading: 90.000 deg"));
  const count = calls.length;
  renderSteeringCurve(document.getElementById("arena-canvas"),
    {az_fly_A:[-90,-90,-90,90,90], omega:[999,2,4,999,-3], t_ms:[0,1000,2000,3000,4000]},
    {transition_s:1,dwell_s:2});
  const plotted = calls.slice(count).filter(call => call[0] === "fillRect");
  assert.equal(plotted.length, 2); // transition samples excluded, dwell means plotted

  // A changed selection must not paint late old responses.
  const oldFetch = fetch;
  let release;
  global.fetch = () => new Promise(resolve => { release = resolve; });
  const oldRequest = loadRasterData(probeGeneration);
  ++probeGeneration;
  document.getElementById("raster-subsample-notice").textContent = "new selection";
  release({ok:true,json:async()=>({columns:{idx:[],t_ms:[]}})});
  await oldRequest;
  assert.equal(document.getElementById("raster-subsample-notice").textContent, "new selection");
  global.fetch = oldFetch;

  document.getElementById("compare-run-a").value = "run-fixture";
  document.getElementById("compare-run-b").value = "run-fixture";
  await executeCompare();
  assert(document.getElementById("compare-pairing").textContent.startsWith("Paired:"));
  const cmp = input.routes["/api/compare?a=run-fixture&b=run-fixture"];
  cmp.paired = false; cmp.reason = "different S"; cmp.paired_differences = {};
  await executeCompare();
  assert(document.getElementById("compare-pairing").textContent.includes("Unpaired: different S"));
  assert(document.querySelector("#compare-results tbody").textContent.includes("sd 0.000, n 1; seeds:"));
  assert.equal(document.getElementById("dashboard-error").hidden, true);
  console.log("FRONTEND_RENDER_OK");
})().catch(error => { console.error(error); process.exitCode = 1; });
`, {filename:"dashboard-app.js"});
'''


def test_frontend_executes_fixture_and_synthetic_panels(fixture_client: TestClient) -> None:
    """Execute the actual JS, failing on absent DOM IDs, errors and false empty states."""
    import subprocess
    static = Path(__file__).parents[1] / "src/flyonenomics/dashboard/static"
    routes = {f"/api/runs/run-fixture/{name}": fixture_client.get(f"/api/runs/run-fixture/{name}").json()
              for name in ("manifest", "experiment", "metrics", "status")}
    for table in ("spikes", "rates", "dopamine", "receptors", "arena"):
        path = f"/api/runs/run-fixture/tables/wild-type/1/0/{table}"
        routes[path] = fixture_client.get(path).json()
    path = "/api/compare?a=run-fixture&b=run-fixture"
    routes[path] = fixture_client.get(path).json()
    node = shutil.which("node") or str(Path.home() / ".local/bin/node")
    result = subprocess.run([node, "-e", FRONTEND_HARNESS], input=json.dumps({"html": (static / "index.html").read_text(),
                            "script": (static / "app.js").read_text(), "routes": routes}), text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FRONTEND_RENDER_OK" in result.stdout


def test_probe_indices_follow_expanded_arm_phases(fixtures_dir: Path, tmp_path: Path) -> None:
    """Dose/wait/repeat occupy phase indices; each arm gets its own probe list."""
    experiment = json.loads((fixtures_dir / "run-fixture/experiment.json").read_text())
    probe = experiment["arms"][0]["protocol"][0]
    experiment["arms"][0]["protocol"] = [{"type": "wait", "hours": 1}, probe,
        {"type": "repeat", "n": 2, "spacing_hours": 1, "body": [probe]}]
    experiment["arms"][1]["protocol"] = experiment["arms"][0]["protocol"]
    root = tmp_path / "run"
    root.mkdir()
    atomic_json(root / "experiment.json", experiment)
    payload = TestClient(create_app(tmp_path)).get("/api/runs/run/experiment").json()
    assert [p["index"] for p in payload["_dashboard_probes"]["wild-type"]] == [1, 2, 4]
    assert [p["index"] for p in payload["_dashboard_probes"]["mn9-threshold"]] == [1, 2, 4]


def test_committed_fixture_input_matches_execution(fixtures_dir: Path) -> None:
    """Recovered input reproduces the saved defaults, resolved populations and hash."""
    from flyonenomics.schema import load_experiment
    source = fixtures_dir / "experiments/dashboard-sugar.json"
    fixture = fixtures_dir / "run-fixture"
    assert load_experiment(source).model_dump(mode="json") == load_experiment(fixture / "experiment.json").model_dump(mode="json")
    assert load_experiment(source).protocol_hash() == json.loads((fixture / "manifest.json").read_text())["protocol_hash"]


def test_picker_includes_committed_wal_without_sidecar_writes(fixtures_dir: Path, tmp_path: Path) -> None:
    """Read uncheckpointed index rows, ignoring uncommitted transactions and torn tails."""
    from flyonenomics.store.index import RunIndex
    index = RunIndex(tmp_path)
    connection = index._connect()  # Keep WAL alive, disable automatic checkpoints.
    try:
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        experiment = json.loads((fixtures_dir / "run-fixture/experiment.json").read_text())
        (tmp_path / "queued").mkdir()
        index.upsert("queued", experiment, {"state": "queued"})
        wal = tmp_path / "index.sqlite-wal"
        assert wal.stat().st_size > 32
        # The checkpoint alone demonstrably does not yet contain this row.
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect((tmp_path / "index.sqlite").as_uri() + "?immutable=1", uri=True)) as checkpoint:
            assert checkpoint.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
        connection.execute("BEGIN")
        connection.execute("UPDATE runs SET state='failed' WHERE run_id='queued'")
        def snapshot() -> dict[str, tuple[bytes, int]]:
            return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in tmp_path.iterdir() if p.is_file()}
        before = snapshot()
        client = TestClient(create_app(tmp_path))
        rows = client.get("/api/runs").json()
        assert rows[0]["run_id"] == "queued" and rows[0]["state"] == "queued"
        assert snapshot() == before
        connection.rollback()
        # Save isolated bytes to exercise partial and checksum-invalid trailing frames.
        from flyonenomics.dashboard.index_snapshot import _overlay
        database, journal = (tmp_path / "index.sqlite").read_bytes(), wal.read_bytes()
        with closing(sqlite3.connect(":memory:")) as memory:
            for tail in (b"partial", journal[32:]):
                memory.deserialize(_overlay(database, journal + tail))
                assert memory.execute("SELECT state FROM runs").fetchone()[0] == "queued"
    finally:
        connection.close()


def test_phase1_status_is_the_results_first_line() -> None:
    """SPEC 1.3: the dashboard and docs/phase1-results.md carry the same status line."""
    from pathlib import Path
    from flyonenomics.dashboard.app import PHASE1_STATUS, phase1_status
    results = Path(__file__).resolve().parents[1] / "docs" / "phase1-results.md"
    line = results.read_text(encoding="utf-8").splitlines()[0]
    assert phase1_status() == line
    assert PHASE1_STATUS == line
