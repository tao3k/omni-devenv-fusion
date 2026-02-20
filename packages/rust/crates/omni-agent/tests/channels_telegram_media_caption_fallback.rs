#![allow(missing_docs)]

mod telegram_media_support;

use anyhow::Result;
use omni_agent::{Channel, TelegramChannel};

use telegram_media_support::{
    spawn_mock_telegram_media_api_with_group_failure,
    spawn_mock_telegram_media_api_with_markdown_error,
    spawn_mock_telegram_upload_api_with_markdown_error,
};

#[tokio::test]
async fn telegram_media_single_caption_markdown_bad_request_falls_back_to_plain() -> Result<()> {
    let Some((api_base, state, handle)) =
        spawn_mock_telegram_media_api_with_markdown_error(Some("can't parse entities")).await?
    else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    channel
        .send("price *up* [IMAGE:https://example.com/a.png]", "123456")
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 2);
    assert_eq!(calls[0].method, "sendPhoto");
    assert_eq!(calls[1].method, "sendPhoto");
    assert_eq!(
        calls[0]
            .payload
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    assert!(
        calls[1].payload.get("parse_mode").is_none(),
        "plain fallback request should not include parse_mode"
    );
    assert_eq!(
        calls[1]
            .payload
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("price *up*")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_group_caption_markdown_bad_request_falls_back_to_plain() -> Result<()> {
    let Some((api_base, state, handle)) =
        spawn_mock_telegram_media_api_with_markdown_error(Some("can't parse entities")).await?
    else {
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
            "price *up* [IMAGE:https://example.com/a.png][DOCUMENT:https://example.com/b.pdf]",
            "123456",
        )
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 2);
    assert_eq!(calls[0].method, "sendMediaGroup");
    assert_eq!(calls[1].method, "sendMediaGroup");

    let first_media = calls[0]
        .payload
        .get("media")
        .and_then(serde_json::Value::as_array)
        .and_then(|media| media.first())
        .cloned()
        .unwrap_or_default();
    let second_media = calls[1]
        .payload
        .get("media")
        .and_then(serde_json::Value::as_array)
        .and_then(|media| media.first())
        .cloned()
        .unwrap_or_default();

    assert_eq!(
        first_media
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    assert!(
        second_media.get("parse_mode").is_none(),
        "plain fallback media-group payload should not include parse_mode"
    );
    assert_eq!(
        second_media
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("price *up*")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_local_file_caption_markdown_bad_request_falls_back_to_plain() -> Result<()>
{
    let Some((api_base, state, handle)) =
        spawn_mock_telegram_upload_api_with_markdown_error(Some("can't parse entities")).await?
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
    let image_path = temp_dir.path().join("caption-fallback.png");
    std::fs::write(&image_path, b"fake image bytes")?;

    channel
        .send(
            &format!("price *up* [IMAGE:{}]", image_path.display()),
            "123456:42",
        )
        .await?;

    let calls = state.calls.lock().await.clone();
    assert_eq!(calls.len(), 2);
    assert_eq!(calls[0].method, "sendPhoto");
    assert_eq!(calls[1].method, "sendPhoto");
    assert!(
        calls[0].field_names.iter().any(|name| name == "caption"),
        "first request should include caption multipart field"
    );
    assert!(
        calls[0].media_json.is_none() && calls[1].media_json.is_none(),
        "sendPhoto requests should not contain media group payload"
    );
    assert_eq!(
        calls[0]
            .text_fields
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    assert!(
        calls[1].text_fields.get("parse_mode").is_none(),
        "plain fallback request should not include parse_mode"
    );
    assert_eq!(
        calls[1]
            .text_fields
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("price *up*")
    );
    assert_ne!(
        calls[0]
            .text_fields
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("price *up*"),
        "MarkdownV2 attempt should use rendered caption"
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_caption_survives_media_group_failure_fallback() -> Result<()> {
    let Some((api_base, state, handle)) =
        spawn_mock_telegram_media_api_with_group_failure(3).await?
    else {
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
            "summary [IMAGE:https://example.com/a.png][DOCUMENT:https://example.com/b.pdf]",
            "123456",
        )
        .await?;

    let calls = state.calls.lock().await;
    let methods: Vec<&str> = calls.iter().map(|call| call.method.as_str()).collect();
    assert_eq!(
        methods,
        vec![
            "sendMediaGroup",
            "sendMediaGroup",
            "sendMediaGroup",
            "sendPhoto",
            "sendDocument"
        ]
    );
    let first_sequential_photo = calls
        .iter()
        .find(|call| call.method == "sendPhoto")
        .cloned()
        .expect("sequential fallback should include sendPhoto");
    assert_eq!(
        first_sequential_photo
            .payload
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("summary")
    );

    handle.abort();
    Ok(())
}
