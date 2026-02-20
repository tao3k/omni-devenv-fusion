#![allow(missing_docs)]

use omni_agent::{Channel, DiscordChannel, DiscordSessionPartition};

fn discord_event(
    message_id: &str,
    content: &str,
    channel_id: &str,
    guild_id: Option<&str>,
    user_id: &str,
    username: Option<&str>,
) -> serde_json::Value {
    let mut payload = serde_json::json!({
        "id": message_id,
        "content": content,
        "channel_id": channel_id,
        "author": {
            "id": user_id
        }
    });
    if let Some(guild) = guild_id {
        payload["guild_id"] = serde_json::Value::String(guild.to_string());
    }
    if let Some(name) = username {
        payload["author"]["username"] = serde_json::Value::String(name.to_string());
    }
    payload
}

#[test]
fn discord_parse_gateway_message_allows_allowed_user() {
    let channel = DiscordChannel::new("fake-token".to_string(), vec!["alice".to_string()], vec![]);
    let event = discord_event("1", "hello", "2001", Some("3001"), "1001", Some("alice"));

    let parsed = channel
        .parse_gateway_message(&event)
        .expect("message should parse");
    assert_eq!(parsed.sender, "1001");
    assert_eq!(parsed.recipient, "2001");
    assert_eq!(parsed.channel, "discord");
}

#[test]
fn discord_parse_gateway_message_allows_allowed_guild() {
    let channel = DiscordChannel::new("fake-token".to_string(), vec![], vec!["3001".to_string()]);
    let event = discord_event("1", "hello", "2001", Some("3001"), "1001", Some("unknown"));

    let parsed = channel
        .parse_gateway_message(&event)
        .expect("message should parse");
    assert_eq!(parsed.sender, "1001");
    assert_eq!(parsed.session_key, "3001:2001:1001");
}

#[test]
fn discord_parse_gateway_message_rejects_unauthorized_sender() {
    let channel = DiscordChannel::new("fake-token".to_string(), vec!["owner".to_string()], vec![]);
    let event = discord_event("1", "hello", "2001", Some("3001"), "1001", Some("alice"));

    assert!(channel.parse_gateway_message(&event).is_none());
}

#[test]
fn discord_parse_gateway_message_rejects_empty_content() {
    let channel = DiscordChannel::new("fake-token".to_string(), vec!["*".to_string()], vec![]);
    let event = discord_event("1", "   ", "2001", Some("3001"), "1001", Some("alice"));

    assert!(channel.parse_gateway_message(&event).is_none());
}

#[test]
fn discord_parse_gateway_message_defaults_dm_scope() {
    let channel = DiscordChannel::new("fake-token".to_string(), vec!["*".to_string()], vec![]);
    let event = discord_event("1", "hello", "2001", None, "1001", Some("alice"));

    let parsed = channel
        .parse_gateway_message(&event)
        .expect("message should parse");
    assert_eq!(parsed.session_key, "dm:2001:1001");
}

#[test]
fn discord_parse_gateway_message_partition_channel_only() {
    let channel = DiscordChannel::new_with_partition(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordSessionPartition::ChannelOnly,
    );
    let event_a = discord_event("1", "hello", "2001", Some("3001"), "1001", Some("alice"));
    let event_b = discord_event("2", "hello", "2001", Some("3001"), "1002", Some("bob"));

    let parsed_a = channel
        .parse_gateway_message(&event_a)
        .expect("message A should parse");
    let parsed_b = channel
        .parse_gateway_message(&event_b)
        .expect("message B should parse");
    assert_eq!(parsed_a.session_key, "3001:2001");
    assert_eq!(parsed_a.session_key, parsed_b.session_key);
}

#[test]
fn discord_parse_gateway_message_partition_user_only() {
    let channel = DiscordChannel::new_with_partition(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordSessionPartition::UserOnly,
    );
    let event_a = discord_event("1", "hello", "2001", Some("3001"), "1001", Some("alice"));
    let event_b = discord_event("2", "hello", "2002", Some("3001"), "1001", Some("alice"));

    let parsed_a = channel
        .parse_gateway_message(&event_a)
        .expect("message A should parse");
    let parsed_b = channel
        .parse_gateway_message(&event_b)
        .expect("message B should parse");
    assert_eq!(parsed_a.session_key, "1001");
    assert_eq!(parsed_a.session_key, parsed_b.session_key);
}

#[test]
fn discord_parse_gateway_message_partition_guild_user() {
    let channel = DiscordChannel::new_with_partition(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordSessionPartition::GuildUser,
    );
    let event_a = discord_event("1", "hello", "2001", Some("3001"), "1001", Some("alice"));
    let event_b = discord_event("2", "hello", "2002", Some("3001"), "1001", Some("alice"));
    let event_c = discord_event("3", "hello", "2003", Some("3002"), "1001", Some("alice"));

    let parsed_a = channel
        .parse_gateway_message(&event_a)
        .expect("message A should parse");
    let parsed_b = channel
        .parse_gateway_message(&event_b)
        .expect("message B should parse");
    let parsed_c = channel
        .parse_gateway_message(&event_c)
        .expect("message C should parse");
    assert_eq!(parsed_a.session_key, "3001:1001");
    assert_eq!(parsed_a.session_key, parsed_b.session_key);
    assert_ne!(parsed_a.session_key, parsed_c.session_key);
}

#[test]
fn discord_session_partition_runtime_toggle_changes_strategy() {
    let channel = DiscordChannel::new_with_partition(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        DiscordSessionPartition::GuildChannelUser,
    );
    let event_a = discord_event("1", "hello", "2001", Some("3001"), "1001", Some("alice"));
    let event_b = discord_event("2", "hello", "2001", Some("3001"), "1002", Some("bob"));

    let parsed_a = channel
        .parse_gateway_message(&event_a)
        .expect("message A should parse");
    let parsed_b = channel
        .parse_gateway_message(&event_b)
        .expect("message B should parse");
    assert_ne!(parsed_a.session_key, parsed_b.session_key);

    channel
        .set_session_partition_mode("channel")
        .expect("mode should be accepted");

    let parsed_a_shared = channel
        .parse_gateway_message(&event_a)
        .expect("message A shared should parse");
    let parsed_b_shared = channel
        .parse_gateway_message(&event_b)
        .expect("message B shared should parse");
    assert_eq!(parsed_a_shared.session_key, "3001:2001");
    assert_eq!(parsed_a_shared.session_key, parsed_b_shared.session_key);
}

#[test]
fn discord_session_partition_mode_rejects_invalid_value() {
    let channel = DiscordChannel::new("fake-token".to_string(), vec!["*".to_string()], vec![]);
    let error = channel
        .set_session_partition_mode("invalid")
        .expect_err("invalid mode should fail");
    assert!(
        error
            .to_string()
            .contains("invalid discord session partition mode")
    );
}
