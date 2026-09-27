"""Reduce the 192-brain-second optic-lobe diagnostic to a committed evidence record."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np

from flyonenomics.diagnostics.visual_path import read_json, write_json
from flyonenomics.io import hash_file, load_npy

ARMS = ("declared", "optic-1mV", "optic-2mV", "connection-sign")


def summarize(source: Path, destination: Path) -> None:
    records = {}
    source_identity = None
    for arm in ARMS:
        audit = read_json(source / f"{arm}-structure.json")
        measurements = read_json(source / f"{arm}.json")
        assert measurements["brain_seconds"] == 48
        assert len(measurements["rows"]) == 12
        assert measurements["identity"] == audit["identity"]
        identity = dict(audit["identity"])
        common = {name: identity.pop(name) for name in
                  ("source_commit", "source_sha256", "runner_sha256", "inputs_sha256", "connectome_sha256", "platform", "engine")}
        if source_identity is None:
            source_identity = common
        assert common == source_identity
        inventory = audit["inventory"]
        subsets = inventory.pop("subsets")
        subset_info = {}
        for name, idx in subsets.items():
            array = np.asarray(idx, dtype=np.int32)
            subset_info[name] = {"n": len(idx), "engine_indices_sha256": hashlib.sha256(array.tobytes()).hexdigest()}
        for info in inventory.values():
            idx = np.asarray(info.pop("indices"), dtype=np.int32)
            roots = np.asarray(info.pop("root_ids"), dtype=np.int64)
            info["engine_indices_sha256"] = hashlib.sha256(idx.tobytes()).hexdigest()
            info["root_ids_sha256"] = hashlib.sha256(roots.tobytes()).hexdigest()
        with load_npy(source / f"{arm}-counts.npz") as counts:
            for row in measurements["rows"]:
                full = counts[f"{arm}-{row['seed']}-{row['condition']}"]
                for name, result in row["populations"].items():
                    if result["n"]:
                        total = int(full[np.asarray(subsets[name], dtype=int)].sum())
                        assert total == result["spikes"]
                        assert total / (result["n"] * 2) == result["rate_hz"]
        mean_rates = {}
        paired = []
        for name in subsets:
            if not len(subsets[name]):
                continue
            mean_rates[name] = {
                condition: float(np.mean([row["populations"][name]["rate_hz"]
                    for row in measurements["rows"] if row["condition"] == condition]))
                for condition in ("ambient", "stripe-left", "stripe-right", "dark")}
        for seed in (1, 2, 3):
            rows = {row["condition"]: row for row in measurements["rows"] if row["seed"] == seed}
            for side in ("left", "right"):
                differences = {name: rows[f"stripe-{side}"]["populations"][name]["rate_hz"]
                               - rows["ambient"]["populations"][name]["rate_hz"]
                               for name in mean_rates}
                paired.append({"seed": seed, "stripe_side": side, "delta_hz": differences})
        records[arm] = {"identity": identity, "inventory": inventory, "subsets": subset_info,
                        "connections": audit["connections"], "model_strings": audit["model_strings"],
                        "parameters": audit["parameters"], "rows": measurements["rows"],
                        "three_seed_mean_hz": mean_rates, "paired_stripe_minus_ambient": paired,
                        "brain_seconds": measurements["brain_seconds"], "wall_seconds": measurements["wall_seconds"]}
    write_json(destination, {
        "class": "development", "purpose": "causal diagnostic, not a qualification or calibration",
        "source_identity": source_identity,
        "protocol": {"master_seed": 20260912, "seeds": [1, 2, 3], "input_light_hz": 150.0,
                     "stripe_width_deg": 5.0, "stripe_azimuths_deg": [-45.0, 45.0],
                     "settle_s": 2.0, "record_s": 2.0, "conditions_reset_independently": True,
                     "live_dopamine_pools": True, "voltage_sample_interval_ms": 10.0,
                     "brain_seconds": 192, "workers": 4},
        "raw_directory": str(source),
        "raw_sha256": {p.name: hash_file(p) for p in sorted(source.iterdir()) if p.is_file()},
        "arms": records,
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source", type=Path, default=Path("camber-runs/diag/optic-lobe"))
    parser.add_argument("--out", type=Path, default=Path("validation/records/p2/optic-lobe-silence.json"))
    args = parser.parse_args()
    summarize(args.source, args.out)
