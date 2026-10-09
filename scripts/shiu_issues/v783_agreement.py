#!/usr/bin/env python3
"""Compare the existing BrianEngine v783 rebuild with upstream loaded by path.

Each implementation lives in its own process. No upstream model code is copied.
Outputs include all-neuron trial counts and exact, sorted integer-tick events.
Use a private writable work directory and single-threaded nice +10 execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

from issue11_sign import (
    build_network, common_parser, event_digest, interval, run_condition,
    setup, sha256, verify_reference, write_json,
)

CORE_FILES = (
    "src/flyonenomics/datasets.py", "src/flyonenomics/connectome_arrays.py",
    "src/flyonenomics/io.py", "src/flyonenomics/types.py",
    "src/flyonenomics/engine/__init__.py", "src/flyonenomics/engine/base.py",
    "src/flyonenomics/engine/models.py", "src/flyonenomics/engine/brian_engine.py",
    "data/params-v0.1.yaml",
)


def canonical_events(indices, ticks, width):
    events = np.asarray(indices, dtype=np.int64) * width + np.asarray(ticks, dtype=np.int64)
    events.sort()
    if events.size > 1 and np.any(events[1:] == events[:-1]):
        raise ValueError("duplicate neuron/tick events")
    return events


def correlation(a, b):
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def rates(a, b, readout, duration):
    ma, mb = a.mean(axis=0) / duration, b.mean(axis=0) / duration
    active = (ma > 0) | (mb > 0)
    return {
        "pearson_all_neuron_mean_rates": correlation(ma, mb),
        "pearson_union_active_mean_rates": correlation(ma[active], mb[active]),
        "union_active_neurons": int(active.sum()),
        "mean_rate_equal_neurons": int(np.count_nonzero(ma == mb)),
        "trial_count_equal_neuron_pairs": int(np.count_nonzero(a == b)),
        "total_neuron_trial_pairs": int(a.size),
        "max_absolute_mean_rate_difference_hz": float(np.max(np.abs(mb - ma))),
        "mean_absolute_mean_rate_difference_hz": float(np.mean(np.abs(mb - ma))),
        "mn9_upstream": interval(a[:, readout] / duration),
        "mn9_rebuild": interval(b[:, readout] / duration),
        "mn9_paired_rebuild_minus_upstream": interval((b[:, readout] - a[:, readout]) / duration),
    }


def child(args):
    started = time.monotonic()
    repo, model, b2, params, roots, root2i, exc, readout, meta = setup(args)
    width = int(round(meta["duration_s"] / meta["dt_s"])) + 1
    engine = None
    if args.implementation == "upstream":
        net, syn, mon = build_network(repo, model, b2, params, exc)
    else:
        sys.path.insert(0, str(args.fly_repo / "src"))
        from flyonenomics.datasets import get_dataset_adapter
        from flyonenomics.types import load_params
        from flyonenomics.engine import BrianEngine, InputTopology, UpstreamBank
        engine = BrianEngine()
        # Give this process its own Cython cache after importing the engine.
        b2.prefs.codegen.runtime.cython.cache_dir = str(args.work_dir / "cython-cache")
        engine.seed(args.seed_base)
        engine.build(get_dataset_adapter("783").connectome_files(),
                     load_params(args.fly_repo / "data/params-v0.1.yaml"),
                     InputTopology(upstream_banks=[UpstreamBank(
                         idx=np.asarray(exc, dtype=np.int32), rate_hz=meta["poisson_rate_hz"])]))
        assert np.array_equal(engine.root_ids, roots)
        assert engine.n_syn == 15091983
        assert engine.engine_model() == "lif" and engine.method() == "linear"
        meta["model_strings"] = engine.model_strings()
        meta["execution"] = "Existing BrianEngine, bare lif, upstream bank, public restore/seed/run_chunk/spikes"
    all_counts, trials = [], []
    for trial, seed in enumerate(meta["seeds"]):
        t0 = time.monotonic()
        if engine is None:
            indices, ticks, counts = run_condition(net, syn, mon, model, b2, params, seed, lambda s: None)
        else:
            engine.restore("initial")
            engine.compose_refractory()
            engine.seed(seed)
            counts = np.zeros(engine.n, dtype=np.int64)
            for _ in range(int(round(meta["duration_s"] * 1000 / args.chunk_ms))):
                counts += engine.run_chunk(args.chunk_ms).counts
            table = engine.spikes(0)
            indices, ticks = table.idx, table.tick
            assert np.array_equal(counts, np.bincount(indices, minlength=engine.n))
        events = canonical_events(indices, ticks, width)
        path = args.work_dir / f"events-{trial:03d}.npz"
        np.savez_compressed(path, events=events)
        all_counts.append(counts)
        trials.append({"seed": seed, "spikes": len(events), "event_sha256": event_digest(indices, ticks, width),
                       "archive_sha256": sha256(path)})
        print(f"{args.implementation} {args.stimulus_side} seed={seed} spikes={len(events)} MN9={counts[readout]} seconds={time.monotonic()-t0:.2f}", flush=True)
    archive = args.work_dir / "trial-counts.npz"
    np.savez_compressed(archive, roots=roots, counts=np.stack(all_counts), seeds=meta["seeds"])
    result = {"metadata": meta, "trials": trials, "counts_sha256": sha256(archive),
              "completed_utc": datetime.now(timezone.utc).isoformat(), "wall_s": time.monotonic() - started}
    if engine is None and args.verify_reference:
        result["fresh_run_trial_validation"] = verify_reference(args, trials[0]["event_sha256"])
    write_json(args.output, result)


def main():
    p = common_parser(__doc__)
    p.add_argument("--fly-repo", type=Path, required=True)
    p.add_argument("--implementation", choices=("upstream", "rebuild"), help="Internal subprocess mode")
    p.add_argument("--chunk-ms", type=float, default=1000.0,
                   help="Public engine stepping duration; 1000 avoids repeated Brian2 preparation overhead")
    p.add_argument("--historical-counts", type=Path, help="Optional earlier Brian2 2.5.1 issue11 count archive")
    p.add_argument("--historical-results", type=Path, help="Optional assembled issue results with fresh-reference hashes")
    args = p.parse_args()
    for name in ("fly_repo", "shiu_repo", "work_dir", "output", "annotations_v1", "annotations_v2", "historical_counts", "historical_results"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())
    if not np.isfinite(args.chunk_ms) or args.chunk_ms <= 0 or args.chunk_ms % 1 or abs(1000 / args.chunk_ms - round(1000 / args.chunk_ms)) > 1e-9:
        p.error("chunk-ms must be a positive integer dividing 1000")
    # The connectome loader creates a child interpreter on a cache miss.
    source = str(args.fly_repo / "src")
    os.environ["PYTHONPATH"] = source + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")
    # Keep arrays, snapshots, bytecode and Cython outputs out of the shared checkout.
    os.environ["FLYONENOMICS_CACHE_DIR"] = str(args.work_dir / "fly-cache") if args.implementation is None else str(args.work_dir.parent / "fly-cache")
    cache = Path(os.environ["FLYONENOMICS_CACHE_DIR"])
    for path in (args.work_dir, args.output, cache):
        if path == args.shiu_repo or args.shiu_repo in path.parents:
            p.error("outputs and caches must be outside the upstream checkout")
    cache.mkdir(parents=True, exist_ok=True)
    link = cache / "Drosophila_brain_model"
    if not link.exists():
        link.symlink_to(args.shiu_repo, target_is_directory=True)
    if link.resolve() != args.shiu_repo:
        p.error("private cache points to the wrong upstream checkout")
    if args.implementation:
        child(args)
        return
    started = time.monotonic()
    changed = subprocess.check_output(["git", "-C", str(args.fly_repo), "diff", "HEAD", "--", *CORE_FILES], text=True)
    if changed:
        raise ValueError("Flyonenomics core differs from its recorded commit")
    metadata = {
        "fly_commit": subprocess.check_output(["git", "-C", str(args.fly_repo), "rev-parse", "HEAD"], text=True).strip(),
        "fly_core_sha256": {f: sha256(args.fly_repo / f) for f in CORE_FILES},
        "comparison_script_sha256": sha256(Path(__file__)),
        "helper_sha256": sha256(Path(__file__).with_name("issue11_sign.py")),
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": {n: importlib.metadata.version(n) for n in (
            "brian2", "numpy", "pandas", "scipy", "cython", "pyarrow", "pydantic", "pyyaml", "joblib", "sympy", "setuptools")},
        "chunk_ms": args.chunk_ms, "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    for implementation in ("upstream", "rebuild"):
        work = args.work_dir / implementation
        command = [sys.executable, str(Path(__file__).resolve()), "--implementation", implementation,
                   "--fly-repo", str(args.fly_repo), "--shiu-repo", str(args.shiu_repo),
                   "--annotations-v1", str(args.annotations_v1), "--annotations-v2", str(args.annotations_v2),
                   "--work-dir", str(work), "--output", str(work / "result.json"),
                   "--stimulus-side", args.stimulus_side, "--seed-base", str(args.seed_base),
                   "--chunk-ms", str(args.chunk_ms)]
        if args.trials is not None:
            command.extend(["--trials", str(args.trials)])
        if args.verify_reference and implementation == "upstream":
            command.append("--verify-reference")
        subprocess.run(command, check=True, timeout=3000)
    u = json.loads((args.work_dir / "upstream/result.json").read_text())
    r = json.loads((args.work_dir / "rebuild/result.json").read_text())
    with np.load(args.work_dir / "upstream/trial-counts.npz") as f:
        roots, a, seeds = f["roots"], f["counts"], f["seeds"]
    with np.load(args.work_dir / "rebuild/trial-counts.npz") as f:
        assert np.array_equal(roots, f["roots"]) and np.array_equal(seeds, f["seeds"])
        b = f["counts"]
    readout = int(np.flatnonzero(roots == u["metadata"]["readout_root"])[0])
    duration = u["metadata"]["duration_s"]
    comparisons = []
    for trial, seed in enumerate(seeds):
        with np.load(args.work_dir / f"upstream/events-{trial:03d}.npz") as f:
            ea = f["events"]
        with np.load(args.work_dir / f"rebuild/events-{trial:03d}.npz") as f:
            eb = f["events"]
        missing, extra = np.setdiff1d(ea, eb, assume_unique=True), np.setdiff1d(eb, ea, assume_unique=True)
        width = int(round(duration / u["metadata"]["dt_s"])) + 1
        changed_neurons = np.unique(np.concatenate((missing, extra)) // width)
        comparisons.append({"seed": int(seed), "exact_events": bool(np.array_equal(ea, eb)),
                            "upstream_spikes": len(ea), "rebuild_spikes": len(eb),
                            "missing_events": len(missing), "extra_events": len(extra),
                            "identical_neuron_trains": len(roots) - len(changed_neurons)})
    result = {"schema_version": 1, "metadata": metadata, "upstream": u, "rebuild": r,
              "rate_agreement": rates(a, b, readout, duration), "event_comparisons": comparisons,
              "all_trials_exact": all(c["exact_events"] for c in comparisons),
              "identical_neuron_trial_trains": sum(c["identical_neuron_trains"] for c in comparisons),
              "total_upstream_spikes": sum(c["upstream_spikes"] for c in comparisons),
              "total_rebuild_spikes": sum(c["rebuild_spikes"] for c in comparisons),
              "missing_events": sum(c["missing_events"] for c in comparisons),
              "extra_events": sum(c["extra_events"] for c in comparisons)}
    if args.historical_counts:
        with np.load(args.historical_counts) as f:
            assert np.array_equal(roots, f["roots"]) and np.array_equal(seeds, f["seeds"])
            result["historical_brian251_vs_modern_upstream"] = rates(f["original"], a, readout, duration)
        result["historical_counts_sha256"] = sha256(args.historical_counts)
    if args.historical_results:
        history = json.loads(args.historical_results.read_text())
        key = "issue11_notebook" if args.stimulus_side == "notebook" else "issue11_right_lb3"
        old = history["reference_validation"][key]
        result["historical_first_seed_event_agreement"] = {
            "historical": old, "modern_upstream_event_sha256": u["trials"][0]["event_sha256"],
            "exact_events": old["event_sha256"] == u["trials"][0]["event_sha256"]}
        result["historical_results_sha256"] = sha256(args.historical_results)
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    result["wall_s"] = time.monotonic() - started
    write_json(args.output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("upstream", "rebuild", "metadata")}, indent=2))


if __name__ == "__main__":
    main()
