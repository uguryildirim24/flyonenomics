"""Development visual-path diagnostic (SPEC section 11 item 65, WP10; SPEC-P2 v2).

v1 (WP10) does not write canonical validation entries and does not
change frozen data files. Overlay populations load from
data/populations-dev.yaml and never merge into the frozen registry.

v2 (WP18) reuses that driver for R3. It adds dark and ambient
conditions, histamine-scale records, rest-substrate hooks, stage
populations, column subsets and V1 statistics. Engine runs wait on
WP14/WP15/WP17/WP19. Constructed-input helpers do not start an engine.
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from flyonenomics.behaviour.encoder import (
    PR_ACCEPTANCE_DEG,
    PR_RATE_DARK_HZ,
    photoreceptor_input_rates,
    preferred_azimuths,
)
from flyonenomics.io import hash_file, read_yaml
from flyonenomics.behaviour.metrics import wrap
from flyonenomics.registry import annotations as ann
from flyonenomics.registry.populations import (
    Population,
    check_inventory,
    check_overlaps,
    load_population_table,
    resolve_population,
)
from flyonenomics.types import LayerFlags, Params, load_params

REPO = Path(__file__).resolve().parents[3]
OVERLAY_PATH = REPO / "data" / "populations-dev.yaml"
FROZEN_POPULATIONS_PATH = REPO / "data" / "populations-v0.1.yaml"
OPEN_LOOP_PATH = REPO / "data" / "experiments" / "open-loop-steering.json"
DOPAMINE_PATH = REPO / "data" / "dopamine-v0.1.yaml"
FROZEN_DATA_FILES = (
    "params-v0.1.yaml",
    "dopamine-v0.1.yaml",
    "behaviour-v0.1.yaml",
    "populations-v0.1.yaml",
    "receptors-v0.1.yaml",
)

# SPEC vis.r_max (item 59/63). Absent from the frozen Params YAML.
# The encoder cap `vis.r_max` (item 59) is a Params class default, read not restated.
R_MAX_HZ = float(load_params().get("vis.r_max"))
LAL_CONTROL_HZ = 500.0
CLASSIFIER_NOTE = ("automatic classifier word from suggest_verdict; the diagnostic's verdict "
                   "is the first line of docs/visual-path-diagnostic.md")
SILENT_HZ = 0.5
BIN_MS = 100.0
PREF_BACK_DEG = 150.0
# SPEC-P2 section 6.1 / WP18 brief: no engine while swap used exceeds 4000 MiB.
SWAP_BUDGET_M = 4000.0
COLUMN_HALFWIDTH_DEG = 10.0
MAX_COLUMN_SPREAD_DEG = 20.0
MIN_DELTA_HZ = 0.5
V_CAL_RATES_HZ = (50.0, 100.0, 150.0, 300.0)
V_CAL_EXTENSION_HZ = (25.0, 10.0)
BOOTSTRAP_QUANTILES = (0.025, 0.975)
STAGE_POPULATIONS: tuple[str, ...] = (
    "R1_6", "L1", "L2", "L3", "L4", "L5",
    "Mi1", "Mi4", "Mi9", "Tm1", "Tm2", "Tm3", "Tm4", "Tm9",
    "T4", "T5", "LC10", "LC_all", "LPLC", "MeTu", "visual_projection",
)
V1_DEPTHS: dict[str, tuple[str, ...]] = {
    "retina": ("R1_6",),
    "lamina": ("L1", "L2"),
    "medulla": ("Mi1", "Tm1", "Tm2", "Tm3", "Tm4", "Tm9"),
    "lobula": ("T5", "LC10", "LC_all", "LPLC", "MeTu"),
    "central_input": ("TuBu", "visual_projection", "LAL_neurons"),
    "steering": ("steering_L", "steering_R"),
}
V2_MEASURED_NAMES: tuple[str, ...] = STAGE_POPULATIONS + (
    "TuBu", "ER", "EPG", "LAL_neurons", "DNa02_L", "DNa02_R",
    "steering_L", "steering_R",
)
MULTIPLIER_SCAN = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0)
TARGET_PR_HZ = (100.0, 300.0)

OVERLAY_NAMES = (
    "R1_6", "R7", "R8", "L1", "L2", "Mi1", "Tm3", "T4", "T5",
    "LC_all", "LPLC", "MeTu", "visual_projection",
)
FROZEN_REUSE_NAMES = (
    "TuBu", "ER", "EPG", "LAL_neurons", "DNa02_L", "DNa02_R",
    "steering_L", "steering_R", "DN_all", "MN9", "motor",
)
MEASURED_NAMES = OVERLAY_NAMES + FROZEN_REUSE_NAMES

SITES: dict[str, tuple[str, ...]] = {
    "R1_6": ("R1_6",),
    "R1_6+R7+R8": ("R1_6", "R7", "R8"),
    "L1+L2": ("L1", "L2"),
    "TuBu": ("TuBu",),
    "LAL_neurons": ("LAL_neurons",),
}
VISUAL_SITES = ("R1_6", "R1_6+R7+R8", "L1+L2", "TuBu")
STRIPE_AZIMUTHS = (-45.0, 45.0)
RATES_HZ = (50.0, 150.0, 300.0)
# WP10 brief: seeds 1 to 3 through the experiment stream derivation. The
# open-loop file supplies only the master seed; its seed list is WP9's.
DIAGNOSTIC_SEEDS = (1, 2, 3)

PATHWAY_STAGES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("photoreceptors", ("R1_6", "R7", "R8")),
    ("lamina", ("L1", "L2")),
    ("medulla_relay", ("Mi1", "Tm3")),
    ("motion", ("T4", "T5")),
    ("LC", ("LC_all",)),
    ("visual_projection", ("visual_projection",)),
    ("central_complex_visual", ("TuBu", "ER", "EPG")),
    ("LAL", ("LAL_neurons",)),
    ("DNa02", ("DNa02_L", "DNa02_R")),
    ("steering", ("steering_L", "steering_R")),
    ("DN_all", ("DN_all",)),
    ("MN9", ("MN9",)),
)

WORKTREE_NAME = REPO.name


def repo_root() -> Path:
    """Return this worktree root. Units: none. Shapes: one path."""
    return REPO


def default_overlay_path() -> Path:
    """Return data/populations-dev.yaml. Units: none. Shapes: one path."""
    return OVERLAY_PATH


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of one file. Units: bytes hashed."""
    return hash_file(path)


def frozen_file_digests() -> dict[str, str]:
    """Return SHA-256 digests of the frozen data files. Units: hex strings."""
    out: dict[str, str] = {}
    for name in FROZEN_DATA_FILES:
        path = REPO / "data" / name
        if path.is_file():
            out[name] = sha256_file(path)
    return out


def code_commit() -> str:
    """Return HEAD commit hex. Units: none. Shapes: one string."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def master_seed_and_seeds() -> tuple[int, list[int]]:
    """Read S from the frozen open-loop file; the diagnostic seeds are 1 to 3. Units: none."""
    raw = read_json(OPEN_LOOP_PATH)
    return int(raw["seed"]), list(DIAGNOSTIC_SEEDS)


def matching_layers() -> LayerFlags:
    """Return the sign-check matching-layers flags. Units: none."""
    return LayerFlags(background=False, dopamine_A=True, transporter_C=True)


def load_dopamine_record() -> dict[str, Any]:
    """Load the frozen dopamine YAML. Units: per record fields."""
    return read_yaml(DOPAMINE_PATH)


def load_overlay_table(path: str | Path | None = None) -> tuple[str, list]:
    """Load the development overlay without reading the frozen registry.

    Units: inventory counts are neuron counts. Shapes: one entry per
    overlay population. Does not write or mutate populations-v0.1.yaml.
    """
    return load_population_table(Path(path) if path is not None else OVERLAY_PATH)


def resolve_overlay(
    annotations: pd.DataFrame,
    engine_order: NDArray[np.int64],
    path: str | Path | None = None,
) -> dict[str, Population]:
    """Resolve overlay populations against annotations and engine order.

    Units: root IDs int64, idx int32. Shapes: (count,) per population.
    Checks overlay inventory and overlay-only overlaps. Does not call
    build_registry and does not mutate the frozen population table.
    """
    _, entries = load_overlay_table(path)
    resolved: dict[str, Population] = {}
    entry_of = {}
    for entry in entries:
        population = resolve_population(entry, annotations, engine_order, resolved)
        check_inventory(population, entry)
        resolved[entry.name] = population
        entry_of[entry.name] = entry
    check_overlaps(resolved, entry_of)
    return resolved


def overlay_counts(resolved: dict[str, Population]) -> dict[str, dict[str, Any]]:
    """Record resolved counts and side splits. Units: neuron counts."""
    rows: dict[str, dict[str, Any]] = {}
    for name, population in resolved.items():
        sides = {str(side): int((population.side == side).sum()) for side in np.unique(population.side)}
        rows[name] = {"count": population.count, "sides": sides, "selector": population.selector}
    return rows


def location_columns(frame: pd.DataFrame) -> NDArray[np.float64]:
    """Return xyz (n, 3): soma when finite and nonzero, else pos.

    Units: x and y are 4 nm voxel units; z is the 40 nm section index.
    Shapes: (n, 3) as x, y, z. Photoreceptor soma columns are almost
    all empty on v2.1.0, so pos_* is the lamina terminal, which is
    retinotopic. This is a monotone rank proxy, not a receptive field.
    """
    soma = frame[["soma_x", "soma_y", "soma_z"]].apply(pd.to_numeric, errors="coerce")
    pos = frame[["pos_x", "pos_y", "pos_z"]].apply(pd.to_numeric, errors="coerce")
    soma_ok = soma.notna().all(axis=1) & (soma.abs().sum(axis=1) > 0)
    loc = np.array(pos.to_numpy(dtype=np.float64), copy=True)
    loc[np.asarray(soma_ok)] = soma.loc[soma_ok].to_numpy(dtype=np.float64)
    return loc


def locations_for_roots(root_ids: NDArray[np.int64], annotations: pd.DataFrame) -> NDArray[np.float64]:
    """Return xyz (n, 3) for roots in input order.

    Units: x,y in 4 nm voxels; z in 40 nm sections.
    """
    indexed = annotations.drop_duplicates("root_id").set_index("root_id")
    rows = indexed.loc[list(int(v) for v in root_ids)]
    return location_columns(rows)


def check_ap_axis(annotations: pd.DataFrame) -> dict[str, Any]:
    """Name the FlyWire anterior-posterior axis from ALPN versus KC somata.

    Units: x and y are 4 nm voxel units; z is the 40 nm section index.
    FAFB was sectioned frontally, so z is anterior-posterior (small z
    is front), y is dorsoventral (larger y is ventral), and x is
    mediolateral (larger x is right). Kenyon-cell somata sit posterior
    of antennal-lobe projection neurons.
    """
    alpn = annotations.loc[annotations.cell_class.fillna("").astype(str) == "ALPN"]
    kc = annotations.loc[annotations.cell_class.fillna("").astype(str) == "Kenyon_Cell"]
    alpn_loc = location_columns(alpn)
    kc_loc = location_columns(kc)
    alpn_z = float(np.nanmean(alpn_loc[:, 2]))
    kc_z = float(np.nanmean(kc_loc[:, 2]))
    alpn_y = float(np.nanmean(alpn_loc[:, 1]))
    kc_y = float(np.nanmean(kc_loc[:, 1]))
    alpn_x = float(np.nanmean(alpn_loc[:, 0]))
    if not (alpn_z < kc_z):
        raise ValueError("ALPN z is not smaller than Kenyon-cell z; AP axis check failed")
    r16 = annotations.loc[annotations.cell_type.fillna("").astype(str) == "R1-6"]
    loc = location_columns(r16)
    soma = r16[["soma_x", "soma_y", "soma_z"]].apply(pd.to_numeric, errors="coerce")
    soma_missing = int((~soma.notna().all(axis=1)).sum())
    left = r16.side.fillna("").astype(str) == "left"
    right = r16.side.fillna("").astype(str) == "right"
    return {
        "units": {
            "x": "4 nm voxels",
            "y": "4 nm voxels",
            "z": "40 nm section index",
        },
        "anterior_posterior_axis": "z (soma_z / pos_z, 40 nm sections)",
        "anterior_is": "smaller z",
        "left_right_axis": "x (soma_x / pos_x, 4 nm voxels)",
        "right_is": "larger x",
        "dorsal_ventral_axis": "y (soma_y / pos_y, 4 nm voxels)",
        "ventral_is": "larger y",
        "elevation_axis": "y rank per eye; larger y is ventral",
        "elevation_used_for_rates": False,
        "landmarks": {
            "ALPN_n": int(len(alpn)),
            "ALPN_mean_z_sections": alpn_z,
            "ALPN_mean_y_voxels": alpn_y,
            "ALPN_mean_x_voxels": alpn_x,
            "Kenyon_Cell_n": int(len(kc)),
            "Kenyon_Cell_mean_z_sections": kc_z,
            "Kenyon_Cell_mean_y_voxels": kc_y,
        },
        "R1_6_left_mean_x_voxels": float(np.nanmean(loc[left.to_numpy(), 0])),
        "R1_6_right_mean_x_voxels": float(np.nanmean(loc[right.to_numpy(), 0])),
        "R1_6_mean_z_sections": float(np.nanmean(loc[:, 2])),
        "R1_6_soma_missing": soma_missing,
        "R1_6_n": int(len(r16)),
        "R1_6_location": "pos_* lamina terminal; 8451 of 8452 R1-6 rows have no soma in the volume",
        "note": "Monotone approximation from location rank, not a measured receptive field.",
        "passed": True,
    }


def retinotopic_azimuths(
    sides: NDArray[np.str_],
    anterior_coord: NDArray[np.floating],
    pref_range: tuple[float, float] = (0.0, PREF_BACK_DEG),
) -> NDArray[np.float64]:
    """Assign fly-relative azimuths in degrees (n,) by AP rank per eye.

    Units: anterior_coord is the z section index; output is degrees.
    Smaller z is the front of the eye (0 deg). The back of the eye is
    ±pref_range[1] deg. Left eye is negative. Rank is stable.
    """
    if len(sides) != len(anterior_coord):
        raise ValueError("sides and anterior_coord must have the same length")
    result = np.full(len(sides), np.nan, dtype=np.float64)
    for side in ("left", "right", "center", "na"):
        idx = np.flatnonzero(np.asarray(sides) == side)
        if not len(idx):
            continue
        order_local = np.argsort(np.asarray(anterior_coord, dtype=np.float64)[idx], kind="stable")
        ordered = idx[order_local]
        count = len(idx)
        if side == "left":
            values = -np.linspace(pref_range[0], pref_range[1], count)
        elif side == "right":
            values = np.linspace(pref_range[0], pref_range[1], count)
        else:
            values = np.linspace(-pref_range[1], pref_range[1], count)
        result[ordered] = values
    if np.isnan(result).any():
        raise ValueError("unknown side in retinotopic assignment")
    return result


def retinotopic_elevations(
    sides: NDArray[np.str_],
    ventral_coord: NDArray[np.floating],
) -> NDArray[np.float64]:
    """Assign unused elevation ranks in degrees (n,) by y rank per eye.

    Units: ventral_coord is y in 4 nm voxels; output is degrees.
    Larger y is ventral. These values are recorded and never drive rates.
    """
    if len(sides) != len(ventral_coord):
        raise ValueError("sides and ventral_coord must have the same length")
    result = np.full(len(sides), np.nan, dtype=np.float64)
    for side in ("left", "right", "center", "na"):
        idx = np.flatnonzero(np.asarray(sides) == side)
        if not len(idx):
            continue
        order_local = np.argsort(np.asarray(ventral_coord, dtype=np.float64)[idx], kind="stable")
        result[idx[order_local]] = np.linspace(-90.0, 90.0, len(idx))
    if np.isnan(result).any():
        raise ValueError("unknown side in elevation assignment")
    return result


def gaussian_stripe_rates(
    preferred: NDArray[np.floating],
    az_fly_deg: float,
    maximum_hz: float,
    sigma_deg: float,
    contrast: float = 1.0,
) -> NDArray[np.float64]:
    """Return encoder-matching Gaussian rates in Hz (n,).

    Units: azimuth degrees, rate Hz, sigma degrees, contrast unitless.
    Matches VisualEncoder.rates for one stimulus.
    """
    if not np.isfinite(maximum_hz) or maximum_hz < 0 or not np.isfinite(sigma_deg) or sigma_deg <= 0:
        raise ValueError("encoder maximum must be nonnegative Hz and sigma positive degrees")
    if contrast <= 0:
        return np.zeros(len(preferred), dtype=np.float64)
    difference = wrap(az_fly_deg - np.asarray(preferred, dtype=np.float64))
    value = contrast * np.exp(-np.square(difference) / (2 * sigma_deg * sigma_deg))
    return np.minimum(maximum_hz, maximum_hz * value)


def first_silent_stage(mean_rates_hz: dict[str, float], threshold_hz: float = SILENT_HZ) -> str | None:
    """Return the first pathway stage with every member below threshold.

    Units: Hz per neuron. Shapes: one scalar per named population.
    Missing names are skipped. Returns None when no stage is silent.
    """
    for stage, names in PATHWAY_STAGES:
        present = [mean_rates_hz[name] for name in names if name in mean_rates_hz]
        if present and all(value < threshold_hz for value in present):
            return stage
    return None


def suggest_verdict(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify encoder-placement versus substrate from condition rows.

    Units: Hz. Shapes: one mapping of flags and the verdict word.
    """
    def mean_of(row: dict[str, Any], name: str) -> float:
        return float(row.get("mean_rate_hz", {}).get(name, 0.0))

    lal_rows = [row for row in rows if row.get("site") == "LAL_neurons"]
    visual_rows = [row for row in rows if row.get("site") in VISUAL_SITES]
    lal_steering = any(
        mean_of(row, "steering_L") >= SILENT_HZ or mean_of(row, "steering_R") >= SILENT_HZ
        for row in lal_rows
    )
    pr_fires = any(
        row.get("site") in ("R1_6", "R1_6+R7+R8") and mean_of(row, "R1_6") >= SILENT_HZ
        for row in visual_rows
    )

    def reaches_central(row: dict[str, Any]) -> bool:
        injected = set(SITES.get(str(row.get("site")), ()))
        names = ("visual_projection", "LAL_neurons", "TuBu", "ER", "EPG")
        return any(
            name not in injected and mean_of(row, name) >= SILENT_HZ
            for name in names
        )

    def steering_asym(row: dict[str, Any]) -> bool:
        return abs(float(row.get("steering_diff_hz", 0.0))) >= SILENT_HZ

    def steering_fires(row: dict[str, Any]) -> bool:
        return mean_of(row, "steering_L") >= SILENT_HZ or mean_of(row, "steering_R") >= SILENT_HZ

    pr_or_lamina = [row for row in visual_rows if row.get("site") in ("R1_6", "R1_6+R7+R8", "L1+L2")]
    tubu = [row for row in visual_rows if row.get("site") == "TuBu"]
    pr_reaches = any(reaches_central(row) or steering_fires(row) for row in pr_or_lamina)
    tubu_reaches = any(reaches_central(row) or steering_fires(row) for row in tubu)
    pr_asym = any(steering_asym(row) for row in pr_or_lamina)
    any_visual_central = any(reaches_central(row) for row in visual_rows)
    any_visual_steer = any(steering_fires(row) for row in visual_rows)

    reason = ""
    if not lal_rows:
        verdict = "inconclusive"
        reason = "No LAL positive-control row was measured."
    elif not lal_steering:
        verdict = "inconclusive"
        reason = "LAL 500 Hz control did not fire steering_L or steering_R."
    elif pr_asym or (pr_reaches and not tubu_reaches):
        verdict = "encoder placement"
        reason = "Photoreceptor or lamina injection reached visual projection, LAL, or steering; TuBu injection did not, or a steering asymmetry appeared."
    elif not any_visual_central and not any_visual_steer and lal_steering:
        verdict = "substrate"
        reason = "The signal died before the central brain from every visual injection site. Only the LAL control fired descending neurons."
    else:
        verdict = "inconclusive"
        reason = "Visual injection reached some stages, or TuBu and photoreceptor sites behaved the same, so placement versus substrate is not split."
    return {
        "verdict": verdict,
        "reason": reason,
        "lal_steering_fires": lal_steering,
        "photoreceptors_fire": pr_fires,
        "pr_or_lamina_reaches_central": pr_reaches,
        "tubu_reaches_central": tubu_reaches,
        "pr_or_lamina_steering_asymmetry": pr_asym,
        "any_visual_central": any_visual_central,
        "any_visual_steering": any_visual_steer,
    }


def condition_id(site: str, azimuth: str, rate_hz: float, seed: int) -> str:
    """Return a filesystem name. Units: Hz. Shapes: one string."""
    site_key = site.replace("+", "-")
    return f"{site_key}_az{azimuth}_rate{int(rate_hz)}_seed{seed}"


def condition_payload(
    *,
    commit: str,
    params_hash: str,
    seed_master: int,
    seed: int,
    site: str,
    azimuth: str,
    rate_hz: float,
    multiplier: float,
    settle_s: float,
    record_s: float,
    bin_rates_hz: dict[str, list[float]],
    mean_rate_hz: dict[str, float],
    network_mean_hz: float,
    steering_diff_hz: float,
    first_silent_stage: str | None,
    spike_count: int,
    n_neurons: int,
) -> dict[str, Any]:
    """Build one per-condition JSON mapping. Units: Hz, seconds, counts."""
    return {
        "code_commit": commit,
        "params_hash": params_hash,
        "seed_master": seed_master,
        "seed": seed,
        "site": site,
        "azimuth": azimuth,
        "rate_hz": rate_hz,
        "multiplier": multiplier,
        "settle_s": settle_s,
        "record_s": record_s,
        "bin_ms": BIN_MS,
        "bin_rates_hz": bin_rates_hz,
        "mean_rate_hz": mean_rate_hz,
        "network_mean_hz": network_mean_hz,
        "steering_diff_hz": steering_diff_hz,
        "first_silent_stage": first_silent_stage,
        "spike_count": spike_count,
        "n_neurons": n_neurons,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write UTF-8 JSON. Units: none. Shapes: one mapping."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    """Read one JSON mapping. Units: none. Shapes: one mapping."""
    from flyonenomics.io import read_json as read_logged_json

    return read_logged_json(path)


def write_propagation_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write one row per condition. Units: Hz. Shapes: table."""
    fields = [
        "id", "site", "azimuth", "rate_hz", "seed", "multiplier",
        "network_mean_hz", "steering_diff_hz", "first_silent_stage", "spike_count",
        *[f"mean_{name}" for name in MEASURED_NAMES],
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {
                "id": row["id"],
                "site": row["site"],
                "azimuth": row["azimuth"],
                "rate_hz": row["rate_hz"],
                "seed": row["seed"],
                "multiplier": row["multiplier"],
                "network_mean_hz": row["network_mean_hz"],
                "steering_diff_hz": row["steering_diff_hz"],
                "first_silent_stage": row["first_silent_stage"] or "",
                "spike_count": row["spike_count"],
            }
            means = row.get("mean_rate_hz", {})
            for name in MEASURED_NAMES:
                out[f"mean_{name}"] = means.get(name, "")
            writer.writerow(out)


def parse_swap_used_m(text: str) -> float:
    """Parse `sysctl vm.swapusage` used mebibytes. Units: MiB."""
    match = re.search(r"used\s*=\s*([0-9.]+)M", text)
    if not match:
        raise ValueError(f"cannot parse swap usage: {text}")
    return float(match.group(1))


def machine_status() -> dict[str, Any]:
    """Read engine-exclusion checks. Units: KiB RSS, MiB swap."""
    ps = subprocess.run(["ps", "-axo", "rss,command"], check=True, capture_output=True, text=True)
    bench = False
    other_heavy = 0
    others: list[str] = []
    for line in ps.stdout.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        rss_s, _, command = stripped.partition(" ")
        try:
            rss_kb = int(rss_s)
        except ValueError:
            continue
        if "bench.py" in command:
            bench = True
        if "worktrees/" in command and f"worktrees/{WORKTREE_NAME}/" not in command:
            if "python" in command.lower() and rss_kb > 1_000_000:
                other_heavy += 1
                others.append(f"{rss_kb} {command[:120]}")
    swap_text = subprocess.run(["sysctl", "vm.swapusage"], check=True, capture_output=True, text=True).stdout
    used_m = parse_swap_used_m(swap_text)
    ready = (not bench) and other_heavy <= 1 and used_m <= 3000
    abort = used_m > 3800
    return {
        "bench": bench,
        "other_heavy_python": other_heavy,
        "others": others,
        "swap_used_m": used_m,
        "ready": ready,
        "abort": abort,
        "ps": ps.stdout,
        "swap": swap_text.strip(),
    }


def wait_for_machine(*, retries: int = 0, sleep_s: float = 300.0) -> dict[str, Any]:
    """Check the engine exclusion. Default is one check and no sleep.

    WP18 must not hold the coordinator with long sleep loops. retries 0
    raises at once when the machine is not ready. Units: seconds, MiB.
    """
    last = machine_status()
    attempt = 0
    while not last["ready"]:
        if last["abort"] or attempt >= retries:
            if last["abort"]:
                raise RuntimeError(f"swap used {last['swap_used_m']} M exceeds {SWAP_BUDGET_M} M")
            raise RuntimeError(f"machine not ready after {retries} waits: {last}")
        attempt += 1
        print(json.dumps({"event": "machine-wait", "attempt": attempt, "status": {
            "bench": last["bench"], "other_heavy_python": last["other_heavy_python"],
            "swap_used_m": last["swap_used_m"],
        }}), flush=True)
        time.sleep(sleep_s)
        last = machine_status()
    return last


def site_members(
    names: tuple[str, ...],
    populations: dict[str, Population],
) -> tuple[NDArray[np.int32], NDArray[np.int64], NDArray[np.str_]]:
    """Union site members in engine-index order. Units: idx int32, roots int64."""
    idx_parts: list[NDArray[np.int32]] = []
    root_parts: list[NDArray[np.int64]] = []
    side_parts: list[NDArray[np.str_]] = []
    for name in names:
        pop = populations[name]
        idx_parts.append(pop.idx)
        root_parts.append(pop.root_ids)
        side_parts.append(pop.side)
    idx = np.concatenate(idx_parts) if idx_parts else np.zeros(0, dtype=np.int32)
    roots = np.concatenate(root_parts) if root_parts else np.zeros(0, dtype=np.int64)
    sides = np.concatenate(side_parts) if side_parts else np.zeros(0, dtype=np.str_)
    order = np.argsort(idx, kind="stable")
    _, unique = np.unique(idx[order], return_index=True)
    keep = order[unique]
    return idx[keep], roots[keep], sides[keep]


def site_preferred(
    site: str,
    populations: dict[str, Population],
    annotations: pd.DataFrame | None,
    params: Params,
) -> tuple[NDArray[np.int32], NDArray[np.float64]]:
    """Return engine indices and preferred azimuths in degrees (m,).

    TuBu uses encoder root-ID grids. Photoreceptor and lamina sites use
    z-section rank (small z is front). Elevation from y is not used.
    LAL has no preferred azimuths (uniform drive).
    """
    names = SITES[site]
    idx, roots, sides = site_members(names, populations)
    if site == "TuBu":
        preferred = preferred_azimuths(roots, sides, tuple(params.get("vis.pref_range")))
        return idx, preferred
    if site == "LAL_neurons":
        return idx, np.zeros(len(idx), dtype=np.float64)
    if annotations is None:
        raise ValueError("retinotopic sites need annotations")
    loc = locations_for_roots(roots, annotations)
    preferred = retinotopic_azimuths(sides, loc[:, 2], tuple(params.get("vis.pref_range")))
    return idx, preferred


def extended_rates(
    extended_idx: NDArray[np.int32],
    site_idx: NDArray[np.int32],
    site_preferred: NDArray[np.float64],
    *,
    azimuth: str,
    rate_hz: float,
    sigma_deg: float,
    multiplier: float,
    uniform: bool,
) -> NDArray[np.float64]:
    """Return extended-input Hz (len(extended_idx),). Units: Hz, degrees."""
    output = np.zeros(len(extended_idx), dtype=np.float64)
    positions = np.searchsorted(extended_idx, site_idx)
    if np.any(positions >= len(extended_idx)) or not np.array_equal(extended_idx[positions], site_idx):
        raise ValueError("site indices absent from extended_idx")
    if uniform:
        values = np.full(len(site_idx), rate_hz * multiplier, dtype=np.float64)
    else:
        values = gaussian_stripe_rates(site_preferred, float(azimuth), rate_hz, sigma_deg) * multiplier
    output[positions] = values
    return output


def bin_population_rates(
    bin_counts: NDArray[np.int64],
    populations: dict[str, Population],
    bin_s: float,
) -> dict[str, list[float]]:
    """Convert spike counts (n_bins, n) to Hz per neuron. Units: Hz."""
    rates: dict[str, list[float]] = {}
    for name in MEASURED_NAMES:
        if name not in populations:
            continue
        idx = populations[name].idx
        if idx.size == 0:
            rates[name] = [0.0] * int(bin_counts.shape[0])
            continue
        total = bin_counts[:, idx].sum(axis=1).astype(np.float64)
        rates[name] = (total / (idx.size * bin_s)).tolist()
    return rates


def mean_over_bins(bin_rates_hz: dict[str, list[float]]) -> dict[str, float]:
    """Mean Hz per neuron across bins. Units: Hz. Shapes: scalars."""
    return {name: float(np.mean(values)) if values else 0.0 for name, values in bin_rates_hz.items()}


def new_run_dir(now: datetime | None = None) -> Path:
    """Return runs/diagnostics/visual-path/<timestamp>/. Units: none."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    path = REPO / "runs" / "diagnostics" / "visual-path" / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def condition_grid(
    *, smoke: bool = False, mode: str | None = None, condition: str | None = None,
) -> list[dict[str, Any]]:
    """Return site/azimuth/rate/seed rows, or the one row named `condition`. Units: Hz, degrees."""
    if condition is not None:
        rows = [row for grid in ("full", "stripes300") for row in condition_grid(mode=grid)
                if condition_id(row["site"], row["azimuth"], row["rate_hz"], row["seed"]) == condition]
        if not rows:
            raise ValueError(f"unknown condition {condition!r}")
        return rows[:1]
    _, seeds = master_seed_and_seeds()
    chosen = mode if mode is not None else ("smoke" if smoke else "full")
    rows: list[dict[str, Any]] = []
    if chosen == "smoke":
        rows.append({
            "site": "R1_6", "azimuth": "full", "rate_hz": R_MAX_HZ, "seed": seeds[0],
            "uniform": True, "lal": False,
        })
        return rows
    if chosen == "stripes300":
        for site in ("R1_6", "R1_6+R7+R8", "L1+L2"):
            for az in (str(int(v)) for v in STRIPE_AZIMUTHS):
                for seed in seeds:
                    rows.append({
                        "site": site, "azimuth": az, "rate_hz": R_MAX_HZ, "seed": seed,
                        "uniform": False, "lal": False,
                    })
        return rows
    for site in VISUAL_SITES:
        for az in (*[str(int(v)) for v in STRIPE_AZIMUTHS], "full"):
            for rate in RATES_HZ:
                for seed in seeds:
                    rows.append({
                        "site": site, "azimuth": az, "rate_hz": rate, "seed": seed,
                        "uniform": az == "full", "lal": False,
                    })
    for seed in seeds:
        rows.append({
            "site": "LAL_neurons", "azimuth": "full", "rate_hz": LAL_CONTROL_HZ, "seed": seed,
            "uniform": True, "lal": True,
        })
    return rows


def apply_composed(engine: Any, mod: Any) -> None:
    """Write composed threshold mV and gain. Units: mV, dimensionless."""
    composed = mod.compose()
    engine.set_threshold(composed.v_th)
    engine.set_gain(composed.gain)


def run_held_window(
    engine: Any,
    mod: Any,
    rates: NDArray[np.float64],
    seconds: float,
    chunk_ms: float,
    collect_bins: bool,
) -> tuple[NDArray[np.int64], int]:
    """Advance held input. Units: seconds, ms, spike counts (n_bins, n) or (n,)."""
    chunks = int(round(seconds * 1000.0 / chunk_ms))
    if not np.isclose(chunks * chunk_ms, seconds * 1000.0):
        raise ValueError("window must divide into engine chunks")
    n_bins = int(round(seconds * 1000.0 / BIN_MS)) if collect_bins else 1
    chunks_per_bin = int(round(BIN_MS / chunk_ms)) if collect_bins else chunks
    if collect_bins and chunks_per_bin * n_bins != chunks:
        raise ValueError("record window must divide into 100 ms bins")
    totals = np.zeros((n_bins, engine.n), dtype=np.int64)
    spike_count = 0
    bin_index = 0
    bin_acc = np.zeros(engine.n, dtype=np.int64)
    steps_in_bin = 0
    for _ in range(chunks):
        engine.set_input_rates(rates)
        result = engine.run_chunk(chunk_ms)
        mod.on_chunk(result.counts, chunk_ms / 1000.0)
        apply_composed(engine, mod)
        bin_acc += result.counts.astype(np.int64)
        spike_count += int(result.counts.sum())
        steps_in_bin += 1
        if steps_in_bin == chunks_per_bin:
            totals[bin_index] = bin_acc
            bin_index += 1
            bin_acc.fill(0)
            steps_in_bin = 0
    return totals, spike_count


class CombinedPopulations:
    """Overlay first, then frozen registry. Does not mutate the frozen map."""

    def __init__(self, overlay: dict[str, Population], frozen: Any) -> None:
        """Store two lookups. Units: per Population fields."""
        self.overlay = overlay
        self.frozen = frozen

    def population(self, name: str) -> Population:
        """Return one overlay or frozen population. Units: per Population."""
        if name in self.overlay:
            return self.overlay[name]
        return self.frozen.population(name)

    def as_dict(self) -> dict[str, Population]:
        """Copy overlay plus reused frozen populations. Units: none."""
        out = dict(self.overlay)
        for name in FROZEN_REUSE_NAMES:
            out[name] = self.frozen.population(name)
        return out


def build_extended_idx(populations: dict[str, Population]) -> NDArray[np.int32]:
    """Sorted unique injection indices. Units: engine index. Shapes: (m,)."""
    parts = [populations[name].idx for names in SITES.values() for name in names]
    return np.unique(np.concatenate(parts)).astype(np.int32)


def measure_one(
    engine: Any,
    mod: Any,
    *,
    extended_idx: NDArray[np.int32],
    rates: NDArray[np.float64],
    seed_master: int,
    seed: int,
    settle_s: float,
    record_s: float,
    chunk_ms: float,
    populations: dict[str, Population],
) -> dict[str, Any]:
    """Restore, seed, settle, record. Units: Hz, seconds, spike counts."""
    from flyonenomics.orchestrator.seeds import brian_seed

    engine.restore("initial")
    engine.seed(brian_seed(seed_master, seed, 0))
    mod.reset_fast()
    apply_composed(engine, mod)
    engine.compose_refractory()
    run_held_window(engine, mod, rates, settle_s, chunk_ms, collect_bins=False)
    bins, spike_count = run_held_window(engine, mod, rates, record_s, chunk_ms, collect_bins=True)
    bin_s = BIN_MS / 1000.0
    bin_rates = bin_population_rates(bins, populations, bin_s)
    means = mean_over_bins(bin_rates)
    network = float(bins.sum() / (engine.n * record_s))
    steering = float(means.get("steering_L", 0.0) - means.get("steering_R", 0.0))
    return {
        "bin_rates_hz": bin_rates,
        "mean_rate_hz": means,
        "network_mean_hz": network,
        "steering_diff_hz": steering,
        "first_silent_stage": first_silent_stage(means),
        "spike_count": spike_count,
        "n_neurons": int(engine.n),
    }


def scan_multiplier(
    engine: Any,
    mod: Any,
    *,
    extended_idx: NDArray[np.int32],
    site_idx: NDArray[np.int32],
    preferred: NDArray[np.float64],
    sigma_deg: float,
    seed_master: int,
    seed: int,
    settle_s: float,
    record_s: float,
    chunk_ms: float,
    populations: dict[str, Population],
) -> tuple[float, dict[str, Any]]:
    """Raise Poisson-rate multiplier until R1_6 is about 100 to 300 Hz.

    Units: Hz, dimensionless multiplier. The engine has no public setter
    for extended-input synaptic weight, and input.f_poi is locked to the
    Shiu default, so the multiplier scales set_input_rates only.
    """
    last: dict[str, Any] | None = None
    chosen = 1.0
    for multiplier in MULTIPLIER_SCAN:
        rates = extended_rates(
            extended_idx, site_idx, preferred, azimuth="full", rate_hz=R_MAX_HZ,
            sigma_deg=sigma_deg, multiplier=multiplier, uniform=True,
        )
        last = measure_one(
            engine, mod, extended_idx=extended_idx, rates=rates, seed_master=seed_master,
            seed=seed, settle_s=settle_s, record_s=record_s, chunk_ms=chunk_ms,
            populations=populations,
        )
        pr = float(last["mean_rate_hz"].get("R1_6", 0.0))
        chosen = multiplier
        print(json.dumps({"event": "multiplier-scan", "multiplier": multiplier, "R1_6_hz": pr}), flush=True)
        if pr >= TARGET_PR_HZ[0]:
            break
    assert last is not None
    return chosen, last


def run_tiny(out_dir: Path | None = None) -> Path:
    """Dry-run the JSON path on the four-neuron fixture engine. Units: Hz."""
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.types import ConnectomeFiles

    params = load_params()
    tiny = ConnectomeFiles(
        completeness=REPO / "tests" / "fixtures" / "engine" / "tiny_completeness.csv",
        connectivity=REPO / "tests" / "fixtures" / "engine" / "tiny_connectivity.parquet",
        version="630",
    )
    extended = np.array([1, 2], dtype=np.int32)
    engine = BrianEngine()
    engine.build(tiny, params, InputTopology(extended_idx=extended, background=False))
    engine.restore("initial")
    engine.seed(1)
    engine.set_input_rates(np.array([50.0, 0.0]))
    counts = np.zeros(engine.n, dtype=np.int64)
    for _ in range(5):
        counts += engine.run_chunk(10.0).counts.astype(np.int64)
    bin_rates = {
        "R1_6": [float(counts[1] / 0.05)],
        "steering_L": [float(counts[2] / 0.05)],
        "steering_R": [float(counts[3] / 0.05)],
    }
    means = mean_over_bins(bin_rates)
    payload = condition_payload(
        commit="tiny", params_hash="tiny", seed_master=0, seed=1, site="R1_6",
        azimuth="full", rate_hz=50.0, multiplier=1.0, settle_s=0.0, record_s=0.05,
        bin_rates_hz=bin_rates, mean_rate_hz=means,
        network_mean_hz=float(counts.sum() / (engine.n * 0.05)),
        steering_diff_hz=float(means["steering_L"] - means["steering_R"]),
        first_silent_stage=first_silent_stage(means), spike_count=int(counts.sum()),
        n_neurons=int(engine.n),
    )
    destination = out_dir or (REPO / "runs" / "diagnostics" / "visual-path" / "tiny")
    write_json(destination / "conditions" / "tiny.json", payload)
    write_json(destination / "manifest.json", {"mode": "tiny", "n_neurons": engine.n, "spike_count": int(counts.sum())})
    write_propagation_csv(destination / "propagation.csv", [{**payload, "id": "tiny"}])
    return destination


def run_diagnostic(
    *,
    smoke: bool = False,
    mode: str | None = None,
    out_dir: Path | None = None,
    skip_machine_check: bool = False,
    settle_s: float | None = None,
    record_s: float | None = None,
    skip_multiplier_scan: bool = False,
    condition: str | None = None,
) -> Path:
    """Build one v783 engine and run the smoke, stripe, or full grid, or one named condition.

    A named condition runs at multiplier 1.0 without a scan, as the record run did.

    Units: Hz, seconds.
    """
    os.environ.setdefault("FLYONENOMICS_CACHE_DIR", "<local-project-root>/.cache")
    if not skip_machine_check:
        wait_for_machine()
    from flyonenomics.engine import BrianEngine, InputTopology
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.orchestrator.workers import connectome_files
    from flyonenomics.registry import build_registry

    params = load_params()
    chunk_ms = float(params.get("engine.chunk_ms"))
    sigma = float(params.get("vis.sigma_vis"))
    seed_master, _ = master_seed_and_seeds()
    chosen = "condition" if condition is not None else (
        mode if mode is not None else ("smoke" if smoke else "full"))
    settle = 0.5 if settle_s is None else settle_s
    record = (0.5 if chosen == "smoke" else 2.0) if record_s is None else record_s
    destination = out_dir or new_run_dir()
    destination.mkdir(parents=True, exist_ok=True)
    frozen_before = frozen_file_digests()
    annotations = ann.load_annotations("v2.1.0")
    engine_order = ann.load_engine_order("783")
    overlay = resolve_overlay(annotations, engine_order)
    axis = check_ap_axis(annotations)
    r16 = overlay["R1_6"]
    r16_loc = locations_for_roots(r16.root_ids, annotations)
    elevation = retinotopic_elevations(r16.side, r16_loc[:, 1])
    axis["R1_6_elevation_deg_min"] = float(np.min(elevation))
    axis["R1_6_elevation_deg_max"] = float(np.max(elevation))
    axis["R1_6_elevation_note"] = "y rank per eye, recorded and not used for input rates"
    frozen = build_registry()
    combined = CombinedPopulations(overlay, frozen)
    populations = combined.as_dict()
    counts = overlay_counts(overlay)
    for name in FROZEN_REUSE_NAMES:
        pop = frozen.population(name)
        counts[name] = {
            "count": pop.count,
            "sides": {str(side): int((pop.side == side).sum()) for side in np.unique(pop.side)},
            "selector": pop.selector,
            "source": "frozen",
        }
    write_json(destination / "overlay_counts.json", counts)
    write_json(destination / "ap_axis.json", axis)
    extended_idx = build_extended_idx(populations)
    layers = matching_layers()
    dopamine = load_dopamine_record()
    engine = BrianEngine()
    engine.build(connectome_files("783"), params, InputTopology(extended_idx=extended_idx, background=False))
    mod = Neuromod(frozen, params, layers, dopamine)
    mod.apply_genotype([], engine)
    engine.store("initial")
    preferred_cache: dict[str, tuple[NDArray[np.int32], NDArray[np.float64]]] = {}
    for site in SITES:
        preferred_cache[site] = site_preferred(site, populations, annotations, params)
    scan_last: dict[str, Any] = {"mean_rate_hz": {}}
    no_scan = skip_multiplier_scan or chosen in ("stripes300", "condition")
    if no_scan:
        multiplier = 1.0
    else:
        scan_idx, scan_pref = preferred_cache["R1_6"]
        multiplier, scan_last = scan_multiplier(
            engine, mod, extended_idx=extended_idx, site_idx=scan_idx, preferred=scan_pref,
            sigma_deg=sigma, seed_master=seed_master, seed=master_seed_and_seeds()[1][0],
            settle_s=settle, record_s=record, chunk_ms=chunk_ms, populations=populations,
        )
    commit = code_commit()
    params_hash = sha256_file(REPO / "data" / "params-v0.1.yaml")
    write_json(destination / "multiplier.json", {
        "multiplier": multiplier,
        "R1_6_hz": scan_last["mean_rate_hz"].get("R1_6"),
        "engine_note": "No public extended-input weight setter; input.f_poi is locked. Multiplier scales Poisson rates.",
        "scan": list(MULTIPLIER_SCAN),
        "skipped_scan": no_scan,
        "mode": chosen,
    })
    rows: list[dict[str, Any]] = []
    grid = condition_grid(mode=chosen, condition=condition)
    for spec in grid:
        site_idx, preferred = preferred_cache[spec["site"]]
        used_multiplier = 1.0 if spec["lal"] else multiplier
        rates = extended_rates(
            extended_idx, site_idx, preferred, azimuth=spec["azimuth"], rate_hz=spec["rate_hz"],
            sigma_deg=sigma, multiplier=used_multiplier, uniform=spec["uniform"] or spec["lal"],
        )
        measured = measure_one(
            engine, mod, extended_idx=extended_idx, rates=rates, seed_master=seed_master,
            seed=spec["seed"], settle_s=settle, record_s=record, chunk_ms=chunk_ms,
            populations=populations,
        )
        ident = condition_id(spec["site"], spec["azimuth"], spec["rate_hz"], spec["seed"])
        payload = condition_payload(
            commit=commit, params_hash=params_hash, seed_master=seed_master,
            seed=spec["seed"], site=spec["site"], azimuth=spec["azimuth"],
            rate_hz=spec["rate_hz"], multiplier=used_multiplier, settle_s=settle,
            record_s=record, **measured,
        )
        write_json(destination / "conditions" / f"{ident}.json", payload)
        rows.append({**payload, "id": ident})
        print(json.dumps({
            "event": "condition", "id": ident,
            "R1_6_hz": payload["mean_rate_hz"].get("R1_6"),
            "steering_diff_hz": payload["steering_diff_hz"],
            "first_silent_stage": payload["first_silent_stage"],
            "network_mean_hz": payload["network_mean_hz"],
        }), flush=True)
    det_spec = grid[0]
    site_idx, preferred = preferred_cache[det_spec["site"]]
    used_multiplier = 1.0 if det_spec["lal"] else multiplier
    rates = extended_rates(
        extended_idx, site_idx, preferred, azimuth=det_spec["azimuth"], rate_hz=det_spec["rate_hz"],
        sigma_deg=sigma, multiplier=used_multiplier, uniform=det_spec["uniform"] or det_spec["lal"],
    )
    replay = measure_one(
        engine, mod, extended_idx=extended_idx, rates=rates, seed_master=seed_master,
        seed=det_spec["seed"], settle_s=settle, record_s=record, chunk_ms=chunk_ms,
        populations=populations,
    )
    identical = int(replay["spike_count"]) == int(rows[0]["spike_count"])
    write_json(destination / "determinism.json", {
        "id": rows[0]["id"],
        "first_spike_count": rows[0]["spike_count"],
        "replay_spike_count": replay["spike_count"],
        "identical": identical,
    })
    write_propagation_csv(destination / "propagation.csv", rows)
    verdict = suggest_verdict(rows)
    frozen_after = frozen_file_digests()
    write_json(destination / "manifest.json", {
        "code_commit": commit,
        "params_hash": params_hash,
        "seed_master": seed_master,
        "mode": chosen,
        "smoke": chosen == "smoke",
        "settle_s": settle,
        "record_s": record,
        "multiplier": multiplier,
        "layers": {"background": False, "dopamine_A": True, "transporter_C": True},
        "connectome_version": "783",
        "lif.g_inh": 1,
        "n_extended": int(extended_idx.size),
        "n_conditions": len(rows),
        "run_dir": str(destination),
        "frozen_digests_before": frozen_before,
        "frozen_digests_after": frozen_after,
        "frozen_unchanged": frozen_before == frozen_after,
        "verdict": verdict,
        "verdict_note": CLASSIFIER_NOTE,
    })
    write_json(destination / "summary.json", {
        "verdict": verdict["verdict"],
        "reason": verdict["reason"],
        "verdict_note": CLASSIFIER_NOTE,
        "n_conditions": len(rows),
        "multiplier": multiplier,
        "run_dir": str(destination),
        "ids": [row["id"] for row in rows],
    })
    return destination


def engine_swap_ok(used_m: float | None = None) -> bool:
    """Return whether an engine run may start. Units: MiB. Shapes: scalar."""
    if used_m is None:
        used_m = float(machine_status()["swap_used_m"])
    return used_m <= SWAP_BUDGET_M


def circular_mean_deg(
    angles_deg: NDArray[np.floating],
    weights: NDArray[np.floating] | None = None,
) -> float:
    """Return the synapse-weighted circular mean in degrees. Units: degrees."""
    rad = np.deg2rad(np.asarray(angles_deg, dtype=np.float64))
    if rad.size == 0:
        return float("nan")
    weight = np.ones(rad.shape, dtype=np.float64) if weights is None else np.asarray(weights, dtype=np.float64)
    sine = float(np.sum(weight * np.sin(rad)))
    cosine = float(np.sum(weight * np.cos(rad)))
    return float(np.rad2deg(np.arctan2(sine, cosine)))


def circular_std_deg(
    angles_deg: NDArray[np.floating],
    weights: NDArray[np.floating] | None = None,
) -> float:
    """Return the circular standard deviation in degrees. Units: degrees."""
    rad = np.deg2rad(np.asarray(angles_deg, dtype=np.float64))
    if rad.size == 0:
        return float("nan")
    weight = np.ones(rad.shape, dtype=np.float64) if weights is None else np.asarray(weights, dtype=np.float64)
    total = float(np.sum(weight))
    if total <= 0:
        return float("nan")
    sine = float(np.sum(weight * np.sin(rad)) / total)
    cosine = float(np.sum(weight * np.cos(rad)) / total)
    radius = float(np.hypot(sine, cosine))
    if radius <= 0.0:
        return 180.0
    if radius >= 1.0:
        return 0.0
    return float(np.rad2deg(np.sqrt(-2.0 * np.log(radius))))


def column_subset_indices(
    azimuths_deg: NDArray[np.floating],
    sides: NDArray[np.str_],
    bar_azimuth_deg: float,
    halfwidth_deg: float = COLUMN_HALFWIDTH_DEG,
) -> NDArray[np.int64]:
    """Return indices of neurons on the bar's side within the column half-width.

    Units: degrees. Shapes: azimuths and sides (n,); output (m,). A bar at
    0° or ±180° uses both eyes. Types that fail the spread test should pass
    a side-wide mask instead of calling this.
    """
    azimuths = np.asarray(azimuths_deg, dtype=np.float64)
    bar = float(wrap(bar_azimuth_deg))
    if abs(bar) < 1e-12 or abs(abs(bar) - 180.0) < 1e-12:
        on_side = np.ones(len(azimuths), dtype=bool)
    else:
        wanted = "right" if bar > 0 else "left"
        on_side = np.asarray(sides) == wanted
    delta = np.abs(np.asarray(wrap(azimuths - bar), dtype=np.float64))
    return np.flatnonzero(on_side & (delta <= halfwidth_deg))


def uses_column_subsets(median_spread_deg: float, max_spread_deg: float = MAX_COLUMN_SPREAD_DEG) -> bool:
    """Return whether a type's median circular spread passes the column test."""
    if not np.isfinite(median_spread_deg):
        return False
    return float(median_spread_deg) <= max_spread_deg


def histamine_scale_record(g_his: float, applied: bool = False) -> dict[str, Any]:
    """Record the histamine scale for a v2 condition. Units: ratio."""
    if not np.isfinite(g_his) or g_his < 0:
        raise ValueError("histamine scale must be a nonnegative ratio")
    return {
        "drive.g_his": float(g_his),
        "applied": bool(applied),
        "reason": None if applied else "waiting WP14 scale_array and WP15 rest-substrate apply",
    }


def photoreceptor_condition_rates(
    preferred_deg: NDArray[np.floating],
    *,
    kind: Literal["stripe", "ambient", "dark"],
    r_light: float,
    r_dark: float = PR_RATE_DARK_HZ,
    acceptance_deg: float = PR_ACCEPTANCE_DEG,
    r_max: float,
    bar_azimuth_deg: float | None = None,
    width_deg: float = 15.0,
    contrast: float = 1.0,
) -> NDArray[np.float64]:
    """Return v2 dark, ambient or stripe Poisson rates in Hz (n,)."""
    stimuli: list[dict[str, float]] = []
    if kind == "stripe":
        if bar_azimuth_deg is None:
            raise ValueError("stripe conditions need a bar azimuth")
        stimuli = [{"az_fly": float(bar_azimuth_deg), "width": float(width_deg), "contrast": float(contrast)}]
    return photoreceptor_input_rates(
        preferred_deg, stimuli, r_light=r_light, r_dark=r_dark,
        acceptance_deg=acceptance_deg, r_max=r_max, kind=kind,
    )


def condition_grid_v2(
    *,
    r_light: float,
    seeds: tuple[int, ...] = DIAGNOSTIC_SEEDS,
    histamine_scales: tuple[float, ...] = (1.0,),
) -> list[dict[str, Any]]:
    """Return dark, ambient and ±45° stripe rows for R3/V1 development. Units: Hz, degrees."""
    rows: list[dict[str, Any]] = []
    for g_his in histamine_scales:
        for seed in seeds:
            rows.append({
                "site": "R1_6", "kind": "dark", "azimuth": None, "rate_hz": r_light,
                "seed": seed, "g_his": g_his,
            })
            rows.append({
                "site": "R1_6", "kind": "ambient", "azimuth": None, "rate_hz": r_light,
                "seed": seed, "g_his": g_his,
            })
            for az in STRIPE_AZIMUTHS:
                rows.append({
                    "site": "R1_6", "kind": "stripe", "azimuth": az, "rate_hz": r_light,
                    "seed": seed, "g_his": g_his,
                })
    return rows


def stripe_minus_ambient(stripe_hz: float, ambient_hz: float) -> float:
    """Return one block difference in Hz. Units: Hz."""
    return float(stripe_hz) - float(ambient_hz)


def delta_steer(
    plus45_right_hz: float,
    plus45_left_hz: float,
    minus45_right_hz: float,
    minus45_left_hz: float,
) -> float:
    """Return (r_R − r_L)(+45°) − (r_R − r_L)(−45°) in Hz. Units: Hz."""
    plus = float(plus45_right_hz) - float(plus45_left_hz)
    minus = float(minus45_right_hz) - float(minus45_left_hz)
    return plus - minus


def bootstrap_mean_interval(
    values: NDArray[np.floating],
    rng: np.random.Generator,
    bootstrap_n: int = 10_000,
    quantiles: tuple[float, float] = BOOTSTRAP_QUANTILES,
) -> dict[str, float]:
    """Return the seed-mean and ANALYSIS-stream bootstrap 95 percent interval. Units: Hz."""
    sample = np.asarray(values, dtype=np.float64)
    if sample.size == 0 or bootstrap_n < 1:
        raise ValueError("bootstrap needs a nonempty sample and a positive resample count")
    draws = rng.choice(sample, size=(bootstrap_n, sample.size), replace=True).mean(axis=1)
    lo, hi = np.quantile(draws, quantiles)
    return {
        "mean": float(sample.mean()),
        "lo": float(lo),
        "hi": float(hi),
        "n": int(sample.size),
        "bootstrap_n": int(bootstrap_n),
    }


def interval_excludes_zero(interval: dict[str, float]) -> bool:
    """Return whether a two-sided interval excludes 0. Units: Hz."""
    return not (interval["lo"] <= 0.0 <= interval["hi"])


def population_carried(interval: dict[str, float]) -> bool:
    """Return whether a stage population is carried. Units: Hz."""
    return interval_excludes_zero(interval)


def evaluate_v1(
    stage_delta_seeds: dict[str, NDArray[np.floating]],
    delta_steer_seeds: NDArray[np.floating],
    rng: np.random.Generator,
    *,
    min_delta_hz: float = MIN_DELTA_HZ,
    bootstrap_n: int = 10_000,
) -> dict[str, Any]:
    """Score V1 on constructed or measured per-seed differences. Units: Hz.

    stage_delta_seeds maps a population name to stripe-minus-ambient Hz
    (n_seeds,). A depth is carried when any of its named populations is.
    """
    steer = bootstrap_mean_interval(delta_steer_seeds, rng, bootstrap_n)
    steer_ok = interval_excludes_zero(steer) and abs(steer["mean"]) >= min_delta_hz
    carried: dict[str, dict[str, Any]] = {}
    for name, values in stage_delta_seeds.items():
        interval = bootstrap_mean_interval(values, rng, bootstrap_n)
        carried[name] = {**interval, "carried": population_carried(interval)}
    depths: dict[str, dict[str, Any]] = {}
    for depth, names in V1_DEPTHS.items():
        present = [name for name in names if name in carried]
        depths[depth] = {
            "populations": present,
            "carried": any(carried[name]["carried"] for name in present),
        }
    all_depths = all(row["carried"] for row in depths.values())
    return {
        "delta_steer": steer,
        "steer_pass": steer_ok,
        "populations": carried,
        "depths": depths,
        "passed": bool(steer_ok and all_depths),
        "break_at": next((depth for depth, row in depths.items() if not row["carried"]), None),
    }


def evaluate_v2(
    l1_column_delta_seeds: NDArray[np.floating],
    mi1_column_delta_seeds: NDArray[np.floating],
) -> dict[str, Any]:
    """Score V2: L1 column subset rises and Mi1 does not. Units: Hz (n_seeds,)."""
    l1 = np.asarray(l1_column_delta_seeds, dtype=np.float64)
    mi1 = np.asarray(mi1_column_delta_seeds, dtype=np.float64)
    l1_rises = bool(l1.size and float(l1.mean()) > 0.0)
    mi1_does_not = bool(mi1.size and float(mi1.mean()) <= 0.0)
    return {
        "l1_mean_delta_hz": float(l1.mean()) if l1.size else None,
        "mi1_mean_delta_hz": float(mi1.mean()) if mi1.size else None,
        "l1_rises": l1_rises,
        "mi1_does_not_rise": mi1_does_not,
        "passed": bool(l1_rises and mi1_does_not),
    }


def rest_substrate_available() -> bool:
    """Return whether WP14 retinotopy and WP15 rest plumbing are importable."""
    try:
        from flyonenomics.substrate import retinotopy as _retinotopy  # noqa: F401
    except ImportError:
        return False
    try:
        from flyonenomics.drive import rest as _rest  # noqa: F401
    except ImportError:
        return False
    return True


def populations_v02_path() -> Path:
    """Return data/populations-v0.2.yaml. Units: none. Shapes: one path."""
    return REPO / "data" / "populations-v0.2.yaml"

