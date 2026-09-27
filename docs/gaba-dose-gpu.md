# Does the GABA dose curve carry over to the GPU engine?

**The main response does.** Reducing the model's GABA brake produces a steep late rise in firing; strengthening it produces a much smaller fall. Reinforcing the glutamate brake removes about three quarters of the partially blocked excess. The block slope, observed half-response point and all three rescue fractions have overlapping intervals between Brian2 and the GPU engine. This is not a claim that the engines are equivalent.

One result is less stable: the GPU **boost** curve does not identify a fitted half-effect within the tested range, although the individual rate changes overlap the Brian2 estimates. Some regional fits and small synchrony detections also differ.

These are simulated firing rates, not drug treatment, seizures or behaviour in a living fly. The model receives injected input; **the fly does not see**. Visual input elsewhere in the project is injected at TuBu; these runs use dark sensory-background drive.

[Overlaid dose curves](../figures/3d/gaba-dose-gpu/curves.svg) · [Brian2 study](gaba-dose-results.md)

## What was compared

The design and analysis were fixed before the GPU outcomes. The engines used the same design with ten runs per condition, but drew different random streams. Each condition settled for two seconds and was measured for ten seconds. Each engine's effects were paired against its **own** control, not the other engine's baseline. Control firing outside sensory neurons was 1.438 Hz in Brian2 and 1.443 Hz on the GPU.

θ is the fraction of GABA conductance blocked. φ is extra GABA conductance, so φ = 2 means three times baseline conductance. The rescue fixes θ at 0.75 and adds glutamate-class conductance ψ in the same way. These are uniform class-level changes, not measured receptor locations. The block axis retains the earlier study's nominal brain-equivalent picrotoxin translation; boost and rescue are **not calibrated drug concentrations**.

Brackets below are 95% whole-run bootstrap intervals: paired resampling for rate, synchrony and rescue effects, and joint resampling across all doses for curve fits. An interval containing zero means **no detected difference**, not equality. Outside-sensory firing is the main rate readout. Δb and ΔF are changes from each engine's control: b is the largest population spike count in a one-millisecond bin divided by the number of neurons; F (the Fano factor) is the variance of those population-bin counts divided by their mean. Ten-millisecond GPU chunks retain every one-millisecond bin.

Two half-points must be kept separate. The **observed-endpoint half** interpolates half of the change at the strongest measured dose. The **fitted half-effect** belongs to a Hill curve with a freely estimated limiting response. Entries marked **†** come from a fit whose half-effect interval leaves the tested range; its slope is conditional, and its half-effect is **not an identified EC50**. Regional “not resolved” entries retain the original analysis's fit limitations, not a claim of no response.

## Side by side

| Measure / setting | Brian2 | GPU |
|---|---:|---:|
| Rate change, Hz · Block θ = 0.10 | 0.093 [0.075, 0.107] | 0.102 [0.094, 0.109] |
| Rate change, Hz · Block θ = 0.25 | 0.295 [0.276, 0.318] | 0.302 [0.289, 0.319] |
| Rate change, Hz · Block θ = 0.50 | 0.972 [0.917, 1.022] | 1.003 [0.947, 1.051] |
| Rate change, Hz · Block θ = 0.75 | 4.591 [4.536, 4.652] | 4.586 [4.543, 4.628] |
| Rate change, Hz · Block θ = 0.90 | 9.591 [9.407, 9.753] | 9.613 [9.474, 9.751] |
| Rate change, Hz · Block θ = 1.00 | 12.588 [12.563, 12.613] | 12.603 [12.574, 12.623] |
| Rate change, Hz · Boost φ = 0.25 | -0.260 [-0.281, -0.238] | -0.279 [-0.312, -0.256] |
| Rate change, Hz · Boost φ = 0.50 | -0.442 [-0.456, -0.432] | -0.454 [-0.482, -0.437] |
| Rate change, Hz · Boost φ = 1.00 | -0.611 [-0.625, -0.598] | -0.608 [-0.636, -0.591] |
| Rate change, Hz · Boost φ = 2.00 | -0.835 [-0.847, -0.823] | -0.841 [-0.868, -0.826] |
| Rate change, Hz · Rescue ψ = 0.50 (θ = 0.75) | 3.510 [3.429, 3.602] | 3.503 [3.431, 3.593] |
| Rate change, Hz · Rescue ψ = 1.00 (θ = 0.75) | 2.502 [2.455, 2.554] | 2.516 [2.456, 2.590] |
| Rate change, Hz · Rescue ψ = 2.00 (θ = 0.75) | 1.147 [1.103, 1.205] | 1.146 [1.100, 1.195] |
| Block Hill slope | 5.048 [4.757, 5.338] † | 4.994 [4.646, 5.434] † |
| Block fitted half-effect, θ | 0.999 [0.961, 1.054] † | 1.006 [0.952, 1.074] † |
| Block half of observed endpoint, θ | 0.801 [0.799, 0.803] | 0.801 [0.800, 0.803] |
| Boost Hill slope | 0.880 [0.780, 0.997] | 0.741 [0.642, 0.839] † |
| Boost fitted half-effect, φ | 1.261 [0.963, 1.796] | 2.209 [1.499, 4.285] † |
| Boost half of observed endpoint, φ | 0.466 [0.454, 0.474] | 0.453 [0.431, 0.466] |
| Excess firing removed, % · ψ = 0.50 | 23.5 [20.9, 26.0] | 23.6 [21.8, 25.2] |
| Excess firing removed, % · ψ = 1.00 | 45.5 [44.7, 46.5] | 45.1 [43.8, 46.2] |
| Excess firing removed, % · ψ = 2.00 | 75.0 [73.7, 76.1] | 75.0 [74.0, 75.9] |
| Δb · Block θ = 0.10 | 0.00005 [-0.00010, 0.00015] | 0.00017 [0.00009, 0.00025] |
| ΔF · Block θ = 0.10 | -0.101 [-0.210, -0.012] | -0.144 [-0.290, -0.020] |
| Δb · Block θ = 0.25 | 0.00025 [0.00013, 0.00036] | 0.00029 [0.00025, 0.00033] |
| ΔF · Block θ = 0.25 | -0.225 [-0.363, -0.108] | -0.300 [-0.408, -0.196] |
| Δb · Block θ = 0.50 | 0.00120 [0.00108, 0.00130] | 0.00127 [0.00116, 0.00139] |
| ΔF · Block θ = 0.50 | -0.196 [-0.451, 0.074] | -0.375 [-0.631, -0.092] |
| Δb · Block θ = 0.75 | 0.00550 [0.00536, 0.00564] | 0.00549 [0.00542, 0.00556] |
| ΔF · Block θ = 0.75 | 0.881 [0.734, 0.999] | 0.884 [0.645, 1.097] |
| Δb · Block θ = 0.90 | 0.01045 [0.01026, 0.01065] | 0.01060 [0.01044, 0.01075] |
| ΔF · Block θ = 0.90 | -0.164 [-0.468, 0.210] | -0.219 [-0.518, 0.044] |
| Δb · Block θ = 1.00 | 0.01372 [0.01357, 0.01385] | 0.01376 [0.01362, 0.01389] |
| ΔF · Block θ = 1.00 | -1.013 [-1.154, -0.911] | -1.092 [-1.295, -0.932] |
| Δb · Boost φ = 0.25 | -0.00045 [-0.00059, -0.00034] | -0.00036 [-0.00045, -0.00028] |
| ΔF · Boost φ = 0.25 | -0.051 [-0.224, 0.093] | -0.122 [-0.311, 0.032] |
| Δb · Boost φ = 0.50 | -0.00068 [-0.00083, -0.00058] | -0.00064 [-0.00073, -0.00056] |
| ΔF · Boost φ = 0.50 | -0.039 [-0.181, 0.075] | -0.074 [-0.277, 0.091] |
| Δb · Boost φ = 1.00 | -0.00085 [-0.00099, -0.00076] | -0.00083 [-0.00092, -0.00075] |
| ΔF · Boost φ = 1.00 | -0.373 [-0.511, -0.269] | -0.474 [-0.681, -0.310] |
| Δb · Boost φ = 2.00 | -0.00114 [-0.00127, -0.00105] | -0.00109 [-0.00118, -0.00102] |
| ΔF · Boost φ = 2.00 | -0.976 [-1.125, -0.863] | -1.031 [-1.227, -0.877] |
| Δb · Rescue ψ = 0.50 (θ = 0.75) | 0.00443 [0.00426, 0.00457] | 0.00448 [0.00439, 0.00458] |
| ΔF · Rescue ψ = 0.50 (θ = 0.75) | 1.198 [1.004, 1.368] | 1.285 [1.066, 1.517] |
| Δb · Rescue ψ = 1.00 (θ = 0.75) | 0.00354 [0.00340, 0.00366] | 0.00363 [0.00355, 0.00371] |
| ΔF · Rescue ψ = 1.00 (θ = 0.75) | 3.471 [3.142, 3.779] | 3.629 [3.139, 4.076] |
| Δb · Rescue ψ = 2.00 (θ = 0.75) | 0.00201 [0.00181, 0.00218] | 0.00198 [0.00188, 0.00208] |
| ΔF · Rescue ψ = 2.00 (θ = 0.75) | 1.371 [1.239, 1.493] | 1.330 [1.067, 1.539] |
| Dopamine neurons · half of observed full-block change, θ | 0.7367 [0.7364, 0.7371] | 0.7372 [0.7368, 0.7377] |
| Ring neurons · half of observed full-block change, θ | 0.9464 [0.9452, 0.9477] | 0.9457 [0.9444, 0.9469] |
| Kenyon cells · half of observed full-block change, θ | 0.7601 [0.7600, 0.7602] | 0.7601 [0.7601, 0.7602] |
| Ascending · half of observed full-block change, θ | 0.8897 [0.8776, 0.9026] | 0.8902 [0.8782, 0.9018] |
| Central · half of observed full-block change, θ | 0.8287 [0.8245, 0.8337] | 0.8283 [0.8245, 0.8322] |
| Descending · half of observed full-block change, θ | 0.8246 [0.8215, 0.8276] | 0.8261 [0.8225, 0.8298] |
| Endocrine · half of observed full-block change, θ | 0.5892 [0.5481, 0.6351] | 0.5955 [0.5705, 0.6205] |
| Motor · half of observed full-block change, θ | 0.8367 [0.8317, 0.8421] | 0.8376 [0.8340, 0.8413] |
| Optic · half of observed full-block change, θ | 0.7455 [0.7385, 0.7514] | 0.7445 [0.7389, 0.7492] |
| Sensory · half of observed full-block change, θ | 0.8228 [0.8176, 0.8286] | 0.8228 [0.8173, 0.8286] |
| Visual centrifugal · half of observed full-block change, θ | 0.7840 [0.7813, 0.7868] | 0.7855 [0.7818, 0.7902] |
| Visual projection · half of observed full-block change, θ | 0.8867 [0.8755, 0.9000] | 0.8865 [0.8738, 0.9005] |
| Courtship P1 · half of observed full-block change, θ | 0.6497 [0.6215, 0.6759] | 0.6378 [0.6138, 0.6642] |
| Descending song command · half of observed full-block change, θ | 0.9481 [0.9461, 0.9497] | 0.9501 [0.9487, 0.9512] |
| Song pattern dPR1 · half of observed full-block change, θ | 0.8733 [0.8249, 0.8859] | 0.8716 [0.8327, 0.8825] |
| Song pattern vPR6 · half of observed full-block change, θ | not resolved | not resolved |
| Song pattern TN1a · half of observed full-block change, θ | 0.4331 [0.3813, 0.9513] | 0.3994 [0.3717, 0.4653] |
| Song pattern TN1c · half of observed full-block change, θ | 0.8661 [0.8640, 0.8681] | 0.8643 [0.8620, 0.8671] |
| Wing motor · half of observed full-block change, θ | 0.8474 [0.8362, 0.8564] | 0.8455 [0.8378, 0.8522] |
| Dopamine neurons · fitted half-effects | θ: not resolved; φ: 0.2492 [0.2331, 0.2686] | θ: not resolved; φ: 0.2656 [0.2276, 0.3004] |
| Ring neurons · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Kenyon cells · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Ascending · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Central · fitted half-effects | θ: not resolved; φ: 1.3626 [1.0987, 1.7718] | θ: not resolved; φ: not resolved |
| Descending · fitted half-effects | θ: not resolved; φ: 0.4217 [0.4025, 0.4431] | θ: not resolved; φ: 0.3580 [0.2990, 0.4020] |
| Endocrine · fitted half-effects | θ: 0.6446 [0.5914, 0.7583]; φ: 0.3168 [0.2979, 0.3418] | θ: 0.6260 [0.5901, 0.7009]; φ: 0.2963 [0.2760, 0.3204] |
| Motor · fitted half-effects | θ: not resolved; φ: 0.3905 [0.3190, 1.6712] | θ: not resolved; φ: 0.3335 [0.2771, 0.6651] |
| Optic · fitted half-effects | θ: 0.8700 [0.8492, 0.8950]; φ: 0.0923 [0.0344, 0.1415] | θ: 0.8567 [0.8392, 0.8745]; φ: 0.1275 [0.0681, 0.1819] |
| Sensory · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Visual centrifugal · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Visual projection · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Courtship P1 · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Descending song command · fitted half-effects | θ: not resolved; φ: 0.1785 [0.1020, 0.2597] | θ: not resolved; φ: 0.1752 [0.1414, 0.2122] |
| Song pattern dPR1 · fitted half-effects | θ: not resolved; φ: 0.2198 [0.1421, 0.2886] | θ: not resolved; φ: 0.2089 [0.1819, 0.2289] |
| Song pattern vPR6 · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Song pattern TN1a · fitted half-effects | θ: not resolved; φ: 0.1767 [0.1076, 0.2398] | θ: not resolved; φ: 0.1681 [0.1414, 0.1880] |
| Song pattern TN1c · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |
| Wing motor · fitted half-effects | θ: not resolved; φ: not resolved | θ: not resolved; φ: not resolved |

## The five expectations on the GPU

1. **Block raises firing monotonically to GABA-off — matching.** The outside-sensory change rises from +0.102 [0.094, 0.109] Hz at 10% block to +12.603 [12.574, 12.623] Hz at full block. The full-block count arrays match the earlier GPU GABA-off outcomes for every measured neuron in every run.
2. **Half-effect below 50% block, with an amplified slope — opposite for the half-point; matching for steepness, with the Hill EC50 unresolved.** Half the observed endpoint change occurs at **80.12% [79.95%, 80.30%]** block on the GPU, versus **80.11% [79.90%, 80.33%]** in Brian2. Conditional block slopes are **4.99 [4.65, 5.43]** and **5.05 [4.76, 5.34]**, respectively. Both fitted half-effect intervals extend beyond complete block, so neither engine identifies that asymptotic half-effect.
3. **A single sharp synchrony transition, central brain first — unclear for a discontinuity; opposite for the region order.** GPU b grows strongly between 50% and 75% block, but F falls at 50%, rises at 75%, has no detected difference at 90%, and falls at full block. The sampled doses do not locate a single discontinuity. Optic neurons reach half their observed endpoint change at **74.45% [73.89%, 74.92%]** block, before central neurons at **82.83% [82.45%, 83.22%]**; Brian2 gives the same order. This is a normalised within-region comparison, not a comparison of absolute firing amplitudes.
4. **Boost lowers firing more shallowly than block raises it — matching for the measured response; unclear for a shared fitted potency.** The four GPU rate changes decrease monotonically from −0.279 to −0.841 Hz, and every dose interval overlaps its Brian2 counterpart. However, the GPU fitted half-effect is **φ = 2.21 [1.50, 4.29]**, beyond the largest tested φ of 2, versus the identified Brian2 value **1.26 [0.96, 1.80]**. The GPU conditional slope is **0.74 [0.64, 0.84]**, versus **0.88 [0.78, 1.00]**. Those parameter intervals overlap, but an overlap does not resolve the GPU fit. The descending-neuron boost half-point intervals narrowly do not overlap; the table retains their precision rather than rounding that difference away.
5. **GluCl reinforcement gives a partial rescue — matching.** Increasing ψ removes **23.6% [21.8%, 25.2%]**, **45.1% [43.8%, 46.2%]** and **75.0% [74.0%, 75.9%]** of the GPU blocked excess. Brian2 gives **23.5% [20.9%, 26.0%]**, **45.5% [44.7%, 46.5%]** and **75.0% [73.7%, 76.1%]**. Each pair of intervals overlaps. The strongest GPU rescue still leaves **+1.146 [1.100, 1.195] Hz** above control, so it is not a full return to baseline.

## What the replication adds

A second implementation reproduces the large block response, regional ordering and rescue pattern without changing model parameters. That makes these findings less dependent on the Brian2 implementation alone. It does not validate the assumed receptor map, turn conductance multipliers into real drug doses, establish spike-train equivalence or show what a living fly would do. Different random streams and different within-engine noise pairing remain relevant: for example, the small b increase at 10% block and F decrease at 50% block are detected on the GPU, while the Brian2 intervals contain zero. Close rate curves can also leave fitted parameters poorly constrained, as the boost result shows.

The reference checks and all GPU outcomes cost **$1.48 metered**, below the $5 allocation. All cloud apps were stopped.

### Reproducibility

[Committed design and commands](../validation/records/p2/male-cuda-dose-plan.md) · [Full comparison and archive bindings](../validation/records/p2/male-cuda-dose-comparison.json) · [Metered cost](../validation/records/p2/male-cuda-dose-cost.json) · [Submission receipts](../validation/records/p2/male-cuda-dose-receipts.json)
