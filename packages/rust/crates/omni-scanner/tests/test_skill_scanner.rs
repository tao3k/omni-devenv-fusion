//! Tests for skill_scanner module.
//!
//! Tests SKILL.md parsing and SkillScanner functionality.

use omni_scanner::{
    CanonicalSkillPayload, SkillMetadata, SkillScanner, SnifferRule, ToolRecord,
    extract_frontmatter,
};
use std::fs;
use tempfile::TempDir;

/// Test SkillScanner creates valid instance.
#[test]
fn test_skill_scanner_new() {
    let _scanner = SkillScanner::new();
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
name: test_skill
description: Use when testing skill functionality.
metadata:
  author: omni-dev-fusion
  version: "1.0.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/test_skill"
  routing_keywords:
    - "test"
    - "example"
  intents:
    - "Test functionality"
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
name: writer
description: Use when editing files or writing content.
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

    let metadata = scanner.parse_skill_md(content, &skill_path).unwrap();

    assert_eq!(metadata.skill_name, "writer");
    assert_eq!(metadata.version, "1.1.0");
    assert_eq!(
        metadata.description,
        "Use when editing files or writing content."
    );
    assert_eq!(metadata.routing_keywords, vec!["write", "edit", "polish"]);
    assert_eq!(metadata.authors, vec!["omni-dev-fusion"]);
    assert_eq!(metadata.intents, vec!["Update documentation"]);
}

/// Test parsing a skill with spaces in routing keywords (Researcher skill).
#[test]
fn test_parse_skill_md_with_spaces_in_keywords() {
    let content = r#"---
name: researcher
description: Use when conducting deep research on codebases.
metadata:
  author: omni-dev-fusion
  version: "1.0.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/researcher"
  routing_keywords:
    - "analyze repo"
    - "git clone"
    - "research github"
    - "repomix"
    - "code analysis"
    - "repository map"
    - "compress code"
    - "read codebase"
    - "compare architecture"
  intents:
    - "research_repository"
    - "analyze_codebase"
    - "compare_architecture"
  permissions: []
---

# Researcher Skill
"#;

    let scanner = SkillScanner::new();
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("researcher");

    let metadata = scanner.parse_skill_md(content, &skill_path).unwrap();

    assert_eq!(metadata.skill_name, "researcher");
    assert_eq!(metadata.version, "1.0.0");
    assert!(
        metadata
            .routing_keywords
            .contains(&"analyze repo".to_string())
    );
    assert!(
        metadata
            .routing_keywords
            .contains(&"repository map".to_string())
    );
    assert!(metadata.routing_keywords.contains(&"git clone".to_string()));
    assert_eq!(metadata.routing_keywords.len(), 9);
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

/// Test that build_index_entry deduplicates tools by name.
#[test]
fn test_build_index_entry_deduplicates_tools() {
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

    // Create tools with duplicate names (simulates docstring example matching)
    let tools = vec![
        ToolRecord {
            tool_name: "test_skill.real_tool".to_string(),
            description: "The real tool".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/real.py".to_string(),
            function_name: "real_tool".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["test".to_string()],
            intents: vec![],
            file_hash: "hash1".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
            skill_tools_refers: vec![],
            resource_uri: "".to_string(),
        },
        // Duplicate from docstring example
        ToolRecord {
            tool_name: "test_skill.real_tool".to_string(),
            description: "Example in docstring".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/other.py".to_string(),
            function_name: "example_func".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["test".to_string()],
            intents: vec![],
            file_hash: "hash2".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
            skill_tools_refers: vec![],
            resource_uri: "".to_string(),
        },
    ];

    let scanner = SkillScanner::new();
    let entry = scanner.build_index_entry(metadata, &tools, &skill_path);

    // Should have only 1 tool (deduplicated)
    assert_eq!(entry.tools.len(), 1);
    assert_eq!(entry.tools[0].name, "test_skill.real_tool");
    // Should keep the first occurrence (the real definition)
    assert_eq!(entry.tools[0].description, "The real tool");
}

/// Test that build_index_entry preserves order of first occurrences.
#[test]
fn test_build_index_entry_preserves_order() {
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
            keywords: vec![],
            intents: vec![],
            file_hash: "hash1".to_string(),
            input_schema: "{}".to_string(),
            docstring: "".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
            skill_tools_refers: vec![],
            resource_uri: "".to_string(),
        },
        ToolRecord {
            tool_name: "test_skill.tool_a".to_string(),
            description: "Tool A".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/a.py".to_string(),
            function_name: "tool_a".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec![],
            intents: vec![],
            file_hash: "hash2".to_string(),
            input_schema: "{}".to_string(),
            docstring: "".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
            skill_tools_refers: vec![],
            resource_uri: "".to_string(),
        },
        // Duplicate of tool_b from docstring
        ToolRecord {
            tool_name: "test_skill.tool_b".to_string(),
            description: "Duplicate B".to_string(),
            skill_name: "test_skill".to_string(),
            file_path: "/test/scripts/c.py".to_string(),
            function_name: "dup_b".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec![],
            intents: vec![],
            file_hash: "hash3".to_string(),
            input_schema: "{}".to_string(),
            docstring: "".to_string(),
            category: "test".to_string(),
            annotations: Default::default(),
            parameters: vec![],
            skill_tools_refers: vec![],
            resource_uri: "".to_string(),
        },
    ];

    let scanner = SkillScanner::new();
    let entry = scanner.build_index_entry(metadata, &tools, &skill_path);

    // Should have 2 tools
    assert_eq!(entry.tools.len(), 2);
    // Order should be preserved (tool_b first, then tool_a)
    assert_eq!(entry.tools[0].name, "test_skill.tool_b");
    assert_eq!(entry.tools[0].description, "Tool B");
    assert_eq!(entry.tools[1].name, "test_skill.tool_a");
    assert_eq!(entry.tools[1].description, "Tool A");
}

/// Test that build_canonical_payload wires references for_tools into skill_tool_references.
#[test]
fn test_build_canonical_payload_fills_skill_tool_references() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("researcher");
    fs::create_dir_all(&skill_path).unwrap();

    let refs_dir = skill_path.join("references");
    fs::create_dir_all(&refs_dir).unwrap();
    let ref_path = refs_dir.join("run_research_graph.md");
    let ref_content = r#"---
metadata:
  for_tools: researcher.run_research_graph
  title: Run Research Graph
---
# Doc body
"#;
    fs::write(&ref_path, ref_content).unwrap();

    let metadata = SkillMetadata {
        skill_name: "researcher".to_string(),
        version: "1.0.0".to_string(),
        description: "Research skill".to_string(),
        routing_keywords: vec!["research".to_string()],
        authors: vec![],
        intents: vec![],
        require_refs: vec![],
        repository: String::new(),
        permissions: vec![],
    };

    let tools = vec![ToolRecord {
        tool_name: "researcher.run_research_graph".to_string(),
        description: "Run the graph".to_string(),
        skill_name: "researcher".to_string(),
        file_path: "researcher/scripts/commands.py".to_string(),
        function_name: "run_research_graph".to_string(),
        execution_mode: "async".to_string(),
        keywords: vec!["research".to_string()],
        intents: vec![],
        file_hash: "abc".to_string(),
        input_schema: "{}".to_string(),
        docstring: String::new(),
        category: "research".to_string(),
        annotations: Default::default(),
        parameters: vec![],
        skill_tools_refers: vec![],
        resource_uri: "".to_string(),
    }];

    let scanner = SkillScanner::new();
    let payload: CanonicalSkillPayload =
        scanner.build_canonical_payload(metadata, &tools, &skill_path);

    assert_eq!(payload.skill_name, "researcher");
    assert_eq!(payload.skill_tools.len(), 1);
    let entry = payload
        .skill_tools
        .get("researcher.run_research_graph")
        .expect("tool entry");
    assert_eq!(
        entry
            .skill_tool_references
            .get("researcher.references.run_research_graph"),
        Some(&ref_path.to_string_lossy().to_string())
    );
    assert_eq!(payload.references.len(), 1);
    assert!(payload.references.contains_key("run_research_graph"));
}
