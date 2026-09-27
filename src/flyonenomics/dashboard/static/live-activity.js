/**
 * FlyOnenomics Dashboard Live Activity View (WP13, SPEC item 66; WP23, SPEC-P2 section 7)
 *
 * Minimal live readout of network activity, in the spirit of fly-wirehead's
 * overlay. A version 2 stream (`live_version: 2`) charts the whole-network
 * spike count per flushed live window (`all_count`) and per-neuron population
 * rates in Hz (`count / (size x window_ms / 1000)`), plus a spike raster of
 * the recorded per-neuron live sample. A version 1 stream keeps its chart
 * under the partial labels: "sum over recorded populations (may overlap, not
 * whole-network)" and "spikes per second, aggregate" — never "whole-network"
 * or per-neuron Hz.
 *
 * Measured values only: no smoothing, no interpolation, no synthetic
 * fluctuation. A constant stream renders flat. A probe without live data
 * shows "no data".
 *
 * Data path: GET /api/runs/{run}/live/{arm}/{seed}/{probe} replays the
 * recorded NDJSON windows; the existing websocket /ws/{run}/{arm}/{seed}/{probe}
 * streams the same windows while a run executes (and replays a finished run).
 */

(function () {
  "use strict";

  // Fixed maximum number of sampled neurons shown in the live raster.
  const RASTER_NEURON_CAP = 64;

  let windows = [];
  let ratePopulations = [];
  let chart = null;
  let watchSocket = null;
  let activityGeneration = 0;
  let pickerReady = false;

  function elements() {
    return {
      empty: document.getElementById("live-activity-empty"),
      chartDiv: document.getElementById("live-activity-chart"),
      rasterWrapper: document.getElementById("live-activity-raster-wrapper"),
      raster: document.getElementById("live-activity-raster"),
      status: document.getElementById("live-activity-status"),
      watchBtn: document.getElementById("live-activity-watch-btn"),
      rateA: document.getElementById("live-activity-rate-a"),
      rateB: document.getElementById("live-activity-rate-b"),
      stageStrip: document.getElementById("live-activity-stage-strip"),
    };
  }

  function setStatus(text, badge) {
    const el = elements().status;
    el.textContent = text;
    el.className = `badge badge-${badge}`;
  }

  /**
   * Stream contract version: 2 only when every window carries live_version 2.
   */
  function streamVersion(list) {
    return list.length > 0 && list.every((w) => w.live_version === 2) ? 2 : 1;
  }

  /**
   * Choose up to two default rate populations: prefer a "central" key, then a
   * "DAN" key, then fill deterministically from the remaining sorted keys.
   */
  function pickRatePopulations(keys) {
    const chosen = [];
    const central = keys.find((k) => /central/i.test(k));
    if (central) chosen.push(central);
    const dan = keys.find((k) => /DAN/.test(k) && !chosen.includes(k));
    if (dan) chosen.push(dan);
    for (const key of [...keys].sort()) {
      if (chosen.length >= 2) break;
      if (!chosen.includes(key)) chosen.push(key);
    }
    return chosen.slice(0, 2);
  }

  /**
   * Recorded population keys of the current stream, in first-seen order.
   */
  function recordedPopulations() {
    const keys = [];
    for (const w of windows) {
      for (const k of Object.keys(w.counts || {})) {
        if (!keys.includes(k)) keys.push(k);
      }
    }
    return keys;
  }

  /**
   * Rebuild the population picker options, keeping any valid user selection;
   * first load takes the deterministic defaults.
   */
  function syncPicker() {
    const el = elements();
    if (!el.rateA || !el.rateB) return;
    const keys = recordedPopulations();
    const previous = pickerReady ? [el.rateA.value, el.rateB.value] : [null, null];
    const defaults = pickRatePopulations(keys);
    const fill = (select, allowNone) => {
      select.textContent = "";
      if (allowNone) {
        const none = document.createElement("option");
        none.value = "";
        none.textContent = "(none)";
        select.appendChild(none);
      }
      for (const key of keys) {
        const option = document.createElement("option");
        option.value = key;
        option.textContent = key;
        select.appendChild(option);
      }
    };
    fill(el.rateA, false);
    fill(el.rateB, true);
    el.rateA.value = keys.includes(previous[0]) ? previous[0] : (defaults[0] || "");
    el.rateB.value = (keys.includes(previous[1]) || previous[1] === "") ? previous[1] : (defaults[1] || "");
    pickerReady = true;
    ratePopulations = [el.rateA.value, el.rateB.value].filter((v) => v);
  }

  /**
   * Neuron count of a recorded population: the stream's own `sizes` under
   * version 2, otherwise null (version 1 streams never show per-neuron Hz).
   */
  function populationSize(pop, version) {
    if (version !== 2) return null;
    for (const w of windows) {
      const size = (w.sizes || {})[pop];
      if (typeof size === "number" && size > 0) return size;
    }
    return null;
  }

  /**
   * Derive chart series from measured windows. Version 2: the count series is
   * the whole-network `all_count`, and a rate is the window count divided by
   * the population's `sizes` entry and the window's own measured `window_ms`.
   * Version 1: the count series is the sum over the recorded populations
   * (which may overlap and need not cover the brain), and a rate is the window
   * count divided by the measured t_ms delta (the first window starts at
   * recording tick 0), an aggregate spikes-per-second, never per-neuron Hz.
   * No smoothing.
   */
  function buildSeries(list, version) {
    const tMs = list.map((w) => w.t_ms);
    const totals = version === 2
      ? list.map((w) => w.all_count)
      : list.map((w) => Object.values(w.counts || {}).reduce((sum, n) => sum + n, 0));
    const rates = ratePopulations.map((pop) => {
      const size = populationSize(pop, version);
      return list.map((w, i) => {
        if (version === 2) {
          const windowS = (w.window_ms || 0) / 1000;
          if (!(windowS > 0) || !size) return null;
          return ((w.counts || {})[pop] || 0) / windowS / size;
        }
        const previous = i > 0 ? list[i - 1].t_ms : 0;
        const windowS = (w.t_ms - previous) / 1000;
        if (!(windowS > 0)) return null;
        return ((w.counts || {})[pop] || 0) / windowS;
      });
    });
    return [tMs, totals, ...rates];
  }

  function countLabel(version) {
    return version === 2
      ? "whole-network spikes/window"
      : "sum over recorded populations (may overlap, not whole-network)";
  }

  function rateLabel(pop, version) {
    if (version !== 2) return `${pop} spikes per second, aggregate`;
    return populationSize(pop, version)
      ? `${pop} mean rate per neuron (Hz)`
      : `${pop} (size unknown, no rate)`;
  }

  function renderChart() {
    const el = elements();
    if (!windows.length) {
      el.empty.style.display = "block";
      el.empty.innerHTML = "<p>No data</p>";
      el.chartDiv.style.display = "none";
      if (chart) { chart.destroy(); chart = null; }
      return;
    }
    el.empty.style.display = "none";
    el.chartDiv.style.display = "block";

    const version = streamVersion(windows);
    const data = buildSeries(windows, version);
    const rateColors = ["#3fb950", "#bc8cff"];
    const series = [
      { label: "t (ms)" },
      { label: countLabel(version), scale: "count", stroke: "#58a6ff", width: 1.5 },
      ...ratePopulations.map((pop, i) => ({
        label: rateLabel(pop, version), scale: "hz", stroke: rateColors[i % rateColors.length], width: 1.5,
      })),
    ];
    const scales = { x: { time: false }, count: { auto: true }, hz: { auto: true } };
    const axes = [
      { label: "Time (ms)", stroke: "#8b949e", grid: { stroke: "#21262d" } },
      { label: countLabel(version), scale: "count", stroke: "#58a6ff", grid: { stroke: "#21262d" } },
      { label: version === 2 ? "Rate per neuron (Hz)" : "Spikes per second, aggregate", scale: "hz", side: 1, stroke: "#3fb950", grid: { show: false } },
    ];
    const width = el.chartDiv.clientWidth || 900;

    const labels = series.map((item) => item.label).join("|");
    if (chart && chart.flyonenomicsLabels !== labels) { chart.destroy(); chart = null; }
    if (chart) {
      chart.setData(data);
      chart.setSize({ width, height: 260 });
    } else {
      chart = new uPlot(
        { width, height: 260, series, scales, axes, legend: { show: true } },
        data,
        el.chartDiv);
      chart.flyonenomicsLabels = labels;
    }
  }

  /**
   * Stage strip for open-loop probes whose version 2 windows carry `block`:
   * per recorded population, the current block's per-neuron rate minus the
   * preceding ambient block's. Hidden when the stream carries no blocks or no
   * preceding ambient block exists.
   */
  function renderStageStrip() {
    const el = elements();
    const strip = el.stageStrip;
    if (!strip) return;
    strip.style.display = "none";
    strip.textContent = "";
    if (streamVersion(windows) !== 2) return;
    const blocked = windows.filter((w) => w.block !== null && w.block !== undefined);
    if (!blocked.length) return;
    const current = blocked[blocked.length - 1].block;
    const blocks = new Map();
    for (const w of blocked) {
      if (!blocks.has(w.block)) blocks.set(w.block, { stimulus: w.stimulus, windows: [] });
      blocks.get(w.block).windows.push(w);
    }
    const ambient = [...blocks.keys()]
      .filter((b) => b < current && blocks.get(b).stimulus === "ambient")
      .sort((a, b) => b - a)[0];
    if (ambient === undefined) return;

    const rate = (block, pop) => {
      const group = blocks.get(block);
      let spikes = 0, ms = 0, size = null;
      for (const w of group.windows) {
        spikes += (w.counts || {})[pop] || 0;
        ms += w.window_ms || 0;
        size = size || (w.sizes || {})[pop];
      }
      if (!(ms > 0) || !size) return null;
      return spikes / (ms / 1000) / size;
    };

    const title = document.createElement("h3");
    title.textContent = `Stage strip: block ${current} (${blocks.get(current).stimulus}) minus block ${ambient} (ambient), per-neuron rate`;
    strip.appendChild(title);
    const row = document.createElement("div");
    row.className = "stage-strip-row";
    for (const pop of recordedPopulations()) {
      const now = rate(current, pop);
      const base = rate(ambient, pop);
      const badge = document.createElement("span");
      badge.className = "badge badge-idle stage-strip-item";
      badge.textContent = now === null || base === null
        ? `${pop}: no measured rate`
        : `${pop}: ${now - base >= 0 ? "+" : ""}${(now - base).toFixed(2)} Hz/neuron`;
      row.appendChild(badge);
    }
    strip.appendChild(row);
    strip.style.display = "block";
  }

  /**
   * Raster of the recorded live spike sample: at most RASTER_NEURON_CAP
   * neuron indices in first-seen order, x in relative ticks as recorded.
   */
  function renderRaster() {
    const el = elements();
    const canvas = el.raster;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const seen = new Map();
    const points = [];
    for (const w of windows) {
      for (const [idx, tick] of w.spikes || []) {
        if (!seen.has(idx)) {
          if (seen.size >= RASTER_NEURON_CAP) continue;
          seen.set(idx, seen.size);
        }
        if (seen.has(idx)) points.push([tick, seen.get(idx)]);
      }
    }

    if (!points.length) {
      el.rasterWrapper.style.display = "none";
      return;
    }
    el.rasterWrapper.style.display = "block";

    const w = canvas.width;
    const h = canvas.height;
    const padding = { left: 50, right: 20, top: 10, bottom: 30 };
    const plotW = w - padding.left - padding.right;
    const plotH = h - padding.top - padding.bottom;

    let minT = Infinity, maxT = -Infinity;
    for (const [tick] of points) { minT = Math.min(minT, tick); maxT = Math.max(maxT, tick); }
    if (minT === maxT) maxT += 1;
    const rows = Math.max(seen.size, 1);

    ctx.strokeStyle = "#30363d";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, h - padding.bottom);
    ctx.lineTo(w - padding.right, h - padding.bottom);
    ctx.stroke();

    ctx.fillStyle = "#8b949e";
    ctx.font = "11px -apple-system, sans-serif";
    ctx.fillText("Tick (relative)", w / 2, h - 8);
    ctx.fillText(`${minT}`, padding.left, h - padding.bottom + 14);
    ctx.fillText(`${maxT}`, w - padding.right - 40, h - padding.bottom + 14);
    ctx.fillText(`${seen.size} sampled neurons`, padding.left, padding.top + 4);

    ctx.fillStyle = "#d29922";
    for (const [tick, row] of points) {
      const x = padding.left + ((tick - minT) / (maxT - minT)) * plotW;
      const y = padding.top + (row / rows) * plotH;
      ctx.fillRect(x - 0.5, y - 1, 1.5, 3);
    }
  }

  function render() {
    renderChart();
    renderStageStrip();
    renderRaster();
  }

  function stopWatch() {
    if (watchSocket) { const s = watchSocket; watchSocket = null; s.close(); }
    elements().watchBtn.textContent = "Watch Live";
  }

  /**
   * Reload the recorded live windows for the current probe selection and
   * render the replay. Called by app.js on every probe data load.
   */
  async function refresh() {
    const generation = ++activityGeneration;
    stopWatch();
    windows = [];
    ratePopulations = [];
    pickerReady = false;
    setStatus("No data", "idle");

    const watchBtn = elements().watchBtn;
    watchBtn.disabled = false;

    if (typeof currentRunId === "undefined" || !currentRunId || !currentArm || currentProbe === null) {
      render();
      return;
    }
    try {
      const url = `/api/runs/${encodeURIComponent(currentRunId)}/live/${encodeURIComponent(currentArm)}/${encodeURIComponent(currentSeed)}/${currentProbe}`;
      const res = await fetch(url);
      if (generation !== activityGeneration) return;
      if (!res.ok) { render(); return; }
      const payload = await res.json();
      if (generation !== activityGeneration) return;
      windows = payload.windows || [];
      syncPicker();
      setStatus(windows.length ? `${windows.length} windows replayed` : "No data",
        windows.length ? "done" : "idle");
      render();
    } catch (err) {
      if (typeof reportError === "function") reportError("Live activity load failed:", err);
    }
  }

  /**
   * Stream the same windows over the existing websocket route: live while a
   * run executes, replayed from tick 0 for a finished run.
   */
  function toggleWatch() {
    if (watchSocket) { stopWatch(); setStatus("Stopped", "idle"); return; }
    if (!currentRunId || !currentArm) {
      alert("Select a run and arm first");
      return;
    }
    const generation = ++activityGeneration;
    windows = [];
    render();

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/${encodeURIComponent(currentRunId)}/${encodeURIComponent(currentArm)}/${encodeURIComponent(currentSeed)}/${currentProbe}`;
    setStatus("Connecting...", "running");
    watchSocket = new WebSocket(wsUrl);
    const socket = watchSocket;

    socket.onopen = () => {
      if (socket !== watchSocket) return;
      elements().watchBtn.textContent = "Stop";
      setStatus("Streaming (max 10 Hz)", "running");
    };
    socket.onmessage = (event) => {
      if (socket !== watchSocket || generation !== activityGeneration) return;
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "final") {
          setStatus(`Finished: ${msg.state}`, "done");
          stopWatch();
          return;
        }
        if (msg.type !== "live") return;
        const line = msg.line || msg;
        windows.push(line);
        syncPicker();
        setStatus(`${windows.length} windows`, "running");
        render();
      } catch (err) {
        if (typeof reportError === "function") reportError("Live activity packet error:", err);
      }
    };
    socket.onclose = () => {
      if (socket !== watchSocket) return;
      stopWatch();
    };
    socket.onerror = (err) => {
      if (typeof reportError === "function") reportError("Live activity websocket error:", err);
      setStatus("Error", "failed");
    };
  }

  document.addEventListener("DOMContentLoaded", () => {
    const el = elements();
    el.watchBtn.addEventListener("click", toggleWatch);
    const onPick = () => {
      ratePopulations = [el.rateA.value, el.rateB.value].filter((v) => v);
      renderChart();
    };
    if (el.rateA) el.rateA.addEventListener("change", onPick);
    if (el.rateB) el.rateB.addEventListener("change", onPick);
  });

  // Hook invoked by app.js loadProbeData().
  window.liveActivityRefresh = refresh;
})();
