#!/usr/bin/env bash
set -euo pipefail

STEM="${1:-architecture}"
RUNS="${2:-5}"
WARM_RUNS="${3:-2}"
PROFILE="${4:-debug}"       # debug | release
BUILD_MODE="${5:-no-build}" # no-build | build
SUBGRAPH_MODE="${6:-auto}"  # auto | disabled | force

cmd=(
  uv run python scripts/benchmark_wendao_related.py
  --root .
  --stem "${STEM}"
  --runs "${RUNS}"
  --warm-runs "${WARM_RUNS}"
  --ppr-subgraph-mode "${SUBGRAPH_MODE}"
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

case "${SUBGRAPH_MODE}" in
auto | disabled | force) ;;
*)
  echo "Invalid subgraph mode: ${SUBGRAPH_MODE} (expected: auto|disabled|force)" >&2
  exit 2
  ;;
esac

"${cmd[@]}"
