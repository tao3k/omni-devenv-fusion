//! Core structural editor implementation.
//!
//! Provides AST-based code modification using ast-grep patterns.
//! Part of The Surgeon.

use std::path::Path;
use std::str::FromStr;

// Use omni-ast for unified ast-grep (re-exports Pattern, SupportLang, LanguageExt)
use omni_ast::{AstLanguage, LanguageExt, MatcherExt, Pattern, SupportLang};

use crate::capture::substitute_captures;
use crate::diff::generate_unified_diff;
use crate::error::EditError;
use crate::types::{EditConfig, EditLocation, EditResult};

/// StructuralEditor - AST-based code modification engine.
///
/// Uses ast-grep patterns for surgical precision in code refactoring.
/// Part of The Surgeon.
///
/// # Example
///
/// ```rust,ignore
/// use omni_edit::StructuralEditor;
///
/// // Rename function calls (use $$$ for variadic args)
/// let result = StructuralEditor::replace(
///     "x = connect(host, port)",
///     "connect($$$)",
///     "async_connect($$$)",
///     "python"
/// )?;
/// assert!(result.modified.contains("async_connect"));
/// ```
pub struct StructuralEditor;

impl StructuralEditor {
    /// Perform structural replace on content.
    ///
    /// # Arguments
    /// * `content` - Source code content
    /// * `pattern` - ast-grep pattern to match (e.g., `connect($$$)`)
    /// * `replacement` - Replacement pattern (e.g., `async_connect($$$)`)
    /// * `language` - Programming language (python, rust, javascript, typescript)
    ///
    /// # Returns
    /// `EditResult` containing original, modified content, diff, and edit locations.
    pub fn replace(
        content: &str,
        pattern: &str,
        replacement: &str,
        language: &str,
    ) -> Result<EditResult, EditError> {
        let lang = SupportLang::from_str(language)
            .map_err(|_| EditError::UnsupportedLanguage(language.to_string()))?;

        let root = lang.ast_grep(content);
        let root_node = root.root();

        let search_pattern =
            Pattern::try_new(pattern, lang).map_err(|e| EditError::Pattern(e.to_string()))?;

        // Collect matches in reverse order for safe replacement
        let mut matches: Vec<(usize, usize, String, String)> = Vec::new();

        for node in root_node.dfs() {
            if let Some(m) = search_pattern.match_node(node.clone()) {
                let start_byte = m.range().start;
                let end_byte = m.range().end;
                let original_text = m.text().to_string();

                let new_text = substitute_captures(replacement, m.get_env(), &original_text);
                matches.push((start_byte, end_byte, original_text, new_text));
            }
        }

        if matches.is_empty() {
            return Ok(EditResult {
                original: content.to_string(),
                modified: content.to_string(),
                count: 0,
                diff: String::new(),
                edits: Vec::new(),
            });
        }

        // Sort by position in reverse order
        matches.sort_by(|a, b| b.0.cmp(&a.0));

        // Apply replacements
        let mut modified = content.to_string();
        let mut edits = Vec::new();

        for (start, end, original_text, new_text) in &matches {
            let line = content[..*start].matches('\n').count() + 1;
            let last_newline = content[..*start].rfind('\n').map_or(0, |i| i + 1);
            let column = start - last_newline + 1;

            modified = format!("{}{}{}", &modified[..*start], new_text, &modified[*end..]);

            edits.push(EditLocation {
                line,
                column,
                original_text: original_text.clone(),
                new_text: new_text.clone(),
            });
        }

        edits.reverse();
        let diff = generate_unified_diff(content, &modified);

        Ok(EditResult {
            original: content.to_string(),
            modified,
            count: edits.len(),
            diff,
            edits,
        })
    }

    /// Perform structural replace on a file.
    ///
    /// # Arguments
    /// * `path` - Path to the source file
    /// * `pattern` - ast-grep pattern to match
    /// * `replacement` - Replacement pattern
    /// * `language` - Optional language hint (auto-detected if None)
    /// * `config` - Edit configuration
    ///
    /// # Returns
    /// `EditResult` with changes (file is modified only if `config.preview_only` is false).
    pub fn replace_in_file<P: AsRef<Path>>(
        path: P,
        pattern: &str,
        replacement: &str,
        language: Option<&str>,
        config: EditConfig,
    ) -> Result<EditResult, EditError> {
        let path = path.as_ref();
        let content = omni_io::read_text_safe(path, config.max_file_size)?;

        let lang_str = match language {
            Some(l) => l.to_string(),
            None => {
                if let Some(lang) = SupportLang::from_path(path) {
                    format!("{lang:?}").to_lowercase()
                } else {
                    let ext = path
                        .extension()
                        .map(|e| e.to_string_lossy().to_string())
                        .unwrap_or_else(|| "unknown".to_string());
                    return Err(EditError::UnsupportedLanguage(ext));
                }
            }
        };

        let result = Self::replace(&content, pattern, replacement, &lang_str)?;

        if !config.preview_only && result.count > 0 {
            std::fs::write(path, &result.modified)
                .map_err(|e| EditError::Replacement(format!("Failed to write file: {}", e)))?;
        }

        Ok(result)
    }

    /// Preview structural replace (no file modification).
    ///
    /// Convenience method that always previews without modifying files.
    pub fn preview<P: AsRef<Path>>(
        path: P,
        pattern: &str,
        replacement: &str,
        language: Option<&str>,
    ) -> Result<EditResult, EditError> {
        Self::replace_in_file(
            path,
            pattern,
            replacement,
            language,
            EditConfig {
                preview_only: true,
                ..Default::default()
            },
        )
    }

    /// Apply structural replace (modify file).
    ///
    /// **Use with caution** - this modifies the file in place.
    pub fn apply<P: AsRef<Path>>(
        path: P,
        pattern: &str,
        replacement: &str,
        language: Option<&str>,
    ) -> Result<EditResult, EditError> {
        Self::replace_in_file(
            path,
            pattern,
            replacement,
            language,
            EditConfig {
                preview_only: false,
                ..Default::default()
            },
        )
    }

    /// Format edit result for display.
    ///
    /// Returns a human-readable summary of the changes.
    pub fn format_result(result: &EditResult, path: Option<&str>) -> String {
        let mut output = String::new();

        if let Some(p) = path {
            output.push_str(&format!("// EDIT: {}\n", p));
        }
        output.push_str(&format!("// Replacements: {}\n", result.count));

        if result.count == 0 {
            output.push_str("[No matches found]\n");
            return output;
        }

        output.push_str("\n// Changes:\n");
        for edit in &result.edits {
            output.push_str(&format!(
                "L{}: \"{}\" -> \"{}\"\n",
                edit.line, edit.original_text, edit.new_text
            ));
        }

        output.push_str("\n// Diff:\n");
        output.push_str(&result.diff);

        output
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::TempDir;

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
        let result =
            StructuralEditor::replace(content, "connect($$$)", "async_connect($$$)", "python")
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

        let result =
            StructuralEditor::apply(&path, "deprecated_call($$$)", "modern_call($$$)", None)
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
}
