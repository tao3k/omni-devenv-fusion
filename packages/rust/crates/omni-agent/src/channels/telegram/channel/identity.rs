pub(super) fn normalize_user_identity(identity: &str) -> String {
    let trimmed = identity.trim();
    if trimmed == "*" {
        return "*".to_string();
    }
    let normalized = match trimmed.split_once(':') {
        Some((prefix, rest))
            if prefix.eq_ignore_ascii_case("telegram") || prefix.eq_ignore_ascii_case("tg") =>
        {
            rest.trim()
        }
        _ => trimmed,
    };
    if normalized.chars().all(|ch| ch.is_ascii_digit()) {
        return normalized.to_string();
    }
    String::new()
}

pub(super) fn normalize_group_identity(identity: &str) -> String {
    identity.trim().to_string()
}

pub(super) fn parse_recipient_target(recipient: &str) -> (&str, Option<&str>) {
    match recipient.split_once(':') {
        Some((chat_id, thread_id)) if !chat_id.is_empty() && !thread_id.is_empty() => {
            (chat_id, Some(thread_id))
        }
        _ => (recipient, None),
    }
}
