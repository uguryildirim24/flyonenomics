# Wing motor playback: two virtual fly bodies

[Watch the 1080p60 clip](../figures/3d/courtship-body/courtship-1080p60.mp4) · [4K master](../figures/3d/courtship-body/courtship-4k.mp4) · [wing joint angles](../figures/3d/courtship-body/wing-joints.csv)

## What it shows

Two identical virtual fly bodies stand side by side for 10 seconds. **The wings move as a chosen mapping of the model's recorded motor spikes**: each body replays the wing motor neuron spikes of one simulated male brain run through a rule we picked (below). The model does not sing, and the clip does not show song or song rhythm.

- **Left, "Resting brain":** a control run. No extra input; the brain runs on its background input only.
- **Right, "Courtship neurons on":** the same seed with strong input injected into the P1 courtship neurons for the first 5 seconds. At 5 s the input stops and the label changes to "Courtship neurons off" for the last 5 seconds.

Both runs come from the courtship circuit run (P1-high and control, one matched seed). Across the ten seeds of that run, high P1 input raised pIP10 firing by about 36 spikes/s, dPR1 by about 26 and the wing motor neuron group by about 9, compared with matched control runs. vPR6 never spiked. In the one seed shown, the four motor cells that drive the wings fired about 31 spikes/s more per side than in the control while P1 input was on. After it stopped they sat about 3 spikes/s above the control's resting rate. That is one seed. The ten-seed group change is an average over all 66 wing motor neurons and does not show that these four cells, or either side, are recruited in particular.

What you see, measured from the playback: the right fly's wings stand out about 47° on average during the first 5 seconds and about 14° after the input stops. The left fly's wings average about 8°. **The resting fly's wings move too.** Wing motor neurons fire on their own at rest, and when a few extra spikes bunch together the same rule swings the wing out briefly. That is the data, not a glitch.

## From spikes to wings

The body is FlyGym 1.1.0's NeuroMechFly v2 fly (Wang-Chen et al., *Nature Methods* 2024, [doi:10.1038/s41592-024-02497-y](https://doi.org/10.1038/s41592-024-02497-y)), simulated in MuJoCo. Its mesh has wing shapes but no wing joints, so the playback adds one hinge per wing at load time. Each hinge swings its wing outward, away from the body, and a position motor pulls the wing toward a target angle.

Four of the 66 wing motor neurons drive the wings: `ps1 MN` and `hg1 MN`, left and right. They are the motor neurons of two wing muscles; the identities and sides come from the MaleCNS motor inventory ([`malecns-populations.json`](../validation/records/p2/malecns-populations.json)). In real flies a small set of wing muscles and their motor neurons shape the male's courtship song (O'Sullivan et al., *Current Biology* 2018, [doi:10.1016/j.cub.2018.06.038](https://doi.org/10.1016/j.cub.2018.06.038)); that is why these cells are the ones read. The paper motivates the choice of cells only. It gives no spike-to-angle rule, and nothing here validates one. Left cells move the left wing, right cells the right wing.

The rule, for each wing, every 0.1 ms:

1. Count that side's `ps1` and `hg1` spikes in the last 0.2 s and turn the count into spikes per second.
2. Subtract the two cells' resting rate: their mean rate in the matched control run while its input window was on (about 33 spikes/s on the left, 52 on the right). Anything below zero counts as zero.
3. Map the extra rate onto an outward swing: 0 extra spikes/s is a folded wing, 40 or more is 70°.
4. On top of that, each recorded `ps1` spike gives the wing a +2° flick and each `hg1` spike a −1° flick. The flicks fade over 20 ms and together never exceed ±4°. They land at the exact recorded spike times. No steady vibration or rhythm is added.

MuJoCo moves the body at 0.1 ms steps, the same step as the brain recording. The film shows the body pose every 1/60 s. Both flies use exactly the same rule and the same resting rate.

The legs hold FlyGym's standing tripod pose and do not move; gravity is switched off so the unpowered legs don't sag. The wing angles come out exactly the same with gravity on and off (checked against an earlier gravity-on run of the same replay).

## Free choices

These are display choices, not measured properties of a fly's wing: the 0.2 s window, subtracting the control rate, the 40 spikes/s scale, the 70° maximum, the hinge axis, the flick sizes and signs, the 20 ms fade, the ±4° cap and the motor strength. So are the camera, lighting, colours, the standing pose, and showing one seed out of ten. Nothing here was fitted to real fly wing movement.

## What it can't claim

- **One-way playback.** The brain ran first; its spikes were recorded; the bodies replay them. Nothing flows back: no wing position, touch, air or sight reaches the brain. It is not a closed loop.
- **The fly doesn't see.** The P1 input and the background input are injected into the model. There is no female, no image and no sound.
- **Not song.** The model does not sing, and the recorded rates don't show rhythmic song output. A real fly vibrates its wing hundreds of times a second when it sings; a 60 fps film can't show that, and this rule doesn't make it. The wing swings show how much four motor cells fired above rest under a chosen rule, not a song and not a validated spike-to-muscle mapping.
- **Not a clean chain.** Wing motor cells fire before P1 does, because they fire at rest, so the first-spike order doesn't show P1 driving the wings step by step.
- **One run.** The motion comes from one seed. The rate numbers above the rule are the ten-seed averages from the courtship run summary.

The recorded spike files stay outside Git. [The playback README](../scripts/courtship_body/README.md) has the environment, the checks it runs on the input files and the commands.
