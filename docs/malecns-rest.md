# MaleCNS rest under the ruled FlyWire configuration

> **Current status (25 September 2026):** Historical resting measurement from 22 September 2026. Runtime now uses the adopted MaleCNS substrate `rest:ed9b0a469d7a6b77` and filled male drive/dopamine tables. See [adoption](malecns-port.md#starting-substrate-port-step-6-item-155), the [first-study design](adhd-study-design.md) and the [confirmation design](adhd-confirm-design.md). Frozen parameter and engine source notes have a [provenance erratum](errata.md).

**Status: Part B complete; configuration accepted by item 155.** The plan was
fixed at `f0cdb28` before any male resting outcome, and the telemetry-only
runner change was committed at `2ef6711` before launch. It applied the
configuration Rolf accepted in SPEC-P2 item 122 without tuning it on MaleCNS.
After seeing these measurements, Rolf ruled in item 155 that this unchanged
configuration is the male resting substrate. The §2.3 lines below are recorded
comparisons, not gates on that decision.

This is a resting-state measurement, not a behaviour. The fly does not see.

## Governing rules

- **Item 121:** report measured values; do not turn model-fitted reflex numbers
  into pass lines.
- **Item 122:** apply the sensory-only 1.0 mV FlyWire resting configuration.
- **Item 149:** MaleCNS is a distinct substrate and no FlyWire result transfers
  as a male result.
- **Items 150--153:** use the male graph, signs, populations, eye assignment and
  dopamine tables. All calibrated male fields remain unset before this run.
- **Item 155:** accept the unchanged item 122 configuration as the male resting
  substrate; treat the §2.3 values as recorded measures rather than gates.
- **This lane's pre-run rule:** first apply item 122 unchanged and measure it
  against SPEC-P2 §2.3. No value is chosen from a male outcome.

## Exact configuration

The source of the ruled unit is `data/drive-v0.2.yaml:2-58`. Its effective
neuron constants come from `data/params-v0.2.yaml:7-19`. The runner constructs
this table in memory because, at measurement time, `data/drive-male-cns-v1.0.yaml:5-60`
kept all male-calibrated fields null; the runner did not overwrite that file.

| Value | Ruled value and source | Male mapping |
|---|---|---|
| Dataset | FlyWire used v783; the measured graph here is `male-cns:v1.0` under items 149--150. | The MaleCNS adapter supplies 162,517 nodes and every retained signed pair. |
| Engine | `lif`; `mechanisms: null` (`data/drive-v0.2.yaml:54`). | The same `lif` equations, `linear` method and no mechanism. |
| Membrane | `v_0=-52`, `v_rst=-52`, `v_th=-45` mV; `t_mbr=20`, `tau=5`, `t_rfc=2.2`, `t_dly=1.8`, `dt=0.1` ms; `w_syn=0.275` mV (`data/params-v0.2.yaml:8-16`). | Applied unchanged to every male node and signed male edge. |
| Transmitter scope | `brain`; unknown positive rows ×1 and unknown negative rows ×`g_gaba` (`data/drive-v0.2.yaml:2-11`). | Male classes come from `data/transmitters-male-cns-v1.0.yaml`; item 150's per-neuron unknown sign remains the edge sign. |
| Scales | `g_gaba=1`, `g_glu=4`, `g_his=1`, `g_gaba_kc=6` (`data/drive-v0.2.yaml:5-11`). | Applied to male edge order. The FlyWire scale-array hash is not reused because it names a different-length array. `KC` is item 152's 4,064-cell male population. |
| Background process | `n_bg=100`, `r_bg=10 Hz/input` (`data/drive-v0.2.yaml:12-14`; matching params at `data/params-v0.2.yaml:27-30`). | Same process for every male neuron; group membership comes from the male registry. |
| Background weights | sensory 1.0 mV; every other group 0 (`data/drive-v0.2.yaml:15-51`). | `sensory` is item 152's male drive group (15,016 cells). Male vocabulary is mapped before the DAN/KC/ER overlays by `src/flyonenomics/drive/background.py:115-132`. No cell is selected by a male firing outcome. |
| Threshold spread | none: `threshold: null`, hence `sigma_th=0` (`data/drive-v0.2.yaml:52`). | Every male cell keeps the common −45 mV base threshold before layer A composition. |
| Optic exemption | false (`data/drive-v0.2.yaml:53`). | Male optic edges receive the same class rules as the rest of the graph. |
| K1 state | wild type; background on; layer A on; pools clamped at `DA_ref=0.02 µM`; layer C on; no drug (SPEC-P2 §2.3; `data/params-v0.2.yaml:61-68`). | Male W, M and receptor arrays are used. No FlyWire `R_c`, `alpha_c` or `S_c` is loaded: the clamp makes `DA_ref` the effective dopamine state while item 153's calibrated male arrays stay null. |
| Randomness | master seed 20260912, seed indices 1--10. | Brian streams use the existing project seed derivation. Conditions within a seed restart from the same stored state and seed. |

### Identity

The female identifier is `rest:379cc4cc9030cdd1`. SPEC-P2 §2.5 defines it as
`rest:` plus the first 16 hexadecimal characters of the drive file SHA-256
when no mechanism is active. The implementation is
`src/flyonenomics/drive/mechanisms.py:357-373`.

This lane did **not** mint a male substrate identifier. Item 155 subsequently
accepted the unchanged configuration; port step 6 writes the separately
versioned male drive bytes and uses that same `substrate_id_for` rule. Reusing
the female identifier would violate item 149.

## Frozen measurement plan

All neural measurements use the K1 state above. A seed file is written by
atomic rename only after all of that seed's arms have finished. Eight
persistent workers each build one engine; individual arms are scheduled
longest-first. The parent writes ten complete seed files under
`camber-runs/malecns-rest/`, then the summarizer computes the dopamine chain.
The held entry point is:

```bash
FLYONENOMICS_CACHE_DIR=~/flyo-cache \
  .venv/bin/python scripts/malecns_rest.py --run \
  --workers 8 --output-dir camber-runs/malecns-rest/run-<stamp>
```

Part B ran detached with parent PID 1, so Mac sleep could not stop it.

### R-screen and gradedness

Ten seeds run 2 s settle plus 10 s measurement at 1.0 and 1.2 mV. The 1.2 mV
pair member is fixed by item 120.1's 0.20 mV sensory-arm step. Gradedness uses
1.4 mV, the next point above that pair, for the same ten seeds and window. That
is more replication than §2.3's original three-seed minimum and introduces no
new criterion.

| Metric | Historical §2.3 comparison | Female value of record (item 121 / its record) | Male measure |
|---|---|---|---|
| F | `< 3` in every seed at both pair weights | maximum 2.618765 | At 1.0, seeds 1, 5 and 9 are at or above the line; max 3.277527. At 1.2 max 2.525789. |
| largest 1 ms fraction `b` | `< 0.05` in every seed at both pair weights | comparison recorded as held; item 121's committed summary gives no numeric maximum | Below the line; maxima 0.002707 at 1.0 and 0.002566 at 1.2 |
| first-1 s / last-1 s central ratio | `[0.5, 2]` in every seed at both pair weights | comparison recorded as held; no per-seed numeric ratios in item 121's summary | Within the interval; ranges 0.966797–1.025182 and 0.974811–1.005235 |
| central rate | seed mean `[0.5, 8] Hz` at both weights | 4.831752 Hz at 1.0; 4.864218 Hz at 1.2 | Within the interval; 4.789499 and 5.029575 Hz |
| DAN rate | seed mean `[0.5, 10] Hz` at both weights | 0.812576 Hz at 1.0; 0.822493 Hz at 1.2 | Within the interval; 1.514387 and 1.243297 Hz |
| KC rate | seed mean `≤ 2 Hz` at both weights | 0.088858 Hz at 1.0; 0.087528 Hz at 1.2 | Below the line; 0.010234 and 0.010746 Hz |
| gradedness | central mean at 1.4 mV `< 3 ×` the central mean at each of 1.0 and 1.2 mV | not measured in the item 120 freeze; explicitly null in the record | Below the line in every seed; 1.4 mV mean 5.306266 Hz |

The output keeps every seed and weight, not only these aggregates. Missing F or
ratio values would be recorded as unavailable rather than silently replaced.

### R-long

At 1.0 mV, ten seeds run 2 s settle plus 30 s measurement.

| Metric | Historical §2.3 / §9.2 comparison | Female value of record | Male measure |
|---|---|---|---|
| F | `< 3` in every seed | item 121 states the ten-seed screen held; no separate 30 s F is stated | Seeds 1, 5 and 9 are at or above the line; max 3.170017 |
| ignition | none: no 1 s central window above 3× a settled baseline at least 0.5 Hz, or above 8 Hz (`data/params-v0.2.yaml:241-245`) | no 30 s ignition vector is stated in item 121 | No seed ignites; peak range 4.900134–5.182683 Hz |
| first-5 s / last-5 s central ratio | `[0.5, 2]` in every seed | no numeric 30 s ratios are stated in item 121 | Every seed is within the interval; range 0.974285–1.008629 |

### Dopamine calibration chain, computed but not yet adopted at measurement time

Seeds 1--3 additionally run the exact §2.5 K2r measurement: 2 s settle plus
5 s, clamped at `DA_ref`, returning each compartment's weighted DAN rate
`R_c`. With the unchanged declared constants (`DA_ref=0.02 µM`, `Vmax=0.11
µM/s`, `Km=1.3 µM`, `k_ns=0.05/s`, `R_min=0.5 weighted spikes/s`), the runner
computes:

```text
Q_c     = DA_ref * (Vmax / (Km + DA_ref) + k_ns)
alpha_c = Q_c / max(R_c, R_min)
S_c     = max(0, Q_c - alpha_c * R_c)
mode    = derived if R_c >= R_min, otherwise source
```

These equations and the three-seed protocol are SPEC-P2 §2.5 lines 510--525.
The complete 37-element vectors were recorded as **computed, not yet adopted**
at this measurement stage. `data/dopamine-male-cns-v1.0.yaml` was null then;
the subsequent [adoption](malecns-port.md#starting-substrate-port-step-6-item-155)
filled the runtime table without making it an input to this measurement.

### R-reflex

R-reflex cannot run. Item 152 found 161 typed labellar gustatory cells but no
sugar modality or receptor label, so `sugar_GRN_R` is empty
(`data/populations-male-cns-v1.0.yaml:1121`). No cells are substituted by
count, type resemblance or output. For comparison only, the female item 121
record is mean 26.6 Hz, minimum 19.3 Hz, same-job bare 57.0 Hz and retention
0.956; those are measurements, not pass lines.

## Cost probe

The Oracle box ran one configured dark brain-second in one process on
Linux/aarch64. This was a cost probe, not Part B.

| Measured quantity | Value |
|---|---:|
| engine/configuration build wall | 77.722 s |
| one brain-second wall | 113.347 s |
| total probe wall | 191.127 s |
| peak RSS | 7,282,909,184 bytes (6.782 GiB) |
| box memory available at probe | 94,245,847,040 bytes |
| box physical memory | 101,036,359,680 bytes |

The plan is 701 brain-seconds: 360 for the two screen weights plus gradedness,
320 for R-long, and 21 for the three K2r rows. Conservatively treating every
worker's peak RSS as private, eight workers use 58,263,273,472 bytes and leave
35,982,573,568 bytes of the measured available memory, above one third of
physical RAM (33,678,786,560 bytes). Eight is therefore the measured limit
under the task's one-third-free rule; the cap is ten.

One parallel build wave plus `701 × 113.347 / 8` gives **10,009.7 s, about 2 h
47 min**, before scheduling and concurrency overhead. This is an estimate from
the probe, not a pass criterion. The machine-readable evidence is
`validation/records/p2/malecns-rest-plan.json`.

## Part B result

At 1.0 mV, R-screen F is at or above the historical value 3 on seeds 1, 5
and 9. The same seeds are at or above 3 in R-long. Every other R-screen
measure lies within its historical §2.3 interval, every gradedness comparison
is below its line, no seed ignites, and every long-window edge ratio is within
its interval. R-reflex remains unmeasurable because there is no ruled male
sugar source. Item 155 records all of these as measures, accepts the unchanged
configuration as the male resting substrate, and sends the separately
versioned drive and substrate identifier to port step 6.

### R-screen: every seed and pair weight

Historical comparison lines: F `<3`; b `<0.05`; ratio `[0.5,2]`; ten-seed
central mean `[0.5,8] Hz`; DAN mean `[0.5,10] Hz`; KC mean `≤2 Hz`. Under item
155 these are not gates. The FlyWire item 121 reference is F max 2.618765,
central 4.831752/4.864218 Hz, DAN 0.812576/0.822493 Hz and KC
0.088858/0.087528 Hz at 1.0/1.2 mV. Its summary says b and stability were below
or within their lines but does not retain their numeric extrema.

#### 1.0 mV

| seed | F | b | ratio | central Hz | DAN Hz | KC Hz |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3.277527 **(at/above historical line)** | 0.002246 | 0.993842 | 4.765378 | 1.793188 | 0.007874 |
| 2 | 2.899698 | 0.002227 | 0.966797 | 4.889341 | 1.193460 | 0.010482 |
| 3 | 2.902565 | 0.002111 | 1.025182 | 4.788207 | 1.510354 | 0.010950 |
| 4 | 2.879400 | 0.001994 | 1.006081 | 4.771171 | 1.519346 | 0.010531 |
| 5 | 3.275508 **(at/above historical line)** | 0.002135 | 0.980118 | 4.768907 | 1.783106 | 0.007874 |
| 6 | 2.877019 | 0.002055 | 1.000962 | 4.770920 | 1.397275 | 0.010310 |
| 7 | 2.916119 | 0.002289 | 0.993093 | 4.801118 | 1.532153 | 0.010950 |
| 8 | 2.799725 | 0.002252 | 0.992039 | 4.778787 | 1.502452 | 0.011171 |
| 9 | 3.065277 **(at/above historical line)** | 0.002707 | 1.007400 | 4.809992 | 1.499183 | 0.011491 |
| 10 | 2.800560 | 0.002031 | 0.975746 | 4.751167 | 1.413351 | 0.010704 |

Ten-seed means: central 4.789499 Hz, DAN 1.514387 Hz, KC 0.010234 Hz. F max 3.277527; b max 0.002707; ratio range 0.966797 to 1.025182.

#### 1.2 mV

| seed | F | b | ratio | central Hz | DAN Hz | KC Hz |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2.383402 | 0.002400 | 0.992164 | 5.075749 | 1.195913 | 0.010531 |
| 2 | 2.387711 | 0.002547 | 1.002882 | 5.080500 | 1.199455 | 0.011393 |
| 3 | 2.286193 | 0.002400 | 0.997313 | 5.071743 | 1.159128 | 0.010876 |
| 4 | 2.325908 | 0.002443 | 0.985301 | 5.061083 | 1.173025 | 0.010285 |
| 5 | 2.336369 | 0.002474 | 1.005235 | 5.060610 | 1.176839 | 0.010261 |
| 6 | 2.445250 | 0.002566 | 0.979264 | 5.046533 | 1.162670 | 0.011122 |
| 7 | 2.467500 | 0.002351 | 0.996994 | 4.914160 | 1.403542 | 0.011294 |
| 8 | 2.525789 | 0.002443 | 1.000278 | 4.909124 | 1.388011 | 0.010851 |
| 9 | 2.409607 | 0.002492 | 0.974811 | 5.024425 | 1.414441 | 0.010187 |
| 10 | 2.341027 | 0.002467 | 0.993721 | 5.051817 | 1.159946 | 0.010655 |

Ten-seed means: central 5.029575 Hz, DAN 1.243297 Hz, KC 0.010746 Hz. F max 2.525789; b max 0.002566; ratio range 0.974811 to 1.005235.

### Gradedness at 1.4 mV

The historical comparison is `central(1.4) < 3 × central(1.0)` and `< 3 ×
central(1.2)`. FlyWire did not measure this point in item 121. All ten male
seeds are below the line.

| seed | 1.0 Hz | 1.2 Hz | 1.4 Hz | comparison |
|---:|---:|---:|---:|---|
| 1 | 4.765378 | 5.075749 | 5.306051 | below |
| 2 | 4.889341 | 5.080500 | 5.312048 | below |
| 3 | 4.788207 | 5.071743 | 5.310014 | below |
| 4 | 4.771171 | 5.061083 | 5.302699 | below |
| 5 | 4.768907 | 5.060610 | 5.306207 | below |
| 6 | 4.770920 | 5.046533 | 5.282260 | below |
| 7 | 4.801118 | 4.914160 | 5.304586 | below |
| 8 | 4.778787 | 4.909124 | 5.319273 | below |
| 9 | 4.809992 | 5.024425 | 5.307776 | below |
| 10 | 4.751167 | 5.051817 | 5.311750 | below |

The ten-seed 1.4 mV mean is 5.306266 Hz.

### R-long at 1.0 mV

Historical comparison lines: F `<3`; no §9.2 ignition; first-5 s / last-5 s
central ratio in `[0.5,2]`. Item 121 states no separate female 30 s values.

| seed | F | ignited | peak central Hz | first 5 Hz | last 5 Hz | ratio |
|---:|---:|---|---:|---:|---:|---:|
| 1 | 3.094994 **(at/above historical line)** | no | 5.004983 | 4.762947 | 4.722202 | 1.008629 |
| 2 | 2.885271 | no | 5.182683 | 4.850550 | 4.978575 | 0.974285 |
| 3 | 2.951743 | no | 4.911416 | 4.791314 | 4.794131 | 0.999412 |
| 4 | 2.859811 | no | 4.900134 | 4.774750 | 4.778459 | 0.999224 |
| 5 | 3.170017 **(at/above historical line)** | no | 4.921230 | 4.738897 | 4.731743 | 1.001512 |
| 6 | 2.927640 | no | 4.924898 | 4.753497 | 4.767207 | 0.997124 |
| 7 | 2.849457 | no | 4.943086 | 4.785526 | 4.786786 | 0.999737 |
| 8 | 2.893682 | no | 4.908304 | 4.772352 | 4.787934 | 0.996746 |
| 9 | 3.020448 **(at/above historical line)** | no | 4.934561 | 4.817793 | 4.804902 | 1.002683 |
| 10 | 2.935942 | no | 4.989022 | 4.737890 | 4.791187 | 0.988876 |

### Dopamine chain (computed, not yet adopted at measurement time)

Eight compartments were in derived mode and 29 in source mode. No array below was written into the male dopamine configuration during this measurement; adoption happened later.

| compartment | R_c weighted spikes/s | alpha_c µM/spike | S_c µM/s | mode |
|---|---:|---:|---:|---|
| gamma1_L | 51.2333333 | 5.2049447e-05 | 0 | derived |
| gamma2_L | 0 | 0.00533333333 | 0.00266666667 | source |
| gamma3_L | 0 | 0.00533333333 | 0.00266666667 | source |
| gamma4_L | 0 | 0.00533333333 | 0.00266666667 | source |
| gamma5_L | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha1_L | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha2_L | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha3_L | 29.6666667 | 8.98876404e-05 | 0 | derived |
| beta1_L | 0 | 0.00533333333 | 0.00266666667 | source |
| beta2_L | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha_prime1_L | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha_prime2_L | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha_prime3_L | 0 | 0.00533333333 | 0.00266666667 | source |
| beta_prime1_L | 0 | 0.00533333333 | 0.00266666667 | source |
| beta_prime2_L | 0 | 0.00533333333 | 0.00266666667 | source |
| gamma1_R | 51.2333333 | 5.2049447e-05 | 0 | derived |
| gamma2_R | 0 | 0.00533333333 | 0.00266666667 | source |
| gamma3_R | 0 | 0.00533333333 | 0.00266666667 | source |
| gamma4_R | 0 | 0.00533333333 | 0.00266666667 | source |
| gamma5_R | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha1_R | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha2_R | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha3_R | 29.6666667 | 8.98876404e-05 | 0 | derived |
| beta1_R | 0 | 0.00533333333 | 0.00266666667 | source |
| beta2_R | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha_prime1_R | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha_prime2_R | 0 | 0.00533333333 | 0.00266666667 | source |
| alpha_prime3_R | 0 | 0.00533333333 | 0.00266666667 | source |
| beta_prime1_R | 0 | 0.00533333333 | 0.00266666667 | source |
| beta_prime2_R | 0 | 0.00533333333 | 0.00266666667 | source |
| EB | 3.34215205 | 0.000797889092 | 0 | derived |
| PB | 0 | 0.00533333333 | 0.00266666667 | source |
| FB | 41.9535773 | 6.3562319e-05 | 0 | derived |
| NO_L | 0.0174744941 | 0.00533333333 | 0.00257346936 | source |
| NO_R | 0.021500499 | 0.00533333333 | 0.00255199734 | source |
| LAL_L | 11.1884765 | 0.000238340463 | 0 | derived |
| LAL_R | 7.81015243 | 0.000341435931 | 0 | derived |

### Concurrent cost and completeness

All 43 arms and ten atomic seed files completed between 2026-09-22T12:57:28.075224+00:00 and 2026-09-22T15:21:14.364957+00:00 (8626.3 s, 2 h 23 min 46 s). The first eight full-load arms measured 92.678 wall s per brain s and revised the finish to 2026-09-22T15:17:20.411682+00:00; actual completion was about four minutes later. Across every arm, mean concurrent cost was 91.306 and the range was 87.860–93.151 wall s per brain s. The greatest worker peak RSS was 7,261,716,480 bytes; summed per-worker peaks were 58,023,702,528 bytes. Each arm’s wall time, worker PID and peak RSS are in the raw `run.log`.

Raw output is under `camber-runs/malecns-rest/run-20260922T125727Z/`; hashes and all per-seed values are committed in `validation/records/p2/malecns-rest.json`. The fly does not see, and nothing here is a behaviour.
