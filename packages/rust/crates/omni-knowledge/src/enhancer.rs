//! ZK Note Enhancement Engine.
//!
//! Secondary analysis for ZK query results — things the ZK CLI cannot do:
//! - Parse YAML frontmatter into structured metadata
//! - Infer typed relations from note structure
//! - Batch enhance notes (frontmatter + entities + relations)
//!
//! The ZK CLI remains the primary engine for scanning, building the link
//! graph, and querying. This module enriches ZK results with deeper
//! structural analysis at Rust-native speed.

use crate::zk::{ZkEntityRef, extract_entity_refs, get_ref_stats};
use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/// Parsed YAML frontmatter from a markdown note.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct NoteFrontmatter {
    /// Document title from frontmatter.
    pub title: Option<String>,
    /// Human-readable description.
    pub description: Option<String>,
    /// Skill name (for SKILL.md files).
    pub name: Option<String>,
    /// Document category (e.g. "pattern", "architecture").
    pub category: Option<String>,
    /// Tags for discovery and filtering.
    #[serde(default)]
    pub tags: Vec<String>,
    /// Routing keywords from `metadata.routing_keywords`.
    #[serde(default)]
    pub routing_keywords: Vec<String>,
    /// Intent descriptions from `metadata.intents`.
    #[serde(default)]
    pub intents: Vec<String>,
}

/// Input for a single note to be enhanced.
#[derive(Debug, Clone)]
pub struct NoteInput {
    /// Relative path to the note (e.g. `docs/architecture/foo.md`).
    pub path: String,
    /// Note title (from ZK or frontmatter).
    pub title: String,
    /// Full raw content of the note.
    pub content: String,
}

/// A relation inferred from note structure.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferredRelation {
    /// Source entity name.
    pub source: String,
    /// Target entity name.
    pub target: String,
    /// Relation type string (e.g. `DOCUMENTED_IN`, `CONTAINS`).
    pub relation_type: String,
    /// Human-readable description of the relation.
    pub description: String,
}

/// A ZK note enriched with secondary analysis.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnhancedNote {
    /// Note path.
    pub path: String,
    /// Note title.
    pub title: String,
    /// Parsed YAML frontmatter.
    pub frontmatter: NoteFrontmatter,
    /// Entity references extracted from wikilinks.
    pub entity_refs: Vec<EntityRefData>,
    /// Reference statistics.
    pub ref_stats: RefStatsData,
    /// Relations inferred from note structure.
    pub inferred_relations: Vec<InferredRelation>,
}

/// Serializable entity reference.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityRefData {
    /// Entity name.
    pub name: String,
    /// Optional entity type hint (from `[[Name#type]]`).
    pub entity_type: Option<String>,
    /// Original matched text.
    pub original: String,
}

/// Serializable reference statistics.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct RefStatsData {
    /// Total entity references found.
    pub total_refs: usize,
    /// Number of unique entities referenced.
    pub unique_entities: usize,
    /// Reference counts grouped by entity type.
    pub by_type: Vec<(String, usize)>,
}

// ---------------------------------------------------------------------------
// Frontmatter parsing
// ---------------------------------------------------------------------------

/// Extract YAML frontmatter from markdown content.
///
/// Looks for `---\n...\n---\n` at the start of the content.
fn extract_frontmatter_yaml(content: &str) -> Option<String> {
    let trimmed = content.trim_start();
    if !trimmed.starts_with("---") {
        return None;
    }

    let after_first = &trimmed[3..];
    // Find the closing ---
    if let Some(end_pos) = after_first.find("\n---") {
        let yaml = &after_first[..end_pos];
        // Skip leading newline
        let yaml = yaml.strip_prefix('\n').unwrap_or(yaml);
        Some(yaml.to_string())
    } else {
        None
    }
}

/// Parse frontmatter from markdown content.
pub fn parse_frontmatter(content: &str) -> NoteFrontmatter {
    let yaml_str = match extract_frontmatter_yaml(content) {
        Some(y) => y,
        None => return NoteFrontmatter::default(),
    };

    // Parse top-level YAML
    let value: serde_yaml::Value = match serde_yaml::from_str(&yaml_str) {
        Ok(v) => v,
        Err(_) => return NoteFrontmatter::default(),
    };

    let mapping = match value.as_mapping() {
        Some(m) => m,
        None => return NoteFrontmatter::default(),
    };

    let get_str = |key: &str| -> Option<String> {
        mapping
            .get(serde_yaml::Value::String(key.to_string()))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
    };

    let get_str_vec = |key: &str| -> Vec<String> {
        mapping
            .get(serde_yaml::Value::String(key.to_string()))
            .and_then(|v| v.as_sequence())
            .map(|seq| {
                seq.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default()
    };

    // Check nested metadata block
    let metadata = mapping
        .get(serde_yaml::Value::String("metadata".to_string()))
        .and_then(|v| v.as_mapping());

    let get_metadata_vec = |key: &str| -> Vec<String> {
        metadata
            .and_then(|m| m.get(serde_yaml::Value::String(key.to_string())))
            .and_then(|v| v.as_sequence())
            .map(|seq| {
                seq.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default()
    };

    let mut tags = get_str_vec("tags");
    if tags.is_empty() {
        tags = get_metadata_vec("tags");
    }

    NoteFrontmatter {
        title: get_str("title"),
        description: get_str("description"),
        name: get_str("name"),
        category: get_str("category"),
        tags,
        routing_keywords: get_metadata_vec("routing_keywords"),
        intents: get_metadata_vec("intents"),
    }
}

// ---------------------------------------------------------------------------
// Relation inference
// ---------------------------------------------------------------------------

/// Infer relations from note structure.
///
/// Relations inferred:
/// - `DOCUMENTED_IN`: Entity refs → this document
/// - `CONTAINS`: Skill SKILL.md → its skill name
/// - `RELATED_TO`: Document → tags
pub fn infer_relations(
    note_path: &str,
    note_title: &str,
    frontmatter: &NoteFrontmatter,
    entity_refs: &[ZkEntityRef],
) -> Vec<InferredRelation> {
    let mut relations = Vec::new();
    let doc_name = note_title;

    // Entity refs → DOCUMENTED_IN
    for entity_ref in entity_refs {
        relations.push(InferredRelation {
            source: entity_ref.name.clone(),
            target: doc_name.to_string(),
            relation_type: "DOCUMENTED_IN".to_string(),
            description: format!("{} documented in {}", entity_ref.name, doc_name),
        });
    }

    // Skill SKILL.md → CONTAINS
    let is_skill = note_path.to_uppercase().contains("SKILL.MD")
        || note_path.to_uppercase().ends_with("SKILL.MD");
    if is_skill {
        if let Some(ref name) = frontmatter.name {
            relations.push(InferredRelation {
                source: name.clone(),
                target: doc_name.to_string(),
                relation_type: "CONTAINS".to_string(),
                description: format!("Skill {} defined in {}", name, doc_name),
            });
        }
    }

    // Tags → RELATED_TO
    for tag in &frontmatter.tags {
        relations.push(InferredRelation {
            source: doc_name.to_string(),
            target: format!("tag:{}", tag),
            relation_type: "RELATED_TO".to_string(),
            description: format!("{} tagged with {}", doc_name, tag),
        });
    }

    relations
}

// ---------------------------------------------------------------------------
// Batch enhance
// ---------------------------------------------------------------------------

/// Enhance a single note with full secondary analysis.
pub fn enhance_note(input: &NoteInput) -> EnhancedNote {
    let frontmatter = parse_frontmatter(&input.content);
    let entity_refs_raw = extract_entity_refs(&input.content);
    let stats_raw = get_ref_stats(&input.content);

    let entity_refs: Vec<EntityRefData> = entity_refs_raw
        .iter()
        .map(|r| EntityRefData {
            name: r.name.clone(),
            entity_type: r.entity_type.clone(),
            original: r.original.clone(),
        })
        .collect();

    let ref_stats = RefStatsData {
        total_refs: stats_raw.total_refs,
        unique_entities: stats_raw.unique_entities,
        by_type: stats_raw.by_type.clone(),
    };

    let relations = infer_relations(&input.path, &input.title, &frontmatter, &entity_refs_raw);

    EnhancedNote {
        path: input.path.clone(),
        title: input.title.clone(),
        frontmatter,
        entity_refs,
        ref_stats,
        inferred_relations: relations,
    }
}

/// Batch enhance multiple notes (parallelized with Rayon).
pub fn enhance_notes_batch(inputs: &[NoteInput]) -> Vec<EnhancedNote> {
    use rayon::prelude::*;
    inputs.par_iter().map(enhance_note).collect()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_frontmatter_basic() {
        let content =
            "---\ntitle: My Note\ndescription: A test\ntags:\n  - python\n  - rust\n---\n# Content";
        let fm = parse_frontmatter(content);
        assert_eq!(fm.title.as_deref(), Some("My Note"));
        assert_eq!(fm.description.as_deref(), Some("A test"));
        assert_eq!(fm.tags, vec!["python", "rust"]);
    }

    #[test]
    fn test_parse_frontmatter_skill() {
        let content = "---\nname: git\ndescription: Git ops\nmetadata:\n  routing_keywords:\n    - commit\n    - branch\n  intents:\n    - version_control\n---\n# SKILL";
        let fm = parse_frontmatter(content);
        assert_eq!(fm.name.as_deref(), Some("git"));
        assert_eq!(fm.routing_keywords, vec!["commit", "branch"]);
        assert_eq!(fm.intents, vec!["version_control"]);
    }

    #[test]
    fn test_parse_frontmatter_empty() {
        let fm = parse_frontmatter("# No frontmatter");
        assert!(fm.title.is_none());
        assert!(fm.tags.is_empty());
    }

    #[test]
    fn test_parse_frontmatter_malformed() {
        let fm = parse_frontmatter("---\n: bad [[\n---\n");
        assert!(fm.title.is_none());
    }

    #[test]
    fn test_infer_relations_documented_in() {
        let refs = vec![ZkEntityRef::new(
            "Python".to_string(),
            None,
            "[[Python]]".to_string(),
        )];
        let fm = NoteFrontmatter::default();
        let rels = infer_relations("docs/test.md", "Test Doc", &fm, &refs);

        assert_eq!(rels.len(), 1);
        assert_eq!(rels[0].source, "Python");
        assert_eq!(rels[0].relation_type, "DOCUMENTED_IN");
    }

    #[test]
    fn test_infer_relations_skill_contains() {
        let fm = NoteFrontmatter {
            name: Some("git".to_string()),
            ..Default::default()
        };
        let rels = infer_relations("assets/skills/git/SKILL.md", "Git Skill", &fm, &[]);

        let contains: Vec<_> = rels
            .iter()
            .filter(|r| r.relation_type == "CONTAINS")
            .collect();
        assert_eq!(contains.len(), 1);
        assert_eq!(contains[0].source, "git");
    }

    #[test]
    fn test_infer_relations_tags() {
        let fm = NoteFrontmatter {
            tags: vec!["search".to_string(), "vector".to_string()],
            ..Default::default()
        };
        let rels = infer_relations("docs/test.md", "Test", &fm, &[]);

        let tag_rels: Vec<_> = rels
            .iter()
            .filter(|r| r.relation_type == "RELATED_TO")
            .collect();
        assert_eq!(tag_rels.len(), 2);
    }

    #[test]
    fn test_enhance_note_full() {
        let input = NoteInput {
            path: "docs/test.md".to_string(),
            title: "Test Doc".to_string(),
            content: "---\ntitle: Test\ntags:\n  - demo\n---\nContent with [[Python#lang]] ref"
                .to_string(),
        };

        let result = enhance_note(&input);
        assert_eq!(result.frontmatter.title.as_deref(), Some("Test"));
        assert_eq!(result.entity_refs.len(), 1);
        assert_eq!(result.entity_refs[0].name, "Python");
        assert_eq!(result.entity_refs[0].entity_type.as_deref(), Some("lang"));
        assert!(result.ref_stats.total_refs >= 1);
        // DOCUMENTED_IN + RELATED_TO(tag:demo)
        assert!(result.inferred_relations.len() >= 2);
    }

    #[test]
    fn test_enhance_notes_batch() {
        let inputs = vec![
            NoteInput {
                path: "a.md".to_string(),
                title: "A".to_string(),
                content: "About [[X]]".to_string(),
            },
            NoteInput {
                path: "b.md".to_string(),
                title: "B".to_string(),
                content: "About [[Y]] and [[Z]]".to_string(),
            },
        ];

        let results = enhance_notes_batch(&inputs);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].entity_refs.len(), 1);
        assert_eq!(results[1].entity_refs.len(), 2);
    }
}
