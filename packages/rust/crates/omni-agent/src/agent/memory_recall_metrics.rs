use std::time::{SystemTime, UNIX_EPOCH};

use super::Agent;
use super::memory_recall_state::SessionMemoryRecallDecision;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct MemoryRecallLatencyBucketsSnapshot {
    pub le_10ms: u64,
    pub le_25ms: u64,
    pub le_50ms: u64,
    pub le_100ms: u64,
    pub le_250ms: u64,
    pub le_500ms: u64,
    pub gt_500ms: u64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MemoryRecallMetricsSnapshot {
    pub captured_at_unix_ms: u64,
    pub planned_total: u64,
    pub injected_total: u64,
    pub skipped_total: u64,
    pub completed_total: u64,
    pub selected_total: u64,
    pub injected_items_total: u64,
    pub context_chars_injected_total: u64,
    pub pipeline_duration_ms_total: u64,
    pub avg_pipeline_duration_ms: f32,
    pub avg_selected_per_completed: f32,
    pub avg_injected_per_injected: f32,
    pub injected_rate: f32,
    pub latency_buckets: MemoryRecallLatencyBucketsSnapshot,
}

#[derive(Debug, Clone, Copy, Default)]
pub(crate) struct MemoryRecallMetricsState {
    planned_total: u64,
    injected_total: u64,
    skipped_total: u64,
    selected_total: u64,
    injected_items_total: u64,
    context_chars_injected_total: u64,
    pipeline_duration_ms_total: u64,
    latency_buckets: MemoryRecallLatencyBucketsSnapshot,
}

impl MemoryRecallMetricsState {
    fn observe_plan(&mut self) {
        self.planned_total = self.planned_total.saturating_add(1);
    }

    fn observe_result(
        &mut self,
        decision: SessionMemoryRecallDecision,
        recalled_selected: usize,
        recalled_injected: usize,
        context_chars_injected: usize,
        pipeline_duration_ms: u64,
    ) {
        match decision {
            SessionMemoryRecallDecision::Injected => {
                self.injected_total = self.injected_total.saturating_add(1)
            }
            SessionMemoryRecallDecision::Skipped => {
                self.skipped_total = self.skipped_total.saturating_add(1)
            }
        }

        self.selected_total = self.selected_total.saturating_add(recalled_selected as u64);
        self.injected_items_total = self
            .injected_items_total
            .saturating_add(recalled_injected as u64);
        self.context_chars_injected_total = self
            .context_chars_injected_total
            .saturating_add(context_chars_injected as u64);
        self.pipeline_duration_ms_total = self
            .pipeline_duration_ms_total
            .saturating_add(pipeline_duration_ms);
        self.observe_latency_bucket(pipeline_duration_ms);
    }

    fn observe_latency_bucket(&mut self, duration_ms: u64) {
        if duration_ms <= 10 {
            self.latency_buckets.le_10ms = self.latency_buckets.le_10ms.saturating_add(1);
        } else if duration_ms <= 25 {
            self.latency_buckets.le_25ms = self.latency_buckets.le_25ms.saturating_add(1);
        } else if duration_ms <= 50 {
            self.latency_buckets.le_50ms = self.latency_buckets.le_50ms.saturating_add(1);
        } else if duration_ms <= 100 {
            self.latency_buckets.le_100ms = self.latency_buckets.le_100ms.saturating_add(1);
        } else if duration_ms <= 250 {
            self.latency_buckets.le_250ms = self.latency_buckets.le_250ms.saturating_add(1);
        } else if duration_ms <= 500 {
            self.latency_buckets.le_500ms = self.latency_buckets.le_500ms.saturating_add(1);
        } else {
            self.latency_buckets.gt_500ms = self.latency_buckets.gt_500ms.saturating_add(1);
        }
    }

    fn snapshot(self) -> MemoryRecallMetricsSnapshot {
        let completed_total = self.injected_total.saturating_add(self.skipped_total);
        MemoryRecallMetricsSnapshot {
            captured_at_unix_ms: now_unix_ms(),
            planned_total: self.planned_total,
            injected_total: self.injected_total,
            skipped_total: self.skipped_total,
            completed_total,
            selected_total: self.selected_total,
            injected_items_total: self.injected_items_total,
            context_chars_injected_total: self.context_chars_injected_total,
            pipeline_duration_ms_total: self.pipeline_duration_ms_total,
            avg_pipeline_duration_ms: ratio_as_f32(
                self.pipeline_duration_ms_total,
                completed_total,
            ),
            avg_selected_per_completed: ratio_as_f32(self.selected_total, completed_total),
            avg_injected_per_injected: ratio_as_f32(self.injected_items_total, self.injected_total),
            injected_rate: ratio_as_f32(self.injected_total, completed_total),
            latency_buckets: self.latency_buckets,
        }
    }
}

fn ratio_as_f32(numerator: u64, denominator: u64) -> f32 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f32 / denominator as f32
    }
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

impl Agent {
    pub(crate) async fn record_memory_recall_plan_metrics(&self) {
        let mut guard = self.memory_recall_metrics.write().await;
        guard.observe_plan();
    }

    pub(crate) async fn record_memory_recall_result_metrics(
        &self,
        decision: SessionMemoryRecallDecision,
        recalled_selected: usize,
        recalled_injected: usize,
        context_chars_injected: usize,
        pipeline_duration_ms: u64,
    ) {
        let mut guard = self.memory_recall_metrics.write().await;
        guard.observe_result(
            decision,
            recalled_selected,
            recalled_injected,
            context_chars_injected,
            pipeline_duration_ms,
        );
    }

    pub async fn inspect_memory_recall_metrics(&self) -> MemoryRecallMetricsSnapshot {
        let guard = self.memory_recall_metrics.read().await;
        (*guard).snapshot()
    }
}

#[cfg(test)]
#[path = "../../tests/agent/memory_recall_metrics.rs"]
mod tests;
