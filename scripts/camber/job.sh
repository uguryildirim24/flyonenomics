#!/usr/bin/env bash
# Camber node entry: install uv, sync the lock, set the cache, run the given command.
# Writes a log under results/<label>/. Usage: scripts/camber/job.sh <label> <command> [args...]
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 <label> <command> [args...]" >&2
  exit 2
fi

LABEL="$1"
shift

export FLYONENOMICS_CACHE_DIR="${FLYONENOMICS_CACHE_DIR:-${PWD}/cache}"
export UV_LINK_MODE="${UV_LINK_MODE:-copy}"
export PATH="${HOME}/.local/bin:${HOME}/.local/node/bin:${HOME}/.cargo/bin:${PATH}"

mkdir -p "results/${LABEL}"
LOG="results/${LABEL}/job.log"

ensure_cc() {
  if command -v gcc >/dev/null 2>&1 || command -v cc >/dev/null 2>&1; then
    return 0
  fi
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    if command -v sudo >/dev/null 2>&1; then
      sudo apt-get update -y
      sudo apt-get install -y --no-install-recommends gcc g++ libc6-dev
    else
      apt-get update -y
      apt-get install -y --no-install-recommends gcc g++ libc6-dev
    fi
  fi
}

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
  command -v uv >/dev/null 2>&1
}

ensure_node() {
  if command -v node >/dev/null 2>&1; then
    return 0
  fi
  # Dashboard pytest executes the frontend with node. Official tarball, no root.
  local ver=v20.19.5
  local dest="${HOME}/.local/node"
  mkdir -p "${dest}"
  curl -fsSL "https://nodejs.org/dist/${ver}/node-${ver}-linux-x64.tar.xz" | tar -xJ -C "${dest}" --strip-components=1
  export PATH="${dest}/bin:${PATH}"
  command -v node >/dev/null 2>&1
}

# Node sizing evidence: CPU topology at start, then load and summed python RSS every 60 s.
sample_usage() {
  while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) load=$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null) python_procs=$(ps -eo comm= | grep -c '^python' || true) python_rss_mib=$(ps -eo rss=,comm= | awk '$2 ~ /^python/ {s += $1} END {printf "%.0f", s / 1024}')"
    sleep 60
  done
}

{
  echo "label=${LABEL}"
  echo "pwd=${PWD}"
  echo "cache=${FLYONENOMICS_CACHE_DIR}"
  echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  uname -a || true
  echo "nproc=$(nproc 2>/dev/null || echo unknown)"
  lscpu 2>/dev/null | grep -E '^(Model name|Socket\(s\)|Core\(s\) per socket|Thread\(s\) per core|CPU\(s\)|NUMA node\(s\))' || grep -m1 'model name' /proc/cpuinfo || true
  grep -E '^(MemTotal|MemAvailable)' /proc/meminfo || true
  sample_usage > "results/${LABEL}/node-usage.log" 2>&1 &
  SAMPLER=$!
  trap 'kill "${SAMPLER}" 2>/dev/null || true' EXIT
  ensure_cc
  echo "cc=$(command -v gcc || command -v cc || echo none)"
  ensure_uv
  ensure_node
  echo "node=$(command -v node || echo none) $(node --version 2>/dev/null || true)"
  if [[ -d .git ]]; then
    # Stash drops the executable bit (100755 -> 100644, same bytes). Without
    # this every clean-tree guard in the job sees a dirty tree.
    git config core.fileMode false
    echo "tracked changes: $(git status --porcelain --untracked-files=no | wc -l | tr -d ' ')"
  fi
  echo "git=$(command -v git || echo none) $(git rev-parse HEAD 2>/dev/null || true)"
  uv --version
  uv sync --frozen
  echo "running: $*"
  set +e
  "$@"
  status=$?
  set -e
  if [[ -d runs && ! -e "results/${LABEL}/runs" ]]; then
    cp -a runs "results/${LABEL}/runs"
  fi
  echo "exit=${status}"
  echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  exit "${status}"
} 2>&1 | tee "${LOG}"
exit "${PIPESTATUS[0]}"
