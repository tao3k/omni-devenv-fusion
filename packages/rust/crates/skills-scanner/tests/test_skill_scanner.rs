//! Tests for skill_scanner module.
//!
//! Tests SKILL.md parsing and SkillScanner functionality.

use skills_scanner::{SkillScanner, SnifferRule, extract_frontmatter};
use std::fs;
use tempfile::TempDir;

/// Test SkillScanner creates valid instance.
#[test]
fn test_skill_scanner_new() {
    let scanner = SkillScanner::new();
    // Just verify it can be created
    assert!(true);
}

/// Test SnifferRule creation.
#[test]
fn test_sniffer_rule_creation() {
    let rule = SnifferRule::new("file_exists", "Cargo.toml");
    assert_eq!(rule.rule_type, "file_exists");
    assert_eq!(rule.pattern, "Cargo.toml");
}

/// Test scanning a valid skill directory.
#[test]
fn test_scan_valid_skill_directory() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    // Create a test skill
    let skill_path = skills_dir.join("test_skill");
    fs::create_dir_all(&skill_path).unwrap();
    fs::write(
        &skill_path.join("SKILL.md"),
        r#"---
name: "test_skill"
version: "1.0.0"
routing_keywords: ["test", "example"]
description: "A test skill"
---
# Test Skill
"#,
    )
    .unwrap();

    let scanner = SkillScanner::new();
    let results = scanner.scan_all(&skills_dir, None).unwrap();

    assert_eq!(results.len(), 1);
    let skill = &results[0];
    assert_eq!(skill.skill_name, "test_skill");
    assert_eq!(skill.version, "1.0.0");
    assert!(skill.routing_keywords.contains(&"test".to_string()));
}

/// Test scanning empty skills directory.
#[test]
fn test_scan_empty_skills_directory() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    let scanner = SkillScanner::new();
    let results = scanner.scan_all(&skills_dir, None).unwrap();

    assert!(results.is_empty());
}

/// Test parsing a skill with full frontmatter.
#[test]
fn test_parse_skill_md_full_frontmatter() {
    let content = r#"---
name: "writer"
version: "1.1.0"
description: "Text manipulation skill"
routing_keywords: ["write", "edit", "polish"]
authors: ["omni-dev-fusion"]
intents: ["Update documentation"]
---

# Writer Skill
"#;

    let scanner = SkillScanner::new();
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("writer");

    let metadata = scanner.parse_skill_md(content, &skill_path).unwrap();

    assert_eq!(metadata.skill_name, "writer");
    assert_eq!(metadata.version, "1.1.0");
    assert_eq!(metadata.description, "Text manipulation skill");
    assert_eq!(metadata.routing_keywords, vec!["write", "edit", "polish"]);
    assert_eq!(metadata.authors, vec!["omni-dev-fusion"]);
    assert_eq!(metadata.intents, vec!["Update documentation"]);
}

/// Test parsing a skill without frontmatter.
#[test]
fn test_parse_skill_md_without_frontmatter() {
    let content = "# Writer Skill\n\nJust a skill without frontmatter.";

    let scanner = SkillScanner::new();
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("writer");

    let metadata = scanner.parse_skill_md(content, &skill_path).unwrap();

    assert_eq!(metadata.skill_name, "writer");
    assert!(metadata.version.is_empty());
    assert!(metadata.routing_keywords.is_empty());
}

/// Test scanning a skill with missing SKILL.md.
#[test]
fn test_scan_skill_missing_skill_md() {
    let scanner = SkillScanner::new();
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("empty_skill");
    fs::create_dir_all(&skill_path).unwrap();

    let result = scanner.scan_skill(&skill_path, None).unwrap();
    assert!(result.is_none());
}

/// Test scanning multiple skills.
#[test]
fn test_scan_all_multiple_skills() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    // Create writer skill
    let writer_path = skills_dir.join("writer");
    fs::create_dir_all(&writer_path).unwrap();
    fs::write(
        &writer_path.join("SKILL.md"),
        r#"---
name: "writer"
version: "1.0"
routing_keywords: ["write", "edit"]
---
# Writer
"#,
    )
    .unwrap();

    // Create git skill
    let git_path = skills_dir.join("git");
    fs::create_dir_all(&git_path).unwrap();
    fs::write(
        &git_path.join("SKILL.md"),
        r#"---
name: "git"
version: "1.0"
routing_keywords: ["commit", "branch"]
---
# Git
"#,
    )
    .unwrap();

    let scanner = SkillScanner::new();
    let metadatas = scanner.scan_all(&skills_dir, None).unwrap();

    assert_eq!(metadatas.len(), 2);
    assert!(metadatas.iter().any(|m| m.skill_name == "writer"));
    assert!(metadatas.iter().any(|m| m.skill_name == "git"));
}

/// Test extract frontmatter helper.
#[test]
fn test_extract_frontmatter() {
    let content = r#"---
name: "test"
version: "1.0"
---
# Content
"#;

    let frontmatter = extract_frontmatter(content).unwrap();
    assert!(frontmatter.contains("name:"));
    assert!(frontmatter.contains("version:"));
}

/// Test extract frontmatter when not present.
#[test]
fn test_extract_frontmatter_no_frontmatter() {
    let content = "# Just content\nNo frontmatter here.";
    assert!(extract_frontmatter(content).is_none());
}

/// Test default skill structure.
#[test]
fn test_default_structure() {
    let structure = SkillScanner::default_structure();

    assert!(!structure.required.is_empty());
    assert!(structure.required.iter().any(|i| i.path == "SKILL.md"));
}

/// Test validate structure with valid skill.
#[test]
fn test_validate_structure_valid() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");
    fs::create_dir_all(&skill_path).unwrap();
    fs::write(&skill_path.join("SKILL.md"), "---\nname: test\n---").unwrap();

    let structure = SkillScanner::default_structure();
    assert!(SkillScanner::validate_structure(&skill_path, &structure));
}

/// Test validate structure with missing SKILL.md.
#[test]
fn test_validate_structure_missing_skill_md() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");
    fs::create_dir_all(&skill_path).unwrap();

    let structure = SkillScanner::default_structure();
    assert!(!SkillScanner::validate_structure(&skill_path, &structure));
}
