//! Bounded session store: session_id → ring buffer of recent turns (omni-window).
//! Used when config.window_max_turns is set; context for LLM is built from recent turns.

use std::collections::{HashMap, VecDeque};
use std::sync::Arc;

use anyhow::{Context, Result};
use omni_window::SessionWindow;
use omni_window::TurnSlot;
use tokio::sync::RwLock;

use crate::observability::SessionEvent;

use super::message::ChatMessage;
use super::redis_backend::RedisSessionBackend;
use super::summary::SessionSummarySegment;

const DEFAULT_SUMMARY_MAX_SEGMENTS: usize = 8;
const DEFAULT_SUMMARY_MAX_CHARS: usize = 480;

/// Bounded session store: one ring buffer (SessionWindow) per session_id. Thread-safe via RwLock.
#[derive(Clone)]
pub struct BoundedSessionStore {
    inner: Arc<RwLock<HashMap<String, SessionWindow>>>,
    summaries: Arc<RwLock<HashMap<String, VecDeque<SessionSummarySegment>>>>,
    max_slots: usize,
    summary_max_segments: usize,
    summary_max_chars: usize,
    redis: Option<Arc<RedisSessionBackend>>,
}

impl BoundedSessionStore {
    fn from_redis_backend(
        max_turns: usize,
        summary_max_segments: usize,
        summary_max_chars: usize,
        redis: Option<Arc<RedisSessionBackend>>,
    ) -> Self {
        let max_turns = max_turns.max(1);
        let max_slots = max_turns.saturating_mul(2).max(2);
        Self {
            inner: Arc::new(RwLock::new(HashMap::new())),
            summaries: Arc::new(RwLock::new(HashMap::new())),
            max_slots,
            summary_max_segments: summary_max_segments.max(1),
            summary_max_chars: summary_max_chars.max(1),
            redis,
        }
    }

    /// Create a store with the given max turns per session.
    pub fn new(max_turns: usize) -> Result<Self> {
        Self::new_with_limits(
            max_turns,
            DEFAULT_SUMMARY_MAX_SEGMENTS,
            DEFAULT_SUMMARY_MAX_CHARS,
        )
    }

    /// Create a store with explicit summary limits.
    pub fn new_with_limits(
        max_turns: usize,
        summary_max_segments: usize,
        summary_max_chars: usize,
    ) -> Result<Self> {
        let redis = match RedisSessionBackend::from_env() {
            Some(Ok(backend)) => {
                tracing::info!(
                    event = SessionEvent::SessionBackendEnabled.as_str(),
                    key_prefix = %backend.key_prefix(),
                    ttl_secs = ?backend.ttl_secs(),
                    max_turns,
                    "bounded session store backend enabled: valkey"
                );
                Some(Arc::new(backend))
            }
            Some(Err(error)) => {
                return Err(error).context("failed to initialize valkey bounded session store");
            }
            None => None,
        };
        Ok(Self::from_redis_backend(
            max_turns,
            summary_max_segments,
            summary_max_chars,
            redis,
        ))
    }

    /// Create a bounded store with explicit Valkey backend parameters.
    pub fn new_with_redis(
        max_turns: usize,
        redis_url: impl Into<String>,
        key_prefix: Option<String>,
        ttl_secs: Option<u64>,
    ) -> Result<Self> {
        Self::new_with_redis_and_limits(
            max_turns,
            redis_url,
            key_prefix,
            ttl_secs,
            DEFAULT_SUMMARY_MAX_SEGMENTS,
            DEFAULT_SUMMARY_MAX_CHARS,
        )
    }

    /// Create a bounded store with explicit Valkey backend and summary limits.
    pub fn new_with_redis_and_limits(
        max_turns: usize,
        redis_url: impl Into<String>,
        key_prefix: Option<String>,
        ttl_secs: Option<u64>,
        summary_max_segments: usize,
        summary_max_chars: usize,
    ) -> Result<Self> {
        let backend = RedisSessionBackend::new_from_parts(redis_url.into(), key_prefix, ttl_secs)?;
        Ok(Self::from_redis_backend(
            max_turns,
            summary_max_segments,
            summary_max_chars,
            Some(Arc::new(backend)),
        ))
    }

    /// Returns recent turns as ChatMessages (role + content only) for LLM context. Oldest first.
    pub async fn get_recent_messages(
        &self,
        session_id: &str,
        limit: usize,
    ) -> Result<Vec<ChatMessage>> {
        let limit_slots = limit.saturating_mul(2);
        if let Some(ref redis) = self.redis {
            let slots = redis
                .get_recent_window_slots(session_id, limit_slots)
                .await
                .with_context(|| {
                    format!("valkey bounded session read failed for session_id={session_id}")
                })?;
            let messages = turn_slots_to_messages(&slots);
            tracing::debug!(
                event = SessionEvent::BoundedRecentMessagesLoaded.as_str(),
                session_id,
                requested_turns = limit,
                loaded_messages = messages.len(),
                backend = "valkey",
                "bounded session recent messages loaded"
            );
            return Ok(messages);
        }
        let g = self.inner.read().await;
        let Some(w) = g.get(session_id) else {
            return Ok(Vec::new());
        };
        let turns = w.get_recent_turns(limit_slots);
        let messages = turns
            .iter()
            .map(|s| ChatMessage {
                role: s.role.clone(),
                content: Some(s.content.clone()),
                tool_calls: None,
                tool_call_id: None,
                name: None,
            })
            .collect::<Vec<_>>();
        tracing::debug!(
            event = SessionEvent::BoundedRecentMessagesLoaded.as_str(),
            session_id,
            requested_turns = limit,
            loaded_messages = messages.len(),
            backend = "memory",
            "bounded session recent messages loaded"
        );
        Ok(messages)
    }

    /// Returns recent raw window slots (oldest to newest) for exact state snapshot/restore.
    pub async fn get_recent_slots(
        &self,
        session_id: &str,
        limit_slots: usize,
    ) -> Result<Vec<TurnSlot>> {
        if limit_slots == 0 {
            return Ok(Vec::new());
        }

        if let Some(ref redis) = self.redis {
            let slots = redis
                .get_recent_window_slots(session_id, limit_slots)
                .await
                .with_context(|| {
                    format!("valkey bounded session slot read failed for session_id={session_id}")
                })?;
            tracing::debug!(
                event = SessionEvent::SessionWindowSlotsLoaded.as_str(),
                session_id,
                requested_limit_slots = limit_slots,
                loaded_slots = slots.len(),
                backend = "valkey",
                "bounded session raw slots loaded"
            );
            return Ok(slots);
        }

        let g = self.inner.read().await;
        let Some(w) = g.get(session_id) else {
            return Ok(Vec::new());
        };
        let slots = w
            .get_recent_turns(limit_slots)
            .into_iter()
            .cloned()
            .collect::<Vec<_>>();
        tracing::debug!(
            event = SessionEvent::SessionWindowSlotsLoaded.as_str(),
            session_id,
            requested_limit_slots = limit_slots,
            loaded_slots = slots.len(),
            backend = "memory",
            "bounded session raw slots loaded"
        );
        Ok(slots)
    }

    /// Append one user/assistant turn. Creates the session window if missing.
    pub async fn append_turn(
        &self,
        session_id: &str,
        user_content: &str,
        assistant_content: &str,
        tool_count: u32,
    ) -> Result<()> {
        let slots = vec![
            TurnSlot::new("user", user_content, 0),
            TurnSlot::new("assistant", assistant_content, tool_count),
        ];
        if let Some(ref redis) = self.redis {
            redis
                .append_window_slots(session_id, self.max_slots, &slots)
                .await
                .with_context(|| {
                    format!("valkey bounded session append failed for session_id={session_id}")
                })?;
            tracing::debug!(
                event = SessionEvent::BoundedTurnAppended.as_str(),
                session_id,
                tool_count,
                user_chars = user_content.chars().count(),
                assistant_chars = assistant_content.chars().count(),
                backend = "valkey",
                "bounded session turn appended"
            );
            return Ok(());
        }

        let mut g = self.inner.write().await;
        let w = g
            .entry(session_id.to_string())
            .or_insert_with(|| SessionWindow::new(session_id, self.max_slots));
        w.append_turn("user", user_content, 0, None);
        w.append_turn("assistant", assistant_content, tool_count, None);
        tracing::debug!(
            event = SessionEvent::BoundedTurnAppended.as_str(),
            session_id,
            tool_count,
            user_chars = user_content.chars().count(),
            assistant_chars = assistant_content.chars().count(),
            backend = "memory",
            "bounded session turn appended"
        );
        Ok(())
    }

    /// Replace active window slots for a session with an exact raw snapshot.
    pub async fn replace_window_slots(&self, session_id: &str, slots: &[TurnSlot]) -> Result<()> {
        if let Some(ref redis) = self.redis {
            redis.clear_window(session_id).await.with_context(|| {
                format!("valkey bounded session clear failed for session_id={session_id}")
            })?;
            if !slots.is_empty() {
                redis
                    .append_window_slots(session_id, self.max_slots, slots)
                    .await
                    .with_context(|| {
                        format!("valkey bounded session restore failed for session_id={session_id}")
                    })?;
            }
            tracing::debug!(
                event = SessionEvent::SessionWindowSlotsAppended.as_str(),
                session_id,
                replaced_slots = slots.len(),
                backend = "valkey",
                "bounded session window slots replaced"
            );
            return Ok(());
        }

        let mut g = self.inner.write().await;
        if slots.is_empty() {
            g.remove(session_id);
            tracing::debug!(
                event = SessionEvent::SessionWindowCleared.as_str(),
                session_id,
                backend = "memory",
                "bounded session window slots replaced with empty snapshot"
            );
            return Ok(());
        }

        let mut window = SessionWindow::new(session_id, self.max_slots);
        for slot in slots {
            window.append_turn(
                &slot.role,
                &slot.content,
                slot.tool_count,
                slot.checkpoint_id.as_deref(),
            );
        }
        g.insert(session_id.to_string(), window);
        tracing::debug!(
            event = SessionEvent::SessionWindowSlotsAppended.as_str(),
            session_id,
            replaced_slots = slots.len(),
            backend = "memory",
            "bounded session window slots replaced"
        );
        Ok(())
    }

    pub async fn atomic_reset_snapshot(
        &self,
        session_id: &str,
        backup_session_id: &str,
        metadata_session_id: &str,
        saved_at_unix_ms: u64,
    ) -> Result<Option<(usize, usize)>> {
        let Some(ref redis) = self.redis else {
            return Ok(None);
        };
        let stats = redis
            .atomic_reset_bounded_snapshot(
                session_id,
                backup_session_id,
                metadata_session_id,
                saved_at_unix_ms,
            )
            .await
            .with_context(|| {
                format!("atomic bounded snapshot reset failed for session_id={session_id}")
            })?;
        Ok(Some(stats))
    }

    pub async fn atomic_resume_snapshot(
        &self,
        session_id: &str,
        backup_session_id: &str,
        metadata_session_id: &str,
    ) -> Result<Option<(usize, usize)>> {
        let Some(ref redis) = self.redis else {
            return Ok(None);
        };
        redis
            .atomic_resume_bounded_snapshot(session_id, backup_session_id, metadata_session_id)
            .await
            .with_context(|| {
                format!("atomic bounded snapshot resume failed for session_id={session_id}")
            })
    }

    pub async fn atomic_drop_snapshot(
        &self,
        backup_session_id: &str,
        metadata_session_id: &str,
    ) -> Result<Option<bool>> {
        let Some(ref redis) = self.redis else {
            return Ok(None);
        };
        let dropped = redis
            .atomic_drop_bounded_snapshot(backup_session_id, metadata_session_id)
            .await
            .with_context(|| {
                format!(
                    "atomic bounded snapshot drop failed for backup_session_id={backup_session_id}"
                )
            })?;
        Ok(Some(dropped))
    }

    /// Session stats: (turn_count, total_tool_calls, ring_len).
    pub async fn get_stats(&self, session_id: &str) -> Result<Option<(u64, u64, usize)>> {
        if let Some(ref redis) = self.redis {
            let stats = redis.get_window_stats(session_id).await.with_context(|| {
                format!("valkey bounded session stats failed for session_id={session_id}")
            })?;
            let mapped = stats.map(|(slots, tool_calls, ring_len)| {
                let turn_count = slots / 2;
                (turn_count, tool_calls, ring_len)
            });
            if let Some((turn_count, tool_calls, ring_len)) = mapped {
                tracing::debug!(
                    event = SessionEvent::BoundedStatsLoaded.as_str(),
                    session_id,
                    turn_count,
                    tool_calls,
                    ring_len,
                    backend = "valkey",
                    "bounded session stats loaded"
                );
            }
            return Ok(mapped);
        }
        let g = self.inner.read().await;
        let mapped = g.get(session_id).map(|w| {
            let (slots, tool_calls, ring_len) = w.get_stats();
            let turn_count = slots / 2;
            (turn_count, tool_calls, ring_len)
        });
        if let Some((turn_count, tool_calls, ring_len)) = mapped {
            tracing::debug!(
                event = SessionEvent::BoundedStatsLoaded.as_str(),
                session_id,
                turn_count,
                tool_calls,
                ring_len,
                backend = "memory",
                "bounded session stats loaded"
            );
        }
        Ok(mapped)
    }

    /// Clear the session (e.g. on explicit clear).
    pub async fn clear(&self, session_id: &str) -> Result<()> {
        if let Some(ref redis) = self.redis {
            redis.clear_window(session_id).await.with_context(|| {
                format!("valkey bounded session clear failed for session_id={session_id}")
            })?;
            redis.clear_summary(session_id).await.with_context(|| {
                format!("valkey bounded summary clear failed for session_id={session_id}")
            })?;
            tracing::debug!(
                event = SessionEvent::BoundedCleared.as_str(),
                session_id,
                backend = "valkey",
                "bounded session cleared"
            );
            return Ok(());
        }
        let mut g = self.inner.write().await;
        g.remove(session_id);
        let mut summaries = self.summaries.write().await;
        summaries.remove(session_id);
        tracing::debug!(
            event = SessionEvent::BoundedCleared.as_str(),
            session_id,
            backend = "memory",
            "bounded session cleared"
        );
        Ok(())
    }

    /// Drain the oldest `n` turns for consolidation. Returns (role, content, tool_count) per turn.
    /// Call when window is at or above consolidation threshold; then summarise and store as episode.
    pub async fn drain_oldest_turns(
        &self,
        session_id: &str,
        n: usize,
    ) -> Result<Vec<(String, String, u32)>> {
        let n_slots = n.saturating_mul(2);
        if let Some(ref redis) = self.redis {
            let slots = redis
                .drain_oldest_window_slots(session_id, n_slots)
                .await
                .with_context(|| {
                    format!("valkey bounded session drain failed for session_id={session_id}")
                })?;
            let mut g = self.inner.write().await;
            if let Some(w) = g.get_mut(session_id) {
                let _ = w.drain_oldest_turns(n_slots);
            }
            let drained = slots
                .into_iter()
                .map(|s| (s.role, s.content, s.tool_count))
                .collect::<Vec<_>>();
            tracing::debug!(
                event = SessionEvent::BoundedTurnsDrained.as_str(),
                session_id,
                requested_turns = n,
                drained_turns = drained.len() / 2,
                drained_slots = drained.len(),
                backend = "valkey",
                "bounded session oldest turns drained"
            );
            return Ok(drained);
        }

        let mut g = self.inner.write().await;
        let Some(w) = g.get_mut(session_id) else {
            return Ok(Vec::new());
        };
        let slots = w.drain_oldest_turns(n_slots);
        let drained = slots
            .into_iter()
            .map(|s| (s.role, s.content, s.tool_count))
            .collect::<Vec<_>>();
        tracing::debug!(
            event = SessionEvent::BoundedTurnsDrained.as_str(),
            session_id,
            requested_turns = n,
            drained_turns = drained.len() / 2,
            drained_slots = drained.len(),
            backend = "memory",
            "bounded session oldest turns drained"
        );
        Ok(drained)
    }

    /// Append a compact summary segment produced during consolidation.
    pub async fn append_summary_segment(
        &self,
        session_id: &str,
        segment: SessionSummarySegment,
    ) -> Result<()> {
        let mut segment = segment;
        segment.summary = truncate_to_chars(&segment.summary, self.summary_max_chars);
        if segment.summary.is_empty() {
            return Ok(());
        }

        if let Some(ref redis) = self.redis {
            redis
                .append_summary_segment(session_id, self.summary_max_segments, &segment)
                .await
                .with_context(|| {
                    format!("valkey bounded summary append failed for session_id={session_id}")
                })?;
            tracing::debug!(
                event = SessionEvent::BoundedSummarySegmentAppended.as_str(),
                session_id,
                chars = segment.summary.chars().count(),
                max_segments = self.summary_max_segments,
                backend = "valkey",
                "bounded session summary segment appended"
            );
            return Ok(());
        }

        let mut g = self.summaries.write().await;
        let queue = g
            .entry(session_id.to_string())
            .or_insert_with(|| VecDeque::with_capacity(self.summary_max_segments));
        queue.push_back(segment);
        while queue.len() > self.summary_max_segments {
            let _ = queue.pop_front();
        }
        tracing::debug!(
            event = SessionEvent::BoundedSummarySegmentAppended.as_str(),
            session_id,
            max_segments = self.summary_max_segments,
            current_segments = queue.len(),
            backend = "memory",
            "bounded session summary segment appended"
        );
        Ok(())
    }

    /// Get the most recent compact summary segments for prompt context injection.
    pub async fn get_recent_summary_segments(
        &self,
        session_id: &str,
        limit: usize,
    ) -> Result<Vec<SessionSummarySegment>> {
        if limit == 0 {
            return Ok(Vec::new());
        }
        if let Some(ref redis) = self.redis {
            let segments = redis
                .get_recent_summary_segments(session_id, limit)
                .await
                .with_context(|| {
                    format!("valkey bounded summary read failed for session_id={session_id}")
                })?;
            tracing::debug!(
                event = SessionEvent::BoundedSummarySegmentsLoaded.as_str(),
                session_id,
                requested_limit = limit,
                loaded_segments = segments.len(),
                backend = "valkey",
                "bounded session summary segments loaded"
            );
            return Ok(segments);
        }
        let g = self.summaries.read().await;
        let Some(queue) = g.get(session_id) else {
            return Ok(Vec::new());
        };
        let take = queue.len().min(limit);
        let mut out = queue.iter().rev().take(take).cloned().collect::<Vec<_>>();
        out.reverse();
        tracing::debug!(
            event = SessionEvent::BoundedSummarySegmentsLoaded.as_str(),
            session_id,
            requested_limit = limit,
            loaded_segments = out.len(),
            backend = "memory",
            "bounded session summary segments loaded"
        );
        Ok(out)
    }

    /// Count compact summary segments for the session without loading full contents.
    pub async fn get_summary_segment_count(&self, session_id: &str) -> Result<usize> {
        if let Some(ref redis) = self.redis {
            let segment_count = redis.get_summary_len(session_id).await.with_context(|| {
                format!("valkey bounded summary count failed for session_id={session_id}")
            })?;
            tracing::debug!(
                event = SessionEvent::BoundedSummarySegmentsLoaded.as_str(),
                session_id,
                loaded_segments = segment_count,
                backend = "valkey",
                count_only = true,
                "bounded session summary segment count loaded"
            );
            return Ok(segment_count);
        }

        let g = self.summaries.read().await;
        let segment_count = g.get(session_id).map_or(0, VecDeque::len);
        tracing::debug!(
            event = SessionEvent::BoundedSummarySegmentsLoaded.as_str(),
            session_id,
            loaded_segments = segment_count,
            backend = "memory",
            count_only = true,
            "bounded session summary segment count loaded"
        );
        Ok(segment_count)
    }
}

fn turn_slots_to_messages(slots: &[TurnSlot]) -> Vec<ChatMessage> {
    slots
        .iter()
        .map(|s| ChatMessage {
            role: s.role.clone(),
            content: Some(s.content.clone()),
            tool_calls: None,
            tool_call_id: None,
            name: None,
        })
        .collect()
}

fn truncate_to_chars(input: &str, max_chars: usize) -> String {
    let trimmed = input.trim();
    if trimmed.is_empty() || max_chars == 0 {
        return String::new();
    }
    let char_count = trimmed.chars().count();
    if char_count <= max_chars {
        return trimmed.to_string();
    }
    let keep = max_chars.saturating_sub(3);
    let mut out = trimmed.chars().take(keep).collect::<String>();
    out.push_str("...");
    out
}
