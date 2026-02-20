use std::sync::Arc;

use crate::channels::traits::Channel;

pub(super) struct RenderedPayload {
    pub(super) payload: String,
    pub(super) render_mode: &'static str,
}

pub(super) fn render_telegram_command_payload(
    channel: &Arc<dyn Channel>,
    message: &str,
    event_name: Option<&str>,
) -> RenderedPayload {
    if channel.name() != "telegram" {
        return RenderedPayload {
            payload: message.to_string(),
            render_mode: "raw",
        };
    }

    if let Some(code_block) = render_json_code_block(message) {
        return RenderedPayload {
            payload: code_block,
            render_mode: "json_code_block",
        };
    }

    if is_json_command_event(event_name) {
        return RenderedPayload {
            payload: render_fallback_code_block(message),
            render_mode: "json_code_block_fallback",
        };
    }

    RenderedPayload {
        payload: message.to_string(),
        render_mode: "raw",
    }
}

fn render_json_code_block(message: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(message).ok()?;
    if !value.is_object() && !value.is_array() {
        return None;
    }
    let pretty = serde_json::to_string_pretty(&value).ok()?;
    Some(format!("```json\n{pretty}\n```"))
}

fn is_json_command_event(event_name: Option<&str>) -> bool {
    event_name
        .map(str::trim)
        .is_some_and(|name| name.ends_with("_json.replied"))
}

fn render_fallback_code_block(message: &str) -> String {
    let trimmed = message.trim();
    format!("```\n{trimmed}\n```")
}
