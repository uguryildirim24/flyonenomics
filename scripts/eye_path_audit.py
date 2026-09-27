"""Reconciliation audit of the signal-transfer voltage probe (t-0028).

Three arithmetic checks on committed evidence, no new engine run:
1. Reconcile the -52.01 mV baseline, the recorded 7.02-7.26 mV gap and the
   -44.7437 mV thresholds with the declared substrate's threshold array.
2. Reconstruct each traced eye target's photoreceptor drive from the
   instantiated weights, the connection-weighted presynaptic event sum and
   the implemented decay constant, and compare it with the recorded voltage.
3. Quantify what the fixed signed-current synapse costs at the deepest eye
   targets, against the project's own conductance-reversal placeholders.

Units: mV for voltages and weights, s for time constants, Hz for rates.
This runner only reads committed records and the pinned scale inputs; it
writes one JSON record and changes no engine behaviour.
"""

from __future__ import annotations

import argparse
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
AUDITED_RECORD = ROOT / "validation" / "records" / "p2" / "signal-transfer-audit.json"
DEFAULT_OUT = ROOT / "validation" / "records" / "p2" / "eye-path-audit.json"
DRIVE_PATH = ROOT / "data" / "drive-v0.2.yaml"
PARAMS_PATH = ROOT / "data" / "params-v0.2.yaml"
DOPAMINE_PATH = ROOT / "data" / "dopamine-v0.2.yaml"
DECLARED_SUBSTRATE_STRING = "1.0-4.0-0.0-False-100-1.0-kc-6.0-sens"
DECLARED_SUBSTRATE_ID = "rest:379cc4cc9030cdd1"
DECLARED_FIELDS = {
    "w_bg_mv": 1.0,
    "g_glu": 4.0,
    "sigma_th_mv": 0.0,
    "optic_exemption": False,
    "n_bg": 100,
    "g_gaba": 1.0,
    "g_gaba_kc": 6.0,
    "arm": "sens",
}
MEASURE_S = 2.0
TAU_S = 0.005
V0_MV = -52.0
E_CL_MV = (-72.0, -62.0, -57.0)
# Sources of the two arrays in check 1, as file:line at the audited checkout.
BASE_THRESHOLD_SOURCE = (
    "data/drive-v0.2.yaml:52 threshold: null",
    "src/flyonenomics/drive/rest.py:628 sigma = drive.get('sigma_th', 0.0) or 0.0",
    "src/flyonenomics/drive/rest.py:629-630 if not thresholds or sigma == 0.0: "
    "return np.full(neurons, v_th), scale",
)
COMPOSED_THRESHOLD_SOURCE = (
    "src/flyonenomics/neuromod/state.py:303 "
    "threshold = np.clip(self.base_v_th + self.shift + d_v, *rec.vth_clip)",
    "src/flyonenomics/neuromod/receptors.py:18 "
    "d_v = -rec.dV_D1 * r1 * occ1 + rec.dV_D2 * r2 * occ2",
    "scripts/audit_signal_transfer.py:488-491,507,520 the gap is threshold_mean - sampled mean",
)


def _sha256(path: Path) -> str:
    from flyonenomics.io import hash_file

    return hash_file(path)


def _load_scale_inputs() -> dict[str, Any]:
    """Load the pinned connectome, transmitter classes and composed weight array."""
    from flyonenomics.connectome_arrays import connectome_source_paths, load_connectome_arrays
    from flyonenomics.drive.rest import apply_rest_substrate, kc_mask_in_engine, load_drive_rest
    from flyonenomics.registry import build_registry
    from flyonenomics.substrate.transmitters import load_transmitters
    from flyonenomics.types import load_params

    class ScaleSink:
        n = 138639

        @staticmethod
        def engine_model() -> str:
            return "lif"

        @staticmethod
        def set_weight_scale(value: np.ndarray) -> None:
            del value

    params = load_params(PARAMS_PATH)
    registry = build_registry("783", populations_path=ROOT / "data" / "populations-v0.2.yaml")
    drive = load_drive_rest(DRIVE_PATH)
    completeness, connectivity = connectome_source_paths("783")
    roots, pre, post, raw = load_connectome_arrays(completeness, connectivity)
    classes = load_transmitters()["class_array"]
    base, scale = apply_rest_substrate(
        ScaleSink(), params, drive, classes=classes, pre=pre, post=post,
        kc_mask=kc_mask_in_engine(), n=registry.n,
    )
    w_syn = float(params.get("lif.w_syn"))
    effective = np.asarray(raw, dtype=np.float64) * w_syn * scale
    return {
        "params": params,
        "registry": registry,
        "drive": drive,
        "roots": np.asarray(roots),
        "pre": np.asarray(pre),
        "post": np.asarray(post),
        "raw": np.asarray(raw, dtype=np.float64),
        "classes": classes,
        "scale": np.asarray(scale),
        "effective": effective,
        "base_v_th": np.asarray(base),
        "w_syn": w_syn,
    }


def _threshold_section(scale_inputs: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    """Check 1: distinct base and composed threshold values with their cell classes."""
    from flyonenomics.io import read_yaml
    from flyonenomics.neuromod.state import Neuromod
    from flyonenomics.substrate.transmitters import annotations_in_engine
    from flyonenomics.types import LayerFlags

    registry = scale_inputs["registry"]
    params = scale_inputs["params"]
    base = scale_inputs["base_v_th"]
    dopamine = read_yaml(DOPAMINE_PATH)
    mod = Neuromod(
        registry, params,
        LayerFlags(background=True, dopamine_A=True, transporter_C=True),
        dopamine, base_v_th=base, schema_version="1.3",
    )
    mod.reset_fast()
    composed = np.asarray(mod.compose().v_th, dtype=np.float64)

    frame, _roots = annotations_in_engine()
    class_of = frame["cell_class"].fillna("").to_numpy(dtype=str)
    super_of = frame["super_class"].fillna("").to_numpy(dtype=str)

    def groups(values: np.ndarray) -> list[dict[str, Any]]:
        order = np.argsort(values, kind="stable")
        sorted_values = values[order]
        rows: list[dict[str, Any]] = []
        start = 0
        for index in range(1, len(sorted_values) + 1):
            if index == len(sorted_values) or sorted_values[index] != sorted_values[start]:
                mask = np.zeros(len(values), dtype=bool)
                mask[order[start:index]] = True
                labels, counts = np.unique(class_of[mask], return_counts=True)
                top = sorted(
                    ({"cell_class": str(label) or "<missing>", "count": int(count)}
                     for label, count in zip(labels, counts, strict=True)),
                    key=lambda row: -row["count"],
                )[:5]
                rows.append({"value_mV": float(sorted_values[start]), "count": int(index - start),
                             "cell_classes": top})
                start = index
        return rows

    base_groups = groups(np.asarray(base, dtype=np.float64))
    composed_groups = groups(composed)
    target_section: dict[str, Any] = {}
    for path in ("eye", "TuBu"):
        indices = np.asarray(audit["static_paths"][path]["strongest_target_indices"], dtype=np.int64)
        values, counts = np.unique(np.round(composed[indices], 12), return_counts=True)
        target_section[path] = {
            "targets_n": int(len(indices)),
            "composed_threshold_counts": [
                {"value_mV": float(value), "count": int(count)}
                for value, count in zip(values, counts, strict=True)
            ],
        }
    return {
        "declared_substrate_id": DECLARED_SUBSTRATE_ID,
        "declared_substrate_string": DECLARED_SUBSTRATE_STRING,
        "declared_fields": DECLARED_FIELDS,
        "base_threshold_mV": {
            "distinct_n": len(base_groups),
            "groups": base_groups,
            "source": list(BASE_THRESHOLD_SOURCE),
            "meaning": "the substrate's own threshold array; sigma_th is 0, so lif.v_th everywhere",
        },
        "composed_threshold_mV": {
            "distinct_n": len(composed_groups),
            "groups": composed_groups,
            "source": list(COMPOSED_THRESHOLD_SOURCE),
            "meaning": "base + dopamine d_v at the dark fixed point; the spread is not the substrate's",
        },
        "traced_targets": target_section,
        "substrate_carries_spread": False,
        "spread_origin": "the dopamine A layer's receptor term d_v, not the drive threshold section",
        "false_field_meaning": "optic_exemption is off; sigma_th 0.0 is the no-spread field",
    }


def _gap_section(audit: dict[str, Any]) -> dict[str, Any]:
    """Check 1: the recorded TuBu baseline and gap against the composed threshold."""
    dynamic = audit["dynamic_paths"]["TuBu"]
    off_v = np.array([
        target["before"]["sampled_mean_v_mV"]
        for row in dynamic["paired_rows"] for target in row["targets"]
    ])
    off_th = np.array([
        target["before"]["threshold_mean_mV"]
        for row in dynamic["paired_rows"] for target in row["targets"]
    ])
    off_gap = np.array([
        target["before"]["mean_distance_to_threshold_mV"]
        for row in dynamic["paired_rows"] for target in row["targets"]
    ])
    values, counts = np.unique(off_th, return_counts=True)
    return {
        "condition": "TuBu input off",
        "rows": int(len(off_v)),
        "baseline_mean_v_mV": float(off_v.mean()),
        "baseline_min_v_mV": float(off_v.min()),
        "baseline_max_v_mV": float(off_v.max()),
        "recorded_gap_mean_mV": float(off_gap.mean()),
        "recorded_gap_min_mV": float(off_gap.min()),
        "recorded_gap_max_mV": float(off_gap.max()),
        "recomputed_gap_mean_mV": float((off_th - off_v).mean()),
        "threshold_counts": [
            {"value_mV": float(value), "count": int(count)}
            for value, count in zip(values, counts, strict=True)
        ],
        "declared_gap_at_minus_45_mV": float(-45.0 - off_v.mean()),
    }


def _reconstruction_section(audit: dict[str, Any]) -> dict[str, Any]:
    """Check 2: connection-weighted photoreceptor drive versus recorded voltage."""
    dynamic = audit["dynamic_paths"]["eye"]
    summary = dynamic["per_target_three_seed_summary"]
    rows_by_position: dict[int, dict[str, list[dict[str, float]]]] = {
        position: {"ambient": [], "stripe": []} for position in range(len(summary))
    }
    conditions = {"before": "ambient", "after": "stripe"}
    for seed_row in dynamic["paired_rows"]:
        for position, target in enumerate(seed_row["targets"]):
            for key, name in conditions.items():
                measured = target[key]["sampled_mean_v_mV"]
                event_sum = target[key]["source_incoming_event_amplitude_sum_mV"]
                recurrent = target[key]["all_recurrent_incoming_event_amplitude_sum_mV"]
                predicted = V0_MV + event_sum / MEASURE_S * TAU_S
                rows_by_position[position][name].append({
                    "condition": name,
                    "seed": int(seed_row["seed"]),
                    "source_event_sum_mV": float(event_sum),
                    "all_recurrent_event_sum_mV": float(recurrent),
                    "sampled_mean_v_mV": float(measured),
                    "sampled_min_v_mV": float(target[key]["sampled_min_v_mV"]),
                    "sampled_max_v_mV": float(target[key]["sampled_max_v_mV"]),
                    "threshold_mean_mV": float(target[key]["threshold_mean_mV"]),
                    "measured_v_minus_v0_mV": float(measured - V0_MV),
                    "reconstructed_mean_v_mV": float(predicted),
                    "residual_mV": float(measured - predicted),
                    "connected_source_cells": int(target[key]["connected_source_cells"]),
                    "connected_source_spikes": int(target[key]["connected_source_spikes"]),
                })
    targets: list[dict[str, Any]] = []
    residuals: list[float] = []
    for position, entry in enumerate(summary):
        target_rows: dict[str, Any] = {}
        for name in ("ambient", "stripe"):
            condition_rows = rows_by_position[position][name]
            target_rows[name] = condition_rows
            residuals.extend(row["residual_mV"] for row in condition_rows)
        targets.append({
            "position": position,
            "engine_index": int(entry["engine_index"]),
            "root_id": int(entry["root_id"]),
            "cell_type": entry.get("cell_type"),
            "super_class": entry.get("super_class"),
            "ambient": target_rows["ambient"],
            "stripe": target_rows["stripe"],
            "max_abs_residual_mV": float(max(
                abs(row["residual_mV"])
                for row in target_rows["ambient"] + target_rows["stripe"]
            )),
        })
    residual_array = np.asarray(residuals, dtype=np.float64)
    # The pooled-rate substitution the record avoids: weight sum times the
    # unweighted mean rate of the connected source cells.
    pooled_errors: list[float] = []
    for target in targets:
        entry = summary[target["position"]]
        static_row = next(
            row for row in audit["static_paths"]["eye"]["targets"]
            if int(row["engine_index"]) == int(entry["engine_index"])
        )
        weight_sum = float(static_row["effective_weight_sum_mV"])
        for name in ("ambient", "stripe"):
            for row in target[name]:
                if not row["connected_source_cells"]:
                    continue
                pooled_rate = row["connected_source_spikes"] / (
                    row["connected_source_cells"] * MEASURE_S
                )
                pooled = V0_MV + weight_sum * pooled_rate * TAU_S
                pooled_errors.append(row["sampled_mean_v_mV"] - pooled)
    pooled_array = np.asarray(pooled_errors, dtype=np.float64)
    return {
        "method": "reconstructed_mean_v = lif.v_0 + source_event_sum / measure_s * lif.tau; "
                  "source_event_sum is sum_i w_ij * n_i, the connection-weighted drive, "
                  "not the pooled R1-6 population rate",
        "tau_s": TAU_S,
        "v0_mV": V0_MV,
        "measure_s": MEASURE_S,
        "rows": int(len(residual_array)),
        "residual_mean_mV": float(residual_array.mean()),
        "residual_std_mV": float(residual_array.std()),
        "residual_min_mV": float(residual_array.min()),
        "residual_max_mV": float(residual_array.max()),
        "pooled_substitution_residual_mean_mV": float(pooled_array.mean()),
        "pooled_substitution_residual_std_mV": float(pooled_array.std()),
        "pooled_substitution_residual_max_abs_mV": float(np.abs(pooled_array).max()),
        "targets": targets,
    }


def _weight_section(scale_inputs: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    """Check 2: reproduce every traced target's effective weight from the raw count."""
    raw = scale_inputs["raw"]
    effective = scale_inputs["effective"]
    pre = scale_inputs["pre"]
    post = scale_inputs["post"]
    registry = scale_inputs["registry"]
    source_idx = np.asarray(registry.population("R1_6").idx, dtype=np.int64)
    source_mask = np.isin(pre, source_idx)
    static_rows = {
        int(row["engine_index"]): row for row in audit["static_paths"]["eye"]["targets"]
    }
    worst_weight = 0.0
    worst_anatomy = 0.0
    checked = 0
    for index in audit["static_paths"]["eye"]["strongest_target_indices"]:
        rows = np.flatnonzero(source_mask & (post == int(index)))
        weight = float(effective[rows].sum())
        anatomy = float(np.abs(raw[rows]).sum())
        static = static_rows[int(index)]
        worst_weight = max(worst_weight, abs(weight - float(static["effective_weight_sum_mV"])))
        worst_anatomy = max(worst_anatomy, abs(anatomy - float(static["anatomical_synapses"])))
        checked += 1
    return {
        "checked_targets": checked,
        "source_population": "R1_6",
        "max_abs_effective_weight_difference_mV": worst_weight,
        "max_abs_anatomical_synapse_difference": worst_anatomy,
        "path": "effective = raw_count * lif.w_syn * scale_array(...); count once, "
                "w_syn once, transmitter multiplier once",
    }


def _reversal_section(audit: dict[str, Any], reconstruction: dict[str, Any]) -> dict[str, Any]:
    """Check 3: the fixed signed current against the conductance placeholders."""
    targets: list[dict[str, Any]] = []
    for target in reconstruction["targets"]:
        entries = target["ambient"] + target["stripe"]
        deepest = min(entries, key=lambda row: row["sampled_mean_v_mV"])
        drive = deepest["source_event_sum_mV"] / MEASURE_S * TAU_S
        conductance: dict[str, Any] = {}
        for e_cl in E_CL_MV:
            h_ss = (-drive) / (V0_MV - e_cl)
            v_cond = (V0_MV + h_ss * e_cl) / (1.0 + h_ss)
            conductance[f"{e_cl:.0f}"] = {
                "h_ss": float(h_ss),
                "v_conductance_mV": float(v_cond),
                "shift_from_current_mV": float(v_cond - deepest["sampled_mean_v_mV"]),
                "measured_min_mV": float(deepest["sampled_min_v_mV"]) if "sampled_min_v_mV" in deepest else None,
            }
        targets.append({
            "position": target["position"],
            "engine_index": target["engine_index"],
            "root_id": target["root_id"],
            "deepest_condition": deepest["condition"],
            "deepest_seed": int(deepest["seed"]),
            "drive_mV": float(drive),
            "sampled_mean_v_mV": float(deepest["sampled_mean_v_mV"]),
            "sampled_min_v_mV": float(deepest["sampled_min_v_mV"]),
            "conductance": conductance,
        })
    drives = np.array([target["drive_mV"] for target in targets])
    means = np.array([target["sampled_mean_v_mV"] for target in targets])
    deepest = min(targets, key=lambda target: target["sampled_mean_v_mV"])
    return {
        "method": "steady state at the dark fixed point. Current-based: v = v_0 + sum_i w_ij r_i tau. "
                  "Conductance-based (SPEC-P2 3c): h_ss = |drive| / (v_0 - E), "
                  "v = (v_0 + h_ss E) / (1 + h_ss); inhibitory events route to h, and v cannot pass E.",
        "reversals_mV": list(E_CL_MV),
        "drive_range_mV": [float(drives.min()), float(drives.max())],
        "measured_mean_v_range_mV": [float(means.min()), float(means.max())],
        "deepest_target": deepest,
        "targets": targets,
        "note": "E values are the project's conductance placeholders (item 31), not a measured "
                "chloride reversal; any of them bounds how negative the model can drive a target.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    from flyonenomics.io import read_json

    audit = read_json(AUDITED_RECORD)
    scale_inputs = _load_scale_inputs()
    reconstruction = _reconstruction_section(audit)
    record = {
        "class": "development",
        "purpose": "reconciliation audit of the signal-transfer voltage probe; no engine run",
        "audited_record": {
            "path": str(AUDITED_RECORD.relative_to(ROOT)),
            "sha256": _sha256(AUDITED_RECORD),
        },
        "identity": {
            "platform": f"{platform.system().lower()}-{platform.machine()}",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "runner_sha256": _sha256(Path(__file__)),
            "inputs_sha256": {
                "data/drive-v0.2.yaml": _sha256(DRIVE_PATH),
                "data/params-v0.2.yaml": _sha256(PARAMS_PATH),
                "data/dopamine-v0.2.yaml": _sha256(DOPAMINE_PATH),
            },
        },
        "check1_thresholds": {
            **_threshold_section(scale_inputs, audit),
            "tuBu_off": _gap_section(audit),
        },
        "check2_photoreceptor_reconstruction": {
            **reconstruction,
            "weight_application": _weight_section(scale_inputs, audit),
        },
        "check3_reversal": _reversal_section(audit, reconstruction),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(__import__("json").dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
