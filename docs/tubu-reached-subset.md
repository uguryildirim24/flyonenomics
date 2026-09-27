# The cells TuBu reaches, one cell at a time

## Result

TuBu drives some of the cells it reaches. The r25 steering null was not a
signal divided by an unreachable observer: the two observer populations r25
averaged are silent cell by cell, while the clearest response is in the
ellipsoid-body ring neurons, which r25 did not observe at all.

- **Directly reached visual-projection cells (244 of 8,053):** none fires, off
  or on, on any of the ten seeds. Their measured distance to threshold stays
  6.888 to 7.803 mV; the single largest TuBu input into this class raises a
  sampled voltage by 0.555 mV.
- **Directly reached LAL cells (5 of 547):** none fires, off or on. Three
  receive no active TuBu input at all on these seeds; the best fed one takes
  +14.4 mV/s and still ends 4.843 mV below threshold.
- **Directly reached ellipsoid-body ring neurons (228 of 278 `ER` cells):** 55
  fire with TuBu on and 0 with TuBu off. Per seed, 41 to 47 of them fire and the
  class emits 4,157 to 4,290 extra spikes over the 18 s window. This is the
  response the earlier population readouts missed.
- **The four steering endpoints (`DNa02_L`, `DNa02_R`, `steering_L`,
  `steering_R`):** they receive no direct TuBu event and their positive
  two-hop intermediates are essentially silent. Across seeds, each nonzero
  paired series spans both signs and `steering_L` stays exactly zero; the four
  means are +3.7, -6.6, 0.0 and -0.2 spikes over 18 s. Their mean membrane
  voltage moves by at most 0.123 mV. This injection produces no consistent
  measured steering direction on this substrate.

This is a per-cell measurement. It records a real null for the two populations
r25 averaged, and a real response where the anterior visual pathway actually
lands. It does not claim a firing floor, a threshold, or an acceptance line; the
numbers are model measurements on the declared substrate.

## Protocol

The probe is the r30 injection: `TuBu` off versus on, on item 122's declared
resting substrate (`rest:379cc4cc9030cdd1`) with the canonical v0.2 data files.
The on condition is a 5-degree stripe at +45 degrees with a 70 Hz cap and a
20-degree encoder width, identical to the r30 TuBu pair. Ten seeds (1 to 10)
pair an off and an on run on the same stored state, 2 s settle and 18 s
measurement each, for 400 brain-seconds. Every traced cell's spike count,
sampled voltage, composed threshold and signed TuBu event amplitude is recorded
per condition and per seed; the source-event value is the sum over
TuBu-to-target recurrent event amplitudes in the window after substrate weight
scaling and live postsynaptic gain.

The source behaves as the r30 probe found: TuBu off is silent on every seed,
and TuBu on adds +9.320 to +9.412 Hz (mean +9.370 Hz), about 25,300 TuBu spikes
over each 18 s window.

The census has 774 traced cells: the 244 direct `visual_projection` targets,
the 5 direct `LAL_neurons` targets, 249 matched unreached controls (244
visual-projection and 5 LAL, matched by cell type and side), the 11 cells on
positive two-hop paths into the four endpoints plus the endpoints themselves,
the 228 direct `ER` ring neurons, the 4 direct `ExR2` ring neurons, and the 36
direct AOTU bulb targets. The 774-cell jobs took 49 to 62 wall-seconds per
brain-second, overlapping the earlier 64-cell jobs' 50 to 56; this was not a
controlled throughput benchmark. At the 0.1 ms step, the 20 s raw voltage
monitor alone holds about 1.24 GB per worker, and extracting the 18 s window
creates about 1.11 GB more. The earlier 1.05 GB estimate used the 656 immediate
targets rather than the 774 cells actually traced.

## What TuBu directly reaches

The composed weights below are the substrate-scaled signed sums of every
TuBu-to-cell connection, from the committed static audit recomputed on the same
arrays. They explain the result: TuBu's grip on the ellipsoid body is dense and
strong, and its grip on the averaged populations is peripheral.

| Direct target class | Reached | Population | Pairs | Synapses | Composed weight | Fraction of class reached |
|---|---:|---:|---:|---:|---:|---:|
| ellipsoid-body ring neurons (`ER`) | 228 | 278 | 479 | 15,213 | +4,183.575 mV | 82.0% of cells |
| AOTU bulb cells | 36 | 258 | 332 | 904 | +248.600 mV | 14.0% of cells |
| `visual_projection` | 244 | 8,053 | 281 | 305 | +83.875 mV | 3.03% of cells |
| `ExR2` ring neurons | 4 | 4 | 55 | 113 | +31.075 mV | 4 of 4 |
| `LAL_neurons` | 5 | 547 | 5 | 7 | +1.925 mV | 0.914% of cells |
| `steering_L`, `steering_R`, `DNa02_L`, `DNa02_R` | 0 | — | 0 | 0 | 0 mV | 0% |

The `ER` row covers 15,213 synapses against 305 for the whole 8,053-cell
visual-projection class. The total composed weight is 49.9 times larger, and
the mean per reached cell is 53.4 times larger.

## The averaged populations are silent cell by cell

### `visual_projection`: 0 of 244

No reached visual-projection cell fires in either condition on any seed. The
per-seed total spike change is exactly 0 for all ten seeds. The class is
dominated by MeTu cells (70 MeTu1, 41 MeTu2, 74 MeTu3, 43 MeTu4) plus 13 LC10.

The input is present and small. 138 of the 244 have a positive TuBu event
change. As a rate over the 18 s window the mean is 2.559 mV/s, the median
0.008 mV/s, and the maximum 25.452 mV/s. The largest inputs move the sampled
voltage by under 0.56 mV:

| Measurement, on minus off | Across-cell mean | Median | Range |
|---|---:|---:|---:|
| TuBu event rate | +2.559 mV/s | +0.008 mV/s | 0 to +25.452 mV/s |
| Mean membrane voltage | +0.0124 mV | +0.0002 mV | -0.009 to +0.128 mV |
| Sampled maximum voltage | +0.0512 mV | +0.0035 mV | -0.023 to +0.555 mV |

The mean distance to threshold under the stripe is 6.888 to 7.803 mV (median
7.001 mV), and the nearest sampled distance is 6.445 to 7.170 mV. There is no
cell near its threshold and no cell crosses it.

### `LAL_neurons`: 0 of 5

Every direct LAL row is a single pair. The five cells, individually:

| Engine index | Root ID | Pairs | Synapses | Composed | TuBu event on minus off | Mean v, on | Nearest threshold gap, on | Spikes off / on |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 13114 | 720575940612106723 | 1 | 1 | +0.275 mV | 0.000 mV | -52.052 mV | 7.000 mV | 0 / 0 |
| 19795 | 720575940614267242 | 1 | 1 | +0.275 mV | 0.000 mV | -52.049 mV | 6.997 mV | 0 / 0 |
| 44833 | 720575940620678772 | 1 | 1 | +0.275 mV | +0.22 mV | -51.598 mV | 3.756 mV | 0 / 0 |
| 108635 | 720575940632469964 | 1 | 1 | +0.275 mV | +259.02 mV | -52.983 mV | 4.843 mV | 0 / 0 |
| 122669 | 720575940637515182 | 1 | 3 | +0.825 mV | 0.000 mV | -62.072 mV | 6.949 mV | 0 / 0 |

Three of the five receive no active TuBu input on these seeds. The best fed
cell (108635, +259.02 mV over the window, +14.4 mV/s) rises to a sampled
-49.843 mV and stays 4.843 mV below threshold. Cell 122669 sits at a mean
-62.072 mV, 17 mV below threshold, and its three-synapse input does not move it.

### `ExR2` ring neurons: 0 of 4

The four `ExR2` cells are a separate class from the `ER` population by
annotation. TuBu reaches them hard (3 to 21 pairs, up to +14.025 mV composed,
74.0 mV/s mean event rate) yet none fires: their largest sampled-voltage
change is -0.239 to +1.093 mV and they hold 5.24 to 7.11 mV from threshold.
Strong direct excitation is not sufficient here; recurrent input holds them
down.

## The ring neurons are the response

228 of the 278 `ER` cells are direct TuBu targets. Of those, 168 carry a
positive TuBu event change on these seeds, and 55 fire with TuBu on and never
with it off. Per seed, 41 to 47 fire and the class emits 4,157 to 4,290 extra
spikes over 18 s (mean 4,203.6). The responders span every large ER type:
ER2 11, ER3w 8, ER3d 9, ER5 9, ER3p 6, ER4m 5, ER4d 4, ER3m 3.

The response is graded, not a fixed fraction. The ten strongest responders:

| Engine index | Type | Spikes on | Spike change | TuBu event rate | Mean v, on | Max v, on | Nearest threshold gap, on |
|---:|---|---:|---:|---:|---:|---:|---:|
| 39059 | ER4m | 807.2 | +807.2 | 3,796.8 mV/s | -51.72 mV | -45.00 mV | 0.00 mV |
| 114398 | ER4m | 602.5 | +602.5 | 2,864.9 mV/s | -50.65 mV | -45.00 mV | 0.00 mV |
| 47109 | ER3w | 287.3 | +287.3 | 1,596.5 mV/s | -49.77 mV | -45.00 mV | 0.00 mV |
| 129944 | ER3w | 238.7 | +238.7 | 1,476.6 mV/s | -49.70 mV | -45.00 mV | 0.00 mV |
| 34576 | ER3w | 226.9 | +226.9 | 1,400.6 mV/s | -49.53 mV | -45.00 mV | 0.00 mV |
| 123109 | ER3w | 202.5 | +202.5 | 1,514.4 mV/s | -49.26 mV | -45.00 mV | 0.00 mV |
| 87826 | ER2 | 168.1 | +168.1 | 1,121.4 mV/s | -49.94 mV | -45.00 mV | 0.00 mV |
| 76100 | ER3w | 167.6 | +167.6 | 1,473.3 mV/s | -48.48 mV | -45.00 mV | 0.00 mV |
| 92478 | ER4d | 164.5 | +164.5 | 933.9 mV/s | -49.67 mV | -45.00 mV | 0.00 mV |
| 75520 | ER2 | 147.4 | +147.4 | 1,215.1 mV/s | -49.08 mV | -45.00 mV | 0.00 mV |

The 173 reached ER cells that stay silent are the weakly fed ones: the class
event rate has median 5.164 mV/s against the top responders' 0.9 to 3.8 V/s.
The measured split is between fed-above-threshold and fed-below-threshold, not
between reached and unreached.

### The bulb: 1 of 36

Of the 36 direct AOTU bulb targets, one responds. Cell 66554 (`AOTU046`) takes
+965.0 mV/s and fires 5.8 spikes on against 0 off, with mean voltage +4.739 mV.
Two cells move slightly negative and 33 are silent. The bulb subset is not a
population-level responder.

## No consistent steering-output response to this injection

The four endpoints are reachable only by two hops, and every positive two-hop
intermediate was measured.

| Endpoint | Engine index | Direct TuBu event | Spikes off / on | Paired spike change (10 seeds) | Mean v change | Max sampled v change |
|---|---:|---:|---:|---|---:|---:|
| `DNa02_L` (= `steering_L`) | 92992 | 0 | 311.0 / 314.7 | +11,-6,+2,-26,-14,+37,+31,-3,-2,+7; mean +3.7 | +0.123 mV | 0.000 mV |
| `DNa02_R` (= `steering_R`) | 904 | 0 | 391.1 / 384.5 | -35,-8,-7,+39,+27,-50,-11,-21,+12,-12; mean -6.6 | -0.101 mV | 0.000 mV |
| `steering_L` | 33924 | 0 | 0.0 / 0.0 | 0 on all ten seeds | -0.010 mV | -0.725 mV |
| `steering_R` | 75935 | 0 | 0.5 / 0.3 | 0,0,+1,0,-1,0,-1,-1,-1,+1; mean -0.2 | +0.096 mV | +0.013 mV |

No endpoint receives a direct TuBu event. The nonzero ten-seed series span
both signs, while `steering_L` is zero throughout, so there is no consistent
steering direction. The two `DNa02` cells are tonically active (about 300 to
390 spikes per 18 s); their paired differences vary in sign across seeds.

The eleven positive two-hop intermediates tell the same story. One, the
`CL053` cell 36647, carries a real if small TuBu input (+14.55 mV over the
window, 0.81 mV/s) and fires 47.0 to 48.6 spikes (change +1.6). The other ten
have an event change of 0.00 to 0.22 mV and a spike change of 0 on every seed;
several sit more than 7 mV below threshold. A signal can exist at the first hop
and still fail to cross an unfed intermediate.

## What this establishes

1. **The averaged populations are a measured null, but the wrong readout for
   TuBu's main projection.** The r25/r30 readouts averaged `visual_projection`
   (3.03% directly reached) and `LAL_neurons` (0.914% directly reached), and
   this per-cell measurement shows those reached subsets themselves are silent.
   The dilution argument was a size argument; the measurement now shows the
   size argument described the wrong observer entirely.
2. **TuBu is not silent at its own projection.** It drives its ring-neuron
   targets to 55 responders and thousands of extra spikes per seed. The earlier
   consult's anatomical note is what the model implements: TuBu supplies the
   ellipsoid-body ring neurons.
3. **The readout must follow the projection, not a population name.** Any
   Phase 2 steering readout built on `visual_projection` or `LAL_neurons`
   measures a class TuBu does not drive. A readout built on `ER` measures the
   class it does.
4. **The steering output is not reached on this substrate.** Direct input is
   absent, the two-hop intermediates are silent apart from one CL053 cell, and
   the endpoints move within seed noise with no consistent sign. This does not
   show that the endpoint cells cannot be driven; it shows this TuBu input does
   not drive them.

## Evidence and identity

- Runner: `scripts/audit_reached_subset.py`
- Raw: `camber-runs/diag/reached-subset/` (`plan.json`, `seed-1.json` to
  `seed-10.json`, `run.log`)
- Committed record: `validation/records/p2/tubu-reached-subset.json`
- Executed source: `3adfff7d0ddf9f212221991a06fc1803852e8aef`
- Executed runner SHA-256:
  `7056911dfd00b3a608e5d51e7b6327206cd839f2a4a5efe50c7d6a5d56caf84d`
  (from the raw files). The committed runner
  (`8b334601647d09f2323adb647d58b6d651730239aadb957d41649b1d9484caef`) adds
  nine read-only summary fields to `summarize` after the run; the `plan` and
  `run` paths are byte for byte the executed ones.
- Probe: 10 seeds x 2 conditions x 20 s = 400 brain-seconds, Oracle
  `linux-aarch64`, plain `lif`, 8 workers, class `development`
- Declared substrate: `rest:379cc4cc9030cdd1`; no canonical data file or
  substrate was changed

The record binds the source and input hashes, the connectome hashes, the plan
hash, and every raw file hash, and holds every per-cell and per-seed value
rather than a population summary.
