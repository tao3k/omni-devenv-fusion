//! Full workflow integration test for skills-scanner.
//!
//! Tests the complete scanning workflow: SKILL.md + scripts.

use skills_scanner::VERSION;
use skills_scanner::{SkillScanner, ToolsScanner};
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
    let tools_scanner = ToolsScanner::new();
    let writer_metadata = metadatas.iter().find(|m| m.skill_name == "writer").unwrap();
    let tools = tools_scanner
        .scan_scripts(
            &writer_scripts,
            "writer",
            &writer_metadata.routing_keywords,
            &writer_metadata.intents,
        )
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

/// Test that duplicate tools within the same skill are detected by scanner.
/// Note: The scanner itself returns duplicates; deduplication happens in:
/// - Python: scan_skill_tools() in bindings/python/src/scanner.rs
/// - Rust: index_skill_tools() in omni-vector/src/skill.rs
#[test]
fn test_scanner_reports_duplicate_tools() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    // Create test skill
    let test_path = skills_dir.join("test");
    fs::create_dir_all(&test_path).unwrap();
    fs::write(
        &test_path.join("SKILL.md"),
        r#"---
name: "test"
version: "1.0.0"
routing_keywords: ["test"]
---
# Test Skill
"#,
    )
    .unwrap();

    let test_scripts = test_path.join("scripts");
    fs::create_dir_all(&test_scripts).unwrap();

    // Create first file with a tool
    fs::write(
        &test_scripts.join("commands.py"),
        r#"
@skill_command(name="run_test")
def run_test(path: str) -> str:
    '''Run a test.'''
    return "passed"
"#,
    )
    .unwrap();

    // Create second file with SAME tool name (this is the duplicate scenario)
    fs::write(
        &test_scripts.join("more_commands.py"),
        r#"
@skill_command(name="run_test")
def run_test_alt(path: str) -> str:
    '''Another run_test definition.'''
    return "also passed"
"#,
    )
    .unwrap();

    // Scan scripts
    let tools_scanner = ToolsScanner::new();
    let tools = tools_scanner
        .scan_scripts(&test_scripts, "test", &["test".to_string()], &[])
        .unwrap();

    // The scanner SHOULD find 2 tools (both definitions)
    // Deduplication is the responsibility of the caller (scan_skill_tools, index_skill_tools)
    assert_eq!(
        tools.len(),
        2,
        "Scanner should find both tools, deduplication happens at higher level. Found: {:?}",
        tools.iter().map(|t| &t.tool_name).collect::<Vec<_>>()
    );

    // Both have the same tool_name
    assert_eq!(tools[0].tool_name, "test.run_test");
    assert_eq!(tools[1].tool_name, "test.run_test");

    // But different file_hash (since content differs)
    assert_ne!(
        tools[0].file_hash, tools[1].file_hash,
        "Duplicate tools should have different file hashes"
    );
}

/// Test that tools from different skills can have the same function name
/// but different full tool names (skill.function_name).
#[test]
fn test_same_function_name_different_skills() {
    let temp_dir = TempDir::new().unwrap();
    let skills_dir = temp_dir.path().join("skills");
    fs::create_dir_all(&skills_dir).unwrap();

    // Create skill1
    let skill1_path = skills_dir.join("skill1");
    fs::create_dir_all(&skill1_path).unwrap();
    fs::write(
        &skill1_path.join("SKILL.md"),
        r#"---
name: "skill1"
version: "1.0.0"
routing_keywords: ["s1"]
---
# Skill 1
"#,
    )
    .unwrap();

    // Create skill2
    let skill2_path = skills_dir.join("skill2");
    fs::create_dir_all(&skill2_path).unwrap();
    fs::write(
        &skill2_path.join("SKILL.md"),
        r#"---
name: "skill2"
version: "1.0.0"
routing_keywords: ["s2"]
---
# Skill 2
"#,
    )
    .unwrap();

    // Both skills have a "process" function
    for (_, skill_path) in [("skill1", &skill1_path), ("skill2", &skill2_path)] {
        let scripts = skill_path.join("scripts");
        fs::create_dir_all(&scripts).unwrap();
        fs::write(
            &scripts.join("main.py"),
            r#"
@skill_command(name="process")
def process(data: str) -> str:
    '''Process data.'''
    return "done"
"#,
        )
        .unwrap();
    }

    // Scan both skills
    let tools_scanner = ToolsScanner::new();

    let tools1 = tools_scanner
        .scan_scripts(
            &skill1_path.join("scripts"),
            "skill1",
            &["s1".to_string()],
            &[],
        )
        .unwrap();
    let tools2 = tools_scanner
        .scan_scripts(
            &skill2_path.join("scripts"),
            "skill2",
            &["s2".to_string()],
            &[],
        )
        .unwrap();

    // Both should have 1 tool
    assert_eq!(tools1.len(), 1);
    assert_eq!(tools2.len(), 1);

    // But different full names
    assert_eq!(tools1[0].tool_name, "skill1.process");
    assert_eq!(tools2[0].tool_name, "skill2.process");
}
