//! Phase 62: Script Scanner for @skill_script Discovery
//!
//! Scans `scripts/*.py` files in skill directories to discover
//! tools decorated with `@skill_script`.
//!
//! Uses ast-grep for precise AST pattern matching.

use anyhow::Result;
use hex;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;
use walkdir::WalkDir;

use omni_ast::{LanguageExt, MatcherExt, Pattern, SupportLang};

/// A discovered tool from script scanning
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolRecord {
    /// Full tool name (e.g., "git.commit")
    pub tool_name: String,
    /// Human-readable description
    pub description: String,
    /// Parent skill name (e.g., "git")
    pub skill_name: String,
    /// Physical file path (e.g., "assets/skills/git/scripts/commit.py")
    pub file_path: String,
    /// Function name in the Python file
    pub function_name: String,
    /// Execution mode (e.g., "script", "library")
    pub execution_mode: String,
    /// Keywords for vector search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content (for incremental indexing)
    pub file_hash: String,
    /// JSON schema for tool parameters (filled by Python extractor)
    pub input_schema: String,
    /// Raw docstring content
    pub docstring: String,
}

/// Scanner for discovering tools in script files using ast-grep
pub struct ScriptScanner;

impl ScriptScanner {
    /// Create a new script scanner.
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    /// Scan a skill directory for script-based tools.
    pub fn scan_skill_dir(&self, skill_path: &Path) -> Result<Vec<ToolRecord>> {
        let scripts_dir = skill_path.join("scripts");
        let mut tools = Vec::new();

        if !scripts_dir.exists() {
            return Ok(tools);
        }

        let skill_name = skill_path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();

        for entry in WalkDir::new(&scripts_dir)
            .into_iter()
            .filter_map(|e| e.ok())
        {
            let path = entry.path();

            if path.is_dir() {
                continue;
            }

            if path.extension().map_or(false, |ext| ext != "py") {
                continue;
            }
            if path.file_name().map_or(false, |name| name == "__init__.py") {
                continue;
            }

            let parsed_tools = self.parse_script(path, &skill_name)?;
            tools.extend(parsed_tools);
        }

        Ok(tools)
    }

    /// Scan a base skills directory for all skills.
    pub fn scan_all(&self, base_path: &Path) -> Result<Vec<ToolRecord>> {
        let mut all_tools = Vec::new();

        if !base_path.exists() {
            return Ok(all_tools);
        }

        for entry in fs::read_dir(base_path)? {
            let entry = entry?;
            let path = entry.path();

            if path.is_dir() {
                let tools = self.scan_skill_dir(&path)?;
                all_tools.extend(tools);
            }
        }

        Ok(all_tools)
    }

    /// Parse a single script file for tool definitions.
    fn parse_script(&self, path: &Path, skill_name: &str) -> Result<Vec<ToolRecord>> {
        let content = fs::read_to_string(path)?;
        let file_path = path.to_string_lossy().to_string();
        let mut tools = Vec::new();

        // Compute SHA256 hash for incremental indexing
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        let file_hash = hex::encode(hasher.finalize());

        // Use ast-grep to find ONLY function definitions decorated with @skill_script
        let lang: SupportLang = "py".parse().expect("Python language should be supported");
        let root = lang.ast_grep(&content);
        let root_node = root.root();

        // Pattern to match @skill_script decorator
        // Note: AST sees it as skill_script(...) Call, not @skill_script(...)
        // The @ is Python syntax, the function name in AST is 'skill_script'
        let decorator_pattern = r#"skill_script($$$)"#;

        let search_decorator = Pattern::try_new(decorator_pattern, lang)
            .map_err(|e| anyhow::anyhow!("Failed to parse decorator pattern: {}", e))?;

        // Also need pattern to get function name
        // Use simple def pattern - ast-grep will match the node containing def
        let func_pattern = r#"def $NAME"#;
        let search_func = Pattern::try_new(func_pattern, lang)
            .map_err(|e| anyhow::anyhow!("Failed to parse function pattern: {}", e))?;

        // Track which functions are decorated by @skill_script
        let mut decorated_functions = std::collections::HashSet::new();

        // Find all decorator positions (byte offsets)
        let mut decorator_positions: Vec<usize> = Vec::new();
        for node in root_node.dfs() {
            if search_decorator.match_node(node.clone()).is_some() {
                // Get the byte position of the end of the decorator
                let range = node.range();
                decorator_positions.push(range.end);
            }
        }

        // Now find functions and check if they have a @skill_script decorator before them
        for node in root_node.dfs() {
            if let Some(m) = search_func.match_node(node.clone()) {
                // Get the match environment
                let env = m.get_env();

                // Get function name from $NAME meta-variable
                let func_name = env
                    .get_match("NAME")
                    .map(|n| n.text().to_string())
                    .unwrap_or_else(|| "unknown".to_string());

                // Get byte position of function definition
                let func_range = m.range();

                // Check if this function is decorated with @skill_script
                // A function is decorated if there's a @skill_script ending
                // within 500 bytes before the function (handles multi-line decorators)
                let is_decorated = decorator_positions
                    .iter()
                    .any(|&dec_pos| dec_pos < func_range.start && func_range.start - dec_pos < 500);

                if is_decorated && !decorated_functions.contains(&func_name) {
                    decorated_functions.insert(func_name.clone());

                    // For Phase 62, tool_name is the function name
                    let tool_name = func_name.clone();

                    // Generate description
                    let description = format!("Execute {}.{}", skill_name, tool_name);

                    // Extract docstring from function body
                    let matched_text = m.text().to_string();
                    let docstring = self.extract_docstring_from_text(&matched_text);

                    tools.push(ToolRecord {
                        tool_name: format!("{}.{}", skill_name, tool_name),
                        description,
                        skill_name: skill_name.to_string(),
                        file_path: file_path.clone(),
                        function_name: func_name,
                        execution_mode: "script".to_string(),
                        keywords: vec![skill_name.to_string(), tool_name.clone()],
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
        // Look for docstring patterns in the function definition text
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
    fn test_ast_grep_pattern() {
        // Test if pattern matching works
        let lang: SupportLang = "py".parse().expect("Python");
        let content = r#"
@skill_script(name="test")
def hello():
    pass
"#;
        let root = lang.ast_grep(content);
        let root_node = root.root();

        // Try a pattern that should match
        let pattern = r#"@skill_script($A)"#;
        let search_pattern = Pattern::try_new(pattern, lang).expect("Pattern should parse");

        let mut matches = 0;
        for node in root_node.dfs() {
            if search_pattern.match_node(node.clone()).is_some() {
                matches += 1;
            }
        }
        // Should find at least one match
        assert!(matches >= 1, "Expected at least 1 match, got {}", matches);
    }

    #[test]
    fn test_scan_skill_dir() {
        let temp_dir = TempDir::new().unwrap();
        let skill_dir = temp_dir.path().join("test_skill");
        let scripts_dir = skill_dir.join("scripts");
        fs::create_dir_all(&scripts_dir).unwrap();

        // Use single-line format for decorators
        let script_content = r#"
from agent.skills.decorators import skill_script

@skill_script(name="hello", description="Say hello to the world")
def hello(name: str) -> str:
    '''Greet someone by name.'''
    return f"Hello, {name}!"

@skill_script(description="An example function")
def example() -> str:
    '''This is an example.'''
    return "example"
"#;
        let script_file = scripts_dir.join("greetings.py");
        let mut file = File::create(&script_file).unwrap();
        file.write_all(script_content.as_bytes()).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_skill_dir(&skill_dir).unwrap();

        assert_eq!(tools.len(), 2);

        let hello_tool = &tools[0];
        assert_eq!(hello_tool.tool_name, "test_skill.hello");
        assert_eq!(hello_tool.description, "Execute test_skill.hello");
        assert_eq!(hello_tool.function_name, "hello");

        let example_tool = &tools[1];
        assert_eq!(example_tool.tool_name, "test_skill.example");
        assert!(example_tool.description.contains("example"));
    }

    #[test]
    fn test_multiline_decorator() {
        // Test that multi-line decorators are handled correctly
        let temp_dir = TempDir::new().unwrap();
        let skill_dir = temp_dir.path().join("test_skill");
        let scripts_dir = skill_dir.join("scripts");
        fs::create_dir_all(&scripts_dir).unwrap();

        // Script with multi-line decorator (like crawl4ai)
        let script_content = r#"
@skill_script(
    name="crawl_url",
    description="Crawl a web page"
)
async def crawl_url(url: str) -> dict:
    '''Crawl a webpage.'''
    pass
"#;
        let script_file = scripts_dir.join("test.py");
        let mut file = File::create(&script_file).unwrap();
        file.write_all(script_content.as_bytes()).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_skill_dir(&skill_dir).unwrap();

        // Should find crawl_url with multi-line decorator
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].tool_name, "test_skill.crawl_url");
        assert_eq!(tools[0].function_name, "crawl_url");
    }

    #[test]
    fn test_skips_internal_functions() {
        // Test that internal decorator functions are not picked up
        let temp_dir = TempDir::new().unwrap();
        let skill_dir = temp_dir.path().join("test_skill");
        let scripts_dir = skill_dir.join("scripts");
        fs::create_dir_all(&scripts_dir).unwrap();

        // Script with internal decorator functions (like in utils.py)
        let script_content = r#"
def skill_script(**kwargs):
    """Internal decorator factory."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

@skill_script(name="real_tool", description="A real tool")
def real_tool():
    '''This is a real tool.'''
    pass
"#;
        let script_file = scripts_dir.join("test.py");
        let mut file = File::create(&script_file).unwrap();
        file.write_all(script_content.as_bytes()).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_skill_dir(&skill_dir).unwrap();

        // Should only find real_tool, not decorator or wrapper
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].tool_name, "test_skill.real_tool");
    }

    #[test]
    fn test_no_scripts_dir() {
        let temp_dir = TempDir::new().unwrap();
        let skill_dir = temp_dir.path().join("empty_skill");
        fs::create_dir_all(&skill_dir).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_skill_dir(&skill_dir).unwrap();
        assert!(tools.is_empty());
    }

    #[test]
    fn test_skips_init_py() {
        let temp_dir = TempDir::new().unwrap();
        let skill_dir = temp_dir.path().join("test_skill");
        let scripts_dir = skill_dir.join("scripts");
        fs::create_dir_all(&scripts_dir).unwrap();

        let init_content = "# Init file";
        let init_file = scripts_dir.join("__init__.py");
        let mut file = File::create(&init_file).unwrap();
        file.write_all(init_content.as_bytes()).unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_skill_dir(&skill_dir).unwrap();
        assert!(tools.is_empty());
    }

    #[test]
    fn test_scan_all() {
        let temp_dir = TempDir::new().unwrap();
        let skills_dir = temp_dir.path().join("skills");
        fs::create_dir_all(&skills_dir).unwrap();

        let skill1 = skills_dir.join("git");
        let scripts1 = skill1.join("scripts");
        fs::create_dir_all(&scripts1).unwrap();
        let script1 = scripts1.join("commit.py");
        fs::write(
            &script1,
            r#"@skill_script(name="commit")
def commit():
    pass
"#,
        )
        .unwrap();

        let skill2 = skills_dir.join("file");
        let scripts2 = skill2.join("scripts");
        fs::create_dir_all(&scripts2).unwrap();
        let script2 = scripts2.join("read.py");
        fs::write(
            &script2,
            r#"@skill_script(name="read")
def read():
    pass
"#,
        )
        .unwrap();

        let scanner = ScriptScanner::new();
        let tools = scanner.scan_all(&skills_dir).unwrap();

        assert_eq!(tools.len(), 2);
        assert!(tools.iter().any(|t| t.tool_name == "git.commit"));
        assert!(tools.iter().any(|t| t.tool_name == "file.read"));
    }
}
