#![allow(missing_docs)]

use std::fs;

use omni_agent::{
    Channel, RecipientCommandAdminUsersMutation, TelegramChannel, TelegramControlCommandPolicy,
    TelegramSessionPartition, load_runtime_settings_from_paths,
};

fn build_channel_with_settings(settings_yaml: &str) -> (tempfile::TempDir, TelegramChannel) {
    let temp_dir = tempfile::tempdir().expect("tempdir");
    let system_settings_path = temp_dir.path().join("settings-system.yaml");
    let user_settings_path = temp_dir.path().join("settings-user.yaml");
    fs::write(&system_settings_path, settings_yaml).expect("write system settings");
    fs::write(&user_settings_path, "").expect("write user settings");

    let channel = TelegramChannel::new_with_partition_and_control_command_policy(
        "fake-token".to_string(),
        vec![],
        vec![],
        TelegramControlCommandPolicy::default(),
        TelegramSessionPartition::ChatUser,
    )
    .expect("policy should compile");
    channel.set_acl_reload_paths_for_test(system_settings_path, user_settings_path);
    channel.reload_acl_from_settings_for_test();
    (temp_dir, channel)
}

fn settings_paths(temp_dir: &tempfile::TempDir) -> (std::path::PathBuf, std::path::PathBuf) {
    (
        temp_dir.path().join("settings-system.yaml"),
        temp_dir.path().join("settings-user.yaml"),
    )
}

fn group_update_for_chat(chat_id: i64, user_id: i64, text: &str) -> serde_json::Value {
    serde_json::json!({
        "update_id": 90001,
        "message": {
            "message_id": 101,
            "text": text,
            "chat": { "id": chat_id, "type": "group", "title": "team" },
            "from": { "id": user_id, "username": format!("u{user_id}") }
        }
    })
}

fn group_update(user_id: i64, text: &str) -> serde_json::Value {
    group_update_for_chat(-200100, user_id, text)
}

fn topic_update(user_id: i64, text: &str, topic_id: i64) -> serde_json::Value {
    let mut update = group_update(user_id, text);
    update["message"]["message_thread_id"] = serde_json::json!(topic_id);
    update
}

#[test]
fn telegram_group_policy_disabled_rejects_group_messages() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: ""
  allowed_groups: "-200100"
  group_policy: "disabled"
"#,
    );

    assert!(
        channel
            .parse_update_message(&group_update(111, "hello"))
            .is_none()
    );
}

#[test]
fn telegram_group_policy_allowlist_uses_group_allow_from() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: ""
  allowed_groups: "-200100"
  group_policy: "allowlist"
  group_allow_from: "111"
"#,
    );

    assert!(
        channel
            .parse_update_message(&group_update(111, "hello"))
            .is_some()
    );
    assert!(
        channel
            .parse_update_message(&group_update(222, "hello"))
            .is_none()
    );
}

#[test]
fn telegram_group_policy_allowlist_falls_back_to_allowed_users_when_group_allow_from_unset() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: "999"
  allowed_groups: "-200100"
  group_policy: "allowlist"
"#,
    );

    assert!(
        channel
            .parse_update_message(&group_update(999, "hello"))
            .is_some()
    );
    assert!(
        channel
            .parse_update_message(&group_update(111, "hello"))
            .is_none()
    );
}

#[test]
fn telegram_group_policy_group_override_can_open_when_global_disabled() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: ""
  allowed_groups: "-200100"
  group_policy: "disabled"
  groups:
    "-200100":
      group_policy: "open"
"#,
    );

    assert!(
        channel
            .parse_update_message(&group_update(333, "hello"))
            .is_some()
    );
}

#[test]
fn telegram_group_policy_require_mention_blocks_plain_group_text() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: ""
  allowed_groups: "-200100"
  group_policy: "open"
  require_mention: true
"#,
    );

    assert!(
        channel
            .parse_update_message(&group_update(111, "hello everyone"))
            .is_none()
    );
    assert!(
        channel
            .parse_update_message(&group_update(111, "/session status"))
            .is_some()
    );
    assert!(
        channel
            .parse_update_message(&group_update(111, "@bot hello"))
            .is_some()
    );
}

#[test]
fn telegram_group_policy_topic_override_has_higher_priority() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: ""
  allowed_groups: "-200100"
  group_policy: "open"
  groups:
    "-200100":
      topics:
        "42":
          group_policy: "allowlist"
          allow_from: "111"
"#,
    );

    assert!(
        channel
            .parse_update_message(&topic_update(111, "topic hello", 42))
            .is_some()
    );
    assert!(
        channel
            .parse_update_message(&topic_update(222, "topic hello", 42))
            .is_none()
    );
    assert!(
        channel
            .parse_update_message(&topic_update(222, "other topic", 99))
            .is_some()
    );
}

#[test]
fn telegram_group_policy_wildcard_override_is_applied_before_specific_group_override() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: ""
  allowed_groups: "-200100,-200200"
  group_policy: "open"
  require_mention: false
  groups:
    "*":
      require_mention: true
    "-200100":
      require_mention: false
"#,
    );

    let group_specific = group_update_for_chat(-200100, 111, "plain group text");
    assert!(channel.parse_update_message(&group_specific).is_some());

    let wildcard_only = group_update_for_chat(-200200, 111, "plain group text");
    assert!(channel.parse_update_message(&wildcard_only).is_none());

    let wildcard_triggered = group_update_for_chat(-200200, 111, "/session status");
    assert!(channel.parse_update_message(&wildcard_triggered).is_some());
}

#[test]
fn telegram_group_policy_require_mention_accepts_reply_to_bot_trigger() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: ""
  allowed_groups: "-200100"
  group_policy: "open"
  require_mention: true
"#,
    );

    let mut update = group_update(111, "hello in reply");
    update["message"]["reply_to_message"] = serde_json::json!({
      "from": { "is_bot": true }
    });
    assert!(channel.parse_update_message(&update).is_some());
}

#[test]
fn telegram_group_policy_require_mention_accepts_entity_mention_trigger() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  allowed_users: ""
  allowed_groups: "-200100"
  group_policy: "open"
  require_mention: true
"#,
    );

    let mut update = group_update(111, "hello");
    update["message"]["entities"] = serde_json::json!([
      { "type": "mention", "offset": 0, "length": 5 }
    ]);
    assert!(channel.parse_update_message(&update).is_some());
}

#[test]
fn telegram_group_policy_group_admin_users_are_scoped_by_recipient() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100,-200200"
  groups:
    "-200100":
      admin_users: "111"
"#,
    );

    assert!(channel.is_authorized_for_control_command_for_recipient(
        "telegram:111",
        "/reset",
        "-200100",
    ));
    assert!(!channel.is_authorized_for_control_command_for_recipient("111", "/reset", "-200200",));
    assert!(!channel.is_authorized_for_control_command_for_recipient("111", "/reset", "12345",));
    assert!(channel.is_authorized_for_slash_command_for_recipient(
        "111",
        "session.status",
        "-200100",
    ));
    assert!(!channel.is_authorized_for_slash_command_for_recipient(
        "111",
        "session.status",
        "-200200",
    ));
}

#[test]
fn telegram_group_policy_topic_admin_users_override_group_and_wildcard_admin_users() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100,-200200"
  groups:
    "*":
      admin_users: "900"
    "-200100":
      admin_users: "111"
      topics:
        "42":
          admin_users: "222"
"#,
    );

    assert!(channel.is_authorized_for_control_command_for_recipient(
        "222",
        "/session partition",
        "-200100:42",
    ));
    assert!(!channel.is_authorized_for_control_command_for_recipient(
        "111",
        "/session partition",
        "-200100:42",
    ));
    assert!(channel.is_authorized_for_control_command_for_recipient(
        "111",
        "/session partition",
        "-200100:99",
    ));
    assert!(channel.is_authorized_for_control_command_for_recipient(
        "900",
        "/session partition",
        "-200200",
    ));
    assert!(channel.is_authorized_for_slash_command_for_recipient(
        "222",
        "session.memory",
        "-200100:42",
    ));
}

#[test]
fn telegram_group_policy_group_admin_users_do_not_override_explicit_global_control_deny() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  control_command_allow_from: ""
  allowed_users: ""
  allowed_groups: "-200100"
  groups:
    "-200100":
      admin_users: "111"
"#,
    );

    assert!(!channel.is_authorized_for_control_command_for_recipient("111", "/reset", "-200100",));
}

#[test]
fn telegram_group_policy_group_admin_users_do_not_override_explicit_global_slash_deny() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  slash_command_allow_from: ""
  allowed_users: ""
  allowed_groups: "-200100"
  groups:
    "-200100":
      admin_users: "111"
"#,
    );

    assert!(!channel.is_authorized_for_slash_command_for_recipient(
        "111",
        "session.status",
        "-200100",
    ));
}

#[test]
fn telegram_group_policy_recipient_admin_users_runtime_mutation_group_scope() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100"
"#,
    );

    assert_eq!(
        channel
            .recipient_command_admin_users("-200100")
            .expect("group recipient query should succeed"),
        None
    );

    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100",
                RecipientCommandAdminUsersMutation::Add(vec!["telegram:111".to_string()]),
            )
            .expect("group add should succeed"),
        Some(vec!["111".to_string()])
    );
    assert!(channel.is_authorized_for_control_command_for_recipient(
        "111",
        "/session partition",
        "-200100",
    ));

    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100",
                RecipientCommandAdminUsersMutation::Remove(vec!["111".to_string()]),
            )
            .expect("group remove should succeed"),
        None
    );
    assert_eq!(
        channel
            .recipient_command_admin_users("-200100")
            .expect("group recipient query should succeed"),
        None
    );
}

#[test]
fn telegram_group_policy_recipient_admin_users_runtime_mutation_topic_scope() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100"
"#,
    );

    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100:42",
                RecipientCommandAdminUsersMutation::Set(vec!["222".to_string(), "222".to_string()]),
            )
            .expect("topic set should succeed"),
        Some(vec!["222".to_string()])
    );
    assert!(channel.is_authorized_for_control_command_for_recipient(
        "222",
        "/session admin",
        "-200100:42",
    ));
    assert!(!channel.is_authorized_for_control_command_for_recipient(
        "222",
        "/session admin",
        "-200100:99",
    ));

    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100:42",
                RecipientCommandAdminUsersMutation::Clear,
            )
            .expect("topic clear should succeed"),
        None
    );
    assert_eq!(
        channel
            .recipient_command_admin_users("-200100:42")
            .expect("topic query should succeed"),
        None
    );
}

#[test]
fn telegram_group_policy_recipient_admin_users_runtime_mutation_group_topic_isolation() {
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100"
"#,
    );

    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100",
                RecipientCommandAdminUsersMutation::Set(vec!["111".to_string()]),
            )
            .expect("group set should succeed"),
        Some(vec!["111".to_string()])
    );
    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100:42",
                RecipientCommandAdminUsersMutation::Set(vec!["222".to_string()]),
            )
            .expect("topic set should succeed"),
        Some(vec!["222".to_string()])
    );

    assert!(!channel.is_authorized_for_control_command_for_recipient(
        "111",
        "/session admin",
        "-200100:42",
    ));
    assert!(channel.is_authorized_for_control_command_for_recipient(
        "111",
        "/session admin",
        "-200100:99",
    ));
    assert!(channel.is_authorized_for_control_command_for_recipient(
        "222",
        "/session admin",
        "-200100:42",
    ));
    assert!(!channel.is_authorized_for_control_command_for_recipient(
        "222",
        "/session admin",
        "-200100:99",
    ));
}

#[test]
fn telegram_group_policy_recipient_admin_users_runtime_mutation_rejects_invalid_identity_or_scope()
{
    let (_temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100"
"#,
    );

    assert!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100",
                RecipientCommandAdminUsersMutation::Set(vec!["alice".to_string()]),
            )
            .is_err(),
        "set should reject non-numeric identity"
    );
    assert!(
        channel.recipient_command_admin_users("12345").is_err(),
        "direct-chat recipient should not support delegated admin mutation"
    );
}

#[test]
fn telegram_group_policy_recipient_admin_users_runtime_mutation_persists_when_enabled() {
    let (temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100"
  session_admin_persist: true
"#,
    );

    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100",
                RecipientCommandAdminUsersMutation::Add(vec!["telegram:111".to_string()]),
            )
            .expect("group add should succeed"),
        Some(vec!["111".to_string()])
    );
    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100:42",
                RecipientCommandAdminUsersMutation::Set(vec![
                    "222".to_string(),
                    "telegram:333".to_string(),
                    "222".to_string(),
                ]),
            )
            .expect("topic set should succeed"),
        Some(vec!["222".to_string(), "333".to_string()])
    );

    let (system_settings_path, user_settings_path) = settings_paths(&temp_dir);
    let merged = load_runtime_settings_from_paths(&system_settings_path, &user_settings_path);
    let groups = merged
        .telegram
        .groups
        .expect("group overrides should persist");
    let group = groups.get("-200100").expect("group override should exist");
    assert_eq!(group.admin_users.as_deref(), Some("111"));
    let topics = group
        .topics
        .as_ref()
        .expect("topic override should persist");
    let topic = topics.get("42").expect("topic override should exist");
    assert_eq!(topic.admin_users.as_deref(), Some("222,333"));
}

#[test]
fn telegram_group_policy_recipient_admin_users_runtime_mutation_clear_prunes_persisted_entries() {
    let (temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100"
  session_admin_persist: true
"#,
    );

    channel
        .mutate_recipient_command_admin_users(
            "-200100",
            RecipientCommandAdminUsersMutation::Set(vec!["111".to_string()]),
        )
        .expect("group set should succeed");
    channel
        .mutate_recipient_command_admin_users(
            "-200100:42",
            RecipientCommandAdminUsersMutation::Set(vec!["222".to_string()]),
        )
        .expect("topic set should succeed");
    channel
        .mutate_recipient_command_admin_users(
            "-200100:42",
            RecipientCommandAdminUsersMutation::Clear,
        )
        .expect("topic clear should succeed");
    channel
        .mutate_recipient_command_admin_users("-200100", RecipientCommandAdminUsersMutation::Clear)
        .expect("group clear should succeed");

    let (system_settings_path, user_settings_path) = settings_paths(&temp_dir);
    let merged = load_runtime_settings_from_paths(&system_settings_path, &user_settings_path);
    assert!(
        merged.telegram.groups.is_none(),
        "clearing overrides should prune persisted group/topic admin entries"
    );
    let user_yaml =
        fs::read_to_string(user_settings_path).expect("user settings should be readable");
    assert!(!user_yaml.contains("admin_users"));
    assert!(!user_yaml.contains("-200100"));
    assert!(!user_yaml.contains("42"));
}

#[test]
fn telegram_group_policy_recipient_admin_users_runtime_mutation_does_not_persist_when_disabled() {
    let (temp_dir, channel) = build_channel_with_settings(
        r#"
telegram:
  admin_users: ""
  allowed_users: ""
  allowed_groups: "-200100"
  session_admin_persist: false
"#,
    );

    assert_eq!(
        channel
            .mutate_recipient_command_admin_users(
                "-200100",
                RecipientCommandAdminUsersMutation::Set(vec!["111".to_string()]),
            )
            .expect("group set should succeed"),
        Some(vec!["111".to_string()])
    );
    assert_eq!(
        channel
            .recipient_command_admin_users("-200100")
            .expect("group query should succeed"),
        Some(vec!["111".to_string()])
    );

    let (system_settings_path, user_settings_path) = settings_paths(&temp_dir);
    let user_yaml =
        fs::read_to_string(&user_settings_path).expect("user settings should be readable");
    assert!(
        user_yaml.trim().is_empty(),
        "persistence-disabled mode must not mutate user settings"
    );

    channel.reload_acl_from_settings_for_test();
    assert_eq!(
        channel
            .recipient_command_admin_users("-200100")
            .expect("group query should succeed"),
        None,
        "process-local override should disappear after reload when persistence is disabled"
    );

    let merged = load_runtime_settings_from_paths(&system_settings_path, &user_settings_path);
    assert!(merged.telegram.groups.is_none());
}
