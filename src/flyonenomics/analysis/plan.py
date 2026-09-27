"""Phase 2 pharmacology experiment files and planning factors (SPEC-P2 4, 6.3)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from flyonenomics.behaviour.visual_calibration import (
    DECLARED_SUBSTRATE_ID as DECLARED_SUBSTRATE_CANDIDATE_ID,
    declared_drive_present,
    declared_substrate,
    declared_substrate_id,
)
from flyonenomics.types import load_params
from flyonenomics.validation.level3 import sensitivity_grid

REPO_ROOT = Path(__file__).resolve().parents[3]

PLAN_SETTLE_S = 2.0
MASTER_SEED = 20260912
SEEDS_10 = list(range(1, 11))
SEEDS_3 = [1, 2, 3]
BURIDAN_S = 20.0
OPENLOOP_S = 47.0
DOSE_PROBE_S = 5.0
COUPLING_S = 20.0
TIY_MM = 3.0
DOSE_LEVELS_MM = (0.1, 0.5, 1.0)
WASHOUT_H = 100.0
WAIT_H = 2.0
MAX_SELECTED = ("dat_half", "dopamine_depleted", "dop1r1_null")
COUPLING_GROUPS = ("Kd_D1", "Kd_D2", "gamma_*", "dV_*", "Vmax", "Km", "k_ns")
SIGN_CHECK_AZIMUTHS = (-150, -120, -90, -60, -45, -30, 0, 30, 45, 60, 90, 120, 150)
DISTRACTOR = {"azimuth": 90, "flicker_hz": 3, "contrast": 1.0, "onset_s": 5, "duration_s": 10}
CAPTURE_DISTRACTOR = {"azimuth": 90, "flicker_hz": 3, "contrast": 1.0}

STAGE_RATES = (
    "R1_6", "L1", "L2", "L3", "L4", "L5",
    "Mi1", "Mi4", "Mi9", "Tm1", "Tm2", "Tm3", "Tm4", "Tm9",
    "T4", "T5", "LC10", "LC_all", "LPLC", "MeTu", "visual_projection",
)
ADDED_RATES = ("DA_exposed", "PAM", "PPL1", "KC", "MBON", "dFB")
SECTION_63_SPIKES = ("DAN", "CX_DAN", "ER", "EPG", "TuBu", "steering_L", "steering_R", "DN_all")
SECTION_63_RATES = ("DAN", "CX_DAN", "ER", "EPG", "steering_L", "steering_R", "DN_all")
NEURAL_RATES = (
    "DA_exposed", "PAM", "PPL1", "CX_DAN", "KC", "MBON", "ER", "EPG", "dFB",
    "TuBu", "steering_L", "steering_R", "DN_all", "DAN",
)

ARM_PREFIX = {
    "wild_type": "wt",
    "fumin": "fumin",
    "dat_half": "dat-half",
    "dopamine_depleted": "dopamine-depleted",
    "dop1r1_null": "dop1r1-null",
    "dop2r_null": "dop2r-null",
    "dan_autoreceptor_null": "dan-autoreceptor-null",
    "er_dop1r1_kd": "er-dop1r1-kd",
    "pam_silenced": "pam-silenced",
    "cx_dan_silenced": "cx-dan-silenced",
    "dfb_silenced": "dfb-silenced",
}
DRUG_SUFFIX = {"vehicle": "vehicle", "methylphenidate": "mph", "3-iodotyrosine": "3iy"}

LAYERS_REST = {
    "background": True,
    "dopamine_A": True,
    "transporter_C": True,
    "dan_fast_synapses": "retain",
    "receptor_kinetics_B": False,
    "learning_D": False,
}

SUBSTRATE_P2 = {
    "connectome_version": "783",
    "annotation_version": "v2.1.0",
    "receptor_map_version": "v0.1",
    "params_version": "v0.2",
    "populations_version": "v0.2",
    "transmitters_version": "v0.2",
    "drive_version": "v0.2",
    "dopamine_version": "v0.2",
    "visual_version": "v0.2",
    "behaviour_version": "v0.2",
}

SUBSTRATE_NEURAL = {
    **SUBSTRATE_P2,
    "behaviour_version": "base-v0.2",
}


def plan_settle_s() -> float:
    """Planning settle per probe; seconds, scalar (SPEC-P2 budget.plan_settle_s)."""
    try:
        return float(load_params().get("budget.plan_settle_s"))
    except (KeyError, TypeError, ValueError):
        return PLAN_SETTLE_S


def brain_s(duration_s: float, n_arms: int, n_seeds: int, n_probes: int,
            n_settings: int = 1, settle_s: float | None = None) -> int:
    """Expanded brain seconds at the planning settle; seconds, scalar."""
    settle = plan_settle_s() if settle_s is None else settle_s
    return int(n_settings * n_arms * n_seeds * n_probes * (duration_s + settle))


def arm_label(genotype: str, drug: str) -> str:
    """Matched-arm label; dimensionless, ARM_PATTERN string."""
    return f"{ARM_PREFIX[genotype]}-{DRUG_SUFFIX[drug]}"


def _record(rates: tuple[str, ...], spikes: tuple[str, ...], *, live: bool) -> dict[str, Any]:
    """Build a record block; population names, scalar flags."""
    return {
        "spikes": list(spikes),
        "rates": list(dict.fromkeys(rates)),
        "dopamine": True,
        "receptors": True,
        "drug": True,
        "arena": True,
        "popcount": True,
        "rate_bin_ms": 50,
        "live": live,
    }


def pharm_record(*, live: bool) -> dict[str, Any]:
    """Screen and prediction recording; section 1.5 plus 4.5 names."""
    rates = SECTION_63_RATES + ADDED_RATES + STAGE_RATES + ("TuBu", "CX_DAN", "PAM", "PPL1")
    return _record(rates, SECTION_63_SPIKES + ("DA_exposed", "PAM", "PPL1", "KC", "MBON", "dFB"), live=live)


def neural_record(*, live: bool) -> dict[str, Any]:
    """Dark-spontaneous neural recording; Hz and µM later, names only here."""
    return _record(NEURAL_RATES, ("DAN", "CX_DAN", "DN_all", "DA_exposed", "PAM"), live=live)


def buridan_probe(label: str) -> dict[str, Any]:
    """20 s Buridan probe with the section 6.3 distractor; seconds, degrees, Hz."""
    return {
        "type": "probe",
        "assay": "buridan",
        "duration_s": BURIDAN_S,
        "label": label,
        "params": {
            "stripes": True,
            "encoder": "on",
            "inject_at": "photoreceptors",
            "initial_heading": "random",
            "distractor": dict(DISTRACTOR),
        },
    }


def openloop_blocks() -> list[dict[str, Any]]:
    """Section 3.6 47 s open-loop probe blocks; degrees, seconds."""
    blocks = [
        {"stimulus": "stripe", "azimuth_deg": float(azimuth), "distractor": None,
         "transition_s": 1.0, "dwell_s": 2.0}
        for azimuth in SIGN_CHECK_AZIMUTHS
    ]
    blocks.append({"stimulus": "stripe", "azimuth_deg": -45.0, "distractor": None,
                   "transition_s": 1.0, "dwell_s": 3.0})
    blocks.append({"stimulus": "stripe", "azimuth_deg": -45.0, "distractor": dict(CAPTURE_DISTRACTOR),
                   "transition_s": 1.0, "dwell_s": 3.0})
    return blocks


def openloop_probe(label: str) -> dict[str, Any]:
    """47 s open-loop probe; seconds, block list."""
    blocks = openloop_blocks()
    duration = sum(block["transition_s"] + block["dwell_s"] for block in blocks)
    if duration != OPENLOOP_S:
        raise ValueError(f"open-loop duration {duration} != {OPENLOOP_S}")
    return {
        "type": "probe",
        "assay": "open_loop_steering",
        "duration_s": OPENLOOP_S,
        "label": label,
        "params": {"blocks": blocks},
    }


def spontaneous_probe(label: str, duration_s: float) -> dict[str, Any]:
    """Dark spontaneous probe; seconds, scalar duration."""
    return {
        "type": "probe",
        "assay": "spontaneous",
        "duration_s": duration_s,
        "label": label,
        "params": {"stimulus": "dark"},
    }


def dose_protocol(drug: str) -> list[dict[str, Any]]:
    """Sequential 0.1, 0.5, 1.0 mM with 100 h washouts; dark 5 s probes."""
    phases: list[dict[str, Any]] = []
    for index, level in enumerate(DOSE_LEVELS_MM):
        if index:
            phases.append({"type": "washout", "drug": drug})
            phases.append({"type": "wait", "hours": WASHOUT_H})
        phases.extend([
            {"type": "dose", "drug": drug, "c_food_mm": level},
            {"type": "wait", "hours": WAIT_H},
            spontaneous_probe(f"dose-{level}", DOSE_PROBE_S),
        ])
    return phases


def depletion_protocol(drug: str) -> list[dict[str, Any]]:
    """Paired 3 mM 3-IY versus vehicle; dark 5 s probe."""
    return [
        {"type": "dose", "drug": drug, "c_food_mm": TIY_MM},
        {"type": "wait", "hours": WAIT_H},
        spontaneous_probe("depletion-3mm", DOSE_PROBE_S),
    ]


def declared_substrate_meta() -> dict[str, Any] | None:
    """The item 122 unit fields every pharmacology file carries. Units: mV, ratios."""
    declared = declared_substrate()
    if declared is None:
        return None
    return {
        key: declared[key]
        for key in (
            "item", "candidate_id", "arm_id", "bg_policy", "w_bg_mv", "g_gaba", "g_glu",
            "g_gaba_kc", "sigma_th_mv", "optic_exemption", "n_bg", "engine_model", "records",
        )
    }


def experiment(name: str, description: str, arms: list[dict[str, Any]], *,
               seeds: list[int], comparison: str = "paired", substrate: dict[str, Any] | None = None,
               record: dict[str, Any] | None = None, live: bool = False,
               meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Schema 1.3 experiment mapping; units per nested fields."""
    declared = declared_substrate_meta()
    if declared is not None:
        meta = {**(meta or {}), "declared_substrate": declared}
    return {
        "schema_version": "1.3",
        "name": name,
        "description": description,
        "seed": MASTER_SEED,
        "seeds": seeds,
        "substrate": dict(substrate or SUBSTRATE_P2),
        "layers": dict(LAYERS_REST),
        "comparison": comparison,
        "arms": arms,
        "record": record if record is not None else pharm_record(live=live),
        "meta": meta or {},
    }


def paired_arms(genotypes: tuple[str, ...], drugs: tuple[str, ...], protocol_for,
                extra: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Matched genotype × drug arms; protocol factory(drug) -> phase list."""
    arms = []
    for genotype in genotypes:
        for drug in drugs:
            arm: dict[str, Any] = {
                "label": arm_label(genotype, drug),
                "genotype": {"named": genotype, "manipulations": []},
                "protocol": protocol_for(drug),
            }
            if extra:
                arm.update(deepcopy(extra))
            arms.append(arm)
    return arms


def ablation_arms(form: str) -> list[dict[str, Any]]:
    """Eight-arm 2×2 pools × fast × genotype; one vehicle probe."""
    probe = buridan_probe("test") if form == "buridan" else openloop_probe("test")
    arms = []
    for pools in (True, False):
        for fast in ("retain", "disconnect"):
            for genotype, tag in (("wild_type", "wt"), ("fumin", "fumin")):
                cell = "on" if pools else "off"
                arms.append({
                    "label": f"{cell}-{fast}-{tag}",
                    "genotype": {"named": genotype, "manipulations": []},
                    "layers": {"dopamine_A": pools, "dan_fast_synapses": fast},
                    "protocol": [deepcopy(probe)],
                })
    return arms


def ablation_files() -> dict[str, dict[str, Any]]:
    """3.8r factorial in both probe forms."""
    files = {}
    for form in ("buridan", "openloop"):
        files[f"ablation-p2-{form}.json"] = experiment(
            f"ablation-p2-{form}",
            "Rest-substrate 2x2 dopamine-pool and fast-DAN factorial, wild type and fumin",
            ablation_arms(form),
            seeds=SEEDS_10, comparison="ablation", live=False,
            record=neural_record(live=False) if form != "buridan" else pharm_record(live=False),
            meta={"stage": "3.8r", "form": form},
        )
    return files


def neural_files() -> dict[str, dict[str, Any]]:
    """Dark-spontaneous 3.2r-3.6r, 3.9r and 3.10r fixtures."""
    coupling_simple = [
        {"label": "wild-type", "genotype": {"named": "wild_type", "manipulations": []},
         "protocol": [spontaneous_probe("coupling", COUPLING_S)]},
        {"label": "fumin", "genotype": {"named": "fumin", "manipulations": []},
         "protocol": [spontaneous_probe("coupling", COUPLING_S)]},
        {"label": "dop1r1-null", "genotype": {"named": "dop1r1_null", "manipulations": []},
         "protocol": [spontaneous_probe("coupling", COUPLING_S)]},
    ]
    sweep_arms = coupling_simple[:2]
    dose_arms = paired_arms(
        ("wild_type", "fumin"), ("vehicle", "methylphenidate"),
        dose_protocol, extra=None,
    )
    # paired_arms uses mph suffix; relabel the Phase 1-style dose arms for 3.3r/3.4r.
    label_map = {
        "wt-vehicle": "vehicle", "wt-mph": "mph",
        "fumin-vehicle": "fumin", "fumin-mph": "fumin-mph",
    }
    for arm in dose_arms:
        arm["label"] = label_map[arm["label"]]
    depletion_arms = paired_arms(
        ("wild_type", "fumin"), ("vehicle", "3-iodotyrosine"),
        depletion_protocol,
    )
    for arm in depletion_arms:
        arm["label"] = {
            "wt-vehicle": "vehicle", "wt-3iy": "3iy",
            "fumin-vehicle": "fumin", "fumin-3iy": "fumin-3iy",
        }[arm["label"]]
    pam_arms = [
        {"label": "baseline", "genotype": {"named": "wild_type", "manipulations": []},
         "protocol": [spontaneous_probe("descending-rate", DOSE_PROBE_S)]},
        {"label": "pam", "genotype": {"named": "wild_type",
         "manipulations": [{"type": "activate", "population": "PAM", "rate_hz": 50.0}]},
         "protocol": [spontaneous_probe("descending-rate", DOSE_PROBE_S)]},
    ]
    return {
        "coupling.json": experiment(
            "coupling",
            "3.10r: wild type, fumin and dop1r1_null, vehicle, ten seeds, 20 s dark spontaneous",
            coupling_simple, seeds=SEEDS_10, substrate=SUBSTRATE_NEURAL,
            record=neural_record(live=False), live=False,
            meta={"stage": "3.10r", "form": "spontaneous-dark"},
        ),
        "coupling-sweep.json": experiment(
            "coupling-sweep",
            "3.9r coupling part: wild type and fumin, vehicle, ten seeds, 20 s dark spontaneous",
            sweep_arms, seeds=SEEDS_10, substrate=SUBSTRATE_NEURAL,
            record=neural_record(live=False), live=False,
            meta={"stage": "3.9r-coupling", "form": "spontaneous-dark",
                  "settings": "coupling_sweep_settings"},
        ),
        "dose-p2.json": experiment(
            "dose-p2",
            "3.3r/3.4r: wild type and fumin, vehicle and methylphenidate, 0.1/0.5/1.0 mM, dark 5 s probes",
            dose_arms, seeds=SEEDS_3, substrate=SUBSTRATE_NEURAL,
            record=neural_record(live=False), live=False,
            meta={"stage": "3.3r", "form": "spontaneous-dark", "dose_mm": list(DOSE_LEVELS_MM)},
        ),
        "depletion-3iy.json": experiment(
            "depletion-3iy",
            "3.5r: paired 3 mM 3-iodotyrosine versus vehicle in wild type and fumin, dark 5 s probe",
            depletion_arms, seeds=SEEDS_3, substrate=SUBSTRATE_NEURAL,
            record=neural_record(live=False), live=False,
            meta={"stage": "3.5r", "form": "spontaneous-dark"},
        ),
        "descending-pam.json": experiment(
            "descending-pam",
            "3.6r PAM 50 Hz minus baseline, dark 5 s spontaneous; DN_all is a proxy, not locomotion",
            pam_arms, seeds=SEEDS_10, substrate=SUBSTRATE_NEURAL,
            record=neural_record(live=False), live=False,
            meta={"stage": "3.6r", "form": "spontaneous-dark"},
        ),
    }


def file_411() -> dict[str, dict[str, Any]]:
    """4.11 open-loop vehicle arms at maximum selection."""
    genotypes = ("wild_type", "fumin") + MAX_SELECTED
    arms = []
    for genotype in genotypes:
        arms.append({
            "label": arm_label(genotype, "vehicle"),
            "genotype": {"named": genotype, "manipulations": []},
            "protocol": [openloop_probe("openloop")],
        })
    return {
        "pharm-411-openloop.json": experiment(
            "pharm-411-openloop",
            "4.11: open-loop probe, vehicle only, wild type, fumin and maximum selected genotypes",
            arms, seeds=SEEDS_10, live=False,
            meta={"stage": "4.11", "form": "openloop", "selection": "maximum",
                  "selected": list(MAX_SELECTED)},
        ),
    }


def all_experiments() -> dict[str, dict[str, Any]]:
    """Every WP21 experiment mapping, keyed by filename."""
    files = {}
    files.update(neural_files())
    files.update(ablation_files())
    # Kept as the source fixture named by the measured P-screen power pilot.
    files.update(file_411())
    return files


def coupling_sweep_settings(params: Any | None = None) -> list[dict[str, Any]]:
    """15 distinct no-drug 3.9r coupling settings; source units per key."""
    grid = sensitivity_grid(params if params is not None else load_params())
    settings: list[dict[str, Any]] = []
    default_added = False
    for setting in grid:
        if setting["group"] not in COUPLING_GROUPS:
            continue
        if setting["level"] == "default":
            if default_added:
                continue
            default_added = True
        settings.append(setting)
    if len(settings) != 15:
        raise ValueError(f"expected 15 coupling settings, got {len(settings)}")
    return settings


def dose_sensitivity_settings(params: Any | None = None) -> list[dict[str, Any]]:
    """27 Phase 1 3.9 settings; source units per key."""
    settings = sensitivity_grid(params if params is not None else load_params())
    if len(settings) != 27:
        raise ValueError(f"expected 27 dose settings, got {len(settings)}")
    return settings


def count_probes(document: dict[str, Any]) -> int:
    """Probes in one expanded arm; count, scalar."""
    n = 0
    for phase in document["arms"][0]["protocol"]:
        if phase["type"] == "probe":
            n += 1
        elif phase["type"] == "repeat":
            n += sum(1 for body in phase["body"] if body["type"] == "probe") * int(phase["n"])
    return n


def document_brain_s(document: dict[str, Any], n_settings: int = 1) -> int:
    """Brain seconds for one file at the planning settle; seconds, scalar."""
    duration = next(phase["duration_s"] for phase in document["arms"][0]["protocol"] if phase["type"] == "probe")
    # dose-p2 has equal 5 s probes; mixed durations would need a sum.
    total = 0
    for phase in document["arms"][0]["protocol"]:
        if phase["type"] == "probe":
            total += phase["duration_s"] + plan_settle_s()
    return int(n_settings * len(document["arms"]) * len(document["seeds"]) * total)


def planning_rows() -> dict[str, dict[str, Any]]:
    """SPEC-P2 section 6.3 WP21 rows; factors and brain s."""
    files = all_experiments()
    return {
        "3.9r-dose": {
            "factors": "27 settings × 3 seeds × 12 probes × 7 s",
            "brain_s": document_brain_s(files["dose-p2.json"], n_settings=27),
            "expected": 6_804,
            "files": ["dose-p2.json"],
        },
        "3.9r-coupling": {
            "factors": "15 settings × 2 arms × 10 × 22 s",
            "brain_s": document_brain_s(files["coupling-sweep.json"], n_settings=15),
            "expected": 6_600,
            "files": ["coupling-sweep.json"],
        },
    }


def write_experiments(root: Any) -> list[str]:
    """Write every experiment JSON under data/experiments/p2/; returns filenames."""
    import json
    from pathlib import Path
    directory = Path(root) / "data" / "experiments" / "p2"
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, document in all_experiments().items():
        path = directory / name
        path.write_text(json.dumps(document, indent=2) + "\n")
        written.append(name)
    return written
