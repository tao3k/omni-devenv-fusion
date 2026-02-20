use serde_json::json;

pub(in super::super) fn format_session_admin_status(
    recipient: &str,
    override_admin_users: Option<&[String]>,
) -> String {
    let scope = scope_from_recipient(recipient);
    [
        "Session delegated admins.".to_string(),
        format!("recipient={recipient}"),
        format!("scope={scope}"),
        format!(
            "override_admin_users={}",
            render_admin_users_for_dashboard(override_admin_users)
        ),
        "note=override list is used only at admin_users fallback stage; clear returns to inherited ACL.".to_string(),
    ]
    .join("\n")
}

pub(in super::super) fn format_session_admin_status_json(
    recipient: &str,
    override_admin_users: Option<&[String]>,
) -> String {
    json!({
        "kind": "session_admin",
        "updated": false,
        "recipient": recipient,
        "scope": scope_from_recipient(recipient),
        "override_admin_users": override_admin_users,
        "note": "override list is used only at admin_users fallback stage; clear returns to inherited ACL",
    })
    .to_string()
}

pub(in super::super) fn format_session_admin_updated(
    action: &str,
    recipient: &str,
    override_admin_users: Option<&[String]>,
) -> String {
    let scope = scope_from_recipient(recipient);
    [
        "Session delegated admins updated.".to_string(),
        format!("action={action}"),
        format!("recipient={recipient}"),
        format!("scope={scope}"),
        format!(
            "override_admin_users={}",
            render_admin_users_for_dashboard(override_admin_users)
        ),
    ]
    .join("\n")
}

pub(in super::super) fn format_session_admin_updated_json(
    action: &str,
    recipient: &str,
    override_admin_users: Option<&[String]>,
) -> String {
    json!({
        "kind": "session_admin",
        "updated": true,
        "action": action,
        "recipient": recipient,
        "scope": scope_from_recipient(recipient),
        "override_admin_users": override_admin_users,
    })
    .to_string()
}

fn scope_from_recipient(recipient: &str) -> &'static str {
    let (chat_id, has_thread) = match recipient.split_once(':') {
        Some((chat, thread)) if !chat.is_empty() && !thread.is_empty() => (chat, true),
        _ => (recipient, false),
    };
    if !chat_id.starts_with('-') {
        return "direct";
    }
    if has_thread { "topic" } else { "group" }
}

fn render_admin_users_for_dashboard(override_admin_users: Option<&[String]>) -> String {
    match override_admin_users {
        Some(entries) if entries.is_empty() => "(inherit)".to_string(),
        Some(entries) => entries.join(","),
        None => "(inherit)".to_string(),
    }
}
