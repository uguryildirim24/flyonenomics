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

- [Frozen preparation and audit history](adhd-study-part-a.md), [scientific specification](SPEC-P2.md) and [machine-readable records](../validation/records/p2/). Run labels and source hashes identify recorded executions. The specifications record historical designs and execution rules. Earlier FlyWire entries are historical female-model evidence, not male results. Their ring-stage runners remain, but some required inputs and raw archives are absent.
- [Tour figures](tour-figures.md), [courtship body playback](courtship-body.md) and [GABA dose body playback](gaba-dose-body.md): model output and its limits.

- [CUDA backend](cuda-backend.md): fused MaleCNS GPU engine, Brian2 comparisons, measured speed and public replay limits. Modal launchers are not included.
- [CUDA methods](cuda-methods.md): engine description, identical-input validation, precision choices and interface limits.

The original private run archives, coordination history, provider receipt trees
and historical research drafts are not part of the public snapshot. Scientific
compute-cost records remain. Published numerical records retain provenance and
input hashes; the original raw archives have not yet been publicly deposited.
Phase 1 steering calibration, behaviour/dose validators and the invariance
runner remain. Their private inputs are not replaced with public configuration
values. Phase 2 arena code retains the original rest-record requirements. Original
private-suite gate counts do not describe the public test set.
Historical substrate regeneration rejects two changed inputs. See
[the pin erratum](errata.md#historical-substrate-input-pins) and
[the public run boundary](../REPRODUCE.md#public-snapshot-boundary).
The source hashes and numbers in frozen scientific records were not relabelled
for this public cleanup.
