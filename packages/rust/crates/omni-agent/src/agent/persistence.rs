use anyhow::Result;
use omni_memory::{
    Episode, EpisodeStore, MemoryGateEvent, MemoryGatePolicy, MemoryGateVerdict,
    MemoryUtilityLedger,
};
use std::sync::Arc;
use std::sync::atomic::Ordering;
use std::time::Instant;

use crate::observability::SessionEvent;
use crate::session::{ChatMessage, SessionSummarySegment};

use super::Agent;
use super::consolidation::{build_consolidated_summary_text, now_unix_ms, summarise_drained_turns};
use super::memory::{sanitize_decay_factor, should_apply_decay};
use super::memory_recall_feedback::classify_assistant_outcome;
use super::memory_state::MemoryStateBackend;

fn persist_memory_state(
    backend: Option<&Arc<MemoryStateBackend>>,
    store: &EpisodeStore,
    session_id: &str,
    reason: &str,
) {
    let Some(backend) = backend else {
        return;
    };
    let started = Instant::now();
    match backend.save(store) {
        Ok(()) => {
            tracing::debug!(
                event = SessionEvent::MemoryStateSaveSucceeded.as_str(),
                backend = backend.backend_name(),
                session_id,
                reason,
                episodes = store.len(),
                q_values = store.q_table.len(),
                duration_ms = started.elapsed().as_millis(),
                "memory state persisted"
            );
        }
        Err(error) => {
            tracing::warn!(
                event = SessionEvent::MemoryStateSaveFailed.as_str(),
                backend = backend.backend_name(),
                session_id,
                reason,
                duration_ms = started.elapsed().as_millis(),
                error = %error,
                "failed to persist memory state"
            );
        }
    }
}

impl Agent {
    fn memory_gate_policy(&self) -> MemoryGatePolicy {
        let mut policy = MemoryGatePolicy::default();
        let Some(memory_cfg) = self.config.memory.as_ref() else {
            return policy;
        };

        policy.promote_threshold = memory_cfg.gate_promote_threshold.clamp(0.0, 1.0);
        policy.obsolete_threshold = memory_cfg.gate_obsolete_threshold.clamp(0.0, 1.0);
        policy.promote_min_usage = memory_cfg.gate_promote_min_usage.max(1);
        policy.obsolete_min_usage = memory_cfg.gate_obsolete_min_usage.max(1);
        policy.promote_failure_rate_ceiling =
            memory_cfg.gate_promote_failure_rate_ceiling.clamp(0.0, 1.0);
        policy.obsolete_failure_rate_floor =
            memory_cfg.gate_obsolete_failure_rate_floor.clamp(0.0, 1.0);
        policy.promote_min_ttl_score = memory_cfg.gate_promote_min_ttl_score.clamp(0.0, 1.0);
        policy.obsolete_max_ttl_score = memory_cfg.gate_obsolete_max_ttl_score.clamp(0.0, 1.0);
        policy
    }

    pub(super) fn memory_stream_name(&self) -> &str {
        self.config
            .memory
            .as_ref()
            .map(|cfg| cfg.stream_name.trim())
            .filter(|value| !value.is_empty())
            .unwrap_or("memory.events")
    }

    async fn publish_memory_stream_event(&self, fields: Vec<(String, String)>) {
        if let Err(error) = self
            .session
            .publish_stream_event(self.memory_stream_name(), fields)
            .await
        {
            tracing::warn!(
                error = %error,
                "failed to publish memory stream event"
            );
        }
    }

    fn maybe_apply_memory_decay(&self, session_id: &str, store: &EpisodeStore) {
        let Some(memory_cfg) = self.config.memory.as_ref() else {
            return;
        };
        let turn_index = self
            .memory_decay_turn_counter
            .fetch_add(1, Ordering::Relaxed)
            .saturating_add(1);
        if !should_apply_decay(
            memory_cfg.decay_enabled,
            memory_cfg.decay_every_turns,
            turn_index,
        ) {
            return;
        }
        let decay_factor = sanitize_decay_factor(memory_cfg.decay_factor);
        let started = Instant::now();
        store.apply_decay(decay_factor);
        persist_memory_state(
            self.memory_state_backend.as_ref(),
            store,
            session_id,
            "decay",
        );
        tracing::debug!(
            event = SessionEvent::MemoryDecayApplied.as_str(),
            session_id,
            turn_index,
            decay_every_turns = memory_cfg.decay_every_turns,
            decay_factor,
            duration_ms = started.elapsed().as_millis(),
            "memory decay applied"
        );
    }

    pub(super) async fn append_turn_to_session(
        &self,
        session_id: &str,
        user_msg: &str,
        assistant_msg: &str,
        tool_count: u32,
    ) -> Result<()> {
        if let Some(ref w) = self.bounded_session {
            w.append_turn(session_id, user_msg, assistant_msg, tool_count)
                .await?;
            self.try_consolidate(session_id).await?;
            self.try_store_turn(session_id, user_msg, assistant_msg, tool_count)
                .await;
            return Ok(());
        }
        let user = ChatMessage {
            role: "user".to_string(),
            content: Some(user_msg.to_string()),
            tool_calls: None,
            tool_call_id: None,
            name: None,
        };
        let assistant = ChatMessage {
            role: "assistant".to_string(),
            content: Some(assistant_msg.to_string()),
            tool_calls: None,
            tool_call_id: None,
            name: None,
        };
        self.session
            .append(session_id, vec![user, assistant])
            .await?;
        self.try_store_turn(session_id, user_msg, assistant_msg, tool_count)
            .await;
        Ok(())
    }

    /// When memory is enabled, store the current turn as one episode (intent=user, experience=assistant, outcome=completed/error).
    async fn try_store_turn(
        &self,
        session_id: &str,
        user_msg: &str,
        assistant_msg: &str,
        tool_count: u32,
    ) {
        let Some(ref store) = self.memory_store else {
            return;
        };
        let outcome = classify_assistant_outcome(assistant_msg)
            .as_memory_label()
            .to_string();
        let reward = if outcome == "error" { 0.0 } else { 1.0 };
        let gate_policy = self.memory_gate_policy();
        let scope_key = Episode::normalize_scope(session_id);
        let normalized_intent = user_msg.trim();
        let existing_episode_id = store
            .get_all()
            .into_iter()
            .rev()
            .find(|episode| {
                episode.scope_key() == scope_key.as_str()
                    && episode.intent.trim() == normalized_intent
            })
            .map(|episode| episode.id);

        let (id, episode_source) = if let Some(existing_id) = existing_episode_id {
            (existing_id, "existing")
        } else {
            let expected_dim = self
                .config
                .memory
                .as_ref()
                .map_or_else(|| store.encoder().dimension(), |cfg| cfg.embedding_dim);
            let id = format!(
                "turn-{}-{}",
                session_id,
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis()
            );
            let embedding = self.embedding_or_hash(user_msg, store, expected_dim).await;
            let episode = Episode::new(
                id.clone(),
                user_msg.to_string(),
                embedding,
                assistant_msg.to_string(),
                outcome.clone(),
            );
            if let Err(error) = store.store_for_scope(session_id, episode) {
                tracing::warn!(
                    event = SessionEvent::MemoryTurnStoreFailed.as_str(),
                    session_id,
                    error = %error,
                    "failed to store memory episode for turn"
                );
                self.publish_memory_stream_event(vec![
                    ("kind".to_string(), "turn_store_failed".to_string()),
                    ("session_id".to_string(), session_id.to_string()),
                    ("error".to_string(), error.to_string()),
                ])
                .await;
                return;
            }
            (id, "new")
        };

        store.update_q(&id, reward);
        let _ = store.record_feedback(&id, reward > 0.0);

        if let Some(stored_episode) = store.get(&id) {
            let react_score = if reward > 0.0 {
                (0.72 + (tool_count.min(6) as f32 * 0.04)).clamp(0.0, 1.0)
            } else {
                (0.20 + (tool_count.min(6) as f32 * 0.01)).clamp(0.0, 1.0)
            };
            let graph_score = if tool_count > 0 { 0.64 } else { 0.45 };
            let omega_score = if reward > 0.0 { 0.78 } else { 0.22 };
            let ledger = MemoryUtilityLedger::from_episode(
                &stored_episode,
                react_score,
                graph_score,
                omega_score,
            );
            let decision = gate_policy.evaluate(
                &ledger,
                vec![
                    format!("react:tool_calls:{tool_count}"),
                    format!("react:outcome:{outcome}"),
                ],
                vec![format!("graph:turn_tool_count:{tool_count}")],
                vec![format!("omega:reward={reward:.3}")],
            );
            let gate_event = MemoryGateEvent::from_decision(
                session_id,
                self.next_runtime_turn_id(),
                &id,
                &ledger,
                decision.clone(),
            );
            tracing::debug!(
                event = SessionEvent::MemoryGateEvaluated.as_str(),
                session_id,
                episode_id = %id,
                episode_source,
                verdict = decision.verdict.as_str(),
                confidence = decision.confidence,
                ttl_score = gate_event.ttl_score,
                utility_score = ledger.utility_score,
                next_action = %decision.next_action,
                reason = %decision.reason,
                "memory gate decision evaluated"
            );
            if matches!(decision.verdict, MemoryGateVerdict::Obsolete) && store.delete_episode(&id)
            {
                tracing::debug!(
                    event = SessionEvent::MemoryGateEvaluated.as_str(),
                    session_id,
                    episode_id = %id,
                    episode_source,
                    action = "purged",
                    "memory episode purged by gate decision"
                );
            }
            self.publish_memory_stream_event(vec![
                ("kind".to_string(), "memory_gate_event".to_string()),
                ("session_id".to_string(), session_id.to_string()),
                ("episode_id".to_string(), id.clone()),
                ("episode_source".to_string(), episode_source.to_string()),
                ("turn_id".to_string(), gate_event.turn_id.to_string()),
                (
                    "state_before".to_string(),
                    gate_event.state_before.as_str().to_string(),
                ),
                (
                    "state_after".to_string(),
                    gate_event.state_after.as_str().to_string(),
                ),
                (
                    "ttl_score".to_string(),
                    format!("{:.3}", gate_event.ttl_score),
                ),
                ("verdict".to_string(), decision.verdict.as_str().to_string()),
                (
                    "confidence".to_string(),
                    format!("{:.3}", decision.confidence),
                ),
                ("next_action".to_string(), decision.next_action),
            ])
            .await;
        }

        persist_memory_state(
            self.memory_state_backend.as_ref(),
            store,
            session_id,
            "turn_store",
        );
        self.maybe_apply_memory_decay(session_id, store);
        self.publish_memory_stream_event(vec![
            ("kind".to_string(), "turn_stored".to_string()),
            ("session_id".to_string(), session_id.to_string()),
            ("episode_id".to_string(), id),
            ("episode_source".to_string(), episode_source.to_string()),
            ("outcome".to_string(), outcome),
            ("reward".to_string(), format!("{reward:.3}")),
        ])
        .await;
    }

    /// When window >= consolidation_threshold_turns and memory is enabled, drain oldest segment and store as episode.
    async fn try_consolidate(&self, session_id: &str) -> Result<()> {
        let (store, threshold, take, consolidate_async) = match (
            self.memory_store.as_ref().cloned(),
            self.config.consolidation_threshold_turns,
            self.config.consolidation_take_turns,
        ) {
            (Some(s), Some(t), take) if take > 0 => (s, t, take, self.config.consolidation_async),
            _ => return Ok(()),
        };
        let Some(ref w) = self.bounded_session else {
            return Ok(());
        };
        let started = Instant::now();
        let Some((turn_count, _total_tool_calls, _len)) = w.get_stats(session_id).await? else {
            return Ok(());
        };
        let turn_count = turn_count as usize;
        if turn_count < threshold {
            return Ok(());
        }
        let drained = w.drain_oldest_turns(session_id, take).await?;
        if drained.is_empty() {
            return Ok(());
        }
        let (intent, experience, outcome) = summarise_drained_turns(&drained);
        let drained_tool_calls: u32 = drained.iter().map(|(_, _, tools)| *tools).sum();
        let summary_text = build_consolidated_summary_text(&intent, &experience, &outcome);
        let summary_segment = SessionSummarySegment::new(
            summary_text,
            drained.len() / 2,
            drained_tool_calls,
            now_unix_ms(),
        );
        w.append_summary_segment(session_id, summary_segment)
            .await?;

        let id = format!("consolidated-{}-{}", session_id, now_unix_ms());
        let expected_dim = self
            .config
            .memory
            .as_ref()
            .map_or_else(|| store.encoder().dimension(), |cfg| cfg.embedding_dim);
        let embedding = self.embedding_or_hash(&intent, &store, expected_dim).await;
        let episode = Episode::new(id.clone(), intent, embedding, experience, outcome.clone());
        let reward = if outcome.to_lowercase().contains("error")
            || outcome.to_lowercase().contains("failed")
        {
            0.0
        } else {
            1.0
        };

        if consolidate_async {
            self.publish_memory_stream_event(vec![
                ("kind".to_string(), "consolidation_enqueued".to_string()),
                ("session_id".to_string(), session_id.to_string()),
                ("drained_turns".to_string(), (drained.len() / 2).to_string()),
                (
                    "drained_tool_calls".to_string(),
                    drained_tool_calls.to_string(),
                ),
                ("episode_id".to_string(), id.clone()),
            ])
            .await;
            let store_for_task = Arc::clone(&store);
            let id_for_task = id.clone();
            let session_id_for_task = session_id.to_string();
            let backend_for_task = self.memory_state_backend.clone();
            tokio::task::spawn_blocking(move || {
                match store_for_task.store_for_scope(&session_id_for_task, episode) {
                    Ok(_) => {
                        store_for_task.update_q(&id_for_task, reward);
                        persist_memory_state(
                            backend_for_task.as_ref(),
                            &store_for_task,
                            &session_id_for_task,
                            "consolidation",
                        );
                    }
                    Err(error) => {
                        tracing::warn!(
                            event = SessionEvent::MemoryConsolidationStoreFailed.as_str(),
                            session_id = %session_id_for_task,
                            error = %error,
                            "failed to store consolidated memory episode"
                        );
                    }
                }
            });
        } else {
            match store.store_for_scope(session_id, episode) {
                Ok(_) => {
                    store.update_q(&id, reward);
                    persist_memory_state(
                        self.memory_state_backend.as_ref(),
                        &store,
                        session_id,
                        "consolidation",
                    );
                    self.publish_memory_stream_event(vec![
                        ("kind".to_string(), "consolidation_stored".to_string()),
                        ("session_id".to_string(), session_id.to_string()),
                        ("episode_id".to_string(), id.clone()),
                        ("reward".to_string(), format!("{reward:.3}")),
                        ("drained_turns".to_string(), (drained.len() / 2).to_string()),
                        (
                            "drained_tool_calls".to_string(),
                            drained_tool_calls.to_string(),
                        ),
                    ])
                    .await;
                }
                Err(error) => {
                    tracing::warn!(
                        event = SessionEvent::MemoryConsolidationStoreFailed.as_str(),
                        session_id,
                        error = %error,
                        "failed to store consolidated memory episode"
                    );
                    self.publish_memory_stream_event(vec![
                        ("kind".to_string(), "consolidation_store_failed".to_string()),
                        ("session_id".to_string(), session_id.to_string()),
                        ("error".to_string(), error.to_string()),
                    ])
                    .await;
                }
            }
        }
        tracing::debug!(
            session_id,
            threshold,
            drained_turns = drained.len() / 2,
            drained_slots = drained.len(),
            drained_tool_calls,
            consolidate_async,
            duration_ms = started.elapsed().as_millis(),
            "session consolidation completed"
        );
        Ok(())
    }
}
