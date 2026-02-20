mod assembler;
mod builder;
mod render;
#[cfg(test)]
mod tests;

use anyhow::{Context, Result};
use xiuxian_qianhuan::{InjectionPolicy, InjectionSnapshot};

use crate::contracts::OmegaDecision;
use crate::session::ChatMessage;
use crate::shortcuts::WorkflowBridgeMode;

pub(super) struct InjectionNormalizationResult {
    pub(super) snapshot: Option<InjectionSnapshot>,
    pub(super) messages: Vec<ChatMessage>,
}

pub(super) fn normalize_messages_with_snapshot(
    session_id: &str,
    turn_id: u64,
    messages: Vec<ChatMessage>,
    policy: InjectionPolicy,
) -> Result<InjectionNormalizationResult> {
    let extraction = builder::extract_blocks(session_id, turn_id, messages);
    if extraction.blocks.is_empty() {
        return Ok(InjectionNormalizationResult {
            snapshot: None,
            messages: extraction.passthrough_messages,
        });
    }

    let snapshot = assembler::assemble_snapshot(session_id, turn_id, policy, extraction.blocks);
    snapshot
        .validate()
        .map_err(anyhow::Error::msg)
        .context("invalid typed injection snapshot")?;

    let mut merged_messages = render::render_snapshot_messages(&snapshot);
    merged_messages.extend(extraction.passthrough_messages);

    Ok(InjectionNormalizationResult {
        snapshot: Some(snapshot),
        messages: merged_messages,
    })
}

pub(super) fn build_snapshot_from_messages(
    session_id: &str,
    turn_id: u64,
    messages: Vec<ChatMessage>,
    policy: InjectionPolicy,
) -> Result<InjectionSnapshot> {
    let extraction = builder::extract_blocks(session_id, turn_id, messages);
    let snapshot = assembler::assemble_snapshot(session_id, turn_id, policy, extraction.blocks);
    snapshot
        .validate()
        .map_err(anyhow::Error::msg)
        .context("invalid typed injection snapshot")?;
    Ok(snapshot)
}

pub(super) fn augment_shortcut_arguments(
    arguments: Option<serde_json::Value>,
    snapshot: Option<&InjectionSnapshot>,
    decision: &OmegaDecision,
    workflow_mode: WorkflowBridgeMode,
) -> Option<serde_json::Value> {
    let mut payload = match arguments {
        Some(serde_json::Value::Object(map)) => map,
        Some(other) => {
            let mut map = serde_json::Map::new();
            map.insert("input".to_string(), other);
            map
        }
        None => serde_json::Map::new(),
    };

    let mut omni_meta = match payload.remove("_omni") {
        Some(serde_json::Value::Object(existing)) => existing,
        _ => serde_json::Map::new(),
    };

    omni_meta.insert(
        "workflow_mode".to_string(),
        serde_json::Value::String(workflow_mode.as_str().to_string()),
    );
    let decision_json = serde_json::to_value(decision).unwrap_or_else(|_| serde_json::json!({}));
    omni_meta.insert("omega_decision".to_string(), decision_json);

    if let Some(snapshot) = snapshot {
        let role_mix_profile_id = snapshot
            .role_mix
            .as_ref()
            .map(|profile| profile.profile_id.clone());
        let role_mix_roles = snapshot.role_mix.as_ref().map_or_else(Vec::new, |profile| {
            profile
                .roles
                .iter()
                .map(|role| role.role.clone())
                .collect::<Vec<_>>()
        });
        omni_meta.insert(
            "session_context".to_string(),
            serde_json::json!({
                "snapshot_id": snapshot.snapshot_id.as_str(),
                "turn_id": snapshot.turn_id,
                "block_count": snapshot.blocks.len(),
                "total_chars": snapshot.total_chars,
                "dropped_block_ids": snapshot.dropped_block_ids.clone(),
                "truncated_block_ids": snapshot.truncated_block_ids.clone(),
                "role_mix_profile_id": role_mix_profile_id,
                "role_mix_roles": role_mix_roles,
            }),
        );
    }

    payload.insert("_omni".to_string(), serde_json::Value::Object(omni_meta));
    Some(serde_json::Value::Object(payload))
}
