"""Probe-local visual and arena behaviour factory."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from flyonenomics.behaviour.arena import Behaviour
from flyonenomics.orchestrator.stubs import IdentityBehaviour
from flyonenomics.schema.experiment import Probe
from flyonenomics.types import Params


def encoder_class_for(inject_at: str) -> type:
    """Return the encoder class for a resolved inject_at. Units: none.

    photoreceptors needs `behaviour.encoder.PhotoreceptorEncoder` (WP18), built
    like VisualEncoder and called as rates(stimuli, enabled=..., lit=...).
    """
    from flyonenomics.behaviour.encoder import VisualEncoder
    import flyonenomics.behaviour.encoder as encoder_mod

    if inject_at == "photoreceptors":
        encoder = getattr(encoder_mod, "PhotoreceptorEncoder", None)
        if encoder is None:
            # A TuBu encoder on R1_6 would silently run a different visual path.
            raise ValueError("inject_at photoreceptors requires PhotoreceptorEncoder (WP18)")
        return encoder
    return VisualEncoder

ROOT = Path(__file__).resolve().parents[3]


def load_settings(
    version: str,
    params: Params,
    overrides: dict[str, Any] | None = None,
    *,
    visual_path: str | Path | None = None,
    assays: set[str] | None = None,
    meta: dict[str, Any] | None = None,
    grid: dict[str, Any] | None = None,
    k_grid: bool = False,
    encoder_grid: bool = False,
) -> dict[str, float | int]:
    """Resolve a pinned behaviour file; speeds mm/s, rates Hz, angles degrees.

    Calibration candidates are explicit experiment metadata, never ambient
    process state. No runtime path opens the holdout-bearing reference file.
    v0.2 pins go through drive.rest loaders (SPEC-P2 section 8.1).
    """
    if version in ("base-v0.2", "v0.2"):
        from flyonenomics.drive.rest import behaviour_dict, resolve_configurations

        resolved = resolve_configurations(
            params=params,
            behaviour_path=ROOT / "data" / f"behaviour-{version}.yaml",
            behaviour_version=version,
            assays=assays or set(),
            visual_path=visual_path,
            meta=meta,
            grid=grid,
            k_grid=k_grid,
            encoder_grid=encoder_grid,
        )
        values = behaviour_dict(resolved.behaviour)
        if overrides:
            raise ValueError("behaviour overrides require behaviour_version=dev")
        return values
    path = ROOT / "data" / f"behaviour-{version}.yaml"
    if not path.is_file():
        raise ValueError(f"behaviour requested: missing pin {path.name}")
    from flyonenomics.io import read_yaml

    record = read_yaml(path) or {}
    if version == "dev" and (record.get("class") != "development" or record.get("provisional") is not True):
        raise ValueError("behaviour-dev.yaml must be provisional development")
    if overrides and version != "dev":
        raise ValueError("behaviour overrides require behaviour_version=dev")
    selected = record.get("selected", {})
    values = {"v_fwd": record.get("v_fwd_mm_s"),
              "sign_steer": record.get("sign_steer", params.get("steer.sign_steer")),
              "K_steer": selected.get("K_steer", params.get("steer.K_steer")),
              "r_vis_max": selected.get("r_vis_max", params.get("vis.r_vis_max")),
              "sigma_vis": selected.get("sigma_vis", params.get("vis.sigma_vis"))}
    if overrides:
        if set(overrides) - values.keys():
            raise ValueError("unknown behaviour override")
        values.update(overrides)
    for key, value in values.items():
        if isinstance(value, bool) or value is None or not np.isfinite(float(value)):
            raise ValueError(f"behaviour {key} must be finite")
        values[key] = float(value)
    if values["sign_steer"] not in (-1, 1):
        raise ValueError("sign_steer must be -1 or +1")
    if any(values[k] <= 0 for k in ("v_fwd", "sigma_vis")) or any(values[k] < 0 for k in ("K_steer", "r_vis_max")):
        raise ValueError("behaviour speed/sigma must be positive and gain/rate nonnegative")
    values["sign_steer"] = int(values["sign_steer"])
    return values


def make_behaviour(plan: Any, registry: Any, params: Params, probe: Probe) -> Behaviour | IdentityBehaviour:
    """Build one probe-local arena; mm/s speed, degrees/Hz gains, Hz rates (n_extended,)."""
    if probe.assay not in ("buridan", "open_loop_steering"):
        return IdentityBehaviour(len(plan.topology.extended_idx))
    values = getattr(plan, "behaviour_settings", None)
    if values is None:
        raise ValueError("behaviour settings must be resolved from the experiment pin before building")
    return Behaviour(plan, registry, params, probe, **values)
