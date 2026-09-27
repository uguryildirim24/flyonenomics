"""Tests for the WP23 live view contract and additions (SPEC-P2 section 7, SPEC items 66 and 75).

A version 2 stream charts the whole-network `all_count` per window and
per-neuron Hz rates from the stream's own `sizes` and `window_ms`, carries the
open-loop `block`/`stimulus` labels into a stage strip and shows the substrate
label in the run header.
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


def make_run(root: Path, run_id: str = "live-run", arm: str = "wild-type", seed: str = "1") -> Path:
    """Create a minimal run directory with arm/seed layout; units none, one path."""
    directory = root / run_id / f"arm-{arm}" / f"seed-{seed}" / "live"
    directory.mkdir(parents=True)
    (root / run_id / "status.json").write_text(json.dumps({"state": "done"}))
    return directory


def v2_window(tick: int, t_ms: float, window_ms: float, counts: dict[str, int], all_count: int,
              sizes: dict[str, int], block: int | None = None, stimulus: str | None = None,
              spikes: list | None = None) -> dict:
    """Build one live_version 2 window line; units ticks/ms/counts per live stream schema."""
    return {"live_version": 2, "tick": tick, "t_ms": t_ms, "window_ms": window_ms,
            "counts": counts, "all_count": all_count, "sizes": sizes,
            "block": block, "stimulus": stimulus, "spikes": spikes or [], "da": [], "arena": {}}


def test_live_route_passes_version2_windows_through_exactly() -> None:
    """Verify the replay route returns version 2 windows with every additive field intact.

    Units: ticks/ms/counts per live stream schema. Shapes: list of windows.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        live_dir = make_run(tmp_dir)
        sizes = {"lamina": 100, "central_complex": 40}
        lines = [v2_window(1000, 100.0, 100.0, {"lamina": 50, "central_complex": 8}, 500, sizes, 0, "ambient"),
                 v2_window(2000, 200.0, 100.0, {"lamina": 70, "central_complex": 9}, 520, sizes, 1, "stripe"),
                 v2_window(2500, 250.0, 50.0, {"lamina": 30, "central_complex": 4}, 240, sizes, 1, "stripe")]
        (live_dir / "probe-0.ndjson").write_text("".join(json.dumps(line) + "\n" for line in lines))
        client = TestClient(create_app(runs_dir=tmp_dir))
        payload = client.get("/api/runs/live-run/live/wild-type/1/0").json()
        assert payload["windows"] == lines
        assert payload["n_windows"] == 3 and payload["malformed_lines"] == 0
    finally:
        shutil.rmtree(tmp_dir)


V2_HARNESS = r'''
const fs = require("fs"), vm = require("vm"), assert = require("assert/strict");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const elements = new Map(), charts = [], fills = [];
class Element {
  constructor() { this.style = {}; this.width = 900; this.height = 200; this.text = ""; this.children = []; this.listeners = {}; this.clientWidth = 900; }
  set innerHTML(v) { this.text = v; this.children = []; } get innerHTML() { return this.text; }
  set textContent(v) { this.text = String(v); } get textContent() { return this.text; }
  addEventListener(name, cb) { this.listeners[name] = cb; }
  appendChild(child) { this.children.push(child); return child; }
  getContext() { return new Proxy({}, {get: (_, key) => (...args) => { if (key === "fillRect") fills.push(args); }}); }
}
for (const m of input.html.matchAll(/id="([^"]+)"/g)) elements.set(m[1], new Element());
const domReady = [];
global.document = { getElementById: id => { assert(elements.has(id), id); return elements.get(id); },
  createElement: () => new Element(),
  addEventListener: (name, cb) => { if (name === "DOMContentLoaded") domReady.push(cb); } };
global.window = { location: { protocol: "http:", host: "localhost" }, addEventListener() {} };
global.uPlot = class { constructor(opts, data) { this.opts = opts; this.data = data; charts.push(this); }
  setData(data) { this.data = data; } setSize() {} destroy() { this.destroyed = true; } };
global.WebSocket = class {};
global.alert = () => {};
let payload = null;
const liveFetches = [];
global.fetch = async url => {
  if (url === "/api/runs") return {ok: true, json: async () => []};
  if (url.startsWith("/api/runs/run/live/")) { liveFetches.push(url); return {ok: true, json: async () => payload}; }
  return {ok: false, json: async () => ({})};
};
vm.runInThisContext(input.app);
vm.runInThisContext(input.script);
for (const cb of domReady) cb();
vm.runInThisContext(`currentRunId = "run"; currentArm = "wild-type"; currentSeed = 1; currentProbe = 0;
  currentExperiment = {arms: [{label: "wild-type"}], seeds: [1],
    _dashboard_probes: {"wild-type": [{index: 0, assay: "open_loop_steering", label: "p0"}]}};`);
function textOf(el) { return (el.text || "") + " " + (el.children || []).map(textOf).join(" "); }
(async () => {
  const out = {substrate: {}};
  for (const [name, man] of Object.entries(input.substrateCases)) {
    vm.runInThisContext(`currentManifest = ${JSON.stringify(man)};`);
    updateRunPickerControls(JSON.parse(JSON.stringify(currentExperiment)), man, {});
    out.substrate[name] = document.getElementById("run-substrate-badge").text;
  }
  for (const [name, entry] of Object.entries(input.cases)) {
    payload = {windows: entry.windows};
    liveFetches.length = 0;
    fills.length = 0;
    vm.runInThisContext(`currentManifest = ${JSON.stringify(entry.manifest || {})};`);
    await window.liveActivityRefresh();
    const chart = charts.filter(c => !c.destroyed).at(-1);
    const strip = document.getElementById("live-activity-stage-strip");
    out[name] = {data: chart ? chart.data : null, labels: chart ? chart.opts.series.map(s => s.label) : null,
                 status: document.getElementById("live-activity-status").text,
                 watchDisabled: !!document.getElementById("live-activity-watch-btn").disabled,
                 liveFetches: liveFetches.length,
                 rateA: document.getElementById("live-activity-rate-a").value,
                 rateB: document.getElementById("live-activity-rate-b").value,
                 stage: strip.style.display, stageText: textOf(strip)};
    if (entry.pick) {
      const select = document.getElementById("live-activity-rate-a");
      select.value = entry.pick;
      select.listeners.change();
      const after = charts.filter(c => !c.destroyed).at(-1);
      out[name].pickedLabels = after.opts.series.map(s => s.label);
    }
  }
  process.stdout.write(JSON.stringify(out));
})().catch(error => { console.error(error); process.exit(1); });
'''


def test_live_v2_whole_network_rates_picker_and_stage_strip(fixtures_dir: Path) -> None:
    """Run app.js and live-activity.js under node against version 2 streams.

    The whole-network series is `all_count` even when recorded populations
    overlap and miss neurons; rates are count / (size x window_ms / 1000),
    including a short final window; the picker re-selects rate populations; the
    stage strip reports the current block minus the preceding ambient block,
    and the substrate label sits in the run header. Units: ms, counts, Hz per neuron. Shapes: one array per
    series.
    """
    import subprocess
    static = Path(__file__).resolve().parents[1] / "src/flyonenomics/dashboard/static"
    sizes = {"lamina": 100, "medulla": 50, "central_complex": 40, "steering": 10}
    # Overlapping populations (lamina and medulla share neurons) plus neurons in
    # no recorded population: the counts sum is not the whole-network count.
    plain = [
        v2_window(1000, 100.0, 100.0, {"lamina": 50, "medulla": 20, "central_complex": 8, "steering": 2}, 500, sizes),
        v2_window(2000, 200.0, 100.0, {"lamina": 70, "medulla": 10, "central_complex": 9, "steering": 3}, 520, sizes),
        v2_window(2500, 250.0, 50.0, {"lamina": 30, "medulla": 5, "central_complex": 4, "steering": 1}, 240, sizes)]
    blocked = [
        v2_window(1000, 100.0, 100.0, {"lamina": 40, "medulla": 20, "central_complex": 8, "steering": 2}, 400, sizes, 0, "ambient"),
        v2_window(2000, 200.0, 100.0, {"lamina": 60, "medulla": 20, "central_complex": 8, "steering": 2}, 420, sizes, 0, "ambient"),
        v2_window(3000, 300.0, 100.0, {"lamina": 90, "medulla": 15, "central_complex": 12, "steering": 5}, 600, sizes, 1, "stripe"),
        v2_window(4000, 400.0, 100.0, {"lamina": 110, "medulla": 15, "central_complex": 12, "steering": 5}, 640, sizes, 1, "stripe")]
    node = shutil.which("node") or str(Path.home() / ".local/bin/node")
    completed = subprocess.run([node, "-e", V2_HARNESS], capture_output=True, text=True, timeout=60,
                               input=json.dumps({
                                   "html": (static / "index.html").read_text(),
                                   "app": (static / "app.js").read_text(),
                                   "script": (static / "live-activity.js").read_text(),
                                   "substrateCases": {"bare": {"layers": {"background": False}},
                                                      "rest": {"substrate_id": "rest:0123456789abcdef",
                                                               "layers": {"background": True}},
                                                      "unlabeled": {"layers": {"background": True}}},
                                   "cases": {
                                       "plain": {"windows": plain, "pick": "medulla"},
                                       "blocked": {"windows": blocked},
                                   }}))
    assert completed.returncode == 0, completed.stderr
    out = json.loads(completed.stdout)

    # Substrate label in the run header: bare or rest:<id>.
    assert out["substrate"] == {"bare": "bare", "rest": "rest:0123456789abcdef",
                                "unlabeled": "rest (id not recorded)"}

    got = out["plain"]
    assert got["labels"][1] == "whole-network spikes/window"
    assert got["data"][1] == [500, 520, 240]  # all_count, not the overlapping partial sum.
    assert got["data"][1] != [sum(w["counts"].values()) for w in plain]
    assert got["rateA"] == "central_complex" and got["rateB"] == "lamina"  # central first, then sorted fill.
    assert got["labels"][2:] == ["central_complex mean rate per neuron (Hz)", "lamina mean rate per neuron (Hz)"]
    for series, pop in zip(got["data"][2:], ("central_complex", "lamina")):
        expected = [w["counts"][pop] / (sizes[pop] * w["window_ms"] / 1000) for w in plain]
        assert series == pytest.approx(expected)  # Short final window uses its own 50 ms.
    assert got["stage"] == "none"  # No block labels, no strip.
    assert got["pickedLabels"][2] == "medulla mean rate per neuron (Hz)"  # Population picker re-renders.

    got = out["blocked"]
    assert got["stage"] == "block"
    assert "block 1 (stripe) minus block 0 (ambient)" in got["stageText"]
    for pop in ("lamina", "medulla", "central_complex", "steering"):
        ambient = sum(w["counts"][pop] for w in blocked[:2]) / (sizes[pop] * 0.2)
        current = sum(w["counts"][pop] for w in blocked[2:]) / (sizes[pop] * 0.2)
        assert f"{pop}: {current - ambient:+.2f} Hz/neuron" in got["stageText"]
