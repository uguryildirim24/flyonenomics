#!/usr/bin/env python3
"""Mechanical first-pass translation of all v0.2 population selectors to MaleCNS."""
from __future__ import annotations

import json
import re
from typing import Any

import numpy as np
import pandas as pd

from flyonenomics.io import read_yaml

from common import CACHE, ROOT, load_tables, write_json

OUT = CACHE / "population-audit.json"
POPULATIONS = ROOT / "data" / "populations-v0.2.yaml"


def match(series: pd.Series, selector: dict[str, Any], prefix: str = "") -> np.ndarray:
    kind = selector["kind"]
    if kind == "values":
        return series.isin(selector[prefix + "values"]).to_numpy()
    if kind == "regex":
        return series.fillna("").astype(str).str.match(selector[prefix + "pattern"]).to_numpy()
    raise ValueError(kind)


def male_column(frame: pd.DataFrame, flywire_name: str) -> pd.Series:
    if flywire_name == "hemibrain_type":
        return frame["type"]
    if flywire_name == "cell_type":
        return frame["flywireType"]
    if flywire_name == "known_nt":
        return frame["consensus_nt"]
    if flywire_name == "cell_class":
        return frame["class"]
    if flywire_name == "super_class":
        return frame["superclass"]
    raise KeyError(flywire_name)


def selector_mask(frame: pd.DataFrame, item: dict[str, Any]) -> tuple[np.ndarray | None, str]:
    selector = item["selector"]
    if selector["kind"] == "explicit":
        return None, "explicit FlyWire roots cannot be carried across datasets"
    name = item["name"]
    # Semantic vocabulary changes that are not represented by a column rename.
    if name == "TuBu":
        mask = frame.type.fillna("").str.match(r"^TuBu").to_numpy()
        translation = "cell_class TuBu -> MaleCNS type ^TuBu"
    elif selector["column"] == "super_class" and selector.get("values") == ["descending"]:
        mask = frame.superclass.eq("descending_neuron").to_numpy()
        translation = "super_class descending -> superclass descending_neuron"
    elif selector["column"] == "super_class" and selector.get("values") == ["motor"]:
        mask = frame.superclass.isin(["vnc_motor", "cb_motor"]).to_numpy()
        translation = "super_class motor -> superclass vnc_motor or cb_motor"
    elif selector["column"] == "super_class" and selector.get("values") == ["sensory"]:
        mask = frame.superclass.fillna("").str.contains("sensory").to_numpy()
        translation = "super_class sensory -> any MaleCNS superclass containing sensory"
    else:
        mask = match(male_column(frame, selector["column"]), selector).copy()
        translation = {
            "hemibrain_type": "hemibrain_type -> MaleCNS type",
            "cell_type": "cell_type -> MaleCNS flywireType cross-map",
            "cell_class": "cell_class -> MaleCNS class",
            "super_class": "super_class -> MaleCNS superclass",
        }[selector["column"]]
    if "or_column" in selector:
        other = male_column(frame, selector["or_column"])
        mask |= other.fillna("").astype(str).str.match(selector["or_pattern"]).to_numpy()
    if "and_column" in selector:
        other = male_column(frame, selector["and_column"])
        mask &= other.fillna("").astype(str).str.match(selector["and_pattern"]).to_numpy()
    if "not_column" in selector:
        other = male_column(frame, selector["not_column"])
        mask &= ~other.fillna("").astype(str).str.match(selector["not_pattern"]).to_numpy()
    side = item.get("side")
    if side:
        male_side = frame.somaSide.fillna(frame.rootSide)
        mask &= male_side.eq({"left": "L", "right": "R"}[side]).to_numpy()
        translation += f"; side {side} -> somaSide/rootSide {dict(left='L', right='R')[side]}"
    return mask, translation


def main() -> int:
    annotations, transmitters = load_tables()
    frame = annotations.loc[(annotations.status == "Traced") & annotations.type.notna()].copy().reset_index(drop=True)
    frame = frame.merge(transmitters[["body", "consensus_nt"]], left_on="bodyId", right_on="body", how="left", validate="one_to_one")
    source = read_yaml(POPULATIONS)
    masks: dict[str, np.ndarray] = {}
    rows: list[dict[str, Any]] = []
    for item in source["populations"]:
        name = item["name"]
        mask, translation = selector_mask(frame, item)
        if mask is not None:
            for exclusion in item.get("exclude", []):
                if exclusion not in masks:
                    raise RuntimeError(f"{name}: exclusion {exclusion} has no translated mask")
                mask &= ~masks[exclusion]
            masks[name] = mask
            count = int(mask.sum())
            expected_nt = item.get("expected_nt")
            nt_match = int((mask & frame.consensus_nt.eq(expected_nt).to_numpy()).sum()) if expected_nt else None
            prior = int(item["inventory_count"])
            drift = None if prior == 0 else (count - prior) / prior
            if count == 0 and prior == 0:
                status = "retained_empty"
            elif count == 0:
                status = "no_candidate"
            elif drift is not None and abs(drift) > source["selector_tolerance_percent"] / 100:
                status = "candidate_count_changed"
            else:
                status = "candidate"
        else:
            count = None
            nt_match = None
            drift = None
            status = "manual_remap_required"
        rows.append({
            "name": name,
            "required": bool(item["required"]),
            "flywire_inventory_count": int(item["inventory_count"]),
            "male_candidate_count": count,
            "fractional_count_change": drift,
            "expected_nt": item.get("expected_nt"),
            "male_candidates_with_expected_consensus_nt": nt_match,
            "status": status,
            "translation": translation,
            "warning": "Candidate counts are a naming cross-map, not validated biological equivalence." if mask is not None else translation,
        })
    required = [r for r in rows if r["required"]]
    payload = {
        "dataset": "male-cns:v1.0",
        "source_registry": "data/populations-v0.2.yaml",
        "graph_scope": "status Traced, non-null MaleCNS type",
        "population_count": len(rows),
        "summary": {
            "candidate": sum(r["status"] == "candidate" for r in rows),
            "candidate_count_changed": sum(r["status"] == "candidate_count_changed" for r in rows),
            "no_candidate": sum(r["status"] == "no_candidate" for r in rows),
            "retained_empty": sum(r["status"] == "retained_empty" for r in rows),
            "manual_remap_required": sum(r["status"] == "manual_remap_required" for r in rows),
            "required_total": len(required),
            "required_with_nonzero_naming_candidate": sum((r["male_candidate_count"] or 0) > 0 for r in required),
            "required_manual_remap": [r["name"] for r in required if r["status"] == "manual_remap_required"],
            "required_no_candidate": [r["name"] for r in required if r["status"] == "no_candidate"],
        },
        "special_cases": {
            "CX_DAN": "Rebuild from MaleCNS dopamine candidates and EB/central-complex ROI output; the flat graph alone is insufficient.",
            "sugar_GRN_R": "No sugar modality exists in the checked MaleCNS flat annotations; taste-peg GRNs are not established equivalents.",
            "MN9": "Two MaleCNS MN9 neurons exist; choose laterality rather than carrying the one FlyWire root.",
            "bitter_GRN_R": "No identity mapping from the 21 FlyWire explicit roots was established.",
        },
        "populations": rows,
    }
    write_json(OUT, payload)
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
