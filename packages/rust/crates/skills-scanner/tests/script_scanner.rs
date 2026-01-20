//! Integration tests for ScriptScanner - tests script parsing and tool discovery.
//!
//! These tests verify that ScriptScanner correctly finds @skill_command
//! decorated functions and extracts metadata.

use skills_scanner::{ScriptScanner, SkillScanner};
use std::fs;
use tempfile::TempDir;

/// Scan single script with @skill_command decorator.
#[test]
fn test_scan_scripts_single_tool() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("writer/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="write_text")
def write_text(content: str) -> str:
    '''Write text to a file.'''
    return "written"
"#;

    let script_file = scripts_dir.join("text.py");
    fs::write(&script_file, script_content).unwrap();

    let scanner = ScriptScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "writer", &["write".to_string()])
        .unwrap();

    assert_eq!(tools.len(), 1);
    assert_eq!(tools[0].tool_name, "writer.write_text");
    assert_eq!(tools[0].function_name, "write_text");
    assert_eq!(tools[0].skill_name, "writer");
}

/// Scan script with multiple tools.
#[test]
fn test_scan_scripts_multiple_tools() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("git/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

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

@skill_command(name="branch")
def branch(name: str) -> str:
    '''Create a new branch.'''
    return f"Created branch: {name}"
"#;

    let script_file = scripts_dir.join("main.py");
    fs::write(&script_file, script_content).unwrap();

    let scanner = ScriptScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "git", &["git".to_string()])
        .unwrap();

    assert_eq!(tools.len(), 3);
    assert!(tools.iter().any(|t| t.tool_name == "git.commit"));
    assert!(tools.iter().any(|t| t.tool_name == "git.status"));
    assert!(tools.iter().any(|t| t.tool_name == "git.branch"));
}

/// Scan scripts directory that doesn't exist returns empty vec.
#[test]
fn test_scan_scripts_no_scripts_dir() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("empty/scripts");

    let scanner = ScriptScanner::new();
    let tools = scanner.scan_scripts(&scripts_dir, "empty", &[]).unwrap();

    assert!(tools.is_empty());
}

/// Scan empty scripts directory returns empty vec.
#[test]
fn test_scan_scripts_empty_dir() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("empty/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let scanner = ScriptScanner::new();
    let tools = scanner.scan_scripts(&scripts_dir, "empty", &[]).unwrap();

    assert!(tools.is_empty());
}

/// Scan scripts skips __init__.py files.
#[test]
fn test_parse_script_skips_init() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Write __init__.py with a decorated function (should be skipped)
    let init_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="init_tool")
def init_tool():
    '''This should be skipped.'''
    pass
"#;

    let init_file = scripts_dir.join("__init__.py");
    fs::write(&init_file, init_content).unwrap();

    let scanner = ScriptScanner::new();
    let tools = scanner.scan_scripts(&scripts_dir, "test", &[]).unwrap();

    assert!(tools.is_empty());
}

/// Tool record includes routing keywords from skill metadata.
#[test]
fn test_tool_record_keywords_includes_skill_keywords() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("writer/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="polish_text")
def polish_text(text: str) -> str:
    '''Polish text using writing guidelines.'''
    return text
"#;

    let script_file = scripts_dir.join("text.py");
    fs::write(&script_file, script_content).unwrap();

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

    // Should include skill name
    assert!(keywords.contains(&"writer".to_string()));
    // Should include tool name
    assert!(keywords.contains(&"polish_text".to_string()));
    // Should include routing keywords from skill
    assert!(keywords.contains(&"polish".to_string()));
    assert!(keywords.contains(&"write".to_string()));
    assert!(keywords.contains(&"edit".to_string()));
}

/// Scan skill scripts via convenience method.
#[test]
fn test_scan_skill_scripts() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");
    let scripts_dir = skill_path.join("scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="test")
def test_tool():
    '''A test tool.'''
    pass
"#;

    let script_file = scripts_dir.join("test.py");
    fs::write(&script_file, script_content).unwrap();

    let scanner = ScriptScanner::new();
    let tools = scanner
        .scan_skill_scripts(&skill_path, "test_skill", &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    assert!(tools[0].tool_name.starts_with("test_skill."));
}

/// Scan with structure - single directory.
#[test]
fn test_scan_with_structure_single_directory() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("writer");
    let scripts_dir = skill_path.join("scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="write_text")
def write_text(content: str) -> str:
    '''Write text to a file.'''
    return "written"
"#;
    fs::write(&scripts_dir.join("text.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    let structure = SkillScanner::default_structure();
    let routing_keywords = vec!["write".to_string(), "edit".to_string()];

    let tools = scanner
        .scan_with_structure(&skill_path, "writer", &routing_keywords, &structure)
        .unwrap();

    assert_eq!(tools.len(), 1);
    assert_eq!(tools[0].tool_name, "writer.write_text");
}

/// Scan with structure - skips missing directories.
#[test]
fn test_scan_with_structure_skips_missing_directories() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("empty_skill");

    // No scripts/ or templates/ directories exist
    let scanner = ScriptScanner::new();
    let structure = SkillScanner::default_structure();
    let routing_keywords = vec![];

    let tools = scanner
        .scan_with_structure(&skill_path, "empty_skill", &routing_keywords, &structure)
        .unwrap();

    assert!(tools.is_empty());
}

/// Scan with structure - handles nonexistent skill path.
#[test]
fn test_scan_with_structure_nonexistent_skill_path() {
    let temp_dir = TempDir::new().unwrap();
    let nonexistent_path = temp_dir.path().join("does_not_exist");

    let scanner = ScriptScanner::new();
    let structure = SkillScanner::default_structure();
    let routing_keywords = vec![];

    let tools = scanner
        .scan_with_structure(&nonexistent_path, "ghost", &routing_keywords, &structure)
        .unwrap();

    assert!(tools.is_empty());
}

/// Scan with structure - includes routing keywords in tool record.
#[test]
fn test_scan_with_structure_includes_routing_keywords() {
    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("git");
    let scripts_dir = skill_path.join("scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="commit")
def commit(message: str) -> str:
    '''Create a commit.'''
    return f"Committed: {message}"
"#;
    fs::write(&scripts_dir.join("main.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    let structure = SkillScanner::default_structure();
    let routing_keywords = vec!["git".to_string(), "version_control".to_string()];

    let tools = scanner
        .scan_with_structure(&skill_path, "git", &routing_keywords, &structure)
        .unwrap();

    assert_eq!(tools.len(), 1);
    let keywords = &tools[0].keywords;
    assert!(keywords.contains(&"git".to_string()));
    assert!(keywords.contains(&"commit".to_string()));
    assert!(keywords.contains(&"version_control".to_string()));
}

/// Tool record contains file path and hash for incremental indexing.
#[test]
fn test_tool_record_contains_file_metadata() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="example")
def example():
    '''Example tool.'''
    pass
"#;
    let script_path = scripts_dir.join("example.py");
    fs::write(&script_path, script_content).unwrap();

    let scanner = ScriptScanner::new();
    let tools = scanner.scan_scripts(&scripts_dir, "test", &[]).unwrap();

    assert_eq!(tools.len(), 1);
    // File path should be set
    assert!(!tools[0].file_path.is_empty());
    // File hash should be set (SHA256)
    assert!(!tools[0].file_hash.is_empty());
    assert_eq!(tools[0].file_hash.len(), 64); // SHA256 hex length
}

/// Scan nested directories within scripts/.
#[test]
fn test_scan_nested_directories() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("writer/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Create nested directory
    let nested_dir = scripts_dir.join("subcommands");
    fs::create_dir_all(&nested_dir).unwrap();

    let script_content = r#"
@skill_command(name="nested_tool")
def nested_tool():
    '''Tool in nested directory.'''
    pass
"#;
    fs::write(&nested_dir.join("nested.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    let tools = scanner.scan_scripts(&scripts_dir, "writer", &[]).unwrap();

    assert_eq!(tools.len(), 1);
    assert_eq!(tools[0].tool_name, "writer.nested_tool");
}

/// Scan only .py files, skip other extensions.
#[test]
fn test_scan_only_python_files() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Create Python file with tool
    let py_content = r#"
@skill_command(name="py_tool")
def py_tool():
    pass
"#;
    fs::write(&scripts_dir.join("tool.py"), py_content).unwrap();

    // Create non-Python file (should be skipped)
    fs::write(&scripts_dir.join("notes.txt"), "Some notes").unwrap();
    fs::write(&scripts_dir.join("data.json"), "{}").unwrap();

    let scanner = ScriptScanner::new();
    let tools = scanner.scan_scripts(&scripts_dir, "test", &[]).unwrap();

    assert_eq!(tools.len(), 1);
    assert_eq!(tools[0].tool_name, "test.py_tool");
}

// ============================================================================
// Enrichment Tests - Test that tool records are properly enriched with metadata
// ============================================================================

/// Test that tool records are enriched with skill metadata keywords.
#[test]
fn test_enrich_tool_record_with_routing_keywords() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("database/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="query")
def query(sql: str) -> str:
    '''Execute a SQL query.'''
    return "results"
"#;
    fs::write(&scripts_dir.join("db.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    let routing_keywords = vec![
        "database".to_string(),
        "query".to_string(),
        "sql".to_string(),
        "postgres".to_string(),
    ];

    let tools = scanner
        .scan_scripts(&scripts_dir, "database", &routing_keywords)
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Verify enrichment: keywords should contain routing keywords
    assert!(tool.keywords.contains(&"database".to_string()));
    assert!(tool.keywords.contains(&"query".to_string()));
    assert!(tool.keywords.contains(&"sql".to_string()));
    assert!(tool.keywords.contains(&"postgres".to_string()));

    // Verify skill name is in keywords
    assert!(tool.keywords.contains(&"database".to_string()));

    // Verify tool name is in keywords
    assert!(tool.keywords.contains(&"query".to_string()));
}

/// Test that multiple tools in same skill get same routing keywords.
#[test]
fn test_enrich_multiple_tools_with_same_keywords() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("api/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="get_user")
def get_user(user_id: str) -> dict:
    '''Get user by ID.'''
    return {}

@skill_command(name="create_user")
def create_user(name: str, email: str) -> dict:
    '''Create a new user.'''
    return {}

@skill_command(name="delete_user")
def delete_user(user_id: str) -> bool:
    '''Delete a user.'''
    return true
"#;
    fs::write(&scripts_dir.join("users.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    let routing_keywords = vec!["api".to_string(), "rest".to_string(), "user".to_string()];

    let tools = scanner
        .scan_scripts(&scripts_dir, "api", &routing_keywords)
        .unwrap();

    assert_eq!(tools.len(), 3);

    // All tools should have the same routing keywords enriched
    for tool in &tools {
        assert!(tool.keywords.contains(&"api".to_string()));
        assert!(tool.keywords.contains(&"rest".to_string()));
        assert!(tool.keywords.contains(&"user".to_string()));
        assert_eq!(tool.skill_name, "api");
    }
}

/// Test that empty routing keywords still enrich with skill name.
#[test]
fn test_enrich_with_empty_routing_keywords() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="hello")
def hello() -> str:
    '''Say hello.'''
    return "Hello!"
"#;
    fs::write(&scripts_dir.join("hello.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    let routing_keywords: Vec<String> = vec![];

    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &routing_keywords)
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Skill name should still be in keywords
    assert!(tool.keywords.contains(&"test".to_string()));
    // Tool name should be in keywords
    assert!(tool.keywords.contains(&"hello".to_string()));
}

/// Test tool record metadata structure for hybrid search enrichment.
#[test]
fn test_enrich_metadata_structure_for_hybrid_search() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("search/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="semantic_search")
def semantic_search(query: str, limit: int = 10) -> list:
    '''Perform semantic search.'''
    return []
"#;
    fs::write(&scripts_dir.join("search.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    let routing_keywords = vec![
        "search".to_string(),
        "semantic".to_string(),
        "vector".to_string(),
    ];

    let tools = scanner
        .scan_scripts(&scripts_dir, "search", &routing_keywords)
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Verify all metadata fields are present for hybrid search
    assert!(!tool.skill_name.is_empty());
    assert!(!tool.tool_name.is_empty());
    assert!(!tool.function_name.is_empty());
    assert!(!tool.file_path.is_empty());
    assert!(!tool.file_hash.is_empty());
    assert!(!tool.description.is_empty());
    assert!(!tool.keywords.is_empty());

    // Verify routing keywords are included in keywords
    assert!(tool.keywords.contains(&"search".to_string()));
    assert!(tool.keywords.contains(&"semantic".to_string()));
    assert!(tool.keywords.contains(&"vector".to_string()));
}

/// Test enrichment preserves docstring content.
#[test]
fn test_enrich_preserves_docstring() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("docs/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="generate_docs")
def generate_docs(source_path: str, output_format: str = "markdown") -> str:
    '''Generate documentation from source code.

    Args:
        source_path: Path to source files
        output_format: Output format (markdown, html, rst)

    Returns:
        Generated documentation content
    '''
    return "docs"
"#;
    fs::write(&scripts_dir.join("docs.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    let routing_keywords = vec!["documentation".to_string(), "docs".to_string()];

    let tools = scanner
        .scan_scripts(&scripts_dir, "docs", &routing_keywords)
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Docstring should be preserved
    assert!(tool.docstring.contains("Generate documentation"));
    assert!(tool.docstring.contains("source_path"));
    assert!(tool.docstring.contains("output_format"));
}

/// Test enrichment with different routing strategy keywords.
#[test]
fn test_enrich_with_intent_keywords() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("planner/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="create_plan")
def create_plan(goal: str, constraints: list[str] = None) -> dict:
    '''Create an execution plan for a goal.'''
    return {}
"#;
    fs::write(&scripts_dir.join("plan.py"), script_content).unwrap();

    let scanner = ScriptScanner::new();
    // Simulate intents from SKILL.md
    let routing_keywords = vec![
        "plan".to_string(),
        "goal".to_string(),
        "execute".to_string(),
        "strategy".to_string(),
    ];

    let tools = scanner
        .scan_scripts(&scripts_dir, "planner", &routing_keywords)
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Verify all routing keywords are enriched
    assert!(tool.keywords.contains(&"planner".to_string()));
    assert!(tool.keywords.contains(&"plan".to_string()));
    assert!(tool.keywords.contains(&"goal".to_string()));
    assert!(tool.keywords.contains(&"execute".to_string()));
    assert!(tool.keywords.contains(&"strategy".to_string()));
}
