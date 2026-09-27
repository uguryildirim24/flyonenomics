# A fused CUDA engine for a connectome-constrained male fly nervous-system model

**Hasan "Rolf" Yildirim**

*Methods draft; computational validation, not a claim of biological validation.*

## Summary

A leaky integrate-and-fire model of the male *Drosophila* central nervous system was implemented in CUDA alongside a Brian2 reference. The retained network contains 162,517 neurons and 25,120,209 directed neuron-to-neuron connections. A persistent kernel—a GPU program that stays active across time steps—advances the neuronal state, detects spikes and delivers delayed synaptic events without returning to Python at every time step. Connectivity is shared across independent simulations in a batch. Dopamine dynamics use two additional GPU kernels.

On an NVIDIA L4, a single 12-second control simulation returning counts required 8.420 seconds of stepping with a 10-millisecond interface—the simulated time advanced between the host CPU's exchanges with the GPU. This includes output transfers and dopamine updates, but not network construction. The one-millisecond interface measured 1.599 wall seconds per simulated second in one run and 1.268 in one run after host transfers were combined; it remains slower than real time. These single observations do not separate the change from run-to-run variation. Faster-than-real-time stepping at the coarser interface is not evidence of a real-time body simulation.

With identical saved background events and dopamine held at its reference concentration, both engines produced identical spike counts for every neuron at every 0.1 ms tick in four 12-second simulations: two input realizations, each intact and with GABAergic outgoing connections removed, one network per run. All 58,655,422 spikes emitted by each engine matched. This establishes spike-output equivalence only for that setting and explicit-event input path. It does not cover the engines' own random-input samplers, stimulation, GPU dopamine kernels, multi-network batches, the 1 ms interface or bitwise equality of internal state. Those other paths have separate, narrower evidence described below.

The model receives injected input; the fly does not see. Visual input elsewhere in the project is injected at tuberculo-bulbar (TuBu) neurons. The comparisons here use dark sensory-background drive and, in the earlier population-stimulation experiment, direct injection into named courtship populations. Simulated firing is not seeing, walking or singing.

## Model and reference implementation

The anatomical source is MaleCNS version 1.0 (Berg and colleagues). The model retains neurons annotated as traced with a non-missing cell type, and every released, aggregated directed pair whose endpoints are retained, without a synapse-count cut. The counts above describe this graph, not the anatomical publication's totals. The model follows the connectome-constrained leaky integrate-and-fire (LIF) approach of Shiu and colleagues. All comparisons retain the reference connectivity, transmitter assignments, resting substrate—the adopted background, weight scales and base thresholds—and parameters. No parameter was adjusted to improve GPU agreement.

| Term | Meaning here |
|---|---|
| Realization | A simulation with one particular random-input stream |
| Settling | The first two simulated seconds, starting from rest voltage and zero synaptic drive and excluded from rate estimates; a fixed interval, not a convergence test |
| Neuron groups | Twelve non-overlapping groups based on MaleCNS broad anatomical classes, with dopamine neurons (367), mushroom-body Kenyon cells (4,064) and ellipsoid-body ring neurons (282) separated out |
| Central, sensory and motor | Broad annotation groups: central includes intrinsic neurons of the central brain and nerve cord after the specialized groups are separated out (39,533 neurons); sensory has 15,016 neurons and motor/efferent has 887, including the wing motor subset |
| Outside sensory | All 147,501 neurons outside the sensory group |
| Ascending and descending | Neurons projecting from the nerve cord toward the brain, and from the brain toward the nerve cord, respectively |
| P1, pIP10 and dPR1 | Named courtship-circuit populations (148, two and two neurons); dPR1 is a firing-rate readout, not measured song |
| Postsynaptic gain | A per-target multiplier on incoming recurrent weights, composed from dopamine receptor occupancy and any genotype gain factor |
| Clamped dopamine | Pools held at the reference concentration; receptor effects stay fixed, not absent |

Each neuron has membrane potential \(v\) and a decaying synaptic drive \(g\), both represented in millivolts by CUDA. The resting potential is \(v_0\); the membrane and synaptic decay time constants are \(\tau_m\) and \(\tau_s\):

\[
\frac{dv}{dt}=\frac{v_0-v+g}{\tau_m},\qquad
\frac{dg}{dt}=-\frac{g}{\tau_s}.
\]

Rest and reset potentials are both −52 mV; the nominal threshold is −45 mV. The membrane and synaptic time constants are 20 and 5 ms, the time step is 0.1 ms, the refractory period is 2.2 ms (22 ticks) and the recurrent delay is 1.8 ms (18 ticks), using the reference's tick-conversion rules. Every neuron has the same nominal base threshold; its working threshold adds genotype and dopamine-receptor offsets and is clipped as described below.

Base synaptic strength is 0.275 mV times the directed pair's synapse count, signed by the presynaptic neuron's consensus transmitter: acetylcholine, dopamine, octopamine, serotonin and tyramine are positive; GABA, glutamate and histamine are negative. Without a consensus label, a neuron is negative only if more than half its presynaptic sites have GABA or glutamate as their highest-probability transmitter prediction; otherwise it is positive. That sign applies to all its outputs. The adopted substrate multiplies glutamatergic weights by four and GABAergic weights onto Kenyon cells by six; other specified inhibitory class scales are one. Unlabelled negative outputs take the general GABA scale, not the Kenyon-cell-specific multiplier. These are modelling choices, not measurements of individual male synapses.

For a time step \(h\), the linear update between events is analytic:

\[
g'=g e^{-h/\tau_s},\qquad
v'=v_0+(v-v_0)e^{-h/\tau_m}
 +g\frac{\tau_s}{\tau_m-\tau_s}
 (e^{-h/\tau_m}-e^{-h/\tau_s}).
\]

A spike occurs only when updated voltage exceeds the working threshold \(v_{th}\): \(v'>v_{th}\). On a spike, voltage resets and synaptic drive becomes zero. Both state variables remain frozen during refractory ticks; synaptic and external writes to \(g\) are rejected during refractoriness, including the firing tick. A delayed recurrent event contributes its signed weight times the target's postsynaptic gain.

At rest, 15,016 sensory neurons receive background drive of 1 mV per event. Other background weights are zero. Each driven neuron receives a Binomial(100, 0.001) count per tick, corresponding to 100 independent 10 Hz sources sampled at 0.1 ms. This is the reference's discrete-time background distribution, not a Poisson approximation. Dopamine pools are clamped at 0.02 µM for the resting-state and identical-input comparisons. Clamping holds receptor effects fixed; it does not turn dopamine modulation off.

## GPU design

### One cooperative launch per chunk

CUDA C++ kernels are compiled at runtime with NVIDIA's NVRTC compiler through CuPy. A cooperative grid stays resident for a complete chunk: 100 ticks at the standard 10 ms interface, or ten ticks at a 1 ms interface. Its block count is determined from occupancy and the GPU's multiprocessor count. Grid-wide synchronization is required; this is not an ordinary kernel whose blocks may be scheduled in arbitrary waves.

Each tick has two globally ordered stages. Threads first update neuron state, apply thresholds and compact firing neuron indices into per-block spike lists. A grid barrier publishes the lists and updated refractory state. Warps, groups of GPU threads, then traverse outgoing edges for the appropriate delayed list and atomically accumulate currents for eligible targets. A second grid barrier finishes delivery before the next neuronal update. There is no per-tick Python loop or host synchronization.

### Delay ring and sparse propagation

Connectivity is stored in compressed sparse row form: a pointer array locates each source neuron's contiguous list of targets and weights. Only firing sources' edges are traversed. The delay ring has one more slot than the delay in ticks. At the adopted delay it has 19 slots; spikes emitted on a tick are delivered in the synaptic stage 18 ticks later and affect the following state update, matching the reference schedule.

Each resident block owns a slice of every ring slot. Slice capacity is derived from the maximum number of neuron states that block can process, so the list does not impose an arbitrary spike-count cutoff. Per-neuron counts, whole-network spike counts per millisecond and first-spike ticks are returned at chunk boundaries. The whole-network counts supply the synchrony statistic; first-spike ticks supply the latency readout. Optional full spike recording allocates enough entries from the chunk length and refractory period, and is consumed before the next chunk. The identical-input study exercises this full-recording path.

### Batching and disconnections

Neuron state, thresholds, gain and outgoing-connection masks have a batch dimension; connectivity, scaled synaptic weights and background weights do not. Conditions differing in synaptic scaling or background drive therefore need separate batches. A mask removes a chosen population's outgoing connections independently in each simulation without silencing its own firing. Changing the weight scale restores disconnected edges, as in the reference, so disconnections must be applied after scaling.

A transmitter removal selects every neuron with that consensus transmitter label; neurons without a clear label form a separate removal condition. Dopamine removal additionally disables receptor modulation and transporter/drug effects. In that condition, with no other genotype changes, every threshold is −45 mV and every gain is one: this is more than an outgoing-edge removal.

Batch position does not select the random stream: counter-based Philox draws are keyed by realization, neuron and tick. Paired GPU conditions therefore receive aligned random input even when their refractory histories diverge. The standard background path samples the binomial distribution by inversion. Uniform draws have 32-bit resolution. There is no recorded known-answer comparison with reference Philox output; evidence for the random-input path comes from the independent-stream comparison, not the exact replay.

Extended PoissonGroup-style stimulation uses one Bernoulli draw per target and tick, not an unrestricted Poisson count. Each event adds 68.75 mV (0.275 mV × 250) to synaptic drive, not directly to voltage. The courtship comparison drove P1 at 10, 30 or 60 Hz, and pIP10 or a random control at 30 Hz, during the first five-second recording window only. The random control comprises 148 cholinergic central-brain intrinsic neurons, matching P1's size and excluding P1 neurons and the direct presynaptic partners of pIP10. Each target has one virtual input source.

The separate explicit-background interface accepts saved tick-by-target integer multiplicities, replaces random background entirely and rejects chunks outside the supplied event window. A batch shares the supplied replay stream.

### Dopamine

A pool kernel advances dopamine concentration in each anatomical compartment by an explicit Euler step every 10 ms. Let \(D_c\) be concentration in compartment \(c\), \(n_i\) the spike count of neuron \(i\) in that step, and \(M_{ci}\) its dopamine-innervation weight. Release per weighted spike is \(\alpha_c\), the effective tonic source is \(S_c\), and the release multiplier is \(\rho\). Saturating transporter uptake has maximum rate \(V_{\max,c}\) and concentration scale \(K_{m,c}\); linear non-transporter loss has rate constant \(k_{ns}\). For step duration \(\Delta t\) in seconds:

\[
D_c' = \max\!\left(0, D_c + \rho\left[\alpha_c\sum_i M_{ci}n_i + S_c\Delta t\right]
-\left[\frac{V_{\max,c}D_c}{K_{m,c}+D_c}+k_{ns}D_c\right]\Delta t\right).
\]

The nominal uptake constants are 0.11 µM/s and 1.3 µM; linear loss is 0.05 s⁻¹. Release coefficients come from the adopted dopamine table, and genotype/drug settings modify the effective coefficients. Compartments without dopamine-neuron innervation, and all compartments when clamped, remain at 0.02 µM. This is distinct from a neuron having no dopamine exposure.

A second kernel composes thresholds and gains. The receptor concentration constant \(K_{d,k}\) is the concentration for half occupancy of receptor class \(k\). Each neuron's concentration \(D_i\) is the exposure-weighted sum of compartment concentrations. For receptor class \(k\) (D1 or D2), occupancy \(o_{ki}\) is \(D_i/(D_i+K_{d,k})\); unexposed neurons have zero occupancy. Let \(r_{ki}\) be receptor density, \(a_k\) the threshold coefficient, \(\gamma_k\) the gain coefficient, \(\delta_i\) the genotype threshold shift and \(G_i\) the genotype gain factor. Clipping limits a value to the stated lower and upper bounds:

\[
v_{th,i}=\operatorname{clip}(-45\,\mathrm{mV}+\delta_i-a_1r_{1i}o_{1i}+a_2r_{2i}o_{2i},
-52\,\mathrm{mV},-30\,\mathrm{mV}),
\]
\[
\mathrm{gain}_i=\operatorname{clip}\!\left(G_i[1+\gamma_1r_{1i}o_{1i}-\gamma_2r_{2i}o_{2i}],0.2,3.0\right).
\]

The D1/D2 occupancy constants are 1.0/0.05 µM, threshold coefficients 1.5/2.0 mV and gain coefficients both 0.3. Silencing overrides the threshold with 10⁶ mV. Disabling receptor modulation removes the receptor terms. Host-side parameter changes can be uploaded without resetting GPU pools.

With 1 ms chunks, counts accumulate on the GPU until the 10 ms update boundary. The host copies of the dopamine objects do not track evolving GPU pools. These equations include assumed receptor densities and transferred kinetic parameters; accelerating them does not establish their biological accuracy. The kernels follow the CPU operation order using basic floating-point arithmetic and clipping, with fused multiply-add contraction disabled, so exact agreement is possible. In a 0.2-second diagnostic of one control realization with 1 ms chunks (20 pool updates), driven by identical spike counts, maximum absolute GPU-versus-CPU differences in pools, thresholds and gains were all zero. Longer free-dopamine comparisons assessed firing statistics, not state equality.

### Precision and ordering

Voltage, synaptic drive, stored weights, arrival sums and dopamine state use 64-bit floating point. Per-connection scale factors pass through 32-bit precision in both engines before multiplication into the stored weights. Fast math is not enabled and fused multiply-add contraction is disabled. Counts and neuron indices use 32-bit integers. Multiplicities in explicit input files use unsigned bytes.

These choices reduce avoidable rounding differences but do not make the engines bitwise identical. Brian2 calculates electrical variables in SI units; CUDA uses millivolts. The algebraic form of the exact update differs. Atomic additions can arrive in different orders, and CUDA groups pending arrivals separately from the already accumulated drive. Floating-point addition is not associative. Threshold crossings can amplify very small differences into different later spike trains. Identical-input replay checks whether spike outputs agree without conflating the comparison with different random generators; it does not measure sensitivity to a deliberately introduced perturbation.

Despite these possible numerical differences, one second of the same stochastic control produced identical per-neuron counts for all 162,517 neurons (202,658 spikes) across batch sizes of one, eight and 32, CPU and GPU dopamine, 1 ms and 10 ms interfaces, and L4 and A100 GPUs. This is count-level CUDA self-consistency for one realization, not a cross-engine spike-timing result or a guarantee of determinism in every condition.

## Measurements

Times below are single observations, not repeated-run estimates. A brain-second is one simulated second in one complete network. Stepping includes dopamine updates where dopamine is free, output transfers and host result collection. The clamped-rest row executes no dopamine kernels. Network construction and archive writing are separate; Modal startup, queueing and download time are additional. Batch throughput is not the latency experienced by each member of a batch.

| GPU | Brains | Simulated seconds per brain | Interface, ms | Build, s | Step, s | Wall s / brain-s |
|---|---:|---:|---:|---:|---:|---:|
| L4 | 1 | 1 | 10 | 270.17 | 0.793 | 0.7926 |
| L4 | 8 | 1 | 10 | 104.65 | 6.506 | 0.8133 |
| L4 | 32 | 1 | 10 | 105.70 | 24.044 | 0.7514 |
| A100 SXM4 40 GB | 1 | 1 | 10 | 108.09 | 0.994 | 0.9941 |
| L4, clamped rest (no dopamine updates) | 10 | 12 | 10 | 265.89 | 102.117 | 0.8510 |
| L4 | 1 | 1 | 1 | 271.03 | 1.599 | 1.5987 |
| L4, full control | 1 | 12 | 10 | 269.29 | 8.420 | 0.7017 |
| L4, mixed conditions | 32 | 12 | 10 | 280.54 | 332.965 | 0.8671 |
| L4, mixed conditions | 32 | 12 | 10 | 97.41 | 321.258 | 0.8366 |
| L4, mixed conditions | 32 | 12 | 10 | 100.38 | 298.355 | 0.7770 |
| L4, mixed conditions | 32 | 12 | 10 | 274.72 | 311.244 | 0.8105 |
| A10, final mixed subset | 11 | 12 | 10 | 110.70 | 84.559 | 0.6406 |

The A10 was requested through Modal's A10G offering, replacing an L4 call cancelled before a worker started. Its subset differs from the L4 workloads and is not a controlled hardware comparison. In the matched one-network pilot, the A100 was slower than the L4 (0.994 versus 0.793 wall seconds per simulated second); single observations do not rank GPU types. Stepping time grew roughly in proportion to batch size: batching mainly spread construction cost across networks rather than improving stepping throughput. The 32-network one-second pilot took 24.044 wall seconds to advance each member by one simulated second, not 0.7514 seconds of latency. The kernel was not profiled, so its speed limit is unknown. The earlier L4 pilots' GPU memory pool held about 0.53 GB for one network and 1.28 GB for 32; these are pool sizes, not measured peak memory use.

The one-second pilots begin from initialized state, without settling. Full runs include two seconds of settling. Construction took approximately 97–281 seconds, clustering near 100 and 270 seconds, and can dominate a short job. Construction includes loading network tables, sorting outgoing edges, applying the substrate, uploading arrays and compiling kernels; its components and the cause of the two timing clusters were not isolated. Before dopamine composition moved to the GPU, one-second L4 pilots took 1.32–1.39 wall seconds per brain-second, with 0.520 of the single-network run's 1.318 seconds in CPU modulation.

No like-for-like Brian2 benchmark was made, and no engine speedup ratio is claimed. For context only, the identical-input harness on an arm64 Mac with Cython code generation and one process took 3.1–4.0 wall seconds per simulated second intact and 7.0 with GABAergic outputs removed. Those timings use one-second Brian2 run calls, random input disabled and dopamine clamped; they include first-run compilation and spike extraction.

Output collection and activity matter. The ordinary-input timings above returned counts, histograms and first-spike ticks, not every spike. With full spike transfer and extraction in the identical-input replay, CUDA took 1.07–1.13 wall seconds per simulated second intact and 1.78–1.79 with GABAergic outputs removed, when it emitted about ten times as many spikes. All four replay runs were slower than real time.

### One-millisecond follow-up

The three always-returned output arrays—counts, one-millisecond histograms and first-spike ticks—were placed in one contiguous buffer and copied to the host together, rather than through three synchronous transfers. No output was dropped. One initialized brain was then measured for one simulated second at each interface width, using ordinary stochastic input and GPU dopamine updates.

| Interface | Build, s | Stepping wall s / brain-s | Kernel and transfer, s | Function total, s |
|---|---:|---:|---:|---:|
| 1 ms | 112.794 | **1.268480** | 1.098067 | 115.643 |
| 10 ms | 96.910 | **0.637029** | 0.626633 | 99.661 |

The one-millisecond result remains slower than real time. The two pilots produced identical per-neuron counts. The earlier 1.599-second observation and the new 1.268-second observation are single measurements; they do not isolate the transfer change from run-to-run variation. The corresponding 10 ms observations were 0.793 and 0.637 seconds. At 1 ms, kernel-plus-transfer time fell from 1.334 to 1.098 seconds, consistent with fewer synchronous transfers, and host collection from 0.128 to 0.067 seconds. At 10 ms, kernel-plus-transfer time changed little (0.644 to 0.627 seconds); most of that pilot's gain came from time outside the recorded components. Some timing variation therefore remains unexplained. No further interface redesign was attempted.

## Agreement with Brian2

### Earlier independent-random-stream comparison

Ten resting realizations and 140 further runs were evaluated with the same analysis in each engine. The latter comprise ten realizations each of a control, eight transmitter removals (acetylcholine, GABA, glutamate, histamine, dopamine, octopamine, serotonin and neurons without a clear transmitter label) and five stimulation conditions (P1 at three rates, pIP10 and the random control). Resting comparisons used clamped dopamine; the other runs used free dopamine except for dopamine removal as described above. Central-neuron, dopamine-neuron and Kenyon-cell rest means were 4.78950 versus 4.78085, 1.51439 versus 1.51117 and 0.0102338 versus 0.0102092 Hz, respectively, for Brian2 versus CUDA.

Several large effects carried over. Outside the sensory population, acetylcholine removal changed firing by −1.43633 versus −1.44098 Hz; GABA removal by +12.58842 versus +12.60250 Hz; and glutamate removal by +10.77944 versus +10.76028 Hz. In the dPR1 readout, medium P1 stimulation minus random-population stimulation was 17.81 [15.81, 19.82] versus 17.85 [16.48, 19.16] Hz. High minus low P1 stimulation was 15.19 [13.18, 17.53] versus 15.39 [13.94, 17.42] Hz. Brackets are 95% percentile intervals from 10,000 bootstrap resamples of the ten paired realizations. An effect is described as detected when its interval excludes zero. These comparisons were not corrected for multiplicity and are descriptive, not an equivalence test.

Effects measured against the unstimulated control differed more: medium P1 stimulation raised dPR1 firing by 19.24 [16.28, 22.62] Hz in Brian2 and 16.00 [14.57, 17.43] Hz in CUDA. Control means were 22.38 versus 25.77 Hz; two Brian2 control realizations fired near 10 Hz. The stimulated absolute means were 41.62 versus 41.77 Hz, so the control shift accounts for almost all the difference in this paired effect. The two contrasts above avoid subtracting those different controls.

Small effects, two-cluster readouts and timing were not interchangeable. Across all 378 paired group-rate effects, 45 changed detection status and five had non-overlapping intervals. The summary comparison tables cover a subset: detection changed in 14 of their 110 effects, comprising five transmitter-removal readouts involving dopamine, octopamine or serotonin, and nine stimulation readouts, five after stimulation ended. With many uncorrected comparisons, sampling alone can change detection; the counts do not identify a cause.

The largest effect discrepancy followed removal of unclear-transmitter outputs in wing motor neurons: −4.79 [−14.20, 3.63] versus −23.35 [−26.37, −17.84] Hz. Realization means clustered near 5 Hz or 31–36 Hz; three of ten Brian2 and nine of ten CUDA realizations were in the low cluster. The same removal also gave non-overlapping ascending and descending effects. Dopamine removal changed dPR1 firing by −4.15 [−8.86, 0.26] versus −8.34 [−11.54, −4.46] Hz, changing from no detected difference to a detected decrease.

Rest motor means were 6.646 versus 6.282 Hz, largely reflecting one unusually active Brian2 realization; ellipsoid-body ring-neuron means were 0.474 versus 0.533 Hz. The random-drive dPR1 effect changed from +1.43 [−0.76, 3.96] to −1.85 [−2.77, −1.20] Hz. The first interval gives no detected difference; it does not establish equality. Control dPR1 first-spike medians after the window boundary were 22.5 versus 58.5 ms. These are spontaneous first spikes after a boundary, not causal response latencies.

Those comparisons shared realization labels, not random events. In Brian2's generated code, the background draw is inside the non-refractory branch, so random-stream consumption depends on refractory history; CUDA's counter-based stream stays aligned across paired conditions. The earlier data therefore could not isolate input randomness from numerical trajectory sensitivity. The later replay clamped dopamine and did not include the unclear-transmitter removal, dopamine removal or stimulation conditions, so it cannot establish that random streams alone caused these differences.

### Identical-input replay

The follow-up fixed the design before outcomes. Two independently generated background streams were saved and supplied to both engines for intact rest and GABA outgoing-connection removal, giving four matched 12-second comparisons. Dopamine was clamped in both conditions to isolate the LIF computation; the earlier GABA-removal comparison instead had free dopamine dynamics.

At each 0.1 ms tick, each driven neuron received a saved binomial multiplicity generated by NumPy's PCG64 generator. Events were generated even during refractory periods: each engine independently applied its existing refractory rejection. The Brian2 harness disabled stochastic input objects and added a zero-delay spike generator. Its synapses ran at the background input's position in the tick schedule, after recurrent delivery. Virtual sources represented target and multiplicity, so a count of two or more was delivered without asking one source to spike repeatedly in a single tick. CUDA read the same saved event files. Neither reference engine code nor model parameters were changed.

Brian2 ran with Cython code generation on an arm64 Mac; CUDA ran in a Linux x86-64 container on an NVIDIA L4. The resulting spike and count archives were byte-identical across engines. Both used the same network-construction code, so this compares stepping, input delivery and disconnection, not independent construction of the network.

Each call held one network, with CUDA using 10 ms chunks. Thresholds and gains were composed once on the host at the reference dopamine concentration; neither engine updated dopamine during replay. The replay covered neuron integration, thresholding, reset, refractoriness, delayed recurrent delivery, outgoing disconnection, explicit background delivery and full spike recording. It bypassed the engines' random-background samplers, stimulation, GPU dopamine kernels, batching and the 1 ms interface; genotype shifts, silencing and weight scaling beyond the resting substrate were not varied.

The only persistent-kernel change between the earlier outcomes and replay added the explicit-event branch; the stochastic branch was unchanged. The host interface also gained event upload and packed count outputs. For one control realization, the updated 1 ms and 10 ms pilots reproduced the earlier one-second per-neuron counts exactly. This links the revisions at the count level, not for every trajectory.

After two seconds of settling, counts were evaluated separately over the first and second five-second recording windows and over their ten-second union. No stimulus changed at their boundary. All output spikes, including settling, were saved. Canonically ordered neuron/tick pairs were compared to find any first unequal output tick. Such a tick would mark the first **spike** divergence, not the first difference in floating-point state. Agreement of window counts alone includes silent neurons and does not imply exact timing.

**The engines produced identical spike output in all four tested trajectories.** Every one of the 162,517 neurons had exactly the same count in the first window, second window and combined ten seconds in each matched run. The signed count-difference distribution was entirely at zero: 162,517 zeros per comparison, with mean, mean absolute difference, root-mean-square difference, minimum, maximum and every reported absolute quantile equal to zero. Because the absolute counts matched, per-neuron GABA-minus-intact count effects also matched exactly.

This was not merely a match between mostly silent neurons. All **58,655,422** spikes emitted by each engine across the four trajectories matched at the 0.1 ms grid resolution, including settling: 5,453,856 in the intact runs and 53,201,566 with GABAergic outputs removed. **No first spike divergence was observed anywhere in the 12-second runs.**

Selected ten-second group means, averaged over the two input realizations, are shown below. The reproducibility record provides every group and both five-second windows separately.

| Group | Intact Brian2, Hz | Intact CUDA, Hz | GABA removed Brian2, Hz | GABA removed CUDA, Hz |
|---|---:|---:|---:|---:|
| Central neurons | 4.864888 | 4.864888 | 27.530368 | 27.530368 |
| Dopamine neurons | 1.601090 | 1.601090 | 140.603951 | 140.603951 |
| Kenyon cells | 0.009117 | 0.009117 | 147.468147 | 147.468147 |
| Ellipsoid-body ring neurons | 0.581738 | 0.581738 | 3.844504 | 3.844504 |
| Motor neurons | 8.292221 | 8.292221 | 57.236697 | 57.236697 |
| Outside sensory population | 1.468613 | 1.468613 | 13.436862 | 13.436862 |

Thus no spike-output discrepancy remains when external randomness is controlled in this clamped setting. The result does not establish bitwise equality of voltage or drive, which were not recorded, or settle every earlier free-dopamine and stimulated comparison. The earlier small-effect intervals should not be treated as interchangeable simply because these replay trajectories agree. No perturbation experiment measured how quickly a rounding-sized state difference would change spike output in this network.

## Replication of a full experiment

The [GABA concentration-response replication](gaba-dose-gpu.md) repeated the whole ladder with the same design, independent random streams and each engine's own controls. The conditional block Hill slope was **4.99 [4.65, 5.43]** on CUDA versus **5.05 [4.76, 5.34]** on Brian2; half the observed full-block change occurred at **80.12% [79.95%, 80.30%]** versus **80.11% [79.90%, 80.33%]** block. The three GluCl rescue fractions (CUDA versus Brian2) were **23.6% [21.8%, 25.2%] versus 23.5% [20.9%, 26.0%]**, **45.1% [43.8%, 46.2%] versus 45.5% [44.7%, 46.5%]**, and **75.0% [74.0%, 75.9%] versus 75.0% [73.7%, 76.1%]**. These interval pairs overlap; they do not establish statistical equivalence. The GPU boost fitted half-effect was not identified within the tested range, despite overlapping rate intervals at each dose. This experiment-level agreement does not extend the identical-input replay's exact-spike scope or validate native pharmacology. Input is injected into sensory cells at dark rest; the fly does not see.

## Cost

Costs distinguish stepping from starting a short cloud job. Using the submit driver's assumed Modal rates for the September 2026 runs of $0.80/hour for L4, $0.0473 per CPU-hour for two CPUs and $0.008 per GiB-hour for 16 GiB, the complete one-brain control's measured stepping time implies approximately **$0.000199 per brain-second** of steady stepping. Its actual metered whole-job cost was **$0.006959 per brain-second**, because construction and other charged work dominate a 12-second job. The rate-derived figure is not a separately metered kernel charge.

For the four full L4 batches of 32 brains, metered whole-job costs were **$0.000306–$0.000463 per brain-second**. The A10 subset cost **$0.000577 per brain-second** metered. The one-brain A100 pilot cost **$0.074840 per brain-second** metered, dominated by construction; its rate-derived stepping cost was about **$0.000641 per brain-second**. The resource assumptions for those calculations use $1.10/hour for A10G and $2.10/hour for A100, with the same CPU and memory reservation.

All earlier GPU development, diagnostics and outcomes together cost **$1.495838 metered**, including unsuccessful submissions. The identical-input follow-up, including four full-spike replays, both interface pilots and their builds, cost **$0.40490238 metered** in total. No separate per-pilot metered charge was available because they shared one app; dividing the app bill into invented pilot costs would be misleading. Its rate-derived stepping estimates are approximately $0.000360 per brain-second at 1 ms and $0.000181 at 10 ms. Together, the two stages cost $1.900740 metered. The follow-up remained below its $5 allocation.

## Limits and a real-time body loop

The implementation supports the adopted plain LIF model, background input, extended stimulation, outgoing disconnections and the existing dopamine layer. It does not implement adaptation, short-term depression, conductance inhibition, upstream input banks, voltage traces or the reference engine's general deterministic spike-list input (events at listed ticks). The explicit-background replay path is not a replacement for that general input. CUDA requires a compatible NVIDIA GPU with cooperative launch support. The implementation was measured with CUDA 12.6.3 and CuPy 13.6.0; the reference uses Brian2 2.10.1. Both replay platforms used NumPy 2.5.3, with Python 3.12.14 on the Mac and 3.12.1 in the cloud container.

A body loop would still need a defined mapping from simulated firing to actuators, sensory transduction back into model input, body/physics stepping, and a measured end-to-end latency budget. Construction must be amortized by keeping the network resident. The body and neural integration schedules must be synchronized, with dopamine still advancing at its prescribed cadence. Reporting throughput for a GPU-only neural workload cannot establish responsiveness once rendering, physics and communication are included. Likewise, reducing returned outputs to selected motor populations would be a different interface that needs its own measurement.

The input replay supplies two realizations and one disconnection, not every stimulus, genotype or receptor setting. Agreement of mean rates does not establish spike-train equivalence, nor does computational agreement validate the model against living flies. Publication would also require positioning against other GPU simulators, including Brian2CUDA, GeNN/Brian2GeNN and NEST GPU, and independent replication. None was benchmarked here; these measurements alone do not establish a new best-in-class simulator.

## References

Software and comparison-simulator citations named above, with primary-source verification recorded in an internal software citation audit held outside the public snapshot:

- Stimberg M, Brette R, Goodman DFM (2019). Brian 2, an intuitive and efficient neural simulator. *eLife* 8:e47314. [doi:10.7554/eLife.47314](https://doi.org/10.7554/eLife.47314).
- Salmon JK, Moraes MA, Dror RO, Shaw DE (2011). Parallel random numbers: as easy as 1, 2, 3. *SC '11*, article 16:1–12. [doi:10.1145/2063384.2063405](https://doi.org/10.1145/2063384.2063405). Philox/Random123.
- Okuta R, Unno Y, Nishino D, Hido S, Loomis C (2017). CuPy: A NumPy-compatible library for NVIDIA GPU calculations. *NIPS LearningSys Workshop*, paper 16. [Workshop PDF](http://learningsys.org/nips17/assets/papers/paper_16.pdf); no registered DOI.
- NVIDIA Corporation (2024). *NVIDIA CUDA Runtime Compilation (NVRTC) Library*. CUDA Toolkit Documentation, version 12.6. [Official documentation](https://docs.nvidia.com/cuda/nvrtc/index.html).
- Alevi D, Stimberg M, Sprekeler H, Obermayer K, Augustin M (2022). Brian2CUDA: Flexible and efficient simulation of spiking neural network models on GPUs. *Frontiers in Neuroinformatics* 16:883700. [doi:10.3389/fninf.2022.883700](https://doi.org/10.3389/fninf.2022.883700).
- Yavuz E, Turner J, Nowotny T (2016). GeNN: a code generation framework for accelerated brain simulations. *Scientific Reports* 6:18854. [doi:10.1038/srep18854](https://doi.org/10.1038/srep18854).
- Stimberg M, Goodman DFM, Nowotny T (2020). Brian2GeNN: accelerating spiking neural network simulations with graphics hardware. *Scientific Reports* 10:410. [doi:10.1038/s41598-019-54957-7](https://doi.org/10.1038/s41598-019-54957-7).
- Golosio B, et al. (2021). Fast simulations of highly-connected spiking cortical models using GPUs. *Frontiers in Computational Neuroscience* 15:627620. [doi:10.3389/fncom.2021.627620](https://doi.org/10.3389/fncom.2021.627620). NeuronGPU.
- Tiddia G, et al. (2022). Fast simulation of a multi-area spiking network model of macaque cortex on an MPI-GPU cluster. *Frontiers in Neuroinformatics* 16:883333. [doi:10.3389/fninf.2022.883333](https://doi.org/10.3389/fninf.2022.883333). NEST GPU.

These works describe other simulators; none was benchmarked against this engine here.

## Sources and reproducibility

- Berg et al., *Sexual dimorphism in the complete Drosophila male central nervous system connectome*, Cell 189:5504–5526.e15 (2026), [doi:10.1016/j.cell.2026.08.015](https://doi.org/10.1016/j.cell.2026.08.015); [MaleCNS dataset](https://male-cns.janelia.org/). Anatomical identity only; this does not validate the model's resting activity.
- Shiu et al., *A Drosophila computational brain model reveals sensorimotor processing*, Nature 634:210–219 (2024), [doi:10.1038/s41586-024-07763-9](https://doi.org/10.1038/s41586-024-07763-9). Model lineage; not validation of the added male dopamine model. Existing literature access and claim limits are documented in the [source audit](../paper/references-verified.md).
- [Dataset adapter](../src/flyonenomics/datasets.py), [population definitions](../data/populations-male-cns-v1.0.yaml), [Brian2 reference engine](../src/flyonenomics/engine/brian_engine.py), [model equations](../src/flyonenomics/engine/models.py), [parameter sources](../data/params-v0.2.yaml), [adopted rest substrate](../data/drive-male-cns-v1.0.yaml), and [dopamine coefficients](../data/dopamine-male-cns-v1.0.yaml).
- [CUDA engine](../src/flyonenomics/engine/cuda_engine.py), [persistent kernel](../src/flyonenomics/engine/cuda_tick.cu), and [dopamine kernels](../src/flyonenomics/engine/cuda_dopamine.cu). [Brian2 documentation](https://brian2.readthedocs.io/), [CuPy RawModule](https://docs.cupy.dev/en/stable/reference/generated/cupy.RawModule.html), and [CUDA programming guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/) name the software mechanisms; timings come from the records below, not vendor claims.
- Earlier [speed measurements](../validation/records/p2/male-cuda-speed.md) and [full timing components](../validation/records/p2/male-cuda-speed.json), [agreement measurements](../validation/records/p2/male-cuda-comparison.md) and [complete group effects](../validation/records/p2/male-cuda-comparison.json), [discrepancy analysis](../validation/records/p2/male-cuda-differences.md), [diagnostics](../validation/records/p2/male-cuda-checks.json), and [metered receipts](../validation/records/p2/male-cuda-receipts.json).
- Identical-input [frozen protocol](../validation/records/p2/male-cuda-identical-plan.md), [event manifest](../validation/records/p2/male-cuda-identical-inputs.json), [comparison and archive bindings](../validation/records/p2/male-cuda-identical-comparison.json), and [receipts and interface timings](../validation/records/p2/male-cuda-identical-receipts.json). Exact seeds, hashes and run identifiers belong to these reproducibility records, not to the scientific narrative.
- [Follow-up checks](../validation/records/p2/male-cuda-identical-checks.json) bind the kernel sources and verify per-neuron count agreement between the interface pilots and existing GPU pilots. Reproduction commands and raw archive locations are in the [backend guide](cuda-backend.md).

AI coding assistants contributed implementation, computational checks and drafting. This document does not imply independent human review of every generated line or biological validation of the added mechanisms.
