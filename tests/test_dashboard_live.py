"""Tests for the WP13 live activity view (SPEC section 3.9, item 66).

The view shows measured values only: the chart data equals the flushed NDJSON
live windows exactly, a constant stream renders flat, a probe without live
data reports "no data", and the existing websocket payload is unchanged.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from flyonenomics.dashboard.app import create_app


@pytest.fixture
def fixtures_dir() -> Path:
    """Return repository tests/fixtures directory path.

    Units: none. Shapes: Path.
    """
    return Path(__file__).resolve().parent / "fixtures"


def read_ndjson(path: Path) -> list[dict]:
    """Parse a live NDJSON file; units per live stream schema, list of windows."""
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def make_run(root: Path, run_id: str = "live-run", arm: str = "wild-type", seed: str = "1") -> Path:
    """Create a minimal run directory with arm/seed layout; units none, one path."""
    directory = root / run_id / f"arm-{arm}" / f"seed-{seed}" / "live"
    directory.mkdir(parents=True)
    (root / run_id / "status.json").write_text(json.dumps({"state": "done"}))
    return directory


def test_live_panel_containers_in_html(fixtures_dir: Path) -> None:
    """Verify the live activity panel and its script are served in the page.

    Units: none. Shapes: HTML document text.
    """
    client = TestClient(create_app(runs_dir=fixtures_dir))
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for container in ('id="live-activity-panel"', 'id="live-activity-chart"',
                      'id="live-activity-raster"', 'id="live-activity-empty"',
                      'id="live-activity-watch-btn"', 'id="live-activity-rate-a"',
                      'id="live-activity-rate-b"', 'id="live-activity-stage-strip"',
                      'id="run-substrate-badge"', "/static/live-activity.js"):
        assert container in html, f"Missing live activity container: {container}"


def test_live_route_matches_ndjson_exactly(fixtures_dir: Path) -> None:
    """Verify the replay route returns the NDJSON windows with no smoothing.

    Units: ticks/ms/counts per live stream schema. Shapes: list of windows.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(fixtures_dir / "run-fixture", tmp_dir / "run-fixture")
        live_file = tmp_dir / "run-fixture" / "arm-wild-type" / "seed-1" / "live" / "probe-0.ndjson"
        expected = read_ndjson(live_file)
        assert expected, "run-fixture probe-0 live stream must not be empty"

        client = TestClient(create_app(runs_dir=tmp_dir))
        response = client.get("/api/runs/run-fixture/live/wild-type/1/0")
        assert response.status_code == 200
        payload = response.json()
        assert payload["no_data"] is False
        assert payload["n_windows"] == len(expected)
        assert payload["malformed_lines"] == 0
        # Measured values only: every field equals the recorded line exactly.
        assert payload["windows"] == expected
        for got, want in zip(payload["windows"], expected):
            assert got["tick"] == want["tick"]
            assert got["t_ms"] == want["t_ms"]
            assert got["counts"] == want["counts"]
            assert got["spikes"] == want["spikes"]
    finally:
        shutil.rmtree(tmp_dir)


def test_live_route_constant_stream_renders_flat() -> None:
    """Verify a constant measured stream comes back constant and renders flat.

    Units: ms / counts. Shapes: list of windows.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        live_dir = make_run(tmp_dir)
        constant = {"sugar_GRN_R": 100, "MN9": 5}
        lines = [{"tick": (i + 1) * 1000, "t_ms": (i + 1) * 100.0, "counts": dict(constant),
                  "spikes": [[7, (i + 1) * 1000]], "da": [0.02], "arena": {"x": 0.0}}
                 for i in range(10)]
        (live_dir / "probe-0.ndjson").write_text("".join(json.dumps(line) + "\n" for line in lines))

        client = TestClient(create_app(runs_dir=tmp_dir))
        payload = client.get("/api/runs/live-run/live/wild-type/1/0").json()
        assert payload["n_windows"] == 10
        counts = [w["counts"] for w in payload["windows"]]
        assert all(c == constant for c in counts), "constant stream must stay constant (flat)"
        totals = [sum(c.values()) for c in counts]
        assert len(set(totals)) == 1, "summed recorded-population count must be flat"
        t_ms = [w["t_ms"] for w in payload["windows"]]
        assert all(b > a for a, b in zip(t_ms, t_ms[1:])), "measured window times must increase"
    finally:
        shutil.rmtree(tmp_dir)


def test_live_route_no_data_for_probe_without_live_file() -> None:
    """Verify a probe without live data reports no_data and empty windows.

    Units: none. Shapes: payload mapping.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        make_run(tmp_dir)  # live directory exists but holds no probe file
        client = TestClient(create_app(runs_dir=tmp_dir))
        payload = client.get("/api/runs/live-run/live/wild-type/1/3").json()
        assert payload == {"run_id": "live-run", "arm": "wild-type", "seed": "1", "probe": 3,
                           "windows": [], "n_windows": 0, "malformed_lines": 0, "no_data": True,
                           "note": "Measured live windows as recorded; no smoothing, no interpolation."}
    finally:
        shutil.rmtree(tmp_dir)


def test_live_route_skips_malformed_lines() -> None:
    """Verify malformed NDJSON lines are skipped and counted, never invented.

    Units: none. Shapes: list of windows.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        live_dir = make_run(tmp_dir)
        good = {"tick": 1000, "t_ms": 100.0, "counts": {"MN9": 2}, "spikes": [], "da": [], "arena": {}}
        (live_dir / "probe-0.ndjson").write_text(
            json.dumps(good) + "\n" + '{"tick": 12' + "\n" + "\n" + json.dumps([1, 2]) + "\n")
        client = TestClient(create_app(runs_dir=tmp_dir))
        payload = client.get("/api/runs/live-run/live/wild-type/1/0").json()
        assert payload["windows"] == [good]
        assert payload["malformed_lines"] == 2
        assert payload["no_data"] is False
    finally:
        shutil.rmtree(tmp_dir)


def test_live_route_rejects_path_traversal(fixtures_dir: Path) -> None:
    """Verify the replay route keeps the existing component validation.

    Units: none. Shapes: HTTP status codes.
    """
    client = TestClient(create_app(runs_dir=fixtures_dir))
    assert client.get("/api/runs/run-fixture/live/wild-type/1/abc").status_code == 400
    # Encoded slash is rejected at the router (404) or by component validation (400).
    assert client.get("/api/runs/run-fixture/live/wild%2Ftype/1/0").status_code in (400, 404)
    assert client.get("/api/runs/no-such-run/live/wild-type/1/0").status_code == 404


def test_websocket_payload_unchanged_for_finished_run(fixtures_dir: Path) -> None:
    """Verify the existing websocket route still replays the recorded payload.

    Units: ticks/ms/counts per live stream schema. Shapes: streaming messages.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(fixtures_dir / "run-fixture", tmp_dir / "run-fixture")
        (tmp_dir / "run-fixture" / "status.json").write_text(json.dumps({"state": "done"}))
        live_file = tmp_dir / "run-fixture" / "arm-wild-type" / "seed-1" / "live" / "probe-0.ndjson"
        expected = read_ndjson(live_file)

        client = TestClient(create_app(runs_dir=tmp_dir))
        received: list[dict] = []
        with client.websocket_connect("/ws/run-fixture/wild-type/1/0") as ws:
            while True:
                msg = ws.receive_json()
                if msg["type"] == "final":
                    assert msg["state"] == "done"
                    break
                if msg["type"] == "status":
                    continue
                assert msg["type"] == "live"
                assert "line" in msg and "status" in msg, "existing payload shape must be kept"
                received.append(msg["line"])
        assert received == expected, "websocket replay must equal the NDJSON windows"
    finally:
        shutil.rmtree(tmp_dir)


LIVE_HARNESS = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert/strict");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const elements = new Map(), charts = [], fills = [];
class Element {
  constructor() { this.style = {}; this.width = 900; this.height = 200; this.text = ""; this.children = []; this.listeners = {}; this.clientWidth = 900; }
  set innerHTML(v) { this.text = v; } get innerHTML() { return this.text; }
  set textContent(v) { this.text = String(v); } get textContent() { return this.text; }
  addEventListener(name, cb) { this.listeners[name] = cb; }
  appendChild(child) { this.children.push(child); return child; }
  getContext() { return new Proxy({}, {get: (_, key) => (...args) => { if (key === "fillRect") fills.push(args); }}); }
}
for (const m of input.html.matchAll(/id="([^"]+)"/g)) elements.set(m[1], new Element());
global.document = { getElementById: id => { assert(elements.has(id), id); return elements.get(id); },
  createElement: () => new Element(),
  addEventListener(name, cb) { if (name === "DOMContentLoaded") cb(); } };
global.window = { location: { protocol: "http:", host: "localhost" } };
global.uPlot = class { constructor(opts, data) { this.opts = opts; this.data = data; charts.push(this); }
  setData(data) { this.data = data; } setSize() {} destroy() { this.destroyed = true; } };
global.currentRunId = "run"; global.currentArm = "wild-type"; global.currentSeed = 1; global.currentProbe = 0;
global.currentManifest = input.manifest;
let payload = null;
global.fetch = async url => { assert.equal(url, "/api/runs/run/live/wild-type/1/0"); return {ok: true, json: async () => payload}; };
vm.runInThisContext(input.script);
(async () => {
  const out = {};
  for (const [name, windows] of Object.entries(input.cases)) {
    payload = {windows};
    fills.length = 0;
    await window.liveActivityRefresh();
    const chart = charts.filter(c => !c.destroyed).at(-1);
    out[name] = {data: chart ? chart.data : null, labels: chart ? chart.opts.series.map(s => s.label) : null,
                 empty: document.getElementById("live-activity-empty").style.display,
                 raster: document.getElementById("live-activity-raster-wrapper").style.display, points: fills.length,
                 rateA: document.getElementById("live-activity-rate-a").value,
                 rateB: document.getElementById("live-activity-rate-b").value,
                 stage: document.getElementById("live-activity-stage-strip").style.display};
  }
  process.stdout.write(JSON.stringify(out));
})().catch(error => { console.error(error); process.exit(1); });
'''


def test_live_chart_series_equal_measured_windows(fixtures_dir: Path) -> None:
    """Run live-activity.js under node: version 1 series are the NDJSON values under the partial labels.

    SPEC-P2 section 7: a stream without live_version 2 keeps its chart, labelled
    "sum over recorded populations (may overlap, not whole-network)" for the
    count series and "spikes per second, aggregate" for the rates — never
    "whole-network" or per-neuron Hz. The first window starts at recording
    tick 0; a zero-length window gets no rate rather than an invented duration.
    Units: ms, counts per window, spikes per second. Shapes: one array per series.
    """
    import subprocess
    static = Path(__file__).resolve().parents[1] / "src/flyonenomics/dashboard/static"
    recorded = read_ndjson(fixtures_dir / "run-fixture" / "arm-wild-type" / "seed-1" / "live" / "probe-0.ndjson")
    irregular = [{"tick": 500, "t_ms": 50.0, "counts": {"DAN": 10, "CX_DAN": 3}, "spikes": [[4, 7]]},
                 {"tick": 1500, "t_ms": 150.0, "counts": {"DAN": 20, "CX_DAN": 0}, "spikes": []},
                 {"tick": 1500, "t_ms": 150.0, "counts": {"DAN": 5, "CX_DAN": 1}, "spikes": []},
                 {"tick": 1750, "t_ms": 175.0, "counts": {"DAN": 2, "CX_DAN": 2}, "spikes": [[9, 1700]]}]
    constant = [{"tick": (i + 1) * 1000, "t_ms": (i + 1) * 100.0, "counts": {"DAN": 7, "CX_DAN": 2}, "spikes": []}
                for i in range(6)]
    sizes = {"DAN": 331, "CX_DAN": 30}
    manifest = {"resolved_populations": {name: list(range(n)) for name, n in sizes.items()}}
    node = shutil.which("node") or str(Path.home() / ".local/bin/node")
    completed = subprocess.run([node, "-e", LIVE_HARNESS], capture_output=True, text=True, timeout=60,
                               input=json.dumps({"html": (static / "index.html").read_text(),
                                                 "script": (static / "live-activity.js").read_text(),
                                                 "manifest": manifest,
                                                 "cases": {"recorded": recorded, "irregular": irregular,
                                                           "constant": constant, "empty": []}}))
    assert completed.returncode == 0, completed.stderr
    out = json.loads(completed.stdout)

    got = out["recorded"]
    assert got["data"][0] == [w["t_ms"] for w in recorded]
    assert got["data"][1] == [sum(w["counts"].values()) for w in recorded]
    assert got["labels"][1] == "sum over recorded populations (may overlap, not whole-network)"
    assert all(label.endswith("spikes per second, aggregate") for label in got["labels"][2:])
    assert "whole-network" not in " ".join(got["labels"][2:]) and "per neuron" not in " ".join(got["labels"][2:])
    assert got["raster"] == "block" and 0 < got["points"] <= sum(len(w["spikes"]) for w in recorded)
    assert got["stage"] == "none"  # No blocks in a version 1 stream.

    got = out["irregular"]
    assert got["data"][0] == [50.0, 150.0, 150.0, 175.0]
    assert got["data"][1] == [13, 20, 6, 4]
    assert got["rateA"] == "DAN" and got["rateB"] == "CX_DAN"  # Picker defaults.
    assert got["labels"][2:] == ["DAN spikes per second, aggregate", "CX_DAN spikes per second, aggregate"]
    deltas_s = [0.05, 0.1, None, 0.025]
    for series, pop in zip(got["data"][2:], ("DAN", "CX_DAN")):
        assert series[2] is None
        expected = [w["counts"][pop] / d for w, d in zip(irregular, deltas_s) if d is not None]
        assert [value for value in series if value is not None] == pytest.approx(expected)
    assert got["points"] == 2

    got = out["constant"]
    assert len(set(got["data"][1])) == 1
    assert all(len(set(series)) == 1 for series in got["data"][2:])

    got = out["empty"]
    assert got["data"] is None and got["empty"] == "block" and got["raster"] == "none"
