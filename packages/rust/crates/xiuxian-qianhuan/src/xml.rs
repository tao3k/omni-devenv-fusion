use crate::{InjectionError, QaEntry};

/// Root XML tag for system prompt injection payloads.
pub const SYSTEM_PROMPT_INJECTION_TAG: &str = "system_prompt_injection";

const QA_TAG: &str = "qa";
const QUESTION_TAG: &str = "q";
const ANSWER_TAG: &str = "a";
const SOURCE_TAG: &str = "source";

pub(crate) fn parse_qa_entries(raw: &str) -> Result<Vec<QaEntry>, InjectionError> {
    let payload = raw.trim();
    if payload.is_empty() {
        return Err(InjectionError::EmptyPayload);
    }

    let mut entries = extract_tag_blocks(payload, QA_TAG)
        .into_iter()
        .map(|block| parse_qa_block(&block))
        .collect::<Result<Vec<_>, _>>()?;

    if entries.is_empty()
        && (extract_tag(payload, QUESTION_TAG).is_some()
            || extract_tag(payload, ANSWER_TAG).is_some())
    {
        entries.push(parse_qa_block(payload)?);
    }

    if entries.is_empty() {
        return Err(InjectionError::MissingQaBlock);
    }
    Ok(entries)
}

pub(crate) fn render_xml(entries: impl Iterator<Item = QaEntry>) -> String {
    let mut lines = vec![format!("<{SYSTEM_PROMPT_INJECTION_TAG}>")];
    for entry in entries {
        lines.push("  <qa>".to_string());
        lines.push(format!("    <q>{}</q>", escape_xml(entry.question.trim())));
        lines.push(format!("    <a>{}</a>", escape_xml(entry.answer.trim())));
        if let Some(source) = entry.source.as_deref().map(str::trim)
            && !source.is_empty()
        {
            lines.push(format!("    <source>{}</source>", escape_xml(source)));
        }
        lines.push("  </qa>".to_string());
    }
    lines.push(format!("</{SYSTEM_PROMPT_INJECTION_TAG}>"));
    lines.join("\n")
}

fn parse_qa_block(block: &str) -> Result<QaEntry, InjectionError> {
    let question = extract_tag(block, QUESTION_TAG).unwrap_or_default();
    if question.trim().is_empty() {
        return Err(InjectionError::MissingQuestion);
    }
    let answer = extract_tag(block, ANSWER_TAG).unwrap_or_default();
    if answer.trim().is_empty() {
        return Err(InjectionError::MissingAnswer);
    }
    let source = extract_tag(block, SOURCE_TAG).map(|value| value.trim().to_string());
    Ok(QaEntry {
        question: question.trim().to_string(),
        answer: answer.trim().to_string(),
        source: source.filter(|value| !value.is_empty()),
    })
}

fn extract_tag(input: &str, tag: &str) -> Option<String> {
    let start_marker = format!("<{tag}>");
    let end_marker = format!("</{tag}>");
    let start = input.find(&start_marker)?;
    let after_start = &input[start + start_marker.len()..];
    let end = after_start.find(&end_marker)?;
    Some(after_start[..end].trim().to_string())
}

fn extract_tag_blocks(input: &str, tag: &str) -> Vec<String> {
    let start_marker = format!("<{tag}>");
    let end_marker = format!("</{tag}>");
    let mut result = Vec::new();
    let mut cursor = input;

    while let Some(start) = cursor.find(&start_marker) {
        let after_start = &cursor[start + start_marker.len()..];
        let Some(end) = after_start.find(&end_marker) else {
            break;
        };
        result.push(after_start[..end].trim().to_string());
        cursor = &after_start[end + end_marker.len()..];
    }

    result
}

fn escape_xml(input: &str) -> String {
    let mut escaped = String::with_capacity(input.len());
    for ch in input.chars() {
        match ch {
            '&' => escaped.push_str("&amp;"),
            '<' => escaped.push_str("&lt;"),
            '>' => escaped.push_str("&gt;"),
            '"' => escaped.push_str("&quot;"),
            '\'' => escaped.push_str("&apos;"),
            _ => escaped.push(ch),
        }
    }
    escaped
}
