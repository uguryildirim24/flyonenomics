# Visual path Phase 2 (WP18)

This document records the photoreceptor encoder and the V0 to V-cal entries against SPEC-P2 sections 3.1 to 3.4.

## Encoder

`PhotoreceptorEncoder` in `behaviour/encoder.py` writes Poisson input rates on `R1_6`. The wall is bright (L = 1) except where a dark bar covers it. Each photoreceptor has a Gaussian acceptance of width `vis.pr_acceptance_deg` 5°.

```
u_k(φ) = ½ [ erf((d(φ, a_k) + w_k/2) / (√2 σ)) − erf((d(φ, a_k) − w_k/2) / (√2 σ)) ]
L(φ)   = max(0, 1 − Σ_k c_k u_k(φ))
rate_i = min(vis.r_max, r_dark + (r_light − r_dark) × L(φ_i))
```

`stripes: false` and `encoder: "off"` both give ambient light (L = 1). Darkness is `stimulus: "dark"`. R7 and R8 get no drive (open question 10).

WP15 dispatches this class when `inject_at` is `photoreceptors` through `encoder_class_for`. Arena still owns the factory call. Preferred azimuths load from the WP14 retinotopy table by root_id. Permutation k is the WP16 within-eye shuffle helper, not the Phase 1 full permutation.

## Rank azimuths

SPEC-P2 section 3.2 maps rank r of n to `(r + 0.5) / n × 150°` in the right eye and the negative of that in the left eye. That map lives in `midpoint_rank_azimuths`. WP14 writes the table into `populations-v0.2.yaml` under `retinotopy.types` with keys `R1_6` and `L2`, each holding `root_ids` and `azimuth_deg`. V0(a) and V0(b) join annotation `side`, `pos_z` and xyz onto those root ids.

## V0

V0 is class canonical and uses no engine.

- (a) Per eye, R1-6 azimuth is strictly monotone in z rank and lies in (0°, 150°) or (−150°, 0°). This uses the WP14 committed table plus annotation `pos_z`.
- (b) SPEC-P2 question 15: record Spearman ρ of propagated L2 azimuth against the rank rule on L2 `pos_z`, and against the rank along each eye's first principal axis of L2 positions, signed to agree with R1-6 z order. If the principal-axis ρ is at least 0.9, V0(b) uses that axis. Otherwise V0(b) is recorded, not gating.
- (c) On a constructed heading and bar set, encoder rates equal the section 3.2 formula to relative error 1e-12. The reference copy in `validation/levelv.py` uses `math.erf`. The production path uses `scipy.special.erf`.

WP14 measured z-rank ρ 0.673 (left) and 0.676 (right), with L2 median column spread 3.0°. WP18 measured principal-axis ρ 0.471 (left) and 0.291 (right) on L2 `pos_*` terminals. V0(b) is recorded, not gating. Review r15 decides.

## V1, V2, V3 and V-cal

Item 122 (Rolf, 2026-09-19) declares the sensory-only arm at 1.0 mV
(`1.0-4.0-0.0-False-100-1.0-kc-6.0-sens`, item 110 arm A; facts in item 121)
as the Phase 2 resting substrate and closes the rest search. V0, V1, V3 and
V-cal bind to that declared unit instead of waiting on WP17's shortlist or
WP19's Q-rest. `behaviour/visual_calibration.py` reads the committed rest
records `validation/records/p2/rest-T3e-decision.json` and
`rest-T3e-freeze-partial.json`, checks the candidate id, and exposes
`declared_substrate()`. R3's table is recorded with that unit as rank 1 and its
recorded screen and freeze facts; its V3 and three-seed V1 cells now contain
the rerun below. R3 passes only if a rate passes both, not merely because its
cells are filled.

The declared unit's drive document `data/drive-v0.2.yaml` is the item 123
canonical configuration: `g_gaba` 1.0, `g_glu` 4.0, `g_gaba_kc` 6.0,
`n_bg` 100, `sigma_th` 0, background into the sensory group only at 1.0 mV,
and `lif`. Its tag is `rest:379cc4cc9030cdd1`. The run also uses item 125's
canonical `data/dopamine-v0.2.yaml`. V0, V1, V3 and V-cal bind the drive tag
as their identity `substrate_id`.

`diagnostics/visual_path.py` v2 adds dark and ambient conditions, histamine-scale
records, column subsets, circular spread and V1/V2 statistics on constructed
per-seed differences.

Fixtures live in `data/experiments/p2/vpath-*.json` as schema 1.3 documents,
pinning `drive_version: v0.2`.

`behaviour/visual_calibration.py` registers `STAGE` `R3` for WP15 `--phase 2`. `V-cal` stays on
`P2_STAGE` because it is not in `ORDER_P2`.

On selection, V-cal writes `data/visual-v0.2.yaml` with the photoreceptor
settings and the V-cal record SHA-256. Those bytes must be committed before
the frozen ten-seed V1 and three-seed V3. This rerun made no selection and
wrote no visual configuration.

## Oracle rerun, 2026-09-19 (t-0010)

Substrate `rest:379cc4cc9030cdd1`, wild type, vehicle, background/A/C on.
Each rate used seeds 1–3, 2 s ambient settle, V3's 10 s ambient recording,
and V1's four 1 s transition + 3 s dwell blocks. The stripe width is the
pinned 5°, not the rejected attempt's 15°.

**V-cal: no selection. V3 meets the specified screen at every rate. V1
breaks at the lamina at every rate.** Stage 2 was not run because stage 1
already had V3 passes. No ten-seed selection/freeze was warranted: the
committed `V1.json` is explicitly the **three-seed V-cal screen**, at 150 Hz,
the V3-passing rate with the largest absolute mean Δsteer. Item 126 sends
this outcome to section 3.7's TuBu path, not another resting candidate.

Rates below are Hz; intervals are 95% seed-bootstrap intervals, not biological
benchmarks. The visual screen's existing numerical criteria were not retuned.

| light input | central | DAN | KC | R1-6 ipsi stripe − ambient | Δsteer [95% interval] |
|---:|---:|---:|---:|---:|---:|
| 50 | 4.8315 | 0.8210 | 0.0877 | −8.6168 | 1.1667 [−2.0000, 4.3333] |
| 100 | 4.8326 | 0.8171 | 0.0904 | −12.3868 | 2.1111 [−0.5000, 3.5000] |
| 150 | 4.8281 | 0.8216 | 0.0872 | −14.5610 | 2.6111 [1.0000, 4.5000] |
| 300 | 4.8298 | 0.8082 | 0.0900 | −16.7769 | 1.3333 [0.3333, 2.8333] |

V3 F ranges from 1.0435 to 1.4856; max 1 ms bin fraction is 0.0099251;
stability ratios range from 0.99504 to 1.00615; no seed ignited. Raw ambient
right-minus-left steering is recorded separately in every V3 row.

L1, L2, Mi1, Tm1/2/3/4/9, T5, LC10, LC_all, LPLC, MeTu and TuBu have
zero stripe-minus-ambient change on both sides at all four rates. Small
central/steering changes do not establish an unbroken visual pathway.
At 150 Hz, R1-6's contralateral change is −0.09014 Hz
[−0.12036, −0.04325], beside the ipsilateral −14.56096 Hz
[−14.62278, −14.52688]. Records retain both bars individually, both sides,
and the exact engine-index subsets; broad-spread types use annotation-side
populations, never a bilateral substitute.

### What changed from the rejected attempt

At the same 50 Hz rate, the retinal change is −8.6168 rather than −25.5539 Hz.
Across 100/150/300 Hz it is −12.3868/−14.5610/−16.7769 rather than
−40.6053/−49.4831/−62.8742 Hz. The lamina break remains. The failed-screen
reporting rate changes from 50 to 150 Hz. V3's four rate-level checks are
numerically identical to the first attempt.

The rerun loads v0.2 dopamine through the orchestrator and updates pools
normally, removing the old driver's reference-pool clamp. All 24 settles
end at 0.020 µM; recording-window fixed-point gaps are at most
7.05e−16 µM. Thus the corrected dopamine setup produces no observed ambient
change here. This is a combined protocol correction, not a factorial test
isolating stripe width from dopamine or population scoring.

### Execution and evidence

`behaviour/visual_run.py` observes the real `open_loop_steering` chunks in
`orchestrator/workers.py`; there is no separate engine builder. The runner
owns topology, pins, seeds, A/C updates, recording and execution manifests.
`scripts/run_visual_path.py` schedules rates, scores them and writes records.

- Measured records: `validation/records/p2/{R3,V1,V3,visual-vcal}.json`.
- Raw experiments, manifests, dependency logs, spike/rate tables and per-rate
  `execution.json`: `camber-runs/wp18/vcal/stage1/` (git-ignored, on this Mac
  and in Oracle `~/flyonenomics-t-0010`). Failed pre-simulation launch trees
  are retained but not referenced as evidence.
- 24 jobs, **360 brain-seconds**, **2298.19 s wall time (38 min 18 s)**,
  up to 12 workers. Oracle source snapshot
  `1936526f3af931411bb2a675bc76f88f8378f8ea` has the same execution source
  scope as Mac `7226912`: `git:c9a4d4001f2439d15112939a57090273cd8c2015eedd05612b5e273e2426a661`.
  Later changes only expose the finished records and adjust their tests/docs.
- Every constituent execution records its actual `lif` engine, input blob
  ids, resolved protocol, code scope and **linux-aarch64** platform. V-cal
  retains all eight identities; its top-level identity is labelled as the
  first constituent, not a fictitious single grid execution.
- These are **development/measured evidence** because they are grid screens,
  not post-freeze matching-layers entries, and V-cal made no selection.
  No Mac identity is synthesized for an Oracle measurement.

## Diagnostic CLI

`scripts/diagnose_visual_path.py` keeps the WP10 smoke, tiny, stripe and full paths. `--v2-formula` writes constructed photoreceptor rates with no engine.
