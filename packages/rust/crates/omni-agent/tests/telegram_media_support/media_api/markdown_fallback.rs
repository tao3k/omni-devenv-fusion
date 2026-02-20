use super::MockTelegramMediaState;

pub(super) fn payload_markdown_mode(payload: &serde_json::Value) -> Option<&str> {
    payload
        .get("parse_mode")
        .and_then(serde_json::Value::as_str)
        .or_else(|| {
            payload
                .get("media")
                .and_then(serde_json::Value::as_array)
                .and_then(|media| media.first())
                .and_then(|first| first.get("parse_mode"))
                .and_then(serde_json::Value::as_str)
        })
}

pub(super) async fn take_markdown_error_description(
    payload: &serde_json::Value,
    state: &MockTelegramMediaState,
) -> Option<String> {
    if payload_markdown_mode(payload) != Some("MarkdownV2") {
        return None;
    }
    state.first_markdown_error.lock().await.take()
}
