# Shiu issues 10 and 11: paired v783 checks

Pinned upstream commit: `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960` in
`philshiu/Drosophila_brain_model`. Both scripts import that checkout's
`model.py`; no upstream implementation is copied into flyonenomics. They
reject a different commit or tracked modifications and never write to the
checkout. Supply its real data files, not Git LFS pointer files.

## Run

On Linux with a C/C++ compiler, install the versions used here (Python, Brian2
and NumPy follow upstream `environment.yml`):

```bash
uv venv --python 3.10 .venv
uv pip install --python .venv/bin/python \
  brian2==2.5.1 numpy==1.24.4 pandas==1.5.3 scipy==1.10.1 \
  cython==0.29.36 setuptools==68.2.2 pyarrow==17.0.0 joblib==1.4.2 \
  sympy==1.14.0

# Run from this scripts directory. All outputs/caches must be outside SHIU.
SHIU=/data/flyonenomics/cache/Drosophila_brain_model
CACHE=/data/flyonenomics/cache
OUT=$HOME/shiu-issues-reproduction
mkdir -p "$OUT"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
COMMON=(--shiu-repo "$SHIU" \
  --annotations-v1 "$CACHE/annotations-v1.1.0.tsv" \
  --annotations-v2 "$CACHE/annotations-v2.1.0.tsv")

# Exact notebook GRN list, with its one changed root mapped to v783.
nice -n 10 .venv/bin/python issue11_sign.py "${COMMON[@]}" \
  --work-dir "$OUT/notebook" --output "$OUT/issue11_notebook.json" \
  --verify-reference

# Additional right-LB3 stimulus, directly testing issue 11's recruitment effect.
nice -n 10 .venv/bin/python issue11_sign.py "${COMMON[@]}" \
  --stimulus-side right --work-dir "$OUT/right" \
  --output "$OUT/issue11_right.json" --verify-reference

# Defaults to right-LB3 drive so the silenced il3LN6 still receives active input.
nice -n 10 .venv/bin/python issue10_silencing.py "${COMMON[@]}" \
  --work-dir "$OUT/silence" --output "$OUT/issue10_right.json" \
  --verify-reference
# Add --stimulus-side notebook to reproduce the extra notebook silencing check.
```

Commands use Bash arrays. If the virtualenv is elsewhere, replace
`.venv/bin/python` with its absolute path. Run sequentially, or at most a few
single-threaded processes on a shared box. Our four main experiments ran
concurrently at nice +10 on Oracle; each finished in under 15 minutes.

## What they print and save

- `issue11_sign.py`: both annotation versions' il3LN6 IDs, transmitter
  predictions/confidences, literature annotations, connection-row and actual
  synapse counts, GABA/sign disagreements by confidence cutoff, then paired
  trials and MN9 rates with 95% intervals. Only left il3LN6
  `720575940632403986` is sign-flipped; the right homolog is left unchanged.
  "Meaningful" means an absolute mean rate change of at least 1 Hz, not a
  multiple-testing significance claim. Both `cell_type` and `hemibrain_type`
  are inspected: il3LN6 is in the latter column.
- `issue10_silencing.py`: the actual silencing code and README quote with line
  numbers, outgoing/incoming synapse counts, and exact integer-clock-tick
  comparisons of **every non-silenced neuron's spike train**, including silent
  cells. The silenced cell's own changes are reported separately.
- Both save JSON, input SHA-256 hashes, package versions and the complete seed
  list. Trial-count arrays are saved as compressed NPZ in `--work-dir`.
  `--verify-reference` also checks the first trial's exact spike-event hash
  against a fresh subprocess calling upstream `run_trial`, rather than our
  snapshot loop.

Defaults are upstream's **30 trials, 1 s, 150 Hz**, with dt 0.1 ms. Upstream
pins no seeds; these checks explicitly pair seeds **783000 through 783029**.
Intervals are Student-t 95% intervals over seed trials, paired for changes.
They describe simulator noise, not biological replicates. Neuron-wise
intervals are pointwise, without multiplicity correction.

## Important stimulus/version details

The notebook calls its stimulus `sugarR`, but all 21 listed GRNs are annotated
`side=left` in both supplied annotation versions. Its old root
`720575940620900446` is absent from v783; the scripts map it to
`720575940639259967` using shared supervoxel `78678166201187069`. The extra
right stimulus is **all 64 v2.1.0 right LB3 GRNs**, not a matched left/right
comparison. Both il3LN6 roots also changed between annotation versions; the
JSON retains the old IDs and explicit shared-supervoxel mappings.

GABA-predicted/excitatory is a disagreement, not automatic permission to flip
all such cells. v1 has 49 duplicate-root annotation rows, removed before
neuron counting; v1 global counts use direct v783 root matches only. v2
matches all 138,005 presynaptic neurons with outgoing connections. Literature
`known_nt` can list multiple cotransmitters; token-inclusive counts are kept
separate from exact `gaba` labels.

## Recorded results

- Left il3LN6: **1,805 connection rows, 12,671 synapses, all excitatory**;
  v2 GABA confidence 0.33984, literature GABA. Right homolog: 1,741 rows,
  11,450 synapses, also all excitatory; predicted acetylcholine (0.31771),
  literature GABA.
- v2: **1,349 GABA-predicted cells** signed excitatory (1,348 besides il3LN6);
  10 have confidence >= 0.9. This is not a blanket correction recommendation.
- Notebook: MN9 **83.47 Hz before and after**, paired change 0 [0, 0]; zero
  neurons with a >= 1 Hz mean rate change. il3LN6 is inactive here.
- Right-LB3: MN9 **20.10 to 61.00 Hz**, paired change **+40.90 Hz**, 95% CI
  **[39.23, 42.57]**; **8,544** neurons change mean rate by >= 1 Hz. Mean
  active neurons/trial fall from 8,687.2 to 433.1.
- Silencing, right-LB3: **4,159,140 exact non-silenced neuron/trial matches**;
  MN9 59.83 Hz in both conditions. Adding the incoming cut zeros weights on
  an additional 1,983 incoming connection rows, representing 17,347 synapses,
  and changes il3LN6 itself from 21.70 to 0 Hz. Fix README wording.

`results.json` contains the four completed 30-trial checks and independent
fresh-upstream validations. Seed 783000 matched a fresh `run_trial` exactly
for notebook activation, right activation, and right outgoing-only silencing;
both first-two-trial count arrays also matched independent reruns.

## Existing flyonenomics rebuild comparison

`v783_agreement.py` compares **the existing BrianEngine**, not another copy of
upstream's implementation. It imports upstream by path and invokes
`FlyWireAdapter("783")` and the bare `UpstreamBank` path in a separate process.
The full comparison uses one supported 1,000 ms engine chunk per trial to avoid
repeated Brian2 preparation overhead. It does not test CUDA or extended inputs.
The exact source revision, environment and run commands are in
`docs/v783-reproduction-note.md` (relative to the repository root).

The comparison needs Python 3.12 and the newer pinned environment documented in
that note, **not this section's Python 3.10 issue-check environment**. It rejects
tracked upstream modifications and modified tracked rebuild core files. It
creates a private cache with an upstream symlink, leaving the shared checkout
unchanged. Per-trial events and count arrays are saved in `--work-dir`.

Additional options:

- `--verify-reference`: check seed 783000 against a fresh upstream `run_trial`.
- `--historical-counts PATH --historical-results results.json`: compare all
  trial counts and the first event hash with the earlier issue-11 baseline.
- `--chunk-ms 10 --trials 2`: repeat the extra notebook check in 10 ms chunks;
  keep it separate from the 30-trial estimates and use a new output directory.

`v783_weight_audit.py` measures float64 weight roundoff from the rebuild's
millivolt cache. `test_v783_agreement.py` has five data-free metric tests.
`v783_agreement_results.json` and `v783-agreement-counts.npz` preserve the
completed comparisons and all-neuron trial counts. Large full-trial event
archives remain under `/home/ubuntu/v783-note` on Oracle and are regenerated by
the scripts. To assemble the JSON and NPZ from completed runs, use:

```bash
nice -n 10 "$WORK/.venv/bin/python" "$SCRIPT/assemble_v783_results.py" \
  --work-dir "$WORK" --output-dir "$WORK/deliverables" \
  --historical-notebook "$HOME/shiu-issues/sign-run/issue11_trial_counts.npz" \
  --historical-right "$HOME/shiu-issues/right-run/issue11_trial_counts.npz"
```

Use the paths of regenerated issue archives on another machine. Optional
supplementary event archives go in `chunk10-notebook/events-000.npz` and
`events-001.npz` under `--work-dir`; if present, supply
`--chunk10-script-sha256` with the comparison script's hash at their execution.
The deposition metadata is a draft only; no upload was performed.
