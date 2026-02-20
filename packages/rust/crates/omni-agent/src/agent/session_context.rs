use anyhow::Result;
use omni_window::TurnSlot;
use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::observability::SessionEvent;
use crate::session::{ChatMessage, SessionSummarySegment};

use super::Agent;

const SESSION_CONTEXT_BACKUP_PREFIX: &str = "__session_context_backup__:";
const SESSION_CONTEXT_BACKUP_META_PREFIX: &str = "__session_context_backup_meta__:";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SessionContextStats {
    pub messages: usize,
    pub summary_segments: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SessionContextSnapshotInfo {
    pub messages: usize,
    pub summary_segments: usize,
    pub saved_at_unix_ms: Option<u64>,
    pub saved_age_secs: Option<u64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionContextMode {
    Bounded,
    Unbounded,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SessionContextWindowInfo {
    pub mode: SessionContextMode,
    pub messages: usize,
    pub summary_segments: usize,
    pub window_turns: Option<usize>,
    pub window_slots: Option<usize>,
    pub total_tool_calls: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct SessionContextBackupMetadata {
    messages: usize,
    summary_segments: usize,
    saved_at_unix_ms: u64,
}

#[derive(Clone, Default)]
struct SessionContextBackup {
    messages: Vec<ChatMessage>,
    summary_segments: Vec<SessionSummarySegment>,
    window_slots: Vec<TurnSlot>,
}

impl SessionContextBackup {
    fn stats(&self) -> SessionContextStats {
        let messages = if self.window_slots.is_empty() {
            self.messages.len()
        } else {
            self.window_slots.len()
        };
        SessionContextStats {
            messages,
            summary_segments: self.summary_segments.len(),
        }
    }

    fn is_empty(&self) -> bool {
        self.messages.is_empty() && self.summary_segments.is_empty() && self.window_slots.is_empty()
    }
}

impl Agent {
    /// Save current session window/context snapshot and clear the active session context.
    ///
    /// This only affects conversation context state (window + in-memory session history).
    /// It does not clear long-term memRL episodes or knowledge/skill memory.
    pub async fn reset_context_window(&self, session_id: &str) -> Result<SessionContextStats> {
        let backup_session_id = backup_session_id(session_id);
        let metadata_session_id = backup_metadata_session_id(session_id);

        if let Some(ref w) = self.bounded_session
            && let Some((messages, summary_segments)) = w
                .atomic_reset_snapshot(
                    session_id,
                    &backup_session_id,
                    &metadata_session_id,
                    now_unix_ms(),
                )
                .await?
        {
            let stats = SessionContextStats {
                messages,
                summary_segments,
            };
            tracing::debug!(
                event = SessionEvent::ContextWindowReset.as_str(),
                session_id,
                messages = stats.messages,
                summary_segments = stats.summary_segments,
                backup_saved = stats.messages > 0 || stats.summary_segments > 0,
                mode = "bounded-atomic",
                "session context window reset"
            );
            return Ok(stats);
        }

        let backup = self.capture_session_backup(session_id).await?;
        let stats = backup.stats();
        let backup_was_empty = backup.is_empty();

        self.clear_session(session_id).await?;

        // Keep prior snapshot when current context is already empty.
        if !backup_was_empty {
            self.store_session_backup(&backup_session_id, &backup)
                .await?;
            self.store_backup_metadata(session_id, stats).await?;
        }

        tracing::debug!(
            event = SessionEvent::ContextWindowReset.as_str(),
            session_id,
            messages = stats.messages,
            summary_segments = stats.summary_segments,
            backup_saved = !backup_was_empty,
            "session context window reset"
        );
        Ok(stats)
    }

    /// Restore the latest saved context snapshot after `/reset` or `/clear`.
    ///
    /// Returns `Ok(None)` when no snapshot exists for this session.
    pub async fn resume_context_window(
        &self,
        session_id: &str,
    ) -> Result<Option<SessionContextStats>> {
        let backup_session_id = backup_session_id(session_id);
        let metadata_session_id = backup_metadata_session_id(session_id);

        if let Some(ref w) = self.bounded_session
            && let Some((messages, summary_segments)) = w
                .atomic_resume_snapshot(session_id, &backup_session_id, &metadata_session_id)
                .await?
        {
            let stats = SessionContextStats {
                messages,
                summary_segments,
            };
            tracing::debug!(
                event = SessionEvent::ContextWindowResumed.as_str(),
                session_id,
                messages = stats.messages,
                summary_segments = stats.summary_segments,
                mode = "bounded-atomic",
                "session context window resumed"
            );
            return Ok(Some(stats));
        }

        let backup = self.capture_session_backup(&backup_session_id).await?;
        if backup.is_empty() {
            tracing::debug!(
                event = SessionEvent::ContextWindowResumeMissing.as_str(),
                session_id,
                "session context resume requested but no snapshot found"
            );
            return Ok(None);
        }

        let stats = backup.stats();
        self.restore_session_backup(session_id, backup).await?;
        self.clear_session(&backup_session_id).await?;
        self.clear_backup_metadata(session_id).await?;
        tracing::debug!(
            event = SessionEvent::ContextWindowResumed.as_str(),
            session_id,
            messages = stats.messages,
            summary_segments = stats.summary_segments,
            "session context window resumed"
        );
        Ok(Some(stats))
    }

    /// Drop saved context snapshot created by `/reset` or `/clear` without restoring it.
    ///
    /// Returns `Ok(true)` when a snapshot existed and was removed.
    pub async fn drop_context_window_backup(&self, session_id: &str) -> Result<bool> {
        let backup_session_id = backup_session_id(session_id);
        let metadata_session_id = backup_metadata_session_id(session_id);

        if let Some(ref w) = self.bounded_session
            && let Some(dropped) = w
                .atomic_drop_snapshot(&backup_session_id, &metadata_session_id)
                .await?
        {
            tracing::debug!(
                event = SessionEvent::ContextWindowSnapshotDropped.as_str(),
                session_id,
                dropped,
                mode = "bounded-atomic",
                "session context snapshot dropped"
            );
            return Ok(dropped);
        }

        let has_backup = if let Some(ref w) = self.bounded_session {
            let has_window_slots = w
                .get_stats(&backup_session_id)
                .await?
                .map(|(_, _, ring_len)| ring_len > 0)
                .unwrap_or(false);
            let summary_segments = w.get_summary_segment_count(&backup_session_id).await?;
            has_window_slots || summary_segments > 0
        } else {
            self.session.len(&backup_session_id).await? > 0
        };

        if has_backup {
            self.clear_session(&backup_session_id).await?;
        }
        self.clear_backup_metadata(session_id).await?;
        tracing::debug!(
            event = SessionEvent::ContextWindowSnapshotDropped.as_str(),
            session_id,
            dropped = has_backup,
            "session context snapshot dropped"
        );
        Ok(has_backup)
    }

    pub async fn peek_context_window_backup(
        &self,
        session_id: &str,
    ) -> Result<Option<SessionContextSnapshotInfo>> {
        let backup = self
            .capture_session_backup(&backup_session_id(session_id))
            .await?;
        if backup.is_empty() {
            return Ok(None);
        }

        let metadata = self.load_backup_metadata(session_id).await?;
        let (saved_at_unix_ms, saved_age_secs) = metadata
            .map(|meta| {
                (
                    Some(meta.saved_at_unix_ms),
                    Some(
                        now_unix_ms()
                            .saturating_sub(meta.saved_at_unix_ms)
                            .saturating_div(1000),
                    ),
                )
            })
            .unwrap_or((None, None));
        let info = SessionContextSnapshotInfo {
            messages: backup.stats().messages,
            summary_segments: backup.stats().summary_segments,
            saved_at_unix_ms,
            saved_age_secs,
        };
        tracing::debug!(
            event = SessionEvent::ContextWindowSnapshotInspected.as_str(),
            session_id,
            messages = info.messages,
            summary_segments = info.summary_segments,
            saved_at_unix_ms = ?info.saved_at_unix_ms,
            saved_age_secs = ?info.saved_age_secs,
            "session context backup snapshot inspected"
        );
        Ok(Some(info))
    }

    /// Inspect active context window counters for this session.
    pub async fn inspect_context_window(
        &self,
        session_id: &str,
    ) -> Result<SessionContextWindowInfo> {
        if let Some(ref w) = self.bounded_session {
            let (turn_count, total_tool_calls, window_slots) =
                w.get_stats(session_id).await?.unwrap_or((0, 0, 0));
            let summary_segments = w.get_summary_segment_count(session_id).await?;
            let info = SessionContextWindowInfo {
                mode: SessionContextMode::Bounded,
                messages: window_slots,
                summary_segments,
                window_turns: Some(turn_count as usize),
                window_slots: Some(window_slots),
                total_tool_calls: Some(total_tool_calls),
            };
            tracing::debug!(
                event = SessionEvent::BoundedStatsLoaded.as_str(),
                session_id,
                mode = "bounded",
                messages = info.messages,
                summary_segments = info.summary_segments,
                window_turns = ?info.window_turns,
                window_slots = ?info.window_slots,
                total_tool_calls = ?info.total_tool_calls,
                "session context window inspected"
            );
            return Ok(info);
        }

        let message_count = self.session.len(session_id).await?;
        let info = SessionContextWindowInfo {
            mode: SessionContextMode::Unbounded,
            messages: message_count,
            summary_segments: 0,
            window_turns: None,
            window_slots: None,
            total_tool_calls: None,
        };
        tracing::debug!(
            event = SessionEvent::SessionMessagesLoaded.as_str(),
            session_id,
            mode = "unbounded",
            messages = info.messages,
            summary_segments = info.summary_segments,
            "session context window inspected"
        );
        Ok(info)
    }

    #[doc(hidden)]
    pub async fn append_turn_for_session(
        &self,
        session_id: &str,
        user_msg: &str,
        assistant_msg: &str,
    ) -> Result<()> {
        self.append_turn_to_session(session_id, user_msg, assistant_msg, 0)
            .await
    }

    async fn capture_session_backup(&self, session_id: &str) -> Result<SessionContextBackup> {
        if let Some(ref w) = self.bounded_session {
            let limit_slots = self
                .config
                .window_max_turns
                .unwrap_or(512)
                .saturating_mul(2);
            let window_slots = w.get_recent_slots(session_id, limit_slots).await?;
            let summary_segments = w
                .get_recent_summary_segments(session_id, self.config.summary_max_segments)
                .await?;
            tracing::debug!(
                event = SessionEvent::ContextBackupCaptured.as_str(),
                session_id,
                messages = window_slots.len(),
                summary_segments = summary_segments.len(),
                backend = "bounded",
                "session context backup captured"
            );
            return Ok(SessionContextBackup {
                messages: Vec::new(),
                summary_segments,
                window_slots,
            });
        }

        let messages = self.session.get(session_id).await?;
        tracing::debug!(
            event = SessionEvent::ContextBackupCaptured.as_str(),
            session_id,
            messages = messages.len(),
            backend = "session-store",
            "session context backup captured"
        );
        Ok(SessionContextBackup {
            messages,
            summary_segments: Vec::new(),
            window_slots: Vec::new(),
        })
    }

    async fn store_session_backup(
        &self,
        session_id: &str,
        backup: &SessionContextBackup,
    ) -> Result<()> {
        self.clear_session(session_id).await?;

        if let Some(ref w) = self.bounded_session {
            for segment in &backup.summary_segments {
                w.append_summary_segment(session_id, segment.clone())
                    .await?;
            }
            w.replace_window_slots(session_id, &backup.window_slots)
                .await?;
            return Ok(());
        }

        self.session
            .append(session_id, backup.messages.clone())
            .await
    }

    async fn restore_session_backup(
        &self,
        session_id: &str,
        backup: SessionContextBackup,
    ) -> Result<()> {
        self.clear_session(session_id).await?;

        if let Some(ref w) = self.bounded_session {
            for segment in backup.summary_segments {
                w.append_summary_segment(session_id, segment).await?;
            }
            w.replace_window_slots(session_id, &backup.window_slots)
                .await?;
            return Ok(());
        }

        self.session.append(session_id, backup.messages).await
    }

    async fn store_backup_metadata(
        &self,
        session_id: &str,
        stats: SessionContextStats,
    ) -> Result<()> {
        let metadata_session_id = backup_metadata_session_id(session_id);
        let metadata = SessionContextBackupMetadata {
            messages: stats.messages,
            summary_segments: stats.summary_segments,
            saved_at_unix_ms: now_unix_ms(),
        };
        let content = serde_json::to_string(&metadata)?;
        self.session.clear(&metadata_session_id).await?;
        self.session
            .append(
                &metadata_session_id,
                vec![ChatMessage {
                    role: "system".to_string(),
                    content: Some(content),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                }],
            )
            .await
    }

    async fn load_backup_metadata(
        &self,
        session_id: &str,
    ) -> Result<Option<SessionContextBackupMetadata>> {
        let metadata_session_id = backup_metadata_session_id(session_id);
        let messages = self.session.get(&metadata_session_id).await?;
        let Some(content) = messages
            .into_iter()
            .rev()
            .find_map(|message| message.content)
        else {
            return Ok(None);
        };
        Ok(serde_json::from_str(&content).ok())
    }

    async fn clear_backup_metadata(&self, session_id: &str) -> Result<()> {
        self.session
            .clear(&backup_metadata_session_id(session_id))
            .await
    }

    #[doc(hidden)]
    pub async fn append_turn_with_tool_count_for_session(
        &self,
        session_id: &str,
        user_msg: &str,
        assistant_msg: &str,
        tool_count: u32,
    ) -> Result<()> {
        self.append_turn_to_session(session_id, user_msg, assistant_msg, tool_count)
            .await
    }
}

fn backup_session_id(session_id: &str) -> String {
    format!("{SESSION_CONTEXT_BACKUP_PREFIX}{session_id}")
}

fn backup_metadata_session_id(session_id: &str) -> String {
    format!("{SESSION_CONTEXT_BACKUP_META_PREFIX}{session_id}")
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}
