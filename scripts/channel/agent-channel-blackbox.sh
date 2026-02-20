#!/usr/bin/env bash
# Compatibility wrapper: use Python implementation for black-box webhook probe.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/agent_channel_blackbox.py" "$@"
