#[derive(Debug)]
pub(super) struct JsonReplySummary {
    pub(super) kind: Option<String>,
    pub(super) available: Option<bool>,
    pub(super) status: Option<String>,
    pub(super) found: Option<bool>,
    pub(super) decision: Option<String>,
    pub(super) logical_session_id: Option<String>,
    pub(super) partition_key: Option<String>,
    pub(super) partition_mode: Option<String>,
    pub(super) context_mode: Option<String>,
    pub(super) saved_snapshot_status: Option<String>,
    pub(super) runtime_backend_ready: Option<bool>,
    pub(super) runtime_active_backend: Option<String>,
    pub(super) runtime_startup_load_status: Option<String>,
    pub(super) result_recalled_injected: Option<u64>,
    pub(super) query_tokens: Option<u64>,
    pub(super) override_admin_count: Option<usize>,
    pub(super) keys: usize,
}

pub(super) fn summarize_json_reply(message: &str) -> Option<JsonReplySummary> {
    let value: serde_json::Value = serde_json::from_str(message).ok()?;
    let object = value.as_object()?;
    let saved_snapshot = object
        .get("saved_snapshot")
        .and_then(serde_json::Value::as_object);
    let runtime = object.get("runtime").and_then(serde_json::Value::as_object);
    let result = object.get("result").and_then(serde_json::Value::as_object);
    let override_admin_count = match object.get("override_admin_users") {
        Some(serde_json::Value::Array(entries)) => Some(entries.len()),
        Some(serde_json::Value::Null) => Some(0),
        _ => None,
    };
    Some(JsonReplySummary {
        kind: object
            .get("kind")
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        available: object.get("available").and_then(serde_json::Value::as_bool),
        status: object
            .get("status")
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        found: object.get("found").and_then(serde_json::Value::as_bool),
        decision: object
            .get("decision")
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        logical_session_id: object
            .get("logical_session_id")
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        partition_key: object
            .get("partition_key")
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        partition_mode: object
            .get("partition_mode")
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        context_mode: object
            .get("mode")
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        saved_snapshot_status: saved_snapshot
            .and_then(|snapshot| snapshot.get("status"))
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        runtime_backend_ready: runtime
            .as_ref()
            .and_then(|runtime_obj| runtime_obj.get("backend_ready"))
            .and_then(serde_json::Value::as_bool),
        runtime_active_backend: runtime
            .as_ref()
            .and_then(|runtime_obj| runtime_obj.get("active_backend"))
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        runtime_startup_load_status: runtime
            .as_ref()
            .and_then(|runtime_obj| runtime_obj.get("startup_load_status"))
            .and_then(serde_json::Value::as_str)
            .map(ToString::to_string),
        result_recalled_injected: result
            .and_then(|result_obj| result_obj.get("recalled_injected"))
            .and_then(serde_json::Value::as_u64),
        query_tokens: object
            .get("query_tokens")
            .and_then(serde_json::Value::as_u64),
        override_admin_count,
        keys: object.len(),
    })
}

pub(super) fn optional_bool_token(value: Option<bool>) -> &'static str {
    match value {
        Some(true) => "true",
        Some(false) => "false",
        None => "",
    }
}

pub(super) fn optional_u64_token(value: Option<u64>) -> String {
    value.map(|value| value.to_string()).unwrap_or_default()
}

pub(super) fn optional_usize_token(value: Option<usize>) -> String {
    value.map(|value| value.to_string()).unwrap_or_default()
}
