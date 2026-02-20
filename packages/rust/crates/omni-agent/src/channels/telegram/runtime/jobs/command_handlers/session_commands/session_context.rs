use std::sync::Arc;

use crate::agent::Agent;
use crate::channels::managed_commands::{
    SLASH_SCOPE_SESSION_BUDGET as TELEGRAM_SLASH_SCOPE_SESSION_BUDGET,
    SLASH_SCOPE_SESSION_MEMORY as TELEGRAM_SLASH_SCOPE_SESSION_MEMORY,
    SLASH_SCOPE_SESSION_STATUS as TELEGRAM_SLASH_SCOPE_SESSION_STATUS,
};
use crate::channels::traits::{Channel, ChannelMessage};

use super::super::super::observability::send_with_observability;
use super::super::super::replies::{
    format_command_error_json, format_context_budget_not_found_json,
    format_context_budget_snapshot, format_context_budget_snapshot_json,
    format_memory_recall_not_found, format_memory_recall_not_found_json,
    format_memory_recall_not_found_telegram, format_memory_recall_snapshot,
    format_memory_recall_snapshot_json, format_memory_recall_snapshot_telegram,
    format_session_context_snapshot, format_session_context_snapshot_json,
};
use super::super::slash_acl::ensure_slash_command_authorized;
use super::{
    EVENT_TELEGRAM_COMMAND_SESSION_BUDGET_JSON_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_BUDGET_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_MEMORY_JSON_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_MEMORY_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_STATUS_JSON_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_STATUS_REPLIED,
};

use crate::channels::telegram::commands::{
    parse_session_context_budget_command, parse_session_context_memory_command,
    parse_session_context_status_command,
};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_session_context_status_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    agent: &Arc<Agent>,
    session_id: &str,
) -> bool {
    let Some(format) = parse_session_context_status_command(&msg.content) else {
        return false;
    };

    if !ensure_slash_command_authorized(
        channel,
        msg,
        TELEGRAM_SLASH_SCOPE_SESSION_STATUS,
        "/session",
    )
    .await
    {
        return true;
    }

    let command_event = if format.is_json() {
        EVENT_TELEGRAM_COMMAND_SESSION_STATUS_JSON_REPLIED
    } else {
        EVENT_TELEGRAM_COMMAND_SESSION_STATUS_REPLIED
    };
    let response = match (
        agent.inspect_context_window(session_id).await,
        agent.peek_context_window_backup(session_id).await,
    ) {
        (Ok(active), Ok(snapshot)) => {
            let partition_mode = channel
                .session_partition_mode()
                .unwrap_or_else(|| "unknown".to_string());
            if format.is_json() {
                format_session_context_snapshot_json(
                    session_id,
                    &msg.session_key,
                    &partition_mode,
                    active,
                    snapshot,
                )
            } else {
                format_session_context_snapshot(
                    session_id,
                    &msg.session_key,
                    &partition_mode,
                    active,
                    snapshot,
                )
            }
        }
        (Err(error), _) if format.is_json() => {
            format_command_error_json("session_context_status", &error.to_string())
        }
        (_, Err(error)) if format.is_json() => {
            format_command_error_json("session_context_status", &error.to_string())
        }
        (Err(error), _) => format!("Failed to inspect active session context: {error}"),
        (_, Err(error)) => format!("Failed to inspect saved session snapshot: {error}"),
    };
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send session context status response",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_session_context_budget_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    agent: &Arc<Agent>,
    session_id: &str,
) -> bool {
    let Some(format) = parse_session_context_budget_command(&msg.content) else {
        return false;
    };

    if !ensure_slash_command_authorized(
        channel,
        msg,
        TELEGRAM_SLASH_SCOPE_SESSION_BUDGET,
        "/session budget",
    )
    .await
    {
        return true;
    }

    let command_event = if format.is_json() {
        EVENT_TELEGRAM_COMMAND_SESSION_BUDGET_JSON_REPLIED
    } else {
        EVENT_TELEGRAM_COMMAND_SESSION_BUDGET_REPLIED
    };
    let response = match agent.inspect_context_budget_snapshot(session_id).await {
        Some(snapshot) if format.is_json() => format_context_budget_snapshot_json(snapshot),
        Some(snapshot) => format_context_budget_snapshot(snapshot),
        None if format.is_json() => format_context_budget_not_found_json(),
        None => "No context budget snapshot found for this session yet.\nRun at least one normal turn first (non-command message).".to_string(),
    };
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send session context budget response",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_session_context_memory_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    agent: &Arc<Agent>,
    session_id: &str,
) -> bool {
    let Some(format) = parse_session_context_memory_command(&msg.content) else {
        return false;
    };

    if !ensure_slash_command_authorized(
        channel,
        msg,
        TELEGRAM_SLASH_SCOPE_SESSION_MEMORY,
        "/session memory",
    )
    .await
    {
        return true;
    }

    let command_event = if format.is_json() {
        EVENT_TELEGRAM_COMMAND_SESSION_MEMORY_JSON_REPLIED
    } else {
        EVENT_TELEGRAM_COMMAND_SESSION_MEMORY_REPLIED
    };
    let runtime_status = agent.inspect_memory_runtime_status();
    let metrics = agent.inspect_memory_recall_metrics().await;
    let response = match agent.inspect_memory_recall_snapshot(session_id).await {
        Some(snapshot) if format.is_json() => {
            format_memory_recall_snapshot_json(snapshot, metrics, runtime_status)
        }
        Some(snapshot) if channel.name() == "telegram" => {
            format_memory_recall_snapshot_telegram(snapshot, metrics, runtime_status)
        }
        Some(snapshot) => format_memory_recall_snapshot(snapshot, metrics, runtime_status),
        None if format.is_json() => format_memory_recall_not_found_json(metrics, runtime_status),
        None if channel.name() == "telegram" => {
            format_memory_recall_not_found_telegram(runtime_status)
        }
        None => format_memory_recall_not_found(runtime_status),
    };
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send session context memory response",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}
