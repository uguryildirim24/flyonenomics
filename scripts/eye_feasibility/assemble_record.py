"""Assemble the committed eye-front-end feasibility evidence record."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--flyvis-run", type=Path, required=True)
    p.add_argument("--connectome-analysis", type=Path, required=True)
    p.add_argument("--flyvis-commit", required=True)
    p.add_argument("--afterlife-commit", required=True)
    p.add_argument("--annotations-commit", required=True)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--freeze", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    from flyonenomics.io import hash_file, read_json

    run = read_json(a.flyvis_run)
    anatomy = read_json(a.connectome_analysis)
    freeze = read_json(a.freeze)
    output = {
        "class": "development",
        "purpose": "feasibility of feeding the v783 spiking substrate with a trained flyvis eye",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "motion seam feasible to attempt; ring seam incomplete",
        "verdict_reasons": [
            "The pinned project annotation contains type but no optic-lobe hex/column identifier, so the local-table-only join found zero unique matches among flyvis's 45,669 cells.",
            "Matsliah, Yu et al. publish a v783 right-eye grid of 796 hex columns, and the associated OpticLobe.jl and Codex resources assign FlyWire roots for all T4a-d and T5a-d types.",
            "The published map still needs a version/root check and a frozen transform from flyvis's 721-column lattice before a dynamic motion-path probe.",
            "Only 20.28% of medulla-origin synapses into the MeTu cells feeding the relevant TuBu set, and 14.74% of their absolute composed input weight, come from flyvis-modelled types, so the ring seam remains incomplete.",
            "The T4/T5 motion anatomy reaches all four steering endpoints, but anatomy does not demonstrate functional propagation.",
        ],
        "provenance": {
            "measurement_platform": run["platform"],
            "flyvis_git_commit": a.flyvis_commit,
            "fly_afterlife_git_commit": a.afterlife_commit,
            "flywire_annotations_git_commit_checked": a.annotations_commit,
            "pinned_v2_1_annotations_commit": "ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0",
            "flyvis_license": "MIT",
            "fly_afterlife_license": "MIT",
            "flywire_data_license": "CC-BY 4.0",
            "published_column_map": {
                "paper_doi": "10.1038/s41586-024-07981-1",
                "optic_lobe_data_commit": "13e0e2bf1db9d7184c084e111591d108332fc440",
                "codex_v783_url": "https://storage.googleapis.com/flywire-data/codex/data/fafb/783/column_assignment.csv.gz",
                "codex_download_sha256": "bdf4ce7f62cc63493d53eefad3816ff2dfd08b190e97b35a492e0e453df2f0f6",
                "verified_right_eye_columns": 796,
                "scope": "right-eye integration claim; includes all T4a-d and T5a-d types but not all 65 flyvis types or a frozen 721-to-796 transform",
            },
            "flyvis_environment_freeze": freeze,
            "pretrained_checkpoint": {"path": "results/flow/0000/000/best_chkpt", "sha256": hash_file(a.checkpoint)},
            "raw_inputs_sha256": {"flyvis_run": hash_file(a.flyvis_run), "connectome_analysis": hash_file(a.connectome_analysis)},
        },
        "flyvis_run": run,
        "connectome_analysis": anatomy,
        "conversion_contract": {
            "status": "proposal only; published right-eye map not yet integrated or validated",
            "transform": "For each uniquely mapped cell, subtract its blank-scene graded baseline, rectify positive activity, divide by a predeclared reference amplitude, clip to [0,1], and use that fraction of a predeclared maximum Poisson rate as additive drive.",
            "free_choices": [
                "pretrained model or externally selected ensemble",
                "two-eye field geometry, orientation, acceptance angle, and flyvis-to-FlyWire hex transform",
                "seam depth and exact type aliases",
                "blank baseline duration and whether negative deviations require a separate OFF channel",
                "reference amplitude and maximum Poisson rate",
                "flyvis frame rate, interpolation into 10 ms engine chunks, and seam latency",
                "Poisson seeds and whether noise is independent or shared across cells",
                "whether seam events add to or replace native incoming current",
                "treatment of unmatched flyvis columns, unmatched FlyWire cells, and types flyvis omits",
                "static-stripe contrast, onset ramp, preperiod, and retinal luminance normalization",
            ],
            "fitting_rule": "Freeze every choice from flyvis calibration data, anatomy, or published physiology before inspecting MeTu, TuBu, ER, lobula-plate, or steering outcomes; no choice may be fitted to a downstream response.",
        },
        "dynamic_probe": {
            "status": "not run",
            "brain_seconds": 0,
            "reason": "The lane did not discover or integrate the published v783 right-eye column map. Type-averaging flyvis onto every same-type root would erase stripe position and would not test the proposed seam.",
        },
        "limits": [
            "flyvis is a trained optic-lobe model, not a biological eye; no result here establishes visual function in the spiking brain.",
            "flyvis was trained on optic flow; static-stripe responses are less tested.",
            "flyvis ends at T4/T5 and the columnar medulla; it does not supply MeTu, TuBu, ER, lobula-plate outputs, descending neurons, or steering cells.",
            "The static graph proves anatomical routes, not dynamic propagation.",
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(output, indent=2, allow_nan=False) + "\n")
    print(a.out, a.out.stat().st_size)


if __name__ == "__main__":
    main()
