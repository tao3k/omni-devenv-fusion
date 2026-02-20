use super::constants::{
    CHUNK_CONTINUED_PREFIX, CHUNK_CONTINUES_SUFFIX, TELEGRAM_MAX_MESSAGE_LENGTH,
};

/// Split a message into chunks that respect Telegram's 4096 character limit.
/// Each chunk stays under the limit even after adding continuation markers.
#[doc(hidden)]
pub fn split_message_for_telegram(message: &str) -> Vec<String> {
    let max_chunk_chars = TELEGRAM_MAX_MESSAGE_LENGTH.saturating_sub(chunk_marker_reserve_chars());
    if max_chunk_chars == 0 {
        return vec![message.to_string()];
    }

    if byte_index_after_n_chars(message, TELEGRAM_MAX_MESSAGE_LENGTH) == message.len() {
        return vec![message.to_string()];
    }

    let mut chunks = Vec::new();
    let mut remaining = message;
    while !remaining.is_empty() {
        let max_chunk_boundary = byte_index_after_n_chars(remaining, max_chunk_chars);
        if max_chunk_boundary == remaining.len() {
            chunks.push(remaining.to_string());
            break;
        }

        let search_area = &remaining[..max_chunk_boundary];
        let chunk_end = choose_split_boundary(search_area, max_chunk_boundary, max_chunk_chars);
        chunks.push(remaining[..chunk_end].to_string());
        remaining = &remaining[chunk_end..];
    }
    chunks
}

/// Reserve space for continuation markers when splitting.
/// Keep this as character-count based so future non-ASCII marker text remains safe.
#[doc(hidden)]
pub fn chunk_marker_reserve_chars() -> usize {
    CHUNK_CONTINUED_PREFIX.chars().count() + CHUNK_CONTINUES_SUFFIX.chars().count()
}

#[doc(hidden)]
pub fn decorate_chunk_for_telegram(chunk: &str, index: usize, total_chunks: usize) -> String {
    if total_chunks <= 1 {
        return chunk.to_string();
    }

    if index == 0 {
        format!("{chunk}{CHUNK_CONTINUES_SUFFIX}")
    } else if index == total_chunks - 1 {
        format!("{CHUNK_CONTINUED_PREFIX}{chunk}")
    } else {
        format!("{CHUNK_CONTINUED_PREFIX}{chunk}{CHUNK_CONTINUES_SUFFIX}")
    }
}

fn byte_index_after_n_chars(text: &str, n: usize) -> usize {
    if n == 0 {
        return 0;
    }

    text.char_indices()
        .nth(n)
        .map(|(idx, _)| idx)
        .unwrap_or(text.len())
}

fn choose_split_boundary(search_area: &str, max_boundary: usize, max_chars: usize) -> usize {
    if let Some(pos) = search_area.rfind('\n') {
        let newline_char_pos = search_area[..pos].chars().count();
        if newline_char_pos >= max_chars / 2 {
            return pos + 1;
        }
    }

    if let Some(pos) = search_area.rfind(' ') {
        return pos + 1;
    }

    max_boundary
}
