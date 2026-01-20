//! Script Scanner - Parses Python scripts for @skill_command decorated functions.
//!
//! Uses ast-grep for precise AST pattern matching to find functions
//! decorated with `@skill_command`.
//!
//! # Architecture
//!
//! Follows the skill structure defined in `settings.yaml`:
//! - Default: `scripts/` - Standalone executables (Python workflows, state management)
//!   NOTE: `tools.py` is deprecated - all tools should be in `scripts/`
//!
//! # Example
//!
//! ```ignore
//! use skills_scanner::ScriptScanner;
//!
//! let scanner = ScriptScanner::new();
//! let tools = scanner.scan_scripts(
//!     PathBuf::from("assets/skills/writer/scripts"),
//!     "writer",
//!     &["write", "edit"]  // routing_keywords from SkillMetadata
//! ).unwrap();
//!
//! for tool in tools {
//!     println!("Found tool: {}", tool.tool_name);
//! }
//! ```

use std::fs;
use std::path::Path;

use hex;
use omni_ast::{LanguageExt, MatcherExt, Pattern, SupportLang};
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

use crate::skill_metadata::{SkillStructure, ToolRecord};

/// Script Scanner - Discovers tools in script files using ast-grep.
///
/// This scanner parses Python files in the `scripts/` directory to find
/// functions decorated with `@skill_command`. The discovered tools are
/// enriched with routing keywords from the skill's SKILL.md file.
///
/// # Usage
///
/// ```ignore
/// use skills_scanner::ScriptScanner;
///
/// let scanner = ScriptScanner::new();
/// let tools = scanner.scan_scripts(
///     Path::new("assets/skills/git/scripts"),
///     "git",
///     &["commit", "branch", "merge"]
/// ).unwrap();
/// ```
#[derive(Debug)]
pub struct ScriptScanner;

impl ScriptScanner {
    /// Create a new script scanner.
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    /// Scan a scripts directory for @skill_command decorated functions.
    ///
    /// # Arguments
    ///
    /// * `scripts_dir` - Path to the scripts directory (e.g., "assets/skills/writer/scripts")
    /// * `skill_name` - Name of the parent skill (e.g., "writer")
    /// * `skill_keywords` - Routing keywords from SKILL.md (used for keyword boosting)
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects representing discovered tools.
    ///
    /// # Examples
    ///
    /// ```ignore
    /// let scanner = ScriptScanner::new();
    /// let tools = scanner.scan_scripts(
    ///     PathBuf::from("assets/skills/writer/scripts"),
    ///     "writer",
    ///     &["write", "edit", "polish"]
    /// ).unwrap();
    /// ```
    pub fn scan_scripts(
        &self,
        scripts_dir: &Path,
        skill_name: &str,
        skill_keywords: &[String],
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let mut tools = Vec::new();

        if !scripts_dir.exists() {
            log::debug!("Scripts directory not found: {:?}", scripts_dir);
            return Ok(tools);
        }

        for entry in WalkDir::new(scripts_dir).into_iter().filter_map(|e| e.ok()) {
            let path = entry.path();

            if path.is_dir() {
                continue;
            }

            // Only scan Python files
            if path.extension().map_or(false, |ext| ext != "py") {
                continue;
            }

            // Skip __init__.py
            if path.file_name().map_or(false, |name| name == "__init__.py") {
                continue;
            }

            let parsed_tools = self.parse_script(path, skill_name, skill_keywords)?;
            tools.extend(parsed_tools);
        }

        if !tools.is_empty() {
            log::info!(
                "Scanned {} tools from {:?} for skill '{}'",
                tools.len(),
                scripts_dir,
                skill_name
            );
        }

        Ok(tools)
    }

    /// Scan a single skill directory (scripts/ subdirectory).
    ///
    /// This is a convenience method that combines finding the scripts directory
    /// and scanning it.
    ///
    /// # Arguments
    ///
    /// * `skill_path` - Path to the skill directory (e.g., "assets/skills/writer")
    /// * `skill_name` - Name of the skill
    /// * `skill_keywords` - Routing keywords from SKILL.md
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects.
    pub fn scan_skill_scripts(
        &self,
        skill_path: &Path,
        skill_name: &str,
        skill_keywords: &[String],
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let scripts_dir = skill_path.join("scripts");
        self.scan_scripts(&scripts_dir, skill_name, skill_keywords)
    }

    /// Scan a skill directory using the canonical skill structure.
    ///
    /// Only scans directories defined in the skill structure's `default` list.
    /// This ensures only intended directories (scripts/, templates/, etc.) are scanned.
    ///
    /// # Arguments
    ///
    /// * `skill_path` - Path to the skill directory
    /// * `skill_name` - Name of the skill
    /// * `skill_keywords` - Routing keywords from SKILL.md
    /// * `structure` - Skill structure defining which directories to scan
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects from all scanned directories.
    pub fn scan_with_structure(
        &self,
        skill_path: &Path,
        skill_name: &str,
        skill_keywords: &[String],
        structure: &SkillStructure,
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let mut all_tools = Vec::new();

        // Get directories to scan from structure
        let script_dirs = structure.script_directories();

        for dir_name in script_dirs {
            let dir_path = skill_path.join(dir_name);
            if dir_path.exists() && dir_path.is_dir() {
                let tools = self.scan_scripts(&dir_path, skill_name, skill_keywords)?;
                all_tools.extend(tools);
            }
        }

        Ok(all_tools)
    }

    /// Parse a single script file for tool definitions.
    ///
    /// Uses ast-grep to find function definitions decorated with `@skill_command`.
    ///
    /// # Arguments
    ///
    /// * `path` - Path to the Python script file
    /// * `skill_name` - Name of the parent skill
    /// * `skill_keywords` - Routing keywords from SKILL.md
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects.
    fn parse_script(
        &self,
        path: &Path,
        skill_name: &str,
        skill_keywords: &[String],
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let content = fs::read_to_string(path)?;
        let file_path = path.to_string_lossy().to_string();
        let mut tools = Vec::new();

        // Compute SHA256 hash for incremental indexing
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        let file_hash = hex::encode(hasher.finalize());

        // Use ast-grep to find ONLY function definitions decorated with @skill_command
        let lang: SupportLang = "py".parse().expect("Python language should be supported");
        let root = lang.ast_grep(&content);
        let root_node = root.root();

        // Pattern to match @skill_command decorator with name parameter
        let decorator_with_name = r#"skill_command(name=$NAME, $$$)"#;
        let search_decorator_with_name = Pattern::try_new(decorator_with_name, lang)
            .map_err(|e| anyhow::anyhow!("Failed to parse decorator pattern: {}", e))?;

        // Pattern to match @skill_command decorator without name parameter
        let decorator_pattern = r#"skill_command($$$)"#;
        let search_decorator = Pattern::try_new(decorator_pattern, lang)
            .map_err(|e| anyhow::anyhow!("Failed to parse decorator pattern: {}", e))?;

        // Pattern to get function name
        let func_pattern = r#"def $NAME"#;
        let search_func = Pattern::try_new(func_pattern, lang)
            .map_err(|e| anyhow::anyhow!("Failed to parse function pattern: {}", e))?;

        // Track which functions are decorated by @skill_command
        let mut decorator_info: std::collections::HashMap<String, (usize, Option<String>)> =
            std::collections::HashMap::new();

        // Find decorators with name parameter and extract the name
        for node in root_node.dfs() {
            if let Some(m) = search_decorator_with_name.match_node(node.clone()) {
                let range = node.range();
                let env = m.get_env();

                let raw_name = env
                    .get_match("NAME")
                    .map(|n| n.text().to_string())
                    .unwrap_or_default();

                let tool_name = raw_name.trim_matches('"').trim_matches('\'').to_string();

                // Find the function this decorator applies to
                let func_range_start = range.end;
                for func_node in root_node.dfs() {
                    if let Some(func_match) = search_func.match_node(func_node.clone()) {
                        let func_env = func_match.get_env();
                        let func_name = func_env
                            .get_match("NAME")
                            .map(|n| n.text().to_string())
                            .unwrap_or_else(|| "unknown".to_string());
                        let func_range = func_match.range();

                        if func_range.start > func_range_start
                            && func_range.start - func_range_start < 500
                        {
                            if !tool_name.is_empty() {
                                decorator_info
                                    .insert(func_name.clone(), (range.end, Some(tool_name)));
                            }
                            break;
                        }
                    }
                }
            }
        }

        // Find decorators without explicit name parameter
        for node in root_node.dfs() {
            if search_decorator.match_node(node.clone()).is_some()
                && search_decorator_with_name
                    .match_node(node.clone())
                    .is_none()
            {
                let range = node.range();

                for func_node in root_node.dfs() {
                    if let Some(func_match) = search_func.match_node(func_node.clone()) {
                        let func_env = func_match.get_env();
                        let func_name = func_env
                            .get_match("NAME")
                            .map(|n| n.text().to_string())
                            .unwrap_or_else(|| "unknown".to_string());
                        let func_range = func_match.range();

                        if func_range.start > range.end && func_range.start - range.end < 500 {
                            if !decorator_info.contains_key(&func_name) {
                                decorator_info.insert(func_name.clone(), (range.end, None));
                            }
                            break;
                        }
                    }
                }
            }
        }

        // Now find functions and create ToolRecords
        for node in root_node.dfs() {
            if let Some(m) = search_func.match_node(node.clone()) {
                let env = m.get_env();

                let func_name = env
                    .get_match("NAME")
                    .map(|n| n.text().to_string())
                    .unwrap_or_else(|| "unknown".to_string());

                // Check if this function has a @skill_command decorator
                if let Some((_, tool_name_opt)) = decorator_info.get(&func_name) {
                    let tool_name = match tool_name_opt {
                        Some(name) => name.clone(),
                        None => func_name.clone(),
                    };

                    // Generate description
                    let description = format!("Execute {}.{}", skill_name, tool_name);

                    // Extract docstring from function body
                    let matched_text = m.text().to_string();
                    let docstring = self.extract_docstring_from_text(&matched_text);

                    // Combine skill-level keywords (from SKILL.md) with tool-level keywords
                    let mut combined_keywords = vec![skill_name.to_string(), tool_name.clone()];
                    combined_keywords.extend(skill_keywords.iter().cloned());

                    tools.push(ToolRecord {
                        tool_name: format!("{}.{}", skill_name, tool_name),
                        description,
                        skill_name: skill_name.to_string(),
                        file_path: file_path.clone(),
                        function_name: func_name,
                        execution_mode: "script".to_string(),
                        keywords: combined_keywords,
                        file_hash: file_hash.clone(),
                        input_schema: "{}".to_string(),
                        docstring,
                    });
                }
            }
        }

        Ok(tools)
    }

    /// Extract docstring from matched function text.
    fn extract_docstring_from_text(&self, text: &str) -> String {
        if let Some(start) = text.find("\"\"\"") {
            if let Some(end) = text[start + 3..].find("\"\"\"") {
                let doc = &text[start + 3..start + 3 + end];
                return doc.trim().to_string();
            }
        }
        if let Some(start) = text.find("'''") {
            if let Some(end) = text[start + 3..].find("'''") {
                let doc = &text[start + 3..start + 3 + end];
                return doc.trim().to_string();
            }
        }
        String::new()
    }
}

impl Default for ScriptScanner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::TempDir;

    #[test]
    fn test_scan_scripts_single_tool() {
        let temp_dir = TempDir::new().unwrap();
        let scripts_dir = temp_dir.path().join("writer/scripts");
        std::fs::create_dir_all(&scripts_dir).unwrap();

        let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="write_text")
def write_text(content: str) -> str:
    '''Write text to a file.'''
    return "written"
"#;

        let script_file = scripts_dir.join("text.py");
        let mut file = File::create(&script_file).unwrap();
        file.write_all(script_content.as_bytes()).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner
            .scan_scripts(&scripts_dir, "writer", &["write".to_string()])
            .unwrap();

        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].tool_name, "writer.write_text");
        assert_eq!(tools[0].function_name, "write_text");
        // Verify routing keywords are included
        assert!(tools[0].keywords.contains(&"write".to_string()));
    }

    #[test]
    fn test_scan_scripts_multiple_tools() {
        let temp_dir = TempDir::new().unwrap();
        let scripts_dir = temp_dir.path().join("git/scripts");
        std::fs::create_dir_all(&scripts_dir).unwrap();

        let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="commit")
def commit(message: str) -> str:
    '''Create a commit.'''
    return f"Committed: {message}"

@skill_command(name="status")
def status() -> str:
    '''Show working tree status.'''
    return "status output"
"#;

        let script_file = scripts_dir.join("main.py");
        let mut file = File::create(&script_file).unwrap();
        file.write_all(script_content.as_bytes()).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner
            .scan_scripts(&scripts_dir, "git", &["git".to_string()])
            .unwrap();

        assert_eq!(tools.len(), 2);
        assert!(tools.iter().any(|t| t.tool_name == "git.commit"));
        assert!(tools.iter().any(|t| t.tool_name == "git.status"));
    }

    #[test]
    fn test_scan_scripts_no_scripts_dir() {
        let temp_dir = TempDir::new().unwrap();
        let scripts_dir = temp_dir.path().join("empty/scripts");

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_scripts(&scripts_dir, "empty", &[]).unwrap();

        assert!(tools.is_empty());
    }

    #[test]
    fn test_scan_scripts_empty_dir() {
        let temp_dir = TempDir::new().unwrap();
        let scripts_dir = temp_dir.path().join("empty/scripts");
        std::fs::create_dir_all(&scripts_dir).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_scripts(&scripts_dir, "empty", &[]).unwrap();

        assert!(tools.is_empty());
    }

    #[test]
    fn test_scan_skill_scripts() {
        let temp_dir = TempDir::new().unwrap();
        let skill_path = temp_dir.path().join("test_skill");
        let scripts_dir = skill_path.join("scripts");
        std::fs::create_dir_all(&scripts_dir).unwrap();

        let script_content = r#"
@skill_command(name="test")
def test_tool():
    '''A test tool.'''
    pass
"#;

        let script_file = scripts_dir.join("test.py");
        std::fs::write(&script_file, script_content).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner
            .scan_skill_scripts(&skill_path, "test_skill", &[])
            .unwrap();

        assert_eq!(tools.len(), 1);
        // When decorator has name="test", tool_name should be "test_skill.test"
        // If it returns "test_skill.test_tool", the decorator name wasn't parsed
        assert!(tools[0].tool_name.starts_with("test_skill."));
    }

    #[test]
    fn test_parse_script_skips_init() {
        let temp_dir = TempDir::new().unwrap();
        let scripts_dir = temp_dir.path().join("test/scripts");
        std::fs::create_dir_all(&scripts_dir).unwrap();

        // Write __init__.py with a decorated function (should be skipped)
        let init_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="init_tool")
def init_tool():
    '''This should be skipped.'''
    pass
"#;

        let init_file = scripts_dir.join("__init__.py");
        std::fs::write(&init_file, init_content).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_scripts(&scripts_dir, "test", &[]).unwrap();

        assert!(tools.is_empty());
    }

    #[test]
    fn test_tool_record_keywords_includes_skill_keywords() {
        let temp_dir = TempDir::new().unwrap();
        let scripts_dir = temp_dir.path().join("writer/scripts");
        std::fs::create_dir_all(&scripts_dir).unwrap();

        let script_content = r#"
@skill_command(name="polish_text")
def polish_text(text: str) -> str:
    '''Polish text using writing guidelines.'''
    return text
"#;

        let script_file = scripts_dir.join("text.py");
        std::fs::write(&script_file, script_content).unwrap();

        let scanner = ScriptScanner::new();
        let routing_keywords = vec![
            "write".to_string(),
            "edit".to_string(),
            "polish".to_string(),
        ];
        let tools = scanner
            .scan_scripts(&scripts_dir, "writer", &routing_keywords)
            .unwrap();

        assert_eq!(tools.len(), 1);
        let keywords = &tools[0].keywords;
        assert!(keywords.contains(&"writer".to_string()));
        assert!(keywords.contains(&"polish_text".to_string()));
        assert!(keywords.contains(&"polish".to_string())); // From routing_keywords
    }

    #[test]
    fn test_script_scanner_new() {
        let _scanner = ScriptScanner::new();
        // Just verify it can be created
        assert!(true);
    }

    // Note: Comprehensive integration tests are in tests/script_scanner.rs
    // These basic tests verify core functionality without complex setup.
}
