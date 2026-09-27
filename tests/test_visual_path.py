"""WP10 visual-path diagnostic tests. No frozen data file is written."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from flyonenomics.behaviour.encoder import VisualEncoder
from flyonenomics.diagnostics import visual_path as vp
from flyonenomics.registry.populations import load_population_table
from flyonenomics.types import load_params

ROOT = Path(__file__).resolve().parents[1]
FROZEN = [ROOT / "data" / name for name in vp.FROZEN_DATA_FILES]


def frozen_bytes() -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in FROZEN if path.is_file()}


def test_overlay_loads_and_does_not_mutate_frozen() -> None:
    before = frozen_bytes()
    frozen_names = [entry.name for entry in load_population_table()[1]]
    version, entries = vp.load_overlay_table()
    after = frozen_bytes()
    assert version == "dev"
    assert [entry.name for entry in entries] == list(vp.OVERLAY_NAMES)
    assert "R1_6" not in frozen_names
    assert before == after
    assert [entry.name for entry in load_population_table()[1]] == frozen_names
    r16 = next(entry for entry in entries if entry.name == "R1_6")
    assert r16.inventory_count == 8452
    assert r16.side is None
    l1 = next(entry for entry in entries if entry.name == "L1")
    assert l1.inventory_count == 1579


def test_overlay_resolves_without_touching_frozen_registry() -> None:
    from flyonenomics.registry import annotations as ann

    before = frozen_bytes()
    annotations = ann.load_annotations("v2.1.0")
    order = ann.load_engine_order("783")
    resolved = vp.resolve_overlay(annotations, order)
    after = frozen_bytes()
    assert before == after
    assert resolved["R1_6"].count == 7932
    left = int((resolved["R1_6"].side == "left").sum())
    right = int((resolved["R1_6"].side == "right").sum())
    assert left + right == resolved["R1_6"].count
    assert left > 0 and right > 0
    assert resolved["L1"].count == 1579
    assert resolved["L2"].count == 1554
    assert resolved["R7"].count == 1337
    assert resolved["R8"].count == 1314
    assert resolved["T4"].count == 6240
    assert resolved["LPLC"].count == 460
    assert "TuBu" not in resolved


def test_azimuth_monotone_per_eye_and_signs() -> None:
    sides = np.array(["left", "left", "left", "right", "right", "right"])
    anterior = np.array([30.0, 10.0, 20.0, 5.0, 25.0, 15.0])
    az = vp.retinotopic_azimuths(sides, anterior, (0.0, 150.0))
    left = az[sides == "left"]
    right = az[sides == "right"]
    left_z = anterior[sides == "left"]
    right_z = anterior[sides == "right"]
    assert np.all(left <= 0) and np.all(right >= 0)
    assert np.all(np.diff(left[np.argsort(left_z)]) < 0)
    assert np.all(np.diff(right[np.argsort(right_z)]) > 0)
    assert az[1] == pytest.approx(0.0)
    assert az[0] == pytest.approx(-150.0)
    assert az[2] == pytest.approx(-75.0)
    assert az[3] == pytest.approx(0.0)
    assert az[4] == pytest.approx(150.0)
    assert az[5] == pytest.approx(75.0)
    elev = vp.retinotopic_elevations(sides, np.array([1.0, 2.0, 3.0, 1.0, 2.0, 3.0]))
    assert elev[0] < elev[2]
    assert elev[3] < elev[5]


def test_ap_axis_landmarks_name_z() -> None:
    from flyonenomics.registry import annotations as ann

    axis = vp.check_ap_axis(ann.load_annotations("v2.1.0"))
    assert axis["passed"]
    assert axis["anterior_is"] == "smaller z"
    assert axis["units"]["x"] == "4 nm voxels"
    assert axis["units"]["z"] == "40 nm section index"
    assert axis["landmarks"]["ALPN_mean_z_sections"] < axis["landmarks"]["Kenyon_Cell_mean_z_sections"]
    assert axis["R1_6_right_mean_x_voxels"] > axis["R1_6_left_mean_x_voxels"]
    assert axis["R1_6_soma_missing"] == 8451
    assert axis["elevation_used_for_rates"] is False
    assert "not a measured receptive field" in axis["note"].lower() or "Monotone" in axis["note"]


def test_condition_grid_sizes() -> None:
    smoke = vp.condition_grid(smoke=True)
    assert len(smoke) == 1
    assert smoke[0]["site"] == "R1_6"
    full = vp.condition_grid(mode="full")
    assert len(full) == 4 * 3 * 3 * 3 + 3
    stripes = vp.condition_grid(mode="stripes300")
    assert len(stripes) == 3 * 2 * 3
    assert {row["rate_hz"] for row in stripes} == {300.0}
    assert "full" not in {row["azimuth"] for row in stripes}


def test_stripe_rates_match_encoder_gaussian() -> None:
    params = load_params()
    idx = np.array([0, 1, 2], dtype=np.int32)
    roots = np.array([11, 12, 13], dtype=np.int64)
    sides = np.array(["left", "left", "right"])
    registry = SimpleNamespace(population=lambda name: SimpleNamespace(
        idx=idx, root_ids=roots, side=sides,
    ))
    encoder = VisualEncoder(registry, idx, params, "TuBu")
    stimuli = [{"az_fly": -45.0, "contrast": 1.0}]
    from_encoder = encoder.rates(stimuli, maximum_hz=150.0, sigma_deg=20.0)
    from_diag = np.zeros(len(idx))
    from_diag[:] = vp.gaussian_stripe_rates(encoder.preferred, -45.0, 150.0, 20.0)
    np.testing.assert_allclose(from_encoder, from_diag)
    full = vp.gaussian_stripe_rates(encoder.preferred, 0.0, 50.0, 20.0)
    assert np.all(full <= 50.0)


def test_first_silent_stage_on_constructed_rates() -> None:
    silent = {name: 0.0 for name in vp.MEASURED_NAMES}
    silent["R1_6"] = 120.0
    silent["R7"] = 80.0
    silent["R8"] = 90.0
    assert vp.first_silent_stage(silent) == "lamina"
    silent["L1"] = 10.0
    silent["L2"] = 8.0
    assert vp.first_silent_stage(silent) == "medulla_relay"
    active = {name: 2.0 for name in vp.MEASURED_NAMES}
    assert vp.first_silent_stage(active) is None
    empty = {"R1_6": 0.1, "R7": 0.1, "R8": 0.1}
    assert vp.first_silent_stage(empty) == "photoreceptors"


def test_json_round_trip(tmp_path: Path) -> None:
    payload = vp.condition_payload(
        commit="abc", params_hash="def", seed_master=20260912, seed=1, site="R1_6",
        azimuth="-45", rate_hz=150.0, multiplier=1.0, settle_s=0.5, record_s=2.0,
        bin_rates_hz={"R1_6": [1.0, 2.0]}, mean_rate_hz={"R1_6": 1.5},
        network_mean_hz=0.01, steering_diff_hz=0.0, first_silent_stage="lamina",
        spike_count=12, n_neurons=4,
    )
    path = tmp_path / "cond.json"
    vp.write_json(path, payload)
    loaded = vp.read_json(path)
    assert loaded["site"] == "R1_6"
    assert loaded["multiplier"] == 1.0
    assert loaded["first_silent_stage"] == "lamina"
    assert loaded["bin_rates_hz"]["R1_6"] == [1.0, 2.0]
    vp.write_propagation_csv(tmp_path / "propagation.csv", [{**loaded, "id": "x"}])
    text = (tmp_path / "propagation.csv").read_text()
    assert "R1_6" in text and "steering_diff_hz" in text


def test_verdict_classifier_on_constructed_tables() -> None:
    def row(site: str, rates: dict[str, float], diff: float = 0.0) -> dict:
        return {"site": site, "mean_rate_hz": rates, "steering_diff_hz": diff}

    lal = row("LAL_neurons", {"steering_L": 80.0, "steering_R": 60.0, "LAL_neurons": 200.0})
    pr = row("R1_6", {"R1_6": 200.0, "visual_projection": 0.0, "LAL_neurons": 0.0, "steering_L": 0.0, "steering_R": 0.0})
    tubu = row("TuBu", {"TuBu": 50.0, "visual_projection": 0.0, "steering_L": 0.0, "steering_R": 0.0})
    substrate = vp.suggest_verdict([lal, pr, tubu])
    assert substrate["verdict"] == "substrate"
    placed = row("R1_6", {"R1_6": 200.0, "visual_projection": 5.0, "steering_L": 0.0, "steering_R": 0.0})
    silent_tubu = row("TuBu", {"TuBu": 40.0, "visual_projection": 0.0, "LAL_neurons": 0.0, "steering_L": 0.0, "steering_R": 0.0})
    assert vp.suggest_verdict([lal, placed, silent_tubu])["verdict"] == "encoder placement"


def test_overlay_never_mutates_built_frozen_registry() -> None:
    """Review r11: the built frozen registry is identical before and after the overlay path."""
    from flyonenomics.registry import annotations as ann
    from flyonenomics.registry import build_registry

    frozen = build_registry()
    names = frozen.populations()
    snapshot = {
        name: (
            frozen.population(name).root_ids.copy(),
            frozen.population(name).idx.copy(),
            frozen.population(name).side.copy(),
            frozen.population(name).count,
            frozen.population(name).selector,
        )
        for name in names
    }
    annotations = ann.load_annotations("v2.1.0")
    overlay = vp.resolve_overlay(annotations, ann.load_engine_order("783"))
    combined = vp.CombinedPopulations(overlay, frozen).as_dict()
    params = load_params()
    for site in vp.SITES:
        vp.site_preferred(site, combined, annotations, params)
    vp.build_extended_idx(combined)
    assert frozen.populations() == names
    assert not ((set(vp.OVERLAY_NAMES) - {"MeTu"}) & set(names))
    assert overlay["MeTu"] is not frozen.population("MeTu")
    for name in names:
        population = frozen.population(name)
        root_ids, idx, side, count, selector = snapshot[name]
        np.testing.assert_array_equal(population.root_ids, root_ids)
        np.testing.assert_array_equal(population.idx, idx)
        np.testing.assert_array_equal(population.side, side)
        assert population.count == count
        assert population.selector == selector
    for name in vp.FROZEN_REUSE_NAMES:
        assert combined[name] is frozen.population(name)


@pytest.mark.parametrize("site", ["R1_6", "L1+L2"])
def test_site_azimuth_direction_on_annotations(site: str) -> None:
    """Review r11: front (small z) is 0 deg, back is +-150 deg, left eye negative, left eye at smaller x."""
    from flyonenomics.registry import annotations as ann

    annotations = ann.load_annotations("v2.1.0")
    overlay = vp.resolve_overlay(annotations, ann.load_engine_order("783"))
    params = load_params()
    back = float(params.get("vis.pref_range")[1])
    assert back == pytest.approx(150.0)
    idx, preferred = vp.site_preferred(site, overlay, annotations, params)
    _, roots, sides = vp.site_members(vp.SITES[site], overlay)
    loc = vp.locations_for_roots(roots, annotations)
    assert set(sides.tolist()) == {"left", "right"}
    assert loc[sides == "left", 0].mean() < loc[sides == "right", 0].mean()
    for side, sign in (("left", -1.0), ("right", 1.0)):
        members = np.flatnonzero(sides == side)
        z = loc[members, 2]
        az = preferred[members]
        assert np.all(sign * az >= 0.0)
        assert az[np.argmin(z)] == pytest.approx(0.0)
        assert az[np.argmax(z)] == pytest.approx(sign * back)
        ordered = az[np.argsort(z, kind="stable")]
        assert np.all(sign * np.diff(ordered) >= 0.0)


def test_stripe_rates_equal_encoder_for_params_sigma() -> None:
    """Review r11: diagnostic stripe rates equal VisualEncoder.rates for vis.sigma_vis, contrast 1."""
    params = load_params()
    sigma = float(params.get("vis.sigma_vis"))
    sides = np.array(["left"] * 40 + ["right"] * 40)
    z = np.concatenate([np.arange(40.0)[::-1], np.arange(40.0)])
    preferred = vp.retinotopic_azimuths(sides, z, tuple(params.get("vis.pref_range")))
    site_idx = np.arange(10, 90, dtype=np.int32)
    extended_idx = np.arange(0, 100, dtype=np.int32)
    registry = SimpleNamespace(population=lambda name: SimpleNamespace(
        idx=site_idx, root_ids=np.arange(site_idx.size, dtype=np.int64), side=sides,
    ))
    encoder = VisualEncoder(registry, extended_idx, params, "R1_6")
    encoder.preferred = preferred
    for azimuth in (-45.0, 45.0, 0.0, 170.0, -180.0):
        from_encoder = encoder.rates(
            [{"az_fly": azimuth, "contrast": 1.0}], maximum_hz=vp.R_MAX_HZ, sigma_deg=sigma,
        )
        from_diag = vp.extended_rates(
            extended_idx, site_idx, preferred, azimuth=str(azimuth), rate_hz=vp.R_MAX_HZ,
            sigma_deg=sigma, multiplier=1.0, uniform=False,
        )
        np.testing.assert_array_equal(from_encoder, from_diag)
        np.testing.assert_array_equal(
            from_diag[site_idx], vp.gaussian_stripe_rates(preferred, azimuth, vp.R_MAX_HZ, sigma),
        )
        assert from_diag[:10].sum() == 0.0 and from_diag[90:].sum() == 0.0
    peak = vp.gaussian_stripe_rates(np.array([45.0, 65.0]), 45.0, vp.R_MAX_HZ, sigma)
    assert peak[0] == pytest.approx(vp.R_MAX_HZ)
    assert peak[1] == pytest.approx(vp.R_MAX_HZ * np.exp(-0.5 * (20.0 / sigma) ** 2))


def test_first_silent_stage_silent_middle_stage() -> None:
    """Review r11: the first silent stage is found even when later stages fire."""
    rates = {name: 5.0 for name in vp.MEASURED_NAMES}
    rates["T4"] = 0.4
    rates["T5"] = 0.49
    assert vp.first_silent_stage(rates) == "motion"
    rates["T5"] = 0.5
    assert vp.first_silent_stage(rates) is None
    rates["Mi1"] = 0.0
    rates["Tm3"] = 0.0
    rates["T5"] = 0.0
    assert vp.first_silent_stage(rates) == "medulla_relay"
    lamina_site = {name: 0.0 for name in vp.MEASURED_NAMES}
    lamina_site.update({"L1": 128.0, "L2": 119.0, "steering_L": 2.75, "DNa02_L": 5.5})
    assert vp.first_silent_stage(lamina_site) == "photoreceptors"


def test_condition_json_and_csv_round_trip_exact(tmp_path: Path) -> None:
    """Review r11: condition JSON round-trips to an equal mapping and CSV cells read back."""
    import csv

    means = {name: float(position) / 7.0 for position, name in enumerate(vp.MEASURED_NAMES)}
    payload = vp.condition_payload(
        commit="a" * 40, params_hash="b" * 64, seed_master=20260912, seed=3, site="L1+L2",
        azimuth="full", rate_hz=300.0, multiplier=1.0, settle_s=0.5, record_s=2.0,
        bin_rates_hz={name: [value, value] for name, value in means.items()},
        mean_rate_hz=means, network_mean_hz=0.123456789012345, steering_diff_hz=-2.75,
        first_silent_stage=None, spike_count=466331, n_neurons=138639,
    )
    path = tmp_path / "conditions" / "cond.json"
    vp.write_json(path, payload)
    loaded = vp.read_json(path)
    assert loaded == payload
    ident = vp.condition_id("L1+L2", "full", 300.0, 3)
    assert ident == "L1-L2_azfull_rate300_seed3"
    vp.write_propagation_csv(tmp_path / "propagation.csv", [{**loaded, "id": ident}])
    with (tmp_path / "propagation.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == ident and row["site"] == "L1+L2" and row["first_silent_stage"] == ""
    assert int(row["spike_count"]) == 466331
    assert float(row["steering_diff_hz"]) == -2.75
    for name, value in means.items():
        assert float(row[f"mean_{name}"]) == value


def test_tiny_engine_json_round_trip(tmp_path: Path) -> None:
    destination = vp.run_tiny(tmp_path)
    payload = vp.read_json(destination / "conditions" / "tiny.json")
    assert payload["n_neurons"] == 4
    assert payload["site"] == "R1_6"
    table = (destination / "propagation.csv").read_text()
    assert "steering_diff_hz" in table
    replay = vp.read_json(destination / "conditions" / "tiny.json")
    assert replay == payload
    before = frozen_bytes()
    vp.run_tiny(tmp_path / "second")
    assert frozen_bytes() == before
