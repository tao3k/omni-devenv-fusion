use serde::{Deserialize, Serialize};

/// Source domain that produced a context block.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PromptContextSource {
    /// Retrieved from short-term memory recall.
    MemoryRecall,
    /// From session-level XML/system prompt injection history.
    SessionXml,
    /// Condensed summary from context window manager.
    WindowSummary,
    /// Retrieved from durable knowledge.
    Knowledge,
    /// Reflection artifacts from previous turns.
    Reflection,
    /// Runtime-generated execution hints.
    RuntimeHint,
    /// Governance/policy directives.
    Policy,
}

/// Category used by policy-level budget and ordering rules.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PromptContextCategory {
    /// Safety-critical guidance.
    Safety,
    /// Governance/policy guidance.
    Policy,
    /// Memory recall content.
    MemoryRecall,
    /// Session XML content.
    SessionXml,
    /// Window summary content.
    WindowSummary,
    /// Durable knowledge content.
    Knowledge,
    /// Reflection content.
    Reflection,
    /// Runtime hint content.
    RuntimeHint,
}

/// Immutable context block in a typed injection snapshot.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PromptContextBlock {
    /// Stable identifier for audit/replay.
    pub block_id: String,
    /// Producer source.
    pub source: PromptContextSource,
    /// Policy category.
    pub category: PromptContextCategory,
    /// Higher value means higher priority.
    pub priority: u16,
    /// Scope identifier, usually a session key.
    pub session_scope: String,
    /// Rendered payload text/XML.
    pub payload: String,
    /// Character count of payload at snapshot time.
    pub payload_chars: usize,
    /// Whether this block is non-evictable.
    pub anchor: bool,
}

impl PromptContextBlock {
    /// Construct a block and compute `payload_chars` from payload text.
    #[must_use]
    pub fn new(
        block_id: impl Into<String>,
        source: PromptContextSource,
        category: PromptContextCategory,
        priority: u16,
        session_scope: impl Into<String>,
        payload: impl Into<String>,
        anchor: bool,
    ) -> Self {
        let payload = payload.into();
        Self {
            block_id: block_id.into(),
            source,
            category,
            priority,
            session_scope: session_scope.into(),
            payload_chars: payload.chars().count(),
            payload,
            anchor,
        }
    }
}
