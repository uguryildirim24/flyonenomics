#!/usr/bin/env bash
# Run the item-88 3c timestep-convergence job.
# Usage: rest_t3c_convergence.sh <label> <plan.json> <workers>
set -euo pipefail
if [[ $# -lt 3 ]]; then
  echo 'usage: rest_t3c_convergence.sh <label> <plan.json> <workers>' >&2
  exit 2
fi
label="$1"
plan="$2"
workers="$3"
export CAMBER_JOB_ID="${CAMBER_JOB_ID:-${JOB_ID:-}}"
: "${CAMBER_JOB_ID:?Camber must supply CAMBER_JOB_ID or JOB_ID}"
timeout_s="${REST_TIMEOUT_S:-9000}"
exec timeout --signal=TERM --kill-after=20s "${timeout_s}s" bash scripts/camber/job.sh "$label" \
  uv run python scripts/camber/rest_tier3.py t3c-dt --plan "$plan" \
  --out "results/$label" --workers "$workers" --job-id "$CAMBER_JOB_ID"
