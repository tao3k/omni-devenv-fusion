use std::path::PathBuf;

use anyhow::{Result, anyhow};
use omni_agent::{
    Agent, AgentConfig, ContextBudgetStrategy, LITELLM_DEFAULT_URL, MemoryConfig, RuntimeSettings,
    load_mcp_config,
};

use crate::resolve::{
    parse_bool_from_env, parse_positive_f32_from_env, parse_positive_u32_from_env,
    parse_positive_u64_from_env, parse_positive_usize_from_env, parse_unit_f32_from_env,
};

fn non_empty_env(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn parse_context_budget_strategy(raw: &str, source: &str) -> Result<ContextBudgetStrategy> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "recent_first" => Ok(ContextBudgetStrategy::RecentFirst),
        "summary_first" => Ok(ContextBudgetStrategy::SummaryFirst),
        _ => Err(anyhow!(
            "invalid {source}: '{raw}' (expected one of: recent_first, summary_first)"
        )),
    }
}

fn resolve_context_budget_strategy(
    runtime_settings: &RuntimeSettings,
) -> Result<ContextBudgetStrategy> {
    if let Some(raw) = non_empty_env("OMNI_AGENT_CONTEXT_BUDGET_STRATEGY") {
        return parse_context_budget_strategy(&raw, "OMNI_AGENT_CONTEXT_BUDGET_STRATEGY");
    }

    if let Some(raw) = runtime_settings
        .session
        .context_budget_strategy
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        return parse_context_budget_strategy(raw, "session.context_budget_strategy");
    }

    Ok(ContextBudgetStrategy::RecentFirst)
}

fn normalize_unit_f32(value: f32, source: &str) -> Option<f32> {
    if (0.0..=1.0).contains(&value) {
        return Some(value);
    }
    tracing::warn!(
        source,
        value,
        "invalid memory gate unit value (expected 0.0..=1.0); keeping previous/default"
    );
    None
}

pub(crate) async fn build_agent(
    mcp_config_path: &PathBuf,
    runtime_settings: &RuntimeSettings,
) -> Result<Agent> {
    let mcp_servers = load_mcp_config(mcp_config_path)?
        .into_iter()
        .filter(|e| e.url.is_some())
        .collect::<Vec<_>>();
    let inference_url = std::env::var("LITELLM_PROXY_URL")
        .or_else(|_| std::env::var("OMNI_AGENT_INFERENCE_URL"))
        .unwrap_or_else(|_| {
            mcp_servers
                .first()
                .and_then(|e| e.url.as_ref())
                .map(|u| {
                    let base = u
                        .trim_end_matches('/')
                        .strip_suffix("/sse")
                        .unwrap_or_else(|| u.trim_end_matches('/'));
                    format!("{base}/v1/chat/completions")
                })
                .unwrap_or_else(|| LITELLM_DEFAULT_URL.to_string())
        });
    let inference_url = {
        let u = inference_url.trim_end_matches('/');
        if u.ends_with("/v1/chat/completions") {
            u.to_string()
        } else {
            format!("{}/v1/chat/completions", u.trim_end_matches('/'))
        }
    };
    // When unset, use empty so MCP inference uses project default (e.g. MiniMax-M2.5 from settings).
    let model = std::env::var("OMNI_AGENT_MODEL").unwrap_or_default();
    let max_tool_rounds = parse_positive_u32_from_env("OMNI_AGENT_MAX_TOOL_ROUNDS")
        .or(runtime_settings.telegram.max_tool_rounds)
        .unwrap_or(30);
    let mcp_pool_size = parse_positive_usize_from_env("OMNI_AGENT_MCP_POOL_SIZE")
        .or(runtime_settings.mcp.agent_pool_size.filter(|v| *v > 0))
        .unwrap_or(4);
    let mcp_handshake_timeout_secs =
        parse_positive_u64_from_env("OMNI_AGENT_MCP_HANDSHAKE_TIMEOUT_SECS")
            .or(runtime_settings
                .mcp
                .agent_handshake_timeout_secs
                .filter(|v| *v > 0))
            .unwrap_or(30);
    let mcp_connect_retries = parse_positive_u32_from_env("OMNI_AGENT_MCP_CONNECT_RETRIES")
        .or(runtime_settings
            .mcp
            .agent_connect_retries
            .filter(|v| *v > 0))
        .unwrap_or(3);
    let mcp_connect_retry_backoff_ms =
        parse_positive_u64_from_env("OMNI_AGENT_MCP_CONNECT_RETRY_BACKOFF_MS")
            .or(runtime_settings
                .mcp
                .agent_connect_retry_backoff_ms
                .filter(|v| *v > 0))
            .unwrap_or(1_000);
    let mcp_tool_timeout_secs = parse_positive_u64_from_env("OMNI_AGENT_MCP_TOOL_TIMEOUT_SECS")
        .or(runtime_settings
            .mcp
            .agent_tool_timeout_secs
            .filter(|v| *v > 0))
        .unwrap_or(180);
    let mcp_list_tools_cache_ttl_ms =
        parse_positive_u64_from_env("OMNI_AGENT_MCP_LIST_TOOLS_CACHE_TTL_MS")
            .or(runtime_settings
                .mcp
                .agent_list_tools_cache_ttl_ms
                .filter(|v| *v > 0))
            .unwrap_or(1_000);
    let window_max_turns = parse_positive_usize_from_env("OMNI_AGENT_WINDOW_MAX_TURNS")
        .or(runtime_settings.session.window_max_turns.filter(|v| *v > 0))
        .or(Some(256));
    let consolidation_take_turns =
        parse_positive_usize_from_env("OMNI_AGENT_CONSOLIDATION_TAKE_TURNS")
            .or(runtime_settings
                .session
                .consolidation_take_turns
                .filter(|v| *v > 0))
            .unwrap_or(32);
    let consolidation_threshold_turns =
        parse_positive_usize_from_env("OMNI_AGENT_CONSOLIDATION_THRESHOLD_TURNS")
            .or(runtime_settings
                .session
                .consolidation_threshold_turns
                .filter(|v| *v > 0))
            .or_else(|| window_max_turns.map(|max_turns| (max_turns.saturating_mul(3)) / 4));
    let consolidation_async = parse_bool_from_env("OMNI_AGENT_CONSOLIDATION_ASYNC")
        .or(runtime_settings.session.consolidation_async)
        .unwrap_or(true);
    let context_budget_tokens = parse_positive_usize_from_env("OMNI_AGENT_CONTEXT_BUDGET_TOKENS")
        .or(runtime_settings
            .session
            .context_budget_tokens
            .filter(|v| *v > 0))
        .or(Some(6000));
    let context_budget_reserve_tokens =
        parse_positive_usize_from_env("OMNI_AGENT_CONTEXT_BUDGET_RESERVE_TOKENS")
            .or(runtime_settings
                .session
                .context_budget_reserve_tokens
                .filter(|v| *v > 0))
            .unwrap_or(512);
    let context_budget_strategy = resolve_context_budget_strategy(runtime_settings)?;
    let summary_max_segments = parse_positive_usize_from_env("OMNI_AGENT_SUMMARY_MAX_SEGMENTS")
        .or(runtime_settings
            .session
            .summary_max_segments
            .filter(|v| *v > 0))
        .unwrap_or(8);
    let summary_max_chars = parse_positive_usize_from_env("OMNI_AGENT_SUMMARY_MAX_CHARS")
        .or(runtime_settings
            .session
            .summary_max_chars
            .filter(|v| *v > 0))
        .unwrap_or(480);
    let mut memory = MemoryConfig::default();
    if let Some(path) = runtime_settings
        .memory
        .path
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        memory.path = path.to_string();
    }
    if let Some(model) = runtime_settings
        .embedding
        .litellm_model
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .or_else(|| {
            runtime_settings
                .embedding
                .model
                .as_deref()
                .map(str::trim)
                .filter(|value| !value.is_empty())
        })
    {
        memory.embedding_model = Some(model.to_string());
    }
    if let Some(embedding_dim) = runtime_settings
        .embedding
        .dimension
        .filter(|value| *value > 0)
    {
        memory.embedding_dim = embedding_dim;
    }
    if let Some(base_url) = runtime_settings
        .embedding
        .client_url
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        memory.embedding_base_url = Some(base_url.to_string());
    }
    if let Some(backend) = runtime_settings
        .memory
        .persistence_backend
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        memory.persistence_backend = backend.to_string();
    }
    if let Some(url) = runtime_settings
        .session
        .valkey_url
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        memory.persistence_valkey_url = Some(url.to_string());
    }
    if let Some(prefix) = runtime_settings
        .memory
        .persistence_key_prefix
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        memory.persistence_key_prefix = prefix.to_string();
    }
    if let Some(strict_startup) = runtime_settings.memory.persistence_strict_startup {
        memory.persistence_strict_startup = Some(strict_startup);
    }
    if let Some(enabled) = runtime_settings.memory.recall_credit_enabled {
        memory.recall_credit_enabled = enabled;
    }
    if let Some(max_candidates) = runtime_settings
        .memory
        .recall_credit_max_candidates
        .filter(|value| *value > 0)
    {
        memory.recall_credit_max_candidates = max_candidates;
    }
    if let Some(enabled) = runtime_settings.memory.decay_enabled {
        memory.decay_enabled = enabled;
    }
    if let Some(every_turns) = runtime_settings
        .memory
        .decay_every_turns
        .filter(|value| *value > 0)
    {
        memory.decay_every_turns = every_turns;
    }
    if let Some(factor) = runtime_settings
        .memory
        .decay_factor
        .filter(|value| *value > 0.0)
    {
        memory.decay_factor = factor;
    }
    if let Some(threshold) = runtime_settings
        .memory
        .gate_promote_threshold
        .and_then(|value| normalize_unit_f32(value, "memory.gate_promote_threshold"))
    {
        memory.gate_promote_threshold = threshold;
    }
    if let Some(threshold) = runtime_settings
        .memory
        .gate_obsolete_threshold
        .and_then(|value| normalize_unit_f32(value, "memory.gate_obsolete_threshold"))
    {
        memory.gate_obsolete_threshold = threshold;
    }
    if let Some(min_usage) = runtime_settings
        .memory
        .gate_promote_min_usage
        .filter(|value| *value > 0)
    {
        memory.gate_promote_min_usage = min_usage;
    }
    if let Some(min_usage) = runtime_settings
        .memory
        .gate_obsolete_min_usage
        .filter(|value| *value > 0)
    {
        memory.gate_obsolete_min_usage = min_usage;
    }
    if let Some(rate) = runtime_settings
        .memory
        .gate_promote_failure_rate_ceiling
        .and_then(|value| normalize_unit_f32(value, "memory.gate_promote_failure_rate_ceiling"))
    {
        memory.gate_promote_failure_rate_ceiling = rate;
    }
    if let Some(rate) = runtime_settings
        .memory
        .gate_obsolete_failure_rate_floor
        .and_then(|value| normalize_unit_f32(value, "memory.gate_obsolete_failure_rate_floor"))
    {
        memory.gate_obsolete_failure_rate_floor = rate;
    }
    if let Some(score) = runtime_settings
        .memory
        .gate_promote_min_ttl_score
        .and_then(|value| normalize_unit_f32(value, "memory.gate_promote_min_ttl_score"))
    {
        memory.gate_promote_min_ttl_score = score;
    }
    if let Some(score) = runtime_settings
        .memory
        .gate_obsolete_max_ttl_score
        .and_then(|value| normalize_unit_f32(value, "memory.gate_obsolete_max_ttl_score"))
    {
        memory.gate_obsolete_max_ttl_score = score;
    }
    if let Some(enabled) = runtime_settings.memory.stream_consumer_enabled {
        memory.stream_consumer_enabled = enabled;
    }
    if let Some(stream_name) = runtime_settings
        .memory
        .stream_name
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        memory.stream_name = stream_name.to_string();
    }
    if let Some(consumer_group) = runtime_settings
        .memory
        .stream_consumer_group
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        memory.stream_consumer_group = consumer_group.to_string();
    }
    if let Some(consumer_name_prefix) = runtime_settings
        .memory
        .stream_consumer_name_prefix
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        memory.stream_consumer_name_prefix = consumer_name_prefix.to_string();
    }
    if let Some(batch_size) = runtime_settings
        .memory
        .stream_consumer_batch_size
        .filter(|value| *value > 0)
    {
        memory.stream_consumer_batch_size = batch_size;
    }
    if let Some(block_ms) = runtime_settings
        .memory
        .stream_consumer_block_ms
        .filter(|value| *value > 0)
    {
        memory.stream_consumer_block_ms = block_ms;
    }

    if let Some(path) = non_empty_env("OMNI_AGENT_MEMORY_PATH") {
        memory.path = path;
    }
    if let Some(model) = non_empty_env("OMNI_AGENT_MEMORY_EMBEDDING_MODEL")
        .or_else(|| non_empty_env("OMNI_AGENT_EMBED_MODEL"))
    {
        memory.embedding_model = Some(model);
    }
    if let Some(base_url) = non_empty_env("OMNI_AGENT_EMBED_BASE_URL") {
        memory.embedding_base_url = Some(base_url);
    }
    if let Some(embedding_dim) = parse_positive_usize_from_env("OMNI_AGENT_MEMORY_EMBEDDING_DIM") {
        memory.embedding_dim = embedding_dim;
    }
    if let Some(backend) = non_empty_env("OMNI_AGENT_MEMORY_PERSISTENCE_BACKEND") {
        memory.persistence_backend = backend;
    }
    if let Some(url) = non_empty_env("VALKEY_URL") {
        memory.persistence_valkey_url = Some(url);
    }
    if let Some(prefix) = non_empty_env("OMNI_AGENT_MEMORY_VALKEY_KEY_PREFIX") {
        memory.persistence_key_prefix = prefix;
    }
    if let Some(strict_startup) =
        parse_bool_from_env("OMNI_AGENT_MEMORY_PERSISTENCE_STRICT_STARTUP")
    {
        memory.persistence_strict_startup = Some(strict_startup);
    }
    if let Some(enabled) = parse_bool_from_env("OMNI_AGENT_MEMORY_RECALL_CREDIT_ENABLED") {
        memory.recall_credit_enabled = enabled;
    }
    if let Some(max_candidates) =
        parse_positive_usize_from_env("OMNI_AGENT_MEMORY_RECALL_CREDIT_MAX_CANDIDATES")
    {
        memory.recall_credit_max_candidates = max_candidates;
    }
    if let Some(enabled) = parse_bool_from_env("OMNI_AGENT_MEMORY_DECAY_ENABLED") {
        memory.decay_enabled = enabled;
    }
    if let Some(every_turns) = parse_positive_usize_from_env("OMNI_AGENT_MEMORY_DECAY_EVERY_TURNS")
    {
        memory.decay_every_turns = every_turns;
    }
    if let Some(factor) = parse_positive_f32_from_env("OMNI_AGENT_MEMORY_DECAY_FACTOR") {
        memory.decay_factor = factor;
    }
    if let Some(threshold) = parse_unit_f32_from_env("OMNI_AGENT_MEMORY_GATE_PROMOTE_THRESHOLD") {
        memory.gate_promote_threshold = threshold;
    }
    if let Some(threshold) = parse_unit_f32_from_env("OMNI_AGENT_MEMORY_GATE_OBSOLETE_THRESHOLD") {
        memory.gate_obsolete_threshold = threshold;
    }
    if let Some(min_usage) = parse_positive_u32_from_env("OMNI_AGENT_MEMORY_GATE_PROMOTE_MIN_USAGE")
    {
        memory.gate_promote_min_usage = min_usage;
    }
    if let Some(min_usage) =
        parse_positive_u32_from_env("OMNI_AGENT_MEMORY_GATE_OBSOLETE_MIN_USAGE")
    {
        memory.gate_obsolete_min_usage = min_usage;
    }
    if let Some(rate) =
        parse_unit_f32_from_env("OMNI_AGENT_MEMORY_GATE_PROMOTE_FAILURE_RATE_CEILING")
    {
        memory.gate_promote_failure_rate_ceiling = rate;
    }
    if let Some(rate) =
        parse_unit_f32_from_env("OMNI_AGENT_MEMORY_GATE_OBSOLETE_FAILURE_RATE_FLOOR")
    {
        memory.gate_obsolete_failure_rate_floor = rate;
    }
    if let Some(score) = parse_unit_f32_from_env("OMNI_AGENT_MEMORY_GATE_PROMOTE_MIN_TTL_SCORE") {
        memory.gate_promote_min_ttl_score = score;
    }
    if let Some(score) = parse_unit_f32_from_env("OMNI_AGENT_MEMORY_GATE_OBSOLETE_MAX_TTL_SCORE") {
        memory.gate_obsolete_max_ttl_score = score;
    }
    if let Some(enabled) = parse_bool_from_env("OMNI_AGENT_MEMORY_STREAM_CONSUMER_ENABLED") {
        memory.stream_consumer_enabled = enabled;
    }
    if let Some(stream_name) = non_empty_env("OMNI_AGENT_MEMORY_STREAM_NAME") {
        memory.stream_name = stream_name;
    }
    if let Some(group) = non_empty_env("OMNI_AGENT_MEMORY_STREAM_CONSUMER_GROUP") {
        memory.stream_consumer_group = group;
    }
    if let Some(prefix) = non_empty_env("OMNI_AGENT_MEMORY_STREAM_CONSUMER_NAME_PREFIX") {
        memory.stream_consumer_name_prefix = prefix;
    }
    if let Some(batch_size) =
        parse_positive_usize_from_env("OMNI_AGENT_MEMORY_STREAM_CONSUMER_BATCH_SIZE")
    {
        memory.stream_consumer_batch_size = batch_size;
    }
    if let Some(block_ms) =
        parse_positive_u64_from_env("OMNI_AGENT_MEMORY_STREAM_CONSUMER_BLOCK_MS")
    {
        memory.stream_consumer_block_ms = block_ms;
    }

    tracing::info!(
        mcp_pool_size,
        mcp_handshake_timeout_secs,
        mcp_connect_retries,
        mcp_connect_retry_backoff_ms,
        mcp_tool_timeout_secs,
        mcp_list_tools_cache_ttl_ms,
        window_max_turns = ?window_max_turns,
        consolidation_threshold_turns = ?consolidation_threshold_turns,
        consolidation_take_turns,
        consolidation_async,
        context_budget_tokens = ?context_budget_tokens,
        context_budget_reserve_tokens,
        context_budget_strategy = context_budget_strategy.as_str(),
        summary_max_segments,
        summary_max_chars,
        memory_embedding_model = memory.embedding_model.as_deref().unwrap_or(""),
        memory_embedding_dim = memory.embedding_dim,
        memory_embedding_base_url = memory.embedding_base_url.as_deref().unwrap_or(""),
        memory_persistence_backend = %memory.persistence_backend,
        memory_persistence_strict_startup = ?memory.persistence_strict_startup,
        memory_recall_credit_enabled = memory.recall_credit_enabled,
        memory_recall_credit_max_candidates = memory.recall_credit_max_candidates,
        memory_decay_enabled = memory.decay_enabled,
        memory_decay_every_turns = memory.decay_every_turns,
        memory_decay_factor = memory.decay_factor,
        memory_gate_promote_threshold = memory.gate_promote_threshold,
        memory_gate_obsolete_threshold = memory.gate_obsolete_threshold,
        memory_gate_promote_min_usage = memory.gate_promote_min_usage,
        memory_gate_obsolete_min_usage = memory.gate_obsolete_min_usage,
        memory_gate_promote_failure_rate_ceiling = memory.gate_promote_failure_rate_ceiling,
        memory_gate_obsolete_failure_rate_floor = memory.gate_obsolete_failure_rate_floor,
        memory_gate_promote_min_ttl_score = memory.gate_promote_min_ttl_score,
        memory_gate_obsolete_max_ttl_score = memory.gate_obsolete_max_ttl_score,
        memory_stream_consumer_enabled = memory.stream_consumer_enabled,
        memory_stream_name = %memory.stream_name,
        memory_stream_consumer_group = %memory.stream_consumer_group,
        memory_stream_consumer_name_prefix = %memory.stream_consumer_name_prefix,
        memory_stream_consumer_batch_size = memory.stream_consumer_batch_size,
        memory_stream_consumer_block_ms = memory.stream_consumer_block_ms,
        memory_path = %memory.path,
        "telegram runtime session window settings"
    );

    let config = AgentConfig {
        inference_url,
        model,
        api_key: None,
        mcp_servers,
        mcp_pool_size,
        mcp_handshake_timeout_secs,
        mcp_connect_retries,
        mcp_connect_retry_backoff_ms,
        mcp_tool_timeout_secs,
        mcp_list_tools_cache_ttl_ms,
        max_tool_rounds,
        memory: Some(memory),
        window_max_turns,
        consolidation_threshold_turns,
        consolidation_take_turns,
        consolidation_async,
        context_budget_tokens,
        context_budget_reserve_tokens,
        context_budget_strategy,
        summary_max_segments,
        summary_max_chars,
    };
    Agent::from_config(config).await
}
