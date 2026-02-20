#![allow(missing_docs)]

use omni_agent::{Channel, TelegramChannel, TelegramSessionPartition};

#[test]
fn telegram_control_command_authorization_supports_selector_rules() {
    let channel = TelegramChannel::new_with_partition_and_admin_users_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["2001".to_string()],
        vec!["/session partition=>1001,1002".to_string()],
        TelegramSessionPartition::ChatUser,
    )
    .expect("rule specs should compile");

    assert!(channel.is_authorized_for_control_command("1001", "/session partition on"));
    assert!(channel.is_authorized_for_control_command("1001", "/session partition json"));
    assert!(channel.is_authorized_for_control_command("1002", "/session partition chat"));
    assert!(
        !channel.is_authorized_for_control_command("2001", "/session partition on"),
        "matched rule should take precedence over admin_users fallback",
    );
    assert!(
        channel.is_authorized_for_control_command("2001", "/resume status"),
        "non-matching commands should fall back to admin_users",
    );
}

#[test]
fn telegram_control_command_authorization_normalizes_rule_and_sender_identities() {
    let channel = TelegramChannel::new_with_partition_and_admin_users_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["2001".to_string()],
        vec!["/session partition=>telegram:1001".to_string()],
        TelegramSessionPartition::ChatUser,
    )
    .expect("rule specs should compile");

    assert!(channel.is_authorized_for_control_command("1001", "/session partition chat"));
    assert!(channel.is_authorized_for_control_command("tg:1001", "/session partition user"));
}

#[test]
fn telegram_control_command_authorization_supports_selector_wildcards_and_bot_mentions() {
    let channel = TelegramChannel::new_with_partition_and_admin_users_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["2001".to_string()],
        vec!["session.*=>3001".to_string(), "/reset=>3001".to_string()],
        TelegramSessionPartition::ChatUser,
    )
    .expect("rule specs should compile");

    assert!(channel.is_authorized_for_control_command("3001", "/session partition chat"));
    assert!(channel.is_authorized_for_control_command("3001", "/session reset"));
    assert!(channel.is_authorized_for_control_command("3001", "/reset@mybot"));
    assert!(!channel.is_authorized_for_control_command("3001", "/resume status"));
}

#[test]
fn telegram_control_command_authorization_supports_cmd_prefix_and_bot_suffix_in_rules() {
    let channel = TelegramChannel::new_with_partition_and_admin_users_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["4001".to_string()],
        vec![
            "cmd:/session partition=>3001".to_string(),
            "cmd:/reset@mybot=>3001".to_string(),
        ],
        TelegramSessionPartition::ChatUser,
    )
    .expect("rule specs should compile");

    assert!(channel.is_authorized_for_control_command("3001", "/session@mybot partition on"));
    assert!(channel.is_authorized_for_control_command("3001", "/reset"));
    assert!(
        !channel.is_authorized_for_control_command("4001", "/session partition on"),
        "matched command-scoped rule should still take precedence over admin_users",
    );
}

#[test]
fn telegram_control_command_authorization_rejects_invalid_wildcard_selector() {
    let result = TelegramChannel::new_with_partition_and_admin_users_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["4001".to_string()],
        vec!["session*=>owner".to_string()],
        TelegramSessionPartition::ChatUser,
    );

    let error = match result {
        Ok(_) => panic!("invalid wildcard selector should fail fast"),
        Err(error) => error,
    };
    assert!(
        error
            .to_string()
            .contains("wildcard `*` is only allowed as full selector `*` or suffix `.*`"),
        "unexpected error: {error}",
    );
}

#[test]
fn telegram_control_command_authorization_control_allow_from_overrides_rules_and_admins() {
    let channel = TelegramChannel::new_with_partition_and_admin_users_and_control_command_allow_from_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["4001".to_string()],
        Some(vec!["3001".to_string()]),
        vec!["/session partition=>1001".to_string()],
        TelegramSessionPartition::ChatUser,
    )
    .expect("authorization policy should compile");

    assert!(channel.is_authorized_for_control_command("3001", "/session partition on"));
    assert!(channel.is_authorized_for_control_command("3001", "/resume"));
    assert!(
        !channel.is_authorized_for_control_command("1001", "/session partition on"),
        "control_command_allow_from should override command-scoped rules",
    );
    assert!(
        !channel.is_authorized_for_control_command("4001", "/resume"),
        "control_command_allow_from should override admin_users fallback",
    );
}

#[test]
fn telegram_control_command_authorization_control_allow_from_empty_denies_all() {
    let channel = TelegramChannel::new_with_partition_and_admin_users_and_control_command_allow_from_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["*".to_string()],
        Some(Vec::new()),
        vec!["/reset,/clear=>3001".to_string()],
        TelegramSessionPartition::ChatUser,
    )
    .expect("authorization policy should compile");

    assert!(!channel.is_authorized_for_control_command("3001", "/reset"));
    assert!(!channel.is_authorized_for_control_command("1001", "/resume"));
}

#[test]
fn telegram_control_command_authorization_ignores_invalid_control_allow_from_entries() {
    let channel = TelegramChannel::new_with_partition_and_admin_users_and_control_command_allow_from_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["owner".to_string(), "2001".to_string()],
        Some(vec!["alice".to_string(), "1001".to_string()]),
        Vec::new(),
        TelegramSessionPartition::ChatUser,
    )
    .expect("authorization policy should compile");

    assert!(
        channel.is_authorized_for_control_command("1001", "/session partition on"),
        "numeric entries should remain authorized after normalization",
    );
    assert!(
        !channel.is_authorized_for_control_command("alice", "/session partition on"),
        "username entries should be ignored by normalization",
    );
    assert!(
        !channel.is_authorized_for_control_command("2001", "/session partition on"),
        "global control allowlist override should still take precedence over admin fallback",
    );
}

#[test]
fn telegram_control_command_authorization_rejects_invalid_rule_specs() {
    let result = TelegramChannel::new_with_partition_and_admin_users_and_command_rule_specs(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["4001".to_string()],
        vec!["invalid-spec-without-separator".to_string()],
        TelegramSessionPartition::ChatUser,
    );

    let error = match result {
        Ok(_) => panic!("invalid rule specs should fail fast"),
        Err(error) => error,
    };
    assert!(
        error
            .to_string()
            .contains("expected `<command-selector>=>user1,user2`"),
        "unexpected error: {error}",
    );
}

#[test]
fn telegram_control_command_authorization_does_not_implicitly_promote_allowed_users() {
    let channel = TelegramChannel::new_with_partition(
        "fake-token".to_string(),
        vec!["1001".to_string()],
        vec![],
        TelegramSessionPartition::ChatUser,
    );

    assert!(
        !channel.is_authorized_for_control_command("1001", "/reset"),
        "allowed_users should not implicitly grant privileged command access"
    );
}
