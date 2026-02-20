#!/usr/bin/env bash
# Run Telegram channel in webhook mode: ensure valkey, start ngrok, set webhook, run agent.
# Usage: TELEGRAM_BOT_TOKEN=xxx ./scripts/channel/agent-channel-webhook.sh [valkey_port]
# Requires: ngrok installed, ngrok authtoken (NGROK_AUTHTOKEN env or ngrok config add-authtoken)
#
# Allowed users: TELEGRAM_ALLOWED_USERS env, or telegram.allowed_users from settings.yaml.
# Examples: TELEGRAM_ALLOWED_USERS="*" (allow all), TELEGRAM_ALLOWED_USERS="username,12345" (allowlist).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"
LOG_FILE="${OMNI_CHANNEL_LOG_FILE:-.run/logs/omni-agent-webhook.log}"
mkdir -p "$(dirname "${LOG_FILE}")"

# Source .env if present (TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS, TELEGRAM_WEBHOOK_SECRET, etc.)
if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi

VALKEY_PORT="${VALKEY_PORT:-6379}"
if [ $# -gt 0 ]; then
  VALKEY_PORT="$1"
  shift
fi

bash "${SCRIPT_DIR}/valkey-start.sh" "${VALKEY_PORT}"
export VALKEY_URL="${VALKEY_URL:-redis://127.0.0.1:${VALKEY_PORT}/0}"

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "Error: TELEGRAM_BOT_TOKEN is required. Set it in env or .env" >&2
  echo "  export TELEGRAM_BOT_TOKEN=your_bot_token" >&2
  exit 1
fi

# Resolve webhook secret token:
#   1) TELEGRAM_WEBHOOK_SECRET env / .env
#   2) telegram.webhook_secret_token from settings
#   3) auto-generate ephemeral secret (local dev fallback)
if [ -z "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
  TELEGRAM_WEBHOOK_SECRET=$(uv run python -c "
from omni.foundation.config.settings import get_setting
print(get_setting('telegram.webhook_secret_token') or '')
" 2>/dev/null) || true
fi
if [ -z "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
  TELEGRAM_WEBHOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  echo "Warning: TELEGRAM_WEBHOOK_SECRET not set; generated ephemeral local secret token."
fi
export TELEGRAM_WEBHOOK_SECRET

if ! command -v ngrok >/dev/null 2>&1; then
  echo "Error: ngrok is required. Install: https://ngrok.com/download" >&2
  exit 1
fi

WEBHOOK_PORT="${WEBHOOK_PORT:-8081}"
NGROK_PID=""

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

cleanup() {
  if [ -n "$NGROK_PID" ]; then
    echo ""
    echo "Stopping ngrok (PID $NGROK_PID)..."
    kill "$NGROK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

ts_utc() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

on_bootstrap_error() {
  local exit_code="$1"
  local line_no="$2"
  local failed_cmd="$3"
  {
    echo "[$(ts_utc)] [agent-channel-webhook] bootstrap_failed exit_code=${exit_code} line=${line_no}"
    echo "[$(ts_utc)] [agent-channel-webhook] failed_command=${failed_cmd}"
  } | tee -a "${LOG_FILE}" >&2
}

trap 'on_bootstrap_error $? $LINENO "$BASH_COMMAND"' ERR

echo "Step 1/4: Valkey ready at ${VALKEY_URL}"
echo "Step 2/4: Starting ngrok tunnel on port $WEBHOOK_PORT..."
ngrok http "$WEBHOOK_PORT" >/tmp/ngrok.log 2>&1 &
NGROK_PID=$!
echo "  Waiting for ngrok to be ready..."
sleep 8

echo "Step 3/4: Fetching public URL from ngrok..."
NGROK_URL=""
for _ in $(seq 1 15); do
  # Try ngrok local API first (port 4040)
  NGROK_URL=$(curl -s --connect-timeout 2 http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if d.get('tunnels'):
        t = d['tunnels'][0]
        print(t.get('public_url', ''))
except Exception:
    pass
" 2>/dev/null) || true
  if [ -n "$NGROK_URL" ]; then
    break
  fi
  # Fallback: parse ngrok log for tunnel URL (exclude dashboard/signup pages)
  if [ -f /tmp/ngrok.log ]; then
    NGROK_URL=$(grep -oE 'https://[a-zA-Z0-9][-a-zA-Z0-9]*\.(ngrok-free\.app|ngrok\.io)\b' /tmp/ngrok.log 2>/dev/null | grep -v dashboard | head -1) || true
  fi
  if [ -n "$NGROK_URL" ]; then
    break
  fi
  sleep 1
done

# Reject invalid URLs (e.g. dashboard/signup when ngrok needs auth)
if [ -n "$NGROK_URL" ] && echo "$NGROK_URL" | grep -qE 'dashboard|signup'; then
  echo "Error: ngrok returned a signup URL (not authenticated)." >&2
  echo "  Set NGROK_AUTHTOKEN or run: ngrok config add-authtoken <your_token>" >&2
  echo "  Get token: https://dashboard.ngrok.com/get-started/your-authtoken" >&2
  kill "$NGROK_PID" 2>/dev/null || true
  exit 1
fi

if [ -z "$NGROK_URL" ]; then
  echo "Error: Could not get ngrok tunnel URL." >&2
  if [ -f /tmp/ngrok.log ] && grep -q -E 'signup|authtoken|dashboard\.ngrok' /tmp/ngrok.log 2>/dev/null; then
    echo "  ngrok requires authentication. Use either:" >&2
    echo "    export NGROK_AUTHTOKEN=<your_token>" >&2
    echo "    or: ngrok config add-authtoken <your_token>" >&2
    echo "  Get your token at: https://dashboard.ngrok.com/get-started/your-authtoken" >&2
  else
    echo "  Check /tmp/ngrok.log. Common causes:" >&2
    echo "  - ngrok needs auth: ngrok config add-authtoken <token>" >&2
    echo "  - port 4040 in use (ngrok inspector)" >&2
  fi
  if [ -f /tmp/ngrok.log ]; then
    echo "" >&2
    echo "  Last 10 lines of /tmp/ngrok.log:" >&2
    tail -10 /tmp/ngrok.log | sed 's/^/    /' >&2
  fi
  kill "$NGROK_PID" 2>/dev/null || true
  exit 1
fi

WEBHOOK_URL="${NGROK_URL}/telegram/webhook"
echo "  Public URL: $WEBHOOK_URL"

echo "  Setting Telegram webhook..."
SET_RESULT=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  --data-urlencode "url=${WEBHOOK_URL}" \
  --data-urlencode "secret_token=${TELEGRAM_WEBHOOK_SECRET}")
if echo "$SET_RESULT" | grep -q '"ok":true'; then
  echo "  Webhook set successfully."
else
  echo "  Webhook response: $SET_RESULT" >&2
fi

echo ""
echo "Step 4/4: Starting omni-agent channel (webhook mode)..."
echo "  VALKEY_URL='${VALKEY_URL}'"
echo "  TELEGRAM_ALLOWED_USERS='${TELEGRAM_ALLOWED_USERS:-}'"
echo "  TELEGRAM_ALLOWED_GROUPS='${TELEGRAM_ALLOWED_GROUPS:-}'"
echo "  TELEGRAM_WEBHOOK_SECRET='***${TELEGRAM_WEBHOOK_SECRET: -6}'"
export RUST_LOG="${RUST_LOG:-omni_agent=debug}"
export RUST_BACKTRACE="${RUST_BACKTRACE:-1}"
REPORT_FILE="${OMNI_CHANNEL_EXIT_REPORT_FILE:-.run/logs/omni-agent-webhook.exit.json}"
REPORT_JSONL="${OMNI_CHANNEL_EXIT_REPORT_JSONL:-.run/logs/omni-agent-webhook.exit.jsonl}"
echo "  RUST_LOG='${RUST_LOG}'"
echo "  RUST_BACKTRACE='${RUST_BACKTRACE}'"
echo "  VERBOSE='true'"
echo "  LOG_FILE='${LOG_FILE}' (tee)"
echo "  EXIT_REPORT='${REPORT_FILE}'"
echo "  EXIT_REPORT_JSONL='${REPORT_JSONL}'"
echo "  Press Ctrl+C to stop (ngrok will be stopped automatically)."
echo ""

# Bootstrap succeeded; from here on, process exit is handled by explicit channel exit reporting.
trap - ERR

python3 scripts/channel/agent_channel_runtime_monitor.py \
  --log-file "${LOG_FILE}" \
  --report-file "${REPORT_FILE}" \
  --report-jsonl "${REPORT_JSONL}" \
  -- \
  cargo run -p omni-agent -- channel \
  --mode webhook \
  --verbose \
  --webhook-bind "0.0.0.0:${WEBHOOK_PORT}" \
  --webhook-secret-token "${TELEGRAM_WEBHOOK_SECRET}" \
  --allowed-users "${TELEGRAM_ALLOWED_USERS:-}" \
  --allowed-groups "${TELEGRAM_ALLOWED_GROUPS:-}" \
  "$@"
