"""R3 visual screen and V-cal (SPEC-P2 sections 2.5 and 3.4).

Item 122 declares the resting substrate: the sensory-only arm at 1.0 mV
(`1.0-4.0-0.0-False-100-1.0-kc-6.0-sens`, item 110 arm A, facts in item 121).
The rest search is closed, so R3's candidate table and the V entries bind to
that declared unit read from the committed rest records, not to WP17's
shortlist or WP19's Q-rest. The declared unit's drive document
(`data/drive-v0.2.yaml`, item 123) is committed, so V0, V1, V3 and V-cal bind
its `rest:<16 hex>` tag and wait only on the engine run.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from flyonenomics.diagnostics.visual_path import V_CAL_EXTENSION_HZ, V_CAL_RATES_HZ

REPO = Path(__file__).resolve().parents[3]
R3_MAX = 6
DECLARED_SUBSTRATE_ID = "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
DECLARED_DRIVE_PATH = REPO / "data" / "drive-v0.2.yaml"
R3_RECORD = REPO / "validation" / "records" / "p2" / "R3.json"
VCAL_RECORD = REPO / "validation" / "records" / "p2" / "visual-vcal.json"
REST_RECORDS = (
    REPO / "validation" / "records" / "p2" / "rest-T3e-decision.json",
    REPO / "validation" / "records" / "p2" / "rest-T3e-freeze-partial.json",
)


def _read_record(path: Path) -> dict[str, Any]:
    """Read one committed rest record. Units: none. Shapes: one mapping."""
    from flyonenomics.io import read_json

    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"rest record is not a mapping: {path}")
    return payload


def declared_substrate() -> dict[str, Any] | None:
    """Item 122's declared resting substrate, or None when the records are absent.

    Reads `validation/records/p2/rest-T3e-decision.json` (the 3e screen,
    item 111) and `rest-T3e-freeze-partial.json` (the ten-seed freeze,
    item 121). Units: mV for weights, ratios for scales, Hz for rates.
    Shapes: one mapping with the candidate, its arm, and both records.
    """
    if not all(path.is_file() for path in REST_RECORDS):
        return None
    rows: dict[str, dict[str, Any]] = {}
    for path in REST_RECORDS:
        record = _read_record(path)
        row = record.get("closest_miss")
        if not isinstance(row, dict) or str(row.get("candidate_id")) != DECLARED_SUBSTRATE_ID:
            return None
        rows[path.name] = row
    decision = rows["rest-T3e-decision.json"]
    freeze = rows["rest-T3e-freeze-partial.json"]
    freeze_record = _read_record(REST_RECORDS[1])
    setting = freeze.get("setting") if isinstance(freeze.get("setting"), dict) else {}
    arm = freeze.get("arm") if isinstance(freeze.get("arm"), dict) else {}
    b_hz = [float(v) for v in freeze.get("b_hz", [])]
    a_hz = [float(v) for v in freeze.get("a_hz", [])]
    from flyonenomics.validation.binding import sha256_file

    return {
        "item": 122,
        "candidate_id": DECLARED_SUBSTRATE_ID,
        "arm_id": str(arm.get("id") or freeze.get("arm_id") or "sens"),
        "bg_policy": str(arm.get("bg_policy") or "sens"),
        "w_bg_mv": float(freeze.get("w_bg", 1.0)),
        "g_gaba": float(freeze.get("g_gaba", 1.0)),
        "g_glu": float(freeze.get("g_glu", 4.0)),
        "sigma_th_mv": float(freeze.get("sigma_th", 0.0)),
        "optic_exemption": bool(freeze.get("optic_exemption", False)),
        "n_bg": int(freeze.get("n_bg", 100)),
        "g_gaba_kc": float(setting.get("g_gaba_kc", freeze.get("g_gaba_kc", 6.0))),
        "engine_model": str(freeze.get("engine_model", "lif")),
        "screen": {
            "passed": bool(decision.get("screen_passed", False)),
            "F_max": decision.get("measured_F_max_pair"),
            "KC_hz": decision.get("measured_kc_hz_mean"),
            "central_hz": decision.get("measured_central_hz_mean"),
            "mn9_dark_max_hz": decision.get("mn9_dark_max_hz"),
        },
        "freeze": {
            "seeds": "11-20",
            "F_max": freeze.get("measured_F_max_pair"),
            "KC_hz": freeze.get("measured_kc_hz_mean"),
            "central_hz": freeze.get("measured_central_hz_mean"),
            "mn9_dark_max_hz": freeze.get("mn9_dark_max_hz"),
            "reflex_mean_hz": float(sum(b_hz) / len(b_hz)) if b_hz else None,
            "reflex_min_hz": min(b_hz) if b_hz else None,
            "a_min_hz": min(a_hz) if a_hz else None,
            "bare_hz": freeze_record.get("job_bare_mean"),
            "retention": (freeze.get("retention") or {}).get("extended"),
        },
        "records": [
            {"path": path.relative_to(REPO).as_posix(), "sha256": sha256_file(path)}
            for path in REST_RECORDS
        ],
    }


def declared_substrate_present() -> bool:
    """Return whether item 122's declared substrate is committed. Units: none."""
    return declared_substrate() is not None


def declared_drive_present() -> bool:
    """Return whether the declared substrate's drive document exists. Units: none."""
    return DECLARED_DRIVE_PATH.is_file()


def declared_substrate_id() -> str | None:
    """Return the declared drive's substrate id, or None when it is absent.

    The id is the drive file's SHA-256 tag (`rest:<16 hex>`), the same one
    every rest entry binds.
    """
    if not declared_drive_present():
        return None
    from flyonenomics.drive.mechanisms import substrate_id_for

    return substrate_id_for(DECLARED_DRIVE_PATH)


def _committed_rate_cells() -> dict[str, Any]:
    """V3 and three-seed V1 cells from the committed R3 record. Units: Hz."""
    if not R3_RECORD.is_file():
        return {}
    record = _read_record(R3_RECORD)
    table = record.get("table")
    if not isinstance(table, list) or not table:
        return {}
    row = table[0]
    if not isinstance(row, dict) or str(row.get("candidate_id")) != DECLARED_SUBSTRATE_ID:
        return {}
    cells = row.get("rates")
    return cells if isinstance(cells, dict) else {}


def _declared_row(rate_cells: dict[str, Any] | None = None) -> dict[str, Any]:
    """The R3 table row for item 122's declared unit. Units: Hz, mV, ratios.

    `rate_cells` fills the V3 and three-seed V1 cells from a run; when it is
    None the committed R3 record's cells are used, or nulls while the run
    has not happened.
    """
    declared = declared_substrate()
    if declared is None:
        raise ValueError("item 122 declared substrate is not committed")
    if rate_cells is None:
        rate_cells = _committed_rate_cells()
    if not rate_cells:
        rate_cells = {str(float(rate)): {"v3": None, "v1_three_seed": None} for rate in V_CAL_RATES_HZ}
    cells = list(rate_cells.values())
    measured = any(cell.get("v3") is not None for cell in cells)
    passed = any(
        (cell.get("v3") or {}).get("passed")
        and (cell.get("v1_three_seed") or {}).get("passed") for cell in cells
    ) if measured else None
    return {
        "rank": 1,
        "candidate_id": str(declared["candidate_id"]),
        "arm_id": declared["arm_id"],
        "w_bg_mv": declared["w_bg_mv"],
        "g_gaba": declared["g_gaba"],
        "g_glu": declared["g_glu"],
        "sigma_th_mv": declared["sigma_th_mv"],
        "n_bg": declared["n_bg"],
        "g_gaba_kc": declared["g_gaba_kc"],
        "engine_model": declared["engine_model"],
        "declared": True,
        "screen": declared["screen"],
        "freeze": declared["freeze"],
        "rates": rate_cells,
        "passed": passed,
    }


def r3_record(rate_cells: dict[str, Any] | None = None) -> dict[str, Any]:
    """R3's record with the V3 and three-seed V1 cells filled. Units: Hz."""
    row = _declared_row(rate_cells)
    return {
        "status": "recorded",
        "reason": (
            "item 122 declares the sensory-only 1.0 mV substrate; the V3 and "
            "three-seed V1 cells are the V-cal screen recorded at r_light"
        ),
        "rates_hz": list(V_CAL_RATES_HZ),
        "r3_max": R3_MAX,
        "candidates": [row],
        "table": [row],
        "substrate_id": declared_substrate_id(),
        "declared_substrate": declared_substrate(),
    }


def run_r3(candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Record R3's table on item 122's declared substrate. Units: Hz.

    A constructed `candidates` list keeps the section 3.4 table shape for
    tests. With no list, item 122's unit is rank 1 and its recorded R-screen
    and freeze facts fill the row; the V3 and three-seed V1 cells need the
    declared drive and an engine run.
    """
    if candidates:
        return {
            "status": "recorded",
            "reason": "constructed candidate table; engine screen waits on the declared substrate drive",
            "rates_hz": list(V_CAL_RATES_HZ),
            "r3_max": R3_MAX,
            "candidates": list(candidates),
            "table": [
                {
                    "rank": int(row.get("rank", index + 1)),
                    "id": row.get("id"),
                    "rates": {rate: {"v3": None, "v1_three_seed": None} for rate in V_CAL_RATES_HZ},
                    "passed": False,
                }
                for index, row in enumerate(candidates[:R3_MAX])
            ],
        }
    if not declared_substrate_present():
        return {
            "status": "blocked",
            "reason": "Waiting for item 122's declared substrate records",
            "rates_hz": list(V_CAL_RATES_HZ),
            "r3_max": R3_MAX,
            "candidates": [],
            "table": [],
        }
    return r3_record()


def run_vcal(r3_table: dict[str, Any] | None = None) -> dict[str, Any]:
    """Choose the lowest r_light that passes V3 and three-seed V1, then ten-seed V1.

    Stage 1 uses {50, 100, 150, 300} Hz. Stage 2 uses {25, 10} Hz when no
    rate passes V3. On selection WP18 commits data/visual-v0.2.yaml.
    Units: Hz. Shapes: one outcome mapping. The substrate is item 122's
    declared unit, not a WP19 Q-rest result.
    """
    declared = declared_substrate()
    if declared is None:
        return {
            "status": "blocked",
            "reason": "Waiting for item 122's declared substrate records",
            "stage1_hz": list(V_CAL_RATES_HZ),
            "stage2_hz": list(V_CAL_EXTENSION_HZ),
            "selected_r_light_hz": None,
            "visual_commit": None,
            "r3_table": r3_table,
            "declared_substrate": None,
        }
    if not declared_drive_present():
        return {
            "status": "blocked",
            "reason": "Waiting for the declared substrate drive data/drive-v0.2.yaml (WP19)",
            "stage1_hz": list(V_CAL_RATES_HZ),
            "stage2_hz": list(V_CAL_EXTENSION_HZ),
            "selected_r_light_hz": None,
            "visual_commit": None,
            "r3_table": r3_table,
            "declared_substrate": declared,
        }
    if VCAL_RECORD.is_file():
        return {**_read_record(VCAL_RECORD), "declared_substrate": declared}
    return {
        "status": "blocked",
        "reason": "The declared substrate is ready; the V-cal engine run is not yet recorded",
        "stage1_hz": list(V_CAL_RATES_HZ),
        "stage2_hz": list(V_CAL_EXTENSION_HZ),
        "selected_r_light_hz": None,
        "visual_commit": None,
        "r3_table": r3_table,
        "declared_substrate": declared,
    }


STAGE: dict[str, Callable[[], dict[str, Any]]] = {"R3": run_r3}
P2_STAGE = {"R3": run_r3, "V-cal": run_vcal}
