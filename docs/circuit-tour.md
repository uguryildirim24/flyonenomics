# Chemical knockout tour and courtship circuit

This model represents retained cells from the male brain and nerve cord. It
receives injected Poisson input. It does not see or sing. Song-neuron
recordings measure model spikes, not sound or movement.

The designs and expectations were frozen before outcomes in SPEC-P2 section 10
items 158 and 159. Ten fresh paired seeds, 501 to 510, use the declared male
starting configuration. A shared control is compared with eight transmitter
blocks and five injected-circuit conditions. Each seed and condition runs
independently. Settle lasts 2 seconds; recording lasts 10 seconds. Courtship
drive is on for the first five recorded seconds and off for the last five.
Control uses those same windows.

The blocks remove outgoing synapses for each consensus transmitter label.
The dopamine block also disables the slow dopamine layer. The histamine block
includes T1 cells. Rest drive reaches R1 to R8 photoreceptors, but this is
injected background noise, not vision.

Courtship conditions inject P1 at 10, 30 and 60 Hz, pIP10 at 30 Hz, or a fixed
random central-brain control at 30 Hz. The random control was chosen before
outcomes from 18,093 eligible cholinergic cells without a direct link to pIP10.
Only its 148 selected roots are used.

## Public CPU command

First install the environment, required Shiu code and MaleCNS cache using
[REPRODUCE.md](../REPRODUCE.md). Choose a new output path:

```sh
uv run --frozen python scripts/circuit_tour.py worker \
  --condition off-gaba --seed 501 \
  --dest camber-runs/circuit-tour/reproduction/seed-501-off-gaba.npz
```

`camber-runs/` is ignored. This runs one current-source condition and seed,
not an exact historical replay. The public runner also accepts `control`,
`P1-high` and the other conditions listed in REPRODUCE.md sections 9 to 11.
No cloud account is needed. The historical paid-cloud launcher is not shipped.

Each complete condition produces a JSON record and checksum-bound NPZ with
one spike count per neuron per window. `scripts/circuit_tour_analysis.py`
analyses those files. It does not run a model. Its whole-seed bootstrap
intervals describe repeated random inputs to one model. An interval containing
zero is called no detected difference, not proof of no effect.

The full-neuron rate-change array is stored beside the run records.
`paint-values.json` supplies paired seed-mean changes to the 3D renderer.
Displayed skeletons are anatomical representatives, not every model neuron.

## Evidence and replay limits

[Tour and courtship results](circuit-tour-results.md) report the measurements.
The original per-condition arrays have no public archive recorded here.
Reanalysis of those numbers requires the original raw files, not just the
committed compute-cost record.

Four visualisation-only replays used seeds 501 and 502, with control and P1
high, to save spike ticks for the circuit and wing motor populations. Every
simulated neuron's ON/OFF totals had to equal the corresponding outcome record
before a replay was written. Those replays support animations, not extra
statistical outcomes. Exact animation regeneration needs the absent raw replay
and pose arrays. The virtual body sends no feedback to the brain.
