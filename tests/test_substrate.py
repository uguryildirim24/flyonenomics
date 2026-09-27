"""WP14 substrate contracts. No engine process is built here."""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from flyonenomics.substrate import scale_array


def test_scale_array_signature_and_docstring() -> None:
    """WP15 depends on this signature: float32 (n_syn,) in file order."""
    parameters = inspect.signature(scale_array).parameters
    assert list(parameters)[:5] == ["classes", "s_pq", "pre", "g_glu", "g_gaba"]
    assert parameters["g_his"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["optic_exemption"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["super_class"].kind is inspect.Parameter.KEYWORD_ONLY
    doc = scale_array.__doc__
    assert doc is not None
    assert "float32" in doc
    assert "(n_syn,)" in doc
    assert "set_weight_scale" in doc
    assert "connection-file order" in doc


def test_scale_array_formula_on_constructed_rows() -> None:
    """Each constructed row equals the section 2.2.1 formula."""
    classes = np.array(["ACh", "Glu", "GABA", "His", "mod", "unk", "unk"])
    s_pq = np.array([1.0, 1.0, -1.0, 1.0, 1.0, 1.0, -1.0])
    pre = np.arange(7, dtype=np.int32)
    scale = scale_array(classes, s_pq, pre, g_glu=4.0, g_gaba=2.0)
    assert scale.dtype == np.float32
    assert scale.shape == (7,)
    expected = np.array([1.0, -4.0, 2.0, -1.0, 1.0, 1.0, 2.0], dtype=np.float32)
    np.testing.assert_array_equal(scale, expected)


def test_scale_array_optic_exemption_drops_inhibitory_gains() -> None:
    """Optic exemption keeps the curated sign and sets g_glu and g_gaba to 1."""
    classes = np.array(["Glu", "GABA", "Glu"])
    s_pq = np.array([1.0, -1.0, 1.0])
    pre = np.array([0, 1, 2], dtype=np.int32)
    groups = np.array(["optic", "optic", "central"])
    scale = scale_array(
        classes, s_pq, pre, g_glu=4.0, g_gaba=2.0,
        optic_exemption=True, super_class=groups,
    )
    np.testing.assert_array_equal(scale, np.array([-1.0, 1.0, -4.0], dtype=np.float32))


def test_scale_array_rejects_zero_sign() -> None:
    """A zero Excitatory column cannot form s_cur / s_pq."""
    with pytest.raises(ValueError, match="nonzero"):
        scale_array(
            np.array(["ACh"]), np.array([0.0]), np.array([0], dtype=np.int32),
            g_glu=1.0, g_gaba=1.0,
        )


def test_scale_array_rejects_a_sign_magnitude() -> None:
    """s_pq is ±1; a magnitude would silently scale the row by 1/|s_pq|."""
    with pytest.raises(ValueError, match="±1"):
        scale_array(
            np.array(["ACh"]), np.array([2.0]), np.array([0], dtype=np.int32),
            g_glu=1.0, g_gaba=1.0,
        )


def test_classify_rows_constructed_order() -> None:
    """Photoreceptors, curated lists, then step 3, in that order."""
    from flyonenomics.substrate.transmitters import classify_rows
    from flyonenomics.validation.level0_substrate import (
        _CONSTRUCTED, _EXPECTED_CLASSES, constructed_leg,
    )

    frame = _CONSTRUCTED
    classes = classify_rows(
        frame["cell_type"].to_numpy(dtype=str),
        frame["known_nt"].to_numpy(dtype=object),
        frame["top_nt"].to_numpy(dtype=object),
        frame["super_class"].to_numpy(dtype=str),
        frame["s_pq"].to_numpy(dtype=np.float64),
    )
    np.testing.assert_array_equal(classes, _EXPECTED_CLASSES)
    measured = constructed_leg()
    assert measured["passed"]


def test_r16_azimuth_midbin_formula() -> None:
    """Rank r of n maps to ±(r + 0.5) / n × 150° per eye."""
    from flyonenomics.substrate.retinotopy import r16_azimuths

    sides = np.array(["left", "left", "right", "right"])
    z_values = np.array([30.0, 10.0, 5.0, 25.0])
    az = r16_azimuths(sides, z_values)
    assert az[1] == pytest.approx(-0.5 / 2 * 150.0)
    assert az[0] == pytest.approx(-1.5 / 2 * 150.0)
    assert az[2] == pytest.approx(0.5 / 2 * 150.0)
    assert az[3] == pytest.approx(1.5 / 2 * 150.0)
    assert az[1] < 0 and az[2] > 0
    assert az[1] > az[0]


def test_r16_ties_take_the_mean_rank_whatever_the_row_order() -> None:
    """Tied pos_z share one azimuth, and permuting rows changes no neuron's azimuth."""
    from flyonenomics.substrate.retinotopy import r16_azimuths

    sides = np.array(["right"] * 4)
    z_values = np.array([7.0, 3.0, 7.0, 9.0])
    az = r16_azimuths(sides, z_values)
    assert az[0] == az[2] == pytest.approx(round((1.5 + 0.5) / 4 * 150.0, 6))
    assert az[1] < az[0] < az[3]
    perm = np.array([2, 3, 0, 1])
    np.testing.assert_array_equal(r16_azimuths(sides[perm], z_values[perm]), az[perm])


def test_r16_sha256_rehashes_from_the_committed_table() -> None:
    """The recorded SHA-256 covers exactly the committed root ids and azimuths."""
    import hashlib

    from flyonenomics.substrate.retinotopy import _canonical_table_bytes, load_retinotopy

    block = load_retinotopy()
    digest = hashlib.sha256(_canonical_table_bytes(block["types"]["R1_6"])).hexdigest()
    assert digest == block["sha256"]


def test_optic_sensory_scope_leaves_central_on_step3() -> None:
    """optic_sensory applies curated labels only to optic and sensory rows."""
    from flyonenomics.substrate.transmitters import classify_rows

    cell_type = np.array(["L1", "X"])
    known_nt = np.array(["glutamate", "glutamate"], dtype=object)
    top_nt = np.array(["acetylcholine", "acetylcholine"], dtype=object)
    super_class = np.array(["optic", "central"])
    s_pq = np.array([-1.0, 1.0])
    brain = classify_rows(cell_type, known_nt, top_nt, super_class, s_pq, scope="brain")
    optic = classify_rows(cell_type, known_nt, top_nt, super_class, s_pq, scope="optic_sensory")
    np.testing.assert_array_equal(brain, np.array(["Glu", "Glu"]))
    np.testing.assert_array_equal(optic, np.array(["Glu", "ACh"]))


def test_transmitters_yaml_roundtrip() -> None:
    """Committed classes unpack to n_engine names and match the SHA-256."""
    from flyonenomics.substrate.transmitters import load_transmitters

    stored = load_transmitters()
    assert stored["n_engine"] == 138639
    assert stored["class_array"].shape == (138639,)
    assert stored["scope"] == "brain"
    # 10,583 photoreceptors plus four ascending neurons curated as "Hist".
    assert stored["class_counts"]["His"] == 10587


def test_r16_committed_table_is_monotone_per_eye() -> None:
    """V0(a): committed R1-6 azimuth is strictly monotone in pos_z per eye, equal within a z tie."""
    from flyonenomics.registry.annotations import load_annotations
    from flyonenomics.substrate.retinotopy import load_retinotopy

    table = load_retinotopy()["types"]["R1_6"]
    roots = np.asarray(table["root_ids"], dtype=np.int64)
    az = np.asarray(table["azimuth_deg"], dtype=np.float64)
    frame = load_annotations("v2.1.0").drop_duplicates("root_id").set_index("root_id").loc[list(roots)]
    sides = frame["side"].fillna("").astype(str).to_numpy()
    z_values = pd.to_numeric(frame["pos_z"], errors="coerce").to_numpy(dtype=np.float64)
    for side, sign in (("right", 1.0), ("left", -1.0)):
        mask = sides == side
        order = np.argsort(z_values[mask], kind="stable")
        ordered = az[mask][order]
        diffs = np.diff(ordered)
        tied = np.diff(z_values[mask][order]) == 0
        assert np.any(tied)  # pos_z is an integer index; ties are real.
        assert np.all(diffs[tied] == 0)
        if side == "right":
            assert np.all(diffs[~tied] > 0)
            assert ordered.min() > 0.0 and ordered.max() < 150.0
        else:
            assert np.all(diffs[~tied] < 0)
            assert ordered.min() > -150.0 and ordered.max() < 0.0
        assert np.all(np.sign(ordered) == sign)


def test_populations_v02_has_stage_types() -> None:
    """v0.2 keeps v0.1 names and adds R1_6 plus side splits."""
    from flyonenomics.registry.populations import load_population_table
    from flyonenomics.substrate.retinotopy import V02_PATH

    _version, entries = load_population_table(V02_PATH)
    names = [entry.name for entry in entries]
    assert "DAN" in names
    assert "R1_6" in names
    assert "R1_6_L" in names
    assert "R1_6_R" in names
    assert "L2" in names
    assert names.count("MeTu") == 1


def test_0_10_pure_leg() -> None:
    """Gate: constructed table and real files, no engine process."""
    from flyonenomics.validation.level0_substrate import test_0_10

    entry = test_0_10()
    assert entry.test_id == "0.10"
    assert entry.outcome == "passed"
    assert entry.measured["constructed"]["passed"]
    assert entry.measured["real"]["passed"]
    assert entry.measured["real"]["l1_glu"]
    assert entry.measured["real"]["photoreceptor_rows_inhibitory"]
    assert entry.measured["real"]["mixed_sign_n"] == 0


