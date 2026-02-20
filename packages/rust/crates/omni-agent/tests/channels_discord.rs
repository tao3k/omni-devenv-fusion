#![allow(missing_docs)]

use omni_agent::{Channel, DiscordChannel, DiscordControlCommandPolicy};

#[test]
fn discord_channel_name() {
    let channel = DiscordChannel::new("fake-token".to_string(), vec!["*".to_string()], vec![]);
    assert_eq!(channel.name(), "discord");
}

#[test]
fn discord_control_command_authorization_supports_selector_rules() {
    let channel = DiscordChannel::new_with_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(
            vec!["ops".to_string()],
            None,
            vec!["/session partition=>alice,1001".to_string()],
        ),
    )
    .expect("rule specs should compile");

    assert!(channel.is_authorized_for_control_command("alice", "/session partition on"));
    assert!(channel.is_authorized_for_control_command("1001", "/session partition json"));
    assert!(
        !channel.is_authorized_for_control_command("ops", "/session partition on"),
        "matched rule should take precedence over admin_users fallback",
    );
    assert!(
        channel.is_authorized_for_control_command("ops", "/resume status"),
        "non-matching commands should fall back to admin_users",
    );
}

#[test]
fn discord_control_command_authorization_normalizes_rule_and_sender_identities() {
    let channel = DiscordChannel::new_with_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(
            vec!["ops".to_string()],
            None,
            vec!["/session partition=>@Owner".to_string()],
        ),
    )
    .expect("rule specs should compile");

    assert!(channel.is_authorized_for_control_command("@OWNER", "/session partition chat"));
    assert!(channel.is_authorized_for_control_command("owner", "/session partition user"));
}

#[test]
fn discord_control_command_authorization_supports_selector_wildcards() {
    let channel = DiscordChannel::new_with_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(
            vec!["ops".to_string()],
            None,
            vec!["session.*=>owner".to_string(), "/reset=>owner".to_string()],
        ),
    )
    .expect("rule specs should compile");

    assert!(channel.is_authorized_for_control_command("owner", "/session partition chat"));
    assert!(channel.is_authorized_for_control_command("owner", "/session reset"));
    assert!(channel.is_authorized_for_control_command("owner", "/reset"));
    assert!(!channel.is_authorized_for_control_command("owner", "/resume status"));
}

#[test]
fn discord_control_command_authorization_supports_cmd_prefix_and_bot_suffix_in_rules() {
    let channel = DiscordChannel::new_with_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(
            vec!["ops".to_string()],
            None,
            vec![
                "cmd:/session partition=>owner".to_string(),
                "cmd:/reset@mybot=>owner".to_string(),
            ],
        ),
    )
    .expect("rule specs should compile");

    assert!(channel.is_authorized_for_control_command("owner", "/session@mybot partition on"));
    assert!(channel.is_authorized_for_control_command("owner", "/reset"));
    assert!(
        !channel.is_authorized_for_control_command("ops", "/session partition on"),
        "matched command-scoped rule should still take precedence over admin_users",
    );
}

#[test]
fn discord_control_command_authorization_rejects_invalid_wildcard_selector() {
    let result = DiscordChannel::new_with_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(
            vec!["ops".to_string()],
            None,
            vec!["session*=>owner".to_string()],
        ),
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
fn discord_control_command_authorization_control_allow_from_overrides_rules_and_admins() {
    let channel = DiscordChannel::new_with_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(
            vec!["ops".to_string()],
            Some(vec!["owner".to_string()]),
            vec!["/session partition=>alice".to_string()],
        ),
    )
    .expect("authorization policy should compile");

    assert!(channel.is_authorized_for_control_command("owner", "/session partition on"));
    assert!(channel.is_authorized_for_control_command("owner", "/resume"));
    assert!(
        !channel.is_authorized_for_control_command("alice", "/session partition on"),
        "control_command_allow_from should override command-scoped rules",
    );
    assert!(
        !channel.is_authorized_for_control_command("ops", "/resume"),
        "control_command_allow_from should override admin_users fallback",
    );
}

#[test]
fn discord_control_command_authorization_control_allow_from_empty_denies_all() {
    let channel = DiscordChannel::new_with_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(
            vec!["*".to_string()],
            Some(Vec::new()),
            vec!["/reset,/clear=>owner".to_string()],
        ),
    )
    .expect("authorization policy should compile");

    assert!(!channel.is_authorized_for_control_command("owner", "/reset"));
    assert!(!channel.is_authorized_for_control_command("alice", "/resume"));
}

#[test]
fn discord_control_command_authorization_rejects_invalid_rule_specs() {
    let result = DiscordChannel::new_with_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(
            vec!["ops".to_string()],
            None,
            vec!["invalid-spec-without-separator".to_string()],
        ),
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

#[tokio::test]
async fn discord_listen_returns_not_implemented_error() {
    let channel = DiscordChannel::new("fake-token".to_string(), vec!["*".to_string()], vec![]);
    let (tx, _rx) = tokio::sync::mpsc::channel(1);
    let error = channel
        .listen(tx)
        .await
        .expect_err("listen should be unimplemented for skeleton");
    assert!(error.to_string().contains("not implemented"));
}
