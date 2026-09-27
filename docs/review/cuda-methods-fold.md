# CUDA methods: fold of findings A and B

2026-09-26. Documentation only. The two findings branches were merged first; neither findings file was edited. No simulation, Modal call, new measurement or test suite was run. Checks here consisted of reading source/records, arithmetic on existing JSON values, and inspecting the documentation diff.

## Outcome

**28 fixed / 3 rejected / 22 notes taken**, covering all 53 numbered findings.

| Pass | Fixed | Rejected | Note-taken | Total |
|---|---:|---:|---:|---:|
| A | 12 | 1 | 10 | 23 |
| B | 16 | 2 | 12 | 30 |
| Total | 28 | 3 | 22 | 53 |

All five must-fix findings are fixed. Of 24 should-fix findings, 23 are fixed and the software-paper bibliography expansion (A-12) is explicitly deferred below. The two other rejections concern proposed note wording/a schematic, not unresolved computational corrections. Verdicts refer to the proposed change; partial improvements and reasons are recorded rather than hidden.

The three largest changes:

1. Exact agreement now means identical spikes at every tick on saved events, with dopamine clamped, one network per run, intact or GABA-off; it is not a validation of every CUDA path.
2. The unsupported Brian2 30 s/s claim is gone from all three permitted documents, including the body-scoping diagram and its derived 5–6 minute closed-loop estimate; measured replay timings carry their conditions and no speedup ratio.
3. The comparison now reports the largest mismatches and changed detections, alongside the matching results, and distinguishes them from the separate count-level determinism evidence.

## Rejected findings

- **A-12:** The full proposed software-paper citation expansion is deferred because the local source audit does not verify the Brian2, Random123 or alternative-simulator papers, and this local records/code fold does not invent bibliographic verification; the already verified Shiu/Berg entries were completed, candidate simulator comparisons named, and the existing software-documentation links retained.
- **B-26:** Calling the rate constants “the provider's list rates” is rejected because the evidence is submit-script assumptions, not a dated provider quote; the text instead gives the driver as source and September 2026 as the run period.
- **B-30:** An additional schedule schematic is not added because the two-stage/barrier and delay-ring prose already states the checked schedule and no schedule defect was found.

### Parts of otherwise accepted suggestions not adopted literally

- **B-4 versus A-10:** B's proposed “GABA and glutamate inhibitory, the rest excitatory” is wrong for consensus histamine in this model. `datasets.py:MALE_NT_SIGN` and `substrate/scales.py` make consensus histamine negative, agreeing with A. The special unknown-consensus rule counts only GABA/glutamate site predictions as inhibitory and uses a strict majority; ties are positive. Both rules are now stated separately.
- **A-1 versus B-14:** Both detection counts are correct. The full JSON contains 378 group-rate effects (21 readouts × eight removals, plus 21 × two windows × five stimulation conditions): 45 detection changes and five non-overlapping interval pairs. The Markdown summary selects 110 of those effects, with 14 changes (five removal and nine stimulation, five of the latter after stimulation). The main text identifies the subset instead of treating the counts as contradictory. The two named dPR1 specificity contrasts and the distribution/synchrony statistics are outside the 378 denominator.
- **A-7/B-10:** The 1 ms component changes are consistent with fewer transfers, but do not isolate a causal speed improvement. The 10 ms observation changes from 0.793 to 0.637 s while its kernel-plus-transfer component changes only from 0.644 to 0.627 s. Both facts are retained; unexplained time is not assigned to a bottleneck.
- **A-20 versus B-26:** A's “driver's assumed rates” wins over B's “provider's list rates” on the source evidence; B's request to date the calculation is still met.
- **B-7:** The control selection is “exclude P1 neurons and direct presynaptic partners of pIP10,” not “exclude the direct inputs to both P1 and pIP10” (`populations-male-cns-v1.0.yaml`, `courtship_random.selector.source`). The 68.75 mV event goes into synaptic drive, not directly into voltage; no unconditional claim that it fires an inhibited network neuron is added.
- **A-1:** Low/high realization means are described as two clusters, not as an experimentally established dynamical bistability mechanism; no perturbation or state-stability analysis was recorded.
- **B-22:** The code-supported 32-bit uniform resolution is included, but the proposed numerical binomial-tail bound is omitted because it is not a recorded validation result; no new sampler calculation or known-answer check is substituted for the missing evidence.
- **A-4/B-28:** The kernel-only difference is the explicit-event branch; host-side changes also include event upload/coverage checks and output packing, so they are not reduced to only a transfer change.

## Every finding

IDs prefix the original numbered headings in [pass A](cuda-methods-findings-a.md) and [pass B](cuda-methods-findings-b.md). “Note-taken” means the observation was incorporated or an important existing qualification retained.

| ID | Priority | Verdict | Disposition and checked evidence |
|---|---|---|---|
| A-1 | must-fix | fixed | Added full detection counts, unclear-transmitter wing-motor discrepancy, dopamine-removal dPR1 effect and control-cohort shift; comparison JSON and differences record. |
| A-2 | must-fix | fixed | Summary states clamped dopamine, two streams, intact/GABA-off, single networks and excluded paths; replay plan, JSON and `cuda_identical.py`. |
| A-3 | must-fix | fixed | Replaced 30 s/s in methods, backend and body scoping with conditional Mac replay timings; removed the unsupported derived closed-loop estimate. |
| A-4 | should-fix | fixed | Added ARM/Cython versus x86/L4 provenance, matching archive hashes, shared builder and revision bridge; replay JSON, checks and source diff. |
| A-5 | should-fix | fixed | Replaced “numerically equivalent” with “produced identical spike output”; replay records compare spikes/counts, not voltages. |
| A-6 | should-fix | fixed | Scoped fast timing to a control with count outputs and added slower full-spike replay timings; speed and replay JSON. |
| A-7 | should-fix | fixed | Summary no longer attributes the whole improvement to packing; body reports both interface component pairs and unexplained variation. |
| A-8 | should-fix | fixed | Added matched A100/L4 observation, weak throughput scaling, unknown bottleneck and explicitly non-peak pool sizes; speed JSON. |
| A-9 | should-fix | fixed | Corrected 140 to include ten controls, named eight removals and five stimulations, and explained consensus-label selection; plan and builders. |
| A-10 | should-fix | fixed | Defined directed pairs, synapse-count weights, retention, transmitter signs and gain, with code deciding the histamine disagreement. |
| A-11 | should-fix | fixed | Added pool/occupancy/threshold/gain equations and scoped zero-error diagnostic to 0.2 s, one realization and 20 updates; kernels, CPU equations and checks. |
| A-12 | should-fix | rejected | Full unverified software-paper bibliography deferred; verified anatomy/model references completed and absent comparator benchmarks named. |
| A-13 | should-fix | fixed | Clamped-rest row and measurement definition now say no dopamine updates; `cuda_circuit.py` attaches no modulator in rest mode. |
| A-14 | note | note-taken | Matching paired count effects are explicitly a consequence of matching absolute counts, not independent evidence. |
| A-15 | note | note-taken | Added absence of a rounding-sized perturbation experiment; no state-sensitivity measurement is claimed. |
| A-16 | note | note-taken | Added one-second count identity across batch sizes, devices, chunks and CPU/GPU dopamine, qualified as self-consistency. |
| A-17 | note | note-taken | Added 1.32–1.39 s/brain-s CPU-dopamine pilots and 0.520 of 1.318 s in CPU modulation; plan amendment and speed JSON. |
| A-18 | note | note-taken | Replaced ambiguous population histograms with whole-network spike counts per millisecond; `cuda_tick.cu`. |
| A-19 | note | note-taken | Defined construction work and said components were not timed separately; builder code and speed records. |
| A-20 | note | note-taken | Prices identified as driver's assumptions; added $1.900740 total metered from both receipt sets. |
| A-21 | note | note-taken | Stated absence of a recorded Philox known-answer check; neither exact replay nor distributional comparisons are called sampler validation. |
| A-22 | note | note-taken | Replaced main-text ON/OFF labels with first/second five-second windows; no boundary stimulus switch implied. |
| A-23 | note | note-taken | Retained and strengthened the limit: clamped replay does not settle all earlier free-dopamine/stimulated effects. |
| B-1 | must-fix | fixed | Summary and replay body enumerate tested/excluded paths, one network and 10 ms chunks; direct inspection of replay harness/kernel. |
| B-2 | must-fix | fixed | Removed unsupported timing and retained compilation/extraction, random-input-off and no-dopamine-update caveats on measured Brian2 values. |
| B-3 | should-fix | fixed | Added definitions before equations/results, including interface, settling, realization, substrate, gain, clamp and neuron/courtship groups. |
| B-4 | should-fix | fixed | Added adapter retention/sign rules, correcting B's histamine proposal from source rather than copying it. |
| B-5 | should-fix | fixed | Defined uniform base threshold, occupancy offsets, clipping, genotype factor and 0.02 µM clamp; parameters, rest builder and compose code. |
| B-6 | should-fix | fixed | Wrote explicit Euler pool equation and replaced “unexposed pools” with compartments lacking dopamine innervation. |
| B-7 | should-fix | fixed | Added stimulation event weight, rates, duration and exact random-control selection; parameters, circuit code and population table. |
| B-8 | should-fix | fixed | Count determinism now accompanies the floating-point-order caveat, without asserting arbitrary-run bitwise equality. |
| B-9 | should-fix | fixed | Named ARM Mac/Cython and Linux x86/L4 replay platforms, plus recorded Python and NumPy versions. |
| B-10 | should-fix | fixed | Marked timings as single observations and included the 0.793/0.637 10 ms pair; no isolated packing speedup claim. |
| B-11 | should-fix | fixed | Distinguished throughput from per-member latency, construction amortization and unprofiled A100/L4 difference. |
| B-12 | should-fix | fixed | Explained shared scaled/background weights and disconnection restoration after scaling; `CUDAEngine` and reference setter. |
| B-13 | should-fix | fixed | Corrected 140-run composition and defined 10,000 paired whole-realization percentile resamples, detection and uncorrected multiplicity. |
| B-14 | should-fix | fixed | Included 14/110 selected-table detection changes and their breakdown alongside the full 45/378 count. |
| B-15 | should-fix | fixed | Added medium-P1 versus control effect, control means and absolute stimulated means to explain why the two specificity contrasts agree more closely. |
| B-16 | should-fix | fixed | Explained consensus selection and dopamine removal's additional receptor/transporter-layer disabling, beyond outgoing masks. |
| B-17 | note | note-taken | Explained refractory-dependent background-draw consumption, checked against installed Brian2 PoissonInput/Cython generator and conditional model writes. |
| B-18 | note | note-taken | Added replay input's schedule position after recurrent delivery, at the background-input slot; `syn.pre.order = 0`. |
| B-19 | note | note-taken | Made total explicitly per engine and split 5,453,856 intact / 53,201,566 GABA-off spikes from archive counts. |
| B-20 | note | note-taken | Clamped-rest timing row explicitly excludes dopamine updates, also resolving A-13. |
| B-21 | note | note-taken | Added build-time clustering near 100/270 s and unknown cause; no cache/cold-start explanation invented. |
| B-22 | note | note-taken | Added code-supported 32-bit uniforms and missing known-answer evidence; unrecorded quantitative tail bound not imported. |
| B-23 | note | note-taken | Replaced opaque deterministic-topology wording with general spike-list input at listed ticks; engine support check. |
| B-24 | note | note-taken | Added why A10 replaced L4, confirmed in cancellation receipt; subset caveat retained. |
| B-25 | note | note-taken | Added 18-tick delay and 22-tick refractoriness using the reference conversion rule. |
| B-26 | note | rejected | Provider-list-rate attribution unsupported; used dated driver assumptions instead, as A-20 recommends. |
| B-27 | note | note-taken | Explained whole-network histogram's synchrony use and first-tick latency readout; circuit collection code. |
| B-28 | note | note-taken | Added explicit-event-only kernel revision and one-second count bridge, without extending it to every run. |
| B-29 | note | note-taken | Clarified 32-bit scale factors before 64-bit stored weights in both engines. |
| B-30 | note | rejected | Kept checked two-stage/ring prose without a redundant schematic. |

## Evidence and numerical trace

Paths below are internal audit pointers, not additions to the main scientific narrative. Bare `male-cuda-*` filenames refer to `validation/records/p2/`. JSON arithmetic here summarizes saved measurements; it does not constitute another experiment.

| Claims in the revision | Source checked / derivation |
|---|---|
| 162,517 neurons, 25,120,209 directed pairs; retention and signs | `male-cuda-identical-comparison.json` → `rows[].runs[].n/edges`; `src/flyonenomics/datasets.py` → `_build_derived`, `MALE_NT_SIGN`, `_unknown_neuron_signs`; `docs/SPEC-P2.md` item 150. |
| Group sizes, 147,501 outside sensory, courtship populations | Replay JSON → `group_sizes`; `data/drive-male-cns-v1.0.yaml`; `drive/background.py:group_indices`; `data/populations-male-cns-v1.0.yaml`. Central includes both `cb_intrinsic` and `vnc_intrinsic`; the motor grouping includes efferents. |
| All LIF, background, clamp, receptor and kinetic constants | `data/params-v0.2.yaml` → `lif`, `bg`, `engine`, `input`, `da`, `rec`; drive file → `scales`, `background`, `threshold: null`; `data/dopamine-male-cns-v1.0.yaml` for release coefficients. |
| Weight/sign and unknown-negative scaling | `connectome_arrays.py:base_weight_memmap`, `substrate/scales.py:scale_array`, `drive/rest.py:apply_rest_substrate`; unknown-negative outputs take `g_gaba`, while the KC multiplier selects class `GABA` only. |
| Stimulation 68.75 mV, 10/30/60 Hz, 148-neuron random group, first five-second window | `params-v0.2.yaml` input weight; `cuda_engine.py:ext_weight`; `circuit_tour.py:DRIVE_HZ/build/worker`; population selector cited above; `cuda_circuit.py` input-window loop. |
| Dopamine equations, clip limits, silencing and innervation versus exposure | `cuda_dopamine.cu`, `cuda_dopamine.py`, `neuromod/pools.py`, `neuromod/receptors.py`, `neuromod/state.py:compose/on_chunk`; pool mask is innervation, compose mask is exposure. |
| 0.2 s / 20-update zero-difference diagnostic | `male-cuda-speed.json` diagnostic row: one control, `simulated_s=0.2`, `chunk_ms=1`, dopamine period 10 ms; `male-cuda-checks.json` → `gpu_cpu_modulation_identical_count_diagnostic`. |
| All original 12 timing rows, 97–281 s builds, GPU models and memory pool sizes | `male-cuda-speed.json` → `measurements`; 526,532,096 and 1,281,231,360 bytes in earlier GPU-dopamine L4 pilots, rounded in decimal GB, not a peak-memory estimate. |
| Earlier CPU-dopamine pilots | Speed JSON: 1.317860952, 1.391304050 and 1.350172354 s/brain-s; single-network `neuromod_s=0.519867095`; `male-cuda-plan.md` amendment. |
| 1 ms and 10 ms follow-up table/components | `male-cuda-identical-receipts.json` → final two `calls`; compared with ordinary GPU-dopamine pilot rows in speed JSON, not with full-spike replay timings. |
| Mac replay 3.1–4.0 and 7.0 s/s; CUDA full-spike 1.07–1.13 and 1.78–1.79 s/s | Replay JSON `stepping_s / 12`: Brian2 intact 47.636596997/12 and 36.725904584/12, GABA-off 83.511169624/12 and 83.675319792/12; CUDA intact 13.612112751/12 and 12.899171316/12, GABA-off 21.327326863/12 and 21.446714699/12. Replay Markdown explicitly warns against deriving original-engine speedup. |
| Platforms, versions and independent replay output identity | Replay JSON `machine/python/numpy/brian2/gpu` fields; every paired `counts_sha256` and `spike_files` entry agrees. `brian_engine.py` sets Cython; `scripts/modal/cuda.py` pins CUDA/CuPy. Raw archives were not rerun or downloaded in this fold. |
| Four runs, every count zero-difference, 58,655,422 spikes per engine | Replay JSON `rows/windows/first_spike_divergence/spike_symmetric_difference`; sum each engine's `spike_files[].spikes`: intact 2,818,622 + 2,635,234; GABA-off 26,637,259 + 26,564,307. Group-rate table checked against replay Markdown/JSON. |
| Count determinism over one second: 202,658 spikes | `male-cuda-checks.json` → eight `same_cuda_rng_one_second_count_comparisons`; `male-cuda-identical-checks.json` → two new pilots and four old archive comparisons; `male-cuda-differences.md` explains the CPU/GPU dopamine bridge. Not a factorial sweep of every combination or full-spike identity. |
| Revision bridge | `git diff e4ed836 ce45119 -- src/flyonenomics/engine/cuda_tick.cu src/flyonenomics/engine/cuda_engine.py`: explicit-event kernel arguments/branch, host event loading/coverage, packed outputs; later count checks above. No model parameter change. |
| 140 runs and 10,000-draw 95% intervals | `male-cuda-plan.md`, comparison JSON `absolute_tour_rates`/`tour_seeds`, and `circuit_tour_analysis.py:interval/analyse`; 10,000 paired whole-realization means, 2.5/97.5 percentiles, no multiplicity correction. |
| 45/378, five non-overlaps, 14/110 | Counted saved `paired_effects` intervals for the group keys in `group_sizes` (21 groups), excluding summary statistics, latencies and the two specificity contrasts. The five non-overlaps are unclear/ascending, unclear/descending, unclear/wing motor, random-drive first-window/dPR1 and random-drive first-window/TN1a. The 110 subset is eight removals × five displayed readouts plus five stimuli × two windows × seven displayed circuit readouts. |
| Largest discrepancy and low/high frequencies | Comparison JSON `paired_effects.off-unclear` → wing motor: Brian2 −4.794545 [−14.198955, 3.627746], CUDA −23.347121 [−26.370458, −17.844682]; `absolute_tour_rates.off-unclear.measure.wing_motor` has three/nine low realizations, spanning approximately 4.46–5.00 Hz versus 31.40–35.80 Hz in the high cluster. No fitted cluster threshold was used as a pass criterion. |
| Dopamine-off dPR1 | Comparison JSON `paired_effects.off-dopamine`: Brian2 −4.15 [−8.855, 0.260125], CUDA −8.335 [−11.540125, −4.455], rounded to two decimals in prose. |
| Rest rates, courtship specificity/direct effects, control shift and first spikes | `male-cuda-comparison.md/.json` and `male-cuda-differences.md`; medium-P1 stimulated dPR1 41.62/41.77, controls 22.38/25.77, effects 19.24/16.00 Hz; Brian2 low controls 10.1 and 10.0 Hz. All original rest means, contrasts and latency numbers retained with their qualifications. |
| Cost values and combined total | `scripts/modal/cuda_driver.py:GPU_HOURLY/price`, same assumptions in identical driver; `male-cuda-receipts.json` metered sum $1.49583791 plus identical receipt $0.40490238 = $1.90074029, rounded to $1.900740. Per-brain costs divide metered call charges by batch × duration; rate-derived costs multiply step time by assumed hourly resource price/3600. |
| A10 replacement | `male-cuda-receipts.json` → L4 `cancelled_before_worker` and following A10G submission, with no simulation on cancelled L4 call. |
| Completed bibliography fields | `paper/references-verified.md` Shiu/Berg sections and `docs/data.md` for the Shiu title. Other software-paper citations are not claim-verified there; their absence is not disguised as a completed literature review. |

## What the records cannot settle

- Why particular free-running cohorts differ: stream pairing, free dopamine dynamics and numerical trajectory sensitivity are not separated by the clamped replay.
- The performance bottleneck, the two construction-time clusters, and how much of the packed-interface timing change is causal rather than run-to-run variation.
- Arbitrary-condition or long-run bitwise determinism, full-state CPU/GPU identity, sampler known-answer correctness, and a real-time end-to-end body loop.
- A claim-checked software-paper bibliography and comparisons with alternative GPU simulators; no external literature research or benchmark was done in this fold.

The first three limitations are explicit in the write-up. The bibliography limitation remains a publication follow-up, not an asserted scientific result. Other body-scoping claims were outside this narrowly authorized timing correction and were not re-audited.
