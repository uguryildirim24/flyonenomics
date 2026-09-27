# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["playwright==1.58.0", "pillow==11.3.0"]
# ///
"""Make the cinematic clip, its poster and teaser, and the four-panel paper still for the primary 5b run.

    uv run --locked scripts/render_adhd_5b_demo.py --out figures/3d/experiment-5b \\
        --values .cache/malecns-v1.0/activity/5b-02/primary-seed-210/values.json

Every picture comes from the audited build: the atlas and cinematic pages must match build.json,
and the values file must be the one the atlas was built from. Before anything is written, the
film's glow and flashes are checked cell by cell against the recorded spike counts. The clip is
encoded in the browser (WebCodecs H.264) and packed into an MP4 here. Network blocked in browser.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import struct

from PIL import Image, ImageChops, ImageStat
from playwright.sync_api import sync_playwright

ORDER = ("wt-a", "fumin-a", "wt-b", "fumin-b")
STILL_BIN = 10               # 1.00-1.10 s after A + B began; the same bin as the atlas stills
FPS, WIDTH, HEIGHT = 30, 1280, 720
CODEC, BITRATE, KEY_EVERY = "avc1.640028", 850_000, 2 * FPS
POSTER = ("fumin-b", STILL_BIN, 0.3, (1920, 1080))    # condition, bin, seconds into the bin, size
TEASER = ("wt-a", 4, 12, 12, (960, 540), 70)           # condition, first bin, end bin, fps, size, WebP quality
PHASES = (0.02, 0.3, 0.6)    # seconds into each held bin; at 0.3 every spike's flash is live
BROWSER_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
MATRIX = struct.pack(">9I", 0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def decode(data_url: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGB")


def open_page(browser, url: str, viewport: tuple[int, int], scale: float, errors: list[str]):
    page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]}, device_scale_factor=scale)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("http://**/*", lambda route: route.abort())
    page.route("https://**/*", lambda route: route.abort())
    if url:
        page.goto(url, wait_until="load")
        page.wait_for_function("window.atlasReady === true", timeout=300_000)
    return page


def box(kind: bytes, *parts: bytes) -> bytes:
    body = b"".join(parts)
    return struct.pack(">I", 8 + len(body)) + kind + body


def full(kind: bytes, version: int, flags: int, *parts: bytes) -> bytes:
    return box(kind, struct.pack(">I", version << 24 | flags), *parts)


def mp4(description: bytes, samples: list[bytes], keys: list[int], fps: int, width: int, height: int) -> bytes:
    """A progressive MP4 (moov before mdat) holding one H.264 track, one sample per chunk."""
    scale, delta = fps * 1000, 1000
    ms = round(len(samples) * 1000 / fps)
    ftyp = box(b"ftyp", b"isom", struct.pack(">I", 0x200), b"isomiso2avc1mp41")

    def moov(offsets: list[int]) -> bytes:
        avc1 = box(b"avc1", bytes(6), struct.pack(">H", 1), bytes(16),
                   struct.pack(">HHII", width, height, 0x480000, 0x480000), bytes(4), struct.pack(">H", 1),
                   bytes(32), struct.pack(">Hh", 0x18, -1), box(b"avcC", description))
        stbl = box(b"stbl", full(b"stsd", 0, 0, struct.pack(">I", 1), avc1),
                   full(b"stts", 0, 0, struct.pack(">III", 1, len(samples), delta)),
                   full(b"stss", 0, 0, struct.pack(f">I{len(keys)}I", len(keys), *[k + 1 for k in keys])),
                   full(b"stsc", 0, 0, struct.pack(">IIII", 1, 1, 1, 1)),
                   full(b"stsz", 0, 0, struct.pack(f">II{len(samples)}I", 0, len(samples), *map(len, samples))),
                   full(b"stco", 0, 0, struct.pack(f">I{len(offsets)}I", len(offsets), *offsets)))
        minf = box(b"minf", full(b"vmhd", 0, 1, bytes(8)),
                   box(b"dinf", full(b"dref", 0, 0, struct.pack(">I", 1), full(b"url ", 0, 1))), stbl)
        mdia = box(b"mdia", full(b"mdhd", 0, 0, struct.pack(">IIIIHH", 0, 0, scale, len(samples) * delta, 0x55C4, 0)),
                   full(b"hdlr", 0, 0, bytes(4), b"vide", bytes(12), b"VideoHandler\0"), minf)
        tkhd = full(b"tkhd", 0, 3, struct.pack(">IIIII", 0, 0, 1, 0, ms), bytes(8), bytes(8), MATRIX,
                    struct.pack(">II", width << 16, height << 16))
        mvhd = full(b"mvhd", 0, 0, struct.pack(">IIIIIH", 0, 0, 1000, ms, 0x10000, 0x100), bytes(10), MATRIX,
                    bytes(24), struct.pack(">I", 2))
        return box(b"moov", mvhd, box(b"trak", tkhd, mdia))

    start = len(ftyp) + len(moov([0] * len(samples))) + 8
    offsets, at = [], start
    for sample in samples:
        offsets.append(at)
        at += len(sample)
    return ftyp + moov(offsets) + box(b"mdat", *samples)


def check_film(page, values: dict, film: dict) -> dict:
    """Every cell at every probed instant: anatomy-only cells stay dim with no flash; a recorded cell
    glows linearly in its own recorded spike count for that bin and flashes once per spike."""
    width = values["bin_edges_s"][1] - values["bin_edges_s"][0]
    column = {body: k for k, body in enumerate(values["body_ids"])}
    rows = {c["id"]: c["values"] for c in values["conditions"]}
    top = round(max(v for c in values["conditions"] for row in c["values"] for v in row) * width)
    if top != film["max_spikes_per_bin"]:
        raise ValueError(f"Film scale {film['max_spikes_per_bin']} spikes, values say {top}")
    cells = page.evaluate("window.filmCells()")
    recorded = sum(c["body_id"] in column for c in cells)
    if recorded != len(column) or recorded != film["recorded_cells"]:
        raise ValueError("Film cells do not match the recorded cells")
    silent, gain, dim, hold = film["glow_silent"], film["glow_gain"], film["dim_anatomy_only"], film["hold_s_per_bin"]
    probes = 0
    for segment in film["segments"]:
        if segment["kind"] != "arm":
            probe = page.evaluate("t => window.filmProbe(t)", (segment["start_s"] + segment["end_s"]) / 2)
            if any(probe["flashes"]) or probe["arm"] is not None:
                raise ValueError(f"Flashes outside a recorded run at {segment}")
            probes += 1
            continue
        for b in range(film["bins"]):
            for phase in PHASES:
                probe = page.evaluate("t => window.filmProbe(t)", segment["start_s"] + b * hold + phase)
                if probe["arm"] != segment["condition"] or probe["bin"] != b:
                    raise ValueError(f"Film shows {probe['arm']} bin {probe['bin']}, expected {segment['condition']} bin {b}")
                for cell, glow, flashes in zip(cells, probe["glow"], probe["flashes"]):
                    k = column.get(cell["body_id"])
                    if k is None:
                        ok = glow == dim and flashes == 0
                    else:
                        n = round(rows[segment["condition"]][b][k] * width)
                        ok = abs(glow - (silent + gain * n / top)) < 1e-5 and (flashes == n if phase == 0.3 else flashes <= n)
                    if not ok:
                        raise ValueError(f"Cell {cell['body_id']} in {segment['condition']} bin {b}: glow {glow}, {flashes} flashes")
                probes += 1
    return dict(probes=probes, cells_per_probe=len(cells), recorded_cells=recorded, anatomy_only_cells=len(cells) - recorded,
                rule=("anatomy-only cells: dim value and no flash; recorded cells: glow = silent + gain * spikes / "
                      f"{top}, and {PHASES[1]} s into each held bin exactly one live flash per recorded spike; "
                      "no flash outside the four runs"))


def arm_time(film: dict, condition: str, bin_: int, phase: float) -> float:
    segment = next(s for s in film["segments"] if s["kind"] == "arm" and s["condition"] == condition)
    return segment["start_s"] + bin_ * film["hold_s_per_bin"] + phase


def encode(page, film: dict) -> tuple[bytes, dict]:
    frames = round(film["duration_s"] * FPS)
    config = page.evaluate("c => window.filmEncodeStart(c)",
                           dict(width=WIDTH, height=HEIGHT, fps=FPS, bitrate=BITRATE, codec=CODEC))
    for start in range(0, frames, 150):
        page.evaluate("a => window.filmEncodeFrames(...a)", [start, min(start + 150, frames), FPS, KEY_EVERY])
        print(f"  encoded {min(start + 150, frames)}/{frames} frames", flush=True)
    result = page.evaluate("window.filmEncodeFinish()")
    data = base64.b64decode(result["data"])
    samples, at = [], 0
    for chunk in result["chunks"]:
        samples.append(data[at:at + chunk["size"]])
        at += chunk["size"]
    stamps = [c["ts"] for c in result["chunks"]]
    if at != len(data) or stamps != [round(i * 1e6 / FPS) for i in range(frames)]:
        raise ValueError("Encoder returned missing, extra or reordered frames")
    # The encoder may add key frames of its own (at cuts); it must not drop a requested one.
    keys = [i for i, c in enumerate(result["chunks"]) if c["key"]]
    if not set(range(0, frames, KEY_EVERY)) <= set(keys):
        raise ValueError("Encoder dropped a requested key frame")
    clip = mp4(base64.b64decode(result["description"]), samples, keys, FPS, WIDTH, HEIGHT)
    return clip, dict(frames=frames, fps=FPS, width=WIDTH, height=HEIGHT, duration_s=round(frames / FPS, 3),
                      codec=config["codec"], bitrate_target_bps=BITRATE, key_frame_every_s=KEY_EVERY / FPS,
                      key_frames=len(keys),
                      encoder="browser WebCodecs VideoEncoder; MP4 packed by this script")


def check_clip(browser, clip: bytes, page, frames: int, errors: list[str]) -> dict:
    """Play the MP4 in the browser and compare decoded frames with fresh renders."""
    viewer = open_page(browser, "", (WIDTH, HEIGHT), 1, errors)
    viewer.set_content("<video muted></video>")
    # A same-origin blob, so decoded frames can be read back (a file:// video taints the canvas).
    meta = viewer.evaluate("""async b64 => {const v = document.querySelector('video');
        v.src = URL.createObjectURL(new Blob([Uint8Array.from(atob(b64), c => c.charCodeAt(0))], {type: 'video/mp4'}));
        await new Promise((ok, fail) => { v.onloadeddata = ok; v.onerror = () => fail(new Error('MP4 does not decode')); });
        return {duration: v.duration, width: v.videoWidth, height: v.videoHeight}; }""", base64.b64encode(clip).decode())
    if abs(meta["duration"] - frames / FPS) > 1 / FPS or (meta["width"], meta["height"]) != (WIDTH, HEIGHT):
        raise ValueError(f"MP4 does not play as written: {meta}")
    diffs = {}
    for index in (round(frames * .3), round(frames * .6), round(frames * .9)):
        shown = decode(viewer.evaluate("""async t => {const v = document.querySelector('video'); v.pause();
            await new Promise(r => { v.onseeked = r; v.currentTime = t; });
            const c = document.createElement('canvas'); c.width = v.videoWidth; c.height = v.videoHeight;
            c.getContext('2d').drawImage(v, 0, 0); return c.toDataURL('image/png'); }""", (index + .5) / FPS))
        render = decode(page.evaluate("t => window.filmSnapshot(t)", index / FPS))
        diffs[f"{index / FPS:.2f}"] = round(sum(ImageStat.Stat(ImageChops.difference(shown, render)).mean) / 3, 2)
    viewer.close()
    if max(diffs.values()) > 8:
        raise ValueError(f"Decoded MP4 frames differ from the renders: {diffs}")
    return dict(duration_s=round(meta["duration"], 3), mean_abs_difference_vs_render=diffs)


def panels(browser, atlas: Path, template: str, errors: list[str]) -> tuple[bytes, dict]:
    page = open_page(browser, atlas.as_uri() + "#figure", (1600, 1000), 2, errors)
    evidence = page.evaluate("window.atlasEvidence")
    show = evidence["display"]
    grey = page.locator("#grey-key").text_content()
    # The panels get their own scale bar and orientation note at a size that survives the layout.
    page.add_style_tag(content="#viewport > :not(#main-canvas) {visibility: hidden}")
    items = []
    for letter, condition in zip("abcd", ORDER):
        state = page.evaluate("s => window.atlasSet(s)", dict(condition=condition, frame=STILL_BIN, value_mode=True))
        if (state["condition"] != condition or state["frame"] != STILL_BIN or not state["value_mode"]
                or state["anatomy_only_opacities"] != [show["anatomy_only"]["opacity"]]):
            raise ValueError(f"Invalid atlas state: {state}")
        canvas = page.locator("#main-canvas")
        width = canvas.evaluate("c => c.clientWidth")
        text = show["conditions"][condition]
        items.append(dict(letter=letter, condition=condition, title=text["title"], detail=text["detail"],
                          colour=text["colour"], when=state["when"], aggregate=f"{state['aggregate']:g}",
                          scale_fraction=state["scale_px_per_100um"] / width if letter == "a" else None,
                          src="data:image/png;base64," + base64.b64encode(canvas.screenshot(timeout=120_000)).decode()))
    page.close()
    scale = show["scale"]
    first = {c: show["conditions"][c] for c in ORDER}
    columns = [dict(title=first[c]["title"], detail=first[c]["science"], colour=first[c]["colour"]) for c in ORDER[:2]]
    rows = [dict(zip(("title", "detail"), first[c]["detail"].split(", ", 1))) for c in ORDER[::2]]
    data = dict(kicker=show["kicker"], title=show["title"],
                subtitle=f"Recorded model activity {items[0]['when']}. {show['fly']}",
                honest=show["honest"], columns=columns, rows=rows, panels=items,
                levels=evidence["colour_levels"], scale=dict(scale, level_labels=[f"{v:g}" for v in scale["levels"]]),
                recorded="Coloured: ring neurons (centre) and TuBu neurons (both sides), each cell's recorded "
                         "spikes in this 100\u00a0ms bin.",
                grey=dict(color=show["anatomy_only"]["color"], text=grey),
                aggregate_label="central-complex dopamine neurons, whole-group total",
                aggregate_text=("Below each panel: the central-complex dopamine neurons' group total, recorded as "
                                "one number. It is not spread over the grey cells."),
                attribution=show["figure_attribution"], orient="Front view of the central brain; the fly's left is on the right.")
    page = open_page(browser, "", (1800, 1000), 2, errors)
    page.set_content(template.replace("__DATA__", json.dumps(data)), wait_until="load")
    page.wait_for_function("window.panelsReady !== undefined")
    page.evaluate("window.panelsReady")
    png = page.locator("#figure").screenshot()
    page.close()
    return png, dict(bin=STILL_BIN, when=items[0]["when"], conditions=list(ORDER), letters="abcd",
                     cx_total_spikes_per_s={i["condition"]: float(i["aggregate"]) for i in items})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True, help="Primary 5b atlas folder with build.json")
    parser.add_argument("--values", type=Path, required=True, help="Display values the atlas was built from")
    args = parser.parse_args()
    out = args.out.resolve()
    receipt = out / "build.json"
    atlas, manifest, cinematic = out / "male-cns-atlas.html", out / "manifest.json", out / "cinematic" / "male-cns-cinematic.html"
    build = json.loads(receipt.read_text())
    for path in (atlas, manifest, cinematic):
        recorded = build["outputs"].get(path.relative_to(out).as_posix())
        if not recorded or path.stat().st_size != recorded["bytes"] or digest(path) != recorded["sha256"]:
            raise ValueError(f"Atlas build receipt does not match {path.relative_to(out)}")
    if build["inputs_sha256"]["activity_manifest"] != digest(manifest):
        raise ValueError("Atlas was built from a different extraction manifest")
    if build["inputs_sha256"]["playback_values"] != digest(args.values):
        raise ValueError("Values file is not the one the atlas was built from")
    values = json.loads(args.values.read_text())
    template = (Path(__file__).parent / "malecns_3d" / "panels.html").read_text()
    written: dict[str, bytes] = {}
    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, args=BROWSER_ARGS)
        figure, four = panels(browser, atlas, template, errors)
        written["primary-four-panel.png"] = figure
        film_page = open_page(browser, cinematic.as_uri() + "#film", (WIDTH, HEIGHT), 1, errors)
        film = film_page.evaluate("window.filmEvidence")
        honesty = check_film(film_page, values, film)
        print(f"Film matches the recorded spikes at {honesty['probes']} instants", flush=True)
        condition, bin_, phase, size = POSTER
        poster_t = arm_time(film, condition, bin_, phase)
        film_page.evaluate("s => window.filmSetSize(...s)", list(size))
        poster = decode(film_page.evaluate("t => window.filmSnapshot(t)", poster_t))
        buffer = BytesIO()
        poster.save(buffer, "PNG", optimize=True)
        written["cinematic/primary-poster.png"] = buffer.getvalue()
        # A short looping teaser for the README. Animated WebP keeps the glow colours that a
        # 256-colour GIF palette bands away, at a fifth of the size.
        condition, first, last, fps, size, quality = TEASER
        film_page.evaluate("s => window.filmSetSize(...s)", list(size))
        start, end = arm_time(film, condition, first, 0), arm_time(film, condition, last, 0)
        count = round((end - start) * fps)
        frames = [decode(film_page.evaluate("t => window.filmSnapshot(t)", start + i / fps)) for i in range(count)]
        buffer = BytesIO()
        frames[0].save(buffer, "WEBP", save_all=True, append_images=frames[1:], duration=round(1000 / fps), loop=0,
                       quality=quality, method=6)
        written["cinematic/primary-teaser.webp"] = buffer.getvalue()
        teaser = dict(condition=condition, from_s=round(start, 3), to_s=round(end, 3), fps=fps, frames=count,
                      width=size[0], height=size[1], bins=[first, last], webp_quality=quality)
        print("Encoding the clip in the browser", flush=True)
        clip, clip_info = encode(film_page, film)
        written["cinematic/primary-demo.mp4"] = clip
        film_page.evaluate("s => window.filmSetSize(...s)", [WIDTH, HEIGHT])
        played = check_clip(browser, clip, film_page, clip_info["frames"], errors)
        browser_version = browser.version
        browser.close()
    if errors:
        raise RuntimeError(errors)
    for name, blob in written.items():
        (out / name).write_bytes(blob)
    build["inputs_sha256"]["scripts/render_adhd_5b_demo.py"] = digest(Path(__file__))
    build["inputs_sha256"]["scripts/render_adhd_5b_demo.py.lock"] = digest(Path(__file__).with_suffix(".py.lock"))
    build["inputs_sha256"]["scripts/malecns_3d/panels.html"] = digest(Path(__file__).parent / "malecns_3d" / "panels.html")
    for name in ("primary-four-panel.png", "cinematic/primary-demo.mp4", "cinematic/primary-poster.png",
                 "cinematic/primary-teaser.webp"):
        path = out / name
        if path.stat().st_size >= 50_000_000:
            raise ValueError(f"Output exceeds GitHub 50 MB limit: {path}")
        build["outputs"][name] = dict(bytes=path.stat().st_size, sha256=digest(path))
    build["demo"] = dict(
        clip=dict(clip_info, played_back=played), segments=film["segments"], hold_s_per_bin=film["hold_s_per_bin"],
        flash_s=film["flash_s"], glow_rule=film["glow_rule"], glow_silent=film["glow_silent"],
        glow_gain=film["glow_gain"], dim_anatomy_only=film["dim_anatomy_only"], captions=film["captions"],
        honesty_check=honesty, poster=dict(condition=POSTER[0], bin=POSTER[1], time_s=round(poster_t, 3),
                                           width=POSTER[3][0], height=POSTER[3][1]),
        teaser=teaser, four_panel=four, browser=browser_version, renderer=film["renderer"])
    receipt.write_text(json.dumps(build, indent=2) + "\n")
    print(f"Wrote the {clip_info['duration_s']} s clip, poster, teaser and four-panel still in {out}")


if __name__ == "__main__":
    main()
