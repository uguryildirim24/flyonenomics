# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "numpy==2.5.3", "pandas==3.0.5", "pyarrow==25.0.1",
#   "pydantic==2.12.4", "pyyaml==6.0.3", "scipy==1.16.2",
#   "fast-simplification==0.1.13", "pillow==11.3.0",
# ]
# ///
"""Blender and Three.js figures for the chemical knockout tour and courtship test.

    uv run --locked scripts/blender/tour.py prepare
    uv run --locked scripts/blender/tour.py values --outcomes per-neuron-delta-hz.npz --out values.npz
    uv run --locked scripts/blender/tour.py figures --values values.npz --out figures/tour \
        --spikes seed-501-P1-high-spikes.npz
    uv run --locked scripts/blender/tour.py viewer --values values.npz --out figures/tour/viewer.html
    uv run --locked scripts/blender/tour.py tipping --outcomes dose/per-neuron-delta-hz.npz \
        --out figures/tour/tipping-point

`prepare` builds display geometry once into the main checkout's ignored cache.
`values` turns the paired per-neuron rate changes into one table per condition.
`figures` runs Blender headless for every still and clip, then adds plain labels;
the courtship clip replays one run's exact spikes.
`viewer` writes the offline Three.js page with the same colour scale.
`tipping` renders the GABA dose clip, with no text, from the dose experiment's paired rate changes.
See docs/tour-figures.md. Nothing here runs or changes the model.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render_malecns_3d as atlas  # noqa: E402

SCENE = "visuals/tour/scene.npz"
BLENDER = shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
POINTS_PER_NEURON = 8
# Courtship path in wiring order: key, figure label, frozen population names.
PATH = [
    ("P1", "P1 neurons", ["P1"]),
    ("pIP10", "pIP10", ["pIP10"]),
    ("song", "Song neurons", ["dPR1", "vPR6", "TN1a", "TN1c"]),
    ("wing", "Wing motor neurons", ["wing_motor"]),
]
LABELS = {
    "control": "Normal brain",
    "off-acetylcholine": "Acetylcholine switched off",
    "off-gaba": "GABA switched off",
    "off-glutamate": "Glutamate switched off",
    "off-histamine": "Histamine switched off",
    "off-dopamine": "Dopamine switched off",
    "off-octopamine": "Octopamine switched off",
    "off-serotonin": "Serotonin switched off",
    "off-unclear": "Unlabelled neurons switched off",
    "P1-low": "P1 switched on, low drive",
    "P1-medium": "P1 switched on, medium drive",
    "P1-high": "P1 switched on, high drive",
    "pIP10": "pIP10 switched on",
    "courtship_random": "Random neurons switched on",
}
KNOCKOUTS = [k for k in LABELS if k.startswith("off-")]
COURTSHIP = ["P1-low", "P1-medium", "P1-high", "pIP10", "courtship_random"]
# One diverging scale for Blender and the browser. Hue carries the sign;
# brightness, glow and dot size carry the size of the change.
LOOK = json.loads((HERE / "look.json").read_text())
PALETTE = LOOK["palette"]


def cache() -> Path:
    return atlas.main_cache()


class Assets(atlas.Assets):
    """The atlas downloader, pinning new fetches in this folder's downloads.json
    so data/ (model input) stays untouched."""

    RECEIPT = HERE / "downloads.json"

    def __init__(self, root: Path):
        super().__init__(root)
        self.pinned = set(self.records)
        for record in json.loads(self.RECEIPT.read_text()):
            self.records.setdefault(record["name"], record)

    def save(self) -> None:
        self.RECEIPT.write_text(json_text([self.records[k] for k in sorted(self.records) if k not in self.pinned]))


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


# ---------------------------------------------------------------- prepare

def splitmix64(x: np.ndarray) -> np.ndarray:
    """Deterministic, outcome-free ordering of synapse ids for sampling."""
    z = x.astype(np.uint64) + np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return z ^ (z >> np.uint64(31))


def keep_first(idx, pri, xyz, k):
    order = np.lexsort((pri, idx))
    idx, pri, xyz = idx[order], pri[order], xyz[order]
    starts = np.r_[0, np.flatnonzero(np.diff(idx)) + 1]
    rank = np.arange(len(idx)) - np.repeat(starts, np.diff(np.r_[starts, len(idx)]))
    keep = rank < k
    return idx[keep], pri[keep], xyz[keep]


def synapse_sample(path: Path, bodies: np.ndarray, k: int):
    """Up to k of each neuron's own synapse sites, chosen by a hash of the site id."""
    import pyarrow as pa
    reader = pa.ipc.open_file(pa.memory_map(str(path)))
    order = np.argsort(bodies)
    sorted_bodies = bodies[order]
    kept, pending = None, []
    for i in range(reader.num_record_batches):
        batch = reader.get_batch(i)
        body = batch.column("body").to_numpy()
        pos = np.minimum(np.searchsorted(sorted_bodies, body), len(bodies) - 1)
        hit = sorted_bodies[pos] == body
        if hit.any():
            xyz = np.stack([batch.column(c).to_numpy()[hit] for c in "xyz"], 1).astype(np.int32)
            pending.append((order[pos[hit]].astype(np.int32),
                            splitmix64(batch.column("point_id").to_numpy()[hit]), xyz))
        if len(pending) >= 256 or (i == reader.num_record_batches - 1 and pending):
            parts = ([kept] if kept else []) + pending
            kept = keep_first(*(np.concatenate([p[j] for p in parts]) for j in range(3)), k)
            pending = []
        if i % 500 == 0:
            print(f"Synapse sites {i}/{reader.num_record_batches}", flush=True)
    return kept[0], kept[2]


def annotations_frame(assets):
    import pandas as pd
    name = "body-annotations-male-cns-v1.0-minconf-0.5.feather"
    record = next(r for r in assets.manifest["files"] if r["name"] == name)
    source = atlas.read_feather(assets.get(name, record["url"], record["used_for"])).to_pandas()
    source = source.loc[(source.status == "Traced") & source.type.notna()]
    return pd.DataFrame({
        "root_id": source.bodyId, "hemibrain_type": source.type,
        "cell_class": source["class"], "cell_sub_class": source["subclass"],
        "side": source.somaSide.fillna(source.rootSide).map({"L": "left", "R": "right"}),
    })


def path_cells(assets, populations: Path):
    annotations = annotations_frame(assets)
    order = annotations.root_id.to_numpy(dtype=np.int64)
    _, entries = atlas.load_population_table(populations)
    entries = {e.name: e for e in entries}
    cells = []
    for key, _, names in PATH:
        missing = [n for n in names if n not in entries]
        if missing:
            raise SystemExit(f"{populations} lacks courtship populations {missing}; pass --populations")
        ids = sorted({int(r) for n in names for r in atlas.resolve_population(entries[n], annotations, order).root_ids})
        cells += [dict(body_id=str(b), group=key) for b in ids]
    return cells


def skeleton_arrays(assets, cells):
    """Whole courtship-path centerlines as vertices + edges, one cell index per vertex."""
    segments = atlas.neurons(assets, cells)
    verts, edges, owner = [], [], []
    offset = 0
    for i, cell in enumerate(segments):
        s = np.frombuffer(base64.b64decode(cell["points"]), "<f4").reshape(-1, 3)
        unique, inverse = np.unique(np.round(s, 2), axis=0, return_inverse=True)
        verts.append(unique)
        edges.append(inverse.reshape(-1, 2) + offset)
        owner.append(np.full(len(unique), i, np.int32))
        offset += len(unique)
    return (np.concatenate(verts).astype(np.float32), np.concatenate(edges).astype(np.int32),
            np.concatenate(owner))


def prepare(args):
    import pandas as pd
    root = cache()
    assets = Assets(root)
    bodies = pd.read_csv(root / "derived/engine-order.csv").root_id.to_numpy(np.int64)
    arrays, meshes = {}, []
    budgets = {"CentralBrain": 160000, "Optic(L)": 80000, "Optic(R)": 80000, "VNC": 100000, "CV": 12000}
    specs = [("major", "rois/malecns-major-compartments-v2", n, "shell", b) for n, b in budgets.items()]
    brain = [f"{p}({s})" for p in ("aL", "bL", "gL", "a'L", "b'L", "CA", "PED", "ME", "LO", "LOP", "BU", "AOTU")
             for s in ("L", "R")] + ["EB", "FB", "PB", "NO"]
    specs += [("neuropils", "rois/fullbrain-roi-v4", n, "neuropil", 12000) for n in brain]
    specs += [("vnc", "rois/malecns-vnc-neuropil-roi-v0", n, "neuropil", 12000) for n in
              [f"LegNp(T{t})({s})" for t in (1, 2, 3) for s in ("L", "R")] + ["ANm", "LTct", "IntTct"]]
    for folder, prefix, name, group, faces in specs:
        m = atlas.mesh_asset(assets, folder, prefix, name, group, "#000000", 0, faces)
        i = len(meshes)
        arrays[f"mesh{i}_v"] = np.frombuffer(base64.b64decode(m["vertices"]), "<f4").reshape(-1, 3)
        arrays[f"mesh{i}_f"] = np.frombuffer(base64.b64decode(m["faces"]), "<u4").reshape(-1, 3)
        meshes.append(dict(name=name, group=group))
    idx, xyz = synapse_sample(root / "syn-points-male-cns-v1.0-minconf-0.5.feather", bodies, args.points)
    # Synapse sites are 8 nm voxels; the atlas transform takes nanometres.
    points = atlas.display_coordinates(xyz.astype(np.float64) * 8).astype(np.float32)
    starts = np.r_[0, np.flatnonzero(np.diff(idx)) + 1]
    rank = (np.arange(len(idx)) - np.repeat(starts, np.diff(np.r_[starts, len(idx)]))).astype(np.int8)
    cells = path_cells(assets, args.populations)
    sv, se, so = skeleton_arrays(assets, cells)
    arrays.update(body_ids=bodies, dust_points=points, dust_neuron=idx.astype(np.int32), dust_rank=rank,
                  path_body=np.array([int(c["body_id"]) for c in cells], np.int64),
                  path_group=np.array([[k for k, *_ in PATH].index(c["group"]) for c in cells], np.int8),
                  skel_v=sv, skel_e=se, skel_cell=so,
                  meta=np.frombuffer(json.dumps(dict(meshes=meshes, path=[p[:2] for p in PATH],
                                                     points_per_neuron=args.points)).encode(), np.uint8))
    out = root / SCENE
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **arrays)
    missing = len(bodies) - len(np.unique(idx))
    print(f"Scene: {len(meshes)} meshes, {len(points):,} synapse sites for "
          f"{len(bodies) - missing:,}/{len(bodies):,} neurons, {len(cells)} path skeletons -> {out}")
    print("Bounds (µm):", points.min(0).round(1), points.max(0).round(1))


# ---------------------------------------------------------------- values

def nice_ceiling(x: float) -> float:
    exponent = math.floor(math.log10(x))
    for step in (1, 2, 5, 10):
        if step * 10 ** exponent >= x:
            return float(step * 10 ** exponent)
    raise AssertionError


def per_neuron(data, bodies: np.ndarray, conditions: list[str]) -> list[np.ndarray]:
    """The named rows of an outcome table, in the scene's neuron order."""
    roots = data["root_ids"].astype(np.int64)
    if len(roots) != len(np.unique(roots)):
        raise ValueError("duplicate neuron ids in outcome table")
    position = {int(r): i for i, r in enumerate(roots)}
    missing = [int(b) for b in bodies if int(b) not in position]
    if missing:
        raise ValueError(f"{len(missing)} simulated neurons have no value, e.g. {missing[:3]}")
    take = np.array([position[int(b)] for b in bodies])
    return [data[c][take] for c in conditions]


def scale_cap(table: np.ndarray) -> float:
    """One fixed visual range for every condition: the 99.5th percentile of all
    non-zero changes, rounded up. Larger changes saturate at the end colour."""
    if not np.isfinite(table).all():
        raise ValueError("non-finite values")
    return nice_ceiling(float(np.percentile(np.abs(table[table != 0]), 99.5)))


def write_values(out: Path, table: np.ndarray, bodies: np.ndarray, meta: dict):
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, values=table.astype(np.float32), body_ids=bodies,
                        meta=np.frombuffer(json.dumps(meta).encode(), np.uint8))


def values(args):
    scene = np.load(cache() / SCENE)
    bodies = scene["body_ids"]
    if args.synthetic:
        # Development only: stripes across the brain that no experiment makes.
        points, owner = scene["dust_points"], scene["dust_neuron"]
        x = np.zeros(len(bodies))
        x[owner] = points[:, 0]
        conditions = ["control", *KNOCKOUTS, *COURTSHIP]
        table = np.stack([np.zeros_like(x) if c == "control" else
                          40 * np.sin(x / 35 + i)
                          for i, c in enumerate(conditions)])
        kind, unit = "synthetic", "made-up units"
    else:
        data = np.load(args.outcomes)
        conditions = ["control"] + [c for c in LABELS if c != "control" and c in data.files]
        unknown = sorted(set(data.files) - set(LABELS) - {"root_ids"})
        if unknown:
            raise ValueError(f"no plain label for conditions {unknown}")
        table = np.stack([np.zeros(len(bodies)), *per_neuron(data, bodies, conditions[1:])])
        kind, unit = "model", "Hz"
    cap = scale_cap(table)
    meta = dict(kind=kind, unit=unit, conditions=conditions, labels=[LABELS[c] for c in conditions],
                cap=cap, knee=cap / 50,
                source=str(args.outcomes) if args.outcomes else "synthetic")
    write_values(args.out, table, bodies, meta)
    summary = {c: dict(mean_abs=float(np.abs(v).mean()), up=int((v > 0).sum()), down=int((v < 0).sum()))
               for c, v in zip(conditions, table)}
    print(json.dumps(dict(cap=cap, unit=unit, kind=kind, summary=summary), indent=1))


def most_changed(values_path: Path) -> str:
    """The knockout with the largest mean absolute change over all simulated neurons."""
    table, meta = load_values(values_path)
    scores = {c: float(np.abs(v).mean()) for c, v in zip(meta["conditions"], table) if c in KNOCKOUTS}
    return max(scores, key=scores.get)


def load_values(path: Path):
    data = np.load(path)
    return data["values"], json.loads(bytes(data["meta"]))


# ---------------------------------------------------------------- figures

# Cameras in atlas µm: +x across, +y dorsal, +z anterior. `direction` points from
# the target to the camera; `up` is the atlas direction shown upward on screen.
VIEWS = {
    # Whole CNS from above and a little in front, brain on the left.
    "hero": dict(target=[0, -90, -330], direction=[0, 1, 0.38], up=[-1, 0, 0], distance=3600, lens=85),
    # Upright CNS turning about its long axis, for the side-by-side panels.
    "spin": dict(target=[0, -90, -400], direction=[0, 1, 0.1], up=[0, 0, 1], distance=2850, lens=85,
                 spin=dict(axis=[0, 0, 1], start=-35, degrees=70)),
    # From the fly's side, brain on the right: P1 → pIP10 → nerve-cord song circuit.
    "path": dict(target=[0, -90, -330], direction=[-1, 0.75, 0.12], up=[0, 1, 0], distance=3100, lens=85),
    "path_move": dict(target=[0, -90, -330], direction=[-1, 0.75, 0.12], up=[0, 1, 0], distance=3100, lens=85,
                      spin=dict(axis=[0, 1, 0], start=-10, degrees=20)),
}
# The path clip's clock: model time runs slowly at first and faster later, so the
# first milliseconds after the input switches on can be followed spike by spike.
# model ms = CLOCK_MS * (e^(CLOCK_GROWTH * clip seconds) - 1); the frames show the true model time.
CLOCK_MS, CLOCK_GROWTH = 10.0, 0.5
SPIKE_FADE_MS = 20.0  # each spike lights its cell; the light fades with this model-time constant
SETTLE_MS, ON_MS = 2000.0, 5000.0  # replay windows: 2 s settle (not saved), then 5 s with the input on


def clock(frames: int, fps: int) -> np.ndarray:
    return CLOCK_MS * np.expm1(CLOCK_GROWTH * np.arange(frames) / fps)


def spike_flashes(replay: Path, condition: str, cells: np.ndarray, times: np.ndarray) -> np.ndarray:
    """[frame, cell] flash strength from the circuit tour's exact spike replay (input-on window).
    Each spike adds a flash of 1 that fades with SPIKE_FADE_MS; a frame shows the mean
    over the model time since the previous frame, like a camera shutter, so a steady
    rate r averages r * SPIKE_FADE_MS whatever the playback speed."""
    record = json.loads(replay.with_suffix(".json").read_text())
    if (record.get("kind") != "visualisation-aid-not-new-outcome"
            or record.get("condition") != condition
            or record.get("recorded_full_neuron_on_off_counts_equal") is not True
            or record.get("dt_ms") != 0.1
            or hashlib.sha256(replay.read_bytes()).hexdigest() != record.get("spike_sha256")):
        raise SystemExit(f"{replay.name} is not a verified replay of {condition}")
    if len(np.unique(cells)) != len(cells):
        raise SystemExit("a path cell appears twice")
    with np.load(replay) as data:
        idx, t = data["on_idx"], data["on_tick"] * record["dt_ms"] - SETTLE_MS
    if len(t) and (t.min() < 0 or t.max() >= ON_MS):
        raise SystemExit("replay spikes fall outside the input-on window")
    order = np.argsort(cells)
    slot = np.minimum(np.searchsorted(cells, idx, sorter=order), len(cells) - 1)
    hit = cells[order[slot]] == idx
    column, t = order[slot[hit]], t[hit]
    out = np.zeros((len(times), len(cells)), np.float32)
    for f, end in enumerate(times):
        start = times[f - 1] if f else end
        live = t <= end
        age = end - t[live]
        if end > start:
            since = np.maximum(start, t[live]) - t[live]
            value = SPIKE_FADE_MS / (end - start) * (np.exp(-since / SPIKE_FADE_MS) - np.exp(-age / SPIKE_FADE_MS))
        else:
            value = np.exp(-age / SPIKE_FADE_MS)
        np.add.at(out[f], column[live], value)
    return out


def clock_text(ms: float) -> str:
    return f"{ms:.1f} ms after the input switched on" if ms < 10 else f"{ms:.0f} ms after the input switched on"


FONT = Path("/Library/Fonts")
INK, MUTED, PAPER = (226, 232, 240), (150, 162, 178), (4, 6, 10)


def slug(label: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in label.lower()).replace("--", "-").strip("-")


def font(weight: str, size: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONT / f"SF-Pro-Display-{weight}.otf"), size)


def scale_position(v, cap, knee):
    return math.copysign(min(math.log1p(abs(v) / knee) / math.log1p(cap / knee), 1.0), v)


def palette_colour(m: float) -> tuple[int, int, int]:
    stops = PALETTE["up" if m >= 0 else "down"]
    pos = [s[0] for s in stops]
    rgb = np.array([[int(s[1][i:i + 2], 16) for i in (1, 3, 5)] for s in stops], float)
    return tuple(int(round(np.interp(abs(m), pos, rgb[:, j]))) for j in range(3))


def ticks(cap: float, knee: float) -> list[float]:
    """0, the ends of the scale and decades in between."""
    result = [0.0, cap, -cap]
    step = 10 ** math.floor(math.log10(cap))
    step = step / 10 if step >= cap / 2 else step
    while step >= knee and len(result) < 7:
        result += [step, -step]
        step /= 10
    return result


def colour_key(meta: dict, width: int, scale: float = 1.0):
    """The shared colour scale: hue for direction, brightness for size of change."""
    from PIL import Image, ImageDraw
    cap, knee, unit = meta["cap"], meta["knee"], meta["unit"]
    bar_h, pad = int(22 * scale), int(64 * scale)
    img = Image.new("RGB", (width, int(210 * scale)), PAPER)
    draw = ImageDraw.Draw(img)
    x0, x1, y0 = pad, width - pad, int(78 * scale)
    for x in range(x0, x1):
        draw.line([(x, y0), (x, y0 + bar_h)], fill=palette_colour(2 * (x - x0) / (x1 - x0) - 1))
    small, label = font("Regular", int(26 * scale)), font("Medium", int(30 * scale))
    title = f"Change in firing rate from the normal brain ({unit})"
    draw.text((width / 2, int(30 * scale)), title, font=label, fill=INK, anchor="mm")
    for v in ticks(cap, knee):
        x = x0 + (scale_position(v, cap, knee) + 1) / 2 * (x1 - x0)
        draw.line([(x, y0 + bar_h), (x, y0 + bar_h + 10 * scale)], fill=MUTED, width=max(1, int(2 * scale)))
        text = "0" if v == 0 else f"{v:+g}".replace("-", "−")
        draw.text((x, y0 + bar_h + 26 * scale), text, font=small, fill=MUTED, anchor="mt")
    draw.text((x0, y0 + bar_h + 76 * scale), "Fires less", font=small, fill=palette_colour(-0.7), anchor="lt")
    draw.text((x1, y0 + bar_h + 76 * scale), "Fires more", font=small, fill=palette_colour(0.7), anchor="rt")
    return img


def stamp(img, meta):
    """Development renders say so across the picture; real data never gets this."""
    if meta["kind"] != "synthetic":
        return img
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    size = max(24, img.width // 40)
    draw.text((img.width - size, size), "SYNTHETIC TEST VALUES · NOT A RESULT", font=font("Bold", size),
              fill=(255, 64, 64), anchor="ra")
    return img


def haloed(img, xy, text: str, face, anchor: str, radius: int):
    """Text over a soft dark halo, so a label stays legible where it crosses lit cells."""
    from PIL import Image, ImageDraw, ImageFilter
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=face, anchor=anchor, fill=255, stroke_width=radius, stroke_fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(v * 0.85))
    img.paste(Image.new("RGB", img.size, PAPER), (0, 0), mask)
    ImageDraw.Draw(img).text(xy, text, font=face, anchor=anchor, fill=INK)


def compose_still(render: Path, label: str, meta: dict, out: Path, view: dict, note: str,
                  anchors: dict | None = None, clock: str | None = None):
    """Label, note, path labels and scale bar; the colour key, or for a spike clip
    frame (whose flashes are spikes, not rate changes) the model clock instead."""
    from PIL import Image, ImageDraw
    img = Image.open(render).convert("RGB")
    s = img.width / 3840
    draw = ImageDraw.Draw(img)
    draw.text((int(150 * s), int(130 * s)), label, font=font("Medium", int(76 * s)), fill=INK, anchor="lm")
    draw.text((int(150 * s), int(210 * s)), note, font=font("Regular", int(36 * s)), fill=MUTED, anchor="lm")
    if anchors:
        names = {key: label for key, label, _ in PATH}
        for key, (x, y, side) in anchors.items():
            px, py = x * img.width, y * img.height
            ty = py + side * 420 * s
            draw.line([(px, py), (px, ty)], fill=MUTED, width=max(1, int(2 * s)))
            haloed(img, (px, ty + side * 16 * s), names[key], font("Regular", int(44 * s)),
                   "ma" if side > 0 else "md", int(10 * s))
    # 100 µm at the depth of the camera target; nearer parts look slightly larger.
    bar = img.width * view["lens"] / (36 * view["distance"]) * 100
    x0, y0 = int(150 * s), img.height - int(150 * s)
    draw.line([(x0, y0), (x0 + bar, y0)], fill=INK, width=max(2, int(5 * s)))
    draw.text((x0 + bar / 2, y0 + 22 * s), "100 µm", font=font("Regular", int(34 * s)), fill=INK, anchor="mt")
    out.parent.mkdir(parents=True, exist_ok=True)
    if clock is not None:
        draw.text((img.width - int(150 * s), y0), clock, font=font("Regular", int(44 * s)), fill=INK, anchor="rm")
        stamp(img, meta).save(out, compress_level=1)
        return
    key = colour_key(meta, int(1500 * s), 1.5 * s)
    img.paste(key, (img.width - key.width - int(80 * s), img.height - key.height - int(40 * s)))
    stamp(img, meta).save(out, optimize=True)


def feathered(panel, edge: int):
    """Fade a panel's border into the page so bloom never ends in a hard line."""
    from PIL import Image, ImageDraw, ImageFilter
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rectangle([edge, edge, panel.width - edge, panel.height - edge], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(edge / 2))


def compose_grid(panels: list[tuple[Path, str]], meta: dict, out: Path):
    from PIL import Image, ImageDraw
    first = Image.open(panels[0][0])
    w, h = first.size
    cols, gap, label_h = 3, 24, 96
    rows = math.ceil(len(panels) / cols)
    key = colour_key(meta, 2000, 1.6)
    canvas = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * (h + label_h) + gap + key.height + 60), PAPER)
    draw = ImageDraw.Draw(canvas)
    for i, (path, label) in enumerate(panels):
        x, y = gap + (i % cols) * (w + gap), gap + (i // cols) * (h + label_h)
        panel = Image.open(path).convert("RGB")
        canvas.paste(panel, (x, y), feathered(panel, 40))
        draw.text((x + w / 2, y + h + 18), label, font=font("Medium", 50), fill=INK, anchor="mt")
    canvas.paste(key, ((canvas.width - key.width) // 2, canvas.height - key.height - 40))
    out.parent.mkdir(parents=True, exist_ok=True)
    stamp(canvas, meta).save(out, optimize=True)


def compose_pair(left: Path, right: Path, labels: tuple[str, str], meta: dict, out: Path):
    from PIL import Image, ImageDraw
    a, b = Image.open(left).convert("RGB"), Image.open(right).convert("RGB")
    canvas = Image.new("RGB", (a.width + b.width, a.height), PAPER)
    canvas.paste(a, (0, 0))
    canvas.paste(b, (a.width, 0))
    draw = ImageDraw.Draw(canvas)
    s = canvas.width / 3840
    for i, label in enumerate(labels):
        draw.text((a.width * (i + 0.5), canvas.height - int(120 * s)), label, font=font("Medium", int(68 * s)),
                  fill=INK, anchor="mm")
    stamp(canvas, meta).save(out, compress_level=1)


def blender(script: str, job: dict, path: Path):
    path.write_text(json_text(job))
    subprocess.run([BLENDER, "-b", "--factory-startup", "-P", str(HERE / script), "--", str(path)], check=True)


MASTER_LIMIT = 95_000_000  # bytes; GitHub refuses files over 100 MiB


def encode(frames: Path, out: Path, name: str, crf: int, work: Path):
    """A 1080p60 copy and a 4K master of one frame sequence. A master too large
    for GitHub is encoded again two CRF steps coarser until it fits."""
    blender("encode.py", dict(frames=str(frames), fps=60, outputs=[
        dict(path=str(out / f"{name}-1080p60.mp4"), percent=50, crf=crf)]), work / f"encode-{name}.json")
    master = out / f"{name}-4k.mp4"
    while True:
        blender("encode.py", dict(frames=str(frames), fps=60, outputs=[
            dict(path=str(master), percent=100, crf=crf)]), work / f"encode-{name}.json")
        if master.stat().st_size <= MASTER_LIMIT:
            return
        crf += 2


def figures(args):
    table, meta = load_values(args.values)
    # Raw renders live under a folder named for the exact value table, look and
    # cameras, so frames from one table (say, synthetic) are never reused for another.
    look = {**LOOK, **(json.loads(args.look) if args.look else {})}
    digest = hashlib.sha256(args.values.read_bytes() + json_text([look, VIEWS]).encode()).hexdigest()[:16]
    out, work = args.out.resolve(), (args.work or cache() / "visuals/tour/work" / digest).resolve()
    if meta["kind"] == "synthetic" and (ROOT / "figures") in [out, *out.parents]:
        raise SystemExit("synthetic values never render into figures/")
    labels = dict(zip(meta["conditions"], meta["labels"]))
    compare = args.compare or most_changed(args.values)
    knockouts = ["control", *[c for c in KNOCKOUTS if c in labels]]
    tasks = [dict(kind="still", view="hero", dust=c, size=[3840, 2160], out=str(work / "hero" / f"{c}.png"))
             for c in meta["conditions"]]
    tasks += [dict(kind="still", view="hero", dust=c, size=[1600, 900], out=str(work / "grid" / f"{c}.png"))
              for c in knockouts]
    tasks.append(dict(kind="still", view="path", dust="control", path=args.path, size=[3840, 2160],
                      out=str(work / "path" / "still.png")))
    if args.clips:
        for c in ("control", compare):
            tasks.append(dict(kind="clip", view="spin", dust=c, size=[1920, 2160], fps=60, seconds=10,
                              out=str(work / "spin" / c)))
        if args.spikes is None:
            raise SystemExit("the path clip needs --spikes, the exact spike replay of --path")
        scene = np.load(cache() / SCENE)
        position = {int(b): i for i, b in enumerate(scene["body_ids"])}
        cells = np.array([position[int(b)] for b in scene["path_body"]])
        times = clock(8 * 60, 60)
        flashes = spike_flashes(args.spikes, args.path, cells, times)
        spikes = work / "path-clip" / f"{args.path}-{hashlib.sha256(flashes.tobytes()).hexdigest()[:12]}"
        spikes.mkdir(parents=True, exist_ok=True)
        np.save(spikes.with_suffix(".npy"), flashes)
        tasks.append(dict(kind="clip", view="path_move", dust="control", spikes=str(spikes.with_suffix(".npy")),
                          size=[3840, 2160], fps=60, seconds=8, out=str(spikes)))
    work.mkdir(parents=True, exist_ok=True)
    blender("scene.py", dict(scene=str(cache() / SCENE), values=str(args.values.resolve()), views=VIEWS,
                             tasks=tasks, look=json.loads(args.look) if args.look else {}), work / "job.json")
    for c in meta["conditions"]:
        compose_still(work / "hero" / f"{c}.png", labels[c], meta, out / "stills" / f"{slug(labels[c])}.png",
                      VIEWS["hero"], "Brain and nerve cord seen from above, head to the left")
    compose_grid([(work / "grid" / f"{c}.png", labels[c]) for c in knockouts], meta, out / "knockout-overview.png")
    anchors = json.loads((work / "path" / "still.json").read_text())["anchors"]
    compose_still(work / "path" / "still.png", labels[args.path], meta, out / "courtship-path.png",
                  VIEWS["path"], "Seen from the side, head to the right", anchors)
    if not args.clips:
        return
    pair = work / "pair" / compare
    pair.mkdir(parents=True, exist_ok=True)
    for frame in sorted((work / "spin" / "control").glob("*.png")):
        target = pair / frame.name
        if not target.exists():
            compose_pair(frame, work / "spin" / compare / frame.name, (labels["control"], labels[compare]), meta, target)
    name = f"normal-vs-{slug(labels[compare])}"
    encode(pair, out, name, args.crf, work)
    frames = work / "path-frames" / spikes.name
    for f, ms in enumerate(times):
        raw = spikes / f"{f:04d}.png"
        anchors = json.loads(raw.with_suffix(".json").read_text())["anchors"]
        compose_still(raw, labels[args.path], meta, frames / raw.name, VIEWS["path_move"],
                      "Each flash is one spike in one run of the model, slowed down. Seen from the side, head to the right",
                      anchors, clock_text(ms))
    encode(frames, out, "courtship-path", args.crf, work)


# ---------------------------------------------------------------- tipping point

# The GABA dose clip. Block levels in recorded order, as the fraction of GABA-class
# conductance removed; rest is the paired control, zero change by construction.
BLOCKS = [0.10, 0.25, 0.50, 0.75, 0.90, 1.00]
# Clip seconds: rest, then the brake released at a steady rate to full block, then a hold.
REST_S, RELEASE_S, CLIP_S = 0.5, 4.0, 6.5
# One CNS turning about its long axis: upright for a 4:5 phone feed, head-left for 16:9.
TIPPING_VIEWS = {
    # From above and in front, so the brain sits nearest the camera; head at the top.
    "portrait": dict(target=[0, -95, -300], direction=[0, 1, 0.6], up=[0, 0, 1], distance=1780, lens=50,
                     fstop=0.005, dolly=-0.08, spin=dict(axis=[0, 0, 1], start=-30, degrees=50), size=[2160, 2700]),
    # The same kind of view lying down, head to the left.
    "landscape": dict(target=[0, -95, -320], direction=[0.3, 1, 0.6], up=[-1, 0.3, 0], distance=2400, lens=50,
                      fstop=0.005, dolly=-0.08, spin=dict(axis=[0, 0, 1], start=-20, degrees=40), size=[3840, 2160]),
}
# Look changes for this clip on top of look.json, held for the whole clip like every
# look setting: only the block level and the camera change from frame to frame.
# A wider bloom lets the lit brain glow into the dark around it.
TIPPING_LOOK = dict(bloom=0.5, bloom_size=0.6)


def release(frames: int, fps: int) -> np.ndarray:
    """Block fraction on each frame."""
    return np.clip((np.arange(frames) / fps - REST_S) / RELEASE_S, 0.0, 1.0)


def tipping(args):
    """The GABA brake released through the recorded block levels, no text: a 4:5
    and a 16:9 clip, each as a 4K master and a 1080p60 copy."""
    bodies = np.load(cache() / SCENE)["body_ids"]
    conditions = [f"block-{b:.2f}" for b in BLOCKS]
    table = np.stack([np.zeros(len(bodies)), *per_neuron(np.load(args.outcomes), bodies, conditions)])
    # The tour's cap (its own rule gives 200 Hz here too), but linear, not the tour's
    # signed log: the brain's light then follows its total extra firing, and the
    # small early changes are not lifted towards the full-block brightness.
    cap = scale_cap(table)
    meta = dict(kind="model", unit="Hz", conditions=["control", *conditions], labels=["Rest", *conditions],
                cap=cap, knee=cap / 50, scale="linear", source=str(args.outcomes))
    frames = round(CLIP_S * 60)
    theta = release(frames, 60)
    digest = hashlib.sha256(table.astype(np.float32).tobytes() + json_text(
        [meta["scale"], cap, LOOK, TIPPING_LOOK, TIPPING_VIEWS, theta.tolist()]).encode()).hexdigest()[:16]
    work = cache() / "visuals/tour/tipping" / digest
    write_values(work / "values.npz", table, bodies, meta)
    levels = [[0.0, "control"], *[[b, c] for b, c in zip(BLOCKS, conditions)]]
    tasks = [dict(kind="release", view=name, levels=levels, theta=theta.tolist(), size=view["size"],
                  out=str(work / name)) for name, view in TIPPING_VIEWS.items()]
    blender("scene.py", dict(scene=str(cache() / SCENE), values=str(work / "values.npz"),
                             views=TIPPING_VIEWS, tasks=tasks, look=TIPPING_LOOK), work / "job.json")
    for name in TIPPING_VIEWS:
        encode(work / name, args.out.resolve(), name, args.crf, work)
    print(f"cap {cap:g} Hz, {frames} frames, full block from frame {int(np.argmax(theta >= 1))}")


# ---------------------------------------------------------------- viewer

def viewer(args):
    """One offline HTML page: pick a condition, turn the brain, same colour scale."""
    import fast_simplification
    table, meta = load_values(args.values)
    if meta["kind"] == "synthetic" and (ROOT / "figures") in [args.out.resolve(), *args.out.resolve().parents]:
        raise SystemExit("synthetic values never go into figures/")
    scene = np.load(cache() / SCENE)
    smeta = json.loads(bytes(scene["meta"]))
    quantum = 0.05  # µm per int16 step; covers ±1,638 µm
    blobs: list[bytes] = []
    size = 0

    def add(values: np.ndarray, kind: str) -> dict:
        nonlocal size
        raw = np.ascontiguousarray(values).tobytes()
        entry = dict(type=kind, offset=size, length=int(values.size))
        blobs.append(raw + b"\0" * (-len(raw) % 4))
        size += len(blobs[-1])
        return entry

    def coords(xyz):
        return add(np.round(np.asarray(xyz) / quantum).astype("<i2"), "i16")

    budgets = {"CentralBrain": 30000, "VNC": 16000, "CV": 3000}
    meshes = []
    for i, m in enumerate(smeta["meshes"]):
        if m["name"].startswith(("LA(", "Optic(")):
            continue
        outline = m["group"] == "shell" or m["name"].startswith(("ME(", "LO(", "LOP("))
        v, f = scene[f"mesh{i}_v"], scene[f"mesh{i}_f"]
        target = budgets.get(m["name"], 5000 if outline else 2000)
        if len(f) > target:
            v, f = fast_simplification.simplify(v, f, target_count=target)
        meshes.append(dict(outline=outline, v=coords(v), f=add(np.asarray(f, "<u4"), "u32")))
    keep = scene["dust_rank"] < args.points
    owner = scene["dust_neuron"][keep]
    n = len(scene["body_ids"])
    cap, knee = meta["cap"], meta["knee"]
    scaled = np.sign(table) * np.minimum(np.log1p(np.abs(table) / knee) / math.log1p(cap / knee), 1)
    position = {int(b): i for i, b in enumerate(scene["body_ids"])}
    path_neuron = np.array([position[int(b)] for b in scene["path_body"]])[scene["skel_cell"]]
    edges = scene["skel_e"]
    group = {"control": "control", **{c: "knockout" for c in KNOCKOUTS}, **{c: "courtship" for c in COURTSHIP}}
    head = dict(
        kind=meta["kind"], unit=meta["unit"], cap=cap, knee=knee, ticks=ticks(cap, knee), quantum=quantum,
        palette=PALETTE, look=LOOK, neurons=n,
        conditions=[dict(id=c, label=l, group=group[c]) for c, l in zip(meta["conditions"], meta["labels"])],
        meshes=meshes,
        dust=dict(pos=coords(scene["dust_points"][keep]), counts=add(np.bincount(owner, minlength=n).astype("u1"), "u8")),
        values=add(np.round(scaled * 127).astype("i1"), "i8"),
        path=dict(pos=coords(scene["skel_v"][edges].reshape(-1, 3)),
                  neuron=add(path_neuron[edges].reshape(-1).astype("<u4"), "u32")),
    )
    # Array offsets count from the first 4-byte boundary after the JSON header.
    text = json.dumps(head, separators=(",", ":")).encode()
    body = len(text).to_bytes(4, "little") + text + b"\0" * (-(4 + len(text)) % 4) + b"".join(blobs)
    assets = Assets(cache())
    libraries = {}
    for key, source in [("THREE", "build/three.module.min.js"), ("CONTROLS", "examples/jsm/controls/OrbitControls.js")]:
        path = assets.get(f"visuals/vendor/three-0.160.1/{Path(source).name}",
                          f"https://unpkg.com/three@0.160.1/{source}", "embedded offline renderer, MIT license")
        libraries[key] = base64.b64encode(path.read_bytes()).decode()
    html = (HERE / "viewer.html").read_text()
    for key, value in libraries.items():
        html = html.replace(f"__{key}__", value)
    html = html.replace("__PAYLOAD__", base64.b64encode(gzip.compress(body, mtime=0)).decode())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)
    print(f"{args.out}: {len(html.encode()) / 1e6:.1f} MB, {int(keep.sum()):,} dots")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="build the display scene once")
    p.add_argument("--populations", type=Path, default=atlas.POPULATIONS)
    p.add_argument("--points", type=int, default=POINTS_PER_NEURON)
    p.set_defaults(run=prepare)
    p = sub.add_parser("values", help="per-condition value table")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--outcomes", type=Path, help="per-neuron-delta-hz.npz from the circuit-tour analysis")
    source.add_argument("--synthetic", action="store_true", help="made-up stripes for development only")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(run=values)
    p = sub.add_parser("figures", help="render every still and clip, then label them")
    p.add_argument("--values", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--work", type=Path, help="raw renders and frames; default: the cache, per value table")
    p.add_argument("--compare", help="knockout for the side-by-side clip; default: largest mean change")
    p.add_argument("--path", default="P1-high", help="courtship condition for the path still and clip")
    p.add_argument("--spikes", type=Path, help="exact spike replay (-spikes.npz) of --path, for the path clip")
    p.add_argument("--no-clips", dest="clips", action="store_false")
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--look", help="JSON overrides of scene.LOOK, for look development")
    p.set_defaults(run=figures)
    p = sub.add_parser("tipping", help="the GABA dose clip: block levels in order, no text")
    p.add_argument("--outcomes", type=Path, required=True, help="per-neuron-delta-hz.npz from the dose analysis")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--crf", type=int, default=18)
    p.set_defaults(run=tipping)
    p = sub.add_parser("viewer", help="offline Three.js page with every condition")
    p.add_argument("--values", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--points", type=int, default=3, help="synapse sites per neuron in the browser")
    p.set_defaults(run=viewer)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
