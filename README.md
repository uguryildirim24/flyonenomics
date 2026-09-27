# flyonenomics

**How does changing dopamine alter activity in a model of a male fly brain?**
This undergraduate, AI-assisted project builds a whole-brain spiking model with
a dopamine layer from the published MaleCNS male fly wiring map. It tests a
prospectively specified neural-history readout after modelled dopamine-transporter
loss and reduced release. Input is injected at **TuBu (tubercle-to-bulb)
neurons**: **the fly does not see**. This is not ADHD in a fly, a behavioural
assay, or a treatment model.

[![Recorded model spiking in one simulated fly](figures/3d/experiment-5b/cinematic/primary-teaser.webp)](figures/3d/experiment-5b/cinematic/primary-demo.mp4)

*Short loop from an illustrative simulation, not the statistical test. Glow tracks
recorded model spiking; flash timing within each bin is illustrative. Input is
injected at TuBu; the fly does not see. [Film (83 s)](figures/3d/experiment-5b/cinematic/primary-demo.mp4)
· [poster](figures/3d/experiment-5b/cinematic/primary-poster.png)
· [figure methods](docs/3d-model.md).*

[MaleCNS anatomy atlas](figures/3d/male-cns-atlas.png):

*Real MaleCNS anatomy, simplified and recoloured—not simulated activity.*
Open [`figures/3d/male-cns-atlas.html`](figures/3d/male-cns-atlas.html) locally
in a browser to rotate it. Its default playback is explicitly **synthetic dummy
data**. [Figure methods and attribution →](docs/3d-model.md)

The first ten-seed study is complete: the vehicle genotype contrast was nominal
only (Holm p = 0.0703125), and the release interaction had **no detected
difference**. [Results](docs/adhd-study-results.md) · [reproduction records](paper/README.md).
The follow-up was planned and frozen in advance; its result is under review.
[Reproduce the results](REPRODUCE.md) · [Cite the paper and MaleCNS source](paper/)
· [MIT code licence](LICENSE) (source data: CC BY 4.0) ·
[Feedback welcome via issues](https://github.com/uguryildirim24/flyonenomics/issues).
The repository name in that link must be set before publishing.

## The model and the evidence

The current dataset is **MaleCNS v1.0**, from **Janelia Research Campus, Google
Research and the University of Cambridge**, released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The model retains **162,517 typed, traced neurons and 25,120,209 directed
connections** from the male central nervous system, including the nerve cord;
it is not every cell in the release. Neurons are simplified leaky
integrate-and-fire units, with declared dopamine/receptor assumptions.
[Build rules and limitations →](docs/malecns-port.md)
[Provenance erratum for frozen parameters and engine notes →](docs/errata.md)

The project began with [Shiu et al.'s 2024 model](https://github.com/philshiu/Drosophila_brain_model)
of the **female FlyWire connectome** (v630/v783). Those experiments remain as
history, not evidence about the male model.

Available now:
- [Male resting-state measurements](docs/malecns-rest.md): ten seeds, a fixed
  configuration, and per-seed results—not biological pass/fail thresholds.
- [Literature and implementation audit](docs/adhd-model-research.md): what
  dopamine-transporter loss (*fumin*) and reduced release can honestly test.
- [Reproduction commands, hashes and costs](REPRODUCE.md).

## Results

The [reviewed first study](docs/adhd-study-results.md) found a nominal
*fumin*-minus-wild-type history contrast that **did not survive the
frozen two-test correction** (Holm p = 0.0703125). The release-reduction
interaction had an interval including zero: **no detected difference and no
detected rescue**. [Numerical record and intervals](validation/records/p2/adhd-study-results.json).
These are stochastic seeds in one fixed model, not independent animals; at most
this is a candidate neural signature, not ADHD, attention or behaviour.
The follow-up design and analysis were **planned and frozen in advance** in
the then-private repository. Its result is under review; no reviewed follow-up
claim is made here. It has one primary comparison, not the first study's
two-test correction. The reviewed result and its record will be linked here
when available.

![Four panels of recorded model activity in one illustrative seed](figures/3d/experiment-5b/primary-four-panel.png)

*Model activity in one illustrative seed, not the statistical test. Input is
injected at TuBu; the fly does not see. [Recorded film](figures/3d/experiment-5b/cinematic/primary-demo.mp4)
· [offline cinematic viewer](figures/3d/experiment-5b/cinematic/male-cns-cinematic.html)
· [figure methods](docs/3d-model.md).*

[Paper draft and PDF build](paper/) (`uv run --locked --script paper/build.py`)
· [reproduction commands](REPRODUCE.md).

## Install and reproduce

With [uv](https://docs.astral.sh/uv/), Git, Python 3.12 and a C/C++ toolchain:

```sh
git clone https://github.com/uguryildirim24/flyonenomics.git
cd flyonenomics
uv sync --frozen
```

Viewing the committed figure needs no Python or data download. Rebuilding it
needs Chrome and about **165 MB** of source assets. Numerical work needs large
cached tables: the complete male flat-data inventory is **24.38 GB**, plus
space for derived arrays. The recorded 701-brain-second rest measurement took
**2 h 24 min** on a 16-core ARM Linux machine with about 94 GiB RAM, using eight
workers (summed worker peak memory about 58 GB). These are measurements, not a
laptop runtime promise. See [REPRODUCE.md](REPRODUCE.md) before starting a run.

## Citation, credits and licences

To cite this project: **Hasan "Rolf" Yildirim**, *flyonenomics* (2026),
[source repository](https://github.com/uguryildirim24/flyonenomics).
Cite the MaleCNS paper separately for the underlying connectome.

MaleCNS: Berg et al., *Sexual dimorphism in the complete Drosophila male central
nervous system connectome*, **Cell** (2026),
[doi:10.1016/j.cell.2026.08.015](https://doi.org/10.1016/j.cell.2026.08.015).
Source data and derived anatomy retain CC BY 4.0 attribution. The atlas embeds
Three.js's MIT notice; historical Shiu/FlyWire and other sources are catalogued
in [the data guide](docs/data.md) and [provenance](data/provenance.json).

Project code is [MIT licensed](LICENSE); third-party code and data licences
remain separate. This is an AI-assisted project; methods and scientific
provenance are linked from the [documentation map](docs/index.md).
