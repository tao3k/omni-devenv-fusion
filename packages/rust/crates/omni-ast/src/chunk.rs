//! AST-based code chunking for semantic partitioning.
//!
//! Provides functions to split source code into semantic chunks based on
//! AST patterns, enabling high-quality knowledge base construction.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;

use crate::lang::Lang;
use crate::python::extract_python_docstring;
use crate::re_exports::{LanguageExt, MatcherExt, MetaVariable, Pattern, SupportLang};

/// Code chunk for semantic partitioning
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CodeChunk {
    /// Chunk identifier
    pub id: String,
    /// Chunk type (function, class, etc.)
    pub chunk_type: String,
    /// Raw code content
    pub content: String,
    /// Byte offset start
    pub start: usize,
    /// Byte offset end
    pub end: usize,
    /// Line number start (1-indexed)
    pub line_start: usize,
    /// Line number end (1-indexed)
    pub line_end: usize,
    /// Captured metadata (function name, class name, etc.)
    pub metadata: HashMap<String, String>,
    /// Docstring/comment content
    pub docstring: Option<String>,
}

/// Chunk a file into semantic units based on AST patterns.
///
/// # Arguments
/// * `content` - Source code content
/// * `file_path` - Path to the file (for ID generation)
/// * `lang` - Programming language
/// * `patterns` - AST patterns to match (e.g., ["def $NAME", "class $NAME"])
/// * `min_lines` - Minimum lines for a chunk to be included
/// * `max_lines` - Maximum lines for a chunk (splits large chunks, 0 = no limit)
///
/// # Returns
/// Vector of CodeChunk objects
pub fn chunk_code(
    content: &str,
    file_path: &str,
    lang: Lang,
    patterns: &[&str],
    min_lines: usize,
    max_lines: usize,
) -> Result<Vec<CodeChunk>> {
    let lang_str = lang.as_str();
    let support_lang: SupportLang = lang_str
        .parse()
        .with_context(|| format!("Failed to parse language: {}", lang_str))?;

    let grep_result = support_lang.ast_grep(content);
    let root_node = grep_result.root();

    let mut chunks = Vec::new();
    let file_name = Path::new(file_path)
        .file_stem()
        .and_then(|n| n.to_str())
        .unwrap_or("unknown");

    for (chunk_idx, pattern) in patterns.iter().enumerate() {
        let search_pattern = Pattern::try_new(pattern, support_lang)
            .with_context(|| format!("Failed to parse pattern: {}", pattern))?;

        // Determine chunk type from pattern
        let chunk_type = detect_chunk_type(pattern, chunk_idx);

        for node in root_node.dfs() {
            if let Some(m) = search_pattern.match_node(node.clone()) {
                let range = m.range();
                let start = range.start;
                let end = range.end;

                // Calculate line numbers
                let line_start = content[..start].lines().count() + 1;
                let line_end = content[..end].lines().count();

                // Skip if too small
                if line_end - line_start + 1 < min_lines {
                    continue;
                }

                // Extract metadata from captures
                let mut metadata = HashMap::new();
                let env = m.get_env();
                for mv in env.get_matched_variables() {
                    if let MetaVariable::Capture(name, _) = mv {
                        if let Some(captured) = env.get_match(&name) {
                            metadata.insert(name.to_string(), captured.text().to_string());
                        }
                    }
                }

                // Generate chunk ID
                let id = generate_chunk_id(&file_name, &chunk_type, &metadata, chunk_idx);

                // Extract docstring from the matched text
                let matched_text = m.text();
                let docstring = if lang == Lang::Python {
                    let doc = extract_python_docstring(&matched_text);
                    if doc.is_empty() { None } else { Some(doc) }
                } else {
                    None
                };

                // Clone chunk_type for the chunk struct
                let chunk_type_for_chunk = chunk_type.clone();

                let chunk = CodeChunk {
                    id,
                    chunk_type: chunk_type_for_chunk,
                    content: m.text().to_string(),
                    start,
                    end,
                    line_start,
                    line_end,
                    metadata,
                    docstring,
                };

                chunks.push(chunk);
            }
        }
    }

    // Sort by line number
    chunks.sort_by(|a, b| a.line_start.cmp(&b.line_start));

    // Handle max_lines by splitting large chunks
    if max_lines > 0 {
        chunks = split_large_chunks(chunks, max_lines);
    }

    Ok(chunks)
}

/// Detect chunk type from pattern string
fn detect_chunk_type(pattern: &str, idx: usize) -> String {
    if pattern.contains("def $NAME") || pattern.contains("function $NAME") {
        "function".to_string()
    } else if pattern.contains("class $NAME") {
        "class".to_string()
    } else if pattern.contains("interface $NAME") {
        "interface".to_string()
    } else if pattern.contains("struct $NAME") {
        "struct".to_string()
    } else if pattern.contains("const $NAME") || pattern.contains("let $NAME") {
        "variable".to_string()
    } else if pattern.contains("fn $NAME") {
        "function".to_string()
    } else {
        format!("chunk_{}", idx)
    }
}

/// Generate unique chunk ID
fn generate_chunk_id(
    file_name: &str,
    chunk_type: &str,
    metadata: &HashMap<String, String>,
    idx: usize,
) -> String {
    if let Some(name) = metadata.get("NAME") {
        format!("{}_{}_{}", file_name, chunk_type, name)
    } else {
        format!("{}_{}_{}", file_name, chunk_type, idx)
    }
}

/// Split large chunks into smaller parts
fn split_large_chunks(chunks: Vec<CodeChunk>, max_lines: usize) -> Vec<CodeChunk> {
    let mut result = Vec::new();

    for chunk in chunks {
        if chunk.line_end - chunk.line_start + 1 > max_lines {
            result.extend(split_chunk(&chunk, max_lines));
        } else {
            result.push(chunk);
        }
    }

    result
}

/// Split a large chunk into smaller parts
fn split_chunk(chunk: &CodeChunk, max_lines: usize) -> Vec<CodeChunk> {
    let total_lines = chunk.line_end - chunk.line_start + 1;
    if total_lines <= max_lines {
        return vec![chunk.clone()];
    }

    let lines: Vec<&str> = chunk.content.lines().collect();
    let num_parts = (total_lines as f64 / max_lines as f64).ceil() as usize;
    let mut parts = Vec::new();

    for i in 0..num_parts {
        let start_line = i * max_lines;
        let end_line = std::cmp::min((i + 1) * max_lines, total_lines);

        if start_line >= lines.len() {
            break;
        }

        let part_content = lines[start_line..end_line].join("\n");
        let trimmed_content = part_content.trim_end();
        let trimmed_len = trimmed_content.len();

        let part_start = chunk.start + (part_content.len() - trimmed_len);
        let part_end = chunk.start + part_content.len();

        let part = CodeChunk {
            id: format!("{}_part_{}", chunk.id, i),
            chunk_type: chunk.chunk_type.clone(),
            content: trimmed_content.to_string(),
            start: part_start,
            end: part_end,
            line_start: chunk.line_start + start_line,
            line_end: chunk.line_start + end_line - 1,
            metadata: chunk.metadata.clone(),
            docstring: if i == 0 {
                chunk.docstring.clone()
            } else {
                None
            },
        };

        parts.push(part);
    }

    parts
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chunk_python_functions() {
        let content = r#"
def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

def goodbye():
    """Say goodbye."""
    pass

class Greeter:
    """A greeting class."""
    def __init__(self, name: str):
        self.name = name
"#;

        let chunks = chunk_code(
            content,
            "test.py",
            Lang::Python,
            &["def $NAME", "class $NAME"],
            2, // min_lines=2 to exclude 1-line functions
            0,
        )
        .unwrap();

        // Should find: hello (4 lines), goodbye (3 lines), Greeter (5 lines)
        assert_eq!(chunks.len(), 3);

        // Check that we found functions and classes
        let funcs: Vec<_> = chunks
            .iter()
            .filter(|c| c.chunk_type == "function")
            .collect();
        let classes: Vec<_> = chunks.iter().filter(|c| c.chunk_type == "class").collect();
        assert_eq!(funcs.len(), 2);
        assert_eq!(classes.len(), 1);

        // Check docstrings
        assert!(funcs[0].docstring.is_some());
        assert_eq!(funcs[0].docstring.as_ref().unwrap(), "Greet someone.");
    }

    #[test]
    fn test_chunk_id_generation() {
        let content = r#"
def my_function():
    pass
"#;

        let chunks = chunk_code(content, "test.py", Lang::Python, &["def $NAME"], 1, 0).unwrap();

        assert_eq!(chunks.len(), 1);
        assert!(chunks[0].id.contains("my_function"));
        // file_stem gives "test" not "test.py"
        assert!(chunks[0].id.contains("test"));
        assert!(chunks[0].id.contains("function"));
    }

    #[test]
    fn test_min_lines_filter() {
        let content = r#"
def short():
    x = 1
def normal():
    x = 1
    y = 2
    z = 3
"#;

        let chunks = chunk_code(content, "test.py", Lang::Python, &["def $NAME"], 3, 0).unwrap();

        // Only the normal function (4 lines) should be included
        assert_eq!(chunks.len(), 1);
        assert!(chunks[0].content.contains("normal"));
    }

    #[test]
    fn test_max_lines_split() {
        // Create a single large function that spans 25 lines
        let mut lines: Vec<String> = vec!["def large_function():".to_string()];
        for i in 0..24 {
            lines.push(format!("    x_{} = {}", i, i));
        }
        let content = lines.join("\n");

        let chunks = chunk_code(&content, "test.py", Lang::Python, &["def $NAME"], 1, 10).unwrap();

        // 25 lines should be split into 3 chunks
        assert_eq!(chunks.len(), 3);
        for (i, chunk) in chunks.iter().enumerate() {
            assert!(chunk.id.contains("large_function"));
            assert!(chunk.id.contains(&format!("_part_{}", i)));
        }
    }

    #[test]
    fn test_chunk_rust_functions() {
        let content = r#"
fn hello(name: &str) -> String {
    format!("Hello, {}!", name)
}

fn goodbye() {
    println!("Goodbye");
}

struct Greeter {
    name: String,
}

impl Greeter {
    fn new(name: String) -> Self {
        Self { name }
    }
}
"#;

        let chunks = chunk_code(
            content,
            "lib.rs",
            Lang::Rust,
            &["fn $NAME", "struct $NAME"],
            1,
            0,
        )
        .unwrap();

        // Should find: hello, goodbye, Greeter, new
        assert_eq!(chunks.len(), 4);

        // Check chunk types
        let funcs: Vec<_> = chunks
            .iter()
            .filter(|c| c.chunk_type == "function")
            .collect();
        let structs: Vec<_> = chunks.iter().filter(|c| c.chunk_type == "struct").collect();
        assert_eq!(funcs.len(), 3);
        assert_eq!(structs.len(), 1);
    }

    #[test]
    fn test_chunk_javascript_functions() {
        let content = r#"
function hello(name) {
    return `Hello, ${name}!`;
}

const goodbye = () => {
    console.log("Goodbye");
};

class Greeter {
    constructor(name) {
        this.name = name;
    }
}
"#;

        let chunks = chunk_code(
            content,
            "app.js",
            Lang::JavaScript,
            &["function $NAME", "const $NAME"],
            1,
            0,
        )
        .unwrap();

        assert_eq!(chunks.len(), 2);
    }

    #[test]
    fn test_chunk_python_async_functions() {
        let content = r#"
async def fetch_data(url: str) -> dict:
    """Fetch data from URL."""
    response = await http_get(url)
    return response.json()

async def process_items():
    """Process all items concurrently."""
    results = []
    for item in items:
        result = await process(item)
        results.append(result)
    return results
"#;

        let chunks =
            chunk_code(content, "api.py", Lang::Python, &["async def $NAME"], 1, 0).unwrap();

        assert_eq!(chunks.len(), 2);
        assert!(chunks[0].content.contains("fetch_data"));
        assert!(chunks[1].content.contains("process_items"));
    }

    #[test]
    fn test_chunk_empty_content() {
        let chunks = chunk_code("", "empty.py", Lang::Python, &["def $NAME"], 1, 0).unwrap();
        assert_eq!(chunks.len(), 0);
    }

    #[test]
    fn test_chunk_no_matches() {
        let content = r#"
x = 1
y = 2
"#;

        let chunks = chunk_code(
            content,
            "test.py",
            Lang::Python,
            &["def $NAME", "class $NAME"],
            1,
            0,
        )
        .unwrap();
        assert_eq!(chunks.len(), 0);
    }

    #[test]
    fn test_chunk_preserves_order() {
        let content = r#"
class First:
    pass

def second():
    pass

class Third:
    pass

def fourth():
    pass
"#;

        let chunks = chunk_code(
            content,
            "test.py",
            Lang::Python,
            &["def $NAME", "class $NAME"],
            1,
            0,
        )
        .unwrap();

        assert_eq!(chunks.len(), 4);

        // Verify order is preserved
        assert!(chunks[0].id.contains("First"));
        assert!(chunks[1].id.contains("second"));
        assert!(chunks[2].id.contains("Third"));
        assert!(chunks[3].id.contains("fourth"));
    }

    #[test]
    fn test_chunk_metadata_extraction() {
        let content = r#"
def process_user_data(user_id: int, name: str, email: str) -> bool:
    """Process user data."""
    return True
"#;

        let chunks = chunk_code(content, "test.py", Lang::Python, &["def $NAME"], 1, 0).unwrap();

        assert_eq!(chunks.len(), 1);
        let chunk = &chunks[0];

        // Check metadata contains NAME capture
        assert!(chunk.metadata.contains_key("NAME"));
        assert_eq!(chunk.metadata["NAME"], "process_user_data");
    }

    #[test]
    fn test_chunk_with_single_quoted_docstring() {
        let content = r#"
def hello():
    '''Single quoted docstring.'''
    pass
"#;

        let chunks = chunk_code(content, "test.py", Lang::Python, &["def $NAME"], 1, 0).unwrap();

        assert_eq!(chunks.len(), 1);
        assert_eq!(
            chunks[0].docstring,
            Some("Single quoted docstring.".to_string())
        );
    }

    #[test]
    fn test_chunk_multiple_patterns_same_file() {
        let content = r#"
def foo():
    pass

class Bar:
    pass

def baz():
    pass
"#;

        // Match both functions and classes in a single call
        let chunks = chunk_code(
            content,
            "test.py",
            Lang::Python,
            &["def $NAME", "class $NAME"],
            1,
            0,
        )
        .unwrap();

        assert_eq!(chunks.len(), 3);
    }

    #[test]
    fn test_chunk_line_numbers_correct() {
        let content = r#"
def first():
    line 2

def second():
    line 5
"#;

        let chunks = chunk_code(content, "test.py", Lang::Python, &["def $NAME"], 1, 0).unwrap();

        assert_eq!(chunks.len(), 2);

        // Check line numbers are correct (1-indexed)
        assert_eq!(chunks[0].line_start, 2);
        assert_eq!(chunks[0].line_end, 3);

        assert_eq!(chunks[1].line_start, 5);
        assert_eq!(chunks[1].line_end, 6);
    }
}
