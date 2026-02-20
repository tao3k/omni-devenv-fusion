use std::sync::Arc;

use crate::channels::managed_commands::SLASH_SCOPE_BACKGROUND_SUBMIT as TELEGRAM_SLASH_SCOPE_BACKGROUND_SUBMIT;
use crate::channels::telegram::commands::parse_background_prompt;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::JobManager;

use super::super::super::observability::send_with_observability;
use super::super::slash_acl::ensure_slash_command_authorized;
use super::{
    EVENT_TELEGRAM_COMMAND_BACKGROUND_SUBMIT_FAILED_REPLIED,
    EVENT_TELEGRAM_COMMAND_BACKGROUND_SUBMIT_REPLIED,
};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_background_prompt_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    job_manager: &Arc<JobManager>,
    session_id: &str,
) -> bool {
    let Some(prompt) = parse_background_prompt(&msg.content) else {
        return false;
    };

    if !ensure_slash_command_authorized(channel, msg, TELEGRAM_SLASH_SCOPE_BACKGROUND_SUBMIT, "/bg")
        .await
    {
        return true;
    }

    match job_manager
        .submit(session_id, msg.recipient.clone(), prompt)
        .await
    {
        Ok(job_id) => {
            let ack = format!(
                "Queued background job `{job_id}`.\nUse `/job {job_id}` for status, `/jobs` for queue health."
            );
            send_with_observability(
                channel,
                &ack,
                &msg.recipient,
                "Failed to send background ack",
                Some(EVENT_TELEGRAM_COMMAND_BACKGROUND_SUBMIT_REPLIED),
                Some(&msg.session_key),
            )
            .await;
        }
        Err(error) => {
            let failure = format!("Failed to queue background job: {error}");
            send_with_observability(
                channel,
                &failure,
                &msg.recipient,
                "Failed to send background queue failure",
                Some(EVENT_TELEGRAM_COMMAND_BACKGROUND_SUBMIT_FAILED_REPLIED),
                Some(&msg.session_key),
            )
            .await;
        }
    }
    true
}
