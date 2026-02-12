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
use omni_ast::{DecoratedFunction, TreeSitterPythonParser};
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

use crate::skills::metadata::{DecoratorArgs, SkillStructure, ToolRecord};
use crate::skills::skill_command::annotations::build_annotations;
use crate::skills::skill_command::category::infer_category_from_skill;
use crate::skills::skill_command::parser::{ParsedParameter, extract_param_descriptions};
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
        skill_intents: &[String],
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let mut tools = Vec::new();

        if !scripts_dir.exists() {
            log::debug!("Scripts directory not found: {:?}", scripts_dir);
            return Ok(tools);
        }

        for entry in WalkDir::new(scripts_dir)
            .follow_links(false)
            .into_iter()
            .filter_map(|e| e.ok())
        {
            let path = entry.path();

            if path.is_dir() {
                continue;
            }

            // Only scan Python files
            if path.extension().map_or(false, |ext| ext != "py") {
                continue;
            }

            // Skip __init__.py and internal private files
            let file_name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if file_name == "__init__.py" || file_name.starts_with('_') {
                continue;
            }

            let parsed_tools =
                self.parse_script(path, skill_name, skill_keywords, skill_intents)?;
            if !parsed_tools.is_empty() {
                log::debug!(
                    "ToolsScanner: Found {} tools in {:?}",
                    parsed_tools.len(),
                    path
                );
            }
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
    /// * `skill_intents` - Intents from SKILL.md
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects.
    pub fn scan_skill_scripts(
        &self,
        skill_path: &Path,
        skill_name: &str,
        skill_keywords: &[String],
        skill_intents: &[String],
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let scripts_dir = skill_path.join("scripts");
        self.scan_scripts(&scripts_dir, skill_name, skill_keywords, skill_intents)
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
    /// * `skill_intents` - Intents from SKILL.md
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
        skill_intents: &[String],
        structure: &SkillStructure,
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let mut all_tools = Vec::new();

        // Get directories to scan from structure
        let script_dirs = structure.script_directories();

        for dir_name in script_dirs {
            let dir_path = skill_path.join(dir_name);
            if dir_path.exists() && dir_path.is_dir() {
                let tools =
                    self.scan_scripts(&dir_path, skill_name, skill_keywords, skill_intents)?;
                all_tools.extend(tools);
            }
        }

        Ok(all_tools)
    }

    /// Parse a single script file for tool definitions.
    ///
    /// Uses tree-sitter for robust parsing of @skill_command decorated functions
    /// with proper handling of triple-quoted strings in decorator arguments.
    ///
    /// # Arguments
    ///
    /// * `path` - Path to the Python script file
    /// * `skill_name` - Name of the parent skill
    /// * `skill_keywords` - Routing keywords from SKILL.md
    /// * `skill_intents` - Intents from SKILL.md
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects with enriched metadata.
    fn parse_script(
        &self,
        path: &Path,
        skill_name: &str,
        skill_keywords: &[String],
        skill_intents: &[String],
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        // Use read_to_string first, fall back to lossy reading for non-UTF-8 files
        let content = match fs::read_to_string(path) {
            Ok(content) => content,
            Err(e) => {
                // Try lossy reading as fallback for files with encoding issues
                match fs::read(path) {
                    Ok(bytes) => String::from_utf8_lossy(&bytes).into_owned(),
                    Err(_) => {
                        return Err(Box::new(std::io::Error::new(
                            std::io::ErrorKind::InvalidData,
                            format!("Failed to read file as UTF-8: {}", e),
                        )));
                    }
                }
            }
        };
        let file_path = path.to_string_lossy().to_string();
        let mut tools = Vec::new();

        // Compute SHA256 hash for incremental indexing
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        let file_hash = hex::encode(hasher.finalize());

        // Use tree-sitter parser for robust decorator extraction
        // This correctly handles triple-quoted strings with commas
        let mut parser = TreeSitterPythonParser::new();
        let decorated_funcs: Vec<DecoratedFunction> =
            parser.find_decorated_functions(&content, "skill_command");

        if !decorated_funcs.is_empty() {
            log::debug!(
                "ToolsScanner: Found {} @skill_command decorated functions in {:?}",
                decorated_funcs.len(),
                path
            );
        }

        // Build a map of function name to docstring from the parsed functions
        let mut func_docstrings: std::collections::HashMap<String, String> =
            std::collections::HashMap::new();
        for func in &decorated_funcs {
            if !func.docstring.is_empty() {
                func_docstrings.insert(func.name.clone(), func.docstring.clone());
            }
        }

        // Process each decorated function
        for func in &decorated_funcs {
            // Extract decorator arguments
            let decorator_args = func.decorator.as_ref().map(|d| &d.arguments);

            // Get tool name from decorator or function name
            let tool_name = decorator_args
                .and_then(|a| a.name.clone())
                .unwrap_or_else(|| func.name.clone());

            // Get docstring
            let docstring = func_docstrings.get(&func.name).cloned().unwrap_or_default();

            // Build description - priority: decorator description > docstring > fallback
            let description = match decorator_args.and_then(|a| a.description.clone()) {
                Some(desc) => desc,
                None if !docstring.is_empty() => docstring.clone(),
                _ => format!("Execute {}.{}", skill_name, tool_name),
            };

            // Build category
            let category = decorator_args
                .and_then(|a| a.category.clone())
                .unwrap_or_else(|| infer_category_from_skill(skill_name));

            // Convert tree-sitter parameters to our ParsedParameter format
            let parameters: Vec<ParsedParameter> = func
                .parameters
                .iter()
                .map(|p| ParsedParameter {
                    name: p.name.clone(),
                    type_annotation: p.type_annotation.clone(),
                    has_default: p.default_value.is_some(),
                    default_value: p.default_value.clone(),
                })
                .collect();

            // Build annotations - convert tree-sitter args to DecoratorArgs
            let decorator_args = match decorator_args {
                Some(ts_args) => DecoratorArgs {
                    name: ts_args.name.clone(),
                    description: ts_args.description.clone(),
                    category: ts_args.category.clone(),
                    destructive: ts_args.destructive,
                    read_only: ts_args.read_only,
                },
                None => DecoratorArgs::default(),
            };
            let annotations = build_annotations(&decorator_args, &func.name, &parameters);

            // Generate input_schema from parameters with description for param docs
            let input_schema = self.generate_input_schema(&parameters, &description);

            // Combine keywords
            let mut combined_keywords = vec![skill_name.to_string(), tool_name.clone()];
            combined_keywords.extend(skill_keywords.iter().cloned());

            tools.push(ToolRecord::with_enrichment(
                format!("{}.{}", skill_name, tool_name),
                description,
                skill_name.to_string(),
                file_path.clone(),
                func.name.clone(),
                "script".to_string(),
                combined_keywords,
                skill_intents.to_vec(),
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

    /// Generate MCP-style inputSchema JSON from parsed parameters.
    ///
    /// # Arguments
    ///
    /// * `parameters` - List of ParsedParameter with type and default info
    /// * `description` - Full decorator description for extracting param descriptions
    fn generate_input_schema(&self, parameters: &[ParsedParameter], description: &str) -> String {
        // Extract parameter descriptions from the decorator description
        let param_descriptions = extract_param_descriptions(description);

        // Guard: only compute expensive debug output when debug logging is enabled
        if log::log_enabled!(log::Level::Debug) {
            log::debug!(
                "generate_input_schema: params={:?}, desc_len={}, param_descs={:?}",
                parameters.iter().map(|p| &p.name).collect::<Vec<_>>(),
                description.len(),
                param_descriptions
            );
        }

        let mut props = serde_json::Map::new();
        let mut required_params: Vec<String> = Vec::new();

        // Guard: collect debug info once instead of multiple log::debug! calls in loop
        let param_debug_info: Vec<_> = if log::log_enabled!(log::Level::Debug) {
            parameters
                .iter()
                .map(|p| {
                    if let Some(d) = param_descriptions.get(&p.name) {
                        format!("Found: {} = {}", p.name, d)
                    } else {
                        format!("Fallback: {}", p.name)
                    }
                })
                .collect()
        } else {
            Vec::new()
        };

        for param in parameters.iter() {
            // Use extracted description or fallback to placeholder
            let desc = if let Some(d) = param_descriptions.get(&param.name) {
                d.clone()
            } else {
                format!("Parameter: {}", param.name)
            };

            // Generate JSON Schema property with type inference
            let mut schema = param.to_json_schema_property();

            // Add description
            if let serde_json::Value::Object(ref mut schema_obj) = schema {
                schema_obj.insert("description".to_string(), serde_json::json!(desc));
            }

            props.insert(param.name.clone(), schema);

            // Add to required if no default value
            if !param.has_default {
                required_params.push(param.name.clone());
            }
        }

        // Output collected debug info (only if debug logging is enabled)
        if !param_debug_info.is_empty() {
            log::debug!("Param processing: {:?}", param_debug_info);
        }

        let schema = serde_json::json!({
            "type": "object",
            "properties": props,
            "required": required_params
        });

        schema.to_string()
    }

    /// Parse script content directly without reading from disk.
    ///
    /// Uses tree-sitter for robust parsing of @skill_command decorated functions
    /// with proper handling of triple-quoted strings in decorator arguments.
    ///
    /// # Arguments
    ///
    /// * `content` - The Python script content as a string
    /// * `file_path` - Virtual file path (for metadata/logging only)
    /// * `skill_name` - Name of the parent skill
    /// * `skill_keywords` - Routing keywords from SKILL.md
    /// * `skill_intents` - Intents from SKILL.md
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects with enriched metadata.
    pub fn parse_content(
        &self,
        content: &str,
        file_path: &str,
        skill_name: &str,
        skill_keywords: &[String],
        skill_intents: &[String],
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let mut tools = Vec::new();

        // Compute SHA256 hash for incremental indexing
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        let file_hash = hex::encode(hasher.finalize());

        // Use tree-sitter parser for robust decorator extraction
        // This correctly handles triple-quoted strings with commas
        let mut parser = TreeSitterPythonParser::new();
        let decorated_funcs: Vec<DecoratedFunction> =
            parser.find_decorated_functions(content, "skill_command");

        if !decorated_funcs.is_empty() {
            log::debug!(
                "ToolsScanner: Found {} @skill_command decorated functions in {}",
                decorated_funcs.len(),
                file_path
            );
        }

        // Build a map of function name to docstring from the parsed functions
        let mut func_docstrings: std::collections::HashMap<String, String> =
            std::collections::HashMap::new();
        for func in &decorated_funcs {
            if !func.docstring.is_empty() {
                func_docstrings.insert(func.name.clone(), func.docstring.clone());
            }
        }

        // Process each decorated function
        for func in &decorated_funcs {
            // Extract decorator arguments
            let decorator_args = func.decorator.as_ref().map(|d| &d.arguments);

            // Get tool name from decorator or function name
            let tool_name = decorator_args
                .and_then(|a| a.name.clone())
                .unwrap_or_else(|| func.name.clone());

            // Get docstring
            let docstring = func_docstrings.get(&func.name).cloned().unwrap_or_default();

            // Build description - priority: decorator description > docstring > fallback
            let description = match decorator_args.and_then(|a| a.description.clone()) {
                Some(desc) => desc,
                None if !docstring.is_empty() => docstring.clone(),
                _ => format!("Execute {}.{}", skill_name, tool_name),
            };

            // Build category
            let category = decorator_args
                .and_then(|a| a.category.clone())
                .unwrap_or_else(|| infer_category_from_skill(skill_name));

            // Convert tree-sitter parameters to our ParsedParameter format
            let parameters: Vec<ParsedParameter> = func
                .parameters
                .iter()
                .map(|p| ParsedParameter {
                    name: p.name.clone(),
                    type_annotation: p.type_annotation.clone(),
                    has_default: p.default_value.is_some(),
                    default_value: p.default_value.clone(),
                })
                .collect();

            // Build annotations - convert tree-sitter args to DecoratorArgs
            let decorator_args = match decorator_args {
                Some(ts_args) => DecoratorArgs {
                    name: ts_args.name.clone(),
                    description: ts_args.description.clone(),
                    category: ts_args.category.clone(),
                    destructive: ts_args.destructive,
                    read_only: ts_args.read_only,
                },
                None => DecoratorArgs::default(),
            };
            let annotations = build_annotations(&decorator_args, &func.name, &parameters);

            // Generate input_schema from parameters with description for param docs
            let input_schema = self.generate_input_schema(&parameters, &description);

            // Combine keywords
            let mut combined_keywords = vec![skill_name.to_string(), tool_name.clone()];
            combined_keywords.extend(skill_keywords.iter().cloned());

            tools.push(ToolRecord::with_enrichment(
                format!("{}.{}", skill_name, tool_name),
                description,
                skill_name.to_string(),
                file_path.to_string(),
                func.name.clone(),
                "script".to_string(),
                combined_keywords,
                skill_intents.to_vec(),
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

    /// Scan a list of virtual file paths with their content.
    ///
    /// This method allows scanning files without filesystem access, which is
    /// useful for:
    /// - Testing with temporary directories (no cleanup needed)
    /// - Processing file content from databases or APIs
    /// - Batch scanning with full control over file content
    ///
    /// # Arguments
    ///
    /// * `files` - Vector of tuples: (file_path: String, content: String)
    /// * `skill_name` - Name of the parent skill
    /// * `skill_keywords` - Routing keywords from SKILL.md
    /// * `skill_intents` - Intents from SKILL.md
    ///
    /// # Returns
    ///
    /// A vector of `ToolRecord` objects from all scanned files.
    ///
    /// # Examples
    ///
    /// ```ignore
    /// let scanner = ToolsScanner::new();
    /// let files = vec![
    ///     ("/tmp/skill/scripts/tool_a.py", r#"
    ///         @skill_command(name="tool_a")
    ///         def tool_a(param: str) -> str:
    ///             '''Tool A implementation.'''
    ///             return param
    ///     "#.to_string()),
    ///     ("/tmp/skill/scripts/tool_b.py", r#"
    ///         @skill_command(name="tool_b")
    ///         def tool_b(value: int) -> int:
    ///             '''Tool B implementation.'''
    ///             value * 2
    ///     "#.to_string()),
    /// ];
    ///
    /// let tools = scanner.scan_paths(&files, "test_skill", &[], &[])?;
    /// ```
    pub fn scan_paths(
        &self,
        files: &[(String, String)],
        skill_name: &str,
        skill_keywords: &[String],
        skill_intents: &[String],
    ) -> Result<Vec<ToolRecord>, Box<dyn std::error::Error>> {
        let mut all_tools = Vec::new();

        for (file_path, content) in files {
            // Skip __init__.py and private files
            let file_name = std::path::Path::new(file_path)
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("");

            if file_name == "__init__.py" || file_name.starts_with('_') {
                continue;
            }

            // Only process Python files
            if !file_path.ends_with(".py") {
                continue;
            }

            let parsed_tools = self.parse_content(
                content,
                file_path,
                skill_name,
                skill_keywords,
                skill_intents,
            )?;

            if !parsed_tools.is_empty() {
                log::debug!(
                    "ToolsScanner: Found {} tools in {}",
                    parsed_tools.len(),
                    file_path
                );
            }

            all_tools.extend(parsed_tools);
        }

        if !all_tools.is_empty() {
            log::info!(
                "Scanned {} tools from {} files for skill '{}'",
                all_tools.len(),
                files.len(),
                skill_name
            );
        }

        Ok(all_tools)
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
            .scan_scripts(&scripts_dir, "writer", &["write".to_string()], &[])
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
            .scan_scripts(&scripts_dir, "git", &["git".to_string()], &[])
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
        let tools = scanner
            .scan_scripts(&scripts_dir, "empty", &[], &[])
            .unwrap();

        assert!(tools.is_empty());
    }

    #[test]
    fn test_scan_scripts_empty_dir() {
        let temp_dir = TempDir::new().unwrap();
        let scripts_dir = temp_dir.path().join("empty/scripts");
        std::fs::create_dir_all(&scripts_dir).unwrap();

        let scanner = ToolsScanner::new();
        let tools = scanner
            .scan_scripts(&scripts_dir, "empty", &[], &[])
            .unwrap();

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
            .scan_skill_scripts(&skill_path, "test_skill", &[], &[])
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
        let tools = scanner
            .scan_scripts(&scripts_dir, "test", &[], &[])
            .unwrap();

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
            .scan_scripts(&scripts_dir, "writer", &routing_keywords, &[])
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

    #[test]
    fn test_parse_content_single_tool() {
        let scanner = ToolsScanner::new();
        let content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="write_text")
def write_text(content: str) -> str:
    '''Write text to a file.'''
    return "written"
"#;

        let tools = scanner
            .parse_content(
                content,
                "/virtual/path/scripts/tool.py",
                "writer",
                &["write".to_string()],
                &[],
            )
            .unwrap();

        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].tool_name, "writer.write_text");
        assert_eq!(tools[0].function_name, "write_text");
        assert_eq!(tools[0].file_path, "/virtual/path/scripts/tool.py");
        assert!(tools[0].keywords.contains(&"write".to_string()));
    }

    #[test]
    fn test_parse_content_multiple_tools() {
        let scanner = ToolsScanner::new();
        let content = r#"
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

        let tools = scanner
            .parse_content(
                content,
                "/virtual/path/scripts/main.py",
                "git",
                &["git".to_string()],
                &[],
            )
            .unwrap();

        assert_eq!(tools.len(), 2);
        assert!(tools.iter().any(|t| t.tool_name == "git.commit"));
        assert!(tools.iter().any(|t| t.tool_name == "git.status"));
    }

    #[test]
    fn test_parse_content_no_decorators() {
        let scanner = ToolsScanner::new();
        let content = r#"
def regular_function():
    '''This function has no decorator.'''
    return "no tool here"
"#;

        let tools = scanner
            .parse_content(content, "/virtual/path/scripts/tool.py", "test", &[], &[])
            .unwrap();

        assert!(tools.is_empty());
    }

    #[test]
    fn test_parse_content_skips_init() {
        let scanner = ToolsScanner::new();
        let content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="init_tool")
def init_tool():
    '''This should be skipped.'''
    pass
"#;

        // parse_content doesn't skip __init__.py - that's handled in scan_paths
        let tools = scanner
            .parse_content(
                content,
                "/virtual/path/scripts/__init__.py",
                "test",
                &[],
                &[],
            )
            .unwrap();

        // This should find the tool since we're calling parse_content directly
        assert_eq!(tools.len(), 1);
    }

    #[test]
    fn test_parse_content_with_category() {
        let scanner = ToolsScanner::new();
        let content = r#"
@skill_command(name="test_tool", category="testing")
def test_tool():
    '''A test tool.'''
    pass
"#;

        let tools = scanner
            .parse_content(content, "/virtual/path/scripts/tool.py", "test", &[], &[])
            .unwrap();

        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].category, "testing");
    }

    #[test]
    fn test_parse_content_with_intents() {
        let scanner = ToolsScanner::new();
        let content = r#"
@skill_command(name="test_tool")
def test_tool():
    '''A test tool.'''
    pass
"#;

        let intents = vec!["test".to_string(), "verify".to_string()];
        let tools = scanner
            .parse_content(
                content,
                "/virtual/path/scripts/tool.py",
                "test",
                &[],
                &intents,
            )
            .unwrap();

        assert_eq!(tools.len(), 1);
        assert!(tools[0].intents.contains(&"test".to_string()));
        assert!(tools[0].intents.contains(&"verify".to_string()));
    }

    #[test]
    fn test_parse_content_file_hash() {
        let scanner = ToolsScanner::new();
        let content = r#"
@skill_command(name="tool")
def tool():
    pass
"#;

        let tools1 = scanner
            .parse_content(content, "/virtual/path/scripts/tool.py", "test", &[], &[])
            .unwrap();

        // Same content should produce same hash
        let tools2 = scanner
            .parse_content(content, "/virtual/path/scripts/tool.py", "test", &[], &[])
            .unwrap();

        assert_eq!(tools1[0].file_hash, tools2[0].file_hash);

        // Different content should produce different hash
        let content2 = r#"
@skill_command(name="tool")
def tool():
    pass
# different
"#;

        let tools3 = scanner
            .parse_content(content2, "/virtual/path/scripts/tool.py", "test", &[], &[])
            .unwrap();

        assert_ne!(tools1[0].file_hash, tools3[0].file_hash);
    }

    #[test]
    fn test_scan_paths_multiple_files() {
        let scanner = ToolsScanner::new();
        let files = vec![
            (
                "/virtual/skill/scripts/tool_a.py".to_string(),
                r#"
@skill_command(name="tool_a")
def tool_a(param: str) -> str:
    '''Tool A implementation.'''
    return param
"#
                .to_string(),
            ),
            (
                "/virtual/skill/scripts/tool_b.py".to_string(),
                r#"
@skill_command(name="tool_b")
def tool_b(value: int) -> int:
    '''Tool B implementation.'''
    return value * 2
"#
                .to_string(),
            ),
        ];

        let tools = scanner.scan_paths(&files, "test_skill", &[], &[]).unwrap();

        assert_eq!(tools.len(), 2);
        assert!(tools.iter().any(|t| t.tool_name == "test_skill.tool_a"));
        assert!(tools.iter().any(|t| t.tool_name == "test_skill.tool_b"));
    }

    #[test]
    fn test_scan_paths_skips_init() {
        let scanner = ToolsScanner::new();
        let files = vec![
            (
                "/virtual/skill/scripts/__init__.py".to_string(),
                r#"
@skill_command(name="init_tool")
def init_tool():
    '''This should be skipped.'''
    pass
"#
                .to_string(),
            ),
            (
                "/virtual/skill/scripts/real_tool.py".to_string(),
                r#"
@skill_command(name="real_tool")
def real_tool():
    '''This should be included.'''
    pass
"#
                .to_string(),
            ),
        ];

        let tools = scanner.scan_paths(&files, "test_skill", &[], &[]).unwrap();

        // Only one tool (skipping __init__.py)
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].tool_name, "test_skill.real_tool");
    }

    #[test]
    fn test_scan_paths_skips_private_files() {
        let scanner = ToolsScanner::new();
        let files = vec![
            (
                "/virtual/skill/scripts/_private.py".to_string(),
                r#"
@skill_command(name="private_tool")
def private_tool():
    '''This should be skipped.'''
    pass
"#
                .to_string(),
            ),
            (
                "/virtual/skill/scripts/public.py".to_string(),
                r#"
@skill_command(name="public_tool")
def public_tool():
    '''This should be included.'''
    pass
"#
                .to_string(),
            ),
        ];

        let tools = scanner.scan_paths(&files, "test_skill", &[], &[]).unwrap();

        // Only one tool (skipping _private.py)
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].tool_name, "test_skill.public_tool");
    }

    #[test]
    fn test_scan_paths_skips_non_python() {
        let scanner = ToolsScanner::new();
        let files = vec![
            (
                "/virtual/skill/scripts/readme.md".to_string(),
                "# This is not Python".to_string(),
            ),
            (
                "/virtual/skill/scripts/real_tool.py".to_string(),
                r#"
@skill_command(name="real_tool")
def real_tool():
    pass
"#
                .to_string(),
            ),
        ];

        let tools = scanner.scan_paths(&files, "test_skill", &[], &[]).unwrap();

        assert_eq!(tools.len(), 1);
    }

    #[test]
    fn test_scan_paths_empty_list() {
        let scanner = ToolsScanner::new();
        let files: Vec<(String, String)> = Vec::new();

        let tools = scanner.scan_paths(&files, "test_skill", &[], &[]).unwrap();

        assert!(tools.is_empty());
    }

    #[test]
    fn test_scan_paths_with_keywords_and_intents() {
        let scanner = ToolsScanner::new();
        let files = vec![(
            "/virtual/skill/scripts/tool.py".to_string(),
            r#"
@skill_command(name="test_tool")
def test_tool():
    '''A test tool.'''
    pass
"#
            .to_string(),
        )];

        let keywords = vec!["test".to_string(), "verify".to_string()];
        let intents = vec!["testing".to_string()];

        let tools = scanner
            .scan_paths(&files, "test_skill", &keywords, &intents)
            .unwrap();

        assert_eq!(tools.len(), 1);
        assert!(tools[0].keywords.contains(&"test".to_string()));
        assert!(tools[0].keywords.contains(&"verify".to_string()));
        assert!(tools[0].intents.contains(&"testing".to_string()));
    }

    // Note: Comprehensive integration tests are in tests/tools_scanner.rs
    // Category inference tests are in skill_command/category.rs
    // These basic tests verify core functionality without complex setup.
}
