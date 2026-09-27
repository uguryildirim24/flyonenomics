"""Transmitter classes from curated annotations (SPEC-P2 section 2.2.1)."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import yaml
from numpy.typing import NDArray

from flyonenomics.datasets import get_dataset_adapter
from flyonenomics.registry.annotations import (
    cached_path,
    load_annotations,
    load_dataset_annotations,
    load_engine_order,
    provenance_records,
    verify_file,
)
from flyonenomics.substrate.scales import (
    CLASS_NAMES,
    EXCITATORY_CLASSES,
    INHIBITORY_CLASSES,
)

Scope = Literal["brain", "optic_sensory"]
CLASS_CODE: dict[str, str] = {
    "A": "ACh",
    "G": "Glu",
    "B": "GABA",
    "H": "His",
    "M": "mod",
    "U": "unk",
}
CODE_OF_CLASS: dict[str, str] = {name: code for code, name in CLASS_CODE.items()}
PHOTORECEPTOR_TYPES: frozenset[str] = frozenset({"R1-6", "R7", "R8"})
CLASSICAL_NT: dict[str, str] = {
    "acetylcholine": "ACh",
    "glutamate": "Glu",
    "gaba": "GABA",
    "histamine": "His",
    # v2.1.0 writes histamine as "Hist" on four ascending neurons (MsAHN, MtAHN).
    "hist": "His",
}
MODULATORY_NT: frozenset[str] = frozenset(
    {"dopamine", "serotonin", "octopamine", "tyramine"}
)
SHIU_EXCITATORY_TOP: frozenset[str] = frozenset(
    {"acetylcholine", "dopamine", "serotonin", "octopamine", "tyramine"}
)
SHIU_INHIBITORY_TOP: frozenset[str] = frozenset({"glutamate", "gaba", "histamine"})
CONNECTIVITY_ITEM = "Shiu clone Connectivity_783.parquet"
DEFAULT_TRANSMITTERS_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "transmitters-v0.2.yaml"
)
SUPER_CLASS_TABLE: tuple[str, ...] = (
    "sensory",
    "optic",
    "central",
    "visual_projection",
    "descending",
)


def tokenize_known_nt(value: object) -> tuple[str, ...]:
    """Split a known_nt cell into lowercase tokens.

    Units: none. Shapes: a tuple of token strings, empty when absent.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return ()
    return tuple(token.strip().lower() for token in text.split(",") if token.strip())


def curated_class(known_nt: object) -> str | None:
    """Return the section 2.2.1 step-2 class, or None when there is no curated label.

    Units: none. Shapes: one class name or None. The first listed
    acetylcholine, glutamate, GABA, or histamine decides. If the
    sign-determining tokens are only modulatory (dopamine, serotonin,
    octopamine, tyramine), the class is mod. Other co-transmitters do
    not block that reading.
    """
    tokens = tokenize_known_nt(known_nt)
    for token in tokens:
        if token in CLASSICAL_NT:
            return CLASSICAL_NT[token]
    if any(token in MODULATORY_NT for token in tokens):
        return "mod"
    return None


def shiu_sign_from_top_nt(top_nt: object) -> float | None:
    """Return the Shiu sign of a predicted transmitter, or None if unknown.

    Units: dimensionless ±1. Shapes: scalar.
    """
    if top_nt is None or (isinstance(top_nt, float) and np.isnan(top_nt)):
        return None
    token = str(top_nt).strip().lower()
    if token in SHIU_INHIBITORY_TOP:
        return -1.0
    if token in SHIU_EXCITATORY_TOP:
        return 1.0
    return None


def class_sign(label: str, s_pq: float | None = None) -> float:
    """Return s_cur of one class. Units: dimensionless ±1. Shapes: scalar."""
    if label in INHIBITORY_CLASSES:
        return -1.0
    if label in EXCITATORY_CLASSES:
        return 1.0
    if label == "unk":
        if s_pq is None or s_pq == 0 or not np.isfinite(s_pq):
            raise ValueError("unk class needs a finite nonzero connection sign")
        return float(np.sign(s_pq))
    raise ValueError(f"unknown transmitter class: {label}")


def step3_class(top_nt: object, s_pq: float) -> str:
    """Name the class within the connection-file sign (section 2.2.1 step 3).

    Units: s_pq dimensionless ±1. Shapes: one class name.
    """
    token = "" if top_nt is None or (isinstance(top_nt, float) and np.isnan(top_nt)) else str(top_nt).strip().lower()
    if s_pq < 0:
        if token == "glutamate":
            return "Glu"
        if token == "gaba":
            return "GABA"
        return "unk"
    if token == "acetylcholine":
        return "ACh"
    if token in {"dopamine", "serotonin", "octopamine", "tyramine"}:
        return "mod"
    return "unk"


def classify_rows(
    cell_type: NDArray[np.str_],
    known_nt: NDArray[np.object_],
    top_nt: NDArray[np.object_],
    super_class: NDArray[np.str_],
    s_pq: NDArray[np.floating],
    *,
    scope: Scope = "brain",
) -> NDArray[np.str_]:
    """Assign each row a class in {ACh, Glu, GABA, His, mod, unk}.

    Units: labels and dimensionless ±1 signs. Shapes: all inputs (n,),
    return (n,) unicode class names. Photoreceptor types R1-6, R7, and
    R8 are His. Curated labels apply under scope brain to every row,
    and under optic_sensory only to super_class optic and sensory;
    remaining rows keep step 3.
    """
    n = int(cell_type.shape[0])
    if not all(arr.shape == (n,) for arr in (known_nt, top_nt, super_class, s_pq)):
        raise ValueError("classify_rows inputs must share shape (n,)")
    if scope not in ("brain", "optic_sensory"):
        raise ValueError("scope must be brain or optic_sensory")
    if not np.all(np.isfinite(s_pq)) or np.any(np.asarray(s_pq) == 0):
        raise ValueError("s_pq must be finite and nonzero for every neuron")
    types = np.asarray(cell_type, dtype=str)
    groups = np.asarray(super_class, dtype=str)
    signs = np.asarray(s_pq, dtype=np.float64)
    labels = np.empty(n, dtype=object)
    for i in range(n):
        photoreceptor = types[i] in PHOTORECEPTOR_TYPES
        curated = curated_class(known_nt[i])
        apply_curated = scope == "brain" or groups[i] in ("optic", "sensory")
        if apply_curated and photoreceptor:
            labels[i] = "His"
        elif apply_curated and curated is not None:
            labels[i] = curated
        else:
            labels[i] = step3_class(top_nt[i], float(signs[i]))
    return np.asarray(labels, dtype=str)


def connectivity_path() -> Path:
    """Return the verified v783 connectivity parquet. Units: none. Shapes: one path."""
    record = provenance_records()[CONNECTIVITY_ITEM]
    path = cached_path(record)
    verify_file(path, record)
    return path


@lru_cache(maxsize=4)
def load_connection_columns(columns: tuple[str, ...]) -> Any:
    """Read named connectivity columns after checksum. Units: per column. Shapes: one table."""
    from flyonenomics.io import read_parquet

    return read_parquet(connectivity_path(), columns=list(columns))


def presynaptic_signs(pre_id: NDArray[np.int64], excitatory: NDArray[np.floating]) -> tuple[
    dict[int, float], tuple[int, ...]
]:
    """Reduce row signs to one sign per presynaptic neuron.

    Units: Excitatory is dimensionless ±1. Shapes: one mapping of root
    ID to sign, plus the root IDs that have more than one distinct sign.
    """
    if pre_id.shape != excitatory.shape or pre_id.ndim != 1:
        raise ValueError("pre_id and excitatory must be one-dimensional and aligned")
    signs = np.sign(np.asarray(excitatory, dtype=np.float64))
    if not np.all(np.isfinite(signs)) or np.any(signs == 0):
        raise ValueError("Excitatory column must be finite and nonzero")
    pre = np.asarray(pre_id, dtype=np.int64)
    order = np.argsort(pre, kind="mergesort")
    pre_sorted = pre[order]
    sign_sorted = signs[order]
    starts = np.empty(pre_sorted.shape[0], dtype=bool)
    if pre_sorted.size:
        starts[0] = True
        starts[1:] = pre_sorted[1:] != pre_sorted[:-1]
    start_idx = np.flatnonzero(starts)
    mins = np.minimum.reduceat(sign_sorted, start_idx)
    maxs = np.maximum.reduceat(sign_sorted, start_idx)
    roots = pre_sorted[start_idx]
    mixed = tuple(int(v) for v in roots[mins != maxs])
    unique = {int(root): float(sign) for root, sign in zip(roots, mins)}
    return unique, mixed


def engine_signs(
    engine_order: NDArray[np.int64],
    unique: dict[int, float],
    top_nt: NDArray[np.object_],
) -> NDArray[np.float64]:
    """One connection-file sign per engine neuron.

    Units: dimensionless ±1. Shapes: (n,) in engine order. Neurons
    with no outgoing row take the Shiu sign of top_nt, or +1 when
    that is unknown, so every class can form s_cur / s_pq.
    """
    n = int(engine_order.shape[0])
    if top_nt.shape != (n,):
        raise ValueError("top_nt must match engine_order")
    out = np.empty(n, dtype=np.float64)
    for i, root in enumerate(engine_order):
        sign = unique.get(int(root))
        if sign is None:
            predicted = shiu_sign_from_top_nt(top_nt[i])
            sign = 1.0 if predicted is None else predicted
        out[i] = sign
    return out


def annotations_in_engine(
    connectome_version: str = "783",
) -> tuple[pd.DataFrame, NDArray[np.int64]]:
    """Return dataset annotations in the selected engine order.

    Units: per annotation column. Shapes: (n_engine,) rows. Drops
    annotated roots absent from the engine; every engine root must
    have an annotation row.
    """
    annotations = load_dataset_annotations(connectome_version).drop_duplicates("root_id").set_index("root_id")
    engine_order = load_engine_order(connectome_version)  # type: ignore[arg-type]
    missing = [int(root) for root in engine_order if int(root) not in annotations.index]
    if missing:
        raise KeyError(f"engine roots missing from annotations: {missing[:8]}")
    frame = annotations.loc[list(int(v) for v in engine_order)].reset_index()
    return frame, engine_order


def classify_engine(
    *, scope: Scope = "brain", connectome_version: str = "783"
) -> tuple[NDArray[np.str_], pd.DataFrame, dict[str, Any]]:
    """Classify every selected-dataset engine neuron under the transmitter rule.

    Units: classes are labels. Shapes: (n_engine,) classes, the aligned
    annotation frame, and a census mapping. No engine process.
    """
    frame, engine_order = annotations_in_engine(connectome_version)
    if connectome_version == "783":
        table = load_connection_columns(("Presynaptic_ID", "Excitatory"))
    else:
        from flyonenomics.io import read_parquet

        connectivity = get_dataset_adapter(connectome_version).connectome_files().connectivity
        table = read_parquet(
            connectivity, columns=["Presynaptic_ID", "Excitatory x Connectivity"]
        )
        table = table.rename_columns(["Presynaptic_ID", "Excitatory"])
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
        scope=scope,
    )
    census = build_census(
        frame, classes, unique, mixed, signs, connectome_version=connectome_version
    )
    return classes, frame, census


def curated_vs_top_nt_counts(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Count curated known_nt sign disagreements with top_nt, by super_class.

    Units: neuron counts. Shapes: two change rows over SUPER_CLASS_TABLE
    plus total. Only rows with both a curated class and a Shiu top_nt
    sign enter the table.
    """
    known = frame["known_nt"].to_numpy(dtype=object)
    top = frame["top_nt"].to_numpy(dtype=object)
    groups = frame["super_class"].fillna("").astype(str).to_numpy()
    pred_exc_cur_inh = {name: 0 for name in SUPER_CLASS_TABLE}
    pred_inh_cur_exc = {name: 0 for name in SUPER_CLASS_TABLE}
    for known_nt, top_nt, group in zip(known, top, groups):
        curated = curated_class(known_nt)
        predicted = shiu_sign_from_top_nt(top_nt)
        if curated is None or predicted is None or group not in SUPER_CLASS_TABLE:
            continue
        curated_sign = class_sign(curated, 1.0)
        if predicted > 0 and curated_sign < 0:
            pred_exc_cur_inh[group] += 1
        elif predicted < 0 and curated_sign > 0:
            pred_inh_cur_exc[group] += 1
    pred_exc_cur_inh["total"] = int(sum(pred_exc_cur_inh[name] for name in SUPER_CLASS_TABLE))
    pred_inh_cur_exc["total"] = int(sum(pred_inh_cur_exc[name] for name in SUPER_CLASS_TABLE))
    return {
        "predicted excitatory, curated inhibitory": pred_exc_cur_inh,
        "predicted inhibitory, curated excitatory": pred_inh_cur_exc,
    }


def photoreceptor_table(frame: pd.DataFrame, engine_roots: set[int]) -> list[dict[str, Any]]:
    """Reproduce the section 2.2.1 photoreceptor and L1 rows.

    Units: neuron counts. Shapes: one mapping per named cell type.
    """
    rows: list[dict[str, Any]] = []
    wanted = (
        ("R1-6", "His"),
        ("R7", "His"),
        ("R8", "His"),
        ("L1", "Glu"),
        ("L2", "ACh"),
        ("Mi1", "ACh"),
        ("Tm3", "ACh"),
    )
    for cell_type, expected in wanted:
        subset = frame.loc[frame["cell_type"].fillna("").astype(str) == cell_type]
        top_counts = subset["top_nt"].fillna("empty").astype(str).value_counts().to_dict()
        known_values = subset["known_nt"].fillna("none").astype(str).value_counts()
        known_summary = "none" if list(known_values.index[:1]) == ["none"] and len(known_values) == 1 else ", ".join(
            f"{name} {int(count)}" for name, count in known_values.head(4).items()
        )
        in_engine = int(subset["root_id"].astype(np.int64).isin(engine_roots).sum()) if "root_id" in subset else 0
        rows.append({
            "cell_type": cell_type,
            "annotation_count": int(len(subset)),
            "in_engine": in_engine,
            "top_nt": {str(k): int(v) for k, v in top_counts.items()},
            "known_nt": known_summary,
            "class": expected,
        })
    return rows


def build_census(
    frame: pd.DataFrame,
    classes: NDArray[np.str_],
    unique: dict[int, float],
    mixed: tuple[int, ...],
    signs: NDArray[np.floating],
    *,
    connectome_version: str = "783",
) -> dict[str, Any]:
    """Census mapping for transmitters-v0.2.yaml and the evidence document.

    Units: neuron and synapse-free counts. Shapes: nested mappings.
    """
    engine_roots = set(int(v) for v in frame["root_id"].to_numpy())
    class_counts = {name: int((classes == name).sum()) for name in CLASS_NAMES}
    disagreements: list[dict[str, Any]] = []
    for i, root in enumerate(frame["root_id"].to_numpy()):
        predicted = shiu_sign_from_top_nt(frame["top_nt"].iloc[i])
        file_sign = unique.get(int(root))
        if predicted is None or file_sign is None:
            continue
        if float(np.sign(file_sign)) != float(predicted):
            disagreements.append({
                "root_id": int(root),
                "super_class": str(frame["super_class"].iloc[i]),
                "cell_type": str(frame["cell_type"].iloc[i]),
                "top_nt": str(frame["top_nt"].iloc[i]),
                "s_pq": float(file_sign),
            })
    central_mask = frame["super_class"].fillna("").astype(str) == "central"
    curated_changed = []
    for i in np.flatnonzero(central_mask.to_numpy()):
        curated = curated_class(frame["known_nt"].iloc[i])
        predicted = shiu_sign_from_top_nt(frame["top_nt"].iloc[i])
        if curated is None or predicted is None:
            continue
        if class_sign(curated, 1.0) != predicted:
            curated_changed.append({
                "root_id": int(frame["root_id"].iloc[i]),
                "cell_type": str(frame["cell_type"].iloc[i] or ""),
                "hemibrain_type": str(frame["hemibrain_type"].iloc[i] or "") if "hemibrain_type" in frame else "",
                "known_nt": str(frame["known_nt"].iloc[i] or ""),
                "top_nt": str(frame["top_nt"].iloc[i] or ""),
                "curated_class": curated,
            })
    full_annotations = load_dataset_annotations(connectome_version)
    output_roots = set(unique)
    has_output = frame["root_id"].astype(np.int64).isin(output_roots).to_numpy()
    output_by_class = {
        name: int(np.count_nonzero((classes == name) & has_output))
        for name in CLASS_NAMES
    }
    return {
        "n_engine": int(len(frame)),
        "class_counts": class_counts,
        "output_bearing_class_counts": output_by_class,
        "no_output_class_counts": {
            name: class_counts[name] - output_by_class[name] for name in CLASS_NAMES
        },
        "mixed_sign_neurons": [int(v) for v in mixed],
        "curated_vs_top_nt": curated_vs_top_nt_counts(full_annotations),
        "curated_vs_top_nt_engine": curated_vs_top_nt_counts(frame),
        "photoreceptors": photoreceptor_table(full_annotations, engine_roots),
        "s_pq_vs_top_nt_n": len(disagreements),
        "s_pq_vs_top_nt_by_super_class": (
            pd.DataFrame(disagreements)["super_class"].value_counts().to_dict() if disagreements else {}
        ),
        "central_curated_corrections": curated_changed,
        "scope": "brain",
    }


def encode_classes(classes: NDArray[np.str_]) -> str:
    """Pack engine-order classes as one character per neuron. Units: none. Shapes: length n."""
    try:
        return "".join(CODE_OF_CLASS[str(label)] for label in classes)
    except KeyError as exc:
        raise ValueError(f"unencodable class: {exc}") from exc


def decode_classes(packed: str) -> NDArray[np.str_]:
    """Unpack a class string to (n,) names. Units: none. Shapes: (len(packed),)."""
    try:
        return np.asarray([CLASS_CODE[ch] for ch in packed], dtype=str)
    except KeyError as exc:
        raise ValueError(f"unknown class code: {exc}") from exc


def transmitters_payload(
    classes: NDArray[np.str_],
    census: dict[str, Any],
    *,
    connectome_version: str = "783",
) -> dict[str, Any]:
    """Build one dataset's transmitter mapping. Units: counts and labels."""
    packed = encode_classes(classes)
    digest = hashlib.sha256(packed.encode("ascii")).hexdigest()
    male = connectome_version == "male-cns:v1.0"
    return {
        "version": "male-cns-v1.0" if male else "v0.2",
        "annotation_version": "male-cns:v1.0" if male else "v2.1.0",
        "connectome_version": connectome_version,
        "scope": "brain",
        "g_his": 1,
        "class_code": dict(CLASS_CODE),
        "n_engine": int(classes.shape[0]),
        "classes_sha256": digest,
        "classes": packed,
        "class_counts": census["class_counts"],
        "curated_vs_top_nt": census["curated_vs_top_nt"],
        "mixed_sign_neurons": census["mixed_sign_neurons"],
        "s_pq_vs_top_nt_n": census["s_pq_vs_top_nt_n"],
    }


def write_transmitters(
    path: Path | None = None, *, connectome_version: str = "783"
) -> dict[str, Any]:
    """Classify one engine, write its transmitter table, and return the census."""
    classes, _frame, census = classify_engine(
        scope="brain", connectome_version=connectome_version
    )
    payload = transmitters_payload(
        classes, census, connectome_version=connectome_version
    )
    destination = path or DEFAULT_TRANSMITTERS_PATH
    destination.write_text(yaml.safe_dump(payload, sort_keys=False, width=120))
    census["classes_sha256"] = payload["classes_sha256"]
    census["classes"] = classes
    return census


def load_transmitters(path: str | Path | None = None) -> dict[str, Any]:
    """Load transmitters-v0.2.yaml. Units: per field. Shapes: classes (n_engine,)."""
    destination = Path(path) if path is not None else DEFAULT_TRANSMITTERS_PATH
    from flyonenomics.io import read_yaml

    raw = read_yaml(destination)
    packed = "".join(ch for ch in str(raw["classes"]) if ch in CLASS_CODE)
    classes = decode_classes(packed)
    if classes.shape[0] != int(raw["n_engine"]):
        raise ValueError("transmitters class string length does not match n_engine")
    digest = hashlib.sha256(packed.encode("ascii")).hexdigest()
    if digest != str(raw["classes_sha256"]):
        raise ValueError("transmitters classes_sha256 mismatch")
    raw["class_array"] = classes
    return raw


SPEC_CURATED_VS_TOP = {
    "predicted excitatory, curated inhibitory": {
        "sensory": 809, "optic": 533, "central": 8, "visual_projection": 0, "descending": 0, "total": 1350,
    },
    "predicted inhibitory, curated excitatory": {
        "sensory": 5, "optic": 492, "central": 41, "visual_projection": 2, "descending": 2, "total": 542,
    },
}
SPEC_PHOTORECEPTORS = {
    "R1-6": {"annotation_count": 8452, "in_engine": 7932},
    "R7": {"annotation_count": 1343, "in_engine": 1337},
    "R8": {"annotation_count": 1324, "in_engine": 1314},
    "L1": {"annotation_count": 1579},
    "L2": {"annotation_count": 1554},
    "Mi1": {"annotation_count": 1580},
    "Tm3": {"annotation_count": 1746},
}
SPEC_SYNAPSES = {
    "L1->Mi1": 121693,
    "L1->Tm3": 80600,
    "R1_6->L1": 63344,
    "R1_6->L2": 62051,
}


def _md_table(headers: list[str], rows: list[list[object]]) -> str:
    """Render a GitHub markdown table. Units: none. Shapes: text."""
    line = "| " + " | ".join(headers) + " |"
    align = "| --- | " + " | ".join("---:" for _ in headers[1:]) + " |"
    body = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([line, align, *body])


def write_census_document(
    census: dict[str, Any],
    retinotopy: dict[str, Any],
    path: Path | None = None,
) -> Path:
    """Write docs/transmitter-census.md from measured census and retinotopy."""
    curated = census["curated_vs_top_nt"]
    spec = SPEC_CURATED_VS_TOP
    disagreements: list[str] = []
    rows = []
    for key in spec:
        measured = curated[key]
        expected = spec[key]
        row = [key]
        for col in (*SUPER_CLASS_TABLE, "total"):
            row.append(f"{measured[col]:,}")
            if measured[col] != expected[col]:
                disagreements.append(
                    f"{key} / {col}: measured {measured[col]:,}, SPEC-P2 {expected[col]:,}"
                )
        rows.append(row)
    expected_rows = []
    for key in spec:
        expected_rows.append([key] + [f"{spec[key][c]:,}" for c in (*SUPER_CLASS_TABLE, "total")])
    pr_rows = []
    for item in census["photoreceptors"]:
        name = item["cell_type"]
        spec_row = SPEC_PHOTORECEPTORS.get(name, {})
        top = ", ".join(f"{k} {v:,}" for k, v in list(item["top_nt"].items())[:6])
        pr_rows.append([
            name, item["annotation_count"], item["in_engine"], top, item["known_nt"], item["class"],
        ])
        if spec_row.get("annotation_count") not in (None, item["annotation_count"]):
            disagreements.append(
                f"{name} annotation_count measured {item['annotation_count']}, SPEC-P2 {spec_row['annotation_count']}"
            )
        if spec_row.get("in_engine") not in (None, item["in_engine"]):
            disagreements.append(
                f"{name} in_engine measured {item['in_engine']}, SPEC-P2 {spec_row['in_engine']}"
            )
    syn_rows = []
    for pair, expected in SPEC_SYNAPSES.items():
        got = int(retinotopy["synapse_counts"].get(pair, {}).get("synapses", -1))
        syn_rows.append([pair, f"{got:,}", f"{expected:,}", "yes" if got == expected else "NO"])
        if got != expected:
            disagreements.append(f"{pair} synapses measured {got:,}, SPEC-P2 {expected:,}")
    extra_syn = []
    for pair, payload in retinotopy["synapse_counts"].items():
        extra_syn.append([pair, payload["pairs"], payload["synapses"]])
    central = census["central_curated_corrections"]
    by_type: dict[str, int] = {}
    for row in central:
        cell = str(row["cell_type"] or "").strip()
        hemi = str(row["hemibrain_type"] or "").strip()
        if cell and cell.lower() != "nan":
            key = cell
        elif hemi and hemi.lower() != "nan":
            key = hemi
        else:
            key = "(empty type)"
        by_type[key] = by_type.get(key, 0) + 1
    type_lines = "\n".join(
        f"- {name}: {count}" for name, count in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    n_central = len(central)
    n_types = len(by_type)
    concentrated = n_types <= 5 and n_central > 0
    lc10 = retinotopy["types"].get("LC10", {})
    lc10_cover = f"{lc10.get('n_with_azimuth', 0)} of {lc10.get('n', 0)}"
    spread_rows = []
    for name, payload in retinotopy["types"].items():
        median = payload["median_spread_deg"]
        spread_rows.append([
            name, payload["n"], payload["n_with_azimuth"],
            f"{median:.3f}" if np.isfinite(median) else "nan",
            "yes" if payload["column_subsets"] else "no",
            payload["source"],
        ])
    spearman = retinotopy["spearman_L2_vs_own_z"]
    class_rows = [[name, census["class_counts"][name]] for name in CLASS_NAMES]
    disagree_text = "None." if not disagreements else "\n".join(f"- {item}" for item in disagreements)
    if disagreements:
        disagree_text += (
            "\n- The three extra central predicted-excitatory / curated-inhibitory "
            "neurons are two PPL203 (`known_nt` `dopamine, gaba`, first classical "
            "token GABA) and one DN1a (`CCHa1, Dh44, glutamate`). The rule takes "
            "the first listed classical transmitter. Scope stays `brain`."
        )
    q4 = (
        f"Central curated sign corrections: {n_central} neurons across {n_types} types. "
        "Rolf's reading for question 4 is whole-brain scope (`brain`). "
    )
    if concentrated:
        q4 += (
            "Corrections sit in a small number of types; the labels themselves are curated "
            "`known_nt` values, so they are not treated as doubtful. Scope stays `brain`."
        )
    else:
        q4 += (
            "Corrections are not concentrated in a few types with doubtful labels. "
            "Scope stays `brain`."
        )
    body = f"""# Transmitter census (WP14)

Pinned annotation v2.1.0, connectome v783. Scope `brain`. No engine process.

## Classes in engine order

{_md_table(["class", "n"], class_rows)}

`n_engine` = {census["n_engine"]:,}. `classes_sha256` = `{census.get("classes_sha256", "")}`.
Mixed-sign presynaptic neurons: {len(census["mixed_sign_neurons"])}.

## Curated `known_nt` sign vs `top_nt` sign (all annotations)

SPEC-P2 section 2.2.1 table:

{_md_table(["Change", *SUPER_CLASS_TABLE, "total"], expected_rows)}

Measured:

{_md_table(["Change", *SUPER_CLASS_TABLE, "total"], rows)}

Engine-only recomputation: see `curated_vs_top_nt_engine` in the report.

Neurons whose connection-file sign `s_pq` differs from the Shiu rule on `top_nt`: {census["s_pq_vs_top_nt_n"]:,}.

## Photoreceptors, L1, L2, Mi1, Tm3

{_md_table(["Cell type", "Annotation count", "In engine", "top_nt counts", "known_nt", "Class"], pr_rows)}

## Synapse counts (in-engine roots)

SPEC-P2 claims:

{_md_table(["Connection", "Measured synapses", "SPEC-P2", "match"], syn_rows)}

All measured pairs, including L2 targets the census must report:

{_md_table(["Connection", "Pairs", "Synapses"], extra_syn)}

## Disagreements with SPEC-P2 tables

{disagree_text}

## Question 4: central correction concentration

{q4}

Counts by `cell_type`:

{type_lines if type_lines else "- none"}

## Stage retinotopy: median column spread (deg)

A type gets column subsets when median spread ≤ {retinotopy["max_column_spread_deg"]}°.
R1-6 neurons are ranked by `pos_z` per eye; `pos_z` is an integer section index, and tied neurons take
the mean of their ranks. Types are assigned one after another in the listed order, so a later type in
the same stage can use an earlier one's azimuths. Column subsets use only the neurons with an azimuth:
`n_with_azimuth` of `n` is the coverage (LC10 {lc10_cover}, SPEC-P2 section 10 question 17).

{_md_table(["Type", "n", "n_with_azimuth", "median_spread_deg", "column_subsets", "source"], spread_rows)}

L2 propagated azimuth vs rank rule on L2 `pos_z`: Spearman ρ left = {spearman.get("left")}, right = {spearman.get("right")}.
R1-6 retinotopy SHA-256 = `{retinotopy.get("r1_6_sha256") or retinotopy.get("sha256")}`.
"""
    destination = path or (Path(__file__).resolve().parents[3] / "docs" / "transmitter-census.md")
    destination.write_text(body)
    return destination
