"""Analytical drug-only slow state; concentrations held during a probe."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Any
from flyonenomics.types import Params

SECONDS_PER_HOUR = 3600
MICROMOLAR_PER_MILLIMOLAR = 1000
DRUGS = ("methylphenidate", "3-iodotyrosine")


@dataclass
class SlowState:
    """One arm/seed brain clock; seconds, food mM, brain µM, scalar mappings."""
    params: Params
    enabled: bool = True
    t_brain_s: float = 0.0
    concentrations: dict[str, float] = field(default_factory=lambda: dict.fromkeys(DRUGS, 0.0))
    food: dict[str, float] = field(default_factory=dict)

    def start_dose(self, drug: str, c_food_mm: float) -> None:
        """Start exposure; food mM, scalar concentration."""
        if drug == "vehicle":
            return
        if drug not in DRUGS or not self.enabled:
            raise ValueError("unsupported drug or transporter_C layer off")
        if not math.isfinite(c_food_mm) or c_food_mm <= 0:
            raise ValueError("dose must be finite and positive")
        self.food[drug] = c_food_mm

    def stop_dose(self, drug: str) -> None:
        """Stop exposure; units none, one drug name."""
        if drug == "vehicle":
            return
        if drug not in DRUGS:
            raise ValueError("unsupported drug")
        self.food.pop(drug, None)

    def advance(self, seconds: float) -> None:
        """Advance both analytical exposure equations; seconds, scalar state per drug."""
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("advance requires finite nonnegative seconds")
        hours = seconds / SECONDS_PER_HOUR
        if self.enabled:
            for drug in DRUGS:
                c = self.concentrations[drug]
                if drug in self.food:
                    target = self.params.get("pk.kappa") * MICROMOLAR_PER_MILLIMOLAR * self.food[drug]
                    c += (target - c) * -math.expm1(-self.params.get("pk.k_a") * hours)
                else:
                    c *= math.exp(-self.params.get("pk.k_e") * hours)
                self.concentrations[drug] = c
        self.t_brain_s += seconds

    def row(self, phase_label: str) -> dict[str, Any]:
        """Snapshot a phase boundary; seconds, µM and dimensionless rel, scalar columns."""
        # IdentityNeuromod does not apply drug release effects in WP4.
        return {"t_brain_s": self.t_brain_s, **{f"C_b_{d}": self.concentrations[d] for d in DRUGS},
                "rel": 1.0, "phase_label": phase_label}
