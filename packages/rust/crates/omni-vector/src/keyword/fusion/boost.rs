//! Field and metadata boosting helpers for weighted RRF.

use crate::ToolSearchResult;

/// Boost score from metadata alignment (routing_keywords, intents, category, description).
/// Precomputes lowercase once per field to avoid repeated allocations in the term loop.
pub fn metadata_alignment_boost(meta: &ToolSearchResult, query_parts: &[&str]) -> f32 {
    if query_parts.is_empty() {
        return 0.0;
    }

    let category = meta.category.to_lowercase();
    let description = meta.description.to_lowercase();
    let routing_lower: Vec<String> = meta
        .routing_keywords
        .iter()
        .map(|k| k.to_lowercase())
        .collect();
    let intents_lower: Vec<String> = meta.intents.iter().map(|i| i.to_lowercase()).collect();

    let mut boost: f32 = 0.0;
    for term in query_parts {
        if term.len() <= 2 {
            continue;
        }

        if routing_lower.iter().any(|k| k.contains(term)) {
            boost += 0.08;
        }
        if intents_lower.iter().any(|i| i.contains(term)) {
            boost += 0.09;
        }
        if !category.is_empty() && category.contains(term) {
            boost += 0.05;
        }
        if description.contains(term) {
            boost += 0.03;
        }
    }

    boost.min(0.45)
}

/// True if the query suggests file-discovery intent (find/list/file/path/glob etc.).
pub fn is_file_discovery_query(query_lower: &str, query_parts: &[&str]) -> bool {
    let intent_terms = [
        "find",
        "list",
        "files",
        "file",
        "directory",
        "folder",
        "path",
        "glob",
        "extension",
    ];
    let has_term = query_parts
        .iter()
        .any(|t| intent_terms.contains(t) || t.starts_with("*."));
    has_term || query_lower.contains(".py") || query_lower.contains(".rs")
}

/// File-discovery terms for Aho-Corasick (single build, reused).
const FILE_DISCOVERY_TERMS: &[&str] = &[
    "find",
    "file",
    "files",
    "directory",
    "path",
    "glob",
    "filename",
];

/// True if the tool metadata indicates file-discovery capability (e.g. smart_find).
/// Uses one lowercase pass per field and Aho-Corasick for O(n+m) term matching.
pub fn file_discovery_boost(meta: &ToolSearchResult) -> bool {
    let category = meta.category.to_lowercase();
    let description = meta.description.to_lowercase();
    let tool_name = meta.tool_name.to_lowercase();

    if tool_name.contains("advanced_tools.smart_find") {
        return true;
    }

    let ac = match aho_corasick::AhoCorasick::new(FILE_DISCOVERY_TERMS) {
        Ok(ac) => ac,
        Err(_) => {
            return meta.routing_keywords.iter().any(|k| {
                let kl = k.to_lowercase();
                FILE_DISCOVERY_TERMS.iter().any(|t| kl.contains(t))
            }) || meta.intents.iter().any(|i| {
                let il = i.to_lowercase();
                FILE_DISCOVERY_TERMS.iter().any(|t| il.contains(t))
            });
        }
    };

    if ac.is_match(&category) || ac.is_match(&description) || ac.is_match(&tool_name) {
        return true;
    }

    let kw_joined = meta
        .routing_keywords
        .iter()
        .map(|k| k.to_lowercase())
        .collect::<Vec<_>>()
        .join(" ");
    if !kw_joined.is_empty() && ac.is_match(&kw_joined) {
        return true;
    }

    let intents_joined = meta
        .intents
        .iter()
        .map(|i| i.to_lowercase())
        .collect::<Vec<_>>()
        .join(" ");
    if !intents_joined.is_empty() && ac.is_match(&intents_joined) {
        return true;
    }

    false
}
