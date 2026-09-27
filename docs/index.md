# Documentation map

The current model uses MaleCNS v1.0. Earlier FlyWire measurements use a female connectome and are not evidence about this male model. Experimental input is injected at TuBu, downstream of the eye: **the fly does not see**.

- [Front page](../README.md), [reproduction guide](../REPRODUCE.md), [paper](../paper/) and [experiment results](adhd-study-results.md).
- [MaleCNS port](malecns-port.md): graph and sign rules, neuron populations, dopamine layer, and starting substrate.
- [Male rest](malecns-rest.md): frozen measurements across ten model seeds, not biological pass lines.
- [First-study design](adhd-study-design.md), [experiment chronology](adhd-experiment.md) and [numerical results](adhd-study-results.md).
- [Literature and implementation audit](adhd-model-research.md): limitations and corrected earlier claims.
- [3D atlas and figure methods](3d-model.md): anatomy from MaleCNS; default animated values are synthetic, not recorded brain activity.
- [Data and licences](data.md).

## Technical provenance, not visitor instructions

- [Frozen preparation and audit history](adhd-study-part-a.md), [dated scientific specification](SPEC-P2.md) and [machine-readable records](../validation/records/p2/). Their internal run labels, source hashes and historical decisions identify exactly what was executed; some earlier entries concern superseded FlyWire work and are not male results.
- [Tour figures](tour-figures.md), [courtship body playback](courtship-body.md) and [GABA dose body playback](gaba-dose-body.md): model output and its limits.

- [CUDA backend](cuda-backend.md): fused MaleCNS GPU engine, Brian2 comparisons, measured speed and run commands.
- [CUDA methods](cuda-methods.md): engine description, identical-input validation, precision choices and interface limits.

The original private run archives, coordination history, cloud receipts and historical research drafts are not part of the public snapshot. Published numerical records include their provenance and input hashes; the original raw archives have not yet been publicly deposited.
