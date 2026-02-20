use std::sync::Arc;

use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::JobManager;

use super::super::command_handlers::background_jobs::{
    try_handle_background_prompt_command, try_handle_job_status_command,
    try_handle_jobs_summary_command,
};

pub(super) async fn try_handle(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    job_manager: &Arc<JobManager>,
    session_id: &str,
) -> bool {
    if try_handle_job_status_command(msg, channel, job_manager).await {
        return true;
    }
    if try_handle_jobs_summary_command(msg, channel, job_manager).await {
        return true;
    }
    if try_handle_background_prompt_command(msg, channel, job_manager, session_id).await {
        return true;
    }

    false
}
