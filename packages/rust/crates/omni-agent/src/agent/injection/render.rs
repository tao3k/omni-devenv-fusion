use xiuxian_qianhuan::InjectionSnapshot;

use crate::session::ChatMessage;

use super::builder::message_name_for_category;

pub(super) fn render_snapshot_messages(snapshot: &InjectionSnapshot) -> Vec<ChatMessage> {
    snapshot
        .blocks
        .iter()
        .map(|block| ChatMessage {
            role: "system".to_string(),
            content: Some(block.payload.clone()),
            tool_calls: None,
            tool_call_id: None,
            name: Some(message_name_for_category(block.category).to_string()),
        })
        .collect()
}
