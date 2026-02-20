#!/usr/bin/env bash
set -euo pipefail

HOST="127.0.0.1"
PORT="3002"
RUNTIME_DIR="${PRJ_RUNTIME_DIR:-.run}"
PID_FILE="${RUNTIME_DIR}/omni-mcp-sse.pid"
LISTENER_PID_FILE=""
LOG_FILE="${RUNTIME_DIR}/logs/omni-mcp-sse.log"
HEALTH_TIMEOUT_SECS="25"
COOLDOWN_SECS="0.1"
STABILIZE_SECS="1"
NO_EMBEDDING="false"

usage() {
  cat <<'EOF'
Usage: restart-omni-mcp.sh [options]

Restart local MCP SSE server and wait until /health is ready.

Options:
  --host <host>                    Bind host (default: 127.0.0.1)
  --port <port>                    Bind port (default: 3002)
  --pid-file <path>                PID file path (default: $PRJ_RUNTIME_DIR/omni-mcp-sse.pid)
  --listener-pid-file <path>       Listener PID file path (default: <pid-file>.listener)
  --log-file <path>                Log file path (default: $PRJ_RUNTIME_DIR/logs/omni-mcp-sse.log)
  --health-timeout-secs <seconds>  Health wait timeout (default: 25)
  --cooldown-secs <seconds>        Delay after spawn before polling health (default: 0.1)
  --stabilize-secs <seconds>       Post-health stabilization window (default: 1)
  --no-embedding                   Start MCP with --no-embedding
  --help                           Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
  --host)
    HOST="$2"
    shift 2
    ;;
  --port)
    PORT="$2"
    shift 2
    ;;
  --pid-file)
    PID_FILE="$2"
    shift 2
    ;;
  --listener-pid-file)
    LISTENER_PID_FILE="$2"
    shift 2
    ;;
  --log-file)
    LOG_FILE="$2"
    shift 2
    ;;
  --health-timeout-secs)
    HEALTH_TIMEOUT_SECS="$2"
    shift 2
    ;;
  --cooldown-secs)
    COOLDOWN_SECS="$2"
    shift 2
    ;;
  --stabilize-secs)
    STABILIZE_SECS="$2"
    shift 2
    ;;
  --no-embedding)
    NO_EMBEDDING="true"
    shift
    ;;
  --help)
    usage
    exit 0
    ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
  esac
done

if [[ -z $LISTENER_PID_FILE ]]; then
  LISTENER_PID_FILE="${PID_FILE}.listener"
fi

mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LISTENER_PID_FILE")" "$(dirname "$LOG_FILE")"

is_non_negative_int() {
  [[ $1 =~ ^[0-9]+$ ]]
}

if ! is_non_negative_int "$HEALTH_TIMEOUT_SECS"; then
  echo "--health-timeout-secs must be a non-negative integer: ${HEALTH_TIMEOUT_SECS}" >&2
  exit 2
fi
if ! is_non_negative_int "$STABILIZE_SECS"; then
  echo "--stabilize-secs must be a non-negative integer: ${STABILIZE_SECS}" >&2
  exit 2
fi

terminate_pid() {
  local pid="$1"
  [[ -z $pid ]] && return 0
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi

  kill "$pid" 2>/dev/null || true
  for _ in {1..50}; do
    if kill -0 "$pid" 2>/dev/null; then
      sleep 0.1
    else
      break
    fi
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
}

list_listening_pids_for_port() {
  lsof -t -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | sort -u || true
}

is_descendant_of() {
  local candidate_pid="$1"
  local ancestor_pid="$2"
  local current="$candidate_pid"

  while [[ -n $current && $current != "1" ]]; do
    if [[ $current == "$ancestor_pid" ]]; then
      return 0
    fi
    current="$(ps -o ppid= -p "$current" 2>/dev/null | tr -d '[:space:]')"
  done

  return 1
}

NEW_PID=""
OWNED_LISTENER_PID=""
HEALTH_URL="http://${HOST}:${PORT}/health"
POLL_INTERVAL_SECS="0.1"

dump_diagnostics() {
  local reason="$1"
  local live_listeners
  live_listeners="$(list_listening_pids_for_port | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  echo "${reason}" >&2
  echo "restart context: host=${HOST} port=${PORT} pid_file=${PID_FILE} listener_pid_file=${LISTENER_PID_FILE} log_file=${LOG_FILE}" >&2
  if [[ -n $NEW_PID ]]; then
    ps -p "$NEW_PID" -o pid=,ppid=,stat=,etime=,command= 2>/dev/null >&2 || true
  fi
  if [[ -n $OWNED_LISTENER_PID ]]; then
    ps -p "$OWNED_LISTENER_PID" -o pid=,ppid=,stat=,etime=,command= 2>/dev/null >&2 || true
  fi
  echo "listening_pids(port=${PORT}): ${live_listeners:-none}" >&2
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null >&2 || true
  tail -n 80 "$LOG_FILE" >&2 || true
}

abort_restart() {
  local reason="$1"
  dump_diagnostics "$reason"
  if [[ -n $OWNED_LISTENER_PID ]]; then
    terminate_pid "$OWNED_LISTENER_PID"
  fi
  if [[ -n $NEW_PID ]]; then
    terminate_pid "$NEW_PID"
  fi
  rm -f "$PID_FILE" "$LISTENER_PID_FILE"
  exit 1
}

if [[ -f $LISTENER_PID_FILE ]]; then
  OLD_LISTENER_PID="$(cat "$LISTENER_PID_FILE" || true)"
  terminate_pid "$OLD_LISTENER_PID"
fi

if [[ -f $PID_FILE ]]; then
  OLD_PID="$(cat "$PID_FILE" || true)"
  terminate_pid "$OLD_PID"
fi

rm -f "$PID_FILE" "$LISTENER_PID_FILE"

# Guard against stale pid-file or manual launches occupying the target port.
while IFS= read -r bound_pid; do
  terminate_pid "$bound_pid"
done < <(list_listening_pids_for_port)

CMD=(uv run omni mcp --transport sse --host "$HOST" --port "$PORT")
if [[ $NO_EMBEDDING == "true" ]]; then
  CMD+=(--no-embedding)
fi

nohup "${CMD[@]}" >>"$LOG_FILE" 2>&1 &
NEW_PID=$!

sleep "$COOLDOWN_SECS"
END_TS=$((SECONDS + HEALTH_TIMEOUT_SECS))

while ((SECONDS < END_TS)); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    LISTEN_PIDS="$(list_listening_pids_for_port)"
    if [[ -z $LISTEN_PIDS ]]; then
      abort_restart "Health is ready but no listening process found on port ${PORT}."
    fi
    OWNED_LISTENER_PID=""
    while IFS= read -r listen_pid; do
      if [[ $listen_pid == "$NEW_PID" ]] || is_descendant_of "$listen_pid" "$NEW_PID"; then
        OWNED_LISTENER_PID="$listen_pid"
        break
      fi
    done <<<"$LISTEN_PIDS"
    if [[ -z $OWNED_LISTENER_PID ]]; then
      abort_restart "Health is ready but listener is not owned by restart root pid ${NEW_PID}. listening_pids=${LISTEN_PIDS}"
    fi

    if ((STABILIZE_SECS > 0)); then
      STABLE_END_TS=$((SECONDS + STABILIZE_SECS))
      while ((SECONDS < STABLE_END_TS)); do
        if ! kill -0 "$OWNED_LISTENER_PID" 2>/dev/null; then
          abort_restart "MCP listener exited during stabilization window (${STABILIZE_SECS}s)."
        fi
        if ! curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
          abort_restart "MCP did not remain healthy during stabilization window (${STABILIZE_SECS}s)."
        fi
        sleep "$POLL_INTERVAL_SECS"
      done
    fi

    echo "$NEW_PID" >"$PID_FILE"
    echo "$OWNED_LISTENER_PID" >"$LISTENER_PID_FILE"
    echo "MCP restarted (pid=${NEW_PID}, listener_pid=${OWNED_LISTENER_PID}, health=${HEALTH_URL}, stabilize_secs=${STABILIZE_SECS})."
    exit 0
  fi
  if ! kill -0 "$NEW_PID" 2>/dev/null; then
    abort_restart "MCP process exited before health was ready (pid=${NEW_PID})."
  fi
  sleep "$POLL_INTERVAL_SECS"
done

abort_restart "Timed out waiting for MCP health (${HEALTH_URL}) after ${HEALTH_TIMEOUT_SECS}s."
