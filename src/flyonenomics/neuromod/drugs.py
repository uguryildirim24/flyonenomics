"""Phase 1 DAT and release effects, with explicit unsupported names."""
from __future__ import annotations

from flyonenomics.types import Params

SUPPORTED = ("vehicle", "methylphenidate", "3-iodotyrosine")
RECOGNISED_UNIMPLEMENTED = ("amphetamine", "atomoxetine", "caffeine", "cocaine")


class NotImplementedInPhase1(ValueError):
    """A recognised drug without a Phase 1 mechanism."""


def check_drug(name: str) -> None:
    """Validate a drug name; names have no units or array shape."""
    if name in RECOGNISED_UNIMPLEMENTED:
        raise NotImplementedInPhase1(name)
    if name not in SUPPORTED:
        raise ValueError(f"unknown drug: {name}")


def drug_effect(concentrations: dict[str, float], params: Params) -> tuple[float, float]:
    """Return Km multiplier and release multiplier; concentrations in brain µM, scalars."""
    km = 1 + concentrations.get("methylphenidate", 0.0) / params.get("drug.mph.Ki")
    rel = 1 / (1 + concentrations.get("3-iodotyrosine", 0.0) / params.get("drug.3iy.EC50"))
    return km, rel
