# MaleCNS v1.0 port: data and adapter

> **Current status (25 September 2026):** Historical port stages from 21–22 September 2026 precede the adopted MaleCNS substrate `rest:ed9b0a469d7a6b77` and filled male drive/dopamine tables. See [adoption below](#starting-substrate-port-step-6-item-155), the [first-study design](adhd-study-design.md) and the [confirmation design](adhd-confirm-design.md). Frozen parameter and engine source notes have a [provenance erratum](errata.md).

This first implementation step established MaleCNS as a separate substrate
named `male-cns:v1.0`, never using the FlyWire `783` label. It installed the
released flat data, defined the canonical loader boundary, applied the no-cut
edge rule and per-neuron T-bar sign rule, and showed that the unchanged
point-neuron engine could build and step the graph. This step did not yet
define MaleCNS populations or compartments or calibrate the male tables; later
sections document those changes. **The fly does not see.**

## Port step 5 Part A: frozen value classification

Part A was committed before any MaleCNS dopamine table or registry matrix was
built. Its exhaustive, leaf-by-leaf record is
[`malecns-dopamine-classification.json`](../validation/records/p2/malecns-dopamine-classification.json).
The table below groups those leaves without changing their class. **Anatomy** is
rebuilt from MaleCNS memberships or connectivity by the same rule;
**declared** values are literature, placeholder, ontology, threshold, schema or
design constants independent of graph outcomes and retain their source; and
**calibrated** values were fitted or selected on the FlyWire substrate and are
left explicitly unset for port step 7. Under the frozen rule, Part B could not
move a value after looking at an output.

| source paths | class | Part B rule |
|---|---|---|
| `compartments`: compartment names, CX names, Aso/Li MBON and DAN type maps, bilateral prefixes, KC lobe rule, citations and notes | declared | Carry the same named-compartment and type rules. |
| `compartments`: unplaced types, `cxdan` inventories/fractions/exclusions and target-mask totals | anatomy | Re-enumerate or recompute on MaleCNS. |
| `receptors`: every version, precedence, density, source and note | declared | Carry the cited or explicitly placeholder density rule, then expand over MaleCNS memberships. |
| `transmitters`: version, scope, `g_his` and class-code vocabulary | declared | Carry the same rule. |
| `transmitters`: release identities, engine count, packed classes/hash/counts, disagreements and mixed-sign audit | anatomy | Rebuild in MaleCNS engine order from its annotations and released transmitter/sign evidence. |
| `dopamine`: version links, compartment order and all kinetic constants | declared | Carry with their existing source; compartment names remain the declared ontology. |
| `dopamine`: connectome identity | anatomy | Name MaleCNS v1.0. |
| `dopamine`: every `R_c`, `alpha_c`, `S_c`, mode, drive binding and K2r provenance | calibrated | Set to YAML `null`; step 7 reruns K2r. |
| `drive`: schema, transmitter scope, unknown-sign convention, `g_his`, `n_bg` and `r_bg` | declared | Carry as release-independent design constants. |
| `drive`: transmitter blob and every group size | anatomy | Rebind to the MaleCNS transmitter table and population inventories. |
| `drive`: `g_gaba`, `g_glu`, `g_gaba_kc`, scale hash, every group `w_bg`, threshold selection, optic exemption, mechanism selection and provenance | calibrated | Set to YAML `null`; step 7 selects/calibrates them on MaleCNS. |
| `params`: `bg.w_bg`, `da.alpha_c`, drive scale/weight pointers, calibrated forward speed and steering/sign values, and `vis.pr_rate_light_hz` | calibrated | Do not transfer the FlyWire-fitted value or pointer. Step 6/7 owns the replacement. |
| `params`: every other leaf, including LIF/kinetic constants, receptor placeholders, thresholds, grids, bounds, criteria and planning constants | declared | Carry its recorded source when step 6 mints the MaleCNS parameter version. A criterion is not anatomy merely because an older result motivated it. |

The exhaustive record covers every scalar/list leaf in the six source files and
stores the old value only as classification evidence. A MaleCNS table never
uses a calibrated old value as a fallback.

### NO laterality rule frozen before Part B

MaleCNS labels the protocerebral bridge and fan-shaped/ellipsoid bodies in the
needed form, but its `NO` ROI is unsided. This port keeps the declared
`NO_L`/`NO_R` compartments. Each `syn-partners` row whose `primary_post` is
`NO` is assigned by the **postsynaptic cell's canonical side** (`somaSide`, then
`rootSide`): left to `NO_L`, right to `NO_R`, and an absent side split 0.5/0.5.
The CX_DAN filter still counts every `NO` row in its central-complex numerator,
so this is the same item-152 keep/drop rule. The same per-synapse split builds
the innervation matrix. This uses target anatomy rather than a model outcome;
a target with no side carries no evidence for either side.

## Cached release data

The authoritative machine-readable inventory is
[`data/malecns-v1.0-manifest.json`](../data/malecns-v1.0-manifest.json). All seven
flat tables are in the shared ignored cache `.cache/malecns-v1.0/`, totaling
24,377,419,334 bytes. Each manifest row carries the official URL, byte size,
SHA-256, purpose, CC BY 4.0 license and attribution.

The cache includes neuron annotations (including `assignedOlHex1/2`), per-neuron
transmitter consensus, body statistics, aggregate connectivity, synaptic partner
pairs with `primary_post` ROI, synapse points with encompassing ROIs, and
per-T-bar transmitter probabilities. The T-bar table now provides one output
sign per unknown-consensus neuron, as item 150 requires; the partner table
audits the superseded per-pair interpretation. This leaves later population
work enough evidence to revisit `CX_DAN`, the unresolved sugar-reflex source,
compartment assignments and the 254 same-name MaleCNS ER candidates plus 28 ER1
candidates.

Raw EM imagery and segmentation are omitted because the model never reads them.
The manifest also records but does not download the official skeleton and mesh
collections for later figures and a demo, with formats, object counts and total
sizes. Native meshes alone are about 756 GB, so they are explicitly visual
assets rather than model dependencies.

## Adapter and canonical schemas

`flyonenomics.datasets.DatasetAdapter` is the only release-specific boundary.
The FlyWire adapters return the historical files and columns unchanged. The
MaleCNS adapter converts official source names into three ignored derived files:

- `derived/annotations.feather`: one typed, traced neuron per row, with the
  registry's canonical column names plus the MaleCNS source identity, direct eye
  columns, transmitter labels and confidence fields;
- `derived/engine-order.csv`: `root_id` (`bodyId`) in official annotation-table
  order;
- `derived/connectivity.parquet`: `Presynaptic_ID`, `Postsynaptic_ID`,
  `Connectivity`, `Presynaptic_Index`, `Postsynaptic_Index`, and signed
  `Excitatory x Connectivity`.

`derived/provenance.json` travels with those tables. It includes all source and
derived SHA-256 values, attribution, exact conversion policy, row counts and
synapse counts. The per-neuron correction is policy `male-cns-adapter-v3`; a
changed source or policy causes regeneration rather than an old-format fallback.

The frozen conversion choices are:

1. nodes have `status == Traced` and a non-null MaleCNS `type`;
2. every globally aggregated directed pair whose endpoints are nodes is kept;
   there is no weight cut, matching the FlyWire loader;
3. the official `minconf-0.5` tables set the synapse confidence boundary; there
   is no second confidence cut on official `consensus_nt`;
4. presynaptic acetylcholine, dopamine, serotonin, octopamine and tyramine are
   positive; GABA, glutamate and histamine are negative;
5. for an unclear or missing consensus, the largest of the seven transmitter
   probabilities labels each of the neuron's released T-bars. One sign applies
   to all of that neuron's output: negative only when more than half of all its
   sites are GABA or glutamate. Other winners and exact ties are positive. Every
   edge is therefore signed; there is no zero-weight shortcut;
6. laterality is `somaSide`, then `rootSide`; `L` and `R` become `left` and
   `right`, and unknown stays missing.

The resulting graph has 162,517 neurons, 25,120,209 retained and signed directed
edges, zero zero-weight edges, and 122,181,879 represented synapses. The 2,529
unknown-consensus neurons have 866,912 released T-bars: 1,685 neurons are
positive, 769 are negative, and 75 have no T-bars. Of the 2,454 classified
neurons, 2,435 supply 560,785 directed pairs; the other 19 and the 75 without
T-bars have no retained output. Compared with the superseded per-pair rule,
89,519 pairs change sign and 2,022 neurons would have mixed output signs.

## Review comparisons and named differences

### FlyWire is unchanged

The FlyWire adapters resolve the same cached files as the pre-adapter code. The
item-150 candidate reloaded and SHA-256 hashed every 630 and 783 engine array;
all eight hashes match the hashes recorded on `main` before the MaleCNS adapter
and after step 1:

| version | engine array | shape | SHA-256 on both revisions |
|---|---|---:|---|
| 630 | root IDs | 127,400 | `a659694cfe091ac64f31cdbeff270a914ee27168b06f7b4068d2781c4beea0e6` |
| 630 | presynaptic indices | 14,687,178 | `50e4a0ca5767dd429512d1cc7a6be7786aa907649cc866e4c0056323d3c9d750` |
| 630 | postsynaptic indices | 14,687,178 | `54a3ce131f7268bee223408bba87e76a14ed8f23e6784a9ff880c6715787de1d` |
| 630 | signed weights | 14,687,178 | `790d7925a908265bda5fca8357af6a077d3b39d4b9386e76f8aa85a4c759869b` |
| 783 | root IDs | 138,639 | `70200482b9fe6656f215a97b71332dd6725b80e2cb32e0052a4d47916ca1579b` |
| 783 | presynaptic indices | 15,091,983 | `8ec65c761057a2b000dcc246d6dc94a586b31596b8331c1db1ada61691d67f17` |
| 783 | postsynaptic indices | 15,091,983 | `302786e9dacecf6f04683f7e46a6c3aa223b136b42b44880ccae0f0487dcd5f3` |
| 783 | signed weights | 15,091,983 | `8ddd4ff45983bd9855ffa01ad5099ccdbd138bc9eb8d6cc2cb2433d01ca18a49` |

The v783 source files also retain their pinned hashes: completeness
`bbb847a4cc2caaa7a16349722d220c087317b946d148d4d592d94d250617a311`
and connectivity
`efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347`.

### Edge-rule parity and before/after counts

The FlyWire engine does no runtime thresholding or grouping: it loads every row
in Shiu's prebuilt v783 parquet. That file has **15,091,983 globally aggregated
directed body pairs** (the pre/post pair is unique; there is no neuropil column),
its minimum `Connectivity` is one, and 7,496,016, 2,679,736, 1,379,004 and
836,714 rows have weights one through four. MaleCNS now applies that same
no-additional-cut rule to its typed/traced nodes. The 18,981,831 restored rows
comprise 10,102,544 weight-one, 4,675,450 weight-two, 2,575,041 weight-three and
1,628,796 weight-four pairs.

| conversion | edges | signed edges | zero-weight edges | represented synapses |
|---|---:|---:|---:|---:|
| step 1, weight ≥5 and unknown zeroed | 6,138,378 | 6,049,915 | 88,463 | 88,488,128 |
| item 150, no cut and per-neuron T-bar signs | 25,120,209 | 25,120,209 | 0 | 122,181,879 |

These values and the exact source and derived hashes are also in ignored
`derived/provenance.json`; changing either of the two newly consumed source
files invalidates the conversion cache.

### Sign and unknown-transmitter policy

For named consensus transmitters, polarity agrees with the constants the
FlyWire substrate applies in code: acetylcholine, dopamine, serotonin,
octopamine and tyramine are positive; glutamate, GABA and histamine are
negative. Tyramine is now explicit even though no retained MaleCNS row currently
has that consensus label.

The FlyWire path was checked at both layers. Its current substrate has 1,747
`unk` neurons; 1,617 supply 73,881 engine edges, and `scale_array` preserves the
pinned nonzero `Excitatory` sign on every such row. The parquet has no
presynaptic neuron with mixed row signs. Shiu et al.'s published construction
first chose the largest predicted transmitter at each presynaptic site, then
made a neuron inhibitory only when **more than half** of all its sites were GABA
or glutamate; dopamine, octopamine and serotonin were positive. Thus “pinned
per-connection sign” describes where the sign is stored and consumed, not a
mixed-sign FlyWire neuron.

Item 150 applies that same site-winner and strict-majority operation once per
MaleCNS unknown-consensus neuron, over all of its released T-bars, and applies
the result to every outgoing pair. The initial per-pair interpretation would
have given 2,022 neurons mixed signs and differs on 89,519 of the 560,785 pairs;
it is not FlyWire parity and was removed in review. The `syn-partners` join is
retained only to report that comparison and to prove every output-bearing
unknown neuron has T-bar evidence. This removes the prior 88,463 zero rows and
does not invent a consensus transmitter label for those neurons.

### Node exclusions and result-critical candidates

The release annotation table has 211,577 body rows, including non-neuronal and
unfinished statuses; 165,122 are `Traced`. The adapter retains the 162,517
traced rows with a non-null `type`, so it drops **2,605 traced but untyped rows**
and **49,060 rows in total**. The often quoted roughly 166,691-neuron release
count is not an exact denominator encoded by this table, so it is not used to
hide the status split.

All named, typed candidates used by the feasibility audit survive the filter:
282 ER-family cells (254 ER2–ER6 plus 28 ER1), 38 named `CX_DAN` candidates, 156
TuBu, 1,009 MeTu, 13,580 T4/T5, 44 H2/HS/VS, four DNa02/DNae001, 439 typed
leg/wing motor neurons, and both MN9 cells. There is one boundary to carry
forward: nine additional `Traced` rows have broad `vnc_motor` leg/wing class
labels but no `type` (eight leg, one wing), so the typed-node rule excludes them.
They were not members of the feasibility audit's named motor candidate set;
the later population ruling must decide whether broad untyped motor rows belong.

## Dark build check

`scripts/malecns_probe.py` selected `male-cns:v1.0` through the production
adapter, loaded unchanged `data/params-v0.2.yaml`, built the Brian LIF engine,
and stepped 1.0 s at 0.1 ms with seed 20260921 and no input.

| measure | step 1 Mac, 6.1M edges | item 150 Mac, 25.1M edges | item 150 box, 25.1M edges |
|---|---:|---:|---:|
| engine build wall time | 2.408 s | 3.342 s | 6.884 s |
| 1 s run wall time | 7.917 s | 8.417 s | 26.159 s |
| process peak RSS | 764,411,904 bytes (729.00 MiB) | 2,048,557,056 bytes (1,953.66 MiB) | 1,748,860,928 bytes (1,667.84 MiB) |
| spikes / firing neurons | 0 / 0 | 0 / 0 | 0 / 0 |

Both item-150 checks used Python 3.12.14, the Brian Cython backend, seed 20260921,
unchanged `params-v0.2.yaml`, and no input. The Mac was arm64 macOS 27.0.0; the
box was aarch64 Linux 6.17.0-1020-oracle. `/usr/bin/time` measured 3,017,480 KiB
for the entire first box command because the missing array cache was built in a
child; the comparable probe-process peak above excludes that child, as did the
step-1 measurement. This is a compatibility and cost measurement only. Zero
input and rest initialization make zero spikes expected; it says nothing about
vision, resting-state calibration or behaviour.

## Population registry

Port step 3 adds [`data/populations-male-cns-v1.0.yaml`](../data/populations-male-cns-v1.0.yaml).
The `male-cns:v1.0` adapter selects that file explicitly; it cannot fall through
to either FlyWire registry. All 142 FlyWire population names have a MaleCNS row,
a measured MaleCNS inventory and explicit laterality (`side: null` means all
annotated sides under the recorded `somaSide`, then `rootSide` rule). The
selectors apply the FlyWire biological rule to the corresponding official
MaleCNS columns. Vocabulary translations—such as `descending` to
`descending_neuron`, and `motor` to typed `vnc_motor` plus `cb_motor`—are stated
per row. These choices were made from labels and anatomy before any firing or
other model outcome. The complete cell-level audit is
[`validation/records/p2/malecns-populations.json`](../validation/records/p2/malecns-populations.json).

### Ring and central-complex dopamine sets

The broad `ER` registry rule remains `^ER\\d`, producing 282 cells. The traced
ring set used by the FlyWire experiments had a narrower anatomical rule: an ER
cell had at least one direct aggregate TuBu pair. Applying that rule on the
item-150 all-pairs graph gives **245 kept and 37 dropped**. The dropped cells are
all 28 ER1 candidates and nine ER3a candidates; the audit lists all 282 body IDs,
types, sides and reasons. A fresh reference calculation found 228 of 278 FlyWire
ER cells under the same rule: all 29 FlyWire ER1 cells were dropped, along with
21 cells of five other ER types. Thus neither the FlyWire count nor a model
response chose the male set.

The MaleCNS anatomical bridge yields 38 named candidates in types ExR2, FB1C,
FB1H, FB2A, FB4L, FB4M, FB5H and PPM1201–1205. `CX_DAN_candidates` retains the
36 with official dopamine consensus; the two PPM1204 cells are excluded because
their official consensus transmitter is glutamate. This maps the different MaleCNS type vocabulary by stated anatomy,
not by string count. The source is Berg et al. 2026, *Cell*, DOI
[`10.1016/j.cell.2026.08.015`](https://doi.org/10.1016/j.cell.2026.08.015), and
the checksummed official release annotation and transmitter tables in the
manifest.

The v783 threshold is then repeated over the same seven conceptual
central-complex compartments. MaleCNS `primary_post` labels represent these as
`EB`, `PB`, `FB`, unsided `NO`, `LAL(L)` and `LAL(R)`. For each candidate, rows
in those ROIs are divided by all outgoing `syn-partners` rows, and a fraction at
least **0.2** is kept. This retains **27 of the 36 dopamine candidates**.
Presynaptic `primary` ROI counts from `syn-points` independently accompany every
candidate in the audit.

This is the closest released-ROI analogue, not an identical numerator. FlyWire
weights aggregate pairs by the postsynaptic cell's compartment-targeting row;
MaleCNS instead counts each released partner synapse by its own postsynaptic
primary ROI. The rule, every candidate fraction and all ROI counts are explicit
in the audit. Compartment matrices and dopamine parameters remain deliberately
out of scope for this step.

### Reflex and motor identities

There is **no clean MaleCNS sugar source**. The release types 161 traced
labellar-bristle gustatory cells entering through MxLbN, but none has a sugar
modality or `receptorType`. Its `flywireType` field is a type-level homology
label, not a root-level FlyWire cross-match. The audit also retains the 60
taste-peg cells considered by the first pass, but they are not a substitute for
Shiu's labellar sugar-sensing source. The registry therefore leaves
`sugar_GRN_R` empty rather than selecting by count or model response. Port step
7 has no sugar-reflex source until one is established. The same no-identity
rule leaves the explicit FlyWire bitter source empty.

MaleCNS has bilateral MN9 cells on the pharyngeal nerve. The FlyWire source is
right-sided, so the stated type-plus-side-plus-nerve rule selects right MN9 body
16949 and drops left body 10331. This is not selected by whether either cell
fires.

The typed-node graph contains **373 leg** motor neurons (`vnc_motor`, subclasses
`fl`, `ml` or `hl`) and **66 wing** motor neurons (`vnc_motor`, subclass `wm`).
The audit lists every body ID, released type, side, subclass and exit nerve.
Nine additional traced rows have broad `vnc_motor` evidence but no released
`type`: eight leg and one wing. They stay excluded because the adapter's frozen
node rule requires a non-null type; broad class alone does not establish a named
motor identity. All nine rows and their side, subclass and exit-nerve evidence
are retained in the audit.

The registry and audit were rebuilt after merging item 150. They require
`male-cns-adapter-v3` with 162,517 nodes and all 25,120,209 pairs; population and
ER membership do not read connection signs. FlyWire registry selection and its
engine arrays remain unchanged, while `male-cns:v1.0` resolves only to the male
registry.

This step defines anatomy only. It does not build compartment matrices, receptor
exposures, dopamine or drive parameters, and it calibrates nothing. **The fly
does not see.**

## Dopamine compartments and uncalibrated tables

Port step 5 adds five dataset-specific files:

- [`compartments-male-cns-v1.0.yaml`](../data/compartments-male-cns-v1.0.yaml),
- [`receptors-male-cns-v1.0.yaml`](../data/receptors-male-cns-v1.0.yaml),
- [`transmitters-male-cns-v1.0.yaml`](../data/transmitters-male-cns-v1.0.yaml),
- [`dopamine-male-cns-v1.0.yaml`](../data/dopamine-male-cns-v1.0.yaml), and
- [`drive-male-cns-v1.0.yaml`](../data/drive-male-cns-v1.0.yaml).

The reproducible builder is
[`scripts/malecns_dopamine_tables.py`](../scripts/malecns_dopamine_tables.py),
and the cell/compartment-level audit is
[`malecns-dopamine-tables.json`](../validation/records/p2/malecns-dopamine-tables.json).
It reads the checksum-verified MaleCNS release through the adapter and does not
run the engine.

### Membership and ROI rules

The 30 mushroom-body compartments retain the Aso et al. 2014 / Li et al. 2020
hemibrain-style type rules and equal splits. MaleCNS DAN types `PPL107`,
`PPL108`, and `PPL201`–`PPL204` have two cells each and remain unplaced for the
same cited anatomical reasons as FlyWire. Of four source-type `MBON25-like`
cells, three carry the exact released `flywireType` `MBON25,MBON34`, an existing
Aso/Li table key, and now use that key; root 76585 has no exact alternate type
and remains unplaced. The broad MaleCNS KC type `KC` has two cells. Neither has
a `flywireType` or subclass, and their released synapse points identify only
the calyx (`CA`), not a gamma, alpha/beta or alpha-prime/beta-prime lobe, so
both remain unplaced. If a lobe were known, placing them would add only two
exposed cells and ten W nonzeros; it does not explain the 651-cell and 5,134-
nonzero male deficits. `KCg` does match the frozen `^KCg` rule and is placed
across the five gamma compartments. The audit records every count, root and
matrix effect.

The `CX_DAN` filter is exactly the item-152 per-synapse rule: for each of the 36
dopamine candidates, count released `syn-partners` rows whose `primary_post` is
`EB`, `PB`, `FB`, `NO`, `LAL(L)` or `LAL(R)` and divide by every outgoing
partner row. The threshold remains the declared 0.2 and keeps the same 27
cells. The matrix differs from FlyWire by construction: FlyWire weights an
aggregate partner pair through that target cell's declared W row, while
MaleCNS assigns each released synapse from its own `primary_post` ROI. Unsided
`NO` rows use the frozen postsynaptic-side rule above in both W/M construction
and the audit; keeping all `NO` rows in the numerator preserves the filter.

The drive table translates MaleCNS's regional superclass vocabulary into the
same 12 conceptual drive groups before the existing DAN/`CX_DAN`, KC and ER
overrides. This is an anatomy vocabulary rule, not a fitted grouping.

| MaleCNS superclass | conceptual group | cells |
|---|---|---:|
| `ascending_neuron` / `efferent_ascending` | ascending | 1,841 / 8 |
| `descending_neuron` / `efferent_descending` | descending | 1,310 / 4 |
| `cb_intrinsic` / `vnc_intrinsic` | central | 31,280 / 12,966 |
| `ol_intrinsic` | optic | 89,353 |
| `cb_endocrine` / `vnc_endocrine` | endocrine | 65 / 22 |
| `cb_motor` / `vnc_motor` / `cb_efferent` / `vnc_efferent` | motor | 106 / 699 / 4 / 78 |
| `cb_sensory` / `ol_sensory` / `vnc_sensory` | sensory | 4,756 / 4,114 / 5,605 |
| `sensory_ascending` / `sensory_ascending_tbc` / `sensory_descending` | sensory | 528 / 1 / 12 |
| `visual_centrifugal` | visual_centrifugal | 562 |
| `visual_projection` / `visual_projection_tbc` | visual_projection | 9,201 / 2 |

Population overrides then produce these final rows:

| drive group | MaleCNS | FlyWire v783 |
|---|---:|---:|
| DAN | 367 | 361 |
| ER | 282 | 278 |
| KC | 4,064 | 5,177 |
| ascending | 1,849 | 2,317 |
| central | 39,533 | 26,568 |
| descending | 1,314 | 1,299 |
| endocrine | 87 | 76 |
| motor | 887 | 106 |
| optic | 89,353 | 77,529 |
| sensory | 15,016 | 16,351 |
| visual_centrifugal | 562 | 524 |
| visual_projection | 9,203 | 8,053 |

### Structural comparison

| structural quantity | MaleCNS v1.0 | FlyWire v783 |
|---|---:|---:|
| neurons | 162,517 | 138,639 |
| compartments | 37 | 37 |
| W exposure shape / nonzeros | 162,517 × 37 / 24,454 | 138,639 × 37 / 29,588 |
| M innervation shape / nonzeros | 37 × 162,517 / 452 | 37 × 138,639 / 465 |
| cells with a nonzero W row | 8,074 | 8,725 |
| cells with any nonzero receptor density | 5,102 | 6,152 |
| cells both exposed and receptor-positive | 5,085 | 6,138 |
| r1 / r2 / rq nonzero cells | 5,075 / 4,950 / 4,064 | 6,122 / 5,999 / 5,177 |

The audit gives all 37 compartment inventories beside one another. Male W, M
and receptor-array hashes are respectively `92dfe339…`, `95a20a60…` and
`4c41c55b…`. Both FlyWire population registries still produce the same W, M,
receptor and root-order hashes (`f775933b…`, `d7b04ce…`, `071f4c28…`,
`70200482…`), all eight 630/783 engine-array hashes remain the item-150 values,
and the packed v783 transmitter hash remains `097100ec…`.

The MaleCNS transmitter table has 162,517 engine-order classes: 102,576 ACh,
29,104 Glu, 21,868 GABA, 4,028 His, 541 modulatory and 4,400 `unk`. Here `unk`
is the model's transmitter **class**: no curated classical/modulatory assignment
and no named class under the released presynaptic sign. It is not an unsigned
edge. Of those cells, 3,556 have output and all use nonzero item-150 signs; 844
have no retained output. Separately, the adapter found 2,529 unknown-consensus
neurons: 1,685 positive, 769 negative and 75 with no T-bar prediction. The 75
have no retained output (an output edge would make the adapter fail), and all
25,120,209 retained engine edges have nonzero signed weight. Receptor densities
and their precedence are the same declared placeholders, expanded on the male
memberships; this is not new receptor-expression evidence.

At this pre-adoption port stage, every graph-selected value was visibly absent
rather than copied. The dopamine table had `null` for all 37 `R_c`, `alpha_c`,
`S_c` and mode rows and for its drive/K2r binding. The drive table had measured
group sizes but `null` scales, background weights, threshold selection, optic
exemption, mechanism and calibration record. `null` meant **unset at that
stage**, never zero and never a fallback to FlyWire. The dopamine and drive
loaders rejected those unset tables explicitly. No resting, visual, steering or
behavioural calibration had run at that stage. The sugar source is still absent,
the eye seam is still partial, and **the fly does not see**.

## Eye assignment

[`data/eye-assignment-male-cns-v1.0.parquet`](../data/eye-assignment-male-cns-v1.0.parquet)
is the versioned cell-level assignment. It has one row for each of the 162,517
typed, traced MaleCNS graph cells, including cells outside flyvis's 65 types.
Each candidate row carries the flyvis alias, eye, native hex, direct or
wiring-inferred method, confidence, winning and eligible evidence weights, tie
count, proposed flyvis coordinate, collision counts, and an unresolved reason.
The complete machine-readable account is
[`validation/records/p2/malecns-eye-assignment.json`](../validation/records/p2/malecns-eye-assignment.json).

### Rules fixed before outcomes

The assignment applies these rules without inspecting a visual, steering or
behavioural result:

1. keep `status == Traced` cells with a non-null MaleCNS type;
2. use **all 25,120,209** released aggregate pairs between those cells, including
   weights one through four, as required by SPEC-P2 item 150;
3. take a cell's direct `assignedOlHex1/2`; otherwise take the hex receiving the
   greatest aggregate incoming weight from directly labelled partners;
   otherwise use outgoing weight;
4. record the lowest `(hex1, hex2)` pair for deterministic output when the
   winning weight is tied, but keep that inference unresolved;
5. use `somaSide`, then `rootSide`, only to select the eye; never use soma or
   centroid XYZ;
6. call a transformed type-position usable only when exactly one concrete
   MaleCNS cell occupies it and its wiring evidence has one winning coordinate.

Direct confidence is 1. For a wiring inference it is the winning coordinate's
aggregate weight divided by all eligible directly labelled partner weight in
that chosen direction. This is evidence concentration in this release, not a
biological probability. `top_tie_count` exposes tied winners; all 1,867 tied
inferences remain unresolved even though the lowest-pair rule makes the artifact
deterministic.

`R1-R6` is retained in the artifact but unresolved: one shared MaleCNS identity
cannot identify flyvis R1, R2, R3, R4, R5 and R6 separately. The two MaleCNS
`CT1` cells likewise do not identify flyvis's `CT1(Lo1)` and `CT1(M10)`
compartments. No compatibility fallback invents those identities.

### Change from the feasibility graph

The lane's deterministic lowest-pair calculation reproduced its reported
all-pairs totals: 18,372 left, 19,339 right and 12,432 type-position slots unique
in both eyes. Review found that 1,867 wiring inferences had tied winning
coordinates, so those assignments cannot be called unique. With ties explicitly
unresolved, keeping every pair changes the feasibility totals from 17,593 to
**17,807** left slots (+214), from 18,918 to **18,999** right slots (+81), and
from 11,994 to **12,089** slots unique in both eyes (+95).

The change is not monotone by type: weak pairs can place a previously unresolved
cell, change which coordinate has greatest aggregate weight, introduce a tie,
or create/remove a rounded-coordinate collision. The record contains every
per-type before/after value. The assignment reads aggregate IDs and weights but
no connection signs, so the adapter-v3 sign correction cannot affect it.

### Mapping onto flyvis's lattice

The geometry-only proposal converts native axial hexes to Cartesian coordinates,
centres each eye on the centroid of its inferred T4/T5 columns, rotates the mean
wiring-derived R7d/R8d dorsal-rim vector upward, applies the prior
`FRONT_SIGN=-1`, and rounds back to flyvis's radius-15 axial lattice. The left
has 875 native inferred motion columns, of which 767 map inside the lattice;
the right has 887, of which 774 map inside. Rounding gives 665 distinct inside
positions on the left and 676 on the right. The nearest native column to each
fractional centroid is `(19, 20)`; it is recorded, not declared a biological
reference.

Three free choices remain explicit: the anatomical orientation source, a
biological reference column rather than a fractional centroid, and whether the
left eye is mirrored. The artifact records the DRA-up, no-left-mirror proposal.
A later anatomy source may replace it. A downstream firing or behavioural
outcome may not choose among transforms, so nothing is fitted here.

### Coverage by type and eye

Each compact cell is `D/I/U/C/X`: directly placed MaleCNS cells, inferred
MaleCNS cells, unique drivable flyvis slots, MaleCNS cells in colliding slots,
and unresolved flyvis slots. `U + X` is 721, except Lawf1/Lawf2 where it is 123.
Direct and inferred counts can exceed slot counts because the two lattices are
not one-to-one.

| type | left D/I/U/C/X | right D/I/U/C/X |
|---|---:|---:|
| R1 | 0/498/0/0/721 | 0/888/0/0/721 |
| R2 | 0/498/0/0/721 | 0/888/0/0/721 |
| R3 | 0/498/0/0/721 | 0/888/0/0/721 |
| R4 | 0/498/0/0/721 | 0/888/0/0/721 |
| R5 | 0/498/0/0/721 | 0/888/0/0/721 |
| R6 | 0/498/0/0/721 | 0/888/0/0/721 |
| R7 | 0/557/375/116/346 | 0/701/468/163/253 |
| R8 | 0/624/410/145/311 | 0/702/479/151/242 |
| L1 | 875/9/563/207/158 | 892/0/580/194/141 |
| L2 | 874/12/562/207/159 | 893/0/579/196/142 |
| L3 | 0/880/484/274/237 | 892/0/580/194/141 |
| L4 | 0/878/239/491/482 | 0/891/275/482/446 |
| L5 | 875/14/559/216/162 | 898/0/576/203/145 |
| Lawf1 | 0/177/19/0/104 | 0/184/22/6/101 |
| Lawf2 | 0/195/24/4/99 | 0/188/27/0/96 |
| Am | 0/0/0/0/721 | 0/0/0/0/721 |
| C2 | 0/871/545/216/176 | 874/0/571/192/150 |
| C3 | 878/9/561/212/160 | 892/0/577/197/144 |
| CT1(Lo1) | 0/1/0/0/721 | 0/1/0/0/721 |
| CT1(M10) | 0/1/0/0/721 | 0/1/0/0/721 |
| Mi1 | 875/11/559/215/162 | 887/0/577/196/144 |
| Mi2 | 0/494/323/127/398 | 0/492/299/145/422 |
| Mi3 | 0/0/0/0/721 | 0/0/0/0/721 |
| Mi4 | 869/14/558/209/163 | 889/0/579/194/142 |
| Mi9 | 871/15/558/212/163 | 889/0/580/194/141 |
| Mi10 | 0/222/156/22/565 | 0/222/170/14/551 |
| Mi11 | 0/0/0/0/721 | 0/0/0/0/721 |
| Mi12 | 0/0/0/0/721 | 0/0/0/0/721 |
| Mi13 | 0/457/261/122/460 | 0/453/297/105/424 |
| Mi14 | 0/160/85/28/636 | 0/155/112/14/609 |
| Mi15 | 0/569/385/137/336 | 0/581/398/134/323 |
| T1 | 872/13/558/212/163 | 892/0/578/196/143 |
| T2 | 0/808/292/408/429 | 0/822/324/398/397 |
| T2a | 0/932/303/521/418 | 0/939/314/517/407 |
| T3 | 0/964/378/504/343 | 0/976/343/551/378 |
| T4a | 0/835/421/313/300 | 0/849/421/320/300 |
| T4b | 0/844/419/332/302 | 0/846/440/314/281 |
| T4c | 0/895/420/367/301 | 0/883/439/341/282 |
| T4d | 0/850/431/318/290 | 0/859/449/313/272 |
| T5a | 0/825/454/268/267 | 0/838/454/281/267 |
| T5b | 0/863/447/318/274 | 0/852/460/296/261 |
| T5c | 0/862/418/354/303 | 0/858/407/366/314 |
| T5d | 0/812/407/325/314 | 0/808/418/308/303 |
| Tm1 | 877/10/560/212/161 | 890/0/579/194/142 |
| Tm2 | 875/8/563/207/158 | 883/0/578/196/143 |
| Tm3 | 0/1017/299/615/422 | 0/1037/293/644/428 |
| Tm4 | 0/837/325/403/396 | 833/0/547/198/174 |
| Tm5Y | 0/435/291/90/430 | 0/463/313/90/408 |
| Tm5a | 0/315/233/50/488 | 0/307/233/47/488 |
| Tm5b | 0/260/209/18/512 | 0/262/205/31/516 |
| Tm5c | 0/374/179/84/542 | 0/374/282/36/439 |
| Tm9 | 856/28/554/216/167 | 887/0/578/197/143 |
| Tm16 | 0/199/132/24/589 | 0/197/136/26/585 |
| Tm20 | 856/30/548/226/173 | 876/0/565/210/156 |
| Tm28 | 0/0/0/0/721 | 0/0/0/0/721 |
| Tm30 | 0/60/30/9/691 | 0/60/29/4/692 |
| TmY3 | 0/415/317/59/404 | 0/409/312/60/409 |
| TmY4 | 0/274/175/45/546 | 0/288/204/40/517 |
| TmY5a | 0/686/336/281/385 | 0/678/399/221/322 |
| TmY9 | 0/0/0/0/721 | 0/0/0/0/721 |
| TmY10 | 0/274/179/40/542 | 0/278/186/34/535 |
| TmY13 | 0/221/171/12/550 | 0/211/163/18/558 |
| TmY14 | 0/243/163/44/558 | 0/234/188/18/533 |
| TmY15 | 0/99/72/2/649 | 0/110/91/2/630 |
| TmY18 | 0/673/297/310/424 | 0/694/325/318/396 |

### Motion seam

T4a-d and T5a-d have no direct MaleCNS hex rows; every placement is inferred.
The motion seam could drive the following fractions under the provisional
transform:

| type | left unique / 721 | left fraction | right unique / 721 | right fraction | unique in both eyes |
|---|---:|---:|---:|---:|---:|
| T4a | 421 | 58.4% | 421 | 58.4% | 263 |
| T4b | 419 | 58.1% | 440 | 61.0% | 290 |
| T4c | 420 | 58.3% | 439 | 60.9% | 275 |
| T4d | 431 | 59.8% | 449 | 62.3% | 290 |
| T5a | 454 | 63.0% | 454 | 63.0% | 315 |
| T5b | 447 | 62.0% | 460 | 63.8% | 311 |
| T5c | 418 | 58.0% | 407 | 56.4% | 256 |
| T5d | 407 | 56.4% | 418 | 58.0% | 266 |

Across all 45,669 flyvis type-position slots, one MaleCNS cell could drive
38.99% on the left and 41.60% on the right; 26.47% are unique in both eyes.
These are assignment fractions, not response rates. Nothing here is calibrated,
and the fly does not see.

## Starting substrate (port step 6, item 155)

Rolf declared the male starting brain at item 122's settings, unchanged:
sensory-only background **1.0 mV**, `g_gaba=1`, `g_glu=4`, `g_his=1`,
`g_gaba_kc=6`, no optic exemption, no threshold spread, plain `lif`.
`data/drive-male-cns-v1.0.yaml` now contains those settings and male group
sizes. No setting was selected by a male firing outcome. Here `threshold:
null` and `mechanisms: null` deliberately select no spread and plain `lif`;
they are not unfilled calibration entries.

`data/dopamine-male-cns-v1.0.yaml` now adopts the mean of the **recorded**
K2r rows for seeds 1–3 (2 s settle + 5 s each). The raw seed files were
verified against t-0069's committed hashes before extracting
`malecns-k2r-measurement.json`. The generator calls WP19's
`rest_release_constants`, rather than copying the chain's numbers. All 37
`R_c`, `alpha_c`, `S_c` and mode entries exactly equal the computed chain in
`malecns-rest.json`; the dopamine document binds the new male drive blob.
The loaders accept the filled male tables and reject remaining null numeric
entries or modes. No free-pool calibration iteration or outcome gate was added.

`substrate_id_for` names this brain **`rest:ed9b0a469d7a6b77`**, never the
FlyWire-only `rest:379cc4cc9030cdd1`. Review regenerated the identifier after
binding the integrated source and loader code; none of the numerical settings
or the scale array changed.

| artifact | SHA-256 |
|---|---|
| male drive | `ed9b0a469d7a6b77bed2a346d0a71d33252a2484aa5d6c9486b3f201c5bd1913` |
| male dopamine | `e6fdafe53ccf025db44dee55a85174c89d56c5fe6a012fd1bff3f40d3e60d653` |
| male scale array (float32) | `fb6270f518f06cd0adb42748ae10baa360dec752edd237ce7ecdefa70450a84c` |
| extracted K2r measurement | `db6a7188d908eb4681a360d1170c516fd8d1a4dbede925cbb72e3c4ef171a77e` |

**Seed check:** `_reset` restores the initial state, then calls
`brian_seed(20260912, s, 0)`, using `SeedSequence` spawn key `(s, 0, ENGINE=1)`.
`BrianEngine.seed` passes that uint32 to Brian2 before its Cython Poisson
background runs. All ten derived seeds differ. Indices 1 and 5 give
2194859040 and 941284824; their first 100 ms contain **5,059 vs 3,595 spikes**
with different spike-index/time hashes. Replaying index 1 is bit-identical.
The similar long-window means therefore do not reflect duplicate streams.
Evidence: `validation/records/p2/malecns-seed-check.json`.

The integrated files built 162,517 cells and 25,120,209 edges on arm64 macOS,
then ran **1 s** with free dopamine pools, A/C and background on: **28.56 s**
run wall time, **60.54 s** total including preparation, **7,167,262,720 bytes**
peak RSS. The short execution check is not a stability or behavioural result.
Input, graph and output hashes are in `malecns-substrate.json` and
`malecns-substrate-probe.json` under `validation/records/p2/`. FlyWire data,
both registry versions' W/M/receptor arrays, and all eight 630/783 engine-array
hashes remain unchanged. The fly still does not see.

From the pinned checkout and cache, one command regenerates both tables and
the substrate identifier. The input record includes the shared registry's
`params-v0.1.yaml` as well as the engine's `params-v0.2.yaml`. It hashes only
the five manifest rows consumed to build model arrays, so adding 3D visual
assets cannot invalidate or rename the numerical substrate:

```bash
FLYONENOMICS_CACHE_DIR=$HOME/flyo-cache .venv/bin/python scripts/malecns_substrate.py --regenerate
```

Use `--seed-check` or `--probe` in place of `--regenerate` for the two short
engine records. None reruns the original 701 brain-seconds of rest measurements.

The lane's pre-integration full box gate (`timeout 5400`, one unfiltered pytest
invocation, one BLAS/OpenMP thread per process) finished with **927 passed, 30
skipped, zero failures** in 4,663.36 s. See `malecns-substrate-gate.json`; the
unchanged FlyWire hashes are in `malecns-substrate-preservation.json` alongside
it. Review separately reran the focused loader tests and the one-second probe
after repairing the integration pin.
