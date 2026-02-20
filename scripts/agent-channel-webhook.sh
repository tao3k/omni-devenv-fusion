#!/usr/bin/env bash
# Compatibility wrapper. Use scripts/channel/agent-channel-webhook.sh directly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/channel/agent-channel-webhook.sh" "$@"
