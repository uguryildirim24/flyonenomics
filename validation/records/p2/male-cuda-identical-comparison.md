# Identical-input CUDA / Brian2 comparison

Signed differences are CUDA minus Brian2. Every count comparison includes all 162,517 neurons. ON is [2,7) s and OFF is [7,12) s; no stimulus changes between these windows. Both intact rest and GABA removal use clamped dopamine. Two seconds of settling precede counting, but first divergence includes settling. The reference engine, model and substrate are unchanged.

Input events are Binomial(100, 0.001) multiplicities at each 0.1 ms tick for each of 15,016 sensory targets. Both engines read the same hashed saved events; random inputs are disabled. The virtual sources in Brian2 preserve simultaneous-event multiplicity. GPU background draws are replaced, not added.

## Per-neuron counts

| Seed | Condition | Window | Exactly matching | Mean difference | Mean absolute | RMS | Signed range | Absolute p50 / p90 / p99 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 501 | control | on | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 501 | control | off | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 501 | control | measure | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 501 | off-gaba | on | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 501 | off-gaba | off | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 501 | off-gaba | measure | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 502 | control | on | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 502 | control | off | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 502 | control | measure | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 502 | off-gaba | on | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 502 | off-gaba | off | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |
| 502 | off-gaba | measure | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 | 0 / 0 / 0 |

The complete signed integer histograms, settling counts and all requested absolute quantiles are in the companion JSON. Equal window counts do not imply equal spike times; silent neurons contribute exact count matches.

## First unequal output spike

| Seed | Condition | First tick | Time from initialization, ms | Brian2-only neurons at that tick | CUDA-only neurons at that tick | Unequal neuron/tick pairs over 12 s |
|---|---|---:|---:|---|---|---:|
| 501 | control | none | none | — | — | 0 |
| 501 | off-gaba | none | none | — | — | 0 |
| 502 | control | none | none | — | — | 0 |
| 502 | off-gaba | none | none | — | — | 0 |

This is the first spike divergence at the 0.1 ms resolution, not the first floating-point state difference. Neuron IDs in this table are zero-based engine indices. All spike archives were hash checked and compared as sorted neuron/tick pairs.

## Group rates, Hz

Arithmetic means over the two seeds; full per-seed rates and group sizes are in the JSON. Columns give Brian2 / CUDA. The ten-second mean is the average of the two five-second windows.

### control

| Group | Neurons | ON Brian2 / CUDA | OFF Brian2 / CUDA | 10 s Brian2 / CUDA |
|---|---:|---:|---:|---:|
| DAN | 367 | 1.580654 / 1.580654 | 1.621526 / 1.621526 | 1.601090 / 1.601090 |
| ER | 282 | 0.601064 / 0.601064 | 0.562411 / 0.562411 | 0.581738 / 0.581738 |
| KC | 4,064 | 0.009227 / 0.009227 | 0.009006 / 0.009006 | 0.009117 / 0.009117 |
| ascending | 1,849 | 3.566522 / 3.566522 | 3.583937 / 3.583937 | 3.575230 / 3.575230 |
| central | 39,533 | 4.858647 / 4.858647 | 4.871128 / 4.871128 | 4.864888 / 4.864888 |
| descending | 1,314 | 3.907382 / 3.907382 | 3.987291 / 3.987291 | 3.947336 / 3.947336 |
| endocrine | 87 | 3.698851 / 3.698851 | 3.837931 / 3.837931 | 3.768391 / 3.768391 |
| motor | 887 | 8.327847 / 8.327847 | 8.256595 / 8.256595 | 8.292221 / 8.292221 |
| optic | 89,353 | 0.019727 / 0.019727 | 0.021117 / 0.021117 | 0.020422 / 0.020422 |
| sensory | 15,016 | 0.896237 / 0.896237 | 0.906313 / 0.906313 | 0.901275 / 0.901275 |
| visual_centrifugal | 562 | 2.782384 / 2.782384 | 3.052847 / 3.052847 | 2.917616 / 2.917616 |
| visual_projection | 9,203 | 0.059165 / 0.059165 | 0.063544 / 0.063544 | 0.061355 / 0.061355 |
| P1 | 148 | 0.089865 / 0.089865 | 0.076351 / 0.076351 | 0.083108 / 0.083108 |
| pIP10 | 2 | 3.150000 / 3.150000 | 2.450000 / 2.450000 | 2.800000 / 2.800000 |
| dPR1 | 2 | 18.800000 / 18.800000 | 18.650000 / 18.650000 | 18.725000 / 18.725000 |
| vPR6 | 8 | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.000000 / 0.000000 |
| TN1a | 22 | 2.277273 / 2.277273 | 2.072727 / 2.072727 | 2.175000 / 2.175000 |
| TN1c | 13 | 0.169231 / 0.169231 | 0.084615 / 0.084615 | 0.126923 / 0.126923 |
| wing_motor | 66 | 27.930303 / 27.930303 | 28.084848 / 28.084848 | 28.007576 / 28.007576 |
| outside_sensory | 147,501 | 1.465565 / 1.465565 | 1.471661 / 1.471661 | 1.468613 / 1.468613 |

### off-gaba

| Group | Neurons | ON Brian2 / CUDA | OFF Brian2 / CUDA | 10 s Brian2 / CUDA |
|---|---:|---:|---:|---:|
| DAN | 367 | 140.670572 / 140.670572 | 140.537330 / 140.537330 | 140.603951 / 140.603951 |
| ER | 282 | 4.487943 / 4.487943 | 3.201064 / 3.201064 | 3.844504 / 3.844504 |
| KC | 4,064 | 147.468258 / 147.468258 | 147.468036 / 147.468036 | 147.468147 / 147.468147 |
| ascending | 1,849 | 53.548837 / 53.548837 | 53.721633 / 53.721633 | 53.635235 / 53.635235 |
| central | 39,533 | 27.513763 / 27.513763 | 27.546973 / 27.546973 | 27.530368 / 27.530368 |
| descending | 1,314 | 28.870244 / 28.870244 | 28.957382 / 28.957382 | 28.913813 / 28.913813 |
| endocrine | 87 | 14.537931 / 14.537931 | 14.633333 / 14.633333 | 14.585632 / 14.585632 |
| motor | 887 | 57.235513 / 57.235513 | 57.237880 / 57.237880 | 57.236697 / 57.236697 |
| optic | 89,353 | 0.333809 / 0.333809 | 0.331809 / 0.331809 | 0.332809 / 0.332809 |
| sensory | 15,016 | 16.921870 / 16.921870 | 16.972669 / 16.972669 | 16.947270 / 16.947270 |
| visual_centrifugal | 562 | 22.200712 / 22.200712 | 22.212811 / 22.212811 | 22.206762 / 22.206762 |
| visual_projection | 9,203 | 1.097914 / 1.097914 | 1.113615 / 1.113615 | 1.105764 / 1.105764 |
| P1 | 148 | 6.313514 / 6.313514 | 6.316216 / 6.316216 | 6.314865 / 6.314865 |
| pIP10 | 2 | 83.750000 / 83.750000 | 85.050000 / 85.050000 | 84.400000 / 84.400000 |
| dPR1 | 2 | 4.800000 / 4.800000 | 2.500000 / 2.500000 | 3.650000 / 3.650000 |
| vPR6 | 8 | 0.000000 / 0.000000 | 0.000000 / 0.000000 | 0.000000 / 0.000000 |
| TN1a | 22 | 70.331818 / 70.331818 | 70.840909 / 70.840909 | 70.586364 / 70.586364 |
| TN1c | 13 | 52.200000 / 52.200000 | 52.169231 / 52.169231 | 52.184615 / 52.184615 |
| wing_motor | 66 | 168.330303 / 168.330303 | 168.383333 / 168.383333 | 168.356818 / 168.356818 |
| outside_sensory | 147,501 | 13.432397 / 13.432397 | 13.441327 / 13.441327 | 13.436862 / 13.436862 |

## Paired GABA-minus-intact count effects

Here the compared arrays are each engine's per-neuron knockout-minus-control count differences, not its absolute counts.

| Seed | Window | Exactly matching effect | Mean cross-engine difference | Mean absolute | RMS | Signed range |
|---|---|---:|---:|---:|---:|---:|
| 501 | on | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 |
| 501 | off | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 |
| 501 | measure | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 |
| 502 | on | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 |
| 502 | off | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 |
| 502 | measure | 162,517 | 0.000000 | 0.000000 | 0.000000 | 0 to 0 |

## Replay timing

Replay timing is not the standard stochastic-input benchmark: Brian2 uses one-second network runs with clamped parameters, while CUDA uses 10 ms full-spike-output chunks. Input decoding/upload and archive compression are separately timed. Neither engine draws background random numbers during replay; disabling Brian2 PoissonInput removes its runtime RNG cost. Brian2 compilation on the first network run is included in its stepping column. Do not derive an original-engine speedup from this differently instrumented harness.

| Backend | Seed | Condition | Build s | Input load s | Step and spike extraction s | Archive s | Total s |
|---|---|---|---:|---:|---:|---:|---:|
| brian | 501 | control | 38.339 | 1.871 | 47.637 | 0.823 | 88.723 |
| cuda | 501 | control | 213.174 | 17.124 | 13.612 | 3.414 | 247.540 |
| brian | 501 | off-gaba | 43.057 | 1.939 | 83.511 | 8.533 | 137.123 |
| cuda | 501 | off-gaba | 269.542 | 11.641 | 21.327 | 32.090 | 334.874 |
| brian | 502 | control | 34.907 | 1.801 | 36.726 | 0.769 | 74.266 |
| cuda | 502 | control | 185.824 | 17.156 | 12.899 | 3.176 | 219.257 |
| brian | 502 | off-gaba | 41.788 | 1.906 | 83.675 | 8.509 | 135.961 |
| cuda | 502 | off-gaba | 251.294 | 11.658 | 21.447 | 31.438 | 316.110 |

## Interpretation

All 58,655,422 saved neuron/tick pairs match in these four runs: the engines are numerically equivalent in observed spike output for these inputs. No spike divergence was observed during any 12-second run. This does not establish bitwise state equivalence or agreement in every condition.

The model receives injected input; the fly does not see. Visual input elsewhere is injected at TuBu; these runs use dark sensory-background input.

Sources: `male-cuda-identical-plan.md`, `male-cuda-identical-inputs.json`, `male-cuda-identical-comparison.json` and `male-cuda-identical-receipts.json`. Raw Brian2 outputs are under `camber-runs/cuda-identical/brian/`; CUDA outputs are under `camber-runs/cuda-identical/downloads/` with a `cuda` symlink. The receipt names the Modal archive.
