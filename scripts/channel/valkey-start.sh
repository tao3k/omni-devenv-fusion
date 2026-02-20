#!/usr/bin/env bash

set -euo pipefail

PORT="${1:-6379}"

if ! command -v valkey-server >/dev/null 2>&1; then
  echo "Error: valkey-server not found in PATH." >&2
  exit 1
fi
if ! command -v valkey-cli >/dev/null 2>&1; then
  echo "Error: valkey-cli not found in PATH." >&2
  exit 1
fi

RUNTIME_DIR="${PRJ_RUNTIME_DIR:-.run}/valkey"
mkdir -p "$RUNTIME_DIR"
PIDFILE="$RUNTIME_DIR/valkey-${PORT}.pid"
LOGFILE="$RUNTIME_DIR/valkey-${PORT}.log"
URL="redis://127.0.0.1:${PORT}/0"

if valkey-cli -u "$URL" ping >/dev/null 2>&1; then
  echo "Valkey is already reachable at $URL."
  exit 0
fi

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Valkey already running on ${PORT} (pid $(cat "$PIDFILE"))."
  valkey-cli -u "$URL" ping || true
  exit 0
fi

echo "Starting Valkey on port ${PORT}..."
valkey-server \
  --port "$PORT" \
  --bind 127.0.0.1 \
  --daemonize yes \
  --dir "$RUNTIME_DIR" \
  --pidfile "$PIDFILE" \
  --logfile "$LOGFILE"

sleep 0.2
valkey-cli -u "$URL" ping
echo "Valkey started. pidfile=$PIDFILE logfile=$LOGFILE"
