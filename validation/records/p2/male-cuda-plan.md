# Fused GPU comparison plan (before outcomes)

- Brian2 and its parameters remain the reference. No fit to GPU outcomes.
- CUDA C++ through CuPy NVRTC: a cooperative persistent grid, two device barriers
  per tick, one launch per chunk. This supports globally ordered threshold and
  CSR event propagation without Python launches or synchronisation each tick.
  State, weights and arrivals are float64; no fast math. Connectivity is shared
  over batch members. Custom Philox input streams differ from Brian2 streams.
- Retain dt 0.1 ms, exact linear LIF update, conditional-write refractory g,
  strict threshold, 18-tick delay, reset after arrivals, and the reference
  binomial background / Bernoulli extended-group distributions. No approximation
  of those distributions by a Poisson count.
- Item 155: seeds 1–10, 2 s settle + 10 s measure, 1.0 mV sensory background,
  dopamine clamped at DA_ref, compare all recorded rest groups with
  `malecns-rest.json` R-screen rows. The historical 1.2/1.4 mV and 30 s runs are
  not rerun: this is a port of the adopted 1.0 mV rest state.
- Items 158–159: seeds 501–510, all 14 conditions, unchanged 2+5+5 s windows,
  dopamine free (A/C off for off-dopamine), input rates 10/30/60 Hz. Feed GPU
  count archives through the existing `scripts/circuit_tour_analysis.py`.
  Reference raw files are read from t-0114 by absolute path, not modified.
- Compare distributions and paired whole-seed effects, not spike trains.
  Report measured numbers without a pass line. Investigate discrepancies in
  scheduling, distributions, numerical precision and sampling before completion.
- Small 0.1 s batch-1 L4 pilot first; then short batch 1/8/32 speed runs and
  (if useful) one A100/A10G run. Separate build, stepping, CPU modulation and
  result collection times. Include end-to-end speed, not just kernel throughput.
- Every submit prints projected spend and reserves its timeout; cap $15. Keep
  app ids, measured duration-based estimates and Modal's actual app charges.
- Implementation amendment, before full outcomes: the one-second L4 pilot
  spent 0.520 of 1.318 stepping seconds in CPU dopamine composition. Port the
  existing pool Euler step and receptor composition literally to float64 CUDA,
  retaining the 10 ms cadence even with 1 ms engine chunks. Compare those GPU
  arrays with CPU Neuromod fed identical pilot counts and record maximum
  absolute differences. This changes execution placement, not equations,
  parameters, analysis, seeds or outcome windows.
- These are model firing rates, not behaviour. The fly does not see. The existing
  visual input is injected at TuBu; this tour instead injects the named courtship
  populations, with no visual stimulus.
