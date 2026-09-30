# GABA dose playback: five virtual fly bodies

[Watch the 1080p60 clip](../figures/3d/gaba-dose-body/gaba-dose-body-1080p60.mp4) · [4K master](../figures/3d/gaba-dose-body/gaba-dose-body-4k.mp4) · [dose results](gaba-dose-results.md) · [courtship playback](courtship-body.md)

## What it shows

Five identical virtual fly bodies stand in a row for 10 seconds. Each body replays the recorded motor neuron spikes of one simulated male brain run through rules we picked (below). All five runs come from the same seed of the GABA concentration-response experiment.

- **Resting brain:** the control run. No drug; the brain runs on its background input only.
- **Quarter of GABA receptors blocked:** every GABA synapse in the model at 75% of its normal strength.
- **Three quarters blocked:** every GABA synapse at 25% strength.
- **All blocked:** GABA synapses switched off.
- **Three quarters blocked plus rescue drug:** the three-quarter block, with the model's other fast inhibitory brake, the glutamate-gated chloride synapses, made three times stronger. This is the strongest rescue in the experiment. It was tested against the three-quarter block, not the full block.

Across the ten seeds of the experiment, the average firing rate outside the sensory neurons (1.4 spikes/s at rest) rose by 0.3 spikes/s at the quarter block, 4.6 at three quarters and 12.6 at the full block. The rescue took away 75% of the three-quarter block's rise and left the brain 1.1 spikes/s above rest. The [results page](gaba-dose-results.md) has the intervals.

What you see, measured from the playback:

- **Wings.** The resting fly's wings stay nearly folded: about 1° out on average, and at most 8° when a few resting spikes bunch together in the counting window. That is the data, as on [the courtship page](courtship-body.md#what-it-shows), where the narrower scale makes the same bunches swing much further. The quarter-block fly's wings average 10° and reach up to 20°. Three quarters average 52° on the left and 55° on the right and swing between about 15° and 70°. All blocked stay between 66° and 74° (the 70° ceiling plus spike flicks). The rescue fly's wings average 10° and 11°, like the quarter block's, but swing further, up to about 38°, because its wing cells fire less evenly. The wings carry the dose steps because this clip uses a ten times wider wing scale than the courtship clip (below). With the rescue, the four wing cells fire on average about 50 spikes/s per side above rest, close to the quarter block's 55.
- **Legs.** The resting fly's legs stand still (see below). At the quarter block the legs lift by at most 1.6° on average, 4.4° at the most. At three quarters they lift 1° to 6° on average, 10° at the most. At the full block they lift 8° to 30° and stay up. The rescue fly's legs lift 0.2° to 2.3° on average, 7° at the most. The legs carry the dose steps.
- **No thrashing.** At the full block the leg motor neurons fire hard but steadily, not in bursts. Under the rule that draws the legs up and holds them there with a small tremble.
- **The first moment.** For the first 0.2 s the counting window is still filling, so every fly starts with folded wings and standing legs, and each drug fly's wings and legs reach their level during that first fifth of a second.

## From spikes to wings

The wings use the courtship clip's rule with one number changed; [the courtship page](courtship-body.md#from-spikes-to-wings) explains it step by step. Each wing reads that side's `ps1 MN` and `hg1 MN`, two of the 66 wing motor neurons. It counts their spikes in the last 0.2 s, subtracts their resting rate (their mean in the first 5 seconds of the resting run: about 33 spikes/s on the left, 52 on the right), and turns the extra rate into an outward swing along a straight line, up to a 70° wing. On top of that, each recorded spike adds a small flick of at most ±4°. MuJoCo moves the body at the brain's 0.1 ms step.

The number that changes is the extra rate that gives the full 70° wing:

| Clip | Full 70° wing at | Why this scale |
|---|---|---|
| [Courtship](courtship-body.md) | 40 extra spikes/s per side | Strong P1 input raised the four cells by about 31 spikes/s per side in the seed shown. |
| GABA dose (this clip) | 400 extra spikes/s per side | The drugs drive the same four cells about ten times harder: about 300 spikes/s per side above rest at three quarters and 390 at the full block. At the quarter block the rise is about 55. |

On the courtship scale, every drug fly's wings would sit at the ceiling from the quarter block on, so the wings couldn't show the dose steps. On the 400 scale the full block sits at the ceiling, three quarters averages 52° to 55°, and the quarter block and the rescue show a small lift, about 10° on average. All five bodies in this clip use the 400 scale, the resting fly too, so they compare with each other. They don't compare angle for angle with the courtship clip: the same wing angle means ten times more firing here. The 0.2 s window, the resting rate and the flicks are the same in both clips. The courtship clip and its `wing-joints.csv` keep the 40 scale and are unchanged.

## From spikes to legs

The MaleCNS motor inventory ([`malecns-populations.json`](../validation/records/p2/malecns-populations.json)) lists 373 typed leg motor neurons. Each one is assigned to a leg by its cell body's side and its leg class (front, middle or hind). That gives six pools of 58 to 68 cells, one per leg.

The rule, for each leg, every 0.1 ms:

1. Count that leg's motor neuron spikes in the last 0.2 s and turn the count into spikes per second per neuron.
2. Subtract the same neurons' mean rate over the whole 10 s resting run: 1.0 to 2.9 spikes/s per neuron, depending on the leg. Anything below zero counts as zero.
3. Map the extra rate onto a lift. 0 extra spikes/s is the standing pose. 30 or more is a full lift: the femur rises by 30° and the tibia folds in by 30°, which raises the foot.

The legs are set by joint angle through the body model's pose, not moved by simulated muscles. The thorax is fixed and gravity is off, as in the courtship clip, so the legs can't collapse under the body, and leg motion can't move the body or the wings.

Every cell in a pool counts the same, whether it is a flexor, extensor, levator or rotator. The rule doesn't set muscles against each other; it reads how hard a leg's whole pool fires. A lift means that leg's motor neurons fired above their resting rate. It doesn't say which muscle would pull.

**The resting fly's legs have nothing to replay.** The resting run's spike recording kept the wing motor and courtship neurons, not the leg motor neurons, so its legs hold the standing pose. Its wings do replay recorded spikes. Standing still is also the rule's zero point, since the rule reads rate above rest. A recorded resting run would still show small chance lifts from spikes that bunch together in the 0.2 s window; the quarter block's lifts, at most about 4°, give a sense of their size. Only the four drug flies' legs are driven by recorded spikes. The dose runs can't stand in for rest: their recordings start after 2 s under the drug, so they hold no drug-free stretch. Driving the resting legs from data would need a new resting run that records the leg motor neurons, and this clip only replays runs that already exist.

## Free choices

These are display choices, not measured properties of a fly's legs or wings: the six pools and assigning cells by cell body side, weighting every cell type the same, the 0.2 s window, subtracting the resting rate, the 30 spikes/s per neuron scale, the 30° lift, lifting the femur and tibia and not other joints, the direction of the lift, and posing the legs by angle. For the wings: the 400 spikes/s per side scale and using it for all five bodies. The wing rule's other choices are listed on [the courtship page](courtship-body.md#free-choices). So are the camera, lighting, colours, the standing pose, the row of five, the labels, and showing one seed out of ten. Nothing here was fitted to real fly movement.

## What it can't claim

- **One-way playback.** The brain ran first; its spikes were recorded; the bodies replay them. Nothing flows back: no leg or wing position, touch, air or sight reaches the brain. It is not a closed loop.
- **The fly doesn't see.** These dark-rest dose runs inject background drive into sensory cells, without a TuBu stimulus. There is no image and no sound.
- **Motor spikes are not behaviour.** The model has no muscles and no body of its own. A lifted leg here means leg motor neurons fired above rest under a chosen rule. It does not show that a fly given a GABA blocker would lift its legs, twitch, freeze or seize.
- **Not a real drug.** A block scales the strength of every GABA synapse in the model at once; the rescue scales the glutamate-gated chloride synapses. The block levels are fractions of GABA conductance blocked, not drug concentrations: the source potency could not be verified. The rescue strength is a multiplier, not a measured dose. There is no absorption, no other drug target and no receptor map.
- **One run per condition.** The motion comes from one seed. The whole-brain numbers are ten-seed averages from the results page. The wing and leg numbers above are from the one seed shown.

The recorded spike files stay outside Git. [The playback README](../scripts/courtship_body/README.md) has the environment, the checks each input file must pass and the commands.
