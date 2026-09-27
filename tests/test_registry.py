"""Registry checks: inventory, mapping, compartments, receptors, detectors."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sparse
import yaml

from flyonenomics.registry import (
    PopulationSpec,
    build_registry,
)
from flyonenomics.registry import annotations as ann
from flyonenomics.registry import compartments as comp
from flyonenomics.registry import receptors as rec
from flyonenomics.registry.populations import (
    ExplicitSelector,
    PopulationEntry,
    RegexSelector,
    ValuesSelector,
    check_inventory,
    load_population_table,
    resolve_population,
)

ROOT = Path(__file__).resolve().parents[1]

#: Measured inventory counts on the pinned v2.1.0 file (spec numbers
#: in comments where they differ). Units: neuron counts.
EXPECTED_COUNTS = {
    "DAN": 331, "PAM": 304, "PPL1": 16, "PPL2": 8,
    "CX_DAN_candidates": 40, "CX_DAN": 30,
    "EB_other": 0, "PB_other": 32, "FB_columnar": 1681,
    "NO_neurons": 16, "LAL_neurons": 547,
    "KC": 5177, "KC_g": 2490, "KC_ab": 1771, "KC_apbp": 916,
    "MBON": 96, "ER": 278, "EPG": 51, "PEN": 42, "PEG": 20,
    "D7": 40, "FB_tangential": 401, "dFB": 90,
    "TuBu": 150, "MeTu": 896,
    "DNa01_L": 1, "DNa01_R": 1, "DNa02_L": 1, "DNa02_R": 1,
    "steering_L": 2, "steering_R": 2, "DN_all": 1303, "DNp01": 2,
    "sugar_GRN_R": 21, "MN9": 1, "bitter_GRN_R": 21,
    "motor": 106, "sensory": 16903,
}

#: Resolved in-engine counts: four descending and 552 sensory
#: annotated roots are absent from the engine order and dropped at
#: resolution. Units: neuron counts.
RESOLVED_COUNTS = dict(EXPECTED_COUNTS, DN_all=1299, sensory=16351)


@pytest.fixture(scope="session")
def registry():
    """Build the v783 registry once per session.

    Units: per Registry fields. Shapes: W (n, 37), M (37, n).
    """
    return build_registry()


def test_every_population_resolves_with_measured_count(registry) -> None:
    """Each population resolves with its measured inventory count.

    Units: neuron counts. Shapes: scalars.
    """
    assert registry.n == 138639
    for name, expected in RESOLVED_COUNTS.items():
        population = registry.population(name)
        assert population.count == expected, name
        count, (low, high) = registry.inventory(name)
        assert count == expected and low <= count <= high, name


def test_inventory_counts_match_yaml(registry) -> None:
    """YAML inventory counts equal the measured counts.

    Units: neuron counts. Shapes: one row per population.
    """
    _, entries = load_population_table()
    for entry in entries:
        if entry.name in EXPECTED_COUNTS:
            assert entry.inventory_count == EXPECTED_COUNTS[entry.name], entry.name


def test_required_population_failure() -> None:
    """Required populations fail loudly when empty or breached.

    Units: neuron counts. Shapes: scalars.
    """
    frame = pd.DataFrame({
        "root_id": [1, 2], "side": ["left", "right"],
        "cell_class": ["X", "X"], "hemibrain_type": ["H", "H"],
        "cell_type": ["T", "T"], "known_nt": ["acetylcholine", "acetylcholine"],
    })
    order = np.asarray([1, 2], dtype=np.int64)
    empty = PopulationEntry(
        name="empty", selector=ValuesSelector(column="cell_class", values=["DAN"]),
        required=True, inventory_count=0, inventory_tolerance="exact",
    )
    with pytest.raises(ValueError, match="required population is empty"):
        check_inventory(resolve_population(empty, frame, order), empty)
    breached = PopulationEntry(
        name="breached", selector=ValuesSelector(column="cell_class", values=["X"]),
        required=True, inventory_count=2, inventory_tolerance="exact",
    )
    resolved = resolve_population(breached, frame, order[:1])
    assert resolved.count == 1
    with pytest.raises(ValueError, match="inventory breach"):
        check_inventory(resolved, breached)


def test_authoritative_lists_unsorted_with_unmapped_counts(registry) -> None:
    """Sugar, bitter, and MN9 lists keep authoritative order unsorted.

    Units: root IDs dimensionless. Shapes: (21,), (21,), (1,).
    """
    raw = yaml.safe_load((ROOT / "data" / "populations-v0.1.yaml").read_text())
    rows = {row["name"]: row for row in raw["populations"]}
    sugar = registry.population("sugar_GRN_R")
    assert sugar.root_ids.tolist() == rows["sugar_GRN_R"]["selector"]["v783_roots"]
    assert rows["sugar_GRN_R"]["selector"]["unmapped_count"] == 0
    assert list(rows["sugar_GRN_R"]["selector"]["source_roots"])[:5] == [
        720575940624963786, 720575940630233916, 720575940637568838,
        720575940638202345, 720575940617000768,
    ]
    assert sugar.root_ids.tolist() != sorted(sugar.root_ids.tolist())
    bitter = registry.population("bitter_GRN_R")
    assert bitter.root_ids.tolist() == rows["bitter_GRN_R"]["selector"]["v783_roots"]
    assert rows["bitter_GRN_R"]["selector"]["unmapped_count"] == 0
    assert bitter.root_ids.tolist() != sorted(bitter.root_ids.tolist())
    mn9 = registry.population("MN9")
    assert mn9.root_ids.tolist() == [720575940660219265]


def test_root_ids_follow_completeness_order(registry) -> None:
    """Registry order equals the completeness file row order.

    Units: root IDs dimensionless int64. Shapes: (138639,).
    """
    assert registry.root_ids.tolist() == ann.load_engine_order("783").tolist()


def test_index_of_lists_unknown_roots(registry) -> None:
    """index_of raises KeyError naming unknown roots.

    Units: root IDs dimensionless. Shapes: (n_queries,).
    """
    known = registry.population("MN9").root_ids
    assert registry.index_of(known).tolist() == [list(registry.root_ids).index(int(known[0]))]
    with pytest.raises(KeyError, match="unknown roots"):
        registry.index_of(np.asarray([1, 2, 3], dtype=np.int64))


def test_resolve_spec_variants(registry) -> None:
    """PopulationSpec resolves by name, explicit list, and query.

    Units: root IDs dimensionless. Shapes: (count,) each.
    """
    by_name = registry.resolve(PopulationSpec(name="MN9"))
    assert by_name.root_ids.tolist() == [720575940660219265]
    from flyonenomics.registry import ExplicitSpec, QuerySpec

    explicit = registry.resolve(PopulationSpec(
        explicit=ExplicitSpec(roots=[720575940660219265], version="783")))
    assert explicit.root_ids.tolist() == [720575940660219265]
    query = registry.resolve(PopulationSpec(
        query=QuerySpec(column="hemibrain_type", values=["DNa01"], side="left")))
    assert query.count == 1
    with pytest.raises(ValueError, match="exactly one"):
        registry.resolve(PopulationSpec())
    with pytest.raises(KeyError, match="unknown population"):
        registry.resolve(PopulationSpec(name="nope"))


def test_cxdan_filter_outcome(registry) -> None:
    """Pre-filter 40, post-filter 30, excluded roots listed.

    Units: fractions dimensionless. Shapes: (40,) fractions.
    """
    table = comp.load_compartment_table()
    assert table.cxdan is not None
    assert table.cxdan.pre_count == 40
    assert table.cxdan.post_count == 30
    assert registry.population("CX_DAN").count == 30
    excluded = {item.root for item in table.cxdan.excluded}
    assert len(excluded) == 10
    fractions = registry.candidate_fractions()
    assert len(fractions) == 40
    for root in excluded:
        assert fractions[root] < 0.2
    kept_types: dict[str, int] = {}
    frame = ann.load_annotations("v2.1.0").set_index("root_id")
    for root in registry.population("CX_DAN").root_ids:
        kept_types[str(frame.loc[int(root), "hemibrain_type"])] = (
            kept_types.get(str(frame.loc[int(root), "hemibrain_type"]), 0) + 1)
    assert kept_types.get("PPM1204,PS139") == 4
    assert kept_types.get("PPM1205") == 2


def test_maps_normalised(registry) -> None:
    """W rows and M columns sum to 1 or 0.

    Units: dimensionless shares. Shapes: W (n, 37), M (37, n).
    """
    dense_w = np.asarray(registry.exposure().sum(axis=1)).ravel()
    assert set(np.unique(np.round(dense_w, 4)).tolist()) <= {0.0, 1.0}
    dense_m = np.asarray(registry.innervation().sum(axis=0)).ravel()
    assert set(np.unique(np.round(dense_m, 4)).tolist()) <= {0.0, 1.0}
    assert int((dense_m > 0).sum()) == 346
    mask = registry.exposed_mask()
    assert mask.dtype == bool and mask.shape == (registry.n,)
    assert int(mask.sum()) == int((dense_w > 0).sum())


def test_aso_table_transcribed_with_citation() -> None:
    """Aso 2014 table carries its citation and the unplaced types.

    Units: none. Shapes: one row per DAN type in the file.
    """
    table = comp.load_compartment_table()
    assert "Aso et al. 2014" in table.aso_citation and "Li et al. 2020" in table.aso_citation
    assert table.dan_compartments["PAM01"] == ["gamma5"]
    assert table.dan_compartments["PAM15"] == ["gamma5", "beta_prime2"]
    assert table.dan_compartments["PPL103"] == ["gamma2", "alpha_prime1"]
    assert table.mbon_compartments["MBON01"] == ["gamma5", "beta_prime2"]
    assert table.mbon_compartments["MBON10"] == ["beta_prime1"]
    assert table.mbon_compartments["MBON22"] == []
    unplaced = {row.hemibrain_type for row in table.unplaced_dan_types}
    assert {"PPL107", "PPL108", "PPL201", "PPL202", "PPL203", "PPL204", "CB2730"} <= unplaced


def test_receptor_precedence_is_total(registry) -> None:
    """Precedence names each row once; densities expand per neuron.

    Units: dimensionless densities in [0, 1]. Shapes: (n,) each.
    """
    table = rec.load_receptor_table()
    roots_of = {name: registry.population(name).root_ids for name in registry.populations()}
    overlaps = rec.check_precedence(table, roots_of)
    assert set(table.precedence) == {row.population for row in table.rows}
    receptor_map = registry.receptors()
    assert receptor_map.r1.shape == (registry.n,)
    assert float(receptor_map.r1.max()) <= 1.0 and float(receptor_map.r2.max()) <= 1.0
    kc = registry.population("KC")
    idx = registry.index_of(np.asarray([kc.root_ids[0]], dtype=np.int64))
    assert receptor_map.r1[int(idx[0])] == 1.0 and receptor_map.rq[int(idx[0])] == 1.0
    assert isinstance(overlaps, dict)


def test_label_check_reports_kenyon_disagreement(registry) -> None:
    """Label check counts the Kenyon-cell dopamine disagreement.

    Units: counts are neurons. Shapes: one row per population.
    """
    from flyonenomics.validation import artefacts

    report = artefacts.label_check()
    assert report["tripped"] is False
    assert report["uses_top_nt"] is False
    assert report["kc_dopamine"] == 5172
    assert report["kc_total"] == 5177
    assert report["per_population"]["DAN"] == 1
    assert report["per_population"]["KC"] == 5173


def test_completeness_unknown_without_denominator(registry, monkeypatch) -> None:
    """Completeness reports unknown while the Codex table is absent.

    Units: fractions dimensionless. Shapes: one row per population.
    """
    from flyonenomics.validation import artefacts

    monkeypatch.setattr(ann, "load_input_counts", lambda roots: None)
    report = artefacts.input_completeness()
    assert report["codex_status"] == "not fetched"
    assert report["tripped"] is False
    assert set(report["populations"]) == set(registry.populations())
    assert set(report["populations"].values()) == {"unknown"}


def test_no_top_nt_selectors() -> None:
    """No population is defined through the predicted top_nt column.

    Units: none. Shapes: one row per population.
    """
    _, entries = load_population_table()
    for entry in entries:
        selector = entry.selector
        columns = []
        if not isinstance(selector, ExplicitSelector):
            columns = [selector.column]
            if isinstance(selector, RegexSelector):
                if selector.and_column is not None:
                    columns.append(selector.and_column)
                if selector.not_column is not None:
                    columns.append(selector.not_column)
        assert "top_nt" not in columns, entry.name


def test_no_hardcoded_constants_in_registry() -> None:
    """Registry sources import no engine and thresholds come from params.

    Units: none. Shapes: source text scan.
    """
    for module in ("__init__", "annotations", "populations", "compartments", "receptors"):
        text = (ROOT / "src" / "flyonenomics" / "registry" / f"{module}.py").read_text()
        assert "import flyonenomics.engine" not in text and "from flyonenomics.engine" not in text, module
    from flyonenomics.types import load_params

    assert float(load_params().get("cxdan.min_cx_output_fraction")) == 0.2
    assert float(load_params().get("artefact.completeness_min")) == 0.5


# --- Ten-neuron toy connectivity with hand-computed W, M, S, T. ---

TOY_ROOTS = np.arange(101, 111, dtype=np.int64)
TOY_INDEX = {int(root): slot for slot, root in enumerate(TOY_ROOTS)}


def _toy_target() -> sparse.csr_matrix:
    """Step-1 W for the toy (hand-computed rows).

    Units: dimensionless shares. Shapes: (10, 37).
    """
    pops = {
        "KC_g": np.asarray([101, 102], dtype=np.int64),
        "KC_ab": np.asarray([], dtype=np.int64),
        "KC_apbp": np.asarray([], dtype=np.int64),
        "EPG": np.asarray([106], dtype=np.int64),
        "ER": np.asarray([], dtype=np.int64),
        "EB_other": np.asarray([], dtype=np.int64),
        "PEN": np.asarray([], dtype=np.int64),
        "PEG": np.asarray([], dtype=np.int64),
        "D7": np.asarray([], dtype=np.int64),
        "PB_other": np.asarray([], dtype=np.int64),
        "FB_tangential": np.asarray([107], dtype=np.int64),
        "FB_columnar": np.asarray([], dtype=np.int64),
        "NO_neurons": np.asarray([108], dtype=np.int64),
        "LAL_neurons": np.asarray([109], dtype=np.int64),
        "MBON": np.asarray([103], dtype=np.int64),
    }
    sides = {name: np.asarray(["left"] * len(roots)) for name, roots in pops.items()}
    sides["NO_neurons"] = np.asarray(["right"])
    mbon = {"MBON01": ["gamma5", "beta_prime2"]}
    return comp.build_target_rows(
        10, pops, sides, TOY_INDEX, mbon, np.asarray(["MBON01"]))


def test_toy_target_rows() -> None:
    """Step-1 rows match the hand-computed exposure shares.

    Units: dimensionless shares. Shapes: (10, 37).
    """
    index = comp.compartment_index()
    dense = _toy_target().toarray()
    gamma_l = [index[f"gamma{i}_L"] for i in range(1, 6)]
    assert dense[0, gamma_l].tolist() == pytest.approx([0.2] * 5)
    assert dense[2, [index["gamma5_L"], index["beta_prime2_L"]]].tolist() == pytest.approx([0.5, 0.5])
    assert dense[5, index["EB"]] == 1.0
    assert dense[6, index["FB"]] == 1.0
    assert dense[7, index["NO_R"]] == 1.0
    assert dense[8, index["LAL_L"]] == 1.0
    assert dense[3].sum() == 0.0 and dense[4].sum() == 0.0 and dense[9].sum() == 0.0


def test_toy_sums_filter_and_maps() -> None:
    """Steps 2-5 on the toy give the hand-computed S, T, M, W.

    Units: synapse counts for S/T, shares for M/W. Shapes: S
    (37, 2), T (2,), M (37, 10), W (10, 37).
    """
    target = _toy_target()
    edges = pd.DataFrame({
        "Presynaptic_ID": [105, 105, 105, 107, 107],
        "Postsynaptic_ID": [106, 107, 110, 101, 110],
        "Connectivity": [20, 5, 75, 90, 810],
    })
    candidates = np.asarray([105, 107], dtype=np.int64)
    sums, totals = comp.candidate_sums(edges, TOY_INDEX, candidates, target)
    assert totals.tolist() == [100.0, 900.0]
    index = comp.compartment_index()
    assert sums[index["EB"], 0] == pytest.approx(20.0)
    assert sums[index["FB"], 0] == pytest.approx(5.0)
    fractions = comp.cx_fractions(sums, totals)
    assert fractions.tolist() == pytest.approx([0.25, 0.0])
    from flyonenomics.types import load_params

    threshold = float(load_params().get("cxdan.min_cx_output_fraction"))
    keep = comp.apply_cx_filter(fractions, threshold)
    assert keep.tolist() == [True, False]
    dan_idx = np.asarray([3], dtype=np.int32)
    innervation = comp.build_innervation(
        10, dan_idx, np.asarray(["PAM01"]), np.asarray(["left"]),
        {"PAM01": ["gamma5"]}, ("PPL1",),
        np.asarray([4], dtype=np.int32),
        sums[:, [0]],
    )
    dense_m = innervation.toarray()
    assert dense_m[index["gamma5_L"], 3] == 1.0
    assert dense_m[:, 4].sum() == pytest.approx(1.0)
    assert dense_m[index["EB"], 4] == pytest.approx(0.8)
    assert dense_m[index["FB"], 4] == pytest.approx(0.2)
    full = comp.build_exposure(target, innervation)
    dense_w = full.toarray()
    assert dense_w[3, index["gamma5_L"]] == 1.0
    assert dense_w[4].sum() == pytest.approx(1.0)
    assert dense_w[6, index["FB"]] == 1.0


def test_suites_return_canonical_entries() -> None:
    """SUITE entries carry canonical binding with the pinned fixture.

    Units: none. Shapes: four entries.
    """
    from flyonenomics.validation import artefacts
    from flyonenomics.validation.binding import ValidationEntry

    assert set(artefacts.SUITE) == {
        "registry.inventory", "registry.labels",
        "registry.precedence", "registry.completeness",
    }
    for test_id, run in artefacts.SUITE.items():
        entry = run()
        assert isinstance(entry, ValidationEntry)
        assert entry.test_id == test_id
        assert entry.compatibility == "canonical"
        assert entry.outcome == "passed"
        assert entry.fixture_path == "tests/fixtures/registry/checks.json"
    assert artefacts.fano_factor_detector() == "not run"
    assert artefacts.weight_jitter_detector() == "not run"
    assert artefacts.encoder_permutation_detector() == "not run"


@pytest.fixture
def input_count_files(tmp_path, monkeypatch):
    """Small real Feather/Parquet sources, with independent checksum records."""
    import hashlib
    import pyarrow as pa
    import pyarrow.feather as feather
    import pyarrow.parquet as parquet
    from flyonenomics.types import ProvenanceRecord

    counts = tmp_path / "counts.feather"
    feather.write_feather(pa.table({"post_pt_root_id": [10, 10, 20, 40, 999],
                                   "neuropil": ["EB", "FB", "EB", "EB", "EB"],
                                   "count": [4, 6, 100, 0, 999]}), counts)
    edges = tmp_path / "edges.parquet"
    parquet.write_table(pa.table({"Presynaptic_ID": [10, 20, 999, 10, 10],
                                  "Postsynaptic_ID": [10, 10, 10, 20, 999],
                                  "Connectivity": [1, 3, 6, 60, 800]}), edges)
    records = {}
    for item, path in [(ann.POST_COUNT_ITEM, counts), (ann.CONNECTIVITY_ITEMS["783"], edges)]:
        records[item] = ProvenanceRecord(item=item, version="test", source="synthetic",
            license="test", used_for="test", status="fetched", path=str(path),
            bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(ann, "provenance_records", lambda: records)
    return records


def test_input_counts_sum_neuropils_and_exclude_external_presynaptic_roots(input_count_files):
    counts = ann.load_input_counts(np.array([20, 10, 30, 40], dtype=np.int64))
    numerator, denominator, present = counts
    assert numerator.tolist() == [60, 4, 0, 0]
    assert denominator.tolist() == [100, 10, 0, 0]
    assert present.tolist() == [True, True, False, True]


def test_input_counts_reject_corrupt_denominator(input_count_files):
    path = Path(input_count_files[ann.POST_COUNT_ITEM].path)
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum mismatch"):
        ann.load_input_counts(np.array([10, 20], dtype=np.int64))


def test_completeness_weighted_fraction_trip_missing_and_empty(input_count_files, monkeypatch):
    from types import SimpleNamespace
    from flyonenomics.validation import artefacts

    members = {"combined": [0, 1], "low": [1], "missing": [2], "empty": [], "zero": [3]}
    registry = SimpleNamespace(root_ids=np.array([20, 10, 30, 40], dtype=np.int64),
        populations=lambda: list(members),
        population=lambda name: SimpleNamespace(idx=np.array(members[name], dtype=np.int32)))
    monkeypatch.setattr(artefacts, "_registry", lambda: registry)
    report = artefacts.input_completeness()
    assert report["populations"]["combined"] == pytest.approx(64 / 110)
    assert report["populations"]["low"] == 0.4
    assert [report["populations"][name] for name in ("missing", "empty", "zero")] == ["unknown"] * 3
    assert report["tripped"] and report["tripped_populations"] == ["low"]
    # An advisory completeness trip is evidence, not a failed inventory check.
    assert artefacts.check_completeness_suite().measured["tripped"]


def test_completeness_uses_fetched_zenodo(registry):
    from flyonenomics.validation import artefacts

    report = artefacts.input_completeness()
    assert report["denominator_status"] == "fetched"
    assert report["populations"]["KC"] == pytest.approx(943190 / 970760)
    assert report["details"]["sensory"]["missing_denominators"] == 420
    assert report["populations"]["sensory"] == "unknown"
    assert not report["tripped"]



def test_rebuild_does_not_hide_changed_inputs(registry, monkeypatch):
    def changed(version):
        raise ValueError("changed annotation checksum")
    monkeypatch.setattr(ann, "load_annotations", changed)
    with pytest.raises(ValueError, match="changed annotation checksum"):
        build_registry()


def test_annotations_submodule_import_is_unambiguous():
    import importlib
    import types

    assert isinstance(ann, types.ModuleType)
    assert ann is importlib.import_module("flyonenomics.registry.annotations")


def test_all_74_yaml_inventories_against_annotation_file():
    frame = ann.load_annotations("v2.1.0")
    file_roots = frame.root_id.to_numpy(dtype=np.int64)
    _, entries = load_population_table()
    resolved = {}
    for entry in entries:
        pop = resolve_population(entry, frame, file_roots, resolved)
        assert pop.count == entry.inventory_count, entry.name
        resolved[entry.name] = pop
    assert len(resolved) == 74


def test_notebook_literals_and_supervoxel_mapping(registry):
    import ast
    import json

    records = ann.provenance_records()
    _, entries = load_population_table()
    entry_of = {entry.name: entry for entry in entries}
    for population, notebook, symbol in [
        ("sugar_GRN_R", "example.ipynb", "neu_sugar"),
        ("bitter_GRN_R", "figures.ipynb", "neu_bitter"),
    ]:
        record = records[f"Shiu clone {notebook}"]
        path = ann.cached_path(record)
        ann.verify_file(path, record)
        literals = []
        for cell in json.loads(path.read_text())["cells"]:
            if cell["cell_type"] != "code":
                continue
            try:
                tree = ast.parse("".join(cell["source"]))
            except SyntaxError:  # Notebook magic is not Python source.
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == symbol for t in node.targets):
                    literals.append(ast.literal_eval(node.value))
        selector = entry_of[population].selector
        assert literals and all(roots == selector.source_roots for roots in literals)
        mapping = ann.map_roots(np.array(literals[0], dtype=np.int64), "v1.1.0", "v2.1.0")
        assert list(mapping.mapped) == selector.v783_roots
        assert mapping.unmapped_count == selector.unmapped_count == 0
        assert registry.population(population).root_ids.tolist() == list(mapping.mapped)
    order630 = {int(root): index for index, root in enumerate(ann.load_engine_order("630"))}
    assert [order630[root] for root in entry_of["sugar_GRN_R"].selector.source_roots[:5]] == [65153, 90982, 113421, 114820, 27680]
    mn9 = entry_of["MN9"].selector
    assert list(ann.map_roots(np.array(mn9.source_roots, dtype=np.int64), "v1.1.0", "v2.1.0").mapped) == mn9.v783_roots


def test_map_roots_joins_supervoxels_not_equal_roots(monkeypatch):
    source = pd.DataFrame({"root_id": [10, 20, 30], "supervoxel_id": [1, 2, 3]})
    target = pd.DataFrame({"root_id": [110, 20, 220], "supervoxel_id": [1, 99, 2]})
    monkeypatch.setattr(ann, "load_annotations", lambda version: source if version == "v1.1.0" else target)
    result = ann.map_roots(np.array([20, 10, 30, 999], dtype=np.int64), "v1.1.0", "v2.1.0")
    assert result.mapped == (220, 110, None, None)
    assert result.unmapped == (30, 999)


def test_target_mask_precedes_filter_and_autoreceptors(registry):
    table = comp.load_compartment_table()
    frame = ann.load_annotations("v2.1.0").set_index("root_id")
    pops = {name: registry.population(name) for name in registry.populations()}
    roots = {name: pop.root_ids for name, pop in pops.items()}
    sides = {name: pop.side for name, pop in pops.items()}
    engine_index = {int(root): idx for idx, root in enumerate(registry.root_ids)}
    target = comp.build_target_rows(registry.n, roots, sides, engine_index,
        table.mbon_compartments, frame.loc[roots["MBON"], "hemibrain_type"].to_numpy())
    index = comp.compartment_index()
    groups = {"EB": ["EB"], "PB": ["PB"], "FB": ["FB"], "NO": ["NO_L", "NO_R"], "LAL": ["LAL_L", "LAL_R"]}
    measured = {name: int(np.count_nonzero(target[:, [index[c] for c in compartments]].getnnz(axis=1)))
                for name, compartments in groups.items()}
    assert measured == table.target_mask_totals == {"EB": 329, "PB": 134, "FB": 2082, "NO": 16, "LAL": 547}
    dan_idx = np.union1d(pops["DAN"].idx, pops["CX_DAN_candidates"].idx)
    assert target[dan_idx].nnz == 0
    assert set(roots["FB_tangential"]).isdisjoint(roots["CX_DAN_candidates"])
    before = target.copy()
    m = registry.innervation()
    full = comp.build_exposure(target, m)
    assert (target != before).nnz == 0
    assert (full != registry.exposure()).nnz == 0
    assert (full[dan_idx] != m[:, dan_idx].T).nnz == 0
    np.testing.assert_array_equal(registry.exposed_mask(), np.asarray(full.sum(axis=1)).ravel() > 0)
    # A different filter cannot mutate the already-built target or its sums.
    candidates = roots["CX_DAN_candidates"]
    sums, totals = comp.candidate_sums(ann.load_connectivity_edges(candidates), engine_index, candidates, target)
    fractions = comp.cx_fractions(sums, totals)
    assert comp.apply_cx_filter(fractions, 0.2).sum() == 30
    assert comp.apply_cx_filter(fractions, 1.0).sum() == 0
    assert (target != before).nnz == 0


def test_ten_aso_table1_transcriptions():
    """Independent spot checks from https://elifesciences.org/articles/04577#table1."""
    table = comp.load_compartment_table()
    mbon = {"MBON01": ["gamma5", "beta_prime2"], "MBON02": ["beta2", "beta_prime2"],
            "MBON05": ["gamma4"], "MBON06": ["beta1"], "MBON09": ["gamma3", "beta_prime1"],
            "MBON11": ["gamma1"], "MBON12": ["gamma2", "alpha_prime1"]}
    dan = {"PAM03": ["beta2", "beta_prime2"], "PAM07": ["gamma4"], "PPL105": ["alpha_prime2", "alpha2"]}
    for name, compartments in mbon.items():
        assert table.mbon_compartments[name] == compartments
    for name, compartments in dan.items():
        assert table.dan_compartments[name] == compartments


def test_precedence_rejects_constructed_cycle_and_resolves_overlap():
    rows = [rec.ReceptorRow(population=name, r1=value, r2=0, rq=0, source="toy")
            for name, value in [("A", 0.2), ("B", 0.5), ("C", 0.8)]]
    roots = {name: np.array([10], dtype=np.int64) for name in "ABC"}
    # Order encodes adjacent precedence: A > B > C > A is a cycle.
    table = rec.ReceptorTable(version="toy", rows=rows, precedence=["A", "B", "C", "A"])
    with pytest.raises(ValueError, match="exactly once"):
        rec.check_precedence(table, roots)
    table.precedence = ["C", "A", "B"]
    assert rec.check_precedence(table, roots)["A"] == ["B", "C"]
    assert rec.build_receptor_arrays(table, roots, {10: 0}, 1).r1[0] == pytest.approx(0.8)


@pytest.mark.parametrize("column", ["column", "or_column", "and_column", "not_column"])
def test_label_check_trips_on_constructed_top_nt_population(registry, monkeypatch, column):
    from flyonenomics.registry import populations
    from flyonenomics.validation import artefacts

    _, entries = load_population_table()
    entry = next(entry for entry in entries if entry.name == "PAM")
    setattr(entry.selector, column, "top_nt")
    monkeypatch.setattr(populations, "load_population_table", lambda: ("toy", entries))
    report = artefacts.label_check()
    assert report["uses_top_nt"] and report["tripped"]
    with pytest.raises(AssertionError):
        artefacts.check_labels_suite()



def test_cx_candidate_selector_uses_cell_type_for_exr2():
    _, entries = load_population_table()
    candidate = next(entry for entry in entries if entry.name == "CX_DAN_candidates")
    frame = pd.DataFrame({"root_id": [1, 2, 3, 4, 5, 6], "side": ["left"] * 6,
        "cell_type": ["ExR2_1", "other", "other", "ExR2_2", "ExR2_1", "other"],
        "hemibrain_type": ["", "FB2A", "PPM1201", "", "", "ExR2"],
        "known_nt": ["dopamine", "dopamine", "dopamine", "GABA", "dopamine", "dopamine"],
        "cell_class": ["", "", "", "", "DAN", ""]})
    pop = resolve_population(candidate, frame, np.arange(1, 7, dtype=np.int64))
    assert pop.root_ids.tolist() == [1, 2, 3]


def test_eb_selector_excludes_exr2_in_either_label():
    _, entries = load_population_table()
    entry = next(entry for entry in entries if entry.name == "EB_other")
    frame = pd.DataFrame({"root_id": [1, 2, 3], "side": ["left"] * 3,
                          "hemibrain_type": ["ExR1", "ExR2", "ExR1"],
                          "cell_type": ["ExR1", "ExR1", "ExR2_1"]})
    assert resolve_population(entry, frame, np.arange(1, 4, dtype=np.int64)).root_ids.tolist() == [1]



def test_input_count_cache_rechecks_hashes_and_returns_copies(input_count_files):
    roots = np.array([10, 20], dtype=np.int64)
    first = ann.load_input_counts(roots)
    first[0][:] = 999
    assert ann.load_input_counts(roots)[0].tolist() == [4, 60]
    path = Path(input_count_files[ann.CONNECTIVITY_ITEMS["783"]].path)
    path.write_bytes(b"corrupt after cached reduction")
    with pytest.raises(ValueError, match="checksum mismatch"):
        ann.load_input_counts(roots)



def test_ad_hoc_queries_cannot_bypass_top_nt_rule(registry):
    from flyonenomics.registry import QuerySpec
    with pytest.raises(ValueError, match="reserved for the label check"):
        registry.resolve(PopulationSpec(query=QuerySpec(column="top_nt", values=["dopamine"])))
