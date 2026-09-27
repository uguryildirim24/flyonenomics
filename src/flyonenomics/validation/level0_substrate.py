"""Level 0 test 0.10 pure leg: transmitter rule and scale composition (WP14)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from flyonenomics.substrate.scales import scale_array
from flyonenomics.substrate.transmitters import (
    CLASS_NAMES,
    annotations_in_engine,
    classify_rows,
    curated_class,
    load_connection_columns,
    load_transmitters,
    PHOTORECEPTOR_TYPES,
    presynaptic_signs,
    engine_signs,
)
from flyonenomics.types import LayerFlags
from flyonenomics.validation.binding import ValidationEntry, build_identity

REPO = Path(__file__).resolve().parents[3]
G_GLU = 4.0
G_GABA = 2.0

# Constructed annotation table covering every section 2.2.1 clause.
_CONSTRUCTED = pd.DataFrame({
    "root_id": np.arange(17, dtype=np.int64),
    "cell_type": [
        "R1-6", "L1", "L2", "Tm3", "PAM", "X", "Y", "L1", "R8", "Z",
        "C2", "PPL203", "DN1a", "MsAHN", "W", "V", "U",
    ],
    "known_nt": [
        "", "glutamate", "acetylcholine", "acetylcholine", "dopamine",
        "", "", "glutamate, gaba", "histamine", "",
        "gaba", "dopamine, gaba", " CCHa1, Dh44, Glutamate", "Hist", "", "sNPF", "",
    ],
    "top_nt": [
        "acetylcholine", "gaba", "acetylcholine", "acetylcholine", "dopamine",
        "glutamate", "acetylcholine", "gaba", "acetylcholine", "",
        "acetylcholine", "dopamine", "acetylcholine", "serotonin", "", "gaba", "gaba",
    ],
    "super_class": [
        "sensory", "optic", "optic", "optic", "central",
        "optic", "central", "optic", "sensory", "central",
        "optic", "central", "central", "ascending", "central", "optic", "optic",
    ],
    "s_pq": [
        1.0, -1.0, 1.0, 1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0,
        1.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0,
    ],
})
# Rows 10 to 16: GABA; the question 14 first-classical-token cases with
# whitespace and case; the "Hist" spelling; unk with s_pq > 0; a
# peptide-only label (no curated class, step 3); an unk optic row with
# s_pq > 0 whose top_nt names the other sign.
_EXPECTED_CLASSES = np.array(
    ["His", "Glu", "ACh", "ACh", "mod", "Glu", "ACh", "Glu", "His", "unk",
     "GABA", "GABA", "Glu", "His", "unk", "GABA", "unk"]
)


def _formula_scale(classes: np.ndarray, signs: np.ndarray, super_class: np.ndarray | None) -> np.ndarray:
    """Section 2.2.1 row scale written out row by row. Units: dimensionless."""
    expected = np.empty(len(classes), dtype=np.float32)
    for k, (label, s_pq) in enumerate(zip(classes, signs)):
        if label in ("Glu", "GABA", "His"):
            s_cur = -1.0
        elif label in ("ACh", "mod"):
            s_cur = 1.0
        else:
            s_cur = float(np.sign(s_pq))
        if label == "Glu":
            gain = G_GLU
        elif label == "GABA":
            gain = G_GABA
        elif label == "unk" and s_pq < 0:
            gain = G_GABA
        else:
            gain = 1.0
        if super_class is not None and super_class[k] == "optic" and gain != 1.0 and label != "His":
            gain = 1.0
        expected[k] = np.float32((s_cur / s_pq) * gain)
    return expected


def constructed_leg() -> dict[str, Any]:
    """Section 2.2.1 classes and scale formula on a constructed table.

    Units: dimensionless scales. Shapes: classes (n,), scale (n_syn,).
    """
    frame = _CONSTRUCTED
    signs = frame["s_pq"].to_numpy(dtype=np.float64)
    classes = classify_rows(
        frame["cell_type"].to_numpy(dtype=str),
        frame["known_nt"].to_numpy(dtype=object),
        frame["top_nt"].to_numpy(dtype=object),
        frame["super_class"].to_numpy(dtype=str),
        signs,
        scope="brain",
    )
    class_ok = np.array_equal(classes, _EXPECTED_CLASSES)
    pre = np.arange(len(frame), dtype=np.int32)
    scale = scale_array(classes, signs, pre, g_glu=G_GLU, g_gaba=G_GABA)
    expected_scale = _formula_scale(classes, signs, None)
    groups = frame["super_class"].to_numpy(dtype=str)
    exempt = scale_array(classes, signs, pre, g_glu=G_GLU, g_gaba=G_GABA, optic_exemption=True, super_class=groups)
    exempt_ok = np.array_equal(exempt, _formula_scale(classes, signs, groups))
    scale_ok = np.array_equal(scale, expected_scale)
    optic = classify_rows(
        frame["cell_type"].to_numpy(dtype=str),
        frame["known_nt"].to_numpy(dtype=object),
        frame["top_nt"].to_numpy(dtype=object),
        frame["super_class"].to_numpy(dtype=str),
        signs,
        scope="optic_sensory",
    )
    # optic_sensory applies curated labels only to optic and sensory rows.
    # Central rows fall back to step 3: PPL203 (s_pq +1, top_nt dopamine)
    # is mod, DN1a (s_pq +1, top_nt acetylcholine) is ACh, and the
    # ascending "Hist" row (s_pq +1, top_nt serotonin) is mod.
    expected_optic = _EXPECTED_CLASSES.copy()
    expected_optic[[11, 12, 13]] = ["mod", "ACh", "mod"]
    optic_ok = np.array_equal(optic, expected_optic)
    return {
        "passed": bool(class_ok and scale_ok and exempt_ok and optic_ok),
        "classes": classes.tolist(),
        "expected_classes": _EXPECTED_CLASSES.tolist(),
        "scale": scale.tolist(),
        "expected_scale": expected_scale.tolist(),
        "class_ok": bool(class_ok),
        "scale_ok": bool(scale_ok),
        "optic_exemption_ok": bool(exempt_ok),
        "optic_sensory_ok": bool(optic_ok),
        "optic_sensory_classes": optic.tolist(),
    }


def real_files_leg() -> dict[str, Any]:
    """Section 2.2.1 checks on the pinned annotation and connection files.

    Units: dimensionless signs and scales. Shapes: (n_engine,) and (n_syn,).
    No engine process.
    """
    stored = load_transmitters()
    frame, engine_order = annotations_in_engine()
    table = load_connection_columns(("Presynaptic_ID", "Presynaptic_Index", "Excitatory"))
    unique, mixed = presynaptic_signs(
        table.column("Presynaptic_ID").to_numpy(),
        table.column("Excitatory").to_numpy(),
    )
    signs = engine_signs(engine_order, unique, frame["top_nt"].to_numpy())
    classes = classify_rows(
        frame["cell_type"].fillna("").to_numpy(dtype=str),
        frame["known_nt"].to_numpy(dtype=object),
        frame["top_nt"].to_numpy(dtype=object),
        frame["super_class"].fillna("").to_numpy(dtype=str),
        signs,
        scope="brain",
    )
    stored_classes = stored["class_array"]
    census_match = np.array_equal(classes, stored_classes)
    class_counts = {name: int((classes == name).sum()) for name in CLASS_NAMES}
    counts_match = class_counts == dict(stored["class_counts"])
    from flyonenomics.registry.annotations import load_annotations
    from flyonenomics.substrate.transmitters import curated_vs_top_nt_counts

    curated_table = curated_vs_top_nt_counts(load_annotations("v2.1.0"))
    curated_table_match = curated_table == dict(stored["curated_vs_top_nt"])
    mixed_match = sorted(int(v) for v in mixed) == sorted(int(v) for v in stored["mixed_sign_neurons"])
    types = frame["cell_type"].fillna("").astype(str).to_numpy()
    photoreceptor = np.isin(types, tuple(PHOTORECEPTOR_TYPES))
    l1 = types == "L1"
    l1_glu = bool(np.all(classes[l1] == "Glu")) if np.any(l1) else False
    # His outside the photoreceptor types only through a curated histamine label.
    curated_his = np.array([curated_class(value) == "His" for value in frame["known_nt"].to_numpy(dtype=object)])
    his_is_pr = bool(np.all((photoreceptor | curated_his)[classes == "His"])) and bool(np.all(classes[photoreceptor] == "His"))
    mixed_ok = len(mixed) == 0
    pre_idx = np.asarray(table.column("Presynaptic_Index").to_numpy(), dtype=np.int32)
    s_pq = np.sign(np.asarray(table.column("Excitatory").to_numpy(), dtype=np.float64))
    scale = scale_array(classes, s_pq, pre_idx, g_glu=1.0, g_gaba=1.0)
    composed = s_pq * np.asarray(scale, dtype=np.float64)
    pr_pre = photoreceptor[pre_idx]
    pr_inhibitory = bool(np.all(composed[pr_pre] < 0)) if np.any(pr_pre) else False
    s_cur = np.empty(classes.shape[0], dtype=np.float64)
    s_cur[np.isin(classes, ("Glu", "GABA", "His"))] = -1.0
    s_cur[np.isin(classes, ("ACh", "mod"))] = 1.0
    unk = classes == "unk"
    s_cur[unk] = signs[unk]
    changed = np.sign(s_cur) != np.sign(signs)
    known = frame["known_nt"].to_numpy(dtype=object)
    curated = np.array([curated_class(value) is not None for value in known])
    allowed = photoreceptor | curated
    outside = changed & ~allowed
    no_outside = bool(np.count_nonzero(outside) == 0)
    passed = all((
        mixed_ok, census_match, counts_match, l1_glu, his_is_pr,
        pr_inhibitory, no_outside, curated_table_match, mixed_match,
    ))
    return {
        "passed": passed,
        "mixed_sign_n": len(mixed),
        "census_match": bool(census_match),
        "counts_match": bool(counts_match),
        "curated_vs_top_nt_match": bool(curated_table_match),
        "curated_vs_top_nt": curated_table,
        "mixed_sign_match": bool(mixed_match),
        "class_counts": class_counts,
        "l1_glu": l1_glu,
        "l1_n": int(np.count_nonzero(l1)),
        "photoreceptor_his": his_is_pr,
        "photoreceptor_n": int(np.count_nonzero(photoreceptor)),
        "photoreceptor_rows_inhibitory": pr_inhibitory,
        "photoreceptor_rows": int(np.count_nonzero(pr_pre)),
        "sign_changes": int(np.count_nonzero(changed)),
        "sign_changes_outside_curated_or_pr": int(np.count_nonzero(outside)),
        "n_engine": int(classes.shape[0]),
        "n_syn": int(s_pq.shape[0]),
    }


def test_0_10() -> ValidationEntry:
    """Pure-leg 0.10: constructed table plus real files. Units: counts and flags."""
    constructed = constructed_leg()
    real = real_files_leg()
    passed = bool(constructed["passed"] and real["passed"])
    fixture_path = "data/transmitters-v0.2.yaml"
    identity = build_identity(
        REPO,
        connectome_version="783",
        layers=LayerFlags(),
        assay="transmitter_rule",
        fixture=fixture_path,
    )
    return ValidationEntry(
        test_id="0.10",
        category="verification",
        outcome="passed" if passed else "failed",
        compatibility="canonical",
        identity=identity,
        measured={"constructed": constructed, "real": real},
        data_dependencies=["transmitters-v0.2.yaml", "populations-v0.2.yaml"],
        fixture_path=fixture_path,
    )


SUITE = {"0.10": test_0_10}
