//! One-turn agent loop: user message -> LLM (+ optional tools) -> tool_calls -> MCP tools/call -> repeat.

mod consolidation;
mod context_budget;
mod context_budget_state;
mod embedding_dimension;
mod graph_bridge;
mod injection;
pub(crate) mod logging;
mod mcp;
mod mcp_pool_state;
mod memory;
mod memory_recall;
mod memory_recall_feedback;
mod memory_recall_feedback_state;
mod memory_recall_metrics;
mod memory_recall_state;
mod memory_state;
mod memory_stream_consumer;
mod omega;
mod persistence;
mod reflection;
mod reflection_runtime_state;
mod session_context;
mod system_prompt_injection_state;

use anyhow::{Context, Result};
use omni_tokenizer::count_tokens;
use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::AtomicU64;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;

use omni_memory::{EpisodeStore, StoreConfig};
use xiuxian_qianhuan::{InjectionPolicy, InjectionSnapshot};

use crate::config::AgentConfig;
use crate::contracts::{OmegaDecision, OmegaFallbackPolicy, OmegaRoute};
use crate::embedding::EmbeddingClient;
use crate::llm::LlmClient;
use crate::mcp_pool::{McpPoolConnectConfig, connect_pool};
use crate::observability::SessionEvent;
use crate::session::{BoundedSessionStore, ChatMessage, SessionStore, SessionSummarySegment};
use crate::shortcuts::{
    CRAWL_TOOL_NAME, WorkflowBridgeMode, parse_crawl_shortcut, parse_react_shortcut,
    parse_workflow_bridge_shortcut,
};
use embedding_dimension::{
    EMBEDDING_SOURCE_EMBEDDING, EMBEDDING_SOURCE_EMBEDDING_REPAIRED, EMBEDDING_SOURCE_HASH,
    repair_embedding_dimension,
};
use memory::{RecalledEpisodeCandidate, apply_recall_credit, select_recall_credit_candidates};
use memory_recall::{
    MEMORY_RECALL_MESSAGE_NAME, MemoryRecallInput, build_memory_context_message,
    estimate_messages_tokens, filter_recalled_episodes, plan_memory_recall,
};
use memory_recall_feedback::{
    RECALL_FEEDBACK_SOURCE_COMMAND, RecallOutcome, ToolExecutionSummary, apply_feedback_to_plan,
    resolve_feedback_outcome, update_feedback_bias,
};
use memory_state::{MemoryStateBackend, MemoryStateLoadStatus};
use memory_stream_consumer::spawn_memory_stream_consumer;
use omega::ShortcutFallbackAction;
use reflection::PolicyHintDirective;
use system_prompt_injection_state::SYSTEM_PROMPT_INJECTION_CONTEXT_MESSAGE_NAME;

const MEMORY_EMBED_FALLBACK_TIMEOUT: Duration = Duration::from_secs(3);

pub use consolidation::summarise_drained_turns;
pub use context_budget::prune_messages_for_token_budget;
pub use context_budget_state::{SessionContextBudgetClassSnapshot, SessionContextBudgetSnapshot};
pub use graph_bridge::{GraphBridgeRequest, GraphBridgeResult, validate_graph_bridge_request};
pub use memory_recall_metrics::{MemoryRecallLatencyBucketsSnapshot, MemoryRecallMetricsSnapshot};
pub use memory_recall_state::{SessionMemoryRecallDecision, SessionMemoryRecallSnapshot};
pub use memory_state::MemoryRuntimeStatusSnapshot;
pub use session_context::{
    SessionContextMode, SessionContextSnapshotInfo, SessionContextStats, SessionContextWindowInfo,
};
pub use system_prompt_injection_state::SessionSystemPromptInjectionSnapshot;

/// Explicit session-level recall feedback direction.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionRecallFeedbackDirection {
    Up,
    Down,
}

/// Result of applying explicit session-level recall feedback.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SessionRecallFeedbackUpdate {
    pub previous_bias: f32,
    pub updated_bias: f32,
    pub direction: SessionRecallFeedbackDirection,
}

/// Agent: config + session store (or bounded session) + LLM client + optional MCP pool + optional memory.
pub struct Agent {
    config: AgentConfig,
    session: SessionStore,
    /// When set, session history is bounded; context built from recent turns.
    bounded_session: Option<BoundedSessionStore>,
    /// When set (and window enabled), consolidation stores episodes into omni-memory.
    memory_store: Option<Arc<EpisodeStore>>,
    /// Memory persistence backend for episode/Q state snapshots.
    memory_state_backend: Option<Arc<MemoryStateBackend>>,
    /// Startup load status for memory state persistence.
    memory_state_load_status: MemoryStateLoadStatus,
    /// Embedding client for semantic memory recall/store.
    embedding_client: Option<EmbeddingClient>,
    /// Most recent context-budget report by logical session id.
    context_budget_snapshots: Arc<RwLock<HashMap<String, SessionContextBudgetSnapshot>>>,
    /// Process-level memory recall metrics snapshot (for diagnostics dashboards).
    memory_recall_metrics: Arc<RwLock<memory_recall_metrics::MemoryRecallMetricsState>>,
    /// Session-level recall feedback bias (-1: broaden recall, +1: tighten recall).
    memory_recall_feedback: Arc<RwLock<HashMap<String, f32>>>,
    /// Session-level injected system prompt window (XML Q&A).
    system_prompt_injection: Arc<RwLock<HashMap<String, SessionSystemPromptInjectionSnapshot>>>,
    /// One-shot next-turn policy hints derived from reflection lifecycle.
    reflection_policy_hints: Arc<RwLock<HashMap<String, PolicyHintDirective>>>,
    /// Counter used by periodic memory decay policy.
    memory_decay_turn_counter: Arc<AtomicU64>,
    llm: LlmClient,
    mcp: Option<crate::mcp_pool::McpClientPool>,
    memory_stream_consumer_task: Option<tokio::task::JoinHandle<()>>,
}

impl Agent {
    /// Build agent from config. Connects to first MCP server that has a URL.
    pub async fn from_config(config: AgentConfig) -> Result<Self> {
        let api_key = config.resolve_api_key();
        let llm = LlmClient::new(config.inference_url.clone(), config.model.clone(), api_key);
        let session = SessionStore::new()?;
        let bounded_session = match config.window_max_turns {
            Some(max_turns) => Some(BoundedSessionStore::new_with_limits(
                max_turns,
                config.summary_max_segments,
                config.summary_max_chars,
            )?),
            None => None,
        };
        Self::build_with_backends(config, llm, session, bounded_session).await
    }

    #[doc(hidden)]
    pub async fn from_config_with_session_backends_for_test(
        config: AgentConfig,
        session: SessionStore,
        bounded_session: Option<BoundedSessionStore>,
    ) -> Result<Self> {
        let api_key = config.resolve_api_key();
        let llm = LlmClient::new(config.inference_url.clone(), config.model.clone(), api_key);
        Self::build_with_backends(config, llm, session, bounded_session).await
    }

    async fn build_with_backends(
        config: AgentConfig,
        llm: LlmClient,
        session: SessionStore,
        bounded_session: Option<BoundedSessionStore>,
    ) -> Result<Self> {
        let mcp = config
            .mcp_servers
            .iter()
            .find(|s| s.url.is_some())
            .and_then(|s| s.url.as_deref());
        let mcp_client = if let Some(url) = mcp {
            let connect_config = McpPoolConnectConfig {
                pool_size: config.mcp_pool_size,
                handshake_timeout_secs: config.mcp_handshake_timeout_secs,
                connect_retries: config.mcp_connect_retries,
                connect_retry_backoff_ms: config.mcp_connect_retry_backoff_ms,
                tool_timeout_secs: config.mcp_tool_timeout_secs,
                list_tools_cache_ttl_ms: config.mcp_list_tools_cache_ttl_ms,
            };
            Some(connect_pool(url, connect_config).await?)
        } else {
            None
        };
        let (memory_store, memory_state_backend, memory_state_load_status) =
            if let Some(memory_cfg) = config.memory.as_ref() {
                let backend = MemoryStateBackend::from_config(memory_cfg)?;
                tracing::info!(
                    event = SessionEvent::MemoryBackendInitialized.as_str(),
                    configured_backend = %memory_cfg.persistence_backend,
                    backend = backend.backend_name(),
                    strict_startup = backend.strict_startup(),
                    store_path = %memory_cfg.path,
                    table_name = %memory_cfg.table_name,
                    embedding_dim = memory_cfg.embedding_dim,
                    "memory persistence backend initialized"
                );
                let store = EpisodeStore::new(StoreConfig {
                    path: memory_cfg.path.clone(),
                    embedding_dim: memory_cfg.embedding_dim,
                    table_name: memory_cfg.table_name.clone(),
                });
                let load_started = Instant::now();
                let load_status = match backend.load(&store) {
                    Ok(()) => {
                        tracing::debug!(
                            event = SessionEvent::MemoryStateLoadSucceeded.as_str(),
                            backend = backend.backend_name(),
                            strict_startup = backend.strict_startup(),
                            episodes = store.len(),
                            q_values = store.q_table.len(),
                            duration_ms = load_started.elapsed().as_millis(),
                            "memory state loaded from persistence backend"
                        );
                        MemoryStateLoadStatus::Loaded
                    }
                    Err(error) => {
                        let duration_ms = load_started.elapsed().as_millis();
                        if backend.strict_startup() {
                            tracing::error!(
                                event = SessionEvent::MemoryStateLoadFailed.as_str(),
                                backend = backend.backend_name(),
                                strict_startup = true,
                                continue_startup = false,
                                duration_ms,
                                error = %error,
                                "strict memory backend load failed during startup"
                            );
                            return Err(error)
                                .context("strict valkey memory backend failed during startup");
                        }
                        tracing::warn!(
                            event = SessionEvent::MemoryStateLoadFailed.as_str(),
                            backend = backend.backend_name(),
                            strict_startup = false,
                            continue_startup = true,
                            duration_ms,
                            error = %error,
                            "failed to load persisted memory state; continuing with empty memory"
                        );
                        MemoryStateLoadStatus::LoadFailedContinue
                    }
                };
                (Some(Arc::new(store)), Some(Arc::new(backend)), load_status)
            } else {
                (None, None, MemoryStateLoadStatus::NotConfigured)
            };

        let embedding_client = config.memory.as_ref().map(|memory_cfg| {
            let base_url = memory_cfg
                .embedding_base_url
                .as_ref()
                .map(String::as_str)
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(ToString::to_string)
                .or_else(|| {
                    std::env::var("OMNI_AGENT_EMBED_BASE_URL")
                        .ok()
                        .map(|value| value.trim().to_string())
                        .filter(|value| !value.is_empty())
                })
                .unwrap_or_else(|| "http://127.0.0.1:3002".to_string());
            EmbeddingClient::new(&base_url, 15)
        });
        let memory_stream_consumer_task = config.memory.as_ref().and_then(|memory_cfg| {
            spawn_memory_stream_consumer(memory_cfg, session.redis_runtime_snapshot())
        });

        Ok(Self {
            config,
            session,
            bounded_session,
            memory_store,
            memory_state_backend,
            memory_state_load_status,
            embedding_client,
            context_budget_snapshots: Arc::new(RwLock::new(HashMap::new())),
            memory_recall_metrics: Arc::new(RwLock::new(
                memory_recall_metrics::MemoryRecallMetricsState::default(),
            )),
            memory_recall_feedback: Arc::new(RwLock::new(HashMap::new())),
            system_prompt_injection: Arc::new(RwLock::new(HashMap::new())),
            reflection_policy_hints: Arc::new(RwLock::new(HashMap::new())),
            memory_decay_turn_counter: Arc::new(AtomicU64::new(0)),
            llm,
            mcp: mcp_client,
            memory_stream_consumer_task,
        })
    }

    async fn try_embed_intent(
        &self,
        intent: &str,
        expected_dim: usize,
    ) -> Option<(Vec<f32>, &'static str)> {
        let client = self.embedding_client.as_ref()?;
        let model = self
            .config
            .memory
            .as_ref()
            .and_then(|cfg| cfg.embedding_model.as_deref());
        let embedded = client.embed_with_model(intent, model).await?;
        if embedded.len() == expected_dim {
            return Some((embedded, EMBEDDING_SOURCE_EMBEDDING));
        }
        let repaired = repair_embedding_dimension(&embedded, expected_dim);
        tracing::warn!(
            event = SessionEvent::MemoryEmbeddingDimMismatch.as_str(),
            returned_dim = embedded.len(),
            expected_dim,
            repair_strategy = "resample",
            "embedding dimension mismatch; repaired vector for memory operations"
        );
        Some((repaired, EMBEDDING_SOURCE_EMBEDDING_REPAIRED))
    }

    async fn embedding_or_hash(
        &self,
        intent: &str,
        store: &EpisodeStore,
        expected_dim: usize,
    ) -> Vec<f32> {
        self.embedding_or_hash_with_source(intent, store, expected_dim)
            .await
            .0
    }

    async fn embedding_or_hash_with_source(
        &self,
        intent: &str,
        store: &EpisodeStore,
        expected_dim: usize,
    ) -> (Vec<f32>, &'static str) {
        match tokio::time::timeout(
            MEMORY_EMBED_FALLBACK_TIMEOUT,
            self.try_embed_intent(intent, expected_dim),
        )
        .await
        {
            Ok(Some((embedding, source))) => {
                return (embedding, source);
            }
            Ok(None) => {}
            Err(_) => {
                tracing::warn!(
                    event = "agent.memory.embedding.timeout_fallback_hash",
                    timeout_ms = MEMORY_EMBED_FALLBACK_TIMEOUT.as_millis(),
                    "memory embedding timed out; falling back to hash encoder"
                );
            }
        }
        (store.encoder().encode(intent), EMBEDDING_SOURCE_HASH)
    }

    fn next_runtime_turn_id(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis() as u64)
            .unwrap_or_default()
    }

    fn record_omega_decision(
        &self,
        session_id: &str,
        decision: &OmegaDecision,
        workflow_mode: Option<WorkflowBridgeMode>,
        tool_name: Option<&str>,
    ) {
        tracing::debug!(
            event = SessionEvent::RouteDecisionSelected.as_str(),
            session_id,
            workflow_mode = workflow_mode.map(WorkflowBridgeMode::as_str),
            tool_name,
            route = decision.route.as_str(),
            risk_level = decision.risk_level.as_str(),
            confidence = decision.confidence,
            fallback_policy = decision.fallback_policy.as_str(),
            tool_trust_class = decision.tool_trust_class.as_str(),
            reason = %decision.reason,
            policy_id = ?decision.policy_id,
            "omega route decision selected"
        );
    }

    fn record_shortcut_fallback(
        &self,
        session_id: &str,
        decision: &OmegaDecision,
        workflow_mode: WorkflowBridgeMode,
        tool_name: &str,
        action: ShortcutFallbackAction,
        error: &anyhow::Error,
    ) {
        tracing::warn!(
            event = SessionEvent::RouteFallbackApplied.as_str(),
            session_id,
            workflow_mode = workflow_mode.as_str(),
            tool_name,
            route = decision.route.as_str(),
            fallback_policy = decision.fallback_policy.as_str(),
            fallback_action = action.as_str(),
            error = %error,
            "omega route fallback applied"
        );
    }

    fn record_injection_snapshot(&self, session_id: &str, snapshot: &InjectionSnapshot) {
        let role_mix_profile_id = snapshot
            .role_mix
            .as_ref()
            .map(|profile| profile.profile_id.as_str());
        let role_mix_roles = snapshot
            .role_mix
            .as_ref()
            .map_or(0, |profile| profile.roles.len());
        tracing::debug!(
            event = SessionEvent::InjectionSnapshotCreated.as_str(),
            session_id,
            snapshot_id = %snapshot.snapshot_id,
            turn_id = snapshot.turn_id,
            blocks = snapshot.blocks.len(),
            total_chars = snapshot.total_chars,
            dropped_blocks = snapshot.dropped_block_ids.len(),
            truncated_blocks = snapshot.truncated_block_ids.len(),
            role_mix_profile_id,
            role_mix_roles,
            "injection snapshot created"
        );
        for block_id in &snapshot.dropped_block_ids {
            tracing::debug!(
                event = SessionEvent::InjectionBlockDropped.as_str(),
                session_id,
                snapshot_id = %snapshot.snapshot_id,
                block_id,
                "injection block dropped"
            );
        }
        for block_id in &snapshot.truncated_block_ids {
            tracing::debug!(
                event = SessionEvent::InjectionBlockTruncated.as_str(),
                session_id,
                snapshot_id = %snapshot.snapshot_id,
                block_id,
                "injection block truncated"
            );
        }
    }

    async fn build_shortcut_injection_snapshot(
        &self,
        session_id: &str,
        turn_id: u64,
        user_message: &str,
    ) -> Result<Option<InjectionSnapshot>> {
        let mut context_messages = Vec::new();
        if let Some(ref w) = self.bounded_session {
            let summary_segments = w
                .get_recent_summary_segments(session_id, self.config.summary_max_segments)
                .await?;
            if !summary_segments.is_empty() {
                let segment_count = summary_segments.len();
                context_messages.extend(summary_segments.into_iter().enumerate().map(
                    |(index, segment)| ChatMessage {
                        role: "system".to_string(),
                        content: Some(format!(
                            "Compressed conversation history from older turns (segment {}/{}): {} (turns={}, tools={})",
                            index + 1,
                            segment_count,
                            segment.summary,
                            segment.turn_count,
                            segment.tool_calls
                        )),
                        tool_calls: None,
                        tool_call_id: None,
                        name: Some(context_budget::SESSION_SUMMARY_MESSAGE_NAME.to_string()),
                    },
                ));
            }
        }
        if let Some(snapshot) = self
            .inspect_session_system_prompt_injection(session_id)
            .await
        {
            context_messages.push(ChatMessage {
                role: "system".to_string(),
                content: Some(snapshot.xml),
                tool_calls: None,
                tool_call_id: None,
                name: Some(SYSTEM_PROMPT_INJECTION_CONTEXT_MESSAGE_NAME.to_string()),
            });
        }
        if let (Some(ref store), Some(ref mem_cfg)) =
            (self.memory_store.as_ref(), self.config.memory.as_ref())
        {
            let recall_plan = plan_memory_recall(MemoryRecallInput {
                base_k1: mem_cfg.recall_k1,
                base_k2: mem_cfg.recall_k2,
                base_lambda: mem_cfg.recall_lambda,
                context_budget_tokens: self.config.context_budget_tokens,
                context_budget_reserve_tokens: self.config.context_budget_reserve_tokens,
                context_tokens_before_recall: estimate_messages_tokens(&context_messages),
                active_turns_estimate: 0,
                window_max_turns: self.config.window_max_turns,
                summary_segment_count: 0,
            });
            let recall_feedback_bias = self.recall_feedback_bias(session_id).await;
            let recall_plan = apply_feedback_to_plan(recall_plan, recall_feedback_bias);
            let query_embedding = self
                .embedding_or_hash(user_message, store, mem_cfg.embedding_dim)
                .await;
            let recalled = store.two_phase_recall_with_embedding_for_scope(
                session_id,
                &query_embedding,
                recall_plan.k1,
                recall_plan.k2,
                recall_plan.lambda,
            );
            let recalled = filter_recalled_episodes(recalled, &recall_plan);
            if let Some(system_content) =
                build_memory_context_message(&recalled, recall_plan.max_context_chars)
            {
                context_messages.push(ChatMessage {
                    role: "system".to_string(),
                    content: Some(system_content),
                    tool_calls: None,
                    tool_call_id: None,
                    name: Some(MEMORY_RECALL_MESSAGE_NAME.to_string()),
                });
            }
        }
        if context_messages.is_empty() {
            return Ok(None);
        }
        let mut policy = InjectionPolicy::default();
        policy.max_chars = policy.max_chars.min(3_500);
        injection::build_snapshot_from_messages(session_id, turn_id, context_messages, policy)
            .map(Some)
            .context("failed to build shortcut injection snapshot")
    }

    /// Run one user turn: history + user message -> LLM (with tools if MCP connected) -> handle tool_calls -> return final text.
    /// When memory is enabled, two_phase_recall(current intent) is injected as system context before the conversation.
    pub async fn run_turn(&self, session_id: &str, user_message: &str) -> Result<String> {
        let forced_react_message = parse_react_shortcut(user_message);
        let mut force_react = forced_react_message.is_some();
        let mut user_message_owned =
            forced_react_message.unwrap_or_else(|| user_message.to_string());
        let turn_id = self.next_runtime_turn_id();

        if !force_react
            && let Some(shortcut) = parse_workflow_bridge_shortcut(user_message_owned.as_str())
        {
            let decision = omega::decide_for_shortcut(
                shortcut.mode,
                user_message_owned.as_str(),
                &shortcut.tool_name,
            );
            self.record_omega_decision(
                session_id,
                &decision,
                Some(shortcut.mode),
                Some(shortcut.tool_name.as_str()),
            );

            if decision.route == OmegaRoute::Graph {
                let shortcut_snapshot = self
                    .build_shortcut_injection_snapshot(
                        session_id,
                        turn_id,
                        user_message_owned.as_str(),
                    )
                    .await?;
                if let Some(snapshot) = &shortcut_snapshot {
                    self.record_injection_snapshot(session_id, snapshot);
                }
                let arguments = injection::augment_shortcut_arguments(
                    shortcut.arguments.clone(),
                    shortcut_snapshot.as_ref(),
                    &decision,
                    shortcut.mode,
                );

                let mut tool_summary = ToolExecutionSummary::default();
                let initial_request = graph_bridge::GraphBridgeRequest {
                    tool_name: shortcut.tool_name.clone(),
                    arguments,
                };

                let out = match self.execute_graph_bridge(initial_request).await {
                    Ok(result) => {
                        tool_summary.record_result(result.is_error);
                        result.output
                    }
                    Err(initial_error) => {
                        tool_summary.record_transport_failure();
                        match omega::resolve_shortcut_fallback(&decision, 0) {
                            ShortcutFallbackAction::RetryBridgeWithoutMetadata => {
                                self.record_shortcut_fallback(
                                    session_id,
                                    &decision,
                                    shortcut.mode,
                                    &shortcut.tool_name,
                                    ShortcutFallbackAction::RetryBridgeWithoutMetadata,
                                    &initial_error,
                                );
                                match self
                                    .execute_graph_bridge(graph_bridge::GraphBridgeRequest {
                                        tool_name: shortcut.tool_name.clone(),
                                        arguments: shortcut.arguments.clone(),
                                    })
                                    .await
                                {
                                    Ok(result) => {
                                        tool_summary.record_result(result.is_error);
                                        result.output
                                    }
                                    Err(retry_error) => {
                                        tool_summary.record_transport_failure();
                                        let error_text = retry_error.to_string();
                                        let _ = self
                                            .update_recall_feedback(
                                                session_id,
                                                user_message_owned.as_str(),
                                                &error_text,
                                                Some(&tool_summary),
                                            )
                                            .await;
                                        self.reflect_turn_and_update_policy_hint(
                                            session_id,
                                            turn_id,
                                            decision.route,
                                            user_message_owned.as_str(),
                                            &error_text,
                                            "error",
                                            tool_summary.attempted,
                                        )
                                        .await;
                                        return Err(retry_error);
                                    }
                                }
                            }
                            ShortcutFallbackAction::RouteToReact => {
                                self.record_shortcut_fallback(
                                    session_id,
                                    &decision,
                                    shortcut.mode,
                                    &shortcut.tool_name,
                                    ShortcutFallbackAction::RouteToReact,
                                    &initial_error,
                                );
                                force_react = true;
                                format!(
                                    "Execute this task with ReAct because workflow bridge failed: {}",
                                    user_message_owned
                                )
                            }
                            ShortcutFallbackAction::Abort => {
                                self.record_shortcut_fallback(
                                    session_id,
                                    &decision,
                                    shortcut.mode,
                                    &shortcut.tool_name,
                                    ShortcutFallbackAction::Abort,
                                    &initial_error,
                                );
                                let error_text = initial_error.to_string();
                                let _ = self
                                    .update_recall_feedback(
                                        session_id,
                                        user_message_owned.as_str(),
                                        &error_text,
                                        Some(&tool_summary),
                                    )
                                    .await;
                                self.reflect_turn_and_update_policy_hint(
                                    session_id,
                                    turn_id,
                                    decision.route,
                                    user_message_owned.as_str(),
                                    &error_text,
                                    "error",
                                    tool_summary.attempted,
                                )
                                .await;
                                return Err(initial_error);
                            }
                        }
                    }
                };

                if !force_react {
                    let _ = self
                        .update_recall_feedback(
                            session_id,
                            user_message_owned.as_str(),
                            &out,
                            Some(&tool_summary),
                        )
                        .await;
                    self.append_turn_to_session(session_id, user_message_owned.as_str(), &out, 1)
                        .await?;
                    self.reflect_turn_and_update_policy_hint(
                        session_id,
                        turn_id,
                        decision.route,
                        user_message_owned.as_str(),
                        &out,
                        "completed",
                        tool_summary.attempted,
                    )
                    .await;
                    return Ok(out);
                }
                user_message_owned = out;
            } else {
                force_react = true;
            }
        }

        let user_message = user_message_owned.as_str();

        if !force_react && let Some(shortcut) = parse_crawl_shortcut(user_message) {
            let mut tool_summary = ToolExecutionSummary::default();
            let out = match self
                .call_mcp_tool_with_diagnostics(CRAWL_TOOL_NAME, Some(shortcut.to_arguments()))
                .await
            {
                Ok(output) => {
                    tool_summary.record_result(output.is_error);
                    output.text
                }
                Err(error) => {
                    tool_summary.record_transport_failure();
                    let error_text = error.to_string();
                    let _ = self
                        .update_recall_feedback(
                            session_id,
                            user_message,
                            &error_text,
                            Some(&tool_summary),
                        )
                        .await;
                    self.reflect_turn_and_update_policy_hint(
                        session_id,
                        turn_id,
                        OmegaRoute::React,
                        user_message,
                        &error_text,
                        "error",
                        tool_summary.attempted,
                    )
                    .await;
                    return Err(error);
                }
            };
            let _ = self
                .update_recall_feedback(session_id, user_message, &out, Some(&tool_summary))
                .await;
            self.append_turn_to_session(session_id, user_message, &out, 1)
                .await?;
            self.reflect_turn_and_update_policy_hint(
                session_id,
                turn_id,
                OmegaRoute::React,
                user_message,
                &out,
                "completed",
                tool_summary.attempted,
            )
            .await;
            return Ok(out);
        }

        let policy_hint = self.take_reflection_policy_hint(session_id).await;
        if let Some(hint) = policy_hint.as_ref() {
            tracing::debug!(
                event = SessionEvent::ReflectionPolicyHintApplied.as_str(),
                session_id,
                source_turn_id = hint.source_turn_id,
                preferred_route = hint.preferred_route.as_str(),
                risk_floor = hint.risk_floor.as_str(),
                fallback_override = hint.fallback_override.map(OmegaFallbackPolicy::as_str),
                tool_trust_class = hint.tool_trust_class.as_str(),
                reason = %hint.reason,
                "reflection policy hint applied to route decision"
            );
        }
        let decision = omega::apply_policy_hint(
            omega::decide_for_standard_turn(force_react),
            policy_hint.as_ref(),
        );
        self.record_omega_decision(session_id, &decision, None, None);

        let mut summary_segments: Vec<SessionSummarySegment> = Vec::new();
        let mut messages: Vec<ChatMessage> = if let Some(ref w) = self.bounded_session {
            let limit = self.config.window_max_turns.unwrap_or(512);
            summary_segments = w
                .get_recent_summary_segments(session_id, self.config.summary_max_segments)
                .await?;
            w.get_recent_messages(session_id, limit).await?
        } else {
            self.session.get(session_id).await?
        };

        if !summary_segments.is_empty() {
            let segment_count = summary_segments.len();
            let summary_messages = summary_segments
                .iter()
                .enumerate()
                .map(|(index, segment)| ChatMessage {
                    role: "system".to_string(),
                    content: Some(format!(
                        "Compressed conversation history from older turns (segment {}/{}): {} (turns={}, tools={})",
                        index + 1,
                        segment_count,
                        segment.summary,
                        segment.turn_count,
                        segment.tool_calls
                    )),
                    tool_calls: None,
                    tool_call_id: None,
                    name: Some(context_budget::SESSION_SUMMARY_MESSAGE_NAME.to_string()),
                })
                .collect::<Vec<_>>();
            messages.splice(0..0, summary_messages);
        }

        if let Some(snapshot) = self
            .inspect_session_system_prompt_injection(session_id)
            .await
        {
            messages.insert(
                0,
                ChatMessage {
                    role: "system".to_string(),
                    content: Some(snapshot.xml),
                    tool_calls: None,
                    tool_call_id: None,
                    name: Some(SYSTEM_PROMPT_INJECTION_CONTEXT_MESSAGE_NAME.to_string()),
                },
            );
        }

        messages.push(ChatMessage {
            role: "user".to_string(),
            content: Some(user_message.to_string()),
            tool_calls: None,
            tool_call_id: None,
            name: None,
        });

        let mut recall_credit_candidates: Vec<RecalledEpisodeCandidate> = Vec::new();

        if let (Some(ref store), Some(ref mem_cfg)) =
            (self.memory_store.as_ref(), self.config.memory.as_ref())
        {
            let recall_started = Instant::now();
            let active_turns_estimate = messages
                .iter()
                .filter(|message| message.role == "user" || message.role == "assistant")
                .count()
                / 2;
            let query_tokens = count_tokens(user_message);
            let recall_plan = plan_memory_recall(MemoryRecallInput {
                base_k1: mem_cfg.recall_k1,
                base_k2: mem_cfg.recall_k2,
                base_lambda: mem_cfg.recall_lambda,
                context_budget_tokens: self.config.context_budget_tokens,
                context_budget_reserve_tokens: self.config.context_budget_reserve_tokens,
                context_tokens_before_recall: estimate_messages_tokens(&messages),
                active_turns_estimate,
                window_max_turns: self.config.window_max_turns,
                summary_segment_count: summary_segments.len(),
            });
            let recall_feedback_bias = self.recall_feedback_bias(session_id).await;
            let recall_plan = apply_feedback_to_plan(recall_plan, recall_feedback_bias);
            tracing::debug!(
                event = SessionEvent::MemoryRecallPlanned.as_str(),
                session_id,
                memory_scope = session_id,
                k1 = recall_plan.k1,
                k2 = recall_plan.k2,
                lambda = recall_plan.lambda,
                min_score = recall_plan.min_score,
                max_context_chars = recall_plan.max_context_chars,
                budget_pressure = recall_plan.budget_pressure,
                window_pressure = recall_plan.window_pressure,
                effective_budget_tokens = ?recall_plan.effective_budget_tokens,
                active_turns_estimate,
                summary_segment_count = summary_segments.len(),
                recall_feedback_bias,
                "memory recall plan selected"
            );
            self.record_memory_recall_plan_metrics().await;

            let (query_embedding, embedding_source) = self
                .embedding_or_hash_with_source(user_message, store, mem_cfg.embedding_dim)
                .await;
            let recalled = store.two_phase_recall_with_embedding_for_scope(
                session_id,
                &query_embedding,
                recall_plan.k1,
                recall_plan.k2,
                recall_plan.lambda,
            );
            let recalled_count = recalled.len();
            let recalled = filter_recalled_episodes(recalled, &recall_plan);
            if let Some(system_content) =
                build_memory_context_message(&recalled, recall_plan.max_context_chars)
            {
                if mem_cfg.recall_credit_enabled {
                    recall_credit_candidates = select_recall_credit_candidates(
                        &recalled,
                        mem_cfg.recall_credit_max_candidates,
                    );
                }
                let injected_count = recalled.len();
                let context_chars_injected = system_content.chars().count();
                let pipeline_duration_ms = recall_started.elapsed().as_millis() as u64;
                let best_score = recalled
                    .first()
                    .map(|(_, score)| *score)
                    .unwrap_or_default();
                let weakest_score = recalled.last().map(|(_, score)| *score).unwrap_or_default();
                messages.insert(
                    0,
                    ChatMessage {
                        role: "system".to_string(),
                        content: Some(system_content),
                        tool_calls: None,
                        tool_call_id: None,
                        name: Some(MEMORY_RECALL_MESSAGE_NAME.to_string()),
                    },
                );
                tracing::debug!(
                    event = SessionEvent::MemoryRecallInjected.as_str(),
                    session_id,
                    query_tokens,
                    embedding_source,
                    recalled_total = recalled_count,
                    recalled_selected = recalled.len(),
                    recalled_injected = injected_count,
                    context_chars_injected,
                    pipeline_duration_ms,
                    best_score,
                    weakest_score,
                    "memory recall context injected"
                );
                self.record_memory_recall_result_metrics(
                    memory_recall_state::SessionMemoryRecallDecision::Injected,
                    recalled.len(),
                    injected_count,
                    context_chars_injected,
                    pipeline_duration_ms,
                )
                .await;
                self.record_memory_recall_snapshot(
                    session_id,
                    memory_recall_state::SessionMemoryRecallSnapshot::from_plan(
                        recall_plan,
                        active_turns_estimate,
                        summary_segments.len(),
                        query_tokens,
                        recall_feedback_bias,
                        embedding_source,
                        recalled_count,
                        recalled.len(),
                        injected_count,
                        context_chars_injected,
                        Some(best_score),
                        Some(weakest_score),
                        pipeline_duration_ms,
                        memory_recall_state::SessionMemoryRecallDecision::Injected,
                    ),
                )
                .await;
            } else {
                let pipeline_duration_ms = recall_started.elapsed().as_millis() as u64;
                let best_score = recalled
                    .first()
                    .map(|(_, score)| *score)
                    .unwrap_or_default();
                tracing::debug!(
                    event = SessionEvent::MemoryRecallSkipped.as_str(),
                    session_id,
                    query_tokens,
                    embedding_source,
                    recalled_total = recalled_count,
                    recalled_selected = recalled.len(),
                    pipeline_duration_ms,
                    best_score,
                    "memory recall skipped after scoring/compaction filters"
                );
                self.record_memory_recall_result_metrics(
                    memory_recall_state::SessionMemoryRecallDecision::Skipped,
                    recalled.len(),
                    0,
                    0,
                    pipeline_duration_ms,
                )
                .await;
                self.record_memory_recall_snapshot(
                    session_id,
                    memory_recall_state::SessionMemoryRecallSnapshot::from_plan(
                        recall_plan,
                        active_turns_estimate,
                        summary_segments.len(),
                        query_tokens,
                        recall_feedback_bias,
                        embedding_source,
                        recalled_count,
                        recalled.len(),
                        0,
                        0,
                        recalled.first().map(|(_, score)| *score),
                        recalled.last().map(|(_, score)| *score),
                        pipeline_duration_ms,
                        memory_recall_state::SessionMemoryRecallDecision::Skipped,
                    ),
                )
                .await;
            }
        }

        let raw_messages = messages;
        match injection::normalize_messages_with_snapshot(
            session_id,
            turn_id,
            raw_messages.clone(),
            InjectionPolicy::default(),
        ) {
            Ok(normalized) => {
                if let Some(snapshot) = normalized.snapshot.as_ref() {
                    self.record_injection_snapshot(session_id, snapshot);
                }
                messages = normalized.messages;
            }
            Err(error) => {
                tracing::warn!(
                    session_id,
                    error = %error,
                    "failed to normalize injection snapshot; context messages unchanged"
                );
                messages = raw_messages;
            }
        }

        if let Some(context_budget_tokens) = self.config.context_budget_tokens
            && context_budget_tokens > 0
        {
            let result = context_budget::prune_messages_for_token_budget_with_strategy(
                messages,
                context_budget_tokens,
                self.config.context_budget_reserve_tokens,
                self.config.context_budget_strategy,
            );
            messages = result.messages;
            let report = result.report;
            self.record_context_budget_snapshot(session_id, &report)
                .await;
            tracing::debug!(
                session_id,
                strategy = report.strategy.as_str(),
                budget_tokens = report.budget_tokens,
                reserve_tokens = report.reserve_tokens,
                effective_budget_tokens = report.effective_budget_tokens,
                pre_messages = report.pre_messages,
                post_messages = report.post_messages,
                pre_tokens = report.pre_tokens,
                post_tokens = report.post_tokens,
                dropped_messages = report.pre_messages.saturating_sub(report.post_messages),
                dropped_tokens = report.pre_tokens.saturating_sub(report.post_tokens),
                non_system_pre_messages = report.non_system.input_messages,
                non_system_kept_messages = report.non_system.kept_messages,
                non_system_dropped_messages = report.non_system.dropped_messages(),
                non_system_pre_tokens = report.non_system.input_tokens,
                non_system_kept_tokens = report.non_system.kept_tokens,
                non_system_dropped_tokens = report.non_system.dropped_tokens(),
                non_system_truncated_messages = report.non_system.truncated_messages,
                non_system_truncated_tokens = report.non_system.truncated_tokens,
                regular_system_pre_messages = report.regular_system.input_messages,
                regular_system_kept_messages = report.regular_system.kept_messages,
                regular_system_dropped_messages = report.regular_system.dropped_messages(),
                regular_system_pre_tokens = report.regular_system.input_tokens,
                regular_system_kept_tokens = report.regular_system.kept_tokens,
                regular_system_dropped_tokens = report.regular_system.dropped_tokens(),
                regular_system_truncated_messages = report.regular_system.truncated_messages,
                regular_system_truncated_tokens = report.regular_system.truncated_tokens,
                summary_pre_messages = report.summary_system.input_messages,
                summary_kept_messages = report.summary_system.kept_messages,
                summary_dropped_messages = report.summary_system.dropped_messages(),
                summary_pre_tokens = report.summary_system.input_tokens,
                summary_kept_tokens = report.summary_system.kept_tokens,
                summary_dropped_tokens = report.summary_system.dropped_tokens(),
                summary_truncated_messages = report.summary_system.truncated_messages,
                summary_truncated_tokens = report.summary_system.truncated_tokens,
                "applied token-budget context packing"
            );
        }

        let tools_json = if self.mcp.is_some() {
            self.mcp_tools_for_llm().await?
        } else {
            None
        };

        let mut round = 0;
        let mut total_tool_calls_this_turn: u32 = 0;
        let mut last_tool_names: Vec<String> = Vec::new();
        let mut tool_summary = ToolExecutionSummary::default();
        loop {
            if round >= self.config.max_tool_rounds {
                let hint = format!(
                    "max_tool_rounds ({}) exceeded after {} rounds ({} tool calls). \\
                    Try again with a fresh message (rounds reset per message), or increase \\
                    OMNI_AGENT_MAX_TOOL_ROUNDS / telegram.max_tool_rounds. \\
                    Last tools: {:?}",
                    self.config.max_tool_rounds, round, total_tool_calls_this_turn, last_tool_names
                );
                tracing::warn!("{}", hint);
                let outcome = self
                    .update_recall_feedback(session_id, user_message, &hint, Some(&tool_summary))
                    .await;
                self.apply_memory_recall_credit(session_id, &recall_credit_candidates, outcome);
                self.reflect_turn_and_update_policy_hint(
                    session_id,
                    turn_id,
                    decision.route,
                    user_message,
                    &hint,
                    "error",
                    total_tool_calls_this_turn,
                )
                .await;
                return Err(anyhow::anyhow!("{}", hint));
            }
            round += 1;

            let resp = self.llm.chat(messages.clone(), tools_json.clone()).await?;

            if let Some(ref tool_calls) = resp.tool_calls {
                if tool_calls.is_empty() {
                    let out = resp.content.unwrap_or_default();
                    let outcome = self
                        .update_recall_feedback(session_id, user_message, &out, Some(&tool_summary))
                        .await;
                    self.apply_memory_recall_credit(session_id, &recall_credit_candidates, outcome);
                    self.append_turn_to_session(
                        session_id,
                        user_message,
                        &out,
                        total_tool_calls_this_turn,
                    )
                    .await?;
                    self.reflect_turn_and_update_policy_hint(
                        session_id,
                        turn_id,
                        decision.route,
                        user_message,
                        &out,
                        "completed",
                        total_tool_calls_this_turn,
                    )
                    .await;
                    return Ok(out);
                }
                total_tool_calls_this_turn += tool_calls.len() as u32;
                last_tool_names = tool_calls
                    .iter()
                    .map(|tc| tc.function.name.clone())
                    .collect();
                // Append assistant message with tool_calls.
                messages.push(ChatMessage {
                    role: "assistant".to_string(),
                    content: resp.content.clone(),
                    tool_calls: Some(tool_calls.clone()),
                    tool_call_id: None,
                    name: None,
                });
                // Call each tool and append tool results.
                for tc in tool_calls.iter() {
                    let name = tc.function.name.clone();
                    let args_str = tc.function.arguments.clone();
                    let args = if args_str.is_empty() {
                        None
                    } else {
                        serde_json::from_str(&args_str).ok()
                    };
                    let result = match self.call_mcp_tool_with_diagnostics(&name, args).await {
                        Ok(output) => {
                            tool_summary.record_result(output.is_error);
                            output.text
                        }
                        Err(error) => {
                            tool_summary.record_transport_failure();
                            let error_text = format!("tool `{name}` call failed: {error}");
                            let outcome = self
                                .update_recall_feedback(
                                    session_id,
                                    user_message,
                                    &error_text,
                                    Some(&tool_summary),
                                )
                                .await;
                            self.apply_memory_recall_credit(
                                session_id,
                                &recall_credit_candidates,
                                outcome,
                            );
                            self.reflect_turn_and_update_policy_hint(
                                session_id,
                                turn_id,
                                decision.route,
                                user_message,
                                &error_text,
                                "error",
                                total_tool_calls_this_turn,
                            )
                            .await;
                            return Err(error);
                        }
                    };
                    messages.push(ChatMessage {
                        role: "tool".to_string(),
                        content: Some(result),
                        tool_calls: None,
                        tool_call_id: Some(tc.id.clone()),
                        name: Some(name),
                    });
                }
                continue;
            }

            let out = resp.content.unwrap_or_default();
            let outcome = self
                .update_recall_feedback(session_id, user_message, &out, Some(&tool_summary))
                .await;
            self.apply_memory_recall_credit(session_id, &recall_credit_candidates, outcome);
            self.append_turn_to_session(session_id, user_message, &out, total_tool_calls_this_turn)
                .await?;
            self.reflect_turn_and_update_policy_hint(
                session_id,
                turn_id,
                decision.route,
                user_message,
                &out,
                "completed",
                total_tool_calls_this_turn,
            )
            .await;
            return Ok(out);
        }
    }

    /// Clear session history for a session.
    pub async fn clear_session(&self, session_id: &str) -> Result<()> {
        if let Some(ref w) = self.bounded_session {
            w.clear(session_id).await?;
        }
        self.memory_recall_feedback.write().await.remove(session_id);
        self.reflection_policy_hints
            .write()
            .await
            .remove(session_id);
        self.clear_memory_recall_feedback_bias(session_id).await;
        let _ = self.clear_session_system_prompt_injection(session_id).await;
        self.session.clear(session_id).await
    }

    /// Apply explicit recall feedback for a session.
    ///
    /// Returns `None` when memory is disabled.
    pub async fn apply_session_recall_feedback(
        &self,
        session_id: &str,
        direction: SessionRecallFeedbackDirection,
    ) -> Option<SessionRecallFeedbackUpdate> {
        if self.memory_store.is_none() {
            return None;
        }
        let outcome = match direction {
            SessionRecallFeedbackDirection::Up => RecallOutcome::Success,
            SessionRecallFeedbackDirection::Down => RecallOutcome::Failure,
        };
        let (previous, updated) = self
            .apply_recall_feedback_outcome(
                session_id,
                outcome,
                RECALL_FEEDBACK_SOURCE_COMMAND,
                None,
            )
            .await;
        Some(SessionRecallFeedbackUpdate {
            previous_bias: previous,
            updated_bias: updated,
            direction,
        })
    }

    async fn recall_feedback_bias(&self, session_id: &str) -> f32 {
        if let Some(bias) = self
            .memory_recall_feedback
            .read()
            .await
            .get(session_id)
            .copied()
        {
            return bias;
        }
        if let Some(bias) = self.load_memory_recall_feedback_bias(session_id).await {
            self.memory_recall_feedback
                .write()
                .await
                .insert(session_id.to_string(), bias);
            return bias;
        }
        0.0
    }

    async fn update_recall_feedback(
        &self,
        session_id: &str,
        user_message: &str,
        assistant_message: &str,
        tool_summary: Option<&ToolExecutionSummary>,
    ) -> Option<RecallOutcome> {
        if self.memory_store.is_none() {
            return None;
        }
        let (outcome, source) =
            resolve_feedback_outcome(user_message, tool_summary, assistant_message);
        self.apply_recall_feedback_outcome(session_id, outcome, source, tool_summary)
            .await;
        Some(outcome)
    }

    fn apply_memory_recall_credit(
        &self,
        session_id: &str,
        candidates: &[RecalledEpisodeCandidate],
        outcome: Option<RecallOutcome>,
    ) {
        let Some(store) = self.memory_store.as_ref() else {
            return;
        };
        let Some(outcome) = outcome else {
            return;
        };
        if candidates.is_empty() {
            return;
        }
        let updates = apply_recall_credit(store, candidates, outcome);
        if updates.is_empty() {
            return;
        }
        let total_delta: f32 = updates.iter().map(|u| u.updated_q - u.previous_q).sum();
        let avg_weight = updates.iter().map(|u| u.weight).sum::<f32>() / updates.len() as f32;
        tracing::debug!(
            event = SessionEvent::MemoryRecallCreditApplied.as_str(),
            session_id,
            outcome = outcome.as_str(),
            candidates = candidates.len(),
            applied = updates.len(),
            avg_weight,
            total_q_delta = total_delta,
            "memory recall credit applied"
        );
    }

    async fn apply_recall_feedback_outcome(
        &self,
        session_id: &str,
        outcome: RecallOutcome,
        source: &str,
        tool_summary: Option<&ToolExecutionSummary>,
    ) -> (f32, f32) {
        let previous = self.recall_feedback_bias(session_id).await;
        let updated = update_feedback_bias(previous, outcome);
        self.memory_recall_feedback
            .write()
            .await
            .insert(session_id.to_string(), updated);
        self.persist_memory_recall_feedback_bias(session_id, updated)
            .await;
        tracing::debug!(
            event = SessionEvent::MemoryRecallFeedbackUpdated.as_str(),
            session_id,
            outcome = outcome.as_str(),
            feedback_source = source,
            tool_attempted = tool_summary.map_or(0, |summary| summary.attempted),
            tool_succeeded = tool_summary.map_or(0, |summary| summary.succeeded),
            tool_failed = tool_summary.map_or(0, |summary| summary.failed),
            recall_feedback_bias_before = previous,
            recall_feedback_bias_after = updated,
            "memory recall feedback updated"
        );
        (previous, updated)
    }
}

impl Drop for Agent {
    fn drop(&mut self) {
        if let Some(task) = self.memory_stream_consumer_task.take() {
            task.abort();
        }
    }
}
