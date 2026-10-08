# Fused CUDA backend

This is a new GPU backend for the 162,517-neuron MaleCNS LIF model. Brian2
remains the reference. It is not a replacement for the other engine variants.
The model receives injected input; the fly does not see or sing. Visual input
elsewhere in the project is injected at TuBu; this comparison instead uses
dark rest and injected courtship-population input.

## Public run boundary

This page records the executed GPU methods and measurements. It is not a
clean-clone GPU launch guide. Paid-cloud submission and billing tools are not
included. No public raw GPU or saved-input archive is recorded. The public
`scripts/cuda_*.py` files do not provide a standalone one-condition CUDA runner.
See [REPRODUCE.md section 13](../REPRODUCE.md#13-gpu-engine-replication).

The recorded cloud image used CUDA 12.6.3 and CuPy 13.6.0. CuPy is GPU-only
and is not in the CPU dependency lock. Kernels compile through NVRTC on the
GPU machine. These are historical environment pins, not hardware provisioning
instructions.

The comparison used the original CPU tour and rest files in place. It verified
count hashes and historical rest-file hashes, then invoked
`scripts/circuit_tour_analysis.py` for both engines. The committed comparison
record retains group rates, paired effects, seed distributions and hashes.
The raw files are not included, so the comparison cannot be rerun from Git alone.

## Implementation

`src/flyonenomics/engine/cuda_engine.py` exposes a batched `CUDAEngine`;
`cuda_tick.cu` is the custom kernel. CUDA C++ was chosen because cooperative
grid barriers let one launch execute a whole chunk, with globally ordered
threshold and event-delivery stages, rather than launching Python/Torch sparse
operations each tick. Each resident block compacts its spikes into a separate
slice of the delay ring. Warps traverse only firing sources' outgoing CSR
edges. There is no per-tick host synchronization or fixed spike-count cap.
Connectivity and base weights are shared across brains.

The engine retains the reference dt, exact linear update, strict threshold,
refractory gating, reset, delay, signs and class scales. State, weights and
atomic arrivals are float64; fast math and fused multiply-add are disabled.
Background uses the reference small-mean Binomial(100, 0.001) distribution.
Extended inputs use one Bernoulli draw per target per tick, as Brian2's
PoissonGroup does—not a Poisson count with potentially several same-tick hits.
Synaptic arrivals and background are rejected while `g` is refractory,
including the firing tick, exactly as Brian2's conditional writes require.

`set_disconnections` supports a different outgoing knockout in each brain.
`set_input_rates` accepts a batch-by-target rate array; it implements the
injected drive used by `Activate`. `set_weight_scale` accepts the same
connection-file-order scale array used by the reference rest-substrate builder.
Thresholds and postsynaptic gains may also differ between brains. Two small
CUDA kernels implement the unchanged dopamine Euler step and receptor
composition at the frozen 10 ms cadence. Initial states and parameters come
from the existing `Neuromod` objects. A 0.2 s pilot, using 1 ms engine chunks,
compared GPU pools, thresholds and gains with CPU Neuromod on identical counts:
the measured maximum absolute differences were all zero. This diagnostic is
separate from the speed measurements.
Item 155 rest is clamped at DA_ref; the tour is free-running, with A/C disabled
and dopamine neurons' outgoing weights removed for the dopamine knockout.

`run_chunk(ms)` returns batched counts, 1 ms histograms and each neuron's first
spike tick; these paths were exercised in the full validation. The original comparison did not exercise full spike times; the
[identical-input replay](../validation/records/p2/male-cuda-identical-comparison.md)
now exercises that path over four complete 12-second runs. Construct with
`record_spikes=True` to retrieve every neuron/tick
pair with `spikes(since_tick, batch=...)`. Full spike lists are chunk-local:
consume them before the next call. There is no silently truncated spike buffer.
Chunk lengths must be whole milliseconds. With `CUDADopamine` attached, chunks
must divide 10 ms; input can change every millisecond without changing the
10 ms dopamine cadence. `refresh_parameters()` uploads changed genotype/drug
parameters without resetting GPU pools; `pools_host()` reads the current pools.
The host Neuromod objects do not themselves track the evolving GPU pool state.
`set_background_events(targets, counts, tick0)` replaces random background with
an explicit uint8 tick-by-target multiplicity array shared across the batch.
It retains existing target weights and refractory rejection. Every subsequent
chunk must be covered by the supplied window; there is no random fallback.
Upstream banks, general deterministic extended-stimulus lists, voltage traces,
adaptation, depression and conductance inhibition are not implemented; asking
for them raises an error.

## Identical-input follow-up

The [methods draft](cuda-methods.md) describes the engine and both comparisons.
The new replay freezes dopamine at its reference value for intact rest and GABA
outgoing disconnection. It uses the same saved Binomial(100, 0.001) input events
for both engines, including multiplicities and rejected refractory-period events.
Brian2 engine code and model data are unchanged; the harness disables stochastic
input and adds a zero-delay spike generator with multiplicity-weighted sources.
ON/OFF are two five-second observation windows, not stimulus switches.

**Result:** all 162,517 neurons' ON/OFF counts matched for both seeds in both
conditions. All 58,655,422 neuron/tick pairs matched at 0.1 ms resolution;
there was no observed spike divergence during any 12-second run. This is
spike-output equivalence for the tested trajectories, not bitwise state equality.
After the packed-output change, L4 stepping took **1.268480 s per brain-second
at 1 ms** and **0.637029 at 10 ms**, in one-second pilots. The 1 ms interface
remains slower than real time. Follow-up Modal spend was **$0.40490238**.

The recorded replay generated saved input events, ran the Brian2 reference,
ran CUDA on cloud hardware and compared the outputs. The public
`scripts/cuda_identical.py` and `scripts/cuda_identical_report.py` retain the
CPU/comparison logic; the cloud driver is not shipped. Reanalysis of the
reported result requires the missing raw inputs and output archives.

The follow-up also measured one-second ordinary-input pilots with 1 ms and
10 ms chunks. Counts, histograms and first ticks transfer together. This
reduces three synchronous host transfers to one without dropping returned
data. Each recorded replay verified its input event file hashes.

Each input file covers one second. Its sparse `flat` array encodes
`relative_tick = flat // len(targets)` and `neuron = targets[flat % len(targets)]`;
`multiplicity` records simultaneous elementary spikes. Add the file's second
number times 10,000 to obtain the absolute tick. This preserves all events
without expanding repeated same-tick spikes into separate source records.

Raw input events and Brian2 spike archives are in `camber-runs/cuda-identical/`.
CUDA archives are downloaded beneath its `downloads/` folder and linked by
`cuda/`; the receipt maps the directory to the Modal app/volume archive.
[Input hashes](../validation/records/p2/male-cuda-identical-inputs.json),
[full comparison](../validation/records/p2/male-cuda-identical-comparison.json),
[readable results](../validation/records/p2/male-cuda-identical-comparison.md) and
[cost/timing receipts](../validation/records/p2/male-cuda-identical-receipts.json)
are committed. The full-spike replay's input decoding and recording costs are
not substituted for the ordinary-input interface benchmark.

## Differences from Brian2

- In ordinary stochastic-input mode, draws use counter-based Philox keyed by seed, neuron and tick, not
  Brian2's RNG. Batch position does not choose the input stream. Paired arms
  share counter-based input draws, whereas Brian's consumed stream can diverge
  when refractory states differ. Compare distributions and paired effects,
  not spike trains or identical confidence-interval widths.
- Atomic edge sums may differ in their floating-point order. Algebraically
  equivalent exact LIF updates also round differently (mV here, volts in Brian).
- Only counts, histograms and first ticks are transferred at chunk boundaries;
  all spike times are optional. The GPU pool/compose steps need no host arrays.
  Build and recording costs are reported
  separately from stepping, not hidden in a kernel-only speed claim.

## Original random-input measurements

The identical-input and packed-interface follow-up is reported above; the
following tables retain the original measurements rather than replacing them.

### Speed

One brain stepped faster than real time with 10 ms chunks, but **not with the
measured 1 ms full-output interface**. This is not yet a real-time virtual-body
demonstration. Times below exclude build and archive writing; they include
output transfers, dopamine and host collection.

| GPU / run | Brains | Simulated seconds each | Step wall seconds | Wall / brain-second |
|---|---:|---:|---:|---:|
| L4 pilot, 10 ms chunks | 1 | 1 | 0.793 | 0.793 |
| L4 pilot, 10 ms chunks | 8 | 1 | 6.506 | 0.813 |
| L4 pilot, 10 ms chunks | 32 | 1 | 24.044 | 0.751 |
| L4 pilot, **1 ms chunks** | 1 | 1 | 1.599 | 1.599 |
| A100 pilot, 10 ms chunks | 1 | 1 | 0.994 | 0.994 |
| L4 complete control | 1 | 12 | 8.420 | 0.702 |
| L4 complete tour batch | 32 | 12 | 321.258 | 0.837 |
| A10G final tour subset | 11 | 12 | 84.559 | 0.641 |

The A10G subset is a different workload, not a controlled speed comparison.
It replaced an L4 call cancelled before a worker started. Builds took roughly
97–281 seconds; Modal startup/queueing and downloads are additional. The speed
record includes function totals and full client elapsed times. For context only,
the identical-input harness on an arm64 Mac (Brian2 Cython, one process,
one-second run calls, random input disabled, dopamine clamped) measured
3.1–4.0 wall seconds per simulated second intact and 7.0 with GABAergic outputs
removed. These timings include first-run compilation and spike extraction;
see the [replay timing record](../validation/records/p2/male-cuda-identical-comparison.md#replay-timing).
They are not a like-for-like benchmark of the ordinary-input engines, and no
speedup ratio is claimed. Batch numbers describe aggregate throughput,
not per-brain real-time execution.

### Agreement and differences

All ten rest seeds and 140 tour outcomes were measured. Central/DAN/KC rest
means closely track the reference. Acetylcholine removal suppresses activity;
GABA and glutamate removal increase it strongly. The dPR1 P1-medium-minus-random
contrast is 17.81 Hz in Brian2 and 17.85 Hz in CUDA; high-minus-low is 15.19 and
15.39 Hz.

Not every small effect or interval is reproduced. Rest ER is 0.474 versus
0.533 Hz, and motor is 6.646 versus 6.282 Hz. The motor difference largely
reflects one high-rate Brian2 realization. Different dPR1 control means
(22.38 versus 25.77 Hz) explain most of the courtship-versus-control difference,
while stimulated absolute rates are much closer. Random-drive, octopamine and
serotonin detections change. First-spike latency distributions also differ,
including in controls; these are not causal response latencies. This earlier study did not isolate counter-based pairing from floating-point
trajectory sensitivity. The later clamped, identical-input replay found no
spike-output difference, but does not make all these free-dopamine effects
interchangeable. Do not infer equivalence from overlapping intervals.

See the measured [comparison](../validation/records/p2/male-cuda-comparison.md),
[difference investigation](../validation/records/p2/male-cuda-differences.md),
[speed record](../validation/records/p2/male-cuda-speed.md), and
[diagnostics](../validation/records/p2/male-cuda-checks.json).
The JSON comparison retains every group and seed, intervals, latencies and hashes.

### Cost

All submissions together cost **$1.495838 metered**, including failed build and
diagnostic attempts. Counting entire final in-flight calls and the replacement
against the later $8 allowance gives **$0.364438**. Conservative duration-based
accounting is $1.963752 total and $0.700511 against the remaining allowance.
Every submit, projection, cancellation and per-app charge is retained in
`validation/records/p2/male-cuda-receipts.json`. No apps await billing.
