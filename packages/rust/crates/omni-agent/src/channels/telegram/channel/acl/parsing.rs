pub(super) fn resolve_string_env_or_setting(
    env_name: &str,
    setting_value: Option<String>,
    default: &str,
) -> String {
    if let Ok(value) = std::env::var(env_name)
        && !value.trim().is_empty()
    {
        return value;
    }
    setting_value.unwrap_or_else(|| default.to_string())
}

pub(super) fn resolve_optional_env_or_setting(
    env_name: &str,
    setting_value: Option<String>,
) -> Option<String> {
    if let Ok(value) = std::env::var(env_name) {
        return Some(value);
    }
    setting_value
}

pub(super) fn resolve_bool_env_or_setting(
    env_name: &str,
    setting_value: Option<bool>,
    default: bool,
) -> bool {
    if let Ok(value) = std::env::var(env_name) {
        return parse_bool_with_context(&value, env_name).unwrap_or(default);
    }
    setting_value.unwrap_or(default)
}

fn parse_bool_with_context(raw: &str, context: &str) -> Option<bool> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => {
            tracing::warn!(
                context = %context,
                value = %raw,
                "invalid boolean value; expected true/false"
            );
            None
        }
    }
}

pub(super) fn parse_comma_entries(raw: &str) -> Vec<String> {
    raw.split(',')
        .map(|entry| entry.trim().to_string())
        .filter(|entry| !entry.is_empty())
        .collect()
}

pub(super) fn parse_optional_comma_entries(raw: Option<String>) -> Option<Vec<String>> {
    raw.map(|value| parse_comma_entries(value.as_str()))
}

pub(super) fn parse_semicolon_entries(raw: &str) -> Vec<String> {
    raw.split(';')
        .map(|entry| entry.trim().to_string())
        .filter(|entry| !entry.is_empty())
        .collect()
}
