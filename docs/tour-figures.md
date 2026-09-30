# Knockout tour and courtship figures

Blender renders and an offline 3D viewer of the recorded transmitter and
unlabelled-neuron knockout tour and courtship test ([results](circuit-tour-results.md), [design](circuit-tour.md)),
and a short clip of the [GABA dose experiment](gaba-dose-results.md).
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
| `tipping-point/portrait-4k.mp4`, `-1080p60.mp4` | 6.5 s, 4:5 (2160×2700 and 1080×1350), no text: one brain and nerve cord as the GABA brake is released ([below](#the-tipping-point-clip)). |
| `tipping-point/landscape-4k.mp4`, `-1080p60.mp4` | The same clip in 16:9 (3840×2160 and 1920×1080), lying down, head to the left. |

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
changes. The tipping-point clip keeps the palette and the cap but drops the
log ([below](#the-tipping-point-clip)).

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

## The tipping-point clip

One brain and nerve cord turns slowly while the model's GABA brake is released
step by step. It stays nearly dark through the lower block levels, then lights
up near full block. This is the [GABA dose result](gaba-dose-results.md): firing
outside the sensory neurons rose by 0.09, 0.30, 0.97, 4.6, 9.6 and 12.6 Hz at
10%, 25%, 50%, 75%, 90% and 100% block. The clip has no words, key or scale
bar, for a LinkedIn post.

**Data.** Each dot is coloured by its neuron's recorded change in firing rate
at that block level, averaged over the ten seeds paired against the matched
control: the dose experiment's per-neuron table, the same kind of value as the
tour stills. The levels come in the order they were recorded: rest, then 10%,
25%, 50%, 75%, 90% and full block (the share of GABA-class synaptic strength
removed). The boost and rescue levels are not in the clip. Rest is the paired
control, so its change is zero everywhere and every dot is dim slate. Full
block is the same runs as "GABA switched off" in the tour. Exact spike replays
exist only for about 1,750 wing motor, leg motor and descending neurons, from
one seed, at three block levels and not at rest, so the clip uses the rate
changes, which cover all 162,517 neurons at every level.

**What is interpolated.** 0.5 s at rest, then the block rises at a steady rate
to full block over 4 s, then 2 s held at full block. Each recorded level falls
on one frame: 10% at 0.9 s, 25% at 1.5 s, 50% at 2.5 s, 75% at 3.5 s, 90% at
4.1 s and full block from 4.5 s. Every other frame of the rise shows each
neuron's change on a straight line between the two recorded levels either
side of it. That is a display choice for smooth motion, not a level we ran.

**Colour scale.** The tour's palette, dots and 200 Hz cap (the tour's own rule
gives 200 Hz from the six block levels too: their 99.5th percentile is
194.8 Hz). Unlike the tour figures, the change maps onto the scale in a
straight line, not by the signed log. The log is built to make small changes
visible; here it would show half block at about a third of full-block
brightness, although the brain's extra firing at half block is under a tenth
of that at full block. On the straight scale the brain's light follows its
total extra firing. It follows it, not in exact proportion, because the
palette, glow and dot opacity are not linear in the scale. Changes of 200 Hz
or more get the end colour. Some neurons fire less: from 75% block on, about
500 drop by more than 10 Hz. They are the few blue dots among the warm ones.

**Look.** Every look setting is fixed for the whole clip: only the block level
and the camera change. The camera turns 50° (4:5) or 40° (16:9) about the long
axis and moves 8% closer, with a shallow depth of field focused near the neck;
the bloom is wider than in the tour stills.

**What it can't claim.** These are model firing rates, not a drug given to a
fly, a seizure or a behaviour. A block scales every GABA-class synapse in the
model at once. The dose runs are dark rest: sensory background drive is
injected, with no visual stimulus, and the fly does not see.

MaleCNS v1.0 · Janelia Research Campus, Google Research & University of
Cambridge · Berg et al., *Cell* (2026),
<https://doi.org/10.1016/j.cell.2026.08.015> · CC BY 4.0.

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
uv run --locked scripts/blender/tour.py tipping \
  --outcomes camber-runs/circuit-tour/dose-summary/per-neuron-delta-hz.npz --out figures/tour/tipping-point
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
