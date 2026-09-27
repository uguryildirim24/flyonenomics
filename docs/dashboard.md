# Dashboard

## Live activity view

WP13, SPEC section 3.9 and item 66; WP23, SPEC-P2 section 7 and item 75. The dashboard page carries a **Live Activity View** panel that shows neurons firing while a run executes and replays a finished run's live stream.

The live stream contract has two versions:

- **Version 2** (`live_version: 2`, WP23): each flushed NDJSON window carries `all_count` (the whole-network spike count accumulated from the full per-neuron count array, independent of the recorded populations), `window_ms` (the actual window duration, including a short final window flushed at close), `sizes` (the neuron count of each recorded population), and `block`/`stimulus` (the open-loop block index and label, or null). The runner passes the block through the `maybe_emit` call.
- **Version 1** (WP13): windows carry only per-population `counts`, which cover the recorded populations and may overlap.

What the view shows:

- **Spike count per live window**: the whole-network `all_count` for a version 2 stream, labelled "whole-network spikes/window". A version 1 stream keeps its chart under the partial label "sum over recorded populations (may overlap, not whole-network)" — never "whole-network".
- **Up to two population rates** on the same plain chart (right axis). For version 2 each rate is per-neuron Hz, `count / (size × window_ms / 1000)` from the stream's own `sizes` and `window_ms`, labelled "mean rate per neuron (Hz)". For version 1 each rate is the window count divided by the measured `t_ms` delta (the first window starts at recording tick 0), labelled "spikes per second, aggregate" — never per-neuron Hz. A **population picker** (two selects over the probe's recorded populations) chooses which populations are charted; the defaults prefer a `central` population, then a `DAN` population, then a deterministic fill.
- **Stage strip** for open-loop probes whose version 2 windows carry `block`: per recorded population, the current block's per-neuron rate minus the preceding ambient block's. Hidden when the stream carries no blocks or no preceding ambient block.
- **Sampled spike raster**: when the recorded windows carry per-neuron `spikes`, a raster of the recorded live sample, at most 64 neuron indices in first-seen order, x in relative ticks as recorded.

The picker bar of the run header shows the **substrate label** (`bare` or `rest:<id>`) from the manifest's `substrate_id`; manifests written before the Phase 2 identity fields fall back to the layer flags (`bare` when `background` is off).

Data rules: measured values only. No smoothing, no interpolation, no synthetic fluctuation. A constant stream renders flat. A probe without live data shows "no data".

Data path:

- `GET /api/runs/{run_id}/live/{arm}/{seed}/{probe}` returns the probe's flushed live NDJSON windows exactly as recorded (`windows`, `n_windows`, `malformed_lines`, `no_data`). This route is additive; no existing route payload changed.
- The existing websocket `/ws/{run_id}/{arm}/{seed}/{probe}` streams the same windows while a run executes and replays them from tick 0 for a finished run. The panel's **Watch Live** button opens this stream; selecting a probe loads the recorded windows through the HTTP route.

Implementation: `src/flyonenomics/dashboard/static/live-activity.js` (uPlot chart vendored under `static/vendor`, no CDN at runtime), panel markup in `static/index.html`, route in `src/flyonenomics/dashboard/app.py`, producer in `src/flyonenomics/orchestrator/live.py`. Tests: `tests/test_live_producer.py`, `tests/test_dashboard_live.py`, `tests/test_dashboard_live_v2.py`.
