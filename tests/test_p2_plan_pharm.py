"""Plan check for WP21 pharmacology files (SPEC-P2 section 6.3)."""
from __future__ import annotations

import json
from pathlib import Path

from flyonenomics.analysis.plan import (
    DECLARED_SUBSTRATE_CANDIDATE_ID,
    OPENLOOP_S,
    all_experiments,
    coupling_sweep_settings,
    declared_substrate,
    dose_sensitivity_settings,
    planning_rows,
    write_experiments,
)
from flyonenomics.types import load_params

ROOT = Path(__file__).resolve().parents[1]
P2 = ROOT / "data" / "experiments" / "p2"
write_experiments(ROOT)


def test_committed_files_match_builder() -> None:
    """Each owned JSON equals the SPEC-P2 builder; nested experiment fields."""
    write_experiments(ROOT)
    built = all_experiments()
    assert set(built) <= {path.name for path in P2.glob("*.json")}
    for name, document in built.items():
        saved = json.loads((P2 / name).read_text())
        assert saved == document
        assert saved["schema_version"] == "1.3"
        assert saved["layers"]["background"] is True
        assert saved["layers"]["dopamine_A"] is True
        assert saved["layers"]["transporter_C"] is True


def test_planning_rows_match_spec_p2_table() -> None:
    """Each WP21 row matches its factors and brain s at settle 2 s."""
    rows = planning_rows()
    for name, row in rows.items():
        assert row["brain_s"] == row["expected"], (name, row)
    assert rows["3.9r-dose"]["brain_s"] == 6_804
    assert rows["3.9r-coupling"]["brain_s"] == 6_600


def test_ablation_probe_forms_and_openloop_duration() -> None:
    """The retained 3.8r ablation exists in both forms; open loop is 47 s."""
    stems = ["ablation-p2"]
    for stem in stems:
        buridan = json.loads((P2 / f"{stem}-buridan.json").read_text())
        openloop = json.loads((P2 / f"{stem}-openloop.json").read_text())
        assert len(buridan["arms"]) == len(openloop["arms"])
        b_probe = next(p for p in buridan["arms"][0]["protocol"] if p["type"] == "probe")
        o_probe = next(p for p in openloop["arms"][0]["protocol"] if p["type"] == "probe")
        assert b_probe["assay"] == "buridan" and b_probe["duration_s"] == 20
        assert o_probe["assay"] == "open_loop_steering" and o_probe["duration_s"] == OPENLOOP_S
        blocks = o_probe["params"]["blocks"]
        assert sum(block["transition_s"] + block["dwell_s"] for block in blocks) == OPENLOOP_S
        assert len(blocks) == 15


def test_coupling_and_dose_files() -> None:
    """3.10r three arms; coupling-sweep drops dop1r1_null; dose-p2 has four arms and three 5 s probes."""
    coupling = json.loads((P2 / "coupling.json").read_text())
    sweep = json.loads((P2 / "coupling-sweep.json").read_text())
    dose = json.loads((P2 / "dose-p2.json").read_text())
    assert [arm["label"] for arm in coupling["arms"]] == ["wild-type", "fumin", "dop1r1-null"]
    assert [arm["label"] for arm in sweep["arms"]] == ["wild-type", "fumin"]
    assert coupling["seeds"] == list(range(1, 11))
    probe = coupling["arms"][0]["protocol"][0]
    assert probe["assay"] == "spontaneous" and probe["params"]["stimulus"] == "dark"
    assert probe["duration_s"] == 20
    assert [arm["label"] for arm in dose["arms"]] == ["vehicle", "mph", "fumin", "fumin-mph"]
    probes = [p for p in dose["arms"][0]["protocol"] if p["type"] == "probe"]
    assert [p["duration_s"] for p in probes] == [5.0, 5.0, 5.0]
    assert [p["label"] for p in probes] == ["dose-0.1", "dose-0.5", "dose-1.0"]
    assert len(dose["arms"]) * len(probes) == 12


def test_3_9r_setting_lists() -> None:
    """27 dose settings and 15 no-drug coupling settings from the Phase 1 3.9 grid."""
    params = load_params()
    dose = dose_sensitivity_settings(params)
    coupling = coupling_sweep_settings(params)
    assert len(dose) == 27
    assert len(coupling) == 15
    assert sum(1 for row in coupling if row["level"] == "default") == 1
    groups = {row["group"] for row in coupling}
    assert groups == {"Kd_D1", "Kd_D2", "gamma_*", "dV_*", "Vmax", "Km", "k_ns"}
    assert "Ki_mph" not in groups and "kappa" not in groups
    defaults = [row for row in dose if row["level"] == "default"]
    assert len(defaults) == 9


def test_schema_13_loader_loads_every_owned_file() -> None:
    """Every WP21 fixture loads through the schema 1.3 model now that WP15 is on main."""
    from flyonenomics.schema import load_experiment
    for name in all_experiments():
        experiment = load_experiment(P2 / name)
        assert experiment.schema_version == "1.3"


def test_every_file_binds_item_122_substrate() -> None:
    """Every pharmacology file names item 122's declared unit in its meta; mV and ratios."""
    declared = declared_substrate()
    assert declared is not None and declared["candidate_id"] == DECLARED_SUBSTRATE_CANDIDATE_ID
    for name in all_experiments():
        saved = json.loads((P2 / name).read_text())
        bound = saved["meta"]["declared_substrate"]
        assert bound["candidate_id"] == DECLARED_SUBSTRATE_CANDIDATE_ID, name
        assert bound["arm_id"] == "sens" and bound["bg_policy"] == "sens", name
        assert bound["w_bg_mv"] == 1.0 and bound["g_gaba_kc"] == 6.0, name
        assert bound["engine_model"] == "lif", name
        assert saved["substrate"]["drive_version"] == "v0.2", name
