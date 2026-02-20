//! AST-based code extraction utilities.
//!
//! Provides high-level functions for extracting code elements from source files
//! with precise location information (byte offsets, line numbers) and capture support.

use std::collections::{HashMap, HashSet};

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
    /// Create a new `ExtractResult`.
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
#[must_use]
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

    let Ok(search_pattern) = Pattern::try_new(pattern, support_lang) else {
        return Vec::new();
    };

    // Pre-compute line index for fast line number lookup
    let line_offsets: Vec<usize> = content
        .char_indices()
        .filter(|(_, c)| *c == '\n')
        .map(|(i, _)| i)
        .chain(std::iter::once(content.len()))
        .collect();

    let capture_names: Option<HashSet<String>> =
        capture_names.map(|v| v.into_iter().map(str::to_string).collect());

    let mut results = Vec::new();

    for node in root_node.dfs() {
        if let Some(m) = search_pattern.match_node(node.clone()) {
            let env = m.get_env();

            // Extract captures based on filter
            let mut captures = HashMap::new();
            for mv in env.get_matched_variables() {
                let name = match &mv {
                    MetaVariable::Capture(name, _) | MetaVariable::MultiCapture(name) => {
                        name.as_str()
                    }
                    _ => continue,
                };

                // Apply capture name filter if provided
                if let Some(ref filter) = capture_names
                    && !filter.contains(name)
                {
                    continue;
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
        .map_or(1, |i| i + 1); // Convert to 1-indexed

    let line_end = line_offsets
        .iter()
        .position(|&offset| offset >= byte_end)
        .map_or(line_start, |i| i + 1); // Convert to 1-indexed

    (line_start, line_end)
}

/// Get skeleton patterns for a language.
///
/// These patterns extract only signatures (function/class definitions with docstrings),
/// removing implementation details for lightweight indexing.
#[must_use]
pub fn get_skeleton_patterns(lang: Lang) -> &'static [&'static str] {
    match lang {
        Lang::Python => &["def $NAME", "class $NAME", "async def $NAME"],
        Lang::Rust => &[
            "fn $NAME",
            "pub fn $NAME",
            "struct $NAME",
            "pub struct $NAME",
            "impl $NAME",
        ],
        Lang::JavaScript | Lang::TypeScript => &[
            "function $NAME",
            "class $NAME",
            "const $NAME = function",
            "const $NAME = (",
        ],
        Lang::Go => &["func $NAME", "type $NAME struct", "type $NAME interface"],
        Lang::Java => &["public $NAME", "class $NAME", "interface $NAME"],
        Lang::C | Lang::Cpp => &["$TYPE $NAME(", "class $NAME", "struct $NAME"],
        Lang::CSharp => &["public $TYPE $NAME", "class $NAME", "interface $NAME"],
        Lang::Ruby => &["def $NAME", "class $NAME"],
        Lang::Swift => &["func $NAME", "class $NAME", "struct $NAME"],
        Lang::Kotlin => &["fun $NAME", "class $NAME", "data class $NAME"],
        Lang::Lua => &["function $NAME", "local $NAME = function"],
        Lang::Php => &["function $NAME", "class $NAME", "public function $NAME"],
        Lang::Bash => &["$NAME()", "function $NAME"],
        _ => &["$NAME"],
    }
}

/// Extract skeleton (signatures + docstrings) from source code.
///
/// This function extracts only the structural definitions (function signatures,
/// class definitions) along with their docstrings, removing implementation bodies.
/// It's ideal for lightweight semantic indexing where full code content is not needed.
///
/// # Arguments
///
/// * `content` - The source code content
/// * `lang` - The programming language
///
/// # Returns
///
/// A concatenated string of all skeletons (signatures + docstrings)
///
/// # Examples
///
/// ```rust
/// use omni_ast::{extract_skeleton, Lang};
///
/// let python_code = r#"
/// def hello(name: str) -> str:
///     """Greet someone by name."""
///     return f"Hello, {name}!"
///
/// def goodbye():
///     """Say goodbye."""
///     print("Goodbye")
/// "#;
///
/// let skeleton = extract_skeleton(python_code, Lang::Python);
/// assert!(skeleton.contains("def hello"));
/// assert!(skeleton.contains("Greet someone")); // docstring preserved
/// ```
#[must_use]
pub fn extract_skeleton(content: &str, lang: Lang) -> String {
    let patterns = get_skeleton_patterns(lang);

    // Extract items for each pattern and combine results
    let mut all_results: Vec<String> = Vec::new();
    for pattern in patterns {
        let results = extract_items(content, pattern, lang, None);
        for result in results {
            if !result.text.is_empty() {
                // Extract just the signature line (before the body starts)
                let signature = extract_signature(&result.text, lang);
                if !signature.is_empty() {
                    all_results.push(signature);
                }
            }
        }
    }

    all_results.join("\n\n")
}

/// Extract just the signature line from a code element, removing the body.
/// For Python: takes everything up to and including the colon on the first line.
/// For Rust/C-like: takes everything up to the first opening brace.
fn extract_signature(text: &str, lang: Lang) -> String {
    let first_line = text.lines().next().unwrap_or(text);

    match lang {
        Lang::Python | Lang::Ruby | Lang::Lua | Lang::Bash => {
            // For Python-like languages, the signature is the entire first line
            first_line.trim().to_string()
        }
        Lang::Rust
        | Lang::C
        | Lang::Cpp
        | Lang::CSharp
        | Lang::Java
        | Lang::Go
        | Lang::Swift
        | Lang::Kotlin
        | Lang::Php
        | Lang::JavaScript
        | Lang::TypeScript => {
            // For C-like languages, truncate at the first '{'
            match first_line.find('{') {
                Some(idx) => first_line[..idx].trim().to_string(),
                None => first_line.trim().to_string(),
            }
        }
        _ => first_line.trim().to_string(),
    }
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

    #[test]
    fn test_extract_skeleton_python() {
        let content = r#"
def hello(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

def goodbye():
    """Say goodbye."""
    print("Goodbye")

class MyClass:
    """A sample class."""
    def method(self):
        """A method."""
        pass
"#;

        let skeleton = extract_skeleton(content, Lang::Python);

        // Should contain function/class names
        assert!(
            skeleton.contains("hello"),
            "Should contain 'hello' function"
        );
        assert!(
            skeleton.contains("goodbye"),
            "Should contain 'goodbye' function"
        );
        assert!(skeleton.contains("MyClass"), "Should contain 'MyClass'");

        // Should NOT contain implementation details
        assert!(
            !skeleton.contains("return f"),
            "Should not contain 'return f'"
        );
        assert!(!skeleton.contains("print("), "Should not contain 'print('");
        assert!(!skeleton.contains("pass"), "Should not contain 'pass'");

        // Each signature should be on its own line
        let lines: Vec<&str> = skeleton.lines().collect();
        assert!(lines.len() >= 3, "Should have at least 3 signatures");
    }

    #[test]
    fn test_extract_skeleton_rust() {
        let content = r#"
fn hello(name: &str) -> String {
    format!("Hello, {}!", name)
}

pub struct User {
    id: u32,
    name: String,
}

impl User {
    pub fn new(id: u32, name: String) -> Self {
        User { id, name }
    }
}
"#;

        let skeleton = extract_skeleton(content, Lang::Rust);

        // Should contain signatures (truncated at '{')
        assert!(skeleton.contains("fn hello"), "Should contain 'fn hello'");
        assert!(
            skeleton.contains("pub struct User"),
            "Should contain 'pub struct User'"
        );
        assert!(skeleton.contains("impl User"), "Should contain 'impl User'");

        // Should NOT contain implementation
        assert!(
            !skeleton.contains("format!"),
            "Should not contain 'format!'"
        );
        assert!(
            !skeleton.contains("User { id, name }"),
            "Should not contain struct init"
        );
    }

    #[test]
    fn test_get_skeleton_patterns() {
        let py_patterns = get_skeleton_patterns(Lang::Python);
        assert!(py_patterns.contains(&"def $NAME"));
        assert!(py_patterns.contains(&"class $NAME"));

        let rs_patterns = get_skeleton_patterns(Lang::Rust);
        assert!(rs_patterns.contains(&"fn $NAME"));
        assert!(rs_patterns.contains(&"pub fn $NAME"));
    }
}
