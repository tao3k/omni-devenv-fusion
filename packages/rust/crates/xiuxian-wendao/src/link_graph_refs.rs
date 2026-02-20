//! LinkGraph reference extraction primitives.
#![allow(clippy::doc_markdown)]
//!
//! Provides fast regex-based extraction of entity references from markdown notes.
//! Pattern: [[EntityName]] or [[EntityName#type]]

use regex::Regex;
use serde::{Deserialize, Serialize};
use std::cmp::Reverse;
use std::collections::HashSet;
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

static WIKILINK_REGEX: LazyLock<Regex> =
    LazyLock::new(|| compile_regex(r"\[\[([^\]#\|]+)(?:#([^\]#\|]+))?(?:\|[^\]]+)?\]\]"));
static WIKILINK_REGEX_EXACT: LazyLock<Regex> =
    LazyLock::new(|| compile_regex(r"^\[\[([^\]#\|]+)(?:#([^\]#\|]+))?(?:\|[^\]]+)?\]\]$"));

/// Represents an entity reference extracted from note content.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct LinkGraphEntityRef {
    /// Entity name (without type hint)
    pub name: String,
    /// Optional entity type hint (e.g., "rust", "py", "pattern")
    #[serde(default)]
    pub entity_type: Option<String>,
    /// Original matched text
    #[serde(skip)]
    pub original: String,
}

impl LinkGraphEntityRef {
    /// Create a new entity reference.
    #[must_use]
    pub fn new(name: String, entity_type: Option<String>, original: String) -> Self {
        Self {
            name,
            entity_type,
            original,
        }
    }

    /// Get the wikilink format: [[Name]] or [[Name#type]]
    #[must_use]
    pub fn to_wikilink(&self) -> String {
        match &self.entity_type {
            Some(t) => format!("[[{}#{}]]", self.name, t),
            None => format!("[[{}]]", self.name),
        }
    }

    /// Get the tag format: #entity or #entity-type
    #[must_use]
    pub fn to_tag(&self) -> String {
        match &self.entity_type {
            Some(t) => format!("#entity-{}", t.to_lowercase()),
            None => "#entity".to_string(),
        }
    }
}

/// Extract all entity references from note content.
///
/// Supports:
/// - [[EntityName]] - reference by name
/// - [[EntityName#type]] - reference with type hint (rust, py, pattern, etc.)
/// - [[EntityName|alias]] - reference with alias (alias is ignored)
///
/// # Arguments
///
/// * `content` - The note body content to search
///
/// # Returns
///
/// Vector of extracted entity references (deduplicated)
pub fn extract_entity_refs(content: &str) -> Vec<LinkGraphEntityRef> {
    let mut seen: HashSet<String> = HashSet::new();
    let mut refs: Vec<LinkGraphEntityRef> = Vec::new();

    for caps in WIKILINK_REGEX.captures_iter(content) {
        let Some(name_match) = caps.get(1) else {
            continue;
        };
        let name = name_match.as_str().trim().to_string();
        let entity_type = caps.get(2).map(|m| m.as_str().trim().to_string());
        let Some(original_match) = caps.get(0) else {
            continue;
        };
        let original = original_match.as_str().to_string();

        // Deduplicate by name
        if !seen.contains(&name) {
            seen.insert(name.clone());
            refs.push(LinkGraphEntityRef::new(name, entity_type, original));
        }
    }

    refs
}

/// Extract entity references from multiple notes (batch processing).
///
/// More efficient than calling extract_entity_refs individually
/// when processing many notes.
///
/// # Arguments
///
/// * `notes` - Vector of (note_id, content) tuples
///
/// # Returns
///
/// Vector of (note_id, entity_references) tuples
#[must_use]
pub fn extract_entity_refs_batch<'a>(
    notes: &[(&'a str, &'a str)],
) -> Vec<(&'a str, Vec<LinkGraphEntityRef>)> {
    notes
        .iter()
        .map(|(note_id, content)| (*note_id, extract_entity_refs(content)))
        .collect()
}

/// Find notes that reference a given entity name.
///
/// # Arguments
///
/// * `entity_name` - The entity name to search for
/// * `contents` - Vector of (note_id, content) tuples to search
///
/// # Returns
///
/// Vector of note IDs that reference the entity
#[must_use]
pub fn find_notes_referencing_entity<'a>(
    entity_name: &str,
    contents: &[(&'a str, &'a str)],
) -> Vec<&'a str> {
    let lower_name = entity_name.to_lowercase();
    let wikilink_pattern = format!("[[{entity_name}]]");
    let wikilink_pattern_typed = format!("[[{entity_name}#");

    contents
        .iter()
        .filter(|(_, content)| {
            let lower = content.to_lowercase();
            lower.contains(&lower_name)
                || lower.contains(&wikilink_pattern.to_lowercase())
                || lower.contains(&wikilink_pattern_typed.to_lowercase())
        })
        .map(|(note_id, _)| *note_id)
        .collect()
}

/// Count entity references in content.
#[must_use]
pub fn count_entity_refs(content: &str) -> usize {
    WIKILINK_REGEX.captures_iter(content).count()
}

/// Validate entity reference format.
#[must_use]
pub fn is_valid_entity_ref(text: &str) -> bool {
    WIKILINK_REGEX_EXACT.is_match(text)
}

/// Parse a single entity reference string.
#[must_use]
pub fn parse_entity_ref(text: &str) -> Option<LinkGraphEntityRef> {
    let caps = WIKILINK_REGEX_EXACT.captures(text)?;
    let name = caps.get(1)?.as_str().trim().to_string();
    Some(LinkGraphEntityRef::new(
        name,
        caps.get(2).map(|m| m.as_str().trim().to_string()),
        text.to_string(),
    ))
}

/// Entity reference statistics for a note.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LinkGraphRefStats {
    /// Total references count
    pub total_refs: usize,
    /// Unique entities referenced
    pub unique_entities: usize,
    /// References by type
    pub by_type: Vec<(String, usize)>,
}

impl LinkGraphRefStats {
    /// Create stats from entity references.
    #[must_use]
    pub fn from_refs(refs: &[LinkGraphEntityRef]) -> Self {
        let mut type_counts: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        let mut unique_names: HashSet<String> = HashSet::new();

        for ref_item in refs {
            unique_names.insert(ref_item.name.clone());
            let t = ref_item
                .entity_type
                .clone()
                .unwrap_or_else(|| "none".to_string());
            *type_counts.entry(t).or_insert(0) += 1;
        }

        let mut by_type: Vec<(String, usize)> = type_counts.into_iter().collect();
        by_type.sort_by_key(|item| Reverse(item.1));

        Self {
            total_refs: refs.len(),
            unique_entities: unique_names.len(),
            by_type,
        }
    }
}

/// Get statistics for entity references in content.
#[must_use]
pub fn get_ref_stats(content: &str) -> LinkGraphRefStats {
    LinkGraphRefStats::from_refs(&extract_entity_refs(content))
}
