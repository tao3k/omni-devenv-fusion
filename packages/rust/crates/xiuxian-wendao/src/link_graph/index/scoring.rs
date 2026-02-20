use super::LinkGraphDocument;
use regex::Regex;

pub(super) fn section_heading_parts(heading_path: &str) -> Vec<&str> {
    heading_path
        .split(" / ")
        .map(str::trim)
        .filter(|part| !part.is_empty())
        .collect()
}

pub(super) fn section_tree_distance(left_heading: &str, right_heading: &str) -> usize {
    let left = section_heading_parts(left_heading);
    let right = section_heading_parts(right_heading);
    if left.is_empty() || right.is_empty() {
        return if left.is_empty() && right.is_empty() {
            0
        } else {
            usize::MAX
        };
    }

    let mut lca_len = 0usize;
    let min_len = left.len().min(right.len());
    while lca_len < min_len && left[lca_len] == right[lca_len] {
        lca_len += 1;
    }
    (left.len() - lca_len) + (right.len() - lca_len)
}

pub(super) fn normalize_with_case(value: &str, case_sensitive: bool) -> String {
    if case_sensitive {
        value.to_string()
    } else {
        value.to_lowercase()
    }
}

pub(super) fn tokenize(value: &str, case_sensitive: bool) -> Vec<String> {
    value
        .split(|c: char| !(c.is_ascii_alphanumeric() || c == '_' || c == '-'))
        .map(str::trim)
        .filter(|t| !t.is_empty())
        .map(|token| normalize_with_case(token, case_sensitive))
        .collect()
}

fn doc_contains_token(doc: &LinkGraphDocument, token: &str, case_sensitive: bool) -> bool {
    if token.is_empty() {
        return false;
    }
    if case_sensitive {
        doc.id.contains(token)
            || doc.stem.contains(token)
            || doc.title.contains(token)
            || doc.path.contains(token)
            || doc.tags.iter().any(|tag| tag.contains(token))
            || doc.search_text.contains(token)
    } else {
        doc.id_lower.contains(token)
            || doc.stem_lower.contains(token)
            || doc.title_lower.contains(token)
            || doc.path_lower.contains(token)
            || doc.tags_lower.iter().any(|tag| tag.contains(token))
            || doc.search_text_lower.contains(token)
    }
}

pub(super) fn score_document(
    doc: &LinkGraphDocument,
    query: &str,
    query_tokens: &[String],
    case_sensitive: bool,
) -> f64 {
    if query.is_empty() {
        return 0.0;
    }
    let (id_value, stem_value, title_value, path_value, content_value, tags_value): (
        &str,
        &str,
        &str,
        &str,
        &str,
        &[String],
    ) = if case_sensitive {
        (
            doc.id.as_str(),
            doc.stem.as_str(),
            doc.title.as_str(),
            doc.path.as_str(),
            doc.search_text.as_str(),
            doc.tags.as_slice(),
        )
    } else {
        (
            doc.id_lower.as_str(),
            doc.stem_lower.as_str(),
            doc.title_lower.as_str(),
            doc.path_lower.as_str(),
            doc.search_text_lower.as_str(),
            doc.tags_lower.as_slice(),
        )
    };

    let mut score: f64 = 0.0;
    if id_value == query || stem_value == query {
        score = score.max(1.0);
    }
    if title_value == query {
        score = score.max(0.95);
    }
    if tags_value.iter().any(|tag| tag == query) {
        score = score.max(0.85);
    }
    if id_value.contains(query)
        || stem_value.contains(query)
        || title_value.contains(query)
        || path_value.contains(query)
        || tags_value.iter().any(|tag| tag.contains(query))
        || content_value.contains(query)
    {
        score = score.max(0.7);
    }

    if !query_tokens.is_empty() {
        let mut matched = 0usize;
        for token in query_tokens {
            if token.is_empty() {
                continue;
            }
            if doc_contains_token(doc, token, case_sensitive) {
                matched += 1;
            }
        }
        if matched > 0 {
            let ratio = matched as f64 / query_tokens.len() as f64;
            score = score.max(0.45 + ratio * 0.45);
        }
    }
    score.clamp(0.0, 1.0)
}

pub(super) fn token_match_ratio(haystack: &str, query_tokens: &[String]) -> f64 {
    if query_tokens.is_empty() {
        return 0.0;
    }
    let mut matched = 0usize;
    for token in query_tokens {
        if token.is_empty() {
            continue;
        }
        if haystack.contains(token) {
            matched += 1;
        }
    }
    (matched as f64 / query_tokens.len() as f64).clamp(0.0, 1.0)
}

pub(super) fn score_path_fields(
    doc: &LinkGraphDocument,
    query: &str,
    query_tokens: &[String],
    case_sensitive: bool,
) -> f64 {
    if query.is_empty() {
        return 0.0;
    }
    let (id_value, stem_value, title_value, path_value): (&str, &str, &str, &str) =
        if case_sensitive {
            (
                doc.id.as_str(),
                doc.stem.as_str(),
                doc.title.as_str(),
                doc.path.as_str(),
            )
        } else {
            (
                doc.id_lower.as_str(),
                doc.stem_lower.as_str(),
                doc.title_lower.as_str(),
                doc.path_lower.as_str(),
            )
        };

    let mut score = 0.0_f64;
    if path_value == query || id_value == query || stem_value == query {
        score = score.max(1.0);
    } else if title_value == query {
        score = score.max(0.95);
    }

    if path_value.contains(query)
        || id_value.contains(query)
        || stem_value.contains(query)
        || title_value.contains(query)
    {
        score = score.max(0.82);
    }

    let path_blob = format!("{path_value} {id_value} {stem_value} {title_value}");
    let token_ratio = token_match_ratio(&path_blob, query_tokens);
    if token_ratio > 0.0 {
        score = score.max(0.50 + token_ratio * 0.45);
    }
    score.clamp(0.0, 1.0)
}

pub(super) fn score_document_exact(
    doc: &LinkGraphDocument,
    query: &str,
    case_sensitive: bool,
) -> f64 {
    if query.is_empty() {
        return 0.0;
    }
    let (id_value, stem_value, title_value, path_value, tags_value): (
        &str,
        &str,
        &str,
        &str,
        &[String],
    ) = if case_sensitive {
        (
            doc.id.as_str(),
            doc.stem.as_str(),
            doc.title.as_str(),
            doc.path.as_str(),
            doc.tags.as_slice(),
        )
    } else {
        (
            doc.id_lower.as_str(),
            doc.stem_lower.as_str(),
            doc.title_lower.as_str(),
            doc.path_lower.as_str(),
            doc.tags_lower.as_slice(),
        )
    };

    if id_value == query || stem_value == query {
        return 1.0;
    }
    if title_value == query {
        return 0.95;
    }
    if tags_value.iter().any(|tag| tag == query) {
        return 0.85;
    }
    if path_value == query {
        return 0.8;
    }
    if (case_sensitive && doc.search_text.contains(query))
        || (!case_sensitive && doc.search_text_lower.contains(query))
    {
        return 0.75;
    }
    0.0
}

pub(super) fn score_document_regex(doc: &LinkGraphDocument, regex: &Regex) -> f64 {
    if regex.is_match(&doc.id) || regex.is_match(&doc.stem) {
        return 1.0;
    }
    if regex.is_match(&doc.title) {
        return 0.95;
    }
    if regex.is_match(&doc.path) {
        return 0.8;
    }
    if doc.tags.iter().any(|tag| regex.is_match(tag)) {
        return 0.85;
    }
    if regex.is_match(&doc.search_text) {
        return 0.75;
    }
    0.0
}
