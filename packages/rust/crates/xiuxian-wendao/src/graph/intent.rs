//! Lightweight query intent extractor.
//!
//! Decomposes a natural-language query into structured intent signals:
//! - **action**: the verb / desired operation (e.g. "commit", "search", "create")
//! - **target**: the object / domain the action applies to (e.g. "code", "file", "git")
//! - **context**: additional qualifiers / modifiers (e.g. "python", "async", "memory")
//! - **keywords**: all significant tokens extracted from the query
//!
//! These signals feed into the routing + fusion pipeline so that KG-rerank
//! and dynamic weight selection can work at the semantic level rather than
//! relying on raw substring matching alone.

use std::collections::HashSet;

/// Structured intent parsed from a user query.
#[derive(Debug, Clone, Default)]
pub struct QueryIntent {
    /// Primary action verb (e.g. "search", "commit", "create")
    pub action: Option<String>,
    /// Target domain or object (e.g. "git", "knowledge", "file")
    pub target: Option<String>,
    /// Context qualifiers (e.g. "python", "async")
    pub context: Vec<String>,
    /// All significant keywords (stop-words removed)
    pub keywords: Vec<String>,
    /// Original query, lower-cased and trimmed
    pub normalized_query: String,
}

// -----------------------------------------------------------------------
// Action vocabulary — maps natural-language verbs to canonical actions.
// -----------------------------------------------------------------------

const ACTION_VERBS: &[(&str, &str)] = &[
    // Search / Retrieval
    ("search", "search"),
    ("find", "search"),
    ("look", "search"),
    ("lookup", "search"),
    ("query", "search"),
    ("recall", "search"),
    ("retrieve", "search"),
    ("fetch", "search"),
    ("get", "search"),
    ("locate", "search"),
    // Create / Write
    ("create", "create"),
    ("make", "create"),
    ("add", "create"),
    ("write", "create"),
    ("generate", "create"),
    ("build", "create"),
    ("scaffold", "create"),
    ("init", "create"),
    ("initialize", "create"),
    ("new", "create"),
    // Modify / Update
    ("update", "update"),
    ("edit", "update"),
    ("modify", "update"),
    ("change", "update"),
    ("refactor", "update"),
    ("rename", "update"),
    ("fix", "update"),
    ("patch", "update"),
    // Delete / Remove
    ("delete", "delete"),
    ("remove", "delete"),
    ("drop", "delete"),
    ("clean", "delete"),
    ("purge", "delete"),
    // Git operations
    ("commit", "commit"),
    ("push", "push"),
    ("pull", "pull"),
    ("merge", "merge"),
    ("rebase", "rebase"),
    ("branch", "branch"),
    ("checkout", "checkout"),
    ("diff", "diff"),
    ("status", "status"),
    ("log", "log"),
    ("stash", "stash"),
    // Run / Execute
    ("run", "run"),
    ("execute", "run"),
    ("start", "run"),
    ("launch", "run"),
    ("test", "test"),
    ("lint", "lint"),
    ("format", "format"),
    // Analyze / Inspect
    ("analyze", "analyze"),
    ("inspect", "analyze"),
    ("explain", "analyze"),
    ("describe", "analyze"),
    ("show", "analyze"),
    ("list", "list"),
    ("count", "count"),
    // Index / Sync
    ("index", "index"),
    ("reindex", "index"),
    ("sync", "sync"),
    ("embed", "embed"),
    // Research
    ("research", "research"),
    ("crawl", "crawl"),
    ("browse", "crawl"),
];

// -----------------------------------------------------------------------
// Domain vocabulary — maps nouns/domains to canonical targets.
// -----------------------------------------------------------------------

const DOMAIN_TARGETS: &[(&str, &str)] = &[
    // Source control
    ("git", "git"),
    ("repo", "git"),
    ("repository", "git"),
    ("branch", "git"),
    ("commit", "git"),
    // Knowledge
    ("knowledge", "knowledge"),
    ("memory", "memory"),
    ("note", "knowledge"),
    ("notes", "knowledge"),
    ("graph", "knowledge"),
    // Code
    ("code", "code"),
    ("function", "code"),
    ("class", "code"),
    ("module", "code"),
    ("file", "code"),
    ("files", "code"),
    ("codebase", "code"),
    ("source", "code"),
    // Skills / Tools
    ("skill", "skill"),
    ("skills", "skill"),
    ("tool", "skill"),
    ("tools", "skill"),
    ("command", "skill"),
    ("commands", "skill"),
    // Web / Research
    ("web", "web"),
    ("internet", "web"),
    ("url", "web"),
    ("page", "web"),
    ("site", "web"),
    ("website", "web"),
    // Database
    ("database", "database"),
    ("db", "database"),
    ("table", "database"),
    ("vector", "database"),
    ("index", "database"),
    // Documentation
    ("doc", "docs"),
    ("docs", "docs"),
    ("documentation", "docs"),
    ("readme", "docs"),
    ("spec", "docs"),
    ("reference", "docs"),
    // Tests
    ("test", "test"),
    ("tests", "test"),
    ("testing", "test"),
];

/// English stop words (common function words to filter out).
const STOP_WORDS: &[&str] = &[
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "shall", "should", "may", "might", "must", "can",
    "could", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all",
    "both", "each", "every", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "also", "about", "up", "down",
    "if", "or", "and", "but", "because", "until", "while", "it", "its", "this", "that", "these",
    "those", "my", "your", "his", "her", "our", "their", "what", "which", "who", "whom", "me",
    "him", "them", "i", "you", "he", "she", "we", "they", "please", "want", "need", "help", "like",
    "using",
];

/// Extract a structured `QueryIntent` from a raw natural-language query.
///
/// The algorithm is zero-allocation-heavy and rule-based — no ML model needed.
/// It runs in microseconds, making it suitable for hot-path routing.
#[must_use]
pub fn extract_intent(query: &str) -> QueryIntent {
    let normalized = query.trim().to_lowercase();
    if normalized.is_empty() {
        return QueryIntent {
            normalized_query: normalized,
            ..Default::default()
        };
    }

    let stop_set: HashSet<&str> = STOP_WORDS.iter().copied().collect();

    // Tokenize: split on whitespace and common delimiters
    let tokens: Vec<&str> = normalized
        .split(|c: char| {
            c.is_whitespace() || c == '.' || c == '_' || c == '-' || c == '/' || c == ','
        })
        .filter(|t| !t.is_empty())
        .collect();

    // Extract keywords (non-stop-word tokens with len >= 2)
    let keywords: Vec<String> = tokens
        .iter()
        .filter(|t| t.len() >= 2 && !stop_set.contains(**t))
        .map(std::string::ToString::to_string)
        .collect();

    // Identify action — first matching action verb (order-sensitive: first token wins)
    let mut action: Option<String> = None;
    for token in &tokens {
        if let Some((_, canonical)) = ACTION_VERBS.iter().find(|(verb, _)| verb == token) {
            action = Some(canonical.to_string());
            break;
        }
    }

    // Identify target — first matching domain noun that is NOT the action token
    let mut target: Option<String> = None;
    for token in &tokens {
        // Skip the action token itself to avoid "commit" mapping to both action and target
        if action.as_deref() == Some(*token) {
            continue;
        }
        if let Some((_, canonical)) = DOMAIN_TARGETS.iter().find(|(noun, _)| noun == token) {
            target = Some(canonical.to_string());
            break;
        }
    }

    // If no explicit target found, try to infer from action context
    if target.is_none()
        && let Some(ref act) = action
    {
        match act.as_str() {
            "commit" | "push" | "pull" | "merge" | "rebase" | "branch" | "checkout" | "diff"
            | "status" | "log" | "stash" => {
                target = Some("git".to_string());
            }
            "crawl" | "research" => {
                target = Some("web".to_string());
            }
            "embed" | "index" => {
                target = Some("database".to_string());
            }
            _ => {}
        }
    }

    // Context: remaining non-stop, non-action, non-target keywords
    let action_tokens: HashSet<&str> = ACTION_VERBS
        .iter()
        .filter_map(|(v, c)| {
            if action.as_deref() == Some(*c) {
                Some(*v)
            } else {
                None
            }
        })
        .collect();

    let target_tokens: HashSet<&str> = DOMAIN_TARGETS
        .iter()
        .filter_map(|(n, c)| {
            if target.as_deref() == Some(*c) {
                Some(*n)
            } else {
                None
            }
        })
        .collect();

    let context: Vec<String> = keywords
        .iter()
        .filter(|kw| !action_tokens.contains(kw.as_str()) && !target_tokens.contains(kw.as_str()))
        .cloned()
        .collect();

    QueryIntent {
        action,
        target,
        context,
        keywords,
        normalized_query: normalized,
    }
}
