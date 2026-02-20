#!/usr/bin/env bash

set -euo pipefail

PORT="${1:-6379}"

RUNTIME_DIR="${PRJ_RUNTIME_DIR:-.run}/valkey"
PIDFILE="$RUNTIME_DIR/valkey-${PORT}.pid"
URL="redis://127.0.0.1:${PORT}/0"

if valkey-cli -u "$URL" ping >/dev/null 2>&1; then
  valkey-cli -u "$URL" shutdown nosave >/dev/null 2>&1 || true
  sleep 0.2
fi

if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE")"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" >/dev/null 2>&1 || true
  fi
  rm -f "$PIDFILE"
fi

if valkey-cli -u "$URL" ping >/dev/null 2>&1; then
  echo "Warning: Valkey is still reachable at $URL (managed by another process)." >&2
  exit 1
fi

echo "Valkey stopped on port ${PORT}."
