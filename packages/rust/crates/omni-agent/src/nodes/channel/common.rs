pub(super) fn parse_comma_separated_entries(raw: &str) -> Vec<String> {
    raw.split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

pub(super) fn parse_optional_comma_separated_entries(raw: Option<String>) -> Option<Vec<String>> {
    raw.map(|value| parse_comma_separated_entries(&value))
}

pub(super) fn parse_semicolon_separated_entries(raw: &str) -> Vec<String> {
    raw.split(';')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

pub(super) fn log_control_command_allow_override(provider: &str, entries: &Option<Vec<String>>) {
    if let Some(entries) = entries {
        if entries.is_empty() {
            tracing::warn!(
                provider = %provider,
                "{provider}.control_command_allow_from is configured but empty; privileged control commands are denied for all senders"
            );
        } else {
            tracing::info!(
                provider = %provider,
                entries = entries.len(),
                "{provider}.control_command_allow_from override is active"
            );
        }
    }
}

pub(super) fn log_slash_command_allow_override(provider: &str, entries: &Option<Vec<String>>) {
    if let Some(entries) = entries {
        if entries.is_empty() {
            tracing::warn!(
                provider = %provider,
                "{provider}.slash_command_allow_from is configured but empty; managed slash commands are denied for all non-admin senders"
            );
        } else {
            tracing::info!(
                provider = %provider,
                entries = entries.len(),
                "{provider}.slash_command_allow_from override is active"
            );
        }
    }
}

pub(super) fn non_empty_string(value: String) -> Option<String> {
    if value.trim().is_empty() {
        None
    } else {
        Some(value)
    }
}
