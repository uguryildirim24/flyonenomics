# Frozen CUDA GABA dose replication — item 163

Frozen on 2026-09-26 after the pre-freeze checks below and before any dose outcome submission. The commit containing this plan and SPEC-P2 §10 item 163 is the outcome source commit recorded by every receipt. The GPU kernels and model parameters are unchanged.

## Design

- MaleCNS v1.0, 162,517 neurons; rest substrate `rest:ed9b0a469d7a6b77`.
- Injected input at TuBu; the fly does not see. Dark background only, no courtship stimulation. Free dopamine, updated every 10 ms.
- Seeds 501–510, master seed 20260912 via the existing `brian_seed` function. Same numerical seeds as item 162, not the same random streams across engines. Pair doses only with controls from their own engine.
- Block θ = 0.10, 0.25, 0.50, 0.75, 0.90, 1.00; boost φ = 0.25, 0.50, 1.00, 2.00; rescue ψ = 0.50, 1.00, 2.00 at θ = 0.75.
- Reuse `scripts/circuit_tour.py::dose_conditions`, `dose_scales`, and `build`'s exact row-class composition: `modified = baseline_scale.copy(); modified[row_classes == 'GABA'] *= gaba; modified[row_classes == 'Glu'] *= glu`. No rederived class mapping. Unknown negative rows retain baseline scaling.
- `CUDAEngine.set_weight_scale` takes a shared `(n_syn,)` float32 array; a batch therefore contains one condition and ten seeds. Disconnection masks are applied after scaling and are empty for every dose, including full block.
- 13 batches × 10 seeds × 12 seconds: 2 s settle + 10 s measurement, 10 ms chunks, 0.1 ms integration. L4 only; `MODAL_PROFILE=flyonenomics` on every Modal command. No shared-box work.
- Existing GPU controls: `<local-project-root>/<reference-checkout>/camber-runs/cuda-circuit/outcomes/seed-{501..510}-control.{json,npz}`, bound by `validation/records/p2/male-cuda-receipts.json`; source Modal volume `flyo-malecns-circuit`. Control rate is ON+OFF counts / 10 s. Synchrony uses that same measured 10 s, not settling.

## Pre-freeze checks (two separate one-seed L4 calls)

A short cloud call still needs the complete 12 brain-seconds to compare with the archived counts. These are reproductions, not the dose outcomes. No additional dose was examined before freeze.

| Check, seed 501 | New / archived total spikes | Differing neurons | Maximum absolute count difference |
|---|---:|---:|---:|
| GABA scale 1.0, control ON | 1,121,398 / 1,121,398 | 0 | 0 |
| GABA scale 1.0, control OFF | 1,126,427 / 1,126,427 | 0 | 0 |
| GABA scale 0.0, full measured window vs GPU off-gaba | 23,234,104 / 23,234,104 | 0 | 0 |

The control count-archive SHA-256 is `8a56ac7c4eb31f4214562328017dbce1ca982b7ebf9676a68a050985e5c7b055` for both copies; full block/off-gaba is `c662234b9fd75d5c45a7c96b272282278b6d3e2dea800d4b8905752428697419` for both. All neuron counts, including zeros, were compared. No discrepancy needs explaining. This measured equivalence does not assert that class scaling and annotation-based disconnection are interchangeable for every substrate.

Apps: `ap-CDTZ85GbDvpFLHDRKYaeuA` (control), `ap-EFvyHhqMxHRuK2hjkN7Y3D` (zero scale). Local archives: `camber-runs/cuda-circuit/fused-reproduce-1790432220611363000-0` and `camber-runs/cuda-circuit/fused-reproduce-1790432537679168000-0`. The receipt file records both submissions, their source diffs, runtime and metering. At freeze: $0.12305086 metered, $0.15613639 conservative elapsed-time accounting; $0.2044384 projected combined. Both apps are stopped. `modal app list` also displays recently stopped apps; zero active apps is the cleanup check, not removal of billing history.

## Locked expectations

Copied from item 162:

1. Outside-sensory firing increases monotonically with θ, reaching the item 158 GABA-off endpoint at θ = 1.
2. The network half-effect point is below θ = 0.5 and its Hill slope is above 1 (network amplification relative to a slope-1 receptor occupancy curve).
3. The maximum 1 ms spike fraction b and Fano factor rise sharply across a block step, not smoothly; central brain tips before optic lobes.
4. Firing decreases monotonically with φ, less steeply than the block rise because injected drive sets a floor.
5. Increasing ψ at θ = 0.75 lowers activity toward control, partially rather than fully, since the two brakes act on different neurons.

Replication addition: put the GPU Hill slope, half-effect and rescue fractions beside Brian2, with intervals; report interval overlap as a finding, not a pass criterion. Expectation 1 refers to this engine's own tour GABA-off endpoint. Assess matching / opposite / unclear; split components where the evidence differs. No fit to a drug concentration on the boost or rescue axes.

## Analysis fixed before outcomes

`analyse(raw=GPU_DOSES, out=GPU_SUMMARY, reference=GPU_CONTROLS)` from **unchanged** `scripts/circuit_tour_dose.py`, SHA-256 `17207df2d81852b6333b1dc741ef1d4c56df85f4325227dc04f58a46730de93b`. The wrapper checks archive hashes, connects the downloaded files without copying them, and passes explicit paths. GPU doses use `counts_measure`, controls `counts_on` + `counts_off`; no loader adaptation is needed.

Keep the existing 10,000 paired whole-seed rate/rescue draws, 500 whole-seed Hill draws, fixed resampling seeds, least-squares bounds/identifiability handling and interpolated half of the observed endpoint. No new hypothesis tests or engine-agreement cutoff. A 95% interval containing zero is **no detected difference**, not equality. Rate and rescue effects pair seeds within engine only. Across engines, compare curve shapes, point estimates and intervals, never spike trains.

Both workers use `FanoAccumulator` on every 1 ms histogram bin outside settling. Thus b = maximum spikes in one 1 ms bin / 162,517, F = variance of population counts across the 10,000 bins / mean bin count. The 10 ms chunk interface does not coarsen these statistics. F is not a per-neuron across-trial Fano factor. CPU analysis source: `<local-project-root>/<reference-checkout>/camber-runs/circuit-tour/dose-summary/analysis.json`.

The comparison record includes full per-group analysis, raw hashes, pre-freeze comparisons, control rates and descriptive interval-overlap flags. Results prose and figures have no development IDs, hashes, seed labels or archive paths. `src/flyonenomics/engine/cuda_tick.cu` remains SHA-256 `6ff6e296990a83a391faa4068b5358f78582ba6a63101340402bf82cb59a5197`. If a kernel change becomes necessary, stop rather than changing the frozen engine.

## Budget and commands

Separate ledger `male-cuda-dose-receipts.json`, cap **$5 for this entire replication**, including checks. At $0.80/L4-hour plus requested CPU/RAM, a conservative 300 s build + 600 s stepping allowance per batch projects **$0.255548 per batch, $3.322124 for all 13** using `scripts/modal/cost.py` for CPU/memory and adding GPU. This is an estimate, not a scientific pass line. Each call reserves a 900 s timeout plus 600 s startup allowance ($0.426083); process-locked reservations include concurrent calls. Every submission prints its projection and checks Modal workspace billing against Rolf's $30 band. Outcomes may submit in up to three concurrent single-condition apps; each app ends immediately after its call. Per-app metering is reconciled before closeout.

```sh
uv sync --frozen
uv pip install --python .venv/bin/python modal==1.5.4 fast-simplification==0.1.13
export FLYONENOMICS_CACHE_DIR=<local-project-root>/.cache
export PYTHONDONTWRITEBYTECODE=1
MODAL_PROFILE=flyonenomics .venv/bin/python scripts/modal/cuda_driver.py reproduce --condition control
MODAL_PROFILE=flyonenomics .venv/bin/python scripts/modal/cuda_driver.py reproduce --condition block-1.00
.venv/bin/python scripts/cuda_dose.py prefreeze
# Commit this plan and SPEC-P2 item 163 before proceeding.
for offset in 0 10 20 30 40 50 60 70 80 90 100 110 120; do
  MODAL_PROFILE=flyonenomics .venv/bin/python scripts/modal/cuda_driver.py dose --batch 10 --offset "$offset" --chunk-ms 10 || break
done
.venv/bin/python scripts/cuda_dose.py analyse --brian-analysis <local-project-root>/<reference-checkout>/camber-runs/circuit-tour/dose-summary/analysis.json
MODAL_PROFILE=flyonenomics .venv/bin/python scripts/modal/cuda_billing.py --dose
MODAL_PROFILE=flyonenomics modal app list --json
```

Use existing archives for analysis reproduction, rather than rerunning paid calls or overwriting completed outcomes. Raw data stay in this worktree's ignored `camber-runs/`. Final records: this plan, `male-cuda-dose-comparison.json`, `male-cuda-dose-cost.json`, `male-cuda-dose-receipts.json`. Checks: syntax preflight, static-IO gate and `git diff --check`; leave the full pytest gate to the pile review.
