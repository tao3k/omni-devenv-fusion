use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use super::Agent;
use crate::session::ChatMessage;

const MEMORY_RECALL_FEEDBACK_SESSION_PREFIX: &str = "__session_memory_recall_feedback__:";
const MEMORY_RECALL_FEEDBACK_MESSAGE_NAME: &str = "agent.memory.recall.feedback";

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
struct StoredMemoryRecallFeedback {
    bias: f32,
    updated_at_unix_ms: u64,
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

fn normalize_bias(value: f32) -> f32 {
    if value.is_finite() {
        value.clamp(-1.0, 1.0)
    } else {
        0.0
    }
}

fn feedback_storage_session_id(session_id: &str) -> String {
    format!("{MEMORY_RECALL_FEEDBACK_SESSION_PREFIX}{session_id}")
}

fn build_feedback_payload(bias: f32) -> StoredMemoryRecallFeedback {
    StoredMemoryRecallFeedback {
        bias: normalize_bias(bias),
        updated_at_unix_ms: now_unix_ms(),
    }
}

fn feedback_chat_message(stored: &StoredMemoryRecallFeedback) -> Option<ChatMessage> {
    let payload = serde_json::to_string(stored).ok()?;
    Some(ChatMessage {
        role: "system".to_string(),
        content: Some(payload),
        tool_calls: None,
        tool_call_id: None,
        name: Some(MEMORY_RECALL_FEEDBACK_MESSAGE_NAME.to_string()),
    })
}

fn parse_feedback_chat_message(message: &ChatMessage) -> Option<f32> {
    if let Some(name) = message.name.as_deref()
        && name != MEMORY_RECALL_FEEDBACK_MESSAGE_NAME
    {
        return None;
    }
    let payload = message.content.as_deref()?;
    let stored: StoredMemoryRecallFeedback = serde_json::from_str(payload).ok()?;
    Some(normalize_bias(stored.bias))
}

impl Agent {
    pub(super) async fn persist_memory_recall_feedback_bias(&self, session_id: &str, bias: f32) {
        let stored_feedback = build_feedback_payload(bias);
        let Some(message) = feedback_chat_message(&stored_feedback) else {
            tracing::warn!(
                session_id,
                "failed to serialize memory recall feedback payload"
            );
            return;
        };
        let storage_session_id = feedback_storage_session_id(session_id);
        if let Err(error) = self
            .session
            .replace(&storage_session_id, vec![message])
            .await
        {
            tracing::warn!(
                session_id,
                storage_session_id,
                error = %error,
                "failed to persist memory recall feedback payload"
            );
            return;
        }
        if let Err(error) = self
            .session
            .publish_stream_event(
                self.memory_stream_name(),
                vec![
                    (
                        "kind".to_string(),
                        "recall_feedback_bias_updated".to_string(),
                    ),
                    ("session_id".to_string(), session_id.to_string()),
                    ("storage_session_id".to_string(), storage_session_id),
                    (
                        "bias".to_string(),
                        format!("{:.6}", normalize_bias(stored_feedback.bias)),
                    ),
                    (
                        "updated_at_unix_ms".to_string(),
                        stored_feedback.updated_at_unix_ms.to_string(),
                    ),
                ],
            )
            .await
        {
            tracing::warn!(
                session_id,
                error = %error,
                "failed to publish memory recall feedback stream event"
            );
        }
    }

    pub(super) async fn load_memory_recall_feedback_bias(&self, session_id: &str) -> Option<f32> {
        let storage_session_id = feedback_storage_session_id(session_id);
        let messages = match self.session.get(&storage_session_id).await {
            Ok(messages) => messages,
            Err(error) => {
                tracing::warn!(
                    session_id,
                    storage_session_id,
                    error = %error,
                    "failed to load memory recall feedback payload"
                );
                return None;
            }
        };
        messages
            .iter()
            .rev()
            .find_map(parse_feedback_chat_message)
            .map(normalize_bias)
    }

    pub(super) async fn clear_memory_recall_feedback_bias(&self, session_id: &str) {
        let storage_session_id = feedback_storage_session_id(session_id);
        if let Err(error) = self.session.clear(&storage_session_id).await {
            tracing::warn!(
                session_id,
                storage_session_id,
                error = %error,
                "failed to clear persisted memory recall feedback payload"
            );
        }
    }
}

#[cfg(test)]
#[path = "../../tests/agent/memory_recall_feedback_state.rs"]
mod tests;
