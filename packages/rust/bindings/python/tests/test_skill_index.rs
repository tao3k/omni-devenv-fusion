//! Tests for Python bindings - skill index deduplication.
//!
//! Verifies that get_skill_index correctly deduplicates tools
//! by reusing SkillScanner::build_index_entry.

use std::fs;
use tempfile::TempDir;

/// Test that build_index_entry deduplicates tools with the same name.
///
/// This is the core deduplication logic reused by PyVectorStore::get_skill_index.
#[test]
fn test_build_index_entry_deduplicates_tools() {
    use skills_scanner::{SkillMetadata, SkillScanner, ToolRecord};

    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");

    let metadata = SkillMetadata {
        skill_name: "test_skill".to_string(),
        version: "1.0.0".to_string(),
        description: "A test skill".to_string(),
        routing_keywords: vec!["test".to_string()],
        authors: vec!["test".to_string()],
        intents: vec![],
        require_refs: vec![],
        repository: "".to_string(),
        permissions: vec![],
    };

    // Create tools with duplicate names
    let tools = vec![
        ToolRecord {
            tool_name: "test_skill.duplicate_tool".to_string(),
            description: "First definition".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/test.py".to_string(),
            function_name: "duplicate_tool".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["test".to_string()],
            intents: vec![],
            file_hash: "hash1".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "First definition".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
        },
        // Duplicate from another function with same tool name
        ToolRecord {
            tool_name: "test_skill.duplicate_tool".to_string(),
            description: "Second definition".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/test.py".to_string(),
            function_name: "another_func".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["test".to_string()],
            intents: vec![],
            file_hash: "hash2".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "Second definition".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
        },
        // Unique tool
        ToolRecord {
            tool_name: "test_skill.unique_tool".to_string(),
            description: "Unique tool".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/test.py".to_string(),
            function_name: "unique_tool".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["test".to_string()],
            intents: vec![],
            file_hash: "hash3".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "Unique tool".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
        },
    ];

    let scanner = SkillScanner::new();
    let entry = scanner.build_index_entry(metadata, &tools, &skill_path);

    // Should have exactly 2 unique tools (not 3)
    assert_eq!(entry.tools.len(), 2);

    // Collect tool names
    let tool_names: Vec<&str> = entry.tools.iter().map(|t| t.name.as_str()).collect();

    // Should contain both unique_tool and one instance of duplicate_tool
    assert!(tool_names.contains(&"test_skill.unique_tool"));
    assert!(tool_names.contains(&"test_skill.duplicate_tool"));

    // Should NOT contain duplicate_tool twice
    assert_eq!(
        tool_names
            .iter()
            .filter(|&&n| n == "test_skill.duplicate_tool")
            .count(),
        1
    );
}

/// Test that build_index_entry preserves order of first occurrences.
#[test]
fn test_build_index_entry_preserves_order() {
    use skills_scanner::{SkillMetadata, SkillScanner, ToolRecord};

    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");

    let metadata = SkillMetadata {
        skill_name: "test_skill".to_string(),
        version: "1.0.0".to_string(),
        description: "A test skill".to_string(),
        routing_keywords: vec!["test".to_string()],
        authors: vec!["test".to_string()],
        intents: vec![],
        require_refs: vec![],
        repository: "".to_string(),
        permissions: vec![],
    };

    // Create tools where tool_b appears before tool_a
    let tools = vec![
        ToolRecord {
            tool_name: "test_skill.tool_b".to_string(),
            description: "Tool B".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/b.py".to_string(),
            function_name: "tool_b".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["test".to_string()],
            intents: vec![],
            file_hash: "hash_b".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "Tool B".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
        },
        ToolRecord {
            tool_name: "test_skill.tool_a".to_string(),
            description: "Tool A".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/a.py".to_string(),
            function_name: "tool_a".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["test".to_string()],
            intents: vec![],
            file_hash: "hash_a".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "Tool A".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
        },
    ];

    let scanner = SkillScanner::new();
    let entry = scanner.build_index_entry(metadata, &tools, &skill_path);

    // Should preserve order of first occurrence
    assert_eq!(entry.tools.len(), 2);
    assert_eq!(entry.tools[0].name, "test_skill.tool_b");
    assert_eq!(entry.tools[1].name, "test_skill.tool_a");
}

/// Test that empty tools list works correctly.
#[test]
fn test_build_index_entry_empty_tools() {
    use skills_scanner::{SkillMetadata, SkillScanner};

    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");

    let metadata = SkillMetadata {
        skill_name: "test_skill".to_string(),
        version: "1.0.0".to_string(),
        description: "A test skill".to_string(),
        routing_keywords: vec![],
        authors: vec![],
        intents: vec![],
        require_refs: vec![],
        repository: "".to_string(),
        permissions: vec![],
    };

    let scanner = SkillScanner::new();
    let entry = scanner.build_index_entry(metadata, &[], &skill_path);

    assert_eq!(entry.tools.len(), 0);
    assert_eq!(entry.name, "test_skill");
}

/// Test that PyVectorStore get_skill_index correctly deduplicates tools.
#[test]
fn test_py_vector_store_get_skill_index_deduplication() {
    // Create a temporary skills directory
    let temp_dir = TempDir::new().unwrap();
    let skills_path = temp_dir.path();

    // Create a skill with SKILL.md
    let skill_path = skills_path.join("test_skill");
    fs::create_dir_all(&skill_path).unwrap();
    fs::create_dir_all(skill_path.join("scripts")).unwrap();

    // Create SKILL.md with frontmatter
    let skill_md = r#"---
name: "test_skill"
version: "1.0.0"
description: "A test skill"
routing_keywords: ["test"]
authors: ["test"]
intents: []
---
# Test Skill
"#;
    fs::write(skill_path.join("SKILL.md"), skill_md).unwrap();

    // Create a script with multiple functions using the same tool name
    let script = r#"
from omni.foundation.api.decorators import skill_command

@skill_command(name="duplicate_tool")
def duplicate_tool():
    '''First definition'''
    pass

@skill_command(name="duplicate_tool")
def another_func():
    '''Second definition with same tool name'''
    pass

@skill_command(name="unique_tool")
def unique_tool():
    '''Unique tool'''
    pass
"#;
    fs::write(skill_path.join("scripts").join("test.py"), script).unwrap();

    // Use the Rust skill scanner directly to test
    use skills_scanner::{SkillScanner, ToolsScanner};

    let skill_scanner = SkillScanner::new();
    let script_scanner = ToolsScanner::new();

    // Scan skill metadata
    let metadatas = skill_scanner.scan_all(skills_path, None).unwrap();
    assert_eq!(metadatas.len(), 1);

    let metadata = &metadatas[0];
    let skill_scripts_path = skill_path.join("scripts");

    // Scan tools
    let tool_records = script_scanner
        .scan_scripts(
            &skill_scripts_path,
            &metadata.skill_name,
            &metadata.routing_keywords,
            &metadata.intents,
        )
        .unwrap();

    // Build index entry (this should deduplicate)
    let entry = skill_scanner.build_index_entry(metadata.clone(), &tool_records, &skill_path);

    // Should have exactly 2 unique tools
    assert_eq!(entry.tools.len(), 2);

    // Verify no duplicate names
    let names: Vec<&str> = entry.tools.iter().map(|t| t.name.as_str()).collect();
    assert!(names.contains(&"test_skill.unique_tool"));
    assert!(names.contains(&"test_skill.duplicate_tool"));
}
