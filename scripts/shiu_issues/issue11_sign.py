#!/usr/bin/env python3
"""Audit v783 transmitter signs and run a paired, default sugarR experiment.

Imports the user's Shiu checkout. No upstream model code is vendored here.
Shared experiment helpers are imported by issue10_silencing.py.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gc
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import t as student_t

PINNED_SHIU_COMMIT = "91bdd1e7dcf193f3e7ca5a8933497fcef63b7960"
IL3LN6_LEFT = 720575940632403986
sys.dont_write_bytecode = True  # never create __pycache__ in the shared checkout


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def common_parser(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--shiu-repo", type=Path, required=True)
    p.add_argument("--work-dir", type=Path, required=True,
                   help="Private writable directory, not the Shiu checkout")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--annotations-v1", type=Path, required=True)
    p.add_argument("--annotations-v2", type=Path, required=True)
    p.add_argument("--stimulus-side", choices=("notebook", "right"), default="notebook",
                   help="notebook: its 21 GRNs, remapped to v783; right: all v2 right LB3 GRNs")
    p.add_argument("--seed-base", type=int, default=783000)
    p.add_argument("--trials", type=int, help="Default: upstream n_run (30)")
    p.add_argument("--verify-reference", action="store_true",
                   help="Also compare the first original trial to a fresh upstream run_trial subprocess")
    return p


def setup(args):
    repo = args.shiu_repo.resolve()
    work = args.work_dir.resolve()
    args.shiu_repo, args.work_dir = repo, work
    args.annotations_v1 = args.annotations_v1.resolve()
    args.annotations_v2 = args.annotations_v2.resolve()
    if work == repo or repo in work.parents:
        raise ValueError("work-dir must be outside the Shiu checkout")
    args.output = args.output.resolve()
    if args.output == repo or repo in args.output.parents:
        raise ValueError("output must be outside the Shiu checkout")
    work.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if commit != PINNED_SHIU_COMMIT:
        raise ValueError(f"Expected Shiu {PINNED_SHIU_COMMIT}, got {commit}")
    # Also reject modified tracked inputs/code, even if HEAD is correct.
    tracked_changes = subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"],
        text=True)
    if tracked_changes:
        raise ValueError(f"Shiu checkout has tracked modifications: {tracked_changes}")
    os.chdir(work)
    import brian2 as b2
    b2.start_scope()
    b2.prefs.codegen.target = "cython"
    b2.prefs.codegen.runtime.cython.cache_dir = str(work / "cython-cache")
    model = load_module("shiu_issue_model", repo / "model.py")
    params = model.default_params.copy()
    trials = args.trials if args.trials is not None else int(params["n_run"])
    if trials < 2:
        raise ValueError("At least two trials are required for intervals")
    params["n_run"] = trials
    # Parse only these literal assignments from the notebook; do not execute it.
    import ast
    notebook = json.loads((repo / "example.ipynb").read_text())
    values = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        if "neu_sugar =" not in source and "id_mn9 =" not in source:
            continue
        for node in ast.parse(source).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ("neu_sugar", "id_mn9"):
                        values[target.id] = ast.literal_eval(node.value)
    comp_path = repo / "Completeness_783.csv"
    con_path = repo / "Connectivity_783.parquet"
    comp = pd.read_csv(comp_path, index_col=0)
    roots = comp.index.to_numpy(dtype=np.int64)
    root2i = {int(root): i for i, root in enumerate(roots)}
    a1 = pd.read_csv(args.annotations_v1, sep="\t", low_memory=False)
    a2 = pd.read_csv(args.annotations_v2, sep="\t", low_memory=False)
    assert a2.root_id.is_unique and a2.supervoxel_id.is_unique
    old_by_root = a1.drop_duplicates("root_id").set_index("root_id")
    new_by_sv = a2.set_index("supervoxel_id")
    remaps = []
    sugar = []
    for root in values["neu_sugar"]:
        if root in root2i:
            sugar.append(root)
        else:
            sv = int(old_by_root.loc[root, "supervoxel_id"])
            new = int(new_by_sv.loc[sv, "root_id"])
            assert new in root2i
            remaps.append({"notebook_root": root, "v783_root": new, "supervoxel_id": sv})
            sugar.append(new)
    if args.stimulus_side == "right":
        sugar = sorted(int(r) for r in a2.loc[(a2.cell_type == "LB3") & (a2.side == "right"), "root_id"])
        assert sugar and all(r in root2i for r in sugar)
    assert len(sugar) == len(set(sugar))
    stimulus_annotation = a2[a2.root_id.isin(sugar)]
    exc = [root2i[root] for root in sugar]
    readout = root2i[values["id_mn9"]]
    meta = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "shiu_commit": commit, "shiu_tracked_changes": tracked_changes,
        "shiu_repo": str(repo), "host": platform.node(),
        "python": platform.python_version(),
        "packages": {n: importlib.metadata.version(n) for n in
                     ("brian2", "numpy", "pandas", "scipy", "cython", "pyarrow", "joblib", "sympy")},
        "input_sha256": {f: sha256(repo / f) for f in
                         ("model.py", "utils.py", "example.ipynb", "Readme.md",
                          "Completeness_783.csv", "Connectivity_783.parquet")},
        "experiment": ("example.ipynb first sugarR activation on v783" if args.stimulus_side == "notebook"
                       else "additional issue11 right-side activation: all right LB3 GRNs from v2.1.0"),
        "stimulus_side_option": args.stimulus_side,
        "notebook_stimulated_roots": values["neu_sugar"],
        "notebook_root_remaps": remaps,
        "stimulated_roots": sugar,
        "stimulated_annotation_sides": stimulus_annotation.side.value_counts().to_dict(),
        "stimulated_annotation_types": stimulus_annotation.cell_type.value_counts().to_dict(),
        "annotation_sha256": {"v1.1.0": sha256(args.annotations_v1), "v2.1.0": sha256(args.annotations_v2)},
        "readout_root": values["id_mn9"],
        "neurons": len(roots), "trials": trials,
        "duration_s": float(params["t_run"] / b2.second),
        "poisson_rate_hz": float(params["r_poi"] / b2.Hz),
        "dt_s": float(b2.defaultclock.dt / b2.second),
        "seeds": list(range(args.seed_base, args.seed_base + trials)),
        "seed_note": "Upstream specifies no seeds. These explicitly chosen seeds are paired across conditions.",
        "execution": "Upstream create_model/poi/silence with Brian2 runtime Cython; restore initial state before each trial",
    }
    return repo, model, b2, params, roots, root2i, exc, readout, meta


def build_network(repo, model, b2, params, exc):
    print("Building upstream network", flush=True)
    neu, syn, mon = model.create_model(repo / "Completeness_783.csv",
                                      repo / "Connectivity_783.parquet", params)
    pois, neu = model.poi(neu, exc, [], params)
    net = b2.Network(neu, syn, mon, *pois)
    # Compile once and initialise delay queues before taking the empty snapshot.
    net.run(0 * b2.ms)
    net.store("initial")
    return net, syn, mon


def run_condition(net, syn, mon, model, b2, params, seed, patch):
    net.restore("initial", restore_random_state=False)
    patch(syn)
    b2.seed(seed)
    net.run(params["t_run"])
    # Copies are important: restore() will reset the monitor on the next run.
    indices = np.asarray(mon.i[:], dtype=np.int64).copy()
    ticks = np.rint(np.asarray(mon.t[:] / b2.second) /
                    float(b2.defaultclock.dt / b2.second)).astype(np.int64)
    counts = np.asarray(mon.count[:], dtype=np.int64).copy()
    return indices, ticks, counts


def event_digest(indices, ticks, ticks_per_trial):
    events = np.asarray(indices, dtype=np.int64) * ticks_per_trial + np.asarray(ticks, dtype=np.int64)
    events.sort()
    return hashlib.sha256(events.astype("<i8").tobytes()).hexdigest()


def verify_reference(args, expected, silence_roots=()):
    output = args.work_dir.resolve() / "fresh-upstream-reference.json"
    command = [sys.executable, str(Path(__file__).resolve()), "--reference-only",
               "--shiu-repo", str(args.shiu_repo.resolve()),
               "--annotations-v1", str(args.annotations_v1.resolve()),
               "--annotations-v2", str(args.annotations_v2.resolve()),
               "--stimulus-side", args.stimulus_side, "--seed-base", str(args.seed_base),
               "--work-dir", str(args.work_dir.resolve()), "--output", str(output)]
    for root in silence_roots:
        command.extend(["--reference-silence-root", str(root)])
    subprocess.run(command, check=True)
    reference = json.loads(output.read_text())
    reference["snapshot_trial_event_sha256"] = expected
    reference["identical_exact_spike_events"] = reference["event_sha256"] == expected
    if not reference["identical_exact_spike_events"]:
        raise AssertionError("Snapshot-based trial differs from fresh upstream run_trial")
    return reference


def interval(samples):
    x = np.asarray(samples, dtype=float)
    mean = float(x.mean())
    half = float(student_t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))
    return {"mean_hz": mean, "ci95_hz": [mean - half, mean + half],
            "trial_rates_hz": x.tolist()}


def summarize_rates(original, corrected, roots, readout, duration):
    a, b = original / duration, corrected / duration
    d = b - a
    mean = d.mean(axis=0)
    half = student_t.ppf(.975, len(d) - 1) * d.std(axis=0, ddof=1) / np.sqrt(len(d))
    # Descriptive threshold, not a multiple-testing significance claim.
    meaningful = np.abs(mean) >= 1.0
    excluded = (mean - half > 0) | (mean + half < 0)
    top = np.argsort(-np.abs(mean))
    top = top[mean[top] != 0][:20]
    return {
        "readout": {"original": interval(a[:, readout]),
                    "corrected": interval(b[:, readout]),
                    "paired_change_corrected_minus_original": interval(d[:, readout])},
        "active_in_any_trial": {"original": int((original.sum(axis=0) > 0).sum()),
                                "corrected": int((corrected.sum(axis=0) > 0).sum())},
        "mean_active_neurons_per_trial": {"original": float((original > 0).sum(axis=1).mean()),
                                          "corrected": float((corrected > 0).sum(axis=1).mean())},
        "any_mean_rate_change_neurons": int((mean != 0).sum()),
        "meaningful_definition": "absolute paired mean rate change >= 1 Hz; all neurons, no significance claim",
        "meaningful_neurons": int(meaningful.sum()),
        "meaningful_and_pointwise_ci_excludes_zero_neurons": int((meaningful & excluded).sum()),
        "interval_method": f"Two-sided Student t 95% CI over {len(d)} independent seed trials (paired for differences); pointwise, no multiplicity correction; model noise, not biological replicates",
        "largest_changes": [{"root_id": int(roots[i]), "original_hz": float(a[:, i].mean()),
                             "corrected_hz": float(b[:, i].mean()), "change_hz": float(mean[i]),
                             "paired_ci95_hz": [float(mean[i] - half[i]), float(mean[i] + half[i])]}
                            for i in top],
    }


def audit_signs(repo, annotation_paths, roots):
    print("Auditing connectivity and annotations", flush=True)
    con = pd.read_parquet(repo / "Connectivity_783.parquet")
    # Ensure upstream's index addressing really is this v783 completeness order.
    for role in ("Presynaptic", "Postsynaptic"):
        idx = con[f"{role}_Index"].to_numpy()
        assert np.array_equal(roots[idx], con[f"{role}_ID"].to_numpy())
    assert np.array_equal(con["Excitatory x Connectivity"].to_numpy(),
                          con["Excitatory"].to_numpy() * con["Connectivity"].to_numpy())
    assert (con.Connectivity > 0).all()
    summary = con.groupby("Presynaptic_ID", sort=False).agg(
        outgoing_rows=("Connectivity", "size"), outgoing_synapses=("Connectivity", "sum"),
        sign_min=("Excitatory", "min"), sign_max=("Excitatory", "max"))
    exc = con[con.Excitatory == 1].groupby("Presynaptic_ID").agg(
        excitatory_rows=("Connectivity", "size"), excitatory_synapses=("Connectivity", "sum"))
    summary = summary.join(exc).fillna({"excitatory_rows": 0, "excitatory_synapses": 0}).astype(np.int64)
    annotations = {name: pd.read_csv(path, sep="\t", low_memory=False)
                   for name, path in annotation_paths.items()}
    a2 = annotations["v2.1.0"]
    id_by_sv = a2.set_index("supervoxel_id")["root_id"]
    report = {"connection_rows": len(con), "total_synapses": int(con.Connectivity.sum()),
              "presynaptic_neurons_with_outgoing": len(summary),
              "mixed_sign_neurons": int((summary.sign_min != summary.sign_max).sum()),
              "weighted_column_equals_sign_times_connectivity": True,
              "completeness_index_mapping_verified": True,
              "annotation_files": {k: {"path": str(v.resolve()), "sha256": sha256(v)}
                                   for k, v in annotation_paths.items()},
              "annotations": {}}
    fields = ["supervoxel_id", "root_id", "cell_type", "hemibrain_type", "cell_class",
              "side", "top_nt", "top_nt_conf", "known_nt", "known_nt_source"]
    for version, ann in annotations.items():
        annotation_rows = len(ann)
        # v1 has 49 repeated roots. Count neurons, not annotation rows; repeated
        # roots have consistent predicted transmitters and confidences.
        assert (ann.groupby("root_id")[["top_nt", "top_nt_conf"]].nunique() <= 1).all().all()
        ann = ann.drop_duplicates("root_id")
        selected = ann[(ann.cell_type == "il3LN6") | (ann.hemibrain_type == "il3LN6")]
        cells = []
        for _, row in selected.iterrows():
            cell = {f: (None if pd.isna(row[f]) else row[f].item()
                        if isinstance(row[f], np.generic) else row[f])
                    for f in fields if f in row.index}
            root = int(row.root_id)
            # v1 roots precede v783. Match across versions by stable supervoxel,
            # not by guessing that an old root ID is a v783 root.
            v783 = int(id_by_sv.loc[row.supervoxel_id])
            cell["v783_root_via_same_supervoxel"] = v783
            cell["direct_root_in_completeness_783"] = root in set(roots)
            cell["direct_root_outgoing"] = ({k: int(v) for k, v in summary.loc[root].items()}
                                             if root in summary.index else None)
            cell["v783_outgoing"] = {k: int(v) for k, v in summary.loc[v783].items()}
            cell["v783_unique_postsynaptic_neurons"] = int(con.loc[
                con.Presynaptic_ID == v783, "Postsynaptic_ID"].nunique())
            cells.append(cell)
        joined = ann.merge(summary, left_on="root_id", right_index=True, how="inner")
        gaba = joined[joined.top_nt.str.lower() == "gaba"]
        discordant = gaba[gaba.excitatory_rows > 0]
        cutoffs = {}
        for cutoff in (0, .5, .7, .9):
            g = gaba[gaba.top_nt_conf >= cutoff]
            e = g[g.excitatory_rows > 0]
            cutoffs[str(cutoff)] = {"predicted_gaba_with_outgoing": len(g),
                                   "signed_excitatory_neurons": len(e),
                                   "excitatory_synapses": int(e.excitatory_synapses.sum())}
        item = {"il3LN6": cells, "annotation_rows": annotation_rows,
                "unique_annotation_roots": len(ann),
                "duplicate_root_rows_removed": annotation_rows - len(ann),
                "root_ids_matched_to_v783_outgoing": len(joined),
                "predicted_gaba_confidence_cutoffs": cutoffs,
                "other_predicted_gaba_signed_excitatory_excluding_all_il3LN6":
                    int((~discordant.root_id.isin([int(c["root_id"]) for c in cells])).sum()),
                "top_discordant_types": discordant.assign(
                    type_label=discordant.cell_type.fillna(discordant.hemibrain_type).fillna("untyped")
                ).groupby("type_label").size().sort_values(ascending=False).head(15).to_dict()}
        if "known_nt" in joined:
            known_gaba = joined[joined.known_nt.str.lower() == "gaba"]
            item["known_nt_exact_gaba_with_outgoing"] = len(known_gaba)
            item["known_nt_exact_gaba_signed_excitatory"] = int((known_gaba.excitatory_rows > 0).sum())
            item["known_nt_exact_gaba_excitatory_synapses"] = int(known_gaba.excitatory_synapses.sum())
            tokens = joined.known_nt.fillna("").str.lower().map(
                lambda s: {part.strip() for part in s.split(",")})
            known_gaba_inclusive = joined[tokens.map(lambda ts: "gaba" in ts)]
            known_inhibitory = joined[tokens.map(lambda ts: bool(ts & {"gaba", "glutamate"}))]
            item["known_nt_contains_gaba_with_outgoing"] = len(known_gaba_inclusive)
            item["known_nt_contains_gaba_signed_excitatory"] = int((known_gaba_inclusive.excitatory_rows > 0).sum())
            item["known_nt_contains_gaba_or_glutamate_signed_excitatory"] = int((known_inhibitory.excitatory_rows > 0).sum())
            item["known_nt_contains_gaba_or_glutamate_excitatory_synapses"] = int(known_inhibitory.excitatory_synapses.sum())
            item["known_nt_note"] = "Comma-separated token membership includes cotransmitters; a disagreement is not by itself proof that all these signs should be flipped."
        report["annotations"][version] = item
    del con
    gc.collect()
    return report


def main():
    p = common_parser(__doc__)
    p.add_argument("--reference-only", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--reference-silence-root", type=int, action="append", default=[], help=argparse.SUPPRESS)
    args = p.parse_args()
    args.shiu_repo = args.shiu_repo.resolve()
    args.work_dir = args.work_dir.resolve()
    started = time.monotonic()
    repo, model, b2, params, roots, root2i, exc, readout, meta = setup(args)
    if args.reference_only:
        b2.seed(args.seed_base)
        trains = model.run_trial(exc, [], [root2i[r] for r in args.reference_silence_root], repo / "Completeness_783.csv",
                                 repo / "Connectivity_783.parquet", params)
        indices, ticks = [], []
        for index, times in trains.items():
            indices.extend([index] * len(times))
            ticks.extend(np.rint(np.asarray(times / b2.second) / meta["dt_s"]).astype(np.int64))
        digest = event_digest(indices, ticks, int(round(meta["duration_s"] / meta["dt_s"])) + 1)
        write_json(args.output, {"seed": args.seed_base, "spikes": len(indices),
                                 "event_sha256": digest, "execution": "fresh upstream model.run_trial"})
        return
    audit = audit_signs(repo, {"v1.1.0": args.annotations_v1, "v2.1.0": args.annotations_v2}, roots)
    result = {"issue": 11, "metadata": meta, "audit": audit,
              "correction": {"roots": [IL3LN6_LEFT], "change": "left il3LN6 only: outgoing weights set negative; right unchanged"}}
    write_json(args.output, result)
    print(json.dumps(audit, indent=2), flush=True)
    net, syn, mon = build_network(repo, model, b2, params, exc)
    outgoing = np.flatnonzero(np.asarray(syn.i[:]) == root2i[IL3LN6_LEFT])
    baseline_weights = syn.w[outgoing].copy()
    assert (baseline_weights > 0 * b2.mV).all()
    def corrected(s):
        s.w[outgoing] = -abs(baseline_weights)
    all_counts = {k: [] for k in ("original", "corrected")}
    input_pairs = []
    for trial, seed in enumerate(meta["seeds"]):
        input_events = []
        for label, patch in (("original", lambda s: None), ("corrected", corrected)):
            t0 = time.monotonic()
            i, ticks, counts = run_condition(net, syn, mon, model, b2, params, seed, patch)
            all_counts[label].append(counts)
            if trial == 0 and label == "original":
                first_trial_digest = event_digest(i, ticks, int(round(meta["duration_s"] / meta["dt_s"])) + 1)
            mask = np.isin(i, exc)
            input_events.append(np.column_stack((i[mask], ticks[mask])))
            print(f"trial={trial} seed={seed} {label} spikes={len(i)} MN9={counts[readout]} wall_s={time.monotonic()-t0:.2f}", flush=True)
        input_pairs.append(bool(np.array_equal(*input_events)))
    a = np.stack(all_counts["original"])
    b = np.stack(all_counts["corrected"])
    np.savez_compressed("issue11_trial_counts.npz", roots=roots, original=a, corrected=b,
                        seeds=meta["seeds"])
    result["simulation"] = summarize_rates(a, b, roots, readout, meta["duration_s"])
    result["simulation"]["stimulated_neuron_spike_trains_identical_each_pair"] = input_pairs
    il = root2i[IL3LN6_LEFT]
    result["simulation"]["il3LN6_rates"] = {"original": interval(a[:, il] / meta["duration_s"]),
                                           "corrected": interval(b[:, il] / meta["duration_s"])}
    if args.verify_reference:
        result["reference_validation"] = verify_reference(args, first_trial_digest)
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    result["wall_s"] = time.monotonic() - started
    write_json(args.output, result)
    print(json.dumps(result["simulation"], indent=2), flush=True)


if __name__ == "__main__":
    main()
