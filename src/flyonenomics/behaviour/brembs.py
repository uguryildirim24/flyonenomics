"""Pinned Colomb/Brembs archive ingestion and reference metric verification."""
from __future__ import annotations

import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np
import pandas as pd

from flyonenomics.behaviour.metrics import Geometry, mindistkeep3, resample, score
from flyonenomics.registry.annotations import cached_path, provenance_records, verify_file
from flyonenomics.types import Params, load_params

ROOT = Path(__file__).resolve().parents[3]
SPLIT_SEED = 20260912  # SPEC section 7.
COHORT_FLIES = 128  # SPEC sections 3.5 and 7.
SPLIT_HALF = 64  # SPEC section 7.
STEP_CANDIDATES_MM = (0.8, 0.6)  # SPEC section 3.5 verification 4.0b.
CETRAN_ITEMS = ("CeTrAn CeTrAn/functions/functions.r", "CeTrAn CeTrAn/functions/utils.r",
                "CeTrAn CeTrAn/scripts/angledev.r", "CeTrAn CeTrAn/CeTrAn_fromxml_4.rgg")


def archive_path() -> Path:
    """Return verified pinned archive path; units none, one path."""
    record = provenance_records()["github-importJnx5V7.zip"]
    path = cached_path(record)
    verify_file(path, record)
    return path


def _reference_list(z: zipfile.ZipFile) -> tuple[list[tuple[str, str]], pd.DataFrame, pd.DataFrame]:
    name = next(n for n in z.namelist() if n.endswith("/4CS_data/diffCS_all.txt"))
    listed = [tuple(line.split()[:2]) for line in z.read(name).decode().splitlines() if ".xml" in line]
    table_name = next(n for n in z.namelist() if n.endswith("output _table.csv"))
    published = pd.read_csv(io.BytesIO(z.read(table_name)))
    group_name = next(n for n in z.namelist() if n.endswith("/4CS_data/Groupdetail.csv"))
    groups = pd.read_csv(io.BytesIO(z.read(group_name))).set_index("Original_group")
    return listed, published, groups


def _trajectory(z: zipfile.ZipFile, xml_name: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Convert one XML/DAT pair to mm/s table (n,4); CeTrAn `functions.r:load.buridan.data` scale."""
    root = ElementTree.fromstring(z.read(xml_name))
    def tag(key: str) -> str | None:
        return root.findtext(key)
    dat_name = str(Path(xml_name).parent / str(tag("DATAFILE")))
    if dat_name not in z.namelist():
        raise FileNotFoundError(dat_name)
    if int(tag("DURATION") or 0) != 300000:
        raise ValueError("duration not 300 s")
    raw = pd.read_csv(io.BytesIO(z.read(dat_name)), sep="\t")
    scale = float(tag("ARENA_DIAMETER_MM")) / (2 * float(tag("ARENA_RADIUS")))
    # Source stripes are at +/-90 degrees from +x. Our azimuth 0 is +y.
    trajectory = pd.DataFrame({"t_s": raw.time.to_numpy(dtype=float) / 1000,
                               "x_mm": (raw.x.to_numpy(dtype=float) - float(tag("ARENA_CENTER_X"))) * scale,
                               "y_mm": (raw.y.to_numpy(dtype=float) - float(tag("ARENA_CENTER_Y"))) * scale,
                               "segment": raw.burst.to_numpy()})
    meta = {"label": tag("FLY"), "xml": xml_name, "dat": dat_name,
            "duration_s": float(tag("DURATION")) / 1000, "frame_count": len(raw),
            "segment_count": int(raw.burst.nunique()), "scale_mm_per_px": scale,
            "stripe_width_deg": float(tag("STRIPE_WIDTH"))}
    return trajectory, meta


def load_reference() -> tuple[list[tuple[dict[str, Any], pd.DataFrame]], list[dict[str, str]]]:
    """Read 128 reference flies, each t_s/x_mm/y_mm/segment (n,); report excluded files.

    XML pixel scaling follows CeTrAn v.4 `functions.r:load.buridan.data`
    and the centre/wall geometry in `functions.r:create.env.vars`.
    """
    records = provenance_records()
    for item in CETRAN_ITEMS:
        verify_file(cached_path(records[item]), records[item])
    flies: list[tuple[dict[str, Any], pd.DataFrame]] = []
    excluded: list[dict[str, str]] = []
    with zipfile.ZipFile(archive_path()) as z:
        listed, published, groups = _reference_list(z)
        names = set(z.namelist())
        prefix = next(n.split("4CS_data/")[0] for n in names if "4CS_data/diffCS_all.txt" in n) + "4CS_data/"
        referenced: set[str] = set()
        for index, (relative, original_group) in enumerate(listed):
            xml = prefix + relative
            if xml not in names:
                matches = [n for n in names if n.casefold() == xml.casefold()]
                if not matches:
                    excluded.append({"file": xml, "reason": "missing XML"})
                    continue
                xml = matches[0]
            try:
                trajectory, meta = _trajectory(z, xml)
            except (FileNotFoundError, ValueError) as exc:
                excluded.append({"file": xml, "reason": str(exc)})
                continue
            row = published.iloc[index]
            number = int(str(row["id"]).split("_")[0])
            if number != 100 + index:
                raise ValueError("published table/order mismatch")
            group = groups.loc[original_group]
            if any(str(group[key]) != str(row[target]) for key, target in
                   (("genotype", "genotype"), ("other", "other"), ("machine", "machine"))):
                raise ValueError(f"Groupdetail and published table disagree at {number}")
            meta.update({"id": str(row["id"]), "original_group": original_group,
                         "sub_strain": str(group["genotype"]),
                         "batch": str(group["other"]), "machine": str(group["machine"]),
                         "published_stripe_deviation_deg": float(row["stripe_deviation"]),
                         "published_walks": int(row["number_of_walks"]),
                         "published_median_speed_mm_s": float(row["median_speed"])})
            flies.append((meta, trajectory))
            referenced.add(meta["dat"])
        for dat in sorted(n for n in names if n.endswith(".dat") and n not in referenced):
            expected_xml = str(Path(dat).with_suffix(".xml"))
            matches = [n for n in names if n.casefold() == expected_xml.casefold()]
            if not matches:
                reason = "missing XML header"
            else:
                duration = ElementTree.fromstring(z.read(matches[0])).findtext("DURATION")
                reason = "duration not 300 s" if duration != "300000" else "outside published 128-fly cohort"
            excluded.append({"file": dat, "reason": reason})
    return flies, excluded


def split(flies: list[tuple[dict[str, Any], pd.DataFrame]]) -> dict[str, Any]:
    """Seeded 64/64 stratification by sub-strain and recording batch; IDs (128,)."""
    rng = np.random.default_rng(SPLIT_SEED)
    groups: dict[tuple[str, str], list[str]] = {}
    for meta, _ in flies:
        groups.setdefault((meta["sub_strain"], meta["batch"]), []).append(meta["id"])
    calibration: list[str] = []
    holdout: list[str] = []
    odds: list[tuple[tuple[str, str], str]] = []
    for key in sorted(groups):
        ids = list(rng.permutation(groups[key]))
        n = len(ids) // 2
        calibration.extend(ids[:n])
        holdout.extend(ids[n:2*n])
        if len(ids) % 2:
            odds.append((key, ids[-1]))
    rng.shuffle(odds)
    needed = len(flies) // 2 - len(calibration)
    calibration.extend(item for _, item in odds[:needed])
    holdout.extend(item for _, item in odds[needed:])
    assert len(flies) == COHORT_FLIES and len(calibration) == len(holdout) == SPLIT_HALF
    by_dat: dict[str, list[str]] = defaultdict(list)
    for meta, _ in flies:
        by_dat[meta["dat"]].append(meta["id"])
    for ids in by_dat.values():
        if len(ids) > 1 and not (set(ids) <= set(calibration) or set(ids) <= set(holdout)):
            raise ValueError(f"duplicate raw trajectory would leak across split: {ids}")
    return {"seed": SPLIT_SEED, "stratified_by": ["sub_strain", "batch"],
            "calibration": sorted(calibration), "holdout": sorted(holdout)}


def verify_4_0b(flies: list[tuple[dict[str, Any], pd.DataFrame]], params: Params | None = None) -> dict[str, Any]:
    """Compare both CeTrAn step thresholds (mm) on 128 full records; angular tolerance degrees, walks count."""
    p = params or load_params()
    geometry = Geometry.from_params(p)
    candidates: dict[str, Any] = {}
    for threshold in STEP_CANDIDATES_MM:
        angle_matches = walk_matches = joint_matches = 0
        residuals: list[dict[str, Any]] = []
        for meta, table in flies:
            measured = score(table, geometry, p, mode="full", step_min_mm=threshold)
            delta_angle = None if measured["stripe_deviation_deg"] is None else measured["stripe_deviation_deg"] - meta["published_stripe_deviation_deg"]
            delta_walks = measured["walks"] - meta["published_walks"]
            a = delta_angle is not None and abs(delta_angle) <= p.get("metrics.cetran_tol_deg")
            w = abs(delta_walks) <= p.get("metrics.cetran_tol_walks")
            angle_matches += a
            walk_matches += w
            joint_matches += a and w
            residuals.append({"id": meta["id"], "angle_delta_deg": delta_angle,
                              "walk_delta": delta_walks, "angle_match": a, "walk_match": w})
        candidates[str(threshold)] = {"angle_matches": angle_matches, "walk_matches": walk_matches,
                                      "joint_matches": joint_matches, "residuals": residuals}
    winner = max(STEP_CANDIDATES_MM, key=lambda value: candidates[str(value)]["joint_matches"])
    return {"selected_step_min_mm": winner, "candidates": candidates,
            "passed": candidates[str(winner)]["joint_matches"] >= 0.9 * len(flies)}


def ingest(output_dir: Path | None = None) -> dict[str, Any]:
    """Write deterministic fly metrics and split JSON; speeds mm/s, all trajectories (n,4)."""
    destination = output_dir or ROOT / "data"
    params = load_params()
    flies, excluded = load_reference()
    division = split(flies)
    checks = verify_4_0b(flies, params)
    geometry = Geometry.from_params(params)
    threshold = checks["selected_step_min_mm"]
    rows: list[dict[str, Any]] = []
    for meta, trajectory in flies:
        measured = score(trajectory, geometry, params, mode="window", step_min_mm=threshold)
        sampled = resample(trajectory, params.get("metrics.resample_hz"))
        speeds: list[float] = []
        for _, segment in sampled.groupby("segment", sort=False):
            pts = mindistkeep3(segment[["x_mm", "y_mm"]].to_numpy(dtype=float), threshold, params.get("metrics.step_max_mm"))
            delta = np.linalg.norm(np.diff(pts, axis=0), axis=1)
            speeds.extend((delta[delta > 0] * params.get("metrics.resample_hz")).tolist())
        rows.append({**meta, "window_metrics": measured,
                     "median_walking_speed_mm_s": float(np.median(speeds)) if speeds else None})
    calibration = set(division["calibration"])
    v_fwd = float(np.median([r["median_walking_speed_mm_s"] for r in rows
                             if r["id"] in calibration and r["median_walking_speed_mm_s"] is not None]))
    calibration_metrics: dict[str, float | int] = {}
    for key in ("fixation_index", "stripe_deviation_deg"):
        values = np.asarray([row["window_metrics"][key] for row in rows
                             if row["id"] in calibration and row["window_metrics"][key] is not None], dtype=float)
        if not len(values):
            raise ValueError(f"no defined calibration values for {key}")
        calibration_metrics[f"{key}_median"] = float(np.median(values))
        calibration_metrics[f"{key}_iqr"] = float(np.percentile(values, 75) - np.percentile(values, 25))
        calibration_metrics[f"{key}_defined_flies"] = len(values)
    division["calibration_metrics"] = calibration_metrics
    by_dat: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_dat[row["dat"]].append(row["id"])
    result = {"source": "Colomb and Brembs 2014, figshare 1014264 v2; CeTrAn v.4",
              "kept": len(rows), "excluded": excluded, "v_fwd_mm_s": v_fwd,
              "duplicate_datafile_refs": {key: ids for key, ids in by_dat.items() if len(ids) > 1},
              "verification_4_0b": checks, "flies": rows}
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in (("brembs-metrics.json", result), ("brembs-split.json", division)):
        (destination / name).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    result = ingest()
    print(json.dumps({"kept": result["kept"], "excluded": len(result["excluded"]),
                      "v_fwd_mm_s": result["v_fwd_mm_s"], "verification_4_0b": {
                          "selected_step_min_mm": result["verification_4_0b"]["selected_step_min_mm"],
                          "passed": result["verification_4_0b"]["passed"],
                          "match_counts": {k: v["joint_matches"] for k, v in result["verification_4_0b"]["candidates"].items()}}}))
