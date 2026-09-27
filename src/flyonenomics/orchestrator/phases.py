"""Assay rates and immutable run-wide input topology."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
import numpy as np
from numpy.typing import NDArray
if TYPE_CHECKING:
    from flyonenomics.engine.base import InputTopology, UpstreamBank
from flyonenomics.schema.experiment import (
    Activate, Arm, BuridanParams, Experiment, OpenLoopParams, Probe, SpontaneousParams, SugarParams,
)

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class TopologyPlan:
    """Shared topology and bank keys; indices int32 (m,), rates Hz."""
    topology: InputTopology
    bank_keys: list[tuple[str, float]]
    behaviour_settings: dict[str, float | int] | None = None
    visual_settings: Any = None
    resolved_params: Any = None


def map_inject_at(name: str | None) -> str | None:
    """Map schema inject_at onto a registry population. Units: none."""
    if name == "photoreceptors":
        return "R1_6"
    return name


def _visual_inject(visual: Any, params: Any) -> str:
    """Resolved visual injection population. Units: none."""
    if visual is not None and getattr(visual, "inject_at", None):
        return str(visual.inject_at)
    return str(params.get("vis.inject_at"))


def _probe_needs_photoreceptors(phase: Probe, visual: Any, params: Any) -> bool:
    """Return whether this probe drives R1_6. Units: none."""
    options = phase.params
    if isinstance(options, BuridanParams) and options.inject_at == "photoreceptors":
        return True
    if isinstance(options, OpenLoopParams):
        inject = options.inject_at or _visual_inject(visual, params)
        return inject == "photoreceptors"
    if isinstance(options, SpontaneousParams) and options.stimulus == "ambient":
        return True
    return False


def _injection_population(phase: Probe, visual: Any, params: Any) -> str:
    """Registry population that receives visual rates. Units: none."""
    options = phase.params
    if isinstance(options, BuridanParams):
        return map_inject_at(options.inject_at) or "TuBu"
    if isinstance(options, OpenLoopParams) and options.inject_at:
        return map_inject_at(options.inject_at) or "TuBu"
    return map_inject_at(_visual_inject(visual, params)) or "TuBu"


def build_topology(experiment: Experiment, registry: Any, params: Any = None, visual: Any = None) -> TopologyPlan:
    """Collect first-use banks and sorted extended union; Hz, int32 indices (m,)."""
    from flyonenomics.engine.base import InputTopology, UpstreamBank
    from flyonenomics.types import load_params

    resolved = params if params is not None else load_params()
    keys: list[tuple[str, float]] = []
    extended: set[int] = set()
    for arm in experiment.arms:
        for hook in arm.genotype.expanded():
            if isinstance(hook, Activate):
                extended.update(int(i) for i in registry.population(hook.population).idx)
        for phase in arm.expanded():
            if not isinstance(phase, Probe):
                continue
            options = phase.params
            if isinstance(options, SugarParams):
                key = (options.population, options.rate_hz)
                if options.mode == "upstream":
                    if key not in keys:
                        keys.append(key)
                else:
                    extended.update(int(i) for i in registry.population(options.population).idx)
            elif isinstance(options, SpontaneousParams) and options.input:
                extended.update(int(i) for i in registry.population(options.input.population).idx)
            if _probe_needs_photoreceptors(phase, visual, resolved):
                extended.update(int(i) for i in registry.population("R1_6").idx)
            elif phase.assay in ("buridan", "open_loop_steering"):
                population = _injection_population(phase, visual, resolved)
                extended.update(int(i) for i in registry.population(population).idx)
    settings = None
    assays = {p.assay for arm in experiment.arms for p in arm.expanded() if isinstance(p, Probe)}
    if assays & {"buridan", "open_loop_steering"}:
        from flyonenomics.behaviour import load_settings

        visual_path = None
        if experiment.substrate.visual_version:
            candidate = ROOT / "data" / f"visual-{experiment.substrate.visual_version}.yaml"
            if candidate.is_file():
                visual_path = candidate
        meta = experiment.meta if isinstance(experiment.meta, dict) else {}
        settings = load_settings(
            experiment.substrate.behaviour_version, resolved,
            meta.get("behaviour_override"),
            visual_path=visual_path,
            assays=assays,
            meta=meta,
            grid=meta.get("grid"),
            k_grid=bool(meta.get("k_grid")),
            encoder_grid=bool(meta.get("encoder_grid")),
        )
    return TopologyPlan(InputTopology(
        upstream_banks=[UpstreamBank(registry.population(name).idx, rate) for name, rate in keys],
        extended_idx=np.array(sorted(extended), dtype=np.int32), background=experiment.layers.background,
    ), keys, settings, visual, resolved)


def probe_inputs(plan: TopologyPlan, probe: Probe, arm: Arm, registry: Any) -> tuple[list[bool], NDArray[np.float64], NDArray[np.int32]]:
    """Compose summed rates and overlap; Hz (n_extended,), active flags, int32 overlap (m,)."""
    rates = np.zeros(registry.n, dtype=np.float64)
    for hook in arm.genotype.expanded():
        if isinstance(hook, Activate):
            rates[registry.population(hook.population).idx] += hook.rate_hz
    active = [False] * len(plan.bank_keys)
    options = probe.params
    if isinstance(options, SugarParams):
        if options.mode == "upstream":
            active[plan.bank_keys.index((options.population, options.rate_hz))] = True
        else:
            rates[registry.population(options.population).idx] += options.rate_hz
    elif isinstance(options, SpontaneousParams) and options.input:
        rates[registry.population(options.input.population).idx] += options.input.rate_hz
    if isinstance(options, SpontaneousParams) and options.stimulus == "ambient":
        # Section 3.2: ambient light is L = 1 at every photoreceptor.
        visual = plan.visual_settings
        if visual is None or getattr(visual, "r_light", None) is None:
            raise ValueError("spontaneous ambient requires r_light from the visual configuration")
        resolved = plan.resolved_params
        cap = float(resolved.get("vis.r_max")) if resolved is not None else float("inf")
        rates[registry.population("R1_6").idx] += min(cap, float(visual.r_light))
    driven = np.zeros(registry.n, dtype=bool)
    for enabled, bank in zip(active, plan.topology.upstream_banks, strict=True):
        if enabled and bank.rate_hz > 0:
            driven[bank.idx] = True
    return active, rates[plan.topology.extended_idx], np.flatnonzero(driven & (rates > 0)).astype(np.int32)
