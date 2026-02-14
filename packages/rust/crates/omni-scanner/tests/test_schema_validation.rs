//! Schema Validation Tests for omni-scanner
//!
//! Critical tests to ensure data schema integrity.
//! These tests verify that:
//! - Tool names follow the correct format: "skill.command" (NOT "skill.skill.command")
//! - JSON serialization/deserialization preserves schema integrity
//! - Index entries contain correctly formatted tool references
//!
//! The tool name schema is the core contract between Rust scanner and Python consumers.

use omni_scanner::{
    IndexToolEntry, SkillIndexEntry, SkillMetadata, SkillScanner, SkillStructure, ToolAnnotations,
    ToolRecord, ToolsScanner,
};
use serde_json;
use std::fs;
use tempfile::TempDir;

/// Validates that tool_name follows the "skill.command" format.
///
/// This is the CORE SCHEMA invariant that MUST be maintained.
/// Tool names must NOT have repeated skill prefixes.
/// CORRECT: "git.smart_commit", "filesystem.read_file"
/// WRONG:   "git.git.smart_commit", "filesystem.filesystem.read_file"
#[test]
fn test_tool_name_format_schema_invariant() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("git/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Create a script with @skill_command decorator
    fs::write(
        &scripts_dir.join("commit.py"),
        r#"
@skill_command(name="smart_commit")
def smart_commit(action: str = "start") -> str:
    '''Smart commit workflow.'''
    return "ok"
"#,
    )
    .unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "git", &["commit".to_string()], &[])
        .unwrap();

    assert_eq!(tools.len(), 1, "Should find exactly one tool");

    let tool = &tools[0];

    // CORE SCHEMA VALIDATION
    assert_eq!(
        tool.tool_name, "git.smart_commit",
        "Tool name MUST be 'skill.command' format. Got: '{}'",
        tool.tool_name
    );

    // Additional validation: tool_name should not contain repeated skill prefix
    let parts: Vec<&str> = tool.tool_name.split('.').collect();
    assert_eq!(
        parts.len(),
        2,
        "Tool name must have exactly 2 parts (skill.command). Got {} parts: {:?}",
        parts.len(),
        parts
    );

    // Verify first part equals skill_name
    assert_eq!(
        parts[0], "git",
        "First part of tool_name must match skill_name. Expected 'git', got '{}'",
        parts[0]
    );

    // Verify no triple repetition like "git.git.git.command"
    assert!(
        !tool.tool_name.starts_with("git.git."),
        "Tool name must NOT have repeated skill prefix. Got: '{}'",
        tool.tool_name
    );
}

/// Tests that JSON serialization preserves the correct tool_name schema.
#[test]
fn test_tool_record_json_serialization_schema() {
    let tool = ToolRecord {
        tool_name: "git.smart_commit".to_string(),
        description: "Execute git.smart_commit".to_string(),
        skill_name: "git".to_string(),
        file_path: "assets/skills/git/scripts/commit.py".to_string(),
        function_name: "smart_commit".to_string(),
        execution_mode: "script".to_string(),
        keywords: vec!["git".to_string(), "smart_commit".to_string()],
        intents: vec![],
        file_hash: "abc123".to_string(),
        input_schema: "{}".to_string(),
        docstring: "Smart commit workflow".to_string(),
        category: "commit".to_string(),
        annotations: ToolAnnotations::default(),
        parameters: vec!["action".to_string()],
        skill_tools_refers: vec![],
        resource_uri: "".to_string(),
    };

    // Serialize to JSON
    let json = serde_json::to_string(&tool).expect("Should serialize");

    // Deserialize back
    let deserialized: ToolRecord = serde_json::from_str(&json).expect("Should deserialize");

    // Verify schema invariant preserved
    assert_eq!(
        deserialized.tool_name, "git.smart_commit",
        "Deserialized tool_name must preserve schema. Got: '{}'",
        deserialized.tool_name
    );
}

/// Tests SkillIndexEntry tool name formatting.
/// When building an index entry, tools must maintain correct format.
#[test]
fn test_skill_index_entry_tool_format() {
    // Create a tool with correct format
    let tool = ToolRecord {
        tool_name: "git.smart_commit".to_string(), // Correct format
        description: "Smart commit".to_string(),
        skill_name: "git".to_string(),
        file_path: "scripts/commit.py".to_string(),
        function_name: "smart_commit".to_string(),
        execution_mode: "script".to_string(),
        keywords: vec![],
        intents: vec![],
        file_hash: "hash".to_string(),
        input_schema: "{}".to_string(),
        docstring: "".to_string(),
        category: "commit".to_string(),
        annotations: ToolAnnotations::default(),
        parameters: vec![],
        skill_tools_refers: vec![],
        resource_uri: "".to_string(),
    };

    // Build index entry
    let scanner = SkillScanner::new();
    let skill_path = TempDir::new().unwrap().path().join("git");

    let entry = scanner.build_index_entry(
        SkillMetadata {
            skill_name: "git".to_string(),
            version: "1.0.0".to_string(),
            description: "Git skill".to_string(),
            routing_keywords: vec!["commit".to_string()],
            authors: vec!["test".to_string()],
            intents: vec![],
            require_refs: vec![],
            repository: "".to_string(),
            permissions: vec![],
        },
        &[tool],
        &skill_path,
    );

    // Verify tool name in entry is correct
    assert_eq!(entry.tools.len(), 1);
    let index_tool = &entry.tools[0];

    // The tool name should NOT be "git.git.smart_commit"
    assert!(
        !index_tool.name.starts_with("git.git."),
        "IndexToolEntry name must NOT have repeated prefix. Got: '{}'",
        index_tool.name
    );

    // Should be exactly "skill.command" format
    assert_eq!(
        index_tool.name, "git.smart_commit",
        "IndexToolEntry name must be 'skill.command'. Got: '{}'",
        index_tool.name
    );
}

/// Tests multiple tools from same skill maintain correct format.
#[test]
fn test_multiple_tools_schema_consistency() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("git/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Create multiple scripts with different commands
    fs::write(
        &scripts_dir.join("commit.py"),
        r#"
@skill_command(name="commit")
def commit(msg: str) -> str:
    '''Create commit.'''
    return "ok"

@skill_command(name="status")
def status() -> str:
    '''Show status.'''
    return "ok"
"#,
    )
    .unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner.scan_scripts(&scripts_dir, "git", &[], &[]).unwrap();

    assert_eq!(tools.len(), 2);

    // Verify all tools have correct format
    for tool in &tools {
        let parts: Vec<&str> = tool.tool_name.split('.').collect();
        assert_eq!(
            parts.len(),
            2,
            "Tool '{}' must have exactly 2 parts",
            tool.tool_name
        );
        assert_eq!(
            parts[0], "git",
            "Tool '{}' first part must be skill name 'git'",
            tool.tool_name
        );

        // Ensure no double prefix
        assert!(
            !tool.tool_name.starts_with("git.git."),
            "Tool '{}' must NOT have repeated prefix",
            tool.tool_name
        );
    }
}

/// Tests edge case: tool with underscore in name.
#[test]
fn test_tool_name_with_underscore_schema() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("my_skill/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    fs::write(
        &scripts_dir.join("utils.py"),
        r#"
@skill_command(name="run_test")
def run_test() -> str:
    '''Run tests.'''
    return "ok"
"#,
    )
    .unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "my_skill", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Should be "my_skill.run_test" not "my_skill.my_skill.run_test"
    assert_eq!(
        tool.tool_name, "my_skill.run_test",
        "Tool with underscore in skill name must be 'skill.command'. Got: '{}'",
        tool.tool_name
    );
}

/// Tests that tool without explicit name uses function name correctly.
#[test]
fn test_tool_name_from_function_schema() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Tool without explicit name parameter
    fs::write(
        &scripts_dir.join("hello.py"),
        r#"
@skill_command()
def my_function():
    '''Test function.'''
    return "ok"
"#,
    )
    .unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Should use function name as tool name
    assert_eq!(tool.tool_name, "test.my_function");

    // Schema validation
    assert!(
        !tool.tool_name.starts_with("test.test."),
        "Tool name should not repeat skill prefix. Got: '{}'",
        tool.tool_name
    );
}

/// Tests JSON schema of complete skill index.
#[test]
fn test_skill_index_json_schema() {
    // Create a minimal valid index entry
    let mut entry = SkillIndexEntry::new(
        "git".to_string(),
        "Git skill".to_string(),
        "1.0.0".to_string(),
        "assets/skills/git".to_string(),
    );

    entry.add_tool(IndexToolEntry {
        name: "git.commit".to_string(),
        description: "Create commit".to_string(),
        category: String::new(),
        input_schema: String::new(),
        file_hash: String::new(),
    });

    entry.add_tool(IndexToolEntry {
        name: "git.smart_commit".to_string(),
        description: "Smart commit workflow".to_string(),
        category: String::new(),
        input_schema: String::new(),
        file_hash: String::new(),
    });

    // Serialize
    let json = serde_json::to_string_pretty(&entry).expect("Should serialize");

    // Verify JSON structure
    let parsed: serde_json::Value = serde_json::from_str(&json).expect("Should parse");

    // Validate top-level fields
    assert_eq!(parsed["name"], "git");
    assert_eq!(parsed["version"], "1.0.0");
    assert!(parsed["tools"].is_array());
    assert_eq!(parsed["tools"].as_array().unwrap().len(), 2);

    // Validate tool names in JSON
    let tool_names: Vec<&str> = parsed["tools"]
        .as_array()
        .unwrap()
        .iter()
        .map(|t| t["name"].as_str().unwrap())
        .collect();

    assert!(tool_names.contains(&"git.commit"));
    assert!(tool_names.contains(&"git.smart_commit"));

    // Verify no malformed names
    for name in &tool_names {
        assert!(
            !name.starts_with("git.git."),
            "Tool name '{}' should not have repeated prefix in JSON",
            name
        );
    }
}

/// Regression test: ensures build_index_entry doesn't double-prefix tool names.
#[test]
fn test_build_index_entry_no_double_prefix_regression() {
    // This test catches the bug where build_index_entry would do:
    // format!("{}.{}", metadata.skill_name, tool.tool_name)
    // resulting in "git.git.smart_commit" instead of "git.smart_commit"

    let scanner = SkillScanner::new();

    // Create a tool with already-correct format
    let tools = vec![ToolRecord {
        tool_name: "git.status".to_string(), // Already correct
        description: "Show status".to_string(),
        skill_name: "git".to_string(),
        file_path: "scripts/status.py".to_string(),
        function_name: "status".to_string(),
        execution_mode: "script".to_string(),
        keywords: vec![],
        intents: vec![],
        file_hash: "hash".to_string(),
        input_schema: "{}".to_string(),
        docstring: "".to_string(),
        category: "status".to_string(),
        annotations: ToolAnnotations::default(),
        parameters: vec![],
        skill_tools_refers: vec![],
        resource_uri: "".to_string(),
    }];

    let skill_path = TempDir::new().unwrap().path().join("git");
    let entry = scanner.build_index_entry(
        SkillMetadata {
            skill_name: "git".to_string(),
            version: "1.0.0".to_string(),
            description: "Git skill".to_string(),
            routing_keywords: vec!["status".to_string()],
            authors: vec![],
            intents: vec![],
            require_refs: vec![],
            repository: "".to_string(),
            permissions: vec![],
        },
        &tools,
        &skill_path,
    );

    assert_eq!(entry.tools.len(), 1);

    // THIS IS THE KEY ASSERTION
    // If this fails, the double-prefix bug is present
    assert_eq!(
        entry.tools[0].name, "git.status",
        "build_index_entry must NOT double-prefix tool names. \
         Expected 'git.status' but got '{}'",
        entry.tools[0].name
    );

    // Also verify it doesn't start with git.git
    assert!(
        !entry.tools[0].name.starts_with("git.git."),
        "Tool name must not start with 'git.git.'. Got: '{}'",
        entry.tools[0].name
    );
}

/// Tests edge case: skill name that looks like a file path.
#[test]
fn test_skill_name_with_path_like_format() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("my_skill/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    fs::write(
        &scripts_dir.join("cmd.py"),
        r#"
@skill_command(name="list_items")
def list_items() -> str:
    '''List items.'''
    return "ok"
"#,
    )
    .unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "my_skill", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Should be "my_skill.list_items", not something else
    assert_eq!(tool.tool_name, "my_skill.list_items");

    // Verify no double prefix
    assert!(
        !tool.tool_name.starts_with("my_skill.my_skill."),
        "Tool '{}' should not have repeated prefix",
        tool.tool_name
    );
}

/// Tests that SkillStructure doesn't affect tool name format.
#[test]
fn test_tool_name_independent_of_structure() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");
    let scripts_dir = skill_path.join("scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Create SKILL.md
    fs::write(
        &skill_path.join("SKILL.md"),
        r#"---
name: "test_skill"
version: "1.0.0"
---
"#,
    )
    .unwrap();

    // Create script
    fs::write(
        &scripts_dir.join("test.py"),
        r#"
@skill_command(name="test_cmd")
def test_cmd() -> str:
    '''Test.'''
    return "ok"
"#,
    )
    .unwrap();

    let scanner = ToolsScanner::new();
    let structure = SkillStructure::default();

    // Scan with structure
    let tools = scanner
        .scan_with_structure(&skill_path, "test_skill", &[], &[], &structure)
        .unwrap();

    assert_eq!(tools.len(), 1);

    // Tool name should still be "test_skill.test_cmd"
    assert_eq!(
        tools[0].tool_name, "test_skill.test_cmd",
        "Tool name format must be independent of structure scanning. Got: '{}'",
        tools[0].tool_name
    );
}

/// Tests that empty tool list is handled correctly.
#[test]
fn test_empty_tools_schema() {
    let scanner = SkillScanner::new();
    let skill_path = TempDir::new().unwrap().path().join("empty_skill");

    fs::create_dir_all(&skill_path).unwrap();
    fs::write(
        &skill_path.join("SKILL.md"),
        r#"---
name: "empty_skill"
version: "1.0.0"
---
"#,
    )
    .unwrap();

    let entry = scanner.build_index_entry(
        SkillMetadata {
            skill_name: "empty_skill".to_string(),
            version: "1.0.0".to_string(),
            description: "Empty skill".to_string(),
            routing_keywords: vec![],
            authors: vec![],
            intents: vec![],
            require_refs: vec![],
            repository: "".to_string(),
            permissions: vec![],
        },
        &[], // Empty tools
        &skill_path,
    );

    assert!(entry.tools.is_empty());
}

/// Validates the test_skill_index.json reference file for data integrity.
///
/// This test ensures the reference test data file doesn't contain:
/// - Tool names with repeated skill prefix (e.g., "git.git.commit")
/// - Paths with extra quotes (e.g., "\"assets/skills/git\"")
/// - Malformed JSON structure
///
/// Run: cargo test -p skills-scanner test_skill_index_json_data_integrity
#[test]
fn test_skill_index_json_data_integrity() {
    use std::path::Path;

    // Path to the test reference file
    let test_file_path = Path::new("../../bindings/python/test_skill_index.json");

    // Read and parse the JSON file
    let content = fs::read_to_string(test_file_path)
        .expect(&format!("Failed to read test file: {:?}", test_file_path));

    let skills: Vec<serde_json::Value> = serde_json::from_str(&content)
        .expect("Failed to parse test_skill_index.json as valid JSON");

    // Track validation errors
    let mut errors: Vec<String> = Vec::new();

    for (i, skill) in skills.iter().enumerate() {
        let skill_name = skill["name"].as_str().unwrap_or("UNKNOWN");
        let skill_path = skill["path"].as_str().unwrap_or("");

        // Validate 1: Path should not have extra quotes
        if skill_path.starts_with('"') && skill_path.ends_with('"') {
            errors.push(format!(
                "[{}] Skill '{}': path has extra quotes: {}",
                i, skill_name, skill_path
            ));
        }

        // Validate 2: Path should start with assets/skills/
        if !skill_path.starts_with("assets/skills/") {
            errors.push(format!(
                "[{}] Skill '{}': path doesn't start with 'assets/skills/': {}",
                i, skill_name, skill_path
            ));
        }

        // Validate 3: Tool names
        if let Some(tools) = skill["tools"].as_array() {
            for (j, tool) in tools.iter().enumerate() {
                let tool_name = tool["name"].as_str().unwrap_or("UNKNOWN");
                // _expected_prefix: format!("{}.", skill_name),

                // Check for repeated skill prefix
                let repeated_prefix = format!("{}.{}", skill_name, skill_name);
                if tool_name.starts_with(&repeated_prefix) {
                    let expected =
                        format!("{}.{}", skill_name, &tool_name[repeated_prefix.len()..]);
                    errors.push(format!(
                        "[{}.{}] Tool '{}': repeated skill prefix (got '{}', expected '{}')",
                        i, j, tool_name, tool_name, expected
                    ));
                }

                // Check tool name format: should be exactly "skill.command"
                let parts: Vec<&str> = tool_name.split('.').collect();
                if parts.len() != 2 {
                    errors.push(format!(
                        "[{}.{}] Tool '{}': wrong format (expected 'skill.command', got {} parts)",
                        i,
                        j,
                        tool_name,
                        parts.len()
                    ));
                }

                // Check that first part matches skill name
                if parts.first().map(|s| s.to_string()) != Some(skill_name.to_string()) {
                    errors.push(format!(
                        "[{}.{}] Tool '{}': first part doesn't match skill name '{}'",
                        i, j, tool_name, skill_name
                    ));
                }
            }
        }
    }

    // Report all errors
    if !errors.is_empty() {
        panic!(
            "test_skill_index.json has {} data integrity issues:\n{}",
            errors.len(),
            errors.join("\n")
        );
    }
}
