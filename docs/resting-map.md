# Resting-state map (Camber stage 1)

This is development evidence (SPEC item 69 (e)). It does not freeze a
drive table and does not enter `validation/status.json`. Stage 2 did
not run: Rolf skipped it, and WP17 confirms. WP17 still has to
re-screen, run R-reflex and R-long, and apply the section 2.6 order
key. This map only says where to look.

Evaluation commit: `4e0220f`. Driver: `scripts/camber/resting_map.py`
on the engine API, layer A off, 100 background inputs at 10 Hz. The
driver is not in `4e0220f`: `stage.sh` overlaid it from lane cam, where
it was committed as `1a48abc` three minutes before the jobs were
created. The evaluation rows record `4e0220f` as commit and code scope.
Platform is Camber `large` (Linux x86, 64 cores, 256 GB).

## Result

The lane's candidate rule is item 43 plus item 35's central cap. At
two adjacent grid weights, in every one of three seeds, 2 s settle and
10 s measured: F below 3, maximum bin fraction below 0.05,
first/last-second central ratio in [0.5, 2], central rate at most
8 Hz, and central rate at the next grid weight below 3 times the
upper pair member's.

Eight (`g_gaba`, `g_glu`, sign) combinations meet it: `g_gaba = 3`
with `g_glu` in {3, 4, 6, 8}, both photoreceptor signs, best common
weight 1.20 mV, adjacent pair 1.20 and 1.25 mV. Three-seed mean central
rate at 1.20 mV is 5.04 to 6.09 Hz and mean F 2.68 to 2.77. Per seed at
1.20 and 1.25 mV, F is 2.48 to 2.88 and maximum bin fraction at most
0.0047. First/last-second ratios sit at 1.00. The next-grid central
rate is 1.07 times the 1.25 mV rate.

The 8 Hz cap is what makes eight. Item 43 as written has no central
cap, and without it 22 combinations (11 scale pairs) pass: the eight
above plus (1,2), (1,3), (1,4), (1,6), (1,8), (3,2) and (4,2), each
only at weights where some seed's central rate exceeds 8 Hz.

The histamine sign flip does not change any resting metric (largest
absolute difference 0). The driver sets the background weight of every
sensory neuron to zero, R1-6 included, and nothing else drives them at
rest. R1-6 therefore do not spike, and the sign of their outgoing
synapses cannot act. R1-6 rates were not recorded; the identical
tables are the evidence. Keep both
signs for visual work. Do not spend a second rest screen on the
histamine copy.

WP3b's global ratio 4 is not a 10 s, three-seed candidate on this
grid. WP3b's pair, 1.148 and 1.268 mV, had no weight between them.
This grid samples 1.20 and 1.25 mV, where F is 4.5 to 5.0 in all three
seeds, so no two adjacent weights pass in every seed: 1.15 mV fails
seed 1 (F 5.62) and 1.30 mV fails seeds 2 and 3 (F 4.31 and 4.21).

## Grid that ran

| Knob | Values |
|---|---|
| `g_gaba` | 1, 2, 3, 4, 6, 8 |
| `g_glu` | 1, 2, 3, 4, 6, 8 |
| Common weight | 0.70 to 1.60 mV, step 0.05 mV (19 points) |
| Photoreceptor sign | model (R1-6 excitatory) and histamine (R1-6 outgoing flipped) |
| Seeds | 1, 2, 3 |
| Window | 2 s settle, 10 s measure |

That is 36 × 19 × 2 × 3 = 4,104 evaluations. Each `(g_gaba, g_glu)`
pair used one process and its own parquet. There was no shared
`index.sqlite`. Glutamate-inhibitory synapses took `g_glu`. Every
other inhibitory synapse took `g_gaba`, so the diagonal
`g_gaba = g_glu` is the WP3b global ratio.

## Jobs

| Job | Label | Size | RUNNING | Node-hours | Credits |
|---|---|---|---:|---:|---:|
| 27163 | map-model | large | 537.75 min | 8.9625 | 22.9440 |
| 27164 | map-histamine | large | 585.13 min | 9.7522 | 24.9657 |
| **total** | | | | **18.7147** | **47.91** |

Start 2026-09-15T00:36:36Z and 00:36:35Z. End 09:34:21Z and
10:21:43Z. Both jobs queued about four minutes. Ledger: lane cam's
`.reports/camber-ledger.md` (lane-local, not committed).

## Diagonal versus WP3b

WP3b (`docs/calibration.md`) used eight geometric weights from 0.70
to 1.40 mV, a 5 s window, and one engine seed. This map uses 0.05 mV
steps, a 10 s window, and three seeds. The first-active WP3b weights
(0.787 to 0.812 mV) do not fall on this grid. The nearest grid point
is 0.80 mV, which sits on the ignition jump, so that edge is not a
like-for-like check.

In the WP3b qualifying band (about 1.15 to 1.27 mV), three-seed means
on the diagonal are:

| `g_inh` | 1.15 mV central, F | 1.20 mV central, F | 1.25 mV central, F |
|---:|---|---|---|
| 1 | 17.73 Hz, 3.67 | 18.45 Hz, 3.61 | 19.19 Hz, 3.64 |
| 2 | 8.51 Hz, 5.06 | 9.04 Hz, 4.82 | 9.60 Hz, 4.41 |
| 3 | 5.65 Hz, 3.09 | 6.09 Hz, 2.77 | 6.58 Hz, 2.61 |
| 4 | 4.85 Hz, 3.60 | 5.46 Hz, 4.84 | 5.93 Hz, 4.71 |
| 6 | 3.79 Hz, 6.57 | 4.18 Hz, 5.85 | 4.57 Hz, 5.73 |
| 8 | 3.11 Hz, 8.44 | 3.41 Hz, 7.29 | 3.77 Hz, 6.98 |

WP3b passed ratio 4 at 1.148 and 1.268 mV on a 5 s screen (central
4.55 and 5.71 Hz, F 2.92 and 2.39). Here the three-seed mean F of
ratio 4 is 3.60 to 4.84 at 1.15 to 1.25 mV, and every seed fails at
1.20 and 1.25 mV, so ratio 4 has no adjacent pair that passes in all
seeds (see Result). Ratio 3 at 1.20 and 1.25 mV passes. Stronger global ratios (6 and 8) stay in a few-hertz central
band with F 5 to 8, the same synchrony failure WP3b saw.

## Candidates at 1.20 mV (mean of three seeds)

Model and histamine rows are identical. Rates are Hz.

| `g_gaba` | `g_glu` | sign | n_ok_pairs | central | DAN | PAM | PPL1 | KC | ER | descending | optic | L1 | Mi1 | Tm3 | MN9 | F | bin frac | first/last |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | 8 | both | 4 | 5.041 | 1.403 | 1.352 | 0.542 | 2.437 | 1.561 | 2.211 | 2.018 | 5.145 | 0.802 | 1.269 | 7.17 | 2.704 | 0.00343 | 1.005 |
| 3 | 6 | both | 5 | 5.467 | 1.443 | 1.345 | 0.438 | 2.600 | 1.618 | 2.326 | 2.052 | 5.143 | 0.777 | 1.413 | 5.63 | 2.682 | 0.00348 | 1.005 |
| 3 | 4 | both | 4 | 5.799 | 1.581 | 1.441 | 0.300 | 2.703 | 1.680 | 2.544 | 2.097 | 5.149 | 0.756 | 1.620 | 7.13 | 2.750 | 0.00376 | 0.998 |
| 3 | 3 | both | 3 | 6.090 | 1.728 | 1.505 | 0.273 | 2.738 | 1.747 | 2.764 | 2.182 | 5.151 | 0.752 | 1.772 | 8.93 | 2.772 | 0.00387 | 0.998 |

Every seed at 1.20 mV and at 1.25 mV has F below 3, bin fraction
below 0.05, first/last in [0.5, 2], and central at most 8 Hz, and the
1.30 mV central rate is below 3 times the 1.25 mV rate.

These are the lane's passers, not SPEC-P2 section 2.3 R-screen
passers: at 1.20 and 1.25 mV seed-mean KC is 2.44 to 2.86 Hz against
R-screen's 2 Hz cap. They meet its central and DAN ranges (central
5.04 to 6.58 Hz, DAN 1.40 to 2.17 Hz).

Per seed at 1.20 mV (model; histamine identical). Rates are Hz.

| `g_glu` | seed | central | DAN | PAM | PPL1 | KC | ER | descending | optic | L1 | Mi1 | Tm3 | MN9 | F | bin frac | first | last | ratio |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 1 | 5.030 | 1.424 | 1.383 | 0.556 | 2.477 | 1.557 | 2.167 | 2.018 | 5.130 | 0.794 | 1.269 | 6.2 | 2.749 | 0.00347 | 5.125 | 5.110 | 0.997 |
| 8 | 2 | 5.043 | 1.357 | 1.308 | 0.556 | 2.407 | 1.559 | 2.216 | 2.021 | 5.154 | 0.812 | 1.268 | 6.5 | 2.666 | 0.00343 | 5.097 | 5.063 | 0.993 |
| 8 | 3 | 5.052 | 1.429 | 1.366 | 0.513 | 2.427 | 1.567 | 2.249 | 2.015 | 5.152 | 0.800 | 1.270 | 8.8 | 2.698 | 0.00338 | 4.971 | 5.095 | 1.025 |
| 6 | 1 | 5.458 | 1.435 | 1.336 | 0.425 | 2.590 | 1.618 | 2.329 | 2.052 | 5.153 | 0.782 | 1.418 | 8.0 | 2.723 | 0.00348 | 5.464 | 5.489 | 1.005 |
| 6 | 2 | 5.458 | 1.465 | 1.371 | 0.475 | 2.611 | 1.608 | 2.318 | 2.056 | 5.141 | 0.779 | 1.414 | 4.1 | 2.715 | 0.00350 | 5.475 | 5.521 | 1.008 |
| 6 | 3 | 5.486 | 1.428 | 1.328 | 0.413 | 2.601 | 1.630 | 2.332 | 2.050 | 5.136 | 0.770 | 1.409 | 4.8 | 2.610 | 0.00346 | 5.486 | 5.498 | 1.002 |
| 4 | 1 | 5.808 | 1.573 | 1.435 | 0.331 | 2.702 | 1.691 | 2.524 | 2.094 | 5.140 | 0.754 | 1.617 | 5.8 | 2.738 | 0.00366 | 5.925 | 5.784 | 0.976 |
| 4 | 2 | 5.792 | 1.575 | 1.433 | 0.288 | 2.690 | 1.674 | 2.592 | 2.099 | 5.148 | 0.764 | 1.621 | 9.2 | 2.790 | 0.00380 | 5.792 | 5.787 | 0.999 |
| 4 | 3 | 5.798 | 1.596 | 1.456 | 0.281 | 2.716 | 1.676 | 2.515 | 2.098 | 5.160 | 0.751 | 1.621 | 6.4 | 2.720 | 0.00381 | 5.754 | 5.856 | 1.018 |
| 3 | 1 | 6.083 | 1.743 | 1.514 | 0.225 | 2.733 | 1.744 | 2.786 | 2.178 | 5.149 | 0.742 | 1.751 | 11.9 | 2.626 | 0.00379 | 6.105 | 6.101 | 0.999 |
| 3 | 2 | 6.092 | 1.736 | 1.510 | 0.331 | 2.731 | 1.737 | 2.788 | 2.191 | 5.164 | 0.766 | 1.778 | 9.8 | 2.884 | 0.00390 | 6.103 | 6.020 | 0.986 |
| 3 | 3 | 6.094 | 1.704 | 1.491 | 0.263 | 2.748 | 1.762 | 2.719 | 2.178 | 5.141 | 0.747 | 1.787 | 5.1 | 2.806 | 0.00393 | 6.101 | 6.142 | 1.007 |

L1 is about 5.15 Hz at rest. Mi1 is 0.75 to 0.80 Hz. Tm3 is 1.27 to
1.77 Hz. On the bare substrate those medulla cells were silent
(WP10). A rest substrate with `g_gaba = 3` already supplies tonic
lamina and medulla rates. Item 68's "silent relay" is a bare-substrate
finding. It is not the state of these candidates.

MN9 sits at 5 to 9 Hz with no sugar stimulus. Stage 2 would have
compared the sugar difference to 86/53 Hz. That measurement does not
exist here.

## Six closest misses (unique scale pairs)

None meets the lane rule. (4,2), (3,2) and (1,8) pass item 43 only
at weights where central exceeds 8 Hz. (4,3), (2,8) and (2,6) fail
item 43 itself: no adjacent pair passes in every seed (in the 1.10 to
1.45 mV band, F reaches 3 in at least one seed).
Ordered by the driver's item-35 violation (lower is closer), not by the
SPEC-P2 section 2.6 order key:

| `g_gaba` | `g_glu` | best weight mV | mean central Hz | mean F | item-35 violation |
|---:|---:|---:|---:|---:|---:|
| 4 | 2 | 1.30 | 6.56 | 2.75 | 0 |
| 4 | 3 | 1.35 | 6.66 | 2.43 | 0 |
| 3 | 2 | 1.30 | 7.65 | 2.81 | 0 |
| 2 | 8 | 1.35 | 7.02 | 3.12 | 0.039 |
| 2 | 6 | 1.35 | 7.77 | 3.13 | 0.042 |
| 1 | 8 | 1.30 | 8.34 | 3.17 | 0.099 |

A zero violation with `candidate = false` means the best adjacent
pair is close, but not every seed passes both weights and the
following graded point together.

## Wall time

The brief planned about 50 Mac engine-hours, then the proof ratio
ρ = 1.763. Thirty-six processes per node give about 50 × 1.763 / 36
≈ 2.4 hours of wall, the "~2 h" plan.

Each evaluation's own `wall_s` (settle plus 10 s measure, no compile)
had median 510 s in the model shard and 530 s in the histamine shard
(521 s pooled): 42.5 and 44.2 seconds of wall per second of brain
time. A shard's 36 pairs ran side by side, 57 evaluations each in
sequence, so a job lasts as long as its slowest pair: 8.92 hours
(model) and 9.71 hours (histamine) of evaluations, against 8.96 and
9.75 hours RUNNING. Setup took minutes. Queue was four minutes.

The 50 engine-hour figure implied about 44 s per evaluation. The
proof ρ came from a dose-series with four workers, not from a
whole-brain 10 s window. SPEC-P2 section 6.3 planned this map at
`q_plan`, about 27 wall seconds per brain second per engine, with 62
engines per node on two nodes: 369 engine-hours, about 3 hours, 15.3
credits. The map measured 42.5 to 44.2 (about 1.6 × `q_plan`) at 36
engines per node and cost 47.91 credits, 3.1 times that row. WP17 must
scale R1 and R-long by the measured cost, not by 1.763.

## What WP17 should take

1. The map has landed. SPEC-P2 section 2.6 step 1 applies. Do not
   fall back to all 36 pairs unless the driver needs a control.
2. Treat the four unique scale pairs `(3,8), (3,6), (3,4), (3,3)` as
   the map's lane-rule passers. They are not R-screen passers (KC above
   2 Hz). Count eight combinations if the driver keys on
   sign; resting numbers do not differ by sign.
3. Take the six lowest unique non-passers, add grid neighbours, and
   keep the first 12 pairs by the section 2.6 order key. The table
   above orders them by the driver's item-35 violation; this map did
   not compute S or J. Recompute those on R-screen.
4. Start R-screen near 1.20 mV for the `g_gaba = 3` band. Do not
   treat WP3b's ratio-4 pair (1.148, 1.268 mV) as already qualified.
5. Layer A was off. Connection-file GABA/glutamate classes were used.
   The map qualifies nothing.
6. Plan Camber wall with about 510 to 530 s per 12 s evaluation at 36
   engines on `large`, a job as long as its slowest shard unit, or
   measure a new ρ on an R-screen unit. The 11-credit WP17 cap is set
   at ρ = 1, and section 6.2 scales it by the measured 1.763 to about
   19.4 credits. At this map's cost that will not cover a wide R1.
7. Stage 2 did not measure sugar retention or stripe propagation.
   R-reflex and WP18 still have to do that work. L1, Mi1 and Tm3
   already fire at rest on the passers, so a dark-bar histamine story
   starts from a non-zero medulla, not from WP10 silence.
8. Camber GPU nodes do not share the five CPU slots. WP17's GPU medium
   probe 27470 ran as a sixth job beside five CPU `large` jobs. Plan
   CPU concurrency on five slots; a GPU job is extra capacity after a
   provisioning wait.
