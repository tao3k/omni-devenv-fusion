#![allow(missing_docs)]

mod telegram_media_support;

use anyhow::Result;
use omni_agent::{Channel, TelegramChannel};

use telegram_media_support::{
    spawn_mock_telegram_upload_api, spawn_mock_telegram_upload_api_with_markdown_error,
};

#[tokio::test]
async fn telegram_media_local_file_caption_markdown_preserves_fenced_code_language_identifier()
-> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_upload_api().await? else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    let plain_caption = "```Rust\nlet value = a_b * 2;\n```";
    let temp_dir = tempfile::tempdir()?;
    let image_path = temp_dir.path().join("caption-lang.png");
    std::fs::write(&image_path, b"fake image bytes")?;

    channel
        .send(
            &format!("{plain_caption} [IMAGE:{}]", image_path.display()),
            "123456:42",
        )
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 1);
    assert_eq!(calls[0].method, "sendPhoto");
    assert!(calls[0].field_names.iter().any(|name| name == "photo"));
    assert_eq!(
        calls[0]
            .text_fields
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    assert_eq!(
        calls[0]
            .text_fields
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("```rust\nlet value = a_b * 2;\n```")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_local_file_caption_markdown_fallback_keeps_original_fenced_code_text()
-> Result<()> {
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
    let plain_caption = "```Rust\nlet value = a_b * 2;\n```";
    let temp_dir = tempfile::tempdir()?;
    let image_path = temp_dir.path().join("caption-lang-fallback.png");
    std::fs::write(&image_path, b"fake image bytes")?;

    channel
        .send(
            &format!("{plain_caption} [IMAGE:{}]", image_path.display()),
            "123456:42",
        )
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 2);
    assert_eq!(calls[0].method, "sendPhoto");
    assert_eq!(calls[1].method, "sendPhoto");
    assert_eq!(
        calls[0]
            .text_fields
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("```rust\nlet value = a_b * 2;\n```")
    );
    assert!(
        calls[1].text_fields.get("parse_mode").is_none(),
        "plain fallback request should not include parse_mode",
    );
    assert_eq!(
        calls[1]
            .text_fields
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some(plain_caption)
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_local_file_caption_markdown_fallback_keeps_original_cjk_fenced_code_text()
-> Result<()> {
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
    let plain_caption = "```Python\n标题：交易说明\nprint(\"买入：BTC\")\n```";
    let temp_dir = tempfile::tempdir()?;
    let image_path = temp_dir.path().join("caption-cjk-fallback.png");
    std::fs::write(&image_path, b"fake image bytes")?;

    channel
        .send(
            &format!("{plain_caption} [IMAGE:{}]", image_path.display()),
            "123456:42",
        )
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 2);
    assert_eq!(calls[0].method, "sendPhoto");
    assert_eq!(calls[1].method, "sendPhoto");
    assert_eq!(
        calls[0]
            .text_fields
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some("```python\n标题：交易说明\nprint(\"买入：BTC\")\n```")
    );
    assert!(
        calls[1].text_fields.get("parse_mode").is_none(),
        "plain fallback request should not include parse_mode",
    );
    assert_eq!(
        calls[1]
            .text_fields
            .get("caption")
            .and_then(serde_json::Value::as_str),
        Some(plain_caption)
    );

    handle.abort();
    Ok(())
}
