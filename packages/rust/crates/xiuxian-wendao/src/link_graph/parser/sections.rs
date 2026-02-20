/// Parsed section row for section-aware retrieval.
#[derive(Debug, Clone)]
pub struct ParsedSection {
    pub heading_path: String,
    pub heading_path_lower: String,
    pub heading_level: usize,
    pub section_text: String,
    pub section_text_lower: String,
}

fn normalize_whitespace(raw: &str) -> String {
    raw.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn parse_markdown_heading(line: &str) -> Option<(usize, String)> {
    let trimmed = line.trim_start();
    if !trimmed.starts_with('#') {
        return None;
    }
    let mut level = 0usize;
    for ch in trimmed.chars() {
        if ch == '#' {
            level += 1;
        } else {
            break;
        }
    }
    if level == 0 || level > 6 {
        return None;
    }
    let rest = trimmed[level..].trim_start();
    if rest.is_empty() {
        return None;
    }
    Some((level, normalize_whitespace(rest)))
}

fn push_section(
    out: &mut Vec<ParsedSection>,
    heading_path: &str,
    heading_level: usize,
    lines: &[String],
) {
    let section_text = lines.join("\n").trim().to_string();
    if section_text.is_empty() && heading_path.trim().is_empty() {
        return;
    }
    out.push(ParsedSection {
        heading_path: heading_path.to_string(),
        heading_path_lower: heading_path.to_lowercase(),
        heading_level,
        section_text_lower: section_text.to_lowercase(),
        section_text,
    });
}

pub(super) fn extract_sections(body: &str) -> Vec<ParsedSection> {
    let mut sections: Vec<ParsedSection> = Vec::new();
    let mut heading_stack: Vec<String> = Vec::new();
    let mut current_heading_path = String::new();
    let mut current_heading_level = 0usize;
    let mut current_lines: Vec<String> = Vec::new();
    let mut in_code_fence = false;

    for line in body.lines() {
        let trimmed = line.trim_start();
        if trimmed.starts_with("```") || trimmed.starts_with("~~~") {
            in_code_fence = !in_code_fence;
            current_lines.push(line.to_string());
            continue;
        }
        if !in_code_fence && let Some((level, heading)) = parse_markdown_heading(trimmed) {
            push_section(
                &mut sections,
                &current_heading_path,
                current_heading_level,
                &current_lines,
            );
            current_lines.clear();
            if heading_stack.len() >= level {
                heading_stack.truncate(level.saturating_sub(1));
            }
            heading_stack.push(heading);
            current_heading_path = heading_stack.join(" / ");
            current_heading_level = level;
            continue;
        }
        current_lines.push(line.to_string());
    }

    push_section(
        &mut sections,
        &current_heading_path,
        current_heading_level,
        &current_lines,
    );
    if sections.is_empty() {
        let section_text = body.trim().to_string();
        sections.push(ParsedSection {
            heading_path: String::new(),
            heading_path_lower: String::new(),
            heading_level: 0,
            section_text_lower: section_text.to_lowercase(),
            section_text,
        });
    }
    sections
}
