#!/usr/bin/env bash
# Compatibility wrapper: use Python event-sequence checker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/check_omni_agent_event_sequence.py" "$@"
