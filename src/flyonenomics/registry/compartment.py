"""Named neuropil volumes. No pandas; workers can import this module."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Compartment:
    """One named neuropil volume holding one dopamine concentration.

    Units: id is dimensionless. Shapes: scalar fields.
    """

    name: str
    side: Literal["left", "right", "center"]
    id: int
