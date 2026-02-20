use std::sync::Arc;

use crate::channels::traits::Channel;

use super::json_summary::{
    optional_bool_token, optional_u64_token, optional_usize_token, summarize_json_reply,
};
use super::preview::log_preview;
use super::render::render_telegram_command_payload;

pub(in crate::channels::telegram::runtime::jobs) async fn send_with_observability(
    channel: &Arc<dyn Channel>,
    message: &str,
    recipient: &str,
    error_context: &str,
    event_name: Option<&str>,
    session_key: Option<&str>,
) {
    let rendered = render_telegram_command_payload(channel, message, event_name);
    let outbound = rendered.payload;
    match channel.send(&outbound, recipient).await {
        Ok(()) => {
            tracing::info!(r#"→ Bot: "{preview}""#, preview = log_preview(&outbound));
            if let Some(event_name) = event_name {
                tracing::info!(
                    event = event_name,
                    session_key = session_key.unwrap_or(""),
                    recipient,
                    channel_name = channel.name(),
                    render_mode = rendered.render_mode,
                    reply_chars = outbound.chars().count(),
                    reply_bytes = outbound.len(),
                    "telegram command reply sent"
                );
                if let Some(json_summary) = summarize_json_reply(message) {
                    tracing::info!(
                        event = event_name,
                        session_key = session_key.unwrap_or(""),
                        recipient,
                        json_kind = json_summary.kind.as_deref().unwrap_or(""),
                        json_available = optional_bool_token(json_summary.available),
                        json_status = json_summary.status.as_deref().unwrap_or(""),
                        json_found = optional_bool_token(json_summary.found),
                        json_decision = json_summary.decision.as_deref().unwrap_or(""),
                        json_logical_session_id =
                            json_summary.logical_session_id.as_deref().unwrap_or(""),
                        json_partition_key = json_summary.partition_key.as_deref().unwrap_or(""),
                        json_partition_mode = json_summary.partition_mode.as_deref().unwrap_or(""),
                        json_context_mode = json_summary.context_mode.as_deref().unwrap_or(""),
                        json_saved_snapshot_status =
                            json_summary.saved_snapshot_status.as_deref().unwrap_or(""),
                        json_runtime_backend_ready =
                            optional_bool_token(json_summary.runtime_backend_ready),
                        json_runtime_active_backend =
                            json_summary.runtime_active_backend.as_deref().unwrap_or(""),
                        json_runtime_startup_load_status = json_summary
                            .runtime_startup_load_status
                            .as_deref()
                            .unwrap_or(""),
                        json_result_recalled_injected =
                            optional_u64_token(json_summary.result_recalled_injected),
                        json_query_tokens = optional_u64_token(json_summary.query_tokens),
                        json_override_admin_count =
                            optional_usize_token(json_summary.override_admin_count),
                        json_keys = json_summary.keys,
                        "telegram command reply json summary"
                    );
                }
            }
        }
        Err(error) => tracing::error!("{error_context}: {error}"),
    }
}
