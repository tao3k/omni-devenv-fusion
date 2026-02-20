#!/usr/bin/env bash
# Compatibility wrapper: use Python implementation for session matrix black-box probes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GROUP_ENV_FILE="${OMNI_TEST_GROUP_ENV_FILE:-.run/config/agent-channel-groups.env}"
if [ -f "${GROUP_ENV_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  source "${GROUP_ENV_FILE}"
  set +a
fi

exec python3 "${SCRIPT_DIR}/test_omni_agent_session_matrix.py" "$@"
