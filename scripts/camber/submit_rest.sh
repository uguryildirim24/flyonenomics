#!/usr/bin/env bash
# Copy a staged commit to the label's own Stash prefix and submit one rest_run.sh job.
# Run only on an explicit GO. Usage: submit_rest.sh <staged stash path> <label> <action> [args...]
# env CAMBER_SIZE (default large), CAMBER_GPU=1 for a GPU node, REST_TIMEOUT_S, REST_Q.
set -euo pipefail
CAMBER="${CAMBER:-${HOME}/.camber/bin/camber}"
ROOT_STASH="${ROOT_STASH:-stash://account-redacted/projects/flyonenomics}"
RECEIPTS="${RECEIPTS:-camber-runs/wp17/receipts}"
base="$1"
label="$2"
shift 2
prefix="${ROOT_STASH}/${label}"
mkdir -p "${RECEIPTS}"
if [[ -e "${RECEIPTS}/${label}-create.txt" ]]; then
  echo "already submitted ${label}; refusing to resubmit" >&2
  exit 2
fi
"${CAMBER}" stash cp -r "${base}" "${prefix}" > "${RECEIPTS}/${label}-stash-cp.log" 2>&1
"${CAMBER}" stash ls "${prefix}/.git" | grep HEAD > /dev/null
"${CAMBER}" stash ls "${prefix}/cache/Drosophila_brain_model" | grep Connectivity_783 > /dev/null
date -u +%Y-%m-%dT%H:%M:%SZ > "${RECEIPTS}/${label}-submit-time.txt"
gpu=""
if [[ "${CAMBER_GPU:-0}" == 1 ]]; then
  gpu="--gpu"
fi
# shellcheck disable=SC2086
"${CAMBER}" job create --engine base --size "${CAMBER_SIZE:-large}" ${gpu} --path "${prefix}" \
  --cmd "git config core.fileMode false && REST_TIMEOUT_S=${REST_TIMEOUT_S:-9000} REST_Q=${REST_Q:-100} bash scripts/camber/rest_run.sh ${label} $*" \
  > "${RECEIPTS}/${label}-create.txt" 2>&1
echo "${label} $(cat "${RECEIPTS}/${label}-submit-time.txt") $(grep 'Job ID' "${RECEIPTS}/${label}-create.txt")"
