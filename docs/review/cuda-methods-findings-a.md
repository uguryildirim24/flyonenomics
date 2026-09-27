# Findings pass A: `docs/cuda-methods.md`

Checker A, 2026-09-26. Read against main at `e0f03f2` (line numbers are that revision). Independent of checker B. The write-up was not edited.

Sources checked: `docs/cuda-methods.md`, `docs/cuda-backend.md`, every `validation/records/p2/male-cuda-*` record (plans, speed, comparison, differences, checks, receipts, budget update, identical-input plan, inputs, comparison, receipts, checks), the two lane reports (t-0122, t-0131), and the code the text describes (`cuda_tick.cu`, `cuda_dopamine.cu`, `cuda_engine.py`, `scripts/cuda_identical.py`, `scripts/cuda_circuit.py`, `scripts/circuit_tour.py`, `models.py`, the driver price constants, `data/params-v0.2.yaml`, `data/drive-male-cns-v1.0.yaml`).

**Counts:** 3 must-fix, 10 should-fix, 10 notes. Every number in the draft matches its record except the Brian2 "roughly 30 s" figure (finding 3). The appendix lists each number and its record.

---

## Must-fix

### 1. The list of effects that did not carry over is incomplete and leaves out the largest differences

- **Where:** `docs/cuda-methods.md:111`, `:113`
- **Text says:** "Large effects carried over." Then: rest motor and ER, the random-drive dPR1 effect, "Octopamine and serotonin detections also changed", and first-spike medians.
- **Record says** (`male-cuda-comparison.json`, `paired_effects`, `absolute_tour_rates`):
  - Of 378 paired group-rate effects, 45 changed detection status between engines and 5 had non-overlapping 95% intervals. (Counting the summary statistics too, it is 51 of 426.)
  - The largest cross-engine difference in the record is not mentioned: unclear-transmitter removal on wing motor neurons, Brian2 −4.79 [−14.20, 3.63] vs CUDA −23.35 [−26.37, −17.84] Hz, with non-overlapping intervals. The per-realization rates are bimodal. Each realization settled low (about 4.5–5.0 Hz) or high (about 31–36 Hz): 3 of 10 Brian2 and 9 of 10 CUDA realizations were low.
  - The same removal also gave non-overlapping ascending effects (−1.07 [−1.52, −0.68] vs −1.97 [−2.18, −1.70] Hz) and descending effects (−1.57 [−1.74, −1.41] vs −1.99 [−2.29, −1.79] Hz).
  - The dopamine-removal dPR1 effect changed detection status: −4.15 [−8.86, 0.26] vs −8.34 [−11.54, −4.46] Hz. This is the project's own manipulation class, so it matters most for future CUDA experiments.
  - dPR1 effects against control are shifted by the control cohorts themselves. Two Brian2 control realizations fired near 10 Hz in the first window, so the control means were 22.38 vs 25.77 Hz. P1-medium minus control was therefore 19.24 vs 16.00 Hz, although the absolute stimulated means were 41.62 vs 41.77 Hz (`male-cuda-differences.md`). `cuda-backend.md:222-225` says this; the methods draft does not. The two highlighted contrasts (17.81 vs 17.85, 15.19 vs 15.39) agree closely partly because they do not subtract a control.
- **Why it matters:** as written, the section looks like it reports the best-matching numbers and skips the worst. A reviewer who opens the JSON will find the wing-motor row first. The identical-input replay used clamped dopamine and did not include these conditions, so it cannot say which cause applies.
- **Proposed wording** (replace the first two sentences of `:113` and keep the rest):

  > Small effects, bistable readouts and timing were not interchangeable. Of 378 paired group-rate effects, 45 changed detection status between engines and 5 had non-overlapping intervals. With this many uncorrected comparisons, some such differences are expected by chance. The largest followed removal of unclear-transmitter outputs: in each realization, wing motor neurons settled either low (about 5 Hz) or high (about 31–36 Hz). Three of ten Brian2 and nine of ten CUDA realizations were low, giving effects of −4.79 [−14.20, 3.63] versus −23.35 [−26.37, −17.84] Hz. Dopamine removal changed dPR1 firing by −4.15 [−8.86, 0.26] versus −8.34 [−11.54, −4.46] Hz. dPR1 effects measured against control inherit a difference between the control cohorts: two Brian2 control realizations fired near 10 Hz, so control means were 22.38 versus 25.77 Hz, and medium P1 stimulation minus control was 19.24 versus 16.00 Hz, although stimulated means were 41.62 versus 41.77 Hz. The contrasts above do not subtract a control. Rest motor means were …

  At the end of `:115`, add: "The later identical-input replay kept dopamine clamped and did not include these conditions, so it does not show whether these differences come from the random streams, the free dopamine dynamics or numerical sensitivity."

### 2. The Summary states the spike-exact result without its scope

- **Where:** `docs/cuda-methods.md:11` (also the lead claim carried into n-0075)
- **Text says:** "With identical saved background input, all 58,655,422 output spikes matched Brian2 across four 12-second simulations. This establishes spike-output equivalence for the tested inputs, not bitwise equality of internal state."
- **Record says:**
  - Both conditions used clamped dopamine: `male-cuda-identical-plan.md`, and `dopamine: "clamped"` in every run row. In the replay, thresholds and gains were composed once on the host (`scripts/cuda_identical.py:86-93`), and no `CUDADopamine` was attached. Neither GPU dopamine kernel ran. Line 9 introduces those kernels as part of the engine.
  - Only intact rest and GABA outgoing removal were replayed, with two input realizations.
  - Each engine ran one brain per call (`CUDAEngine(record_spikes=True)` defaults to batch 1), so mixed-condition batches were not covered.
  - CUDA read the saved events through the new explicit-event branch (`cuda_tick.cu:65-68`). The Philox binomial sampler and the Bernoulli extended-input path used for experiments were not in the exact test; they are covered only by the earlier distributional comparison.
  - The spike-count total (58,655,422), four runs and 12 s are all correct.
- **Proposed wording:**

  > With identical saved background input and dopamine clamped at its reference level, all 58,655,422 output spikes matched Brian2 in four 12-second simulations: two input realizations, each intact and with GABAergic outgoing connections removed, one network per run. This establishes spike-output equivalence for that setting and input path. It does not cover the random-input samplers, the GPU dopamine kernels, stimulated or batched runs, or bitwise equality of internal state.

### 3. The Brian2 "roughly 30 wall seconds per simulated second" figure has no record, and the project's own records contradict it

- **Where:** `docs/cuda-methods.md:92`
- **Text says:** "The previously reported Brian2 figure of roughly 30 wall seconds per simulated second on a Mac is contextual, not a same-hardware speedup measurement."
- **Record says:**
  - The only source is "The task brief reports about 30 wall s / simulated s" (`male-cuda-speed.json`, `baseline_context`). No measurement backs it. The 30 in `docs/calibration-p2.md:9` is an escalation threshold, not a measurement.
  - The identical-input record timed Brian2 on this model on the Mac (macOS arm64, Cython code generation, one process, stochastic input disabled, one-second run calls, first-run compilation and spike extraction included). Stepping took 36.7–47.6 s per 12 simulated seconds intact (3.1–4.0 s per simulated second) and 83.5–83.7 s with GABA outgoing connections removed (7.0 s per simulated second). Source: `male-cuda-identical-comparison.json`, Brian2 `stepping_s`.
  - `docs/bench.md` B1 measured 17.4–21.0 s per simulated second on a different model (FlyWire v783, 138,639 neurons), with 10 ms run calls and a different input.
  - The replay record itself warns against deriving an engine speedup from its timing.
- **Why it matters:** next to 0.70 s, "30 s" invites a ~40× reading that no record supports. The only same-harness pair is the replay itself, both engines with full spike extraction: Brian2 36.7–47.6 s vs CUDA 12.9–13.6 s per 12 simulated seconds intact, and 83.5–83.7 vs 21.3–21.4 s with GABA outgoing connections removed. That record says not to turn these into an engine speedup, so the write-up should not either.
- **Proposed wording** (replace the last sentence of `:92`):

  > No same-hardware Brian2 benchmark was made, and no speedup ratio is claimed. For context only: in the identical-input harness on a Mac (arm64, Cython code generation, one process, random input disabled, one-second run calls, first-run compilation included), Brian2 stepped this model at 3.1–4.0 wall seconds per simulated second intact and 7.0 with GABAergic outgoing connections removed.

  Or delete the sentence. Either way, fix the same figure in `docs/cuda-backend.md:208-209` and `docs/fly-body-scoping.md:250`.

---

## Should-fix

### 4. The replay's scope and provenance are missing from the body

- **Where:** `docs/cuda-methods.md:119-127`, `:140`
- **Text says:** the replay's design and exact agreement. It does not say where each engine ran, which kernel revision ran, or which paths the replay skipped.
- **Record says:**
  - Brian2 ran on macOS arm64 (Python 3.12.14). CUDA ran on a Linux x86-64 container on an NVIDIA L4 (Python 3.12.1). Every per-second spike archive and count archive is byte-identical across engines (same SHA-256; `male-cuda-identical-comparison.json`, `runs[].spike_files`). This is a strength, and it answers the obvious question of whether the two archives are independent.
  - The replay kernel (`cuda_tick.cu` 6ff6e296…, now on main) differs from the one behind the speed table and the earlier comparison (a34de6bb…, `male-cuda-checks.json`). Between the two (`e4ed836` → `ce45119`), the kernel gained only the explicit-event branch (10 lines), and `cuda_engine.py` gained the packed output buffer and event upload. The bridge evidence: the new 1 ms and 10 ms pilots gave the same per-neuron counts as four older pilots for one control realization (`male-cuda-identical-checks.json`).
  - Network construction (connectivity, weights, substrate scales, thresholds, gains) is the same Python builder for both engines (`scripts/circuit_tour.py` `build`). The replay tests the stepping, not the construction.
- **Proposed wording** (add after `:121`):

  > Brian2 ran on an arm64 Mac and CUDA on an x86-64 cloud container with an NVIDIA L4; the resulting spike and count archives were byte-identical. Both engines were built by the same network-construction code, so the replay tests time stepping, input delivery and disconnection, not construction. Each run held one network. The replay engine differs from the one used for the earlier comparison and most timings only by an explicit-event input branch in the kernel and a single packed output transfer on the host side. For one control realization, both kernels gave identical per-neuron counts over one second.

### 5. "Numerically equivalent" overstates what was compared

- **Where:** `docs/cuda-methods.md:125` (bold sentence)
- **Text says:** "The engines were numerically equivalent in observed spike output for all four tested trajectories."
- **Record says:** every neuron/tick spike pair matched. Voltages and synaptic drive were not recorded (`:140` says so). "Numerically equivalent" reads as a claim about the numbers the engines compute, i.e. state.
- **Proposed wording:**

  > **The engines produced identical spike output in all four tested trajectories.**

### 6. "Faster than real time" depends on activity and on what the host collects; the full-recording timings are missing

- **Where:** `docs/cuda-methods.md:11`, `:53`, `:75`
- **Text says:** 8.420 s stepping per 12 s for one control brain. Line 53 says the replay "exercises this full-recording path" but gives no timing.
- **Record says:**
  - All single-brain ordinary-input timings are control or rest runs. In the replay, which pulls every spike to the host each 10 ms chunk, CUDA took 12.9–13.6 s per 12 simulated seconds intact (1.07–1.13 s per simulated second). With GABA outgoing connections removed, it emitted about ten times as many spikes and took 21.3–21.4 s (1.78–1.79). All four replays were slower than real time. Source: `male-cuda-identical-comparison.json`, CUDA `stepping_s`.
  - The 8.420 s figure is one measurement on the earlier kernel revision.
- **Proposed wording** (add to Measurements after `:92`):

  > Stepping time depends on network activity and on what is returned. The single-network timings above come from control or rest runs returning counts. In the identical-input replay, which also transferred every spike to the host, one network took 1.07–1.13 wall seconds per simulated second intact and 1.78–1.79 with GABAergic outgoing connections removed, when it emitted about ten times as many spikes. Those runs were slower than real time.

  In `:11`, after "8.420 seconds of stepping", add "in a single control run returning counts".

### 7. The 1 ms speed-up is attributed to the transfer change in the Summary; the record's breakdown is more specific

- **Where:** `docs/cuda-methods.md:11`, `:96-103`
- **Text says:** "1.599 … originally and 1.268 after consolidating host transfers" (Summary). The body correctly says the two single measurements don't isolate the change.
- **Record says** (`male-cuda-speed.json`, `male-cuda-identical-receipts.json`):
  - At 1 ms, kernel-plus-transfer time fell from 1.334 to 1.098 s and host collection from 0.128 to 0.067 s. About 0.24 ms per chunk is consistent with removing two synchronous transfers per chunk. A further 0.136 → 0.103 s of stepping time falls in none of the recorded components.
  - At 10 ms, kernel-plus-transfer barely moved (0.644 → 0.627 s). Most of that pilot's gain (0.793 → 0.637) came from the unattributed component (0.134 → 0.001 s).
  - So part of the 1 ms gain fits the transfer change, and part is unexplained.
- **Proposed wording** (Summary):

  > The one-millisecond interface required 1.599 wall seconds per simulated second in one run and 1.268 in one run after the host transfers were combined; it remains slower than real time.

  In `:103`, add: "At 1 ms, kernel-plus-transfer time fell from 1.334 to 1.098 s, consistent with fewer synchronous transfers. At 10 ms it changed little (0.644 to 0.627 s), and most of that pilot's gain came from stepping time outside the recorded components."

### 8. The A100 was slower than the L4 on the same workload; performance limits were not profiled

- **Where:** `docs/cuda-methods.md:82`, `:92`
- **Text says:** line 92 disclaims only the A10 subset.
- **Record says:**
  - The A100 and L4 one-network, one-second, 10 ms pilots are the same workload. The A100 took 0.994 s and the L4 0.793 s (432 vs 232 resident blocks). Single observations.
  - Batch 32 took 24.0 s for one simulated second, 30× the batch-1 time, so batching barely raised throughput per network.
  - The CuPy memory pool size was 0.53 GB at batch 1 and 1.28 GB at batch 32 (`gpu_memory_pool_bytes`; the pool size, not a measured peak). Neither is reported.
  - No profile says whether grid barriers, memory traffic or event delivery bound the step.
- **Proposed wording** (add to `:92`):

  > In the one matched pilot, the A100 was slower than the L4 (0.994 versus 0.793 wall seconds per simulated second); single observations do not rank GPU types. Throughput per network hardly changed from one to 32 networks. The kernel was not profiled, so what limits its speed is unknown. The GPU memory pool held about 0.5 GB for one network and 1.3 GB for 32.

### 9. "140 transmitter-removal or courtship-stimulation outcomes" miscounts, and the conditions are not named

- **Where:** `docs/cuda-methods.md:109`
- **Text says:** "Ten resting realizations and 140 transmitter-removal or courtship-stimulation outcomes".
- **Record says:** 140 = 14 conditions × 10 realizations (`male-cuda-plan.md`, `male-cuda-comparison.json` `absolute_tour_rates`). That is 10 controls, 80 removals (acetylcholine, GABA, glutamate, histamine, dopamine, octopamine, serotonin, unclear) and 50 stimulations (P1 at three rates, pIP10, random population). The draft names neither list, and it never says the removal set comes from each neuron's consensus transmitter annotation (`scripts/circuit_tour.py:116-126`).
- **Proposed wording:**

  > Ten resting realizations and 140 further runs (ten realizations each of a control, eight removals of one transmitter class's outgoing connections — acetylcholine, GABA, glutamate, histamine, dopamine, octopamine, serotonin and neurons without a clear transmitter label — and five injections: P1 at three rates, pIP10 and a random population) were evaluated with the same analysis in both engines.

### 10. The model definition leaves out sign rules, the retention rule and what "connection" means

- **Where:** `docs/cuda-methods.md:9`, `:17`, `:26`, `:37`
- **Text says:** "25,120,209 directed connections" (line 9), then "0.275 mV times the signed connection count" (line 26). It also says "follows the existing model" for thresholds, and uses "postsynaptic gain" (line 37) without defining it.
- **Record/code says:**
  - The 25,120,209 are directed neuron-to-neuron pairs (`engine.n_syn` = rows of the connectivity file).
  - The weight is 0.275 mV × the pair's synapse count × the presynaptic sign (`connectome_arrays.base_weight_memmap`).
  - Classes are ACh, Glu, GABA, His, modulatory and unknown (`data/transmitters-male-cns-v1.0.yaml`). The substrate scales glutamate by 4 and GABA onto Kenyon cells by 6. Unknown negatives take the GABA scale (`data/drive-male-cns-v1.0.yaml`).
  - Thresholds and gains are per-neuron values composed from the rest substrate and dopamine receptor occupancy (see finding 11). With dopamine clamped, they are fixed per neuron.
- **Proposed wording:**
  - Line 9: "25,120,209 directed neuron-to-neuron connections".
  - Line 26: "Base synaptic strength is 0.275 mV times the connection's synapse count, signed by the presynaptic neuron's transmitter class (acetylcholine excitatory; GABA, glutamate and histamine inhibitory; [state the rule for modulatory and unlabelled classes])."
  - Line 26 or 37: add one sentence defining the per-neuron threshold and the postsynaptic gain as the outputs of the dopamine composition step in finding 11.
  - Line 17: state the adapter's retention rule in one clause (which cells or edges are dropped), or cite where it is specified.

### 11. The dopamine equations are not written down, and the zero-difference diagnostic is not explained

- **Where:** `docs/cuda-methods.md:63-65`
- **Text says:** "applies the existing release and clearance equations" and "calculates D1/D2 occupancy and applies the existing threshold and gain rules". The 0.2 s diagnostic had all-zero differences.
- **Code/record says** (`cuda_dopamine.cu`):
  - Pools advance by explicit Euler every 10 ms: C ← max(0, C + r·(α·Σ m·spikes + s·Δt) − (Vmax·C/(Km+C) + k_ns·C)·Δt).
  - Occupancy is D/(D+K_d) for each receptor class.
  - Threshold shift is −Δv₁·r₁·occ₁ + Δv₂·r₂·occ₂, and gain is g_geno·(1 + γ₁·r₁·occ₁ − γ₂·r₂·occ₂), where g_geno is the genotype gain factor. Both are clipped to bounds, and silenced neurons get a fixed threshold.
  - These use only IEEE-rounded +, −, ×, ÷ and min/max, with contraction disabled. That is why bit-exact agreement with the CPU code is possible.
  - The diagnostic covered one control realization for 0.2 s (20 pool updates) with 1 ms chunks (`male-cuda-checks.json`).
- **Proposed wording:** add the two update equations, and:

  > Pools advance by an explicit Euler step every 10 ms and are floored at zero. The kernels use only basic floating-point operations in the CPU code's order, with contraction disabled, so exact agreement is possible. In a 0.2-second diagnostic (20 pool updates, one control realization) driven by identical spike counts, maximum absolute GPU-versus-CPU differences in pools, thresholds and gains were zero. Longer free-dopamine runs were compared only through their firing statistics.

### 12. Related work and software citations are missing

- **Where:** `docs/cuda-methods.md:156`, `:160-163`
- **Text says:** "Publication would also require positioning against other GPU simulators", but none is named. Brian2 is cited only through its documentation site. The Philox generator is uncited. The Shiu et al. entry has no title, and Berg et al. has no volume or pages.
- **Record says:** `paper/references-verified.md` confirms Berg et al., *Cell* 189:5504–5526.e15 (2026). Nothing in the repo covers the rest.
- **Why it matters:** the first question a reviewer will ask is why not Brian2CUDA or Brian2GeNN, which generate GPU code from the same Brian2 model.
- **Proposed wording:** add one related-work paragraph naming GeNN / Brian2GeNN, Brian2CUDA and NEST GPU, and say no comparison with them was run. Cite Brian2 (Stimberg et al., eLife 2019) and Random123/Philox (Salmon et al., SC 2011) for the generator. Complete the Shiu and Berg entries. Verify each through `paper/references-verified.md` before it lands; I did not verify these here.

### 13. Clamped rest row: "Stepping includes dopamine" is not true for that row

- **Where:** `docs/cuda-methods.md:75`, `:83`
- **Text says:** "Stepping includes dopamine, output transfers and host result collection."
- **Code says:** clamped rest attaches no GPU dopamine (`scripts/cuda_circuit.py:67-69`, `if not rest`). The 0.8510 row has no dopamine kernel.
- **Proposed wording:** label the row "L4, clamped rest (no dopamine update)". Change `:75` to "Stepping includes dopamine updates where dopamine is free, output transfers and host result collection."

---

## Notes

### 14. The matching per-neuron GABA effects add no separate evidence

- **Where:** `docs/cuda-methods.md:125`
- **Says:** "Per-neuron GABA-minus-intact count effects also matched exactly."
- **Note:** this follows from the absolute counts matching. Keep it, but don't present it as a second result. Suggested: "Because every count matched, the per-neuron GABA-minus-intact effects are also identical."

### 15. Sensitivity to rounding was not measured

- **Where:** `docs/cuda-methods.md:71`, `:140`
- **Says:** "Threshold crossings can amplify very small differences into different later spike trains."
- **Note:** asserted, not shown. No run perturbed the state by a rounding-sized amount, and voltages were not compared. So the exact match can't tell apart "rounding differences never decided a threshold crossing" and "the network damps such differences". Suggested addition to `:140`: "No perturbation test measured how quickly a rounding-sized difference would change the spike output in this network."

### 16. Evidence of run-to-run determinism exists but is not reported

- **Where:** `docs/cuda-methods.md:71`, `:103`
- **Record:** in stochastic mode, the same control realization gave identical per-neuron counts over one second across L4 and A100, batch 1/8/32, CPU and GPU dopamine, and 1 and 10 ms chunks: eight earlier pilots (`male-cuda-checks.json`) plus the two new ones.
- **Note:** despite atomic accumulation, CUDA outputs were reproducible at the count level. Suggested addition after `:71`: "In stochastic mode, repeated CUDA runs of one control realization gave identical one-second per-neuron counts across two GPU types, batch sizes of 1, 8 and 32, and both interface widths." (Counts only, one second.)

### 17. Earlier CPU-dopamine pilots are left out of the speed table

- **Where:** `docs/cuda-methods.md:77-90`
- **Record:** three pilots with CPU dopamine composition ran at 1.318, 1.391 and 1.350 s per network-second (batches 1, 8, 32). The plan amendment moved dopamine to the GPU because 0.520 of 1.318 s went to CPU composition (`male-cuda-plan.md`).
- **Note:** one sentence would show why the dopamine kernels exist: "Before the dopamine step moved to the GPU, one-second pilots took 1.32–1.39 wall seconds per simulated second, with 0.52 s of the single-network run in CPU composition."

### 18. "One-millisecond population histograms" is ambiguous

- **Where:** `docs/cuda-methods.md:53`
- **Code:** `hist` is the whole-network spike total per millisecond per network (`cuda_tick.cu:61`), not per population.
- **Suggested:** "whole-network spike counts per millisecond".

### 19. Construction time is large and unexplained

- **Where:** `docs/cuda-methods.md:92`
- **Record:** CUDA construction took 97–281 s. In the replay, Brian2 construction on the Mac took 35–43 s (different machine).
- **Note:** a reader will ask what dominates it. Suggested: one clause on what construction includes (reading the tables from the cloud volume, sorting edges into CSR form, applying the substrate, uploading, compiling the kernel), or "its components were not timed separately."

### 20. Cost wording

- **Where:** `docs/cuda-methods.md:144`, `:148`
- **Record:** "requested resource rates" are the driver's assumed prices (`scripts/modal/cuda_driver.py:42`), not a Modal quote. All figures match: $0.000199, $0.006959, $0.000306–$0.000463, $0.000577, $0.074840, $0.000641, $1.495838, $0.40490238, $0.000360, $0.000181.
- **Suggested:**
  - "Using the driver's assumed Modal rates of …"
  - Add the total: "All GPU work described here cost $1.900740 metered."

### 21. Philox and the binomial sampler have no direct check

- **Where:** `docs/cuda-methods.md:57-59`
- **Code/record:** the Philox4x32-10 routine (`cuda_tick.cu:8-20`) has no recorded known-answer check against Random123, and there are no tests for `CUDAEngine`. The sampler's correctness rests on distributional agreement, e.g. sensory rest rates of 0.894 vs 0.895 Hz in `male-cuda-comparison.md`.
- **Suggested:** "The generator was not checked against reference Philox output; its input statistics are supported only by the distributional comparison below."

### 22. "ON"/"OFF" are harness window names

- **Where:** `docs/cuda-methods.md:123`
- **Note:** n-0051 keeps arm and harness codes out of paper text. The draft explains the names, but for a paper, "first and second five-second windows" reads better and removes the need to explain them.

### 23. Keep line 140's limit as written

- **Where:** `docs/cuda-methods.md:140`
- **Note:** the coordinator fact n-0075 says "Earlier small-effect differences were random-stream differences only". The replay does not show that: it was clamped, unstimulated, and excluded the conditions in finding 1. Line 140 of the draft states the limit correctly. The fold should keep it and not adopt the stronger phrase.

---

## Appendix: numbers checked against records

| Line | Number(s) | Record | Status |
|---|---|---|---|
| 9 | 162,517 neurons; 25,120,209 connections | `male-cuda-identical-comparison.json` runs `n`, `edges` | match (see 10 on wording) |
| 11 | 8.420 s / 12 s, 10 ms | `male-cuda-speed.json` tour batch 1 | match |
| 11 | 1.599, 1.268 | speed.json 1 ms pilot; identical receipts | match (see 7) |
| 11, 127 | 58,655,422 spikes, four 12 s runs | sum of `spike_files[].spikes` per backend; `male-cuda-identical-checks.json` | match |
| 26 | −52, −45, 20, 5, 0.1, 2.2, 1.8 ms, 0.275 mV | `data/params-v0.2.yaml` | match |
| 26 | glutamate ×4, GABA→KC ×6, others 1 | `data/drive-male-cns-v1.0.yaml` scales | match |
| 39 | 15,016 sensory, 1 mV, Binomial(100, 0.001) | drive file `w_bg`; params `n_bg`, `r_bg`; inputs manifest | match |
| 45 | 100 / 10 ticks per chunk | `cuda_engine.run_chunk` | match |
| 51 | 19 slots, 18 ticks | `cuda_tick.cu:88`, delay 1.8 ms / 0.1 ms | match |
| 65 | 0.2 s, all-zero differences | `male-cuda-checks.json` | match |
| 69 | float64, FMA off, int32, uint8 | `cuda_engine.py:91`, arrays | match |
| 79–90 | all 12 rows | `male-cuda-speed.md/.json` | match |
| 92 | 97–281 s build | speed rows 97.41–280.54 | match |
| 92 | ~30 s Brian2 | none | no record (finding 3) |
| 100–101 | 112.794 / 1.268480 / 1.098067 / 115.643; 96.910 / 0.637029 / 0.626633 / 99.661 | `male-cuda-identical-receipts.json` calls 5–6 | match |
| 103 | identical pilot counts | `male-cuda-identical-checks.json` | match |
| 109 | rest means 4.78950/4.78085, 1.51439/1.51117, 0.0102338/0.0102092 | `male-cuda-comparison.md` rest | match |
| 109 | "140 … outcomes" | 14 × 10 incl. controls | miscount (finding 9) |
| 111 | −1.43633/−1.44098, +12.58842/+12.60250, +10.77944/+10.76028 | comparison JSON `outside_sensory` | match |
| 111 | 17.81 [15.81, 19.82] / 17.85 [16.48, 19.16]; 15.19 [13.18, 17.53] / 15.39 [13.94, 17.42] | `paired_effects` contrasts | match |
| 113 | 6.646/6.282; 0.474/0.533; +1.43 [−0.76, 3.96] / −1.85 [−2.77, −1.20]; 22.5/58.5 ms | comparison and differences records | match (incomplete, finding 1) |
| 125 | 162,517 exact, all statistics zero | identical comparison `windows` | match |
| 133–138 | all 12 group means | `male-cuda-identical-comparison.md` | match |
| 144 | $0.80, $0.0473 × 2, $0.008 × 16; $0.000199; $0.006959 | driver price line; tour batch-1 metered $0.08351254 / 12 | match |
| 146 | $0.000306–$0.000463; $0.000577; $0.074840; $0.000641; $1.10, $2.10 | receipts per app | match |
| 148 | $1.495838; $0.40490238; $0.000360; $0.000181; $5 | receipts; identical receipts | match |
| 152 | CUDA 12.6.3, CuPy 13.6.0, Brian2 2.10.1 | `scripts/modal/cuda.py:11-14`; run rows | match |
