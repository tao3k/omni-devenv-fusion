use regex::Regex;
use serde_yaml::Value;
use std::sync::LazyLock;

fn compile_regex(pattern: &str) -> Regex {
    match Regex::new(pattern) {
        Ok(regex) => regex,
        Err(_compile_err) => match Regex::new(r"$^") {
            Ok(fallback) => fallback,
            Err(fallback_err) => panic!("hardcoded fallback regex must compile: {fallback_err}"),
        },
    }
}

static FRONTMATTER_REGEX: LazyLock<Regex> =
    LazyLock::new(|| compile_regex(r"(?s)\A---\s*\n(.*?)\n(?:---|\.\.\.)\s*\n?"));

fn normalize_whitespace(raw: &str) -> String {
    raw.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn value_to_non_negative_f64(value: &Value) -> Option<f64> {
    match value {
        Value::Number(number) => number.as_f64().filter(|v| v.is_finite() && *v >= 0.0),
        Value::String(raw) => raw
            .trim()
            .parse::<f64>()
            .ok()
            .filter(|v| v.is_finite() && *v >= 0.0),
        _ => None,
    }
}

pub(super) fn parse_frontmatter(content: &str) -> (Option<Value>, &str) {
    let Some(caps) = FRONTMATTER_REGEX.captures(content) else {
        return (None, content);
    };
    let body = caps.get(0).map_or(content, |m| &content[m.end()..]);
    let parsed = caps
        .get(1)
        .and_then(|m| serde_yaml::from_str::<Value>(m.as_str()).ok());
    (parsed, body)
}

pub(super) fn extract_tags(frontmatter: Option<&Value>) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let Some(value) = frontmatter else {
        return out;
    };
    let Some(tags_val) = value.get("tags") else {
        return out;
    };
    match tags_val {
        Value::String(s) => {
            let tag = s.trim();
            if !tag.is_empty() {
                out.push(tag.to_string());
            }
        }
        Value::Sequence(seq) => {
            for item in seq {
                if let Some(tag) = item.as_str() {
                    let cleaned = tag.trim();
                    if !cleaned.is_empty() {
                        out.push(cleaned.to_string());
                    }
                }
            }
        }
        _ => {}
    }
    out.sort();
    out.dedup();
    out
}

pub(super) fn extract_title(
    frontmatter: Option<&Value>,
    body: &str,
    fallback_stem: &str,
) -> String {
    if let Some(value) = frontmatter {
        let frontmatter_title = value
            .get("title")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty());
        if let Some(title) = frontmatter_title {
            return title.to_string();
        }
    }

    for line in body.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix("# ") {
            let candidate = rest.trim();
            if !candidate.is_empty() {
                return candidate.to_string();
            }
        }
    }
    fallback_stem.to_string()
}

pub(super) fn extract_saliency_params(frontmatter: Option<&Value>) -> (f64, f64) {
    let default_base = crate::link_graph::saliency::DEFAULT_SALIENCY_BASE;
    let default_decay = crate::link_graph::saliency::DEFAULT_DECAY_RATE;
    let Some(frontmatter) = frontmatter else {
        return (default_base, default_decay);
    };

    let saliency_base = frontmatter
        .get("saliency_base")
        .and_then(value_to_non_negative_f64)
        .unwrap_or(default_base);
    let decay_rate = frontmatter
        .get("decay_rate")
        .and_then(value_to_non_negative_f64)
        .unwrap_or(default_decay);

    (saliency_base, decay_rate)
}

pub(super) fn extract_lead(body: &str) -> String {
    for line in body.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') || trimmed.starts_with("```") {
            continue;
        }
        let lead = normalize_whitespace(trimmed);
        if lead.is_empty() {
            continue;
        }
        return lead.chars().take(180).collect();
    }
    String::new()
}

pub(super) fn count_words(body: &str) -> usize {
    body.split_whitespace().count()
}
