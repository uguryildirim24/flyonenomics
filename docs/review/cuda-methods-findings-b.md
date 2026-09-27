# Findings B: `docs/cuda-methods.md`

Checker B. Independent pass on the GPU engine methods draft, 2026-09-26. The draft was not edited.

**Counts:** 2 must-fix, 14 should-fix, 14 note.

**Read:** `docs/cuda-methods.md` first, cold, as a journal reviewer would. Then `docs/cuda-backend.md`; `src/flyonenomics/engine/{cuda_engine.py,cuda_tick.cu,cuda_dopamine.py,cuda_dopamine.cu,brian_engine.py,models.py}`; `src/flyonenomics/neuromod/{pools.py,receptors.py,state.py}`; `src/flyonenomics/drive/{rest.py,background.py}`; `scripts/{cuda_circuit.py,cuda_identical.py,circuit_tour.py,circuit_tour_analysis.py}`; `scripts/modal/cuda*.py`; every `validation/records/p2/male-cuda-*` record; the installed Brian2 2.10.1 PoissonInput, binomial and Cython code generator. Line numbers are at commit `e0f03f2`. Nothing was run on Modal, and no tests were written or run.

## What checks out

The tick schedule in the text is the schedule in the code, and it matches Brian2's:

- **Integration.** The analytic update (lines 28–35) is correct for the stated equations. `cuda_engine.py:69-70` computes exactly those factors, and `cuda_tick.cu:46-53` applies them.
- **Threshold, reset and refractoriness.** The threshold is strict. Reset sets v to −52 mV and g to 0. The refractory period is 22 ticks, from Brian2's own `timestep()` rounding (`cuda_engine.py:64`), and both state variables are frozen during it (`cuda_tick.cu:48-62`). Arrivals, background and stimulation are all rejected while a neuron is refractory, including on its firing tick (`cuda_tick.cu:63-82, 99`). This matches Brian2's `(unless refractory)` conditional writes (`models.py:16-17`).
- **Delay.** The ring has 19 slots. A spike is delivered 18 ticks later and first affects the next update (`cuda_tick.cu:40, 88-101`), which is Brian2's order.
- **Background.** Background input is Binomial(100, 0.001), sampled by inversion (`cuda_tick.cu:69-78`). The 15,016 sensory neurons get 1 mV per event and every other neuron gets 0 (`drive-male-cns-v1.0.yaml:45`).
- **Stimulation.** Stimulation is one Bernoulli draw per target per tick, matching Brian2's one-to-one PoissonGroup (`brian_engine.py:462-478`).
- **Disconnection.** A knockout masks every outgoing edge of each chosen neuron and leaves that neuron's own firing intact. This is equivalent to `BrianEngine.disconnect` zeroing those weights.
- **Dopamine kernels.** Both are literal ports of `pools.euler_step` and `Neuromod.compose`, and they run at the 10 ms cadence even with 1 ms chunks (`cuda_dopamine.py:63-84`).
- **Precision.** The code sets `--fmad=false` and does not enable fast math (`cuda_engine.py:91`).

Every number in the text that I traced matches its record:

- speed table and interface table (`male-cuda-speed.md`, `male-cuda-identical-receipts.json`);
- costs (rates × times, metered ÷ brain-seconds);
- rest means, knockout effects and contrasts (`male-cuda-comparison.md`);
- replay group rates (`male-cuda-identical-comparison.md:37-89`);
- 58,655,422 spikes and 162,517 exact per-neuron matches.

The problems are scope, missing definitions and a few statements that the code or records contradict or don't support.

---

## Must-fix

### 1. The equivalence claim is broader than what the replay exercised

- **Where:** `docs/cuda-methods.md:11`, `:125`, `:140`. The same scope question also applies to `:57`, `:59` and `:63`.
- **Text says:** "With identical saved background input, all 58,655,422 output spikes matched Brian2 … This establishes spike-output equivalence for the tested inputs" (:11). "**The engines were numerically equivalent in observed spike output for all four tested trajectories.**" (:125). A reader naturally applies this to the engine as described in the GPU design section, meaning the Philox background, stimulation, dopamine kernels and batching. The project fact n-0075 already reads it that way: "new experiments may run on the CUDA backend".
- **Code says:** the replay bypassed most of those paths.
  - The events came from NumPy's PCG64 `binomial`, not from either engine's sampler (`scripts/cuda_identical.py:43-47`). The CUDA side used the explicit-event branch (`cuda_identical.py:128-130`; `cuda_tick.cu:65-68`), so the Philox generator and the inversion sampler (`cuda_tick.cu:8-20, 69-78`) never ran.
  - Stimulation rates stayed at zero (`cuda_identical.py:113`), so the Bernoulli path never ran.
  - No `CUDADopamine` was attached. `cuda_identical.py` builds a bare `CUDAEngine` (:86), clamps once, composes thresholds and gains once (:89-93) and never imports the modulator. The modulator is attached only in `cuda_circuit.py:67-69`. On the Brian2 side, `_net.run(1000 ms)` has no host dopamine step (:136). Neither pool nor composition kernel ran in either engine.
  - Batch size was 1 (`cuda_identical.py:86`) and the interface was 10 ms only (:142).
  - There was no synaptic weight scaling beyond the rest substrate, and no silencing or threshold shifts.
- **What the replay did cover:** the LIF update, threshold, reset and refractory rule, CSR delivery through the delay ring, the per-source disconnection mask, the explicit-event background path and full spike recording.
- **Evidence for the rest is weaker and should be named:**
  - the earlier independent-stream comparison, which matches at distribution level only (:107-115);
  - the 0.2 s pool and composition diagnostic (:65);
  - CUDA-to-CUDA count identity across batch sizes, chunk widths, GPUs and CPU-versus-GPU dopamine (finding 8). That is self-consistency, not agreement with Brian2.
- **Proposed wording** (replace the fourth and fifth sentences of :11):
  > With identical saved background input, supplied to both engines as explicit event lists, all 58,655,422 output spikes of each engine matched across four 12-second simulations. That replay exercised the neuron update, refractory rule, delayed delivery, outgoing disconnection and full spike recording at batch size one. It did not exercise the GPU's own random background sampler, stimulation input, dopamine kernels, multi-brain batches or the 1 ms interface. Those rest on the earlier distribution-level comparison and on separate diagnostics.
- **Proposed wording** (new paragraph after :127, headed "What the replay covers"): the same list, plus "Dopamine was held at its reference concentration by composing thresholds and gains once before the run; neither engine executed dopamine updates during the replay."

### 2. The 30 s/s Brian2 context figure has no measurement behind it, and the records contain a different one

- **Where:** `docs/cuda-methods.md:92`.
- **Text says:** "The previously reported Brian2 figure of roughly 30 wall seconds per simulated second on a Mac is contextual, not a same-hardware speedup measurement."
- **Record says:** `male-cuda-speed.md:27` says: "The task brief reports about 30 wall s / simulated s for Brian2 on this Mac". So the source is a task brief, not a measurement. The only Brian2 timings in the CUDA records are the replay runs on that Mac. In `male-cuda-identical-comparison.json` (`stepping_s` at :132, :656, :1180, :1704) they are 36.7–83.7 s per 12-second run, which is 3.1–7.0 wall s per simulated second. That harness disables random input, skips dopamine updates and runs one-second segments, and `male-cuda-identical-comparison.md:104-108` warns against deriving a speed-up from it. A reviewer who opens the records finds a figure four to ten times smaller than the text's.
- **Proposed wording:** delete the sentence, or replace it with:
  > No like-for-like Brian2 timing was made, so no speed-up is claimed. For orientation only: in the replay harness (random input disabled, no dopamine updates, one-second segments), Brian2 on an Apple-silicon laptop took 3.1–7.0 wall seconds per simulated second. That figure includes first-run compilation and spike extraction, so it is an upper bound on its stepping time.
- **Also:** `male-cuda-identical-comparison.md:104-108` says the Brian2 step column includes first-run Cython compilation and spike extraction. Any folded figure must carry that caveat, or it repeats the error this finding is about.

---

## Should-fix

### 3. Terms a reader outside the project cannot decode

- **Where:** `docs/cuda-methods.md:9-13, 45, 75, 109-113, 119-123, 131-138`.
- **Text uses without definition:**
  - "interface" (:11, first use; it means the host–GPU exchange period, i.e. the chunk length);
  - "settling" (:92, :123);
  - "realization" (:109);
  - "resting substrate" and "adopted substrate" (:17, :26);
  - "TuBu" (:13);
  - "central neurons", "outside sensory population", "dopamine neurons", "Kenyon cells", "ellipsoid-body ring neurons", "motor neurons" (:109-113, :131-138);
  - "P1", "dPR1", "pIP10", "random-population stimulation" (:111-113);
  - "gain" (:37, :57, :63);
  - "clamped" (:39).
- **Code or record says:**
  - The twelve drive groups partition all 162,517 neurons. They come from MaleCNS `super_class` annotations, with dopamine neurons, Kenyon cells and ER cells carved out by the population registry (`drive/background.py:114-132`). Sizes: central 39,533; optic 89,353; sensory 15,016; visual projection 9,203; Kenyon cells 4,064; ascending 1,849; descending 1,314; motor 887; visual centrifugal 562; dopamine neurons 367; ER 282; endocrine 87 (`drive-male-cns-v1.0.yaml:15-51`).
  - "Outside sensory" means all 147,501 non-sensory neurons (`cuda_circuit.py:55`).
  - dPR1 has 2 neurons, pIP10 2, P1 148 (`male-cuda-identical-comparison.md:37-60`).
  - "Settling" is simply the first 2 s, discarded, from initial state v = v₀ and g = 0 (`cuda_circuit.py:71`). It is not a convergence rule.
- **Proposed wording:** add a short definitions table after :17:
  > | Term | Meaning here |
  > |---|---|
  > | Interface (chunk) | Simulated time the GPU advances per launch before returning counts to the host: 10 ms standard, 1 ms tested |
  > | Brain-second | One simulated second of one complete network |
  > | Settling | The first 2 simulated seconds, started from v = v₀ and g = 0 and excluded from counts |
  > | Realization | One run with one random-input stream |
  > | Neuron groups | Twelve groups partitioning all neurons by MaleCNS super-class, with dopamine neurons (367), Kenyon cells (4,064) and ellipsoid-body ring (ER) neurons (282) separated out. Central 39,533; sensory 15,016; motor 887. "Outside sensory" is every non-sensory neuron (147,501) |
  > | P1, pIP10, dPR1 | Named courtship-circuit cell types (148, 2 and 2 neurons). dPR1 is the readout |
  > | Gain | A per-neuron multiplier on incoming synaptic weights, set by dopamine receptor occupancy |
  > | Clamped | Dopamine held at its reference concentration, so thresholds and gains stay constant |
  > | TuBu | Tuberculo-bulbar neurons, where visual input is injected elsewhere in the project |

### 4. The node and edge retention rule and the sign rule are not stated

- **Where:** `docs/cuda-methods.md:9, 17, 26`.
- **Text says:** neurons and connections are "retained using the repository's dataset adapter" (:17), and base strength is "0.275 mV times the signed connection count" (:26). What decides retention and sign is never said.
- **Record says:** `docs/SPEC-P2.md:1941` (item 150): the model keeps the 162,517 traced and typed neurons out of 211,577 annotation rows, and keeps every aggregated directed pair with no weight cut, giving 25,120,209 edges. `datasets.py:265-350` shows the sign rule: GABA and glutamate inhibitory, all other transmitters excitatory, and neurons without a consensus transmitter signed once from the majority of their per-T-bar predictions.
- **Proposed wording** (replace the second sentence of :17 and extend :26):
  > The model keeps the 162,517 traced and typed neurons of the release and every aggregated directed neuron pair with at least one synapse (25,120,209 edges; no weight cut). Each edge's sign follows its presynaptic neuron's predicted transmitter: GABA and glutamate are inhibitory, the rest excitatory. A neuron without a consensus transmitter takes the majority sign of its individual synapse predictions. Base strength is 0.275 mV times the signed synapse count of the pair.

### 5. How thresholds and gains are set, and what "clamped" means, is vague

- **Where:** `docs/cuda-methods.md:26, 37, 39, 63`.
- **Text says:** "Resting and dopamine-related threshold composition follows the existing model rather than replacing the nominal threshold everywhere" (:26). The text never defines "gain". "Dopamine pools are clamped to their reference concentration" (:39).
- **Code says:**
  - Every neuron's base threshold is exactly −45 mV, because the adopted substrate has `threshold: null` (`drive-male-cns-v1.0.yaml:52`; `drive/rest.py:688-690`).
  - The threshold actually used is clip(−45 + genotype shift + ΔV_DA, −52, −30) mV, where ΔV_DA = −dV_D1·r1·occ1 + dV_D2·r2·occ2 and occ = [DA]/([DA] + Kd) for neurons exposed to a dopamine compartment (`neuromod/receptors.py:15-19`; `state.py:300-306`; `cuda_dopamine.cu:30-41`; clip limits at `params-v0.2.yaml:78`).
  - Gain is clip(genotype gain × (1 + γ1·r1·occ1 − γ2·r2·occ2), 0.2, 3.0) (`params-v0.2.yaml:77`).
  - Silenced neurons get a threshold of 10⁶ mV (`params-v0.2.yaml:20`).
  - "Clamped" pins every compartment at DA_ref = 0.02 µM (`params-v0.2.yaml:62`), so each exposed neuron keeps a constant, nonzero receptor offset. Clamping holds the dopamine effect fixed; it does not remove it.
- **Proposed wording** (replace the sentence at :26):
  > Every neuron starts from the nominal −45 mV threshold. Its working threshold adds any genotype shift and a dopamine receptor offset, −dV_D1·r1·occ1 + dV_D2·r2·occ2. Here r1 and r2 are the neuron's D1 and D2 receptor densities, and occ = [DA]/([DA] + K_d) is receptor occupancy at the exposure-weighted dopamine concentration of the compartments the neuron sits in; unexposed neurons have zero occupancy. The result is clipped to −52 to −30 mV. The postsynaptic gain, which multiplies incoming weights, is 1 + γ1·r1·occ1 − γ2·r2·occ2, clipped to 0.2–3.0.
- **Proposed wording** (append to :39):
  > Clamping holds every compartment at 0.02 µM, so each exposed neuron keeps the constant receptor offset of that concentration.

### 6. The dopamine pool equation is not written, and "unexposed" names the wrong thing

- **Where:** `docs/cuda-methods.md:63`.
- **Text says:** "applies the existing release and clearance equations. Clearance combines saturating transporter uptake with linear non-transporter loss. … Clamped or unexposed pools retain the reference concentration."
- **Code says:** the kernel resets a compartment to DA_ref when `clamped[b] || !mask[c]` (`cuda_dopamine.cu:10`). Here `mask` is `innervated_mask`, meaning compartments that receive any dopamine-neuron innervation (`pools.py:9-11, 52`). Exposure is a per-neuron property used only in composition (`cuda_dopamine.cu:34-35`). The update is one explicit Euler step per 10 ms (`cuda_dopamine.cu:13-16`; `pools.py:49-52`). The kinetic constants are Vmax 0.11 µM/s, Km 1.3 µM and k_ns 0.05 s⁻¹ (`params-v0.2.yaml:66-68`), and the release constants come from `data/dopamine-male-cns-v1.0.yaml`.
- **Proposed wording** (replace :63's second and last sentences):
  > Each 10 ms, compartment c advances by one explicit Euler step, DA ← max(0, DA + rel·(α_c·Σ_i M_ci n_i + S_c·Δt) − (V_max·DA/(K_m + DA) + k_ns·DA)·Δt), where n_i are the neurons' spike counts in the step and M is the dopamine-neuron innervation matrix. Compartments that no dopamine neuron innervates, and all compartments when clamped, stay at the reference concentration.

### 7. Stimulation strength, rates and targets are missing

- **Where:** `docs/cuda-methods.md:13, 59, 111`.
- **Text says:** "direct injection into named courtship populations" (:13) and "Extended PoissonGroup-style stimulation uses one Bernoulli draw per target and tick" (:59). No weight or rate is given.
- **Code says:** each stimulation event adds w_syn × f_poi = 0.275 × 250 = **68.75 mV** to g (`cuda_engine.py:75`; `params-v0.2.yaml:24-25`). That is ten times the 7 mV gap from rest to threshold. Rates were 10, 30 and 60 Hz for P1 low, medium and high, and 30 Hz for pIP10 and the random control (`circuit_tour.py:26, 165-168`). Targets are one virtual source per neuron in the union of P1, pIP10 and the random control population (`circuit_tour.py:86`; `brian_engine.py:476-478`). The random control is 148 cholinergic central-brain intrinsic neurons, the same size as P1, excluding P1 and pIP10's direct presynaptic partners (`populations-male-cns-v1.0.yaml:2400-2403`). Stimulation is applied only in the first 5 s window.
- **Proposed wording** (append to :59):
  > Each stimulation event adds 68.75 mV to the target's synaptic drive (0.275 mV × 250, the reference's input weight), enough to fire it from rest. The courtship comparison drove P1 at 10, 30 or 60 Hz, and pIP10 or a random control at 30 Hz, during the first five-second window only. The random control is 148 cholinergic central-brain neurons, matching P1's size, that exclude P1 and pIP10's direct inputs.

### 8. The engine's own determinism evidence is left out, next to a sentence that implies nondeterminism

- **Where:** `docs/cuda-methods.md:71, 103, 166`.
- **Text says:** "Atomic additions can arrive in different orders" (:71). The only related evidence is "verify per-neuron count agreement between the interface pilots and existing GPU pilots" (:166).
- **Record says:** in `male-cuda-checks.json:7-70` and `male-cuda-identical-checks.json:3-49`, the same one-second stochastic control produced identical per-neuron counts for all 162,517 neurons (202,658 spikes) across:
  - batch sizes 1, 8 and 32;
  - CPU and GPU dopamine;
  - 1 ms and 10 ms interfaces;
  - an L4 (232 blocks) and an A100 (432 blocks).

  `male-cuda-differences.md:63` states this, but the methods text does not. A reviewer will ask whether the GPU result is reproducible run to run, given the floating-point atomics.
- **Proposed wording** (after :71):
  > Floating-point atomics make bitwise run-to-run identity unguaranteed. In practice, one second of the same stochastic control produced identical per-neuron spike counts across batch sizes 1, 8 and 32, CPU and GPU dopamine, 1 ms and 10 ms interfaces, and two GPU models with different block counts.

### 9. The platforms and code-generation target are not named

- **Where:** `docs/cuda-methods.md:121, 152`.
- **Text says:** "The implementation was measured with CUDA 12.6.3 and CuPy 13.6.0; the reference uses Brian2 2.10.1." It does not say where Brian2 ran or how it generated code.
- **Record says:** the Brian2 replays ran on `macOS-27.0-arm64` and the CUDA replays on `Linux … x86_64` with an NVIDIA L4 (`male-cuda-identical-comparison.json:126, 339`). Brian2 used the Cython code-generation target (`brian_engine.py:90`). Both sides used NumPy 2.5.3. Python was 3.12.14 on the Mac and 3.12.1 in the container. Exact equality across an ARM CPU and an NVIDIA GPU is part of what the result shows, and a reader needs to know it.
- **Proposed wording** (append to :152):
  > The Brian2 reference ran with Cython code generation on an Apple-silicon (arm64) laptop; the CUDA runs used x86-64 cloud containers. Both used NumPy 2.5.3.

### 10. The speed numbers are single runs whose repeat spread is as large as the claimed 1 ms improvement

- **Where:** `docs/cuda-methods.md:11, 75, 101-103`.
- **Text says:** "1.599 wall seconds per simulated second originally and 1.268 after consolidating host transfers" (:11). The hedge at :103 covers only the 1 ms pair.
- **Record says:** the same configuration (one brain, one second, 10 ms, L4, GPU dopamine, same seed, identical counts) measured **0.793** s/s (`male-cuda-speed.md:9`) and later **0.637** (`male-cuda-identical-receipts.json:121`). That is a 20% spread. Kernel-plus-transfer time barely moved (0.644 to 0.627 s), so most of the gap is outside the kernel and unexplained. The 1 ms change, 1.599 to 1.268, is 21%.
- **Proposed wording** (:11):
  > The one-millisecond interface measured 1.599 and, after host transfers were consolidated, 1.268 wall seconds per simulated second. These are single runs. The same 10 ms configuration measured 0.793 and 0.637 in two runs, so the improvement is not separated from run-to-run variation.
- **Also:** add the 0.793 versus 0.637 pair to the sentence at :103.

### 11. Nothing says what limits speed: the A100 is slower than the L4, and batching adds no throughput

- **Where:** `docs/cuda-methods.md:77-92`.
- **Text says:** the table shows these results without comment.
- **Record says:** in `male-cuda-speed.md:9-12`, per-brain stepping is 0.793 (1 brain), 0.813 (8) and 0.751 (32) on the L4, and 0.994 on the A100, which has far more FP64 throughput. Stepping time grows in step with batch size. Batching therefore amortizes construction and cost, not stepping time. No profiling record exists. A reviewer will ask why a faster double-precision GPU is slower, and what batching is for. My guess is that barrier latency or memory atomics set the bound rather than arithmetic, but that is unmeasured and belongs in a profiling task, not the text.
- **Proposed wording** (after :92):
  > Stepping time grew in proportion to batch size, so batching mainly spreads the construction cost across brains rather than speeding up each brain. A batch of 32 advances each member at about 24–28 wall seconds per simulated second. The A100 was slower than the L4 despite its much higher double-precision throughput; no profiling was done.

### 12. Batching limits that matter for planned experiments are unstated

- **Where:** `docs/cuda-methods.md:57, 152`.
- **Text says:** "Neuron state, thresholds, gain and outgoing-connection masks have a batch dimension; connectivity and base weights do not."
- **Code says:** the *scaled* weights have no batch axis either. `set_weight_scale` writes one shared weight array (`cuda_engine.py:151-155`), and background weights are one `(n,)` vector (`cuda_engine.py:84, 120-124`). Conditions that differ in synaptic scaling, such as a graded GABA dose, or in background drive cannot share a batch. `set_weight_scale` also re-enables every disconnected edge (`cuda_engine.py:156-157`, which mirrors Brian2's rewrite), so disconnections must be applied after any scaling.
- **Proposed wording** (append to :57):
  > Synaptic weight scaling and background weights are shared by the whole batch, so conditions that differ in either need separate batches. Changing the weight scale restores every disconnected connection, as in the reference.

### 13. The earlier comparison is miscounted, and its statistics are not defined

- **Where:** `docs/cuda-methods.md:109, 111, 113`.
- **Text says:** "140 transmitter-removal or courtship-stimulation outcomes" (:109), and "Brackets are paired whole-realization 95% bootstrap intervals" (:111). "Detection" (:113) is never defined.
- **Code says:** the 140 are 14 conditions × 10 seeds: 10 unmanipulated controls, 80 removals and 50 stimulations (`circuit_tour.py:38-39`; `cuda_driver.py:50-51`). The intervals are percentile intervals from 10,000 paired whole-seed resamples of 10 seeds (`circuit_tour_analysis.py:23, 70`). "Detected" means the interval excludes zero (`circuit_tour_analysis.py:73`).
- **Proposed wording** (:109):
  > Ten resting realizations, and 140 tour runs (ten realizations each of a control, eight transmitter removals and five stimulation conditions), were analysed identically in both engines.
- **Proposed wording** (:111, the last sentence):
  > Brackets are 95% percentile intervals from 10,000 bootstrap resamples of the ten paired realizations. An effect is "detected" when its interval excludes zero.

### 14. The list of changed detections is incomplete

- **Where:** `docs/cuda-methods.md:113`.
- **Text says:** "The random-drive dPR1 effect changed … Octopamine and serotonin detections also changed."
- **Record says:** of the 110 tabulated intervals (`male-cuda-comparison.md:29-68, 74-143`), 14 change detection between engines:
  - Removal: dopamine/central (CUDA only); octopamine/outside-sensory and octopamine/central (Brian2 only); serotonin/outside-sensory and serotonin/DAN (Brian2 only).
  - Stimulation: P1-medium OFF/wing motor, pIP10 ON/P1 (Brian2 only); P1-high OFF/P1, pIP10 OFF/P1, pIP10 OFF/pIP10, pIP10 OFF/TN1a, random-drive ON/pIP10, ON/dPR1 and ON/TN1a (CUDA only).
- **Proposed wording** (replace :113's fifth sentence):
  > Detection changed in 14 of 110 tabulated effects: five transmitter-removal readouts (dopamine, octopamine and serotonin) and nine small stimulation readouts, five of them in the post-stimulation window.

### 15. Only the dPR1 contrasts are reported; the direct effects and the control shift behind them are not

- **Where:** `docs/cuda-methods.md:111-113`.
- **Text says:** "Large effects carried over … medium P1 stimulation minus random-population stimulation was 17.81 … versus 17.85". Only contrasts between two stimulated conditions are given.
- **Record says:** the direct dPR1 effects differ more. P1-medium minus control is +19.24 [16.28, 22.62] versus +16.00 [14.57, 17.43] Hz, and P1-low is +11.04 versus +8.34 (`male-cuda-comparison.md:76, 90`). The cause is the control cohort: control dPR1 in the ON window is 22.38 Hz in Brian2 and 25.77 in CUDA, and Brian2 has two roughly 10 Hz control realizations (`male-cuda-differences.md:24, 36`). The stimulated absolute rates agree within 1.4 Hz (`male-cuda-differences.md:28-34`). The contrasts agree because they don't subtract the differing controls. Without this, a reader who finds the direct effects will suspect cherry-picking.
- **Proposed wording** (after the contrast sentences at :111):
  > Effects measured against the unstimulated control differed more: P1-medium raised dPR1 by 19.24 [16.28, 22.62] Hz in Brian2 and 16.00 [14.57, 17.43] in CUDA. The control cohorts account for this. Control dPR1 averaged 22.38 Hz in Brian2, which had two realizations near 10 Hz, and 25.77 Hz in CUDA. Stimulated rates agreed within 1.4 Hz.

### 16. The dopamine knockout also switches off the dopamine layer, which the text never says

- **Where:** `docs/cuda-methods.md:57, 111, 119`.
- **Text says:** the transmitter removal masks "one transmitter population's outgoing connections … This operation does not silence the population's own firing" (:57). The removed population is not defined. The text never mentions that the dopamine condition differs from the others.
- **Code says:** the removed population is every neuron whose consensus `top_nt` annotation matches the label; unannotated neurons form the "unclear" condition (`circuit_tour.py:116-126`; `cuda_circuit.py:47-48`). For dopamine removal the receptor and transporter layers are also turned off (`LayerFlags(dopamine_A=False, transporter_C=False)`, `circuit_tour.py:105-108`; `cuda_circuit.py:40-43`). All thresholds then revert to −45 mV and all gains to 1, a whole-brain change beyond losing dopamine neurons' outgoing edges. The replay contrasts with "free dopamine dynamics" (:119) without saying this.
- **Proposed wording** (append to :57):
  > A removal takes every neuron whose consensus transmitter annotation matches the label; neurons without one form the "unclear" condition. The dopamine removal additionally disables the dopamine receptor and transporter layers, so every threshold and gain returns to its dopamine-free value.

---

## Notes

### 17. The basis for "Brian2's consumed random stream can change with refractory history" is not given

- **Where:** `docs/cuda-methods.md:115`.
- **Text says:** the sentence stands without support.
- **Code says:** it is correct. Brian2's PoissonInput code is `g += binomial()*w_bg_i` (`brian2/input/poissoninput.py:87`). The Cython generator wraps a statement that writes a conditional-write variable in `if not_refractory:` (`brian2/codegen/generators/cython_generator.py:196-199`), so refractory neurons draw no random numbers.
- **Proposed wording:**
  > In Brian2's generated code the binomial draw sits inside the non-refractory branch, so the number of random values consumed, and therefore every later draw, depends on refractory history.

### 18. The replay's position in the Brian2 schedule is not stated

- **Where:** `docs/cuda-methods.md:121`.
- **Text says:** "added a zero-delay spike generator".
- **Code says:** the replay synapses were placed in the synapses slot at order 0, the PoissonInput's own position, after recurrent delivery at order −1 (`cuda_identical.py:109-110`).
- **Proposed wording** (append):
  > Its synapses were scheduled at the same point in each tick as the background input they replaced.

### 19. The spike total is per engine, and nine-tenths of it comes from the GABA-removal runs

- **Where:** `docs/cuda-methods.md:11, 127`.
- **Text says:** "all 58,655,422 output spikes matched" and "All 58,655,422 emitted neuron/tick pairs across the four trajectories matched".
- **Record says:** that total is each engine's count (`male-cuda-identical-checks.json`, `spikes_per_backend`). The two intact runs contribute 5,453,856 spikes and the two GABA-removal runs 53,201,566, or 91% (per-run totals in `male-cuda-identical-comparison.json`).
- **Proposed wording** (:127):
  > All 58,655,422 spikes emitted by each engine (5.45 million in the two intact runs, 53.2 million with GABA removed) matched at the 0.1 ms grid resolution, including settling.

### 20. The clamped-rest timing row ran no dopamine kernels

- **Where:** `docs/cuda-methods.md:75, 83`.
- **Text says:** "Stepping includes dopamine".
- **Code says:** rest mode attaches no modulator (`cuda_circuit.py:67-69`), and `male-cuda-speed.json` labels the row "clamped rest".
- **Proposed wording:** add "(no dopamine updates)" to the row label at :83.

### 21. Construction time has an unexplained two-level pattern

- **Where:** `docs/cuda-methods.md:92`.
- **Text says:** "approximately 97–281 seconds".
- **Record says:** build times cluster near 100 s and near 270 s (`male-cuda-speed.md:9-20`) with no stated cause. Cold versus warm container or cache is the likely candidate, but it was not tested.
- **Proposed wording** (append):
  > Build times clustered near 100 s and near 270 s; the cause was not isolated.

### 22. The random generator has no known-answer check, and its uniforms have 32-bit resolution

- **Where:** `docs/cuda-methods.md:57-59`.
- **Code says:** Philox4x32-10 is hand-written (`cuda_tick.cu:8-20`). Its round and key schedule match Random123, but nothing checks it against Random123's published test vectors. `uniform` has 2⁻³² resolution (`cuda_tick.cu:19`), so the inversion sampler can never return k ≥ 7. Under Binomial(100, 0.001) that has probability 1.5×10⁻¹¹ per draw, which is negligible. Brian2's own inversion also has a restart bound.
- **Proposed wording** (append to :59):
  > Uniform variates have 32-bit resolution, which truncates the binomial tail at a probability below 10⁻¹⁰ per draw.

### 23. "General deterministic extended-stimulus topology" is opaque

- **Where:** `docs/cuda-methods.md:152`.
- **Code says:** this means the reference's spike-list input, a SpikeGeneratorGroup that delivers events at listed ticks (`brian_engine.py:486-500`, refused at `cuda_engine.py:49-51`).
- **Proposed wording:**
  > … or the reference engine's deterministic spike-list input (events at listed ticks).

### 24. The reason for the A10 run is missing

- **Where:** `docs/cuda-methods.md:90-92`.
- **Record says:** "It replaced an L4 call cancelled before a worker started" (`docs/cuda-backend.md:206`).
- **Proposed wording** (append to the A10 sentence):
  > It replaced an L4 call that was cancelled before starting.

### 25. The tick conversions are implicit

- **Where:** `docs/cuda-methods.md:26`.
- **Code says:** the delay is round(1.8/0.1) = 18 ticks, and the refractory period is 22 ticks by Brian2's `timestep()` rule, ⌊(2.2 + 10⁻⁴)/0.1⌋ (`cuda_engine.py:63-64`).
- **Proposed wording** (append to the constants sentence):
  > (18 and 22 time steps, converted with the reference's rounding rule).

### 26. The price rates have no date or source

- **Where:** `docs/cuda-methods.md:144-146`.
- **Code says:** the rates are constants in the submit scripts (`scripts/modal/cuda_driver.py:16, 42`; `cuda_identical_driver.py:18`). Metered figures come from Modal billing.
- **Proposed wording:**
  > … using the provider's list rates at the time of the runs (September 2026) …

### 27. What the histograms and first-spike ticks are for is unsaid

- **Where:** `docs/cuda-methods.md:53`.
- **Code says:** the 1 ms histogram is the network-wide spike count per millisecond and feeds the synchrony (Fano) statistic. First-spike ticks feed the latency readout (`cuda_circuit.py:118-128`).
- **Proposed wording** (append):
  > The histogram is the whole-network spike count per millisecond, used for the synchrony statistic. First-spike ticks give the latency readout.

### 28. The kernel changed between the earlier outcomes and the replay

- **Where:** `docs/cuda-methods.md:166`.
- **Code says:** the earlier outcomes ran before the explicit-event branch existed. The only kernel change afterwards is that added branch (commit `ce45119`, `cuda_tick.cu:65-68`); the stochastic path is untouched. The later kernel reproduced the earlier one-second pilot counts exactly (`male-cuda-identical-checks.json:12-49`).
- **Proposed wording** (append):
  > The only kernel change between the earlier outcomes and the replay added the explicit-event branch. The updated kernel reproduced the earlier pilot counts exactly.

### 29. Weights are not uniformly 64-bit

- **Where:** `docs/cuda-methods.md:69`.
- **Code says:** "Voltage, synaptic drive, weights … use 64-bit floating point" is true of stored weights. Both engines, however, pass the per-edge scale factors through float32 first (`cuda_engine.py:152`; `brian_engine.py:762`). The substrate's ×4 and ×6 are exact in float32, and both engines round identically, so this is no discrepancy. Fractional dose factors would be rounded.
- **Proposed wording** (append):
  > Per-connection scale factors are stored in 32-bit precision in both engines.

### 30. There is no schematic of the tick schedule

- **Where:** `docs/cuda-methods.md:43-53`.
- **Text says:** the two-stage tick, the delay ring and the delivery order are described only in prose.
- **Suggestion:** a methods reader would expect one figure: a single tick drawn as update → threshold/compaction → barrier → delayed delivery → barrier, with the ring slot indices. Brian2's schedule (groups, thresholds, synapses, resets) could be drawn alongside for comparison.
