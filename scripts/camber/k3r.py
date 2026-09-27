#!/usr/bin/env python3
"""Camber K3r / K3r-T / 4.8r planner (SPEC-P2 sections 3.5, 6.2, 6.3).

`--plan` prints brain seconds and credits; it also names item 122's declared
substrate (through `behaviour/visual_calibration.py`) and the real missing
inputs. `--run` executes the named WP20 stages through
`behaviour/buridan.py`, refusing until WP18's V-cal and item 125's dopamine
file land; Q-rest is not a WP20 input.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
K3R_K = (1, 2, 4, 8, 16)
K3R_SEEDS = 5
BURIDAN_S = 20.0
PLAN_SETTLE_S = 2.0
ENGINES_PER_NODE = 62
CREDITS_PER_NODE_HOUR = 2.56
CAP_RHO1 = 4.0
MEASURED_RHO = 1.76
Q_PLAN = 27.0
# 4.8r: 3 perms + 5 jitter + sigma_h {0,20} + v_fwd {half, double} + histamine off = 13.
N_4_8R_VARIANTS = 13
N_4_8R_ARMS = 3
N_4_8R_SEEDS = 10


def probe_s() -> float:
    """One Buridan probe including planning settle. Units: seconds."""
    return BURIDAN_S + PLAN_SETTLE_S


def credits(brain_s: float, rho: float) -> float:
    """Camber credits at two concurrent large nodes. Units: credits."""
    engine_hours = (brain_s / 3600.0) * rho * Q_PLAN / 5.0
    # Section 6.3 quotes node-hours = engine-hours / 62 at rho=1 planning figures.
    # The table credits already include rho=1: 0.2 for K3r, 2.7 for 4.8r.
    node_hours = (brain_s / 3600.0) / ENGINES_PER_NODE * rho
    return node_hours * CREDITS_PER_NODE_HOUR


def plan() -> dict[str, Any]:
    """Return the section 6.3 K3r, 4.8r and K3r-T rows. Units: s, hours, credits."""
    from flyonenomics.behaviour.buridan import p2_missing_dependencies
    from flyonenomics.behaviour.visual_calibration import declared_substrate, declared_substrate_id

    k3r_brain = len(K3R_K) * K3R_SEEDS * probe_s()
    k3r_t_brain = k3r_brain
    four8_brain = N_4_8R_VARIANTS * N_4_8R_ARMS * N_4_8R_SEEDS * probe_s()
    rows = {
        "K3r_proposal": {"brain_s": k3r_brain, "factors": "5 K_steer x 5 seeds x 22 s",
                         "engine_hours_rho1": 4.1, "credits_rho1": 0.2,
                         "credits_rho_1_76": round(0.2 * MEASURED_RHO, 3)},
        "4.8r": {"brain_s": four8_brain, "factors": "13 variants x 3 arms x 10 seeds x 22 s",
                 "engine_hours_rho1": 64.0, "credits_rho1": 2.7,
                 "credits_rho_1_76": round(2.7 * MEASURED_RHO, 3)},
        "K3r-T": {"brain_s": k3r_t_brain, "factors": "5 K_steer x 5 seeds x 22 s",
                  "engine_hours_rho1": 4.1, "credits_rho1": 0.2,
                  "credits_rho_1_76": round(0.2 * MEASURED_RHO, 3)},
    }
    total_rho1 = 0.2 + 2.7 + 0.2
    missing = p2_missing_dependencies()
    reason = "Waiting for: " + (", ".join(missing) if missing else "the coordinator's engine slot")
    return {
        "wp": "WP20",
        "substrate_id": declared_substrate_id(),
        "declared_substrate": declared_substrate(),
        "missing": missing,
        "cap_credits_rho1": CAP_RHO1,
        "cap_credits_rho_1_76": round(CAP_RHO1 * MEASURED_RHO, 3),
        "measured_rho": MEASURED_RHO,
        "rows": rows,
        "total_credits_rho1": total_rho1,
        "total_credits_rho_1_76": round(total_rho1 * MEASURED_RHO, 3),
        "under_cap": total_rho1 <= CAP_RHO1 and total_rho1 * MEASURED_RHO <= CAP_RHO1 * MEASURED_RHO + 1e-9,
        "run_refused": True,
        "reason": reason + ". Ask CREDITS w20 before any Camber job.",
    }


def main(argv: list[str] | None = None) -> None:
    """CLI: --plan prints JSON; --run executes the named WP20 stages."""
    from flyonenomics.behaviour.buridan import WAVE

    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true")
    group.add_argument("--run", action="store_true")
    parser.add_argument("--stages", default=",".join(WAVE),
                        help="comma-separated WP20 stages (bias, 4.1r-sign, K3r, K3r-T, VT-cal, 4.1r, 4.2r, 4.8r, open-loop)")
    parser.add_argument("--workers", type=int, default=1,
                        help="engine workers per WP20 run (default 1)")
    args = parser.parse_args(argv)
    os.environ["FLYONENOMICS_P2_WORKERS"] = str(max(1, args.workers))
    document = plan()
    if args.plan:
        print(json.dumps(document, indent=2))
        return
    stages = tuple(stage.strip() for stage in args.stages.split(",") if stage.strip())
    from flyonenomics.behaviour.buridan import p2_missing_dependencies, run_wave

    # Check only the first stage: later consumers may use bytes it creates.
    # Each runner checks its own dependencies again at execution time.
    run_missing = p2_missing_dependencies(stages[0] if stages else None)
    if run_missing:
        reason = "Waiting for: " + ", ".join(run_missing)
        print(reason, file=sys.stderr)
        print(json.dumps({"status": "refused", **document,
                          "run_missing": run_missing, "reason": reason}, indent=2))
        raise SystemExit(2)
    results = run_wave(stages)
    blocked = [name for name, row in results["results"].items() if row.get("status") == "blocked"]
    failed = [name for name, row in results["results"].items()
              if row.get("status") == "failed" or row.get("outcome") == "failed"]
    status = ("blocked" if blocked else "failed" if failed else
              "checkpoint" if results["checkpoint"] else "done")
    print(json.dumps({"status": status, "stages": list(stages),
                      "blocked": blocked, "failed": failed,
                      "checkpoint": results["checkpoint"],
                      "results": results["results"]}, indent=2, default=str))
    if blocked or failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
