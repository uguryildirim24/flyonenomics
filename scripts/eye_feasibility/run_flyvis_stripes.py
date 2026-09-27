"""Run a pretrained flyvis model on 20 s, 5-degree static/moving stripes.

This script belongs in a separate flyvis environment; it deliberately has no
project imports.  FLYVIS_ROOT_DIR must point at data populated by
``flyvis download-pretrained``.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import resource
import time



def main() -> None:
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="flow/0000/000")
    parser.add_argument("--duration-s", type=float, default=20.0)
    parser.add_argument("--fps", type=int, default=100)
    parser.add_argument("--azimuths", default="-60,0,60")
    parser.add_argument("--stripe-width-deg", type=float, default=5.0)
    parser.add_argument("--degrees-per-column", type=float, default=5.0)
    parser.add_argument("--moving-speed-deg-s", type=float, default=60.0)
    args = parser.parse_args()

    # This script runs in the separate flyvis environment. Keeping all of its
    # third-party imports inside main lets project tooling import the module.
    import flyvis
    from flyvis import NetworkView
    import numpy as np
    import psutil
    import torch

    if not os.environ.get("FLYVIS_ROOT_DIR"):
        raise SystemExit("FLYVIS_ROOT_DIR must name the separate flyvis data directory")
    process = psutil.Process()
    started = time.monotonic()
    load_started = time.monotonic()
    net = NetworkView(args.model).init_network()
    net.eval()
    load_wall = time.monotonic() - load_started
    nodes = net.connectome.nodes
    node_type = nodes.type[:].astype(str)
    node_u = np.asarray(nodes.u[:], dtype=np.int32)
    node_v = np.asarray(nodes.v[:], dtype=np.int32)
    types = sorted(set(node_type))
    receptor = node_type == "R1"
    # The receptor input lattice has 721 axial coordinates. Most modelled
    # types share it, while the two strided Lawf layers have 123 cells each.
    u = node_u[receptor]
    v = node_v[receptor]
    if len(u) != 721:
        raise ValueError(f"expected 721 hex columns, found {len(u)}")
    # The horizontal coordinate follows flyvis's image x convention.  This is
    # an explicit geometric choice for the feasibility timing probe, not a
    # FlyWire correspondence.
    x_deg = (u + 0.5 * v) * args.degrees_per_column
    n_frames = int(round(args.duration_s * args.fps))
    t = np.arange(n_frames, dtype=np.float32) / args.fps
    azimuths = [float(value) for value in args.azimuths.split(",")]
    conditions = [(f"static_{az:+g}", np.full(n_frames, az, np.float32)) for az in azimuths]
    # One moving condition crosses the complete represented field repeatedly.
    lo, hi = float(x_deg.min()), float(x_deg.max())
    span = hi - lo
    moving = lo + np.mod(args.moving_speed_deg_s * t, span)
    conditions.append(("moving", moving.astype(np.float32)))

    rows = []
    for name, centres in conditions:
        lum = np.full((1, n_frames, 1, 721), 0.5, dtype=np.float32)
        distance = np.abs(x_deg[None, :] - centres[:, None])
        lum[0, :, 0, :][distance <= args.stripe_width_deg / 2] = 0.0
        tensor = torch.from_numpy(lum)
        before_rss = process.memory_info().rss
        run_started = time.monotonic()
        with torch.no_grad():
            activity = net.simulate(tensor.to(flyvis.device), dt=1 / args.fps, as_layer_activity=True)
        run_wall = time.monotonic() - run_started
        by_type = {}
        for cell_type in types:
            values = np.asarray(getattr(activity, cell_type).squeeze(0), dtype=np.float32)
            # Preserve graded output per type and hex column compactly: temporal
            # mean, standard deviation, minimum and maximum for every column.
            by_type[cell_type] = {
                "columns": int(values.shape[1]),
                "mean": values.mean(axis=0).astype(float).tolist(),
                "std": values.std(axis=0).astype(float).tolist(),
                "min": values.min(axis=0).astype(float).tolist(),
                "max": values.max(axis=0).astype(float).tolist(),
            }
        rows.append({
            "condition": name,
            "wall_seconds": run_wall,
            "rss_before_bytes": before_rss,
            "rss_after_bytes": process.memory_info().rss,
            "graded_activity": by_type,
        })
        del activity, tensor, lum

    import importlib.metadata
    output = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(), "machine": platform.machine(),
            "python": platform.python_version(), "processor": platform.processor(),
        },
        "versions": {
            "flyvis": importlib.metadata.version("flyvis"),
            "torch": torch.__version__, "numpy": np.__version__,
        },
        "device": str(flyvis.device),
        "model": args.model,
        "network": {"cell_types": len(types), "cells": int(len(node_type)), "hex_columns": int(len(u))},
        "protocol": {
            "duration_s": args.duration_s, "fps": args.fps, "dt_s": 1 / args.fps,
            "stripe_width_deg": args.stripe_width_deg,
            "static_azimuths_deg": azimuths,
            "moving_speed_deg_s": args.moving_speed_deg_s,
            "degrees_per_column_choice": args.degrees_per_column,
            "luminance_background": 0.5, "luminance_stripe": 0.0,
        },
        "hex_columns": {"u": u.astype(int).tolist(), "v": v.astype(int).tolist(), "x_deg": x_deg.astype(float).tolist()},
        "load_wall_seconds": load_wall,
        "total_wall_seconds": time.monotonic() - started,
        "peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "peak_rss_units_note": "bytes on macOS; KiB on Linux",
        "conditions": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "out": str(args.out), "load_wall_seconds": load_wall,
        "total_wall_seconds": output["total_wall_seconds"],
        "peak_rss_bytes": output["peak_rss_bytes"],
        "condition_wall_seconds": {row["condition"]: row["wall_seconds"] for row in rows},
    }, indent=2))


if __name__ == "__main__":
    main()
