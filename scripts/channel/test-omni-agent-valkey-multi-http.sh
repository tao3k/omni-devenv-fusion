#!/usr/bin/env bash
# Compatibility wrapper: use Python Valkey suite runner (multi-http).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/test_omni_agent_valkey_suite.py" --suite multi-http "$@"
