#!/usr/bin/env bash
# Compatibility wrapper: use Python implementation for concurrent dual-session black-box probe.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/test_omni_agent_concurrent_sessions.py" "$@"
