"""Camber planning helper for the retained 3.9r sensitivity work."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from flyonenomics.analysis.plan import (
    coupling_sweep_settings,
    declared_drive_present,
    declared_substrate,
    dose_sensitivity_settings,
    planning_rows,
)
from flyonenomics.types import load_params

REPO = Path(__file__).resolve().parents[2]
SWAP_CAP_MIB = 4000
Q_PLAN = 27.0
ENGINES_PER_NODE = 62
CREDITS_PER_NODE_HOUR = 2.56
CAMBER_STAGE = REPO / "scripts" / "camber" / "stage.sh"


def swap_used_mib() -> float:
    """Used swap from sysctl vm.swapusage; MiB, scalar."""
    text = subprocess.check_output(["sysctl", "vm.swapusage"], text=True)
    used = 0.0
    tokens = text.split()
    for index, token in enumerate(tokens):
        if token == "used" and index + 2 < len(tokens) and tokens[index + 1] == "=":
            used = float(tokens[index + 2].rstrip("M"))
    return used


def credits_for(brain_s: float, rho: float = 1.0) -> float:
    """Node-hour credit estimate at 62 engines; credits, scalar."""
    engine_hours = rho * Q_PLAN * brain_s / 3600.0
    node_hours = engine_hours / ENGINES_PER_NODE
    return node_hours * CREDITS_PER_NODE_HOUR


def plan_text() -> str:
    """Print the section 6.3 WP21 Camber rows; seconds and credits."""
    rows = planning_rows()
    lines = ["WP21 Camber plan (no engine)", f"swap_used_mib={swap_used_mib():.0f} cap={SWAP_CAP_MIB}"]
    for name in ("3.9r-dose", "3.9r-coupling"):
        row = rows[name]
        lines.append(f"{name}: {row['factors']} brain_s={row['brain_s']} credits~{credits_for(row['brain_s']):.1f}")
    lines.append(f"dose_settings={len(dose_sensitivity_settings(load_params()))}")
    lines.append(f"coupling_settings={len(coupling_sweep_settings(load_params()))}")
    declared = declared_substrate()
    lines.append(f"declared_substrate={declared['candidate_id'] if declared else None}")
    lines.append(f"declared_drive_present={declared_drive_present()}")
    sensitivity = credits_for(rows["3.9r-dose"]["brain_s"] + rows["3.9r-coupling"]["brain_s"])
    lines.append(f"3.9r sensitivity: ~{sensitivity:.1f} credits")
    lines.append("The 3.2r-3.10r neural wave runs on the Mac (section 6.1), not here")
    return "\n".join(lines) + "\n"


def settings_json() -> str:
    """Serialize the 3.9r setting lists; source units per key."""
    params = load_params()
    payload = {
        "dose": dose_sensitivity_settings(params),
        "coupling": coupling_sweep_settings(params),
        "files": ["coupling-sweep.json", "dose-p2.json"],
    }
    return json.dumps(payload, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Plan, print settings, or refuse a launch until dependencies land."""
    parser = argparse.ArgumentParser(description="WP21 3.9r sensitivity planning helper")
    parser.add_argument("--plan", action="store_true", help="print brain s and credit rows")
    parser.add_argument("--settings", action="store_true", help="print 3.9r setting lists as JSON")
    parser.add_argument("--run", action="store_true", help="launch Camber jobs (blocked until dependencies land)")
    args = parser.parse_args(argv)
    if args.settings:
        sys.stdout.write(settings_json())
        return 0
    sys.stdout.write(plan_text())
    if not args.run:
        return 0
    used = swap_used_mib()
    if used > SWAP_CAP_MIB:
        sys.stderr.write(f"swap used {used:.0f}M exceeds {SWAP_CAP_MIB}M; not launching\n")
        return 2
    if not declared_drive_present():
        sys.stderr.write("Waiting for: the declared substrate drive data/drive-v0.2.yaml (WP19)\n")
        return 3
    if not CAMBER_STAGE.is_file():
        sys.stderr.write("Waiting for: lane-cam stage.sh\n")
        return 3
    sys.stderr.write("No 3.9r Camber launcher is implemented; this command is planning-only\n")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
