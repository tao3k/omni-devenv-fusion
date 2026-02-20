#!/usr/bin/env bash
# Run Telegram channel in polling mode with local Valkey bootstrapping.
# Usage: TELEGRAM_BOT_TOKEN=xxx ./scripts/channel/agent-channel-polling.sh [valkey_port]
# Allowed users: TELEGRAM_ALLOWED_USERS env, or telegram.allowed_users from settings.yaml.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# Source .env if present
if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi

VALKEY_PORT="${VALKEY_PORT:-6379}"
if [ $# -gt 0 ] && [[ $1 =~ ^[0-9]+$ ]]; then
  VALKEY_PORT="$1"
  shift
fi

bash "${SCRIPT_DIR}/valkey-start.sh" "${VALKEY_PORT}"
export VALKEY_URL="${VALKEY_URL:-redis://127.0.0.1:${VALKEY_PORT}/0}"

# Resolve allowed users/groups: env > settings.yaml
if [ -z "${TELEGRAM_ALLOWED_USERS:-}" ]; then
  TELEGRAM_ALLOWED_USERS=$(uv run python -c "
from omni.foundation.config.settings import get_setting
print(get_setting('telegram.allowed_users') or '')
" 2>/dev/null) || true
fi
if [ -z "${TELEGRAM_ALLOWED_GROUPS:-}" ]; then
  TELEGRAM_ALLOWED_GROUPS=$(uv run python -c "
from omni.foundation.config.settings import get_setting
print(get_setting('telegram.allowed_groups') or '')
" 2>/dev/null) || true
fi

echo "Starting Telegram channel (polling mode)..."
echo "VALKEY_URL='${VALKEY_URL}'"
echo "TELEGRAM_ALLOWED_USERS='${TELEGRAM_ALLOWED_USERS:-}' TELEGRAM_ALLOWED_GROUPS='${TELEGRAM_ALLOWED_GROUPS:-}'"

cargo run -p omni-agent -- channel \
  --mode polling \
  --allowed-users "${TELEGRAM_ALLOWED_USERS:-}" \
  --allowed-groups "${TELEGRAM_ALLOWED_GROUPS:-}" \
  "$@"
