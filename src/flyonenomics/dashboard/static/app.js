/**
 * FlyOnenomics Dashboard Client Application (WP8)
 *
 * Implements panel rendering, interactive raster subsampling notice,
 * dopamine baseline reference line, receptor occupancy toggle,
 * arena top-down heading visualization, metrics tables, comparison panel,
 * and WebSocket live mode.
 */

const CODEX_BASE_URL = "https://codex.flywire.ai/app/cell_details?root_id=";
// WP8 mechanics: discard responses from earlier run/probe selections.
let runGeneration = 0;
let probeGeneration = 0;
let currentExperiment = {};
let currentManifest = {};

function reportError(message, error) {
  console.error(message, error);
  const banner = document.getElementById("dashboard-error");
  banner.hidden = false;
  banner.textContent = `${message} ${error?.message || error || ""}`;
}
window.addEventListener("error", e => reportError("JavaScript error:", e.error || e.message));
window.addEventListener("unhandledrejection", e => reportError("Request failed:", e.reason));

function addRow(body, cells) {
  const row = document.createElement("tr");
  cells.forEach(value => {
    const cell = document.createElement("td");
    cell.textContent = String(value ?? "-");
    row.appendChild(cell);
  });
  body.appendChild(row);
}
const number = value => Number.isFinite(value) ? value.toFixed(3) : "-";
const seriesMin = values => values.reduce((a, b) => Math.min(a, b), Infinity);
const seriesMax = values => values.reduce((a, b) => Math.max(a, b), -Infinity);
function probeUrl(table) {
  return `/api/runs/${encodeURIComponent(currentRunId)}/tables/${encodeURIComponent(currentArm)}/${encodeURIComponent(currentSeed)}/${currentProbe}/${table}`;
}
function stopLiveStream() {
  if (liveSocket) { const socket = liveSocket; liveSocket = null; socket.close(); }
  document.getElementById("live-connect-btn").textContent = "Start Live Stream";
  document.getElementById("live-status-indicator").textContent = "Disconnected";
}

let currentRunId = null;
let currentArm = null;
let currentSeed = null;
let currentProbe = 0;
let showReceptors = false;

let cachedDopamineData = null;
let cachedReceptorsData = null;
let liveSocket = null;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  loadRuns();
});

function initEventListeners() {
  document.getElementById("refresh-runs-btn").addEventListener("click", loadRuns);

  document.getElementById("run-select").addEventListener("change", (e) => {
    selectRun(e.target.value);
  });

  document.getElementById("arm-select").addEventListener("change", (e) => {
    currentArm = e.target.value;
    updateProbeControls();
    loadProbeData();
  });

  document.getElementById("seed-select").addEventListener("change", (e) => {
    currentSeed = e.target.value;
    loadProbeData();
  });

  document.getElementById("probe-select").addEventListener("change", (e) => {
    currentProbe = parseInt(e.target.value, 10) || 0;
    loadProbeData();
  });

  document.getElementById("dopamine-toggle").addEventListener("click", () => {
    showReceptors = !showReceptors;
    document.getElementById("dopamine-toggle").textContent = showReceptors
      ? "Toggle Dopamine Concentrations"
      : "Toggle Receptors (occ_D1 / occ_D2)";
    renderDopamineOrReceptors();
  });

  document.getElementById("execute-compare-btn").addEventListener("click", executeCompare);

  document.getElementById("live-connect-btn").addEventListener("click", toggleLiveStream);
}

/**
 * Fetch and populate run list from /api/runs
 */
async function loadRuns() {
  try {
    const res = await fetch("/api/runs");
    if (!res.ok) throw new Error("Failed to load runs");
    const runs = await res.json();

    const select = document.getElementById("run-select");
    const compA = document.getElementById("compare-run-a");
    const compB = document.getElementById("compare-run-b");

    select.innerHTML = '<option value="">Select a run...</option>';
    compA.innerHTML = '<option value="">Select Run A...</option>';
    compB.innerHTML = '<option value="">Select Run B...</option>';

    runs.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r.run_id;
      opt.textContent = `${r.run_id} [${r.state}] - ${r.name || "unnamed"}`;
      select.appendChild(opt);

      const optA = opt.cloneNode(true);
      const optB = opt.cloneNode(true);
      compA.appendChild(optA);
      compB.appendChild(optB);
    });

    if (runs.length > 0 && !currentRunId) {
      select.value = runs[0].run_id;
      selectRun(runs[0].run_id);
    }
  } catch (err) {
    reportError("Error loading runs:", err);
  }
}

/**
 * Select and load all details for one run
 */
async function selectRun(runId) {
  if (!runId) { currentRunId = null; ++runGeneration; loadProbeData(); return; }
  const generation = ++runGeneration;
  ++probeGeneration;
  stopLiveStream();
  currentRunId = runId;
  currentArm = null;
  currentSeed = null;
  document.getElementById("dashboard-error").hidden = true;

  try {
    // 1. Fetch Experiment
    const expRes = await fetch(`/api/runs/${encodeURIComponent(runId)}/experiment`);
    let exp = {};
    if (expRes.ok) exp = await expRes.json();

    // 2. Fetch Manifest
    const manRes = await fetch(`/api/runs/${encodeURIComponent(runId)}/manifest`);
    let man = {};
    if (manRes.ok) man = await manRes.json();

    // 3. Fetch Metrics
    const metRes = await fetch(`/api/runs/${encodeURIComponent(runId)}/metrics`);
    let met = {};
    if (metRes.ok) met = await metRes.json();

    // 4. Fetch Status
    const stRes = await fetch(`/api/runs/${encodeURIComponent(runId)}/status`);
    let status = {};
    if (stRes.ok) status = await stRes.json();

    if (generation !== runGeneration) return;
    currentExperiment = exp;
    currentManifest = man;
    const phase1Status = document.getElementById("phase1-status");
    phase1Status.textContent = man.phase1_status || "";
    phase1Status.hidden = !man.phase1_status;
    updateRunPickerControls(exp, man, status);
    renderManifestSummary(man, exp);
    renderMetrics(met);

    await loadProbeData();
  } catch (err) {
    reportError("Error selecting run:", err);
  }
}

function updateRunPickerControls(exp, man, status) {
  const state = man.state || status.state || "unknown";
  const badge = document.getElementById("run-lifecycle-badge");
  badge.textContent = state;
  badge.className = `state-display badge badge-${state}`;

  // WP23 (SPEC-P2 section 7): the substrate label in the run header. Manifests
  // written before the Phase 2 identity fields carry no substrate_id; those
  // fall back to the layer flags.
  const substrateBadge = document.getElementById("run-substrate-badge");
  const layers = man.layers || exp.layers || {};
  substrateBadge.textContent = man.substrate_id || (layers.background ? "rest (id not recorded)" : "bare");

  const armSelect = document.getElementById("arm-select");
  const seedSelect = document.getElementById("seed-select");
  const probeSelect = document.getElementById("probe-select");

  armSelect.innerHTML = "";
  seedSelect.innerHTML = "";
  probeSelect.innerHTML = "";

  const arms = exp.arms || [];
  arms.forEach((arm, i) => {
    const opt = document.createElement("option");
    opt.value = arm.label;
    opt.textContent = `Arm: ${arm.label}`;
    armSelect.appendChild(opt);
    if (i === 0) currentArm = arm.label;
  });
  armSelect.disabled = arms.length === 0;

  const seeds = exp.seeds || [];
  seeds.forEach((seed, i) => {
    const opt = document.createElement("option");
    opt.value = seed;
    opt.textContent = `Seed ${seed}`;
    seedSelect.appendChild(opt);
    if (i === 0) currentSeed = seed;
  });
  seedSelect.disabled = seeds.length === 0;

  updateProbeControls();
}

function updateProbeControls() {
  const select = document.getElementById("probe-select");
  select.innerHTML = "";
  const probes = currentExperiment._dashboard_probes?.[currentArm] || [];
  probes.forEach(probe => {
    const option = document.createElement("option");
    option.value = probe.index;
    option.textContent = `Probe ${probe.index}: ${probe.label || probe.assay}`;
    select.appendChild(option);
  });
  currentProbe = probes.length ? probes[0].index : null;
  select.disabled = probes.length <= 1;
}

/**
 * Manifest Summary Panel
 */
function renderManifestSummary(manifest, experiment) {
  const layersDiv = document.getElementById("manifest-layers");
  layersDiv.textContent = "";
  const status = document.createElement("p");
  status.textContent = `Configuration: ${manifest.compatibility || "not reported"}; stubs: ${(manifest.stubs || []).join(", ") || "none reported"}`;
  layersDiv.appendChild(status);
  const behaviour = document.createElement("p");
  behaviour.textContent = `Behaviour component: ${manifest.behaviour_component || "unavailable"}`;
  layersDiv.appendChild(behaviour);
  for (const [layer, value] of Object.entries(manifest.layers || experiment.layers || {})) {
    const tag = document.createElement("span");
    tag.className = "tag";
    const validation = manifest.layer_validation?.[layer]?.validation || "absent";
    tag.textContent = `${layer}: ${value} (${validation})`;
    layersDiv.appendChild(tag);
  }
  for (const [arm, flags] of Object.entries(manifest.arm_layers || {})) {
    const row = document.createElement("p");
    row.textContent = `${arm}: ${JSON.stringify(flags)}`;
    layersDiv.appendChild(row);
  }
  const params = document.querySelector("#manifest-params tbody");
  params.innerHTML = "";
  for (const [key, value] of Object.entries(manifest.free_parameters || {})) addRow(params, [key, JSON.stringify(value)]);
  if (!params.children.length) addRow(params, ["No free parameters reported", "-"]);
  document.getElementById("manifest-slowstate").textContent = manifest.slow_state || "Not reported";
  const unsettled = manifest.unsettled;
  document.getElementById("manifest-unsettled").textContent = Array.isArray(unsettled)
    ? (unsettled.length ? JSON.stringify(unsettled) : "All probes settled") : "Settle results not reported";
  const artefacts = document.getElementById("manifest-artefacts");
  artefacts.textContent = "";
  for (const [name, result] of Object.entries(manifest.artefacts || {})) {
    const entry = document.createElement("details");
    const title = document.createElement("summary");
    title.textContent = `${name}: ${typeof result === "string" ? result : result.outcome || "reported"}`;
    entry.appendChild(title);
    if (typeof result === "object") {
      const details = document.createElement("pre");
      details.textContent = JSON.stringify(result, null, 2);
      entry.appendChild(details);
    }
    artefacts.appendChild(entry);
  }
  if (!artefacts.children.length) artefacts.textContent = "Artefact results not reported";
  const flags = document.createElement("p");
  flags.textContent = `Flags: ${JSON.stringify(manifest.artefact_flags || [])}`;
  artefacts.appendChild(flags);
  const validation = document.querySelector("#manifest-validation tbody");
  validation.innerHTML = "";
  for (const entry of manifest.validation || []) {
    addRow(validation, [entry.test_id, `${entry.binding || "unknown"} (${entry.outcome || "not reported"}); arms: ${JSON.stringify(entry.arm_bindings || {})}`, entry.identity_hash]);
  }
  if (!validation.children.length) addRow(validation, ["No validation entries recorded", "unknown", "-"]);
}

/**
 * Load probe-specific Parquet tables
 */
async function loadProbeData() {
  const generation = ++probeGeneration;
  stopLiveStream();
  cachedDopamineData = null;
  cachedReceptorsData = null;
  document.getElementById("codex-links").textContent = "";
  for (const id of ["raster-canvas", "rates-canvas", "dopamine-canvas", "arena-canvas"]) clearCanvas(document.getElementById(id));
  document.getElementById("raster-subsample-notice").textContent = "No selected recording loaded";
  document.getElementById("dopamine-empty").style.display = "block";
  document.getElementById("dopamine-empty").textContent = "No selected recording loaded";
  document.getElementById("dopamine-chart-wrapper").style.display = "none";
  document.getElementById("arena-empty").style.display = "block";
  document.getElementById("arena-empty").textContent = "No selected recording loaded";
  document.getElementById("arena-chart-wrapper").style.display = "none";
  if (!currentRunId || !currentArm || currentProbe === null) {
    if (typeof window.liveActivityRefresh === "function") window.liveActivityRefresh();
    return;
  }
  await Promise.all([loadRasterData(generation), loadRatesData(generation),
    loadDopamineAndReceptorData(generation), loadArenaData(generation)]);
  // WP13: refresh the live activity view for the selected probe.
  if (typeof window.liveActivityRefresh === "function") window.liveActivityRefresh();
}

/**
 * Raster plot
 */
async function loadRasterData(generation = probeGeneration) {
  const canvas = document.getElementById("raster-canvas");
  const notice = document.getElementById("raster-subsample-notice");
  const codexLinks = document.getElementById("codex-links");

  try {
    const res = await fetch(probeUrl("spikes"));
    if (generation !== probeGeneration) return;
    if (!res.ok) {
      notice.textContent = "No spike data available";
      clearCanvas(canvas);
      return;
    }
    const data = await res.json();
    if (generation !== probeGeneration) return;
    notice.textContent = data.subsampling_stated || "Complete raster";

    const cols = data.columns || {};
    const tMs = cols.t_ms || [];
    const idx = cols.idx || [];

    renderRasterPlot(canvas, tMs, idx);

    // Every displayed engine index links through the exact int64 index table.
    const uniqueIds = Array.from(new Set(idx));
    codexLinks.innerHTML = "";
    for (const id of uniqueIds) {
      const root = data.neuron_roots?.[id];
      const link = document.createElement(root ? "a" : "span");
      if (root) {
        link.href = `${CODEX_BASE_URL}${encodeURIComponent(root)}`;
        link.target = "_blank";
        link.rel = "noopener";
      }
      link.textContent = root ? `Neuron ${id} — root ${root}` : `Neuron ${id}: root ID unavailable`;
      link.style.marginRight = "0.75rem";
      codexLinks.appendChild(link);
    }
    if (!uniqueIds.length) codexLinks.textContent = "No spikes recorded";

  } catch (err) {
    reportError("Error loading raster:", err);
  }
}

function renderRasterPlot(canvas, tMs, idx) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (!tMs.length) {
    drawEmptyMessage(ctx, w, h, "No spikes in this recording");
    return;
  }

  const padding = { left: 50, right: 20, top: 20, bottom: 40 };
  const plotW = w - padding.left - padding.right;
  const plotH = h - padding.top - padding.bottom;

  let minT = seriesMin(tMs);
  let maxT = seriesMax(tMs);
  if (minT === maxT) maxT += 1.0;

  let minIdx = seriesMin(idx);
  let maxIdx = seriesMax(idx);
  if (minIdx === maxIdx) maxIdx += 1;

  // Draw axes
  ctx.strokeStyle = "#30363d";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top);
  ctx.lineTo(padding.left, h - padding.bottom);
  ctx.lineTo(w - padding.right, h - padding.bottom);
  ctx.stroke();

  // Draw axis labels
  ctx.fillStyle = "#8b949e";
  ctx.font = "11px -apple-system, sans-serif";
  ctx.fillText("Time (ms)", w / 2, h - 10);
  ctx.save();
  ctx.translate(15, h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Neuron Index", 0, 0);
  ctx.restore();

  // Ticks
  ctx.fillText(`${minT.toFixed(0)} ms`, padding.left, h - padding.bottom + 15);
  ctx.fillText(`${maxT.toFixed(0)} ms`, w - padding.right - 40, h - padding.bottom + 15);
  ctx.fillText(`${minIdx}`, padding.left - 35, h - padding.bottom);
  ctx.fillText(`${maxIdx}`, padding.left - 35, padding.top + 10);

  // Spikes
  ctx.fillStyle = "#58a6ff";
  for (let i = 0; i < tMs.length; i++) {
    const x = padding.left + ((tMs[i] - minT) / (maxT - minT)) * plotW;
    const y = h - padding.bottom - ((idx[i] - minIdx) / (maxIdx - minIdx)) * plotH;
    ctx.fillRect(x - 1, y - 2, 2, 4);
  }
}

/**
 * Population Rates plot
 */
async function loadRatesData(generation = probeGeneration) {
  const canvas = document.getElementById("rates-canvas");
  try {
    const res = await fetch(probeUrl("rates"));
    if (generation !== probeGeneration) return;
    if (!res.ok) {
      clearCanvas(canvas);
      return;
    }
    const data = await res.json();
    if (generation !== probeGeneration) return;
    const cols = data.columns || {};
    renderRatesPlot(canvas, cols);
  } catch (err) {
    reportError("Error loading rates:", err);
  }
}

function renderRatesPlot(canvas, cols) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const tMs = cols.t_ms || cols.tick || [];
  const populations = Object.keys(cols).filter((k) => k !== "tick" && k !== "t_ms");

  if (!tMs.length || populations.length === 0) {
    drawEmptyMessage(ctx, w, h, "No rate data recorded");
    return;
  }

  const padding = { left: 50, right: 120, top: 20, bottom: 40 };
  const plotW = w - padding.left - padding.right;
  const plotH = h - padding.top - padding.bottom;

  let minT = seriesMin(tMs);
  let maxT = seriesMax(tMs);
  if (minT === maxT) maxT += 1.0;

  let maxRate = 1.0;
  populations.forEach((pop) => {
    const arr = cols[pop] || [];
    if (arr.length) maxRate = Math.max(maxRate, seriesMax(arr));
  });
  maxRate *= 1.1;

  // Axes
  ctx.strokeStyle = "#30363d";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top);
  ctx.lineTo(padding.left, h - padding.bottom);
  ctx.lineTo(w - padding.right, h - padding.bottom);
  ctx.stroke();

  // Labels
  ctx.fillStyle = "#8b949e";
  ctx.font = "11px -apple-system, sans-serif";
  ctx.fillText("Time (ms)", w / 2, h - 10);
  ctx.save();
  ctx.translate(15, h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("Firing Rate (Hz)", 0, 0);
  ctx.restore();

  // Ticks
  ctx.fillText(`${minT.toFixed(0)} ms`, padding.left, h - padding.bottom + 15);
  ctx.fillText(`${maxT.toFixed(0)} ms`, w - padding.right - 40, h - padding.bottom + 15);
  ctx.fillText("0 Hz", padding.left - 30, h - padding.bottom);
  ctx.fillText(`${maxRate.toFixed(1)} Hz`, padding.left - 45, padding.top + 10);

  const colors = ["#3fb950", "#bc8cff", "#58a6ff", "#d29922", "#f85149"];

  // Lines
  populations.forEach((pop, pIdx) => {
    const color = colors[pIdx % colors.length];
    const rates = cols[pop] || [];
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < tMs.length; i++) {
      const x = padding.left + ((tMs[i] - minT) / (maxT - minT)) * plotW;
      const y = h - padding.bottom - (rates[i] / maxRate) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Legend
    ctx.fillStyle = color;
    ctx.fillRect(w - padding.right + 15, padding.top + pIdx * 20, 10, 10);
    ctx.fillStyle = "#c9d1d9";
    ctx.fillText(pop, w - padding.right + 30, padding.top + pIdx * 20 + 9);
  });
}

/**
 * Dopamine and Receptors
 */
async function loadDopamineAndReceptorData(generation = probeGeneration) {
  try {
    const [daRes, recRes] = await Promise.all([
      fetch(probeUrl("dopamine")),
      fetch(probeUrl("receptors")),
    ]);

    const da = daRes.ok ? await daRes.json() : null;
    const rec = recRes.ok ? await recRes.json() : null;
    if (generation !== probeGeneration) return;
    cachedDopamineData = da;
    cachedReceptorsData = rec;
    document.getElementById("da-reference").textContent = da ? `da.DA_ref = ${da.da_ref} µM (Params)` : "DA_ref unavailable";

    renderDopamineOrReceptors();
  } catch (err) {
    reportError("Error loading dopamine/receptors:", err);
  }
}

function renderDopamineOrReceptors() {
  const emptyDiv = document.getElementById("dopamine-empty");
  const wrapper = document.getElementById("dopamine-chart-wrapper");
  const canvas = document.getElementById("dopamine-canvas");

  const data = showReceptors ? cachedReceptorsData : cachedDopamineData;
  const cols = data && data.columns ? data.columns : {};
  const tMs = cols.t_ms || cols.tick || [];
  const fields = Object.keys(cols).filter((k) => k !== "tick" && k !== "t_ms");

  if (!tMs.length || fields.length === 0) {
    emptyDiv.style.display = "block";
    emptyDiv.textContent = data ? "No neuromodulation layer in this run" : "Dopamine/receptor table unavailable";
    wrapper.style.display = "none";
    return;
  }

  emptyDiv.style.display = "none";
  wrapper.style.display = "block";

  renderTimeSeriesWithRef(canvas, tMs, fields, cols, showReceptors ? "Receptor Occupancy (0-1)" : "Dopamine (µM)", showReceptors ? null : data.da_ref);
}

function renderTimeSeriesWithRef(canvas, tMs, fields, cols, yLabel, refLine) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const padding = { left: 50, right: 140, top: 20, bottom: 40 };
  const plotW = w - padding.left - padding.right;
  const plotH = h - padding.top - padding.bottom;

  let minT = seriesMin(tMs);
  let maxT = seriesMax(tMs);
  if (minT === maxT) maxT += 1.0;

  let maxY = refLine ? refLine * 1.5 : 1.0;
  fields.forEach((f) => {
    const arr = cols[f] || [];
    if (arr.length) maxY = Math.max(maxY, seriesMax(arr));
  });
  maxY *= 1.1;

  // Axes
  ctx.strokeStyle = "#30363d";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top);
  ctx.lineTo(padding.left, h - padding.bottom);
  ctx.lineTo(w - padding.right, h - padding.bottom);
  ctx.stroke();

  // Labels
  ctx.fillStyle = "#8b949e";
  ctx.font = "11px -apple-system, sans-serif";
  ctx.fillText("Time (ms)", w / 2, h - 10);
  ctx.save();
  ctx.translate(15, h / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText(yLabel, 0, 0);
  ctx.restore();

  // Ticks
  ctx.fillText(`${minT.toFixed(0)} ms`, padding.left, h - padding.bottom + 15);
  ctx.fillText(`${maxT.toFixed(0)} ms`, w - padding.right - 40, h - padding.bottom + 15);
  ctx.fillText("0", padding.left - 20, h - padding.bottom);
  ctx.fillText(`${maxY.toFixed(3)}`, padding.left - 45, padding.top + 10);

  // Reference line (da.DA_ref)
  if (refLine !== null && refLine !== undefined) {
    const refY = h - padding.bottom - (refLine / maxY) * plotH;
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = "#f85149";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(padding.left, refY);
    ctx.lineTo(w - padding.right, refY);
    ctx.stroke();
    ctx.restore();
    ctx.fillStyle = "#f85149";
    ctx.fillText(`DA_ref (${refLine} µM)`, w - padding.right + 10, refY + 4);
  }

  const colors = ["#d29922", "#3fb950", "#58a6ff", "#bc8cff", "#f0883e"];

  // Data lines
  fields.forEach((f, idx) => {
    const color = colors[idx % colors.length];
    const vals = cols[f] || [];
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < tMs.length; i++) {
      const x = padding.left + ((tMs[i] - minT) / (maxT - minT)) * plotW;
      const y = h - padding.bottom - (vals[i] / maxY) * plotH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Legend
    ctx.fillStyle = color;
    ctx.fillRect(w - padding.right + 15, padding.top + (idx + (refLine ? 1 : 0)) * 18, 10, 10);
    ctx.fillStyle = "#c9d1d9";
    ctx.fillText(f, w - padding.right + 30, padding.top + (idx + (refLine ? 1 : 0)) * 18 + 9);
  });
}

/**
 * Arena Panel
 */
async function loadArenaData(generation = probeGeneration) {
  const emptyDiv = document.getElementById("arena-empty");
  const wrapper = document.getElementById("arena-chart-wrapper");
  const canvas = document.getElementById("arena-canvas");
  const info = document.getElementById("arena-info");

  try {
    const res = await fetch(probeUrl("arena"));
    if (generation !== probeGeneration) return;
    if (!res.ok) {
      emptyDiv.style.display = "block";
      emptyDiv.textContent = "Arena table unavailable";
      wrapper.style.display = "none";
      return;
    }
    const data = await res.json();
    if (generation !== probeGeneration) return;
    const cols = data.columns || {};
    const xs = cols.x || [];
    const ys = cols.y || [];
    const hs = cols.h || [];

    if (!xs.length || (currentManifest.stubs || []).includes("IdentityBehaviour")) {
      emptyDiv.style.display = "block";
      emptyDiv.innerHTML = "<p>No arena data in this run</p>";
      wrapper.style.display = "none";
      return;
    }

    emptyDiv.style.display = "none";
    wrapper.style.display = "flex";

    const assay = currentExperiment._dashboard_probes?.[currentArm]?.find(p => p.index === currentProbe)?.assay;
    const tuning = assay === "open_loop_steering" ? renderSteeringCurve(canvas, cols, data.openloop) : null;
    if (!tuning) renderArenaTopDown(canvas, xs, ys, hs, data.arena_radius_mm);

    const finalX = xs[xs.length - 1];
    const finalY = ys[ys.length - 1];
    const finalH = hs[hs.length - 1];
    const stimuli = ["A", "B", "distractor"].map(stimulus =>
      `${stimulus}: ` + ["az_arena", "az_fly", "width", "contrast"].map(field =>
        `${field}=${number(cols[`${field}_${stimulus}`]?.at(-1))}`).join(", "));
    info.textContent = `${assay === "open_loop_steering" ? "Steering tuning curve" : "Arena trajectory"}\nSamples: ${xs.length}\nFinal position: (${number(finalX)}, ${number(finalY)}) mm\nHeading: ${number(finalH)} deg\nStimuli (angles/width in deg):\n${stimuli.join("\n")}${tuning ? "\nDwell means (transitions excluded):\n" + JSON.stringify(tuning, null, 2) : ""}`;

  } catch (err) {
    reportError("Error loading arena:", err);
  }
}

function renderSteeringCurve(canvas, cols, timing) {
  const ctx = canvas.getContext("2d");
  clearCanvas(canvas);
  const groups = new Map();
  const periodMs = (timing.transition_s + timing.dwell_s) * 1000;
  (cols.az_fly_A || []).forEach((az, i) => {
    if (cols.t_ms[i] % periodMs < timing.transition_s * 1000) return;
    if (!groups.has(az)) groups.set(az, []);
    groups.get(az).push(i);
  });
  const xs = [...groups.keys()].sort((a, b) => a - b);
  const means = xs.map(az => {
    const indices = groups.get(az);
    return {azimuth_deg: az,
      mean_omega_deg_s: indices.reduce((sum, i) => sum + cols.omega[i], 0) / indices.length,
      mean_rate_difference_hz: cols.r_L && cols.r_R
        ? indices.reduce((sum, i) => sum + cols.r_R[i] - cols.r_L[i], 0) / indices.length : null};
  });
  const ys = means.map(row => row.mean_omega_deg_s);
  if (!xs.length) { drawEmptyMessage(ctx, canvas.width, canvas.height, "No steering dwell samples"); return; }
  const minX = seriesMin(xs), maxX = seriesMax(xs);
  const minY = seriesMin(ys), maxY = seriesMax(ys);
  ctx.fillStyle = "#58a6ff";
  xs.forEach((x, i) => ctx.fillRect(50 + (x-minX)/(maxX-minX || 1)*(canvas.width-100),
    canvas.height-50-(ys[i]-minY)/(maxY-minY || 1)*(canvas.height-100), 3, 3));
  ctx.fillText("Stimulus A az_fly (deg)", 50, canvas.height-15);
  ctx.fillText(`Mean omega (deg/s): ${number(minY)} to ${number(maxY)}`, 50, 20);
  return means;
}

function renderArenaTopDown(canvas, xs, ys, hs, radiusMm) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2;
  const radius = Math.min(w, h) / 2 - 25;

  // Draw circular arena boundary
  ctx.strokeStyle = "#30363d";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, 2 * Math.PI);
  ctx.stroke();

  const scale = radius / radiusMm;

  // Draw trajectory
  ctx.strokeStyle = "#58a6ff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let i = 0; i < xs.length; i++) {
    const px = cx + xs[i] * scale;
    const py = cy - ys[i] * scale;
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.stroke();

  // Draw start dot
  const startX = cx + xs[0] * scale;
  const startY = cy - ys[0] * scale;
  ctx.fillStyle = "#3fb950";
  ctx.beginPath();
  ctx.arc(startX, startY, 4, 0, 2 * Math.PI);
  ctx.fill();

  // Draw current position and heading arrow
  const endX = cx + xs[xs.length - 1] * scale;
  const endY = cy - ys[ys.length - 1] * scale;
  const heading = hs[hs.length - 1] * Math.PI / 180;

  ctx.fillStyle = "#f85149";
  ctx.beginPath();
  ctx.arc(endX, endY, 5, 0, 2 * Math.PI);
  ctx.fill();

  // Heading vector
  const arrowLen = 15;
  const hx = endX + Math.sin(heading) * arrowLen;
  const hy = endY - Math.cos(heading) * arrowLen;
  ctx.strokeStyle = "#f85149";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(endX, endY);
  ctx.lineTo(hx, hy);
  ctx.stroke();
}

/**
 * Metrics Panel
 */
function renderMetrics(metrics) {
  const summary = document.querySelector("#metrics-summary-table tbody");
  const differences = document.querySelector("#metrics-diffs-table tbody");
  summary.innerHTML = "";
  differences.innerHTML = "";
  for (const [arm, data] of Object.entries(metrics.arms || {})) {
    for (const [key, stats] of Object.entries(data.summary || {})) addRow(summary, [arm, key, number(stats.mean), number(stats.sd), stats.n]);
  }
  for (const [contrast, data] of Object.entries(metrics.paired_differences || {})) {
    for (const [key, stats] of Object.entries(data)) addRow(differences, [contrast, key, number(stats.mean), number(stats.sd), stats.ci95 ? stats.ci95.map(number).join(" to ") : "-"]);
  }
  if (!summary.children.length) addRow(summary, ["No summary metrics"]);
  if (!differences.children.length) addRow(differences, ["No paired differences"]);
  const notes = document.getElementById("metrics-notes");
  notes.textContent = Object.entries(metrics).filter(([key]) => !["arms", "paired_differences"].includes(key))
    .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`).join("\n");
}

async function executeCompare() {
  const a = document.getElementById("compare-run-a").value;
  const b = document.getElementById("compare-run-b").value;
  const metric = document.getElementById("compare-metric").value.trim();
  const body = document.querySelector("#compare-results tbody");
  if (!a || !b) return;
  try {
    let url = `/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`;
    if (metric) url += `&metric=${encodeURIComponent(metric)}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error("Comparison request failed");
    const data = await response.json();
    body.innerHTML = "";
    document.getElementById("compare-pairing").textContent = data.paired
      ? "Paired: run B minus run A, bootstrap 95% intervals" : `Unpaired: ${data.reason}; no paired difference or interval`;
    const armsA = data.run_a.metrics.arms || {}, armsB = data.run_b.metrics.arms || {};
    for (const arm of new Set([...Object.keys(armsA), ...Object.keys(armsB)])) {
      const sumA = armsA[arm]?.summary || {}, sumB = armsB[arm]?.summary || {};
      for (const key of new Set([...Object.keys(sumA), ...Object.keys(sumB)])) {
        const describe = (stats, rows) => stats
          ? `mean ${number(stats.mean)}, sd ${number(stats.sd)}, n ${stats.n}; seeds: ${(rows || []).map(row => `${row.seed}: ${number(row[key])}`).join(", ")}` : "unavailable";
        const diff = data.paired_differences[arm]?.[key];
        addRow(body, [`${arm}: ${key}`, describe(sumA[key], armsA[arm]?.per_seed), describe(sumB[key], armsB[arm]?.per_seed),
          diff ? `${number(diff.mean)} [${diff.ci95.map(number).join(", ")}]` : "unpaired / unavailable"]);
      }
    }
    if (!body.children.length) addRow(body, ["No matching metrics"]);
  } catch (error) { reportError("Compare failed:", error); }
}

/**
 * WebSocket Live Stream
 */
function toggleLiveStream() {
  const btn = document.getElementById("live-connect-btn");
  const indicator = document.getElementById("live-status-indicator");

  if (liveSocket) {
    liveSocket.close();
    liveSocket = null;
    btn.textContent = "Start Live Stream";
    indicator.textContent = "Disconnected";
    indicator.className = "live-status badge badge-idle";
    return;
  }

  if (!currentRunId || !currentArm) {
    alert("Select a run and arm first");
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/${encodeURIComponent(currentRunId)}/${encodeURIComponent(currentArm)}/${encodeURIComponent(currentSeed)}/${currentProbe}`;

  indicator.textContent = "Connecting...";
  indicator.className = "live-status badge badge-running";

  liveSocket = new WebSocket(wsUrl);
  const socket = liveSocket;
  const logEl = document.getElementById("live-packet-log");
  logEl.textContent = `Connecting to ${wsUrl}...\n`;

  liveSocket.onopen = () => {
    btn.textContent = "Stop Live Stream";
    indicator.textContent = "Streaming (Max 10 Hz)";
    indicator.className = "live-status badge badge-done";
  };

  liveSocket.onmessage = (event) => {
    if (socket !== liveSocket) return;
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "final") {
        logEl.textContent = `[FINAL] ${msg.message}\n` + logEl.textContent;
        indicator.textContent = `Finished: ${msg.state}`;
        indicator.className = "live-status badge badge-done";
        btn.textContent = "Start Live Stream";
        liveSocket = null;
        selectRun(currentRunId);
        return;
      }

      if (msg.type === "status") {
        document.getElementById("live-state-display").textContent = msg.status.state || "unknown";
        logEl.textContent = `[STATUS] ${JSON.stringify(msg.status)}\n` + logEl.textContent.slice(0, 1000);
        return;
      }
      // Update live stats
      const timeMs = msg.t_ms !== undefined ? msg.t_ms : (msg.line && msg.line.t_ms);
      const tick = msg.tick !== undefined ? msg.tick : (msg.line && msg.line.tick);
      if (timeMs !== undefined) {
        document.getElementById("live-time").textContent = `${timeMs.toFixed(1)} ms (tick ${tick})`;
      }

      const spikes = msg.spikes || (msg.line && msg.line.spikes) || [];
      document.getElementById("live-spikes-count").textContent = `${spikes.length} sampled spikes`;

      const state = (msg.status && msg.status.state) || "running";
      document.getElementById("live-state-display").textContent = state;

      logEl.textContent = `[tick ${tick}] ${JSON.stringify(msg.counts || {})}\n` + logEl.textContent.slice(0, 1000);
    } catch (e) {
      reportError("Live packet error:", e);
    }
  };

  liveSocket.onclose = () => {
    if (socket !== liveSocket) return;
    btn.textContent = "Start Live Stream";
    if (indicator.textContent.includes("Streaming")) {
      indicator.textContent = "Closed";
      indicator.className = "live-status badge badge-idle";
    }
    liveSocket = null;
  };

  liveSocket.onerror = (err) => {
    reportError("WebSocket error:", err);
    indicator.textContent = "Error";
    indicator.className = "live-status badge badge-failed";
  };
}

function clearCanvas(canvas) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function drawEmptyMessage(ctx, w, h, text) {
  ctx.fillStyle = "#8b949e";
  ctx.font = "italic 13px -apple-system, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(text, w / 2, h / 2);
  ctx.textAlign = "left";
}
