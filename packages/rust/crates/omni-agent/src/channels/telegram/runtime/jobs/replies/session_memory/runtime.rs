use serde_json::json;

use super::super::shared::{
    format_optional_bool, format_optional_f32, format_optional_str, format_optional_string,
    format_optional_u32, format_optional_usize, format_yes_no,
};

pub(super) fn format_memory_runtime_status_lines(
    status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> Vec<String> {
    let backend_ready = memory_backend_ready(&status);
    vec![
        format!("- `memory_enabled={}`", format_yes_no(status.enabled)),
        format!(
            "- `configured_backend={}`",
            format_optional_string(status.configured_backend)
        ),
        format!(
            "- `active_backend={}`",
            format_optional_str(status.active_backend)
        ),
        format!(
            "- `strict_startup={}`",
            format_optional_bool(status.strict_startup)
        ),
        format!("- `startup_load_status={}`", status.startup_load_status),
        format!("- `backend_ready={}`", format_yes_no(backend_ready)),
        format!(
            "- `store_path={}`",
            format_optional_string(status.store_path)
        ),
        format!(
            "- `table_name={}`",
            format_optional_string(status.table_name)
        ),
        format!(
            "- `gate_promote_threshold={}`",
            format_optional_f32(status.gate_promote_threshold)
        ),
        format!(
            "- `gate_obsolete_threshold={}`",
            format_optional_f32(status.gate_obsolete_threshold)
        ),
        format!(
            "- `gate_promote_min_usage={}`",
            format_optional_u32(status.gate_promote_min_usage)
        ),
        format!(
            "- `gate_obsolete_min_usage={}`",
            format_optional_u32(status.gate_obsolete_min_usage)
        ),
        format!(
            "- `gate_promote_failure_rate_ceiling={}`",
            format_optional_f32(status.gate_promote_failure_rate_ceiling)
        ),
        format!(
            "- `gate_obsolete_failure_rate_floor={}`",
            format_optional_f32(status.gate_obsolete_failure_rate_floor)
        ),
        format!(
            "- `gate_promote_min_ttl_score={}`",
            format_optional_f32(status.gate_promote_min_ttl_score)
        ),
        format!(
            "- `gate_obsolete_max_ttl_score={}`",
            format_optional_f32(status.gate_obsolete_max_ttl_score)
        ),
        format!(
            "- `episodes_total={}`",
            format_optional_usize(status.episodes_total)
        ),
        format!(
            "- `q_values_total={}`",
            format_optional_usize(status.q_values_total)
        ),
    ]
}

pub(super) fn format_memory_runtime_status_json(
    status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> serde_json::Value {
    let backend_ready = memory_backend_ready(&status);
    json!({
        "memory_enabled": status.enabled,
        "configured_backend": status.configured_backend,
        "active_backend": status.active_backend,
        "strict_startup": status.strict_startup,
        "startup_load_status": status.startup_load_status,
        "backend_ready": backend_ready,
        "store_path": status.store_path,
        "table_name": status.table_name,
        "gate_promote_threshold": status.gate_promote_threshold,
        "gate_obsolete_threshold": status.gate_obsolete_threshold,
        "gate_promote_min_usage": status.gate_promote_min_usage,
        "gate_obsolete_min_usage": status.gate_obsolete_min_usage,
        "gate_promote_failure_rate_ceiling": status.gate_promote_failure_rate_ceiling,
        "gate_obsolete_failure_rate_floor": status.gate_obsolete_failure_rate_floor,
        "gate_promote_min_ttl_score": status.gate_promote_min_ttl_score,
        "gate_obsolete_max_ttl_score": status.gate_obsolete_max_ttl_score,
        "episodes_total": status.episodes_total,
        "q_values_total": status.q_values_total,
    })
}

pub(super) fn format_memory_gate_policy_compact_line(
    status: &crate::agent::MemoryRuntimeStatusSnapshot,
) -> String {
    format!(
        "- `promote(threshold={},min_usage={},max_failure_rate={},min_ttl={})` `obsolete(threshold={},min_usage={},min_failure_rate={},max_ttl={})`",
        format_optional_f32(status.gate_promote_threshold),
        format_optional_u32(status.gate_promote_min_usage),
        format_optional_f32(status.gate_promote_failure_rate_ceiling),
        format_optional_f32(status.gate_promote_min_ttl_score),
        format_optional_f32(status.gate_obsolete_threshold),
        format_optional_u32(status.gate_obsolete_min_usage),
        format_optional_f32(status.gate_obsolete_failure_rate_floor),
        format_optional_f32(status.gate_obsolete_max_ttl_score),
    )
}

pub(super) fn memory_backend_ready(status: &crate::agent::MemoryRuntimeStatusSnapshot) -> bool {
    status.enabled && status.active_backend.is_some() && status.startup_load_status == "loaded"
}
