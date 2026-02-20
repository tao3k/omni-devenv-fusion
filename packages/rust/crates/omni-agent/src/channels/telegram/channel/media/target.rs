use std::borrow::Cow;
use std::path::{Path, PathBuf};

use super::attachment::{TelegramAttachmentKind, TelegramAttachmentTarget};

fn is_http_url(target: &str) -> bool {
    target.starts_with("http://") || target.starts_with("https://")
}

pub(super) fn normalize_attachment_target(target: &str) -> Option<TelegramAttachmentTarget> {
    let candidate = target
        .trim()
        .trim_matches(|c| matches!(c, '`' | '"' | '\''));
    if candidate.is_empty() {
        return None;
    }

    if is_http_url(candidate) {
        if candidate.chars().any(char::is_whitespace) {
            return None;
        }
        return Some(TelegramAttachmentTarget::Url(candidate.to_string()));
    }

    let local_candidate = candidate.strip_prefix("file://").unwrap_or(candidate);
    let path = PathBuf::from(local_candidate);
    if !path.exists() {
        return None;
    }
    Some(TelegramAttachmentTarget::LocalPath(path))
}

pub(super) fn infer_attachment_kind_from_target(
    target: &TelegramAttachmentTarget,
) -> Option<TelegramAttachmentKind> {
    let normalized: Cow<'_, str> = match target {
        TelegramAttachmentTarget::Url(url) => Cow::Owned(
            url.split('?')
                .next()
                .unwrap_or(url)
                .split('#')
                .next()
                .unwrap_or(url)
                .to_string(),
        ),
        TelegramAttachmentTarget::LocalPath(path) => Cow::Borrowed(path.as_os_str().to_str()?),
    };

    let extension = Path::new(normalized.as_ref())
        .extension()
        .and_then(|ext| ext.to_str())?
        .to_ascii_lowercase();

    match extension.as_str() {
        "png" | "jpg" | "jpeg" | "gif" | "webp" | "bmp" => Some(TelegramAttachmentKind::Image),
        "mp4" | "mov" | "mkv" | "avi" | "webm" => Some(TelegramAttachmentKind::Video),
        "mp3" | "m4a" | "wav" | "flac" => Some(TelegramAttachmentKind::Audio),
        "ogg" | "oga" | "opus" => Some(TelegramAttachmentKind::Voice),
        "pdf" | "txt" | "md" | "csv" | "json" | "xml" | "zip" | "tar" | "gz" | "doc" | "docx"
        | "xls" | "xlsx" | "ppt" | "pptx" => Some(TelegramAttachmentKind::Document),
        _ => None,
    }
}
