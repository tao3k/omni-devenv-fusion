use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use super::Agent;
use super::memory_recall::MemoryRecallPlan;
use crate::session::ChatMessage;

const MEMORY_RECALL_SNAPSHOT_SESSION_PREFIX: &str = "__session_memory_recall__:";
const MEMORY_RECALL_SNAPSHOT_MESSAGE_NAME: &str = "agent.memory.recall.snapshot";
const EMBEDDING_SOURCE_EMBEDDING: &str = "embedding";
const EMBEDDING_SOURCE_EMBEDDING_REPAIRED: &str = "embedding_repaired";
const EMBEDDING_SOURCE_HASH: &str = "hash";
const EMBEDDING_SOURCE_UNKNOWN: &str = "unknown";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SessionMemoryRecallDecision {
    Injected,
    Skipped,
}

impl SessionMemoryRecallDecision {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Injected => "injected",
            Self::Skipped => "skipped",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SessionMemoryRecallSnapshot {
    pub created_at_unix_ms: u64,
    pub query_tokens: usize,
    pub recall_feedback_bias: f32,
    pub embedding_source: &'static str,
    pub k1: usize,
    pub k2: usize,
    pub lambda: f32,
    pub min_score: f32,
    pub max_context_chars: usize,
    pub budget_pressure: f32,
    pub window_pressure: f32,
    pub effective_budget_tokens: Option<usize>,
    pub active_turns_estimate: usize,
    pub summary_segment_count: usize,
    pub recalled_total: usize,
    pub recalled_selected: usize,
    pub recalled_injected: usize,
    pub context_chars_injected: usize,
    pub best_score: Option<f32>,
    pub weakest_score: Option<f32>,
    pub pipeline_duration_ms: u64,
    pub decision: SessionMemoryRecallDecision,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StoredSessionMemoryRecallSnapshot {
    created_at_unix_ms: u64,
    query_tokens: usize,
    #[serde(default)]
    recall_feedback_bias: f32,
    embedding_source: String,
    k1: usize,
    k2: usize,
    lambda: f32,
    min_score: f32,
    max_context_chars: usize,
    budget_pressure: f32,
    window_pressure: f32,
    effective_budget_tokens: Option<usize>,
    active_turns_estimate: usize,
    summary_segment_count: usize,
    recalled_total: usize,
    recalled_selected: usize,
    recalled_injected: usize,
    context_chars_injected: usize,
    best_score: Option<f32>,
    weakest_score: Option<f32>,
    pipeline_duration_ms: u64,
    decision: SessionMemoryRecallDecision,
}

impl SessionMemoryRecallSnapshot {
    pub(crate) fn from_plan(
        plan: MemoryRecallPlan,
        active_turns_estimate: usize,
        summary_segment_count: usize,
        query_tokens: usize,
        recall_feedback_bias: f32,
        embedding_source: &'static str,
        recalled_total: usize,
        recalled_selected: usize,
        recalled_injected: usize,
        context_chars_injected: usize,
        best_score: Option<f32>,
        weakest_score: Option<f32>,
        pipeline_duration_ms: u64,
        decision: SessionMemoryRecallDecision,
    ) -> Self {
        Self {
            created_at_unix_ms: now_unix_ms(),
            query_tokens,
            recall_feedback_bias,
            embedding_source,
            k1: plan.k1,
            k2: plan.k2,
            lambda: plan.lambda,
            min_score: plan.min_score,
            max_context_chars: plan.max_context_chars,
            budget_pressure: plan.budget_pressure,
            window_pressure: plan.window_pressure,
            effective_budget_tokens: plan.effective_budget_tokens,
            active_turns_estimate,
            summary_segment_count,
            recalled_total,
            recalled_selected,
            recalled_injected,
            context_chars_injected,
            best_score,
            weakest_score,
            pipeline_duration_ms,
            decision,
        }
    }
}

impl From<SessionMemoryRecallSnapshot> for StoredSessionMemoryRecallSnapshot {
    fn from(snapshot: SessionMemoryRecallSnapshot) -> Self {
        Self {
            created_at_unix_ms: snapshot.created_at_unix_ms,
            query_tokens: snapshot.query_tokens,
            recall_feedback_bias: snapshot.recall_feedback_bias,
            embedding_source: snapshot.embedding_source.to_string(),
            k1: snapshot.k1,
            k2: snapshot.k2,
            lambda: snapshot.lambda,
            min_score: snapshot.min_score,
            max_context_chars: snapshot.max_context_chars,
            budget_pressure: snapshot.budget_pressure,
            window_pressure: snapshot.window_pressure,
            effective_budget_tokens: snapshot.effective_budget_tokens,
            active_turns_estimate: snapshot.active_turns_estimate,
            summary_segment_count: snapshot.summary_segment_count,
            recalled_total: snapshot.recalled_total,
            recalled_selected: snapshot.recalled_selected,
            recalled_injected: snapshot.recalled_injected,
            context_chars_injected: snapshot.context_chars_injected,
            best_score: snapshot.best_score,
            weakest_score: snapshot.weakest_score,
            pipeline_duration_ms: snapshot.pipeline_duration_ms,
            decision: snapshot.decision,
        }
    }
}

impl StoredSessionMemoryRecallSnapshot {
    fn into_runtime(self) -> SessionMemoryRecallSnapshot {
        SessionMemoryRecallSnapshot {
            created_at_unix_ms: self.created_at_unix_ms,
            query_tokens: self.query_tokens,
            recall_feedback_bias: self.recall_feedback_bias,
            embedding_source: normalize_embedding_source(&self.embedding_source),
            k1: self.k1,
            k2: self.k2,
            lambda: self.lambda,
            min_score: self.min_score,
            max_context_chars: self.max_context_chars,
            budget_pressure: self.budget_pressure,
            window_pressure: self.window_pressure,
            effective_budget_tokens: self.effective_budget_tokens,
            active_turns_estimate: self.active_turns_estimate,
            summary_segment_count: self.summary_segment_count,
            recalled_total: self.recalled_total,
            recalled_selected: self.recalled_selected,
            recalled_injected: self.recalled_injected,
            context_chars_injected: self.context_chars_injected,
            best_score: self.best_score,
            weakest_score: self.weakest_score,
            pipeline_duration_ms: self.pipeline_duration_ms,
            decision: self.decision,
        }
    }
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

fn snapshot_session_id(session_id: &str) -> String {
    format!("{MEMORY_RECALL_SNAPSHOT_SESSION_PREFIX}{session_id}")
}

fn normalize_embedding_source(value: &str) -> &'static str {
    match value {
        EMBEDDING_SOURCE_EMBEDDING => EMBEDDING_SOURCE_EMBEDDING,
        EMBEDDING_SOURCE_EMBEDDING_REPAIRED => EMBEDDING_SOURCE_EMBEDDING_REPAIRED,
        EMBEDDING_SOURCE_HASH => EMBEDDING_SOURCE_HASH,
        _ => EMBEDDING_SOURCE_UNKNOWN,
    }
}

fn snapshot_chat_message(snapshot: &SessionMemoryRecallSnapshot) -> Option<ChatMessage> {
    let payload =
        serde_json::to_string(&StoredSessionMemoryRecallSnapshot::from(*snapshot)).ok()?;
    Some(ChatMessage {
        role: "system".to_string(),
        content: Some(payload),
        tool_calls: None,
        tool_call_id: None,
        name: Some(MEMORY_RECALL_SNAPSHOT_MESSAGE_NAME.to_string()),
    })
}

fn parse_snapshot_chat_message(message: &ChatMessage) -> Option<SessionMemoryRecallSnapshot> {
    if let Some(name) = message.name.as_deref()
        && name != MEMORY_RECALL_SNAPSHOT_MESSAGE_NAME
    {
        return None;
    }
    let payload = message.content.as_deref()?;
    let stored: StoredSessionMemoryRecallSnapshot = serde_json::from_str(payload).ok()?;
    Some(stored.into_runtime())
}

impl Agent {
    pub(crate) async fn record_memory_recall_snapshot(
        &self,
        session_id: &str,
        snapshot: SessionMemoryRecallSnapshot,
    ) {
        let Some(message) = snapshot_chat_message(&snapshot) else {
            tracing::warn!(
                session_id,
                "failed to serialize memory recall snapshot payload"
            );
            return;
        };

        let storage_session_id = snapshot_session_id(session_id);
        if let Err(error) = self
            .session
            .replace(&storage_session_id, vec![message])
            .await
        {
            tracing::warn!(
                session_id,
                storage_session_id,
                error = %error,
                "failed to persist memory recall snapshot payload"
            );
            return;
        }
        if let Err(error) = self
            .session
            .publish_stream_event(
                self.memory_stream_name(),
                vec![
                    ("kind".to_string(), "recall_snapshot_updated".to_string()),
                    ("session_id".to_string(), session_id.to_string()),
                    ("storage_session_id".to_string(), storage_session_id.clone()),
                    (
                        "decision".to_string(),
                        snapshot.decision.as_str().to_string(),
                    ),
                    (
                        "recalled_selected".to_string(),
                        snapshot.recalled_selected.to_string(),
                    ),
                    (
                        "recalled_injected".to_string(),
                        snapshot.recalled_injected.to_string(),
                    ),
                    (
                        "pipeline_duration_ms".to_string(),
                        snapshot.pipeline_duration_ms.to_string(),
                    ),
                    (
                        "captured_at_unix_ms".to_string(),
                        snapshot.created_at_unix_ms.to_string(),
                    ),
                ],
            )
            .await
        {
            tracing::warn!(
                session_id,
                error = %error,
                "failed to publish memory recall snapshot stream event"
            );
        }
        tracing::debug!(
            session_id,
            storage_session_id,
            "memory recall snapshot persisted"
        );
    }

    pub async fn inspect_memory_recall_snapshot(
        &self,
        session_id: &str,
    ) -> Option<SessionMemoryRecallSnapshot> {
        let storage_session_id = snapshot_session_id(session_id);
        let messages = match self.session.get(&storage_session_id).await {
            Ok(messages) => messages,
            Err(error) => {
                tracing::warn!(
                    session_id,
                    storage_session_id,
                    error = %error,
                    "failed to load memory recall snapshot payload"
                );
                return None;
            }
        };

        let snapshot = messages.iter().rev().find_map(parse_snapshot_chat_message);
        if snapshot.is_none() && !messages.is_empty() {
            tracing::warn!(
                session_id,
                storage_session_id,
                persisted_messages = messages.len(),
                "failed to parse persisted memory recall snapshot payload"
            );
        }
        snapshot
    }
}

#[cfg(test)]
#[path = "../../tests/agent/memory_recall_state.rs"]
mod tests;
