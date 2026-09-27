"""Construct Phase 1 components and use WP6's probe-local behaviour factory."""
from __future__ import annotations

import importlib
from typing import Any

from flyonenomics.neuromod import Neuromod
from flyonenomics.orchestrator.stubs import IdentityBehaviour
from flyonenomics.schema.experiment import Probe
from flyonenomics.types import LayerFlags, Params


def make_neuromod(registry: Any, params: Params, layers: LayerFlags, dopamine_table: dict[str, Any],
                  *, base_v_th: Any = None, schema_version: str = "1.2",
                  drive_groups: dict[str, Any] | None = None) -> Neuromod:
    """Create a pool model; arrays (n,) and (n_comp,), dopamine in µM.

    schema_version names the settle rule; drive_groups maps group names to
    int32 indices (m,) and joins the schema 1.3 decision candidates.
    """
    return Neuromod(registry, params, layers, dopamine_table, base_v_th=base_v_th,
                    schema_version=schema_version, drive_groups=drive_groups)


def make_behaviour(plan: Any, registry: Any, params: Params, probe: Probe) -> Any:
    """Create one probe arena; encoder Hz (n_extended,), positions mm."""
    try:
        module = importlib.import_module("flyonenomics.behaviour")
    except ModuleNotFoundError as exc:
        if exc.name != "flyonenomics.behaviour":
            raise
        return IdentityBehaviour(len(plan.topology.extended_idx))
    return module.make_behaviour(plan, registry, params, probe)


def active_stubs(assays: list[str]) -> list[str]:
    """List identities used for these assays; names, one entry per component.

    IdentityBehaviour on sugar_reflex or spontaneous is a no-op arena, not a
    stub of the behaviour component. The component is stubbed only when a
    behaviour assay would run without the real module, or when the experiment
    has no behaviour assay at all.
    """
    behaviour_assays = ("buridan", "open_loop_steering")
    try:
        importlib.import_module("flyonenomics.behaviour")
    except ModuleNotFoundError as exc:
        if exc.name != "flyonenomics.behaviour":
            raise
        return ["IdentityBehaviour"] if assays else []
    if any(assay in behaviour_assays for assay in assays):
        return []
    return ["IdentityBehaviour"] if assays else []
