#!/usr/bin/env python3
"""Audit the rebuild's cached weight arithmetic without running a simulation."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

from issue11_sign import PINNED_SHIU_COMMIT, load_module, sha256, write_json


def digest(values):
    return hashlib.sha256(np.asarray(values, dtype="<f8").tobytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fly-repo", type=Path, required=True)
    p.add_argument("--shiu-repo", type=Path, required=True)
    p.add_argument("--cache-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    repo, cache, output = args.shiu_repo.resolve(), args.cache_dir.resolve(), args.output.resolve()
    for path in (cache, output):
        if path == repo or repo in path.parents:
            p.error("outputs must be outside upstream")
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if commit != PINNED_SHIU_COMMIT:
        p.error("wrong upstream commit")
    if subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True):
        p.error("upstream tracked modifications")
    os.environ["FLYONENOMICS_CACHE_DIR"] = str(cache)
    source = str(args.fly_repo.resolve() / "src")
    sys.path.insert(0, source)
    os.environ["PYTHONPATH"] = source + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    from brian2 import mV
    from flyonenomics.connectome_arrays import load_connectome_arrays, base_weight_memmap
    model = load_module("weight_audit_shiu", repo / "model.py")
    comp, con = repo / "Completeness_783.csv", repo / "Connectivity_783.parquet"
    roots, i, j, raw = load_connectome_arrays(comp, con)
    w_syn = model.default_params["w_syn"]
    # Upstream multiplies directly in SI units. The rebuild caches in mV first.
    upstream = np.asarray(raw) * float(w_syn)
    rebuilt = np.asarray(base_weight_memmap(raw, float(w_syn / mV), comp, con)) * float(mV)
    error = np.abs(rebuilt - upstream)
    different = rebuilt.view(np.uint64) != upstream.view(np.uint64)
    result = {
        "shiu_commit": commit, "script_sha256": sha256(Path(__file__)),
        "connectivity_sha256": sha256(con), "neurons": len(roots), "connection_rows": len(raw),
        "bitwise_equal_weight_rows": int((~different).sum()),
        "bitwise_different_weight_rows": int(different.sum()),
        "maximum_absolute_difference_volts": float(error.max()),
        "maximum_relative_difference": float(np.max(error / np.abs(upstream))),
        "weight_sign_changes": int(np.count_nonzero(np.signbit(upstream) != np.signbit(rebuilt))),
        "upstream_si_weight_sha256": digest(upstream), "rebuild_si_weight_sha256": digest(rebuilt),
        "explanation": "upstream raw * w_syn_in_volts; rebuild (raw * w_syn_in_mV) * mV_in_volts; both float64",
    }
    write_json(output, result)
    print(result)


if __name__ == "__main__":
    main()
