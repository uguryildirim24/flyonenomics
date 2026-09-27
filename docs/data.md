# External data and attribution

## Current: MaleCNS v1.0

Start with [REPRODUCE.md](../REPRODUCE.md) for the current male model's setup
and manifest-driven download. Its seven flat tables total 24.38 GB and are
listed, with official URLs and SHA-256 values, in
[`data/malecns-v1.0-manifest.json`](../data/malecns-v1.0-manifest.json).
The model build and transformations are described in [the port guide](malecns-port.md).
The much smaller, separate [3D build](3d-model.md) downloads only selected
anatomy and viewer dependencies; it does not need the numerical tables.

MaleCNS v1.0 is by Janelia Research Campus, Google Research and University of
Cambridge; Berg et al., *Sexual dimorphism in the complete Drosophila male
central nervous system connectome*, **Cell** (2026),
<https://doi.org/10.1016/j.cell.2026.08.015>, under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Derived graphs/assignments retain the source attribution; the atlas is
simplified and recoloured. Three.js's MIT notice is embedded in its HTML.
The dashboard's separate uPlot dependency retains its
[MIT notice](../src/flyonenomics/dashboard/static/vendor/LICENSE).

Project code is [MIT licensed](../LICENSE), chosen by Rolf on
**2026-09-23 (a-19)**, matching the package metadata. This does not replace
any of the third-party code or data licences here, including CC BY 4.0 for
MaleCNS-derived data. The repository stays private;
other release decisions remain open, as recorded in an internal release audit held outside the public snapshot.

## Historical: FlyWire assets

The remainder describes the female FlyWire-era assets and their setup.
Small curated files under `data/` are committed and need no download.
`scripts/fetch_data.py` fetches or verifies these historical assets, not MaleCNS,
and records sizes and checksums in `data/provenance.json`. Provenance records use paths of the
form `.cache/...`, which resolve under `$FLYONENOMICS_CACHE_DIR` when set and
under the repository `.cache` otherwise.

The FlyWire/FAFB source work is credited to Dorkenwald et al. and the FlyWire
Consortium, [*Nature* (2024)](https://doi.org/10.1038/s41586-024-07558-y),
with annotations from Schlegel et al.,
[*Nature* (2024)](https://doi.org/10.1038/s41586-024-07686-5).
The computational starting point is Shiu et al.,
[*A Drosophila computational brain model reveals sensorimotor processing*,
Nature (2024)](https://doi.org/10.1038/s41586-024-07763-9).
Project-derived parameters and simulations are additions, not upstream data.

## Shiu model clone

The Shiu 2024 whole-brain model code and connectome files live at
`.cache/Drosophila_brain_model` from `https://github.com/philshiu/Drosophila_brain_model`
at commit `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960`. The five data files are
the v630 completeness list (3,057,611 bytes) and connectivity (86,630,944
bytes), the v783 completeness list (3,327,347 bytes) and connectivity
(100,804,642 bytes), and `sez_neurons.pickle` (5,114 bytes); `model.py`,
`utils.py`, `example.ipynb`, and `figures.ipynb` are pinned by the same commit. The repository
is MIT licensed; the underlying FlyWire data is CC-BY 4.0. A fresh machine
clones the repository at that commit into the cache directory before running
the fetch script, which verifies the checkout but never modifies it.

## Shiu 2024 simulation archive

The published simulation outputs live at `.cache/shiu-archive/results.zip`
(4,499,610,373 bytes, SHA-256
`f757c8e18e3826c89ba12f930bee455bb6dc22f28403a27161e9b9d9f0a65e93`,
MD5 `f6f2e314821fa6a4196214e3b2b14bc4`). It comes from the Edmond record
`https://doi.org/10.17617/3.CZODIW` (dataset version 3, file id 223847),
whose license is MIT. The record offers no separate sugar file, so the fetch
script downloads the whole archive. The archive holds 11,157 files: 11,012
parquet spike outputs, 142 rate CSV files, and 3 pickles, covering every
simulation in the paper's `figures.ipynb`.

Test 1.2 needs only the published right-sugar-GRN stimulation on v630, so the
fetch script extracts two members and records each with its own size and
SHA-256: `.cache/shiu-archive/sugarR.parquet` (770,820 bytes, the notebook's
default 30-trial sugar run) and `.cache/shiu-archive/sugarR_150Hz.parquet`
(769,702 bytes, the figure 1 run at 150 Hz). Each holds 30 one-second trials
with spike times, trial numbers, and FlyWire IDs; per-neuron rates derive with
the upstream `utils.get_rate` helper. Nothing else is extracted.

## FlyWire annotations

The v783 registry source `.cache/annotations-v2.1.0.tsv` (27,015,208 bytes)
and its column documentation `.cache/annotations-v2.1.0-columns.md` (6,674
bytes) come from `flywire_annotations` release v2.1.0 at commit
`ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0`. The v630 bridge file
`.cache/annotations-v1.1.0.tsv` (21,714,061 bytes, SHA-256
`55c99c61eecf8db6cc36f1a684b35e4c4208afbab02197d753ccc8dc2a6e2e76`)
comes from release v1.1.0 at commit `df6bb136f5b3d91c3992df4e8de2642329e2a384`.
Both are CC-BY 4.0 and are downloaded from pinned raw URLs by the fetch
script.

## Buridan reference data

The Colomb and Brembs 2014 trajectories live at
`.cache/github-importJnx5V7.zip` (6,728,585 bytes, MD5
`c9e8e9c72fc04a694fb24e4f84b9699d`) from figshare article 1014264 version 2
(DOI `10.6084/m9.figshare.1014264.v2`), licensed CC BY 4.0. The archive holds
135 `.dat` trajectory files and 134 `.xml` headers, which the fetch script
counts on every run.

## CeTrAn metric sources

The normative metric definitions live under `.cache/CeTrAn/` at tag `v.4`,
commit `1f98ddd83366db53d4aabfa6f42b1153f8e1553d`: `functions.r`, `utils.r`,
`angledev.r`, and `CeTrAn_fromxml_4.rgg`. They are downloaded from pinned raw
URLs and used under the Creative Commons Attribution 3.0 Unported License
stated in that commit's README.

## Per-neuron input synapse counts

The completeness detector divides each population's in-model input synapses by
an external per-neuron input total. That denominator is the open Zenodo copy
of the Codex v783 release, record 10676866 (FlyWire whole-brain connectome
connectivity data, DOI `10.5281/zenodo.10676866`), file
`per_neuron_neuropil_count_post_783.feather` (233,843,050 bytes, SHA-256
`e2418f4794fe47984bb4bc15ffc194003ea8e349a428551f30af94947d85d712`),
stored at `.cache/zenodo-10676866/per_neuron_neuropil_count_post_783.feather`
under CC-BY 4.0. It has 43,439,994 rows and 3 columns
(`post_pt_root_id`, `neuropil`, `count`); summing `count` over neuropils per
`post_pt_root_id` gives the per-neuron input total. The native Codex download
(`https://codex.flywire.ai/api/download`) is not fetched because its Download
Data app needs a Google sign-in, which an unattended fetch cannot provide; its
provenance record stays `not fetched` with that reason, and the 9,492,998,242
byte synapse table is not needed while the 234 MB export exists.

## Proof-run reference copies

`data/reference/l5-baseline-spikes.parquet` and
`data/reference/l5-baseline-results.json` are committed copies of the WP0
proof-run outputs (seed 20260912, v630, 21 right sugar GRNs at 150 Hz,
upstream-exact mode) used by test 0.3. The fetch script verifies them against
the recorded hashes and copies them only when missing.

## Fresh machine recipe

Set `FLYONENOMICS_CACHE_DIR` to the shared cache, clone the Shiu repository
at the pinned commit into `$FLYONENOMICS_CACHE_DIR/Drosophila_brain_model`,
run `uv sync --frozen`, then run `uv run python scripts/fetch_data.py`. The
script downloads about 4.79 GB in total (4.50 GB archive, 234 MB Zenodo
table, 55 MB of smaller files) and verifies everything else. The
per-invocation byte guard defaults to 30 GB and is read from the single
function `download_limit_bytes`, which honours
`FLYONENOMICS_DOWNLOAD_LIMIT_BYTES` when set. A second invocation transfers
zero bytes and leaves `data/provenance.json` unchanged. Never delete or
rename cache entries by hand; lanes share the cache.

For a new cache, the exact setup commands (from the project checkout) are:

```sh
export FLYONENOMICS_CACHE_DIR="${FLYONENOMICS_CACHE_DIR:-$PWD/.cache}"
mkdir -p "$FLYONENOMICS_CACHE_DIR"
git clone https://github.com/philshiu/Drosophila_brain_model "$FLYONENOMICS_CACHE_DIR/Drosophila_brain_model"
git -C "$FLYONENOMICS_CACHE_DIR/Drosophila_brain_model" checkout --detach 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960
uv sync --frozen
uv run python scripts/fetch_data.py
```

The roughly 4.79 GB fetched by the script excludes the Git clone transfer.
The committed proof references require no local `l5-proof` directory.
`figures.ipynb` supplies the authoritative bitter-GRN literal (SPEC 11.9)
and is verified against its pinned Git object and recorded SHA-256.
