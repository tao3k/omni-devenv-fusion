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
