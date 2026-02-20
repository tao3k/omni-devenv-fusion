#!/usr/bin/env bash
# Entry script for end-to-end agent channel acceptance checks.
#
# Positional args:
#   1: max_wait_secs
#   2: max_idle_secs
#   3: evolution_max_wait_secs
#   4: evolution_max_idle_secs
#   5: evolution_max_parallel
#   6: titles_csv
#   7: log_file
#   8: output_json
#   9: output_markdown
#  10: retries

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GROUP_ENV_FILE="${OMNI_TEST_GROUP_ENV_FILE:-.run/config/agent-channel-groups.env}"
if [ -f "${GROUP_ENV_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  source "${GROUP_ENV_FILE}"
  set +a
fi

MAX_WAIT_SECS="${1:-40}"
MAX_IDLE_SECS="${2:-25}"
EVOLUTION_MAX_WAIT_SECS="${3:-90}"
EVOLUTION_MAX_IDLE_SECS="${4:-60}"
EVOLUTION_MAX_PARALLEL="${5:-4}"
TITLES_CSV="${6:-Test1,Test2,Test3}"
LOG_FILE="${7:-.run/logs/omni-agent-webhook.log}"
OUTPUT_JSON="${8:-.run/reports/agent-channel-acceptance.json}"
OUTPUT_MARKDOWN="${9:-.run/reports/agent-channel-acceptance.md}"
RETRIES="${10:-2}"

exec python3 "${SCRIPT_DIR}/test_omni_agent_acceptance.py" \
  --titles "${TITLES_CSV}" \
  --log-file "${LOG_FILE}" \
  --max-wait "${MAX_WAIT_SECS}" \
  --max-idle-secs "${MAX_IDLE_SECS}" \
  --evolution-max-wait "${EVOLUTION_MAX_WAIT_SECS}" \
  --evolution-max-idle-secs "${EVOLUTION_MAX_IDLE_SECS}" \
  --evolution-max-parallel "${EVOLUTION_MAX_PARALLEL}" \
  --retries "${RETRIES}" \
  --output-json "${OUTPUT_JSON}" \
  --output-markdown "${OUTPUT_MARKDOWN}"
