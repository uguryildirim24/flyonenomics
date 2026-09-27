"""Retinotopy and stage populations (SPEC-P2 sections 3.2 and 3.3)."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from numpy.typing import NDArray
from scipy.stats import rankdata, spearmanr

from flyonenomics.io import read_yaml

from flyonenomics.registry.annotations import load_engine_order
from flyonenomics.registry.populations import (
    PopulationEntry,
    check_inventory,
    check_overlaps,
    resolve_population,
)
from flyonenomics.io import read_yaml
from flyonenomics.substrate.transmitters import load_connection_columns

REPO = Path(__file__).resolve().parents[3]
V01_PATH = REPO / "data" / "populations-v0.1.yaml"
V02_PATH = REPO / "data" / "populations-v0.2.yaml"
EYE_SPAN_DEG = 150.0
# Committed azimuths and the table SHA-256 use the same rounding.
AZIMUTH_DECIMALS = 6
MAX_COLUMN_SPREAD_DEG = 20.0
COLUMN_HALFWIDTH_DEG = 10.0

# Assignment order of section 3.3, then remaining WP10 overlay types.
STAGE_ORDER: tuple[tuple[str, str, str, str], ...] = (
    ("R1_6", "values", "cell_type", "R1-6"),
    ("L1", "values", "cell_type", "L1"),
    ("L2", "values", "cell_type", "L2"),
    ("L3", "values", "cell_type", "L3"),
    ("L4", "values", "cell_type", "L4"),
    ("L5", "values", "cell_type", "L5"),
    ("Mi1", "values", "cell_type", "Mi1"),
    ("Mi4", "values", "cell_type", "Mi4"),
    ("Mi9", "values", "cell_type", "Mi9"),
    ("Tm1", "values", "cell_type", "Tm1"),
    ("Tm2", "values", "cell_type", "Tm2"),
    ("Tm3", "values", "cell_type", "Tm3"),
    ("Tm4", "values", "cell_type", "Tm4"),
    ("Tm9", "values", "cell_type", "Tm9"),
    ("T4", "regex", "cell_type", "^T4"),
    ("T5", "regex", "cell_type", "^T5"),
    ("LC10", "regex", "cell_type", "^LC10"),
)
OVERLAY_EXTRA: tuple[tuple[str, str, str, str], ...] = (
    ("R7", "values", "cell_type", "R7"),
    ("R8", "values", "cell_type", "R8"),
    ("LC_all", "regex", "cell_type", "^LC"),
    ("LPLC", "regex", "hemibrain_type", "^LPLC"),
    ("visual_projection", "values", "super_class", "visual_projection"),
)
EXISTING_V01_NAMES = frozenset({"MeTu"})
SYNAPSE_PAIRS: tuple[tuple[str, str], ...] = (
    ("R1_6", "L1"),
    ("R1_6", "L2"),
    ("L1", "Mi1"),
    ("L1", "Tm3"),
    ("L2", "Tm1"),
    ("L2", "Tm2"),
    ("L2", "Tm4"),
    ("L2", "Tm9"),
)


def r16_azimuths(
    sides: NDArray[np.str_],
    pos_z: NDArray[np.floating],
) -> NDArray[np.float64]:
    """Assign R1-6 fly-relative azimuths by lamina-terminal z rank.

    Units: pos_z is the 40 nm section index; return is degrees.
    Shapes: sides (n,), pos_z (n,), return (n,). Rank r of n maps to
    (r + 0.5) / n × 150° in the right eye and the negative of that in
    the left eye, with 0° straight ahead. Anterior is smaller z.
    pos_z is an integer section index with many ties; tied neurons take
    the mean of their 0-based ranks, so the azimuth never depends on file
    row order. Values are rounded to AZIMUTH_DECIMALS, as committed.
    """
    if sides.shape != pos_z.shape or sides.ndim != 1:
        raise ValueError("sides and pos_z must be one-dimensional and aligned")
    result = np.full(len(sides), np.nan, dtype=np.float64)
    z_values = np.asarray(pos_z, dtype=np.float64)
    side_values = np.asarray(sides, dtype=str)
    for side, sign in (("right", 1.0), ("left", -1.0)):
        idx = np.flatnonzero(side_values == side)
        if not len(idx):
            continue
        count = len(idx)
        rank = rankdata(z_values[idx], method="average") - 1.0
        result[idx] = np.round(sign * (rank + 0.5) / count * EYE_SPAN_DEG, AZIMUTH_DECIMALS)
    if np.isnan(result).any():
        raise ValueError("R1-6 retinotopy needs left or right side labels")
    return result


def type_mask(frame: pd.DataFrame, kind: str, column: str, pattern: str) -> NDArray[np.bool_]:
    """Return a boolean mask for one stage selector. Units: none. Shapes: (n,)."""
    series = frame[column].fillna("").astype(str)
    if kind == "values":
        return series.to_numpy() == pattern
    return series.str.match(pattern, na=False).to_numpy()


def select_type_frame(frame: pd.DataFrame, spec: tuple[str, str, str, str]) -> pd.DataFrame:
    """Rows of one named type. Units: per annotation column. Shapes: (count,)."""
    _name, kind, column, pattern = spec
    return frame.loc[type_mask(frame, kind, column, pattern)]


def propagate_from_edges(
    post_roots: NDArray[np.int64],
    pre_id: NDArray[np.int64],
    post_id: NDArray[np.int64],
    weight: NDArray[np.floating],
    azimuth_of: dict[int, float],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Weighted circular mean and spread for each postsynaptic root.

    Units: azimuth degrees, weights synapse counts. Shapes: post_roots
    (m,), edges (n_syn,), returns two (m,) arrays. Partners without an
    azimuth are ignored.
    """
    if not azimuth_of:
        nan = np.full(post_roots.shape[0], np.nan, dtype=np.float64)
        return nan, nan.copy()
    have = np.fromiter(azimuth_of.keys(), dtype=np.int64, count=len(azimuth_of))
    az_vals = np.fromiter((azimuth_of[int(k)] for k in have), dtype=np.float64, count=len(have))
    indexer = pd.Index(have)
    pre_pos = indexer.get_indexer(np.asarray(pre_id, dtype=np.int64))
    keep = pre_pos >= 0
    if not np.any(keep):
        nan = np.full(post_roots.shape[0], np.nan, dtype=np.float64)
        return nan, nan.copy()
    posts = np.asarray(post_id, dtype=np.int64)[keep]
    w = np.asarray(weight, dtype=np.float64)[keep]
    az = az_vals[pre_pos[keep]]
    rad = np.deg2rad(az)
    order = np.argsort(posts, kind="mergesort")
    posts_s = posts[order]
    w_s = w[order]
    sin_s = w_s * np.sin(rad[order])
    cos_s = w_s * np.cos(rad[order])
    change = np.empty(posts_s.shape[0], dtype=bool)
    change[0] = True
    change[1:] = posts_s[1:] != posts_s[:-1]
    starts = np.flatnonzero(change)
    sum_sin = np.add.reduceat(sin_s, starts)
    sum_cos = np.add.reduceat(cos_s, starts)
    sum_w = np.add.reduceat(w_s, starts)
    grouped_posts = posts_s[starts]
    mean = np.rad2deg(np.arctan2(sum_sin, sum_cos))
    radius = np.clip(np.hypot(sum_sin, sum_cos) / np.maximum(sum_w, 1e-15), 0.0, 1.0)
    std = np.full(mean.shape, 180.0, dtype=np.float64)
    ok = radius > 1e-15
    std[ok] = np.rad2deg(np.sqrt(-2.0 * np.log(radius[ok])))
    lookup_mean = {int(root): float(val) for root, val in zip(grouped_posts, mean)}
    lookup_std = {int(root): float(val) for root, val in zip(grouped_posts, std)}
    means = np.array([lookup_mean.get(int(root), np.nan) for root in post_roots], dtype=np.float64)
    stds = np.array([lookup_std.get(int(root), np.nan) for root in post_roots], dtype=np.float64)
    return means, stds


def synapse_count(
    pre_roots: NDArray[np.int64],
    post_roots: NDArray[np.int64],
    pre_id: NDArray[np.int64],
    post_id: NDArray[np.int64],
    connectivity: NDArray[np.floating],
) -> dict[str, int]:
    """Count pairs and synapses from one type onto another.

    Units: pair count and synapse count. Shapes: scalars.
    """
    pre_index = pd.Index(np.asarray(pre_roots, dtype=np.int64))
    post_index = pd.Index(np.asarray(post_roots, dtype=np.int64))
    keep = (pre_index.get_indexer(pre_id) >= 0) & (post_index.get_indexer(post_id) >= 0)
    return {
        "pairs": int(np.count_nonzero(keep)),
        "synapses": int(np.asarray(connectivity, dtype=np.int64)[keep].sum()),
    }


def build_retinotopy(frame: pd.DataFrame) -> dict[str, Any]:
    """Rank R1-6, then propagate azimuth in the section 3.3 type order.

    Units: degrees and synapse counts. Shapes: per-type tables of
    in-engine neurons. No engine process.
    """
    engine_order = load_engine_order("783")
    table = load_connection_columns(
        ("Presynaptic_ID", "Postsynaptic_ID", "Connectivity")
    )
    pre_id = table.column("Presynaptic_ID").to_numpy()
    post_id = table.column("Postsynaptic_ID").to_numpy()
    weight = table.column("Connectivity").to_numpy()
    azimuth_of: dict[int, float] = {}
    types: dict[str, dict[str, Any]] = {}
    r16 = select_type_frame(frame, STAGE_ORDER[0])
    sides = r16["side"].fillna("").astype(str).to_numpy()
    pos_z = pd.to_numeric(r16["pos_z"], errors="coerce").to_numpy(dtype=np.float64)
    az = r16_azimuths(sides, pos_z)
    r16_roots = r16["root_id"].to_numpy(dtype=np.int64)
    for root, angle in zip(r16_roots, az):
        azimuth_of[int(root)] = float(angle)
    types["R1_6"] = {
        "root_ids": [int(v) for v in r16_roots],
        "azimuth_deg": [float(v) for v in az],
        "spread_deg": [0.0] * int(len(r16_roots)),
        "side": [str(v) for v in sides],
        "pos_z": [float(v) for v in pos_z],
        "median_spread_deg": 0.0,
        "n": int(len(r16_roots)),
        "n_with_azimuth": int(len(r16_roots)),
        "column_subsets": True,
        "source": "rank",
    }
    for spec in STAGE_ORDER[1:]:
        name, _kind, _column, _pattern = spec
        subset = select_type_frame(frame, spec)
        roots = subset["root_id"].to_numpy(dtype=np.int64)
        means, stds = propagate_from_edges(roots, pre_id, post_id, weight, azimuth_of)
        finite = np.isfinite(means)
        for root, angle, ok in zip(roots, means, finite):
            if ok:
                azimuth_of[int(root)] = float(angle)
        median = float(np.nanmedian(stds)) if np.any(finite) else float("nan")
        types[name] = {
            "root_ids": [int(v) for v in roots],
            "azimuth_deg": [None if not np.isfinite(v) else float(v) for v in means],
            "spread_deg": [None if not np.isfinite(v) else float(v) for v in stds],
            "side": [str(v) for v in subset["side"].fillna("").astype(str).to_numpy()],
            "median_spread_deg": median,
            "n": int(len(roots)),
            "n_with_azimuth": int(np.count_nonzero(finite)),
            "column_subsets": bool(np.isfinite(median) and median <= MAX_COLUMN_SPREAD_DEG),
            "source": "propagated",
        }
    l2 = types["L2"]
    l2_frame = select_type_frame(frame, ("L2", "values", "cell_type", "L2"))
    l2_sides = l2_frame["side"].fillna("").astype(str).to_numpy()
    l2_z = pd.to_numeric(l2_frame["pos_z"], errors="coerce").to_numpy(dtype=np.float64)
    rank_az = r16_azimuths(l2_sides, l2_z)
    prop = np.array([np.nan if v is None else v for v in l2["azimuth_deg"]], dtype=np.float64)
    spearman: dict[str, float] = {}
    for side in ("left", "right"):
        mask = (l2_sides == side) & np.isfinite(prop)
        if int(np.count_nonzero(mask)) < 3:
            spearman[side] = float("nan")
            continue
        rho, _p = spearmanr(rank_az[mask], prop[mask])
        spearman[side] = float(rho)
    root_of_type = {name: np.asarray(payload["root_ids"], dtype=np.int64) for name, payload in types.items()}
    synapses = {}
    for pre_name, post_name in SYNAPSE_PAIRS:
        synapses[f"{pre_name}->{post_name}"] = synapse_count(
            root_of_type[pre_name], root_of_type[post_name], pre_id, post_id, weight
        )
    canonical = _canonical_table_bytes(types["R1_6"])
    return {
        "engine_n": int(engine_order.shape[0]),
        "types": types,
        "spearman_L2_vs_own_z": spearman,
        "synapse_counts": synapses,
        "r1_6_sha256": hashlib.sha256(canonical).hexdigest(),
        "max_column_spread_deg": MAX_COLUMN_SPREAD_DEG,
        "column_halfwidth_deg": COLUMN_HALFWIDTH_DEG,
        "eye_span_deg": EYE_SPAN_DEG,
    }


def _canonical_table_bytes(payload: dict[str, Any]) -> bytes:
    """Canonical CSV of root_id,azimuth_deg for the SHA-256. Units: bytes."""
    lines = ["root_id,azimuth_deg\n"]
    for root, angle in zip(payload["root_ids"], payload["azimuth_deg"]):
        lines.append(f"{int(root)},{round(float(angle), AZIMUTH_DECIMALS):.{AZIMUTH_DECIMALS}f}\n")
    return "".join(lines).encode("ascii")


def check_r16_monotone(payload: dict[str, Any]) -> dict[str, Any]:
    """V0(a) checks: per-eye monotone z rank and coverage of (0°, 150°).

    Units: degrees. Shapes: scalars per eye. Azimuth is strictly monotone
    across distinct z values and equal within a tie of z.
    """
    sides = np.asarray(payload["side"], dtype=str)
    z_values = np.asarray(payload["pos_z"], dtype=np.float64)
    az = np.asarray(payload["azimuth_deg"], dtype=np.float64)
    out: dict[str, Any] = {}
    for side, lo, hi in (("right", 0.0, EYE_SPAN_DEG), ("left", -EYE_SPAN_DEG, 0.0)):
        mask = sides == side
        order = np.argsort(z_values[mask], kind="stable")
        ordered = az[mask][order]
        diffs = np.diff(ordered)
        tied = np.diff(z_values[mask][order]) == 0
        steps = diffs[~tied]
        monotone = bool(np.all(diffs[tied] == 0)) and (
            bool(np.all(steps > 0)) if side == "right" else bool(np.all(steps < 0))
        )
        out[side] = {
            "n": int(np.count_nonzero(mask)),
            "min_deg": float(ordered[0]) if len(ordered) else float("nan"),
            "max_deg": float(ordered[-1]) if len(ordered) else float("nan"),
            "monotone": monotone,
            "covers_open_interval": bool(
                len(ordered) and float(ordered.min()) > lo and float(ordered.max()) < hi
            ),
        }
    return out


def _population_entry(
    name: str,
    kind: str,
    column: str,
    pattern: str,
    inventory_count: int,
    overlaps: list[str],
    side: str | None,
    note: str,
    required: bool = False,
) -> dict[str, Any]:
    """One populations-v0.2.yaml row. Units: inventory_count is a neuron count."""
    if kind == "values":
        selector: dict[str, Any] = {"kind": "values", "column": column, "values": [pattern]}
    else:
        selector = {"kind": "regex", "column": column, "pattern": pattern}
    return {
        "name": name,
        "selector": selector,
        "required": required,
        "exclude": [],
        "inventory_count": int(inventory_count),
        "inventory_tolerance": "percent",
        "overlaps_with": list(overlaps),
        "expected_nt": None,
        "side": side,
        "note": note,
    }


def _annotation_inventory(full: pd.DataFrame, spec: tuple[str, str, str, str], side: str | None) -> int:
    """Count annotated rows of one type, optionally by side. Units: neuron count."""
    subset = select_type_frame(full, spec)
    if side is not None:
        subset = subset.loc[subset["side"].fillna("").astype(str) == side]
    return int(len(subset))


def build_population_entries(full: pd.DataFrame, engine_frame: pd.DataFrame) -> list[dict[str, Any]]:
    """v0.1 rows plus stage and overlay types, with side splits.

    Units: inventory counts are annotation neuron counts. Shapes: one
    mapping per population. MeTu is not duplicated; side splits are
    added. Overlaps are filled after a dry resolve.
    """
    raw = read_yaml(V01_PATH)
    entries: list[dict[str, Any]] = list(raw["populations"])
    specs = list(STAGE_ORDER) + [spec for spec in OVERLAY_EXTRA if spec[0] not in EXISTING_V01_NAMES]
    existing = {row["name"] for row in entries}
    new_rows: list[dict[str, Any]] = []
    for spec in specs:
        name, kind, column, pattern = spec
        if name in existing:
            continue
        count = _annotation_inventory(full, spec, None)
        note = f"WP14 stage population; annotation {count} on v2.1.0."
        new_rows.append(_population_entry(name, kind, column, pattern, count, [], None, note, required=name == "R1_6"))
        for side, suffix in (("left", "_L"), ("right", "_R")):
            side_count = _annotation_inventory(full, spec, side)
            if side_count == 0:
                continue
            new_rows.append(_population_entry(
                f"{name}{suffix}", kind, column, pattern, side_count,
                [name], side, f"Side split of {name}; annotation {side_count} {side}.",
            ))
    for side, suffix in (("left", "_L"), ("right", "_R")):
        spec = ("MeTu", "regex", "cell_type", "^MeTu")
        side_count = _annotation_inventory(full, spec, side)
        new_rows.append(_population_entry(
            f"MeTu{suffix}", "regex", "cell_type", "^MeTu", side_count,
            ["MeTu"], side, f"Side split of MeTu; annotation {side_count} {side}.",
        ))
    trial = copy.deepcopy(entries) + copy.deepcopy(new_rows)
    engine_order = engine_frame["root_id"].to_numpy(dtype=np.int64)
    resolved: dict[str, Any] = {}
    entry_of: dict[str, PopulationEntry] = {}
    validated = [PopulationEntry.model_validate(row) for row in trial]
    for entry in validated:
        population = resolve_population(entry, full, engine_order, resolved)
        check_inventory(population, entry)
        resolved[entry.name] = population
        entry_of[entry.name] = entry
    # Declare overlaps involving new names against everyone.
    new_names = [row["name"] for row in new_rows]
    all_names = [row["name"] for row in trial]
    extra: dict[str, list[str]] = {name: [] for name in new_names}
    root_sets = {name: set(int(v) for v in resolved[name].root_ids) for name in all_names}
    already: set[frozenset[str]] = set()
    for row in trial:
        for other in row.get("overlaps_with") or []:
            already.add(frozenset((row["name"], other)))
    for new_name in new_names:
        for other in all_names:
            if other == new_name:
                continue
            pair = frozenset((new_name, other))
            if pair in already:
                continue
            if root_sets[new_name] & root_sets[other]:
                extra[new_name].append(other)
                already.add(pair)
    by_name = {row["name"]: row for row in new_rows}
    for name, others in extra.items():
        by_name[name]["overlaps_with"] = sorted(set(by_name[name]["overlaps_with"] + others))
    # Re-validate overlaps.
    combined = entries + new_rows
    validated = [PopulationEntry.model_validate(row) for row in combined]
    resolved = {}
    entry_of = {}
    for entry in validated:
        population = resolve_population(entry, full, engine_order, resolved)
        check_inventory(population, entry)
        resolved[entry.name] = population
        entry_of[entry.name] = entry
    check_overlaps(resolved, entry_of)
    return combined


def write_populations(retinotopy: dict[str, Any], entries: list[dict[str, Any]], path: Path | None = None) -> Path:
    """Write populations-v0.2.yaml with retinotopy tables. Units: none."""
    compact_types = {}
    for name, payload in retinotopy["types"].items():
        compact_types[name] = {
            "n": payload["n"],
            "n_with_azimuth": payload["n_with_azimuth"],
            "median_spread_deg": payload["median_spread_deg"],
            "column_subsets": payload["column_subsets"],
            "source": payload["source"],
            "root_ids": payload["root_ids"],
            "azimuth_deg": [
                None if v is None else round(float(v), AZIMUTH_DECIMALS) for v in payload["azimuth_deg"]
            ],
        }
    document = {
        "version": "v0.2",
        "annotation_version": "v2.1.0",
        "annotation_commit": "ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0",
        "mapping_date": "2026-09-14",
        "selector_tolerance_percent": 10,
        "inventory_note": (
            "v0.1 populations plus WP14 stage and WP10 overlay types. "
            "Side splits use the annotation side column. Retinotopy tables "
            "are in-engine root IDs. Counts measured on pinned v2.1.0."
        ),
        "retinotopy": {
            "rule": (
                "SPEC-P2 3.2 rank of pos_z per eye, tied z at the mean rank, azimuth rounded to "
                f"{AZIMUTH_DECIMALS} decimals; 3.3 connectivity mean, types assigned one after another "
                "in the listed order"
            ),
            "sha256": retinotopy["r1_6_sha256"],
            "eye_span_deg": EYE_SPAN_DEG,
            "max_column_spread_deg": MAX_COLUMN_SPREAD_DEG,
            "column_halfwidth_deg": COLUMN_HALFWIDTH_DEG,
            "spearman_L2_vs_own_z": retinotopy["spearman_L2_vs_own_z"],
            "synapse_counts": retinotopy["synapse_counts"],
            "types": compact_types,
        },
        "populations": entries,
    }
    destination = path or V02_PATH
    destination.write_text(yaml.safe_dump(document, sort_keys=False, width=120))
    return destination


def load_retinotopy(path: str | Path | None = None) -> dict[str, Any]:
    """Load the retinotopy block of populations-v0.2.yaml. Units: degrees."""
    destination = Path(path) if path is not None else V02_PATH
    raw = read_yaml(destination)
    return raw["retinotopy"]


def build_wp14_files() -> dict[str, Any]:
    """Write transmitters, populations, and the census document. Units: none."""
    from flyonenomics.registry.annotations import load_annotations
    from flyonenomics.substrate.transmitters import (
        annotations_in_engine,
        write_census_document,
        write_transmitters,
    )

    census = write_transmitters()
    full = load_annotations("v2.1.0")
    engine_frame, _order = annotations_in_engine()
    retinotopy = build_retinotopy(engine_frame)
    entries = build_population_entries(full, engine_frame)
    write_populations(retinotopy, entries)
    write_census_document(census, retinotopy)
    return {"census": census, "retinotopy": retinotopy}
