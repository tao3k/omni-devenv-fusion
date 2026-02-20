//! Context Assembler - Parallel I/O + Templating + Token Counting
//!
//! This module provides the core context hydration logic for skills.
//! It combines parallel file reading, template rendering, and token counting
//! into a single efficient operation.

use std::path::PathBuf;

use minijinja::Environment;
use rayon::prelude::*;
use serde_json::Value;

use crate::error::Result;
use omni_tokenizer::count_tokens;

/// Result of assembling skill context.
#[derive(Debug, Clone)]
pub struct AssemblyResult {
    /// The assembled content string.
    pub content: String,
    /// Token count of the content.
    pub token_count: usize,
    /// List of reference paths that could not be read.
    pub missing_refs: Vec<PathBuf>,
}

/// Context assembler for skill protocols.
///
/// Combines parallel I/O (rayon), template rendering (minijinja),
/// and token counting (omni-tokenizer) for efficient context hydration.
#[derive(Debug, Clone)]
pub struct ContextAssembler {
    env: Environment<'static>,
}

impl ContextAssembler {
    /// Create a new context assembler with default settings.
    #[must_use]
    pub fn new() -> Self {
        let mut env = Environment::new();
        env.set_undefined_behavior(minijinja::UndefinedBehavior::Strict);
        Self { env }
    }

    /// Assemble skill context from main file and references.
    ///
    /// This method:
    /// 1. Reads the main skill file and all references in parallel
    /// 2. Renders the main template with the provided variables
    /// 3. Assembles the final content with proper formatting
    /// 4. Counts tokens using omni-tokenizer
    ///
    /// # Arguments
    ///
    /// * `main_path` - Path to the main SKILL.md file
    /// * `ref_paths` - List of paths to reference files
    /// * `variables` - JSON object with template variables
    ///
    /// # Returns
    ///
    /// `Result<AssemblyResult>` containing the assembled content and metadata
    ///
    /// # Errors
    ///
    /// This currently never returns an error and is modeled as `Result` for API compatibility.
    #[cfg(feature = "assembler")]
    #[allow(clippy::needless_pass_by_value, clippy::unnecessary_wraps)]
    pub fn assemble_skill(
        &self,
        main_path: PathBuf,
        ref_paths: Vec<PathBuf>,
        variables: Value,
    ) -> Result<AssemblyResult> {
        // 1. [Parallel I/O] Read main file and references concurrently
        let (main_res, refs_res) = rayon::join(
            || std::fs::read_to_string(&main_path),
            || {
                ref_paths
                    .par_iter()
                    .map(|p| (p.clone(), std::fs::read_to_string(p)))
                    .collect::<Vec<_>>()
            },
        );

        let main_template = main_res.unwrap_or_default();

        // 2. [Templating] Render the main template
        let rendered_main = self
            .env
            .render_str(&main_template, &variables)
            .unwrap_or_else(|e| format!("[Template Error: {e}]"));

        // 3. [Assembly] Build the final buffer
        let mut buffer = String::with_capacity(rendered_main.len() + 2048);
        buffer.push_str("# Active Protocol\n");
        buffer.push_str(&rendered_main);

        let mut missing = Vec::new();

        if !ref_paths.is_empty() {
            buffer.push_str("\n\n# Required References\n");
            for (path, content_res) in refs_res {
                match content_res {
                    Ok(c) => {
                        buffer.push_str("\n## ");
                        if let Some(name) = path.file_name() {
                            buffer.push_str(&name.to_string_lossy());
                        }
                        buffer.push('\n');
                        buffer.push_str(&c);
                    }
                    Err(_) => missing.push(path),
                }
            }
        }

        // 4. [Token Counting] using omni-tokenizer
        let count = count_tokens(&buffer);

        Ok(AssemblyResult {
            content: buffer,
            token_count: count,
            missing_refs: missing,
        })
    }
}

impl Default for ContextAssembler {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
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

        assert!(result.missing_refs.len() == 1);
    }
}
