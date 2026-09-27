# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "numpy==2.5.3", "pandas==3.0.5", "pyarrow==25.0.1",
#   "pydantic==2.12.4", "pyyaml==6.0.3", "scipy==1.16.2",
#   "fast-simplification==0.1.13", "playwright==1.58.0",
# ]
# ///
"""Build the offline MaleCNS atlas and its PNG; never imports/runs the engine.

    uv run --locked scripts/render_malecns_3d.py

See docs/3d-model.md. Downloaded assets live in the main checkout's cache.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import urllib.parse
import urllib.request

import fast_simplification
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from flyonenomics.io import hash_file, read_bytes, read_feather, read_json, read_text  # noqa: E402
from flyonenomics.registry.populations import load_population_table, resolve_population  # noqa: E402
from malecns_3d.activity import extract_primary_5b, extract_study, load_values  # noqa: E402
from malecns_3d.display import PAPER_ANATOMY, display_block  # noqa: E402

BASE = "https://storage.googleapis.com/flyem-male-cns/"
SKELETONS = "v1.0/segmentation/skeletons-malecns/skeletons-precomputed/"
MANIFEST = ROOT / "data/malecns-v1.0-manifest.json"
POPULATIONS = ROOT / "data/populations-male-cns-v1.0.yaml"
TEMPLATE = ROOT / "scripts/malecns_3d/viewer.html"
CINEMATIC = ROOT / "scripts/malecns_3d/cinematic.html"
ANATOMY_PAPER = ROOT / "scripts/malecns_3d/anatomy-paper.html"
DISPLAY = ROOT / "scripts/malecns_3d/display.py"
LIMIT = 20_000_000_000
FILE_LIMIT = 20_000_000
CIRCUIT_GROUPS = [
    ("P1", "P1 courtship neurons", "#D45C54", ["P1"]),
    ("pIP10", "Descending song command", "#E89B47", ["pIP10"]),
    ("song", "Song pattern neurons", "#E0BF54", ["dPR1", "vPR6", "TN1a", "TN1c"]),
    ("wing", "Wing motor neurons", "#76BC85", ["wing_motor"]),
]
# Okabe-Ito colours, colour-blind safe; both dopamine groups share the warm family.
GROUPS = [
    ("CX_DAN", "Central-complex dopamine neurons", "#CC79A7", ["CX_DAN"]),
    ("ER", "Ring neurons (ellipsoid body)", "#009E73", ["ER"]),
    ("TuBu", "Tubercle-to-bulb (TuBu) neurons", "#E69F00", ["TuBu"]),
    ("MB_DAN", "Mushroom-body dopamine neurons", "#D55E00", ["PAM", "PPL1"]),
    ("KC", "Kenyon cells", "#0072B2", ["KC"]),
]
# Three.js 0.160.1 postprocessing modules for the cinematic page's bloom, vendored byte for byte
# from https://unpkg.com/three@0.160.1/examples/jsm/ (MIT; the licence is beside them).
VENDOR = ROOT / "scripts/malecns_3d/vendor/three-0.160.1"
BLOOM_MODULES = ["postprocessing/EffectComposer.js", "postprocessing/RenderPass.js",
                 "postprocessing/UnrealBloomPass.js", "postprocessing/OutputPass.js",
                 "postprocessing/ShaderPass.js", "postprocessing/MaskPass.js", "postprocessing/Pass.js",
                 "shaders/CopyShader.js", "shaders/LuminosityHighPassShader.js", "shaders/OutputShader.js"]


def json_text(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def main_cache() -> Path:
    override = os.environ.get("FLYONENOMICS_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve() / "malecns-v1.0"
    common = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True
    ).strip()
    return Path(common).parent / ".cache/malecns-v1.0"


class Assets:
    """Bounded, sequential, checksummed downloads; no whole-neuron mesh fetches."""

    def __init__(self, cache: Path):
        self.cache = cache
        self.manifest = read_json(MANIFEST)
        self.flat_names = {r["name"] for r in self.manifest["files"]}
        self.records = {r["name"]: r for r in self.manifest["files"] + self.manifest.get("visual_files", [])}
        self.used: set[str] = set()
        self.downloaded = 0

    def save(self) -> None:
        self.manifest["visual_files"] = [self.records[k] for k in sorted(self.records) if k not in self.flat_names]
        self.manifest["visual_size_method"] = (
            "Full-collection totals above are the 2026-09-22 public GCS inventory, not downloads. "
            "visual_files records the individually fetched ROI meshes, body-id skeletons, metadata "
            "and embedded viewer dependencies; paths are relative to .cache/malecns-v1.0/."
        )
        MANIFEST.write_text(json.dumps(self.manifest, indent=2) + "\n")

    def get(self, name: str, url: str, used_for: str) -> Path:
        path = self.cache / name
        record = self.records.get(name)
        self.used.add(name)
        if record:
            if record["url"] != url:
                raise ValueError(f"Source URL changed: {name}")
            if path.exists():
                if path.stat().st_size != record["bytes"] or hash_file(path) != record["sha256"]:
                    raise ValueError(f"Cache checksum mismatch: {path}")
                return path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Only a complete, verified response becomes an asset. The temporary file
        # is removed even after network failure, and each successful fetch is recorded.
        temporary = path.with_suffix(path.suffix + ".part")
        try:
            with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as out:
                length = int(response.headers.get("Content-Length", 0))
                if self.downloaded + length > LIMIT:
                    raise ValueError("20 GB visual-download budget exceeded")
                while chunk := response.read(1 << 20):
                    self.downloaded += len(chunk)
                    if self.downloaded > LIMIT:
                        raise ValueError("20 GB visual-download budget exceeded")
                    out.write(chunk)
            size, digest = temporary.stat().st_size, hash_file(temporary)
            if record and (size != record["bytes"] or digest != record["sha256"]):
                raise ValueError(f"Downloaded asset differs from pinned manifest: {name}")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        self.records[name] = dict(name=name, url=url, bytes=size, sha256=digest, used_for=used_for)
        self.save()
        return path

    def gcs(self, name: str, source: str, purpose: str) -> Path:
        return self.get(name, BASE + urllib.parse.quote(source, safe="/"), purpose)


def packed(array: np.ndarray, dtype: str) -> str:
    return base64.b64encode(np.asarray(array, dtype=dtype).tobytes()).decode()


def display_coordinates(vertices: np.ndarray) -> np.ndarray:
    """Native nm → µm; x unchanged, y/z negated (a rotation, NOT a mirror)."""
    return (vertices.astype(np.float64) / 1000 - [384, 200, 230]) * [1, -1, -1]


def mesh_asset(assets: Assets, folder: str, prefix: str, name: str,
               group: str, color: str, opacity: float, faces: int) -> dict:
    path = assets.gcs(f"visuals/meshes/{folder}/{name}.ngmesh", f"{prefix}/mesh/{name}.ngmesh",
                      f"native-space published ROI mesh: {name}; display only")
    raw = read_bytes(path)
    count = struct.unpack_from("<I", raw)[0]
    vertices = np.frombuffer(raw, "<f4", count * 3, 4).reshape(-1, 3)
    triangles = np.frombuffer(raw, "<u4", offset=4 + count * 12).reshape(-1, 3)
    original_faces = len(triangles)
    vertices = display_coordinates(vertices)
    if len(triangles) > faces:
        vertices, triangles = fast_simplification.simplify(vertices, triangles, target_count=faces)
    return dict(name=name, group=group, color=color, opacity=opacity,
                vertices=packed(np.round(vertices, 2), "<f4"), faces=packed(triangles, "<u4"),
                source_faces=original_faces, display_faces=len(triangles))


def meshes(assets: Assets) -> list[dict]:
    result = []
    major = "rois/malecns-major-compartments-v2"
    brain = "rois/fullbrain-roi-v4"
    vnc = "rois/malecns-vnc-neuropil-roi-v0"
    for prefix in (major, brain, vnc):
        assets.gcs(f"visuals/metadata/{prefix.split('/')[-1]}.json", prefix + "/info", "ROI source coordinate metadata")
        assets.gcs(f"visuals/metadata/{prefix.split('/')[-1]}-labels.json", prefix + "/segment_properties/info", "published ROI names and label IDs")
    for name, budget in [("CentralBrain", 18000), ("Optic(L)", 12000), ("Optic(R)", 12000), ("VNC", 16000), ("CV", 3000)]:
        result.append(mesh_asset(assets, "major", major, name, "shell", "#8BA2B6", .085, budget))
    for name in ("EB", "FB", "PB", "NO"):
        result.append(mesh_asset(assets, "neuropils", brain, name, "cx", "#CC8793", .16, 3500))
    for part in ("aL", "bL", "gL", "a'L", "b'L", "CA", "PED"):
        for side in ("L", "R"):
            result.append(mesh_asset(assets, "neuropils", brain, f"{part}({side})", "mb", "#9489BD", .10, 2000))
    for part in ("LA", "ME", "LO", "LOP"):
        for side in ("L", "R"):
            result.append(mesh_asset(assets, "neuropils", brain, f"{part}({side})", "optic", "#82A7B7", .09, 4500))
    for part in ("BU", "AOTU"):
        for side in ("L", "R"):
            result.append(mesh_asset(assets, "neuropils", brain, f"{part}({side})", "visual", "#D5B576", .17, 2000))
    for name in [f"LegNp(T{t})({s})" for t in (1, 2, 3) for s in ("L", "R")] + ["ANm", "LTct", "IntTct"]:
        result.append(mesh_asset(assets, "vnc", vnc, name, "vnc", "#91AAA0", .13, 4000))
    return result


def selected_cells(assets: Assets) -> tuple[list[dict], list[dict]]:
    # Resolve the project's actual selectors, without triggering the adapter's
    # connectivity build or reading the ~24 GB synapse/edge tables.
    name = "body-annotations-male-cns-v1.0-minconf-0.5.feather"
    record = next(r for r in assets.manifest["files"] if r["name"] == name)
    path = assets.get(name, record["url"], record["used_for"])
    source = read_feather(path).to_pandas()
    source = source.loc[(source.status == "Traced") & source.type.notna()]
    annotations = pd.DataFrame({
        "root_id": source.bodyId, "hemibrain_type": source.type,
        "cell_class": source["class"],
        "cell_sub_class": source["subclass"],
        "side": source.somaSide.fillna(source.rootSide).map({"L": "left", "R": "right"}),
    })
    order = annotations.root_id.to_numpy(dtype=np.int64)
    _, entries = load_population_table(POPULATIONS)
    entries = {e.name: e for e in entries}
    lookup = annotations.set_index("root_id")
    cells, groups = [], []
    for key, label, color, names in GROUPS:
        ids = sorted({int(r) for name in names for r in resolve_population(entries[name], annotations, order).root_ids})
        total = len(ids)
        if key in ("P1", "wing"):
            ids = sorted(ids, key=lambda r: hashlib.sha256(f"circuit-tour-display:{r}".encode()).digest())[:20]
        if key == "KC":
            # Eight per released type × side stratum, or all if smaller. Stable,
            # outcome-independent hash ordering; not an abundance estimate.
            picked = []
            for _, frame in lookup.loc[ids].groupby(["hemibrain_type", "side"], dropna=False, sort=True):
                picked.extend(sorted(frame.index, key=lambda r: hashlib.sha256(f"male-cns-3d-v1:{r}".encode()).digest())[:8])
            ids = sorted(map(int, picked))
        groups.append(dict(id=key, label=label, color=color, selectors=names, total=total, shown=len(ids)))
        for body in ids:
            row = lookup.loc[body]
            cells.append(dict(body_id=str(body), group=key, type=str(row.hemibrain_type), side=str(row.side)))
    return cells, groups


def simplify_skeleton(vertices: np.ndarray, edges: np.ndarray, tolerance: float = 1.0) -> np.ndarray:
    """RDP each maximal degree-two path; preserve all tips and branch points.

    Output is independent line segments (E, 2, 3), in µm. No twig pruning.
    The released centerlines have undirected edges, not SWC parent ordering.
    """
    adjacent: list[list[int]] = [[] for _ in vertices]
    for a, b in edges:
        adjacent[a].append(int(b))
        adjacent[b].append(int(a))
    visited = set()
    segments = []
    starts = [i for i, neighbors in enumerate(adjacent) if len(neighbors) != 2]
    # The final range also covers an isolated degree-two cycle, should one exist.
    for start in starts + list(range(len(vertices))):
        for nxt in adjacent[start]:
            if (min(start, nxt), max(start, nxt)) in visited:
                continue
            path = [start]
            prev, current = start, nxt
            while True:
                visited.add((min(prev, current), max(prev, current)))
                path.append(current)
                if len(adjacent[current]) != 2 or current == start:
                    break
                following = next(n for n in adjacent[current] if n != prev)
                prev, current = current, following
            points = vertices[path]
            keep = {0, len(points) - 1}
            stack = [(0, len(points) - 1)]
            while stack:
                lo, hi = stack.pop()
                if hi - lo <= 1:
                    continue
                delta = points[hi] - points[lo]
                norm = float(delta @ delta)
                t = np.clip((points[lo + 1:hi] - points[lo]) @ delta / norm, 0, 1) if norm else np.zeros(hi - lo - 1)
                distances = np.linalg.norm(points[lo + 1:hi] - (points[lo] + t[:, None] * delta), axis=1)
                farthest = int(np.argmax(distances)) + lo + 1
                if distances[farthest - lo - 1] > tolerance:
                    keep.add(farthest)
                    stack.extend([(lo, farthest), (farthest, hi)])
            reduced = points[sorted(keep)]
            segments.extend(zip(reduced[:-1], reduced[1:]))
    if len(visited) != len(edges):
        raise ValueError("Skeleton contains duplicate edges or unvisited topology")
    return np.asarray(segments, dtype=np.float32).reshape(-1, 2, 3)


def neurons(assets: Assets, cells: list[dict]) -> list[dict]:
    assets.gcs("visuals/metadata/skeletons-precomputed.json", SKELETONS + "info", "native nm centerline format")
    result = []
    for i, cell in enumerate(cells):
        body = cell["body_id"]
        path = assets.gcs(f"visuals/skeletons/{body}", SKELETONS + body, f"body {body}, {cell['group']}; native nm centerline")
        raw = read_bytes(path)
        nv, ne = struct.unpack_from("<II", raw)
        if len(raw) != 8 + 12 * nv + 8 * ne:
            raise ValueError(f"Unexpected skeleton format for {body}")
        vertices = display_coordinates(np.frombuffer(raw, "<f4", nv * 3, 8).reshape(-1, 3))
        edges = np.frombuffer(raw, "<u4", ne * 2, 8 + nv * 12).reshape(-1, 2)
        if nv == 0 or ne == 0 or edges.max() >= nv or not np.isfinite(vertices).all():
            raise ValueError(f"Invalid skeleton for {body}")
        segments = simplify_skeleton(vertices, edges)
        result.append(dict(**cell, points=packed(np.round(segments, 2), "<f4"),
                           source_edges=ne, display_edges=len(segments)))
        if i % 100 == 0:
            print(f"Skeletons {i + 1}/{len(cells)}", flush=True)
    return result


def playback(cells: list[dict], path: Path | None) -> dict:
    ids = [c["body_id"] for c in cells]
    if path:
        data = read_json(path)
    else:
        t = np.linspace(0, 2, 41)
        # Explicit synthetic phases, not an RNG or a model result.
        values = (0.5 + 0.5 * np.sin(2 * np.pi * t[:, None] / 2 + np.arange(len(ids))[None, :] * .37))
        data = dict(dataset="male-cns:v1.0", label="DUMMY DATA · synthetic sine waves — not a model run",
                    unit="arbitrary units", body_ids=ids, times_s=t.tolist(), values=np.round(values, 4).tolist())
    return load_values(cells, data)


def open_page(browser, url: str, viewport: dict, scale: int, errors: list[str]):
    page = browser.new_page(viewport=viewport, device_scale_factor=scale)
    page.on("pageerror", lambda error: errors.append(f"{url.rsplit('/', 1)[-1]}: {error}"))
    # Actual file:// render with ALL network access blocked.
    page.route("http://**/*", lambda route: route.abort())
    page.route("https://**/*", lambda route: route.abort())
    page.goto(url, wait_until="load")
    page.wait_for_function("window.atlasReady === true", timeout=300_000)
    return page


def paper_figure(browser, page, evidence: dict, path: Path, errors: list[str]) -> None:
    """The paper's anatomy figure: the atlas's two views at print size, without the page around them."""
    state = page.evaluate("window.atlasState()")
    hide = page.add_style_tag(content="#viewport > :not(#main-canvas), #context > :not(#context-canvas) {visibility: hidden}")
    views = {}
    for name, scale in (("main", "scale_px_per_100um"), ("context", "context_scale_px_per_100um")):
        canvas = page.locator(f"#{name}-canvas")
        width, height = canvas.evaluate("c => [c.clientWidth, c.clientHeight]")
        views[name] = dict(src="data:image/png;base64," + base64.b64encode(canvas.screenshot(timeout=120_000)).decode(),
                           width=width, height=height, scale_px_per_100um=state[scale])
    views["context"]["extent"] = state["context_extent"]
    hide.evaluate("e => e.remove()")
    figure = browser.new_page(viewport={"width": 1000, "height": 800}, device_scale_factor=3)
    figure.on("pageerror", lambda error: errors.append(f"{path.name}: {error}"))
    figure.route("http://**/*", lambda route: route.abort())
    figure.route("https://**/*", lambda route: route.abort())
    data = dict(views=views, groups=evidence["groups"], text=PAPER_ANATOMY)
    figure.set_content(read_text(ANATOMY_PAPER).replace("__DATA__", json_text(data)), wait_until="load")
    figure.evaluate("window.figureReady")
    figure.locator("#figure").screenshot(path=str(path))
    figure.close()


def screenshot(html: Path, png: Path, dummy_png: Path | None, paper_png: Path | None, series: dict,
               still_time: float | None, cinematic: Path | None) -> tuple[dict, list[Path]]:
    from playwright.sync_api import sync_playwright
    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True,
                                     args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        # The interactive page: exercise the real controls, not only a static frame.
        page = open_page(browser, html.as_uri(), {"width": 1600, "height": 1050}, 2, errors)
        evidence = page.evaluate("window.atlasEvidence")
        evidence["browser_version"] = browser.version
        if dummy_png:
            page.locator("#mode").click()
            page.locator("#timeline").fill("20")
            page.locator("#timeline").dispatch_event("input")
            page.wait_for_function("document.querySelector('#time').textContent === '1.00 s'")
        else:
            before = page.evaluate("window.atlasState().frame")
            page.locator("#play").click()
            page.wait_for_function("before => window.atlasState().frame !== before", arg=before)
            page.locator("#play").click()
            evidence["play_advanced"] = True
        page.close()
        # Figure mode: the same renderer laid out as a clean still, with no controls.
        page = open_page(browser, html.as_uri() + "#figure", {"width": 1600, "height": 1000}, 2, errors)
        outputs = [png]
        if dummy_png:
            page.screenshot(path=str(png))
            paper_figure(browser, page, evidence, paper_png, errors)
            outputs += [paper_png, dummy_png]
            page.evaluate("s => window.atlasSet(s)", {"frame": 20, "value_mode": True})
            page.screenshot(path=str(dummy_png))
        else:
            times = np.asarray(series["times_s"])
            if still_time is not None and not times[0] <= still_time <= times[-1]:
                raise ValueError("--still-time is outside recorded bin centres")
            frame = len(times) // 2 if still_time is None else int(np.argmin(abs(times - still_time)))
            evidence["stills"] = []
            for i, condition in enumerate(series["conditions"]):
                state = page.evaluate("s => window.atlasSet(s)",
                                      {"condition": condition["id"], "frame": frame, "value_mode": True})
                path = html.parent / f"male-cns-{condition['id']}.png"
                page.screenshot(path=str(path))
                outputs.append(path)
                evidence["stills"].append(state)
                if i == 0:
                    page.screenshot(path=str(png))
        page.close()
        if cinematic:
            # The cinematic page must also load offline, cleanly; the clip script records it.
            page = open_page(browser, cinematic.as_uri(), {"width": 1280, "height": 720}, 1, errors)
            evidence["cinematic"] = page.evaluate("window.filmEvidence")
            page.close()
        browser.close()
    if errors:
        raise RuntimeError(f"Viewer errors: {errors}")
    return evidence, outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=main_cache())
    parser.add_argument("--out", type=Path, default=ROOT / "figures/3d")
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--values", type=Path, help="Value JSON (single array or multiple conditions)")
    inputs.add_argument("--study", type=Path, help="Read-only directory of complete 5a/5b seed manifests and NPZs")
    parser.add_argument("--plan", type=Path, help="Frozen study plan; required with --study")
    parser.add_argument("--params", type=Path, default=ROOT / "data/params-v0.2.yaml")
    parser.add_argument("--pair", type=Path, help="Frozen pair record; required for 5b")
    parser.add_argument("--activity-cache", type=Path, help="Extracted means, per-seed rates and manifest (not the raw folder)")
    parser.add_argument("--source", help="Original study source location for the extraction manifest")
    parser.add_argument("--primary-5b", action="store_true", help="Four vehicle arms, selected seed, first 2 s of test")
    parser.add_argument("--audit", type=Path, default=ROOT / "validation/records/p2/adhd-study-5b-audit.json")
    parser.add_argument("--results", type=Path, default=ROOT / "validation/records/p2/adhd-study-results.json")
    parser.add_argument("--bin-ms", type=float, default=100)
    parser.add_argument("--still-time", type=float, help="Bin centre nearest this run time; default: middle bin, same for every arm")
    parser.add_argument("--circuit", action="store_true", help="Add courtship skeletons to the existing MaleCNS view")
    args = parser.parse_args()
    if args.study and not args.plan:
        parser.error("--study requires --plan")
    if args.primary_5b and (not args.study or not args.pair or args.bin_ms != 100):
        parser.error("--primary-5b requires --study, --pair and 100 ms bins")
    cache, out = args.cache.expanduser().resolve(), args.out.expanduser().resolve()
    if args.study and (out == args.study.resolve() or args.study.resolve() in out.parents):
        parser.error("--out must be outside the raw study directory")
    if args.circuit:
        GROUPS.extend(CIRCUIT_GROUPS)
    assets = Assets(cache)
    cells, groups = selected_cells(assets)
    activity_manifest = None
    values_path = args.values
    if args.study:
        name = "body-annotations-male-cns-v1.0-minconf-0.5.feather"
        table = read_feather(cache / name).to_pandas()
        roots = table.loc[(table.status == "Traced") & table.type.notna(), "bodyId"].to_numpy(dtype="<i8")
        destination = args.activity_cache or cache / "activity" / args.study.resolve().name / "display"
        if args.primary_5b:
            values_path = extract_primary_5b(args.study, args.plan, args.pair, args.params,
                                             args.audit, args.results, roots, cells, destination)
        else:
            values_path = extract_study(args.study, args.plan, args.params, roots, cells, destination,
                                        source=args.source or str(args.study.resolve()), pair_path=args.pair,
                                        bin_s=args.bin_ms / 1000)
        activity_manifest = values_path.parent / "manifest.json"
    series = playback(cells, values_path)
    # Custom arrays start in value mode; the original dummy demo starts in anatomy mode.
    series["start_in_values"] = values_path is not None
    # Plain page text: stage, seed and file names stay in the receipt, not on the pictures.
    if args.study:
        extraction, plan = read_json(activity_manifest), read_json(args.plan)
        pair = read_json(args.pair)["pair"] if args.pair else None
        if args.primary_5b:
            seeds = plan["seeds"]["5b"]
            show = display_block(series, "primary", stage="5b", pair=pair,
                                 fly=(seeds.index(extraction["seed"]) + 1, len(seeds)))
        else:
            show = display_block(series, "study", stage=extraction["stage"], pair=pair,
                                 runs=len(plan["seeds"][extraction["stage"]]))
    else:
        show = display_block(series, "custom" if values_path else "anatomy")
    out.mkdir(parents=True, exist_ok=True)
    if activity_manifest:
        (out / "manifest.json").write_text(read_text(activity_manifest))
    print(f"Displayed populations: {groups}", flush=True)
    region_meshes = meshes(assets)
    skeletons = neurons(assets, cells)
    if not values_path:
        (out / "dummy-values.json").write_text(json_text(series) + "\n")
    payload = dict(dataset="male-cns:v1.0", groups=groups, meshes=region_meshes, cells=skeletons,
                   playback=series, display=show)
    packed_payload = base64.b64encode(gzip.compress(json_text(payload).encode(), mtime=0)).decode()
    libraries = {}
    for key, source in [("THREE", "build/three.module.min.js"), ("CONTROLS", "examples/jsm/controls/OrbitControls.js")]:
        path = assets.get(f"visuals/vendor/three-0.160.1/{Path(source).name}",
                          f"https://unpkg.com/three@0.160.1/{source}", "embedded offline renderer, MIT license")
        libraries[key] = base64.b64encode(read_bytes(path)).decode()
    assets.get("visuals/vendor/three-0.160.1/LICENSE", "https://unpkg.com/three@0.160.1/LICENSE", "Three.js license")

    def page(template: Path, path: Path, extra: dict[str, str]) -> Path:
        html = read_text(template)
        if args.circuit:
            html = html.replace('Sources, body IDs and hashes: build.json and data/malecns-v1.0-manifest.json.',
                                'Anatomical and simulation provenance is recorded separately.')
        for key, value in {**libraries, **extra, "PAYLOAD": packed_payload}.items():
            html = html.replace(f"__{key}__", value)
        if len(html.encode()) >= FILE_LIMIT:
            raise ValueError(f"{path.name} exceeds 20 MB; reduce display geometry before writing")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
        return path

    html_path, png_path = page(TEMPLATE, out / "male-cns-atlas.html", {}), out / "male-cns-atlas.png"
    cinematic = None
    if args.primary_5b:
        modules = {name: base64.b64encode(read_bytes(VENDOR / "jsm" / name)).decode() for name in BLOOM_MODULES}
        cinematic = page(CINEMATIC, out / "cinematic/male-cns-cinematic.html", {"MODULES": json_text(modules)})
    dummy_png = out / "male-cns-dummy-playback.png" if not values_path else None
    paper_png = out / "male-cns-anatomy-paper.png" if not values_path else None
    evidence, screenshots = screenshot(html_path, png_path, dummy_png, paper_png, series, args.still_time, cinematic)
    inputs = {str(p.relative_to(ROOT)): hash_file(p) for p in
              (POPULATIONS, Path(__file__), Path(__file__).with_suffix(".py.lock"), TEMPLATE, DISPLAY,
               ROOT / "scripts/malecns_3d/activity.py",
               ROOT / "src/flyonenomics/registry/populations.py", ROOT / "src/flyonenomics/io.py")}
    if cinematic:
        for path in [CINEMATIC, *(VENDOR / "jsm" / name for name in BLOOM_MODULES)]:
            inputs[str(path.relative_to(ROOT))] = hash_file(path)
    if paper_png:
        inputs[str(ANATOMY_PAPER.relative_to(ROOT))] = hash_file(ANATOMY_PAPER)
    inputs["released_annotations"] = next(r["sha256"] for r in assets.manifest["files"] if r["name"].startswith("body-annotations"))
    if values_path:
        inputs["playback_values"] = hash_file(values_path)
    if activity_manifest:
        inputs["activity_manifest"] = hash_file(activity_manifest)
    outputs = [html_path, *screenshots]
    if cinematic:
        outputs.append(cinematic)
    if dummy_png:
        outputs.append(out / "dummy-values.json")
    if activity_manifest:
        outputs.append(out / "manifest.json")
    receipt = dict(dataset=payload["dataset"], label=series["label"], inputs_sha256=inputs, groups=groups, cells=cells,
                   coordinate_transform="display_um = (native_nm / 1000 - [384,200,230]) * [1,-1,-1]; no mirror",
                   skeleton_simplification="RDP 1 um on degree-two paths; retain all branch points and tips; round to 0.01 um",
                   meshes=[{k: v for k, v in m.items() if k not in ("vertices", "faces")} for m in region_meshes],
                   skeleton_source_edges=sum(c["source_edges"] for c in skeletons),
                   skeleton_display_edges=sum(c["display_edges"] for c in skeletons),
                   source_asset_count=len(assets.used), source_bytes=sum(assets.records[n]["bytes"] for n in assets.used),
                   visual_source_bytes=sum(assets.records[n]["bytes"] for n in assets.used if n not in assets.flat_names),
                   new_download_bytes=assets.downloaded, browser=evidence,
                   outputs={str(p.relative_to(out)): dict(bytes=p.stat().st_size, sha256=hash_file(p))
                            for p in outputs})
    (out / "build.json").write_text(json.dumps(receipt, indent=2) + "\n")
    for path in out.rglob("*"):
        if path.is_file() and path.stat().st_size >= FILE_LIMIT:
            raise ValueError(f"Output exceeds 20 MB: {path}")
    print(json.dumps({"png": str(png_path), "html": str(html_path), "source_bytes": receipt["source_bytes"],
                      "new_download_bytes": assets.downloaded, "outputs": receipt["outputs"]}, indent=2))


if __name__ == "__main__":
    main()
