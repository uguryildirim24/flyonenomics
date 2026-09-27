# Why signals stop in the declared fly brain

## Bottom line

The evidence does **not** support a general engine or indexing defect, and “nothing propagates” is too broad: the sugar path still reaches MN9, photoreceptor contrast reaches lamina voltage, and direct TuBu input strongly changes TuBu itself. For the eye, conversion of lamina voltage changes into spikes fails. For TuBu, the downstream population contrasts do not establish a reproducible steering response; the first failed relay has not been localized.

The best diagnosis is therefore two statements at once:

1. **The silence is a property of the model as currently specified.** Its current-based point-LIF neurons transmit only spikes. A silent neuron starting at leak potential and receiving only inhibitory input returns toward that leak potential when inhibition is removed; it has no graded transmitter release, rebound, intrinsic tonic current, or receptor-specific reversal to carry a disinhibitory signal.
2. **The declared rest supplies an unsuitable operating point for the tested lamina relays; that remains a hypothesis for the TuBu targets.** It gives a calm central population and preserves the sugar path, but directly drives only cells labelled `sensory`. L1/L2, the rest of the optic lobe, visual-projection neurons and TuBu receive no direct background. L1/L2 are measured several millivolts below threshold. The group-wide central mean does not tell us the voltages of the exact TuBu recipients.

This is not a choice between “bad rest” and “model limitation.” The sparse operating point is produced by our rest specification; the loss of onward spike-mediated communication at the silent lamina follows from that operating point combined with the point-LIF abstraction. Candidate revisions are **cell-type-specific operating points**, with non-uniform E/I regulation if needed for stability, or a hybrid model with graded visual transmission. The records do not establish that either recipe is necessary or sufficient for biological fidelity. Global threshold/weight changes risk disturbing the measured rest and do not specifically address the relay failure; restoring the old photoreceptor signs reverses the measured visual contrast.

## 1. What is and is not broken

### The premise needs narrowing

The declared substrate has a measured central mean of 4.83 Hz, low KC activity and low dark MN9 activity (not necessarily zero), and its sugar-minus-dark MN9 response occurs on every fresh seed; the exact values are records of the model, not biological pass lines (`validation/records/p2/rest-T3e-freeze-partial.json:55-96`; `docs/SPEC-P2.md:1888-1890`). The original rest sample also shows why a population mean is insufficient: 1,809 of a fixed 2,000-cell central sample were silent (`validation/records/p2/rest-T3e-decision.json:123-142`; fixed sampling in `src/flyonenomics/drive/rest_nonuniform.py:223-239`).

The two failed paths are more specific:

- The visual encoder changes R1–6 firing. The stripe then raises ipsilateral L1/L2 voltage by 0.599–0.808 mV, but ambient L1/L2 means are about −57 mV and even the largest sampled voltage is −51.827 mV, below the −45 mV threshold (`docs/optic-lobe-silence.md:55-78`). This is **subthreshold propagation**, not no propagation.
- In the corrected TuBu run, 70 Hz input changed TuBu by 9.377 Hz, but visual projection by 0.000095 Hz and LAL by 0.0038 Hz; the ten-seed steering interval included zero (`validation/records/p2/wp20-wave.json:640-700`; steering intervals in `docs/behaviour-p2.md:68-80`). These are population-mean contrasts, not proof that every recipient is silent; cancellation or dilution within the observers remains possible.
- The sugar circuit is a counterexample to a global engine failure. It still responds on the same declared substrate (`docs/SPEC-P2.md:1888-1890`).

### Implementation defect: unlikely for the final evidence

The engine equations, object construction and constants are tied back to the pinned Shiu implementation. The model is built with the selected equations, initializes `v`, `g`, threshold and gain explicitly, and derives recurrent weights from the signed connectome counts (`src/flyonenomics/engine/brian_engine.py:261-327`, `src/flyonenomics/engine/brian_engine.py:373-424`). It also raises if the inherited Shiu constants drift (`src/flyonenomics/engine/brian_engine.py:550-567`).

The eye audit found all 5,867 R1–6→L1 pairs non-zero and negative after composition, spanning 63,344 anatomical synapses. R1–6 reaches 1,247 of 1,579 L1 cells, so incomplete coverage cannot explain silence in every connected L1 (`docs/optic-lobe-silence.md:131-155`). The +2 mV optic-background counterfactual makes L1/L2 and several deeper types fire without changing thresholds (`docs/optic-lobe-silence.md:87-123`). Together with the intact weight rows and measured stripe-linked lamina voltage, this supports a functional photoreceptor-to-lamina event path. Background rescue alone would not exclude disconnected recurrent rows, because it directly excites the optic cells.

There were real WP20 fixture/observer defects, including an initially wrong injection target, but the invalid compute was rejected and the corrected TuBu run was performed after the repair; it is the corrected run cited here (`docs/behaviour-p2.md:48-80`). Those fixed defects do not explain the final null.

A narrower uncertainty remains: unlike the eye path, the TuBu path has not yet had a row-by-row effective-weight and immediate-child audit. Its result can therefore be caused by a poor operating point, weak/sparse TuBu efferents in this subset, or a population/readout mismatch. That distinction is the first cheap test below.

### Threshold, time constants, weights, background and signs

| Candidate cause | Reading of the evidence |
|---|---|
| **Threshold** | −45 mV with rest/reset −52 mV and no threshold spread is inherited from Shiu, not an accidental value (`data/params-v0.2.yaml:7-16`; `data/drive-v0.2.yaml:52-54`). It is nevertheless a uniform, non-cell-specific modelling assumption, not a measured threshold for L1, L2 or TuBu targets. Lowering it could wake relays but would be a new model, not a bug fix. |
| **Time constants** | The inherited membrane and synaptic constants are 20 ms and 5 ms (`data/params-v0.2.yaml:11-12`). No timing evidence points to an integrator error. Changing the synaptic decay would change mean integrated current and changing the membrane constant would change temporal filtering, but both would be new, cell-type-uncalibrated gains rather than repairs. Neither gives an inhibited silent relay graded output. |
| **Base weights** | Base recurrent weight is the Shiu free parameter, 0.275 mV per anatomical synapse (`data/params-v0.2.yaml:15`). Eye rows are present and large, so a zero scale is excluded. The TuBu efferent scale still needs auditing. |
| **Our weight scaling** | This is a material departure: Glu is ×4 and GABA→KC is ×6 while histamine remains ×1 (`data/drive-v0.2.yaml:5-10`). The scale code enforces cell-wide signs for known transmitter classes and these gains (unknown-class rows retain their connection-file sign) (`src/flyonenomics/substrate/scales.py:41-53`, `src/flyonenomics/substrate/scales.py:77-114`). Glu ×4 magnifies L1→Mi1/Tm3 inhibition when L1 spikes (`docs/optic-lobe-silence.md:142-148`). It is a candidate downstream bottleneck, not an isolated causal result: silent L1 emits no such current in the declared eye runs, and network-wide Glu effects were not separately ablated. |
| **Background** | Lack of sufficient depolarizing drive is the supported lamina first-break cause. One hundred 10 Hz inputs are our design choice (`data/params-v0.2.yaml:27-30`), and only the 16,351 sensory cells get 1 mV; optic, central and visual-projection groups get zero (`data/drive-v0.2.yaml:12-51`). The runtime expands exactly those group values (`src/flyonenomics/drive/rest.py:517-534`). |
| **Transmitter signs** | Histamine is correctly treated as inhibitory in the declared rule. Photoreceptors are explicitly classified His (`src/flyonenomics/substrate/transmitters.py:145-183`), and His is assigned negative sign (`src/flyonenomics/substrate/scales.py:8-10`, `src/flyonenomics/substrate/scales.py:83-90`). Restoring the mixed connection-file signs makes L1/L2 fire with the *wrong* stripe sign and does not wake Mi1/Tm3 (`docs/optic-lobe-silence.md:125-162`). A sign flip is therefore neither biological nor a repair. |
| **Connectome subset** | This brain-only subset does not establish a whole-animal motor circuit, and incomplete pair coverage limits anatomical claims. Missing type resolution already prevented the proposed LPi13/LPi15 hub arm (`validation/records/p2/rest-T3e-decision.json:1606-1624`). They do not explain the first eye break because the audited R1–6→L1/L2 connections are present. They may matter for the unaudited TuBu→steering route. |
| **Point-LIF/current synapses** | This is the relevant structural limitation at the measured silent lamina operating point. The declared equation is `dv/dt=(v0-v+g)/tm`, events add signed current to `g`, and spikes are the only recurrent output (`src/flyonenomics/engine/models.py:15-26`). There is no graded release or rebound. The model can carry disinhibition as a firing-rate change only when the recipient has sufficient excitation to fire; subthreshold voltage changes alone cannot leave that cell. A biological graded-transfer replacement would need cell-type-specific literature support, not just this model diagnosis. |

The current substrate does **not** contain spike-frequency adaptation. `mechanisms: null` selects plain `lif` (`data/drive-v0.2.yaml:52-54`; `src/flyonenomics/engine/models.py:122-150`). Adaptation was an explored alternative, not part of item 122. Describing the current brain as “LIF with SFA” is inaccurate.

## 2. The operating point

For a quiet neuron in this model,

\[
\tau_m\dot v = v_0-v+g, \qquad \tau_s\dot g=-g.
\]

For the stationary **subthreshold linear system**, ignoring spike resets and refractory periods, the mean voltage is `v0 + mean(g)`. Recurrent events change `g` by signed weight times postsynaptic gain (`src/flyonenomics/engine/models.py:15-25`). Background instead uses unscaled `w_bg_i`, with 100 independent 10 Hz inputs per neuron (`src/flyonenomics/engine/brian_engine.py:443-453`). In that subthreshold approximation,

\[
E[g]=100(10\,\mathrm{s}^{-1})(0.005\,\mathrm{s})w_{bg}=5w_{bg}.
\]

At 1 mV this is 5 mV of mean drive against the fixed 7 mV `v0`-to-threshold gap, before recurrent input and fluctuations. L1/L2 get none of that positive background and receive tonic negative histaminergic current, explaining their measured mean near −57 mV. Removing some photoreceptor inhibition moves them toward −52 mV, not toward −45 mV (`docs/optic-lobe-silence.md:164-190`).

Dopamine can move the operating point indirectly: the neuromodulation layer composes receptor-dependent threshold shifts and postsynaptic gains (`src/flyonenomics/neuromod/state.py:293-306`). But the visual diagnostic measured exactly −45 mV thresholds in L1/L2/Mi1/Tm3, so dopamine is not rescuing those relays (`docs/optic-lobe-silence.md:204-216`). The current drug result is also tonic-source pharmacology: K2r measured zero compartment-weighted DAN input and selected source mode (`validation/records/p2/wp19-K2r-iteration-1-b51d49f2968ad52d.json:758-797`, `validation/records/p2/wp19-K2r-iteration-1-b51d49f2968ad52d.json:875-913`). This does not mean every neuron labelled DAN is silent, nor does it establish activity-driven dopamine release.

### What the published models do

- **Shiu et al. 2024** did not construct an awake resting operating point. Its code attaches high-gain Poisson input only to the neurons selected for activation; zero input leaves the network at `v0`. The repository audit confirms that “silent baseline” is an inference from this design, not a quoted experimental finding (`docs/research/R2-model-users.md:73-77`, corrected at `docs/research/R2-model-users.md:229-237`). Its stimulus event adds `0.275 mV × 250 = 68.75 mV` to `g`, **not directly to voltage** (`data/params-v0.2.yaml:22-25`; `src/flyonenomics/engine/brian_engine.py:459-469`). For an isolated cell initially at −52 mV, the no-reset impulse response is Δv(t) = W τs/(τm−τs) [exp(−t/τm)−exp(−t/τs)]. With 20/5 ms constants its peak would be about 10.83 mV above leak at 9.24 ms, so the cell crosses −45 mV first; ongoing inhibition can prevent that in the network. This is equation arithmetic, not a measured voltage excursion. Recurrent gain is otherwise synapse count times the single 0.275 mV free parameter. The MN9 validation summarized in R4 compares evoked behaviour, not measured MN9 spike rates or membrane operating points (`docs/research/R4-mn9-facts.md:22-24`).
- **FlyWire** supplies this project's anatomy, cell types and transmitter predictions (`docs/research/R2-model-users.md:41-59`). This implementation obtains thresholds and membrane constants from Shiu and background from design choices, not from those anatomical inputs (`data/params-v0.2.yaml:7-30`); cell-wide signs/gains are composed by the scale rule above, not measured receptor-specific responses. Treating a wiring diagram as a complete dynamical resting brain is an extra assumption.
- **Histamine.** The qualitative inhibitory sign is defensible for fly photoreceptors and is the sign required for dark-bar disinhibition in SPEC-P2 §3.1 (`docs/SPEC-P2.md:689-697`). What is not established is our conversion of every photoreceptor output into a current pulse onto a spiking point neuron. FlyWire transmitter identity does not specify the postsynaptic receptor, graded release function or resting conductance. The sign is likely right; the transfer model is incomplete.
- **Later FlyWire-constrained work** does not give a plug-compatible answer. R2 describes Lappalainen et al.'s visual model as a recurrent rate model, not a whole-brain spiking-rest validation (`docs/research/R2-model-users.md:58`). R2's coordinator check distinguishes two 2026 works: Li, Ping, Zhang and Wang identify inhibitory hubs sustaining rest (bioRxiv `10.64898/2026.08.21.745055v1`); Li, Wang, Liao, Zhang and Wang use an online-fitted model reproducing spontaneous calcium dynamics and avalanches (OpenReview `wCBNxp1qWe`; `docs/research/R2-model-users.md:229-234`). That check does not establish the precise fitted-drive recipe or prove that our remaining failure sits in those hubs. These are precedents for investigation, not transferable parameters or a necessity theorem.

### Are our departures defensible?

Adding background was the project's chosen way to obtain an active substrate for pharmacology, and restricting it to sensory afferents was a sensible way to avoid directly exciting motor and high-degree central cells. It demonstrably produced a calm network with a sugar response, so item 122 was defensible for that purpose.

It was not evidence that every sensory system had a usable baseline. In particular, SPEC-P2 expected optic neurons to fire near their group rate in darkness before histamine was released (`docs/SPEC-P2.md:689-695`), while the declared file gives the entire optic group zero direct background and the diagnostic finds L1/L2 silent even in darkness. That is a mismatch between the expected mechanism and the measured selected substrate; zero direct background alone would not prove silence, since recurrent excitation could in principle supply it. The rest decision optimized coarse whole-brain and sugar measures; it never constrained the operating point of each inhibitory relay.

The curated histamine correction is defensible. The unmeasured Glu ×4 factor, GABA→KC ×6 factor, uniform thresholds and cell-wide signs are engineering choices that must remain explicit. They are not properties read from FlyWire and should not be described as fly physiology.

## 3. Can one parameter region both rest and respond?

**Yes for at least one pathway, no demonstrated common region for vision/steering.** The declared substrate itself proves coexistence of calm measured rest and a sugar response. The optic +2 mV arm shows that model-sized depolarization can wake L1/L2 and produce signed contrasts in Mi1/Tm3/T5, without changing the measured L1/L2/Mi1/Tm3 thresholds (`docs/optic-lobe-silence.md:87-123`, `docs/optic-lobe-silence.md:204-216`). Because it drives the whole optic group, it does not prove that lamina-only recruitment is sufficient.

But no measured condition yet combines all of the following on the same bytes: the declared resting activity, retina-to-central visual propagation, TuBu-to-LAL propagation, and stimulus-dependent steering. Optic +2 mV still leaves LPLC, MeTu and TuBu silent. Direct TuBu injection gives small LAL mean contrasts and a ten-seed steering interval spanning zero, not an equivalence demonstration or proof of zero effect. There may be a **regional** window, but a global one has not been shown.

The earlier search reports a tension between quiet rest and reflex preservation over its tested global drive/inhibition settings (historical summary in `docs/research/R2-model-users.md:65-71`). The heavy-tailed-connectivity explanation in R2 is a mechanistic hypothesis here, not proof that every uniform setting must fail. Sensory-only drive preserves the sugar assay, not all pathways. If the targeted tests below find no usable interval, that rules out **the sampled interventions and ranges**, not every current-based spike-only parameterization or the existence of responsive rest in a fly.

### Candidate revisions, not established requirements

A staged engineering proposal is:

1. retain sensory-only drive and the measured calm central substrate;
2. add independently justified tonic drive or threshold offsets only to the exact relay populations that require a baseline;
3. only if local recruitment destabilizes the network, investigate incoming-gain normalization or inhibitory-hub regulation; and
4. fit all of that jointly to resting activity **and** paired stimulus contrasts, never to a desired model firing floor.

A separate hypothesis is a hybrid model with graded release at specifically justified visual relays and spikes where appropriate. Graded release and conductance-based inhibition are different changes and should be tested separately. R2's rate-model precedent does not establish that all lamina/medulla cells require graded transmission or where the graded-to-spiking boundary belongs. Those choices, membrane parameters and receptor signs need cell-type-specific literature or explicitly labelled fitting assumptions before a biological claim.

## 4. Ranked cheap tests

These are proposals, not authorization to run or change the declared substrate. Brain-seconds below count simulated time approximately; they are planning estimates, not acceptance criteria. Every dynamic test compares paired conditions and reports measured values. None introduces a firing floor.

### 1. Static TuBu efferent and readout audit — **0 brain-s**

Reproduce the eye audit for TuBu: immediate postsynaptic roots, cell types, membership in `visual_projection`, LAL and steering populations, signed effective weights after every scale and postsynaptic gain, anatomical synapse counts, coverage, and short paths to DNa02/LAL. Verify the runtime injection roots and side/rate mapping, not just the intended 150-cell count (`docs/optic-lobe-silence.md:39-47`). A path's product of signs does not establish functional transmission through its intervening neurons.

First reuse saved spike/voltage data, where available, to split the broad readouts by immediate target, type and side; do not rerun the already demonstrated lamina voltage effect. Check whether a tiny group mean hides a sparse response or cancellation. With the audited signed events, use the linear equations above to estimate input and voltage changes; a cell with only nonpositive input, initially at leak, cannot cross the higher threshold merely by removing inhibition. This analytic exclusion costs no brain-seconds.

**Measures:** structural connectivity, observer coverage and the strongest available evidence of subthreshold transfer.

**Changes the diagnosis if:** relevant rows are absent or observers omit responding targets. Unexpected inhibitory signs or weak routes motivate sign/gain investigation but do not alone identify the cause. A substantial excitatory route makes an operating-point test worthwhile; it does not establish that diagnosis.

### 2. Immediate-child voltage-transfer probe — **8 brain-s pilot; about 24–48 if expanded**

Start with TuBu, whose immediate recipients have not been measured: one paired seed, 2 s settle plus 2 s measurement per condition (2 × 4 s = 8 brain-s). Trace up to 64 informative targets, stratified by side, sign and path to the readout, not only largest weights. Record source spikes, target `v` and `g`, composed thresholds/gains, refractory state and signed incoming events with delays. Plain `lif` currently exposes only `v` through its StateMonitor (`src/flyonenomics/engine/brian_engine.py:502-514`); current/event tracing therefore has implementation cost and is not already available from that API.

Expand an informative result to three seeds (24 brain-s). Add a distinct unresolved eye-stage probe only if the existing lamina evidence cannot answer it (48 total for two paths). Actual settle requirements may raise these estimates.

**Measures:** where a paired change disappears: source output, target current, voltage, or spike conversion. Separate excitatory and inhibitory contributions so cancellation is visible.

**Changes the diagnosis if:** known arriving events fail to produce the equation's predicted `g` increments after checking gain, delay, reset and refractory timing; that would reopen routing/integration concerns. Nonzero weights alone are insufficient: the source must change its events and net input can cancel. A subthreshold response establishes transfer without spiking, not necessarily that background rather than effective connectivity is the sole cause. A sampled near-threshold voltage is not itself evidence of a threshold defect.

### 3. Local excitability contrasts — **start at about 24–40 brain-s; expand only if informative**

On the immediate recipient populations identified above, compare the declared setting and two informative interventions on one path/seed, paired conditions: 3 settings × 2 conditions × 4 s = 24 brain-s. Choose interventions from background, threshold offset or gain on the audited source-to-target edges, according to the sign/current evidence. Reuse a matching declared pair where possible. For the eye, a targeted L1/L2 rescue and a matched downstream-only drive control (two extra pairs, 16 brain-s) can distinguish relay recruitment from the existing whole-optic counterfactual's direct activation of deeper stages.

A background weight increment Δw has subthreshold mean drive 5Δw, not Δw. Even a threshold decrease matched to that mean is not dynamically equivalent: Poisson fluctuations, reset distance and recurrence differ. Scaling an inhibitory source does not supply missing positive drive. Keep other bytes fixed. Consider a `tau`/`t_mbr` sensitivity only if traces implicate filtering; `tau` also changes integrated input, while `t_mbr` does not change the stationary subthreshold mean.

A full two-path, three-mechanism, three-level, three-seed design would cost 2 × 3 × 3 × 2 × 3 × 4 = 432 brain-s before removing duplicated declared pairs. It is an expansion ceiling for this example, not the first or necessary experiment.

**Measures:** baseline voltage/rate, evoked voltage/rate contrast, downstream contrast, and whether recruitment is gradual or an abrupt silence-to-saturation transition.

**Changes the diagnosis if:** selective rescue supports one mechanism over the tested alternatives. Background, thresholds, weights and time constants all affect excitability and are not uniquely identifiable from a rescue alone; interpret them against the measured currents/voltages. Failure rules out the sampled settings, not the entire point-LIF model class.

### 4. Staged regional operating-point grid with joint rest readout — **about 800–1,200 brain-s**

Promote only the promising manipulation from test 3. Drive named stages, not the whole optic/central super-class: first L1/L2, then the relevant medulla/lobula cells, then immediate TuBu recipients. A small 3×3 regional grid over three seeds is a possible discovery design, not a guaranteed sufficient search. For every arm record the existing dark rest measures, exact relay baselines, paired visual/TuBu contrasts, sugar response, and MN9 in darkness. Compare them with the declared substrate's distributions; do not turn those values into new cutoffs. For scale, 9 arms × 3 seeds × 4 paired assays × 2 conditions × 4 s = 864 brain-s with short probes; longer rest windows and adaptive settling cost more and must be itemized before launch.

**Measures:** whether there is an empirical region on the same run bytes where rest remains recognizably calm and both local and downstream stimulus contrasts exist.

**Changes the diagnosis if:** such a region exists reproducibly, demonstrating that a regional operating-point change can rescue the tested model contrasts without the observed rest trade-off. If every sampled responsive arm creates saturation, ignition, or loss of sugar response, report that trade-off within the tested grid, not impossibility outside it.

### 5. Graded-relay pilot, if evidence justifies it — **about 200–400 brain-s plus implementation**

Prototype graded release for one or two specifically justified visual relays, using presynaptic voltage relative to its dark baseline to modulate postsynaptic current. Define a nonnegative release function, its tonic offset and receptor sign explicitly: a signed voltage deviation must not silently turn an inhibitory synapse excitatory. Keep the central model and item-122 background unchanged. Sweep a few labelled transfer gains and retain shuffled-column and sign controls. For example, 3 gains × 3 seeds × 3 control variants × 2 conditions × 4 s = 216 brain-s; four variants cost 288. Literature support is needed before calling this physiological, regardless of test 4's outcome.

**Measures:** whether the measured 0.6–0.8 mV lamina signal can cross the next anatomical stages without forcing lamina spikes.

**Changes the diagnosis if:** graded transmission carries contrast where the tested spike-only arms did not. That demonstrates a possible transfer mechanism, not its biological correctness or the impossibility of spike-based alternatives. A failed pilot leaves transfer calibration, path completeness and sign/receptor mapping open.

A confirmation estimate must name its schedule: ten seeds × two configurations (candidate and declared reference) × (32 s dark rest + three 2-condition assays × 4 s) = 1,120 brain-s, before extra controls or settling. This illustrates the roughly 1,000–2,000 brain-s planning scale, not a cap or sufficiency claim. Reuse existing evidence and localize the missing transfer before proposing another global search.

## 5. Reviewer-safe Phase 2 framing

The committed configuration is already `controller: open_loop` (`data/behaviour-v0.2.yaml:2`; `docs/behaviour-p2.md:60-66`). A suitably limited Phase 2 claim is:

> We built a reproducible FlyWire-constrained current-based LIF neuropharmacology simulator and measured a stable sensory-driven substrate that preserves a model sugar response. Dopamine source, transporter and drug manipulations change the model's extracellular dopamine as specified. In the visual system, photoreceptor contrast reaches lamina membrane potential but does not produce downstream spikes; synthetic TuBu input activates TuBu, but the measured LAL and ten-seed steering contrast intervals span zero. The released configuration therefore uses an open-loop behavioural scaffold and does not implement visually guided attention.

It can claim:

- exact connectome/configuration provenance and reproducible null results;
- a measured model resting regime and model sugar response;
- tonic-source dopamine pharmacology, including fumin, methylphenidate and 3-IY effects (`validation/records/p2/wp21-neural.json:98-110`, `validation/records/p2/wp21-neural.json:1353-1437`); and
- localization of the lamina spike-conversion failure, plus a downstream TuBu population-readout null that still needs localization.

The eye and TuBu diagnostics are linux-aarch64 measurements (`docs/optic-lobe-silence.md:192-200`; `docs/behaviour-p2.md:98-104`). Their evidence does not turn a software gate into biological validation.

It cannot claim:

- a validated whole-fly resting brain;
- retina-to-brain functional vision;
- visually driven steering, fixation or closed-loop attention;
- an ADHD-like behavioural phenotype or behavioural drug rescue;
- circuit-driven dopamine release—the K2r compartment-weighted DAN inputs are zero and release uses source mode; or
- biological firing-rate agreement, especially for MN9. R4 found no electrical MN9 rate measurements at rest or during sugar PER in the literature it surveyed (`docs/research/R4-mn9-facts.md:11-35`).

Open loop is not a failed version of closed-loop attention that can be described with softer words. It is a pharmacology and neural-response instrument with a null visual-to-behaviour result. For a portfolio, that is a defensible result; calling it a virtual attention phenotype is not.

## 6. Corrections to the current shorthand

1. “No signal propagates anywhere” is false: sugar propagates, TuBu responds locally, and the stripe changes lamina voltage.
2. “The eye works” should mean only that the encoder drives R1–6. It does not mean retinal contrast reaches a spiking optic-lobe output.
3. The declared model is plain `lif`, not `lif+sfa`.
4. A mean central rate of 4.83 Hz does not mean the particular postsynaptic targets needed for steering are near threshold.
5. The +2 mV optic result is a causal excitability probe, not evidence that 2 mV is biological or that vision is repaired.
6. Histamine-off is a negative mechanistic control. Its activity with reversed stripe sign is not a candidate fix.
7. The final TuBu null is valid only after the corrected injection fixture. The earlier wrongly targeted run must stay excluded.
