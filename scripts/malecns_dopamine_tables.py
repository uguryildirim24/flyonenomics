#!/usr/bin/env python3
"""Rebuild MaleCNS port-step-5 anatomy tables without running an engine."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
from flyonenomics.datasets import get_dataset_adapter
from flyonenomics.drive.background import MALE_DRIVE_GROUPS, group_indices
from flyonenomics.io import hash_file, read_json, read_yaml
from flyonenomics.registry import Registry, build_registry
from flyonenomics.substrate.transmitters import (
    annotations_in_engine,
    classify_engine,
    transmitters_payload,
)
from flyonenomics.drive.rest import blob_id

ROOT = Path(__file__).resolve().parents[1]
MALE = "male-cns:v1.0"
EXPECTED_FLYWIRE_ENGINE = {
    "630": {
        "root_ids": "a659694cfe091ac64f31cdbeff270a914ee27168b06f7b4068d2781c4beea0e6",
        "presynaptic_indices": "50e4a0ca5767dd429512d1cc7a6be7786aa907649cc866e4c0056323d3c9d750",
        "postsynaptic_indices": "54a3ce131f7268bee223408bba87e76a14ed8f23e6784a9ff880c6715787de1d",
        "signed_weights": "790d7925a908265bda5fca8357af6a077d3b39d4b9386e76f8aa85a4c759869b",
    },
    "783": {
        "root_ids": "70200482b9fe6656f215a97b71332dd6725b80e2cb32e0052a4d47916ca1579b",
        "presynaptic_indices": "8ec65c761057a2b000dcc246d6dc94a586b31596b8331c1db1ada61691d67f17",
        "postsynaptic_indices": "302786e9dacecf6f04683f7e46a6c3aa223b136b42b44880ccae0f0487dcd5f3",
        "signed_weights": "8ddd4ff45983bd9855ffa01ad5099ccdbd138bc9eb8d6cc2cb2433d01ca18a49",
    },
}
EXPECTED_FLYWIRE_REGISTRY = {
    "root_ids": "70200482b9fe6656f215a97b71332dd6725b80e2cb32e0052a4d47916ca1579b",
    "W": "f775933b8ca9638087a5f1552a9e6c828b195638be422a22a65747f628934259",
    "M": "d7b04ce82828e6bff3d2664b367baa62518ddd736e989aaf19383c3c22e07b5e",
    "receptors": "071f4c28fef94537abf14b4121194786c9f8059fdb116b3858dd98d3dfa08a4c",
}
EXPECTED_FLYWIRE_TRANSMITTER = "097100ec1abdc1a57b64da8e782ba4fcfef2dc85acf58906fd5cff023066698e"


def sha_arrays(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def sparse_hash(matrix: Any) -> str:
    csr = matrix.tocsr()
    return sha_arrays(csr.data, csr.indices, csr.indptr)


def registry_summary(registry: Registry) -> dict[str, Any]:
    w = registry.exposure()
    m = registry.innervation()
    receptor = registry.receptors()
    inventories = []
    for compartment in registry.compartments():
        inventories.append({
            "name": compartment.name,
            "side": compartment.side,
            "exposure_nonzero_cells": int(w[:, compartment.id].getnnz()),
            "innervating_dan_cells": int(m[compartment.id, :].getnnz()),
        })
    return {
        "neurons": registry.n,
        "compartments": len(registry.compartments()),
        "compartment_inventory": inventories,
        "W_exposure": {"shape": list(w.shape), "nonzero": int(w.nnz)},
        "M_innervation": {"shape": list(m.shape), "nonzero": int(m.nnz)},
        "exposed_cells": int(registry.exposed_mask().sum()),
        "receptor_nonzero_cells": {
            "r1": int(np.count_nonzero(receptor.r1)),
            "r2": int(np.count_nonzero(receptor.r2)),
            "rq": int(np.count_nonzero(receptor.rq)),
            "any": int(np.count_nonzero((receptor.r1 != 0) | (receptor.r2 != 0) | (receptor.rq != 0))),
        },
        "DA_exposed_cells": int(np.count_nonzero(
            np.asarray(registry.exposed_mask())
            & ((receptor.r1 != 0) | (receptor.r2 != 0) | (receptor.rq != 0))
        )),
        "hashes": {
            "root_ids": sha_arrays(registry.root_ids),
            "W": sparse_hash(w),
            "M": sparse_hash(m),
            "receptors": sha_arrays(receptor.r1, receptor.r2, receptor.rq),
        },
        "provenance": registry.provenance(),
    }


def target_totals(registry: Registry) -> dict[str, int]:
    """Count non-DAN target rows in the seven CX columns."""
    w = registry.exposure().tolil(copy=True)
    dan_rows = np.unique(np.concatenate((registry.population("DAN").idx, registry.population("CX_DAN").idx)))
    if dan_rows.size:
        w[dan_rows, :] = 0
    csr = w.tocsr()
    return {
        c.name: int(csr[:, c.id].getnnz())
        for c in registry.compartments()
        if c.name in {"EB", "PB", "FB", "NO_L", "NO_R", "LAL_L", "LAL_R"}
    }


def write_compartment_totals(registry: Registry) -> None:
    path = ROOT / "data" / "compartments-male-cns-v1.0.yaml"
    raw = read_yaml(path)
    raw["target_mask_totals"] = target_totals(registry)
    path.write_text(yaml.safe_dump(raw, sort_keys=False, width=120))


def write_transmitter_table() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    male_classes, _frame, male_census = classify_engine(connectome_version=MALE)
    male_payload = transmitters_payload(male_classes, male_census, connectome_version=MALE)
    path = ROOT / "data" / "transmitters-male-cns-v1.0.yaml"
    path.write_text(yaml.safe_dump(male_payload, sort_keys=False, width=120))
    fly_classes, _fly_frame, fly_census = classify_engine(connectome_version="783")
    fly_payload = transmitters_payload(fly_classes, fly_census, connectome_version="783")
    if fly_payload["classes_sha256"] != EXPECTED_FLYWIRE_TRANSMITTER:
        raise ValueError("FlyWire transmitter classes moved")
    return male_payload, fly_payload, male_census


def write_dopamine_table(compartments: list[str]) -> None:
    source = read_yaml(ROOT / "data" / "dopamine-v0.2.yaml")
    unset = [None] * len(compartments)
    payload = {
        "version": "male-cns-v1.0",
        "params_version": None,
        "receptor_map_version": "male-cns-v1.0",
        "connectome_version": MALE,
        "compartments": compartments,
        "R_c": unset,
        "alpha_c": unset.copy(),
        "S_c": unset.copy(),
        "mode": unset.copy(),
        "constants": source["constants"],
        "drive_blob_id": None,
        "calibration_status": "unset",
        "calibration_required": "Port step 7 must calibrate the MaleCNS resting drive and rerun WP19 K2r; no FlyWire R_c, alpha_c, S_c, mode, or drive binding transfers.",
        "provenance": {"source_method": "WP19 K2r", "male_record": None},
    }
    (ROOT / "data" / "dopamine-male-cns-v1.0.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120)
    )


def write_drive_table(male: Registry, transmitter_path: Path) -> dict[str, int]:
    source = read_yaml(ROOT / "data" / "drive-v0.2.yaml")
    groups = group_indices(male)
    sizes = {str(name): int(indices.size) for name, indices in groups.items()}
    payload = {
        "version": "male-cns-v1.0",
        "transmitter_rule": {
            "blob_id": blob_id(transmitter_path),
            "scope": source["transmitter_rule"]["scope"],
        },
        "scales": {
            "g_gaba": None,
            "g_glu": None,
            "g_his": source["scales"]["g_his"],
            "g_gaba_kc": None,
            "unk": source["scales"]["unk"],
            "sha256": None,
        },
        "background": {
            "n_bg": source["background"]["n_bg"],
            "r_bg": source["background"]["r_bg"],
            "groups": {name: {"size": size, "w_bg": None} for name, size in sizes.items()},
        },
        "threshold": {"sigma_th": None, "seed": None, "z_sha256": None},
        "optic_exemption": None,
        "mechanisms": None,
        "calibration_status": "unset",
        "calibration_required": "Port step 7 must select scales, every background weight, threshold spread, optic exemption, and mechanism on MaleCNS. Null is not a zero or FlyWire fallback.",
        "provenance": {"source_stage": "MaleCNS port step 7", "record": None},
    }
    (ROOT / "data" / "drive-male-cns-v1.0.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120)
    )
    return sizes


def male_drive_translation() -> list[dict[str, Any]]:
    """Count every released MaleCNS superclass before population overrides."""
    frame, _roots = annotations_in_engine(MALE)
    counts = frame["super_class"].astype(str).value_counts().to_dict()
    return [
        {
            "male_super_class": source,
            "conceptual_group": MALE_DRIVE_GROUPS[source],
            "cells": int(counts.get(source, 0)),
        }
        for source in MALE_DRIVE_GROUPS
    ]


def broad_kc_roi_evidence(roots: list[int]) -> dict[str, Any]:
    """Count released synapse-point ROIs for broad, otherwise untyped KCs."""
    import pyarrow as pa
    import pyarrow.ipc as ipc

    path = get_dataset_adapter(MALE).auxiliary_table_path("synapse_points")
    if path is None:
        raise ValueError("MaleCNS adapter carries no synapse-point table")
    wanted = np.asarray(sorted(roots), dtype=np.int64)
    counts = {int(root): Counter() for root in wanted}
    with pa.memory_map(str(path), "r") as mapped:
        reader = ipc.open_file(mapped)
        body_col = reader.schema.get_field_index("body")
        kind_col = reader.schema.get_field_index("kind")
        primary_col = reader.schema.get_field_index("primary")
        subprimary_col = reader.schema.get_field_index("subprimary")
        for batch_number in range(reader.num_record_batches):
            batch = reader.get_batch(batch_number)
            bodies = batch.column(body_col).to_numpy(zero_copy_only=False).astype(np.int64, copy=False)
            slots = np.flatnonzero(np.isin(bodies, wanted))
            for slot in slots:
                body = int(bodies[slot])
                kind = str(batch.column(kind_col)[int(slot)].as_py())
                primary = str(batch.column(primary_col)[int(slot)].as_py())
                subprimary = str(batch.column(subprimary_col)[int(slot)].as_py())
                counts[body][f"{kind}:{primary}:{subprimary}"] += 1
    return {
        "source": path.name,
        "rows": [
            {
                "root": root,
                "roi_counts": dict(sorted(counts[root].items())),
                "lobe_roi_present": any(
                    key.split(":", 2)[1].startswith(("gL(", "aL(", "bL(", "a'L(", "b'L("))
                    for key in counts[root]
                ),
            }
            for root in sorted(counts)
        ],
    }


def unplaced_type_effects(male: Registry, flywire: Registry) -> dict[str, Any]:
    """Measure each unmatched anatomy label and its bounded matrix effect."""
    frame, _roots = annotations_in_engine(MALE)
    source_type = frame["hemibrain_type"].fillna("").astype(str)
    flywire_type = frame["cell_type"].fillna("").astype(str)
    dan_types = ("PPL107", "PPL108", "PPL201", "PPL202", "PPL203", "PPL204")
    dan = [
        {
            "type": name,
            "cells": int(np.count_nonzero(source_type == name)),
            "effect": "all-zero M columns; the cited anatomy is outside the 30 represented MB lobes",
        }
        for name in dan_types
    ]
    mbon_mask = source_type == "MBON25-like"
    mbon_roots = frame.loc[mbon_mask, "root_id"].astype(np.int64).tolist()
    fallback_mask = mbon_mask & (flywire_type == "MBON25,MBON34")
    fallback_roots = frame.loc[fallback_mask, "root_id"].astype(np.int64).tolist()
    unplaced_mbon_roots = sorted(set(mbon_roots) - set(fallback_roots))
    kc_mask = source_type == "KC"
    kc_roots = frame.loc[kc_mask, "root_id"].astype(np.int64).tolist()
    male_summary = registry_summary(male)
    fly_summary = registry_summary(flywire)
    return {
        "DAN": dan,
        "MBON25-like": {
            "cells": len(mbon_roots),
            "placed_by_exact_flywire_type": len(fallback_roots),
            "placed_roots": sorted(fallback_roots),
            "unplaced_cells": len(unplaced_mbon_roots),
            "unplaced_roots": unplaced_mbon_roots,
            "rule": "when source type is not a declared key, use an exact released flywireType that is a declared Aso/Li key",
        },
        "broad_KC": {
            "cells": len(kc_roots),
            "roots": sorted(kc_roots),
            "flywire_type_values": sorted(set(flywire_type[kc_mask]) - {""}),
            "subclass_values": sorted(set(frame.loc[kc_mask, "cell_sub_class"].dropna().astype(str))),
            "effect_if_a_lobe_were_known": {
                "additional_exposed_cells": len(kc_roots),
                "additional_W_nonzeros": 5 * len(kc_roots),
            },
            "released_roi_evidence": broad_kc_roi_evidence(kc_roots),
        },
        "matrix_gap": {
            "W_nonzeros_male_minus_flywire": int(
                male_summary["W_exposure"]["nonzero"] - fly_summary["W_exposure"]["nonzero"]
            ),
            "exposed_cells_male_minus_flywire": int(
                male_summary["exposed_cells"] - fly_summary["exposed_cells"]
            ),
            "KC_population_male_minus_flywire": int(
                male.population("KC").count - flywire.population("KC").count
            ),
            "broad_KC_explains_gap": False,
        },
    }


def flywire_engine_hashes() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for version in ("630", "783"):
        completeness, connectivity = connectome_source_paths(version)
        roots, pre, post, weights = load_connectome_arrays(completeness, connectivity)
        measured = {
            "root_ids": sha_arrays(roots),
            "presynaptic_indices": sha_arrays(pre),
            "postsynaptic_indices": sha_arrays(post),
            "signed_weights": sha_arrays(weights),
        }
        if measured != EXPECTED_FLYWIRE_ENGINE[version]:
            raise ValueError(f"FlyWire {version} engine arrays moved: {measured}")
        result[version] = measured
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the five tables and audit record")
    args = parser.parse_args()
    if not args.write:
        parser.error("--write is required")

    male = build_registry(MALE)
    fly_default = build_registry("783")
    fly_v02 = build_registry("783", populations_path=ROOT / "data" / "populations-v0.2.yaml")
    write_compartment_totals(male)
    male_transmitters, fly_transmitters, male_transmitter_census = write_transmitter_table()
    transmitter_path = ROOT / "data" / "transmitters-male-cns-v1.0.yaml"
    write_dopamine_table([c.name for c in male.compartments()])
    male_group_sizes = write_drive_table(male, transmitter_path)
    fly_group_sizes = {str(name): int(idx.size) for name, idx in group_indices(fly_v02).items()}

    male_summary = registry_summary(male)
    fly_summary = registry_summary(fly_v02)
    if fly_summary["hashes"] != EXPECTED_FLYWIRE_REGISTRY:
        raise ValueError("FlyWire registry arrays moved")
    default_summary = registry_summary(fly_default)
    if default_summary["hashes"] != EXPECTED_FLYWIRE_REGISTRY:
        raise ValueError("FlyWire default registry arrays moved")

    compartment_table = read_yaml(ROOT / "data" / "compartments-male-cns-v1.0.yaml")
    candidates = male.candidate_fractions()
    manifest = read_json(ROOT / "data" / "malecns-v1.0-manifest.json")
    source_hashes = {row["name"]: row["sha256"] for row in manifest["files"]}
    male_derived = get_dataset_adapter(MALE).connectome_files().connectivity.parent
    male_derived_provenance = read_json(male_derived / "provenance.json")
    output_names = (
        "compartments-male-cns-v1.0.yaml",
        "receptors-male-cns-v1.0.yaml",
        "transmitters-male-cns-v1.0.yaml",
        "dopamine-male-cns-v1.0.yaml",
        "drive-male-cns-v1.0.yaml",
    )
    record = {
        "record": "malecns-dopamine-tables",
        "class": "development",
        "connectome_version": MALE,
        "adapter_policy": "male-cns-adapter-v3",
        "release": {
            "date": manifest["release_date"],
            "license": manifest["license"],
            "attribution": manifest["attribution"],
            "source_sha256": source_hashes,
        },
        "rules_frozen_before_output": {
            "classification": "validation/records/p2/malecns-dopamine-classification.json at Part A commit f1f723fd2bb1c017c440637b379cacfd7f17eb76",
            "mb_kc_types": "Aso et al. 2014 and Li et al. 2020 hemibrain-style names; same equal-split rules as FlyWire",
            "cxdan_filter": "candidate central-complex primary_post synapses / every outgoing syn-partners row >= 0.2",
            "NO": "keep NO_L/NO_R; assign primary_post NO by postsynaptic canonical side (somaSide then rootSide), split missing side 0.5/0.5; include every NO row in the filter numerator",
            "receptors": "same cited/placeholder densities and precedence, expanded on MaleCNS memberships",
            "transmitters": "same class order: photoreceptor histamine, curated/ground-truth label, then released presynaptic sign and consensus label",
            "drive_groups": "translate MaleCNS regional superclasses into the FlyWire drive's 12 conceptual groups before DAN/CX_DAN, KC, and ER overrides; every sensory-labelled superclass stays sensory",
            "calibration": "all graph-selected drive and dopamine values are null until port step 7",
        },
        "unplaced_types": {
            "DAN": compartment_table["unplaced_dan_types"],
            "MBON": compartment_table["unplaced_mbon_types"],
            "KC": compartment_table["unplaced_kc_types"],
        },
        "unplaced_type_effects": unplaced_type_effects(male, fly_v02),
        "cxdan": {
            "candidates": len(candidates),
            "kept": male.population("CX_DAN").count,
            "fractions": [{"root": root, "fraction": candidates[root]} for root in sorted(candidates)],
            "difference_from_flywire": "MaleCNS counts each released partner synapse by its own primary_post ROI; FlyWire weights aggregate partner pairs by the target cell's declared W row.",
        },
        "structural_comparison": {"male_cns": male_summary, "flywire_v783": fly_summary},
        "drive_group_sizes": {"male_cns": male_group_sizes, "flywire_v783": fly_group_sizes},
        "drive_superclass_translation": male_drive_translation(),
        "transmitters": {
            "male_cns": {
                **{k: male_transmitters[k] for k in ("n_engine", "classes_sha256", "class_counts", "mixed_sign_neurons", "s_pq_vs_top_nt_n")},
                "output_bearing_class_counts": male_transmitter_census["output_bearing_class_counts"],
                "no_output_class_counts": male_transmitter_census["no_output_class_counts"],
                "unknown_definition": "class unk means no curated classical/modulatory assignment and no named class under the released presynaptic sign; it does not mean an unsigned engine edge",
                "unknown_consensus_sign_derivation": male_derived_provenance["unknown_neuron_signs"],
                "engine_edges_zero_signed": male_derived_provenance["item150_after_counts"]["edges_zero_weight"],
            },
            "flywire_v783": {k: fly_transmitters[k] for k in ("n_engine", "classes_sha256", "class_counts", "mixed_sign_neurons", "s_pq_vs_top_nt_n")},
        },
        "flywire_unchanged": {
            "default_and_v0.2_registry_hashes_identical": True,
            "registry_hashes": fly_summary["hashes"],
            "engine_array_hashes": flywire_engine_hashes(),
            "transmitter_classes_sha256": fly_transmitters["classes_sha256"],
        },
        "calibration": {
            "performed": False,
            "engine_run": False,
            "unset_dopamine_paths": ["R_c", "alpha_c", "S_c", "mode", "drive_blob_id", "provenance.male_record"],
            "unset_drive_paths": ["scales.g_gaba", "scales.g_glu", "scales.g_gaba_kc", "scales.sha256", "background.groups.*.w_bg", "threshold.*", "optic_exemption", "mechanisms", "provenance.record"],
            "null_loader_rule": "explicit null calibrated fields raise; there is no zero or FlyWire fallback",
        },
        "files": {name: hash_file(ROOT / "data" / name) for name in output_names},
        "limitations": [
            "No sugar-labelled MaleCNS input exists, so this does not restore the reflex check.",
            "No engine was run and no resting, visual, steering, or behavioural outcome was inspected.",
            "The eye assignment remains partial and inferred; the fly does not see.",
        ],
    }
    destination = ROOT / "validation" / "records" / "p2" / "malecns-dopamine-tables.json"
    destination.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "record": str(destination),
        "male": male_summary,
        "flywire": fly_summary,
        "files": record["files"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
