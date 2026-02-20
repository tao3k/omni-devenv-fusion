use anyhow::{Context, Result, bail};

use crate::config::load_runtime_settings;

pub(super) const DEFAULT_GATE_KEY_PREFIX: &str = "omni-agent:session-gate";
pub(super) const DEFAULT_GATE_LEASE_TTL_SECS: u64 = 30;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) enum SessionGateBackendMode {
    Auto,
    Memory,
    Valkey,
}

#[derive(Debug, Clone)]
pub(super) struct SessionGateRuntimeConfig {
    pub(super) backend_mode: SessionGateBackendMode,
    pub(super) valkey_url: Option<String>,
    pub(super) key_prefix: String,
    pub(super) lease_ttl_secs: u64,
    pub(super) acquire_timeout_secs: Option<u64>,
}

impl SessionGateRuntimeConfig {
    pub(super) fn from_env() -> Result<Self> {
        let settings = load_runtime_settings();
        let telegram = &settings.telegram;
        let session = &settings.session;

        let valkey_url = non_empty_env("VALKEY_URL")
            .or_else(|| session.valkey_url.clone())
            .and_then(non_empty_string);

        let backend_mode = match non_empty_env("OMNI_AGENT_TELEGRAM_SESSION_GATE_BACKEND")
            .or_else(|| telegram.foreground_session_gate_backend.clone())
            .and_then(non_empty_string)
        {
            Some(raw) => parse_backend_mode(&raw)?,
            None => {
                if valkey_url.is_some() {
                    SessionGateBackendMode::Valkey
                } else {
                    SessionGateBackendMode::Memory
                }
            }
        };

        let key_prefix = non_empty_env("OMNI_AGENT_TELEGRAM_SESSION_GATE_KEY_PREFIX")
            .or_else(|| telegram.foreground_session_gate_key_prefix.clone())
            .and_then(non_empty_string)
            .unwrap_or_else(|| DEFAULT_GATE_KEY_PREFIX.to_string());

        let lease_ttl_secs = parse_env_or_setting_u64(
            "OMNI_AGENT_TELEGRAM_SESSION_GATE_LEASE_TTL_SECS",
            telegram.foreground_session_gate_lease_ttl_secs,
            DEFAULT_GATE_LEASE_TTL_SECS,
        )?;
        if lease_ttl_secs == 0 {
            bail!("telegram session gate lease ttl must be greater than 0 seconds");
        }

        let acquire_timeout_secs = parse_env_or_setting_optional_u64(
            "OMNI_AGENT_TELEGRAM_SESSION_GATE_ACQUIRE_TIMEOUT_SECS",
            telegram.foreground_session_gate_acquire_timeout_secs,
        )?;

        Ok(Self {
            backend_mode,
            valkey_url,
            key_prefix,
            lease_ttl_secs,
            acquire_timeout_secs,
        })
    }
}

fn parse_backend_mode(raw: &str) -> Result<SessionGateBackendMode> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "auto" => Ok(SessionGateBackendMode::Auto),
        "memory" => Ok(SessionGateBackendMode::Memory),
        "valkey" | "redis" => Ok(SessionGateBackendMode::Valkey),
        other => {
            bail!("invalid telegram session gate backend `{other}`; expected auto|memory|valkey")
        }
    }
}

fn non_empty_env(name: &str) -> Option<String> {
    std::env::var(name).ok().and_then(non_empty_string)
}

fn non_empty_string(value: String) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}

fn parse_env_or_setting_u64(name: &str, setting: Option<u64>, default: u64) -> Result<u64> {
    match non_empty_env(name) {
        Some(raw) => raw
            .parse::<u64>()
            .with_context(|| format!("invalid value for {name}: `{raw}`")),
        None => Ok(setting.unwrap_or(default)),
    }
}

fn parse_env_or_setting_optional_u64(name: &str, setting: Option<u64>) -> Result<Option<u64>> {
    match non_empty_env(name) {
        Some(raw) => {
            let parsed = raw
                .parse::<u64>()
                .with_context(|| format!("invalid value for {name}: `{raw}`"))?;
            Ok((parsed > 0).then_some(parsed))
        }
        None => Ok(setting.filter(|value| *value > 0)),
    }
}
