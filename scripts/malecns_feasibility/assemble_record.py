#!/usr/bin/env python3
"""Assemble the committed MaleCNS feasibility validation record."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flyonenomics.io import read_json

from common import CACHE, ROOT, file_record, sha256, write_json

OUT = ROOT / "validation" / "records" / "p2" / "malecns-feasibility.json"
SOURCES = CACHE / "sources"
AFTERLIFE = ROOT / ".cache" / "fly-afterlife"


def main() -> int:
    analysis = read_json(CACHE / "analysis.json")
    probe = read_json(CACHE / "probe.json")
    populations = read_json(CACHE / "population-audit.json")
    source_records = analysis["downloads"] + [
        file_record(SOURCES / "download.html", "https://male-cns.janelia.org/download/"),
        file_record(SOURCES / "release.html", "https://male-cns.janelia.org/release/"),
        file_record(SOURCES / "malecns-biorxiv-v2.html", "https://www.biorxiv.org/content/10.1101/2025.10.09.680999v2.full"),
        file_record(SOURCES / "malecns-biorxiv-v2.pdf", "https://www.biorxiv.org/content/10.1101/2025.10.09.680999v2.full.pdf"),
        file_record(SOURCES / "crossref-title.json", "https://api.crossref.org/works?query.title=Sexual%20dimorphism%20in%20the%20complete%20connectome%20of%20the%20Drosophila%20male%20central%20nervous%20system&rows=5"),
        file_record(SOURCES / "crossref-cell-correct.json", "https://api.crossref.org/works/10.1016/j.cell.2026.08.015"),
    ]
    eye_columns = analysis["eye_columns"]
    eye_columns["method"] = (
        "own direct hex, else strongest aggregate hex-tagged input, else output; "
        "ties use lowest (hex1, hex2); DRA/front orientation; no soma/centroid XYZ; "
        "R1-R6 alias rejected as non-unique"
    )
    eye_columns["comparison_with_flywire_v783"] = {
        "flywire_right": "published 796-column map with direct root assignments for all T4a-d/T5a-d; better-supported motion seam today",
        "flywire_left": "no reviewed published left-eye map",
        "malecns_left": "zero direct T4/T5 hex rows; 419-447 unique slots per type from connectivity-derived placement",
        "malecns_right": "zero direct T4/T5 hex rows; 402-458 unique slots per type from connectivity-derived placement",
        "malecns_bilateral": "275-310 common unique slots per T4/T5 type; bilateral but partial and inferred",
    }
    payload = {
        "class": "development",
        "purpose": "MaleCNS v1.0 migration feasibility, with emphasis on optic columns and full-CNS motor routes",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "anatomically and computationally feasible as a new substrate; not a drop-in migration and not validated vision",
        "decision": {
            "recommendation": "proceed only as a separately versioned MaleCNS adapter and calibration programme",
            "eye_labels": "useful for a prototype but incomplete",
            "full_body": "usable graph and candidate sensorimotor routes; behavioural equivalence untested",
            "current_flywire_substrate": "retain as the validation baseline until MaleCNS-specific registries and assays pass",
        },
        "verdict_reasons": [
            "The downloaded v1.0 flat tables build and run in the existing Brian LIF core after conversion to its array schema.",
            "MaleCNS contributes bilateral assignedOlHex1/2 context, but only 15 of flyvis's 65 types have direct labels and T4/T5 require connectivity-derived placement; FlyWire v783 therefore has the better-supported right-eye motion seam today.",
            "The heuristic seam produces 17,593 unique left, 18,918 unique right and 11,994 bilateral flyvis type-position matches, but the shared R1-R6 label cannot identify R1 through R6 and the two lattices are not one-to-one.",
            "All TuBu candidates connect to ER and 974/1,009 MeTu candidates connect to the relevant TuBu set; bilateral motion, descending and motor populations are present.",
            "Three required FlyWire explicit populations need manual remapping: CX_DAN, sugar_GRN_R and MN9; CX_DAN and sugar_GRN_R have no clean checked equivalent.",
            "A one-second zero-input run measures engineering cost only. It cannot show that the model sees, steers or behaves like a male fly.",
        ],
        "provenance": {
            "dataset": "male-cns:v1.0",
            "dataset_release_date": "2026-06-08",
            "checked_at": "2026-09-21",
            "dataset_license": "CC BY 4.0",
            "official_download_page": "https://male-cns.janelia.org/download/",
            "official_release_page": "https://male-cns.janelia.org/release/",
            "paper": {
                "peer_reviewed_title": "Sexual dimorphism in the complete Drosophila male central nervous system connectome",
                "peer_reviewed_citation": "Berg et al., Cell (2026)",
                "peer_reviewed_doi": "10.1016/j.cell.2026.08.015",
                "preprint_doi": "10.1101/2025.10.09.680999",
                "preprint_version": "v2",
                "reference_verification": "Crossref DOI and title queries independently resolve the connectome paper to Berg et al., Cell (2026), DOI 10.1016/j.cell.2026.08.015.",
            },
            "downloads": source_records,
            "derived_text": {
                "path": ".cache/malecns-v1.0/sources/malecns-biorxiv-v2.txt",
                "derived_from": ".cache/malecns-v1.0/sources/malecns-biorxiv-v2.html",
                "bytes": (SOURCES / "malecns-biorxiv-v2.txt").stat().st_size,
                "sha256": sha256(SOURCES / "malecns-biorxiv-v2.txt"),
            },
            "method_precedent": {
                "repository": "https://github.com/nsfm/fly-afterlife.git",
                "commit": "e4d3f0bf1ee65651e189cc07868659f1f366efd4",
                "license": "MIT",
                "scope": "connectivity-derived MaleCNS optic-column placement and pinned DRA/front orientation; evidence, not imported production code",
                "license_sha256": sha256(AFTERLIFE / "LICENSE"),
            },
            "source_policy": "The downloadable flat tables are CC BY 4.0. Preserve release, URL, checksum and attribution in any adapter or redistributed derived graph.",
        },
        "assumptions": [
            "Graph nodes are MaleCNS status=Traced rows with non-null type; edges retain both endpoints and at least five synapses.",
            "Connection sign is presynaptic consensus_nt under the Shiu fast-transmitter convention: acetylcholine/dopamine/serotonin/octopamine positive; GABA/glutamate/histamine negative.",
            "Unclear or missing consensus neurotransmitter gives zero outgoing model weight, not an inferred sign.",
            "Population cross-maps are naming candidates, not claims that male and female neurons are functionally interchangeable.",
            "Eye placement takes a cell's direct hex if present, else its strongest aggregate hex-tagged input, else output; a tie uses the lowest (hex1, hex2). DRA photoreceptors define up and fly-afterlife FRONT_SIGN=-1 defines front. Neuron soma/centroid XYZ positions are not used; somaSide/rootSide only selects the eye.",
            "Only uniquely occupied transformed flyvis positions count; the one MaleCNS R1-R6 type is rejected for all six separate flyvis identities.",
            "The current 0.275 mV/synapse scale and v0.2 LIF parameters were reused only for cost/path probes and require recalibration.",
        ],
        "graph": analysis["graph"],
        "neurotransmitters": analysis["signs"],
        "population_audit": populations,
        "key_populations": analysis["populations"],
        "ring_route_relevance": analysis["ring_route_relevance"],
        "eye_columns": eye_columns,
        "motor_routes": analysis["motor_routes"],
        "cost_probe": probe,
        "engineering_port": {
            "reusable": [
                "BrianEngine dynamics, sparse array cache, stepping, snapshot and deterministic-seed machinery",
                "edge-weight conversion after a MaleCNS adapter supplies root_ids/i/j/weights",
                "generic population/compartment concepts after rebuilding memberships",
            ],
            "must_change": [
                "Add a first-class male-cns:v1.0 version; current type and experiment literals admit only 630/783.",
                "Replace filename switches in connectome_arrays and orchestrator workers with dataset adapters.",
                "Add a MaleCNS annotation schema and versioned engine-order loader; do not alias it to 783 as the probe does.",
                "Rebuild all 142 population memberships, explicit roots, side rules, inventory tolerances and overlap declarations.",
                "Rebuild compartment targets, CX_DAN ROI filtering, W/M matrices, dopamine calibration and receptor/exposure assumptions.",
                "Replace FlyWire retinotopy root lists with a versioned MaleCNS eye seam carrying method and confidence per assignment.",
                "Introduce a new substrate identity and MaleCNS-specific params/drive/dopamine/behaviour versions; never relabel existing v783 records.",
                "Re-run structural, resting, reflex, visual-path, open-loop and behavioural validations before making MaleCNS a default.",
            ],
        },
        "limitations": [
            "Only the annotation, aggregate transmitter and aggregate weighted-connection flat files were downloaded; ROI synapse-distribution and point tables were not needed for this bounded check and remain required for production CX_DAN/compartment work.",
            "The 151,856,684 raw connection rows include untyped/untraced segments; the feasibility graph deliberately keeps 6,138,378 edges after endpoint and weight filters.",
            "MaleCNS direct optic hex fields cover 23,720 typed traced rows overall and 15/65 flyvis types, not a complete flyvis-to-MaleCNS identity map.",
            "Connectivity-derived eye labels are sensitive to graph version, strongest-partner ties, orientation and rounding; 770/769 physical T4/T5 columns fall inside a 721-site target lattice before collision rejection, proving the transform is not bijective.",
            "The exploratory path product is topology bookkeeping, not a biological gain or simulated propagation result.",
            "MaleCNS is male while the current substrate and many calibrations use a female FlyWire brain; sex-specific and dimorphic circuitry prevent blanket transfer of validation claims.",
        ],
        "reproduction": [
            "uv run python scripts/malecns_feasibility/fetch.py --download",
            "uv run python scripts/malecns_feasibility/build_graph.py",
            "uv run python scripts/malecns_feasibility/analyse.py",
            "uv run python scripts/malecns_feasibility/audit_populations.py",
            "uv run python scripts/malecns_feasibility/run_probe.py",
            "uv run python scripts/malecns_feasibility/assemble_record.py",
        ],
    }
    write_json(OUT, payload)
    print(OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
