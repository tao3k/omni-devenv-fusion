use chrono::{DateTime, NaiveDate, TimeZone, Utc};
use serde_yaml::Value;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

fn system_time_to_unix(ts: SystemTime) -> Option<i64> {
    let seconds = ts.duration_since(UNIX_EPOCH).ok()?.as_secs();
    i64::try_from(seconds).ok()
}

fn parse_timestamp_value(value: &Value) -> Option<i64> {
    match value {
        Value::Number(num) => num
            .as_i64()
            .or_else(|| num.as_u64().and_then(|v| i64::try_from(v).ok())),
        Value::String(raw) => {
            let trimmed = raw.trim();
            if trimmed.is_empty() {
                return None;
            }
            if let Ok(epoch) = trimmed.parse::<i64>() {
                return Some(epoch);
            }
            if let Ok(dt) = DateTime::parse_from_rfc3339(trimmed) {
                return Some(dt.timestamp());
            }
            if let Ok(date) = NaiveDate::parse_from_str(trimmed, "%Y-%m-%d") {
                return date
                    .and_hms_opt(0, 0, 0)
                    .map(|naive| Utc.from_utc_datetime(&naive).timestamp());
            }
            if let Ok(date) = NaiveDate::parse_from_str(trimmed, "%Y/%m/%d") {
                return date
                    .and_hms_opt(0, 0, 0)
                    .map(|naive| Utc.from_utc_datetime(&naive).timestamp());
            }
            None
        }
        _ => None,
    }
}

fn extract_frontmatter_timestamp(frontmatter: Option<&Value>, keys: &[&str]) -> Option<i64> {
    let value = frontmatter?;
    for key in keys {
        let Some(raw) = value.get(*key) else {
            continue;
        };
        if let Some(parsed) = parse_timestamp_value(raw) {
            return Some(parsed);
        }
    }
    None
}

fn extract_filesystem_timestamps(path: &Path) -> (Option<i64>, Option<i64>) {
    let Ok(meta) = std::fs::metadata(path) else {
        return (None, None);
    };
    let created = meta.created().ok().and_then(system_time_to_unix);
    let modified = meta.modified().ok().and_then(system_time_to_unix);
    (created, modified)
}

pub(super) fn resolve_note_timestamps(
    frontmatter: Option<&Value>,
    path: &Path,
) -> (Option<i64>, Option<i64>) {
    let frontmatter_created =
        extract_frontmatter_timestamp(frontmatter, &["created", "created_at", "date"]);
    let frontmatter_modified = extract_frontmatter_timestamp(
        frontmatter,
        &["modified", "modified_at", "updated", "updated_at"],
    );
    let (filesystem_created, filesystem_modified) = extract_filesystem_timestamps(path);
    (
        frontmatter_created.or(filesystem_created),
        frontmatter_modified.or(filesystem_modified),
    )
}
