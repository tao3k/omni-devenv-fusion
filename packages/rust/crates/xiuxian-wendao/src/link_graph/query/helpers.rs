use super::super::models::{
    LinkGraphEdgeType, LinkGraphMatchStrategy, LinkGraphScope, LinkGraphSortField,
    LinkGraphSortOrder, LinkGraphSortTerm,
};
use chrono::{DateTime, NaiveDate, TimeZone, Utc};

pub(super) fn split_terms_preserving_quotes(raw: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut quote: Option<char> = None;

    for ch in raw.chars() {
        if let Some(active) = quote {
            if ch == active {
                quote = None;
            } else {
                current.push(ch);
            }
            continue;
        }
        if ch == '"' || ch == '\'' {
            quote = Some(ch);
            continue;
        }
        if ch.is_whitespace() {
            if !current.is_empty() {
                out.push(current.clone());
                current.clear();
            }
            continue;
        }
        current.push(ch);
    }

    if !current.is_empty() {
        out.push(current);
    }
    out
}

pub(super) fn parse_bool(raw: &str) -> Option<bool> {
    match raw.trim().to_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => None,
    }
}

pub(super) fn parse_scope(raw: &str) -> Option<LinkGraphScope> {
    match raw.trim().to_lowercase().as_str() {
        "doc" | "doc_only" => Some(LinkGraphScope::DocOnly),
        "section" | "section_only" => Some(LinkGraphScope::SectionOnly),
        "mixed" => Some(LinkGraphScope::Mixed),
        _ => None,
    }
}

pub(super) fn parse_edge_type(raw: &str) -> Option<LinkGraphEdgeType> {
    match raw.trim().to_lowercase().as_str() {
        "structural" => Some(LinkGraphEdgeType::Structural),
        "semantic" => Some(LinkGraphEdgeType::Semantic),
        "provisional" => Some(LinkGraphEdgeType::Provisional),
        "verified" => Some(LinkGraphEdgeType::Verified),
        _ => None,
    }
}

pub(super) fn parse_timestamp(raw: &str) -> Option<i64> {
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

pub(super) fn normalize_boolean_operators(raw: &str) -> String {
    let mut text = raw.trim().replace("||", "|").replace("&&", "&");
    for (from, to) in [
        (" OR ", " | "),
        (" and ", " & "),
        (" AND ", " & "),
        (" or ", " | "),
        (" not ", " !"),
        (" NOT ", " !"),
    ] {
        text = text.replace(from, to);
    }
    text
}

pub(super) fn split_top_level(raw: &str, separators: &[char]) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut quote: Option<char> = None;
    let mut depth: i32 = 0;

    for ch in raw.chars() {
        if let Some(active) = quote {
            if ch == active {
                quote = None;
            } else {
                current.push(ch);
            }
            continue;
        }

        if ch == '"' || ch == '\'' {
            quote = Some(ch);
            continue;
        }

        if ch == '(' {
            depth += 1;
            current.push(ch);
            continue;
        }
        if ch == ')' {
            depth = (depth - 1).max(0);
            current.push(ch);
            continue;
        }

        if depth == 0 && separators.contains(&ch) {
            let token = current.trim();
            if !token.is_empty() {
                out.push(token.to_string());
            }
            current.clear();
            continue;
        }

        current.push(ch);
    }

    let token = current.trim();
    if !token.is_empty() {
        out.push(token.to_string());
    }
    out
}

pub(super) fn has_balanced_outer_parens(raw: &str) -> bool {
    let text = raw.trim();
    if text.len() < 2 || !text.starts_with('(') || !text.ends_with(')') {
        return false;
    }
    let mut depth: i32 = 0;
    let mut quote: Option<char> = None;
    for (idx, ch) in text.char_indices() {
        if let Some(active) = quote {
            if ch == active {
                quote = None;
            }
            continue;
        }
        if ch == '"' || ch == '\'' {
            quote = Some(ch);
            continue;
        }
        if ch == '(' {
            depth += 1;
        } else if ch == ')' {
            depth -= 1;
            if depth < 0 {
                return false;
            }
            if depth == 0 && idx < text.len() - 1 {
                return false;
            }
        }
    }
    depth == 0
}

pub(super) fn strip_outer_parens(raw: &str) -> String {
    let mut text = raw.trim().to_string();
    while has_balanced_outer_parens(&text) {
        text = text[1..text.len().saturating_sub(1)].trim().to_string();
    }
    text
}

pub(super) fn parse_list_values(raw: &str) -> Vec<String> {
    let normalized = normalize_boolean_operators(raw);
    split_top_level(&normalized, &[',', '|', ';', '&'])
        .into_iter()
        .map(|item| strip_outer_parens(&item))
        .map(|item| {
            item.trim()
                .trim_matches('"')
                .trim_matches('\'')
                .trim()
                .to_string()
        })
        .filter(|item| !item.is_empty())
        .collect()
}

pub(super) fn parse_tag_atom(raw: &str) -> Option<(bool, String)> {
    let mut token = strip_outer_parens(raw).trim().to_string();
    if token.is_empty() {
        return None;
    }

    let mut is_not = false;
    if let Some(rest) = token.strip_prefix('!').or_else(|| token.strip_prefix('-')) {
        is_not = true;
        token = rest.trim().to_string();
    } else if token.len() >= 4 && token[..4].eq_ignore_ascii_case("not ") {
        is_not = true;
        token = token[4..].trim().to_string();
    }

    token = strip_outer_parens(&token)
        .trim()
        .trim_matches('"')
        .trim_matches('\'')
        .trim()
        .to_string();
    if token.is_empty() {
        return None;
    }
    Some((is_not, token))
}

pub(super) fn push_unique_many(dst: &mut Vec<String>, values: Vec<String>) {
    for value in values {
        if !dst
            .iter()
            .any(|existing| existing.eq_ignore_ascii_case(&value))
        {
            dst.push(value);
        }
    }
}

pub(super) fn looks_like_regex(query: &str) -> bool {
    let q = query.trim();
    if q.is_empty() {
        return false;
    }
    q.starts_with('^')
        || q.ends_with('$')
        || q.contains(".*")
        || q.contains('[')
        || q.contains('(')
        || q.contains('\\')
}

pub(super) fn looks_machine_like(query: &str) -> bool {
    let q = query.trim().to_lowercase();
    if q.is_empty() {
        return false;
    }
    let is_slugish = q
        .chars()
        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_' || c == '-');
    let has_signal = q.chars().any(|c| c.is_ascii_digit()) || q.contains('_') || q.contains('-');
    let has_note_suffix = [".md", ".mdx", ".markdown"].iter().any(|ext| {
        if !q.ends_with(ext) {
            return false;
        }
        let prefix_len = q.len().saturating_sub(ext.len());
        if prefix_len == 0 {
            return false;
        }
        q[..prefix_len]
            .chars()
            .any(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
    });
    let pathish = q.contains('/') || has_note_suffix;
    (is_slugish && (has_signal || q.len() >= 24)) || pathish
}

pub(super) fn parse_time_filter(
    token: &str,
    created_after: &mut Option<i64>,
    created_before: &mut Option<i64>,
    modified_after: &mut Option<i64>,
    modified_before: &mut Option<i64>,
) -> bool {
    let lower = token.trim().to_lowercase();
    let rules = [
        ("created>=", "created_after"),
        ("created<=", "created_before"),
        ("created>", "created_after"),
        ("created<", "created_before"),
        ("modified>=", "modified_after"),
        ("modified<=", "modified_before"),
        ("modified>", "modified_after"),
        ("modified<", "modified_before"),
        ("updated>=", "modified_after"),
        ("updated<=", "modified_before"),
        ("updated>", "modified_after"),
        ("updated<", "modified_before"),
    ];
    for (prefix, slot) in rules {
        if !lower.starts_with(prefix) {
            continue;
        }
        let value = token[prefix.len()..].trim().trim_start_matches(':');
        let Some(parsed) = parse_timestamp(value) else {
            return false;
        };
        match slot {
            "created_after" => *created_after = Some(parsed),
            "created_before" => *created_before = Some(parsed),
            "modified_after" => *modified_after = Some(parsed),
            "modified_before" => *modified_before = Some(parsed),
            _ => {}
        }
        return true;
    }
    false
}

pub(super) fn parse_sort_field(raw: &str) -> Option<LinkGraphSortField> {
    match raw.trim().to_lowercase().replace('-', "_").as_str() {
        "score" => Some(LinkGraphSortField::Score),
        "path" => Some(LinkGraphSortField::Path),
        "title" => Some(LinkGraphSortField::Title),
        "stem" => Some(LinkGraphSortField::Stem),
        "created" => Some(LinkGraphSortField::Created),
        "modified" | "updated" => Some(LinkGraphSortField::Modified),
        "random" => Some(LinkGraphSortField::Random),
        "word_count" => Some(LinkGraphSortField::WordCount),
        _ => None,
    }
}

pub(super) fn parse_sort_order(raw: &str) -> Option<LinkGraphSortOrder> {
    match raw.trim().to_lowercase().as_str() {
        "asc" | "+" => Some(LinkGraphSortOrder::Asc),
        "desc" | "-" => Some(LinkGraphSortOrder::Desc),
        _ => None,
    }
}

pub(super) fn default_order_for_field(field: LinkGraphSortField) -> LinkGraphSortOrder {
    match field {
        LinkGraphSortField::Path
        | LinkGraphSortField::Title
        | LinkGraphSortField::Stem
        | LinkGraphSortField::Random => LinkGraphSortOrder::Asc,
        LinkGraphSortField::Score
        | LinkGraphSortField::Created
        | LinkGraphSortField::Modified
        | LinkGraphSortField::WordCount => LinkGraphSortOrder::Desc,
    }
}

pub(super) fn parse_sort_term(raw: &str) -> LinkGraphSortTerm {
    let value = raw.trim().to_lowercase().replace('-', "_");
    if value.is_empty() {
        return LinkGraphSortTerm::default();
    }

    let pair = value
        .split_once(':')
        .or_else(|| value.split_once('/'))
        .or_else(|| value.rsplit_once('_'));
    if let Some((field_raw, order_raw)) = pair
        && let (Some(field), Some(order)) =
            (parse_sort_field(field_raw), parse_sort_order(order_raw))
    {
        return LinkGraphSortTerm { field, order };
    }

    if let Some(field) = parse_sort_field(&value) {
        return LinkGraphSortTerm {
            field,
            order: default_order_for_field(field),
        };
    }

    LinkGraphSortTerm::default()
}

pub(super) fn parse_tag_expression(
    raw: &str,
    tags_all: &mut Vec<String>,
    tags_any: &mut Vec<String>,
    tags_not: &mut Vec<String>,
) {
    let normalized = strip_outer_parens(&normalize_boolean_operators(raw));
    if normalized.trim().is_empty() {
        return;
    }
    let or_groups = split_top_level(&normalized, &['|']);
    let has_or = or_groups.len() > 1;
    for group in or_groups {
        for part in split_top_level(&group, &[',', '&']) {
            let Some((is_not, cleaned)) = parse_tag_atom(&part) else {
                continue;
            };
            if is_not {
                push_unique_many(tags_not, vec![cleaned]);
            } else if has_or {
                push_unique_many(tags_any, vec![cleaned]);
            } else {
                push_unique_many(tags_all, vec![cleaned]);
            }
        }
    }
}

pub(super) fn paren_balance(raw: &str) -> i32 {
    let mut depth: i32 = 0;
    let mut quote: Option<char> = None;
    for ch in raw.chars() {
        if let Some(active) = quote {
            if ch == active {
                quote = None;
            }
            continue;
        }
        if ch == '"' || ch == '\'' {
            quote = Some(ch);
            continue;
        }
        if ch == '(' {
            depth += 1;
        } else if ch == ')' {
            depth -= 1;
        }
    }
    depth
}

pub(super) fn is_boolean_connector_token(raw: &str) -> bool {
    let token = raw.trim();
    token == "&"
        || token == "|"
        || token.eq_ignore_ascii_case("and")
        || token.eq_ignore_ascii_case("or")
}

pub(super) fn parse_directive_key(raw_key: &str) -> (bool, String) {
    let mut token = raw_key.trim();
    let mut negate = false;
    while let Some(rest) = token.strip_prefix('-').or_else(|| token.strip_prefix('!')) {
        negate = !negate;
        token = rest.trim_start();
    }
    (negate, token.to_lowercase())
}

pub(super) fn is_default_sort_terms(terms: &[LinkGraphSortTerm]) -> bool {
    terms.is_empty() || (terms.len() == 1 && terms[0] == LinkGraphSortTerm::default())
}

pub(super) fn infer_strategy_from_residual(query: &str) -> Option<LinkGraphMatchStrategy> {
    if looks_like_regex(query) {
        Some(LinkGraphMatchStrategy::Re)
    } else if looks_machine_like(query) {
        Some(LinkGraphMatchStrategy::Exact)
    } else {
        None
    }
}
