use serde_json::json;

pub(super) fn format_memory_recall_metrics_lines(
    metrics: crate::agent::MemoryRecallMetricsSnapshot,
) -> Vec<String> {
    vec![
        format!("- `planned_total={}`", metrics.planned_total),
        format!(
            "- `completed_total={}` / `injected={}` / `skipped={}`",
            metrics.completed_total, metrics.injected_total, metrics.skipped_total
        ),
        format!(
            "- `selected_total={}` / `injected_items_total={}`",
            metrics.selected_total, metrics.injected_items_total
        ),
        format!(
            "- `context_chars_injected_total={}`",
            metrics.context_chars_injected_total
        ),
        format!(
            "- `avg_pipeline_duration_ms={:.2}` / `total_pipeline_duration_ms={}`",
            metrics.avg_pipeline_duration_ms, metrics.pipeline_duration_ms_total
        ),
        format!(
            "- `injected_rate={:.3}` / `avg_selected_per_completed={:.3}` / `avg_injected_per_injected={:.3}`",
            metrics.injected_rate,
            metrics.avg_selected_per_completed,
            metrics.avg_injected_per_injected
        ),
        format!(
            "- `latency_buckets_ms`: `<=10:{}` `<=25:{}` `<=50:{}` `<=100:{}` `<=250:{}` `<=500:{}` `>500:{}`",
            metrics.latency_buckets.le_10ms,
            metrics.latency_buckets.le_25ms,
            metrics.latency_buckets.le_50ms,
            metrics.latency_buckets.le_100ms,
            metrics.latency_buckets.le_250ms,
            metrics.latency_buckets.le_500ms,
            metrics.latency_buckets.gt_500ms
        ),
    ]
}

pub(super) fn format_memory_recall_metrics_json(
    metrics: crate::agent::MemoryRecallMetricsSnapshot,
) -> serde_json::Value {
    json!({
        "captured_at_unix_ms": metrics.captured_at_unix_ms,
        "planned_total": metrics.planned_total,
        "injected_total": metrics.injected_total,
        "skipped_total": metrics.skipped_total,
        "completed_total": metrics.completed_total,
        "selected_total": metrics.selected_total,
        "injected_items_total": metrics.injected_items_total,
        "context_chars_injected_total": metrics.context_chars_injected_total,
        "pipeline_duration_ms_total": metrics.pipeline_duration_ms_total,
        "avg_pipeline_duration_ms": metrics.avg_pipeline_duration_ms,
        "avg_selected_per_completed": metrics.avg_selected_per_completed,
        "avg_injected_per_injected": metrics.avg_injected_per_injected,
        "injected_rate": metrics.injected_rate,
        "latency_buckets_ms": {
            "le_10ms": metrics.latency_buckets.le_10ms,
            "le_25ms": metrics.latency_buckets.le_25ms,
            "le_50ms": metrics.latency_buckets.le_50ms,
            "le_100ms": metrics.latency_buckets.le_100ms,
            "le_250ms": metrics.latency_buckets.le_250ms,
            "le_500ms": metrics.latency_buckets.le_500ms,
            "gt_500ms": metrics.latency_buckets.gt_500ms,
        },
    })
}
