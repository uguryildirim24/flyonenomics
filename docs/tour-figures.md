# Knockout tour and courtship figures

Blender renders and an offline 3D viewer of the recorded transmitter and
unlabelled-neuron knockout tour and courtship test ([results](circuit-tour-results.md), [design](circuit-tour.md)).
They show model activity: background and courtship input are injected, and the
fly does not see, move or sing.

## Files

All in [`figures/tour/`](../figures/tour/):

| File | What it shows |
|---|---|
| `stills/<condition>.png` | One 4K still per condition (14), the brain and nerve cord seen from above, head to the left. |
| `knockout-overview.png` | The normal brain beside seven transmitter knockouts and the unlabelled-neuron knockout, same view and scale. |
| `courtship-path.png` | P1, pIP10, song and wing motor neurons, coloured by their change at high P1 drive, seen from the side. |
| `courtship-path-4k.mp4`, `-1080p60.mp4` | 8 s: the same cells lighting up spike by spike after the P1 drive switches on. |
| `normal-vs-gaba-switched-off-4k.mp4`, `-1080p60.mp4` | 10 s: the normal brain turning beside the knockout with the largest change. |
| `viewer.html` | Pick any condition and turn the brain in a browser; works offline. |

## How to read them

**A dot is a synapse site.** Every simulated neuron is drawn as up to 8 of its
own synapse sites (3 in the browser), chosen by a fixed hash of the site id, so
the choice never depends on an outcome. That is 1,298,969 dots for 162,457
neurons; the 60 neurons with no recorded synapse site are not drawn. Brain
region outlines are the MaleCNS neuropil meshes.

**Colour is the change in firing rate from the normal brain.** Values are the
recorded per-neuron change, averaged over ten seeds paired against the healthy
control. Warm (ember, orange, gold) means the neuron fires more; cold (deep to
pale blue) means it fires less; dim slate means little or no change. One scale
serves every still, the grid, the clips and the viewer: a signed logarithm,
nearly linear below a 4 Hz knee, that saturates at ±200 Hz. The 200 Hz cap is
the 1-2-5 rounding up of the 99.5th percentile of non-zero changes across all
conditions; the knee is cap/50. Brighter and larger dots mean larger
changes.

Per-neuron means carry seed noise, so a condition with no detected difference
at group level (histamine, dopamine) still shows faint scattered dots of both
colours. Group numbers and intervals are in the [results](circuit-tour-results.md).

**The side-by-side** picks the knockout with the largest mean absolute change
over all neurons: GABA switched off (13.2 Hz), ahead of glutamate (10.0 Hz).

**The courtship path still** draws the 261 traced cells of the path (148 P1,
2 pIP10, 45 song neurons of types dPR1, vPR6, TN1a and TN1c, 66 wing motor
neurons) as centerlines, in the same colour scale. vPR6 never spiked, so those
cells stay slate.

**The courtship clip** replays the exact spikes of one run at high P1 drive,
checked when it was recorded to match every neuron's spike totals in the
original run. Each spike lights its cell up the warm ramp, and the light fades
over 20 ms of model time, like a calcium indicator. Each frame averages over
the model time since the previous frame, so a steady rate looks equally bright
at any playback speed. The clock runs slowly at first, 10 × (e^(t/2) − 1) ms
after t seconds of clip, reaching 531 ms on the last frame; the label always
shows true model time. Wing motor neurons also fire at rest, so a few are lit
before the P1 response arrives.
The clip has no colour key because its colours show recent spikes, not rate
changes.

## Rebuild

Needs Blender 5.2 (`blender` on `PATH`, Metal GPU) and the SF Pro Display
fonts in `/Library/Fonts`. The courtship groups come from the population
table frozen with the circuit tour.

```sh
uv run --locked scripts/blender/tour.py prepare
uv run --locked scripts/blender/tour.py values \
  --outcomes camber-runs/circuit-tour/summary/per-neuron-delta-hz.npz --out values.npz
uv run --locked scripts/blender/tour.py figures --values values.npz --out figures/tour \
  --spikes camber-runs/circuit-tour/outcomes/seed-501-P1-high-spikes.npz
uv run --locked scripts/blender/tour.py viewer --values values.npz --out figures/tour/viewer.html
```

`prepare` builds the display scene once into the ignored cache. `figures`
keeps raw frames in the cache under a folder named for the value table, look
and cameras, so an interrupted run resumes. `values --synthetic` makes
striped test values for development; those renders carry a red stamp and are
refused under `figures/`. The look lives in `scripts/blender/look.json`,
shared by Blender and the viewer. Videos are H.264 at CRF 18; a 4K master over
95 MB is encoded again two steps coarser, so it stays under GitHub's file
limit (the side-by-side master is CRF 20).

MaleCNS v1.0 · Janelia Research Campus, Google Research & University of
Cambridge · Berg et al., *Cell* (2026),
<https://doi.org/10.1016/j.cell.2026.08.015> · CC BY 4.0. Geometry is
simplified and recoloured. Three.js r160 (MIT) is embedded in the viewer.
