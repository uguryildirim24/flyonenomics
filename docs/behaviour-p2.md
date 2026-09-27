# Phase 2 steering (WP20)

This document records the closed-loop steering code against SPEC-P2 sections 3.5, 3.6, 3.7 and 5.3.

## Why Phase 1 test 4.1 failed

Phase 1 injected the visual encoder at TuBu or ER. The sign check on the bare substrate with layers A and C on gave 0 Hz left-minus-right steering and 0 deg/s turn at every azimuth in seeds 1 to 3 at 100, 140 and 280 Hz (item 64). K3 had no closed-loop candidate. `data/behaviour-v0.1.yaml` froze the section 9.1 fallback. Phase 2 changes the injection site to photoreceptors on a rest substrate, subtracts a measured bias, and uses `steer_gain` instead of a per-azimuth omega threshold.

## Metrics (`behaviour/metrics.py`)

- `steer_gain` (Hz per degree): least-squares slope of bias-corrected block-mean `r_R − r_L` against fly-relative azimuth on stripe blocks with |azimuth| ≤ 60°.
- `fixation_retention`: window-mode fixation index on the distractor episode minus the index on [0, onset).
- `distractor_capture_hz`: bias-corrected `r_R − r_L` with the distractor on minus the same with it off.

Omega is `sign_steer × K_steer × ((r_R − r_L) − bias_hz)`. Bias is subtracted once. A constant offset does not change `steer_gain` or a two-block difference.

`model_probe_metrics` reads `step_min_mm` from the pinned behaviour file. It does not use `params metrics.step_min_mm` (review r13 seam).

## Stages (`behaviour/buridan.py`)

Order: bias, 4.1r-sign, K3r (or the TuBu chain), then 4.1r and 4.2r.

- Bias: ten-seed mean of `r_R − r_L` on a 10 s ambient probe that pins `base-v0.2`.
- Sign check: seeds 1 to 3, 13 azimuths, 1 s transition plus 2 s dwell. `sign_steer` is +1 when the `steer_gain` interval lies above zero and −1 when it lies below. An interval that includes zero is flat and starts section 3.7.
- K3r: `K_steer` in {1, 2, 4, 8, 16}. Objective `((FI_m − FI_c) / IQR_FI_c)² + ((dev_m − dev_c) / IQR_dev_c)²`. Camber proposes five seeds. The Mac reruns the three lowest-objective values at seeds 1 to 10 and ties to the lower `K_steer`.

Phase 1 `STAGE` names `sign` and `K3` stay in place. Phase 2 names live on `P2_STAGE`, which now carries the engine runners: `measure_bias`, `sign_check_p2`, `run_k3r`, `run_k3r_tubu`, `run_vtcal`, `run_4_1r`, `run_4_2r`, `run_4_8r` and `run_open_loop`. Each checks `p2_missing_dependencies(stage)`, runs its fixture through the orchestrator or a direct driver, scores with the evaluators above and writes its record under `validation/records/p2/`. Orchestrated records take `substrate_id`, engine model, platform and actual settle durations from their run manifests, reject mixed identities, and never infer those facts from the requested fixture.

- Record names follow the encoder in force (SPEC-P2 section 3.7). The photoreceptor path writes `bias`, `signcheck`, `k3r`, `4.1r`, `4.2r`; the TuBu path writes `bias-T`, `4.1r-T-sign`, `k3r-tubu`, `4.1r-T`, `4.2r-T`, so the TuBu chain never overwrites the evidence of why photoreceptors failed.
- `run_k3r` and `run_k3r_tubu` commit `data/behaviour-v0.2.yaml` with `controller: closed_loop`. `run_vtcal` uses `vpath-vtcal.json` with explicit TuBu injection, a null visual pin and the declared `r_vis_max` grid, measures the central-input populations (`TuBu`, `visual_projection`, `LAL_neurons`) and the ±45° Δsteer, runs ten seeds at the lowest passing rate, and commits `data/visual-v0.2.yaml` for `inject_at: TuBu` on a ten-seed pass.
- `run_open_loop` is section 3.7 step 3: it picks the encoder from the V-cal V3 passers or the VT-cal table, commits `data/visual-v0.2.yaml` for it, runs V1 and V3 (or V1-T) on those bytes, measures the bias, and commits `data/behaviour-v0.2.yaml` with `controller: open_loop` and null sign and gain. Photoreceptor runs use WP18's corrected `VisualProbe`: V1 keeps ipsilateral/contralateral values separate, and V3 records the full ambient stability screen, not just steering. Their records are `V1-open-loop.json` and `V3-open-loop.json`, preserving earlier V-cal evidence. The TuBu branch needs V1-T only, saved as `V1-T-open-loop.json`.
- `run_4_8r` is the section 3.5 sensitivity entry, class development. A direct driver applies the three within-eye permutations, five JITTER streams, `sigma_h` 0 and 20, `v_fwd` half and double, and histamine off to the 4.2r controls. Histamine off changes only photoreceptor connection rows back to scale 1 (their connection-file sign), preserving every other rest-substrate scale factor. The record includes the direct engine model, platform and per-seed settle results, and compares histamine off with the canonical 4.2r conclusion rather than a permuted arm.
- `scripts/camber/k3r.py --run` runs the primary wave (bias, 4.1r-sign, K3r, 4.1r, 4.2r) and refuses until the inputs land; `--stages K3r-T,VT-cal,4.8r,open-loop` selects others and `--workers N` sets the per-run worker count (`FLYONENOMICS_P2_WORKERS`, default one). `WAVE` in `behaviour/buridan.py` names the primary order. A wave stops on failure or refusal and checkpoints after writing a visual or behaviour configuration, so a later invocation runs against committed bytes. Scores read the run's arena and rates tables: `open_loop_blocks` and `open_loop_population_blocks` take dwell-only block means, and `model_probe_metrics` scores Buridan runs.

## Declared substrate (item 122)

Every WP20 entry binds the declared resting substrate through the one reader in `behaviour/visual_calibration.py`; WP20 writes no second reader. `p2_missing_dependencies(stage)` names item 122's records, `data/drive-v0.2.yaml` (item 123) and `data/dopamine-v0.2.yaml` (item 125). Visual producers (`VT-cal` and `open-loop`) require a recorded photoreceptor failure instead of `data/visual-v0.2.yaml`; the visual file is their output, not an input. Open loop additionally requires a recorded TuBu failure, so a three-seed VT-cal candidate—or a ten-seed pass—cannot skip step 2. Every consumer and the default dependency query still require the visual file. The CLI checks the first requested stage, then each runner checks its own inputs, so a producer can precede consumers without a circular prerequisite. Q-rest is never a WP20 input after item 122. `validation/level4_p2.py` sets each entry's identity `substrate_id` to the declared drive's `rest:<16 hex>` tag and records `declared_substrate` and `declared_drive` in `measured`. `scripts/camber/k3r.py --plan` prints the same substrate id, the declared substrate and the missing list.

## Fallback (`behaviour/visual_status.py`)

The state machine classifies constructed `visual-status.json` records. It does not write a committed status.

1. Photoreceptor failure: no V-cal selection, V1 or V3 fail on committed bytes, a flat sign check, or a 4.1r or 4.2r failure. Item 122 closed the rest search and item 123 closed WP19, so the former next-candidate retry is removed and the machine proceeds directly to step 2.
2. TuBu path: VT-cal, bias-T, 4.1r-T-sign, K3r-T, 4.1r-T, 4.2r-T. Pass gives status "TuBu closed loop".
3. Open loop if the TuBu path fails. Encoder is photoreceptors at the V3-passing rate with the largest |mean Δsteer|, else TuBu at the VT-cal value with the largest |mean Δsteer|. Behaviour commits with `controller: open_loop`.

WP18 owns the V-cal commit of `data/visual-v0.2.yaml`. WP20 owns every visual and behaviour commit under steps 2 and 3.

The first t-0013 VT-cal attempt is **invalid evidence**: the reused WP18 fixture
resolved `inject_at: photoreceptors` despite TuBu grid metadata. Its five runs
(481 actual brain-seconds; 9259.90 s wall) remain in `camber-runs/wp20/runs/`
and `camber-runs/wp20/vtcal.log` for audit, but its `vtcal.json` and premature
step-3 visual configuration were removed. The immediately following open-loop
job was stopped. The corrected fixture and constructed topology regression
explicitly require TuBu, no visual pin, and the requested input rate; no
scientific conclusion is drawn from the rejected run.

## Oracle wave, 2026-09-20 (t-0013)

**Final visual status: open loop**, section 3.7 step 3, on
`rest:379cc4cc9030cdd1`. Corrected TuBu injection produces a central-input
response, but the lowest three-seed candidate (70 Hz) does not retain a
nonzero steering interval on ten seeds. The selected final encoder is
photoreceptors at 150 Hz, the earlier V3-passing rate with largest |mean
Δsteer|. `data/behaviour-v0.2.yaml` has `controller: open_loop`, null sign and
gain, and the measured bias below. This is not closed-loop steering success.

| TuBu input Hz | seeds | Δsteer Hz, 95% seed-bootstrap interval |
|---:|---:|---:|
| 40 | 3 | −0.3889 [−3.1667, 2.1667] |
| 70 | 3 | −1.6667 [−2.5000, −0.5000] |
| 100 | 3 | −0.5556 [−2.0000, 0.3333] |
| 150 | 3 | −3.6111 [−7.1667, −1.1667] |
| 280 | 3 | −1.2778 [−4.8333, 1.8333] |
| 70 | 10 | −0.6000 [−1.8000, 0.8833] |

At 70 Hz on ten seeds, TuBu's mean stripe-minus-ambient change is
9.3770 Hz [9.3243, 9.4238]. Visual-projection and LAL mean changes are
0.0000952 Hz [−0.0000662, 0.0002546] and 0.003809 Hz [−0.018221, 0.025868].
No new numerical acceptance rule is inferred from these values.

On the committed step-3 visual bytes:
- V1, ten seeds: lamina break remains; R1-6 ipsilateral change −14.5035 Hz
  [−14.5496, −14.4574]; L1/L2 and the intervening medulla/lobula populations
  remain exactly zero on both sides. Δsteer is 0.7833 Hz [−0.6500, 2.3667].
- V3, three seeds: central 4.8281 Hz [4.8245, 4.8346], DAN 0.8216 Hz
  [0.8150, 0.8327], KC 0.08717 Hz [0.08455, 0.08855]. No ignition;
  F 1.1861–1.2160, stability ratio 0.99762–0.99876. The specified screen passes.
- Ambient bias, ten seeds: 1.8975 Hz [1.4318, 2.4465].

Valid work: VT-cal 800 brain-seconds / 11,411.94 s wall; step 3
346 brain-seconds / 4,196.28 s wall. Total 1,146 brain-seconds / 4 h 20 min
8 s stage wall-clock, excluding collection, gates and rejected compute.
VT-cal and bias settled for 3 s per probe (the first estimate assumed 2);
final V1/V3 used their fixture's 2 s. No bias-T/sign-T/K3r-T/4.1r-T/4.2r-T
runs were warranted after the ten-seed VT-cal failure.

The box was capped at eight workers, with BLAS/OMP threads capped at one.
Records retain **linux-aarch64**, engine `lif`; this remains development
measurement evidence because VT-cal failed before the matching-layers stages.
`validation/records/p2/wp20-wave.json` binds all nine valid runs to raw
experiment/manifest hashes and verified source-scope mappings. It reports
pinned input snapshot blobs separately from the manifests' runtime input
maps, which are empty. Source snapshots were not relabelled as Mac runs.
Raw trees and the reproduction collector are under `camber-runs/wp20/`.
Final records are `vtcal.json`, `V1-open-loop.json`, `V3-open-loop.json`,
`bias-open-loop.json`, `open-loop.json` and `visual-status.json` in
`validation/records/p2/`. No t-0013 process remains on the box.

## Fixtures

`data/experiments/p2/{bias,signcheck,k3r,k3r-tubu,buridan-controls}.json` are schema 1.3. `k3r.json` and `k3r-tubu.json` are K-grid fixtures. They take `sign_steer`, `bias_hz` and the visual blob id from metadata after those stages run, and one `K_steer` grid point per run. `buridan-controls.json` holds three experiments (`stripes_on`, `stripes_off`, `encoder_off`). Paired arms cannot differ in stripe or encoder params, so the three controls cannot share one `Experiment`. `scripts/camber/k3r.py --plan` prints the section 6.3 credits. `--run` executes the wave once the dependencies land.

WP20 Camber cap is 4 credits at ρ = 1 (about 7 at ρ = 1.76). Ask `CREDITS w20` before any Camber job.

## Evaluators (`validation/level4_p2.py`)

4.0c, bias, 4.1r-sign, K3r, 4.1r, 4.2r, 4.8r, their retained -T calibration or consistency variants, VT-cal and V1-T run on constructed tables. Entries 4.4r to 4.7r and 4.4r-T to 4.7r-T have the terminal outcome `not run`: SPEC-P2 item 144 skips the full open-loop P-screen that would have supplied their predictions. They have no constructed result, are not waiting and are never filled from the measured power pilot. Engine execution for retained entries waits on WP18's V-cal and item 125's dopamine file on item 122's declared substrate.
