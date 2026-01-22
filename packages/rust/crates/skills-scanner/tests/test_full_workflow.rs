//! Full workflow integration test for skills-scanner.
//!
//! Tests the complete scanning workflow: SKILL.md + scripts.

use skills_scanner::VERSION;
use skills_scanner::{ScriptScanner, SkillScanner};
use std::fs;
use tempfile::TempDir;

/// Test the complete scanning workflow.
#[test]
fn test_full_scan_workflow() {
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
version: "1.1.0"
routing_keywords: ["write", "edit", "polish"]
---
# Writer
"#,
    )
    .unwrap();

    let writer_scripts = writer_path.join("scripts");
    fs::create_dir_all(&writer_scripts).unwrap();
    fs::write(
        &writer_scripts.join("text.py"),
        r#"
@skill_command(name="write_text")
def write_text(content: str) -> str:
    '''Write text to file.'''
    return "written"
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

    // Scan metadatas
    let skill_scanner = SkillScanner::new();
    let metadatas = skill_scanner.scan_all(&skills_dir, None).unwrap();
    assert_eq!(metadatas.len(), 2);

    // Scan scripts for writer
    let script_scanner = ScriptScanner::new();
    let writer_metadata = metadatas.iter().find(|m| m.skill_name == "writer").unwrap();
    let tools = script_scanner
        .scan_scripts(&writer_scripts, "writer", &writer_metadata.routing_keywords)
        .unwrap();

    assert_eq!(tools.len(), 1);
    assert_eq!(tools[0].tool_name, "writer.write_text");
    // Verify routing keywords are included
    assert!(tools[0].keywords.contains(&"write".to_string()));
}

/// Test that VERSION constant is valid.
#[test]
fn test_version_constant() {
    assert!(!VERSION.is_empty());
    // Version should match Cargo.toml
    assert_eq!(VERSION, env!("CARGO_PKG_VERSION"));
}

/// Test multiple skills with different configurations.
#[test]
fn test_multiple_skills_scan() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    // Create python skill
    let python_path = skills_dir.join("python");
    fs::create_dir_all(&python_path).unwrap();
    fs::write(
        &python_path.join("SKILL.md"),
        r#"---
name: "python"
version: "2.0.0"
routing_keywords: ["python", "py"]
---
# Python Skill
"#,
    )
    .unwrap();

    // Create rust skill
    let rust_path = skills_dir.join("rust");
    fs::create_dir_all(&rust_path).unwrap();
    fs::write(
        &rust_path.join("SKILL.md"),
        r#"---
name: "rust"
version: "1.5.0"
routing_keywords: ["rust", "cargo"]
---
# Rust Skill
"#,
    )
    .unwrap();

    let scanner = SkillScanner::new();
    let results = scanner.scan_all(&skills_dir, None).unwrap();

    assert_eq!(results.len(), 2);

    // Verify python skill
    let python = results.iter().find(|s| s.skill_name == "python").unwrap();
    assert_eq!(python.version, "2.0.0");
    assert!(python.routing_keywords.contains(&"python".to_string()));

    // Verify rust skill
    let rust = results.iter().find(|s| s.skill_name == "rust").unwrap();
    assert_eq!(rust.version, "1.5.0");
    assert!(rust.routing_keywords.contains(&"rust".to_string()));
}
