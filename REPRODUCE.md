# Reproduce the current results

This guide covers the **male substrate, rest measurement, literature research,
3D atlas and completed first perturbation experiment** reported on the front page.
The first ten-seed study is complete: the vehicle genotype contrast was nominal
only (Holm p = 0.0703125), and the release interaction had **no detected
difference**. [Results](docs/adhd-study-results.md) · [paper reproduction records](paper/README.md).
The follow-up was planned and frozen in advance and is **under review**, not
yet a reviewed finding. Experimental input is injected at TuBu; **the fly does not see**. Rest metrics
and neural responses are not behaviour or ADHD.

[Provenance erratum for frozen parameters and engine notes →](docs/errata.md)

The snapshot pin below describes the earlier substrate/rest/atlas audit;
§7 instead identifies each experiment's actual executed revision. No numerical
or rendering jobs were rerun for this documentation update. Historical FlyWire
work is indexed in [docs/index.md](docs/index.md), not relabelled as male evidence.

Project code is [MIT licensed](LICENSE); third-party code and data licences
remain separate. The original raw archives are not included in this source
snapshot. See the committed result records for their file hashes.

## 1. Pin the checkout and environment

The original private-source evidence snapshot was
`287ffa4275e22a07fb59d150024b941c150d47ac`. It is a provenance
identifier, **not a commit available in this fresh public repository**. The
export manifest records the source revision of the public snapshot. Use a
separate checkout for reproduction: several builders overwrite tracked outputs.
Do not run these commands in a checkout executing an experiment.

From the public checkout:

```sh
uv sync --frozen
export FLYONENOMICS_CACHE_DIR="$PWD/.cache"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
```

Requirements: Git, [uv](https://docs.astral.sh/uv/), Python **3.12** (the
recorded numerical runs used 3.12.14), and a C/C++ compiler with Python headers
for Brian2's Cython backend. ARM macOS and ARM Linux have recorded runs;
platform is provenance, not a scientific acceptance rule. The dependency pin
is [`uv.lock`](uv.lock), SHA-256
`be51ced5948bb3907d0c7233fff57419fcaa1b363a79f1a9f87d5a07a24ad619`.
No GPU is needed for numerical runs. Opening the committed atlas needs only a
current WebGL-capable browser; rebuilding it additionally needs Google Chrome.

### Required Shiu code-only checkout

Before **any numerical command**, pin the upstream code used by the male
engine. `BrianEngine.build` loads `model.py` from this location even when using
MaleCNS rather than the historical female FlyWire connectome:

```sh
git clone https://github.com/philshiu/Drosophila_brain_model "$FLYONENOMICS_CACHE_DIR/Drosophila_brain_model"
git -C "$FLYONENOMICS_CACHE_DIR/Drosophila_brain_model" checkout --detach 91bdd1e7dcf193f3e7ca5a8933497fcef63b7960
```

The Shiu model **code is MIT licensed**; its original FlyWire data is CC BY
4.0 ([source and licence details](docs/data.md#shiu-model-clone)). This checkout
supplies code/defaults, **not** female-connectome outcome data. Do not download
the unrelated multi-gigabyte historical simulation archives for this step.

### Male source data: one-time download, not a model run

The seven flat tables total **24,377,419,334 bytes**, excluding derived arrays,
Python packages and outputs. URLs, individual sizes and expected SHA-256 values
are in [`data/malecns-v1.0-manifest.json`](data/malecns-v1.0-manifest.json),
under `files`. They are MaleCNS v1.0, CC BY 4.0 (Berg et al.; Janelia, Google
Research and Cambridge). Keep this attribution with derived data.

The older `scripts/fetch_data.py` provisions **FlyWire**, not MaleCNS. The
feasibility downloader fetches only three male tables, insufficient for the
current adapter. This manifest-driven command obtains all seven and verifies
existing files too. It downloads no raw EM, segmentation or full mesh archive:

```sh
uv run --frozen python - <<'PY'
import hashlib, json, os, urllib.request
from pathlib import Path

rows = json.loads(Path('data/malecns-v1.0-manifest.json').read_text())['files']
assert len(rows) == 7 and sum(r['bytes'] for r in rows) == 24_377_419_334
cache = Path(os.environ['FLYONENOMICS_CACHE_DIR']) / 'malecns-v1.0'
cache.mkdir(parents=True, exist_ok=True)
for row in rows:
    target = cache / row['name']
    candidate = target if target.exists() else target.with_suffix('.part')
    if not target.exists():
        with urllib.request.urlopen(row['url'], timeout=120) as src, candidate.open('wb') as dst:
            size = 0
            while block := src.read(1 << 20):
                size += len(block)
                if size > row['bytes']:
                    raise RuntimeError(f"unexpected size: {row['name']}")
                dst.write(block)
    with candidate.open('rb') as src:
        digest = hashlib.file_digest(src, 'sha256').hexdigest()
    if candidate.stat().st_size != row['bytes'] or digest != row['sha256']:
        raise RuntimeError(f"checksum mismatch: {row['name']}")
    if candidate != target:
        candidate.replace(target)
    print(row['name'], digest)
PY
```

Cost: network/disk dependent; no end-to-end download time is recorded. The
production graph consumes five of these tables (10,537,867,410 bytes); the
other two support anatomy audits. Do not interpret source-file size as the RAM
requirement. Figure-only reproduction skips this download entirely.

## 2. Male graph and adopted starting substrate

### Graph conversion (no simulation)

```sh
uv run --frozen python -m flyonenomics.datasets build-male
```

Inputs: the manifest's five `MALE_ENGINE_SOURCES` listed in
[`datasets.py`](src/flyonenomics/datasets.py). Outputs go to
`$FLYONENOMICS_CACHE_DIR/malecns-v1.0/derived/`: annotations, engine order,
connectivity and `provenance.json`. The graph has **162,517 nodes,
25,120,209 signed pairs and 122,181,879 represented synapses**, with no added
weight cut. [Conversion and exclusion rules](docs/malecns-port.md).

Expected **array** hashes below are from
[`malecns-substrate.json`](validation/records/p2/malecns-substrate.json), not
hashes of the CSV/Parquet containers. The derived provenance records container
hashes. Conversion-only elapsed time and peak RAM were not separately recorded.

| Array encoding | SHA-256 |
|---|---|
| roots, little-endian int64 | `88b9d91aa2593b2f019567dea5ccbe1a900d7daf73c8e1a9308773a305928aa9` |
| presynaptic indices, little-endian int32 | `7c9b158dd4699451c2697848f5c2c5e3f36935e70d7118c0a5c86197f0a149b4` |
| postsynaptic indices, little-endian int32 | `ca8c7cafe58328f1bc9e73e756babce1244c0111a3415b01f80b062728f22737` |
| signed weights, little-endian float64 | `3a7b3dfb054a8ec8be611b243b1755454cc2d5177a1703c0e1a1cc1b348d7868` |

### Starting configuration (no new rest measurement)

```sh
uv run --frozen python scripts/malecns_substrate.py --regenerate
```

Inputs: the male graph/cache, committed male anatomy tables, both parameter
versions, source code and the **already committed** K2r measurement (the
three-seed dopamine-release measurement). All 18 input pins are enforced by
[`malecns-substrate-inputs.json`](validation/records/p2/malecns-substrate-inputs.json).
This command recomputes the recorded release chain; it does not run the 701
brain-seconds again. Output identity: **`rest:ed9b0a469d7a6b77`**.

| Output | Expected SHA-256 |
|---|---|
| `data/drive-male-cns-v1.0.yaml` | `ed9b0a469d7a6b77bed2a346d0a71d33252a2484aa5d6c9486b3f201c5bd1913` |
| `data/dopamine-male-cns-v1.0.yaml` | `e6fdafe53ccf025db44dee55a85174c89d56c5fe6a012fd1bff3f40d3e60d653` |
| scale array, little-endian float32 | `fb6270f518f06cd0adb42748ae10baa360dec752edd237ce7ecdefa70450a84c` |
| committed K2r input JSON | `db6a7188d908eb4681a360d1170c516fd8d1a4dbede925cbb72e3c4ef171a77e` |

Regeneration was exercised on ARM Linux/macOS, but its standalone elapsed time
and peak RAM were not recorded. It builds/loads large arrays, not an engine.
A pin mismatch is a changed-input result; do not bypass it to obtain the old ID.

### Reported execution and seed checks (optional numerical runs)

| Reported artifact | One command | Inputs and recorded cost |
|---|---|---|
| Initial no-input adapter check, cached `malecns-v1.0/probe.json` | `uv run --frozen python scripts/malecns_probe.py` | Male graph and unchanged `params-v0.2.yaml`, seed 20260921. ARM Mac: 3.342 s engine build + 8.417 s run, 2.05 GB peak RSS; ARM Linux: 6.884 + 26.159 s, 1.75 GB. Expected zero spikes; graph array hashes above. |
| Rest cost probe underlying `malecns-rest-plan.json` | `uv run --frozen python scripts/malecns_rest.py --probe --output camber-runs/malecns-rest/cost-probe.json` | Fixed clamped rest setup, seed index 1, one brain-second. ARM Linux: 191.13 s total, 113.35 s run, 7.28 GB peak RSS. This emits the probe, not the hand-assembled plan wrapper. |
| One-second free-pool execution check, `malecns-substrate-probe.json` | `uv run --frozen python scripts/malecns_substrate.py --probe` | Adopted tables and pins above; master seed 20260912, index 1. ARM macOS 27, Python 3.12.14: 60.54 s total, 28.56 s engine run, 7.17 GB peak RSS. |
| Distinct seed streams and exact seed-1 replay, `malecns-seed-check.json` | `uv run --frozen python scripts/malecns_substrate.py --seed-check` | Male anatomy and fixed clamped rest setup; indices 1, 5, 1, 100 ms each. 16-core ARM Linux: 91.35 s total, 7.15 GB peak RSS. |

The last two commands write under `validation/records/p2/`. The free-pool
probe's expected count-array
SHA-256 is `d2027b484f67ee7da33155444fe74e3e711d0195915ae0804d97dc2ad68d039a`.
Per-seed spike-index/time hashes are in
[`malecns-seed-check.json`](validation/records/p2/malecns-seed-check.json):
5,059 spikes for seed 1 versus 3,595 for seed 5. Whole receipt bytes change with
wall time, memory and platform; do not compare those as deterministic outputs.
These checks are not evidence of biological stability or behaviour.

## 3. Ten-seed rest measurement

**Heavy.** After setup, this single shell command runs all 43 arms and summarizes
them in a new ignored directory; the directory must not already exist:

```sh
mkdir -p camber-runs/malecns-rest && \
mkdir camber-runs/malecns-rest/reproduction && \
uv run --frozen python scripts/malecns_rest.py --run --workers 8 \
  --output-dir camber-runs/malecns-rest/reproduction \
  > camber-runs/malecns-rest/reproduction/run.log 2>&1 && \
uv run --frozen python scripts/malecns_rest.py --summarize \
  --output-dir camber-runs/malecns-rest/reproduction \
  --output camber-runs/malecns-rest/reproduction/summary.json
```

Inputs: male graph, population/compartment/receptor/transmitter tables,
`params-v0.1.yaml` (registry) and `params-v0.2.yaml` (engine), and
[`malecns_rest.py`](scripts/malecns_rest.py). It constructs the fixed sensory
background in memory, uses clamped dopamine, and **does not load the subsequently
adopted dopamine calibration as an input to its own measurement**. Master seed
20260912; seed indices 1–10. Original runner commit: `2ef6711`.
The [frozen plan and every measured value](docs/malecns-rest.md) specify windows,
weights and the dopamine equations.

Recorded cost: **701 brain-seconds, 8,626.29 wall seconds (2 h 23 min 46 s)**,
eight workers on 16-core Linux/aarch64, Python 3.12.14, 101,036,359,680 bytes
physical RAM (about 94 GiB). Largest worker RSS: 7,261,716,480 bytes; summed
worker peaks: 58,023,702,528 bytes. Use fewer `--workers` if memory is limited;
that runtime has not been measured. No dollar cost was recorded for this run.

Outputs: ten `seed-N.json` files, `run-complete.json`, `run.log` and
`summary.json`. Expected numerical values include central mean **4.789499 Hz**
at 1.0 mV and **5.029575 Hz** at 1.2 mV, and all the per-seed rows in
[`malecns-rest.json`](validation/records/p2/malecns-rest.json).
That committed report's SHA-256 is
`d4815a59674e3a6dc38ba9c3081e029d99834a09fa4f426d6dd7822a3adbbbf5`.

**Reproduction boundary:** the committed report is a curated record, not the
schema emitted by `--summarize`; no committed command assembles it verbatim.
Original raw-file hashes are in its `raw.files_sha256`, including summary
`3365c6830e8b543739c07bc1c362fd24dde7d9d46f7213b897be34fe7bd4196f`.
They identify the original files, not expected hashes for a rerun containing
new timings/PIDs/platform metadata. The original raw directory is ignored,
and no public archive URL is recorded. Thus a clone can rerun the measurement
and inspect committed per-seed values, but cannot retrieve the original raw
receipts from Git alone. Publishing those receipts and the curated-report
assembler remains a release gap.

If the **original** raw files become available, extracting the committed K2r
input is a separate, non-simulation command (uses the original hashes):

```sh
uv run --frozen python scripts/malecns_substrate.py --import-k2r camber-runs/malecns-rest/run-20260922T125727Z
```

Do not feed newly timed seed JSON files to this importer; it deliberately
requires the original bytes. Extraction-only time was not recorded.

## 4. Literature research

Artifact: [`docs/adhd-model-research.md`](docs/adhd-model-research.md).
One command verifies which text is being read, with no data/model dependency:

```sh
shasum -a 256 docs/adhd-model-research.md
```

Expected SHA-256 for the **current file** after its dated provenance banner and
erratum link: `5b3f8e99ba01b23460c1b2fa9344ed54ddd14caa7e313ef269f8ae614d252687`.
The 22 September reviewed text, before that banner, hashed to
`2d90766ca6d427b983c33712b7a91f6b7b2e91b88d195a2fff040ff7d0a47327`.
The current file comes from the integration with the dated banner; recheck its
hash if further edits are merged. Inputs are its 21 linked papers/access records and code-inspection snapshot
`18072403d27c4951f1444d62a4792fe549eaf2f3`. This is an **AI-assisted,
source-checked research document**, not an algorithm with a regeneration
command; it is not represented as an independent human literature review.
Follow its DOI/PMC links to repeat the source checks; abstract-only findings
are labelled.
Any laptop can verify the text; review effort was not timed and no simulation
compute was used. A checksum verifies the document, not its scientific truth.

## 5. 3D anatomical model and dummy playback

Skip all numerical-data setup. From the checkout, with Chrome installed:

```sh
uv run --locked scripts/render_malecns_3d.py
```

Inputs: the released annotation table, 1,006 selected geometry/vendor assets
in the male manifest's `visual_files`, committed population selectors,
viewer and paper-figure templates and the script's own lockfile. Total sources: **164,622,937 bytes**;
no connectivity or simulation is used. Default output: `figures/3d/`.
[`build.json`](figures/3d/build.json) pins source/code hashes, displayed IDs,
reductions and browser version; [methods](docs/3d-model.md) explain the selection.

| Output | Expected SHA-256 |
|---|---|
| `male-cns-atlas.html` | `3401ea6a695dedeb25e6656ab19adfe93f77c82a63a046685d0f2631c63fa2a8` |
| `male-cns-atlas.png` | `2a339b7966c197d578d89cb4de3f04184071ace167bbdead33c4780ea0bbba8c` |
| `male-cns-anatomy-paper.png` (paper anatomy figure) | `e78b713996494a2f10c0a5a8ae4fe90c92ed7f9adea57f7f10150abd19f26c3f` |
| `male-cns-dummy-playback.png` | `f56527dd74a10c4ef045d40d32f98ce93b85f9c92c1e225d61abe3032d660e28` |
| `dummy-values.json` | `2b6b6312ff95e58a2776e24ed381dc0d8a4673b8a48e8ccb1eb6876a0a07e16d` |

Recorded machine: ARM Mac, Chrome **153.0.8010.53**, WebGL 2, Three.js 0.160.1.
A cached rebuild fetched zero bytes, and a second build gave the same hashes
for all three PNGs and `dummy-values.json`.
Elapsed time and peak memory were not recorded. Raster hashes can differ with
browser/OS/GPU; receipt download counts differ between cold and warm cache.
The playback values are synthetic sine waves, **not experimental results**.

## 6. Supporting male anatomy artifacts

These are already committed inputs to the current model. Rebuild only in an
independent checkout; the historical dopamine-table builder writes **unset**
drive/dopamine tables, not the adopted substrate.

| Artifact | One command | Inputs, expected hashes and cost |
|---|---|---|
| Population table and `malecns-populations.json` | `uv run --frozen python scripts/build_malecns_populations.py` | Male derived graph, annotation/NT/weight/partner/point tables; FlyWire population rules and reference cache from [data guide](docs/data.md). YAML SHA-256 `4b67f2a4d5d54b5bb552bdd54ec350d99842d239a35d5c4cfb48f73daa3bdb63`. Static CPU/table work; standalone time/RAM not recorded. |
| Partial eye assignment and `malecns-eye-assignment.json` | `uv run --frozen python scripts/malecns_eye_assignment.py` | Male annotations/weights and committed feasibility comparison record. Parquet SHA-256 `ec5bacb5064561f3c15812ca6aceee43fe930bff3eeaf6413a4ea6beafbacab4`; source pins and rules in the JSON. Static CPU/table work; time/RAM not recorded. |
| Pre-calibration dopamine anatomy audit, `malecns-dopamine-tables.json` | `uv run --frozen python scripts/malecns_dopamine_tables.py --write` | Male and FlyWire caches/registries, declared compartment/receptor rules. Expected historical file hashes: record's `files`; W/M/receptor hashes: `structural_comparison`. Static CPU/table work; time/RAM not recorded. **Overwrites adopted drive/dopamine values with nulls.** |

These builders are not a complete from-zero curation pipeline: anatomical
rules and some tables were committed by hand. The dopamine audit predates the
adopted drive/dopamine files, so its two old hashes are intentionally not the
current hashes in §2. Keep the committed runtime tables for a normal rest run.
The earlier feasibility graph/probe used a now-superseded weight cut; see the
historical documents rather than using it to reproduce the current substrate.
The value-classification, plan, preservation and full-gate JSON records are
hand-assembled decisions/verification receipts, not separately scripted
scientific results; their wrappers have no one-command generator.

## 7. Completed first male perturbation experiment — technical provenance

The [frozen design](docs/adhd-study-design.md) (SPEC-P2 §10 item 156)
compares modelled transporter loss (*fumin*) and reduced release using artificial
TuBu input. **The fly does not see.** The [reviewed first-study result](docs/adhd-study-results.md)
shows a nominal genotype contrast that did not survive the frozen
two-test correction, and no detected difference in the release interaction. It is a candidate neural signature
in one fixed model, not ADHD, attention or behaviour. These are the **recorded
commands**, not an instruction to run heavy jobs on the shared box now. For
an exact historical replay use the stated executed revision and frozen inputs;
§1's older snapshot does not contain the eventual experiment runner and records.
Do not replace these commands with historical FlyWire `ring_dopamine_stage*.py` runs.

All neural runs and numerical analysis were on the ARM64 Linux box
`compute host:<compute-run-root>` with the MaleCNS cache at
`$HOME/flyo-cache`. The original raw `5a-01` and `5b-02` files are ignored by
Git, retained on that box and copied to the Mac under
`camber-runs/adhd-study/`; there is no public raw archive. To run from a clean
checkout with those files, the cache and `.venv` provisioned, use the recorded
source/plan/pair bindings rather than switching to the old §1 snapshot.

### Calibration 5a-01 — historical run, failed RNG audit

At executed revision `f774c3bdb3dcac6f0c766c45bfe5fd77122a381a`, the
recorded command was:

```sh
.venv/bin/python scripts/adhd_study.py 5a --workers 10 --out camber-runs/adhd-study/5a-01
```

On `compute host`, ten workers completed the original calibration arm files in
**12,526 s** wall (exit 1 at the whole-seed RNG audit; no complete runtime
seed manifests). Do **not** present this as a clean successful rerun. The
original plan SHA-256 is `893419c653028bf5bbd3073d5e39b127fac085f6a66e92007a806195631cd290`;
the later analysis uses the archived calibration plan SHA-256
`c40623ac8b8e099f55acd2b0a8899e65a089dfb795bdc2c5ecbdb29b8207d944`.
The 5a replay record holds the original files' expected per-arm SHA-256 values
under `raw_sha256`; it is held outside the public snapshot because it carries
machine paths and run logistics, and is available from the author on request;
for example `seed-101-arm-00.npz` is
`f82ab17d488bf1114cbe33837ca3df42779272752017b9a26894ac06ef7e5589`.
Post-hoc selection-only receipts are **not** original runtime certificates.
The replay of the first two seeds matched NPZ bytes but failed its corrected
RNG audit; the rest were skipped under d-0025. The pair was committed before
5b; the frozen pair record SHA-256 is
`b941a440714244811e9ce305a45e678d5f9e5ea25a4a8f2ed638c0f630eff4dc`.
The [pair-selection command](docs/adhd-study-part-a.md#historical-d-0023-run-sequence--superseded-by-d-0025-above)
is recorded there; it is not a certification of the old RNG pairing.

### Experiment 5b-02 — audited run

At executed revision `f28779b2099018f7188de8c7f73234c0c53b828f`, after the
d-0025 repair and qualification, the recorded command was:

```sh
FLYONENOMICS_CACHE_DIR=$HOME/flyo-cache .venv/bin/python scripts/adhd_study.py 5b --workers 10 --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/5b-02
```

On `compute host`, **ten workers, 73,374 s wall, exit 0**. The run uses plan SHA-256
`dc1fb1df32b795303a16a931673cabdbf570d7ef0b446542808e8c5e37835b29`
and the pair hash above. Expected raw NPZ, journal and seed-manifest hashes are
listed individually in the [exact 5b audit](validation/records/p2/adhd-study-5b-audit.json);
the [execution receipt](validation/records/p2/adhd-study-5b-rerun.json) records
its wall time and worker count. The partial `5b-01` run is void and excluded.

### Frozen analysis and descriptions

On the same Linux box (Python 3.12.14), the unchanged analysis ran in the
recorded **04:54:15–04:54:39 UTC** window on 2026-09-24 (24 s by the recorded
timestamps; worker count was **not recorded** for this single analysis command):

```sh
.venv/bin/python scripts/adhd_study.py analyse --raw camber-runs/adhd-study/5b-02 --calibration camber-runs/adhd-study/5a-01 --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/5b-02-results.json
```

Its [committed result record](validation/records/p2/adhd-study-results.json)
has expected SHA-256 `47c6fc6e9ef83b13bdacc3af1b89b96f6b3b8d6f25c0bd1dd577d42326c0657e`.
This is a hash of the committed result record, **not a promised byte hash of
the rerun's `camber-runs/` output**. The [analysis execution receipt](validation/records/p2/adhd-study-analysis-execution.json)
records the command, source, plan/pair bindings and output hashes. The two
separate recorded commands for descriptive figures and secondary readouts are:

```sh
.venv/bin/python scripts/adhd_describe.py 5a --raw camber-runs/adhd-study/5a-01 --plan validation/records/p2/adhd-study-calibration-plan.json --pair validation/records/p2/adhd-study-pair.json --out camber-runs/adhd-study/5b-02-figures --record camber-runs/adhd-study/5a-01-descriptive.json
.venv/bin/python scripts/adhd_describe.py 5b --raw camber-runs/adhd-study/5b-02 --calibration camber-runs/adhd-study/5a-01 --pair validation/records/p2/adhd-study-pair.json --result camber-runs/adhd-study/5b-02-results.json --out camber-runs/adhd-study/5b-02-figures --record camber-runs/adhd-study/5b-02-descriptive.json
```

Their committed records' SHA-256 values are `31304c6ccc33ae5b478db1c8a177e9ee4b9256c2a98472ec288dfefb96e1921a`
(5a), `742b51c2e4ec1d3c49507af0bec92cc8500fb4045bce60cc6c5dac1b4175d67b`
(5b) and `669c6acb6cba2d88e9b32bbf3baf53fd09cb2955e14427a74c7288fa4e9fdc9b`
(secondaries). Individual descriptive-command wall times and worker counts were
**not recorded**; do not infer them from the analysis window.

### Recorded 3D experiment playback

On the **ARM Mac**, using Chrome, `uv`, the existing MaleCNS visual cache and
the retained `5b-02` raw files, the [figure recipe and selection rule](docs/3d-model.md#recorded-experiment-playback-5b-02)
records these commands (the renderer runs no neural simulation):

```sh
RAW=<local-project-root>/.worktrees/t-0077/camber-runs/adhd-study/5b-02
uv run --locked scripts/render_malecns_3d.py \
  --primary-5b --study "$RAW" \
  --plan validation/records/p2/adhd-study-plan.json \
  --pair validation/records/p2/adhd-study-pair.json \
  --activity-cache /path/to/main-checkout/.cache/malecns-v1.0/activity/5b-02/primary-seed-210 \
  --out figures/3d/experiment-5b
uv run --locked scripts/render_adhd_5b_demo.py \
  --out figures/3d/experiment-5b \
  --values /path/to/main-checkout/.cache/malecns-v1.0/activity/5b-02/primary-seed-210/values.json
```

The first renders the [offline viewer](figures/3d/experiment-5b/male-cns-atlas.html),
[cinematic page](figures/3d/experiment-5b/cinematic/male-cns-cinematic.html) and
individual stills. The second renders the
[four-panel PNG](figures/3d/experiment-5b/primary-four-panel.png),
[83-second film](figures/3d/experiment-5b/cinematic/primary-demo.mp4),
[looping teaser](figures/3d/experiment-5b/cinematic/primary-teaser.webp) and
[poster](figures/3d/experiment-5b/cinematic/primary-poster.png).
`/path/to/main-checkout/` is a **replaceable cache location**, not a recorded
execution path. The [playback receipt](figures/3d/experiment-5b/build.json)
gives the output hashes: film `bd86690d526193a16ac28c6f10844e60e07c30786d51369429a2ea6561a68a73`,
teaser `76609b83469bf77172fc387d8c8d4c77b4e70824110d687360ee41d9635549dc`,
poster `7ee6a67902fe779d92200080a68123de90e647bb03a39aebdb0dab59951cdc2d`,
and four-panel PNG `4f43fa1dd14d390f37bc1b27098932cb0177ab3c01c580a38759357ba092836e`.
The 83 seconds are playback time, not neural run time. Raster and video bytes may
vary by browser, OS or GPU; see [figure methods](docs/3d-model.md#cinematic-film).

The follow-up was planned and frozen in advance in the then-private repository.
Its result remains **under review**; a reviewed record and reproduction command
will be linked after integration. It has one primary comparison and no
multiplicity adjustment.

## Checks and historical evidence

The project's full numerical gate is `uv run --frozen pytest` after provisioning
both datasets; it is **not a quick installation check**. The recorded male
substrate gate took 4,663.36 s on ARM Linux (927 passed, 30 skipped), with a
5,400 s timeout and one process. See
[`malecns-substrate-gate.json`](validation/records/p2/malecns-substrate-gate.json).
Documentation and figure edits should be checked by inspection or a relevant build, not by running a test suite.

Historical FlyWire result recipes, missing ignored evidence and older compute
runbooks remain linked in [the documentation map](docs/index.md). This guide
does not claim that every historical/development receipt has a public raw
archive or a one-command report generator.
