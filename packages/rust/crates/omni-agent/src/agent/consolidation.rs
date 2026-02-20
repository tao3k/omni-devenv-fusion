/// Build intent (first user message), experience (assistant responses joined), outcome (completed/error).
#[doc(hidden)]
pub fn summarise_drained_turns(drained: &[(String, String, u32)]) -> (String, String, String) {
    let intent = drained
        .iter()
        .find(|(role, _, _)| role == "user")
        .map(|(_, c, _)| c.as_str())
        .unwrap_or("(no user message)")
        .to_string();
    let experience: String = drained
        .iter()
        .filter(|(role, _, _)| role == "assistant")
        .map(|(_, c, _)| c.as_str())
        .collect::<Vec<_>>()
        .join("\n\n");
    let experience = if experience.is_empty() {
        "(no assistant response)".to_string()
    } else {
        experience
    };
    let has_error = drained.iter().any(|(_, c, _)| {
        let lower = c.to_lowercase();
        lower.contains("error") || lower.contains("failed") || lower.contains("exception")
    });
    let outcome = if has_error {
        "error".to_string()
    } else {
        "completed".to_string()
    };
    (intent, experience, outcome)
}

pub(crate) fn build_consolidated_summary_text(
    intent: &str,
    experience: &str,
    outcome: &str,
) -> String {
    let intent = compact_single_line(intent, 180);
    let experience = compact_single_line(experience, 220);
    format!(
        "Outcome={outcome}; intent={intent}; assistant={experience}",
        outcome = outcome.trim(),
        intent = intent,
        experience = experience
    )
}

fn compact_single_line(input: &str, max_chars: usize) -> String {
    let normalized = input.split_whitespace().collect::<Vec<_>>().join(" ");
    if normalized.chars().count() <= max_chars {
        return normalized;
    }
    let keep = max_chars.saturating_sub(3);
    let mut out = normalized.chars().take(keep).collect::<String>();
    out.push_str("...");
    out
}

pub(crate) fn now_unix_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}
