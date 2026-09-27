# Body playback (courtship and GABA dose) — local build

This is an isolated uv project. On this Mac: `cd scripts/courtship_body && uv sync --frozen`. It does not touch the brain environment. Requires Blender 5.2 at `/opt/homebrew/bin/blender`. FlyGym 1.1.0 (NeuroMechFly v2 mesh), MuJoCo 3.2.3 and NumPy 1.26.4 are pinned in `pyproject.toml` and `uv.lock`. FlyGym was chosen over flybody: its NeuroMechFly mesh loads on this Mac and runs in plain MuJoCo without flybody's dm_control/JAX policy stack. **Important:** this FlyGym asset has wing *bodies* but no wing *joints*. `playback.py` adds L/R hinges and position servos in memory before simulation; these hinges and gains are a chosen mapping of the recorded motor spikes, not validated wing joints, and the playback shows no song.

## Courtship clip

Inputs come from the courtship run (`scripts/circuit_tour.py` on main): the P1-high outcome and its same-seed control, each as `*.npz` with its same-stem `*.json`, both exact-tick replays (`*-spikes.npz` with matching `*-spikes.json`), and the matching `engine-order.csv`. From the repository root:

```
P=/absolute/path/to/courtship/outcomes
scripts/courtship_body/.venv/bin/python scripts/courtship_body/playback.py \
  --counts "$P/seed-501-P1-high.npz" --spikes "$P/seed-501-P1-high-spikes.npz" \
  --control-counts "$P/seed-501-control.npz" --control-spikes "$P/seed-501-control-spikes.npz" \
  --engine-order .cache/malecns-v1.0/derived/engine-order.csv \
  --poses /tmp/courtship-poses.npz --csv figures/3d/courtship-body/wing-joints.csv
/opt/homebrew/bin/blender -b -t 8 --python scripts/courtship_body/render.py -- \
  --poses /tmp/courtship-poses.npz --out figures/3d/courtship-body/courtship-4k.mp4
```

Before simulating, `playback.py` checks each archive's SHA-256 against its run record, checks that each replay belongs to its outcome (seed, condition, source hash), that both runs share a seed, and that every one of the four motor cells' ON/OFF spike totals equals its outcome count. The control run's ON-window mean rates are the spontaneous baseline for both bodies. `wing-joints.csv` holds each body's measured and target wing angles per frame.

## GABA dose clip

Inputs: the dose outcome folder of the GABA concentration-response run (`scripts/circuit_tour_dose_replay.py`), which holds `seed-S-{block-0.25,block-0.75,block-1.00,rescue-2.00}.npz` and their `-spikes.npz` replays of the wing motor, typed leg motor and descending neurons, each with its `.json`; and the same seed's courtship-run control and control replay as the resting body. From the repository root:

```
D=/absolute/path/to/dose-outcomes
P=/absolute/path/to/courtship/outcomes
scripts/courtship_body/.venv/bin/python scripts/courtship_body/dose.py \
  --outcomes "$D" --seed 501 \
  --control-counts "$P/seed-501-control.npz" --control-spikes "$P/seed-501-control-spikes.npz" \
  --engine-order .cache/malecns-v1.0/derived/engine-order.csv --poses /tmp/dose-poses.npz
/opt/homebrew/bin/blender -b -t 8 --python scripts/courtship_body/render.py -- \
  --poses /tmp/dose-poses.npz --out figures/3d/gaba-dose-body/gaba-dose-body-4k.mp4
```

`dose.py` checks each dose archive and replay the same way (hashes, seed, condition, source hash, the 2 s settle plus 10 s measure windows, ticks inside the measure window), that the replay's leg motor neurons are exactly the inventory's 373 typed leg motor neurons, and that the spike totals of the four wing cells and of each leg pool equal the outcome counts. Wings use `playback.py`'s rule with the full 70° wing at 400 extra spikes/s per side instead of 40 (`WING_HZ` in `dose.py`, for all five bodies), because the drugs drive the wing cells about ten times harder than courtship input; `playback.py` keeps 40 for the courtship clip. Legs use `leg_lift` in `playback.py`. The resting replay recorded no leg motor spikes, so the resting body's legs hold the standing pose. It prints each body's mean and largest wing angle and each leg's mean and largest lift. A run takes about 15 seconds.

## Rendering

The pose NPZ holds geometry, per-frame geom poses and the layout (body order, offsets, labels) for re-rendering and is not committed. Add `--preview --frame N` to the Blender line to render one labelled half-resolution still instead of the clip. A full courtship render takes about two hours on the M5 Pro; the five-body dose render took 1 h 40 min.

Blender on this Mac cannot select FFMPEG as a headless output format, so `render.py` renders 4K PNGs to a temporary directory and encodes them with the isolated environment's `imageio-ffmpeg` binary, which also draws the labels and a light vignette. It then writes the 1080p60 copy (`*-1080p60.mp4`). See [the courtship explanation](../../docs/courtship-body.md) and [the dose explanation](../../docs/gaba-dose-body.md) for the mappings and their limits. No brain data, engine code or tests are changed.
