//! AST-based code extraction utilities.
//!
//! Provides high-level functions for extracting code elements from source files
//! with precise location information (byte offsets, line numbers) and capture support.

use std::collections::HashMap;

use crate::lang::Lang;
use crate::re_exports::{LanguageExt, MatcherExt, MetaVariable, Pattern, SupportLang};

/// Result of extracting a single code element.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExtractResult {
    /// The matched code text
    pub text: String,
    /// Byte offset start position
    pub start: usize,
    /// Byte offset end position
    pub end: usize,
    /// Line number start (1-indexed)
    pub line_start: usize,
    /// Line number end (1-indexed)
    pub line_end: usize,
    /// Captured variable values (name -> value)
    pub captures: HashMap<String, String>,
}

impl ExtractResult {
    /// Create a new ExtractResult
    #[must_use]
    pub fn new(
        text: String,
        start: usize,
        end: usize,
        line_start: usize,
        line_end: usize,
        captures: HashMap<String, String>,
    ) -> Self {
        Self {
            text,
            start,
            end,
            line_start,
            line_end,
            captures,
        }
    }
}

/// Extract code elements from content using an ast-grep pattern.
///
/// # Arguments
///
/// * `content` - The source code content to search
/// * `pattern` - The ast-grep pattern (e.g., "def $NAME", "class $CLASS")
/// * `lang` - The programming language
/// * `capture_names` - Optional list of capture names to include in results
///
/// # Returns
///
/// A vector of `ExtractResult` containing all matches with location info and captures.
///
/// # Examples
///
/// ```rust
/// use omni_ast::{extract_items, Lang};
///
/// let content = r#"
/// def hello(name: str) -> str:
///     '''Greet someone.'''
///     return f"Hello, {name}!"
///
/// def goodbye():
///     pass
/// "#;
///
/// let results = extract_items(content, "def $NAME", Lang::Python, None);
/// assert_eq!(results.len(), 2);
/// ```
pub fn extract_items(
    content: &str,
    pattern: &str,
    lang: Lang,
    capture_names: Option<Vec<&str>>,
) -> Vec<ExtractResult> {
    let lang_str = lang.as_str();
    let support_lang: SupportLang = match lang_str.parse() {
        Ok(l) => l,
        Err(_) => return Vec::new(),
    };

    let grep_result = support_lang.ast_grep(content);
    let root_node = grep_result.root();

    let search_pattern = match Pattern::try_new(pattern, support_lang) {
        Ok(p) => p,
        Err(_) => return Vec::new(),
    };

    // Pre-compute line index for fast line number lookup
    let line_offsets: Vec<usize> = content
        .char_indices()
        .filter(|(_, c)| *c == '\n')
        .map(|(i, _)| i)
        .chain(std::iter::once(content.len()))
        .collect();

    let capture_names: Option<HashMap<String, ()>> =
        capture_names.map(|v| v.into_iter().map(|s| (s.to_string(), ())).collect());

    let mut results = Vec::new();

    for node in root_node.dfs() {
        if let Some(m) = search_pattern.match_node(node.clone()) {
            let env = m.get_env();

            // Extract captures based on filter
            let mut captures = HashMap::new();
            for mv in env.get_matched_variables() {
                let name = match &mv {
                    MetaVariable::Capture(name, _) => name.as_str(),
                    MetaVariable::MultiCapture(name) => name.as_str(),
                    _ => continue,
                };

                // Apply capture name filter if provided
                if let Some(ref filter) = capture_names {
                    if !filter.contains_key(name) {
                        continue;
                    }
                }

                if let Some(captured) = env.get_match(name) {
                    captures.insert(name.to_string(), captured.text().to_string());
                }
            }

            // Calculate line numbers from byte offsets
            let start = m.range().start;
            let end = m.range().end;
            let (line_start, line_end) = byte_to_line(start, end, &line_offsets);

            results.push(ExtractResult {
                text: m.text().to_string(),
                start,
                end,
                line_start,
                line_end,
                captures,
            });
        }
    }

    results
}

/// Convert byte offsets to line numbers (1-indexed).
fn byte_to_line(byte_start: usize, byte_end: usize, line_offsets: &[usize]) -> (usize, usize) {
    let line_start = line_offsets
        .iter()
        .position(|&offset| offset >= byte_start)
        .map(|i| i + 1) // Convert to 1-indexed
        .unwrap_or(1);

    let line_end = line_offsets
        .iter()
        .position(|&offset| offset >= byte_end)
        .map(|i| i + 1) // Convert to 1-indexed
        .unwrap_or(line_start);

    (line_start, line_end)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_python_functions() {
        let content = r#"
def hello(name: str) -> str:
    '''Greet someone.'''
    return f"Hello, {name}!"

def goodbye():
    pass
"#;

        let results = extract_items(content, "def $NAME", Lang::Python, None);
        // Should find 2 top-level functions (not method inside class)
        assert_eq!(results.len(), 2);

        // Check first function
        let hello = &results[0];
        assert!(hello.text.starts_with("def hello"));
        assert!(hello.captures.contains_key("NAME"));
        assert_eq!(hello.captures["NAME"], "hello");
        assert!(hello.line_start >= 2);
        assert!(hello.line_end >= hello.line_start);
    }

    #[test]
    fn test_extract_with_capture_filter() {
        let content = r#"
def hello(name: str) -> str:
    return f"Hello, {name}!"

def goodbye():
    pass
"#;

        // Use simple pattern without ARGS to match both functions
        let results = extract_items(content, "def $NAME", Lang::Python, Some(vec!["NAME"]));
        assert_eq!(results.len(), 2);

        for r in &results {
            assert!(r.captures.contains_key("NAME"));
        }
    }

    #[test]
    fn test_extract_rust_functions() {
        let content = r#"
fn hello(name: &str) -> String {
    format!("Hello, {}!", name)
}

fn goodbye() {
    println!("Goodbye");
}
"#;

        let results = extract_items(content, "fn $NAME", Lang::Rust, None);
        assert_eq!(results.len(), 2);

        let hello = &results[0];
        assert!(hello.text.starts_with("fn hello"));
        assert_eq!(hello.captures["NAME"], "hello");
    }

    #[test]
    fn test_extract_classes() {
        let content = r#"
class MyClass:
    def method(self):
        pass

class AnotherClass:
    pass
"#;

        let results = extract_items(content, "class $NAME", Lang::Python, None);
        assert_eq!(results.len(), 2);
    }

    #[test]
    fn test_extract_empty_result() {
        let content = "let x = 42;";
        let results = extract_items(content, "def $NAME", Lang::Python, None);
        assert!(results.is_empty());
    }

    #[test]
    fn test_line_numbers() {
        let content = "x = 1\ny = 2\nz = 3\n";
        let results = extract_items(content, "$NAME = $VALUE", Lang::Python, Some(vec!["NAME"]));

        // Should find 3 matches
        assert_eq!(results.len(), 3);

        // Check line numbers (1-indexed)
        assert_eq!(results[0].line_start, 1);
        assert_eq!(results[1].line_start, 2);
        assert_eq!(results[2].line_start, 3);
    }

    #[test]
    fn test_invalid_pattern() {
        let content = "def hello(): pass";
        let results = extract_items(content, "invalid[pattern", Lang::Python, None);
        assert!(results.is_empty());
    }

    #[test]
    fn test_extract_variables() {
        let content = r#"
x = 1
y = 2
name = "hello"
"#;

        let results = extract_items(content, "$NAME = $VALUE", Lang::Python, None);
        assert_eq!(results.len(), 3);

        for r in &results {
            assert!(r.captures.contains_key("NAME"));
            assert!(r.captures.contains_key("VALUE"));
        }
    }
}
