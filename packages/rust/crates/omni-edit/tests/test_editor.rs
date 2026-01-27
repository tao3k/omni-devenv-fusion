//! Tests for editor module - StructuralEditor functionality.

use std::fs::File;
use std::io::Write;
use tempfile::TempDir;

use omni_edit::{EditResult, StructuralEditor};

/// Helper function to create a simple edit result for testing.
#[allow(dead_code)]
fn make_edit_result(original: &str, modified: &str, count: usize) -> EditResult {
    EditResult {
        original: original.to_string(),
        modified: modified.to_string(),
        count,
        diff: String::new(),
        edits: Vec::new(),
    }
}

#[test]
fn test_simple_replace() {
    let content = "x = connect(host, port)";
    let result = StructuralEditor::replace(
        content,
        "connect($$$ARGS)",
        "async_connect($$$ARGS)",
        "python",
    )
    .expect("Should replace");

    assert_eq!(result.count, 1);
    assert!(result.modified.contains("async_connect"));
    assert!(!result.diff.is_empty());
}

#[test]
fn test_multiple_replacements() {
    let content = r#"
def foo():
    connect(a, b)
    connect(c, d)
    connect(e, f)
"#;
    let result = StructuralEditor::replace(
        content,
        "connect($$$ARGS)",
        "safe_connect($$$ARGS)",
        "python",
    )
    .expect("Should replace multiple");

    assert_eq!(result.count, 3);
    assert_eq!(result.modified.matches("safe_connect").count(), 3);
}

#[test]
fn test_no_matches() {
    let content = "x = 1 + 2";
    let result = StructuralEditor::replace(content, "connect($$$)", "async_connect($$$)", "python")
        .expect("Should handle no matches");

    assert_eq!(result.count, 0);
    assert_eq!(result.original, result.modified);
}

#[test]
fn test_rust_replace() {
    let content = "let x = old_function(arg1, arg2);";
    let result = StructuralEditor::replace(
        content,
        "old_function($$$ARGS)",
        "new_function($$$ARGS)",
        "rust",
    )
    .expect("Should replace Rust code");

    assert_eq!(result.count, 1);
    assert!(result.modified.contains("new_function"));
}

#[test]
fn test_class_rename() {
    let content = r#"
class OldName:
    pass

x = OldName()
"#;
    let result = StructuralEditor::replace(content, "OldName", "NewName", "python")
        .expect("Should rename class");

    assert!(result.count >= 1);
    assert!(result.modified.contains("NewName"));
}

#[test]
fn test_file_preview() {
    let dir = TempDir::new().expect("Create temp dir");
    let path = dir.path().join("test.py");
    let content = "result = old_api(data)";

    File::create(&path)
        .expect("Create file")
        .write_all(content.as_bytes())
        .expect("Write content");

    let result = StructuralEditor::preview(&path, "old_api($$$)", "new_api($$$)", None)
        .expect("Should preview");

    assert_eq!(result.count, 1);

    let file_content = std::fs::read_to_string(&path).expect("Read file");
    assert!(file_content.contains("old_api")); // Original unchanged
}

#[test]
fn test_file_apply() {
    let dir = TempDir::new().expect("Create temp dir");
    let path = dir.path().join("test.py");
    let content = "result = deprecated_call(x)";

    File::create(&path)
        .expect("Create file")
        .write_all(content.as_bytes())
        .expect("Write content");

    let result = StructuralEditor::apply(&path, "deprecated_call($$$)", "modern_call($$$)", None)
        .expect("Should apply");

    assert_eq!(result.count, 1);

    let file_content = std::fs::read_to_string(&path).expect("Read file");
    assert!(file_content.contains("modern_call"));
    assert!(!file_content.contains("deprecated_call"));
}

#[test]
fn test_format_result() {
    let content = "x = connect(a)";
    let result = StructuralEditor::replace(
        content,
        "connect($$$ARGS)",
        "async_connect($$$ARGS)",
        "python",
    )
    .expect("Should replace");

    let formatted = StructuralEditor::format_result(&result, Some("test.py"));

    assert!(formatted.contains("EDIT: test.py"));
    assert!(formatted.contains("Replacements: 1"));
    assert!(formatted.contains("Diff:"));
}
