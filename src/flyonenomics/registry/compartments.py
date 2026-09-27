"""Compartment maps W (exposure) and M (innervation) in five fixed steps (WP2).

Step 1 builds target rows of W from annotation only. Step 2 sums
candidate DAN output onto the fixed target mask from the weighted
connectivity. Step 3 filters candidates by their central-complex
output fraction. Step 4 builds M for DAN and CX_DAN columns. Step 5
adds autoreceptor rows of W. No step depends on a later one; the
mask of step 1 never sees the filter outcome.

Tables are pandas only at the file boundary; maps are SciPy sparse
CSR matrices (float32). Thresholds arrive as arguments (read from
data/params-v0.1.yaml by the caller), compartment ids and the Aso
2014 type table from data/compartments-v0.1.yaml.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sparse
from numpy.typing import NDArray
from pydantic import Field

from flyonenomics.registry.populations import StrictModel

#: The seven central-complex compartments. Units: none. Shapes: names only.
CX_COMPARTMENTS: tuple[str, ...] = ("EB", "PB", "FB", "NO_L", "NO_R", "LAL_L", "LAL_R")

_MB_LOBES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("gamma", ("gamma1", "gamma2", "gamma3", "gamma4", "gamma5")),
    ("alpha", ("alpha1", "alpha2", "alpha3")),
    ("beta", ("beta1", "beta2")),
    ("alpha_prime", ("alpha_prime1", "alpha_prime2", "alpha_prime3")),
    ("beta_prime", ("beta_prime1", "beta_prime2")),
)


def compartment_names() -> list[str]:
    """Return the 37 compartment names in fixed id order.

    Units: none. Shapes: 37 names. The fifteen mushroom-body
    compartments per side come first (left 0..14, right 15..29),
    then EB, PB, FB, NO_L, NO_R, LAL_L, LAL_R (30..36).
    """
    names: list[str] = []
    for side in ("L", "R"):
        for _, stems in _MB_LOBES:
            names.extend(f"{stem}_{side}" for stem in stems)
    names.extend(CX_COMPARTMENTS)
    return names


def compartment_index() -> dict[str, int]:
    """Map compartment name to integer id.

    Units: ids are dimensionless. Shapes: 37 entries.
    """
    return {name: position for position, name in enumerate(compartment_names())}


class ExcludedCandidate(StrictModel):
    """One candidate DAN removed by the connectivity filter.

    Units: fraction is dimensionless output share. Shapes: scalars.
    """

    root: int = Field(ge=0)
    fraction: float = Field(ge=0, le=1)


class CxdanRecord(StrictModel):
    """Pre- and post-filter CX_DAN inventories with the excluded roots.

    Units: counts are neurons; fractions dimensionless. Shapes:
    scalars and one row per excluded root.
    """

    threshold_source: str = Field(min_length=1)
    pre_count: int = Field(ge=0)
    post_count: int = Field(ge=0)
    excluded: list[ExcludedCandidate] = Field(default_factory=list)


class UnplacedDanType(StrictModel):
    """One DAN hemibrain type the Aso 2014 table does not place.

    Units: none. Shapes: one row per type. Such types get an
    all-zero M column.
    """

    hemibrain_type: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class CompartmentTable(StrictModel):
    """The curated content of data/compartments-v0.1.yaml.

    Units: ids dimensionless; M/W weights dimensionless. Shapes:
    37 compartments; one entry per MBON/DAN type present in the
    annotation file. mbon_compartments maps MBON hemibrain type to
    Phase 1 compartments (dendritic compartment only; multi-
    compartment types split equally). dan_compartments maps DAN
    hemibrain type to Phase 1 compartments (each weight 1/k).
    """

    version: str = Field(min_length=1)
    compartments: list[str] = Field(min_length=1)
    cx_compartments: list[str] = Field(default_factory=list)
    aso_citation: str = Field(min_length=1)
    mbon_compartments: dict[str, list[str]] = Field(min_length=1)
    mbon_notes: str = ""
    dan_compartments: dict[str, list[str]] = Field(min_length=1)
    bilateral_dan_prefixes: list[str] = Field(default_factory=list)
    bilateral_note: str = ""
    kc_lobe_note: str = ""
    unplaced_dan_types: list[UnplacedDanType] = Field(default_factory=list)
    unplaced_mbon_types: list[UnplacedDanType] = Field(default_factory=list)
    unplaced_kc_types: list[UnplacedDanType] = Field(default_factory=list)
    pedc_note: str = ""
    cxdan: CxdanRecord | None = None
    target_mask_totals: dict[str, int] = Field(default_factory=dict)


def default_compartments_path() -> Path:
    """Return the repo-relative path of the compartments file.

    Units: none. Shapes: a single path.
    """
    return Path(__file__).resolve().parents[3] / "data" / "compartments-v0.1.yaml"


def load_compartment_table(path: str | Path | None = None) -> CompartmentTable:
    """Load the compartments YAML into a validated table.

    Units: per row. Shapes: 37 compartments. Raises if the
    compartment list differs from the fixed order.
    """
    from flyonenomics.io import read_yaml

    resolved = Path(path) if path is not None else default_compartments_path()
    table = CompartmentTable.model_validate(read_yaml(resolved))
    if table.compartments != compartment_names():
        raise ValueError("compartment list differs from the fixed order")
    return table


def _side_suffix(side: str) -> str | None:
    """Map an annotation side to an MB compartment suffix.

    Units: none. Shapes: one string or None for non-lateral sides.
    """
    if side == "left":
        return "L"
    if side == "right":
        return "R"
    return None


def build_target_rows(
    n: int,
    populations: dict[str, NDArray[np.int64]],
    sides: dict[str, NDArray[np.str_]],
    engine_index: dict[int, int],
    mbon_compartments: dict[str, list[str]],
    mbon_types: NDArray[np.str_],
) -> sparse.csr_matrix:
    """Build step-1 target rows of W from annotation only.

    Units: weights are dimensionless exposure shares. Shapes: (n,
    37) float32 CSR; each populated row sums to 1. MBON rows follow
    the Aso 2014 name table (split equally); Kenyon cells spread
    uniformly over their lobe's compartments; EPG/ER/EB_other go to
    EB; PEN/PEG/D7/PB_other to PB; FB_tangential/FB_columnar to FB;
    NO/LAL neurons to their side's compartment. Neurons with a
    non-lateral side split equally across both sides. DAN and
    candidate rows stay zero here.
    """
    index_of_comp = compartment_index()
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []

    def add(engine: int, compartments: list[str], side: str) -> None:
        suffix = _side_suffix(side)
        if compartments and compartments[0] in index_of_comp and "_" not in compartments[0]:
            targets = [index_of_comp[name] for name in compartments]
            weight = 1.0 / len(targets)
            for target in targets:
                rows.append(engine)
                cols.append(target)
                data.append(weight)
            return
        names: list[str] = []
        for stem in compartments:
            names.append(f"{stem}_{suffix}" if suffix is not None else stem)
        if suffix is None:
            expanded: list[str] = []
            for stem in compartments:
                expanded.extend((f"{stem}_L", f"{stem}_R"))
            names = expanded
        targets = [index_of_comp[name] for name in names]
        weight = 1.0 / len(targets)
        for target in targets:
            rows.append(engine)
            cols.append(target)
            data.append(weight)

    gamma = ("gamma1", "gamma2", "gamma3", "gamma4", "gamma5")
    alphabeta = ("alpha1", "alpha2", "alpha3", "beta1", "beta2")
    aprime = ("alpha_prime1", "alpha_prime2", "alpha_prime3", "beta_prime1", "beta_prime2")
    for pop_name, stems in (
        ("KC_g", gamma),
        ("KC_ab", alphabeta),
        ("KC_apbp", aprime),
    ):
        for root, side in zip(populations[pop_name], sides[pop_name], strict=True):
            engine = engine_index.get(int(root))
            if engine is not None:
                add(engine, list(stems), str(side))
    for pop_name, compartments in (
        ("EPG", ["EB"]),
        ("ER", ["EB"]),
        ("EB_other", ["EB"]),
        ("PEN", ["PB"]),
        ("PEG", ["PB"]),
        ("D7", ["PB"]),
        ("PB_other", ["PB"]),
        ("FB_tangential", ["FB"]),
        ("FB_columnar", ["FB"]),
    ):
        for root in populations[pop_name]:
            engine = engine_index.get(int(root))
            if engine is not None:
                add(engine, compartments, "left")
    for pop_name, stem in (("NO_neurons", "NO"), ("LAL_neurons", "LAL")):
        for root, side in zip(populations[pop_name], sides[pop_name], strict=True):
            engine = engine_index.get(int(root))
            if engine is None:
                continue
            suffix = _side_suffix(str(side))
            if suffix is None:
                for full in (f"{stem}_L", f"{stem}_R"):
                    rows.append(engine)
                    cols.append(index_of_comp[full])
                    data.append(0.5)
            else:
                rows.append(engine)
                cols.append(index_of_comp[f"{stem}_{suffix}"])
                data.append(1.0)
    mbon_roots = populations["MBON"]
    for root, side, hemi in zip(mbon_roots, sides["MBON"], mbon_types, strict=True):
        engine = engine_index.get(int(root))
        if engine is None:
            continue
        compartments = mbon_compartments.get(str(hemi))
        if not compartments:
            continue
        if all(name in index_of_comp for name in compartments):
            weight = 1.0 / len(compartments)
            for name in compartments:
                rows.append(engine)
                cols.append(index_of_comp[name])
                data.append(weight)
        else:
            stems = [name.rsplit("_", 1)[0] if name.rsplit("_", 1)[-1] in ("L", "R") else name for name in compartments]
            add(engine, stems, str(side))
    matrix = sparse.csr_matrix(
        (np.asarray(data, dtype=np.float32), (np.asarray(rows), np.asarray(cols))),
        shape=(n, len(compartment_names())),
        dtype=np.float32,
    )
    return matrix


def candidate_sums(
    edges: pd.DataFrame,
    engine_index: dict[int, int],
    candidate_roots: NDArray[np.int64],
    target_w: sparse.csr_matrix,
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Sum candidate DAN output onto compartments (step 2).

    Units: Connectivity is a synapse count; S holds weighted sums
    in the same units, T holds total output synapses. Shapes: S is
    (37, n_candidates), T is (n_candidates,). S[c, j] sums
    Connectivity over rows with presynaptic j times W[post, c];
    T[j] sums Connectivity over all rows with presynaptic j.
    Edges whose postsynaptic root is outside the engine order are
    skipped for S but kept in T.
    """
    n_comp = int(target_w.shape[1])
    n_cand = int(candidate_roots.size)
    position_of = {int(root): slot for slot, root in enumerate(candidate_roots)}
    totals = np.zeros(n_cand, dtype=np.float64)
    sums = np.zeros((n_comp, n_cand), dtype=np.float64)
    pre = edges["Presynaptic_ID"].to_numpy()
    post = edges["Postsynaptic_ID"].to_numpy()
    weight = edges["Connectivity"].to_numpy(dtype=np.float64)
    for pre_root, post_root, count in zip(pre, post, weight, strict=True):
        slot = position_of.get(int(pre_root))
        if slot is None:
            continue
        totals[slot] += count
        post_idx = engine_index.get(int(post_root))
        if post_idx is None:
            continue
        row = target_w.getrow(post_idx)
        if row.nnz:
            sums[row.indices, slot] += count * row.data
    return np.asarray(sums, dtype=np.float32), np.asarray(totals, dtype=np.float32)


def male_roi_candidate_sums(
    partners_path: str | Path,
    candidate_roots: NDArray[np.int64],
    post_sides: dict[int, str],
) -> tuple[NDArray[np.float32], NDArray[np.float32]]:
    """Reduce MaleCNS per-synapse ``primary_post`` ROIs for CX_DAN.

    Units: one row is one released synapse. Shapes: S is (37,
    n_candidates), totals is (n_candidates,). EB/PB/FB and sided LAL
    labels map directly. Unsided NO uses the frozen target-side rule:
    postsynaptic left/right maps to NO_L/NO_R and missing side splits
    0.5/0.5. Every outgoing row enters the denominator, including rows
    outside a central-complex ROI.
    """
    import pyarrow as pa
    import pyarrow.ipc as ipc

    candidates = np.asarray(candidate_roots, dtype=np.int64)
    position_of = {int(root): slot for slot, root in enumerate(candidates)}
    sums = np.zeros((len(compartment_names()), candidates.size), dtype=np.float64)
    totals = np.zeros(candidates.size, dtype=np.float64)
    index = compartment_index()
    direct = {
        "EB": index["EB"],
        "PB": index["PB"],
        "FB": index["FB"],
        "LAL(L)": index["LAL_L"],
        "LAL(R)": index["LAL_R"],
    }
    with pa.memory_map(str(partners_path), "r") as mapped:
        reader = ipc.open_file(mapped)
        pre_col = reader.schema.get_field_index("body_pre")
        post_col = reader.schema.get_field_index("body_post")
        roi_col = reader.schema.get_field_index("primary_post")
        for batch_number in range(reader.num_record_batches):
            batch = reader.get_batch(batch_number)
            pre = batch.column(pre_col).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
            keep = np.isin(pre, candidates)
            if not keep.any():
                continue
            post = batch.column(post_col).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)[keep]
            rois = batch.column(roi_col).to_numpy(zero_copy_only=False)[keep]
            for pre_root, post_root, roi in zip(pre[keep], post, rois, strict=True):
                slot = position_of[int(pre_root)]
                totals[slot] += 1.0
                label = str(roi)
                target = direct.get(label)
                if target is not None:
                    sums[target, slot] += 1.0
                elif label == "NO":
                    side = post_sides.get(int(post_root), "na")
                    if side == "left":
                        sums[index["NO_L"], slot] += 1.0
                    elif side == "right":
                        sums[index["NO_R"], slot] += 1.0
                    else:
                        sums[index["NO_L"], slot] += 0.5
                        sums[index["NO_R"], slot] += 0.5
    return np.asarray(sums, dtype=np.float32), np.asarray(totals, dtype=np.float32)


def cx_fractions(
    sums: NDArray[np.float32],
    totals: NDArray[np.float32],
    cx_rows: NDArray[np.int64] | None = None,
) -> NDArray[np.float32]:
    """Divide summed central-complex output by total output (step 3 input).

    Units: dimensionless fractions in [0, 1]. Shapes: (n_candidates,)
    in and out. cx_rows selects the seven central-complex rows of S
    (defaults to the fixed mask ids).
    """
    if cx_rows is None:
        index_of_comp = compartment_index()
        cx_rows = np.asarray([index_of_comp[name] for name in CX_COMPARTMENTS])
    with np.errstate(divide="ignore", invalid="ignore"):
        fractions = sums[cx_rows, :].sum(axis=0) / totals
    fractions = np.where(totals > 0, fractions, 0.0)
    return np.asarray(fractions, dtype=np.float32)


def apply_cx_filter(
    fractions: NDArray[np.float32], threshold: float
) -> NDArray[np.bool_]:
    """Keep candidates whose central-complex fraction reaches threshold.

    Units: fractions and threshold are dimensionless. Shapes:
    (n_candidates,) boolean mask.
    """
    return np.asarray(fractions >= threshold, dtype=np.bool_)


def build_innervation(
    n: int,
    dan_idx: NDArray[np.int32],
    dan_types: NDArray[np.str_],
    dan_sides: NDArray[np.str_],
    dan_compartments: dict[str, list[str]],
    bilateral_prefixes: tuple[str, ...],
    cxdan_idx: NDArray[np.int32],
    cx_sums: NDArray[np.float32],
) -> sparse.csr_matrix:
    """Build M (step 4): nonzero only for DAN and CX_DAN columns.

    Units: weights are dimensionless innervation shares. Shapes:
    (37, n) float32 CSR; every nonzero column sums to 1.
    Mushroom-body DANs split 1/k over the k compartments of their
    Aso 2014 type (bilateral prefixes split across both sides);
    CX_DAN columns normalise their central-complex sums. Types
    missing from the table get all-zero columns.
    """
    index_of_comp = compartment_index()
    cx_rows = np.asarray([index_of_comp[name] for name in CX_COMPARTMENTS])
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for position, engine in enumerate(dan_idx):
        hemi = str(dan_types[position])
        compartments = dan_compartments.get(hemi)
        if not compartments:
            continue
        bilateral = any(hemi.startswith(prefix) for prefix in bilateral_prefixes)
        if bilateral:
            names = [f"{stem}_L" for stem in compartments] + [f"{stem}_R" for stem in compartments]
        else:
            suffix = _side_suffix(str(dan_sides[position]))
            if suffix is None:
                names = [f"{stem}_L" for stem in compartments] + [f"{stem}_R" for stem in compartments]
            else:
                names = [f"{stem}_{suffix}" for stem in compartments]
        targets = [index_of_comp[name] for name in names]
        weight = 1.0 / len(targets)
        for target in targets:
            rows.append(target)
            cols.append(int(engine))
            data.append(weight)
    for slot, engine in enumerate(cxdan_idx):
        column = cx_sums[cx_rows, slot]
        total = float(column.sum())
        if total <= 0:
            continue
        for row_pos, comp in enumerate(cx_rows):
            share = float(column[row_pos]) / total
            if share > 0:
                rows.append(int(comp))
                cols.append(int(engine))
                data.append(share)
    matrix = sparse.csr_matrix(
        (np.asarray(data, dtype=np.float32), (np.asarray(rows), np.asarray(cols))),
        shape=(len(compartment_names()), n),
        dtype=np.float32,
    )
    return matrix


def build_exposure(
    target_w: sparse.csr_matrix, innervation: sparse.csr_matrix
) -> sparse.csr_matrix:
    """Add autoreceptor rows to the target map (step 5).

    Units: dimensionless exposure shares. Shapes: (n, 37) float32
    CSR. Every DAN and CX_DAN member gets W[j, :] = M[:, j];
    every other row is the step-1 target row.
    """
    full = target_w.tolil()
    switched = innervation.tocsc()
    _, columns = switched.nonzero()
    for engine in np.unique(columns):
        full[int(engine), :] = switched[:, int(engine)].T
    return full.tocsr()
