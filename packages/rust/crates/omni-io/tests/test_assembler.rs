//! Tests for ContextAssembler - Parallel I/O + Templating + Token Counting.
//!
//! Tests cover:
//! - Basic assembly with template variables
//! - Multiple reference files
//! - Missing file handling
//! - Special character handling
//! - Token counting accuracy
//! - Template error fallback

#![cfg(feature = "assembler")]

use omni_io::ContextAssembler;
use std::fs;
use tempfile::TempDir;

#[test]
fn test_assemble_skill_basic() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "Hello {{ name }}!").unwrap();

    let assembler = ContextAssembler::new();
    let variables = serde_json::json!({"name": "World"});

    let result = assembler
        .assemble_skill(main_path, Vec::new(), variables)
        .unwrap();

    assert!(result.content.contains("Hello World!"));
    assert!(result.token_count > 0);
    assert!(result.missing_refs.is_empty());
}

#[test]
fn test_assemble_skill_with_references() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "Main: {{ var1 }}").unwrap();

    let ref_path = temp_dir.path().join("ref.md");
    fs::write(&ref_path, "Reference content").unwrap();

    let assembler = ContextAssembler::new();
    let variables = serde_json::json!({"var1": "test"});

    let result = assembler
        .assemble_skill(main_path, vec![ref_path], variables)
        .unwrap();

    assert!(result.content.contains("Main: test"));
    assert!(result.content.contains("Reference content"));
    assert!(result.content.contains("# Required References"));
}

#[test]
fn test_assemble_skill_missing_reference() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "Main content").unwrap();

    let missing_path = temp_dir.path().join("missing.md");

    let assembler = ContextAssembler::new();

    let result = assembler
        .assemble_skill(main_path, vec![missing_path], serde_json::json!({}))
        .unwrap();

    assert_eq!(result.missing_refs.len(), 1);
}

#[test]
fn test_assemble_skill_empty_variables() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "No variables here").unwrap();

    let assembler = ContextAssembler::new();
    let result = assembler
        .assemble_skill(main_path, Vec::new(), serde_json::json!({}))
        .unwrap();

    assert!(result.content.contains("No variables here"));
    assert!(result.token_count > 0);
}

#[test]
fn test_assemble_skill_multiple_references() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "Main with {{ ref1 }} and {{ ref2 }}").unwrap();

    let ref1 = temp_dir.path().join("ref1.md");
    fs::write(&ref1, "Reference 1 content").unwrap();

    let ref2 = temp_dir.path().join("ref2.md");
    fs::write(&ref2, "Reference 2 content").unwrap();

    let assembler = ContextAssembler::new();
    let variables = serde_json::json!({
        "ref1": "VAR1",
        "ref2": "VAR2"
    });

    let result = assembler
        .assemble_skill(main_path, vec![ref1, ref2], variables)
        .unwrap();

    assert!(result.content.contains("Main with VAR1 and VAR2"));
    assert!(result.content.contains("Reference 1 content"));
    assert!(result.content.contains("Reference 2 content"));
    assert!(result.missing_refs.is_empty());
}

#[test]
fn test_assemble_skill_special_characters() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    let special_content = r#"# Special Chars

| Column | Value |
|--------|-------|
| Name    | {{ name }} |

```python
def hello():
    print("{{ name }}")
```

- [ ] Task 1
- [x] Task 2
"#;
    fs::write(&main_path, special_content).unwrap();

    let assembler = ContextAssembler::new();
    let variables = serde_json::json!({"name": "World"});

    let result = assembler
        .assemble_skill(main_path, Vec::new(), variables)
        .unwrap();

    assert!(result.content.contains("Special Chars"));
    assert!(result.content.contains("World"));
    assert!(result.token_count > 0);
}

#[test]
fn test_assemble_skill_template_error_fallback() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    // Template with undefined variable (strict mode)
    fs::write(&main_path, "Value: {{ undefined_var }}").unwrap();

    let assembler = ContextAssembler::new();
    let variables = serde_json::json!({}); // Missing required variable

    let result = assembler
        .assemble_skill(main_path, Vec::new(), variables)
        .unwrap();

    // Should contain template error message
    assert!(result.content.contains("Template Error"));
}

#[test]
fn test_assemble_skill_token_count_reasonable() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    let content = "word ".repeat(100);
    fs::write(&main_path, &content).unwrap();

    let assembler = ContextAssembler::new();
    let result = assembler
        .assemble_skill(main_path, Vec::new(), serde_json::json!({}))
        .unwrap();

    // Token count should be proportional to content (roughly 4 chars per token)
    assert!(result.token_count >= 20);
    assert!(result.token_count <= 150);
}

#[test]
fn test_assemble_skill_missing_main_file() {
    let temp_dir = TempDir::new().unwrap();
    let missing_main = temp_dir.path().join("nonexistent.md");

    let assembler = ContextAssembler::new();
    let result = assembler
        .assemble_skill(missing_main, Vec::new(), serde_json::json!({}))
        .unwrap();

    // Main file missing should result in empty content (unwrap_or_default)
    assert!(result.missing_refs.is_empty());
}

#[test]
fn test_assemble_skill_all_missing_references() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "Main content").unwrap();

    let ref1 = temp_dir.path().join("missing1.md");
    let ref2 = temp_dir.path().join("missing2.md");

    let assembler = ContextAssembler::new();
    let result = assembler
        .assemble_skill(main_path, vec![ref1, ref2], serde_json::json!({}))
        .unwrap();

    assert_eq!(result.missing_refs.len(), 2);
}

#[test]
fn test_assemble_result_fields() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "Test {{ value }}").unwrap();

    let assembler = ContextAssembler::new();
    let result = assembler
        .assemble_skill(
            main_path,
            Vec::new(),
            serde_json::json!({"value": "RESULT"}),
        )
        .unwrap();

    // Verify all fields are populated correctly
    assert_eq!(result.content, "# Active Protocol\nTest RESULT");
    assert!(result.token_count > 0);
    assert!(result.missing_refs.is_empty());
}

#[test]
fn test_assemble_skill_preserves_markdown_structure() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    let content = r#"# Title

## Section 1

Content 1

## Section 2

Content 2

### Subsection

More content
"#;
    fs::write(&main_path, content).unwrap();

    let assembler = ContextAssembler::new();
    let result = assembler
        .assemble_skill(main_path, Vec::new(), serde_json::json!({}))
        .unwrap();

    // Markdown structure should be preserved
    assert!(result.content.contains("# Title"));
    assert!(result.content.contains("## Section 1"));
    assert!(result.content.contains("## Section 2"));
    assert!(result.content.contains("### Subsection"));
}

#[test]
fn test_assemble_skill_nested_variables() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    let content = r#"---
name: {{ skill.name }}
version: {{ skill.version }}
description: {{ skill.description }}
---

# {{ skill.name }}

This is version {{ skill.version }}.
"#;
    fs::write(&main_path, content).unwrap();

    let assembler = ContextAssembler::new();
    let variables = serde_json::json!({
        "skill": {
            "name": "TestSkill",
            "version": "1.0.0",
            "description": "A test skill"
        }
    });

    let result = assembler
        .assemble_skill(main_path, Vec::new(), variables)
        .unwrap();

    assert!(result.content.contains("name: TestSkill"));
    assert!(result.content.contains("version: 1.0.0"));
    assert!(result.content.contains("description: A test skill"));
    assert!(result.content.contains("# TestSkill"));
    assert!(result.content.contains("This is version 1.0.0."));
}

#[test]
fn test_assemble_skill_no_references_section_when_empty() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "No references here").unwrap();

    let assembler = ContextAssembler::new();
    let result = assembler
        .assemble_skill(main_path, Vec::new(), serde_json::json!({}))
        .unwrap();

    // When no references, the "# Required References" section should not appear
    assert!(!result.content.contains("# Required References"));
}

#[test]
fn test_assemble_skill_reference_includes_filename() {
    let temp_dir = TempDir::new().unwrap();
    let main_path = temp_dir.path().join("SKILL.md");
    fs::write(&main_path, "Main content").unwrap();

    let ref_path = temp_dir.path().join("my_reference.md");
    fs::write(&ref_path, "Reference content").unwrap();

    let assembler = ContextAssembler::new();
    let result = assembler
        .assemble_skill(main_path, vec![ref_path], serde_json::json!({}))
        .unwrap();

    // Reference filename should be included in output
    assert!(result.content.contains("## my_reference.md"));
    assert!(result.content.contains("Reference content"));
}
