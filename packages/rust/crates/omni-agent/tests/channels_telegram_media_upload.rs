#![allow(missing_docs)]

mod telegram_media_support;

use anyhow::Result;
use omni_agent::{Channel, TelegramChannel};

use telegram_media_support::{
    spawn_mock_telegram_media_group_upload_api, spawn_mock_telegram_upload_api,
};

#[tokio::test]
async fn telegram_media_local_file_marker_uses_multipart_upload() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_upload_api().await? else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    let temp_dir = tempfile::tempdir()?;
    let image_path = temp_dir.path().join("upload.png");
    std::fs::write(&image_path, b"fake image bytes")?;

    channel
        .send(&format!("[IMAGE:{}]", image_path.display()), "123456:42")
        .await?;

    let field_names = state.field_names.lock().await.clone();
    assert!(field_names.iter().any(|name| name == "photo"));
    assert!(field_names.iter().any(|name| name == "chat_id"));
    assert!(field_names.iter().any(|name| name == "message_thread_id"));

    let text_fields = state.text_fields.lock().await.clone();
    assert_eq!(
        text_fields
            .get("chat_id")
            .and_then(serde_json::Value::as_str),
        Some("123456")
    );
    assert_eq!(
        text_fields
            .get("message_thread_id")
            .and_then(serde_json::Value::as_str),
        Some("42")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_group_local_files_use_attach_multipart() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_media_group_upload_api().await?
    else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    let temp_dir = tempfile::tempdir()?;
    let image_path = temp_dir.path().join("one.png");
    let document_path = temp_dir.path().join("two.pdf");
    std::fs::write(&image_path, b"fake image bytes")?;
    std::fs::write(&document_path, b"fake pdf bytes")?;

    channel
        .send(
            &format!(
                "[IMAGE:{}][DOCUMENT:{}]",
                image_path.display(),
                document_path.display()
            ),
            "123456:42",
        )
        .await?;

    let field_names = state.field_names.lock().await.clone();
    assert!(field_names.iter().any(|name| name == "chat_id"));
    assert!(field_names.iter().any(|name| name == "message_thread_id"));
    assert!(field_names.iter().any(|name| name == "media"));
    assert!(field_names.iter().any(|name| name == "file0"));
    assert!(field_names.iter().any(|name| name == "file1"));

    let media_json = state.media_json.lock().await.clone().unwrap_or_default();
    let media_items = media_json.as_array().cloned().unwrap_or_default();
    assert_eq!(media_items.len(), 2);
    assert_eq!(
        media_items[0]
            .get("media")
            .and_then(serde_json::Value::as_str),
        Some("attach://file0")
    );
    assert_eq!(
        media_items[1]
            .get("media")
            .and_then(serde_json::Value::as_str),
        Some("attach://file1")
    );

    let text_fields = state.text_fields.lock().await.clone();
    assert_eq!(
        text_fields
            .get("chat_id")
            .and_then(serde_json::Value::as_str),
        Some("123456")
    );
    assert_eq!(
        text_fields
            .get("message_thread_id")
            .and_then(serde_json::Value::as_str),
        Some("42")
    );

    handle.abort();
    Ok(())
}
