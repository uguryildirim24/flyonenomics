# What happens when the fly model's GABA brake is dialled down?

In this male fly network, reducing GABA-class synaptic conductance raises firing outside the sensory neurons. The response is gradual at first and accelerates at high block. Increasing that conductance lowers activity slightly; strengthening the separate glutamate-gated chloride brake brings most, but not all, of the partially blocked response back toward rest. These are **model firing rates**, not drug treatment in a fly, a seizure diagnosis or movement. These dark-rest runs inject sensory background drive without a TuBu stimulus; the fly does not see.

[Conductance-response curves](../figures/3d/gaba-dose/curves.svg) · [3D dose overview](../figures/3d/gaba-dose/overview.png) · [interactive 3D model](../figures/3d/gaba-dose/male-cns-atlas.html). The interactive view and individual images cover every block, potentiation and rescue level. Colours show changes from rest on a shared scale; displayed skeletons are anatomical representatives, not the entire measured population.

## Dose means a fraction of GABA conductance blocked

The model's dose axis is the fraction of GABA-class conductance blocked, and it is not mapped to a drug concentration because the source potency could not be verified. The model scales all GABA-class conductances uniformly and does not simulate picrotoxin's other channel targets, absorption, receptor distribution or chloride reversal. The two other axes below are **conductance multipliers**, not measured drug concentrations: no positive-modulator potency for fly Rdl or GluCl agonist potency calibrates them.

The block levels were 10%, 25%, 50%, 75%, 90% and 100%.

The reference control and full GABA-off responses were reproduced exactly, neuron by neuron, before the design was frozen. The results use that reference control, with paired whole-run bootstrap intervals. A 95% interval containing zero means **no detected difference**, not that two conditions are the same. The control outside-sensory rate was 1.438 Hz.

## Five predictions, checked against the observations

1. **Block raises firing monotonically to GABA-off — matching.** Outside-sensory rate differences from rest at 10%, 25%, 50%, 75%, 90% and 100% block were respectively **+0.093, +0.295, +0.972, +4.591, +9.591 and +12.588 Hz**. Their paired 95% intervals were [0.075, 0.107], [0.276, 0.318], [0.917, 1.022], [4.536, 4.652], [9.407, 9.753] and [12.563, 12.613] Hz. The full-block endpoint matches the earlier GABA-off result.
2. **An amplified response with a half-effect below 50% block — opposite for the half-effect; matching for steepness, but the network Hill EC50 is unresolved.** Half of the *observed full-block change* is reached at **80.1% block [79.9%, 80.3%]**, well above 50%. A free-asymptote Hill fit gives slope **5.05 [4.76, 5.34]** but extrapolates its half-effect to **99.9% [96.1%, 105.4%]**; the interval extends beyond physically possible occupancy. It would be misleading to present that value as an identified network EC50. The steep late response is real within the sampled doses; its asymptotic potency is not measured.
3. **A sharp synchrony tipping point with central brain first — unclear for a single tipping point; opposite for the proposed region order.** The largest 1 ms spike fraction *b* rises from a change of +0.00120 [0.00108, 0.00130] at 50% block to +0.00550 [0.00536, 0.00564] at 75%, then +0.01045 [0.01026, 0.01065] at 90%. There is no single resolved discontinuity between sampled doses. Fano changes are **−0.196 [−0.451, 0.074]**, **+0.881 [0.734, 0.999]**, **−0.164 [−0.468, 0.210]**, and **−1.013 [−1.154, −0.911]** at 50%, 75%, 90%, and full block. Thus Fano does *not* climb monotonically with b. Central and optic differences are already detected at the first sampled block; the optic lobes reach half their observed full-block change at **74.5% [73.8%, 75.1%]**, the central region at **82.9% [82.4%, 83.4%]**. These normalised within-region readouts do not support central-first tipping, although central firing changes far more in absolute Hz (at 75%: +7.037 [6.885, 7.206] versus optic +0.157 [0.154, 0.161]).
4. **Potentiation decreases firing more shallowly than block raises it — matching.** Extra GABA conductance φ of 0.25, 0.50, 1.00 and 2.00 lowers outside-sensory firing by **0.260 [0.238, 0.281]**, **0.442 [0.432, 0.456]**, **0.611 [0.598, 0.625]**, and **0.835 [0.823, 0.847] Hz** respectively. The best-fit Hill half-effect is **φ = 1.26 [0.96, 1.80]**, slope **0.88 [0.78, 1.00]**. This fit is in φ units, not an Rdl-modulator EC50 in µM. At the strongest potentiation the fall remains much smaller than the full-block rise; the injected drive remains present.
5. **GluCl reinforcement partially rescues 75% GABA block — matching.** Extra Glu conductance ψ of 0.50, 1.00 and 2.00 removes **23.5% [20.9%, 26.0%]**, **45.5% [44.7%, 46.5%]** and **75.0% [73.7%, 76.1%]** of the blocked outside-sensory excess. Even at the strongest rescue, firing remains **+1.147 [1.103, 1.205] Hz** above rest. The rescue fraction is a paired fraction of mean changes; it is not the fraction of biological receptors recovered.

## Regional curves

Each entry is a fitted Hill half-effect in the axis units, then slope, both with 95% whole-run bootstrap intervals. “Not resolved” means that a stable fit or an in-range half-effect was not supported; it does not mean no firing response. For block, central and whole-brain free-asymptote fits run past the tested range, so the directly interpolated within-range half-endpoint values above are more useful. The central, optic, descending and motor labels are network groups, not a claim about where native Rdl is expressed.

| Region/group | Block: half-effect; slope | Potentiation: half-effect; slope |
|---|---|---|
| Dopamine neurons | not resolved | 0.25 [0.23, 0.27]; 2.93 [2.62, 3.39] |
| Ring neurons | not resolved | not resolved |
| Kenyon cells | not resolved | not resolved |
| Ascending | not resolved | not resolved |
| Central | not resolved | 1.36 [1.10, 1.77]; 0.90 [0.83, 0.98] |
| Descending | not resolved | 0.42 [0.40, 0.44]; 1.30 [1.18, 1.42] |
| Endocrine | 0.64 [0.59, 0.76]; 3.97 [2.81, 5.33] | 0.32 [0.30, 0.34]; 2.91 [2.68, 3.27] |
| Motor | not resolved | 0.39 [0.32, 1.67]; 1.39 [0.52, 3.41] |
| Optic | 0.87 [0.85, 0.90]; 4.66 [4.45, 4.83] | 0.09 [0.03, 0.14]; 1.15 [0.40, 1.84] |
| Sensory | not resolved | not resolved |
| Visual centrifugal | not resolved | not resolved |
| Visual projection | not resolved | not resolved |
| Courtship P1 | not resolved | not resolved |
| Descending song command | not resolved | 0.18 [0.10, 0.26]; 1.83 [1.20, 2.34] |
| Song pattern dPR1 | not resolved | 0.22 [0.14, 0.29]; 2.01 [1.28, 2.65] |
| Song pattern vPR6 | not resolved | not resolved |
| Song pattern TN1a | not resolved | 0.18 [0.11, 0.24]; 1.99 [1.35, 2.51] |
| Song pattern TN1c | not resolved | not resolved |
| Wing motor | not resolved | not resolved |
| Outside sensory | not resolved | 1.26 [0.96, 1.80]; 0.88 [0.78, 1.00] |

Rates, silent fractions, median and 99th-percentile rates, drive-group changes and synchrony at every dose are retained in the analysis archive. Exact spike-time replays of wing motor, typed leg motor and descending neurons at three block levels and the strongest rescue are checked against the original full-neuron count arrays. They are visualisation inputs, not new experimental outcomes.
