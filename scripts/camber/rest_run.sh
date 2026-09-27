#!/usr/bin/env bash
# Camber node: one rest_screen.py action under a whole-command timeout.
# Usage: rest_run.sh <label> <action> [args...]   (env REST_TIMEOUT_S, REST_Q)
set -euo pipefail
if [[ $# -lt 2 ]]; then
  echo 'usage: rest_run.sh <label> <action> [args...]' >&2
  exit 2
fi
label="$1"
shift
export CAMBER_JOB_ID="${CAMBER_JOB_ID:-${JOB_ID:-}}"
: "${CAMBER_JOB_ID:?Camber must supply CAMBER_JOB_ID or JOB_ID}"
exec timeout --signal=TERM --kill-after=20s "${REST_TIMEOUT_S:-9000}s" bash scripts/camber/job.sh "$label" \
  uv run python scripts/camber/rest_screen.py "$@" --job-id "$CAMBER_JOB_ID" --q "${REST_Q:-100}"
