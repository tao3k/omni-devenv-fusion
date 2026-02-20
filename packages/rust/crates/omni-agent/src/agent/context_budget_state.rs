use std::time::{SystemTime, UNIX_EPOCH};

use crate::config::ContextBudgetStrategy;

use super::Agent;
use super::context_budget::{ContextBudgetClassStats, ContextBudgetReport};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SessionContextBudgetClassSnapshot {
    pub input_messages: usize,
    pub kept_messages: usize,
    pub dropped_messages: usize,
    pub truncated_messages: usize,
    pub input_tokens: usize,
    pub kept_tokens: usize,
    pub dropped_tokens: usize,
    pub truncated_tokens: usize,
}

impl SessionContextBudgetClassSnapshot {
    fn from_stats(stats: &ContextBudgetClassStats) -> Self {
        Self {
            input_messages: stats.input_messages,
            kept_messages: stats.kept_messages,
            dropped_messages: stats.dropped_messages(),
            truncated_messages: stats.truncated_messages,
            input_tokens: stats.input_tokens,
            kept_tokens: stats.kept_tokens,
            dropped_tokens: stats.dropped_tokens(),
            truncated_tokens: stats.truncated_tokens,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SessionContextBudgetSnapshot {
    pub created_at_unix_ms: u64,
    pub strategy: ContextBudgetStrategy,
    pub budget_tokens: usize,
    pub reserve_tokens: usize,
    pub effective_budget_tokens: usize,
    pub pre_messages: usize,
    pub post_messages: usize,
    pub dropped_messages: usize,
    pub pre_tokens: usize,
    pub post_tokens: usize,
    pub dropped_tokens: usize,
    pub non_system: SessionContextBudgetClassSnapshot,
    pub regular_system: SessionContextBudgetClassSnapshot,
    pub summary_system: SessionContextBudgetClassSnapshot,
}

impl SessionContextBudgetSnapshot {
    pub(crate) fn from_report(report: &ContextBudgetReport) -> Self {
        Self {
            created_at_unix_ms: now_unix_ms(),
            strategy: report.strategy,
            budget_tokens: report.budget_tokens,
            reserve_tokens: report.reserve_tokens,
            effective_budget_tokens: report.effective_budget_tokens,
            pre_messages: report.pre_messages,
            post_messages: report.post_messages,
            dropped_messages: report.pre_messages.saturating_sub(report.post_messages),
            pre_tokens: report.pre_tokens,
            post_tokens: report.post_tokens,
            dropped_tokens: report.pre_tokens.saturating_sub(report.post_tokens),
            non_system: SessionContextBudgetClassSnapshot::from_stats(&report.non_system),
            regular_system: SessionContextBudgetClassSnapshot::from_stats(&report.regular_system),
            summary_system: SessionContextBudgetClassSnapshot::from_stats(&report.summary_system),
        }
    }
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

impl Agent {
    pub(crate) async fn record_context_budget_snapshot(
        &self,
        session_id: &str,
        report: &ContextBudgetReport,
    ) {
        let snapshot = SessionContextBudgetSnapshot::from_report(report);
        let mut guard = self.context_budget_snapshots.write().await;
        guard.insert(session_id.to_string(), snapshot);
    }

    pub async fn inspect_context_budget_snapshot(
        &self,
        session_id: &str,
    ) -> Option<SessionContextBudgetSnapshot> {
        let guard = self.context_budget_snapshots.read().await;
        guard.get(session_id).copied()
    }
}
