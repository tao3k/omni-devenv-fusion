#!/usr/bin/env bash
set -euo pipefail

QUERY="${1:-architecture}"
RUNS="${2:-5}"
WARM_RUNS="${3:-2}"
PROFILE="${4:-debug}"       # debug | release
BUILD_MODE="${5:-no-build}" # no-build | build

cmd=(
  uv run python scripts/benchmark_wendao_search.py
  --root .
  --query "${QUERY}"
  --runs "${RUNS}"
  --warm-runs "${WARM_RUNS}"
)

case "${PROFILE}" in
debug) ;;
release) cmd+=(--release) ;;
*)
  echo "Invalid profile: ${PROFILE} (expected: debug|release)" >&2
  exit 2
  ;;
esac

case "${BUILD_MODE}" in
no-build) cmd+=(--no-build) ;;
build) ;;
*)
  echo "Invalid build mode: ${BUILD_MODE} (expected: no-build|build)" >&2
  exit 2
  ;;
esac

"${cmd[@]}"
