#!/usr/bin/env bash
# Stage a git archive plus the cache files an engine run and pytest -m "not slow" read.
# Usage: scripts/camber/stage.sh [commit]
set -euo pipefail

CAMBER="${CAMBER:-${HOME}/.camber/bin/camber}"
COMMIT="$(git rev-parse "${1:-HEAD}")"
REPO_ROOT="$(git rev-parse --show-toplevel)"
GIT_COMMON="$(cd "$(git rev-parse --git-common-dir)" && pwd)"
if [[ -n "${FLYONENOMICS_CACHE_DIR:-}" ]]; then
  CACHE_ROOT="${FLYONENOMICS_CACHE_DIR}"
else
  CACHE_ROOT="$(cd "${GIT_COMMON}/../.cache" && pwd)"
fi
STASH="${STASH:-stash://roller/projects/flyonenomics/${COMMIT}}"

# Whole-tree clean guard: a job runs committed bytes only. The overlay below
# is taken from HEAD, so nothing uncommitted anywhere in this worktree can
# reach Stash.
if [[ -n "$(git -C "${REPO_ROOT}" status --porcelain --untracked-files=all)" ]]; then
  echo "working tree is not clean; commit before staging" >&2
  git -C "${REPO_ROOT}" status --short >&2
  exit 1
fi
OVERLAY_COMMIT="$(git -C "${REPO_ROOT}" rev-parse HEAD)"

# Engine run (dose-series v783): completeness, connectivity, model.py, annotations v2.1.0.
# Pytest -m "not slow" also opens v630 completeness, annotations v1.1.0, Zenodo
# post-counts, the figshare Buridan zip, the four CeTrAn sources, and the two
# Shiu notebooks (population literal check). shiu-archive (4.2 GB) is not staged:
# only validation.level1 test 1.2 reads it (pytest -m "not slow" skips that suite).
CACHE_FILES=(
  Drosophila_brain_model/Completeness_783.csv
  Drosophila_brain_model/Connectivity_783.parquet
  Drosophila_brain_model/model.py
  Drosophila_brain_model/example.ipynb
  Drosophila_brain_model/figures.ipynb
  Drosophila_brain_model/2023_03_23_completeness_630_final.csv
  annotations-v2.1.0.tsv
  annotations-v1.1.0.tsv
  zenodo-10676866/per_neuron_neuropil_count_post_783.feather
  github-importJnx5V7.zip
  CeTrAn/1f98ddd83366db53d4aabfa6f42b1153f8e1553d/functions.r
  CeTrAn/1f98ddd83366db53d4aabfa6f42b1153f8e1553d/utils.r
  CeTrAn/1f98ddd83366db53d4aabfa6f42b1153f8e1553d/angledev.r
  CeTrAn/1f98ddd83366db53d4aabfa6f42b1153f8e1553d/CeTrAn_fromxml_4.rgg
)

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/flyonenomics-camber.XXXXXX")"
cleanup() { rm -rf "${STAGE}"; }
trap cleanup EXIT

echo "commit ${COMMIT}"
echo "cache ${CACHE_ROOT}"
echo "stash ${STASH}"
echo "stage ${STAGE}"
echo "overlay ${OVERLAY_COMMIT}"

git -C "${REPO_ROOT}" archive --format=tar "${COMMIT}" | tar -C "${STAGE}" -xf -

missing=0
for rel in "${CACHE_FILES[@]}"; do
  src="${CACHE_ROOT}/${rel}"
  dest="${STAGE}/cache/${rel}"
  if [[ ! -f "${src}" ]]; then
    echo "missing cache file: ${src}" >&2
    missing=1
    continue
  fi
  mkdir -p "$(dirname "${dest}")"
  cp -p "${src}" "${dest}"
  echo "cache ${rel} $(wc -c < "${src}" | tr -d ' ') bytes"
done
if [[ "${missing}" -ne 0 ]]; then
  exit 1
fi

if [[ ! -f "${STAGE}/uv.lock" ]]; then
  echo "uv.lock absent from git archive of ${COMMIT}" >&2
  exit 1
fi

# Git archive has no .git. Binding and pytest call git rev-parse HEAD and
# git show <historical sha>:path, so plant the history of the staged commit
# and of main. Not a mirror: that would also upload refs/stash and every
# lane branch.
MAIN_REPO="$(cd "${GIT_COMMON}/.." && pwd)"
git init -q --bare "${STAGE}/.git"
git -C "${MAIN_REPO}" push -q "${STAGE}/.git" "${COMMIT}:refs/heads/staged" "refs/heads/main:refs/heads/main"
git --git-dir="${STAGE}/.git" --work-tree="${STAGE}" config --bool core.bare false
git --git-dir="${STAGE}/.git" --work-tree="${STAGE}" checkout --force "${COMMIT}"
planted="$(git --git-dir="${STAGE}/.git" --work-tree="${STAGE}" rev-parse HEAD)"
if [[ "${planted}" != "${COMMIT}" ]]; then
  echo "planted HEAD ${planted} != ${COMMIT}" >&2
  exit 1
fi
echo "git HEAD ${planted}"

# Overlay the Camber scripts as committed at HEAD. git archive of an older
# evaluation commit (bbb00c2, 4e0220f) does not contain scripts/camber/.
git -C "${REPO_ROOT}" archive --format=tar "${OVERLAY_COMMIT}" scripts/camber | tar -C "${STAGE}" -xf -

"${CAMBER}" stash cp -r \
  --exclude shiu-archive \
  --exclude cython \
  --exclude .venv \
  --exclude runs \
  --exclude l5-proof \
  --exclude scratch \
  --exclude uv \
  "${STAGE}" \
  "${STASH}"

echo "staged ${STASH}"
"${CAMBER}" stash ls "${STASH}"
"${CAMBER}" stash ls "${STASH}/cache" || true
