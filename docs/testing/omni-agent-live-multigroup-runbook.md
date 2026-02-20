# Omni-Agent Live Multi-Group Runbook

This runbook standardizes live black-box validation on three real Telegram groups (`Test1`, `Test2`, `Test3`).

## 1. Preconditions

1. `omni-agent` webhook runtime is already running.
2. Runtime logs are written to `.run/logs/omni-agent-webhook.log` (or a known path).
3. You have posted at least one message (for example `/help`) in each target group so the runtime log contains `chat_id` + `chat_title`.

## 2. Capture Group Profile

```bash
python3 scripts/channel/capture_telegram_group_profile.py \
  --titles Test1,Test2,Test3 \
  --log-file .run/logs/omni-agent-webhook.log \
  --output-json .run/config/agent-channel-groups.json \
  --output-env .run/config/agent-channel-groups.env
```

Load the generated profile:

```bash
set -a
source .run/config/agent-channel-groups.env
set +a
```

## 3. Run Live Session Isolation Matrix

```bash
python3 scripts/channel/test_omni_agent_session_matrix.py \
  --chat-id "$OMNI_TEST_CHAT_ID" \
  --chat-b "$OMNI_TEST_CHAT_B" \
  --chat-c "$OMNI_TEST_CHAT_C" \
  --user-a "$OMNI_TEST_USER_ID" \
  --user-b "$OMNI_TEST_USER_B" \
  --user-c "$OMNI_TEST_USER_C" \
  --max-wait 45 \
  --max-idle-secs 30 \
  --output-json .run/reports/agent-channel-session-matrix-live.json \
  --output-markdown .run/reports/agent-channel-session-matrix-live.md
```

Pass condition:

- `overall_passed=true`
- all steps pass
- three distinct group IDs are present.

## 4. Run Live Memory Evolution DAG

```bash
python3 scripts/channel/test_omni_agent_complex_scenarios.py \
  --dataset scripts/channel/fixtures/memory_evolution_complex_scenarios.json \
  --scenario memory_self_correction_high_complexity_dag \
  --chat-a "$OMNI_TEST_CHAT_ID" \
  --chat-b "$OMNI_TEST_CHAT_B" \
  --chat-c "$OMNI_TEST_CHAT_C" \
  --user-a "$OMNI_TEST_USER_ID" \
  --user-b "$OMNI_TEST_USER_B" \
  --user-c "$OMNI_TEST_USER_C" \
  --max-wait 90 \
  --max-idle-secs 40 \
  --max-parallel 1 \
  --output-json .run/reports/omni-agent-memory-evolution-live.json \
  --output-markdown .run/reports/omni-agent-memory-evolution-live.md
```

Pass condition:

- scenario passes
- quality gates meet the dataset thresholds.

## 5. Run Live Trace Reconstruction

```bash
python3 scripts/channel/reconstruct_omni_agent_trace.py \
  .run/logs/omni-agent-webhook.log \
  --session-id "telegram:${OMNI_TEST_CHAT_ID}" \
  --max-events 4000 \
  --required-stage route \
  --required-stage injection \
  --required-stage reflection \
  --required-stage memory \
  --json-out .run/reports/omni-agent-trace-reconstruction-live.json \
  --markdown-out .run/reports/omni-agent-trace-reconstruction-live.md
```

Pass condition:

- required stages present
- quality score is `100.0`
- no reconstruction errors.

## 6. Release Artifact Checklist

Attach these files to the release/test evidence set:

1. `.run/config/agent-channel-groups.json`
2. `.run/reports/agent-channel-session-matrix-live.json`
3. `.run/reports/omni-agent-memory-evolution-live.json`
4. `.run/reports/omni-agent-trace-reconstruction-live.json`
