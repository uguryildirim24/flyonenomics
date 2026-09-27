# Chemical knockout tour and courtship circuit

The model is the complete male brain and nerve cord, not a fly with eyes, wings or a microphone. It does not see or sing. Background activity and courtship input are injected Poisson events; the song-neuron recordings measure electrical spikes, not sound or movement.

The designs and their expectations are frozen in SPEC-P2 §10 items 158–159. Ten fresh paired seeds, 501–510, begin at the reviewed male rest substrate. A shared healthy control is compared with eight chemical blocks (all outgoing synapses for each consensus chemical label, plus the slow dopamine layer for dopamine), then five injected-circuit conditions (P1 at 10, 30, 60 Hz, pIP10 at 30 Hz, fixed random central-brain control at 30 Hz). Each seed and condition runs independently. Settle lasts 2 seconds; recording lasts 10 seconds. For circuit conditions the drive is on for the first five recorded seconds and off for the last five; control uses those same windows.

The histamine block includes T1 cells. The rest input reaches R1–R8 photoreceptors; this is still injected background noise, not vision. The random control is selected before results are read, from 18,093 eligible cholinergic central-brain cells without a direct link to pIP10. Only the 148 selected roots are used.

## Run

After checking the frozen commit and the Modal workspace, from a clean checkout containing the unchanged frozen design and simulation runner:

```sh
MODAL_PROFILE=flyonenomics MODAL_MAX_DOLLARS=30 .venv/bin/python scripts/modal/circuit.py run --freeze <freeze-commit-sha>
```

Never change the active Modal profile; the command rejects any profile except `flyonenomics`. It prints the projection before the submit, including the full timeout-bound cost plus previous recorded spending; if the ceiling would be crossed, it stops. It uploads the five source tables, their derived graph and the engine's `model.py` to the project volume, launches one container per seed and condition in a single fan-out, pulls the records into `camber-runs/circuit-tour/outcomes/`, and creates the paired summary. `camber-runs/circuit-tour/modal-cost.json` logs projected and estimated actual billed worker time. Check Modal's invoice for final billed charges. The 0.2-second control-only container path check uses `scripts/modal/circuit.py check`; it is not a chemical or courtship outcome.

Each complete condition has a JSON record and checksum-bound NPZ with one spike count per neuron per window. `scripts/circuit_tour_analysis.py` computes group and whole-brain rate differences, distributions, synchrony, first-spike order and whole-seed bootstrap intervals; it never runs the model. A bracket containing zero is called **no detected difference**, not proof of no effect. The summary says matching, opposite or unclear relative to the written predictions; small/local predictions have no fabricated numeric pass line. The full-neuron Δ-rate array stays alongside the records. `paint-values.json` supplies the existing 3D MaleCNS renderer with those paired seed-mean changes; the skeleton view shows anatomical representatives, not every neuron. Images omit seed and build identifiers.

After the outcome summary, four visualisation-only replays (seeds 501 and 502; healthy control and P1 high) save exact spike ticks for P1, pIP10, dPR1, vPR6, TN1a, TN1c and wing motor neurons. They reuse the frozen runner and rest state. Each replay refuses to write unless **every simulated neuron's** ON and OFF totals equal its original complete outcome record. The spike NPZ and verification JSON are stored beside their original outcome files. Run them with `MODAL_PROFILE=flyonenomics MODAL_MAX_DOLLARS=30 .venv/bin/python scripts/modal/circuit.py replay --freeze <freeze-commit-sha>`; their cost is added to the same ledger. These are animation aids, not extra outcomes.
