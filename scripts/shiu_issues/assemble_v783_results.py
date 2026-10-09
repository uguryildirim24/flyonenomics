#!/usr/bin/env python3
"""Package completed v783 comparisons and generated counts, without source data."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from issue11_sign import sha256, write_json


def load_counts(path, expected_sha=None):
    if expected_sha is not None and sha256(path) != expected_sha:
        raise ValueError(f"archive checksum mismatch: {path}")
    with np.load(path) as f:
        return {k: f[k] for k in f.files}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work-dir", type=Path, required=True)
    p.add_argument("--historical-notebook", type=Path, required=True)
    p.add_argument("--historical-right", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--chunk10-script-sha256", help="Execution provenance for optional chunk10-notebook events")
    args = p.parse_args()
    work, out = args.work_dir.resolve(), args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "assembled_utc": datetime.now(timezone.utc).isoformat(),
              "assembler_sha256": sha256(Path(__file__)), "comparisons": {}}
    arrays = {}
    for side, historical in (("notebook", args.historical_notebook), ("right", args.historical_right)):
        result = json.loads((work / f"{side}.json").read_text())
        report["comparisons"][side] = result
        for implementation in ("upstream", "rebuild"):
            path = work / side / implementation / "trial-counts.npz"
            data = load_counts(path, result[implementation]["counts_sha256"])
            if "roots" not in arrays:
                arrays["roots"], arrays["seeds"] = data["roots"], data["seeds"]
            assert np.array_equal(arrays["roots"], data["roots"])
            assert np.array_equal(arrays["seeds"], data["seeds"])
            arrays[f"{side}_{implementation}"] = data["counts"]
        data = load_counts(historical, result["historical_counts_sha256"])
        assert np.array_equal(arrays["roots"], data["roots"])
        assert np.array_equal(arrays["seeds"], data["seeds"])
        arrays[f"{side}_legacy"] = data["original"]
    report["weight_audit"] = json.loads((work / "weight-audit.json").read_text())
    supplement = []
    for trial in (0, 1):
        path = work / "chunk10-notebook" / f"events-{trial:03d}.npz"
        if not path.is_file():
            continue
        if not args.chunk10_script_sha256:
            p.error("supply --chunk10-script-sha256 for supplementary event files")
        with np.load(path) as f:
            events = f["events"]
        with np.load(work / "notebook/upstream" / f"events-{trial:03d}.npz") as f:
            reference = f["events"]
        seed = int(arrays["seeds"][trial])
        arrays[f"notebook_chunk10_events_seed_{seed}"] = events
        supplement.append({"seed": seed, "chunk_ms": 10, "duration_s": 1,
                           "spikes": len(events), "exact_events": bool(np.array_equal(events, reference)),
                           "archive_sha256": sha256(path),
                           "event_sha256": hashlib.sha256(events.astype("<i8").tobytes()).hexdigest()})
    report["supplementary_chunk10_notebook"] = {
        "comparison_script_sha256_at_execution": args.chunk10_script_sha256,
        "note": "Supplementary 10 ms chunks, separate from full 30-trial comparisons; reproduce with --chunk-ms 10 --trials 2.",
        "trials": supplement,
    }
    # Keep IDs and tick encodings int64; counts are losslessly int32.
    for name, array in arrays.items():
        if name.endswith(("_upstream", "_rebuild", "_legacy")):
            assert array.min() >= 0 and array.max() <= np.iinfo(np.int32).max
            arrays[name] = array.astype(np.int32)
    archive = out / "v783-agreement-counts.npz"
    np.savez_compressed(archive, **arrays)
    report["packaged_counts_archive"] = {"file": archive.name, "sha256": sha256(archive),
                                         "fields": list(arrays)}
    starts = [datetime.fromisoformat(r["metadata"]["started_utc"]) for r in report["comparisons"].values()]
    ends = [datetime.fromisoformat(r["completed_utc"]) for r in report["comparisons"].values()]
    report["resources"] = {"nice": 10, "max_simulation_processes": 2,
                            "numerical_library_threads": 1,
                            "final_comparisons_elapsed_s": (max(ends) - min(starts)).total_seconds()}
    write_json(out / "v783_agreement_results.json", report)


if __name__ == "__main__":
    main()
