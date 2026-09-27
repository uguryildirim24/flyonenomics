#!/usr/bin/env bash
# Dose-series speed legs on one node: four workers, then sixteen.
set -euo pipefail

uv run python scripts/run_experiment.py data/experiments/dose-series.json \
  --workers 4 --runs-dir results/dose-series/runs-w4
uv run python scripts/run_experiment.py data/experiments/dose-series.json \
  --workers 16 --runs-dir results/dose-series/runs-w16
