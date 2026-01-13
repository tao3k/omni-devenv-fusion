//! Diff generation utilities.
//!
//! Provides unified diff output for structural edits using the `similar` crate.

use similar::{ChangeTag, TextDiff};

/// Generate a unified diff between two strings.
///
/// Uses the `similar` crate for line-by-line diffing with context.
///
/// # Arguments
/// * `original` - The original content
/// * `modified` - The modified content
///
/// # Returns
/// A string containing the unified diff with `+`, `-`, and ` ` prefixes.
pub fn generate_unified_diff(original: &str, modified: &str) -> String {
    let diff = TextDiff::from_lines(original, modified);
    let mut output = String::new();

    for (idx, group) in diff.grouped_ops(3).iter().enumerate() {
        if idx > 0 {
            output.push_str("...\n");
        }
        for op in group {
            for change in diff.iter_changes(op) {
                let sign = match change.tag() {
                    ChangeTag::Delete => "-",
                    ChangeTag::Insert => "+",
                    ChangeTag::Equal => " ",
                };
                output.push_str(sign);
                output.push_str(change.value());
                if change.missing_newline() {
                    output.push('\n');
                }
            }
        }
    }

    output
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_diff() {
        let original = "line1\nold_text\nline3";
        let modified = "line1\nnew_text\nline3";
        let diff = generate_unified_diff(original, modified);

        assert!(diff.contains("-old_text"));
        assert!(diff.contains("+new_text"));
    }

    #[test]
    fn test_no_changes() {
        let content = "unchanged content";
        let diff = generate_unified_diff(content, content);
        assert!(diff.is_empty() || !diff.contains('-') && !diff.contains('+'));
    }

    #[test]
    fn test_addition_only() {
        let original = "line1\nline2";
        let modified = "line1\nline2\nline3";
        let diff = generate_unified_diff(original, modified);

        assert!(diff.contains("+line3"));
    }
}
