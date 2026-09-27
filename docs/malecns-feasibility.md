# MaleCNS migration feasibility

> **Current status (25 September 2026):** Historical feasibility assessment checked 21 September 2026, before the adopted MaleCNS substrate `rest:ed9b0a469d7a6b77` and filled male drive/dopamine tables. See [adoption](malecns-port.md#starting-substrate-port-step-6-item-155), the [first-study design](adhd-study-design.md) and the [confirmation design](adhd-confirm-design.md). Frozen parameter and engine source notes have a [provenance erratum](errata.md).

## Verdict

**Move forward with MaleCNS as a separately versioned experimental substrate, not
as a drop-in replacement for FlyWire v783.** The anatomy, flat data and existing
Brian core make the port technically feasible. MaleCNS adds bilateral
optic-column context and, unlike the then-current brain-only substrate, supplies a
connected brain–neck–VNC graph with motor neurons. At the assessment date,
FlyWire v783 had the stronger right-eye motion map:
published direct root assignments cover all T4/T5 types, while MaleCNS T4/T5
assignments are partial and inferred from wiring. MaleCNS does **not** yet supply
a complete, one-to-one flyvis eye mapping or evidence that the model sees or
behaves.

The practical answer to the eye-label question is **useful but incomplete**:
MaleCNS v1.0 has `assignedOlHex1/2` on 23,720 typed, traced rows, but those rows
cover only 15 of flyvis's 65 types. T4/T5 have no direct hex fields. A pinned
connectivity-derived method produces partial bilateral assignments, including
all eight T4/T5 types, but only 11,994 of flyvis's 45,669 type-position slots
have a unique assignment in both eyes. R1–R6 remain unresolved because MaleCNS
uses one shared `R1-R6`/`R1-6` identity rather than six photoreceptor identities.

At the assessment date, FlyWire was the validation baseline. Production
migration required a first-class adapter, new population and compartment
registries, fresh calibration, and a new substrate identity. Existing v783
validation records cannot be transferred to the male animal.

## Sources, release and license

The check used the official **MaleCNS v1.0** release dated 2026-06-08, checked
2026-09-21. The official download and release pages state **CC BY 4.0**. Any
redistributed source or derived graph must preserve attribution, release, source
URLs and checksums.

The peer-reviewed article is Berg et al., “Sexual dimorphism in the complete
*Drosophila* male central nervous system connectome,” *Cell* (2026), DOI
[`10.1016/j.cell.2026.08.015`](https://doi.org/10.1016/j.cell.2026.08.015).
Crossref independently confirms that title, first author, journal and DOI. The
correct DOI response and title-search response are retained with checksums in
the validation record. The locally cached full text is preprint v2, DOI
`10.1101/2025.10.09.680999`; release v1.0 remains the authority for the files
tested here.

The release inventory includes hosted imagery and segmentation, neuPrint,
annotation and body-stat tables, aggregate connectivity, synapse points and
partners, per-synapse transmitter predictions, meshes and skeletons. This
bounded check needed only three flat files (1,109,008,094 bytes total, 1.033
GiB), below the 20 GB limit:

| file | bytes | SHA-256 |
|---|---:|---|
| `body-annotations-male-cns-v1.0-minconf-0.5.feather` | 14,483,314 | `2177e246113e4cfbf1e7772ec37c6da1955ff22e8063d0b1f833101f99a9a3b2` |
| `body-neurotransmitters-male-cns-v1.0.feather` | 43,282,834 | `95c9289220663abeb3409f3ad9e5a7f8a53f8093f5139d15502cd08da8879621` |
| `connectome-weights-male-cns-v1.0-minconf-0.5.feather` | 1,051,241,946 | `e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1` |

Every downloaded data/page/paper/metadata file has URL, byte size and SHA-256
in `validation/records/p2/malecns-feasibility.json`. Discovery, data and the
pinned implementation precedent stayed under `.cache/`. The latter is
`fly-afterlife` commit `e4d3f0bf1ee65651e189cc07868659f1f366efd4`, MIT
licensed. Its connectivity-derived column placement and DRA/front orientation
were reused as methodology, not as biological validation or imported production
code.

## Graph and transmitter feasibility

A Brian-compatible exploratory graph was made from typed, traced neurons and
connections of at least five synapses whose endpoints are both retained:

| quantity | result |
|---|---:|
| traced annotation rows | 165,122 |
| typed traced graph neurons | 162,517 |
| raw aggregate connection rows | 151,856,684 |
| raw aggregate synapses | 311,833,243 |
| retained directed edges | 6,138,378 |
| synapses represented by retained edges | 88,488,128 |
| nodes with signed consensus transmitter | 159,988 (98.4439%) |
| unclear/missing sign | 2,529 (1.5561%) |

The sign rule is explicit: presynaptic acetylcholine, dopamine, serotonin and
octopamine are positive; GABA, glutamate and histamine are negative. This is the
same fast-transmitter convention used by the current model and Shiu precedent.
Unclear or missing consensus gives zero outgoing model weight. That conservative
choice leaves 6,049,915 retained edges with nonzero sign and needs sensitivity
analysis before calibration. Neuromodulators are treated as fast positive signs
here only because this is the inherited LIF convention; that is not a claim
about their biological time course.

The conversion establishes data and engine compatibility. It does not justify
the inherited five-synapse threshold, 0.275 mV/synapse scale, LIF parameters or
resting drive for this larger male graph.

## Eye and optic-column labels

### What is direct

All 23,720 direct `assignedOlHex1/2` rows in the checked typed/traced graph fall
within these 15 flyvis type aliases:

`C2`, `C3`, `L1`, `L2`, `L3`, `L5`, `Mi1`, `Mi4`, `Mi9`, `T1`, `Tm1`,
`Tm2`, `Tm20`, `Tm4`, and `Tm9`.

There are 10,453 left and 13,267 right rows. Direct counts are not the same as a
721-cell flyvis layer: MaleCNS has roughly 800–900 labelled columns for several
types, and the eye geometry differs.

### What was inferred

For a flyvis-compatible prototype, each matching MaleCNS cell takes:

1. its own direct MaleCNS hex, if available;
2. otherwise the hex with greatest aggregate incoming synapse weight;
3. otherwise the hex with greatest aggregate outgoing weight.

A tie at either wiring step is resolved by the lowest `(hex1, hex2)` pair. The
DRA photoreceptors define vertical orientation; the pinned `fly-afterlife`
`FRONT_SIGN=-1` defines front. Male physical hexes are rotated, rounded onto
flyvis's radius-15 axial lattice, and only a flyvis type-position occupied by
exactly one MaleCNS cell is accepted. The assignment uses connectivity to
already hex-labelled partners. It does **not** use neuron soma or centroid XYZ
positions; `somaSide`/`rootSide` only selects the eye. Shared `R1-R6` rows are
always rejected as unique R1, R2, …, R6 identities.

| coverage over 45,669 flyvis type-position slots | unique slots | fraction |
|---|---:|---:|
| left eye | 17,593 | 38.52% |
| right eye | 18,918 | 41.42% |
| present uniquely in both eyes | 11,994 | 26.26% |

T4/T5 illustrate both the gain and the remaining uncertainty:

| type | direct hex rows | unique left | unique right | bilateral |
|---|---:|---:|---:|---:|
| T4a | 0 | 419 | 420 | 275 |
| T4b | 0 | 434 | 454 | 306 |
| T4c | 0 | 432 | 439 | 282 |
| T4d | 0 | 440 | 443 | 294 |
| T5a | 0 | 446 | 458 | 307 |
| T5b | 0 | 447 | 451 | 310 |
| T5c | 0 | 445 | 402 | 279 |
| T5d | 0 | 424 | 419 | 278 |

The fair motion-seam comparison is:

| substrate and eye | T4/T5 column evidence | present choice |
|---|---|---|
| FlyWire v783 right | published 796-column map; all T4a–d/T5a–d assigned directly to roots | **better supported motion seam at assessment** |
| FlyWire v783 left | the reviewed publication claim does not establish a left-eye map | not ready |
| MaleCNS v1.0 left | 0 direct T4/T5 hex rows; 419–447 unique slots per type, inferred from labelled partners | provisional only |
| MaleCNS v1.0 right | 0 direct T4/T5 hex rows; 402–458 unique slots per type, inferred from labelled partners | provisional only |
| MaleCNS bilateral | 275–310 common unique slots per T4/T5 type | bilateral reach, but still partial and inferred |

Thus “both eyes” is a coverage advantage, not stronger assignment evidence.
MaleCNS is enough to build an explicitly provisional motion seam, but not a
complete eye. Fourteen types have no unique result in either eye, including all
six separate R1–R6 types, and many other types are sparse. Although 770 left and
769 right physical T4/T5 columns transform inside the 721-site target lattice,
rounding collisions reduce unique coverage. That non-bijection, orientation,
strongest-partner ties and release dependence must be carried as assignment
method/confidence, not hidden behind a root-to-hex table.

## Population translation and the ring route

All **142** definitions in `data/populations-v0.2.yaml` received a mechanical
first-pass audit. The complete per-population matrix is embedded in the
validation record. This maps `hemibrain_type` to MaleCNS `type`, FlyWire
`cell_type` to the MaleCNS `flywireType` cross-map, and side to
`somaSide`/`rootSide`; broad superclass vocabulary changes are explicit.
These are naming candidates, not validated sex-independent equivalents.

Summary: 69 populations remain within the old 10% count tolerance, 67 have a
nonzero candidate but changed by more than 10%, one old nonempty selector has no
candidate, one deliberately empty selector remains empty, and four explicit
FlyWire-root populations require manual remapping.

| required population | FlyWire inventory | Male naming candidate | result |
|---|---:|---:|---|
| DAN | 331 | 340 | candidate; 338 dopamine consensus |
| CX_DAN | 30 | — | rebuild with MaleCNS ROI output |
| KC | 5,177 | 4,064 | candidate, large count change |
| MBON | 96 | 97 | candidate |
| ER | 278 | 282 | candidate |
| EPG | 51 | 50 | candidate |
| TuBu | 150 | 156 | candidate |
| steering L / R | 2 / 2 | 2 / 2 | bilateral candidates |
| DN_all | 1,303 | 1,310 | candidate |
| sugar_GRN_R | 21 | — | no clean sugar-labelled equivalent |
| MN9 | 1 | 2 | type exists bilaterally; choose side explicitly |
| R1_6 | 8,452 | 1,394 | shared type and incomplete retina; large change |

For the result-critical sets, the audit found:

| set | FlyWire result/in-engine count | MaleCNS naming candidate | qualification |
|---|---:|---:|---|
| traced `ER` set | 228 | 254 across the same ten broad subtype names | broad-name candidates, not one-to-one identities; MaleCNS also has 28 `ER1` cells, giving 282 total `ER` |
| `CX_DAN` | 30 roots | 38 named candidates, 36 dopamine consensus | **no clean match** until the EB/central-complex ROI-output filter is repeated |
| TuBu | 150 | 156 | all ten broad TuBu names present |
| MeTu | 896 total / 886 route-relevant | 1,009 total / 974 route-relevant | two `MeTu4_unclear`; candidate family split differs |
| T4a–d/T5a–d | 12,238 | 13,580 | all eight names present; exact per-type counts are in the record |
| H2 / HS / VS | 2 / 6 / 32 | 2 / 8 / 34 | bilateral naming candidates |
| DNa02 / DNae001 | 2 / 2 | 2 / 2 | bilateral naming candidates |
| sugar source | 21 `sugar_GRN_R` | 60 taste-peg GRNs | **no clean match**: no checked sugar-modality label |
| MN9 | 1 explicit root | 2 named cells | type match exists, but laterality must be chosen explicitly |
| R1–R6 / R7 / R8 | 7,932 / 1,337 / 1,314 | 1,394 / 1,299 / 1,329 | R1–R6 are merged and the retina is incomplete |

The 228-cell FlyWire `ER` subtype counts versus same-broad-name MaleCNS
candidates are: ER2 38/41, ER3a 24/30, ER3d 51/54, ER3m 14/18, ER3p 17/18,
ER3w 25/31, ER4d 25/26, ER4m 11/11, ER5 21/21 and ER6 2/4. MaleCNS subdivides
several of these names, so these remain population candidates rather than a
cross-animal identity map.

The central-complex visual route is structurally promising:

- 282 ER neurons and 156 TuBu neurons are present;
- all 156 TuBu have at least one edge to ER: 568 pairs and 16,055 synapses;
- 974 of 1,009 MeTu connect to a TuBu in that set: 6,118 pairs and 60,486
  synapses;
- all T4a–d/T5a–d types, bilateral H2/HS/VS families and bilateral DNa02 and
  DNae001 exist.

The old `CX_DAN` definition cannot simply be renamed. Thirty FlyWire roots were
selected by an EB/central-complex output-fraction filter. MaleCNS has 38 named
central-complex candidates, 36 with dopamine consensus, but the omitted ROI
synapse-distribution table is needed to repeat the filter. Likewise, MaleCNS has
60 taste-peg GRNs but no checked `sugar` modality label, so equating them with
the 21-cell `sugar_GRN_R` source would be unsupported.

## Full-CNS motor evidence

The graph contains 373 typed leg and 66 typed wing motor neurons under the
checked subclass rules. Strongest-product exploration finds short candidate
routes from both copies of DNa02 and DNae001:

| source | leg route | wing route |
|---|---|---|
| DNa02 L/R | direct to sternal anterior rotator MN | direct to `hg1 MN` |
| DNae001 L/R | direct to tibia extensor MN | two hops via VNC interneuron to wing MN |

Examples and every edge weight/body ID are in the machine record. At three
hops, each source reaches hundreds of leg and all 66 wing motor candidates
under this unconstrained strongest-product traversal. Products of signed
`0.275 × synapse_count` edge weights are topology bookkeeping: they are not
probabilities, biological gains, causal flow or simulated movement.

## Brian cost probe

The existing Brian LIF core built and stepped the converted graph. The probe
used seed `20260921`, unchanged `data/params-v0.2.yaml`, rest initialization,
no input banks, no extended input, no spike list, and no background. The array
cache had already been generated.

| measure | result |
|---|---:|
| graph build wall time | 2.139 s |
| simulated duration | 1.0 s at 0.1 ms |
| run wall time | 7.189 s |
| process peak RSS | 763,641,856 bytes (728.27 MiB) |
| spikes / firing neurons | 0 / 0 |

Platform: arm64 macOS, Python 3.12.14, Brian Cython backend. The machine had
1,412 MiB of swap in use when recorded, but `/usr/bin/time` reported zero swap
events for the process. Zero spikes are expected from a zero-input network
initialized at rest. **This is only a build/runtime measurement; the fly does
not see in this probe.**

## Port plan

The numerical core is reusable, but the surrounding substrate is tightly bound
to FlyWire materializations:

- `src/flyonenomics/types.py:39` and
  `src/flyonenomics/schema/experiment.py:58` admit only `630` or `783`;
- `src/flyonenomics/connectome_arrays.py:165-167` and
  `src/flyonenomics/orchestrator/workers.py:279-283` switch hard-coded FlyWire
  filenames;
- `src/flyonenomics/registry/annotations.py:24-69` fixes the two FlyWire
  annotation/connectome versions and expects FlyWire columns such as `root_id`,
  `cell_type`, `hemibrain_type`, `known_nt` and `top_nt`;
- `data/populations-v0.2.yaml:8-82215` is the v783 retinotopy table;
  `data/populations-v0.2.yaml:82216-84462` carries FlyWire selectors,
  inventories and explicit roots, including `CX_DAN`, `sugar_GRN_R` and MN9;
- `src/flyonenomics/registry/__init__.py:297-367` always loads FlyWire v2.1.0,
  repeats the v783 `CX_DAN` connectivity filter and builds memberships;
  `src/flyonenomics/registry/compartments.py:354-426` turns those memberships
  into the 37-column innervation/exposure matrices;
- `data/transmitters-v0.2.yaml:3`, `data/dopamine-v0.2.yaml:4` and
  `data/drive-v0.2.yaml:57-58` pin the v783 transmitter map, dopamine table and
  declared resting drive; all values in `data/params-v0.2.yaml`,
  `data/compartments-v0.1.yaml` and `data/receptors-v0.1.yaml` were calibrated
  or curated around those memberships;
- `data/visual-v0.2.yaml`, `data/behaviour-v0.2.yaml`, experiment fixtures and
  every existing validation record are outcomes bound to the FlyWire substrate,
  not inputs that can be relabelled.

A safe implementation order is:

1. Add a dataset-adapter interface and first-class `male-cns:v1.0` version;
   never masquerade as `783` as this probe does to reuse the array loader.
2. Define canonical MaleCNS annotation, engine-order and edge conversion
   schemas, with source checksums and CC BY attribution.
3. Commit a MaleCNS population registry after biological review of all 142
   audit rows, explicit laterality and a repeated ROI-based `CX_DAN` filter.
4. Commit a versioned eye-assignment artifact carrying direct/inferred method,
   confidence, collisions and unresolved identities per cell.
5. Rebuild compartment targets, W/M matrices, receptor exposures and every
   dopamine/drive parameter on the male graph.
6. Mint new parameter, drive, dopamine, visual and behaviour versions plus a
   new substrate ID. Do not reuse `rest:379cc4cc9030cdd1`.
7. Re-run structural checks, resting calibration, sugar/reflex replacement,
   visual transfer, open-loop steering and behavioural assays before considering
   MaleCNS a default.

## Reproduction and evidence

```sh
uv run python scripts/malecns_feasibility/fetch.py --download
uv run python scripts/malecns_feasibility/build_graph.py
uv run python scripts/malecns_feasibility/analyse.py
uv run python scripts/malecns_feasibility/audit_populations.py
uv run python scripts/malecns_feasibility/run_probe.py
uv run python scripts/malecns_feasibility/assemble_record.py
```

Committed evidence:

- `validation/records/p2/malecns-feasibility.json` — provenance, all 142
  population rows, all 65 eye-type results, graph/sign statistics, exact motor
  paths, assumptions, limitations and cost probe;
- `scripts/malecns_feasibility/` — resumable download, conversion, analyses,
  probe and record assembly.

The downloaded source data and large derived arrays remain ignored under
`.cache/malecns-v1.0/`.
