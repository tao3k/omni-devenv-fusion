use crate::cli::{TelegramChannelMode, WebhookDedupBackendMode};

pub(crate) fn resolve_string(
    cli_value: Option<String>,
    env_name: &str,
    settings_value: Option<&str>,
    default: &str,
) -> String {
    if let Some(value) = cli_value {
        return value;
    }
    if let Ok(value) = std::env::var(env_name)
        && !value.trim().is_empty()
    {
        return value;
    }
    if let Some(value) = settings_value {
        return value.to_string();
    }
    default.to_string()
}

pub(crate) fn resolve_optional_string(
    cli_value: Option<String>,
    env_name: &str,
    settings_value: Option<&str>,
) -> Option<String> {
    if cli_value.is_some() {
        return cli_value;
    }
    if let Ok(value) = std::env::var(env_name) {
        return Some(value);
    }
    settings_value.map(ToString::to_string)
}

pub(crate) fn resolve_positive_u64(
    cli_value: Option<u64>,
    env_name: &str,
    settings_value: Option<u64>,
    default: u64,
) -> u64 {
    if let Some(value) = cli_value
        && value > 0
    {
        return value;
    }
    if let Some(value) = parse_positive_u64_from_env(env_name) {
        return value;
    }
    if let Some(value) = settings_value
        && value > 0
    {
        return value;
    }
    default
}

pub(crate) fn resolve_positive_usize(
    cli_value: Option<usize>,
    env_name: &str,
    settings_value: Option<usize>,
    default: usize,
) -> usize {
    if let Some(value) = cli_value
        && value > 0
    {
        return value;
    }
    if let Some(value) = parse_positive_usize_from_env(env_name) {
        return value;
    }
    if let Some(value) = settings_value
        && value > 0
    {
        return value;
    }
    default
}

pub(crate) fn resolve_channel_mode(
    cli_mode: Option<TelegramChannelMode>,
    settings_mode: Option<&str>,
) -> TelegramChannelMode {
    if let Some(mode) = cli_mode {
        return mode;
    }
    if let Ok(raw) = std::env::var("OMNI_AGENT_TELEGRAM_MODE") {
        if let Some(mode) = parse_channel_mode(&raw) {
            return mode;
        }
        tracing::warn!(
            value = %raw,
            "invalid OMNI_AGENT_TELEGRAM_MODE; using settings/default"
        );
    }
    if let Some(raw) = settings_mode {
        if let Some(mode) = parse_channel_mode(raw) {
            return mode;
        }
        tracing::warn!(
            value = %raw,
            "invalid telegram.mode in settings; using default"
        );
    }
    TelegramChannelMode::Webhook
}

pub(crate) fn resolve_dedup_backend(
    cli_backend: Option<WebhookDedupBackendMode>,
    settings_backend: Option<&str>,
) -> WebhookDedupBackendMode {
    if let Some(backend) = cli_backend {
        return backend;
    }
    if let Ok(raw) = std::env::var("OMNI_AGENT_TELEGRAM_WEBHOOK_DEDUP_BACKEND") {
        if let Some(backend) = parse_dedup_backend(&raw) {
            return backend;
        }
        tracing::warn!(
            value = %raw,
            "invalid OMNI_AGENT_TELEGRAM_WEBHOOK_DEDUP_BACKEND; using settings/default"
        );
    }
    if let Some(raw) = settings_backend {
        if let Some(backend) = parse_dedup_backend(raw) {
            return backend;
        }
        tracing::warn!(
            value = %raw,
            "invalid telegram.webhook_dedup_backend in settings; using default"
        );
    }
    WebhookDedupBackendMode::Valkey
}

fn parse_channel_mode(raw: &str) -> Option<TelegramChannelMode> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "polling" => Some(TelegramChannelMode::Polling),
        "webhook" => Some(TelegramChannelMode::Webhook),
        _ => None,
    }
}

fn parse_dedup_backend(raw: &str) -> Option<WebhookDedupBackendMode> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "memory" => Some(WebhookDedupBackendMode::Memory),
        "valkey" | "redis" => Some(WebhookDedupBackendMode::Valkey),
        _ => None,
    }
}

pub(crate) fn parse_positive_u32_from_env(name: &str) -> Option<u32> {
    let raw = std::env::var(name).ok()?;
    match raw.parse::<u32>() {
        Ok(value) if value > 0 => Some(value),
        _ => {
            tracing::warn!(env_var = %name, value = %raw, "invalid positive integer env value");
            None
        }
    }
}

pub(crate) fn parse_positive_usize_from_env(name: &str) -> Option<usize> {
    let raw = std::env::var(name).ok()?;
    match raw.parse::<usize>() {
        Ok(value) if value > 0 => Some(value),
        _ => {
            tracing::warn!(env_var = %name, value = %raw, "invalid positive integer env value");
            None
        }
    }
}

pub(crate) fn parse_positive_u64_from_env(name: &str) -> Option<u64> {
    let raw = std::env::var(name).ok()?;
    match raw.parse::<u64>() {
        Ok(value) if value > 0 => Some(value),
        _ => {
            tracing::warn!(env_var = %name, value = %raw, "invalid positive integer env value");
            None
        }
    }
}

pub(crate) fn parse_positive_f32_from_env(name: &str) -> Option<f32> {
    let raw = std::env::var(name).ok()?;
    match raw.parse::<f32>() {
        Ok(value) if value > 0.0 => Some(value),
        _ => {
            tracing::warn!(env_var = %name, value = %raw, "invalid positive float env value");
            None
        }
    }
}

pub(crate) fn parse_unit_f32_from_env(name: &str) -> Option<f32> {
    let raw = std::env::var(name).ok()?;
    match raw.parse::<f32>() {
        Ok(value) if (0.0..=1.0).contains(&value) => Some(value),
        _ => {
            tracing::warn!(
                env_var = %name,
                value = %raw,
                "invalid unit float env value (expected 0.0..=1.0)"
            );
            None
        }
    }
}

pub(crate) fn parse_bool_from_env(name: &str) -> Option<bool> {
    let raw = std::env::var(name).ok()?;
    match raw.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => {
            tracing::warn!(
                env_var = %name,
                value = %raw,
                "invalid boolean env value"
            );
            None
        }
    }
}
