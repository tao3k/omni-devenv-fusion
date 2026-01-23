//! High-performance AST-based symbol extractor for code navigation.
//!
//! Extracts symbols (functions, classes, etc.) from source code using ast-grep
//! patterns. Part of The Cartographer.

use std::path::Path;
use std::str::FromStr;

use omni_ast::{AstLanguage, LanguageExt, MatcherExt, MetaVariable, Pattern, SupportLang};

use crate::error::{SearchError, TagError};
use crate::patterns::{
    JS_CLASS_PATTERN, JS_FN_PATTERN, PYTHON_ASYNC_DEF_PATTERN, PYTHON_CLASS_PATTERN,
    PYTHON_DEF_PATTERN, RUST_ENUM_PATTERN, RUST_FN_PATTERN, RUST_IMPL_PATTERN, RUST_STRUCT_PATTERN,
    RUST_TRAIT_PATTERN, TS_INTERFACE_PATTERN,
};
use crate::types::{SearchConfig, SearchMatch, Symbol, SymbolKind};

/// High-performance AST-based symbol extractor for code navigation.
///
/// Extracts symbols (functions, classes, etc.) from source code using ast-grep
/// patterns. Part of The Cartographer.
pub struct TagExtractor;

impl TagExtractor {
    /// Generate a symbolic outline for a file
    /// Returns formatted string ready for LLM consumption
    pub fn outline_file<P: AsRef<Path>>(
        path: P,
        language: Option<&str>,
    ) -> Result<String, TagError> {
        let path = path.as_ref();
        let content = omni_io::read_text_safe(path, 1024 * 1024)?; // 1MB limit for outlining

        let lang = match language {
            Some(l) => match SupportLang::from_str(l) {
                Ok(lang) => lang,
                Err(_) => return Ok(format!("[No outline available for {}", l)),
            },
            None => {
                if let Some(lang) = SupportLang::from_path(path) {
                    lang
                } else {
                    return Ok(format!("[No outline available for {}]", path.display()));
                }
            }
        };

        let symbols = match lang {
            SupportLang::Python => Self::extract_python(&content),
            SupportLang::Rust => Self::extract_rust(&content),
            SupportLang::JavaScript => Self::extract_js(&content),
            SupportLang::TypeScript => Self::extract_ts(&content),
            _ => return Ok(format!("[No outline available for {:?}", lang)),
        };

        if symbols.is_empty() {
            return Ok(format!("[No symbols found in {}]", path.display()));
        }

        // Build CCA-style outline
        let mut output = String::new();
        output.push_str(&format!("// OUTLINE: {}\n", path.display()));
        output.push_str(&format!("// Total symbols: {}\n", symbols.len()));

        for sym in &symbols {
            let kind_str = format!("{:?}", sym.kind).to_lowercase();
            output.push_str(&format!(
                "L{: <4} {: <12} {} {}\n",
                sym.line,
                format!("[{}]", kind_str),
                sym.name,
                sym.signature
            ));
        }

        Ok(output)
    }

    // ============================================================================
    // The Hunter - Structural Code Search
    // ============================================================================

    /// Search for a pattern in a single file using ast-grep
    ///
    /// # Arguments
    /// * `path` - Path to the file to search
    /// * `pattern` - ast-grep pattern (e.g., "connect($ARGS)", "class $NAME")
    /// * `language` - Optional language hint (python, rust, javascript, typescript)
    ///
    /// # Returns
    /// Formatted string showing all matches with context
    pub fn search_file<P: AsRef<Path>>(
        path: P,
        pattern: &str,
        language: Option<&str>,
    ) -> Result<String, SearchError> {
        let path = path.as_ref();
        let content = omni_io::read_text_safe(path, 1024 * 1024)?;

        let lang = match language {
            Some(l) => match SupportLang::from_str(l) {
                Ok(lang) => lang,
                Err(_) => return Err(SearchError::UnsupportedLanguage(l.to_string())),
            },
            None => {
                if let Some(lang) = SupportLang::from_path(path) {
                    lang
                } else {
                    let ext = path
                        .extension()
                        .map(|e| e.to_string_lossy().to_string())
                        .unwrap_or_else(|| "unknown".to_string());
                    return Err(SearchError::UnsupportedLanguage(ext));
                }
            }
        };

        let matches = Self::search_content(&content, pattern, lang, path)?;

        if matches.is_empty() {
            return Ok(format!(
                "[No matches for pattern '{}' in {}]",
                pattern,
                path.display()
            ));
        }

        // Build formatted output
        let mut output = String::new();
        output.push_str(&format!("// SEARCH: {}\n", path.display()));
        output.push_str(&format!("// Pattern: {}\n", pattern));
        output.push_str(&format!("// Total matches: {}\n", matches.len()));

        for m in &matches {
            output.push_str(&format!("L{: <4}:{: <3} {}\n", m.line, m.column, m.content));
        }

        Ok(output)
    }

    /// Search for a pattern in a directory recursively
    ///
    /// # Arguments
    /// * `dir` - Directory to search in
    /// * `pattern` - ast-grep pattern
    /// * `config` - Search configuration
    ///
    /// # Returns
    /// Formatted string showing all matches across files
    pub fn search_directory<P: AsRef<Path>>(
        dir: P,
        pattern: &str,
        config: SearchConfig,
    ) -> Result<String, SearchError> {
        use walkdir::WalkDir;

        let dir = dir.as_ref();
        let mut all_matches: Vec<SearchMatch> = Vec::new();
        let mut file_count = 0;

        let walker = WalkDir::new(dir).follow_links(false).into_iter();

        for entry in walker {
            let entry = match entry {
                Ok(e) => e,
                Err(_) => continue,
            };

            if !entry.file_type().is_file() {
                continue;
            }

            let path = entry.path();
            let ext = path.extension().and_then(|e| e.to_str());

            // Skip files without extensions or not matching language
            let Some(lang_ext) = ext else {
                continue;
            };

            // Map extension to language
            let lang = match lang_ext {
                "py" => Some(SupportLang::Python),
                "rs" => Some(SupportLang::Rust),
                "js" => Some(SupportLang::JavaScript),
                "ts" => Some(SupportLang::TypeScript),
                _ => None,
            };

            if lang.is_none() {
                continue;
            }

            let lang = lang.unwrap();

            // Check file size
            if let Ok(metadata) = entry.metadata() {
                if metadata.len() > config.max_file_size {
                    continue;
                }
            }

            file_count += 1;

            match std::fs::read_to_string(path) {
                Ok(content) => {
                    let matches = Self::search_content(&content, pattern, lang, path)?;
                    all_matches.extend(matches);

                    if all_matches.len() >= config.max_matches_per_file * 10 {
                        // Stop if we have too many matches
                        break;
                    }
                }
                Err(_) => continue,
            };
        }

        if all_matches.is_empty() {
            return Ok(format!(
                "[No matches for pattern '{}' in {}]",
                pattern,
                dir.display()
            ));
        }

        // Group matches by file
        let mut output = String::new();
        output.push_str(&format!("// SEARCH: {}\n", dir.display()));
        output.push_str(&format!("// Pattern: {}\n", pattern));
        output.push_str(&format!("// Files searched: {}\n", file_count));
        output.push_str(&format!("// Total matches: {}\n", all_matches.len()));

        // Group by file
        let mut current_file = String::new();
        for m in all_matches {
            if m.path != current_file {
                current_file = m.path.clone();
                output.push_str(&format!("\n// File: {}\n", current_file));
            }
            output.push_str(&format!("L{: <4}:{: <3} {}\n", m.line, m.column, m.content));
        }

        Ok(output)
    }

    /// Internal: Search content for a pattern
    fn search_content(
        content: &str,
        pattern_str: &str,
        lang: SupportLang,
        path: &Path,
    ) -> Result<Vec<SearchMatch>, SearchError> {
        let root = lang.ast_grep(content);
        let root_node = root.root();

        // Create the pattern using try_new to handle errors gracefully
        let pattern = match Pattern::try_new(pattern_str, lang) {
            Ok(p) => p,
            Err(e) => return Err(SearchError::Pattern(e.to_string())),
        };

        let mut matches = Vec::new();

        // DFS search through all nodes
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let start_pos = m.start_pos();
                let line = start_pos.line();
                // Column calculation requires node reference; use line for simplicity
                let column = 0;

                // Extract captures - get_env returns &MetaVarEnv directly
                let mut captures = std::collections::HashMap::new();
                let env = m.get_env();
                let vars: Vec<String> = env
                    .get_matched_variables()
                    .filter_map(|mv| {
                        // Extract capture name from MetaVariable
                        match mv {
                            MetaVariable::Capture(name, _) => Some(name.to_string()),
                            MetaVariable::MultiCapture(name) => Some(name.to_string()),
                            MetaVariable::Dropped(_) | MetaVariable::Multiple => None,
                        }
                    })
                    .collect();
                for key in &vars {
                    if let Some(captured) = env.get_match(key) {
                        captures.insert(key.clone(), captured.text().to_string());
                    }
                }

                matches.push(SearchMatch {
                    path: path.to_string_lossy().to_string(),
                    line,
                    column,
                    content: m.text().to_string(),
                    captures,
                });

                if matches.len() >= 100 {
                    break; // Limit matches per file
                }
            }
        }

        Ok(matches)
    }

    /// Extract symbols from Python source using AST patterns
    fn extract_python(content: &str) -> Vec<Symbol> {
        let lang = SupportLang::Python;
        let root = lang.ast_grep(content);
        let root_node = root.root();

        let mut symbols = Vec::new();

        // Extract classes
        let pattern = Pattern::new(PYTHON_CLASS_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("class {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Class,
                    line,
                    signature: sig,
                });
            }
        }

        // Extract functions
        let pattern = Pattern::new(PYTHON_DEF_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("def {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Function,
                    line,
                    signature: sig,
                });
            }
        }

        // Extract async functions
        let pattern = Pattern::new(PYTHON_ASYNC_DEF_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("async def {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::AsyncFunction,
                    line,
                    signature: sig,
                });
            }
        }

        // Sort by line number and deduplicate
        symbols.sort_by_key(|s| s.line);
        symbols
    }

    /// Extract symbols from Rust source using AST patterns
    fn extract_rust(content: &str) -> Vec<Symbol> {
        let lang = SupportLang::Rust;
        let root = lang.ast_grep(content);
        let root_node = root.root();

        let mut symbols = Vec::new();

        // Extract structs
        let pattern = Pattern::new(RUST_STRUCT_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("struct {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Struct,
                    line,
                    signature: sig,
                });
            }
        }

        // Extract functions
        let pattern = Pattern::new(RUST_FN_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("fn {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Function,
                    line,
                    signature: sig,
                });
            }
        }

        // Extract enums
        let pattern = Pattern::new(RUST_ENUM_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("enum {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Enum,
                    line,
                    signature: sig,
                });
            }
        }

        // Extract traits
        let pattern = Pattern::new(RUST_TRAIT_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("trait {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Trait,
                    line,
                    signature: sig,
                });
            }
        }

        // Extract impl blocks
        let pattern = Pattern::new(RUST_IMPL_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("impl {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Impl,
                    line,
                    signature: sig,
                });
            }
        }

        symbols.sort_by_key(|s| s.line);
        symbols
    }

    /// Extract symbols from JavaScript source
    fn extract_js(content: &str) -> Vec<Symbol> {
        let lang = SupportLang::JavaScript;
        let root = lang.ast_grep(content);
        let root_node = root.root();

        let mut symbols = Vec::new();

        // Extract classes
        let pattern = Pattern::new(JS_CLASS_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("class {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Class,
                    line,
                    signature: sig,
                });
            }
        }

        // Extract functions
        let pattern = Pattern::new(JS_FN_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("function {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Function,
                    line,
                    signature: sig,
                });
            }
        }

        symbols.sort_by_key(|s| s.line);
        symbols
    }

    /// Extract symbols from TypeScript source
    fn extract_ts(content: &str) -> Vec<Symbol> {
        let lang = SupportLang::TypeScript;
        let root = lang.ast_grep(content);
        let root_node = root.root();

        let mut symbols = Vec::new();

        // First extract JS-like symbols
        symbols.extend(Self::extract_js(content));

        // Extract interfaces
        let pattern = Pattern::new(TS_INTERFACE_PATTERN, lang);
        for node in root_node.dfs() {
            if let Some(m) = pattern.match_node(node.clone()) {
                let name = Self::get_capture(&m, "NAME");
                let line = m.start_pos().line();
                let sig = format!("interface {}", name);
                symbols.push(Symbol {
                    name: name.clone(),
                    kind: SymbolKind::Interface,
                    line,
                    signature: sig,
                });
            }
        }

        symbols.sort_by_key(|s| s.line);
        symbols
    }

    /// Get the text of a variable capture from a matched node
    fn get_capture<D: omni_ast::Doc>(m: &omni_ast::NodeMatch<D>, capture: &str) -> String {
        m.get_env()
            .get_match(capture)
            .map(|n| n.text().to_string())
            .unwrap_or_default()
    }
}
