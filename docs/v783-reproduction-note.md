# Reproducing the Shiu FlyWire v783 model through flyonenomics

Rolf Yildirim (Lasell University)

Technical note. 8 October 2026.

## Abstract

The existing flyonenomics Brian2 wrapper was compared with the pinned Shiu model using FlyWire v783 and two sugar gustatory receptor neuron stimuli, each with 30 paired one-second trials. All 14,178,689 spike events matched at the 0.1 ms grid; all 8,318,340 neuron/trial trains matched, including silent cells. Mean-rate correlations were one and paired MN9 differences zero. This reproduces two software experiments, not the entire paper or biological function. Separate upstream checks confirm that changing one il3LN6 output sign strongly changes right-LB3 recruitment, whereas adding an incoming cut to outgoing-only silencing leaves every other cell's spikes unchanged.

## What was rebuilt

The rebuild is an existing path. `FlyWireAdapter("783")` in `src/flyonenomics/datasets.py` selects `Completeness_783.csv` and `Connectivity_783.parquet`; `connectome_arrays.py` preserves their order in memory-mapped arrays. `BrianEngine` constructs the recurrent network and reads `data/params-v0.1.yaml`. Its `UpstreamBank` mode imports the external checkout's `default_params` and calls `poi`. This is a wrapper reproduction with shared input code, not a fully independent simulator [1, 2]. No upstream source is vendored.

The tested configuration is bare `lif`, linear integration, uniform threshold and unit gain. Background input, dopamine modulation and transport, adaptation, depression, conductance inhibition and behavioural coupling are absent. Dopamine-labelled neurons remain in the recurrent network with the supplied fixed signs. Neither the CUDA engine nor the extended input mode is tested. Rest/reset potential is -52 mV, threshold -45 mV, membrane time constant 20 ms, synaptic decay 5 ms, refractory period 2.2 ms, delay 1.8 ms and weight per anatomical synapse 0.275 mV. The upstream input adds 68.75 mV directly to voltage and sets stimulated neurons' refractory period to zero. Both implementations use dt = 0.1 ms.

## Versions and inputs

Upstream is `philshiu/Drosophila_brain_model`, commit `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960`. The tests ran from flyonenomics development commit `8456a69ecddbee114606a89f1536f634e186467f`. Every file under `src/` and `data/params-v0.1.yaml` in that commit is byte-identical to public commit `8f3c223832d53fac11dcd8cf0b0e278216b68ede` of `uguryildirim24/flyonenomics`, except `src/flyonenomics/diagnostics/visual_path.py`, whose only change is a redacted local cache path; the comparison never imports it. The comparison does not modify either numerical implementation. The upstream tracked checkout was clean. Its v783 tables contain 138,639 neurons and 15,091,983 directed connection rows representing 54,492,922 anatomical synapses.

The following SHA-256 digests identify the actual inputs, rather than Git LFS pointer files:

```text
model.py                 fc45837d7122c6ce2a7f3f2f23c515992e4b232aadb919efabb72337fac88e4e
Completeness_783.csv      bbb847a4cc2caaa7a16349722d220c087317b946d148d4d592d94d250617a311
Connectivity_783.parquet  efeb23fb99098e9c390f6869969b2a121a2ee92c833cfc45ecb2c1d8e1af0347
annotations-v1.1.0.tsv    55c99c61eecf8db6cc36f1a684b35e4c4208afbab02197d753ccc8dc2a6e2e76
annotations-v2.1.0.tsv    30be6c73975a70c56d930e27911f36455d3886e15abf383b78edd2a5d679e0b6
params-v0.1.yaml          884156a4642f66f6ae038ae627ee27a4f60e8c6f3772e3cb7f1f0730dd644fce
```

`v783_agreement_results.json` in `scripts/shiu_issues/` records individual core-source and script hashes, selected package versions, trial seeds, event hashes and exact comparisons. It is not a complete dependency lock; the commands below do not pin every transitive dependency. Both implementations ran on Linux aarch64 on `oci-pi`, with Python 3.12.14, Brian2 2.10.1, NumPy 2.5.3, pandas 3.0.5, SciPy 1.16.2, Cython 3.1.3, PyArrow 25.0.1 and SymPy 1.14.0, using runtime Cython and GCC 13.3.0. The earlier issue checks used Python 3.10.21, Brian2 2.5.1, NumPy 1.24.4, pandas 1.5.3, SciPy 1.10.1 and Cython 0.29.36. They are retained separately in `results.json`; the two environments are not silently pooled.

## Experiment and agreement

The first stimulus is the notebook's 21 `neu_sugar` roots in its original order. Although named `sugarR`, all 21 are annotated left in v1.1.0; their v2.1.0 roots, after the remap below, are all left LB3 [3]. The v1.1.0 rows have no `cell_type` or `hemibrain_type` labels. One notebook root, `720575940620900446`, is absent from v783 and was mapped to `720575940639259967` through shared supervoxel `78678166201187069`. The second stimulus is all 64 v2.1.0 right LB3 roots, sorted by root ID, as in the earlier issue check. It is not a matched left/right experiment. MN9 is root `720575940660219265`.

Both stimuli use the code default 150 Hz, not the notebook prose's 200 Hz. Seeds 783000 through 783029 are applied after initial-state restoration; upstream specifies no seeds. Separate processes use identical environments, stimulus order and seeds. The reference calls upstream `create_model` and `poi`, restoring a compiled zero-time snapshot between trials. A fresh `run_trial` subprocess checks the first seed. The rebuild uses its public methods and one supported 1,000 ms `run_chunk` call per trial, avoiding repeated Brian2 preparation overhead. Two notebook seeds were also checked with the usual 10 ms chunks, separately and without pooling.

| Stimulus | Matched events over 30 trials | Identical neuron/trial trains | MN9 Hz in both implementations, 95% CI |
| --- | ---: | ---: | --- |
| Notebook, 21 GRNs | 408,193 | 4,159,170 of 4,159,170 | 83.47 [81.88, 85.06] |
| Right LB3, 64 GRNs | 13,770,496 | 4,159,170 of 4,159,170 | 20.10 [18.95, 21.25] |

There were zero missing or extra events in every trial. All 138,639 mean rates and all neuron/trial counts were equal for each stimulus. Correlations were 1.0 both across all neurons and across the union of active neurons, comprising 431 notebook cells and 9,158 right-LB3 cells. The paired MN9 difference was 0 Hz [0, 0] for both stimuli.

Exact comparison sorts `(neuron index, integer clock tick)` events without tolerance. Pearson correlations use 30-trial mean-rate vectors. MN9 intervals are two-sided Student-t 95% intervals across seeds, paired for differences; they describe simulator noise, not biological replicates. All 8,318,340 counts also matched the earlier Brian2 2.5.1 baseline; each stimulus's first-seed event hash matched across versions. The two 10 ms notebook checks matched all 27,508 events. Runs used nice +10, single-threaded numerical libraries and at most two simulation processes. Final comparisons, including fresh-reference checks, took 13.11 minutes elapsed: notebook 468.25 s and right LB3 786.51 s. This is resource accounting, not a speed benchmark.

## Implementation differences

The rebuild replaces upstream's scalar threshold with `v_th_i`, multiplies recurrent input by `gain_i_post` and declares an additional background-weight variable. These have neutral values in this test: -45 mV, one and zero. It uses unique object names, int32 connection indices and cached float64 arrays rather than loading pandas tables directly. Neuron/edge order, initial voltage and synaptic state, reset, refractory rule, integration method, delays and input ordering are otherwise preserved. Annotation transmitter labels do not recompute the supplied signs.

Weight arithmetic is not bit-identical: upstream multiplies the signed count directly by the weight in volts; the rebuild first caches that product in millivolts and then converts to volts. The independent `v783_weight_audit.py` finds 3,139,057 differing float64 weight rows, no sign changes, a maximum absolute difference of 1.1102230246251565e-16 V and maximum relative difference of 2.194116649456831e-16. These weight differences did not change any observed spike event in the tested conditions.

The rebuild uses disk-backed snapshots, excludes immutable connection indices from their payload and stores weights in a sidecar array. Its snapshot implementation uses private Brian2 state APIs. It restores RNG state and then reseeds; the upstream comparison restores without RNG state and then reseeds. The rebuild returns full count vectors, chunk histograms and integer ticks; upstream's helper returns only active cells. Comparisons include silent cells explicitly. The wrapper's missing-joblib placeholder was not used: joblib 1.4.2 was installed. Other model variants are outside scope.

## Issue #11: il3LN6 sign and recruitment

The issue's sign concern is confirmed [4]. Left il3LN6, root `720575940632403986`, has 1,805 outgoing rows and 12,671 anatomical synapses, all excitatory in the supplied file. In v2.1.0 its predicted transmitter is GABA with confidence 0.33984; `known_nt` is GABA, with the annotation citing Tanaka et al. (2012). The right homolog is also signed excitatory and has `known_nt` GABA, but is predicted acetylcholine. These checks change only the left cell and do not resolve the right homolog's literature/sign disagreement.

In the earlier 30 paired upstream trials, flipping that cell's outgoing weights negative changes right-LB3 MN9 from 20.10 Hz [18.95, 21.25] to 61.00 Hz [59.62, 62.38]. The paired change is +40.90 Hz [39.23, 42.57]. Mean active neurons per trial fall from 8,687.2 to 433.1; 8,544 neurons change mean rate by at least 1 Hz. That threshold is descriptive, not a multiplicity-corrected significance test. The notebook stimulus stays at 83.47 Hz [81.88, 85.06], with no mean-rate changes, because this il3LN6 never spikes. The v2 audit finds 1,349 GABA-predicted neurons with excitatory output, including this cell; ten disagreements remain at confidence >= 0.9. These disagreements do not justify blanket sign correction. Other experiments in the issue were not retested.

## Issue #10: outgoing-only silencing

At the pinned revision, `model.py:124-125` cuts outgoing weights only. `Readme.md:28` instead says, "This sets all synaptic connections to and from those neurons to zero" [5]. Under right-LB3 stimulation, silencing left il3LN6 outgoing-only versus cutting both directions produces zero differences in 4,159,140 non-silenced neuron/trial spike trains: 138,638 cells across 30 seeds. MN9 is 59.83 Hz [58.36, 61.30] in both conditions. Cutting incoming weights additionally zeroes weights on 1,983 connection rows representing 17,347 synapses and changes the silenced cell itself from 21.70 Hz to zero. The rows remain present. The incoming cut therefore is not a no-op.

Equivalence follows from the fixed zero outgoing weights: the disconnected cell cannot affect others through those edges. This does not generalize to biological silencing or plastic weights; a directly stimulated cell may still spike despite an incoming cut. Preserve the published implementation and change the README to: "This sets all outgoing synaptic weights from those neurons to zero; the neurons can still receive input and spike." The wrapper's `disconnect` method has that outgoing-only meaning.

## Limitations and reproduction

Only two stimuli, one duration and these seeds were tested. The paper used FlyWire v630, whereas these tests use the upstream v783 tables. GPU agreement, speed superiority, perturbation validity, male/female comparability and physiological accuracy are not established. Brian2 and upstream's Poisson input are shared. Cross-version timing was checked only for each stimulus's first seed; other cross-version checks use counts. Portability to other architectures or Brian2 versions is untested. Issue results use the earlier environment, not new wrapper perturbation runs. AI assisted scripting, analysis and drafting; executed artifacts are evidence, not independent peer review. Text is CC BY 4.0; flyonenomics code remains MIT. Upstream code and connectome tables are not redistributed.

Run from the checkout containing this note. Supply clean pinned upstream code, real v783 files and both annotations. Obtain data separately on a fresh machine; never change the shared upstream checkout. Bash commands:

```bash
ROOT=$PWD
WORK=$HOME/v783-note-rerun  # choose a fresh run directory
SHIU=/data/flyonenomics/cache/Drosophila_brain_model
CACHE=/data/flyonenomics/cache
mkdir -p "$WORK"
git worktree add --detach "$WORK/flyonenomics" \
  8f3c223832d53fac11dcd8cf0b0e278216b68ede
uv venv --python 3.12.14 "$WORK/.venv"
uv pip install --python "$WORK/.venv/bin/python" \
  brian2==2.10.1 numpy==2.5.3 pandas==3.0.5 scipy==1.16.2 \
  cython==3.1.3 pyarrow==25.0.1 pydantic==2.12.4 pyyaml==6.0.3 \
  joblib==1.4.2 sympy==1.14.0 setuptools==80.9.0
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
SCRIPT=$ROOT/scripts/shiu_issues
COMMON=(--fly-repo "$WORK/flyonenomics" --shiu-repo "$SHIU" \
  --annotations-v1 "$CACHE/annotations-v1.1.0.tsv" \
  --annotations-v2 "$CACHE/annotations-v2.1.0.tsv" --verify-reference)
for SIDE in notebook right; do
  nice -n 10 "$WORK/.venv/bin/python" "$SCRIPT/v783_agreement.py" \
    "${COMMON[@]}" --stimulus-side "$SIDE" \
    --work-dir "$WORK/$SIDE" --output "$WORK/$SIDE.json"
done
nice -n 10 "$WORK/.venv/bin/python" "$SCRIPT/v783_weight_audit.py" \
  --fly-repo "$WORK/flyonenomics" --shiu-repo "$SHIU" \
  --cache-dir "$WORK/notebook/fly-cache" --output "$WORK/weight-audit.json"
"$WORK/.venv/bin/python" "$SCRIPT/test_v783_agreement.py"
```

The scripts save per-trial exact-event archives and all-neuron counts outside upstream. `v783-agreement-counts.npz` accompanies the recorded comparison JSON. Regenerate the earlier issue checks with the Python 3.10/Brian2 2.5.1 commands in `scripts/shiu_issues/README.md`. To compare their counts with the newer reference, add `--historical-counts` pointing to the corresponding `issue11_trial_counts.npz` and `--historical-results "$SCRIPT/results.json"`.

## References

1. Shiu, P. K. et al. (2024). A Drosophila computational brain model reveals sensorimotor processing. *Nature* 634, 210 to 219. DOI: 10.1038/s41586-024-07763-9.
2. Shiu, P. and Spiller, N. `philshiu/Drosophila_brain_model`, pinned code revision above. Repository: `https://github.com/philshiu/Drosophila_brain_model`.
3. Schlegel, P. et al. (2024). Whole-brain annotation and multi-connectome cell typing of Drosophila. *Nature* 634, 139 to 152. DOI: 10.1038/s41586-024-07686-5. This note identifies the consumed annotation releases by file hash.
4. Santos, Allan Matheus Silva. Issue #11, opened 28 September 2026. `https://github.com/philshiu/Drosophila_brain_model/issues/11`.
5. Kisame76. Issue #10, opened 15 September 2026. `https://github.com/philshiu/Drosophila_brain_model/issues/10`.
6. Related flyonenomics Zenodo deposits: DOI 10.5281/zenodo.23091460 and DOI 10.5281/zenodo.23070186. They are related records, not identifiers for this note.
