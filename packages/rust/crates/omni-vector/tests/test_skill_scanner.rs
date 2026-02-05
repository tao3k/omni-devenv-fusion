//! Tests for SkillScanner - SKILL.md parsing.

use omni_scanner::{SkillScanner, SkillStructure, ToolsScanner, extract_frontmatter};
use tempfile::TempDir;

#[test]
fn test_parse_skill_md_with_frontmatter() {
    let content = r#"---
name: writer
description: Use when editing files or writing documentation
metadata:
  author: omni-dev-fusion
  version: "1.1.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/writer"
  routing_keywords:
    - "write"
    - "edit"
    - "polish"
  intents:
    - "Update documentation"
---

# Writer Skill
"#;

    let scanner = SkillScanner::new();
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("writer");
    std::fs::create_dir_all(&skill_path).unwrap();

    let manifest = scanner.parse_skill_md(content, &skill_path).unwrap();

    assert_eq!(manifest.skill_name, "writer");
    assert_eq!(manifest.version, "1.1.0");
    assert_eq!(
        manifest.description,
        "Use when editing files or writing documentation"
    );
    assert_eq!(manifest.routing_keywords, vec!["write", "edit", "polish"]);
    assert_eq!(manifest.authors, vec!["omni-dev-fusion"]);
    assert_eq!(manifest.intents, vec!["Update documentation"]);
}

#[test]
fn test_parse_skill_md_without_frontmatter() {
    let content = "# Writer Skill\n\nJust a skill without frontmatter.";

    let scanner = SkillScanner::new();
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("writer");

    let manifest = scanner.parse_skill_md(content, &skill_path).unwrap();

    assert_eq!(manifest.skill_name, "writer");
    assert!(manifest.version.is_empty());
    assert!(manifest.routing_keywords.is_empty());
}

#[test]
fn test_scan_skill_missing_skill_md() {
    let scanner = SkillScanner::new();
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("empty_skill");
    std::fs::create_dir_all(&skill_path).unwrap();

    let result = scanner.scan_skill(&skill_path, None).unwrap();
    assert!(result.is_none());
}

#[test]
fn test_scan_all_multiple_skills() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    std::fs::create_dir_all(&skills_dir).unwrap();

    // Create writer skill
    let writer_path = skills_dir.join("writer");
    std::fs::create_dir_all(&writer_path).unwrap();
    std::fs::write(
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
    std::fs::create_dir_all(&git_path).unwrap();
    std::fs::write(
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
    let structure = SkillStructure::default();
    let manifests = scanner.scan_all(&skills_dir, Some(&structure)).unwrap();

    assert_eq!(manifests.len(), 2);
    assert!(manifests.iter().any(|m| m.skill_name == "writer"));
    assert!(manifests.iter().any(|m| m.skill_name == "git"));
}

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

#[test]
fn test_extract_frontmatter_no_frontmatter() {
    let content = "# Just content\nNo frontmatter here.";
    assert!(extract_frontmatter(content).is_none());
}

/// Regression test: Verify routing keywords are scanned from SKILL.md
#[test]
fn test_scan_skill_tools_includes_routing_keywords() {
    let skill_scanner = SkillScanner::new();
    let script_scanner = ToolsScanner::new();
    let structure = SkillStructure::default();

    // manifest_dir: packages/rust/crates/omni-vector
    let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));

    // Navigate up to project root (5 levels up)
    let project_root = manifest_dir
        .parent()
        .unwrap() // omni-vector -> crates
        .parent()
        .unwrap() // crates -> rust
        .parent()
        .unwrap() // rust -> packages
        .parent()
        .unwrap() // packages -> omni-dev-fusion
        .parent()
        .unwrap(); // omni-dev-fusion -> parent

    let skills_path = project_root.join("omni-dev-fusion").join("assets/skills");

    if !skills_path.exists() {
        println!("skills directory not found, skipping test");
        return;
    }

    // Get metadatas for routing_keywords
    let metadatas = skill_scanner
        .scan_all(&skills_path, Some(&structure))
        .unwrap();

    // Find writer skill metadata
    let writer_metadata = metadatas
        .iter()
        .find(|m| m.skill_name == "writer")
        .expect("writer skill should exist");

    // Verify routing_keywords are not empty
    assert!(
        !writer_metadata.routing_keywords.is_empty(),
        "writer skill should have routing_keywords"
    );

    // Scan scripts with routing_keywords
    let skill_scripts_path = skills_path.join("writer").join("scripts");
    let tools = script_scanner
        .scan_scripts(
            &skill_scripts_path,
            "writer",
            &writer_metadata.routing_keywords,
            &[],
        )
        .unwrap();

    // Verify tools have routing_keywords
    assert!(!tools.is_empty(), "writer skill should have tools");

    for tool in &tools {
        // Check that routing_keywords are included in tool keywords
        let has_routing_kw = tool
            .keywords
            .iter()
            .any(|kw| writer_metadata.routing_keywords.contains(kw));

        assert!(
            has_routing_kw,
            "Tool {} should include at least one routing keyword from SKILL.md",
            tool.tool_name
        );
    }
}
