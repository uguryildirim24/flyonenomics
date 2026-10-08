#!/usr/bin/env bash
# Submit tier-2 completion shards whose Stash prefixes are staged. Run only on an explicit GO.
# Usage: scripts/camber/submit_tier2_completion.sh A-01 [B-03 ...]
set -euo pipefail
CAMBER="${CAMBER:-${HOME}/.camber/bin/camber}"
ROOT_STASH="${ROOT_STASH:-stash://account-redacted/projects/flyonenomics}"
RECEIPTS="${RECEIPTS:-camber-runs/wp17/receipts}"
mkdir -p "${RECEIPTS}"
for shard in "$@"; do
  label="tier2c-${shard}"
  plan="validation/records/p2/rest-tier2-completion/${shard}.json"
  [[ -f "${plan}" ]] || { echo "no plan ${plan}" >&2; exit 2; }
  if [[ -e "${RECEIPTS}/${label}-create.txt" ]]; then
    echo "already submitted ${label}; refusing to resubmit" >&2
    exit 2
  fi
  date -u +%Y-%m-%dT%H:%M:%SZ > "${RECEIPTS}/${label}-submit-time.txt"
  "${CAMBER}" job create --engine base --size large --path "${ROOT_STASH}/${label}" \
    --cmd "git config core.fileMode false && REST_TIMEOUT_S=9000 REST_Q=100 bash scripts/camber/rest_screen.sh ${label} ${plan} 30" \
    > "${RECEIPTS}/${label}-create.txt" 2>&1
  echo "${label} $(cat "${RECEIPTS}/${label}-submit-time.txt") $(grep 'Job ID' "${RECEIPTS}/${label}-create.txt")"
done
