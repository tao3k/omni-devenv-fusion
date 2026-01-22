//! Tests for skill_metadata module.
//!
//! Tests SkillMetadata, SnifferRule, ReferencePath, and related types.

use skills_scanner::{ReferencePath, SkillIndexEntry, SnifferRule};

/// Test SnifferRule creation and field access.
#[test]
fn test_sniffer_rule_creation() {
    let rule = SnifferRule::new("file_exists", "Cargo.toml");
    assert_eq!(rule.rule_type, "file_exists");
    assert_eq!(rule.pattern, "Cargo.toml");
}

/// Test SkillIndexEntry with sniffer rules.
#[test]
fn test_skill_index_entry_with_rules() {
    let mut entry = SkillIndexEntry::new(
        "rust".to_string(),
        "Rust skill".to_string(),
        "1.0".to_string(),
        "path".to_string(),
    );
    assert!(entry.sniffing_rules.is_empty());
    entry
        .sniffing_rules
        .push(SnifferRule::new("file_exists", "Cargo.toml"));
    assert_eq!(entry.sniffing_rules.len(), 1);
}

/// Test ReferencePath validation.
#[test]
fn test_reference_path_validation() {
    assert!(ReferencePath::new("docs/guide.md").is_ok());
    assert!(ReferencePath::new("/absolute.md").is_err());
    assert!(ReferencePath::new("../escape.md").is_err());
    assert!(ReferencePath::new("invalid.xyz").is_err());
}

/// Test ReferencePath with various extensions.
#[test]
fn test_reference_path_extensions() {
    for ext in &["md", "pdf", "txt", "html", "json", "yaml", "yml"] {
        let path = format!("docs/file.{}", ext);
        assert!(
            ReferencePath::new(path).is_ok(),
            "Extension {} should be valid",
            ext
        );
    }
}

/// Test empty ReferencePath is rejected.
#[test]
fn test_reference_path_empty() {
    assert!(ReferencePath::new("").is_err());
    assert!(ReferencePath::new("   ").is_err());
}

/// Test ReferencePath display implementation.
#[test]
fn test_reference_path_display() {
    let path = ReferencePath::new("docs/test.md").unwrap();
    assert_eq!(path.to_string(), "docs/test.md");
}

/// Test SnifferRule with different types.
#[test]
fn test_sniffer_rule_types() {
    let file_exists = SnifferRule::new("file_exists", "package.json");
    assert_eq!(file_exists.rule_type, "file_exists");

    let file_pattern = SnifferRule::new("file_pattern", "*.py");
    assert_eq!(file_pattern.rule_type, "file_pattern");
}

/// Test SkillIndexEntry default values.
#[test]
fn test_skill_index_entry_defaults() {
    let entry = SkillIndexEntry::new(
        "test".to_string(),
        "Test skill".to_string(),
        "1.0.0".to_string(),
        "assets/skills/test".to_string(),
    );

    assert!(entry.tools.is_empty());
    assert!(entry.routing_keywords.is_empty());
    assert!(entry.intents.is_empty());
    assert_eq!(entry.authors, vec!["omni-dev-fusion".to_string()]);
    assert!(entry.sniffing_rules.is_empty());
}
