# How far apart are the Brian2 and CUDA firing-rate distributions?

Across all neurons, the average distance between matched runs is **0.0333 Hz at control** and **0.0419 Hz with GABA fully blocked**. Pooling all ten runs before comparing gives smaller distances: **0.0107 Hz** and **0.0217 Hz**. These are distances between distributions, not differences in the firing of the same individual neuron.

Outside sensory neurons, the corresponding run-level distances are **0.0356 Hz** and **0.0415 Hz**. They are **1.55 [0.69, 2.63]** and **1.11 [0.79, 2.58]** times the median distance between two Brian2 runs. Relative to CUDA's own variation, the ratios are **1.62 [0.93, 2.48]** and **1.83 [1.35, 2.59]**. The choice of reference matters, and ten runs leave substantial uncertainty.

Large populations can hide much larger local differences. Disconnecting neurons with unclear transmitter labels leaves an **18.1 Hz** average distribution distance in wing-motor neurons. The dose conditions also contain large, variable differences in small song-related populations, detailed below.

The model receives injected input; **the fly does not see**. Visual input elsewhere is injected at TuBu. The control, knockout and dose runs here use dark sensory-background drive; the courtship runs additionally inject the named populations. These are model firing measurements, not vision, song or drug responses in a living fly. No new simulations were run for this analysis.

## What the measures mean

**Wasserstein-1 distance** compares the full distribution of per-neuron firing rates, including silent neurons. Imagine sorting both lists of rates and averaging the absolute gap between corresponding positions. The result is in Hz: a smaller value means the two rate distributions lie closer together. Sorting discards neuron identity, so it cannot establish that particular cells fire alike, or that their spike timing agrees. It is also not just the difference between two population means.

Each rate uses the ten-second measurement after two seconds of settling. Courtship distributions combine the five seconds with drive and five seconds after drive; their previously reported effects retain those windows separately. All 162,517 neurons enter the whole-network calculation; 147,501 enter the outside-sensory calculation. The calculation uses the exact 0.1 Hz count spacing, without smoothing or a chosen histogram width.

**Cross-engine versus within-engine distance** asks how the engine gap compares with changing the random realisation while keeping the engine fixed. The numerator is the mean of ten matched cross-engine distances. Each denominator is the median of all 45 distinct pairs of runs within one engine. A ratio of two means that the mean cross-engine distance is twice that within-engine median. This compares a mean with a median: a few far-apart realisations can raise the ratio even when most runs are close. It is not an equivalence test.

**Pooled distance** compares the combined neuron-rate samples from all ten runs per engine. It does not average each neuron's rate first. Pooling can conceal run-to-run differences, so it is reported alongside, not substituted for, the run-level distance. The ratios use the run-level numerator, never the pooled one.

Brackets are 95% whole-run bootstrap intervals from 10,000 resamples. Each draw resamples ten matched run blocks, preserves their pairing across conditions and engines, and recomputes the numerator and within-engine medians. Neurons and the 45 dependent pair distances are not independently resampled. Repeated copies of one original run have zero distance. These are descriptive intervals without multiple-comparison adjustment, not simultaneous bounds for the whole table.

## Distances across every condition

“Matched” is the mean of the ten cross-engine distances; matching does **not** mean identical random input. Every distance below is in Hz. Conductance multipliers describe model interventions, not calibrated drug concentrations. The full-block dose and GABA-removal rows give the same numbers and are not independent evidence.

| Condition | All neurons, matched | All neurons, pooled | Outside sensory, matched | Outside sensory, pooled |
|---|---:|---:|---:|---:|
| Control | 0.03331 | 0.01066 | 0.03557 | 0.01263 |
| Acetylcholine removed | 0.00034 | 0.00008 | 0.00005 | 0.00002 |
| GABA removed | 0.04192 | 0.02175 | 0.04146 | 0.02068 |
| Glutamate removed | 0.04436 | 0.01329 | 0.05010 | 0.01483 |
| Histamine removed | 0.03564 | 0.01928 | 0.03807 | 0.02066 |
| Dopamine removed | 0.02950 | 0.01153 | 0.03185 | 0.01360 |
| Octopamine removed | 0.05408 | 0.02857 | 0.05755 | 0.03013 |
| Serotonin removed | 0.03894 | 0.01486 | 0.04195 | 0.01617 |
| Unclear-transmitter neurons disconnected | 0.06107 | 0.03275 | 0.06659 | 0.03537 |
| P1 drive, 10 Hz | 0.03109 | 0.01080 | 0.03386 | 0.01233 |
| P1 drive, 30 Hz | 0.03902 | 0.01410 | 0.04267 | 0.01508 |
| P1 drive, 60 Hz | 0.02682 | 0.00925 | 0.02924 | 0.00999 |
| pIP10 drive, 30 Hz | 0.03424 | 0.00781 | 0.03734 | 0.00813 |
| Random-population drive, 30 Hz | 0.03144 | 0.00923 | 0.03352 | 0.01102 |
| GABA blocked 10% | 0.02448 | 0.01300 | 0.02635 | 0.01347 |
| GABA blocked 25% | 0.03579 | 0.01316 | 0.03897 | 0.01344 |
| GABA blocked 50% | 0.10147 | 0.03326 | 0.10961 | 0.03734 |
| GABA blocked 75% | 0.12007 | 0.02589 | 0.12581 | 0.02437 |
| GABA blocked 90% | 0.30039 | 0.02474 | 0.28240 | 0.02693 |
| GABA blocked 100% | 0.04192 | 0.02175 | 0.04146 | 0.02068 |
| GABA conductance ×1.25 | 0.03173 | 0.01759 | 0.03357 | 0.01824 |
| GABA conductance ×1.5 | 0.01607 | 0.00659 | 0.01696 | 0.00780 |
| GABA conductance ×2 | 0.01149 | 0.00725 | 0.01234 | 0.00793 |
| GABA conductance ×3 | 0.00899 | 0.00322 | 0.00913 | 0.00353 |
| 75% GABA block + GluCl ×1.5 | 0.16735 | 0.01725 | 0.17655 | 0.01801 |
| 75% GABA block + GluCl ×2 | 0.15370 | 0.02376 | 0.16214 | 0.02435 |
| 75% GABA block + GluCl ×3 | 0.06786 | 0.00751 | 0.06710 | 0.00721 |

## The within-engine baseline

These figures use **outside-sensory neurons** throughout. Baselines are medians in Hz; ratios are dimensionless. Both engines' baselines are shown rather than choosing whichever gives a smaller ratio.

| Condition | Brian2 baseline | CUDA baseline | Ratio to Brian2 [95%] | Ratio to CUDA [95%] |
|---|---:|---:|---:|---:|
| Control | 0.02291 | 0.02194 | 1.55 [0.69, 2.63] | 1.62 [0.93, 2.48] |
| Acetylcholine removed | 0.00005 | 0.00005 | 0.97 [0.83, 1.24] | 0.95 [0.82, 1.28] |
| GABA removed | 0.03729 | 0.02260 | 1.11 [0.79, 2.58] | 1.83 [1.35, 2.59] |
| Glutamate removed | 0.04549 | 0.03375 | 1.10 [0.73, 3.15] | 1.48 [1.00, 2.59] |
| Histamine removed | 0.02006 | 0.02737 | 1.90 [1.11, 4.41] | 1.39 [0.86, 2.45] |
| Dopamine removed | 0.03339 | 0.01968 | 0.95 [0.71, 1.53] | 1.62 [0.87, 2.75] |
| Octopamine removed | 0.05295 | 0.04277 | 1.09 [0.85, 2.73] | 1.35 [0.82, 2.41] |
| Serotonin removed | 0.02286 | 0.02391 | 1.84 [0.64, 5.32] | 1.75 [0.76, 5.09] |
| Unclear-transmitter neurons disconnected | 0.05562 | 0.03385 | 1.20 [0.91, 2.12] | 1.97 [0.93, 4.25] |
| P1 drive, 10 Hz | 0.02724 | 0.02205 | 1.24 [0.83, 2.71] | 1.54 [1.00, 4.31] |
| P1 drive, 30 Hz | 0.02231 | 0.03382 | 1.91 [1.01, 2.84] | 1.26 [0.59, 3.70] |
| P1 drive, 60 Hz | 0.01895 | 0.01691 | 1.54 [0.78, 2.67] | 1.73 [0.89, 3.40] |
| pIP10 drive, 30 Hz | 0.02249 | 0.02290 | 1.66 [0.91, 3.03] | 1.63 [0.94, 3.66] |
| Random-population drive, 30 Hz | 0.01604 | 0.02218 | 2.09 [1.11, 3.32] | 1.51 [0.87, 3.90] |
| GABA blocked 10% | 0.01735 | 0.01686 | 1.52 [0.75, 3.15] | 1.56 [0.81, 2.71] |
| GABA blocked 25% | 0.02453 | 0.03069 | 1.59 [0.79, 2.93] | 1.27 [0.63, 4.78] |
| GABA blocked 50% | 0.08687 | 0.06775 | 1.26 [0.74, 3.28] | 1.62 [0.72, 5.99] |
| GABA blocked 75% | 0.10926 | 0.10141 | 1.15 [0.84, 2.61] | 1.24 [0.72, 2.61] |
| GABA blocked 90% | 0.23302 | 0.28796 | 1.21 [0.47, 7.10] | 0.98 [0.57, 2.37] |
| GABA blocked 100% | 0.03729 | 0.02260 | 1.11 [0.79, 2.58] | 1.83 [1.35, 2.59] |
| GABA conductance ×1.25 | 0.03101 | 0.01995 | 1.08 [0.73, 3.34] | 1.68 [0.99, 2.87] |
| GABA conductance ×1.5 | 0.00567 | 0.01430 | 2.99 [0.93, 3.64] | 1.19 [0.88, 1.86] |
| GABA conductance ×2 | 0.01950 | 0.00732 | 0.63 [0.49, 2.23] | 1.69 [0.70, 2.65] |
| GABA conductance ×3 | 0.01153 | 0.00457 | 0.79 [0.57, 1.87] | 2.00 [1.06, 3.36] |
| 75% GABA block + GluCl ×1.5 | 0.13346 | 0.13046 | 1.32 [0.83, 2.65] | 1.35 [0.65, 3.19] |
| 75% GABA block + GluCl ×2 | 0.08334 | 0.11605 | 1.95 [1.02, 3.59] | 1.40 [0.78, 2.71] |
| 75% GABA block + GluCl ×3 | 0.06709 | 0.06071 | 1.00 [0.49, 1.72] | 1.11 [0.54, 1.90] |

For all neurons rather than outside sensory, the control baselines are 0.02125 Hz in Brian2 and 0.02097 Hz in CUDA; the ratios are 1.57 [0.71, 2.62] and 1.59 [0.95, 2.37]. Under full GABA block, the baselines are 0.03420 and 0.02486 Hz, with ratios 1.23 [0.76, 2.33] and 1.69 [1.27, 2.96].

The largest whole-network matched distance occurs at **90% GABA block**, not full block. Its outside-sensory distance is 0.2824 Hz, alongside within-engine medians of 0.2330 and 0.2880 Hz. Conversely, strengthening GABA by half gives the largest outside-sensory ratio to Brian2, **2.99**, despite a distance of only **0.0170 Hz**: its reference median is just 0.00567 Hz. Absolute distances and ratios answer different questions.

Comparing engines with within-engine variation follows the approach used by [van Albada and colleagues (2018)](https://doi.org/10.3389/fnins.2018.00291) and [Knight and Nowotny (2018)](https://doi.org/10.3389/fnins.2018.00941). Their cortical-network divergence comparisons motivate the baseline, not a universal numerical cutoff for this fly model's Wasserstein mean-to-median ratio. The accompanying research survey's proposed numerical margin is not substantiated there by a passage from either paper; it is not treated as a published equivalence rule here.

## Looking inside the average

The twelve background-drive groups show different scales. Below, distance is the matched-run mean in Hz and the ratio uses the Brian2 within-group median. Full intervals and both engines' baselines for every group and condition are in the data record.

| Group | Control distance | Control ratio | Full GABA block distance | Full GABA block ratio |
|---|---:|---:|---:|---:|
| Dopamine neurons | 0.23572 | 1.03 | 0.28011 | 1.34 |
| Ring neurons | 0.14560 | 1.27 | 0.43312 | 1.27 |
| Kenyon cells | 0.00164 | 1.96 | 0.05066 | 0.97 |
| Ascending | 0.19150 | 1.21 | 0.38124 | 0.99 |
| Central | 0.09280 | 1.23 | 0.12980 | 1.15 |
| Descending | 0.34623 | 1.62 | 0.30683 | 0.94 |
| Endocrine | 0.63092 | 0.98 | 0.32425 | 1.25 |
| Motor | 0.72567 | 2.21 | 0.74811 | 1.73 |
| Optic | 0.00646 | 2.54 | 0.00326 | 1.04 |
| Sensory | 0.03340 | 0.85 | 0.09221 | 1.02 |
| Visual centrifugal | 0.46060 | 1.62 | 0.26532 | 0.86 |
| Visual projection | 0.00739 | 1.99 | 0.01863 | 0.99 |

Several local results deserve attention:

- **Unclear-transmitter disconnection, wing motor:** matched distance 18.09 Hz, pooled distance 17.73 Hz. Within-engine medians are 4.23 Hz in Brian2 and 0.55 Hz in CUDA, giving ratios 4.28 [0.33, 19.59] and 32.81 [12.16, 65.26]. The within-Brian2 *mean* is 14.85 Hz, much higher than its median. The broad, uneven variation must not be hidden behind the whole-network average.
- **75% GABA block with GluCl ×1.5, dPR1:** matched distance 107.57 Hz but pooled distance 9.00 Hz. The Brian2 median is 34.8 Hz; its mean is 92.41 Hz. The ratio estimate is 3.09, but 42% of bootstrap draws have a zero Brian2 median, so a finite unconditional interval is not reported.
- **75% GABA block with GluCl ×2, TN1a:** matched distance 25.04 Hz, pooled distance 6.04 Hz, Brian2 median 1.34 Hz and mean 17.12 Hz. The median-based ratio is 18.67 [0.67, 43.86]. Again, a high ratio does not describe every pair of runs.
- **Histamine removal, Kenyon cells:** distance 0.00180 Hz, only a small absolute displacement, but 3.67 [2.11, 6.87] times the Brian2 median. Relative to CUDA it is 0.77 [0.58, 2.15]. A large ratio alone does not imply a large firing-rate difference.
- **Dopamine removal, dPR1:** matched distance 6.01 Hz and pooled distance 3.13 Hz, against a Brian2 median of 7.10 Hz. The ratio is 0.85 [0.52, 2.10]. This does not erase the differing perturbation effects below.

Exactly silent or sparsely firing groups can have zero within-engine medians. Their ratios are undefined, not zero or evidence of agreement. If any bootstrap draw has a zero denominator, the record retains the count of such draws and separately labels any finite-draw interval as conditional; it does not silently discard them.

## Do the perturbation effects differ relative to their own spread?

This is a different calculation from the distribution distance. First subtract each engine's own matched control. Then subtract the Brian2 mean effect from the CUDA mean effect. Divide that signed difference by the standard deviation of the ten Brian2 effects. This pools all within-Brian2 pairs: the square root of half their mean squared effect difference equals that standard deviation. It is **not** a standard error, and CUDA's spread is not included in the denominator.

Negative values mean CUDA's effect is more negative or less positive. Courtship rows below use the five-second drive window; the two drive-to-drive contrasts replace the control subtraction. All 428 previously reported paired effects, including the other groups, after-drive windows, distribution summaries and synchrony, were reconstructed from the saved outcomes and matched to the original analysis.

| Condition / contrast | Readout | CUDA − Brian2 effect, Hz | Brian2 effect SD, Hz | Difference / SD [95%] |
|---|---|---:|---:|---:|
| Acetylcholine removed | Outside sensory | −0.0047 | 0.0227 | −0.21 [−5.39, 0.66] |
| GABA removed | Outside sensory | +0.0141 | 0.0420 | 0.33 [−0.51, 1.23] |
| Glutamate removed | Outside sensory | −0.0192 | 0.0335 | −0.57 [−1.49, 0.19] |
| Histamine removed | Outside sensory | −0.0032 | 0.0130 | −0.25 [−1.63, 0.71] |
| Dopamine removed | Outside sensory | −0.0014 | 0.0364 | −0.04 [−0.68, 0.83] |
| Octopamine removed | Outside sensory | +0.0253 | 0.0315 | 0.80 [−0.06, 1.72] |
| Serotonin removed | Outside sensory | −0.0079 | 0.0234 | −0.34 [−1.29, 0.56] |
| Unclear-transmitter neurons disconnected | Outside sensory | −0.0399 | 0.0506 | −0.79 [−2.17, 0.09] |
| P1 drive, 10 Hz | dPR1 | −2.7000 | 5.7182 | −0.47 [−1.10, 0.30] |
| P1 drive, 30 Hz | dPR1 | −3.2400 | 5.3889 | −0.60 [−1.46, 0.07] |
| P1 drive, 60 Hz | dPR1 | −2.5000 | 5.3083 | −0.47 [−1.36, 0.38] |
| pIP10 drive, 30 Hz | dPR1 | −2.0000 | 5.4615 | −0.37 [−1.13, 0.47] |
| Random-population drive, 30 Hz | dPR1 | −3.2800 | 3.9828 | −0.82 [−1.94, −0.30] |
| P1 30 Hz minus random drive | dPR1 | +0.0400 | 3.4158 | 0.01 [−0.89, 1.10] |
| P1 60 Hz minus P1 10 Hz | dPR1 | +0.2000 | 3.7513 | 0.05 [−0.64, 1.62] |
| Dopamine removed | dPR1 | −4.1850 | 7.8427 | −0.53 [−2.36, 0.48] |
| Unclear-transmitter neurons disconnected | Wing motor | −18.5526 | 15.0257 | −1.23 [−8.08, −0.60] |
| P1 drive, 30 Hz | Motor | +0.4562 | 0.0769 | 5.93 [−0.30, 20.30] |

The largest absolute standardised point estimate among these effects is the motor response to the middle P1 drive: 5.93 Brian2 standard deviations. Its broad interval includes zero: **no detected difference**, not equality. The wing-motor effect after unclear-transmitter disconnection is −4.79 Hz in Brian2 versus −23.35 Hz in CUDA; its cross-engine interval does not include zero. The dopamine-removal dPR1 effect changes from −4.15 to −8.33 Hz, but its cross-engine interval includes zero. Normalising these gaps describes their scale; it does not explain their cause.

## What this adds

The [identical-input comparison](cuda-methods.md) established tick-level spike identity only for the tested saved inputs with clamped dopamine. The [dose replication](gaba-dose-gpu.md) showed that the main block response and rescue pattern carry over, while some boost fits remain less stable. This analysis adds the *shape* of the free-running rate distributions and a measured within-engine reference for their differences. Small global distances coexist with substantial local gaps and uneven run-to-run variation. Counts cannot establish temporal firing regularity or pairwise spike correlations, and these comparisons cannot separate random-input differences from numerical trajectory sensitivity. They strengthen the description of what reproduces without establishing universal engine equivalence or biological validity.

### Reproducibility

[Calculation script](../scripts/cuda_agreement.py) · [Complete numeric record and input archive hashes](../validation/records/p2/male-cuda-agreement.json)

The record holds the input directories, matching identifiers, all individual distances and within-engine pairs, bootstrap specification, group bindings, signed effect differences and zero-denominator cases. The script reads the original archives in place and records checksums for all 540 count archives and their 540 receipts. This is a retrospective descriptive analysis, not a newly frozen outcome experiment.
