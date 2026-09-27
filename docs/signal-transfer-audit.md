# Where the visual signal disappears

## Result

The two failures are different.

- **Eye:** the stripe changes R1–6 spikes, signed recurrent event amplitude, and every traced immediate target's voltage. None of the 64 strongest condition-sensitive targets spikes. The signal reaches synaptic current and membrane voltage, then dies at spike conversion because these targets remain far below their composed thresholds.
- **TuBu:** the represented route is present and TuBu's strongest immediate children do receive the signal. All 64 receive positive direct event-amplitude changes, all show a higher sampled voltage maximum, and 37 have a positive three-seed spike-count change. The TuBu null therefore does **not** begin at TuBu's first synapse. Instead, TuBu's direct coverage of the reported populations is sparse: 244 of 8,053 `visual_projection` cells and 5 of 547 `LAL_neurons`, with no direct DNa02 or steering cell. Positive two-hop routes to both DNa02 cells exist, but they run through a very small set of intermediates.

This rules out a general engine or routing defect at both tested first synapses. It confirms the eye's operating-point failure. For TuBu it narrows the loss to the sparse readout route and later integration, after a functioning first relay; it does not show that every weak direct LAL row or every second-hop cell is excitable.

These are model measurements, not firing floors or acceptance lines. The declared substrate remains `rest:379cc4cc9030cdd1`; no canonical data file was changed.

## Test 1: static TuBu audit

The complete per-root inventory is in `validation/records/p2/signal-transfer-audit.json` under `static_paths.TuBu.targets`. It records every immediate target's engine index, root ID, annotation cell type, side, background group, membership in each reported population, anatomical count, and composed signed weight.

The corrected WP20 fixture was read at its pinned commit `5f2cefc`. Both probes in `data/experiments/p2/vpath-vtcal.json` say `inject_at: TuBu`. The encoder population contains exactly 150 unique TuBu cells. Its root-ID hash is `c6571103…b10e`. The fixture observes `TuBu`, `visual_projection`, `LAL_neurons`, `steering_L`, and `steering_R`; those names exactly match the populations represented in its VT-cal record. Counts and hashes of every observer subset are retained in the evidence.

### Immediate efferents

| Source | Source cells | Connection pairs | Anatomical synapses | Immediate targets | Effective sign | Effective sum |
|---|---:|---:|---:|---:|---|---:|
| R1–6 | 7,932 | 26,983 | 226,909 | 6,933 | all inhibitory | −62,399.975 mV |
| TuBu | 150 | 1,859 | 21,349 | 656 | all excitatory | +5,870.975 mV |

The base recurrent weight is 0.275 mV per anatomical synapse. Curated R1–6 is histaminergic with gain 1, so its composed rows are `−0.275 mV × count`. Curated TuBu is cholinergic with gain 1, so its rows are `+0.275 mV × count`. The declared scale-array hash is `9f7ad6bb…aea88`; this includes every transmitter, optic-exemption and GABA→KC factor even though the two audited source classes themselves use unit gain. The dynamic event sums below additionally include the live postsynaptic dopamine gain.

R1–6's immediate targets are 5,876 optic and 1,057 sensory cells. TuBu's are 408 central, 244 visual-projection, three visual-centrifugal and one descending cell. TuBu coverage of the recorded/downstream populations is:

| Population | Direct targets reached | Population cells | Coverage | Direct pairs | Anatomical synapses | Effective sum |
|---|---:|---:|---:|---:|---:|---:|
| `visual_projection` | 244 | 8,053 | 3.030% | 281 | 305 | +83.875 mV |
| `LAL_neurons` | 5 | 547 | 0.914% | 5 | 7 | +1.925 mV |
| `steering_L` | 0 | 2 | 0% | 0 | 0 | 0 |
| `steering_R` | 0 | 2 | 0% | 0 | 0 | 0 |
| `DNa02_L` | 0 | 1 | 0% | 0 | 0 | 0 |
| `DNa02_R` | 0 | 1 | 0% | 0 | 0 | 0 |

The 244 direct visual-projection targets are mostly MeTu cells: 70 MeTu1, 41 MeTu2, 74 MeTu3 and 43 MeTu4, plus small LC10 and unresolved groups. The five direct LAL rows carry only one, one, one, one and three anatomical synapses. None of the 64 strongest condition-sensitive TuBu targets belongs to the broad visual-projection, LAL or steering observers; those observer rows are weaker than the selected first-relay rows.

### Shortest signed routes

A directed search over every nonzero composed edge finds represented routes from the injected TuBu set:

| Readout | Shortest route | Sign | Example effective edge weights |
|---|---:|---|---|
| `LAL_neurons` | 1 hop | positive | five reached cells, +0.275 to +0.825 mV |
| `DNa02_L` | 2 hops | positive | +0.825, then +5.500 mV |
| `DNa02_R` | 2 hops | positive | +0.275, then +1.925 mV |
| `steering_L` | 2 hops | positive | both cells reachable; examples +0.275/+0.275 and +0.825/+5.500 mV |
| `steering_R` | 2 hops | positive | both cells reachable; examples +0.275/+1.925 and +0.275/+0.550 mV |

The exact root paths and every edge's anatomical count, effective weight and sign are committed in the record. Thus “the path is absent” is false. “The path represented by the population averages is broad” is also false: direct TuBu coverage is sparse and the shortest steering routes depend on a few small first-hop rows.

## Test 2: immediate-child voltage transfer

### Protocol

For each path, targets were ranked by the absolute expected paired change in source event-amplitude rate, not by a desired response. Up to 64 immediate targets were traced. The eye pair was ambient versus a 5° stripe at +45° with 150 Hz light. The TuBu pair was input off versus a +45° stripe with a 70 Hz cap and 20° encoder width. Each condition started from the same stored declared state and ran for 2 s settle plus 2 s measurement, independently for seeds 1–3.

The signed incoming-event measurement is the sum of recurrent event amplitudes over the 2 s window after declared substrate scaling and the live postsynaptic gain. It excludes external and background Poisson events. Each target row also records spikes in its connected source cells, target spikes, full 0.1 ms membrane samples, composed threshold distance, and both source-only and all-recurrent event sums.

This final run is 2 paths × 2 conditions × 3 seeds × 4 s = **48 brain-seconds**. It ran on Oracle as **linux-aarch64**, plain `lif`, with four workers and one whole-brain job per child. Individual paired jobs took 404–451 wall-seconds. Two excluded launches are documented in `camber-runs/diag/signal-transfer/attempts.md`: a schema rejection advanced no time, then a worker-reuse teardown failed after at least 36 extra brain-seconds. Their outputs were removed before the final run.

### Eye: current and voltage move, spikes do not

The stripe changed whole-population R1–6 rate by −1.028, −1.036 and −1.041 Hz across the three seeds (−16,307 to −16,509 spikes over each 2 s whole-source comparison). For every traced target, its connected R1–6 cells emitted fewer spikes.

Three-seed per-target paired means across the 64 strongest targets:

| Measurement, stripe minus ambient | Across-target mean | Median | Target range | Direction count |
|---|---:|---:|---:|---:|
| Source-only incoming event amplitude | +808.262 mV | +702.212 | +384.817 to +1,678.325 | 64 positive |
| All recurrent incoming event amplitude | +808.218 mV | +702.121 | +384.817 to +1,678.325 | 64 positive |
| Mean membrane voltage | +2.024 mV | +1.769 | +1.012 to +4.154 | 64 positive |
| Sampled maximum voltage | +1.925 mV | +1.761 | +0.268 to +4.290 | 64 positive |
| Target spike count | 0 | 0 | 0 to 0 | 64 zero |

The positive event change is release from histaminergic inhibition: fewer R1–6 spikes make the signed sum less negative. Mean target voltage was −71.024 mV in ambient and −69.001 mV under the stripe when pooled over targets and seeds. Under the stripe, per-target/seed mean voltage ranged from −107.519 to −56.073 mV. Mean distance to threshold ranged from 11.073 to 62.519 mV, and the nearest sampled distance still ranged from 8.919 to 52.574 mV. No traced target spiked in either condition.

The engine therefore carries the eye signal through source spikes, signed synaptic events and voltage. The break is the conversion of that subthreshold voltage into spikes. This reproduces the operating-point diagnosis at a stronger, condition-selected set of immediate targets; it does not reopen routing or indexing.

### TuBu: the first relay transmits

Turning TuBu input on changed whole-population TuBu rate by +9.623, +9.427 and +9.297 Hz across the seeds (+2,887, +2,828 and +2,789 spikes over 2 s). All 64 targets received a positive direct TuBu event-amplitude change.

| Measurement, on minus off | Across-target mean | Median | Target range | Direction count |
|---|---:|---:|---:|---:|
| Source-only incoming event amplitude | +1,952.583 mV | +1,369.490 | +471.842 to +10,231.283 | 64 positive |
| All recurrent incoming event amplitude | +1,515.621 mV | +1,015.719 | −669.142 to +9,528.475 | 59 positive, 5 negative |
| Mean membrane voltage | +1.796 mV | +2.097 | −2.225 to +4.906 | 58 positive, 6 negative |
| Sampled maximum voltage | +6.265 mV | +6.926 | +2.909 to +7.256 | 64 positive |
| Target spike count | +13.495 | +0.333 | 0 to +135 | 37 positive, 27 zero |

Every target was silent with input off. With input on, the 64 targets emitted 2,591 spikes across the three 2 s measurements; 37 targets had a positive three-seed mean spike change. Mean distance to threshold changed from 7.235 to 5.440 mV when pooled over targets and seeds. The on-condition mean gaps ranged from 2.116 to 9.827 mV, while nearest sampled gaps ranged from approximately 0 to 5.131 mV. Among targets that remained silent in a seed, the closest sampled gaps reached 0.079, 0.135 and 0.142 mV in seeds 1–3.

The five negative all-recurrent event changes and six negative mean-voltage changes occur despite positive direct TuBu events, so recurrent network input can oppose the direct excitation. They are not missing source routing: every target's sampled maximum still rises. Some silent near-threshold children may depend on integration timing, but the first-relay population as a whole clearly converts the TuBu signal into spikes.

## What the two tests rule in and out

1. **General engine/routing defect: ruled out at both immediate relays.** Nonzero source changes and composed weights produce signed event changes and voltage changes. TuBu also produces immediate-child spikes.
2. **Eye operating point: ruled in.** The eye signal is measurable in current and voltage but remains many millivolts below threshold at the strongest affected targets. Point-LIF's spike-only output stops it there.
3. **Missing TuBu graph path: ruled out.** Positive one- and two-hop paths reach LAL, DNa02 and both steering populations.
4. **TuBu first-synapse threshold failure: ruled out as a general explanation.** Most strongest children depolarize and 37 of 64 increase their spikes.
5. **Sparse route/readout mismatch: ruled in as a material limit.** Only 5 LAL cells and no steering cells are immediate TuBu targets, and none of the 64 strongest affected children is in the broad populations averaged by the existing record. A spiking response confined to the directly reached cells would be diluted about 33-fold in the 8,053-cell `visual_projection` observer and about 109-fold in the 547-cell `LAL_neurons` observer, before later integration is considered. Whether those directly reached observer cells spike is not measured here.
6. **Later TuBu operating-point or integration failures: still possible.** This probe intentionally stops at the strongest immediate children. It does not dynamically trace the weak five-cell direct LAL subset or the second hop into DNa02, so it cannot claim those later relays are excitable.

The evidence supports the consult's model-limitation diagnosis for the eye and narrows the TuBu result: the synthetic central input does propagate locally, but the measured steering route is sparse and the population readouts do not follow the strongest efferents.

## Evidence and identity

- Runner: `scripts/audit_signal_transfer.py`
- Raw: `camber-runs/diag/signal-transfer/`
- Committed record: `validation/records/p2/signal-transfer-audit.json`
- Executed source: `59f6851b285f7735c5c9075918f545f3bec9a60b`
- Executed runner SHA-256: `78b522e6b38378a93655678db563118cf4e3526bca63261f97e755a4a530ed66`
- Committed runner SHA-256: `69e88705bf46c3975c642fa2d200901224156a0d38fcdf3117076480be763114` (adds the checked JSON reader in `cb1fe57`, after the final run; the record binds the executed runner)
- Drive SHA-256: `379cc4cc9030cdd1bc2235ae28a97f96d0f90c9a95879a51388a5cff513ec278`
- Dopamine SHA-256: `629d4017d96588401a2517c7afec719d4b26944453bed2253bfff635975e81`
- Connectivity SHA-256: `efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347`
- Background-array SHA-256: `02b5dd6377c73da5d9c16981b725daaaaea53dd039cc2e8dbef1619b5c8a8df5`
- Scale-array SHA-256: `9f7ad6bb0c93974297283f2e40e1e2ac8f18260f364843afed23b0cb1c6aea88`

The zero-brain-second graph audit ran on `darwin-arm64`; the 48-brain-second voltage probe ran on `linux-aarch64`. The record retains all source/input/connectome hashes, target identities, raw-file hashes and per-seed values rather than borrowing an earlier run identity.
