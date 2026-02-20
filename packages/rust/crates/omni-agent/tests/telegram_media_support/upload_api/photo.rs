use axum::{Json, extract::Multipart, extract::State, http::StatusCode};

use super::{MockTelegramUploadState, UploadCall};

pub(super) async fn handle_upload_photo(
    State(state): State<MockTelegramUploadState>,
    mut multipart: Multipart,
) -> (StatusCode, Json<serde_json::Value>) {
    let mut field_names = Vec::new();
    let mut text_fields = serde_json::Map::new();

    while let Ok(Some(field)) = multipart.next_field().await {
        let Some(name) = field.name().map(str::to_string) else {
            continue;
        };
        if matches!(
            name.as_str(),
            "chat_id" | "message_thread_id" | "caption" | "parse_mode"
        ) && let Ok(value) = field.text().await
        {
            text_fields.insert(name.clone(), serde_json::json!(value));
        }
        field_names.push(name);
    }

    let parse_mode = text_fields
        .get("parse_mode")
        .and_then(serde_json::Value::as_str);
    if parse_mode == Some("MarkdownV2") {
        let mut first_markdown_error = state.first_markdown_error.lock().await;
        if let Some(description) = first_markdown_error.take() {
            state.calls.lock().await.push(UploadCall {
                method: "sendPhoto".to_string(),
                field_names: field_names.clone(),
                text_fields: text_fields.clone(),
                media_json: None,
            });
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "ok": false,
                    "error_code": 400,
                    "description": description
                })),
            );
        }
    }

    state.calls.lock().await.push(UploadCall {
        method: "sendPhoto".to_string(),
        field_names: field_names.clone(),
        text_fields: text_fields.clone(),
        media_json: None,
    });
    *state.field_names.lock().await = field_names;
    *state.text_fields.lock().await = text_fields;

    (
        StatusCode::OK,
        Json(serde_json::json!({"ok": true, "result": {"message_id": 1}})),
    )
}
