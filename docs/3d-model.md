# MaleCNS 3D atlas

- [Offline viewer](../figures/3d/male-cns-atlas.html): open directly in a current browser.
- [Paper anatomy figure](../figures/3d/male-cns-anatomy-paper.png): 3000 × 2646, the
  static figure for the manuscript (see [below](#paper-anatomy-figure)).
- [Atlas still](../figures/3d/male-cns-atlas.png): 3200 × 2000, the viewer's clean figure layout.
- [Dummy-playback PNG](../figures/3d/male-cns-dummy-playback.png): made-up demo values at 1.00 s.

The links above are **anatomy and labelled dummy values, not model results**.
[Calibration 5a playback](../figures/3d/calibration-5a/male-cns-atlas.html)
adds recorded model activity (details below). [Stage 5b experiment playback](../figures/3d/experiment-5b/male-cns-atlas.html) shows one selected seed's primary test window, and a
[cinematic film](../figures/3d/experiment-5b/cinematic/primary-demo.mp4) replays it
for a general audience. No simulation runs in this renderer.

## Rebuild

With `uv` and Google Chrome installed, from the repository:

```sh
uv run --locked scripts/render_malecns_3d.py
```

The script has its own pinned Python dependency lock. It fetches only selected
geometry, the small released annotation table if absent, and Three.js. It never
imports the engine, reads connectivity or builds a model. Playwright uses
installed Chrome, with all HTTP(S) requests blocked during the PNG render.

The default cache is the **main checkout's** `.cache/malecns-v1.0/`, located
through Git's common directory even from a worktree. No worktree copy is made.
Override with `--cache /path/to/malecns-v1.0` or
`FLYONENOMICS_CACHE_DIR=/path/to/.cache`. Downloads are sequential, capped at
20 GB per invocation; every completed file has URL, bytes and SHA-256 in
`data/malecns-v1.0-manifest.json`. A hash mismatch fails, not silently refreshes.
With the cache populated, rebuilding downloads zero bytes.

Outputs in `figures/3d/` (`--out` changes this): HTML ~6.93 MB, atlas PNG
~1.69 MB, paper anatomy PNG ~1.75 MB, dummy PNG ~1.64 MB, `dummy-values.json`
~0.28 MB, `build.json` ~0.12 MB.
No committed file exceeds 20 MB. The receipt holds displayed body IDs, counts,
geometry reductions, source/output hashes and browser version. HTML and PNGs
reproduced byte-for-byte on this Mac; raster pixels may differ across browser,
OS or GPU versions. The receipt's measured download count changes on a cached
rebuild. Raw geometry stays in the cache, not beside the offline HTML.

## Sources and size

All anatomy comes from the public [MaleCNS release](https://male-cns.janelia.org/download/),
in **native, unmirrored MaleCNS EM space**, not FlyWire or a template.
Paths below are relative to `gs://flyem-male-cns/`:

| Source | Selected files | Bytes |
|---|---:|---:|
| `rois/malecns-major-compartments-v2/mesh/` | 5 | 25,383,476 |
| `rois/fullbrain-roi-v4/mesh/` | 30 | 50,149,188 |
| `rois/malecns-vnc-neuropil-roi-v0/mesh/` | 9 | 44,387,952 |
| `v1.0/segmentation/skeletons-malecns/skeletons-precomputed/` | 952 bodies | 29,507,104 |
| Coordinate and ROI-label metadata | 7 | 9,168 |
| Three.js 0.160.1, OrbitControls and MIT license | 3 | 702,735 |
| **Visual sources** | **1,006** | **150,139,623** |

The pinned annotation table adds 14,483,314 bytes: **164,622,937 bytes total**
(0.165 GB). Cache paths: `visuals/meshes/{major,neuropils,vnc}/`,
`visuals/skeletons/<body_id>`, `visuals/metadata/`,
`visuals/vendor/three-0.160.1/`.

Source discovery checked published ROI meshes first. The segmentation also
provides sharded multiresolution Draco meshes at
`v1.0/segmentation/multi-res-meshes/`; listed shards are around 1–2 GB each.
A range-aware client could fetch individual LODs, but unsharded body-ID
centerlines are smaller and sufficient here. Neither those shards nor the
756 GB single-resolution neuron-mesh collection was downloaded. Native
precomputed skeletons are smaller than SWC and use nanometres, like ROI vertices.

The **outline is a union of major neuropil compartments**, not an outer
cell-body rind: central brain, optic lobes, cervical connective and VNC.
Internal context includes EB/FB/PB/NO; bilateral mushroom-body lobes, calyces
and peduncles; lamina/medulla/lobula/lobula plate; anterior optic tubercle and
bulb; leg neuropils T1–T3, abdominal neuropil, lower/intermediate tectulum.
These are selected regions, not every VNC ROI.

## Selection and display geometry

The project's `resolve_population` reads the actual population YAML selectors.
The small annotation table supplies the adapter's traced/typed node rule and
same type, class and laterality mapping; no connectivity-dependent build occurs.

| Display group | YAML selection | Shown / selected |
|---|---|---:|
| CX dopamine | `CX_DAN`, frozen explicit IDs | 27 / 27 |
| Ring neurons | `ER`, not just the TuBu-reached trace subset | 282 / 282 |
| Tubercle → bulb | `TuBu` | 156 / 156 |
| Mushroom-body dopamine | `PAM ∪ PPL1`; not PPL2 | 332 / 332 |
| Kenyon cells | `KC` | 155 / 4,064 |

KC display takes at most eight cells per released type × side stratum, keeping
smaller strata whole. IDs are ordered by `sha256("male-cns-3d-v1:<body_id>")`.
This outcome-independent selection preserves rare types; **it is not
proportional sampling or a population-density plot**. No body fetch was skipped.

Quadric simplification reduces 6,664,390 mesh triangles to 182,998.
Ramer–Douglas–Peucker simplification uses 1 µm on each degree-two skeleton path,
retaining every branch point and tip, without twig pruning: 1,474,267 edges
become 279,301 segments. Coordinates are then rounded to 0.01 µm. Do not use
this display geometry for synapse, diameter or surface-area measurements.

The rigid transform is `(native_nm / 1000 - [384,200,230]) * [1,-1,-1]`:
units, translation and rotation only; no mirroring or warping. The anterior
brain view has dorsal up and the fly's right on screen left. Whole CNS puts
native negative z upward. Both use orthographic projection and equal scale
in all dimensions. The 100 µm bar tracks zoom. The distant cord is hidden in
the brain-only viewport, not projected behind it; the CNS context includes it.

## Paper anatomy figure

[`male-cns-anatomy-paper.png`](../figures/3d/male-cns-anatomy-paper.png) is the
manuscript's anatomy figure. The same `render_malecns_3d.py` run that builds the
atlas captures the viewer's two views without the page around them and lays them
out with `scripts/malecns_3d/anatomy-paper.html`, 1000 CSS px wide at 3×. At a
468 pt text width its smallest text is about 7 pt.

- **a**, brain front view, with a 100 µm scale bar; **b**, whole CNS at one
  scale, with a 200 µm bar. Both bars use the viewer's own pixels per micrometre
  at capture. Panel b is exactly as wide as everything the whole-CNS view draws,
  plus a 6% margin on each side, so nothing drawn is cropped.
- A key of the five groups with the cells drawn: 156 TuBu (the model's input is
  injected here); 282 ring neurons (all drawn; **the 245 with a direct TuBu
  connection are the analysed readout**); 27 central-complex dopamine; 332
  mushroom-body dopamine; 155 of 4,064 Kenyon cells (a stratified sample, shape
  not density).
- "Anatomy only, no activity is shown", a line on centrelines and simplified
  meshes, and the MaleCNS attribution.

It has no controls, sliders, dummy values or page statistics. The interactive
atlas and its still stay separate.

## Viewer and later playback

**Three.js** gives a small embedded viewer, one material per cell, group toggles
and a CNS context view without a Python server or runtime CDN. Direct binary
decoding avoids a large morphology stack; `fast-simplification` handles meshes.
Gzip-packed geometry plus embedded modules keeps HTML under 7 MB. A current
browser needs WebGL and `DecompressionStream` support.

Drag to rotate, scroll/pinch to zoom, right-drag to pan; choose Brain/Whole CNS,
reset, toggle groups or hover for body IDs. Save view exports the canvas with
attribution and, in value mode, its plain labels, condition, time and colour scale.

Opening a viewer with `#figure` appended to its address gives the clean figure
layout used for every committed still: no buttons, sliders, checkboxes or hints;
title, honest labels, colour scale and key only; a playback figure is centred on
the recorded cells. Page text comes from `scripts/malecns_3d/display.py` in plain
words ("Normal brain", "Broken dopamine cleanup", "Simulated fly 10 of 10").
Stage, seed and arm codes, file paths and hashes stay in the receipts and this
document, never on the pictures.

**Show values** colours each recorded cell on a dark stage, from dark purple
(low) through orange to pale yellow (high, the *inferno* scale), with opacity
rising with the value. When every value is a whole number of spikes per bin
(stage 5b), the scale has one colour step per spike; averages (stage 5a) use a
continuous scale. Cells without a per-cell recording stay faint grey, never
coloured as zero. Play or the slider selects time.
The explicit dummy array is 41 × 952: `0.5 + 0.5 sin(2π t/2 + 0.37 i)`, rounded
to four decimals, at 41 times from 0 to 2 s. HTML, the dummy still and value
exports label it **DUMMY DATA · synthetic sine waves — not a model run**.

A future run supplies JSON with `dataset: "male-cns:v1.0"`, descriptive `label`,
`unit` (e.g. `Hz`), unique string `body_ids`, strictly increasing finite
`times_s` (at least two), and finite `values` shaped `[time, body_id]`.
Every displayed ID must exist **unless its group is explicitly listed in
`anatomy_only_groups`**. Missing values are never filled with zero or with a
population mean. Extra cells are ignored after an explicit ID join, never
assumed to follow engine order. Invalid/missing/duplicate data fails. One fixed
range across recorded displayed cells, **all conditions and all times** sets the
colour scale; a constant array uses its midpoint. The range and unit are shown on
the colourbar. This normalization is visual, not an analytical or biological threshold.

```sh
uv run --locked scripts/render_malecns_3d.py --values /path/to/rates.json --out /path/to/run-atlas
```

Use a separate output directory for real data. Custom builds hash their input
array, start in value mode and write no dummy files. Multi-condition JSON replaces
`values` with `conditions: [{id, label, values, aggregates, phases}]`; IDs are
unique filename-safe strings. `aggregate_specs` gives each aggregate's `id`,
`label` and `unit`; `aggregates.CX_DAN` is a finite nonnegative `[time]` population
total, drawn separately. Optional `bin_edges_s` has one more entry than the bin
centres in `times_s`; phases specify `start_s`, `end_s`, `label`. `kind` is
`model` or `synthetic`, and `summary` describes averaging. The original
single-array dummy input remains supported.

## Recorded calibration activity (5a-01)

**Simulated activity in a male fly brain model. Input injected at TuBu; the fly
does not see. Calibration runs, not the experiment's result.** These labels are on
the HTML, each still and exported views. Conditions are named by their injected
input pattern ("TuBu input pattern +50°"), not by arm number.

- [Offline five-condition viewer](../figures/3d/calibration-5a/male-cns-atlas.html).
- Stills: [off](../figures/3d/calibration-5a/male-cns-arm-00.png),
  [−150°](../figures/3d/calibration-5a/male-cns-arm-01.png),
  [−50°](../figures/3d/calibration-5a/male-cns-arm-02.png),
  [+50°](../figures/3d/calibration-5a/male-cns-arm-03.png),
  [+150°](../figures/3d/calibration-5a/male-cns-arm-04.png).
  Each uses the same middle bin, **[11.00, 11.10) s**, shown as "11.00–11.10 s
  from run start", not a selected peak. `--still-time` chooses another bin centre.
- [Source/extraction manifest](../figures/3d/calibration-5a/manifest.json)
  and [render receipt](../figures/3d/calibration-5a/build.json) hold hashes.

| Display group | Recorded/displayed quantity |
|---|---|
| ER (282) | **Per-cell emitted spike rate**, all 282 columns of `er_edge_presynaptic_counts`; engine indices joined to hash-verified MaleCNS body IDs. The 245 `er_counts` columns cross-check the overlapping trace subset. |
| TuBu (156) | **Per-cell emitted spike rate**, `tubu_counts`, joined by the frozen plan's `source_body_ids`. These are not the injected input-event counts. |
| CX_DAN (27) | **Anatomy only**, grey in value mode. `CX_DAN_counts` is a **population sum**, plotted separately as spikes/s, never copied or divided into per-cell values. |
| MB_DAN (332), KC (155 displayed) | **Anatomy only**, grey in value mode; no matching per-cell recording. The broader `DAN_counts` and `central_counts` totals are not presented as these groups' activity. |

All ten frozen seeds (101–110), wild type, all five recorded input positions;
substrate `rest:ed9b0a469d7a6b77`. Sum ten adjacent 10 ms chunks per 100 ms bin,
divide by 0.1 s, then take the arithmetic seed mean. All 22 s are retained,
including 0–2 s settling with input off. No smoothing or analysis/selection
changes. Cell opacity and aggregate-plot scales each stay fixed across every
condition and time. The position names are imposed TuBu labels, not seen space.

Source: `compute host:~/flyonenomics-t-0077-study/camber-runs/adhd-study/5a-01/`;
only the 50 NPZs, ten complete-seed JSONs and the plan were copied to the Mac.
Each NPZ hash is verified against its seed receipt. Example `seed-101-arm-00.npz`:
`f82ab17d488bf1114cbe33837ca3df42779272752017b9a26894ac06ef7e5589`.
The supplied continuation/analysis plan SHA-256 is
`c40623ac8b8e099f55acd2b0a8899e65a089dfb795bdc2c5ecbdb29b8207d944`.
**The 5a-01 receipts are reconstructed, not original runtime receipts**: their
executed-plan hash is
`893419c653028bf5bbd3073d5e39b127fac085f6a66e92007a806195631cd290`.
Their RNG-audit/replay caveats are preserved verbatim in the manifest; this
visualization does not establish replay verification or an experiment finding.

Rebuild from the copied sources (no box work or neural runs):

```sh
C=/path/to/main-checkout/.cache/malecns-v1.0
uv run --locked scripts/render_malecns_3d.py \
  --study "$C/activity/5a-01/raw" \
  --plan "$C/activity/5a-01/adhd-study-plan.json" \
  --activity-cache "$C/activity/5a-01/display" \
  --source 'compute host:~/flyonenomics-t-0077-study/camber-runs/adhd-study/5a-01/' \
  --out figures/3d/calibration-5a
```

The ignored activity cache holds `values.json` (means), `per-seed.npz`
(`rates_hz[seed,condition,time_bin,body_id]`,
`cx_dan_total_spikes_s[seed,condition,time_bin]`, IDs, seeds, bin edges and label),
and `manifest.json` (source hashes, original receipt caveats, extraction code
hash, derived-file hashes). The committed HTML embeds means, not all seeds;
the identical extraction manifest is published with it.

### Later 5b records: the same command and loader

```sh
uv run --locked scripts/render_malecns_3d.py \
  --study /path/to/5b-01 --plan /path/to/adhd-study-plan.json \
  --pair /path/to/frozen-pair.json --out /path/to/5b-viewer
```

The read-only source folder must contain each frozen `seed-<n>.json` with
`seed`, `stage`, `identity`, `plan_sha256`, `pair_sha256` and ordered `rows`.
Rows carry `condition`, `protocol` (`[history,test]` in 5b), `file`, `sha256`,
`male_array_binding`, and, in current records, `chunk_s`. NPZ fields used are
those in the table plus `er_edge_presynaptic_indices`. Shapes are
`[chunk,recorded_cell]`, except `CX_DAN_counts[chunk]`. Frozen plan fields used:
`identity`, `substrate_id`, `engine_arrays_sha256`, `male_array_binding`, `cells`,
`source_indices`, `source_body_ids`, `seeds`, `timing`. The pair provides `pair`
and the **calibration** plan hash (distinct from the 5b continuation plan hash). Timing comes from hash-bound `data/params-v0.2.yaml`
(`--params` overrides the path), also covering historical receipts without
`chunk_s`. Every seed, arm, source hash, root order and mapping must agree.
The loader reads all conditions without selecting a pair or importing analysis.
It labels settling/history/gap/test and A/B positions from the frozen pair.

`tests/test_malecns_activity.py` exercises made-up 5b manifests/NPZs through
this exact extraction and value loader, including shuffled cell columns,
known bin sums/seed means, and aggregates that remain separate. Synthetic plan
and seed records explicitly set `synthetic: true` (boolean); outputs say
**SYNTHETIC · made-up test records, not a neural run**. The ordinary plan's
`synthetic` validation-results object does not mark its recorded activity as
synthetic. A full-geometry synthetic 5b HTML and the dummy path were also
rendered offline; no real 5b records were accessed.

## Recorded experiment playback (5b-02)

[Offline four-arm 3D viewer](../figures/3d/experiment-5b/male-cns-atlas.html) ·
[four-panel paper PNG](../figures/3d/experiment-5b/primary-four-panel.png) ·
[cinematic film (MP4)](../figures/3d/experiment-5b/cinematic/primary-demo.mp4) ·
[poster](../figures/3d/experiment-5b/cinematic/primary-poster.png) ·
[looping teaser](../figures/3d/experiment-5b/cinematic/primary-teaser.webp) ·
[cinematic page](../figures/3d/experiment-5b/cinematic/male-cns-cinematic.html).
The HTML also supplies four individual stills at the same instant. All four
panels show **wild type (vehicle) and fumin (vehicle), each after A→A+B or
B→A+B history**, during test [0,2) s (run [8,10) s). On the pictures these read
"Normal brain" and "Broken dopamine cleanup", "Input A first" and "Input B first,
then A + B together". The paper figure holds the same bin **[1.00,1.10) s** in all
four panels, lettered a–d (lower case, so they are not read as inputs A and B),
with columns in the condition colours (wild type #0072B2, fumin #D55E00), one
shared colourbar with one step per spike in the 100 ms bin (0–90 Hz), the
central-complex dopamine group total under each panel and a 100 µm bar.

**Seed rule:** before examining the visual activity, choose the smallest
absolute distance of per-seed genotype ΔH_gen to its ten-seed mean in
`adhd-study-results.json`, breaking a tie with the smallest seed number.
Seed **210** has ΔH_gen −0.08965933 versus mean −0.08515599 (distance
0.00450334). This is one illustrative run, not a ten-seed average or a
selection based on appearance; the figure is not the study's statistical test.

**Simulated activity in a male fly brain model. Input injected at TuBu; the fly
does not see. Candidate neural signature, not ADHD or behaviour.** These labels,
the condition, input history and test-relative time appear on every still,
panel and film frame; the run appears as "Simulated fly 10 of 10", not by seed
number. A=−50°, B=+50° are injected input labels, not viewed stimuli.
ER (282 cells) and TuBu (156 cells) are recorded per-cell emitted spike rates.
CX dopamine (27 cells) is anatomy-only in the 3D view and its **recorded group
total** is reported separately in spikes/s, never distributed over cells.
Mushroom-body dopamine and sampled Kenyon cells are grey anatomy only,
**not zero-filled recordings**. The per-cell colour scale (0–90 Hz) and
aggregate plot scale are fixed across all four arms and 20 time bins.

The original raw folder is read-only: only the selected complete-seed receipt
and four NPZ arms are opened after their SHA-256 digests match the independent
650-artifact audit. The plan, pair and hash-bound timing are also checked. Raw
files are never copied or changed; the extracted `values.json` is a derived
cache, whose hash and source hashes are in
[manifest.json](../figures/3d/experiment-5b/manifest.json). The 3D atlas
uses the same MaleCNS geometry and offline browser path as calibration 5a.

### Cinematic film

`cinematic/male-cns-cinematic.html` is a second offline page built from the same
payload as the atlas, with Three.js 0.160.1 bloom (EffectComposer, RenderPass,
UnrealBloomPass, OutputPass and their shaders, MIT) embedded like the core
library. Those ten modules are vendored byte for byte from
`https://unpkg.com/three@0.160.1/examples/jsm/` in
`scripts/malecns_3d/vendor/three-0.160.1/`, with the Three.js licence; their
hashes are build inputs in `build.json`. It plays an 82.9 s film: a title card;
the real anatomy with its groups labelled; a card on the experiment; then the four
arms (wild type then fumin after input A, then the same after input B), each
showing all 20 recorded 100 ms bins held 0.65 s each (model time slowed 6.5×);
and an end card with the project name, Hasan "Rolf" Yildirim and the MaleCNS
attribution. Its own page has play, scrub and a free camera.

How the film turns data into light:

- A recorded cell's steady glow in a bin is `0.16 + 1.25 × spikes / 9`, from its
  recorded spike count in that 100 ms bin; 9 is the most any cell has in any bin.
- Each recorded spike sends one flash along that cell's centreline within the held
  bin. When a spike happened inside the bin is not recorded, so flash start times
  and paths are illustrative; the number of flashes is not.
- Cells without a per-cell recording (central-complex and mushroom-body dopamine,
  Kenyon cells) stay dim blue anatomy, with no glow and no flash. The
  central-complex dopamine group total is a separate step plot in spikes/s.
- Every data frame carries "Glow shows recorded model spiking; flash paths are
  illustrative. Simulated activity; input injected at TuBu; the fly does not
  see." and "Candidate neural signature, not ADHD or behaviour."
- On screen, bloom and overlapping lines make dense bundles brighter. Read
  quantities from the paper figure, not the film.

`scripts/render_adhd_5b_demo.py` then:

1. refuses to run unless the atlas page, cinematic page and extraction manifest
   match `build.json` and `--values` is the file the atlas was built from;
2. probes the film at 248 instants (three per held bin in every arm, and each
   non-data segment) and checks all 952 cells each time: anatomy-only cells dim with
   no flash; recorded cells at exactly the glow above; 0.3 s into each held bin,
   exactly one live flash per recorded spike; no flash outside the four runs;
3. lays out the four-panel paper figure from the atlas's figure mode with
   `scripts/malecns_3d/panels.html`;
4. renders the poster (fumin, input B first, the paper figure's bin, 1920 × 1080)
   and a 5.2 s looping teaser (wild type, input A first, bins 0.4–1.2 s,
   960 × 540, 12 fps). The teaser is an animated WebP: a 256-colour GIF banded
   the glow and came out at 4–9 MB;
5. encodes every film frame at 1280 × 720, 30 fps in the browser (WebCodecs
   H.264 High, 0.85 Mbit/s target, a key frame at least every 2 s), packs the MP4
   itself (no ffmpeg), plays it back in Chrome and compares decoded frames with
   fresh renders.

The probe rule and decoded-frame differences are recorded under `demo` in
`build.json`.

Rebuild the viewer, stills and cinematic page (needs `uv`, Chrome and the
existing MaleCNS visual cache), then the film, poster, teaser and paper figure
(Pillow and Playwright are pinned in the second script's lock):

```sh
RAW=<local-project-root>/.worktrees/t-0077/camber-runs/adhd-study/5b-02
CACHE=/path/to/main-checkout/.cache/malecns-v1.0/activity/5b-02/primary-seed-210
uv run --locked scripts/render_malecns_3d.py \
  --primary-5b --study "$RAW" \
  --plan validation/records/p2/adhd-study-plan.json \
  --pair validation/records/p2/adhd-study-pair.json \
  --activity-cache "$CACHE" \
  --out figures/3d/experiment-5b
uv run --locked scripts/render_adhd_5b_demo.py \
  --out figures/3d/experiment-5b --values "$CACHE/values.json"
```

Input SHA-256 (plan and pair are distinct frozen records):

| Input | SHA-256 |
|---|---|
| `seed-210.json` | `7e4e6363b6a373a47d87d7eadad038217772efe0cc5238d76f051a04b8a6d04d` |
| `seed-210-arm-05.npz` (wild type, A→A+B) | `12d7a35cf20b774c5e071e1fce63b57d7b51bb4a7346f6d09f947ae608c9168e` |
| `seed-210-arm-07.npz` (wild type, B→A+B) | `6adf39c056d78f05028ac7e89d627c9f31dbc0a9e28e9bbdc933d5975eb7e452` |
| `seed-210-arm-13.npz` (fumin, A→A+B) | `967d131b3f6f590dbce748a057b2fda5ca4a2983d92a33e356e5096ed2f5437b` |
| `seed-210-arm-15.npz` (fumin, B→A+B) | `312ef5a9d4441af2426db983aa92233cf988b93cba1868d04bc7e348ccafbf7c` |
| `adhd-study-plan.json` | `dc1fb1df32b795303a16a931673cabdbf570d7ef0b446542808e8c5e37835b29` |
| `adhd-study-pair.json` | `b941a440714244811e9ce305a45e678d5f9e5ea25a4a8f2ed638c0f630eff4dc` |
| `params-v0.2.yaml` | `a029f2341e301c2dd36443ae349a33952b017f7c4a0b4e50eabc6dc14369ad9e` |
| `adhd-study-5b-audit.json` | `4af5fbf07ce096fcd0a31ba0f940c2086dfd81c90c86f7e664b19ff3311f2ab5` |
| `adhd-study-results.json` | `47c6fc6e9ef83b13bdacc3af1b89b96f6b3b8d6f25c0bd1dd577d42326c0657e` |

Output SHA-256 (`figures/3d/experiment-5b/`; full code/asset hashes and
Chrome version in [build.json](../figures/3d/experiment-5b/build.json)):

| Output | Bytes | SHA-256 |
|---|---:|---|
| `male-cns-atlas.html` | 6,830,289 | `71afb3afcc2a8a10e1dbc08af99a34e27640eb9fe2cf6d28299304a1fb095ecb` |
| `male-cns-atlas.png` (same bytes as `male-cns-wt-a.png`) | 2,219,621 | `28446cd46fd3b84dd7c0a4e0aa48df51b8155ad6f7c9905a789724da161e4e9d` |
| `male-cns-wt-a.png` | 2,219,621 | `28446cd46fd3b84dd7c0a4e0aa48df51b8155ad6f7c9905a789724da161e4e9d` |
| `male-cns-fumin-a.png` | 2,223,881 | `9f8cae0553802649ebefbd1ec241f8be5db5c7eb92d2d0a925f4622e352e6052` |
| `male-cns-wt-b.png` | 2,227,824 | `bd071decc6082f41416864a3ced005bc1a870c11624fd06ee926178b65017498` |
| `male-cns-fumin-b.png` | 2,246,060 | `d1548d5f876f767763aaa7c16cab16ea68d6df04181f87c57c00a0b4cb1fec94` |
| `primary-four-panel.png` | 2,519,198 | `4f43fa1dd14d390f37bc1b27098932cb0177ab3c01c580a38759357ba092836e` |
| `cinematic/male-cns-cinematic.html` | 6,867,589 | `32319951e9239a4838ad36d1c75d8d84bffbeadf2808208718959fe378d6d887` |
| `cinematic/primary-demo.mp4` | 9,176,090 | `bd86690d526193a16ac28c6f10844e60e07c30786d51369429a2ea6561a68a73` |
| `cinematic/primary-poster.png` | 1,401,250 | `7ee6a67902fe779d92200080a68123de90e647bb03a39aebdb0dab59951cdc2d` |
| `cinematic/primary-teaser.webp` | 1,113,952 | `76609b83469bf77172fc387d8c8d4c77b4e70824110d687360ee41d9635549dc` |
| `manifest.json` | 1,475 | `3f514e4fe446ee77d1b58c3255e3b2da0ddbb9c73876b946dadf8c6f1552fe7a` |

Every output is under 10 MB; browser raster and video pixels may vary with
Chrome, GPU, OS and font versions. `build.json` records exact local hashes; it
is a receipt, not an input to the renderer. The root `figures/3d/build.json`
is the separate anatomy/dummy build and is not a list of study playbacks.

## Attribution

MaleCNS v1.0, Janelia Research Campus, Google Research and University of
Cambridge; Berg et al., *Sexual dimorphism in the complete Drosophila male
central nervous system connectome*, **Cell** (2026),
<https://doi.org/10.1016/j.cell.2026.08.015>. CC BY 4.0. Geometry is simplified
and recoloured here. Attribution is in the HTML/PNGs; Three.js's MIT notice is
embedded in HTML and retained in the cache.

## Chemical and courtship circuit views

[The overview](../figures/3d/circuit-tour/overview.png) shows one rate-change view for each chemical block and injected courtship condition on the same MaleCNS geometry. Individual views live beside it, including [high P1 drive](../figures/3d/circuit-tour/P1-high.png). Red means higher firing than the paired control; blue means lower. They show anatomical representatives, not every simulated neuron. The full-neuron rate arrays and exact paired summary are saved with the local run records; the images contain no seed or build identifiers. Input is injected and the fly does not see or sing. See [results](circuit-tour-results.md) for what the spikes do and do not show.
