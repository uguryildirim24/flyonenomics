# Interpreting the CUDA/Brian2 comparison

The ten rest seeds and all 140 tour outcomes are complete. The unchanged tour analysis was run on both engines. No parameters, populations, windows or seeds were fitted or replaced. All values below come from `male-cuda-comparison.json`; the complete tables are in the adjacent Markdown record.

The model receives injected input; the fly does not see or sing. Visual input elsewhere is injected at TuBu; this tour injects the named courtship populations.

## What carries over

Rest central, DAN and KC means (Brian2 → CUDA, Hz) are 4.78950 → 4.78085, 1.51439 → 1.51117 and 0.0102338 → 0.0102092. Global Fano means are 2.96934 → 3.00057.

The large knockout effects retain their direction and magnitude. Outside-sensory mean changes are −1.43633 → −1.44098 Hz for acetylcholine, +12.58842 → +12.60250 for GABA and +10.77944 → +10.76028 for glutamate. Histamine's optic intervals and dopamine's outside-sensory intervals contain zero in both cohorts: **no detected difference**, not equality.

The dPR1 courtship contrasts also carry over (Hz, paired whole-seed 95% bootstrap):

| Contrast | Brian2 | CUDA |
|---|---:|---:|
| P1 medium minus random drive | 17.81 [15.81, 19.82] | 17.85 [16.48, 19.16] |
| P1 high minus low | 15.19 [13.18, 17.53] | 15.39 [13.94, 17.42] |

P1 and pIP10 injection increase dPR1 firing in both cohorts. All five OFF-versus-control dPR1 intervals contain zero. This is simulated firing, not song production.

## Why the courtship-versus-control numbers differ

The dPR1 control mean in the ON window is 22.38 Hz in Brian2 and 25.77 Hz in CUDA, a 3.39 Hz shift. Brian2 has two low-rate control realizations (10.1 and 10.0 Hz); CUDA's control range is 20.2–31.1 Hz. Numerical seed labels identify the experiments, not identical random streams across engines.

Stimulated absolute means are much closer:

| ON dPR1 rate (Hz) | Brian2 | CUDA |
|---|---:|---:|
| P1 low | 33.42 | 34.11 |
| P1 medium | 41.62 | 41.77 |
| P1 high | 48.61 | 49.50 |
| pIP10 | 36.79 | 38.18 |
| Random drive | 23.81 | 23.92 |

Thus the P1-medium paired-effect difference is exactly `(41.77−41.62) − (25.77−22.38) = −3.24 Hz`: the control cohort explains almost all of it. Random-drive versus control changes from +1.43 [−0.76, 3.96] to −1.85 [−2.77, −1.20] Hz. That changed detection must not be described as reproducing the same null result. The specificity contrast against random drive is nearly unchanged because it does not subtract the differing controls.

## First-spike timing is not identical

Median dPR1 first-spike times after ON (ms) are:

| Condition | Brian2 | CUDA |
|---|---:|---:|
| Control | 22.5 | 58.5 |
| P1 low | 19 | 37.5 |
| P1 medium | 16 | 23 |
| P1 high | 13.5 | 18 |
| pIP10 | 16 | 26.5 |
| Random drive | 23 | 58 |

These are the first spikes after the window boundary, **not estimates of the first causal response**: the neurons already fire without injection. The difference is present in the controls before interpreting any input response. Higher P1 drive shortens the median in both cohorts. Checking all 420 control/courtship group/windows per backend found no mismatch between the reported first-spike time and the first nonzero 10 ms count bin. This rules out a chunk-offset error in those records, not a difference in underlying trajectories. Full latency lists are retained.

## Rest and small-knockout discrepancies

- Rest motor means are 6.64612 → 6.28166 Hz. Brian2 seed 2 is 9.51432 Hz; the other nine average 6.32743. CUDA has no comparable high-rate realization (range 6.01150–6.50158). This accounts for most of the mean shift. This leave-one-out calculation is descriptive only; the primary record retains all ten seeds.
- Rest ER means are 0.47394 → 0.53323 Hz. Mean bootstrap intervals are [0.43869, 0.51376] and [0.50280, 0.56784]. This remains a measured cohort difference, not a demonstrated equivalence or a reason to refit ER parameters.
- Octopamine's outside-sensory effect changes from −0.04070 [−0.06005, −0.02294] to −0.01538 [−0.03338, 0.00086] Hz. Central, motor and ascending groups contribute +0.01355, +0.00535 and +0.00418 Hz to that cross-engine effect difference. Motor effects themselves change from −0.6390 to +0.2500 Hz, with substantial seed variation.
- Serotonin changes from +0.01310 [0.00209, 0.02905] to +0.00525 [−0.00203, 0.01259] Hz outside sensory. Its detection also changes.
- The unclear-transmitter effect is −0.12991 → −0.16982 Hz. Central, ascending and motor contribute −0.01255, −0.01130 and −0.00879 Hz to the difference. Low motor activity realizations near 2.2 Hz occur more often in this CUDA cohort; both cohorts also contain higher-rate realizations. The JSON provides the exact population-weighted decomposition for every knockout.

## What the investigation establishes—and does not

Scheduling was checked against Brian2's conditional refractory writes, exact LIF update, delay ordering, binomial background and Bernoulli extended input. Both engines use the same substrate bindings. GPU dopamine evaluated on identical counts matched CPU pools, thresholds and gains exactly in the 0.2 s diagnostic. Across existing one-second GPU pilots, all 162,517 seed-501 neuron counts matched across batch sizes 1/8/32, CPU/GPU dopamine, 1/10 ms chunks and L4/A100.

CUDA uses counter-based input draws that stay aligned across paired arms. Brian2's consumed random stream can diverge with refractory trajectories. This changes pairing and interval widths as well as finite-cohort realizations. Atomic summation order and mV-versus-volt arithmetic are additional numerical differences. The observed control shifts and population decompositions explain where the reported differences enter; these runs do **not** isolate RNG effects from floating-point trajectory sensitivity or establish distributional equivalence for every small effect. No such claim is made, and Brian2 remains the reference.
