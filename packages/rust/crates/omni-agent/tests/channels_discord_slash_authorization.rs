#![allow(missing_docs)]

use omni_agent::{
    Channel, DiscordChannel, DiscordControlCommandPolicy, DiscordSessionPartition,
    DiscordSlashCommandPolicy,
};

const SCOPE_SESSION_STATUS: &str = "session.status";
const SCOPE_SESSION_MEMORY: &str = "session.memory";
const SCOPE_JOBS_SUMMARY: &str = "jobs.summary";

#[test]
fn discord_slash_authorization_falls_back_to_admin_users() {
    let channel = DiscordChannel::new_with_partition_and_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(vec!["ops".to_string()], None, Vec::new()),
        DiscordSessionPartition::GuildChannelUser,
    )
    .expect("policy should compile");

    assert!(channel.is_authorized_for_slash_command("ops", SCOPE_SESSION_STATUS));
    assert!(!channel.is_authorized_for_slash_command("alice", SCOPE_SESSION_STATUS));
}

#[test]
fn discord_slash_authorization_global_override_takes_precedence() {
    let slash_policy = DiscordSlashCommandPolicy {
        slash_command_allow_from: Some(vec!["owner".to_string()]),
        session_status_allow_from: Some(vec!["alice".to_string()]),
        ..DiscordSlashCommandPolicy::default()
    };
    let channel = DiscordChannel::new_with_partition_and_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(vec!["ops".to_string()], None, Vec::new())
            .with_slash_command_policy(slash_policy),
        DiscordSessionPartition::GuildChannelUser,
    )
    .expect("policy should compile");

    assert!(channel.is_authorized_for_slash_command("owner", SCOPE_SESSION_STATUS));
    assert!(
        !channel.is_authorized_for_slash_command("alice", SCOPE_SESSION_STATUS),
        "global override should ignore command-scoped allowlist"
    );
    assert!(
        !channel.is_authorized_for_slash_command("ops", SCOPE_SESSION_STATUS),
        "global override should ignore admin fallback"
    );
}

#[test]
fn discord_slash_authorization_command_scope_rules_are_partial() {
    let slash_policy = DiscordSlashCommandPolicy {
        session_memory_allow_from: Some(vec!["alice".to_string()]),
        ..DiscordSlashCommandPolicy::default()
    };
    let channel = DiscordChannel::new_with_partition_and_control_command_policy(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordControlCommandPolicy::new(vec!["ops".to_string()], None, Vec::new())
            .with_slash_command_policy(slash_policy),
        DiscordSessionPartition::GuildChannelUser,
    )
    .expect("policy should compile");

    assert!(channel.is_authorized_for_slash_command("alice", SCOPE_SESSION_MEMORY));
    assert!(channel.is_authorized_for_slash_command("ops", SCOPE_SESSION_MEMORY));
    assert!(!channel.is_authorized_for_slash_command("bob", SCOPE_SESSION_MEMORY));
    assert!(
        channel.is_authorized_for_slash_command("ops", SCOPE_JOBS_SUMMARY),
        "unconfigured command should still fall back to admin_users"
    );
}
