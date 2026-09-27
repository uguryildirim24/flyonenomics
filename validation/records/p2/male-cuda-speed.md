# Measured CUDA speed

One measured run per configuration. Pilot timings start from initialized state, without a settling window. Full tour timings include the frozen settle/on/off windows. No pass criterion.

Stepping includes device work, output transfers and host result collection, but excludes build and archive writing. Function total includes both; it excludes Modal startup, queueing and downloads. Full client elapsed times are in the JSON. Diagnostic CPU comparisons are not speed benchmarks.

| GPU | Batch | Duration (s) | Chunk (ms) | Mode | Build (s) | Step (s) | Step / brain-s | Function total / brain-s |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| NVIDIA L4 | 1 | 1 | 10 | pilot | 270.17 | 0.793 | 0.7926 | 271.0098 |
| NVIDIA L4 | 8 | 1 | 10 | pilot | 104.65 | 6.506 | 0.8133 | 13.9298 |
| NVIDIA L4 | 32 | 1 | 10 | pilot | 105.70 | 24.044 | 0.7514 | 4.0917 |
| NVIDIA A100-SXM4-40GB | 1 | 1 | 10 | pilot | 108.09 | 0.994 | 0.9941 | 109.1218 |
| NVIDIA L4 | 10 | 12 | 10 | rest | 265.89 | 102.117 | 0.8510 | 3.0710 |
| NVIDIA L4 | 1 | 1 | 1 | pilot | 271.03 | 1.599 | 1.5987 | 272.6767 |
| NVIDIA L4 | 32 | 12 | 10 | tour | 280.54 | 332.965 | 0.8671 | 1.6028 |
| NVIDIA L4 | 1 | 12 | 10 | tour | 269.29 | 8.420 | 0.7017 | 23.1513 |
| NVIDIA L4 | 32 | 12 | 10 | tour | 97.41 | 321.258 | 0.8366 | 1.0948 |
| NVIDIA L4 | 32 | 12 | 10 | tour | 100.38 | 298.355 | 0.7770 | 1.0423 |
| NVIDIA L4 | 32 | 12 | 10 | tour | 274.72 | 311.244 | 0.8105 | 1.5339 |
| NVIDIA A10 | 11 | 12 | 10 | tour | 110.70 | 84.559 | 0.6406 | 1.4856 |

Modal metered cost across all submits (including failed builds/diagnostics): $1.495838.
Conservative elapsed-time budget accounting: $1.963752 of the $15 cap.
Apps awaiting billing: [].
Counted against the later $8 remaining cap: $0.364438 metered, $0.700511 conservative. Entire carry-in calls are counted.

The task brief reports about 30 wall s / simulated s for Brian2 on this Mac; not a new same-hardware benchmark.
