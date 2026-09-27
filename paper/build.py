#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["CairoSVG==2.7.1"]
# ///
"""One-command draft PDF; no simulation, result analysis or remote compute."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from fill_results import TEMPLATE, fill
from plot_results import DEFAULT as RESULTS, RESULTS_SHA256, load_json
from plot_confirmation import DEFAULT as CONFIRMATION

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic-confirmation', type=Path, help='test-only labelled confirmation record')
    parser.add_argument('--final', action='store_true', help='omit draft banner and approval sentence')
    args = parser.parse_args()
    confirmation = args.synthetic_confirmation or CONFIRMATION
    confirmation_record = load_json(confirmation)
    if args.synthetic_confirmation and confirmation_record.get('_paper_fixture') != 'synthetic':
        raise ValueError('test override requires a labelled synthetic record')
    if not args.synthetic_confirmation and confirmation_record.get('_paper_fixture'):
        raise ValueError('default build refuses synthetic confirmation')
    tectonic = shutil.which("tectonic")
    if tectonic is None:
        raise SystemExit("Install Tectonic first; see paper/README.md.")
    # Cairo is a system library on macOS; set the loader path before importing.
    if sys.platform == "darwin" and not os.environ.get("DYLD_FALLBACK_LIBRARY_PATH"):
        env = dict(os.environ, DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:/usr/local/lib:/usr/lib")
        os.execve(sys.executable, [sys.executable, *sys.argv], env)
    import cairocffi
    import cairosvg

    build = HERE / "build"
    build.mkdir(exist_ok=True)
    tex = build / "manuscript.tex"
    (build / "final-mode.tex").write_text("\\finaltrue\n" if args.final else "\\finalfalse\n")
    result_path = RESULTS.resolve()
    if hashlib.sha256(result_path.read_bytes()).hexdigest() != RESULTS_SHA256:
        raise ValueError("reviewed result record differs from the manuscript's frozen findings")
    fill(result_path, confirmation, tex)
    dose_curves = HERE.parent / 'figures/3d/gaba-dose/curves.svg'
    cairosvg.svg2pdf(url=str(dose_curves), write_to=str(build / 'gaba-curves.pdf'))
    subprocess.run([tectonic, "--keep-logs", "manuscript.tex"], cwd=build, check=True)
    subprocess.run([tectonic, "--keep-logs", "--outdir", str(build),
                    str(HERE / "supplement.tex")], cwd=build, check=True)
    sources = [TEMPLATE, HERE / "supplement.tex", HERE / "result-bindings.json",
               HERE / "fill_results.py", HERE / "build.py", HERE / "build.py.lock",
               confirmation, dose_curves,
               HERE.parent / "figures/3d/male-cns-anatomy-paper.png", result_path]
    receipt = {"sources_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
               "tectonic": subprocess.check_output([tectonic, "--version"], text=True).strip(),
               "cairosvg": cairosvg.__version__, "cairo": cairocffi.cairo_version_string(),
               "python": sys.version,
               "results_inserted": True, "synthetic_confirmation": bool(args.synthetic_confirmation), "final": args.final, "replay_certified_by_build": False}
    (build / "build.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(build / "manuscript.pdf")
    print(build / "supplement.pdf")


if __name__ == "__main__":
    main()
