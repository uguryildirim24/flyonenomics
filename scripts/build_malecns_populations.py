#!/usr/bin/env python3
"""Build the MaleCNS v1.0 population registry and its audit record.

This is a table reduction, not a simulation.  Run it on the large-memory box:
FLYONENOMICS_CACHE_DIR=~/flyo-cache uv run python scripts/build_malecns_populations.py
"""
from __future__ import annotations

from collections import defaultdict
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather
import pyarrow.ipc as ipc
import yaml

from flyonenomics.datasets import get_dataset_adapter
from flyonenomics.io import read_json, read_yaml

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("FLYONENOMICS_CACHE_DIR", ROOT / ".cache")) / "malecns-v1.0"
SOURCE = ROOT / "data" / "populations-v0.2.yaml"
DESTINATION = ROOT / "data" / "populations-male-cns-v1.0.yaml"
RECORD = ROOT / "validation" / "records" / "p2" / "malecns-populations.json"
CX_THRESHOLD = 0.2
CX_TYPES = r"^(ExR2|FB1C|FB1H|FB2A|FB4L|FB4M|FB5H|PPM120[1-5])$"
# MaleCNS primary_post labels collapse the bilateral NO pair to ``NO`` and
# spell the bilateral LAL pair as LAL(L)/LAL(R). Together with EB/PB/FB these
# are the same seven conceptual central-complex compartments used by FlyWire.
CX_PRIMARY_POST_ROIS = ("EB", "PB", "FB", "NO", "LAL(L)", "LAL(R)")


def _table(name: str) -> pa.Table:
    return feather.read_table(CACHE / name)


def _clean(value: Any) -> Any:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return value.item() if isinstance(value, np.generic) else value


def _row_evidence(row: pd.Series) -> dict[str, Any]:
    fields = (
        "bodyId", "instance", "type", "flywireType", "somaSide", "rootSide",
        "superclass", "class", "subclass", "entryNerve", "exitNerve",
        "receptorType", "consensus_nt",
    )
    return {name: _clean(row.get(name)) for name in fields}


def _scan_candidate_rois(candidate_ids: set[int]) -> tuple[dict[int, dict[str, int]], dict[int, dict[str, int]]]:
    """Count output-post ROIs and presynaptic-point ROIs for CX candidates."""
    partners = CACHE / "syn-partners-male-cns-v1.0-minconf-0.5.feather"
    output: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with pa.memory_map(str(partners), "r") as mapped:
        reader = ipc.open_file(mapped)
        for number in range(reader.num_record_batches):
            batch = reader.get_batch(number)
            pre = batch.column(batch.schema.get_field_index("body_pre"))
            mask = pc.is_in(pre, value_set=pa.array(sorted(candidate_ids), type=pa.int64()))
            if not pc.any(mask).as_py():
                continue
            bodies = pc.filter(pre, mask).to_numpy(zero_copy_only=False)
            rois = pc.filter(batch.column(batch.schema.get_field_index("primary_post")), mask).to_pylist()
            for body, roi in zip(bodies, rois, strict=True):
                output[int(body)][str(roi)] += 1

    points = CACHE / "syn-points-male-cns-v1.0-minconf-0.5.feather"
    tbar: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    with pa.memory_map(str(points), "r") as mapped:
        reader = ipc.open_file(mapped)
        for number in range(reader.num_record_batches):
            batch = reader.get_batch(number)
            body = batch.column(batch.schema.get_field_index("body"))
            kind = batch.column(batch.schema.get_field_index("kind"))
            mask = pc.and_(
                pc.is_in(body, value_set=pa.array(sorted(candidate_ids), type=pa.int64())),
                pc.equal(kind, "PreSyn"),
            )
            if not pc.any(mask).as_py():
                continue
            bodies = pc.filter(body, mask).to_numpy(zero_copy_only=False)
            rois = pc.filter(batch.column(batch.schema.get_field_index("primary")), mask).to_pylist()
            for candidate, roi in zip(bodies, rois, strict=True):
                tbar[int(candidate)][str(roi)] += 1
    return output, tbar


def _selector_mask(frame: pd.DataFrame, selector: dict[str, Any], side: str | None) -> np.ndarray:
    if selector["kind"] == "values":
        mask = frame[selector["column"]].isin(selector["values"]).to_numpy(copy=True)
    elif selector["kind"] == "regex":
        mask = frame[selector["column"]].fillna("").astype(str).str.match(selector["pattern"]).to_numpy(copy=True)
        if selector.get("or_column"):
            mask |= frame[selector["or_column"]].fillna("").astype(str).str.match(selector["or_pattern"]).to_numpy()
        if selector.get("and_column"):
            mask &= frame[selector["and_column"]].fillna("").astype(str).str.match(selector["and_pattern"]).to_numpy()
        if selector.get("not_column"):
            mask &= ~frame[selector["not_column"]].fillna("").astype(str).str.match(selector["not_pattern"]).to_numpy()
    else:
        roots = set(int(value) for value in selector["source_roots"])
        mask = frame.root_id.isin(roots).to_numpy()
    if side:
        mask &= frame.side.eq(side).to_numpy()
    return mask


def _translated_selector(item: dict[str, Any], cx_roots: list[int]) -> tuple[dict[str, Any], str, bool, str | None]:
    """Return selector, rule, required and no-clean-match reason."""
    name = item["name"]
    selector = dict(item["selector"])
    required = bool(item["required"])
    no_match = None
    if name == "CX_DAN_candidates":
        selector = {
            "kind": "regex", "column": "hemibrain_type", "pattern": CX_TYPES,
            "and_column": "top_nt", "and_pattern": "^dopamine$",
        }
        rule = "MaleCNS anatomical CX dopamine types, with official consensus_nt dopamine"
    elif name == "CX_DAN":
        selector = {
            "kind": "explicit",
            "source": "MaleCNS syn-partners central-complex primary_post fraction >= 0.2",
            "source_version": "male-cns:v1.0",
            "source_roots": cx_roots,
            "mapping_date": "2026-09-22",
            "unmapped_count": 0,
        }
        rule = "CX_DAN candidate with central-complex postsynapse fraction >= cxdan.min_cx_output_fraction (0.2)"
    elif name in ("sugar_GRN_R", "bitter_GRN_R"):
        selector = {"kind": "values", "column": "hemibrain_type", "values": [f"NO_CLEAN_{name}_MATCH"]}
        required = False
        no_match = (
            "No MaleCNS modality, receptor, or root-level FlyWire cross-match identifies sugar among labellar GRNs"
            if name == "sugar_GRN_R" else
            "No MaleCNS modality or receptor label identifies the FlyWire bitter source"
        )
        rule = "empty by evidence: do not substitute unlabeled gustatory candidates"
    elif name == "MN9":
        selector = {"kind": "values", "column": "hemibrain_type", "values": ["MN9"]}
        rule = "MaleCNS type MN9, right side, matching the FlyWire source side and pharyngeal nerve"
    elif name == "TuBu":
        selector = {"kind": "regex", "column": "hemibrain_type", "pattern": "^TuBu"}
        rule = "FlyWire TuBu class translated to MaleCNS named TuBu types"
    elif selector["kind"] == "explicit":
        selector = {"kind": "values", "column": "hemibrain_type", "values": [f"NO_CLEAN_{name}_MATCH"]}
        required = False
        no_match = "Explicit FlyWire roots have no cross-dataset identity mapping"
        rule = "empty by evidence: explicit FlyWire identity is not transferable"
    else:
        column = selector["column"]
        rule = f"FlyWire {column} selector applied to the corresponding canonical MaleCNS column"
        if column == "super_class" and selector.get("values") == ["descending"]:
            selector["values"] = ["descending_neuron"]
            rule = "FlyWire descending superclass translated to MaleCNS descending_neuron"
        elif column == "super_class" and selector.get("values") == ["motor"]:
            selector["values"] = ["vnc_motor", "cb_motor"]
            rule = "FlyWire motor superclass translated to typed MaleCNS vnc_motor and cb_motor"
        elif column == "super_class" and selector.get("values") == ["sensory"]:
            selector = {"kind": "regex", "column": "super_class", "pattern": ".*sensory.*"}
            rule = "FlyWire sensory superclass translated to MaleCNS superclasses containing sensory"
    return selector, rule, required, no_match


def _flywire_er_rule_check() -> dict[str, Any]:
    """Recompute the reference ER trace-set rule on the unchanged v783 graph."""
    adapter = get_dataset_adapter("783")
    annotation = adapter.load_annotations("v2.1.0")
    edges = adapter.load_connectivity_edges(None)
    er = annotation[annotation.hemibrain_type.fillna("").str.match(r"^ER\d")]
    tubu = set(annotation.loc[annotation.cell_class.eq("TuBu"), "root_id"].astype(int))
    direct = set(
        edges.loc[
            edges.Presynaptic_ID.isin(tubu) & edges.Postsynaptic_ID.isin(er.root_id),
            "Postsynaptic_ID",
        ].astype(int)
    )
    dropped = er.loc[~er.root_id.isin(direct)]
    dropped_types = {
        str(name): int(count)
        for name, count in dropped.groupby("hemibrain_type", dropna=False).size().items()
    }
    er1 = er.hemibrain_type.eq("ER1")
    return {
        "candidates": int(len(er)),
        "kept": int(len(direct)),
        "dropped": int(len(er) - len(direct)),
        "er1_candidates": int(er1.sum()),
        "er1_kept": int(er.loc[er1, "root_id"].isin(direct).sum()),
        "dropped_types": dropped_types,
    }


def main() -> int:
    source = read_yaml(SOURCE)
    adapter_provenance = read_json(CACHE / "derived" / "provenance.json")
    if adapter_provenance.get("policy_version") != "male-cns-adapter-v3":
        raise ValueError("population audit requires the item-150 male-cns-adapter-v3 graph")
    if adapter_provenance.get("item150_after_counts", {}).get("edges") != 25_120_209:
        raise ValueError("population audit requires the item-150 all-pairs graph")
    annotation = _table("body-annotations-male-cns-v1.0-minconf-0.5.feather").to_pandas()
    nt = _table("body-neurotransmitters-male-cns-v1.0.feather").to_pandas()
    raw = annotation.merge(nt[["body", "consensus_nt"]], left_on="bodyId", right_on="body", how="left", validate="one_to_one")
    traced = raw[(raw.status == "Traced") & raw.type.notna()].copy().reset_index(drop=True)
    traced["root_id"] = traced.bodyId.astype(np.int64)
    traced["hemibrain_type"] = traced.type
    traced["cell_type"] = traced.flywireType
    traced["cell_class"] = traced["class"]
    traced["super_class"] = traced.superclass
    traced["top_nt"] = traced.consensus_nt
    traced["known_nt"] = traced.consensus_nt
    traced["side"] = traced.somaSide.fillna(traced.rootSide).map({"L": "left", "R": "right"})

    anatomical_candidates = traced[
        traced.hemibrain_type.fillna("").str.match(CX_TYPES)
    ].copy()
    output_rois, tbar_rois = _scan_candidate_rois(set(anatomical_candidates.root_id.astype(int)))
    cx_audit = []
    cx_roots = []
    for _, row in anatomical_candidates.sort_values("root_id").iterrows():
        body = int(row.root_id)
        rois = dict(sorted(output_rois.get(body, {}).items()))
        total = sum(rois.values())
        cx = sum(rois.get(roi, 0) for roi in CX_PRIMARY_POST_ROIS)
        fraction = cx / total if total else 0.0
        transmitter_eligible = row.top_nt == "dopamine"
        keep = transmitter_eligible and fraction >= CX_THRESHOLD
        if keep:
            cx_roots.append(body)
        evidence = _row_evidence(row)
        if not transmitter_eligible:
            reason = "dropped before ROI filter: official consensus_nt is not dopamine"
        else:
            reason = "central-complex output fraction >= 0.2" if keep else "central-complex output fraction < 0.2"
        evidence.update({
            "transmitter_eligible": transmitter_eligible,
            "outgoing_synapses": total,
            "central_complex_postsynapses": cx,
            "central_complex_output_fraction": fraction,
            "central_complex_primary_post_rois": list(CX_PRIMARY_POST_ROIS),
            "kept": keep,
            "reason": reason,
            "primary_post_roi_counts": rois,
            "presynaptic_point_primary_roi_counts": dict(sorted(tbar_rois.get(body, {}).items())),
        })
        cx_audit.append(evidence)

    tubu = set(traced.loc[traced.hemibrain_type.fillna("").str.match("^TuBu"), "root_id"].astype(int))
    er = traced[traced.hemibrain_type.fillna("").str.match(r"^ER\d")].copy()
    weights = _table("connectome-weights-male-cns-v1.0-minconf-0.5.feather").to_pandas()
    direct_er = set(weights.loc[weights.body_pre.isin(tubu) & weights.body_post.isin(er.root_id), "body_post"].astype(int))
    er_audit = []
    for _, row in er.sort_values("root_id").iterrows():
        evidence = _row_evidence(row)
        keep = int(row.root_id) in direct_er
        evidence.update({
            "kept_in_traced_ring_set": keep,
            "reason": "direct aggregate TuBu input, the FlyWire trace-set rule" if keep else "no direct aggregate TuBu input",
        })
        er_audit.append(evidence)

    rows = []
    rules: dict[str, str] = {}
    no_matches: dict[str, str] = {}
    masks: dict[str, np.ndarray] = {}
    old_count: dict[str, int] = {}
    for original in source["populations"]:
        item = dict(original)
        selector, rule, required, no_match = _translated_selector(item, cx_roots)
        side = item.get("side")
        if item["name"] == "MN9":
            side = "right"
        mask = _selector_mask(traced, selector, side)
        for excluded in item.get("exclude", []):
            mask &= ~masks[excluded]
        masks[item["name"]] = mask
        count = int(mask.sum())
        row = {
            "name": item["name"], "selector": selector, "required": required,
            "exclude": list(item.get("exclude", [])), "inventory_count": count,
            "inventory_tolerance": "exact" if selector["kind"] == "explicit" or count == 0 else "percent",
            "overlaps_with": list(item.get("overlaps_with", [])),
            "expected_nt": item.get("expected_nt"), "side": side,
            "note": f"MaleCNS v1.0. {rule}. Explicit laterality: {side or 'bilateral/all annotated sides'}."
                    + (f" No clean match: {no_match}." if no_match else ""),
        }
        rows.append(row)
        rules[item["name"]] = rule
        old_count[item["name"]] = int(item["inventory_count"])
        if no_match:
            no_matches[item["name"]] = no_match

    # Declare every observed overlap, rather than assuming FlyWire's overlap graph transfers.
    names = [row["name"] for row in rows]
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            if np.any(masks[first] & masks[second]):
                first_row = rows[i]
                second_row = rows[names.index(second)]
                if second not in first_row["overlaps_with"] and first not in second_row["overlaps_with"]:
                    first_row["overlaps_with"].append(second)
    for row in rows:
        row["overlaps_with"] = sorted(set(row["overlaps_with"]))

    destination = {
        "version": "male-cns-v1.0",
        "annotation_version": "male-cns:v1.0",
        "mapping_date": "2026-09-22",
        "selector_tolerance_percent": 10,
        "inventory_note": (
            "MaleCNS v1.0 typed/traced graph. Every selector is translated before model outcomes; "
            "side is explicit on every row (null means all annotated sides)."
        ),
        "laterality_rule": "somaSide, then rootSide; L/R become left/right; null side selects all annotated sides",
        "populations": rows,
    }
    DESTINATION.write_text(yaml.safe_dump(destination, sort_keys=False, width=120))

    labellar = raw[
        (raw.status == "Traced") & raw.type.notna() & raw["class"].eq("gustatory")
        & raw.subclass.eq("labellar bristle")
    ].sort_values("bodyId")
    taste_peg = raw[
        (raw.status == "Traced") & raw.type.notna() & raw["class"].eq("gustatory")
        & raw.subclass.eq("taste peg")
    ].sort_values("bodyId")
    typed_leg = traced[traced.superclass.eq("vnc_motor") & traced.subclass.isin(["fl", "ml", "hl"])].sort_values("root_id")
    typed_wing = traced[traced.superclass.eq("vnc_motor") & traced.subclass.eq("wm")].sort_values("root_id")
    untyped_motor = raw[
        (raw.status == "Traced") & raw.type.isna() & raw.superclass.eq("vnc_motor")
        & raw.subclass.isin(["fl", "ml", "hl", "wm"])
    ].sort_values("bodyId")
    mn9_candidates = traced[traced.hemibrain_type.eq("MN9")].sort_values("root_id")

    population_rows = []
    for row in rows:
        name = row["name"]
        population_rows.append({
            "name": name,
            "flywire_count": old_count[name],
            "male_count": int(row["inventory_count"]),
            "rule": rules[name],
            "laterality": row["side"] or "all annotated sides",
            "no_clean_match": no_matches.get(name),
        })
    record = {
        "class": "development",
        "purpose": "MaleCNS v1.0 population registry audit; no calibration and no model outcome",
        "dataset": "male-cns:v1.0",
        "governing_decisions": ["SPEC-P2 item 121", "SPEC-P2 item 149", "SPEC-P2 item 150"],
        "sources": [
            {
                "citation": "Berg et al. 2026, Cell, Sexual dimorphism in the complete Drosophila male central nervous system connectome",
                "doi": "10.1016/j.cell.2026.08.015",
                "use": "MaleCNS anatomy, official types, sides, nerve and ROI annotations",
            },
            {
                "artifact": "data/malecns-v1.0-manifest.json",
                "use": "checksummed official v1.0 annotation, transmitter, aggregate-connectivity and synapse tables",
            },
            {"artifact": "data/populations-v0.2.yaml", "use": "FlyWire population rules and counts"},
        ],
        "rules": {
            "outcome_blinding": "All memberships use released anatomy/labels/connectivity only; no firing or downstream outcome was inspected.",
            "node_scope": "status Traced and non-null MaleCNS type, matching the declared adapter graph",
            "edge_scope": "every official globally aggregated directed pair between graph nodes; no weight cut (item 150)",
            "laterality": destination["laterality_rule"],
            "er_trace_set": "ER registry candidates (^ER\\d) with any direct aggregate TuBu pair; this is the FlyWire trace-set rule",
            "cx_dan": (
                "official dopamine anatomical candidates whose syn-partners primary_post fraction in "
                "EB, PB, FB, NO, LAL(L), or LAL(R) is at least 0.2; these labels represent the seven "
                "FlyWire CX compartments because MaleCNS collapses bilateral NO to one ROI label"
            ),
            "cx_dan_roi_analogue": (
                "MaleCNS counts each released postsynaptic partner synapse by its own primary_post ROI. "
                "FlyWire instead multiplies each aggregate pair by the postsynaptic cell's compartment-targeting "
                "weights, so this is the closest released-ROI analogue, not the same numerator construction."
            ),
            "sugar": (
                "do not assign an unlabeled labellar gustatory candidate to sugar; flywireType is a type label, "
                "not a root-level FlyWire cross-match"
            ),
            "mn9": "type MN9 on the FlyWire source's right side and pharyngeal nerve",
            "untyped_motor": "exclude from the typed/traced graph and populations because no released type establishes motor identity beyond broad class",
        },
        "summary": {
            "population_count": len(rows),
            "male_graph_nodes": len(traced),
            "er_candidates": len(er_audit),
            "er_trace_kept": sum(row["kept_in_traced_ring_set"] for row in er_audit),
            "er_trace_dropped": sum(not row["kept_in_traced_ring_set"] for row in er_audit),
            "cx_dan_named_candidates": len(cx_audit),
            "cx_dan_dopamine_candidates": sum(row["transmitter_eligible"] for row in cx_audit),
            "cx_dan_kept": len(cx_roots),
            "sugar_source_count": 0,
            "sugar_candidates_listed": len(labellar),
            "taste_peg_cells_reviewed": len(taste_peg),
            "typed_leg_motor": len(typed_leg),
            "typed_wing_motor": len(typed_wing),
            "untyped_broad_motor_excluded": len(untyped_motor),
        },
        "adapter_base": {
            "policy_version": adapter_provenance["policy_version"],
            "nodes": adapter_provenance["nodes"],
            "edges": adapter_provenance["item150_after_counts"]["edges"],
            "synapses": adapter_provenance["item150_after_counts"]["synapses"],
            "sign_policy_relevance": "Population and ER membership do not read connection signs.",
        },
        "populations": population_rows,
        "er_trace_audit": er_audit,
        "flywire_er_rule_check": _flywire_er_rule_check(),
        "cx_dan_audit": cx_audit,
        "sugar_reflex": {
            "status": "no clean match",
            "reason": (
                "MaleCNS types labellar gustatory cells and their entry nerve, but supplies no sugar modality or "
                "receptor label and no root-level FlyWire cross-match. Port step 7 has no sugar-reflex source "
                "until one is established."
            ),
            "labellar_candidates": [_row_evidence(row) for _, row in labellar.iterrows()],
            "taste_peg_cells_reviewed": [_row_evidence(row) for _, row in taste_peg.iterrows()],
            "cross_match_check": (
                "flywireType provides type-level labels only; the release has no FlyWire root-ID column. "
                "No labellar candidate has receptorType."
            ),
            "MN9_rule": "right MN9 on PhN, matching FlyWire laterality and nerve",
            "MN9_candidates": [_row_evidence(row) for _, row in mn9_candidates.iterrows()],
            "MN9_kept": [int(value) for value in mn9_candidates.loc[mn9_candidates.side.eq("right"), "root_id"]],
        },
        "motor_neurons": {
            "typed_rule": "Traced, non-null type, superclass vnc_motor; leg subclasses fl/ml/hl, wing subclass wm",
            "typed_leg": [_row_evidence(row) for _, row in typed_leg.iterrows()],
            "typed_wing": [_row_evidence(row) for _, row in typed_wing.iterrows()],
            "untyped_rule": "excluded: broad vnc_motor class is evidence, but missing released type violates the adapter's typed-node rule",
            "untyped_rows": [_row_evidence(row) for _, row in untyped_motor.iterrows()],
        },
        "limitations": [
            "The sugar-reflex input remains empty; port step 7 has no source until a MaleCNS sugar identity is established.",
            "Population names are anatomy-based cross-animal rules, not one-to-one cell identities.",
            "Nothing is calibrated here and the fly does not see.",
        ],
    }
    RECORD.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
