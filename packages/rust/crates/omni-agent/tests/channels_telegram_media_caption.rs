#![allow(missing_docs)]

mod telegram_media_support;

use anyhow::Result;
use omni_agent::{Channel, TelegramChannel};

use telegram_media_support::{spawn_mock_telegram_media_api, spawn_mock_telegram_upload_api};

#[tokio::test]
async fn telegram_media_markers_attach_short_text_as_media_group_caption() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_media_api().await? else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    channel
        .send(
            "summary [IMAGE:https://example.com/a.png] [DOCUMENT:https://example.com/b.pdf]",
            "123456",
        )
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 1);
    assert_eq!(calls[0].method, "sendMediaGroup");
    let media = calls[0]
        .payload
        .get("media")
        .and_then(serde_json::Value::as_array)
        .cloned()
        .unwrap_or_default();
    assert_eq!(media.len(), 2);
    assert_eq!(
        media[0].get("media").and_then(serde_json::Value::as_str),
        Some("https://example.com/a.png")
    );
    assert_eq!(
        media[0].get("caption").and_then(serde_json::Value::as_str),
        Some("summary")
    );
    assert_eq!(
        media[1].get("media").and_then(serde_json::Value::as_str),
        Some("https://example.com/b.pdf")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_short_text_uses_caption_for_local_file_upload() -> Result<()> {
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
    let image_path = temp_dir.path().join("caption.png");
    std::fs::write(&image_path, b"fake image bytes")?;

    channel
        .send(
            &format!("summary [IMAGE:{}]", image_path.display()),
            "123456:42",
        )
        .await?;

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
    assert_eq!(
        text_fields
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("summary")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_text_exceeding_caption_limit_is_sent_before_media() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_media_api().await? else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    let text = "a".repeat(1025);
    channel
        .send(
            &format!("{text}[IMAGE:https://example.com/caption-limit.png]"),
            "123456",
        )
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 2);
    assert_eq!(calls[0].method, "sendMessage");
    assert_eq!(calls[1].method, "sendPhoto");
    assert_eq!(
        calls[0]
            .payload
            .get("text")
            .and_then(serde_json::Value::as_str),
        Some(text.as_str())
    );
    assert!(
        calls[1].payload.get("caption").is_none(),
        "caption should not be used when text exceeds caption limit"
    );

    handle.abort();
    Ok(())
}
