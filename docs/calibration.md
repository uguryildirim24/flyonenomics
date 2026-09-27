Partial-delivery predicate met at 119d533; main predicate not met: closed-loop not achieved because the sign curve stayed flat at 280 Hz.

# Calibration log K1, K2, sign check, K3 (SPEC sections 3.3, 3.4, 3.5, 7.1)

Historical absolute cache paths in this log are shown as portable examples. The 2026 runs used a shared cache, not necessarily the current checkout's `.cache`; commands below were not rerun when paths were normalized.

## WP9 final bare-substrate sign check and K3 outcome

The historical `scripts/calibrate.py` run exited 0 on 2026-09-13 using a shared cache. A portable rerun command is `FLYONENOMICS_CACHE_DIR="$PWD/.cache" uv run python scripts/calibrate.py` (after provisioning the cache). K1 returned the item-47 skip; K2/Q replayed the frozen, qualified `data/dopamine-v0.1.yaml` without changing it. The sign check used `background: false`, `dopamine_A: true`, `transporter_C: true`, `dan_fast_synapses: retain`, inhibitory ratio 1, wild type, seeds 1–3, and the eleven −150° to +150° azimuths. Each azimuth had 600 recorded dwell chunks across the three seeds, excluding the one-second transition per seed. The `Params` class supplied the 300 Hz encoder cap without changing `data/params-v0.1.yaml`.

| `r_vis_max` (Hz) | Run ID | Mean right-minus-left steering rate at every azimuth (Hz) | Mean turn rate at every azimuth (deg/s) | Wall time (s) |
|---:|---|---:|---:|---:|
| 100 | `20260913T204503.718326Z-7e627180` | 0 | 0 | 1335.134 |
| 140 | `20260913T210720.742900Z-275a5789` | 0 | 0 | 1123.906 |
| 280 | `20260913T213006.976642Z-f41b1785` | 0 | 0 | 1135.397 |

The 100, 140, then 280 Hz order stopped at the specified cap-side value. The sign remains +1; reversing it cannot create a steering response from zero rates. `data/behaviour-v0.1.yaml` freezes `K_steer: 4`, `r_vis_max: 280`, `sigma_vis: 20`, the sign, speed, split hashes, seeds and source versions with `qualified: false`. These constants are fallback settings, not a K3-calibrated winner. K3 is recorded `unavailable` with zero candidate runs because the section 9.1 fallback applies after the flat 280 Hz curve. The Brembs holdout remains sealed.

SPEC section 11 items 43–58 supersede the earlier ratio-4 resting assumption. The ratio-4 table is a development candidate: it misses five K1 targets and abolishes the background-off sugar reflex. Review r5 withdrew the initial 10 s Fano objection after measuring the required 2 s settle; the three-seed adjacent-weight resting criterion remains unmeasured. Phase 1 calibrates the bare substrate (`background: false`, inhibitory ratio 1). `scripts/calibrate.py` records K1 as skipped; K2 measured zero tonic DAN rate and Q follows on free pools.

## K1 background weights

**Skipped for Phase 1 (item 47).** No frozen `drive-v0.1.yaml` is written from the ratio-4 development candidate. `data/drive-dev.yaml` remains unqualified. `run_k1()` returns the recorded non-blocking reason `item 47: no frozen drive on the bare substrate`.

## K1-dev provisional base-array drive (WP3)

Run `uv run python -m flyonenomics.drive.background --dev` with
`FLYONENOMICS_CACHE_DIR="$PWD/.cache"` set (or an absolute shared-cache path). This
is a development calibration only: the threshold is `lif.v_th` for every
neuron, gain is one, and layer A is off. The K1 stage in `scripts/calibrate.py`
is now WP5's recorded item-47 skip. This drive cannot
satisfy the background component map or qualification Q.
The committed calibration runner rejects stage names outside its fixed order,
so `K1-dev` is exposed as `DEV_STAGE` and through this CLI rather than in
its `STAGE` discovery mapping.

In attempt 2, each candidate restores `initial`, sets the same ENGINE seed derived from
`(S, s, k) = (20260912, 0, 0)` for paired candidate comparisons, and writes
copies of the unchanged threshold and gain arrays,
settles for 2 brain seconds, and records 5 brain seconds in 10 ms chunks. A
tripped synchrony detector is infeasible. A group with no measured spike
receives a one-spike-equivalent rate floor for the log objective, to keep the
numerical search finite; this approximates the specified zero-rate infinite
penalty. This floor is not a measured rate.

Attempt 1 derived a different ENGINE seed from each evaluation index and used
0.5 mV initially, then 0.65, 0.8, and 0.95 mV per group in
sequence. It was stopped after 20 completed evaluations on the orchestrator's
request. Full per-evaluation JSON is in `.reports/k1-attempt1.log` (the final
Brian2 traceback followed the interrupt during evaluation 21, not a completed
evaluation). An abridged log follows; weights not mentioned remained at the
last accepted coordinates, and rates are Hz.

| Eval | Candidate change | DAN | KC | central | F | Objective |
|---:|---|---:|---:|---:|---:|---:|
| 1 | all nonsensory 0.5 mV | 0 | 0 | 0 | unknown | 917.78 |
| 4 | DAN 0.95 | 0.105 | 0 | approximately 0 | 1.03 | 807.65 |
| 10 | KC 0.95 | 0.078 | 0.047 | 0.001 | 1.05 | 643.68 |
| 13 | ascending 0.95 | 47.35 | 47.92 | 12.19 | 2.65 | 104.46 |
| 20 | endocrine 0.65 | 47.98 | 48.13 | 15.04 | 2.80 | 78.51 |

The drop in the floored-log objective after evaluation 13 is misleading for
development: one ascending step ignited a recurrent high-rate state. DAN was
nearly 10 times its 5 Hz target, KC nearly 500 times its 0.1 Hz target, and
central 15 times its 1 Hz target at evaluation 20. Fano remained just below
its threshold, so Fano alone did not make that state useful. Attempt 1 wrote
no drive file.

Attempt 2 brackets the collective transition first: eight geometrically
spaced common weights from 0.5 to 0.95 mV across all nonsensory groups, then
up to four geometric bisections between the largest low-rate and first higher
rejected common scale. It selects the largest synchrony-clear, low-rate scale with central within a
factor of two of target, or the largest low-rate scale if none is that close.
For this provisional search, a candidate is labelled ignited and rejected if
central, DAN, or KC exceeds twice its target, even if Fano is clear. It then
tests a 0.05 mV step in both directions for each group, prioritising DAN, KC,
and central, and spends remaining evaluations on small focused steps toward
those three targets, halving a step after rejection. The cap is 40 evaluations
for this new run. The best feasible low-rate point is written even if target
misses remain; no hot state is eligible. The complete attempt 2 log is
`.reports/k1-attempt2.log` (renamed when WP3b attempt 3 began).

Attempt 2 completed all 40 evaluations in 5,065.99 wall seconds (84.43
minutes), with objective 676.628. The retained evaluation was number 35:
`F = 1.02879`, maximum 1 ms bin fraction `0.00002164`, status clear. All
eleven targeted groups missed their factor-of-two bounds. The exact
common-scale edge under this seed was 0.7773437 mV (near-silent and clear)
versus 0.7818114 mV (DAN 43.18 Hz, KC 45.61 Hz, central 13.59 Hz; rejected
as ignited). This is evidence for a collective transition under the base
arrays, not a qualified calibration. The complete JSON log is
`.reports/k1-attempt2.log`.

| Group | Neurons | Target Hz | Retained weight mV | Measured Hz |
|---|---:|---:|---:|---:|
| DAN | 361 | 5 | 0.877344 | 0.011080 |
| ER | 278 | 2 | 0.827344 | 0.001439 |
| KC | 5,177 | 0.1 | 0.727344 | 0 |
| ascending | 2,317 | 1 | 0.827344 | 0.000345 |
| central | 26,568 | 1 | 0.777344 | 0.000060 |
| descending | 1,299 | 1 | 0.777344 | 0 |
| endocrine | 76 | 1 | 0.727344 | 0 |
| motor | 106 | 0.5 | 0.827344 | 0.001887 |
| optic | 77,529 | 1 | 0.827344 | 0.000893 |
| sensory | 16,351 | none | 0 | 0 |
| visual_centrifugal | 524 | 1 | 0.727344 | 0 |
| visual_projection | 8,053 | 1 | 0.727344 | 0 |

An abridged attempt-2 log shows the boundary and retained-candidate logic
(rates are Hz; `—` means the candidate was rejected rather than scored):

| Eval | Change or phase | DAN | KC | central | F | Objective |
|---:|---|---:|---:|---:|---:|---:|
| 1 | common 0.5 mV | 0 | 0 | 0 | unknown | 917.78 |
| 5 | common 0.7215 mV | 0 | 0 | 0 | unknown | 917.78 |
| 6 | common 0.7908 mV, ignited | 23.15 | 24.37 | 7.27 | 310.53 | — |
| 11 | common 0.78181 mV, ignited | 43.18 | 45.61 | 13.59 | 2.95 | — |
| 12 | common 0.77734 mV, clear edge | 0 | 0 | 0.000090 | 0.99 | 802.96 |
| 16 | KC up, ignited | 44.42 | 46.29 | 13.60 | 2.95 | — |
| 18 | central up, ignited | 43.32 | 44.82 | 13.84 | 2.94 | — |
| 22 | ascending up, low side | 0.0011 | 0 | 0.000075 | 1.04 | 738.99 |
| 30 | optic up, low side | 0 | 0 | 0.000045 | 1.04 | 720.46 |
| 35 | DAN up, retained best | 0.0111 | 0 | 0.000060 | 1.03 | 676.63 |
| 38 | DAN up, synchrony trip | 0.56 | 0.524 | 0.159 | 592.47 | — |
| 40 | central up, synchrony trip | 24.21 | 24.57 | 7.54 | 298.36 | — |

## Diagnostic: background variance

This is one exploratory sweep, not a K1 evaluation or a change to
`data/params-v0.1.yaml`. Two separate v783 engine processes used in-memory
copies of Params with `bg.n_bg` set to 10 or 20 inputs per neuron, while
`bg.r_bg` stayed at its 10 Hz YAML value. Each point restored `initial`, used
the same derived ENGINE seed, set one common weight on every nonsensory group
and zero on sensory, settled 2 s, then measured 3 s with the Fano detector.
There were six geometric weights per input-count setting. The 12 measurement
windows totalled 1,032.04 wall seconds; the whole run finished under its
29-minute cap. Full per-point rates, Fano, bin fractions, and timings are in
`.reports/bg-variance-sweep.log`. Weights above 2 mV are diagnostic probes
outside the permitted K1 weight range and were never written to the drive.

| Inputs/neuron | Weight mV | central Hz | DAN Hz | KC Hz | F | Detector |
|---:|---:|---:|---:|---:|---:|---|
| 10 | 1.000 | 0 | 0 | 0 | unknown | unknown |
| 10 | 1.431 | 0 | 0 | 0 | unknown | unknown |
| 10 | 2.048 | 0 | 0 | 0 | unknown | unknown |
| 10 | 2.930 | 0 | 0 | 0 | unknown | unknown |
| 10 | 4.193 | 11.871 | 33.919 | 39.369 | 2.702 | clear |
| 10 | 6.000 | 13.321 | 38.953 | 42.262 | 2.630 | clear |
| 20 | 0.500 | 0 | 0 | 0 | unknown | unknown |
| 20 | 0.715 | 0 | 0 | 0 | unknown | unknown |
| 20 | 1.024 | 0 | 0 | 0 | unknown | unknown |
| 20 | 1.465 | 0 | 0 | 0 | unknown | unknown |
| 20 | 2.096 | 0 | 0 | 0 | unknown | unknown |
| 20 | 3.000 | 12.791 | 38.657 | 42.520 | 2.803 | clear |

No sampled point met the exploratory low-rate question (central 0.1 to
3 Hz, DAN a few Hz, F below the configured maximum). Reducing the number of
inputs shifted the observed silent-to-hot jump to higher common weights, but
did not resolve it at six-point spacing. A narrower window between 2.930
and 4.193 mV for `n_bg=10`, or between 2.096 and 3.000 mV for `n_bg=20`,
could contain a graded regime; these measurements do not establish that it
does or does not. This remains a spec decision rather than a parameter
change in WP3.

## K1b: inhibitory weight ratio

WP3b studies one lever, `g_inh`, multiplying the magnitude of negative
connections while leaving positive connections unchanged. This composition
uses v783 parquet connection order, the signed `Excitatory x Connectivity`
column, and the base `w_syn = 0.275 mV`. It is a read-only census, not a
simulation. The full machine-readable table is `.reports/k1b-composition.json`.
The optional sparse eigenvalue calculation was skipped to keep the bounded
transition map first in the compute budget.

| Sign | Connections | Summed absolute base weight, mV |
|---|---:|---:|
| Inhibitory | 6,032,681 | 6,049,506.375 |
| Excitatory | 9,059,302 | 8,936,047.175 |
| Total | 15,091,983 | 14,985,553.550 |

The inhibitory share below is summed inhibitory incoming absolute weight
divided by all incoming absolute weight for the drive group. Groups use the
same annotation overrides as K1.

| Drive group | Neurons | Inhibitory share |
|---|---:|---:|
| DAN | 361 | 20.73% |
| ER | 278 | 76.38% |
| KC | 5,177 | 14.01% |
| ascending | 2,317 | 47.43% |
| central | 26,568 | 38.37% |
| descending | 1,299 | 43.22% |
| endocrine | 76 | 44.24% |
| motor | 106 | 51.18% |
| optic | 77,529 | 42.63% |
| sensory | 16,351 | 52.93% |
| visual_centrifugal | 524 | 37.86% |
| visual_projection | 8,053 | 40.67% |

Largest inhibitory presynaptic sources by summed absolute base weight onto
the named postsynaptic drive group. A dash means `cell_type` is unannotated;
the `super_class` is shown in parentheses.

| Rank | Onto KC: root ID, label, mV | Onto central: root ID, label, mV |
|---:|---|---|
| 1 | 720575940624547622, — (central), 14,713.60 | 720575940625741287, — (central), 4,442.90 |
| 2 | 720575940613583001, — (central), 12,416.25 | 720575940626462014, AN_multi_28 (ascending), 4,277.63 |
| 3 | 720575940618932603, — (central), 939.13 | 720575940612718563, AN_multi_28 (ascending), 4,119.50 |
| 4 | 720575940606769854, — (central), 936.37 | 720575940608545219, — (central), 3,927.83 |
| 5 | 720575940628334342, — (central), 794.47 | 720575940625102224, — (central), 3,560.15 |
| 6 | 720575940615183071, — (central), 609.67 | 720575940618366843, — (central), 3,553.28 |
| 7 | 720575940614137809, — (central), 603.07 | 720575940604569824, — (central), 3,525.78 |
| 8 | 720575940635468991, — (central), 592.90 | 720575940627796298, — (central), 3,524.95 |
| 9 | 720575940638028607, — (central), 270.05 | 720575940610584184, — (central), 3,443.28 |
| 10 | 720575940630496374, — (central), 268.68 | 720575940624377224, — (central), 3,198.53 |

### K1b transition map: screening candidate

The ratio-4 state is a **map-level candidate**, not a resting state or a
resting calibration (SPEC 11.43). Ignition from silence remains a jump at
every sampled ratio. Screening in a 5 s window does not establish the
10 s, three-seed resting criterion; the retained table misses five targets.
The canonical substrate remains bare (`lif.g_inh=1`, background off).
Only background-on development runs use the ratio-4 weights and hash.

The six-ratio map used base arrays, 100 background inputs at 10 Hz per
neuron, the same derived ENGINE seed, eight geometric common weights from
0.70 to 1.40 mV, four edge bisections, and 2 s settle plus 5 s measured per
point. There were 72 valid evaluations. The full JSON evaluations are in
`.reports/k1b-map.log`, and the interim decision record is
`.reports/k1b-map.md`. The first active point below means central at least
0.3 Hz; the low-side edge is the highest sampled weight with central at
most 3 Hz and the detector not tripped. Tiny residual spikes mean the latter
is not always literally silent.

| `g_inh` | Low-side edge mV | First active mV | Central Hz, F at first active | Amended qualifying pair |
|---:|---:|---:|---|---|
| 1 | 0.782488 | 0.787346 | 3.462, 491.34 | none |
| 2 | 0.782488 | 0.812091 | 6.227, 5.05 | none |
| 3 | 0.777661 | 0.812091 | 4.094, 2.89 | none (1.400 mV is 8.0566 Hz, above cap) |
| 4 | 0.787346 | 0.812091 | 2.993, 14.97 | 1.148469 and 1.268013 mV |
| 6 | 0.802101 | 0.807080 | 2.674, 8.71 | none |
| 8 | 0.802101 | 0.807080 | 2.062, 6.90 | none |

The orchestrator amended the decision rule after the grid was measured:
two adjacent grid points must each have F below 3, maximum 1 ms bin fraction
below 0.05, a first/last-second central-rate ratio in [0.5, 2], central
at most 8 Hz, and next-grid central rate less than three times its own.
The previous central 0.3 to 3 Hz band is a K1 target, not a map gate.
At `g_inh=4`, the qualifying pair gives central 4.554 and 5.708 Hz, F 2.922
and 2.391, bin fractions 0.003181 and 0.003960, and first/last ratios
0.998 and 1.006. The next-grid rate ratios are 1.254 and 1.254. The
provisionally suggested `g_inh=3` pair misses the exact 8 Hz cap by
0.0566 Hz at 1.400 mV. K1-dev attempt 3 therefore uses `g_inh=4` and
starts from the lower qualifying common weight, 1.1484694984106931 mV.

An initial map continuation mistakenly stored a previous ratio's active
end state as the next ratio's initial state; it was stopped and archived at
`.reports/k1b-map-attempt1.log`. Ratios 1 and 2 from that first run began
from a fresh build and are valid. The corrected ratios 3, 4, 6, and 8 each
ran in a fresh process, at most two concurrently, avoiding both carry-over
and an exit-134 abort after an in-process ratio change. This correction
added no measurement points. The old WP3 edge (0.7773–0.7818 mV) and this
map's ratio-1 edge (0.78249–0.78735 mV) come from different sampling
grids and rejection rules, not a single monotonic transition. Review r5
reproduced central 13.588768 Hz at 0.7818113596961447 mV and
0.0000451671 Hz at the slightly higher 0.7824883147390435 mV, using the
same seed, raw weights, 2 s settle, 5 s recording and 10 ms chunks.
Every group rate matched the respective original log. The near-edge
response to common weight is nonmonotonic for this fixed seed, so the
reported intervals are sampled brackets, not bounds on a unique critical
weight. WP3 brackets a synchrony/central-DAN-KC ignition constraint;
the map brackets central at most 3 Hz and the synchrony detector.

Review r5 also compared the numerical weight paths: WP3 leaves the
original synaptic volt values untouched; the map calls
`set_weight_scale(ones)`, whose volt-to-mV-to-volt round trip changes
767,572 of 15,091,983 weights by at most 5.551115123125783e-17 V.
At the WP3 hot point, both paths and both repetitions produced identical
per-neuron counts and population histograms. At the map low point, both
paths also reproduced the original nearly silent rates and identical
counts/histograms. The rounding is therefore
not the observed cause of that bracket discrepancy. Background-off
workers now retain the original bare weights without this unnecessary
rewrite. These checks give no evidence of silent engine nondeterminism.


Attempt 3 keeps the fixed 2 s settle, 5 s measured window, per-group log
objective, and 40-evaluation cap. Its scheduled search is one mapped common
start, bidirectional 0.05 mV steps on each nonsensory group in sequence,
then targeted refinements of the largest log-rate misses until the cap.
Only detector-clear evaluations can become the retained table. The WP3
hot-state cutoff is not used at `g_inh=4`, because it would reject the
amended map's legitimate, detector-clear starting point before group tuning.

Run with
`uv run python -m flyonenomics.drive.background --dev --g-inh 4 --start-mv 1.1484694984106931`.
Attempt 3 completed the 40-evaluation cap in 5,185.97 wall seconds
(86.43 min); the full log is `.reports/k1-dev.log`, while the WP3 attempt-2
log is preserved as `.reports/k1-attempt2.log`. The best feasible candidate
was evaluation 21, not the final trial. It has objective 16.78754, F 2.59435,
maximum 1 ms bin fraction 0.002799, and detector status clear. The resulting
`data/drive-dev.yaml` has `g_inh: 4`, `qualified: false`, and lists five
factor-of-two target misses. A finite clear candidate exists, so the amended
condition for the extra `bg.n_bg=10` scenario is not met; that scenario was
not run. This is an active development drive, not a tonic target match.

| Group | Target Hz | Retained weight mV | Measured Hz | Factor-of-two |
|---|---:|---:|---:|---|
| DAN | 5 | 1.148469 | 0.768421 | miss |
| ER | 2 | 1.148469 | 1.235252 | within |
| KC | 0.1 | 1.098469 | 1.449913 | miss |
| ascending | 1 | 1.098469 | 1.788174 | within |
| central | 1 | 1.198469 | 4.943993 | miss |
| descending | 1 | 1.148469 | 1.825096 | within |
| endocrine | 1 | 1.098469 | 1.657895 | within |
| motor | 0.5 | 1.098469 | 1.613208 | miss |
| optic | 1 | 1.148469 | 1.445978 | within |
| sensory | none | 0 | 0.089732 | no target |
| visual_centrifugal | 1 | 1.198469 | 2.439695 | miss |
| visual_projection | 1 | 1.148469 | 0.748442 | within |

An abridged attempt-3 log shows why better DAN mean rates were rejected
(rates in Hz; dash means the synchrony-tripped point was not scored):

| Eval | Phase | central | DAN | KC | F | Objective |
|---:|---|---:|---:|---:|---:|---:|
| 1 | mapped common start | 4.554 | 0.826 | 1.506 | 2.922 | 18.909 |
| 3 | DAN up 0.05 mV | 5.168 | 3.389 | 4.644 | 5.754 | — |
| 21 | retained best | 4.944 | 0.768 | 1.450 | 2.594 | 16.788 |
| 24 | smaller DAN-up refinement | 5.510 | 1.177 | 1.884 | 2.718 | 17.586 |
| 30 | DAN-up refinement | 5.434 | 3.180 | 4.760 | 5.504 | — |
| 40 | final trial, rejected | 5.507 | 2.628 | 4.233 | 4.985 | — |

The lane’s original development validation remeasured the table in fresh
engine processes (24 entries, zero infrastructure errors; the pre-r5 snapshot).
Entry 2.1 reproduced the retained 5 s group rates exactly and failed the
five factor-of-two checks and the DAN 2–10 Hz check. Entry 2.2 passed its
distribution thresholds: per-neuron median 0.8 Hz and 0.4140% above 50 Hz
over 10 s. Entry 2.3 failed synchrony over 10 s: F 3.59135 versus the
configured maximum 3, while maximum bin fraction 0.002928 was below 0.05.
Those original 2.2/2.3 windows started from initial without an excluded
settle, unlike K1; they cannot establish failure of the settled 10 s
criterion. Review r5 corrected that window (below). Entry 1.4 failed: its
ten MN9 sugar-minus-silent differences ranged from −19 to
+7 Hz, nowhere near the bound (then a greater-than-50 Hz result in every seed; since item 61 a ten-seed mean above 50 Hz with no seed below 40 Hz).
Entry 2.4 also failed; its baseline difference was +6 Hz, five jittered
differences were −11, +1, +3, −16, and −1 Hz, and three changed sign. Group
rates were not all within factor 1.5. Entry 2.5 failed the warm q1 target
(17.41943 versus 15); the full cold/warm row is in `docs/bench.md`. All
these entries remain `development` and satisfy no component-map item.

The sugar-reflex cost is severe. The original `data/experiments/sugar-reflex.json`
kept `background: false`, but its pinned drive applied `g_inh=4` before the
worker snapshot. With two workers (the later two-whole-brain cap superseded
the brief's four-worker command), both wild-type seeds gave MN9 0 Hz in
upstream and extended probes, against review r4's 86 and 53 Hz baseline.
The completed run is `runs/20260913T095006.652926Z-db8dd67c`; its manifest
records `g_inh=4` and the drive checksum even with background off. A
one-seed, wild-type diagnostic copy at
`.reports/sugar-reflex-background-dev.json` switched only its own
background layer on; the committed experiment files were not edited. That
run (`runs/20260913T095733.123865Z-4aef16d3`) gave MN9 3 Hz upstream and
8 Hz extended. Its full-population count averaged 307.421 and 297.928
spikes per 1 ms bin; first versus last 200 ms means were 303.64 versus
307.91 and 300.99 versus 300.67. There was no abrupt high-rate ignition
in those recorded windows, but F was 4.466 and 4.167, so the stimulated
state remained synchrony-tripped and the reflex remained far below baseline.

### Review r5: bare switch and settled 10 s candidate

The background switch now controls both the weights and their inhibitory
ratio. With background off, the worker preserves the bare build’s exact
ratio-1 weights and the manifest records `lif.g_inh: 1` without a drive
hash. The authorized two-worker sugar gate reproduced the r4 wild-type
means, **86 Hz upstream and 53 Hz extended**; the threshold-shift arm was
74/46 Hz. Its run is `20260913T110156.168375Z-db8dd67c`.

One unforced, one-seed recording derived from `spontaneous.json` used the
ratio-4 development table, base arrays, seed id 0, 2 s excluded settle and
10 s recording (`20260913T110757.994910Z-1e24a854`). It recorded
2,677,319 spikes across 138,639 neurons. F was
**2.590928546**, maximum 1 ms bin fraction
0.002798635305, and central first/last-second
rate ratio 1.003835245. F for seconds 1–10 was:

`2.619227, 2.525103, 2.719952, 2.803380, 2.256067, 2.504031, 2.419470, 2.598738, 2.574388, 2.787734`.

The mean central rate was 4.933318 Hz,
DAN 0.776177, KC 1.455032,
and ER 1.254317. The original five target misses
remain; no target or detector threshold changed.

The mean-removed Hann population-count periodogram below 20 Hz has its
largest peak at 12.6 Hz (PSD 27.305695 (spikes/bin)^2/Hz). Welch averaging
with 2 s windows and 50% overlap peaks at 12.5 Hz (PSD 9.369320).
The 12–13 Hz band peaks at 12.6 Hz in both halves, though the final half’s
overall largest peak is 9.8 Hz. This is a weak ~12.5–12.6 Hz oscillatory
feature. The settled window does not sustain the old above-threshold
Fano result; the excess in the startup-inclusive window is consistent
with an onset transient. The earlier F=3.591348 was measured without
settling, not under the item-43 2 s + 10 s criterion. Its historical
wording in SPEC should be corrected, without changing the threshold 3.
The raw spectrum and analysis are in `.reports/spontaneous-spectrum-below20hz.csv`
and `.reports/spontaneous-analysis.json` in review r5.

This remains a **map-level candidate, not a resting calibration**: one
seed and weight do not establish the three-seed, adjacent-weight resting
definition, and ignition from silence remains a jump. The canonical
substrate stays bare. The regenerated validation has 31 entries and
zero infrastructure errors: 1.4 failed, 2.1 failed,
2.2 passed, 2.3 passed, 2.4 failed,
and 2.5 failed; all remain development and satisfy no
component-map entry. The corrected 2.3 measurement is
F=2.590928546 after the required settle.

## K2 release constants

**Measured; qualified under SPEC item 61.** One bare network was restored and seeded independently for seeds 1, 2 and 3 (master seed 20260912). Each seed ran 2 s settle plus 5 s measurement with background off, A and C on, no drug, and pools clamped at `da.DA_ref`; no stimulus was applied. Every seed returned `R_c = 0` weighted DAN spikes/s in all 37 compartments. All 37 are below `da.R_min = 0.5` and receive `alpha_c = da.alpha_max = 0.1` µM/weighted spike. Every compartment is innervated and receives `da.tonic_source = da.DA_ref × (da.Vmax / (da.Km + da.DA_ref) + da.k_ns) = 0.0026666666666666666` µM/s, a provisional item-24 rule. The source enters both Euler release and the analytic fixed point; release genotypes and 3-IY scale it, while fumin and methylphenidate act through clearance. `data/dopamine-v0.1.yaml` records the three seed vectors, the calibration date and the input file versions.

## Q free-pool qualification

**Completed; qualified under SPEC items 60 and 61.** The clamp was released, pools started at the analytic fixed point, and free-pool checks ran with A and C on, background off. **SPEC item 60** evaluates bare 2.2 on a 10 s stimulated sugar-reflex recording reused from 1.4 seed 0: all-neuron median at most 5 Hz and fewer than 1% above 50 Hz, with no median floor. The 0.2 Hz floor remains only for background-on development. Background tests 2.1 and 2.3–2.5 remain unavailable or development.

| Q step | Measurement | Bound | Outcome |
| --- | --- | --- | --- |
| 3.1b, seeds 1–3 | all settled; DA 0.020000 µM in every compartment; chunk arrays bitwise equal; worst per-neuron dV error 4.00e-15 mV and gain error 2.26e-14 (review r9, 10 s each) | DA 0.016–0.024 µM; worst-neuron bounds 0.1 mV and 0.01 gain | passed |
| 1.4, seeds 0–9 | MN9 sugar-minus-silent Hz: 56, 50, 58, 58, 63, 48, 59, 61, 53, 62; mean 56.8, minimum 48 | ten-seed mean >50 Hz; every seed ≥40 Hz (item 61) | passed |
| 2.2, stimulated seed 0, 10 s | median 0 Hz; fraction above 50 Hz 0.000324584; Fano 2.22097; maximum bin fraction 0.000209176 | median ≤5 Hz; fraction <0.01; diagnostic Fano ≤3 and bin fraction ≤0.05 | passed |

Q measured 968.27 wall seconds on the item-60 retry. The original strict-per-seed interpretation of 1.4, requiring every seed to exceed 50 Hz, failed on seeds 1 and 5 (50 and 48 Hz). SPEC item 61 replaces that bare-substrate interpretation with the ten-seed mean and a 40 Hz seed floor; the same rule applies to background-on development. The stored per-seed values were rescored without rerunning the network or tuning parameters. All three Q checks pass under items 60 and 61, so `data/dopamine-v0.1.yaml` is frozen with `qualified: true`. The original section-3.3 escalation table remains in the YAML as a labelled historical diagnostic, including per-compartment means, group rates, Fano and per-neuron modulation errors. An earlier Q attempt failed while serializing a NumPy group-name key and wrote no qualification record; the successful item-60 retry added native-type conversion and a pre-YAML checkpoint.

Review r9 reran Q once on 2026-09-13, with **10 s per seed for 3.1b** after 2 s settle. All three seeds passed 1,000 chunk comparisons, with each compartment mean 0.019999999999999664 µM; no neuron exceeded its own modulation bound. The complete Q rerun took 1,332.48 command wall seconds (1,327.19 s measured after build). Every one of the ten stored MN9 differences reproduced exactly, as did stimulated 2.2: median 0 Hz, fraction above 50 Hz 0.00032458399151753835, Fano 2.220973410910589, maximum bin fraction 0.00020917635008908027. The 3.1b block and explicit windows were refreshed while preserving K2's date and versions, the accepted item-61 reflex block and historical failed-Q escalation.

Under item 62, canonical and background-on development 1.4 record 1 s per condition after settle in each of ten seeds and are scored by item 61; 2.2 extends the stimulated condition of seed 0 to 10 s as a separate rate-safety window in `qualification.windows_s`, preserving the frozen record unchanged.

Phasic `alpha_max` remains a placeholder scale because K2 measured zero tonic DAN spikes; background-target qualification remains deferred on the canonical bare substrate. The 100 h washout uses the exact exponential PK solution, giving an effectively washed-out but nonzero residual; it is not a literal zero assignment.

Under item 53, the fixed point scales both tonic terms by the retained fraction of a compartment's M weight after DAN silencing. This is a uniform-contribution approximation from compartment totals. The inhibitory ratio is not a neuromod constant; background-off canonical runs use the bare substrate, and r5's drive table applies its ratio only to background-on development runs.

## Sign check

Provisional development procedure is implemented in `flyonenomics.behaviour.buridan.sign_check`. It uses `data/experiments/open-loop-steering.json`: wild type, `IdentityNeuromod`, background/A/C off, fast DAN synapses retained, three seeds, and the full eleven-azimuth 33 s schedule. Each azimuth occupies a 1 s excluded transition followed by a 2 s dwell. The curve reports the dwell means of `r_R - r_L` (Hz) and `omega` (degrees/s), with chunk counts. The sign is chosen once from the +/-30 and +/-60 degree points and checked against the 4.1 direction rule. If every azimuth has |mean omega| below 5 degrees/s, the record is `flat (provisional)` and K3 still runs as a code-path check. The curve and decision were written to `data/behaviour-dev.yaml` with class `development`; WP9 deleted that file after the fallback freeze (items 58, 64), and it remains in git history.

The three-seed development run `20260913T055240.948009Z-39925503` completed with one whole-brain worker and an empty `validate_run` result. At each azimuth from −150 to +150 degrees in 30-degree steps, the 600 dwell chunks yielded mean `r_R − r_L = 0 Hz` and mean `omega = 0 degrees/s`. The result is **flat (provisional)**; `sign_steer` remains +1 by convention. TuBu spiked in the inspected seed, while both steering populations had zero spikes. Under this layers-off state, closed-loop fixation has not emerged; the K3 development grid still runs to exercise the code path. The full curve was in the since-deleted `data/behaviour-dev.yaml`. The final bare-substrate sign check with qualified K2 and layers A and C on is the WP9 section of this log; it was flat at 100, 140 and 280 Hz (item 64), and `scripts/calibrate.py` replays it from `data/behaviour-v0.1.yaml`.

## K3 behaviour constants

Reference ingestion is complete: the calibration half has 64 flies, of which 61 have defined window-mode FI and stripe deviation. Its FI median/IQR are 0.7035827186512118/0.3025954198473282; stripe-deviation median/IQR are 18.72920562777381/12.781842833392218 degrees. Full-record CeTrAn comparison selected 0.8 mm: joint matches are 128/128 at 0.8 mm and 120/128 at 0.6 mm. The calibration-half median walking speed is 15.251167474671366 mm/s, recorded then as `v_fwd` in `data/behaviour-dev.yaml` and now as `v_fwd_mm_s` in `data/behaviour-v0.1.yaml`.

The provisional K3 grid completed with wild type, background/A/C off, the neuromod stub, two seeds, 10 s Buridan probes, and a fixed 2×2×2 sub-grid: `K_steer` {2, 8} degrees/s/Hz, `r_vis_max` {70, 150} Hz, `sigma_vis` {15, 30} degrees. Each candidate was scored in window mode against the calibration half with `((FI_m - FI_c)/IQR_FI_c)^2 + ((dev_m - dev_c)/IQR_dev_c)^2`. All eight candidates tied exactly: model median FI 0.9948979591836735, stripe deviation 9.840958541496427 degrees, objective 1.4103878231219227. The earliest candidate wins the specified tie: `K_steer=2`, `r_vis_max=70`, `sigma_vis=15`. This is a provisional code-path result, not a qualified visual calibration: the sign curve was flat and K3 parameters had no measured effect. The full table and run paths were in the since-deleted `data/behaviour-dev.yaml`, marked `development`. The three-seed, 20 s stripes-on and two-control 4.2 comparison also completed: all three medians were FI 0.9744897959183674 and stripe deviation 10.343163370650203 degrees, with zero difference against either control. Provisional 4.2 fails, and the high raw FI does not demonstrate visual fixation. Final K3 on the bare substrate is recorded `unavailable` with zero candidates under the section 9.1 fallback (item 64); see the WP9 section of this log.
