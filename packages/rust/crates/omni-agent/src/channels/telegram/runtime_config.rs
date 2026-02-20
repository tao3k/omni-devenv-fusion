//! Telegram foreground runtime configuration (queueing, concurrency, timeout).

use crate::config::{TelegramSettings, load_runtime_settings};

const DEFAULT_INBOUND_QUEUE_CAPACITY: usize = 100;
const DEFAULT_FOREGROUND_QUEUE_CAPACITY: usize = 256;
const DEFAULT_FOREGROUND_MAX_IN_FLIGHT_MESSAGES: usize = 16;
const DEFAULT_FOREGROUND_TURN_TIMEOUT_SECS: u64 = 300;

#[derive(Debug, Clone, Copy)]
pub struct TelegramRuntimeConfig {
    pub inbound_queue_capacity: usize,
    pub foreground_queue_capacity: usize,
    pub foreground_max_in_flight_messages: usize,
    pub foreground_turn_timeout_secs: u64,
}

impl Default for TelegramRuntimeConfig {
    fn default() -> Self {
        Self {
            inbound_queue_capacity: DEFAULT_INBOUND_QUEUE_CAPACITY,
            foreground_queue_capacity: DEFAULT_FOREGROUND_QUEUE_CAPACITY,
            foreground_max_in_flight_messages: DEFAULT_FOREGROUND_MAX_IN_FLIGHT_MESSAGES,
            foreground_turn_timeout_secs: DEFAULT_FOREGROUND_TURN_TIMEOUT_SECS,
        }
    }
}

impl TelegramRuntimeConfig {
    pub fn from_env() -> Self {
        let settings = load_runtime_settings();
        Self::from_lookup(|name| std::env::var(name).ok(), Some(&settings.telegram))
    }

    #[doc(hidden)]
    pub fn from_lookup_for_test<F>(lookup: F, settings: Option<&TelegramSettings>) -> Self
    where
        F: Fn(&str) -> Option<String>,
    {
        Self::from_lookup(lookup, settings)
    }

    fn from_lookup<F>(lookup: F, settings: Option<&TelegramSettings>) -> Self
    where
        F: Fn(&str) -> Option<String>,
    {
        let defaults = Self::default();
        Self {
            inbound_queue_capacity: resolve_usize(
                &lookup,
                "OMNI_AGENT_TELEGRAM_INBOUND_QUEUE_CAPACITY",
                settings.and_then(|s| s.inbound_queue_capacity),
                defaults.inbound_queue_capacity,
            ),
            foreground_queue_capacity: resolve_usize(
                &lookup,
                "OMNI_AGENT_TELEGRAM_FOREGROUND_QUEUE_CAPACITY",
                settings.and_then(|s| s.foreground_queue_capacity),
                defaults.foreground_queue_capacity,
            ),
            foreground_max_in_flight_messages: resolve_usize(
                &lookup,
                "OMNI_AGENT_TELEGRAM_FOREGROUND_MAX_IN_FLIGHT",
                settings.and_then(|s| s.foreground_max_in_flight_messages),
                defaults.foreground_max_in_flight_messages,
            ),
            foreground_turn_timeout_secs: resolve_u64(
                &lookup,
                "OMNI_AGENT_TELEGRAM_FOREGROUND_TURN_TIMEOUT_SECS",
                settings.and_then(|s| s.foreground_turn_timeout_secs),
                defaults.foreground_turn_timeout_secs,
            ),
        }
    }
}

fn resolve_usize<F>(lookup: &F, name: &str, setting_value: Option<usize>, default: usize) -> usize
where
    F: Fn(&str) -> Option<String>,
{
    if let Some(raw) = lookup(name) {
        match raw.parse::<usize>() {
            Ok(value) if value > 0 => return value,
            _ => tracing::warn!(
                env_var = %name,
                value = %raw,
                "invalid runtime config env value; using settings/default"
            ),
        }
    }
    match setting_value {
        Some(value) if value > 0 => value,
        Some(value) => {
            tracing::warn!(
                setting = %name,
                value,
                default,
                "invalid runtime config settings value; using default"
            );
            default
        }
        None => default,
    }
}

fn resolve_u64<F>(lookup: &F, name: &str, setting_value: Option<u64>, default: u64) -> u64
where
    F: Fn(&str) -> Option<String>,
{
    if let Some(raw) = lookup(name) {
        match raw.parse::<u64>() {
            Ok(value) if value > 0 => return value,
            _ => tracing::warn!(
                env_var = %name,
                value = %raw,
                "invalid runtime config env value; using settings/default"
            ),
        }
    }
    match setting_value {
        Some(value) if value > 0 => value,
        Some(value) => {
            tracing::warn!(
                setting = %name,
                value,
                default,
                "invalid runtime config settings value; using default"
            );
            default
        }
        None => default,
    }
}
