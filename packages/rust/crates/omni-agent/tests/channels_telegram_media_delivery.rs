#![allow(missing_docs)]

mod telegram_media_support;

use anyhow::Result;
use omni_agent::{Channel, TELEGRAM_MAX_MESSAGE_LENGTH, TelegramChannel};

use telegram_media_support::{MediaCall, spawn_mock_telegram_media_api};

#[tokio::test]
async fn telegram_media_path_only_url_auto_detects_voice_method() -> Result<()> {
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
        .send("https://example.com/voice.ogg", "123456")
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 1);
    assert_eq!(calls[0].method, "sendVoice");
    assert_eq!(
        calls[0]
            .payload
            .get("voice")
            .and_then(serde_json::Value::as_str),
        Some("https://example.com/voice.ogg")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_topic_routing_adds_message_thread_id_to_media_payload() -> Result<()> {
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
        .send("[VIDEO:https://example.com/topic.mp4]", "123456:42")
        .await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 1);
    assert_eq!(calls[0].method, "sendVideo");
    assert_eq!(
        calls[0]
            .payload
            .get("chat_id")
            .and_then(serde_json::Value::as_str),
        Some("123456")
    );
    assert_eq!(
        calls[0]
            .payload
            .get("message_thread_id")
            .and_then(serde_json::Value::as_str),
        Some("42")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_group_splits_batches_at_telegram_limit() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_media_api().await? else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    let payload = (0..12)
        .map(|index| format!("[IMAGE:https://example.com/{index}.png]"))
        .collect::<String>();

    channel.send(&payload, "123456").await?;

    let calls = state.calls.lock().await;
    assert_eq!(calls.len(), 2);
    assert!(calls.iter().all(|call| call.method == "sendMediaGroup"));

    let first_batch = calls[0]
        .payload
        .get("media")
        .and_then(serde_json::Value::as_array)
        .cloned()
        .unwrap_or_default();
    let second_batch = calls[1]
        .payload
        .get("media")
        .and_then(serde_json::Value::as_array)
        .cloned()
        .unwrap_or_default();

    assert_eq!(first_batch.len(), 10);
    assert_eq!(second_batch.len(), 2);
    assert_eq!(
        first_batch[0]
            .get("media")
            .and_then(serde_json::Value::as_str),
        Some("https://example.com/0.png")
    );
    assert_eq!(
        second_batch[0]
            .get("media")
            .and_then(serde_json::Value::as_str),
        Some("https://example.com/10.png")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_group_splits_on_incompatible_attachment_kind() -> Result<()> {
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
            "[IMAGE:https://example.com/1.png]\
[DOCUMENT:https://example.com/2.pdf]\
[VOICE:https://example.com/3.ogg]\
[VIDEO:https://example.com/4.mp4]\
[AUDIO:https://example.com/5.mp3]",
            "123456",
        )
        .await?;

    let calls = state.calls.lock().await;
    let methods: Vec<&str> = calls.iter().map(|call| call.method.as_str()).collect();
    assert_eq!(
        methods,
        vec!["sendMediaGroup", "sendVoice", "sendMediaGroup"]
    );

    let first_group_len = calls[0]
        .payload
        .get("media")
        .and_then(serde_json::Value::as_array)
        .map(std::vec::Vec::len)
        .unwrap_or_default();
    let second_group_len = calls[2]
        .payload
        .get("media")
        .and_then(serde_json::Value::as_array)
        .map(std::vec::Vec::len)
        .unwrap_or_default();
    assert_eq!(first_group_len, 2);
    assert_eq!(second_group_len, 2);

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_media_long_text_chunks_preserve_all_content_before_media_send() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_media_api().await? else {
        return Ok(());
    };

    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    let long_text = "a".repeat(TELEGRAM_MAX_MESSAGE_LENGTH * 2 + 256);
    let message = format!("{long_text}[IMAGE:https://example.com/chunked.png]");

    channel.send(&message, "123456").await?;

    let calls = state.calls.lock().await;
    let message_calls: Vec<&MediaCall> = calls
        .iter()
        .filter(|call| call.method == "sendMessage")
        .collect();
    assert!(message_calls.len() >= 2);
    assert_eq!(
        calls.last().map(|call| call.method.as_str()),
        Some("sendPhoto")
    );

    let sent_a_count: usize = message_calls
        .iter()
        .map(|call| {
            call.payload
                .get("text")
                .and_then(serde_json::Value::as_str)
                .unwrap_or_default()
                .chars()
                .filter(|ch| *ch == 'a')
                .count()
        })
        .sum();
    assert_eq!(sent_a_count, long_text.len());

    handle.abort();
    Ok(())
}
