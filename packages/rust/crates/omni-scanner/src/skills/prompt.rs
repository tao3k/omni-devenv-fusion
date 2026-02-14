//! Prompt Scanner - Parses Python scripts for @prompt decorated functions.
//!
//! Uses TreeSitterPythonParser for robust decorator extraction.

use std::fs;
use std::path::Path;

use hex;
use omni_ast::{DecoratedFunction, TreeSitterPythonParser};
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

use crate::skills::metadata::PromptRecord;

/// Scanner for @prompt decorated functions.
#[derive(Debug)]
pub struct PromptScanner;

impl PromptScanner {
    /// Create a new prompt scanner.
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    /// Scan a scripts directory for @prompt decorated functions.
    ///
    /// # Arguments
    ///
    /// * `scripts_dir` - Path to the scripts directory
    /// * `skill_name` - Name of the parent skill
    ///
    /// # Returns
    ///
    /// A vector of `PromptRecord` objects.
    pub fn scan(
        &self,
        scripts_dir: &Path,
        skill_name: &str,
    ) -> Result<Vec<PromptRecord>, Box<dyn std::error::Error>> {
        let mut prompts = Vec::new();

        if !scripts_dir.exists() {
            log::debug!("Scripts directory not found: {:?}", scripts_dir);
            return Ok(prompts);
        }

        for entry in WalkDir::new(scripts_dir)
            .follow_links(true)
            .sort_by_file_name()
        {
            let entry = match entry {
                Ok(e) => e,
                Err(e) => {
                    log::warn!("Error walking directory {:?}: {}", scripts_dir, e);
                    continue;
                }
            };

            let path = entry.path();
            if !entry.file_type().is_file() {
                continue;
            }

            // Only scan Python files, skip __init__.py
            if path.extension().map(|e| e.to_string_lossy()) != Some("py".into()) {
                continue;
            }
            if path
                .file_name()
                .map(|n| n.to_string_lossy().starts_with("__"))
                == Some(true)
            {
                continue;
            }

            match self.scan_file(path, skill_name) {
                Ok(file_prompts) => prompts.extend(file_prompts),
                Err(e) => log::warn!("Error scanning {:?}: {}", path, e),
            }
        }

        log::debug!(
            "PromptScanner: Found {} @prompt functions in {:?}",
            prompts.len(),
            scripts_dir
        );

        Ok(prompts)
    }

    /// Scan a single file for @prompt decorated functions.
    fn scan_file(
        &self,
        path: &Path,
        skill_name: &str,
    ) -> Result<Vec<PromptRecord>, Box<dyn std::error::Error>> {
        let content = fs::read_to_string(path)?;
        let file_hash = hex::encode(Sha256::digest(content.as_bytes()));

        let mut parser = TreeSitterPythonParser::new();
        let decorated_funcs: Vec<DecoratedFunction> =
            parser.find_decorated_functions(&content, "prompt");

        let mut prompts = Vec::new();

        for func in &decorated_funcs {
            let decorator_args = func.decorator.as_ref().map(|d| &d.arguments);

            // Get prompt name from decorator or function name
            let name = decorator_args
                .and_then(|a| a.name.clone())
                .unwrap_or_else(|| func.name.clone());

            // Get description from docstring or decorator
            let description = decorator_args
                .and_then(|a| a.description.clone())
                .or_else(|| {
                    if !func.docstring.is_empty() {
                        Some(func.docstring.clone())
                    } else {
                        None
                    }
                })
                .unwrap_or_else(|| format!("Prompt {}.{}", skill_name, name));

            // Extract parameter names
            let parameters: Vec<String> = func.parameters.iter().map(|p| p.name.clone()).collect();

            prompts.push(PromptRecord::new(
                name,
                description,
                skill_name.to_string(),
                path.to_string_lossy().to_string(),
                func.name.clone(),
                file_hash.clone(),
                parameters,
            ));
        }

        Ok(prompts)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn test_scan_empty_dir() {
        let scanner = PromptScanner::new();
        let prompts = scanner.scan(Path::new("/nonexistent"), "test").unwrap();
        assert!(prompts.is_empty());
    }

    #[test]
    fn test_scan_finds_prompt() {
        let scanner = PromptScanner::new();
        let files = vec![(
            "/virtual/skill/scripts/prompt.py".to_string(),
            r#"
@prompt(
    name="analyze_code",
    description="Analyze code structure"
)
def analyze_code(file_path: str):
    '''Analyze the given code file.'''
    return f"Please analyze {file_path}"
"#
            .to_string(),
        )];

        let prompts = scanner.scan_paths(&files, "test").unwrap();
        assert_eq!(prompts.len(), 1);
        assert_eq!(prompts[0].name, "analyze_code");
    }
}

impl PromptScanner {
    /// Scan multiple files for @prompt decorated functions.
    ///
    /// Used for testing.
    pub fn scan_paths(
        &self,
        files: &[(String, String)],
        skill_name: &str,
    ) -> Result<Vec<PromptRecord>, Box<dyn std::error::Error>> {
        let mut all_prompts = Vec::new();

        for (file_path, content) in files {
            let _path = Path::new(file_path);
            let file_hash = hex::encode(Sha256::digest(content.as_bytes()));

            let mut parser = TreeSitterPythonParser::new();
            let decorated_funcs: Vec<DecoratedFunction> =
                parser.find_decorated_functions(content, "prompt");

            for func in &decorated_funcs {
                let decorator_args = func.decorator.as_ref().map(|d| &d.arguments);

                let name = decorator_args
                    .and_then(|a| a.name.clone())
                    .unwrap_or_else(|| func.name.clone());

                let description = decorator_args
                    .and_then(|a| a.description.clone())
                    .or_else(|| {
                        if !func.docstring.is_empty() {
                            Some(func.docstring.clone())
                        } else {
                            None
                        }
                    })
                    .unwrap_or_else(|| format!("Prompt {}.{}", skill_name, name));

                let parameters: Vec<String> =
                    func.parameters.iter().map(|p| p.name.clone()).collect();

                all_prompts.push(PromptRecord::new(
                    name,
                    description,
                    skill_name.to_string(),
                    file_path.clone(),
                    func.name.clone(),
                    file_hash.clone(),
                    parameters,
                ));
            }
        }

        Ok(all_prompts)
    }
}
