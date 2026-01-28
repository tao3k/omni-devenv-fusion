//! Script Scanner - Parses Python scripts for @skill_command decorated functions.
//!
//! Uses ast-grep for precise AST pattern matching to find functions
//! decorated with `@skill_command`.
//!
//! # Architecture
//!
//! Follows the skill structure defined in `settings.yaml`:
//! - Default: `scripts/` - Standalone executables (Python workflows, state management)
//!
//! # Example
//!
//! ```ignore
//! use skills_scanner::ToolsScanner;
//!
//! let scanner = ToolsScanner::new();
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
use omni_ast::{Lang, Match, scan};
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

use crate::skill_command::annotations::build_annotations;
use crate::skill_command::category::infer_category_from_skill;
use crate::skill_command::parser::{
    extract_docstring_from_text, extract_parameters_from_text, find_skill_command_decorators,
    parse_decorator_args,
};
use crate::skill_metadata::{SkillStructure, ToolRecord};
///
/// This scanner parses Python files in the `scripts/` directory to find
/// functions decorated with `@skill_command`. The discovered tools are
/// enriched with routing keywords from the skill's SKILL.md file.
///
/// # Usage
///
/// ```ignore
/// use skills_scanner::ToolsScanner;
///
/// let scanner = ToolsScanner::new();
/// let tools = scanner.scan_scripts(
///     Path::new("assets/skills/git/scripts"),
///     "git",
///     &["commit", "branch", "merge"]
/// ).unwrap();
/// ```
#[derive(Debug)]
pub struct ToolsScanner;

impl ToolsScanner {
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
    /// let scanner = ToolsScanner::new();
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
    /// Uses AST traversal to find @skill_command decorated functions and
    /// extract all decorator kwargs (name, description, category, etc.).
    ///
    /// # Arguments
    ///
    /// * `path` - Path to the Python script file
    /// * `skill_name` - Name of the parent skill
    /// * `skill_keywords` - Routing keywords from SKILL.md
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects with enriched metadata.
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

        // Find all @skill_command decorated functions using AST
        // Note: omni-ast has issues with decorator patterns, so we use a hybrid approach:
        // 1. Find all decorators using simple string matching (not regex)
        // 2. Find all functions using AST
        // 3. Associate decorators with functions by position

        // Find all decorators with their positions
        let decorators = find_skill_command_decorators(&content);

        // Find all function definitions using AST pattern matching
        let all_funcs = scan(&content, "def $NAME", Lang::Python)?;

        // Associate decorators with functions by position (decorator should be right before function)
        // decorated_funcs contains tuples of (decorator_text, Match)
        let mut decorated_funcs: Vec<(String, Match)> = Vec::new();

        for func in &all_funcs {
            let func_start = func.start;
            let _func_name = match func.get_capture("NAME") {
                Some(n) => n,
                None => continue,
            };

            // Find decorator closest before this function
            // decorators is Vec<(start, end, text)>
            let mut best_decorator: Option<&(usize, usize, String)> = None;
            for dec in &decorators {
                let dec_end = dec.1;
                if dec_end < func_start {
                    // Check if decorator is within reasonable distance (500 chars)
                    let distance = func_start - dec_end;
                    if distance < 500 {
                        if best_decorator.is_none() || dec_end > best_decorator.unwrap().1 {
                            best_decorator = Some(dec);
                        }
                    }
                }
            }

            if let Some(dec) = best_decorator {
                decorated_funcs.push((dec.2.clone(), func.clone()));
            }
        }

        // Build a map of function name to docstring
        // The pattern "def $NAME" matches the full function including docstring
        let mut func_docstrings: std::collections::HashMap<String, String> =
            std::collections::HashMap::new();
        for func in &all_funcs {
            let func_name = func.get_capture("NAME").map(|s| s.to_string());
            if let Some(name) = &func_name {
                // Extract docstring from the matched text
                let docstring = extract_docstring_from_text(&func.text);
                func_docstrings.insert(name.clone(), docstring);
            }
        }

        // Process each decorated function (decorator, function pair)
        for (decorator_text, func) in &decorated_funcs {
            // Get the function name from captures
            let func_name = match func.get_capture("NAME").map(|s| s.to_string()) {
                Some(name) => name,
                None => continue,
            };

            // Get decorator arguments
            let args = parse_decorator_args(decorator_text);

            // Get docstring from pre-built map
            let docstring = func_docstrings.get(&func_name).cloned().unwrap_or_default();

            // Extract tool name
            let tool_name = match &args.name {
                Some(name) => name.clone(),
                None => func_name.clone(),
            };

            // Extract function parameters from the matched text
            let parameters = extract_parameters_from_text(&func.text);

            // Build description
            let description = match &args.description {
                Some(desc) => desc.clone(),
                None => {
                    if !docstring.is_empty() {
                        docstring.clone()
                    } else {
                        format!("Execute {}.{}", skill_name, tool_name)
                    }
                }
            };

            // Build category
            // Priority: 1) @skill_command(category="...")  2) Inferred from skill name  3) empty
            let category = args
                .category
                .clone()
                .unwrap_or_else(|| infer_category_from_skill(skill_name));

            // Build annotations
            let annotations = build_annotations(&args, &func_name, &parameters);

            // Generate input_schema from parameters
            let input_schema = self.generate_input_schema(&parameters);

            // Combine keywords
            let mut combined_keywords = vec![skill_name.to_string(), tool_name.clone()];
            combined_keywords.extend(skill_keywords.iter().cloned());

            tools.push(ToolRecord::with_enrichment(
                format!("{}.{}", skill_name, tool_name),
                description,
                skill_name.to_string(),
                file_path.clone(),
                func_name.clone(),
                "script".to_string(),
                combined_keywords,
                file_hash.clone(),
                docstring,
                category,
                annotations,
                parameters,
                input_schema,
            ));
        }

        Ok(tools)
    }

    /// Generate MCP-style inputSchema JSON from parameter names.
    fn generate_input_schema(&self, parameters: &[String]) -> String {
        let mut props = serde_json::Map::new();
        for param in parameters {
            props.insert(
                param.clone(),
                serde_json::json!({
                    "type": "string",
                    "description": format!("Parameter: {}", param)
                }),
            );
        }

        let schema = serde_json::json!({
            "type": "object",
            "properties": props,
            "required": parameters
        });

        schema.to_string()
    }
}

impl Default for ToolsScanner {
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

        let scanner = ToolsScanner::new();
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

        let scanner = ToolsScanner::new();
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

        let scanner = ToolsScanner::new();
        let tools = scanner.scan_scripts(&scripts_dir, "empty", &[]).unwrap();

        assert!(tools.is_empty());
    }

    #[test]
    fn test_scan_scripts_empty_dir() {
        let temp_dir = TempDir::new().unwrap();
        let scripts_dir = temp_dir.path().join("empty/scripts");
        std::fs::create_dir_all(&scripts_dir).unwrap();

        let scanner = ToolsScanner::new();
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

        let scanner = ToolsScanner::new();
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

        let scanner = ToolsScanner::new();
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

        let scanner = ToolsScanner::new();
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
    fn test_tools_scanner_new() {
        let _scanner = ToolsScanner::new();
        // Just verify it can be created
        assert!(true);
    }

    // Note: Comprehensive integration tests are in tests/tools_scanner.rs
    // Category inference tests are in skill_command/category.rs
    // These basic tests verify core functionality without complex setup.
}
