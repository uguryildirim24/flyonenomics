#!/usr/bin/env bash
# Run only after the coordinator approves this particular label and budget.
set -euo pipefail
if [[ $# -lt 2 ]]; then
  echo 'usage: rest_screen.sh <label> <plan.json> [workers=36]' >&2
  exit 2
fi
label="$1"
plan="$2"
workers="${3:-36}"
export CAMBER_JOB_ID="${CAMBER_JOB_ID:-${JOB_ID:-}}"
: "${CAMBER_JOB_ID:?Camber must supply CAMBER_JOB_ID or JOB_ID}"
# Bound the whole node command (including dependency setup), below the granted running cap.
timeout_s="${REST_TIMEOUT_S:-12000}"
q="${REST_Q:-42.5}"
exec timeout --signal=TERM --kill-after=20s "${timeout_s}s" bash scripts/camber/job.sh "$label" uv run python scripts/camber/rest_screen.py \
  screen --input "$plan" --out "results/$label/R1" --workers "$workers" \
  --job-id "$CAMBER_JOB_ID" --q "$q"
