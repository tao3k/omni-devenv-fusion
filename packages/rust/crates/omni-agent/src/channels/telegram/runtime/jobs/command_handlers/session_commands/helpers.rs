use std::sync::Arc;

use crate::channels::traits::{Channel, RecipientCommandAdminUsersMutation};

use super::super::super::replies::{
    format_command_error_json, format_session_admin_updated, format_session_admin_updated_json,
};

pub(in crate::channels::telegram::runtime::jobs::command_handlers) fn truncate_preview(
    value: &str,
    max_chars: usize,
) -> String {
    if value.chars().count() <= max_chars {
        return value.to_string();
    }
    if max_chars <= 3 {
        return ".".repeat(max_chars);
    }
    let mut out = String::new();
    for ch in value.chars().take(max_chars.saturating_sub(3)) {
        out.push(ch);
    }
    out.push_str("...");
    out
}

pub(in crate::channels::telegram::runtime::jobs::command_handlers) fn update_session_admin_users(
    channel: &Arc<dyn Channel>,
    recipient: &str,
    mutation: RecipientCommandAdminUsersMutation,
    action: &str,
    json_format: bool,
) -> String {
    match channel.mutate_recipient_command_admin_users(recipient, mutation) {
        Ok(admin_users) if json_format => {
            format_session_admin_updated_json(action, recipient, admin_users.as_deref())
        }
        Ok(admin_users) => format_session_admin_updated(action, recipient, admin_users.as_deref()),
        Err(error) if json_format => {
            format_command_error_json("session_admin_update", &error.to_string())
        }
        Err(error) => format!("Failed to update session delegated admins: {error}"),
    }
}
