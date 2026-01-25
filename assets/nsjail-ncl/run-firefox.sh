#!/usr/bin/env bash
# run-firefox.sh - Firefox isolation script using NSJail
#
# Usage: ./run-firefox.sh [--url URL]
#
# Options:
#   --url URL    Open specific URL in Firefox

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NSJAIL_CONFIG_DIR="${SCRIPT_DIR}/nsjail-configs"
FIREFOX_CONFIG="${NSJAIL_CONFIG_DIR}/examples/firefox.ncl"
NSJAIL_BIN="${NSJAIL_BIN:-nsjail}"
LOG_FILE="/var/log/nsjail-firefox.log"
UID="${UID:-1000}"
GID="${GID:-1000}"

# Parse arguments
URL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
  --url)
    URL="$2"
    shift 2
    ;;
  --url=*)
    URL="${1#*=}"
    shift
    ;;
  --help | -h)
    echo "Usage: $0 [--url URL]"
    echo ""
    echo "Options:"
    echo "  --url URL    Open specific URL in Firefox"
    echo "  --help       Show this help message"
    exit 0
    ;;
  *)
    echo "Unknown option: $1"
    echo "Use --help for usage information"
    exit 1
    ;;
  esac
done

# Override UV_PROJECT_ENVIRONMENT to avoid devenv issues
if [[ -n ${UV_PROJECT_ENVIRONMENT:-} ]]; then
  echo "Overriding UV_PROJECT_ENVIRONMENT for isolation"
  export UV_PROJECT_ENVIRONMENT=""
fi

# Check dependencies
check_dependency() {
  if ! command -v "$1" &>/dev/null; then
    echo "Error: $1 is not installed" >&2
    exit 1
  fi
}

check_dependency "nickel"
check_dependency "$NSJAIL_BIN"

# Generate nsjail config if needed
generate_config() {
  echo "Generating NSJail configuration..."
  nickel export -f yaml "$FIREFOX_CONFIG" >/tmp/nsjail-firefox.cfg
}

# Create required directories
setup_directories() {
  mkdir -p /var/log
  mkdir -p "$(dirname "$LOG_FILE")"
  mkdir -p /run/user/1000
}

# Pre-flight checks
preflight_checks() {
  # Check if X11 is running
  if [[ -z ${DISPLAY:-} ]]; then
    echo "Warning: DISPLAY is not set. X11 forwarding may not work."
  fi

  # Check for Firefox
  if ! command -v firefox &>/dev/null; then
    echo "Error: Firefox is not installed" >&2
    exit 1
  fi

  # Check for X11 socket
  if [[ ! -d "/tmp/.X11-unix" ]]; then
    echo "Error: X11 socket not found at /tmp/.X11-unix" >&2
    exit 1
  fi
}

# Build nsjail command
build_nsjail_cmd() {
  local cmd=("$NSJAIL_BIN")

  # Mode
  cmd+=("-M" "ONCE")

  # Configuration file
  cmd+=("-C" "/tmp/nsjail-firefox.cfg")

  # Logging
  cmd+=("-l" "$LOG_FILE")
  cmd+=("--log_level" "info")

  # UID/GID mapping
  cmd+=("--uid" "$UID")
  cmd+=("--gid" "$GID")

  # Skip capability checks for GUI apps
  cmd+=("--skip_seccomp_compiler_check")

  # Working directory
  cmd+=("--cwd" "/user/home")

  # Command
  local firefox_cmd=("/usr/bin/firefox" "--no-remote" "--new-instance")

  # Add URL if specified
  if [[ -n $URL ]]; then
    firefox_cmd+=("$URL")
  else
    firefox_cmd+=("-P" "default")
  fi

  cmd+=("--" "${firefox_cmd[@]}")

  echo "${cmd[@]}"
}

# Main execution
main() {
  echo "=== Firefox NSJail Isolation ==="
  echo ""

  setup_directories
  preflight_checks
  generate_config

  echo "Starting Firefox with NSJail isolation..."
  echo "Log file: $LOG_FILE"
  echo ""

  # Execute nsjail
  eval "$(build_nsjail_cmd)"

  echo ""
  echo "Firefox terminated."
}

main "$@"
