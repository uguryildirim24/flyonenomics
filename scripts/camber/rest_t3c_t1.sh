#!/usr/bin/env bash
# Run the item-89 3c T1 R-screen (and T2 if it admits) at dt 0.05 ms.
# Usage: rest_t3c_t1.sh <label> <plan.json> <workers>
set -euo pipefail
if [[ $# -lt 3 ]]; then
  echo 'usage: rest_t3c_t1.sh <label> <plan.json> <workers>' >&2
  exit 2
fi
label="$1"
plan="$2"
workers="$3"
export CAMBER_JOB_ID="${CAMBER_JOB_ID:-${JOB_ID:-}}"
: "${CAMBER_JOB_ID:?Camber must supply CAMBER_JOB_ID or JOB_ID}"
timeout_s="${REST_TIMEOUT_S:-10800}"
exec timeout --signal=TERM --kill-after=20s "${timeout_s}s" bash scripts/camber/job.sh "$label" \
  uv run python scripts/camber/rest_tier3.py t3c-t1 --plan "$plan" \
  --out "results/$label" --workers "$workers" --job-id "$CAMBER_JOB_ID"
