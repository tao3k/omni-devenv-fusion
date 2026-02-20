use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub(in crate::channels::telegram::channel) enum TelegramAttachmentKind {
    Image,
    Document,
    Video,
    Audio,
    Voice,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(in crate::channels::telegram::channel) enum TelegramAttachmentTarget {
    Url(String),
    LocalPath(PathBuf),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(in crate::channels::telegram::channel) struct TelegramAttachment {
    pub(in crate::channels::telegram::channel) kind: TelegramAttachmentKind,
    pub(in crate::channels::telegram::channel) target: TelegramAttachmentTarget,
}

impl TelegramAttachmentKind {
    pub(in crate::channels::telegram::channel) fn from_marker(marker: &str) -> Option<Self> {
        match marker.trim().to_ascii_uppercase().as_str() {
            "IMAGE" | "PHOTO" => Some(Self::Image),
            "DOCUMENT" | "FILE" => Some(Self::Document),
            "VIDEO" => Some(Self::Video),
            "AUDIO" => Some(Self::Audio),
            "VOICE" => Some(Self::Voice),
            _ => None,
        }
    }
}

impl TelegramAttachmentTarget {
    pub(in crate::channels::telegram::channel) fn as_url(&self) -> Option<&str> {
        match self {
            Self::Url(url) => Some(url.as_str()),
            Self::LocalPath(_) => None,
        }
    }

    pub(in crate::channels::telegram::channel) fn as_path(&self) -> Option<&Path> {
        match self {
            Self::Url(_) => None,
            Self::LocalPath(path) => Some(path.as_path()),
        }
    }
}
