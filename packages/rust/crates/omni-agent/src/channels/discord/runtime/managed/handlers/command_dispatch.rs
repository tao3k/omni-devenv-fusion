use std::sync::Arc;

use crate::agent::{Agent, SessionRecallFeedbackDirection};
use crate::channels::managed_commands::{
    SLASH_SCOPE_BACKGROUND_SUBMIT, SLASH_SCOPE_JOB_STATUS, SLASH_SCOPE_JOBS_SUMMARY,
    SLASH_SCOPE_SESSION_BUDGET, SLASH_SCOPE_SESSION_FEEDBACK, SLASH_SCOPE_SESSION_MEMORY,
    SLASH_SCOPE_SESSION_STATUS,
};
use crate::channels::managed_runtime::turn::build_session_id;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::JobManager;

use super::super::parsing::{
    FeedbackDirection, ManagedCommand, ResumeCommand, parse_managed_command,
};
use super::super::replies::{
    format_command_error_json, format_context_budget_not_found_json,
    format_context_budget_snapshot, format_context_budget_snapshot_json, format_job_metrics,
    format_job_metrics_json, format_job_not_found, format_job_not_found_json, format_job_status,
    format_job_status_json, format_memory_recall_not_found, format_memory_recall_not_found_json,
    format_memory_recall_snapshot, format_memory_recall_snapshot_json,
    format_session_context_snapshot, format_session_context_snapshot_json, format_session_feedback,
    format_session_feedback_json, format_session_feedback_unavailable_json,
    format_session_partition_admin_required, format_session_partition_admin_required_json,
    format_session_partition_error_json, format_session_partition_status,
    format_session_partition_status_json, format_session_partition_updated,
    format_session_partition_updated_json, format_slash_help, format_slash_help_json,
};
use super::auth::{ensure_control_command_authorized, ensure_slash_command_authorized};
use super::events::{
    EVENT_DISCORD_COMMAND_BACKGROUND_SUBMIT_FAILED_REPLIED,
    EVENT_DISCORD_COMMAND_BACKGROUND_SUBMIT_REPLIED, EVENT_DISCORD_COMMAND_JOB_STATUS_JSON_REPLIED,
    EVENT_DISCORD_COMMAND_JOB_STATUS_REPLIED, EVENT_DISCORD_COMMAND_JOBS_SUMMARY_JSON_REPLIED,
    EVENT_DISCORD_COMMAND_JOBS_SUMMARY_REPLIED, EVENT_DISCORD_COMMAND_SESSION_BUDGET_JSON_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_BUDGET_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_FEEDBACK_JSON_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_FEEDBACK_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_MEMORY_JSON_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_MEMORY_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_PARTITION_JSON_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_PARTITION_REPLIED, EVENT_DISCORD_COMMAND_SESSION_RESET_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_RESUME_DROP_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_RESUME_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_RESUME_STATUS_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_STATUS_JSON_REPLIED,
    EVENT_DISCORD_COMMAND_SESSION_STATUS_REPLIED, EVENT_DISCORD_COMMAND_SLASH_HELP_JSON_REPLIED,
    EVENT_DISCORD_COMMAND_SLASH_HELP_REPLIED,
};
use super::send::send_response;

pub(in super::super::super) async fn handle_inbound_managed_command(
    agent: &Arc<Agent>,
    channel: &Arc<dyn Channel>,
    msg: &ChannelMessage,
    job_manager: &Arc<JobManager>,
) -> bool {
    let Some(command) = parse_managed_command(&msg.content) else {
        return false;
    };
    let session_id = build_session_id(&msg.channel, &msg.session_key);

    match command {
        ManagedCommand::Help(format) => {
            let (event, response) = if format.is_json() {
                (
                    EVENT_DISCORD_COMMAND_SLASH_HELP_JSON_REPLIED,
                    format_slash_help_json(),
                )
            } else {
                (
                    EVENT_DISCORD_COMMAND_SLASH_HELP_REPLIED,
                    format_slash_help(),
                )
            };
            send_response(channel, &msg.recipient, response, msg, event).await;
            true
        }
        ManagedCommand::Reset => {
            if !ensure_control_command_authorized(channel, msg, "/reset").await {
                return true;
            }
            let response = match agent.reset_context_window(&session_id).await {
                Ok(stats) => {
                    if stats.messages > 0 || stats.summary_segments > 0 {
                        format!(
                            "Session context reset.\nmessages_cleared={} summary_segments_cleared={}\nUse `/resume` to restore this session context.\nLong-term memory and knowledge stores are unchanged.",
                            stats.messages, stats.summary_segments
                        )
                    } else {
                        "Session context reset.\nmessages_cleared=0 summary_segments_cleared=0\nNo active context snapshot was created because this session is already empty.\nLong-term memory and knowledge stores are unchanged."
                            .to_string()
                    }
                }
                Err(error) => format!("Failed to reset session context: {error}"),
            };
            send_response(
                channel,
                &msg.recipient,
                response,
                msg,
                EVENT_DISCORD_COMMAND_SESSION_RESET_REPLIED,
            )
            .await;
            true
        }
        ManagedCommand::Resume(resume_command) => {
            let resume_requires_admin =
                matches!(resume_command, ResumeCommand::Restore | ResumeCommand::Drop);
            if resume_requires_admin {
                let command = match resume_command {
                    ResumeCommand::Restore => "/resume",
                    ResumeCommand::Status => "/resume status",
                    ResumeCommand::Drop => "/resume drop",
                };
                if !ensure_control_command_authorized(channel, msg, command).await {
                    return true;
                }
            }

            let (event, response) = match resume_command {
                ResumeCommand::Restore => (
                    EVENT_DISCORD_COMMAND_SESSION_RESUME_REPLIED,
                    match agent.resume_context_window(&session_id).await {
                        Ok(Some(stats)) => format!(
                            "Session context restored.\nmessages_restored={} summary_segments_restored={}",
                            stats.messages, stats.summary_segments
                        ),
                        Ok(None) => {
                            "No saved session context snapshot found. Use `/reset` or `/clear` first."
                                .to_string()
                        }
                        Err(error) => format!("Failed to restore session context: {error}"),
                    },
                ),
                ResumeCommand::Status => (
                    EVENT_DISCORD_COMMAND_SESSION_RESUME_STATUS_REPLIED,
                    match agent.peek_context_window_backup(&session_id).await {
                        Ok(Some(info)) => {
                            let mut lines = vec![
                                "Saved session context snapshot:".to_string(),
                                format!("messages={}", info.messages),
                                format!("summary_segments={}", info.summary_segments),
                            ];
                            if let Some(saved_at_unix_ms) = info.saved_at_unix_ms {
                                lines.push(format!("saved_at_unix_ms={saved_at_unix_ms}"));
                            }
                            if let Some(saved_age_secs) = info.saved_age_secs {
                                lines.push(format!("saved_age_secs={saved_age_secs}"));
                            }
                            lines.push("Use `/resume` to restore.".to_string());
                            lines.join("\n")
                        }
                        Ok(None) => "No saved session context snapshot found.".to_string(),
                        Err(error) => format!("Failed to inspect session context snapshot: {error}"),
                    },
                ),
                ResumeCommand::Drop => (
                    EVENT_DISCORD_COMMAND_SESSION_RESUME_DROP_REPLIED,
                    match agent.drop_context_window_backup(&session_id).await {
                        Ok(true) => "Saved session context snapshot dropped.".to_string(),
                        Ok(false) => "No saved session context snapshot found to drop.".to_string(),
                        Err(error) => {
                            format!("Failed to drop saved session context snapshot: {error}")
                        }
                    },
                ),
            };
            send_response(channel, &msg.recipient, response, msg, event).await;
            true
        }
        ManagedCommand::SessionStatus(format) => {
            if !ensure_slash_command_authorized(
                channel,
                msg,
                SLASH_SCOPE_SESSION_STATUS,
                "/session",
            )
            .await
            {
                return true;
            }
            let command_event = if format.is_json() {
                EVENT_DISCORD_COMMAND_SESSION_STATUS_JSON_REPLIED
            } else {
                EVENT_DISCORD_COMMAND_SESSION_STATUS_REPLIED
            };
            let response = match (
                agent.inspect_context_window(&session_id).await,
                agent.peek_context_window_backup(&session_id).await,
            ) {
                (Ok(active), Ok(snapshot)) => {
                    let partition_mode = channel
                        .session_partition_mode()
                        .unwrap_or_else(|| "unknown".to_string());
                    if format.is_json() {
                        format_session_context_snapshot_json(
                            &session_id,
                            &msg.session_key,
                            &partition_mode,
                            active,
                            snapshot,
                        )
                    } else {
                        format_session_context_snapshot(
                            &session_id,
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
            send_response(channel, &msg.recipient, response, msg, command_event).await;
            true
        }
        ManagedCommand::SessionBudget(format) => {
            if !ensure_slash_command_authorized(
                channel,
                msg,
                SLASH_SCOPE_SESSION_BUDGET,
                "/session budget",
            )
            .await
            {
                return true;
            }
            let command_event = if format.is_json() {
                EVENT_DISCORD_COMMAND_SESSION_BUDGET_JSON_REPLIED
            } else {
                EVENT_DISCORD_COMMAND_SESSION_BUDGET_REPLIED
            };
            let response = match agent.inspect_context_budget_snapshot(&session_id).await {
                Some(snapshot) if format.is_json() => format_context_budget_snapshot_json(snapshot),
                Some(snapshot) => format_context_budget_snapshot(snapshot),
                None if format.is_json() => format_context_budget_not_found_json(),
                None => "No context budget snapshot found for this session yet.\nRun at least one normal turn first (non-command message).".to_string(),
            };
            send_response(channel, &msg.recipient, response, msg, command_event).await;
            true
        }
        ManagedCommand::SessionMemory(format) => {
            if !ensure_slash_command_authorized(
                channel,
                msg,
                SLASH_SCOPE_SESSION_MEMORY,
                "/session memory",
            )
            .await
            {
                return true;
            }
            let command_event = if format.is_json() {
                EVENT_DISCORD_COMMAND_SESSION_MEMORY_JSON_REPLIED
            } else {
                EVENT_DISCORD_COMMAND_SESSION_MEMORY_REPLIED
            };
            let runtime_status = agent.inspect_memory_runtime_status();
            let metrics = agent.inspect_memory_recall_metrics().await;
            let response = match agent.inspect_memory_recall_snapshot(&session_id).await {
                Some(snapshot) if format.is_json() => {
                    format_memory_recall_snapshot_json(snapshot, metrics, runtime_status)
                }
                Some(snapshot) => format_memory_recall_snapshot(snapshot, metrics, runtime_status),
                None if format.is_json() => {
                    format_memory_recall_not_found_json(metrics, runtime_status)
                }
                None => format_memory_recall_not_found(runtime_status),
            };
            send_response(channel, &msg.recipient, response, msg, command_event).await;
            true
        }
        ManagedCommand::SessionFeedback(command) => {
            if !ensure_slash_command_authorized(
                channel,
                msg,
                SLASH_SCOPE_SESSION_FEEDBACK,
                "/session feedback",
            )
            .await
            {
                return true;
            }
            let command_event = if command.format.is_json() {
                EVENT_DISCORD_COMMAND_SESSION_FEEDBACK_JSON_REPLIED
            } else {
                EVENT_DISCORD_COMMAND_SESSION_FEEDBACK_REPLIED
            };
            let direction = match command.direction {
                FeedbackDirection::Up => SessionRecallFeedbackDirection::Up,
                FeedbackDirection::Down => SessionRecallFeedbackDirection::Down,
            };
            let response = match agent
                .apply_session_recall_feedback(&session_id, direction)
                .await
            {
                Some(update) if command.format.is_json() => format_session_feedback_json(
                    direction,
                    update.previous_bias,
                    update.updated_bias,
                ),
                Some(update) => {
                    format_session_feedback(direction, update.previous_bias, update.updated_bias)
                }
                None if command.format.is_json() => format_session_feedback_unavailable_json(),
                None => {
                    "Session recall feedback is unavailable because memory is disabled.".to_string()
                }
            };
            send_response(channel, &msg.recipient, response, msg, command_event).await;
            true
        }
        ManagedCommand::SessionPartition(command) => {
            let command_event = if command.format.is_json() {
                EVENT_DISCORD_COMMAND_SESSION_PARTITION_JSON_REPLIED
            } else {
                EVENT_DISCORD_COMMAND_SESSION_PARTITION_REPLIED
            };
            let current_mode = channel
                .session_partition_mode()
                .unwrap_or_else(|| "unknown".to_string());
            let sender_is_admin =
                channel.is_authorized_for_control_command(&msg.sender, &msg.content);
            if !sender_is_admin {
                let response = if command.format.is_json() {
                    format_session_partition_admin_required_json(&msg.sender, &current_mode)
                } else {
                    format_session_partition_admin_required(&msg.sender, &current_mode)
                };
                send_response(channel, &msg.recipient, response, msg, command_event).await;
                return true;
            }

            let response = match command.mode {
                None if command.format.is_json() => {
                    format_session_partition_status_json(&current_mode)
                }
                None => format_session_partition_status(&current_mode),
                Some(mode) => {
                    let requested_mode = mode.to_string();
                    match channel.set_session_partition_mode(&requested_mode) {
                        Ok(()) => {
                            let updated_mode = channel
                                .session_partition_mode()
                                .unwrap_or_else(|| requested_mode.clone());
                            if command.format.is_json() {
                                format_session_partition_updated_json(
                                    &requested_mode,
                                    &updated_mode,
                                )
                            } else {
                                format_session_partition_updated(&requested_mode, &updated_mode)
                            }
                        }
                        Err(error) if command.format.is_json() => {
                            format_session_partition_error_json(&requested_mode, &error.to_string())
                        }
                        Err(error) => format!(
                            "Failed to update session partition mode.\nrequested_mode={requested_mode}\nerror={error}"
                        ),
                    }
                }
            };
            send_response(channel, &msg.recipient, response, msg, command_event).await;
            true
        }
        ManagedCommand::JobStatus { job_id, format } => {
            if !ensure_slash_command_authorized(channel, msg, SLASH_SCOPE_JOB_STATUS, "/job").await
            {
                return true;
            }
            let command_event = if format.is_json() {
                EVENT_DISCORD_COMMAND_JOB_STATUS_JSON_REPLIED
            } else {
                EVENT_DISCORD_COMMAND_JOB_STATUS_REPLIED
            };
            let response = match job_manager.get_status(&job_id).await {
                Some(snapshot) if format.is_json() => format_job_status_json(&snapshot),
                Some(snapshot) => format_job_status(&snapshot),
                None if format.is_json() => format_job_not_found_json(&job_id),
                None => format_job_not_found(&job_id),
            };
            send_response(channel, &msg.recipient, response, msg, command_event).await;
            true
        }
        ManagedCommand::JobsSummary(format) => {
            if !ensure_slash_command_authorized(channel, msg, SLASH_SCOPE_JOBS_SUMMARY, "/jobs")
                .await
            {
                return true;
            }
            let command_event = if format.is_json() {
                EVENT_DISCORD_COMMAND_JOBS_SUMMARY_JSON_REPLIED
            } else {
                EVENT_DISCORD_COMMAND_JOBS_SUMMARY_REPLIED
            };
            let metrics = job_manager.metrics().await;
            let response = if format.is_json() {
                format_job_metrics_json(&metrics)
            } else {
                format_job_metrics(&metrics)
            };
            send_response(channel, &msg.recipient, response, msg, command_event).await;
            true
        }
        ManagedCommand::BackgroundSubmit(prompt) => {
            if !ensure_slash_command_authorized(channel, msg, SLASH_SCOPE_BACKGROUND_SUBMIT, "/bg")
                .await
            {
                return true;
            }
            let response = match job_manager
                .submit(&session_id, msg.recipient.clone(), prompt)
                .await
            {
                Ok(job_id) => format!(
                    "Queued background job `{job_id}`.\nUse `/job {job_id}` for status, `/jobs` for queue health."
                ),
                Err(error) => format!("Failed to queue background job: {error}"),
            };
            let event = if response.starts_with("Queued background job") {
                EVENT_DISCORD_COMMAND_BACKGROUND_SUBMIT_REPLIED
            } else {
                EVENT_DISCORD_COMMAND_BACKGROUND_SUBMIT_FAILED_REPLIED
            };
            send_response(channel, &msg.recipient, response, msg, event).await;
            true
        }
    }
}
