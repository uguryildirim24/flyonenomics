#!/usr/bin/env bash
# Run one packed WP27 diagnostic job. Usage: rest_tier3_diag.sh <label> <plan.json> <job-index> <workers>
set -euo pipefail
if [[ $# -lt 4 ]]; then
  echo 'usage: rest_tier3_diag.sh <label> <plan.json> <job-index> <workers>' >&2
  exit 2
fi
label="$1"
plan="$2"
job_index="$3"
workers="$4"
export CAMBER_JOB_ID="${CAMBER_JOB_ID:-${JOB_ID:-}}"
: "${CAMBER_JOB_ID:?Camber must supply CAMBER_JOB_ID or JOB_ID}"
timeout_s="${REST_TIMEOUT_S:-9000}"
exec timeout --signal=TERM --kill-after=20s "${timeout_s}s" bash scripts/camber/job.sh "$label" \
  uv run python scripts/camber/rest_tier3.py diag --plan "$plan" --job-index "$job_index" \
  --out "results/$label" --workers "$workers" --job-id "$CAMBER_JOB_ID"
