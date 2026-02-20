//! Telegram attachment parsing and routing helpers.

mod attachment;
mod marker;
mod target;

pub(in crate::channels::telegram::channel) use attachment::{
    TelegramAttachment, TelegramAttachmentKind,
};
pub(in crate::channels::telegram::channel) use marker::{
    parse_attachment_markers, parse_path_only_attachment,
};
