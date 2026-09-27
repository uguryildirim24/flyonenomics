"""Unexecuted level-3 protocol builders for WP9; food mM, neural rates Hz."""
from __future__ import annotations

from pathlib import Path

from flyonenomics.schema import Experiment, load_experiment
from flyonenomics.validation.level3 import sensitivity_grid
from flyonenomics.types import Params

REPO = Path(__file__).resolve().parents[3]
# SPEC 7.2: 3.5 food level, 3.6 activation rate and ten shared seeds.
DEPLETION_FOOD_MM = 3.0
PAM_ACTIVATION_HZ = 50.0
PREDICTION_SEEDS = tuple(range(10))


def depletion_protocol() -> Experiment:
    """Build paired WT/fumin 3-IY versus vehicle; 3 mM food, 2 h wait, 5 s probe."""
    document = load_experiment(REPO / "data/experiments/dose-series.json").model_dump(mode="json")
    document["name"] = "depletion-3iy"
    document["description"] = "Unexecuted level 3.5: paired 3-IY depletion in wild type and fumin."
    for arm in document["arms"]:
        drugged = arm["label"] in ("mph", "fumin-mph")
        arm["label"] = arm["label"].replace("mph", "3iy")
        arm["protocol"] = arm["protocol"][:3]
        arm["protocol"][2]["label"] = "depletion-3mm"
        arm["protocol"][0].update(drug="3-iodotyrosine" if drugged else "vehicle", c_food_mm=DEPLETION_FOOD_MM)
    return Experiment.model_validate(document)


def prediction_protocols() -> dict[str, Experiment]:
    """Build 3.6's ten-seed vehicle contrasts: fumin-WT and PAM 50 Hz-baseline."""
    base = load_experiment(REPO / "data/experiments/dose-series.json").model_dump(mode="json")
    protocols = {}
    for name in ("fumin", "pam"):
        document = {**base, "name": f"descending-{name}", "seeds": list(PREDICTION_SEEDS),
                    "description": "Unexecuted level 3.6 descending-rate proxy; no locomotion claim."}
        probe = {**base["arms"][0]["protocol"][2], "label": "descending-rate"}
        document["arms"] = [
            {"label": "baseline", "genotype": {"named": "wild_type"}, "protocol": [probe]},
            {"label": name, "genotype": {"named": "fumin"} if name == "fumin" else
             {"named": "wild_type", "manipulations": [{"type": "activate", "population": "PAM", "rate_hz": PAM_ACTIVATION_HZ}]},
             "protocol": [probe]},
        ]
        document["record"] = {**base["record"], "rates": ["DN_all"]}
        protocols[name] = Experiment.model_validate(document)
    return protocols


def sensitivity_protocols(params: Params) -> list[tuple[Experiment, dict[str, float]]]:
    """Return 27 three-seed dose protocols with Params overrides; values retain each key's units.

    Overrides must be installed in isolated evaluation Params by the WP9 driver;
    they are not experiment-schema fields and never modify the frozen YAML here.
    """
    experiment = load_experiment(REPO / "data/experiments/dose-series.json")
    return [(experiment.model_copy(deep=True), setting["overrides"]) for setting in sensitivity_grid(params)]
