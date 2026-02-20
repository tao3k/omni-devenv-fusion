#!/usr/bin/env bash
# Compatibility wrapper: use Python memory benchmark runner.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/test_omni_agent_memory_benchmark.py" "$@"
