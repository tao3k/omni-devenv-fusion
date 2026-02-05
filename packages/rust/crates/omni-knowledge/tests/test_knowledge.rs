//! Tests for omni-knowledge crate.

use omni_knowledge::{KnowledgeCategory, KnowledgeEntry, KnowledgeSearchQuery, KnowledgeStats};

/// Test KnowledgeCategory enum variants.
#[test]
fn test_knowledge_category_variants() {
    // Test all category variants exist
    let _ = KnowledgeCategory::Pattern;
    let _ = KnowledgeCategory::Solution;
    let _ = KnowledgeCategory::Error;
    let _ = KnowledgeCategory::Technique;
    let _ = KnowledgeCategory::Note;
    let _ = KnowledgeCategory::Reference;
    let _ = KnowledgeCategory::Architecture;
    let _ = KnowledgeCategory::Workflow;
}

/// Test KnowledgeEntry creation with required fields.
#[test]
fn test_knowledge_entry_creation() {
    let entry = KnowledgeEntry::new(
        "test-001".to_string(),
        "Error Handling Pattern".to_string(),
        "Best practices for error handling in Rust...".to_string(),
        KnowledgeCategory::Pattern,
    );

    assert_eq!(entry.id, "test-001");
    assert_eq!(entry.title, "Error Handling Pattern");
    assert_eq!(entry.category, KnowledgeCategory::Pattern);
    assert!(entry.tags.is_empty());
    assert!(entry.source.is_none());
    assert_eq!(entry.version, 1);
}

/// Test KnowledgeEntry with optional fields.
#[test]
fn test_knowledge_entry_with_options() {
    let entry = KnowledgeEntry::new(
        "test-002".to_string(),
        "Async Error Handling".to_string(),
        "Handling errors in async Rust code...".to_string(),
        KnowledgeCategory::Technique,
    )
    .with_tags(vec![
        "async".to_string(),
        "error".to_string(),
        "rust".to_string(),
    ])
    .with_source(Some("docs/async-errors.md".to_string()));

    assert_eq!(entry.tags.len(), 3);
    assert_eq!(entry.source, Some("docs/async-errors.md".to_string()));
}

/// Test KnowledgeEntry tag operations.
#[test]
fn test_knowledge_entry_tag_operations() {
    let mut entry = KnowledgeEntry::new(
        "test-003".to_string(),
        "Tagged Entry".to_string(),
        "Content with tags...".to_string(),
        KnowledgeCategory::Note,
    );

    // Add unique tag
    entry.add_tag("unique-tag".to_string());
    assert_eq!(entry.tags.len(), 1);

    // Add duplicate tag (should not increase count)
    entry.add_tag("unique-tag".to_string());
    assert_eq!(entry.tags.len(), 1);
}

/// Test KnowledgeSearchQuery creation.
#[test]
fn test_search_query_creation() {
    let query = KnowledgeSearchQuery::new("error handling".to_string());

    assert_eq!(query.query, "error handling");
    assert!(query.category.is_none());
    assert!(query.tags.is_empty());
    assert_eq!(query.limit, 5);
}

/// Test KnowledgeSearchQuery builder methods.
#[test]
fn test_search_query_builder() {
    let query = KnowledgeSearchQuery::new("database error".to_string())
        .with_category(KnowledgeCategory::Error)
        .with_tags(vec!["sql".to_string(), "postgres".to_string()])
        .with_limit(10);

    assert_eq!(query.query, "database error");
    assert_eq!(query.category, Some(KnowledgeCategory::Error));
    assert_eq!(query.tags.len(), 2);
    assert_eq!(query.limit, 10);
}

/// Test KnowledgeEntry default category.
#[test]
fn test_knowledge_entry_default_category() {
    let entry = KnowledgeEntry::new(
        "test-004".to_string(),
        "Simple Note".to_string(),
        "Just a note...".to_string(),
        KnowledgeCategory::default(),
    );

    assert_eq!(entry.category, KnowledgeCategory::Note);
}

/// Test KnowledgeStats default values.
#[test]
fn test_knowledge_stats_default() {
    let stats = KnowledgeStats::default();

    assert_eq!(stats.total_entries, 0);
    assert!(stats.entries_by_category.is_empty());
    assert_eq!(stats.total_tags, 0);
    assert!(stats.last_updated.is_none());
}

/// Test KnowledgeEntry equality (ignoring timestamps).
#[test]
fn test_knowledge_entry_equality() {
    let entry1 = KnowledgeEntry {
        id: "same-id".to_string(),
        title: "Title".to_string(),
        content: "Content".to_string(),
        category: KnowledgeCategory::Note,
        tags: vec!["tag1".to_string()],
        source: None,
        created_at: chrono::DateTime::parse_from_rfc3339("2026-01-01T00:00:00Z")
            .unwrap()
            .with_timezone(&chrono::Utc),
        updated_at: chrono::DateTime::parse_from_rfc3339("2026-01-01T00:00:00Z")
            .unwrap()
            .with_timezone(&chrono::Utc),
        version: 1,
        metadata: std::collections::HashMap::new(),
    };

    let entry2 = KnowledgeEntry {
        id: "same-id".to_string(),
        title: "Title".to_string(),
        content: "Content".to_string(),
        category: KnowledgeCategory::Note,
        tags: vec!["tag1".to_string()],
        source: None,
        created_at: chrono::DateTime::parse_from_rfc3339("2026-01-01T00:00:00Z")
            .unwrap()
            .with_timezone(&chrono::Utc),
        updated_at: chrono::DateTime::parse_from_rfc3339("2026-01-01T00:00:00Z")
            .unwrap()
            .with_timezone(&chrono::Utc),
        version: 1,
        metadata: std::collections::HashMap::new(),
    };

    assert_eq!(entry1, entry2);
}

/// Test KnowledgeEntry cloning.
#[test]
fn test_knowledge_entry_clone() {
    let entry = KnowledgeEntry::new(
        "clone-test".to_string(),
        "Clone This".to_string(),
        "Content to clone...".to_string(),
        KnowledgeCategory::Solution,
    )
    .with_tags(vec!["clone".to_string()])
    .with_source(Some("clone.md".to_string()));

    let cloned = entry.clone();

    assert_eq!(entry.id, cloned.id);
    assert_eq!(entry.title, cloned.title);
    assert_eq!(entry.content, cloned.content);
    assert_eq!(entry.category, cloned.category);
    assert_eq!(entry.tags, cloned.tags);
    assert_eq!(entry.source, cloned.source);
}

/// Test KnowledgeEntry with metadata.
#[test]
fn test_knowledge_entry_with_metadata() {
    use serde_json::json;

    let mut entry = KnowledgeEntry::new(
        "metadata-test".to_string(),
        "With Metadata".to_string(),
        "Entry with extra metadata...".to_string(),
        KnowledgeCategory::Reference,
    );

    // Add metadata
    entry
        .metadata
        .insert("author".to_string(), json!("test-author"));
    entry.metadata.insert("reviewed".to_string(), json!(true));

    assert_eq!(entry.metadata.len(), 2);
    assert_eq!(entry.metadata.get("author"), Some(&json!("test-author")));
}

/// Test KnowledgeCategory equality.
#[test]
fn test_knowledge_category_equality() {
    assert_eq!(KnowledgeCategory::Pattern, KnowledgeCategory::Pattern);
    assert_ne!(KnowledgeCategory::Pattern, KnowledgeCategory::Solution);
}

/// Test KnowledgeSearchQuery default.
#[test]
fn test_search_query_default() {
    let query = KnowledgeSearchQuery::default();

    assert!(query.query.is_empty());
    assert!(query.category.is_none());
    assert!(query.tags.is_empty());
    assert_eq!(query.limit, 0);
}
