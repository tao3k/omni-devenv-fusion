#!/usr/bin/env bash
# Compatibility wrapper: use Python implementation for dedup black-box probe.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/test_omni_agent_dedup_events.py" "$@"
