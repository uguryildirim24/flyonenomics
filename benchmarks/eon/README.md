# Eon benchmark: identical inputs, separate GPL checkout

**Status (October 8, 2026): CPU ground truth, a CPU-only adapter semantic check
and one CUDA replay are complete. The CUDA replay matched Eon's Brian2 CPU
reference on all 1,711 of 1,711 spikes (zero missing, zero extra) and ran at
3.30 wall seconds per simulated second on one NVIDIA L4, against 10.33 for the
CPU reference. That 3.13 ratio compares two different machines; it is not a
same-hardware speedup. One configuration only: sugar, 0.1 s, one trial, seed
501, saved inputs.** Everything authored here is covered by the repository's
MIT license. No Eon implementation is vendored. Its runner and comparison
functions are imported by path from a separate scratch checkout; generated
Brian C++ files stay in scratch, not in this repository.

Pinned upstream: `eonsystemspbc/fly-brain` commit
`a3db62f9436074e485c0278290c2164ed6150808`.

## What Eon measures, in plain words

There are six simulators: Brian2 CPU, Brian2CUDA, PyTorch, NEST GPU (custom
`user_m1` neuron), direct GeNN/PyGeNN, and Brian2GeNN. The first five are the
normal CLI suite; Brian2GeNN needs a separate environment because its Brian2
version constraint conflicts with Brian2CUDA's. Brian2 CPU is the computational
ground truth, not measured fly spike trains. It runs the Shiu LIF equations
using the v783 connectivity files. The paper's biological prediction accuracy
is a different result and is not this benchmark's agreement metric.

The default experiment stimulates **21 sugar GRNs at 200 Hz**. The alternative
P9 experiment stimulates two forward-walking neurons at 100 Hz. The normal
CLI grid is duration `[0.1, 1, 10, 100, 1000]` seconds and trial count
`[1, 4, 8, 16, 32]`. The paper grid omits 1000 seconds and repeats five rounds:
20 configurations x six backends x five rounds = 600 spike files. The separate
`no_io` dataset disables spike probing/output; do not compare its times with
recording-enabled runs as if they were the same workload.

Eon's speed is simulated seconds (`duration * trials`) divided by timed
simulation wall seconds. Setup, build, extraction, and parquet writing are
reported separately. In **the actual CPU source**, one trial uses C++ standalone
and times `device.run`; that includes executable initialization and its internal
result writes, but excludes Python spike extraction and parquet export. More
than one CPU trial instead uses joblib runtime workers; their reported
simulation interval includes worker/network setup. CUDA standalone trials are
sequential; PyTorch/direct GeNN can batch trials. Thus the grid is not a pure
kernel-timing comparison with identical timing boundaries everywhere.

`code/compare_ground_truth.py` reports:

- active-neuron intersection/union (Jaccard), precision and recall;
- Pearson correlation of firing rates **only over neurons active in both runs**;
- total spike-count ratio, and percent rate deviations on that shared set.

Rates are spike counts divided by `duration * trials`. Its printed `MATCH`
means correlation > 0.99 and Jaccard > 0.90; `CLOSE` means correlation > 0.95
and Jaccard > 0.80. Neither means identical spikes. The pairwise script also
matches spike times greedily, one-to-one, separately for each trial and neuron,
within a default **1 ms** window, reporting precision/recall/F1. Our comparison
calls these exact upstream functions by path (not copied implementations) and
adds **zero-tolerance integer-tick** matches. Exact match rate means
`2 * matching_spikes / (CPU_spikes + CUDA_spikes)`; precision, recall, extras,
and missing spikes are also retained. Empty spike sets have an undefined F1,
not a fabricated 100% score.

Primary source locations in the pinned external checkout: `README.md`,
`main.py`, `code/benchmark.py`, `code/run_brian2_cuda.py`,
`code/compare_ground_truth.py`, and `code/compare_spike_outputs.py`.

## First matched configuration

We chose the **smallest standard grid point**, not a toy subnetwork or the
smaller nondefault P9 experiment: sugar, 0.1 seconds, one trial. No settling,
background input, dopamine, silencing, or warm-up is added.

| Setting | Value |
|---|---|
| Connectome | Eon's own FlyWire v783 CSV/parquet, unchanged engine order |
| Neurons / connection rows | 138,639 / 15,091,983 (actual file counts, not README's approximate synapse count) |
| dt / duration / trials | 0.1 ms / 0.1 s / 1 |
| Rest/reset/threshold | -52 / -52 / -45 mV; strict `v > threshold` |
| Membrane / synaptic time constants | 20 / 5 ms; exact linear update |
| Refractory | 2.2 ms ordinarily; **0 ms on the 21 stimulated neurons** |
| Recurrent delay | 1.8 ms (18 ticks); arrival affects the following state update |
| Recurrent weight | file's signed `Excitatory x Connectivity` value x 0.275 mV |
| Stimulus | N=1 Brian PoissonInput, 200 Hz, into **v**, kick 68.75 mV (0.275 x 250) |
| Seed | Brian2 501, set after standalone device reinitialization |

Eon's CPU runner does not itself freeze a shared cross-backend stimulus/seed.
We add one explicit seed, otherwise leave its model alone, and observe its
actual PoissonInput increments with read-only monitors before/after the
synapses stage. We first run without those monitors, then with them; **all
1,711 spikes and the parquet bytes agree exactly**. `stimulus.npz` saves the
resulting 1000 x 21 uint8 event counts, target indices, and exact int64 FlyWire
IDs. The manifest saves seed, numerical parameters in mV/ms and original SI
values, dt, duration, connectome hashes, and input/output hashes. CUDA replays
those draws; merely giving another RNG seed 501 would NOT produce identical
inputs.

## Model differences and their resolution

The adapter is a benchmark-only subclass of Rolf's existing `CUDAEngine`.
Production `src/` and all MaleCNS code/data are untouched. It derives a kernel
variant by five fail-closed substitutions in **Rolf's MIT kernel**, not Eon's
source. It retains cooperative execution, sparse edges, delay rings, float64
state, spike recording, and the engine's chunk API.

| Difference in unadapted Rolf engine | Benchmark resolution |
|---|---|
| Typical MaleCNS/rest substrate and modulation | Load Eon's exact v783 files; no rest drive, modulation, gain changes or mechanisms |
| Extended/background events normally enter g | Reuse the explicit event buffer but apply captured kicks to **v**, at the synapses stage, after thresholding and before reset |
| One ordinary refractory period for all neurons | Per-neuron refractory tick array; 0 for stimulated targets, 22 for others |
| Ordinary spike-buffer bound assumes refractory >= 1 | Reserve up to one recorded spike per tick, including zero-refractory targets |
| Philox vs Brian random streams | Disable random drive; replay saved events with no random fallback |
| mV state and equivalent-but-different algebra | Use original SI values/products and stored exact-linear coefficients; align the update's arithmetic grouping; disable CUDA FMA |
| Chunk-local monitoring | Concatenate all ten 10 ms chunks into Eon's canonical parquet schema, without dropping boundary spikes |

Brian freezes both v and g during refractory. Its conditional writes reject
recurrent arrivals while refractory. Input on an already-firing neuron is
removed by reset; it cannot cause a second same-tick spike. The kernel keeps
those rules and resets v/g. Eon's reset contains an extra `w=0` local assignment;
it is not a neuron state or a recurrent weight update, so there is no extra
state to reset in CUDA. Threshold and synapse schedule semantics are checked
by the CPU semantic test and its small delay/reset tests.

The subclass switches its internal voltage arrays to SI units: use
`build_eon`/`run_chunk`/`spikes`, not the generic public mV parameter setters
or `set_weight_scale` after building. Only sugar, one trial, no silencing is
supported in this first harness; CPU capture also permits the standard 1 s
point for later testing.

**Settled by the October 8 GPU run:** the adapted kernel compiled, launched
cooperatively and recorded spikes through ten 10 ms chunks on one L4, and its
parallel floating-point reductions produced the same 1,711 spikes as Eon's CPU
reference for this configuration. The CPU semantic check alone could not show
that; this run does, for this one configuration. Other durations, trials,
seeds, hardware and cross-platform roundoff are untested.
Python is 3.12.3 on OCI and 3.12.1 on Modal rather than Eon's conda Python 3.10;
Brian2 2.8.0 and NumPy 1.26.4 match Eon's declared environment. These are
declared software/hardware differences, not altered biological parameters.

## Completed results

On `oci-pi`, 16 shared ARM cores / ~94 GiB RAM, October 8, 2026 UTC. Every
compute command used `nice -n 10`; compilation was capped at two jobs. The
single-trial generated CPU neuron loop is serial, not a claimed 16-core result.

| Measurement | Result |
|---|---:|
| Saved stimulus events | 427 |
| Brian2 CPU spikes / active neurons | 1,711 / 348 |
| Unobserved CPU `sim_time` | 1.0332282749 s |
| CPU wall seconds / simulated second | **10.3322827490** |
| CPU build / Eon total elapsed | 12.0590874781 / 15.3489783660 s |
| Observed CPU `sim_time` | 1.1987914830 s (capture overhead; NOT the speed baseline) |
| Two-run harness wall time | 33.1434833212 s |
| CPU-only NumPy adapter semantic check | 1,711 exact matches; F1 1.0, Jaccard 1.0, shared-neuron Pearson 1.0 |

The semantic check is **not** a GPU result or alternative ground truth. Its
only purpose is to test the planned adapted tick semantics against the actual
Eon CPU spikes. Short-run speed includes significant fixed executable overhead;
one shared-machine measurement is not a publication-quality speed estimate.

### CUDA replay on Modal, October 8, 2026

One NVIDIA L4 on Modal (CUDA runtime 12.9, driver 13.0, CuPy 13.6.0, Python
3.12.1, 2 CPU cores), run once with `gpu.py` and `compare.py`
against the saved sugar, 0.1 s, one-trial, seed 501 inputs. The CUDA run and the
CPU reference share input manifest
`fcc5f99e4f13c1a696b0ac1a94015f114052b66dc7d362f65c0ef2ccdc20f5b6`. Eon's own comparison
functions at pin `a3db62f` produced every Eon metric below.

| Measurement | Result |
|---|---:|
| CUDA spikes / CPU spikes | 1,711 / 1,711 |
| Exact one-to-one matches (trial, neuron, 0.1 ms tick) | 1,711 |
| Missing / extra spikes (symmetric difference) | 0 / 0 |
| Exact precision / recall / F1 | 1.0 / 1.0 / 1.0 |
| Active neurons CUDA / CPU / shared | 348 / 348 / 348 |
| Eon active-neuron Jaccard | 1.0 |
| Eon firing-rate Pearson (shared neurons) | 1.0 |
| Eon timing F1 at its 1 ms window; mean absolute timing difference | 1.0; 0.0 ms |
| CUDA stepping time | 0.3302071670 s for 0.1 simulated s |
| **CUDA wall seconds / simulated second** | **3.3020716700** |
| CPU wall seconds / simulated second (oci-pi, above) | 10.3322827490 |
| CPU-to-CUDA ratio | **3.13 (cross-machine)** |
| CUDA build / spike extraction / parquet save | 8.17 / 0.48 / 0.03 s (excluded from stepping time) |
| CUDA harness total | 9.02 s |

Timing boundaries differ and the ratio is a **cross-machine wall-time ratio**,
not a same-hardware speedup: the CPU interval includes executable
initialization and its internal result writes (one Arm host, shared); the CUDA
interval includes per-chunk allocations and host transfers (ten 10 ms chunks).
Build and parquet export are excluded from both. The CUDA event interval
(0.3298 s) is not kernel-only. One run, one configuration, no repeats.

Guard fix: `modal_run.py` now checks the paid-launch flag only with
`modal.is_local()`, because the container re-imported the module without the
local environment variable and failed.

Saved local bundle: `benchmarks/eon/artifacts/sugar-0.1s-n1-seed501/`.
CPU semantic outputs: `artifacts/adapter-cpu-check/` and
`artifacts/adapter-cpu-comparison.json`. Original CPU log: `artifacts/cpu.log`.
CUDA outputs (`comparison.json`, `run.json`, `spikes.parquet`):
`artifacts/cuda-seed501/`, with its own `checksums.sha256`.
`artifacts/checksums.sha256` covers the committed result bundle. Large data and
C++ generated builds remain outside this repo. The same raw files/builds remain
on OCI in `/home/ubuntu/eon-bench/artifacts/`; GPL checkout is
`/home/ubuntu/eon-bench/fly-brain`. A local external checkout is at
`$HOME/eon-bench/fly-brain`.

## Run each step

Run commands from the **eon-bench worktree**, not the main checkout. Scripts
refuse an upstream checkout inside the MIT repository or at a different commit.
Use an isolated environment: the normal flyonenomics Brian2/NumPy pins differ.

```sh
# Local CPU-only tools; no paid run.
uv venv .venvs/eon --python 3.12
uv pip install --python .venvs/eon/bin/python -r benchmarks/eon/requirements-cpu.txt
# For the exact resolved OCI packages, use the saved environment.txt instead.

# Fetch upstream OUTSIDE the repo, then detach at the pin.
git clone https://github.com/eonsystemspbc/fly-brain.git $HOME/eon-bench/fly-brain
git -C $HOME/eon-bench/fly-brain checkout --detach a3db62f9436074e485c0278290c2164ed6150808

# Verify committed results (macOS).
cd benchmarks/eon/artifacts && shasum -a 256 -c checksums.sha256 && cd ../../..
.venvs/eon/bin/python -m pytest benchmarks/eon/test_harness.py -q

# Recompute Eon's metrics on saved CPU semantic outputs, no simulation.
.venvs/eon/bin/python benchmarks/eon/compare.py \
  --eon-repo $HOME/eon-bench/fly-brain \
  --inputs benchmarks/eon/artifacts/sugar-0.1s-n1-seed501 \
  --candidate benchmarks/eon/artifacts/adapter-cpu-check \
  --out /tmp/eon-semantic-comparison.json

# Recompute Eon's metrics on the saved CUDA outputs, no simulation. Every metric
# should match artifacts/cuda-seed501/comparison.json; its top_deviations list is
# ten neurons all at 0.0% difference, so which ten it names can differ.
.venvs/eon/bin/python benchmarks/eon/compare.py \
  --eon-repo $HOME/eon-bench/fly-brain \
  --inputs benchmarks/eon/artifacts/sugar-0.1s-n1-seed501 \
  --candidate benchmarks/eon/artifacts/cuda-seed501 \
  --out /tmp/eon-cuda-comparison.json
```

On OCI, keep everything in this task's scratch directory. Copy `src/` and
`benchmarks/eon/*.py` to `/home/ubuntu/eon-bench/mit-repo/` in their same relative
locations (do not use another session's checkout). The harness root must be
`mit-repo`, not `/home/ubuntu`, so the external-checkout guard works.

```sh
ssh oci-pi
cd /home/ubuntu/eon-bench
# Upstream clone already exists here; for a new scratch installation:
# git clone https://github.com/eonsystemspbc/fly-brain.git fly-brain
# git -C fly-brain checkout --detach a3db62f9436074e485c0278290c2164ed6150808
~/.local/bin/uv venv venv --python /usr/bin/python3.12
~/.local/bin/uv pip install --python venv/bin/python \
  -r mit-repo/benchmarks/eon/requirements-cpu.txt
# Choose a NEW output path; never overwrite a measured bundle.
timeout 5400 nice -n 10 env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 \
  venv/bin/python mit-repo/benchmarks/eon/cpu.py --eon-repo fly-brain \
  --out artifacts/sugar-0.1s-n1-seed501-repeat --seed 501 --duration 0.1 --compile-jobs 2
nice -n 10 venv/bin/python mit-repo/benchmarks/eon/reference.py \
  --eon-repo fly-brain --inputs artifacts/sugar-0.1s-n1-seed501-repeat \
  --out artifacts/semantic-repeat
nice -n 10 venv/bin/python mit-repo/benchmarks/eon/compare.py \
  --eon-repo fly-brain --inputs artifacts/sugar-0.1s-n1-seed501-repeat \
  --candidate artifacts/semantic-repeat --out artifacts/semantic-repeat-comparison.json
```

`cpu.py` calls `run_single_benchmark` directly rather than reimplementing it.
This is the seeded/captured equivalent of Eon's
`python main.py --brian2-cpu --experiment sugar --t_run 0.1 --n_run 1`.

### GPU launch

On any CUDA host you control, install `cupy-cuda12x==13.6.0` alongside
the isolated requirements and run:

```sh
.venvs/eon/bin/python benchmarks/eon/gpu.py \
  --eon-repo /path/outside/mit-repo/fly-brain \
  --inputs benchmarks/eon/artifacts/sugar-0.1s-n1-seed501 \
  --out /path/outside/mit-repo/cuda-eon-seed501 --chunk-ms 10
.venvs/eon/bin/python benchmarks/eon/compare.py \
  --eon-repo /path/outside/mit-repo/fly-brain \
  --inputs benchmarks/eon/artifacts/sugar-0.1s-n1-seed501 \
  --candidate /path/outside/mit-repo/cuda-eon-seed501 \
  --out /path/outside/mit-repo/cuda-eon-comparison.json
```

The **paid Modal** command below is what produced the October 8 result. It
spends money on every run, so launch it only deliberately:

```sh
# One-time local client installation, not a GPU launch:
uv pip install --python .venvs/eon/bin/python modal
# PAID: one L4, 2 CPU cores, 16 GiB, 900 s timeout, no retries, max 1 container.
# Choose a NEW output path; the October 8 result is already in cuda-seed501.
EON_BENCH_ALLOW_PAID_GPU=YES .venvs/eon/bin/modal run benchmarks/eon/modal_run.py \
  --inputs benchmarks/eon/artifacts/sugar-0.1s-n1-seed501 \
  --out $HOME/eon-bench/cuda-seed501-repeat
```

The launcher fetches the pinned GPL repository into `/opt/eon-fly-brain`,
outside `/mit`, sends only the small saved numerical bundle, and returns
`spikes.parquet`, `run.json`, and `comparison.json`. It does not deploy, create
a persistent volume, submit multiple trials, or call any other provider. Without
`EON_BENCH_ALLOW_PAID_GPU=YES` the local launch raises before any remote call.
The check runs only when `modal.is_local()` is true, so the container's own
re-import of the module does not need the variable.

Cost estimate using Modal's public rates checked October 8, 2026:
L4 $0.000222/s + 2 CPU cores x $0.0000131/s + 16 GiB x $0.00000222/s
= **$0.00028372/s**. Allow **$0.034 to $0.085 for 2 to 5 minutes**, and about
**$0.26 for the full 900-second function timeout**, before image-build/startup,
2-second idle time, and any egress charges. This is an estimate, not a billing
cap; a function timeout does not cap all lifecycle charges. Source:
https://modal.com/pricing . The estimate was computed before the run; the
billed cost of the October 8 run is not recorded here.

The comparison reports CUDA stepping wall time and CPU/CUDA ratio, plus exact
and Eon metrics. CUDA stepping includes allocations, kernel work and host
transfers but excludes `spikes()` sorting and parquet export; CPU stepping is
Eon's executable interval. Both receipts keep their timing definitions and
machine details. The resulting ratio is **cross-hardware wall time**, not a
same-hardware or kernel-only speedup.

## Still to do

1. Done (October 8, 2026): the single Modal replay, with hashes, exact
   F1/precision/recall, Eon shared-neuron correlation and Jaccard checked
   against the saved CPU reference. No mismatch to inspect.
2. Repeat the 1 s standard grid point and gather repeated timing samples (and
   separately labeled no-recording measurements if wanted). The 0.1 s result does
   not by itself say the 1 s run agrees.
3. Run the same comparison under the CLI's own independent Philox drive through
   the planned seventh backend (`PR-backend.md`). The replay above uses saved
   Brian draws and does not measure that path.
4. Publish only after review. No push, issue, or post has been made from here.
