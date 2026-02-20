use axum::{Json, extract::Multipart, extract::State, http::StatusCode};

use super::{MockTelegramUploadState, UploadCall};

pub(super) async fn handle_upload_media_group(
    State(state): State<MockTelegramUploadState>,
    mut multipart: Multipart,
) -> (StatusCode, Json<serde_json::Value>) {
    let mut field_names = Vec::new();
    let mut text_fields = serde_json::Map::new();
    let mut media_json = None;

    while let Ok(Some(field)) = multipart.next_field().await {
        let Some(name) = field.name().map(str::to_string) else {
            continue;
        };

        if matches!(name.as_str(), "chat_id" | "message_thread_id" | "media")
            && let Ok(value) = field.text().await
        {
            if name == "media" {
                media_json = serde_json::from_str::<serde_json::Value>(&value).ok();
            } else {
                text_fields.insert(name.clone(), serde_json::json!(value));
            }
        }

        field_names.push(name);
    }

    let parse_mode = media_json
        .as_ref()
        .and_then(serde_json::Value::as_array)
        .and_then(|media| media.first())
        .and_then(|first| first.get("parse_mode"))
        .and_then(serde_json::Value::as_str);
    if parse_mode == Some("MarkdownV2") {
        let mut first_markdown_error = state.first_markdown_error.lock().await;
        if let Some(description) = first_markdown_error.take() {
            state.calls.lock().await.push(UploadCall {
                method: "sendMediaGroup".to_string(),
                field_names: field_names.clone(),
                text_fields: text_fields.clone(),
                media_json: media_json.clone(),
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
        method: "sendMediaGroup".to_string(),
        field_names: field_names.clone(),
        text_fields: text_fields.clone(),
        media_json: media_json.clone(),
    });
    *state.field_names.lock().await = field_names;
    *state.text_fields.lock().await = text_fields;
    *state.media_json.lock().await = media_json;

    (
        StatusCode::OK,
        Json(serde_json::json!({"ok": true, "result": {"message_id": 1}})),
    )
}
