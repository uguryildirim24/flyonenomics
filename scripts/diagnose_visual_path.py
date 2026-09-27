"""WP10 visual-path diagnostic CLI; WP18 adds v2 constructed-formula mode."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

from flyonenomics.diagnostics.visual_path import (
    PR_ACCEPTANCE_DEG,
    condition_grid_v2,
    photoreceptor_condition_rates,
    run_diagnostic,
    run_tiny,
    write_json,
)
from flyonenomics.types import load_params


def main() -> None:
    """Run the smoke, tiny, full, or v2 constructed-formula path. Units: seconds, Hz."""
    parser = argparse.ArgumentParser(description="WP10/WP18 visual-path diagnostic")
    parser.add_argument("--smoke", action="store_true", help="one site, one seed, 1 s brain time")
    parser.add_argument("--tiny", action="store_true", help="fixture-engine JSON dry run")
    parser.add_argument("--stripes-300", action="store_true",
                        help="corrected-azimuth 300 Hz stripes for R1_6, R1_6+R7+R8, L1+L2")
    parser.add_argument("--condition", default=None,
                        help="one condition id, e.g. R1_6_az-45_rate300_seed1, plus its determinism replay")
    parser.add_argument("--v2-formula", action="store_true",
                        help="constructed photoreceptor dark/ambient/stripe rates; no engine")
    parser.add_argument("--out", type=Path, default=None, help="run directory")
    parser.add_argument("--skip-machine-check", action="store_true", help="skip swap and process gate")
    args = parser.parse_args()
    os.environ.setdefault("FLYONENOMICS_CACHE_DIR", "<local-project-root>/.cache")
    if args.v2_formula:
        params = load_params()
        r_max = float(params.get("vis.r_max"))
        preferred = np.linspace(-150.0, 150.0, 21)
        r_light = 150.0
        payload = {
            "r_light_hz": r_light,
            "acceptance_deg": PR_ACCEPTANCE_DEG,
            "grid": condition_grid_v2(r_light=r_light, seeds=(1,)),
            "rates": {
                "dark": photoreceptor_condition_rates(
                    preferred, kind="dark", r_light=r_light, r_max=r_max,
                ).tolist(),
                "ambient": photoreceptor_condition_rates(
                    preferred, kind="ambient", r_light=r_light, r_max=r_max,
                ).tolist(),
                "stripe_45": photoreceptor_condition_rates(
                    preferred, kind="stripe", r_light=r_light, r_max=r_max,
                    bar_azimuth_deg=45.0,
                ).tolist(),
            },
        }
        destination = args.out or (Path("runs") / "diagnostics" / "visual-path" / "v2-formula")
        write_json(destination / "formula.json", payload)
        print(json.dumps({"out": str(destination), "n_grid": len(payload["grid"])}))
        print(destination)
        return
    if args.tiny:
        path = run_tiny(args.out)
    else:
        mode = "stripes300" if args.stripes_300 else ("smoke" if args.smoke else "full")
        path = run_diagnostic(
            mode=mode, out_dir=args.out, skip_machine_check=args.skip_machine_check,
            condition=args.condition,
        )
    print(path)


if __name__ == "__main__":
    main()
