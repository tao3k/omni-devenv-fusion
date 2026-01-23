//! Tests for diff module - unified diff generation.

use omni_edit::diff::generate_unified_diff;

#[test]
fn test_simple_diff() {
    let old = "line1\nline2\nline3\n";
    let new = "line1\nmodified\nline3\n";

    let diff = generate_unified_diff(old, new);

    assert!(diff.contains("-line2"));
    assert!(diff.contains("+modified"));
}

#[test]
fn test_no_changes() {
    let content = "same content\n";
    let diff = generate_unified_diff(content, content);
    // When content is identical, there may be no changes or empty diff
    assert!(diff.is_empty() || (!diff.contains('-') && !diff.contains('+')));
}

#[test]
fn test_addition_only() {
    let old = "";
    let new = "new line\n";

    let diff = generate_unified_diff(old, new);

    assert!(diff.contains("+new line"));
}
