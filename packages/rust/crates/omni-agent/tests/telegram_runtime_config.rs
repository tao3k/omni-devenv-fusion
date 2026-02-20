#![allow(missing_docs)]

use std::collections::HashMap;

use omni_agent::{TelegramRuntimeConfig, TelegramSettings};

#[test]
fn defaults_are_applied_when_env_missing() {
    let cfg = TelegramRuntimeConfig::from_lookup_for_test(|_| None, None);
    assert_eq!(cfg.inbound_queue_capacity, 100);
    assert_eq!(cfg.foreground_queue_capacity, 256);
    assert_eq!(cfg.foreground_max_in_flight_messages, 16);
    assert_eq!(cfg.foreground_turn_timeout_secs, 300);
}

#[test]
fn valid_env_values_override_defaults() {
    let values = HashMap::from([
        (
            "OMNI_AGENT_TELEGRAM_INBOUND_QUEUE_CAPACITY",
            "200".to_string(),
        ),
        (
            "OMNI_AGENT_TELEGRAM_FOREGROUND_QUEUE_CAPACITY",
            "512".to_string(),
        ),
        (
            "OMNI_AGENT_TELEGRAM_FOREGROUND_MAX_IN_FLIGHT",
            "32".to_string(),
        ),
        (
            "OMNI_AGENT_TELEGRAM_FOREGROUND_TURN_TIMEOUT_SECS",
            "600".to_string(),
        ),
    ]);
    let cfg = TelegramRuntimeConfig::from_lookup_for_test(|name| values.get(name).cloned(), None);
    assert_eq!(cfg.inbound_queue_capacity, 200);
    assert_eq!(cfg.foreground_queue_capacity, 512);
    assert_eq!(cfg.foreground_max_in_flight_messages, 32);
    assert_eq!(cfg.foreground_turn_timeout_secs, 600);
}

#[test]
fn invalid_values_fall_back_to_defaults() {
    let values = HashMap::from([
        (
            "OMNI_AGENT_TELEGRAM_INBOUND_QUEUE_CAPACITY",
            "0".to_string(),
        ),
        (
            "OMNI_AGENT_TELEGRAM_FOREGROUND_QUEUE_CAPACITY",
            "-3".to_string(),
        ),
        (
            "OMNI_AGENT_TELEGRAM_FOREGROUND_MAX_IN_FLIGHT",
            "not-a-number".to_string(),
        ),
        (
            "OMNI_AGENT_TELEGRAM_FOREGROUND_TURN_TIMEOUT_SECS",
            "0".to_string(),
        ),
    ]);
    let cfg = TelegramRuntimeConfig::from_lookup_for_test(|name| values.get(name).cloned(), None);
    assert_eq!(cfg.inbound_queue_capacity, 100);
    assert_eq!(cfg.foreground_queue_capacity, 256);
    assert_eq!(cfg.foreground_max_in_flight_messages, 16);
    assert_eq!(cfg.foreground_turn_timeout_secs, 300);
}

#[test]
fn settings_values_used_when_env_missing() {
    let settings = TelegramSettings {
        inbound_queue_capacity: Some(123),
        foreground_queue_capacity: Some(456),
        foreground_max_in_flight_messages: Some(7),
        foreground_turn_timeout_secs: Some(42),
        ..Default::default()
    };
    let cfg = TelegramRuntimeConfig::from_lookup_for_test(|_| None, Some(&settings));
    assert_eq!(cfg.inbound_queue_capacity, 123);
    assert_eq!(cfg.foreground_queue_capacity, 456);
    assert_eq!(cfg.foreground_max_in_flight_messages, 7);
    assert_eq!(cfg.foreground_turn_timeout_secs, 42);
}
