Verdict: inconclusive

Reading (review r11, SPEC section 11 item 68): `inconclusive` stays as the measured word against the brief's two strict definitions. For the decision item 65 asked, whether Phase 2 moves the encoder's injection site or pursues the resting substrate, item 68 reads the answer as substrate. No photoreceptor or lamina condition carries a signal past the medulla relay. The connectome makes that relay inhibitory under the section 3.1 sign rule: L1 is predicted glutamatergic or GABAergic, and nearly all L1 synapses onto Mi1 and Tm3 carry a negative `Excitatory` sign. The counts are under "Engine gap" below.

A stripe at the photoreceptors or the lamina does not propagate through the optic lobe. Mi1 and Tm3 stay at 0.0 Hz on every corrected 300 Hz stripe. LAL and steering stay at 0.0 Hz on those stripes; visual projection stays at or below 0.002173103191357258 Hz. The same medulla silence holds on the superseded full-field photoreceptor arms. Direct L1+L2 full-field drive at about 128 Hz still leaves Tm3 at 0.0 Hz and Mi1 below 0.03 Hz, but that arm fires `steering_L` at 1.5 to 2.75 Hz. The LAL 500 Hz control fires the descending neurons. The measurements therefore do not match encoder placement (the optic-lobe path is silent) and do not match substrate (lamina full-field fires steering without a medulla relay). The azimuth axis error does not change this split.

This document takes every number from a file under `runs/diagnostics/visual-path/`, except the wall times and the review r11 connectome counts under "Engine gap", whose sources are named where they appear. The azimuth assignment is a monotone rank, not a measured receptive field.

## Run directories

| Id | Role | Commit | Conditions | Wall time |
|---|---|---|---:|---:|
| `20260914T150502Z` | Record: corrected 300 Hz stripes | `a9270671965274987c759c50a4cb1ddfb1110619` | 18 | 572.37 s |
| `20260914T124802Z` | Superseded 111-condition grid (wrong AP axis) | `6b69505d2e226dc0df53b70d4963c5a8099ff988` | 111 | 3496.20 s |
| `20260914T124629Z` | Smoke (one site, 0.5 s settle + 0.5 s record) | `6b69505d2e226dc0df53b70d4963c5a8099ff988` | 1 | 42.01 s |

Wall times are the `real` lines of the lane's run logs (`.reports/wp10-stripes300.log`, `.reports/wp10-grid.log`, `.reports/wp10-smoke.log` in the w10 worktree, git-ignored), not a run-directory file.

The record run is `20260914T150502Z`. That directory holds `propagation.csv`, `determinism.json`, `ap_axis.json`, `multiplier.json`, `manifest.json`, and `overlay_counts.json`. See `20260914T124802Z/SUPERSEDED.md` for the axis error and the replacement id.

This lane ran the reduced 18-condition stripe rerun, not a second 111-condition grid. The first grid took 3496.20 s. A full corrected rerun would take about one more hour. The 50 Hz and 150 Hz stripe rows and every full-field row come from `20260914T124802Z` with the old y-axis rank. Full-field arms do not use azimuth. The first grid already showed Tm3 at 0.0 Hz and Mi1 below 0.03 Hz on every photoreceptor and lamina site.

Connectome v783. `lif.g_inh` 1. `background: false`. Layers A and C on. Frozen dopamine record. Master seed 20260912. Seeds 1, 2, 3. Settle 0.5 s. Record 2.0 s. Params hash `884156a4642f66f6ae038ae627ee27a4f60e8c6f3772e3cb7f1f0730dd644fce` (`manifest.json` in both grids). Frozen data files were byte-identical after each run (`frozen_unchanged: true`).

## Axis and units

`20260914T150502Z/ap_axis.json`:

- Units: x and y are 4 nm voxels; z is the 40 nm section index.
- Anterior-posterior axis is z. `anterior_is: smaller z`. Small z is front (0 degrees azimuth). Large z is back.
- Dorsoventral axis is y. `ventral_is: larger y`. Elevation is the y rank per eye. `elevation_used_for_rates: false`.
- Left-right axis is x. `right_is: larger x`.
- Landmarks: ALPN mean z 1215.32700729927 sections (n=685). Kenyon_Cell mean z 4814.081514390574 sections (n=5177). ALPN is anterior of Kenyon cells. `passed: true`.
- R1-6: n=8452. `R1_6_soma_missing: 8451`. `pos_*` is the lamina terminal. That location is retinotopic. The diagnostic uses it.
- Note in the file: "Monotone approximation from location rank, not a measured receptive field."

`20260914T124802Z/ap_axis.json` set `anterior_is: larger y` and labelled the coordinates nanometres. That file is wrong. Do not use it.

## Multiplier

`20260914T124802Z/multiplier.json`: multiplier 1.0. Measured R1-6 rate 128.2636157337368 Hz on the 300 Hz full-field scan. The engine has no public extended-input weight setter. `input.f_poi` is locked. The multiplier scales Poisson rates only.

`20260914T150502Z/multiplier.json`: multiplier 1.0. The stripe rerun skipped the scan and reused 1.0.

## Core contrast

Lamina cells fire from photoreceptor Poisson drive, but the medulla relay does not. Direct lamina injection at the same photoreceptor-achieved rate still leaves Tm3 at 0.0 Hz and Mi1 below 0.03 Hz.

| Condition | Run | File | R1_6 Hz | L1 Hz | Mi1 Hz | Tm3 Hz | VP Hz | steering_L − steering_R Hz |
|---|---|---|---:|---:|---:|---:|---:|---:|
| R1_6 full-field 300 Hz seed 1 | `20260914T124802Z` | `propagation.csv` row `R1_6_azfull_rate300_seed1` | 128.2636157337368 | 10.472450918302723 | 0.021835443037974685 | 0.0 | 0.0 | 0.0 |
| L1+L2 full-field 300 Hz seed 1 | `20260914T124802Z` | `propagation.csv` row `L1-L2_azfull_rate300_seed1` | 0.0 | 128.3495883470551 | 0.025632911392405068 | 0.0 | 0.024649199056252326 | 2.75 |

Photoreceptor drive at 300 Hz full-field reaches L1 at 10.472450918302723 Hz. Direct L1+L2 injection at 300 Hz reaches L1 at 128.3495883470551 Hz. Both leave Tm3 at 0.0 Hz. Mi1 stays below 0.03 Hz. Visual projection stays below 0.5 Hz. The 0.5 Hz silent-stage threshold therefore still classifies the medulla as silent.

## Propagation

Rates are mean Hz per neuron in the 2 s record window. `first_silent_stage` is the first stage in anatomical order whose mean stays below 0.5 Hz. A non-photoreceptor site therefore often reports `photoreceptors` even when later stages fire.

Corrected 300 Hz stripes (`20260914T150502Z/propagation.csv`). Every seed. Steering difference 0.0 Hz. Mi1 0.0 Hz. Tm3 0.0 Hz.

| Id | R1_6 | R7 | R8 | L1 | L2 | Mi1 | Tm3 | VP | steering diff | first silent |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| R1_6_az-45_rate300_seed1 | 27.15040342914775 | 0.0 | 0.0 | 1.6833438885370486 | 1.3233590733590732 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6_az-45_rate300_seed2 | 27.11119515885023 | 0.0 | 0.0 | 1.6763774540848637 | 1.3297940797940797 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6_az-45_rate300_seed3 | 27.118696419566316 | 0.0 | 0.0 | 1.6757441418619379 | 1.3265765765765765 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6_az45_rate300_seed1 | 26.134455370650528 | 0.0 | 0.0 | 2.584863837872071 | 1.9945302445302446 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6_az45_rate300_seed2 | 26.08654815935451 | 0.0 | 0.0 | 2.587397086763775 | 2.00032175032175 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6_az45_rate300_seed3 | 26.134455370650528 | 0.0 | 0.0 | 2.6051298290057 | 2.0038610038610036 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6-R7-R8_az-45_rate300_seed1 | 32.145297528996466 | 11.811518324607327 | 11.609208523592084 | 1.9901836605446483 | 1.5398970398970397 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6-R7-R8_az-45_rate300_seed2 | 32.13180786686838 | 11.787958115183246 | 11.552130898021309 | 1.9968334388853701 | 1.5376447876447876 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6-R7-R8_az-45_rate300_seed3 | 32.10539586485124 | 11.782722513089002 | 11.58904109589041 | 1.9898670044331854 | 1.5241312741312742 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6-R7-R8_az45_rate300_seed1 | 29.37581946545638 | 16.860882572924456 | 16.54946727549467 | 2.888853704876504 | 2.0971685971685967 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6-R7-R8_az45_rate300_seed2 | 29.405509329299043 | 16.982049364248315 | 16.668949771689498 | 2.8875870804306523 | 2.1084298584298584 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6-R7-R8_az45_rate300_seed3 | 29.39019162884518 | 16.869109947643977 | 16.673515981735157 | 2.8920202659911336 | 2.116151866151866 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| L1-L2_az-45_rate300_seed1 | 0.0 | 0.0 | 0.0 | 27.10924635845472 | 23.251287001287 | 0.0 | 0.0 | 0.0020489258661368437 | 0.0 | photoreceptors |
| L1-L2_az-45_rate300_seed2 | 0.0 | 0.0 | 0.0 | 27.050031665611147 | 23.2979407979408 | 0.0 | 0.0 | 0.0019247485409164288 | 0.0 | photoreceptors |
| L1-L2_az-45_rate300_seed3 | 0.0 | 0.0 | 0.0 | 27.03008233058897 | 23.198519948519948 | 0.0 | 0.0 | 0.002173103191357258 | 0.0 | photoreceptors |
| L1-L2_az45_rate300_seed1 | 0.0 | 0.0 | 0.0 | 27.250791640278656 | 23.55759330759331 | 0.0 | 0.0 | 0.0011796845895939404 | 0.0 | photoreceptors |
| L1-L2_az45_rate300_seed2 | 0.0 | 0.0 | 0.0 | 27.30398986700443 | 23.594916344916342 | 0.0 | 0.0 | 0.0008692412765429032 | 0.0 | photoreceptors |
| L1-L2_az45_rate300_seed3 | 0.0 | 0.0 | 0.0 | 27.33533882203926 | 23.535392535392536 | 0.0 | 0.0 | 0.0008692412765429031 | 0.0 | photoreceptors |

Superseded full-field and LAL rows (`20260914T124802Z/propagation.csv`). Seed 1 unless the row names another seed.

| Id | R1_6 | L1 | L2 | Mi1 | Tm3 | VP | TuBu | ER | LAL | steering_L | steering_R | diff | first silent |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| R1_6_azfull_rate300_seed1 | 128.2636157337368 | 10.472450918302723 | 7.897683397683397 | 0.021835443037974685 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6_azfull_rate300_seed2 | 128.2165279878971 | 10.465801139962 | 7.881595881595882 | 0.021202531645569615 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6_azfull_rate300_seed3 | 128.20158850226926 | 10.491450284990501 | 7.873552123552125 | 0.023101265822784815 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| R1_6-R7-R8_azfull_rate300_seed1 | 128.26311144730204 | 10.600696643445218 | 7.88867438867439 | 0.025 | 0.0 | 0.0044082950453247245 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | medulla_relay |
| L1-L2_azfull_rate300_seed1 | 0.0 | 128.3495883470551 | 119.10263835263834 | 0.025632911392405068 | 0.0 | 0.024649199056252326 | 0.0 | 0.0 | 0.010054844606946983 | 2.75 | 0.0 | 2.75 | photoreceptors |
| L1-L2_azfull_rate300_seed2 | 0.0 | 128.40658644711843 | 119.23777348777348 | 0.027531645569620254 | 0.0 | 0.025021731031913567 | 0.0 | 0.0 | 0.010968921389396709 | 2.0 | 0.0 | 2.0 | photoreceptors |
| L1-L2_azfull_rate300_seed3 | 0.0 | 128.3828372387587 | 119.03603603603604 | 0.026898734177215194 | 0.0 | 0.025021731031913567 | 0.0 | 0.0 | 0.008226691042047532 | 1.5 | 0.0 | 1.5 | photoreceptors |
| TuBu_azfull_rate300_seed1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 125.16 | 7.809352517985609 | 0.0 | 0.0 | 0.0 | 0.0 | photoreceptors |
| LAL_neurons_azfull_rate500_seed1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.14615671178442813 | 0.0 | 0.021582733812949638 | 149.57678244972578 | 89.0 | 62.75 | 26.25 | photoreceptors |
| LAL_neurons_azfull_rate500_seed2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.12510865515956787 | 0.0 | 0.021582733812949638 | 149.60420475319924 | 87.0 | 70.5 | 16.5 | photoreceptors |
| LAL_neurons_azfull_rate500_seed3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0916428660126661 | 0.0 | 0.017985611510791366 | 149.9616087751371 | 90.0 | 74.75 | 15.25 | photoreceptors |

R7 and R8 on `R1_6-R7-R8_azfull_rate300_seed1`: 128.6009723261032 Hz and 128.25913242009133 Hz. DNa02_L on L1+L2 full-field 300 Hz: 5.5, 4.0, 3.0 Hz for seeds 1, 2, 3. DNa02_R stays 0.0 Hz on that arm. MN9 is 0.5 Hz only on LAL seed 3.

Superseded 50 Hz and 150 Hz stripe examples, old y-axis (`20260914T124802Z/propagation.csv`):

| Id | R1_6 | L1 | Mi1 | Tm3 | steering diff | first silent |
|---|---:|---:|---:|---:|---:|---|
| R1_6_az-45_rate50_seed1 | 7.280698436712052 | 0.21120962634578846 | 0.0 | 0.0 | 0.0 | lamina |
| R1_6_az-45_rate150_seed1 | 17.310766515380738 | 1.1253958201393286 | 0.0 | 0.0 | 0.0 | medulla_relay |

Across all 111 superseded rows, Tm3 is 0.0 Hz on every visual site. The maximum Mi1 rate on any R1_6 row is 0.023417721518987345 Hz. The maximum visual-projection rate on any photoreceptor row is 0.004532472370545139 Hz. Those maxima stay below 0.5 Hz.

`20260914T124802Z/summary.json` reports `verdict: encoder placement` because L1+L2 full-field 300 Hz has `|steering_diff_hz| >= 0.5`. That classifier does not inspect the medulla. Do not take that automatic word as the diagnostic verdict.

## Photoreceptor rates

Multiplier 1.0 is enough. Photoreceptors fire.

| Condition | Run | R1_6 Hz |
|---|---|---:|
| Full-field 300 Hz seed 1 (scan) | `20260914T124802Z/multiplier.json` | 128.2636157337368 |
| Stripe −45 degrees 300 Hz seed 1 | `20260914T150502Z/propagation.csv` | 27.15040342914775 |
| Stripe +45 degrees 300 Hz seed 1 | `20260914T150502Z/propagation.csv` | 26.134455370650528 |
| Stripe −45 degrees 50 Hz seed 1 | `20260914T124802Z/propagation.csv` | 7.280698436712052 |

## Steering differences per seed

Corrected 300 Hz stripes: 0.0 Hz on all 18 rows (`20260914T150502Z/propagation.csv`).

Photoreceptor sites on the superseded grid: 0.0 Hz on every seed and every rate (`20260914T124802Z/propagation.csv`).

L1+L2 full-field 300 Hz (`20260914T124802Z/propagation.csv`):

| Seed | steering_L Hz | steering_R Hz | diff Hz | DNa02_L Hz |
|---:|---:|---:|---:|---:|
| 1 | 2.75 | 0.0 | 2.75 | 5.5 |
| 2 | 2.0 | 0.0 | 2.0 | 4.0 |
| 3 | 1.5 | 0.0 | 1.5 | 3.0 |

TuBu full-field 300 Hz seeds 1 to 3: steering difference 0.0 Hz. TuBu rates 125.16, 125.02333333333334, 125.43333333333332 Hz. ER rates 7.809352517985609, 7.811151079136688, 7.848920863309353 Hz. Visual projection 0.0 Hz. LAL 0.0 Hz.

## LAL control

`20260914T124802Z/propagation.csv`, site `LAL_neurons`, 500 Hz uniform, full-field. This arm does not use azimuth.

| Seed | LAL Hz | steering_L Hz | steering_R Hz | diff Hz | DNa02_L Hz | DNa02_R Hz | MN9 Hz |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 149.57678244972578 | 89.0 | 62.75 | 26.25 | 177.5 | 124.5 | 0.0 |
| 2 | 149.60420475319924 | 87.0 | 70.5 | 16.5 | 172.5 | 139.5 | 0.0 |
| 3 | 149.9616087751371 | 90.0 | 74.75 | 15.25 | 179.5 | 149.5 | 0.5 |

The control fires `steering_L` and `steering_R` on every seed.

## Determinism

`20260914T150502Z/determinism.json`: condition `R1_6_az-45_rate300_seed1`. First spike count 466331. Replay spike count 466331. `identical: true`.

`20260914T124802Z/determinism.json`: condition `R1_6_az-45_rate50_seed1`. First spike count 121823. Replay spike count 121823. `identical: true`.

## Overlay counts

From `20260914T150502Z/overlay_counts.json` (same counts in the superseded overlay file). L1 is cell_type `L1` (1579), not the brief figure 2066.

| Name | Count | Source |
|---|---:|---|
| R1_6 | 7932 | overlay |
| R7 | 1337 | overlay |
| R8 | 1314 | overlay |
| L1 | 1579 | overlay |
| L2 | 1554 | overlay |
| Mi1 | 1580 | overlay |
| Tm3 | 1746 | overlay |
| T4 | 6240 | overlay |
| T5 | 5998 | overlay |
| LC_all | 1496 | overlay |
| LPLC | 460 | overlay |
| MeTu | 896 | overlay |
| visual_projection | 8053 | overlay |
| TuBu | 150 | frozen |
| ER | 278 | frozen |
| EPG | 51 | frozen |
| LAL_neurons | 547 | frozen |
| DNa02_L | 1 | frozen |
| DNa02_R | 1 | frozen |
| steering_L | 2 | frozen |
| steering_R | 2 | frozen |
| DN_all | 1299 | frozen |
| MN9 | 1 | frozen |
| motor | 106 | frozen |

`ap_axis.json` counts 8452 R1-6 annotation rows. 8451 of those rows have no soma. The overlay count 7932 is the resolved engine population.

## Engine gap

The engine exposes spike lists, population indices, and `set_input_rates`. It has no public setter for extended-input synaptic weight. This diagnostic scales Poisson rates with multiplier 1.0.

### Sign of the lamina-to-medulla relay (review r11)

Review r11 counted these from the engine's connectivity table and the annotations, not from a run directory. Sources: `Drosophila_brain_model/Connectivity_783.parquet` under `FLYONENOMICS_CACHE_DIR` (sha256 `efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347`, verified against its provenance record), whose `Excitatory x Connectivity` column times `lif.w_syn` is the synapse weight the engine builds (`engine/brian_engine.py`), and `annotations-v2.1.0.tsv` (`top_nt`). Populations are resolved through `data/populations-dev.yaml` against the v783 engine order. A pair is one presynaptic and one postsynaptic neuron; `Excitatory` is signed per pair in the table.

| Connection | Pairs | Synapses | Inhibitory pairs (synapses) | Excitatory pairs (synapses) | Sum of `Excitatory x Connectivity` |
|---|---:|---:|---:|---:|---:|
| L1 → Mi1 | 1743 | 121693 | 1716 (121406) | 27 (287) | −121119 |
| L1 → Tm3 | 8829 | 80600 | 8790 (80408) | 39 (192) | −80216 |
| R1-6 → L1 | 5867 | 63344 | 1114 (14014) | 4753 (49330) | +35316 |
| R1-6 → L2 | 5727 | 62051 | 1105 (14109) | 4622 (47942) | +33833 |
| L2 → Mi1 | 940 | 2007 | 8 (130) | 932 (1877) | +1747 |
| L2 → Tm3 | 400 | 593 | 23 (100) | 377 (493) | +393 |

L1 transmitter prediction (`top_nt`, all 1579 cells in the engine): glutamate 1043, GABA 512, acetylcholine 24. By synapse count Mi1 (121693) and Tm3 (80600) are two of L1's three largest targets; L5 is the other (111800).

The medulla silence is what the sign rule predicts. R1-6 excite L1 and L2 on net, so the lamina fires under photoreceptor drive. More than 99% of L1's synapses onto Mi1 and Tm3 are inhibitory, so more L1 spikes can only hyperpolarise the ON relay. With `background: false` that relay has no baseline firing to decrease. L2's net excitatory input to Mi1 (+1747) and Tm3 (+393) is small against L1's net inhibition (−121119 and −80216), including on the L1+L2 full-field arm that drives both.
