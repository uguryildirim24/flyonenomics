# Can a flyvis eye feed this brain?

## Verdict

**The motion-path seam is feasible to attempt, but has not been built or tested.**
flyvis runs comfortably on this Mac, and the v783 graph contains a T4/T5 route
to descending and steering neurons. The pinned FlyWire annotation table in this
repository has no retinal hex or column identifier, so the lane's direct join
found **0 unique matches among flyvis's 45,669 cells**. That is a limitation of
that local table, not proof that v783 column correspondence is unavailable.

Matsliah, Yu et al. (2024) published a v783 right-eye grid with **796 columns**,
hexagonal `(p,q)` coordinates, and FlyWire root assignments. The associated
OpticLobe.jl resources include every T4a-d and T5a-d type needed for the motion
seam. The lane missed this source, so its original “not feasible” verdict and
its claim that a future lane must obtain or derive the table were wrong. The
published table still has to be pinned, checked against this substrate, and
reconciled with flyvis's 721-column lattice before a dynamic probe is valid.

The ring route has a separate biological/model-coverage gap. Among
medulla-origin inputs to the MeTu cells that supply the relevant TuBu set,
flyvis models types carrying only **20.28% of synapses and 14.74% of absolute
composed weight**. Driving that subset would omit most measured input,
especially untyped optic cells, Dm2, Dm21 and several CB types. The ring seam is
therefore not justified by the published column map alone.

flyvis is a trained optic-lobe model, not a biological eye. No result here shows
visual function in the spiking brain.

## 1. flyvis on this Mac

flyvis was installed in a separate uv environment at `/tmp/flyvis-env-t0048`.
Neither flyvis nor PyTorch was added to this project's dependencies. The run
used:

- flyvis 1.2.0 at git commit
  `92b3845cc426dd309a1a0e1b3890156c42e14021`;
- PyTorch 2.14.0, NumPy 2.5.3, Python 3.12.14;
- pretrained model `flow/0000/000`, checkpoint SHA-256
  `d8a57a022aa18ca338599be713af9db29b89cde4b00098ffe42b78f0d583e46a`;
- CPU on this arm64 Mac; peak RSS 2,377,039,872 bytes (2.21 GiB);
- flyvis software under the repository's MIT license. The official downloader
  supplied the checkpoint; no separate checkpoint license was found in the
  repository, so redistribution rights for that file were not assumed. The
  FIB-derived connectome behind flyvis is a separate source dataset.

The protocol was 20 s at 100 frames/s, matching our 10 ms interaction timing.
A 5° dark stripe on 0.5 luminance was held at -60°, 0° and +60°. A fourth
condition moved the stripe at 60°/s across the represented lattice and wrapped.
The explicit timing-probe geometry assigned 5° to one flyvis horizontal hex
step; it is not a claimed FlyWire eye geometry.

| condition | wall time for 20 s |
|---|---:|
| static -60° | 5.92 s |
| static 0° | 5.75 s |
| static +60° | 5.67 s |
| moving | 5.65 s |

Loading took 2.28 s; the complete run plus extraction took 25.68 s. flyvis
returned graded activity with shape **time × type × hex cell**: 2,000 time
samples and 65 cell types. Sixty-three types have 721 cells; the two strided
Lawf types have 123 each, for **45,669 cells** total. The record keeps, for every
condition and type, each cell's temporal mean, standard deviation, minimum and
maximum. Example global ranges:

| condition | type | range of temporal means | largest activity |
|---|---|---:|---:|
| static 0° | Mi1 | 0.259 to 0.789 | 0.789 |
| static 0° | T4a | -0.240 to 1.261 | 1.281 |
| static 0° | T5a | -0.328 to 1.131 | 1.427 |
| moving | Mi1 | 0.532 to 0.776 | 1.103 |
| moving | T4a | -0.139 to 1.255 | 1.491 |
| moving | T5a | -0.179 to 1.045 | 1.314 |

This establishes runtime and spatially resolved graded output. It does not
validate static-stripe physiology: flyvis was trained on optic flow, and its
static-stripe responses are less tested than its motion responses.

Reproduction:

```sh
uv venv --python 3.12 /tmp/flyvis-env
VIRTUAL_ENV=/tmp/flyvis-env uv pip install /path/to/flyvis
FLYVIS_ROOT_DIR=/tmp/flyvis-data /tmp/flyvis-env/bin/flyvis download-pretrained --skip_large_files
FLYVIS_ROOT_DIR=/tmp/flyvis-data /tmp/flyvis-env/bin/python \
  scripts/eye_feasibility/run_flyvis_stripes.py --out /tmp/flyvis-stripes.json
```

## 2. Connectome version and the precedent

The declared substrate `rest:379cc4cc9030cdd1` uses FlyWire materialization
**783**: 138,639 engine neurons and 15,091,983 directed connection rows. Its
annotation source is the FlyWire v2.1.0 release at commit
`ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0`, where `root_id` is explicitly the
materialization-783 ID.

`fly-afterlife` commit `e4d3f0bf1ee65651e189cc07868659f1f366efd4`
is MIT licensed. Its `seam/build_flywire.py` also expects
`proofread_connections_783.feather`, so the **materialization matches**. That is
not enough to reuse its seam:

- `seam/build_flywire.py` builds a female v783 node table but does not attach
  optic-lobe columns.
- `seam/columns.py` and `seam/columns_all.py` read MaleCNS fields
  `assignedOlHex1` and `assignedOlHex2`.
- The actual fly-afterlife seam uses those MaleCNS columns to drive its own
  T4/T5 cells. It reports rate-coded Poisson drive, and its working document
  also withdraws several early loom-selectivity claims after controls. It is a
  useful implementation precedent, not transferable evidence for our female
  v783 mapping or downstream response.

## 3. Type and column mapping

The pinned annotation table used by this repository provides `cell_type`,
`hemibrain_type`, side and positions, but no ommatidial/hex/optic-column field.
Type matching against that table alone finds candidates for 55 of 65 flyvis
types. It cannot choose which candidate corresponds to flyvis coordinate
`(u,v)`. The R1-R6 bridge is especially ambiguous: each of the six flyvis types
points at the same 7,932 FlyWire `R1-6` candidates. Ten flyvis types have no
exact candidate under the checked aliases.

Accordingly, the lane's **local-table-only** join returned zero unique matches:

| flyvis type | v783 type candidates | unique type+hex matches |
|---|---:|---:|
| `Am` | 313 | 0 |
| `C2` | 1,456 | 0 |
| `C3` | 1,460 | 0 |
| `CT1(Lo1)` | 0 | 0 |
| `CT1(M10)` | 0 | 0 |
| `L1` | 1,579 | 0 |
| `L2` | 1,554 | 0 |
| `L3` | 1,406 | 0 |
| `L4` | 1,398 | 0 |
| `L5` | 1,606 | 0 |
| `Lawf1` | 353 | 0 |
| `Lawf2` | 313 | 0 |
| `Mi1` | 1,580 | 0 |
| `Mi10` | 401 | 0 |
| `Mi11` | 0 | 0 |
| `Mi12` | 0 | 0 |
| `Mi13` | 720 | 0 |
| `Mi14` | 248 | 0 |
| `Mi15` | 980 | 0 |
| `Mi2` | 829 | 0 |
| `Mi3` | 0 | 0 |
| `Mi4` | 1,528 | 0 |
| `Mi9` | 1,568 | 0 |
| `R1` | 7,932 | 0 |
| `R2` | 7,932 | 0 |
| `R3` | 7,932 | 0 |
| `R4` | 7,932 | 0 |
| `R5` | 7,932 | 0 |
| `R6` | 7,932 | 0 |
| `R7` | 1,337 | 0 |
| `R8` | 1,314 | 0 |
| `T1` | 1,390 | 0 |
| `T2` | 1,454 | 0 |
| `T2a` | 1,781 | 0 |
| `T3` | 1,615 | 0 |
| `T4a` | 1,463 | 0 |
| `T4b` | 1,507 | 0 |
| `T4c` | 1,692 | 0 |
| `T4d` | 1,578 | 0 |
| `T5a` | 1,482 | 0 |
| `T5b` | 1,520 | 0 |
| `T5c` | 1,529 | 0 |
| `T5d` | 1,467 | 0 |
| `Tm1` | 1,544 | 0 |
| `Tm16` | 343 | 0 |
| `Tm2` | 1,528 | 0 |
| `Tm20` | 1,488 | 0 |
| `Tm28` | 0 | 0 |
| `Tm3` | 1,746 | 0 |
| `Tm30` | 0 | 0 |
| `Tm4` | 1,489 | 0 |
| `Tm5Y` | 808 | 0 |
| `Tm5a` | 450 | 0 |
| `Tm5b` | 0 | 0 |
| `Tm5c` | 607 | 0 |
| `Tm9` | 1,506 | 0 |
| `TmY10` | 0 | 0 |
| `TmY13` | 0 | 0 |
| `TmY14` | 370 | 0 |
| `TmY15` | 225 | 0 |
| `TmY18` | 1,128 | 0 |
| `TmY3` | 734 | 0 |
| `TmY4` | 426 | 0 |
| `TmY5a` | 1,025 | 0 |
| `TmY9` | 727 | 0 |

The complete machine-readable local-table result is at
`connectome_analysis.mapping.coverage_by_type` in the evidence record. The
correct denominator is 45,669, not the 46,865 produced by the original analysis
script's assumption that both strided Lawf layers also had 721 cells.

This zero does **not** include the independent Matsliah–Yu column resource. The
Nature article page labels Supplementary Data 2 as cell-type cards, not as the
coordinate CSV; the machine-readable column sources verified here are the
OpticLobe.jl files and the v783 Codex download. The publication-era OpticLobe.jl
construction defines `(p,q)` for 796 right-eye
columns, anchors each with a v783 Mi1 root, and assigns columns by connectivity
to 29 more types: L1-L5, C2, C3, Mi4, Mi9, T1, T2, T2a, T3, T4a-d, T5a-d,
Tm1, Tm2, Tm3, Tm4, Tm9, Tm20, TmY5a and Y3. Its code reports unassigned cells
and contains two manual L1 fixes, so these are assignments, not a guarantee of
one complete cell of every type in every column.

The current v783 Codex `column_assignment.csv.gz` checked during review is a
direct root-ID table with 22,933 right-side rows, all 796 right-eye columns and
31 types: C2, C3, L1-L5, Mi1, Mi4, Mi9, R7, R8, T1, T2, T2a, T3, T4a-d,
T5a-d, Tm1, Tm2, Tm3, Tm4, Tm9, Tm20 and Tm21. All eight T4/T5 types are
present. That download also contains left-side assignments, but the published
grid and the integration claim assessed here are right-eye only; left-eye
orientation and completeness still require validation. Neither source covers
all 65 flyvis types, R1-R6, or the 721-to-796 lattice transform. Soma or
representative coordinates are not a substitute for these validated columns.

## 4. Ring route: medulla → MeTu → TuBu → ER

Starting with the 228 `ER` cells in
`validation/records/p2/tubu-reached-subset.json`, 147 of 150 TuBu cells have a
direct edge to at least one of them. Those TuBu cells receive direct input from
1,335 neurons, including **886 MeTu cells**:

| MeTu type | cells presynaptic to relevant TuBu |
|---|---:|
| MeTu1 | 244 |
| MeTu2 | 100 |
| MeTu3 | 273 |
| MeTu4 | 269 |

The evidence record lists every one by root ID, engine index, side, number of
relevant TuBu targets, input synapses and composed input weight at
`connectome_analysis.ring_path.presynaptic_MeTu`. The full relevant TuBu list is
next to it.

Restricting incoming edges to sources whose v783 `super_class` is `optic`, the
886 MeTu cells receive 203,355 synapses over 63,883 connection pairs. Their
absolute composed input weight is 83,220.225 mV after the declared substrate's
0.275 mV base weight and connection scaling. Exact type overlap with flyvis is:

| input set | synapses | fraction | absolute composed weight | fraction |
|---|---:|---:|---:|---:|
| all optic → relevant MeTu | 203,355 | 100% | 83,220.225 mV | 100% |
| source type modelled by flyvis | 41,235 | **20.28%** | 12,264.450 mV | **14.74%** |

Mi15 dominates the covered part (35,156 synapses; 9,667.9 mV). Large uncovered
inputs include untyped optic cells (48,445 synapses), Dm2 (44,872), Dm21
(16,609), CB3825 (14,891), CB3855 (7,530) and CB3838 (6,633). The record gives
the complete per-type breakdown.

Thus flyvis does not provide most of the measured drive into the MeTu population
that supplies this ring route. The published map removes the blanket spatial
unmappability claim for its covered right-eye types, but the proposed ring seam
remains dynamically incomplete.

## 5. Motion route: T4/T5 → lobula plate → steering

The v783 substrate contains 12,238 exact T4a-d/T5a-d cells. There are 52,920
connection pairs from them into 144 named lobula-plate tangential candidates
(`LPT*`, HS, VS, H1 and H2), then 1,181 direct pairs from those cells into
descending neurons. Strong aggregate examples include T5b→H2 (12,771 synapses,
3,512.025 mV), T4b→H2 (11,942; 3,284.05 mV), T5a→HSE (6,826; 1,877.15 mV) and
T4d→VS2 (5,710; 1,570.25 mV).

All four steering endpoints measured in item 131's TuBu study are structurally
reachable:

| endpoint | shortest example | edge synapses | composed edge weights | path product* |
|---|---|---|---|---:|
| DNa02 R | T4b → H2 → DNa02 R | 25, 3 | +6.875, +0.825 mV | +5.671875 |
| DNa02 L | T5b → H2 → DNa02 L | 28, 2 | +7.700, +0.550 mV | +4.235000 |
| DNae001 L | T5a → LPT31 → WED096a → DNae001 L | 5, 1, 1 | +1.375, +0.275, -1.100 mV | -0.415938 |
| DNae001 R | T4b → H2 → DNge040 → DNae001 R | 25, 1, 1 | +6.875, +0.275, -1.100 mV | -2.079688 |

`*` The product is topology bookkeeping in mV raised to the number of hops, not
a biological transfer gain. The point-LIF dynamics are nonlinear. These routes
show anatomy, not that a flyvis stimulus will make an endpoint spike.

This makes the motion path the stronger integration candidate. A published
right-eye column map exists and covers T4/T5, but this review did not integrate
or validate it against the 12,238 T4/T5 roots. The table establishes feasibility
of attempting the seam, not dynamic propagation.

## 6. Graded-to-spiking conversion

The proposed conversion follows the useful part of the fly-afterlife precedent:
for each uniquely mapped cell, subtract its activity under a common blank scene,
rectify positive deviations, divide by a fixed reference amplitude, clip to
[0,1], and use that fraction of a fixed maximum rate for Poisson drive into the
corresponding spiking cell.

Every free choice must be frozen before inspecting MeTu, TuBu, ER,
lobula-plate, descending or steering responses:

1. pretrained model or externally selected ensemble;
2. two-eye field geometry, orientation, acceptance angle and hex transform;
3. seam depth and exact type aliases;
4. blank duration, baseline estimator and handling of negative/OFF deviations;
5. reference amplitude and maximum Poisson rate;
6. frame rate, 10 ms interpolation and seam latency;
7. independent versus shared Poisson noise and all seeds;
8. additive drive versus replacement of native input;
9. unmatched columns, unmatched roots and omitted-type policy;
10. contrast, luminance normalization, onset ramp and preperiod.

Reference amplitude may be fixed from a held-out flyvis calibration stimulus
set, and a maximum rate from published physiology. Neither may be chosen to
make our downstream cells fire. A blank-subtracted drive also needs an explicit
OFF-channel rule; silently discarding negative graded activity would bias the
conversion.

## 7. Dynamic probe

**Not run; 0 brain-seconds.** The lane did not discover or integrate the
published column map. Broadcasting a type average to every same-type FlyWire
root would erase stripe position and create a different, artificial input. Its
per-cell MeTu/TuBu/ER or steering output would not test the proposed seam.
Stopping here avoided fitting or interpreting an invalid input, but the reason
is unfinished mapping work rather than absence of a v783 table.

## What full integration would take

For the motion route, the v783 right-eye table is a download plus a version and
root-ID check, not a table that must be derived. Work remains to validate its
T4/T5 assignments, choose and freeze the right-eye orientation and 721-to-796
transform, freeze the graded-to-spiking conversion on upstream data, add a seam
runner outside `src/`, and validate synthetic spatial patterns. The lane's
**five-to-eight-engineering-day** estimate explicitly included obtaining or
deriving the supposedly missing table, so it is not a sound estimate of this
corrected scope. This review supplies no replacement estimate. The lane's
three-seed, 20 s stripe/blank probe budget was at most 120 brain-seconds for one
path.

The ring route is not an integration-only job. It needs a justified model for
the large non-flyvis medulla contribution, or evidence that the covered subset
is sufficient without selecting that subset from the ER outcome. That is
roughly **one to two additional weeks of model and physiology work** before a
valid stage-4 position-coding feed can be attempted. Stage 5's two simultaneous
stripes needs the same validated retinotopy and a renderer that preserves both
objects; after stage 4 works, adding and freezing those stimuli is about **one
to two days**, excluding the already planned brain run.

flyvis stops at T4/T5 and the columnar medulla. It does not supply MeTu, TuBu,
`ER`, lobula-plate outputs, descending neurons or steering cells. Its optic-flow
training makes motion the defensible first target; static bars remain a weaker
extrapolation.

## Evidence and sources

- Machine record: `validation/records/p2/eye-frontend-feasibility.json`.
- Scripts: `scripts/eye_feasibility/run_flyvis_stripes.py`,
  `analyse_connectome.py`, `assemble_record.py`.
- Lappalainen et al. (2024), *Nature*,
  <https://doi.org/10.1038/s41586-024-07939-3>.
- Matsliah, Yu et al. (2024), “Neuronal parts list and wiring diagram for a
  visual system,” *Nature* 634:166–180,
  <https://doi.org/10.1038/s41586-024-07981-1>.
- OpticLobe.jl right-eye grid and assignments, including
  `data/RightEyeGrid.csv`, `data/columns_Mi1.csv`,
  `src/columncoordinates.jl` and `src/columncell.jl`, at data commit
  `13e0e2bf1db9d7184c084e111591d108332fc440`:
  <https://github.com/hsseung/OpticLobe.jl>.
- FlyWire Codex v783 `column_assignment.csv.gz`, checked during review; the
  compressed file SHA-256 was
  `bdf4ce7f62cc63493d53eefad3816ff2dfd08b190e97b35a492e0e453df2f0f6`.
- flyvis source and MIT license at the commit above:
  <https://github.com/TuragaLab/flyvis>.
- fly-afterlife source and MIT license at the commit above:
  <https://github.com/nsfm/fly-afterlife>. Relevant files are
  `docs/SEAM.md`, `seam/build_flywire.py`, `seam/columns.py`,
  `seam/columns_all.py` and `seam/seam_v2.py`.
- FlyWire v783 annotations and CC-BY 4.0 data provenance are recorded in
  `docs/data.md` and `data/provenance.json`.

## Verification

```text
........................................................................ [ 99%]
..                                                                       [100%]
911 passed, 27 skipped, 11 deselected, 49 warnings in 890.55s (0:14:50)
```

```text
vm.swapusage: total = 2048.00M  used = 1412.12M  free = 635.88M  (encrypted)
```
