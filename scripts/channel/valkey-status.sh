#!/usr/bin/env bash

set -euo pipefail

PORT="${1:-6379}"

RUNTIME_DIR="${PRJ_RUNTIME_DIR:-.run}/valkey"
PIDFILE="$RUNTIME_DIR/valkey-${PORT}.pid"
URL="redis://127.0.0.1:${PORT}/0"

if valkey-cli -u "$URL" ping >/dev/null 2>&1; then
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Valkey is running on ${PORT} (pid $(cat "$PIDFILE"))."
  else
    echo "Valkey is reachable on ${PORT} (pidfile not managed by just)."
  fi
  echo "PONG"
  exit 0
fi

echo "Valkey is not running on ${PORT}."
exit 1
