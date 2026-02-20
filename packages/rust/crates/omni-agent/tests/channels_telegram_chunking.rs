#![allow(missing_docs)]

use omni_agent::{
    TELEGRAM_MAX_MESSAGE_LENGTH, chunk_marker_reserve_chars, decorate_chunk_for_telegram,
    split_message_for_telegram,
};

fn max_chunk_chars() -> usize {
    TELEGRAM_MAX_MESSAGE_LENGTH - chunk_marker_reserve_chars()
}

fn assert_decorated_chunks_within_limit(chunks: &[String]) {
    for (index, chunk) in chunks.iter().enumerate() {
        let decorated = decorate_chunk_for_telegram(chunk, index, chunks.len());
        assert!(
            decorated.chars().count() <= TELEGRAM_MAX_MESSAGE_LENGTH,
            "decorated chunk {index} exceeds limit: {} > {}",
            decorated.chars().count(),
            TELEGRAM_MAX_MESSAGE_LENGTH
        );
    }
}

#[test]
fn split_message_handles_multibyte_char_at_chunk_boundary() {
    let max_chunk = max_chunk_chars();
    let message = format!("{}{}{}", "a".repeat(max_chunk - 1), "：", "z".repeat(64));

    let chunks = split_message_for_telegram(&message);

    assert!(chunks.len() > 1);
    assert!(chunks[0].ends_with('：'));
    assert_eq!(chunks.concat(), message);
    assert_decorated_chunks_within_limit(&chunks);
}

#[test]
fn split_message_preserves_cjk_content_without_panicking() {
    let message = "说".repeat(TELEGRAM_MAX_MESSAGE_LENGTH + 128);

    let chunks = split_message_for_telegram(&message);

    assert!(chunks.len() > 1);
    assert!(chunks.iter().all(|chunk| !chunk.is_empty()));
    assert_eq!(chunks.concat(), message);
    assert_decorated_chunks_within_limit(&chunks);
}

#[test]
fn split_message_prefers_nearby_newline_breaks() {
    let max_chunk = max_chunk_chars();
    let message = format!("{}\n{}", "a".repeat(max_chunk - 8), "b".repeat(80));

    let chunks = split_message_for_telegram(&message);

    assert!(chunks.len() > 1);
    assert!(chunks[0].ends_with('\n'));
    assert_eq!(chunks.concat(), message);
    assert_decorated_chunks_within_limit(&chunks);
}

#[test]
fn split_message_falls_back_to_space_when_newline_is_too_early() {
    let max_chunk = max_chunk_chars();
    let start = "head\n";
    let middle = "x".repeat(max_chunk - start.chars().count() - 1);
    let message = format!("{start}{middle} {}", "tail".repeat(32));

    let chunks = split_message_for_telegram(&message);

    assert!(chunks.len() > 1);
    assert!(chunks[0].ends_with(' '));
    assert_eq!(chunks.concat(), message);
    assert_decorated_chunks_within_limit(&chunks);
}
