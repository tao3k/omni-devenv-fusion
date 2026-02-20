use xiuxian_qianhuan::{PromptContextBlock, PromptContextCategory, PromptContextSource};

use crate::session::ChatMessage;

use super::super::context_budget::SESSION_SUMMARY_MESSAGE_NAME;
use super::super::memory_recall::MEMORY_RECALL_MESSAGE_NAME;
use super::super::system_prompt_injection_state::SYSTEM_PROMPT_INJECTION_CONTEXT_MESSAGE_NAME;

#[derive(Debug, Clone)]
pub(super) struct ExtractionResult {
    pub blocks: Vec<PromptContextBlock>,
    pub passthrough_messages: Vec<ChatMessage>,
}

pub(super) fn extract_blocks(
    session_id: &str,
    turn_id: u64,
    messages: Vec<ChatMessage>,
) -> ExtractionResult {
    let mut blocks = Vec::new();
    let mut passthrough_messages = Vec::new();

    for message in messages {
        let Some((source, category, priority, source_key)) = classify_message(&message) else {
            passthrough_messages.push(message);
            continue;
        };

        let Some(payload) = message.content.clone() else {
            passthrough_messages.push(message);
            continue;
        };

        if payload.trim().is_empty() {
            passthrough_messages.push(message);
            continue;
        }

        let block_id = format!(
            "{session_id}:turn-{turn_id}:{}:{source_key}",
            blocks.len().saturating_add(1)
        );
        blocks.push(PromptContextBlock::new(
            block_id, source, category, priority, session_id, payload, false,
        ));
    }

    ExtractionResult {
        blocks,
        passthrough_messages,
    }
}

pub(super) fn message_name_for_category(category: PromptContextCategory) -> &'static str {
    match category {
        PromptContextCategory::MemoryRecall => MEMORY_RECALL_MESSAGE_NAME,
        PromptContextCategory::SessionXml => SYSTEM_PROMPT_INJECTION_CONTEXT_MESSAGE_NAME,
        PromptContextCategory::WindowSummary => SESSION_SUMMARY_MESSAGE_NAME,
        _ => "agent.injection.context",
    }
}

fn classify_message(
    message: &ChatMessage,
) -> Option<(
    PromptContextSource,
    PromptContextCategory,
    u16,
    &'static str,
)> {
    if message.role != "system" {
        return None;
    }
    let name = message.name.as_deref()?;
    match name {
        MEMORY_RECALL_MESSAGE_NAME => Some((
            PromptContextSource::MemoryRecall,
            PromptContextCategory::MemoryRecall,
            900,
            "memory_recall",
        )),
        SYSTEM_PROMPT_INJECTION_CONTEXT_MESSAGE_NAME => Some((
            PromptContextSource::SessionXml,
            PromptContextCategory::SessionXml,
            960,
            "session_xml",
        )),
        SESSION_SUMMARY_MESSAGE_NAME => Some((
            PromptContextSource::WindowSummary,
            PromptContextCategory::WindowSummary,
            780,
            "window_summary",
        )),
        _ => None,
    }
}
