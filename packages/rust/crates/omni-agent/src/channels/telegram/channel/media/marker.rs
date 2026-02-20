use super::attachment::{TelegramAttachment, TelegramAttachmentKind};
use super::target::{infer_attachment_kind_from_target, normalize_attachment_target};

pub(in crate::channels::telegram::channel) fn parse_path_only_attachment(
    message: &str,
) -> Option<TelegramAttachment> {
    let trimmed = message.trim();
    if trimmed.is_empty() || trimmed.contains('\n') {
        return None;
    }

    let candidate = normalize_attachment_target(trimmed)?;
    let kind = infer_attachment_kind_from_target(&candidate)?;
    Some(TelegramAttachment {
        kind,
        target: candidate,
    })
}

pub(in crate::channels::telegram::channel) fn parse_attachment_markers(
    message: &str,
) -> (String, Vec<TelegramAttachment>, bool) {
    let mut cleaned = String::with_capacity(message.len());
    let mut attachments = Vec::new();
    let mut has_invalid_attachment_marker = false;
    let mut cursor = 0;

    while cursor < message.len() {
        let Some(open_rel) = message[cursor..].find('[') else {
            cleaned.push_str(&message[cursor..]);
            break;
        };

        let open = cursor + open_rel;
        cleaned.push_str(&message[cursor..open]);

        let Some(close_rel) = message[open..].find(']') else {
            cleaned.push_str(&message[open..]);
            break;
        };

        let close = open + close_rel;
        let marker = &message[open + 1..close];

        let parsed = marker.split_once(':').and_then(|(kind, target)| {
            let kind = TelegramAttachmentKind::from_marker(kind)?;
            let target = normalize_attachment_target(target)?;
            Some(TelegramAttachment { kind, target })
        });

        if let Some(attachment) = parsed {
            attachments.push(attachment);
        } else {
            cleaned.push_str(&message[open..=close]);
            if let Some((kind, _)) = marker.split_once(':')
                && TelegramAttachmentKind::from_marker(kind).is_some()
            {
                has_invalid_attachment_marker = true;
            }
        }

        cursor = close + 1;
    }

    (
        cleaned.trim().to_string(),
        attachments,
        has_invalid_attachment_marker,
    )
}
