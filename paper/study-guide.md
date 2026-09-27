# Study guide for Hasan "Rolf" Yildirim

## The answer in half a minute

“I tested whether removing dopamine clearance in a fixed fly-brain model changes how ring neurons respond to earlier artificial input. In ten paired simulations, the response difference was −0.0852 template units: a hint, but not one that survived the two-test Holm correction. Reducing dopamine release did not establish rescue. The independent follow-up has reported no detected difference in 40 new simulation seeds, but that result still awaits review. A simulated neural response is not ADHD or attention. Input is injected at TuBu; the fly does not see.”

This describes the reviewed first study. A new, independent run of 40 simulation seeds has reported a **not-confirmed** result, but its review is still pending; do not treat the report as a reviewed finding yet. Its recorded genotype contrast is −0.001286 template units (95% interval [−0.037968, +0.037578], paired sign-randomisation p = 0.945398). The interval includes zero, so the correct wording is **no detected difference**, not sameness. Pooling both runs gives −0.018060 template units, a descriptive mean that does not change the confirmation decision. These figures come from the follow-up's committed result record on its separate branch and will be checked again after review. Reviewers independently recomputed the first study's two primary contrasts. The original calibration run failed its random-stream audit, even though its raw files replayed byte-for-byte. The repaired main run passed the exact input and random-stream checks. This is a draft awaiting Hasan "Rolf" Yildirim's approval, not peer review.

## Key terms to explain before the details

A **connectome** maps neurons and their connections; this one is a single male specimen. A **spiking model** calculates how its simplified neurons pass electrical events. The **dopamine transporter** removes dopamine after release; **fumin** lacks normal transporter function. We inject artificial input at **TuBu** (tubercle-to-bulb cells) and measure downstream **ring/ER neurons**. The fly does not see. The **history contrast H** asks whether the same final input gives a different ring-neuron response after earlier input A rather than B. A **template unit** is the size of the A-minus-B response measured in independent calibration. A **bootstrap interval** comes from resampling whole simulation seeds; a **sign-randomisation test** compares their paired difference with sign-flipped differences. The **Holm correction** accounts for testing two primary questions. The **prospective freeze** means committing the independent follow-up's question and rule before seeing its outcomes, in the then-private repository on 24 September 2026.

## 1. Question and biological scope

| Choice | Why this choice | Reviewer question → one-line answer |
|---|---|---|
| A dopamine-transporter-loss proxy | Fumin has a direct clearance mechanism and published adult arousal/clearance evidence. | “Did you replicate ADHD?” → No; I tested one ADHD-relevant molecular perturbation against one neural endpoint. |
| Neural history representation, not activity alone | More spikes would not establish attention, impulsivity or hyperactivity; fumin's original daily activity increase was not faster activity whenever awake. | “Why not report hyperactivity?” → There is no validated spike-to-movement or waking-time mapping here. |
| Ring neurons | Sun et al. reported history-dependent suppression in ring-neuron calcium responses. | “Are these Sun's exact cells and signals?” → No; anatomy motivates the assay, but our cell set and spike readout are not matched experimental drivers or calcium measurements. |
| No predicted beneficial sign | Published studies do not tell us which direction of change would be better for this response. | “Is bigger H better?” → Neither sign has been validated as better function. |
| Synthesis-inhibitor-like release reduction | Adult ex vivo 3-iodotyrosine evidence supports reducing release, not fumin attention rescue. | “What dose did you simulate?” → None; 0.375 is a multiplier in an equation, not bath, food, brain or human concentration. |
| Not methylphenidate | The implemented methylphenidate action requires the transporter removed by fumin. | “Why not the familiar ADHD medicine?” → A null result in this knockout would be encoded by the model, not discovered. |

Literature claims were checked against the project's source review. Earlier, superseded assertions should not be reused. The source-review file names are in the technical appendix.

## 2. What is fixed in the model

| Choice | Why this choice | Reviewer question → one-line answer |
|---|---|---|
| MaleCNS v1.0 | Hasan "Rolf" Yildirim chose the male CNS reconstruction, with brain, optic lobes and nerve cord in one specimen. | “Do your old FlyWire results validate this?” → No; male calibration is separate and old female results do not transfer. |
| Traced, typed nodes; every retained aggregate pair | A reproducible released-label filter and no extra edge-weight cut keep weak edges rather than selecting connections from outcomes. | “Is this every released cell?” → No; 162,517 nodes satisfy the declared filter, including exclusions documented in the port audit. |
| One sign per presynaptic neuron | Named transmitter polarity or a majority over predicted presynaptic sites provides a consistent conversion. | “Is a sign measured physiology?” → No; it is a declared transmitter-to-effect rule, with additional uncertainty for predicted transmitters. |
| Synapse count weights | Counts provide structural constraints, not measured connection strengths. | “Does more anatomy mean a more accurate brain?” → It constrains possible wiring, but cannot determine all functional parameters. |
| Leaky integrate-and-fire cells | Simplified neurons that accumulate input and fire at a threshold let us simulate events through the retained network. | “Why not realistic compartments?” → The experiment trades cellular detail for a whole-network, explicitly limited test. |
| Shared intrinsic constants | Rest/reset −52 mV, threshold −45 mV, membrane 20 ms, synaptic decay 5 ms, refractory 2.2 ms, delay 1.8 ms, base weight 0.275 mV specify the inherited model. | “Are all fly neurons identical?” → No; uniform constants are an approximation, not a biological finding. |
| Fixed inhibition and sensory-only background | The male measurements applied the adopted configuration unchanged: GABA 1, glutamate 4, histamine 1, GABA-to-KC 6; sensory background 100 × 10 Hz at 1 mV, none directly elsewhere. | “Did you tune rest to get the history effect?” → No; these settings precede that experiment, but they are not proven in vivo resting physiology. |
| No extra mechanisms or threshold spread | These simplified spiking cells have no adaptation, short-term synaptic depression or learning. | “Does this simulate memory formation?” → No; history dependence can arise from dynamic state without synaptic learning. |
| No male sugar-reflex claim | A defensible male sugar-sensing source has not been identified. | “Was the motor pathway validated here?” → No; an absent source is a limitation, not permission to substitute cells by their output. |

The male starting configuration has a recorded fingerprint. It identifies the setup; it is not a biological score. Its exact value is in the technical appendix.

## 3. Dopamine choices

| Choice | Why this choice | Reviewer question → one-line answer |
|---|---|---|
| 37 pools and anatomical maps | Dopamine-neuron events enter regional concentration variables; those variables then influence mapped cells. | “Is a pool an electrode measurement?” → No; it is a coarse concentration variable for a declared region. |
| Wild-type release calibration | Three recorded clamped male resting seeds determine source rates, then release balances clearance at 0.02 µM. Sparse sources receive a standing source term. | “Did you normalise the mutant back to wild type?” → No; all conditions retain the same wild-type release coefficients. |
| Uptake plus non-transporter clearance | Saturable transporter clearance and a first-order term make the mathematical intervention explicit. | “Are the kinetics adult male measurements?” → No; uptake constants originate in larval work, and their compartment-wide use is an assumption. |
| Fumin sets Vmax to zero | Removes only transporter uptake; first-order clearance remains. | “Is this the full mutant?” → No; development, compensation and recycling are omitted. |
| Release fraction from chemistry | At reference concentration, `f = (k_ns × D_ref) / [Vmax × D_ref/(Km+D_ref) + k_ns × D_ref] = 0.375`. | “Did you pick the best rescue strength?” → No; it was frozen algebraically before neural outcomes. |
| Apply that fraction to both genotypes | The wild-type intervention arm separates genotype-specific change from a general release effect. | “Why four conditions?” → Two alone cannot estimate the genotype-by-intervention interaction. |
| Analytic condition-specific pool starts | Slow fumin clearance makes a common start misleading during a short trial. | “Do the starts guarantee equilibrium?” → No; they assume wild-type source firing, so settle drift and feedback remain measured. |
| PB held at 0.02 µM | The implementation holds this uninnervated pool at the reference. | “Does every pool respond to fumin?” → No; PB is an explicit exception, not a discovered resistance. |
| Two active receptor channels | The model's dopamine-receptor terms change how easily cells fire and how strongly they receive input. | “Does dopamine always excite these cells?” → No; threshold, positive inputs, negative inputs and recurrence interact. |
| Uniform ring receptor densities | All ER cells have declared r1=1 and r2=0.5, without a validated male subtype map. | “Did you reproduce receptor biology?” → No; Dop1R2 is census-only, DopEcR absent, and subtype heterogeneity remains a major uncertainty. |
| No added CX dopamine drive | Only resting dopamine-cell activity and feedback act in the four arms. | “Is this also an activation experiment?” → No; transporter loss and release reduction are the interventions. |

The pool starts (WT/vehicle, fumin/vehicle, WT/release, fumin/release) are
0.02, 0.05333333333333333, 0.007455292704222517 and approximately 0.02 µM
in innervated compartments. These are **calculated setup values**, not
experimental result blanks. The complete arrays are in the experiment plan.

## 4. Inputs, histories and independence

| Choice | Why this choice | Reviewer question → one-line answer |
|---|---|---|
| TuBu injection | The visual front end has not been validated for this task. | “What does the fly see?” → Nothing demonstrated: the experiment injects artificial input at TuBu. |
| Four body-ID-based positions, Gaussian width 20° | Gives reproducible coarse input patterns without fitting to ER activity. | “Are those true visual angles?” → They are imposed labels, not measured receptive fields. |
| Matched single-input totals; 70 Hz cap | Prevents nominal input strength from selecting the pair, while preserving the actual encoder. | “Is A+B just A plus B?” → Not after the cap; injected event hashes and emitted TuBu spikes are audited separately. |
| 245 directly TuBu-reached ring cells | Anatomy selects the readout, not successful responses. | “Did you drop silent cells?” → No; every cell in this anatomical set remains. |
| Separate calibration seeds 101–110 | The representation axis is learned before the later genotype outcomes on 201–210. | “Is there decoder leakage?” → Scaling and centroids hold out whole seeds, and the final axis uses only calibration. |
| First eligible pair in fixed order | Tests represented inputs, favouring opposite hemifields without maximising separation. | “Did you cherry-pick the best pair?” → The order and prerequisites were frozen, not ranked by observed distance. |
| Reliable binary margins and independent templates | Off/A, off/B and A/B must support interpretable representation. | “Did you invent another biological threshold?” → These are declared statistical/identifiability prerequisites, not a firing-rate success line. |
| Eight protocols | Four blank-prefix controls plus pair/off tests after A and B distinguish input history from current input. | “Why off after A or B?” → It subtracts additive prefix carry-over. |
| No history-matched single-input tests | The frozen experiment has a bounded scope. | “Does H isolate competition-specific memory?” → No; that stronger claim requires additional controls. |
| 2 s settle, 5 s prefix, 1 s gap, 14 s test | Fixes a continuous 20 s history trial after settle and retains a long descriptive response. | “Why the first 2 s?” → It is the frozen transient window, not the bin that looked most favourable. |
| Restore only between arms | Carries neural and chemical state through prefix, gap and test. | “Did resetting erase history?” → No reset or reseed occurs within a trial. |
| Matched external streams | Paired arms consume the same external random draws at corresponding times. | “Are all neural spikes matched?” → No; different states can generate different emitted spikes under identical injected events. |

## 5. Explain the statistics without jargon first

**The history contrast (H):** give the model earlier input A, then the final pair A+B. Measure the ring-neuron response. Repeat with earlier input B and the same final pair. For each earlier input, also measure the response when the final input is off; subtract it to account for simple carry-over. The difference between the two corrected responses is H. We measure that difference along an A-versus-B response pattern learned from separate calibration seeds. One template unit means a difference as large as the calibrated A-minus-B response. The precise axis is `d/(d·d)`, not a unit-length axis.

**Genotype comparison:** subtract the wild-type history contrast from the transporter-loss history contrast under vehicle: `H(fumin, vehicle) − H(wild type, vehicle)`.

**Release comparison:** subtract the genotype gap under vehicle from the genotype gap under reduced release. The gap might narrow, vanish or overshoot to a larger gap in the other direction. Inspect both absolute gaps; the interaction alone cannot establish rescue.

| Choice | Why this choice | Reviewer question → one-line answer |
|---|---|---|
| Seed is the replicate | Cells, time bins and conditions in a seed are dependent. | “Why not thousands of neurons as n?” → That would confuse repeated measurements with independent simulations. |
| Ten paired experimental seeds | This is the frozen pilot sample, not ten flies. | “Can it generalise to animals?” → No; it estimates stochastic uncertainty in this single fixed model. |
| 10,000 whole-seed bootstrap draws | Retains the full within-seed design and refits the calibration axis on independently resampled calibration seeds. | “What uncertainty is absent?” → Pair selection, biological parameters and animal variation. |
| Count undefined bootstrap fits | Degenerate training/template samples cannot produce a valid estimate. | “Did you silently replace failures?” → No; the analysis records how many it excluded. |
| Exact sign-randomisation p values | Flips the sign of each paired difference in all 1,024 combinations to see how unusual the observed difference is if signs are exchangeable. The axis remains fixed. | “Do p values include template uncertainty?” → No; the bootstrap intervals do, whereas these conditional p values do not. |
| Holm across two primaries | Adjusts for asking two primary questions, about genotype and the release interaction. | “Is every displayed interval multiplicity corrected?” → No; intervals are unadjusted, and the affine secondary is not in the primary family. |
| No equivalence claim | There is no justified biological equivalence margin. | “The interval includes zero: are they the same?” → No detected difference, not sameness or no effect. |
| Affine prediction from off/A/B only | Tests whether ordinary cellwise scaling plus offset predicts the history change without training on pair outcomes. | “Why not fit the final pair?” → That would use the outcome to explain itself. |
| Noise-corrected, leave-one-seed-out slopes | Corrects sampling moments and keeps evaluated seed information out of training, including bootstrap duplicates. | “Does it remove every rate confound?” → No; it evaluates one fitted affine prediction, not all possible transforms. |
| Intercept-only unresolved cells | A nonpositive corrected predictor variance cannot identify a slope. | “Does their residual disprove scaling?” → No; an arbitrary intercept-only convention cannot exclude an unidentified slope. |
| Unconstrained mixture coefficients | Allows changes in response amplitude and unexplained activity. | “Are coefficients attention probabilities?” → No; they are projections and do not sum to one. |
| Pool, occupancy, input and signed-edge audits | Checks the implemented chemical-to-neural chain. | “Does a negative edge prove competition?” → No; there was no causal inhibition ablation. |

## 6. Validation, rendering and authorship

- **Synthetic validation:** exact and noisy counterexamples exercise the analysis.
  A noisy affine-only example still produced a false-positive-looking secondary
  interval. Reviewer: “Was this a power study?” → No; known inputs test code,
  not biological sensitivity or the long-run false-positive rate.
- **Reproducibility:** Checksums identify the graph, code, design, chosen inputs and raw arrays. A fixed random seed is not enough on its own: code, input files, the order in which random draws are used and computing platform must also be recorded. The exact seed values are listed in the technical appendix below.
- **Calibration replay and repair:** The first audit checked memory addresses instead of unread random values. Replaying two calibration seeds reproduced their raw arrays byte-for-byte, but both still failed the corrected random-stream audit. The original input pair and calibration data were retained under a documented decision, not retroactively certified. The repaired main run used the same per-trial model law and passed every exact input and random-stream check. The remaining calibration seeds were not replayed. The technical appendix below gives the run and decision identifiers.
- **Voided partial run:** An earlier run stopped before any complete seed had been recorded. “Were those data analysed?” → No; only the complete, audited main run enters the result record. Exact run counts and identifiers are in the technical appendix below.
- **3D model:** anatomical geometry is simplified, and only a stratified sample
  of Kenyon cells is displayed. Reviewer: “Is that glowing activity evidence?”
  → No; Figure 1 is anatomy-only, and dummy playback is not used in the paper.
- **AI use:** Agents helped design, code, check sources and draft. Hasan "Rolf" Yildirim directed the work and made the recorded project decisions. “What did a human independently verify?” → No complete manual code, source or raw-data audit is documented. He must review the final claims and approve the manuscript before submission. Agent review is not human replication.

## Results: reviewer questions in one line

- “The genotype interval excludes zero: is it significant?” → Nominally yes
  (exact sign p 36/1024 = 0.0352; 95% interval [−0.153954, −0.020968]), but
  Holm p 0.0703 exceeds 0.05 for the prospectively frozen family of two primaries.
  Neither survives multiplicity correction; the interval is not simultaneous.
- “Does a positive interaction show rescue?” → No. ΔΔH is +0.045877,
  [−0.059833, +0.158040], exact sign p 450/1024 = 0.4395: no detected
  difference, not equivalence. The point-estimate genotype gap narrows from
  −0.085156 to −0.039279, but rescue is not established.
- “Could simple gain/offset explain the pattern?” → The frozen affine
  secondary is numerically uninformative (mean −1.5765×10¹², interval includes
  zero). Tiny positive corrected predictor variances caused explosive slopes;
  115–121/245 cells per held-out fold had unresolved slopes. No post-hoc cap
  was used. It cannot rule an affine explanation in or out.
- “Was the input repair tuned to these outcomes?” → No. It was committed and checked before the main run. The input and model law for each trial and the analysis stayed unchanged. Exact keyed TuBu event lists and state-independent background draws repaired the required matching across histories.
- “Did the failed earlier run contaminate the findings?” → No. Every trial from the incomplete run is void. Two calibration seeds replayed byte-for-byte but failed the corrected audit; the others were not replayed. This history is disclosed, not renamed success.

## Before defending a finding

1. Read the reviewed result JSON, replay evidence and input/chemistry audits.
2. Quote the two primary estimates, intervals **and** Holm p values; retain every
   seed and unresolved outcome.
3. Show both genotype gaps before describing movement toward control.
4. Explain whether the affine prediction was identifiable, not only its residual.
5. Supply the archived raw data, execution revision and reproduction command.
6. End with the claim ceiling: a candidate neural signature in one fixed model;
   not ADHD, attention, behaviour or a dose. Input is injected at TuBu; the fly does not see.

## Technical appendix: identifiers behind the first study

Literature source checks are in `references-verified.md` and `../docs/adhd-model-research.md`; earlier L2 assertions are superseded. The male starting configuration is `rest:ed9b0a469d7a6b77`. The frozen pilot uses master seed 20260912 and bootstrap seed 14620260922. The original calibration run is 5a; replay seeds 101/102 reproduced all ten NPZ files but failed the corrected audit, while seeds 103–110 were not replayed. Decision d-0023 records that replay; d-0025 records the input repair and retention of the original pair. That repair keyed TuBu events by seed, segment and stimulus and drew sensory background independently of state before gating. Stage 5a used older plumbing with the same input statistics. The main audited run is 5b-02; all ten exact audits passed. The void 5b-01 run stopped at 60/320 trials, all WT vehicle, without a complete seed manifest. The raw-data locations, analysis commands and checksums are recorded in the repository. These identifiers document provenance; they are not biological results.
