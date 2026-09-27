#!/usr/bin/env bash
# Run one packed T2 job. Usage: rest_tier3_t2.sh <label> <plan.json> <job-index> <workers>
set -euo pipefail
if [[ $# -lt 4 ]]; then
  echo 'usage: rest_tier3_t2.sh <label> <plan.json> <job-index> <workers>' >&2
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
  uv run python scripts/camber/rest_tier3.py t2 --plan "$plan" --job-index "$job_index" \
  --out "results/$label" --workers "$workers" --job-id "$CAMBER_JOB_ID"
