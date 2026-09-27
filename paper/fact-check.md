# Manuscript numerical fact check

| Paper item | Check | Source / scope |
|---|---|---|
| Affiliation | Hasan “Rolf” Yildirim followed by `Lasell University` in manuscript and supplement author lines. No city or state is asserted. | Rolf confirmed Lasell as the affiliation on 27 Sep 2026; city/state were not verified from Lasell's site. |
| Final build switch | `paper/build.py --final` writes `\finaltrue` to `paper/build/final-mode.tex`; the default writes `\finalfalse`. The manuscript loads that preamble line and uses `\iffinal\else ... \fi` only around the draft status and approval sentence. Receipt has `final: true/false`; supplement build is unchanged. | Local draft and final builds succeeded; their extracted text differs only by the draft status and approval sentence in content (PDF page-number and bibliography extraction order shift with layout). |

Line references are to the reviewed sources on `main` at the lane start; manuscript line numbers refer to `paper/manuscript.tex` in this change. Values inserted by `paper/build.py` are shown at the build's six-significant-digit precision. A range below lists **every** value in that phrase, not a new inference. No raw-run identifiers belong in the manuscript.

| Manuscript line | Numbers (in manuscript order) | Source on main, line(s) |
|---|---|---|
| 21 | MaleCNS 162,517 neurons; 25,120,209 directed connections | `docs/cuda-methods.md:9`, `docs/adhd-study-results.md:12` |
| 32 | Supplementary tables S1–S5 cover model summary, population breakdown, neuron and synapse parameters, update equations and named-cell identifiers | Model and population details `docs/cuda-methods.md:19-29,33-55,85-106`; named types `paper/manuscript.tex:62-65` on main. Tables S1–S5 are present in `paper/supplement.tex`; see `paper/supplement-fact-check.md` for their source audit. |
| 34 | two initial primaries; one follow-up primary | `docs/adhd-study-results.md:21`, `docs/adhd-confirm-results.md:3,9-11` |
| 38 | recombinant potency 1 µM in occupancy equation | `docs/gaba-dose-results.md:9`, `docs/research/drug-action-in-network-models.md:407` |
| 40 | 58,655,422 spikes; four 12-s trajectories; 0.1-ms grid; one network per run | `docs/cuda-methods.md:119-127` (identical-input replay); `docs/cuda-methods.md:79,85` (single-brain runs) |
| 40 | L4, 12 simulated seconds, 8.420 s stepping, 10-ms interface | `docs/cuda-methods.md:11,85` |
| 40 | 0.637029 s per simulated second (10-ms interface), 1.268480 (1-ms interface) | `docs/cuda-methods.md:100-101`; these are separate short single observations, not the full-run rate |
| 40 | Whole ladder repeated with same design, independent random streams and within-engine controls; overlap describes effect estimates, not statistical equivalence | `docs/gaba-dose-gpu.md:11-19,121-123`; `validation/records/p2/male-cuda-dose-plan.md:9,46` (same numerical seeds, different random streams); exact replay scope `docs/cuda-methods.md:119-127` |
| 47 | pilot −0.085156; nominal 95% [−0.153954, −0.0209676]; Holm p 0.0703125 | `validation/records/p2/adhd-study-results.json:68,81-87`; rounded summary `docs/adhd-study-results.md:5` |
| 47 | interaction +0.0458767, 95% [−0.0598327, +0.15804]; no detected difference | `validation/records/p2/adhd-study-results.json:90-110` |
| 49 | confirmation −0.00128594; nominal 95% [−0.0379679, +0.0375782]; p 0.945398; not confirmed | `validation/records/p2/adhd-confirm-results.json:5-8,52-59`; reading `docs/adhd-confirm-results.md:3` |
| 58 | ACh −1.436 [−1.451, −1.426]; GABA +12.588 [+12.563, +12.613]; glutamate +10.779 [+10.760, +10.799] Hz | `docs/circuit-tour-results.md:7` |
| 60 | histamine −0.001 [−0.002, +0.001]; dopamine +0.001 [−0.019, +0.025] Hz; both no detected difference; unlabelled neurons −0.130 [−0.159, −0.100] Hz | `docs/circuit-tour-results.md:9` |
| 69 | P1 +32.457 [31.928, 32.837]; pIP10 +35.940 [32.370, 38.420]; dPR1 +26.230 [23.390, 29.650]; wing motor +9.159 [8.203, 10.150] Hz | `docs/circuit-tour-results.md:13` |
| 69 | medium P1 vs random dPR1 +17.810 [15.810, 19.820]; direct pIP10 dPR1 +14.410 [11.360, 17.830] Hz; vPR6 inactivity | `docs/circuit-tour-results.md:13-15` |
| 71 | low-drive route not demonstrated | `docs/p1-routes.md:3,9-16` |
| 82 | rest 1.438 Hz; block 10%, 25%, 50%, 75%, 90%, 100%; respective +0.093, +0.295, +0.972, +4.591, +9.591, +12.588 Hz | `docs/gaba-dose-results.md:15,19` |
| 82 | half observed full-block change 80.1% [79.9%, 80.3%]; fitted slope 5.05 [4.76, 5.34] | `docs/gaba-dose-results.md:20`; not an identified network EC50 |
| 82 | 50% = 1.000 µM; 90% = 9.000 µM brain-equivalent | `docs/gaba-dose-results.md:9-13` |
| 84 | extra GABA multipliers 0.25, 0.50, 1.00, 2.00; corresponding decreases 0.260 [0.238, 0.281], 0.442 [0.432, 0.456], 0.611 [0.598, 0.625], 0.835 [0.823, 0.847] Hz | `docs/gaba-dose-results.md:22` |
| 84 | 75% block; GluCl multipliers 0.50, 1.00, 2.00; reductions in excess 23.5% [20.9%, 26.0%], 45.5% [44.7%, 46.5%], 75.0% [73.7%, 76.1%]; residual +1.147 [1.103, 1.205] Hz | `docs/gaba-dose-results.md:23` |
| 86 | Conditional block Hill slope GPU 4.99 [4.65, 5.43] vs Brian2 5.05 [4.76, 5.34]; observed-endpoint half GPU 80.12% [79.95%, 80.30%] vs Brian2 80.11% [79.90%, 80.33%] | `docs/gaba-dose-gpu.md:115`; both fitted block half-effects remain unidentified |
| 86 | GluCl rescue GPU 23.6% [21.8%, 25.2%] vs Brian2 23.5% [20.9%, 26.0%]; GPU 45.1% [43.8%, 46.2%] vs Brian2 45.5% [44.7%, 46.5%]; GPU 75.0% [74.0%, 75.9%] vs Brian2 75.0% [73.7%, 76.1%] | `docs/gaba-dose-gpu.md:118` |
| 86 | Boost fitted half-effect GPU φ 2.21 [1.50, 4.29] vs Brian2 φ 1.26 [0.96, 1.80]; GPU not identified in tested range; individual rate intervals overlap | `docs/gaba-dose-gpu.md:117` |
| 97 | body angles ~47°, ~14°, ~8° | `docs/courtship-body.md:14`; chosen mapping `docs/courtship-body.md:20-35` |
| 113 | EM does not resolve electrical synapses (gap junctions); no electrical connections in model | `docs/research/comparable-preprints.md:182-186,222-225` (EM scope); `docs/cuda-methods.md:19,42,65-76` (model graph is directed chemical connections); `docs/feasibility.md:55` (no gap junctions). |
| 113 | No neuropeptide co-transmission; only dopamine has neuromodulator dynamics; other labelled transmitters use assigned signs | `docs/cuda-methods.md:42,83-106` (chemical signs and dopamine pool/receptor equations); `src/flyonenomics/substrate/transmitters.py:37-44,82-90` (co-transmitters classified by single sign); `docs/research/comparable-preprints.md:222-225` (omission audit). |
| 113 | Point neurons share base electrical parameters | `docs/cuda-methods.md:33-40` (shared membrane, synapse and nominal threshold; working threshold may vary with dopamine/genotype); `paper/manuscript.tex:21,108` on main. |
| 113 | Sensory-only background at rest; a silent target cannot show an inhibitory firing-rate reduction, limiting detectable GABA disinhibition where injected input fails to reach | `docs/cuda-methods.md:55` (other background weights zero); `paper/manuscript.tex:21,76` on main; `docs/research/comparable-preprints.md:192-194,222-225` (silent-target implication). |
| 116 | MaleCNS v1.0 public portal and CC BY 4.0, Berg attribution | `docs/research/preprint-availability.md:12-28,51-61,412`; `paper/references-verified.md:48-66`. |
| 116 | Private repository contains model code, reviewed result records and figure sources; reasonable-request access and future public snapshot/archived DOI are draft commitments | `paper/manuscript.tex:114` on main (private code/reviewed results); `paper/figure-fields.md` (figure sources); `docs/research/preprint-availability.md:342-355,412` (Version A, unchanged here; the release script will replace it on go day). |
| 116 | Raw-run public hosting undecided | `paper/manuscript.tex:114` on main; `paper/README.md:70-87`. |
| 119 | Sole author, direction, division of AI tasks, checks not independent replication, ICMJE/COPE and Cell Press disclosure, approval pending in draft only | `paper/manuscript.tex:114` on main (preserved declaration and approval); `--final` omits the approval sentence. |
| 122 | No competing interests | Rolf confirmed on 27 Sep 2026; declaration unchanged. |
| 125 | No external funding | Declaration unchanged. |
| 130 | MaleCNS v1.0, CC BY 4.0 | `paper/references-verified.md:48-66` |
| 144-151 | literature years, volumes, pages and DOI metadata | `paper/references-verified.md:20-21,33-55,70-102`; Zhang et al. 1995, *Molecular Pharmacology* 48:835-840: `docs/research/drug-action-in-network-models.md:444-446` |
| 152-157 | Brian 2, Philox/Random123, CuPy, NVRTC, Brian2CUDA and Knight & Nowotny bibliography years, volumes, pages and identifiers | `docs/research/software-citations.md:18-30,36-40,46-48,53-69,84-112`; verification scopes transcribed in `paper/references-verified.md` |
| 40, 152-157 | Software names and their roles in CPU/GPU implementation | `docs/cuda-methods.md:9,52,69`; `docs/research/software-citations.md:18-30`; agreement wording from `docs/research/cross-simulator-replication.md` section 6 |

## Existing figure labels

- Static anatomy (manuscript 129-130): the printed 100 µm and 200 µm scale bars, 156 TuBu, 282 ring (245 analysed), 27 central-complex dopamine, 332 mushroom-body dopamine and 155 of 4,064 Kenyon cells, plus the up-to-8-per-type sample rule, are documented at `docs/3d-model.md:118-128`. Biological version and CC BY 4.0: `paper/references-verified.md:48-66`. It has no simulation-result overlay.
- Knockout and courtship panels (manuscript 133-138): `docs/tour-figures.md:15-16,21-41`; the printed ±200 and ±10 Hz colour ticks and the 100 µm scale annotation come from the already rendered figures, with the colour cap explained at lines 29-36; scale geometry is documented in `docs/3d-model.md:106-110`. They are not numerical result tests.
- Dose curves (manuscript 141-142): `figures/3d/gaba-dose/curves.svg` is converted without changing its geometry or values; its axes and 95% intervals correspond to `docs/gaba-dose-results.md:15,19-23`. The labelled fraction and multiplier ticks are display positions, not additional measured endpoints. The source SVG is included in the build receipt.

Dose input in manuscript line 78 is dark-rest sensory background only, with no TuBu stimulus: `docs/SPEC-P2.md:1973,2093-2097` describes the design as dark rest (item 162 also contains a contradictory parenthetical about injected TuBu); `docs/gaba-dose-results.md:3` repeats the generic TuBu warning. The dose series reuses the dark-rest control, not a visual stimulation arm (`docs/gaba-dose-results.md:13-15`; `scripts/circuit_tour.py:140-172`, where dose windows have no ON stimulus and input rates remain zero).

`docs/gaba-dose-body.md` was not on main at the lane start. The body paragraph uses only the available courtship playback and makes no claim about a GABA body clip.
