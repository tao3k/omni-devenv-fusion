#![allow(missing_docs)]

use std::path::PathBuf;

use omni_agent::load_runtime_settings_from_paths;
use tempfile::TempDir;

fn write_file(path: PathBuf, content: &str) {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).expect("create parent dir");
    }
    std::fs::write(path, content).expect("write yaml");
}

#[test]
fn merge_user_overrides_system() {
    let tmp = TempDir::new().expect("tempdir");
    let system = tmp.path().join("packages/conf/settings.yaml");
    let user = tmp.path().join(".config/omni-dev-fusion/settings.yaml");

    write_file(
        system.clone(),
        r#"
mcp:
  agent_pool_size: 4
  agent_handshake_timeout_secs: 30
  agent_connect_retries: 2
  agent_connect_retry_backoff_ms: 500
  agent_tool_timeout_secs: 120
  agent_list_tools_cache_ttl_ms: 900
  agent_discover_cache_enabled: true
  agent_discover_cache_key_prefix: "system-discover"
  agent_discover_cache_ttl_secs: 45
telegram:
  allowed_users: "1001"
  allowed_groups: "-2001"
  session_admin_persist: true
  admin_users: "1001"
  control_command_allow_from: "1001,ops"
  admin_command_rules: "/session partition=>1001"
  slash_command_allow_from: "1001,ops"
  slash_session_status_allow_from: "observer"
  slash_session_budget_allow_from: "observer"
  slash_session_memory_allow_from: "observer"
  slash_session_feedback_allow_from: "editor"
  slash_job_allow_from: "ops"
  slash_jobs_allow_from: "ops"
  slash_bg_allow_from: "runner"
  mode: "webhook"
  webhook_dedup_backend: "valkey"
  inbound_queue_capacity: 100
  foreground_queue_capacity: 256
  foreground_max_in_flight_messages: 16
  foreground_turn_timeout_secs: 300
  session_partition: "chat"
  max_tool_rounds: 30
discord:
  allowed_users: "dx1"
  allowed_guilds: "3001"
  admin_users: "dx1"
  control_command_allow_from: "dx1,ops"
  admin_command_rules: "/session partition=>dx1"
  slash_command_allow_from: "dx1,ops"
  slash_session_status_allow_from: "auditor"
  slash_session_budget_allow_from: "auditor"
  slash_session_memory_allow_from: "auditor"
  slash_session_feedback_allow_from: "ops"
  slash_job_allow_from: "ops"
  slash_jobs_allow_from: "ops"
  slash_bg_allow_from: "runner"
  ingress_bind: "0.0.0.0:8082"
  ingress_path: "/discord/ingress"
  ingress_secret_token: "system-secret"
  session_partition: "guild_channel_user"
  inbound_queue_capacity: 512
  turn_timeout_secs: 120
session:
  window_max_turns: 512
  consolidation_async: true
  context_budget_tokens: 5000
  context_budget_reserve_tokens: 256
  context_budget_strategy: "recent_first"
  summary_max_segments: 6
  summary_max_chars: 256
  redis_prefix: "system-prefix"
  ttl_secs: 3600
embedding:
  model: "ollama/qwen3-embedding:0.6b"
  litellm_model: "ollama/qwen3-embedding:0.6b"
  dimension: 1024
  client_url: "http://127.0.0.1:3002"
memory:
  persistence_backend: "local"
  persistence_strict_startup: true
  recall_credit_enabled: false
  recall_credit_max_candidates: 2
  decay_enabled: false
  decay_every_turns: 12
  decay_factor: 0.95
  gate_promote_threshold: 0.77
  gate_obsolete_threshold: 0.33
  gate_promote_min_usage: 4
  gate_obsolete_min_usage: 3
  gate_promote_failure_rate_ceiling: 0.24
  gate_obsolete_failure_rate_floor: 0.71
  gate_promote_min_ttl_score: 0.55
  gate_obsolete_max_ttl_score: 0.40
  stream_consumer_enabled: true
  stream_name: "memory.events.system"
  stream_consumer_group: "system-group"
  stream_consumer_name_prefix: "system-agent"
  stream_consumer_batch_size: 12
  stream_consumer_block_ms: 1500
"#,
    );
    write_file(
        user.clone(),
        r#"
mcp:
  agent_pool_size: 8
  agent_connect_retries: 5
  agent_tool_timeout_secs: 240
  agent_list_tools_cache_ttl_ms: 2500
  agent_discover_cache_enabled: false
  agent_discover_cache_key_prefix: "user-discover"
  agent_discover_cache_ttl_secs: 90
telegram:
  allowed_users: "2002"
  session_admin_persist: false
  admin_users: "2002"
  control_command_allow_from: ""
  admin_command_rules: "/reset,/clear=>2002"
  slash_command_allow_from: ""
  slash_session_status_allow_from: "2002"
  slash_session_budget_allow_from: "2002"
  slash_session_memory_allow_from: "2002"
  slash_session_feedback_allow_from: "ops"
  slash_job_allow_from: "ops"
  slash_jobs_allow_from: "ops"
  slash_bg_allow_from: "ops"
  mode: "polling"
  inbound_queue_capacity: 120
discord:
  allowed_users: "ux2"
  admin_users: "ux2"
  control_command_allow_from: ""
  admin_command_rules: "/resume=>ux2"
  slash_command_allow_from: ""
  slash_session_status_allow_from: "ux2"
  slash_session_budget_allow_from: "ux2"
  slash_session_memory_allow_from: "ux2"
  slash_session_feedback_allow_from: "ops"
  slash_job_allow_from: "ops"
  slash_jobs_allow_from: "ops"
  slash_bg_allow_from: "ops"
  ingress_bind: "127.0.0.1:9092"
  inbound_queue_capacity: 1024
session:
  window_max_turns: 2048
  consolidation_async: false
  context_budget_tokens: 7000
  context_budget_strategy: "summary_first"
  summary_max_segments: 10
  redis_prefix: "user-prefix"
embedding:
  dimension: 768
memory:
  persistence_strict_startup: false
  recall_credit_enabled: true
  recall_credit_max_candidates: 5
  decay_enabled: true
  decay_every_turns: 20
  decay_factor: 0.99
  gate_promote_threshold: 0.88
  gate_obsolete_min_usage: 5
  gate_obsolete_failure_rate_floor: 0.92
  stream_consumer_enabled: false
  stream_name: "memory.events.user"
  stream_consumer_group: "user-group"
  stream_consumer_name_prefix: "user-agent"
  stream_consumer_batch_size: 24
  stream_consumer_block_ms: 900
"#,
    );

    let merged = load_runtime_settings_from_paths(&system, &user);
    assert_eq!(merged.mcp.agent_pool_size, Some(8));
    assert_eq!(merged.mcp.agent_handshake_timeout_secs, Some(30));
    assert_eq!(merged.mcp.agent_connect_retries, Some(5));
    assert_eq!(merged.mcp.agent_connect_retry_backoff_ms, Some(500));
    assert_eq!(merged.mcp.agent_tool_timeout_secs, Some(240));
    assert_eq!(merged.mcp.agent_list_tools_cache_ttl_ms, Some(2500));
    assert_eq!(merged.mcp.agent_discover_cache_enabled, Some(false));
    assert_eq!(
        merged.mcp.agent_discover_cache_key_prefix.as_deref(),
        Some("user-discover")
    );
    assert_eq!(merged.mcp.agent_discover_cache_ttl_secs, Some(90));
    assert_eq!(merged.telegram.allowed_users.as_deref(), Some("2002"));
    assert_eq!(merged.telegram.allowed_groups.as_deref(), Some("-2001"));
    assert_eq!(merged.telegram.session_admin_persist, Some(false));
    assert_eq!(merged.telegram.admin_users.as_deref(), Some("2002"));
    assert_eq!(
        merged.telegram.control_command_allow_from.as_deref(),
        Some("")
    );
    assert_eq!(
        merged.telegram.admin_command_rules.as_deref(),
        Some("/reset,/clear=>2002")
    );
    assert_eq!(
        merged.telegram.slash_command_allow_from.as_deref(),
        Some("")
    );
    assert_eq!(
        merged.telegram.slash_session_status_allow_from.as_deref(),
        Some("2002")
    );
    assert_eq!(
        merged.telegram.slash_session_budget_allow_from.as_deref(),
        Some("2002")
    );
    assert_eq!(
        merged.telegram.slash_session_memory_allow_from.as_deref(),
        Some("2002")
    );
    assert_eq!(
        merged.telegram.slash_session_feedback_allow_from.as_deref(),
        Some("ops")
    );
    assert_eq!(merged.telegram.slash_job_allow_from.as_deref(), Some("ops"));
    assert_eq!(
        merged.telegram.slash_jobs_allow_from.as_deref(),
        Some("ops")
    );
    assert_eq!(merged.telegram.slash_bg_allow_from.as_deref(), Some("ops"));
    assert_eq!(merged.telegram.mode.as_deref(), Some("polling"));
    assert_eq!(
        merged.telegram.webhook_dedup_backend.as_deref(),
        Some("valkey")
    );
    assert_eq!(merged.telegram.inbound_queue_capacity, Some(120));
    assert_eq!(merged.telegram.foreground_queue_capacity, Some(256));
    assert_eq!(merged.telegram.foreground_max_in_flight_messages, Some(16));
    assert_eq!(merged.telegram.foreground_turn_timeout_secs, Some(300));
    assert_eq!(merged.telegram.session_partition.as_deref(), Some("chat"));
    assert_eq!(merged.telegram.max_tool_rounds, Some(30));
    assert_eq!(merged.discord.allowed_users.as_deref(), Some("ux2"));
    assert_eq!(merged.discord.allowed_guilds.as_deref(), Some("3001"));
    assert_eq!(merged.discord.admin_users.as_deref(), Some("ux2"));
    assert_eq!(
        merged.discord.control_command_allow_from.as_deref(),
        Some("")
    );
    assert_eq!(
        merged.discord.admin_command_rules.as_deref(),
        Some("/resume=>ux2")
    );
    assert_eq!(merged.discord.slash_command_allow_from.as_deref(), Some(""));
    assert_eq!(
        merged.discord.slash_session_status_allow_from.as_deref(),
        Some("ux2")
    );
    assert_eq!(
        merged.discord.slash_session_budget_allow_from.as_deref(),
        Some("ux2")
    );
    assert_eq!(
        merged.discord.slash_session_memory_allow_from.as_deref(),
        Some("ux2")
    );
    assert_eq!(
        merged.discord.slash_session_feedback_allow_from.as_deref(),
        Some("ops")
    );
    assert_eq!(merged.discord.slash_job_allow_from.as_deref(), Some("ops"));
    assert_eq!(merged.discord.slash_jobs_allow_from.as_deref(), Some("ops"));
    assert_eq!(merged.discord.slash_bg_allow_from.as_deref(), Some("ops"));
    assert_eq!(
        merged.discord.ingress_bind.as_deref(),
        Some("127.0.0.1:9092")
    );
    assert_eq!(
        merged.discord.ingress_path.as_deref(),
        Some("/discord/ingress")
    );
    assert_eq!(
        merged.discord.ingress_secret_token.as_deref(),
        Some("system-secret")
    );
    assert_eq!(
        merged.discord.session_partition.as_deref(),
        Some("guild_channel_user")
    );
    assert_eq!(merged.discord.inbound_queue_capacity, Some(1024));
    assert_eq!(merged.discord.turn_timeout_secs, Some(120));
    assert_eq!(merged.session.window_max_turns, Some(2048));
    assert_eq!(merged.session.consolidation_async, Some(false));
    assert_eq!(merged.session.context_budget_tokens, Some(7000));
    assert_eq!(merged.session.context_budget_reserve_tokens, Some(256));
    assert_eq!(
        merged.session.context_budget_strategy.as_deref(),
        Some("summary_first")
    );
    assert_eq!(merged.session.summary_max_segments, Some(10));
    assert_eq!(merged.session.summary_max_chars, Some(256));
    assert_eq!(merged.session.redis_prefix.as_deref(), Some("user-prefix"));
    assert_eq!(merged.session.ttl_secs, Some(3600));
    assert_eq!(
        merged.embedding.model.as_deref(),
        Some("ollama/qwen3-embedding:0.6b")
    );
    assert_eq!(
        merged.embedding.litellm_model.as_deref(),
        Some("ollama/qwen3-embedding:0.6b")
    );
    assert_eq!(merged.embedding.dimension, Some(768));
    assert_eq!(
        merged.embedding.client_url.as_deref(),
        Some("http://127.0.0.1:3002")
    );
    assert_eq!(merged.memory.persistence_backend.as_deref(), Some("local"));
    assert_eq!(merged.memory.persistence_strict_startup, Some(false));
    assert_eq!(merged.memory.recall_credit_enabled, Some(true));
    assert_eq!(merged.memory.recall_credit_max_candidates, Some(5));
    assert_eq!(merged.memory.decay_enabled, Some(true));
    assert_eq!(merged.memory.decay_every_turns, Some(20));
    assert_eq!(merged.memory.decay_factor, Some(0.99));
    assert_eq!(merged.memory.gate_promote_threshold, Some(0.88));
    assert_eq!(merged.memory.gate_obsolete_threshold, Some(0.33));
    assert_eq!(merged.memory.gate_promote_min_usage, Some(4));
    assert_eq!(merged.memory.gate_obsolete_min_usage, Some(5));
    assert_eq!(merged.memory.gate_promote_failure_rate_ceiling, Some(0.24));
    assert_eq!(merged.memory.gate_obsolete_failure_rate_floor, Some(0.92));
    assert_eq!(merged.memory.gate_promote_min_ttl_score, Some(0.55));
    assert_eq!(merged.memory.gate_obsolete_max_ttl_score, Some(0.40));
    assert_eq!(merged.memory.stream_consumer_enabled, Some(false));
    assert_eq!(
        merged.memory.stream_name.as_deref(),
        Some("memory.events.user")
    );
    assert_eq!(
        merged.memory.stream_consumer_group.as_deref(),
        Some("user-group")
    );
    assert_eq!(
        merged.memory.stream_consumer_name_prefix.as_deref(),
        Some("user-agent")
    );
    assert_eq!(merged.memory.stream_consumer_batch_size, Some(24));
    assert_eq!(merged.memory.stream_consumer_block_ms, Some(900));
}

#[test]
fn merge_telegram_group_policy_overrides_deeply() {
    let tmp = TempDir::new().expect("tempdir");
    let system = tmp.path().join("packages/conf/settings.yaml");
    let user = tmp.path().join(".config/omni-dev-fusion/settings.yaml");

    write_file(
        system.clone(),
        r#"
telegram:
  group_policy: "allowlist"
  group_allow_from: "ops"
  session_admin_persist: true
  require_mention: true
  groups:
    "*":
      admin_users: "9090"
      require_mention: true
      topics:
        "42":
          enabled: false
    "-100":
      group_policy: "disabled"
      allow_from: "root"
      admin_users: "3001"
      topics:
        "10":
          allow_from: "ops1"
          admin_users: "7001"
"#,
    );
    write_file(
        user.clone(),
        r#"
telegram:
  group_policy: "open"
  session_admin_persist: false
  require_mention: false
  groups:
    "-100":
      allow_from: "admin2"
      admin_users: "3002"
      topics:
        "10":
          require_mention: true
          admin_users: "7002"
        "11":
          enabled: true
          admin_users: "8001"
    "-200":
      enabled: true
      admin_users: "4001"
"#,
    );

    let merged = load_runtime_settings_from_paths(&system, &user);
    assert_eq!(merged.telegram.group_policy.as_deref(), Some("open"));
    assert_eq!(merged.telegram.group_allow_from.as_deref(), Some("ops"));
    assert_eq!(merged.telegram.session_admin_persist, Some(false));
    assert_eq!(merged.telegram.require_mention, Some(false));

    let groups = merged.telegram.groups.expect("merged groups");
    let wildcard = groups.get("*").expect("wildcard group");
    assert_eq!(wildcard.admin_users.as_deref(), Some("9090"));
    assert_eq!(wildcard.require_mention, Some(true));

    let group_100 = groups.get("-100").expect("group -100");
    assert_eq!(group_100.group_policy.as_deref(), Some("disabled"));
    assert_eq!(group_100.allow_from.as_deref(), Some("admin2"));
    assert_eq!(group_100.admin_users.as_deref(), Some("3002"));
    let topics_100 = group_100.topics.as_ref().expect("group -100 topics");
    let topic_10 = topics_100.get("10").expect("topic 10");
    assert_eq!(topic_10.allow_from.as_deref(), Some("ops1"));
    assert_eq!(topic_10.admin_users.as_deref(), Some("7002"));
    assert_eq!(topic_10.require_mention, Some(true));
    let topic_11 = topics_100.get("11").expect("topic 11");
    assert_eq!(topic_11.admin_users.as_deref(), Some("8001"));
    assert_eq!(topic_11.enabled, Some(true));

    let group_200 = groups.get("-200").expect("group -200");
    assert_eq!(group_200.admin_users.as_deref(), Some("4001"));
    assert_eq!(group_200.enabled, Some(true));
}

#[test]
fn missing_files_fallback_to_defaults() {
    let tmp = TempDir::new().expect("tempdir");
    let merged = load_runtime_settings_from_paths(
        &tmp.path().join("missing-system.yaml"),
        &tmp.path().join("missing-user.yaml"),
    );
    assert!(merged.telegram.allowed_users.is_none());
    assert!(merged.telegram.group_policy.is_none());
    assert!(merged.telegram.session_admin_persist.is_none());
    assert!(merged.telegram.group_allow_from.is_none());
    assert!(merged.telegram.require_mention.is_none());
    assert!(merged.telegram.groups.is_none());
    assert!(merged.telegram.admin_users.is_none());
    assert!(merged.telegram.control_command_allow_from.is_none());
    assert!(merged.telegram.admin_command_rules.is_none());
    assert!(merged.telegram.slash_command_allow_from.is_none());
    assert!(merged.telegram.slash_session_status_allow_from.is_none());
    assert!(merged.telegram.slash_session_budget_allow_from.is_none());
    assert!(merged.telegram.slash_session_memory_allow_from.is_none());
    assert!(merged.telegram.slash_session_feedback_allow_from.is_none());
    assert!(merged.telegram.slash_job_allow_from.is_none());
    assert!(merged.telegram.slash_jobs_allow_from.is_none());
    assert!(merged.telegram.slash_bg_allow_from.is_none());
    assert!(merged.telegram.max_tool_rounds.is_none());
    assert!(merged.discord.allowed_users.is_none());
    assert!(merged.discord.admin_users.is_none());
    assert!(merged.discord.control_command_allow_from.is_none());
    assert!(merged.discord.admin_command_rules.is_none());
    assert!(merged.discord.slash_command_allow_from.is_none());
    assert!(merged.discord.slash_session_status_allow_from.is_none());
    assert!(merged.discord.slash_session_budget_allow_from.is_none());
    assert!(merged.discord.slash_session_memory_allow_from.is_none());
    assert!(merged.discord.slash_session_feedback_allow_from.is_none());
    assert!(merged.discord.slash_job_allow_from.is_none());
    assert!(merged.discord.slash_jobs_allow_from.is_none());
    assert!(merged.discord.slash_bg_allow_from.is_none());
    assert!(merged.discord.session_partition.is_none());
    assert!(merged.mcp.agent_pool_size.is_none());
    assert!(merged.mcp.agent_handshake_timeout_secs.is_none());
    assert!(merged.mcp.agent_connect_retries.is_none());
    assert!(merged.mcp.agent_connect_retry_backoff_ms.is_none());
    assert!(merged.mcp.agent_tool_timeout_secs.is_none());
    assert!(merged.mcp.agent_list_tools_cache_ttl_ms.is_none());
    assert!(merged.mcp.agent_discover_cache_enabled.is_none());
    assert!(merged.mcp.agent_discover_cache_key_prefix.is_none());
    assert!(merged.mcp.agent_discover_cache_ttl_secs.is_none());
    assert!(merged.session.window_max_turns.is_none());
    assert!(merged.session.context_budget_strategy.is_none());
    assert!(merged.session.summary_max_segments.is_none());
    assert!(merged.embedding.model.is_none());
    assert!(merged.embedding.dimension.is_none());
    assert!(merged.memory.gate_promote_threshold.is_none());
    assert!(merged.memory.gate_obsolete_threshold.is_none());
    assert!(merged.memory.gate_promote_min_usage.is_none());
    assert!(merged.memory.gate_obsolete_min_usage.is_none());
    assert!(merged.memory.gate_promote_failure_rate_ceiling.is_none());
    assert!(merged.memory.gate_obsolete_failure_rate_floor.is_none());
    assert!(merged.memory.gate_promote_min_ttl_score.is_none());
    assert!(merged.memory.gate_obsolete_max_ttl_score.is_none());
}

#[test]
fn invalid_yaml_is_ignored() {
    let tmp = TempDir::new().expect("tempdir");
    let system = tmp.path().join("packages/conf/settings.yaml");
    let user = tmp.path().join(".config/omni-dev-fusion/settings.yaml");

    write_file(system, "telegram: [");
    write_file(
        user.clone(),
        r#"
telegram:
  allowed_users: "ok-user"
"#,
    );

    let merged =
        load_runtime_settings_from_paths(&tmp.path().join("packages/conf/settings.yaml"), &user);
    assert_eq!(merged.telegram.allowed_users.as_deref(), Some("ok-user"));
}
