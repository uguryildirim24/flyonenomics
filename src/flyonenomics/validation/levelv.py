"""Visual-path entries V0 to V3 and V-cal (SPEC-P2 section 3.4)."""
from __future__ import annotations

from math import erf, sqrt
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np
from numpy.typing import NDArray

from flyonenomics.behaviour.encoder import (
    EYE_SPAN_DEG,
    PR_ACCEPTANCE_DEG,
    PR_RATE_DARK_HZ,
    PhotoreceptorEncoder,
    midpoint_rank_azimuths,
    photoreceptor_input_rates,
)
from flyonenomics.behaviour.metrics import wrap
from flyonenomics.behaviour.visual_calibration import (
    declared_drive_present,
    declared_substrate,
    declared_substrate_id,
    declared_substrate_present,
    run_r3,
    run_vcal,
)
from flyonenomics.diagnostics.visual_path import (
    MIN_DELTA_HZ,
    V_CAL_RATES_HZ,
    rest_substrate_available,
)
from flyonenomics.types import LayerFlags, load_params
from flyonenomics.validation.binding import ValidationEntry, build_identity

REPO = Path(__file__).resolve().parents[3]
VPATH_DIR = REPO / "data" / "experiments" / "p2"
MATCHING_LAYERS = LayerFlags(background=True, dopamine_A=True, transporter_C=True)
RELATIVE_ERROR = 1e-12
V0_FIXTURE = "data/experiments/p2/vpath-v0.json"
V1_FIXTURE = "data/experiments/p2/vpath-v1.json"
V2_FIXTURE = "data/experiments/p2/vpath-v2.json"
V3_FIXTURE = "data/experiments/p2/vpath-v3.json"
VCAL_FIXTURE = "data/experiments/p2/vpath-vcal.json"
V3_RECORD = REPO / "validation" / "records" / "p2" / "V3.json"
V1_RECORD = REPO / "validation" / "records" / "p2" / "V1.json"
VCAL_RECORD = REPO / "validation" / "records" / "p2" / "visual-vcal.json"


def _entry(
    test_id: str,
    category: str,
    outcome: str,
    measured: dict[str, Any],
    *,
    fixture: str,
    compatibility: str = "canonical",
    layers: LayerFlags | None = None,
    declared: bool = False,
    identity: dict[str, Any] | None = None,
) -> ValidationEntry:
    """Bind one visual-path result. Units: per measured mapping.

    declared True binds the entry to item 122's declared resting substrate:
    the identity's substrate id is the declared drive's SHA-256 tag once that
    drive is committed. `identity` is the execution's own IdentityBlock
    written by the run on the box; when present it is used as-is so an Oracle
    result keeps its real platform, code scope and inputs.
    """
    flags = LayerFlags(background=False, dopamine_A=False, transporter_C=False) if layers is None else layers
    substrate_id = declared_substrate_id() if declared else None
    if identity is not None:
        from flyonenomics.validation.binding import IdentityBlock

        block = IdentityBlock.model_validate(identity)
    else:
        block = build_identity(
            REPO, connectome_version="783", layers=flags,
            assay="open_loop_steering", fixture=fixture, substrate_id=substrate_id,
        )
    record = measured.get("record", {})
    if identity is not None:
        compatibility = record["compatibility"]
    return ValidationEntry(
        test_id=test_id, category=category, outcome=outcome,  # type: ignore[arg-type]
        compatibility=compatibility,  # type: ignore[arg-type]
        identity=block, measured=measured,
        data_dependencies=[], fixture_path=fixture,
        declared_inputs=list(block.inputs),
        stub=record.get("qualification_note") if compatibility == "development" else None,
    )


def _math_erf_array(values: NDArray[np.floating]) -> NDArray[np.float64]:
    """Scalar math.erf over an array. Units: dimensionless. Shapes: (n,)."""
    return np.array([erf(float(value)) for value in np.asarray(values, dtype=np.float64)], dtype=np.float64)


def reference_section_32_rates(
    preferred_deg: NDArray[np.floating],
    bars: list[tuple[float, float, float]],
    *,
    r_light: float,
    r_dark: float,
    acceptance_deg: float,
    r_max: float,
    kind: Literal["stripe", "ambient", "dark"] = "stripe",
) -> NDArray[np.float64]:
    """Independent SPEC-P2 section 3.2 formula for V0(c). Units: Hz, degrees.

    bars are (az_fly_deg, width_deg, contrast). This copy uses math.erf, not
    the production scipy.special.erf path in behaviour.encoder.
    """
    phi = np.asarray(preferred_deg, dtype=np.float64)
    if kind == "dark":
        return np.minimum(r_max, np.full(len(phi), r_dark, dtype=np.float64))
    if kind == "ambient" or not bars:
        return np.minimum(r_max, np.full(len(phi), r_dark + (r_light - r_dark), dtype=np.float64))
    luminance = np.ones(len(phi), dtype=np.float64)
    scale = sqrt(2.0) * float(acceptance_deg)
    for azimuth, width, contrast in bars:
        difference = np.asarray(wrap(phi - float(azimuth)), dtype=np.float64)
        half = float(width) / 2.0
        occupancy = 0.5 * (
            _math_erf_array((difference + half) / scale) - _math_erf_array((difference - half) / scale)
        )
        luminance = luminance - float(contrast) * occupancy
    luminance = np.maximum(0.0, luminance)
    return np.minimum(r_max, r_dark + (r_light - r_dark) * luminance)


def check_v0_a(
    sides: NDArray[np.str_],
    z: NDArray[np.floating],
    azimuths_deg: NDArray[np.floating],
    span_deg: float = EYE_SPAN_DEG,
) -> dict[str, Any]:
    """V0(a): per eye, R1-6 azimuth is monotone in z rank and covers (0, span).

    WP14 assigns tied z section indices the mean of their 0-based ranks, so
    azimuth is equal within a z tie and strictly monotone across distinct z
    values. That is the same rule as `substrate.retinotopy.check_r16_monotone`.
    """
    eyes: dict[str, dict[str, Any]] = {}
    passed = True
    for side, lo, hi, sign in (
        ("right", 0.0, span_deg, 1.0),
        ("left", -span_deg, 0.0, -1.0),
    ):
        idx = np.flatnonzero(np.asarray(sides) == side)
        if idx.size < 2:
            eyes[side] = {"n": int(idx.size), "monotone": False, "covers": False}
            passed = False
            continue
        order = np.argsort(np.asarray(z, dtype=np.float64)[idx], kind="stable")
        ordered_z = np.asarray(z, dtype=np.float64)[idx][order]
        azimuth = np.asarray(azimuths_deg, dtype=np.float64)[idx][order]
        steps = np.diff(sign * azimuth)
        tied = np.diff(ordered_z) == 0.0
        monotone = bool(np.all(steps[tied] == 0.0)) and bool(np.all(steps[~tied] > 0.0))
        covers = bool(np.all((azimuth > lo) & (azimuth < hi)))
        eyes[side] = {
            "n": int(idx.size),
            "monotone": monotone,
            "covers": covers,
            "min_deg": float(azimuth.min()),
            "max_deg": float(azimuth.max()),
        }
        passed = passed and monotone and covers
    return {"passed": passed, "eyes": eyes}


def principal_axis_scores(
    xyz: NDArray[np.floating],
    z_ref: NDArray[np.floating],
) -> tuple[NDArray[np.float64], dict[str, Any]]:
    """Project positions onto PC1, signed to agree with z order.

    SPEC-P2 question 15. Units: xyz are annotation coordinates; z_ref is
    the pos_z section index; return is the signed PC1 coordinate (n,).
    """
    from scipy.stats import spearmanr

    points = np.asarray(xyz, dtype=np.float64)
    z_values = np.asarray(z_ref, dtype=np.float64)
    scores = np.full(len(points), np.nan, dtype=np.float64)
    finite = np.isfinite(points).all(axis=1)
    if int(np.count_nonzero(finite)) < 3:
        return scores, {"n": int(np.count_nonzero(finite)), "flipped": False, "explained_ratio": None}
    data = points[finite]
    mean = data.mean(axis=0)
    centred = data - mean
    _u, singular, vt = np.linalg.svd(centred, full_matrices=False)
    axis = vt[0]
    total = float(np.sum(singular ** 2))
    explained = float((singular[0] ** 2) / total) if total > 0 else None
    projection = (points - mean) @ axis
    projection = np.where(np.isfinite(points).all(axis=1), projection, np.nan)
    pair = np.isfinite(projection) & np.isfinite(z_values)
    flipped = False
    if int(np.count_nonzero(pair)) >= 3:
        rho = float(spearmanr(projection[pair], z_values[pair]).statistic)
        if np.isfinite(rho) and rho < 0.0:
            projection = -projection
            axis = -axis
            flipped = True
    scores[finite] = projection[finite]
    return scores, {
        "n": int(np.count_nonzero(finite)),
        "flipped": flipped,
        "explained_ratio": explained,
        "axis": [float(v) for v in axis],
    }


def _spearman_rank_vs_prop(
    sides: NDArray[np.str_],
    coord: NDArray[np.floating],
    propagated_deg: NDArray[np.floating],
    side: str,
) -> dict[str, Any]:
    """Spearman ρ of rank-rule azimuth vs propagated azimuth on one eye."""
    from scipy.stats import spearmanr

    from flyonenomics.substrate.retinotopy import r16_azimuths

    mask = (
        (np.asarray(sides) == side)
        & np.isfinite(coord)
        & np.isfinite(np.asarray(propagated_deg, dtype=np.float64))
    )
    n = int(np.count_nonzero(mask))
    if n < 3:
        return {"n": n, "rho": None, "passed": False}
    rank = r16_azimuths(np.asarray(sides)[mask], np.asarray(coord, dtype=np.float64)[mask])
    rho = float(spearmanr(rank, np.asarray(propagated_deg, dtype=np.float64)[mask]).statistic)
    ok = bool(np.isfinite(rho) and rho >= 0.9)
    return {"n": n, "rho": rho, "passed": ok}


def check_v0_b(
    l2_z: NDArray[np.floating],
    l2_sides: NDArray[np.str_],
    l2_propagated_deg: NDArray[np.floating],
    min_rho: float = 0.9,
    *,
    l2_xyz: NDArray[np.floating] | None = None,
) -> dict[str, Any]:
    """V0(b): record ρ vs z rank and vs each eye's first principal axis.

    SPEC-P2 question 15: if principal-axis ρ ≥ 0.9, V0(b) uses that axis.
    Otherwise V0(b) is recorded, not gating.
    """
    z_eyes: dict[str, dict[str, Any]] = {}
    pca_eyes: dict[str, dict[str, Any]] = {}
    pca_ok = l2_xyz is not None
    for side in ("left", "right"):
        z_eyes[side] = _spearman_rank_vs_prop(l2_sides, l2_z, l2_propagated_deg, side)
        z_eyes[side]["passed"] = bool(
            z_eyes[side]["rho"] is not None and z_eyes[side]["rho"] >= min_rho
        )
        if l2_xyz is None:
            continue
        idx = np.flatnonzero(np.asarray(l2_sides) == side)
        scores = np.full(len(l2_sides), np.nan, dtype=np.float64)
        meta = {"n": 0, "flipped": False, "explained_ratio": None}
        if idx.size:
            local, meta = principal_axis_scores(np.asarray(l2_xyz)[idx], np.asarray(l2_z, dtype=np.float64)[idx])
            scores[idx] = local
        pca_row = _spearman_rank_vs_prop(l2_sides, scores, l2_propagated_deg, side)
        pca_row["passed"] = bool(pca_row["rho"] is not None and pca_row["rho"] >= min_rho)
        pca_row["axis_n"] = meta["n"]
        pca_row["flipped"] = meta["flipped"]
        pca_row["explained_ratio"] = meta["explained_ratio"]
        pca_eyes[side] = pca_row
        pca_ok = pca_ok and pca_row["passed"]
    if l2_xyz is not None and pca_ok:
        axis_used = "principal_axis"
        gating = True
        passed = True
        recorded_not_gating = False
    elif l2_xyz is not None:
        axis_used = "recorded"
        gating = False
        passed = False
        recorded_not_gating = True
    else:
        axis_used = "z_rank"
        gating = True
        passed = bool(z_eyes["left"]["passed"] and z_eyes["right"]["passed"])
        recorded_not_gating = False
    return {
        "passed": passed,
        "gating": gating,
        "recorded_not_gating": recorded_not_gating,
        "axis_used": axis_used,
        "min_rho": min_rho,
        "z_rank": z_eyes,
        "principal_axis": pca_eyes,
    }


def check_v0_c(
    preferred_deg: NDArray[np.floating],
    stimuli: list[dict[str, float]],
    *,
    r_light: float,
    r_dark: float = PR_RATE_DARK_HZ,
    acceptance_deg: float = PR_ACCEPTANCE_DEG,
    r_max: float,
    kind: Literal["stripe", "ambient", "dark"] = "stripe",
    encoder: PhotoreceptorEncoder | None = None,
) -> dict[str, Any]:
    """V0(c): encoder rates equal the section 3.2 formula to relative error 1e-12."""
    bars = [(float(row["az_fly"]), float(row["width"]), float(row["contrast"])) for row in stimuli]
    formula = reference_section_32_rates(
        preferred_deg, bars, r_light=r_light, r_dark=r_dark,
        acceptance_deg=acceptance_deg, r_max=r_max, kind=kind,
    )
    if encoder is None:
        produced = photoreceptor_input_rates(
            preferred_deg, stimuli, r_light=r_light, r_dark=r_dark,
            acceptance_deg=acceptance_deg, r_max=r_max, kind=kind,
        )
    else:
        produced = encoder.rates(
            stimuli, enabled=kind != "dark", r_light=r_light, r_dark=r_dark,
            sigma_deg=acceptance_deg, maximum_hz=r_max, kind=kind,
        )
        produced = produced[encoder.positions]
    peak = float(np.max(np.abs(formula)))
    scale = peak if peak > 0 else 1.0
    relative = np.abs(produced - formula) / scale
    max_relative = float(relative.max()) if relative.size else 0.0
    return {
        "passed": bool(max_relative <= RELATIVE_ERROR),
        "max_relative_error": max_relative,
        "n": int(len(preferred_deg)),
        "r_light_hz": float(r_light),
        "kind": kind,
    }


def constructed_v0_c_case() -> dict[str, Any]:
    """One constructed heading and bar set for V0(c). Units: degrees, Hz."""
    preferred = np.array([-120.0, -45.0, -5.0, 5.0, 45.0, 120.0], dtype=np.float64)
    stimuli = [
        {"az_fly": 45.0, "width": 15.0, "contrast": 1.0},
        {"az_fly": -90.0, "width": 10.0, "contrast": 0.5},
    ]
    params = load_params()
    r_max = float(params.get("vis.r_max"))
    r_light = 150.0
    idx = np.arange(len(preferred), dtype=np.int32)
    registry = type("Registry", (), {
        "population": staticmethod(lambda name: type("Pop", (), {
            "idx": idx, "root_ids": np.arange(len(preferred), dtype=np.int64),
            "side": np.array(["left", "left", "left", "right", "right", "right"]),
        })()),
    })()
    encoder = PhotoreceptorEncoder(
        registry, idx, params, "R1_6", preferred=preferred, r_light=r_light,
    )
    stripe = check_v0_c(
        preferred, stimuli, r_light=r_light, r_max=r_max, encoder=encoder,
    )
    ambient = check_v0_c(
        preferred, [], r_light=r_light, r_max=r_max, kind="ambient", encoder=encoder,
    )
    off = check_v0_c(
        preferred, stimuli, r_light=r_light, r_max=r_max, kind="ambient", encoder=encoder,
    )
    dark = check_v0_c(
        preferred, stimuli, r_light=r_light, r_max=r_max, kind="dark", encoder=encoder,
    )
    return {
        "stripe": stripe,
        "ambient": ambient,
        "encoder_off_ambient": off,
        "dark": dark,
        "passed": bool(stripe["passed"] and ambient["passed"] and off["passed"] and dark["passed"]),
    }


def load_retinotopy_table(path: Path | None = None) -> dict[str, Any] | None:
    """Load WP14 retinotopy tables from populations-v0.2.yaml when present."""
    try:
        from flyonenomics.substrate.retinotopy import V02_PATH, load_retinotopy
    except ImportError:
        return None
    target = path or V02_PATH
    if not target.is_file():
        return None
    table = load_retinotopy(target)
    return table if isinstance(table, dict) else None


def _geometry_for_roots(root_ids: NDArray[np.int64]) -> tuple[NDArray[np.str_], NDArray[np.float64], NDArray[np.float64]]:
    """Join annotation side, pos_z and pos xyz onto committed root ids.

    Units: x and y are 4 nm voxel units; z is the 40 nm section index.
    Shapes: sides (n,), pos_z (n,), xyz (n, 3). Question 15 uses pos_* so
    the principal axis sits in the same lamina-terminal frame as the z rank.
    """
    import pandas as pd

    from flyonenomics.registry.annotations import load_annotations

    annotations = load_annotations("v2.1.0")
    indexed = annotations.drop_duplicates("root_id").set_index("root_id")
    rows = indexed.loc[list(int(v) for v in root_ids)]
    sides = rows["side"].fillna("").astype(str).to_numpy()
    pos = rows[["pos_x", "pos_y", "pos_z"]].apply(pd.to_numeric, errors="coerce")
    xyz = pos.to_numpy(dtype=np.float64)
    z_values = xyz[:, 2].copy()
    return sides, z_values, xyz


def _finite_azimuths(values: list[Any]) -> NDArray[np.float64]:
    """Parse a committed azimuth list that may hold nulls. Units: degrees."""
    return np.array([np.nan if v is None else float(v) for v in values], dtype=np.float64)


def verify_v0() -> ValidationEntry:
    """V0 verification: retinotopy monotone coverage and encoder formula. No engine."""
    constructed = constructed_v0_c_case()
    table = load_retinotopy_table()
    part_a: dict[str, Any]
    part_b: dict[str, Any]
    waiting: list[str] = []
    if table is None or "types" not in table:
        part_a = {"passed": False, "reason": "Waiting for WP14 populations-v0.2.yaml retinotopy table"}
        part_b = {"passed": False, "reason": "Waiting for WP14 propagated L2 azimuth"}
        waiting.extend(["WP14 populations-v0.2.yaml", "WP14 L2 retinotopy"])
    else:
        types = table["types"]
        r16 = types.get("R1_6")
        l2 = types.get("L2")
        if not isinstance(r16, dict) or "root_ids" not in r16 or "azimuth_deg" not in r16:
            part_a = {"passed": False, "reason": "R1_6 retinotopy block missing root_ids or azimuth_deg"}
            waiting.append("WP14 R1_6 retinotopy columns")
        else:
            sides, z_values, _xyz = _geometry_for_roots(np.asarray(r16["root_ids"], dtype=np.int64))
            part_a = check_v0_a(sides, z_values, _finite_azimuths(r16["azimuth_deg"]))
            part_a["sha256"] = table.get("sha256")
        if not isinstance(l2, dict) or "root_ids" not in l2 or "azimuth_deg" not in l2:
            part_b = {"passed": False, "reason": "L2 retinotopy block missing root_ids or azimuth_deg"}
            waiting.append("WP14 L2 retinotopy columns")
        else:
            sides, z_values, xyz = _geometry_for_roots(np.asarray(l2["root_ids"], dtype=np.int64))
            part_b = check_v0_b(
                z_values, sides, _finite_azimuths(l2["azimuth_deg"]), l2_xyz=xyz,
            )
            part_b["median_spread_deg"] = l2.get("median_spread_deg")
            part_b["n_with_azimuth"] = l2.get("n_with_azimuth")
            part_b["wp14_spearman_L2_vs_own_z"] = table.get("spearman_L2_vs_own_z")
    b_allows = bool(part_b.get("passed") or part_b.get("recorded_not_gating"))
    passed = bool(part_a.get("passed") and b_allows and constructed["passed"] and not waiting)
    if waiting and not passed:
        outcome: Literal["passed", "failed", "unavailable"] = "unavailable"
    else:
        outcome = "passed" if passed else "failed"
    return _entry(
        "V0", "verification", outcome,
        {
            "a": part_a,
            "b": part_b,
            "c": constructed,
            "waiting": waiting,
            "declared_substrate": declared_substrate(),
            "question_15": (
                "ρ recorded on z rank and on each eye's first principal axis of L2 "
                "positions, signed to agree with R1-6 z order. Principal-axis ρ ≥ 0.9 "
                "gates V0(b); otherwise V0(b) is recorded, not gating."
            ),
            "relative_error": RELATIVE_ERROR,
        },
        fixture=V0_FIXTURE, declared=True,
    )


def verify_v1() -> ValidationEntry:
    """V1 matching-layers propagation on item 122's declared substrate."""
    measured: dict[str, Any] = {
        "min_delta_hz": MIN_DELTA_HZ,
        "rates_hz": list(V_CAL_RATES_HZ),
        "rest_substrate": rest_substrate_available(),
        "declared_substrate": declared_substrate(),
        "declared_drive": declared_drive_present(),
    }
    if V1_RECORD.is_file():
        from flyonenomics.io import read_json

        record = read_json(V1_RECORD)
        measured["record"] = record
        if record["status"] == "unavailable":
            return _entry(
                "V1", "consistency", "unavailable", measured, fixture=V1_FIXTURE,
                compatibility="matching-layers", layers=MATCHING_LAYERS, declared=True,
            )
        return _entry(
            "V1", "consistency", "passed" if record.get("passed") else "failed", measured,
            fixture=V1_FIXTURE, compatibility="matching-layers", layers=MATCHING_LAYERS,
            declared=True, identity=record["identity"],
        )
    reason = []
    if not rest_substrate_available():
        reason.append("Waiting for WP14 retinotopy and WP15 rest-substrate plumbing")
    if not declared_substrate_present():
        reason.append("Waiting for item 122's declared substrate records")
    elif not declared_drive_present():
        reason.append("Waiting for the declared substrate drive data/drive-v0.2.yaml")
    else:
        reason.append("V1 engine execution on the declared substrate is not yet recorded")
    measured["reason"] = "; ".join(reason)
    return _entry(
        "V1", "consistency", "unavailable", measured,
        fixture=V1_FIXTURE, compatibility="matching-layers", layers=MATCHING_LAYERS,
        declared=True,
    )


def verify_v2() -> ValidationEntry:
    """V2 recorded L1 rise / Mi1 does-not on stripe blocks. Waits on V1 measurements."""
    return _entry(
        "V2", "consistency", "unavailable",
        {"reason": "Waiting for V1 stripe-block rates on the declared substrate"},
        fixture=V2_FIXTURE, compatibility="matching-layers", layers=MATCHING_LAYERS,
        declared=True,
    )


def verify_v3() -> ValidationEntry:
    """V3 ambient stability on item 122's declared substrate."""
    measured: dict[str, Any] = {"declared_substrate": declared_substrate()}
    if V3_RECORD.is_file():
        from flyonenomics.io import read_json

        record = read_json(V3_RECORD)
        measured["record"] = record
        return _entry(
            "V3", "consistency", "passed" if record.get("passed") else "failed", measured,
            fixture=V3_FIXTURE, compatibility="matching-layers", layers=MATCHING_LAYERS,
            declared=True, identity=record["identity"],
        )
    if not declared_substrate_present():
        reason = "Waiting for item 122's declared substrate records"
    elif not declared_drive_present():
        reason = "Waiting for the declared substrate drive data/drive-v0.2.yaml"
    else:
        reason = "V3 engine execution on the declared substrate is not yet recorded"
    measured["reason"] = reason
    return _entry(
        "V3", "consistency", "unavailable", measured,
        fixture=V3_FIXTURE, compatibility="matching-layers", layers=MATCHING_LAYERS,
        declared=True,
    )


def verify_vcal() -> ValidationEntry:
    """V-cal calibration outcome on item 122's declared substrate."""
    r3 = run_r3()
    outcome = run_vcal(r3)
    measured: dict[str, Any] = {
        "r3": r3,
        "vcal": outcome,
        "declared_substrate": declared_substrate(),
        "declared_drive": declared_drive_present(),
    }
    if VCAL_RECORD.is_file():
        from flyonenomics.io import read_json

        record = read_json(VCAL_RECORD)
        measured["record"] = record
        return _entry(
            "V-cal", "calibration", "passed" if record.get("status") == "passed" else "failed",
            measured, fixture=VCAL_FIXTURE, compatibility="matching-layers", layers=MATCHING_LAYERS,
            declared=True, identity=record["identity"],
        )
    return _entry(
        "V-cal", "calibration", "unavailable" if outcome["status"] != "passed" else "passed",
        measured, fixture=VCAL_FIXTURE, compatibility="matching-layers", layers=MATCHING_LAYERS,
        declared=True,
    )


SUITE: dict[str, Callable[[], ValidationEntry]] = {
    "V0": verify_v0,
    "V1": verify_v1,
    "V2": verify_v2,
    "V3": verify_v3,
    "V-cal": verify_vcal,
}

__all__ = [
    "SUITE",
    "check_v0_a",
    "check_v0_b",
    "check_v0_c",
    "constructed_v0_c_case",
    "principal_axis_scores",
    "reference_section_32_rates",
    "verify_v0",
    "verify_v1",
    "verify_v2",
    "verify_v3",
    "verify_vcal",
]
