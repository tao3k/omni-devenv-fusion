use axum::{
    Json,
    extract::{Path, State},
    http::StatusCode,
};

use super::{
    MediaCall, MockTelegramMediaState, markdown_fallback::take_markdown_error_description,
};

pub(super) async fn handle_method(
    Path(method): Path<String>,
    State(state): State<MockTelegramMediaState>,
    Json(payload): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    if method == "sendMediaGroup" {
        let mut remaining_failures = state.fail_send_media_group_remaining.lock().await;
        if *remaining_failures > 0 {
            *remaining_failures -= 1;
            state.calls.lock().await.push(MediaCall { method, payload });
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({
                    "ok": false,
                    "error_code": 500,
                    "description": "internal error"
                })),
            );
        }
    }

    if let Some(description) = take_markdown_error_description(&payload, &state).await {
        state.calls.lock().await.push(MediaCall { method, payload });
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "ok": false,
                "error_code": 400,
                "description": description
            })),
        );
    }

    state.calls.lock().await.push(MediaCall { method, payload });
    (
        StatusCode::OK,
        Json(serde_json::json!({"ok": true, "result": {"message_id": 1}})),
    )
}
