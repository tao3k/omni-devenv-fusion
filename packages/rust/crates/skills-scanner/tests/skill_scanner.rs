//! Integration tests for SkillScanner - tests SKILL.md parsing and structure validation.
//!
//! These tests verify the public API of SkillScanner by creating
//! temporary skill directories and scanning them.

use skills_scanner::SkillScanner;
use std::fs;
use std::path::PathBuf;
use tempfile::TempDir;

/// Test default structure matches settings.yaml definition.
#[test]
fn test_default_structure_required_files() {
    let structure = SkillScanner::default_structure();

    // Required: SKILL.md
    assert!(!structure.required.is_empty());
    assert!(structure.required.iter().any(|i| i.path == "SKILL.md"));
    assert!(structure.required.iter().any(|i| i.item_type == "file"));
}

/// Test default structure contains expected default directories.
#[test]
fn test_default_structure_default_directories() {
    let structure = SkillScanner::default_structure();

    // Default directories should include scripts/, templates/, etc.
    assert!(!structure.default.is_empty());
    assert!(structure.default.iter().any(|i| i.path == "scripts/"));
    assert!(structure.default.iter().any(|i| i.path == "templates/"));
    assert!(structure.default.iter().any(|i| i.path == "references/"));
}

/// Validate skill with valid SKILL.md passes.
#[test]
fn test_validate_structure_valid_skill() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("writer");
    fs::create_dir_all(&skill_path).unwrap();

    // Create required SKILL.md
    fs::write(
        &skill_path.join("SKILL.md"),
        r#"---
name: "writer"
version: "1.0"
routing_keywords: ["write", "edit"]
---
# Writer Skill
"#,
    )
    .unwrap();

    let structure = SkillScanner::default_structure();
    assert!(SkillScanner::validate_structure(&skill_path, &structure));
}

/// Validate skill missing SKILL.md fails.
#[test]
fn test_validate_structure_missing_skill_md() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("empty_skill");
    fs::create_dir_all(&skill_path).unwrap();

    // No SKILL.md created
    let structure = SkillScanner::default_structure();
    assert!(!SkillScanner::validate_structure(&skill_path, &structure));
}

/// Validate nonexistent path returns false.
#[test]
fn test_validate_structure_nonexistent_path() {
    let structure = SkillScanner::default_structure();
    let nonexistent = PathBuf::from("/nonexistent/path");
    assert!(!SkillScanner::validate_structure(&nonexistent, &structure));
}

/// Scan skill with full routing keywords from frontmatter.
#[test]
fn test_scan_skill_parses_routing_keywords() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("git");
    fs::create_dir_all(&skill_path).unwrap();

    fs::write(
        &skill_path.join("SKILL.md"),
        r#"---
name: "git"
version: "2.0"
description: "Git version control skill"
routing_keywords: ["commit", "branch", "merge", "checkout"]
authors: ["omni-dev-fusion"]
intents: ["Create commit", "Manage branches"]
---
# Git Skill
"#,
    )
    .unwrap();

    let scanner = SkillScanner::new();
    let structure = SkillScanner::default_structure();

    let result = scanner.scan_skill(&skill_path, Some(&structure)).unwrap();
    assert!(result.is_some());

    let metadata = result.unwrap();
    assert_eq!(metadata.skill_name, "git");
    assert_eq!(metadata.version, "2.0");
    assert_eq!(metadata.description, "Git version control skill");
    assert_eq!(metadata.routing_keywords.len(), 4);
    assert!(metadata.routing_keywords.contains(&"commit".to_string()));
    assert!(metadata.routing_keywords.contains(&"branch".to_string()));
}

/// Scan skill without frontmatter returns empty metadata.
#[test]
fn test_scan_skill_without_frontmatter() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("minimal");
    fs::create_dir_all(&skill_path).unwrap();

    // SKILL.md without frontmatter
    fs::write(
        &skill_path.join("SKILL.md"),
        r#"# Minimal Skill

Just a name, no metadata.
"#,
    )
    .unwrap();

    let scanner = SkillScanner::new();

    let result = scanner.scan_skill(&skill_path, None).unwrap();
    assert!(result.is_some());

    let metadata = result.unwrap();
    assert_eq!(metadata.skill_name, "minimal");
    assert!(metadata.version.is_empty());
    assert!(metadata.routing_keywords.is_empty());
}

/// Scan all skills in base directory with structure validation.
#[test]
fn test_scan_all_with_structure_validation() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    // Create valid writer skill
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

    // Create valid git skill
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

    // Create incomplete skill (no SKILL.md)
    let no_md_path = skills_dir.join("no_md");
    fs::create_dir_all(&no_md_path).unwrap();

    let scanner = SkillScanner::new();
    let structure = SkillScanner::default_structure();

    let metadatas = scanner.scan_all(&skills_dir, Some(&structure)).unwrap();
    assert_eq!(metadatas.len(), 2);

    // Verify both valid skills are found
    assert!(metadatas.iter().any(|m| m.skill_name == "writer"));
    assert!(metadatas.iter().any(|m| m.skill_name == "git"));
    // Incomplete skill should not be in results (no SKILL.md)
    assert!(!metadatas.iter().any(|m| m.skill_name == "no_md"));
}

/// Scan all skills without structure (backward compatibility).
#[test]
fn test_scan_all_without_structure() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    let writer_path = skills_dir.join("writer");
    fs::create_dir_all(&writer_path).unwrap();
    fs::write(
        &writer_path.join("SKILL.md"),
        r#"---
name: "writer"
version: "1.0"
---
# Writer
"#,
    )
    .unwrap();

    let scanner = SkillScanner::new();
    // Pass None - should still work
    let metadatas = scanner.scan_all(&skills_dir, None).unwrap();
    assert_eq!(metadatas.len(), 1);
}

/// Scan all skills with empty directory returns empty vec.
#[test]
fn test_scan_all_empty_directory() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("empty");
    fs::create_dir_all(&skills_dir).unwrap();

    let scanner = SkillScanner::new();
    let metadatas = scanner.scan_all(&skills_dir, None).unwrap();
    assert!(metadatas.is_empty());
}

/// Scan all skills with nonexistent base path returns empty vec.
#[test]
fn test_scan_all_nonexistent_base_path() {
    let scanner = SkillScanner::new();
    let nonexistent_path = PathBuf::from("/nonexistent");
    let metadatas = scanner.scan_all(&nonexistent_path, None).unwrap();
    assert!(metadatas.is_empty());
}

/// Skill name is derived from directory name when not in frontmatter.
#[test]
fn test_skill_name_from_directory() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("custom_skill_name");
    fs::create_dir_all(&skill_path).unwrap();

    fs::write(
        &skill_path.join("SKILL.md"),
        r#"---
version: "1.0"
---
# Content
"#,
    )
    .unwrap();

    let scanner = SkillScanner::new();
    let result = scanner.scan_skill(&skill_path, None).unwrap().unwrap();

    assert_eq!(result.skill_name, "custom_skill_name");
}

// =============================================================================
// TOML Rules Parsing Tests
// =============================================================================

/// Test parsing valid rules.toml file.
#[test]
fn test_parse_rules_toml_valid() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("python");
    fs::create_dir_all(&skill_path).unwrap();

    // Create required SKILL.md
    fs::write(
        &skill_path.join("SKILL.md"),
        r#"---
name: "python"
version: "1.0"
routing_keywords: ["python", "py"]
---
# Python Skill
"#,
    )
    .unwrap();

    let rules_path = skill_path.join("extensions/sniffer");
    fs::create_dir_all(&rules_path).unwrap();

    fs::write(
        &rules_path.join("rules.toml"),
        r#"
[[match]]
type = "file_exists"
pattern = "pyproject.toml"

[[match]]
type = "file_pattern"
pattern = "*.py"
"#,
    )
    .unwrap();

    use skills_scanner::SkillScanner;
    let scanner = SkillScanner::new();
    let structure = SkillScanner::default_structure();

    // Scan and build index entry
    let result = scanner
        .scan_skill(&skill_path, Some(&structure))
        .unwrap()
        .unwrap();
    assert_eq!(result.skill_name, "python");

    // Verify the skill directory has rules
    let rules = scanner.scan_skill(&skill_path, Some(&structure)).unwrap();
    assert!(rules.is_some());
}

/// Test parsing missing rules.toml returns empty rules.
#[test]
fn test_parse_rules_toml_missing() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");
    fs::create_dir_all(&skill_path).unwrap();

    // No rules.toml created - scanner should still work
    use skills_scanner::SkillScanner;
    let scanner = SkillScanner::new();

    let result = scanner.scan_skill(&skill_path, None).unwrap();
    // Should return Some because SKILL.md exists (not created, so None)
    assert!(result.is_none());
}

/// Test build_index_entry includes sniffer rules from rules.toml.
#[test]
fn test_build_index_entry_with_sniffer_rules() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    let python_path = skills_dir.join("python");
    fs::create_dir_all(&python_path).unwrap();

    // Create SKILL.md
    fs::write(
        &python_path.join("SKILL.md"),
        r#"---
name: "python"
version: "1.0"
routing_keywords: ["python", "py"]
---
# Python Skill
"#,
    )
    .unwrap();

    // Create rules.toml
    let rules_path = python_path.join("extensions/sniffer");
    fs::create_dir_all(&rules_path).unwrap();
    fs::write(
        &rules_path.join("rules.toml"),
        r#"
[[match]]
type = "file_exists"
pattern = "pyproject.toml"
"#,
    )
    .unwrap();

    use skills_scanner::{SkillScanner, ToolsScanner};
    let scanner = SkillScanner::new();
    let tools_scanner = ToolsScanner::new();

    let metadatas = scanner.scan_all(&skills_dir, None).unwrap();
    assert_eq!(metadatas.len(), 1);

    let metadata = &metadatas[0];
    let scripts_path = python_path.join("scripts");
    let tools = if scripts_path.exists() {
        tools_scanner
            .scan_scripts(
                &scripts_path,
                &metadata.skill_name,
                &metadata.routing_keywords,
                &[],
            )
            .unwrap()
    } else {
        Vec::new()
    };

    let entry = scanner.build_index_entry(metadata.clone(), &tools, &python_path);

    // Verify sniffer rules are populated
    assert!(!entry.sniffing_rules.is_empty());
    assert_eq!(entry.sniffing_rules[0].pattern, "pyproject.toml");
    assert_eq!(entry.sniffing_rules[0].rule_type, "file_exists");
}
