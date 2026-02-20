use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use xiuxian_qianhuan::{InjectionWindowConfig, SystemPromptInjectionWindow};

use super::Agent;
use crate::session::ChatMessage;

const SYSTEM_PROMPT_INJECTION_SESSION_PREFIX: &str = "__session_system_prompt_injection__:";
const SYSTEM_PROMPT_INJECTION_STORAGE_MESSAGE_NAME: &str = "agent.system_prompt.injection";
pub(super) const SYSTEM_PROMPT_INJECTION_CONTEXT_MESSAGE_NAME: &str =
    "agent.system_prompt.injection.context";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionSystemPromptInjectionSnapshot {
    pub updated_at_unix_ms: u64,
    pub qa_count: usize,
    pub xml: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct StoredSessionSystemPromptInjection {
    updated_at_unix_ms: u64,
    qa_count: usize,
    xml: String,
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

fn storage_session_id(session_id: &str) -> String {
    format!("{SYSTEM_PROMPT_INJECTION_SESSION_PREFIX}{session_id}")
}

fn snapshot_to_message(snapshot: &SessionSystemPromptInjectionSnapshot) -> Option<ChatMessage> {
    let payload = serde_json::to_string(&StoredSessionSystemPromptInjection {
        updated_at_unix_ms: snapshot.updated_at_unix_ms,
        qa_count: snapshot.qa_count,
        xml: snapshot.xml.clone(),
    })
    .ok()?;
    Some(ChatMessage {
        role: "system".to_string(),
        content: Some(payload),
        tool_calls: None,
        tool_call_id: None,
        name: Some(SYSTEM_PROMPT_INJECTION_STORAGE_MESSAGE_NAME.to_string()),
    })
}

fn message_to_snapshot(message: &ChatMessage) -> Option<SessionSystemPromptInjectionSnapshot> {
    if let Some(name) = message.name.as_deref()
        && name != SYSTEM_PROMPT_INJECTION_STORAGE_MESSAGE_NAME
    {
        return None;
    }
    let payload = message.content.as_deref()?;
    let stored: StoredSessionSystemPromptInjection = serde_json::from_str(payload).ok()?;
    Some(SessionSystemPromptInjectionSnapshot {
        updated_at_unix_ms: stored.updated_at_unix_ms,
        qa_count: stored.qa_count,
        xml: stored.xml,
    })
}

fn validate_and_normalize_xml(raw_xml: &str) -> Result<SessionSystemPromptInjectionSnapshot> {
    let window = SystemPromptInjectionWindow::from_xml(raw_xml, InjectionWindowConfig::default())
        .context("invalid system prompt injection xml payload")?;
    let xml = window.render_xml();
    Ok(SessionSystemPromptInjectionSnapshot {
        updated_at_unix_ms: now_unix_ms(),
        qa_count: window.len(),
        xml,
    })
}

impl Agent {
    pub async fn upsert_session_system_prompt_injection_xml(
        &self,
        session_id: &str,
        raw_xml: &str,
    ) -> Result<SessionSystemPromptInjectionSnapshot> {
        let snapshot = validate_and_normalize_xml(raw_xml)?;
        let Some(message) = snapshot_to_message(&snapshot) else {
            anyhow::bail!("failed to serialize system prompt injection payload");
        };
        let storage_id = storage_session_id(session_id);
        self.session
            .replace(&storage_id, vec![message])
            .await
            .with_context(|| {
                format!("failed to persist system prompt injection payload: {storage_id}")
            })?;

        self.system_prompt_injection
            .write()
            .await
            .insert(session_id.to_string(), snapshot.clone());

        if let Err(error) = self
            .session
            .publish_stream_event(
                self.memory_stream_name(),
                vec![
                    (
                        "kind".to_string(),
                        "system_prompt_injection_updated".to_string(),
                    ),
                    ("session_id".to_string(), session_id.to_string()),
                    ("storage_session_id".to_string(), storage_id),
                    ("qa_count".to_string(), snapshot.qa_count.to_string()),
                    (
                        "updated_at_unix_ms".to_string(),
                        snapshot.updated_at_unix_ms.to_string(),
                    ),
                ],
            )
            .await
        {
            tracing::warn!(
                session_id,
                error = %error,
                "failed to publish system prompt injection update stream event"
            );
        }

        Ok(snapshot)
    }

    pub async fn inspect_session_system_prompt_injection(
        &self,
        session_id: &str,
    ) -> Option<SessionSystemPromptInjectionSnapshot> {
        if let Some(snapshot) = self
            .system_prompt_injection
            .read()
            .await
            .get(session_id)
            .cloned()
        {
            return Some(snapshot);
        }

        let storage_id = storage_session_id(session_id);
        let messages = match self.session.get(&storage_id).await {
            Ok(messages) => messages,
            Err(error) => {
                tracing::warn!(
                    session_id,
                    storage_session_id = storage_id,
                    error = %error,
                    "failed to load system prompt injection payload"
                );
                return None;
            }
        };
        let snapshot = messages.iter().rev().find_map(message_to_snapshot);
        if snapshot.is_none() && !messages.is_empty() {
            tracing::warn!(
                session_id,
                storage_session_id = storage_id,
                persisted_messages = messages.len(),
                "failed to parse persisted system prompt injection payload"
            );
        }
        if let Some(value) = snapshot.clone() {
            self.system_prompt_injection
                .write()
                .await
                .insert(session_id.to_string(), value);
        }
        snapshot
    }

    pub async fn clear_session_system_prompt_injection(&self, session_id: &str) -> Result<bool> {
        let removed_cache = self
            .system_prompt_injection
            .write()
            .await
            .remove(session_id)
            .is_some();
        let storage_id = storage_session_id(session_id);
        let existed_storage = self
            .session
            .get(&storage_id)
            .await
            .map(|messages| !messages.is_empty())
            .unwrap_or(false);
        self.session.clear(&storage_id).await.with_context(|| {
            format!("failed to clear system prompt injection payload: {storage_id}")
        })?;
        if let Err(error) = self
            .session
            .publish_stream_event(
                self.memory_stream_name(),
                vec![
                    (
                        "kind".to_string(),
                        "system_prompt_injection_cleared".to_string(),
                    ),
                    ("session_id".to_string(), session_id.to_string()),
                    ("storage_session_id".to_string(), storage_id),
                ],
            )
            .await
        {
            tracing::warn!(
                session_id,
                error = %error,
                "failed to publish system prompt injection clear stream event"
            );
        }
        Ok(removed_cache || existed_storage)
    }
}
