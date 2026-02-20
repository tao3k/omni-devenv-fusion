use super::constants::TELEGRAM_MAX_CAPTION_LENGTH;
use super::markdown::markdown_to_telegram_markdown_v2;

pub(super) struct MediaGroupFilePart {
    pub(super) field_name: String,
    pub(super) file_name: String,
    pub(super) file_bytes: Vec<u8>,
}

pub(super) struct PreparedCaption {
    plain: String,
    markdown_v2: Option<String>,
}

impl PreparedCaption {
    pub(super) fn from_plain(text: &str) -> Self {
        let markdown_v2 = markdown_to_telegram_markdown_v2(text);
        let markdown_v2 =
            (markdown_v2.chars().count() <= TELEGRAM_MAX_CAPTION_LENGTH).then_some(markdown_v2);
        Self {
            plain: text.to_string(),
            markdown_v2,
        }
    }

    pub(super) fn plain_text(&self) -> &str {
        self.plain.as_str()
    }

    pub(super) fn markdown_text(&self) -> Option<&str> {
        self.markdown_v2.as_deref()
    }
}
