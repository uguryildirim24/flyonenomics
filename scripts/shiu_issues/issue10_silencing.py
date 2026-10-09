#!/usr/bin/env python3
"""Compare outgoing-only versus bidirectional silencing, spike for spike.

Uses upstream silence() unchanged, then optionally zeros incoming weights too.
Default silenced neuron is recurrent il3LN6, not an isolated/terminal neuron.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from issue11_sign import (IL3LN6_LEFT, common_parser, setup, build_network,
                          run_condition, interval, write_json, event_digest,
                          verify_reference)


def code_quotes(repo):
    lines = (repo / "model.py").read_text().splitlines()
    start = next(i for i, s in enumerate(lines) if s.startswith("def silence("))
    loop = next(i for i in range(start, len(lines)) if lines[i].strip() == "for i in slnc:")
    sentence = "This sets all synaptic connections to and from those neurons to zero."
    readme = (repo / "Readme.md").read_text().splitlines()
    return {"code_path": "model.py", "code_lines": [loop + 1, loop + 2],
            "code_quote": "\n".join(lines[loop:loop + 2]),
            "readme_path": "Readme.md", "readme_line": readme.index(sentence) + 1,
            "readme_quote": sentence,
            "suggested_readme": "This sets all outgoing synaptic weights from those neurons to zero; the neurons can still receive input and spike."}


def canonical_events(indices, ticks, excluded, ticks_per_trial):
    mask = ~np.isin(indices, excluded)
    # A spike is exactly (neuron index, integer time tick); sort independently
    # of Brian2's cross-neuron monitor ordering. No approximate time tolerance.
    events = indices[mask] * ticks_per_trial + ticks[mask]
    events.sort()
    return events


def main():
    p = common_parser(__doc__)
    p.set_defaults(stimulus_side="right")  # il3LN6 is active under right-LB3 drive
    p.add_argument("--silence-root", type=int, action="append",
                   help="Repeatable; default left il3LN6 720575940632403986")
    args = p.parse_args()
    started = time.monotonic()
    repo, model, b2, params, roots, root2i, exc, readout, meta = setup(args)
    silenced_roots = args.silence_root or [IL3LN6_LEFT]
    slnc = [root2i[root] for root in silenced_roots]
    if len(set(slnc)) != len(slnc):
        raise ValueError("Duplicate silencing roots")
    con = pd.read_parquet(repo / "Connectivity_783.parquet")
    outgoing_rows = np.flatnonzero(con.Presynaptic_ID.isin(silenced_roots).to_numpy())
    incoming_rows = np.flatnonzero(con.Postsynaptic_ID.isin(silenced_roots).to_numpy())
    incoming_only = np.setdiff1d(incoming_rows, outgoing_rows)
    connectivity = {
        "outgoing_connection_rows": len(outgoing_rows),
        "outgoing_synapses": int(con.iloc[outgoing_rows].Connectivity.sum()),
        "incoming_connection_rows": len(incoming_rows),
        "incoming_synapses": int(con.iloc[incoming_rows].Connectivity.sum()),
        "additional_incoming_rows_zeroed": len(incoming_only),
        "additional_incoming_synapses_zeroed": int(con.iloc[incoming_only].Connectivity.sum()),
    }
    del con
    result = {"issue": 10, "metadata": meta, "quotes": code_quotes(repo),
              "silenced_roots": silenced_roots, "connectivity": connectivity}
    write_json(args.output, result)
    print(json.dumps({"quotes": result["quotes"], "connectivity": connectivity}, indent=2), flush=True)
    net, syn, mon = build_network(repo, model, b2, params, exc)
    def outgoing(s):
        model.silence(slnc, s)
    def both(s):
        model.silence(slnc, s)
        s.w[incoming_rows] = 0 * b2.mV
    ticks_per_trial = int(round(meta["duration_s"] / meta["dt_s"])) + 1
    trials = []
    counts_by_condition = {label: [] for label in ("outgoing_only", "both_directions")}
    # Cumulative digest of all exact, canonical event arrays including seed.
    digests = {label: hashlib.sha256() for label in counts_by_condition}
    for trial, seed in enumerate(meta["seeds"]):
        trains = []
        own = []
        for label, patch in (("outgoing_only", outgoing), ("both_directions", both)):
            t0 = time.monotonic()
            i, ticks, counts = run_condition(net, syn, mon, model, b2, params, seed, patch)
            counts_by_condition[label].append(counts)
            if trial == 0 and label == "outgoing_only":
                first_trial_digest = event_digest(i, ticks, ticks_per_trial)
            events = canonical_events(i, ticks, slnc, ticks_per_trial)
            trains.append(events)
            own.append(canonical_events(i, ticks, np.setdiff1d(np.arange(len(roots)), slnc), ticks_per_trial))
            digests[label].update(np.asarray([seed, len(events)], dtype="<i8").tobytes())
            digests[label].update(events.astype("<i8").tobytes())
            print(f"trial={trial} seed={seed} {label} spikes={len(i)} MN9={counts[readout]} silenced_spikes={counts[slnc].tolist()} wall_s={time.monotonic()-t0:.2f}", flush=True)
        different_events = np.setxor1d(*trains, assume_unique=True)
        changed_neurons = np.unique(different_events // ticks_per_trial)
        a = counts_by_condition["outgoing_only"][-1]
        b = counts_by_condition["both_directions"][-1]
        count_difference = a - b
        count_difference[slnc] = 0
        trials.append({"trial": trial, "seed": seed,
                       "other_neuron_spike_trains_identical": bool(np.array_equal(*trains)),
                       "other_neurons_compared": len(roots) - len(slnc),
                       "other_spike_events_compared": [len(x) for x in trains],
                       "other_neurons_with_changed_trains": len(changed_neurons),
                       "other_neurons_with_changed_counts": int((count_difference != 0).sum()),
                       "other_spike_event_symmetric_difference": len(different_events),
                       "silenced_neuron_spike_trains_identical": bool(np.array_equal(*own)),
                       "silenced_neuron_spike_counts": [a[slnc].tolist(), b[slnc].tolist()]})
    counts = {k: np.stack(v) for k, v in counts_by_condition.items()}
    np.savez_compressed("issue10_trial_counts.npz", roots=roots, seeds=meta["seeds"], **counts)
    n_identical = sum(t["other_neuron_spike_trains_identical"] for t in trials)
    simulation = {
        "trials": trials, "other_neuron_trains_identical_trials": n_identical,
        "all_other_neuron_trains_identical": n_identical == len(trials),
        "neuron_trial_comparisons": (len(roots) - len(slnc)) * len(trials),
        "non_silenced_spike_digest_sha256": {k: h.hexdigest() for k, h in digests.items()},
        "comparison": "Exact (neuron index, Brian2 clock tick) events, including silent neurons; no timing tolerance",
        "silenced_neuron_trains_differ_trials": sum(not t["silenced_neuron_spike_trains_identical"] for t in trials),
        "silenced_rates": {k: {str(root): interval(v[:, idx] / meta["duration_s"])
                               for root, idx in zip(silenced_roots, slnc)} for k, v in counts.items()},
        "readout_rates": {k: interval(v[:, readout] / meta["duration_s"]) for k, v in counts.items()},
    }
    if n_identical == len(trials):
        simulation["conclusion"] = "For all tested seeds, every other neuron's spike train is identical. Align README with outgoing-only implementation; no model change is needed to fix the documentation mismatch. The silenced neurons can still receive input and spike."
    else:
        simulation["conclusion"] = "Other-neuron spike trains differ; inspect trial differences before suggesting a documentation-only fix."
    result["simulation"] = simulation
    if args.verify_reference:
        result["reference_validation"] = verify_reference(args, first_trial_digest, silenced_roots)
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    result["wall_s"] = time.monotonic() - started
    write_json(args.output, result)
    print(json.dumps({k: v for k, v in simulation.items() if k != "trials"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
