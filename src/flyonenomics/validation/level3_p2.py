"""Phase 2 level-3 and pharmacology entries (SPEC-P2 5.3: 3.2r-3.10r, 4.9-4.11)."""
from __future__ import annotations

from typing import Any, Callable, Mapping

import numpy as np
from numpy.typing import NDArray

from flyonenomics.analysis.contrasts import paired_difference, bootstrap_mean_interval
from flyonenomics.analysis.plan import (
    coupling_sweep_settings,
    declared_drive_present,
    declared_substrate,
    declared_substrate_id,
    dose_sensitivity_settings,
)
from flyonenomics.types import LayerFlags
from flyonenomics.validation.binding import ValidationEntry, build_identity
from flyonenomics.validation.level3 import depletion_response

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
COUPLING_FIXTURE = "data/experiments/p2/coupling.json"
COUPLING_SWEEP_FIXTURE = "data/experiments/p2/coupling-sweep.json"
DOSE_FIXTURE = "data/experiments/p2/dose-p2.json"
DEPLETION_FIXTURE = "data/experiments/p2/depletion-3iy.json"
PAM_FIXTURE = "data/experiments/p2/descending-pam.json"
VISUAL_STATUS_RECORD = "validation/records/p2/visual-status.json"
NEURAL_RECORD = "validation/records/p2/wp21-neural.json"
NEURAL_PENDING = f"Waiting for the WP21 neural record {NEURAL_RECORD}"
ABLATION_PENDING = "Waiting for the WP21 3.8r factorial run ({fixture})"
SENSITIVITY_PENDING = "Waiting for the WP21 3.9r receptor-constant sensitivity run"
NOT_RUN_REASON = (
    "Not run under SPEC-P2 item 144: the full open-loop P-screen was skipped, "
    "so this entry is not produced"
)
PREDICTION_3_6_FIELDS = frozenset({
    "fumin_minus_wild_type_dn_all_hz",
    "fumin_minus_wild_type_da_exposed_hz",
    "pam_minus_baseline_dn_all_hz",
})
LEVER_GROUPS = ("gamma_*", "dV_*", "Kd_D1", "Kd_D2")


def evaluate_3_2r(wt: Mapping[str, float], fumin: Mapping[str, float],
                  fixed_point: Mapping[str, float]) -> dict[str, Any]:
    """fumin DA vs wild type and fixed point; µM per compartment name."""
    names = tuple(wt)
    if set(names) != set(fumin) or set(names) != set(fixed_point) or not names:
        raise ValueError("3.2r needs the same nonempty compartment names")
    rows = {}
    for name in names:
        wild = float(wt[name])
        mutant = float(fumin[name])
        fp = float(fixed_point[name])
        rows[name] = {
            "wt_um": wild, "fumin_um": mutant, "fixed_point_um": fp,
            "wt_above_zero": wild > 0,
            "at_least_2x": wild > 0 and mutant >= 2 * wild,
            "within_20pct_fp": abs(mutant - fp) <= 0.2 * abs(fp) if fp != 0 else mutant == 0,
        }
    passed = all(row["wt_above_zero"] and row["at_least_2x"] and row["within_20pct_fp"]
                 for row in rows.values())
    return {"passed": passed, "compartments": rows}


def evaluate_3_3r(vehicle: NDArray[np.float64], drug: NDArray[np.float64],
                  fumin: NDArray[np.float64]) -> dict[str, Any]:
    """Monotone MPH dose between vehicle and fumin; µM, shape (3,)."""
    vehicle = np.asarray(vehicle, dtype=np.float64)
    drug = np.asarray(drug, dtype=np.float64)
    fumin = np.asarray(fumin, dtype=np.float64)
    if vehicle.shape != (3,) or drug.shape != (3,) or fumin.shape != (3,):
        raise ValueError("3.3r needs three dose levels")
    monotone = bool(all(a < b for a, b in zip(drug[:-1], drug[1:], strict=True)))
    between = bool(all(v < d < f for v, d, f in zip(vehicle, drug, fumin, strict=True)))
    return {"passed": monotone and between, "vehicle_um": vehicle.tolist(),
            "mph_um": drug.tolist(), "fumin_um": fumin.tolist(),
            "monotone": monotone, "between_wt_and_fumin": between}


def evaluate_3_4r(vehicle: NDArray[np.float64], drug: NDArray[np.float64],
                  rng: np.random.Generator, n_boot: int, margin_fraction: float) -> dict[str, Any]:
    """fumin MPH null: paired interval inside ±margin of the vehicle mean; µM."""
    vehicle = np.asarray(vehicle, dtype=np.float64)
    drug = np.asarray(drug, dtype=np.float64)
    differences = paired_difference(drug, vehicle)
    mean, interval, _ = bootstrap_mean_interval(differences, rng, n_boot)
    margin = float(margin_fraction) * float(vehicle.mean())
    passed = bool(interval[0] > -margin and interval[1] < margin)
    return {"passed": passed, "mean_um": mean, "ci95_um": interval,
            "equivalence_margin_um": margin, "per_seed_um": differences.tolist(),
            "model_note": "Methylphenidate changes Km only, so fumin has no modelled DAT target"}


def evaluate_3_5r(vehicle: dict[str, NDArray[np.float64]],
                  treated: dict[str, NDArray[np.float64]]) -> dict[str, Any]:
    """3 mM 3-IY lowers settled DA in wild type and fumin; µM vectors."""
    return depletion_response(vehicle, treated)


def evaluate_3_10r(wt: NDArray[np.float64], fumin: NDArray[np.float64],
                   rng: np.random.Generator, n_boot: int) -> dict[str, Any]:
    """Coupling: fumin-minus-WT DA_exposed interval excludes zero; Hz."""
    diff = paired_difference(np.asarray(fumin, dtype=np.float64), np.asarray(wt, dtype=np.float64))
    mean, interval, _ = bootstrap_mean_interval(diff, rng, n_boot)
    passed = bool(interval[0] > 0 or interval[1] < 0)
    return {"passed": passed, "mean_hz": mean, "ci95_hz": interval, "per_seed_hz": diff.tolist()}


def relative_change(overrides: Mapping[str, float], defaults: Mapping[str, float]) -> float:
    """Largest |override/default − 1| across keys; dimensionless, scalar."""
    changes = []
    for key, value in overrides.items():
        base = float(defaults[key])
        if base == 0:
            changes.append(abs(float(value)))
        else:
            changes.append(abs(float(value) / base - 1.0))
    return max(changes) if changes else 0.0


def smallest_coupling_lever(
    results: list[dict[str, Any]],
    *,
    groups: tuple[str, ...] = LEVER_GROUPS,
) -> dict[str, Any]:
    """Section 4.7: smallest in-range change that excludes zero; dimensionless."""
    default = next((row for row in results if row.get("level") == "default"), None)
    if default is not None:
        interval = default["ci95"]
        if interval[0] > 0 or interval[1] < 0:
            return {"change": 0.0, "setting": default, "already_excludes_zero": True}
    candidates = []
    for row in results:
        if row.get("group") not in groups:
            continue
        interval = row["ci95"]
        if not (interval[0] > 0 or interval[1] < 0):
            continue
        candidates.append((row["relative_change"], row))
    if not candidates:
        return {"change": None, "setting": None, "already_excludes_zero": False}
    candidates.sort(key=lambda item: (item[0], item[1].get("group", ""), item[1].get("level", "")))
    best = candidates[0][1]
    return {"change": candidates[0][0], "setting": best, "already_excludes_zero": False}


def _read_record(relative: str) -> dict[str, Any] | None:
    """Read one committed JSON record from the repository, or None. Units per document."""
    from flyonenomics.io import read_json

    path = REPO / relative
    if not path.is_file():
        return None
    document = read_json(path)
    return document if isinstance(document, dict) else None


def recorded_visual_status() -> str | None:
    """The recorded SPEC-P2 3.7 visual status, or None when none exists. Units: none."""
    status = (_read_record(VISUAL_STATUS_RECORD) or {}).get("status")
    return str(status) if status else None


def visual_fixture_form(status: str | None = None) -> str:
    """Fixture form matching the recorded status: `openloop` under open loop, else `buridan`."""
    current = recorded_visual_status() if status is None else status
    return "openloop" if current == "open loop" else "buridan"


def fixture_for(stem: str, status: str | None = None) -> str:
    """The committed fixture whose probe form matches the recorded status (SPEC-P2 4.4)."""
    path = f"data/experiments/p2/{stem}-{visual_fixture_form(status)}.json"
    if not (REPO / path).is_file():
        raise ValueError(f"missing fixture for the recorded visual status: {path}")
    return path


def _not_run(test_id: str) -> ValidationEntry:
    """Terminal item-144 prediction entry. Units: none."""
    flags = LayerFlags(background=True)
    identity = build_identity(
        REPO, connectome_version="783", layers=flags, assay="open_loop_steering",
        fixture=None, run_code_hash="", substrate_id=declared_substrate_id(),
    )
    return ValidationEntry(
        test_id=test_id, category="prediction", outcome="not run",
        compatibility="matching-layers", identity=identity,
        measured={
            "reason": NOT_RUN_REASON,
            "declared_substrate": declared_substrate(),
            "declared_drive": declared_drive_present(),
        },
    )


def _pending(test_id: str, category: str, fixture: str, *, reason: str,
             compatibility: str = "canonical", development: bool = False) -> ValidationEntry:
    """Unavailable entry until declared-substrate engine runs exist; no engine evidence."""
    flags = LayerFlags(background=True)
    identity = build_identity(REPO, connectome_version="783", layers=flags,
                              assay="spontaneous", fixture=fixture, run_code_hash="",
                              substrate_id=declared_substrate_id())
    return ValidationEntry(
        test_id=test_id, category=category, outcome="unavailable",
        compatibility="development" if development else compatibility, identity=identity,
        measured={
            "reason": reason,
            "intended_class": compatibility,
            "declared_substrate": declared_substrate(),
            "declared_drive": declared_drive_present(),
        },
        data_dependencies=["params-v0.1.yaml"], fixture_path=fixture,
        stub="RestSubstratePending" if development else None,
    )


def _neural_record() -> dict[str, Any] | None:
    """The committed neural-half measured record, or None. Units: per stored fields."""
    return _read_record(NEURAL_RECORD)


def _measured_outcome(test_id: str, payload: dict[str, Any]) -> str:
    """Measured entry outcome; incomplete predictions stay unavailable. Units: none."""
    if test_id == "3.6r":
        return "recorded" if PREDICTION_3_6_FIELDS <= payload.keys() else "unavailable"
    if test_id == "3.2r":
        return "passed" if all(bool(probe.get("passed")) for probe in payload.values()) else "failed"
    return "passed" if payload.get("passed") else "failed"


def _measured_entry(test_id: str, category: str, fixture: str) -> ValidationEntry | None:
    """Entry from the committed neural record, or None. Units: per stored fields."""
    record = _neural_record()
    payload = ((record or {}).get("measured") or {}).get(test_id)
    if not isinstance(payload, dict):
        return None
    flags = LayerFlags(background=True)
    identity = build_identity(REPO, connectome_version="783", layers=flags,
                              assay="spontaneous", fixture=fixture, run_code_hash="",
                              substrate_id=declared_substrate_id())
    run_scope = str((record or {}).get("code_scope") or "")
    missing_readouts = sorted(PREDICTION_3_6_FIELDS - payload.keys()) if test_id == "3.6r" else []
    identity = identity.model_copy(update={
        "code_commit": str((record or {}).get("run_code_commit") or identity.code_commit),
        "code_hash": "", "run_code_hash": "", "code_scope": run_scope,
        "run_code_scope": run_scope, "fixture_hash": "", "protocol_hash": None,
        "machine": "aarch64 aarch64", "date": "", "inputs": {},
        "platform": str((record or {}).get("platform") or ""),
        "substrate_id": str((record or {}).get("substrate_id") or identity.substrate_id),
        "engine_model": str((record or {}).get("engine_model") or identity.engine_model),
    })
    compatibility = str((record or {}).get("class") or "development")
    return ValidationEntry(
        test_id=test_id, category=category, outcome=_measured_outcome(test_id, payload),
        compatibility=compatibility,
        stub="RecordedDevelopment" if compatibility == "development" else None,
        identity=identity,
        measured={**payload, "record": NEURAL_RECORD,
                  "platform": (record or {}).get("platform"),
                  "run_code_commit": (record or {}).get("run_code_commit"),
                  "dopamine_sha256": (record or {}).get("dopamine_sha256"),
                  "dopamine_qualified": (record or {}).get("dopamine_qualified"),
                  "qualification_note":
                      "The existing record retains its stored class; platform is provenance.",
                  "missing_required_readouts": missing_readouts,
                  "note": (record or {}).get("note")},
        data_dependencies=["params-v0.2.yaml"], fixture_path=fixture)


def test_3_2r() -> ValidationEntry:
    """3.2r fumin DA on the rest substrate; µM, measured on the declared unit."""
    return _measured_entry("3.2r", "consistency", DOSE_FIXTURE) or _pending(
        "3.2r", "consistency", DOSE_FIXTURE, reason=NEURAL_PENDING)


def test_3_3r() -> ValidationEntry:
    """3.3r dose series on the rest substrate; µM, measured on the declared unit."""
    return _measured_entry("3.3r", "consistency", DOSE_FIXTURE) or _pending(
        "3.3r", "consistency", DOSE_FIXTURE, reason=NEURAL_PENDING)


def test_3_4r() -> ValidationEntry:
    """3.4r methylphenidate on fumin; µM, measured on the declared unit."""
    return _measured_entry("3.4r", "consistency", DOSE_FIXTURE) or _pending(
        "3.4r", "consistency", DOSE_FIXTURE, reason=NEURAL_PENDING)


def test_3_5r() -> ValidationEntry:
    """3.5r 3-iodotyrosine depletion; µM, measured on the declared unit."""
    return _measured_entry("3.5r", "consistency", DEPLETION_FIXTURE) or _pending(
        "3.5r", "consistency", DEPLETION_FIXTURE, reason=NEURAL_PENDING)


def test_3_6r() -> ValidationEntry:
    """3.6r DN_all and DA_exposed predictions; Hz, with partial Oracle measurements."""
    return _measured_entry("3.6r", "prediction", COUPLING_FIXTURE) or _pending(
        "3.6r", "prediction", COUPLING_FIXTURE, reason=NEURAL_PENDING)


def test_3_8r() -> ValidationEntry:
    """3.8r factorial; the ablation form matching the recorded visual status."""
    fixture = fixture_for("ablation-p2")
    return _pending("3.8r", "consistency", fixture, compatibility="matching-layers",
                    reason=ABLATION_PENDING.format(fixture=fixture))


def test_3_9r() -> ValidationEntry:
    """3.9r receptor-constant sensitivity; pending the WP21 sensitivity run."""
    measured = {
        "reason": SENSITIVITY_PENDING,
        "dose_settings": len(dose_sensitivity_settings()),
        "coupling_settings": len(coupling_sweep_settings()),
        "intended_class": "development",
        "declared_substrate": declared_substrate(),
        "declared_drive": declared_drive_present(),
    }
    flags = LayerFlags(background=True)
    identity = build_identity(REPO, connectome_version="783", layers=flags,
                              assay="spontaneous", fixture=COUPLING_SWEEP_FIXTURE, run_code_hash="",
                              substrate_id=declared_substrate_id())
    return ValidationEntry(test_id="3.9r", category="sensitivity", outcome="unavailable",
                           compatibility="development", identity=identity, measured=measured,
                           data_dependencies=["params-v0.1.yaml"], fixture_path=COUPLING_SWEEP_FIXTURE,
                           stub="CamberSweepPending")


def test_3_10r() -> ValidationEntry:
    """3.10r coupling on DA_exposed; Hz, measured on the declared unit."""
    return _measured_entry("3.10r", "consistency", COUPLING_FIXTURE) or _pending(
        "3.10r", "consistency", COUPLING_FIXTURE, reason=NEURAL_PENDING)


def test_4_9() -> ValidationEntry:
    """4.9 is terminally not run under SPEC-P2 item 144."""
    return _not_run("4.9")


def test_4_10() -> ValidationEntry:
    """4.10 is terminally not run under SPEC-P2 item 144."""
    return _not_run("4.10")


def test_4_11() -> ValidationEntry:
    """4.11 is terminally not run under SPEC-P2 item 144."""
    return _not_run("4.11")


SUITE: dict[str, Callable[[], ValidationEntry]] = {
    "3.2r": test_3_2r,
    "3.3r": test_3_3r,
    "3.4r": test_3_4r,
    "3.5r": test_3_5r,
    "3.6r": test_3_6r,
    "3.8r": test_3_8r,
    "3.9r": test_3_9r,
    "3.10r": test_3_10r,
    "4.9": test_4_9,
    "4.10": test_4_10,
    "4.11": test_4_11,
}
