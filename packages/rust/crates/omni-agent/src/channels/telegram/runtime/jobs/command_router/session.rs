use std::sync::Arc;

use crate::agent::Agent;
use crate::channels::traits::{Channel, ChannelMessage};

use super::super::command_handlers::session_commands::{
    try_handle_session_admin_command, try_handle_session_context_budget_command,
    try_handle_session_context_memory_command, try_handle_session_context_status_command,
    try_handle_session_feedback_command, try_handle_session_injection_command,
    try_handle_session_partition_command,
};
use super::super::command_handlers::session_control::{
    try_handle_help_command, try_handle_reset_context_command, try_handle_resume_context_command,
};

pub(super) async fn try_handle(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    agent: &Arc<Agent>,
    session_id: &str,
) -> bool {
    if try_handle_help_command(msg, channel).await {
        return true;
    }
    if try_handle_reset_context_command(msg, channel, agent, session_id).await {
        return true;
    }
    if try_handle_resume_context_command(msg, channel, agent, session_id).await {
        return true;
    }
    if try_handle_session_context_status_command(msg, channel, agent, session_id).await {
        return true;
    }
    if try_handle_session_context_budget_command(msg, channel, agent, session_id).await {
        return true;
    }
    if try_handle_session_context_memory_command(msg, channel, agent, session_id).await {
        return true;
    }
    if try_handle_session_feedback_command(msg, channel, agent, session_id).await {
        return true;
    }
    if try_handle_session_injection_command(msg, channel, agent, session_id).await {
        return true;
    }
    if try_handle_session_admin_command(msg, channel).await {
        return true;
    }
    if try_handle_session_partition_command(msg, channel).await {
        return true;
    }

    false
}
