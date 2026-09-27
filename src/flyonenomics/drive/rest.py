"""Phase 2 rest-substrate loaders (SPEC-P2 sections 2.5 and 8.1).

Runtime steering values come from the pinned behaviour file. Encoder
settings come from the pinned visual file, or from encoder-grid metadata
and params-v0.2.yaml. K-grid fixtures take sign and bias from committed
metadata and K_steer from the declared grid.

Units: rates Hz, speeds mm/s, angles degrees, gains deg/s per Hz.
Shapes: scalars and small lists; no neuron arrays.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from flyonenomics.io import read_bytes, read_yaml
from flyonenomics.types import Params, is_rest_drive, load_params, params_path_for_version

ROOT = Path(__file__).resolve().parents[3]
Controller = Literal["base", "closed_loop", "open_loop"]
K_STEER_GRID = (1.0, 2.0, 4.0, 8.0, 16.0)
# Declared encoder grids: V-cal and R3 rates with the V-cal extension (section 3.4), VT-cal (section 3.7).
R_LIGHT_GRID = (10.0, 25.0, 50.0, 100.0, 150.0, 300.0)
R_VIS_MAX_GRID = (40.0, 70.0, 100.0, 150.0, 280.0)
ENCODER_GRID_KEYS = frozenset(("r_light", "r_vis_max"))


@dataclass(frozen=True)
class VisualSettings:
    """Resolved visual encoder settings. Units: Hz and degrees. Shapes: scalars."""

    inject_at: str
    r_light: float | None = None
    r_dark: float = 0.0
    pr_acceptance_deg: float = 5.0
    r_vis_max: float | None = None
    sigma_vis: float | None = None
    blob_id: str | None = None
    source: str = "params"


@dataclass(frozen=True)
class BehaviourSettings:
    """Resolved steering settings. Units: mm/s, Hz, deg/s per Hz. Shapes: scalars."""

    v_fwd: float
    step_min_mm: float
    r_max_hz: float
    sign_steer: int | None
    bias_hz: float
    K_steer: float | None
    controller: Controller
    visual_blob_id: str | None = None
    kind: str = "base-v0.2"
    r_vis_max: float | None = None
    sigma_vis: float | None = None
    r_light: float | None = None


@dataclass(frozen=True)
class ResolvedRun:
    """Params, visual and behaviour objects for one experiment. Units per field."""

    params: Params
    visual: VisualSettings
    behaviour: BehaviourSettings


def _finite(name: str, value: Any) -> float:
    """Require a finite numeric value. Units: per caller. Shapes: scalar."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"missing or non-finite runtime value: {name}")
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"missing or non-finite runtime value: {name}")
    return number


def _optional_finite(name: str, value: Any) -> float | None:
    """Return a finite number or None. Units: per caller. Shapes: scalar."""
    if value is None:
        return None
    return _finite(name, value)


def blob_id(path: str | Path) -> str:
    """Return the git blob id of one file's bytes (section 8.1). Units: none. Shapes: one hex."""
    import hashlib

    data = read_bytes(path)
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _sign(value: Any) -> int:
    """Require sign_steer to be exactly +1 or -1. Units: none. Shapes: scalar."""
    number = _finite("sign_steer", value)
    if number not in (-1.0, 1.0):
        raise ValueError("sign_steer must be +1 or -1")
    return int(number)


def load_params_version(version: str, root: Path = ROOT) -> Params:
    """Load params-v0.1.yaml or params-v0.2.yaml. Units: per YAML row."""
    path = root / "data" / f"params-{version}.yaml"
    if not path.is_file():
        path = params_path_for_version(version)
    return load_params(path)


def load_dopamine_v02(path: str | Path, compartment_names: list[str]) -> dict[str, Any]:
    """Load dopamine-v0.2.yaml and check compartment order. Units: µM and µM/s."""
    record = read_yaml(path) or {}
    if record.get("calibration_status") == "unset":
        raise ValueError("dopamine calibration is unset")
    names = record.get("compartments")
    if names != compartment_names:
        raise ValueError("dopamine table compartment order does not match registry")
    for key in ("R_c", "alpha_c", "S_c"):
        values = record.get(key)
        if not isinstance(values, list) or len(values) != len(compartment_names):
            raise ValueError(f"dopamine {key} must match registry compartment order")
        if any(item is None for item in values):
            raise ValueError(f"dopamine {key} is unset")
        if any(not np.isfinite(float(item)) or float(item) < 0 for item in values):
            raise ValueError(f"dopamine {key} must be finite and nonnegative")
    # Historical records without mode still load; an explicit null is never
    # a calibrated mode. The separately versioned male table requires it.
    if "mode" in record or record.get("version") == "male-cns-v1.0":
        modes = record.get("mode")
        if (not isinstance(modes, list) or len(modes) != len(compartment_names)
                or any(mode not in ("source", "derived") for mode in modes)):
            raise ValueError("dopamine mode must be source or derived in registry order")
    male_markers = (
        record.get("version") == "male-cns-v1.0",
        record.get("receptor_map_version") == "male-cns-v1.0",
        record.get("connectome_version") == "male-cns:v1.0",
    )
    if any(male_markers):
        expected = {
            "version": "male-cns-v1.0",
            "params_version": "v0.2",
            "receptor_map_version": "male-cns-v1.0",
            "connectome_version": "male-cns:v1.0",
        }
        for key, value in expected.items():
            if record.get(key) != value:
                raise ValueError(f"dopamine {key} must be {value}")
        if not record.get("drive_blob_id"):
            raise ValueError("dopamine drive_blob_id is unset")
        constants = record.get("constants")
        if not isinstance(constants, dict):
            raise ValueError("dopamine constants are unset")
        params = load_params_version("v0.2")
        for key in ("DA_ref", "Vmax", "Km", "k_ns", "R_min", "alpha_max"):
            if _finite(f"dopamine.constants.{key}", constants.get(key)) != float(params.get(f"da.{key}")):
                raise ValueError(f"dopamine constant {key} differs from params-v0.2")
    return record


def load_visual_v02(path: str | Path | None, params: Params, *, meta: dict[str, Any] | None = None) -> VisualSettings:
    """Resolve encoder settings from a visual file or encoder-grid metadata.

    Units: Hz and degrees. Shapes: scalars. Encoder-grid fixtures pin no visual
    file and supply r_light or r_vis_max in metadata.
    """
    meta = meta or {}
    if path is None:
        if "r_light" in meta or "r_vis_max" in meta:
            if "r_light" in meta and "r_vis_max" in meta:
                raise ValueError("encoder-grid fixture supplies r_light or r_vis_max, not both")
            key, grid = ("r_light", R_LIGHT_GRID) if "r_light" in meta else ("r_vis_max", R_VIS_MAX_GRID)
            if _finite(key, meta[key]) not in grid:
                raise ValueError("grid value outside its fixture's declared grid")
            if "r_light" in meta:
                return VisualSettings(
                    inject_at="photoreceptors",
                    r_light=_finite("r_light", meta["r_light"]),
                    r_dark=float(params.get("vis.pr_rate_dark_hz")),
                    pr_acceptance_deg=float(params.get("vis.pr_acceptance_deg")),
                    source="encoder-grid",
                )
            return VisualSettings(
                inject_at="TuBu",
                r_vis_max=_finite("r_vis_max", meta["r_vis_max"]),
                sigma_vis=float(params.get("vis.sigma_vis")),
                r_dark=float(params.get("vis.pr_rate_dark_hz")),
                pr_acceptance_deg=float(params.get("vis.pr_acceptance_deg")),
                source="encoder-grid",
            )
        return VisualSettings(
            inject_at=str(params.get("vis.inject_at")),
            r_dark=float(params.get("vis.pr_rate_dark_hz")),
            pr_acceptance_deg=float(params.get("vis.pr_acceptance_deg")),
            r_vis_max=float(params.get("vis.r_vis_max")),
            sigma_vis=float(params.get("vis.sigma_vis")),
            source="params",
        )
    record = read_yaml(path) or {}
    inject = record.get("inject_at", params.get("vis.inject_at"))
    if inject not in ("TuBu", "ER", "photoreceptors"):
        raise ValueError("inject_at must be TuBu, ER or photoreceptors")
    # Sections 3.2 and 3.7: each encoder's settings come only from the visual file.
    present = {"r_light": record.get("r_light", record.get("r_light_hz")),
               "r_vis_max": record.get("r_vis_max"), "sigma_vis": record.get("sigma_vis")}
    required = ("r_light",) if inject == "photoreceptors" else ("r_vis_max", "sigma_vis")
    missing = [key for key in required if present[key] is None]
    if missing:
        raise ValueError(f"visual file with inject_at {inject} lacks {', '.join(missing)}")
    return VisualSettings(
        inject_at=str(inject),
        r_light=_optional_finite("r_light", record.get("r_light", record.get("r_light_hz"))),
        r_dark=_finite("r_dark", record.get("r_dark", record.get("r_dark_hz", params.get("vis.pr_rate_dark_hz")))),
        pr_acceptance_deg=_finite(
            "pr_acceptance_deg",
            record.get("pr_acceptance_deg", params.get("vis.pr_acceptance_deg")),
        ),
        r_vis_max=_optional_finite("r_vis_max", record.get("r_vis_max")),
        sigma_vis=_optional_finite("sigma_vis", record.get("sigma_vis")),
        blob_id=blob_id(path),
        source="file",
    )


def _behaviour_kind(version: str, record: dict[str, Any], *, k_grid: bool, encoder_grid: bool) -> str:
    """Name the loader branch. Units: none. Shapes: one token."""
    if encoder_grid:
        return "encoder-grid"
    if k_grid:
        return "k-grid"
    if version == "base-v0.2":
        return "base-v0.2"
    controller = record.get("controller")
    if controller == "open_loop":
        return "open_loop"
    if controller == "closed_loop":
        return "closed_loop"
    return version


def load_behaviour_v02(
    path: str | Path,
    params: Params,
    *,
    version: str,
    visual: VisualSettings,
    visual_path: str | Path | None,
    assays: set[str],
    meta: dict[str, Any] | None = None,
    grid: dict[str, Any] | None = None,
    k_grid: bool = False,
    encoder_grid: bool = False,
) -> BehaviourSettings:
    """Load a v0.2 behaviour pin with the section 8.1 checks. Units: mm/s, Hz."""
    meta = dict(meta or {})
    grid = dict(grid or {})
    record = read_yaml(path) or {}
    kind = _behaviour_kind(version, record, k_grid=k_grid, encoder_grid=encoder_grid)
    if encoder_grid:
        if visual_path is not None:
            raise ValueError("encoder-grid fixture must not pin a visual file")
        if "buridan" in assays:
            raise ValueError("encoder-grid fixture must not contain a Buridan probe")
        runtime = {
            "v_fwd": _finite("v_fwd_mm_s", record.get("v_fwd_mm_s")),
            "step_min_mm": _finite("step_min_mm", record.get("step_min_mm")),
            "r_max_hz": _finite("r_max_hz", record.get("r_max_hz")),
        }
        return BehaviourSettings(
            v_fwd=runtime["v_fwd"],
            step_min_mm=runtime["step_min_mm"],
            r_max_hz=runtime["r_max_hz"],
            sign_steer=None,
            bias_hz=0.0,
            K_steer=None,
            controller="base",
            kind=kind,
            r_vis_max=visual.r_vis_max,
            sigma_vis=visual.sigma_vis,
            r_light=visual.r_light,
        )
    runtime = {
        "v_fwd": _finite("v_fwd_mm_s", record.get("v_fwd_mm_s")),
        "step_min_mm": _finite("step_min_mm", record.get("step_min_mm")),
        "r_max_hz": _finite("r_max_hz", record.get("r_max_hz")),
    }
    if k_grid:
        if version != "base-v0.2":
            raise ValueError("K-grid fixture must pin base-v0.2")
        if visual_path is None or visual.blob_id is None:
            raise ValueError("K-grid fixture requires a visual pin")
        # sign_steer and bias_hz come from the fixture's committed metadata only.
        sign = meta.get("sign_steer")
        bias = meta.get("bias_hz")
        if sign is None or bias is None:
            raise ValueError("K-grid fixture requires sign_steer and bias_hz metadata")
        sign_i = _sign(sign)
        if set(grid) - {"K_steer"}:
            raise ValueError("K-grid fixture may grid only K_steer")
        if "K_steer" not in grid:
            raise ValueError("K-grid fixture requires a K_steer grid point")
        k_value = _finite("K_steer", grid["K_steer"])
        declared = record.get("grid", {}).get("K_steer", list(K_STEER_GRID))
        if k_value not in {float(item) for item in declared}:
            raise ValueError("grid value outside its fixture's declared grid")
        recorded_blob = meta.get("visual")
        if recorded_blob is None:
            raise ValueError("K-grid fixture requires the visual blob id in its metadata")
        if str(recorded_blob) != visual.blob_id:
            raise ValueError("K-grid visual blob id differs from the pinned visual file")
        return BehaviourSettings(
            v_fwd=runtime["v_fwd"],
            step_min_mm=runtime["step_min_mm"],
            r_max_hz=runtime["r_max_hz"],
            sign_steer=sign_i,
            bias_hz=_finite("bias_hz", bias),
            K_steer=k_value,
            controller="closed_loop",
            visual_blob_id=visual.blob_id,
            kind=kind,
            r_vis_max=visual.r_vis_max,
            sigma_vis=visual.sigma_vis,
            r_light=visual.r_light,
        )
    recorded_blob = record.get("visual")
    if version != "base-v0.2":
        # behaviour-v0.2.yaml takes encoder settings only from the pinned visual file.
        if visual_path is None or visual.blob_id is None:
            raise ValueError("behaviour-v0.2 requires a visual pin")
        if recorded_blob is None:
            raise ValueError("behaviour-v0.2 requires the visual blob id")
    if recorded_blob is not None:
        if visual.blob_id is None or str(recorded_blob) != visual.blob_id:
            raise ValueError("behaviour visual blob id differs from the pinned visual file")
    controller = record.get("controller", "base" if version == "base-v0.2" else None)
    if controller not in ("base", "closed_loop", "open_loop", None):
        raise ValueError("unknown behaviour controller")
    if controller is None:
        controller = "closed_loop" if record.get("K_steer") is not None else "base"
    if version == "base-v0.2" or controller == "open_loop":
        if "buridan" in assays and not k_grid:
            raise ValueError("Buridan probes require a closed-loop behaviour file or a K-grid fixture")
    sign = record.get("sign_steer")
    k_steer = record.get("K_steer")
    if version == "base-v0.2":
        bias = record.get("bias_hz", 0.0)
    else:
        bias = _finite("bias_hz", record.get("bias_hz"))
    if controller == "closed_loop":
        sign_i = _sign(sign)
        k_value: float | None = _finite("K_steer", k_steer)
    else:
        sign_i = None if sign is None else _sign(sign)
        k_value = None if k_steer is None else _finite("K_steer", k_steer)
        if controller == "open_loop":
            sign_i = None
            k_value = None
    return BehaviourSettings(
        v_fwd=runtime["v_fwd"],
        step_min_mm=runtime["step_min_mm"],
        r_max_hz=runtime["r_max_hz"],
        sign_steer=sign_i,
        bias_hz=_finite("bias_hz", bias) if bias is not None else 0.0,
        K_steer=k_value,
        controller=controller if controller != "base" else "base",
        visual_blob_id=visual.blob_id if visual.blob_id else (None if recorded_blob is None else str(recorded_blob)),
        kind=kind,
        r_vis_max=visual.r_vis_max,
        sigma_vis=visual.sigma_vis,
        r_light=visual.r_light,
    )


def resolve_configurations(
    *,
    params: Params,
    behaviour_path: str | Path,
    behaviour_version: str,
    assays: set[str],
    visual_path: str | Path | None = None,
    meta: dict[str, Any] | None = None,
    grid: dict[str, Any] | None = None,
    k_grid: bool = False,
    encoder_grid: bool = False,
) -> ResolvedRun:
    """Build params, visual and behaviour objects. Units: per field. Shapes: scalars."""
    visual = load_visual_v02(visual_path, params, meta=meta)
    behaviour = load_behaviour_v02(
        behaviour_path, params, version=behaviour_version, visual=visual,
        visual_path=visual_path, assays=assays, meta=meta, grid=grid,
        k_grid=k_grid, encoder_grid=encoder_grid,
    )
    return ResolvedRun(params=params, visual=visual, behaviour=behaviour)


def behaviour_dict(settings: BehaviourSettings) -> dict[str, float | int]:
    """Adapter dict for the Phase 1 Behaviour constructor. Units: mm/s, Hz, degrees."""
    sign = 1 if settings.sign_steer is None else int(settings.sign_steer)
    k_steer = 0.0 if settings.K_steer is None else float(settings.K_steer)
    r_vis = settings.r_vis_max
    if r_vis is None:
        if settings.r_light is None:
            raise ValueError("behaviour settings carry neither r_vis_max nor r_light")
        r_vis = settings.r_light
    sigma = settings.sigma_vis if settings.sigma_vis is not None else 20.0
    return {
        "v_fwd": settings.v_fwd,
        "sign_steer": sign,
        "K_steer": k_steer,
        "r_vis_max": float(r_vis),
        "sigma_vis": float(sigma),
        "bias_hz": float(settings.bias_hz),
    }


THRESHOLD_Z_LIMIT = 2.0
DRIVE_SECTIONS = ("transmitter_rule", "scales", "background", "threshold", "optic_exemption", "provenance")
DRIVE_OPTIONAL = ("mechanisms", "version", "configuration_class")
DRIVE_DEVELOPMENT = ("candidate_id", "selection", "note")


def load_drive_rest(path: str | Path) -> dict[str, Any]:
    """Load drive-v0.2.yaml in the section 2.5 structure. Units: ratios, mV, Hz.

    Sections: `transmitter_rule` {blob_id, scope}; `scales` {g_gaba, g_glu,
    g_his, unk, sha256}; `background` {n_bg, r_bg, groups: {name: {size,
    w_bg}}}; `threshold` {sigma_th, seed, z_sha256} or null;
    `optic_exemption`; `provenance`. The file carries no qualification flag.
    Shapes: scalars and one group mapping.
    """
    record = read_yaml(path) or {}
    if not isinstance(record, dict):
        raise ValueError("drive configuration must be a mapping")
    if record.get("calibration_status") == "unset":
        raise ValueError("drive calibration is unset")
    missing = [key for key in DRIVE_SECTIONS if key not in record]
    if missing:
        raise ValueError(f"drive configuration misses sections: {', '.join(missing)}")
    if "qualified" in record:
        raise ValueError("drive configuration must not carry a qualified field (section 2.5)")
    allowed = set(DRIVE_SECTIONS) | set(DRIVE_OPTIONAL) | set(DRIVE_DEVELOPMENT)
    unknown = [key for key in record if key not in allowed]
    if unknown:
        raise ValueError(f"unknown top-level key: {unknown[0]}")
    if "version" in record and record["version"] not in ("v0.2", "male-cns-v1.0"):
        raise ValueError("drive version must be v0.2 or male-cns-v1.0")
    if "configuration_class" in record and record["configuration_class"] != "development":
        raise ValueError("configuration_class must be development")
    if any(key in record for key in DRIVE_DEVELOPMENT) and record.get("configuration_class") != "development":
        raise ValueError("candidate_id, selection and note require configuration_class development")
    from flyonenomics.drive.mechanisms import parse_mechanisms_section

    mechanisms = parse_mechanisms_section(record["mechanisms"]) if "mechanisms" in record else None
    rule = record["transmitter_rule"] or {}
    scope = rule.get("scope")
    if scope not in ("brain", "optic_sensory"):
        raise ValueError("drive transmitter_rule.scope must be brain or optic_sensory")
    if not rule.get("blob_id"):
        raise ValueError("drive transmitter_rule.blob_id is required")
    scales = record["scales"] or {}
    if record.get("version") == "male-cns-v1.0":
        if not scales.get("sha256"):
            raise ValueError("drive scales.sha256 is unset")
        if "g_gaba_kc" not in scales:
            raise ValueError("drive.g_gaba_kc is unset")
        if scales.get("unk") != "positive:1; negative:g_gaba":
            raise ValueError("drive scales.unk differs from the MaleCNS sign rule")
        if "mechanisms" not in record:
            raise ValueError("drive mechanisms must explicitly state the selected mechanism or null for lif")
        provenance = record.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("connectome_version") != "male-cns:v1.0":
            raise ValueError("drive provenance must bind male-cns:v1.0")
        for key in ("record", "record_sha256", "inputs_record_sha256"):
            if not provenance.get(key):
                raise ValueError(f"drive provenance.{key} is unset")
    g_his = _finite("drive.g_his", scales.get("g_his"))
    if g_his != 1.0:
        raise ValueError("drive.g_his stays 1 (section 2.2.1)")
    if "g_gaba_kc" not in scales:
        # Historical pre-WP26 drive records omitted this field and mean 1.
        g_gaba_kc = 1.0
    else:
        # An explicit null is an uncalibrated value, not the historical
        # omission and never a silent factor of one.
        g_gaba_kc = _finite("drive.g_gaba_kc", scales["g_gaba_kc"])
        if g_gaba_kc < 1:
            raise ValueError("drive.g_gaba_kc must be at least 1")
    threshold = record["threshold"]
    if threshold is None:
        sigma_th, seed, z_sha = 0.0, None, None
    else:
        sigma_th = _finite("drive.sigma_th", threshold.get("sigma_th"))
        if sigma_th < 0:
            raise ValueError("drive.sigma_th must be nonnegative")
        seed_value = threshold.get("seed")
        if isinstance(seed_value, bool) or not isinstance(seed_value, int):
            raise ValueError("drive.seed must be an integer")
        seed, z_sha = int(seed_value), threshold.get("z_sha256")
        if sigma_th > 0 and not z_sha:
            raise ValueError("drive threshold.z_sha256 is required when sigma_th > 0")
    background = record["background"] or {}
    groups = background.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise ValueError("drive background.groups must be a non-empty mapping")
    weights = {str(name): _finite(f"drive.w_bg[{name}]", (row or {}).get("w_bg")) for name, row in groups.items()}
    if record.get("version") == "male-cns-v1.0":
        for name, row in groups.items():
            size = (row or {}).get("size")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise ValueError(f"drive background group {name} has an invalid size")
    optic = record["optic_exemption"]
    if not isinstance(optic, bool):
        raise ValueError("drive optic_exemption must be true or false")
    return {
        "g_glu": _finite("drive.g_glu", scales.get("g_glu")),
        "g_gaba": _finite("drive.g_gaba", scales.get("g_gaba")),
        "g_gaba_kc": g_gaba_kc,
        "g_his": g_his,
        "scale_sha256": scales.get("sha256"),
        "scope": scope,
        "transmitters_blob_id": str(rule["blob_id"]),
        "optic_exemption": optic,
        "sigma_th": sigma_th,
        "seed": seed,
        "z_sha256": z_sha,
        "n_bg": _finite("drive.n_bg", background.get("n_bg")),
        "r_bg": _finite("drive.r_bg", background.get("r_bg")),
        "w_bg": weights,
        "mechanisms": mechanisms,
        "raw": record,
    }


def draw_threshold_z(seed: int, n: int) -> NDArray[np.float64]:
    """z_i from N(0, 1) truncated to ±2 by redrawing, DRIVE stream. Units: none. Shapes: (n,)."""
    from flyonenomics.types import DRIVE

    rng = np.random.default_rng(np.random.SeedSequence(int(seed), spawn_key=(0, 0, DRIVE)))
    z = rng.standard_normal(int(n))
    outside = np.flatnonzero(np.abs(z) > THRESHOLD_Z_LIMIT)
    while outside.size:
        z[outside] = rng.standard_normal(outside.size)
        outside = outside[np.abs(z[outside]) > THRESHOLD_Z_LIMIT]
    return z


def z_sha256(z: NDArray[np.floating]) -> str:
    """SHA-256 of the float32 z array (section 2.2.3). Units: none. Shapes: one hex."""
    import hashlib

    return hashlib.sha256(np.ascontiguousarray(np.asarray(z, dtype=np.float32)).tobytes()).hexdigest()


@lru_cache(maxsize=1)
def kc_mask_in_engine() -> NDArray[np.uint8]:
    """uint8 KC mask in v783 engine order from annotations (SPEC-P2 2.2.4 3d).

    `annotations_in_engine` is the checksummed artefact path. `cell_class`
    `Kenyon_Cell` is the same selector as population KC. Connectome post
    indices used with this mask are loaded through `flyonenomics.io`.
    Units: none. Shapes: (engine.n,) uint8.
    """
    from flyonenomics.substrate.transmitters import annotations_in_engine

    frame, _order = annotations_in_engine()
    return np.asarray(
        frame["cell_class"].fillna("").to_numpy(dtype=str) == "Kenyon_Cell",
        dtype=np.uint8,
    )


def rest_background_weights(registry: Any, drive: dict[str, Any], params: Params) -> NDArray[np.float64]:
    """Expand drive-v0.2 group weights onto neurons. Units: mV. Shapes: (registry.n,).

    The engine draws n_bg inputs at r_bg from params, so the file's values
    must equal the pinned params rows.
    """
    from flyonenomics.drive.background import group_indices

    for key in ("n_bg", "r_bg"):
        if float(drive[key]) != float(params.get(f"bg.{key}")):
            raise ValueError(f"drive background.{key} differs from params bg.{key}")
    indices = group_indices(registry)
    if set(indices) != set(drive["w_bg"]):
        raise ValueError("drive groups do not match registry")
    weights = np.zeros(registry.n, dtype=np.float64)
    for name, idx in indices.items():
        weights[idx] = float(drive["w_bg"][name])
    return weights


def apply_rest_substrate(
    engine: Any,
    params: Params,
    drive: dict[str, Any],
    *,
    classes: np.ndarray | None = None,
    s_pq: np.ndarray | None = None,
    pre: np.ndarray | None = None,
    post: np.ndarray | None = None,
    kc_mask: np.ndarray | None = None,
    n: int | None = None,
    super_class: np.ndarray | None = None,
    connectome_version: str = "783",
    thresholds: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply transmitter scales and draw per-neuron base thresholds.

    Units: scales dimensionless, thresholds mV. Shapes: scale (n_syn,),
    base_v_th (n,). Arrays follow connection-file / engine order. thresholds
    False (the section 8.1 feed-forward fixture) returns lif.v_th everywhere.
    """
    from flyonenomics.drive.mechanisms import engine_model_of
    from flyonenomics.substrate.scales import scale_array

    if "mechanisms" not in drive:
        raise ValueError("drive mapping must state mechanisms")
    if hasattr(engine, "engine_model") and callable(engine.engine_model):
        expected = engine_model_of(drive.get("mechanisms"))
        got = engine.engine_model()
        if got != expected:
            raise ValueError(
                f"engine_model {got} differs from drive mechanisms ({expected})"
            )

    if classes is None or s_pq is None or pre is None:
        from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
        from flyonenomics.substrate.transmitters import DEFAULT_TRANSMITTERS_PATH, load_connection_columns, load_transmitters
        from flyonenomics.validation.binding import blob_id as git_blob_id

        transmitters = load_transmitters()
        if str(transmitters["connectome_version"]) != str(connectome_version):
            raise ValueError("transmitters file connectome version differs from the engine")
        if drive.get("scope") is not None and drive["scope"] != transmitters["scope"]:
            raise ValueError("drive transmitter_rule.scope differs from the transmitters file")
        if drive.get("transmitters_blob_id") is not None:
            if git_blob_id(ROOT, str(DEFAULT_TRANSMITTERS_PATH.relative_to(ROOT))) != drive["transmitters_blob_id"]:
                raise ValueError("drive transmitter_rule.blob_id differs from the transmitters file")
        classes = transmitters["class_array"]
        completeness, connectivity = connectome_source_paths(connectome_version)
        _roots, i_pre, j_post, _weights = load_connectome_arrays(completeness, connectivity)
        table = load_connection_columns(("Excitatory",))
        s_pq = np.sign(np.asarray(table.column("Excitatory").to_numpy(), dtype=np.float64))
        pre = np.asarray(i_pre, dtype=np.int32)
        if post is None:
            post = np.asarray(j_post, dtype=np.int32)
        del _roots, _weights
    classes = np.asarray(classes)
    s_pq = np.asarray(s_pq, dtype=np.float64)
    pre = np.asarray(pre, dtype=np.int32)
    neurons = int(n if n is not None else getattr(engine, "n", classes.shape[0]))
    optic = bool(drive.get("optic_exemption", False))
    if optic and super_class is None:
        from flyonenomics.substrate.transmitters import annotations_in_engine

        frame, _order = annotations_in_engine()
        super_class = frame["super_class"].fillna("").to_numpy(dtype=str)
    g_kc = float(drive.get("g_gaba_kc", 1.0))
    if g_kc != 1.0:
        if post is None:
            raise ValueError("g_gaba_kc other than 1 requires post")
        post = np.asarray(post, dtype=np.int32)
        if kc_mask is None:
            kc_mask = kc_mask_in_engine()
    scale = scale_array(
        classes, s_pq, pre,
        float(drive["g_glu"]), float(drive["g_gaba"]),
        g_his=float(drive.get("g_his", 1.0)),
        optic_exemption=optic,
        super_class=super_class,
        g_gaba_kc=g_kc,
        post=None if post is None else np.asarray(post, dtype=np.int32),
        kc_mask=None if kc_mask is None else np.asarray(kc_mask),
    )
    expected_scale = drive.get("scale_sha256")
    if expected_scale:
        import hashlib

        if hashlib.sha256(np.ascontiguousarray(scale, dtype=np.float32).tobytes()).hexdigest() != expected_scale:
            raise ValueError("scale array SHA-256 differs from drive scales.sha256")
    engine.set_weight_scale(scale)
    v_th = float(params.get("lif.v_th"))
    sigma = float(drive.get("sigma_th", 0.0) or 0.0)
    if not thresholds or sigma == 0.0:
        return np.full(neurons, v_th, dtype=np.float64), scale
    z_i = draw_threshold_z(int(drive["seed"]), neurons)
    expected_z = drive.get("z_sha256")
    if expected_z and z_sha256(z_i) != expected_z:
        raise ValueError("threshold z SHA-256 differs from drive threshold.z_sha256")
    base = np.asarray(v_th + sigma * z_i, dtype=np.float64)
    return base, scale
