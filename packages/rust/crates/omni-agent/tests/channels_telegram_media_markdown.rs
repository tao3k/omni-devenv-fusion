#![allow(missing_docs)]

mod telegram_media_support;

use anyhow::Result;
use omni_agent::{Channel, TelegramChannel};

use telegram_media_support::{
    spawn_mock_telegram_media_api, spawn_mock_telegram_media_api_with_markdown_error,
};

#[tokio::test]
async fn telegram_media_group_caption_markdown_preserves_fenced_code_language_identifier()
-> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_media_api().await? else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    let plain_caption = "```Rust\nlet value = a_b * 2;\n```";

    channel
        .send(
            &format!(
                "{plain_caption} [IMAGE:https://example.com/a.png][DOCUMENT:https://example.com/b.pdf]"
            ),
            "123456",
        )
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 1);
    assert_eq!(calls[0].method, "sendMediaGroup");

    let first_media = calls[0]
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
    assert_eq!(
        first_media
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("```rust\nlet value = a_b * 2;\n```")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_group_caption_markdown_fallback_keeps_original_fenced_code_text()
-> Result<()> {
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
    let plain_caption = "```Rust\nlet value = a_b * 2;\n```";

    channel
        .send(
            &format!(
                "{plain_caption} [IMAGE:https://example.com/a.png][DOCUMENT:https://example.com/b.pdf]"
            ),
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
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("```rust\nlet value = a_b * 2;\n```")
    );
    assert!(
        second_media.get("parse_mode").is_none(),
        "plain fallback media-group payload should not include parse_mode"
    );
    assert_eq!(
        second_media
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some(plain_caption)
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_group_caption_markdown_drops_unsupported_fenced_code_language_identifier()
-> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_media_api().await? else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    let plain_caption = "```foo/bar\nlet value = 1;\n```";

    channel
        .send(
            &format!(
                "{plain_caption} [IMAGE:https://example.com/a.png][DOCUMENT:https://example.com/b.pdf]"
            ),
            "123456",
        )
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 1);
    assert_eq!(calls[0].method, "sendMediaGroup");

    let first_media = calls[0]
        .payload
        .get("media")
        .and_then(serde_json::Value::as_array)
        .and_then(|media| media.first())
        .cloned()
        .unwrap_or_default();
    assert_eq!(
        first_media
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("```\nlet value = 1;\n```")
    );

    handle.abort();
    Ok(())
}
