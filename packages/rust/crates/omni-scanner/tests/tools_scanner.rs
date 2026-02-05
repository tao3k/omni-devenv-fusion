//! Integration tests for ToolsScanner - tests tool parsing and discovery.
//!
//! These tests verify that ToolsScanner correctly finds @skill_command
//! decorated functions and extracts metadata.

use omni_scanner::{SkillScanner, ToolsScanner};
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

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "writer", &["write".to_string()], &[])
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

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "git", &["git".to_string()], &[])
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

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "empty", &[], &[])
        .unwrap();

    assert!(tools.is_empty());
}

/// Scan empty scripts directory returns empty vec.
#[test]
fn test_scan_scripts_empty_dir() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("empty/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "empty", &[], &[])
        .unwrap();

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

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

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

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_skill_scripts(&skill_path, "test_skill", &[], &[])
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

    let scanner = ToolsScanner::new();
    let structure = SkillScanner::default_structure();
    let routing_keywords = vec!["write".to_string(), "edit".to_string()];

    let tools = scanner
        .scan_with_structure(&skill_path, "writer", &routing_keywords, &[], &structure)
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
    let scanner = ToolsScanner::new();
    let structure = SkillScanner::default_structure();
    let routing_keywords = vec![];

    let tools = scanner
        .scan_with_structure(
            &skill_path,
            "empty_skill",
            &routing_keywords,
            &[],
            &structure,
        )
        .unwrap();

    assert!(tools.is_empty());
}

/// Scan with structure - handles nonexistent skill path.
#[test]
fn test_scan_with_structure_nonexistent_skill_path() {
    let temp_dir = TempDir::new().unwrap();
    let nonexistent_path = temp_dir.path().join("does_not_exist");

    let scanner = ToolsScanner::new();
    let structure = SkillScanner::default_structure();
    let routing_keywords = vec![];

    let tools = scanner
        .scan_with_structure(
            &nonexistent_path,
            "ghost",
            &routing_keywords,
            &[],
            &structure,
        )
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

    let scanner = ToolsScanner::new();
    let structure = SkillScanner::default_structure();
    let routing_keywords = vec!["git".to_string(), "version_control".to_string()];

    let tools = scanner
        .scan_with_structure(&skill_path, "git", &routing_keywords, &[], &structure)
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

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

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

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "writer", &[], &[])
        .unwrap();

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

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

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

    let scanner = ToolsScanner::new();
    let routing_keywords = vec![
        "database".to_string(),
        "query".to_string(),
        "sql".to_string(),
        "postgres".to_string(),
    ];

    let tools = scanner
        .scan_scripts(&scripts_dir, "database", &routing_keywords, &[])
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

    let scanner = ToolsScanner::new();
    let routing_keywords = vec!["api".to_string(), "rest".to_string(), "user".to_string()];

    let tools = scanner
        .scan_scripts(&scripts_dir, "api", &routing_keywords, &[])
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

    let scanner = ToolsScanner::new();
    let routing_keywords: Vec<String> = vec![];

    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &routing_keywords, &[])
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

    let scanner = ToolsScanner::new();
    let routing_keywords = vec![
        "search".to_string(),
        "semantic".to_string(),
        "vector".to_string(),
    ];

    let tools = scanner
        .scan_scripts(&scripts_dir, "search", &routing_keywords, &[])
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
from agent.skills.decorators import skill_command

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

    let scanner = ToolsScanner::new();
    let routing_keywords = vec!["documentation".to_string(), "docs".to_string()];

    let tools = scanner
        .scan_scripts(&scripts_dir, "docs", &routing_keywords, &[])
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

    let scanner = ToolsScanner::new();
    // Simulate intents from SKILL.md
    let routing_keywords = vec![
        "plan".to_string(),
        "goal".to_string(),
        "execute".to_string(),
        "strategy".to_string(),
    ];

    let tools = scanner
        .scan_scripts(&scripts_dir, "planner", &routing_keywords, &[])
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

// ============================================================================
// Decorator Kwargs Extraction Tests - Test deep AST parsing of @skill_command
// ============================================================================

/// Test that description kwarg is extracted from decorator.
#[test]
fn test_decorator_kwargs_extracts_description() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="fetch_data", description="Fetch data from API endpoint")
def fetch_data(url: str) -> dict:
    '''This docstring should be overridden by decorator description.'''
    return {}
"#;
    fs::write(&scripts_dir.join("api.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Description from decorator should take precedence
    assert_eq!(tool.description, "Fetch data from API endpoint");
}

/// Test that category kwarg is extracted from decorator.
#[test]
fn test_decorator_kwargs_extracts_category() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="process", category="data_processing")
def process_data(input: str) -> str:
    '''Process input data.'''
    return input
"#;
    fs::write(&scripts_dir.join("process.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Category should be extracted from decorator
    assert_eq!(tool.category, "data_processing");
}

/// Test that destructive kwarg is extracted from decorator.
#[test]
fn test_decorator_kwargs_extracts_destructive() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="delete_all", destructive=True)
def delete_all() -> str:
    '''Delete all data.'''
    return "deleted"
"#;
    fs::write(&scripts_dir.join("danger.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Destructive annotation should be set
    assert!(tool.annotations.destructive);
    assert!(!tool.annotations.idempotent);
}

/// Test that read_only kwarg is extracted from decorator.
#[test]
fn test_decorator_kwargs_extracts_read_only() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="get_status", read_only=True)
def get_status() -> dict:
    '''Get system status.'''
    return {}
"#;
    fs::write(&scripts_dir.join("status.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Read-only annotation should be set
    assert!(tool.annotations.read_only);
    assert!(tool.annotations.idempotent);
}

/// Test that all kwargs can be combined in single decorator.
#[test]
fn test_decorator_kwargs_combined() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(
    name="complex_op",
    description="Perform a complex operation",
    category="operations",
    destructive=False,
    read_only=True
)
def complex_operation(param1: str, param2: int, optional: bool = True) -> str:
    '''Complex operation with all kwargs.'''
    return "done"
"#;
    fs::write(&scripts_dir.join("complex.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // All kwargs should be extracted
    assert_eq!(tool.description, "Perform a complex operation");
    assert_eq!(tool.category, "operations");
    assert!(tool.annotations.read_only);
    assert!(!tool.annotations.destructive);
}

// ============================================================================
// Parameter Extraction Tests - Test function signature parsing
// ============================================================================

/// Test that function parameters are extracted correctly.
#[test]
fn test_parameter_extraction_basic() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="example")
def example(a: str, b: int, c: bool) -> str:
    '''Example with multiple params.'''
    return "ok"
"#;
    fs::write(&scripts_dir.join("params.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Parameters should be extracted
    assert_eq!(tool.parameters, vec!["a", "b", "c"]);
}

/// Test that parameters with default values are extracted.
#[test]
fn test_parameter_extraction_with_defaults() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="defaults")
def with_defaults(required: str, optional: str = "default", number: int = 42) -> str:
    '''Function with default values.'''
    return "ok"
"#;
    fs::write(&scripts_dir.join("defaults.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // All parameters should be extracted (defaults don't affect extraction)
    assert_eq!(tool.parameters, vec!["required", "optional", "number"]);
}

/// Tests that input_schema correctly handles async functions with typed parameters.
#[test]
fn test_async_function_type_inference() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("skill/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Simulate the actual skill.discover function signature
    let script_content = r#"
@skill_command(name="discover")
async def discover(intent: str, limit: int = 3) -> dict:
    '''Test async function.'''
    return {}
"#;
    fs::write(&scripts_dir.join("discover.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "skill", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Print for debugging
    println!("\n=== Tool ===");
    println!("tool_name: {}", tool.tool_name);
    println!("input_schema: {}", tool.input_schema);
    println!("parameters: {:?}", tool.parameters);

    // Parse the generated schema
    let schema: serde_json::Value =
        serde_json::from_str(&tool.input_schema).expect("input_schema should be valid JSON");

    let props = schema["properties"].as_object().unwrap();

    // Verify types
    assert_eq!(
        props["intent"]["type"], "string",
        "intent with type str should map to string"
    );
    assert_eq!(
        props["limit"]["type"], "integer",
        "limit with type int should map to integer"
    );

    // Verify required array (limit has default, should NOT be required)
    let required: Vec<&str> = schema["required"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_str().unwrap())
        .collect();

    assert!(
        required.contains(&"intent"),
        "intent is required (no default)"
    );
    assert!(
        !required.contains(&"limit"),
        "limit has default, should NOT be required"
    );
}

/// Tests that input_schema correctly infers Python types as JSON Schema types.
///
/// Validates the MCP tool schema specification:
/// - str -> "string"
/// - int -> "integer"
/// - bool -> "boolean"
/// - list[str] -> {"type": "array", "items": {"type": "string"}}
/// - dict[str, str] -> {"type": "object", "additionalProperties": true}
/// - Parameters with defaults are NOT in "required" array
/// - Parameters without defaults ARE in "required" array
#[test]
fn test_input_schema_type_inference() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="types")
def test_types(
    name: str,
    count: int = 10,
    enabled: bool,
    tags: list[str],
    metadata: dict[str, str] | None = None,
) -> str:
    '''Test type inference.'''
    return name
"#;
    fs::write(&scripts_dir.join("types.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Parse the generated schema
    let schema: serde_json::Value =
        serde_json::from_str(&tool.input_schema).expect("input_schema should be valid JSON");

    // Validate schema structure
    assert_eq!(schema["type"], "object");
    assert!(schema["properties"].is_object());
    assert!(schema["required"].is_array());

    let props = schema["properties"].as_object().unwrap();

    // Verify each parameter has correct type
    assert_eq!(
        props["name"]["type"], "string",
        "str should map to string type"
    );
    assert_eq!(
        props["count"]["type"], "integer",
        "int should map to integer type"
    );
    assert_eq!(
        props["enabled"]["type"], "boolean",
        "bool should map to boolean type"
    );

    // Verify list type has items
    let tags_type = &props["tags"]["type"];
    assert_eq!(tags_type["type"], "array");
    assert_eq!(tags_type["items"]["type"], "string");

    // Verify dict type has additionalProperties
    let metadata_type = &props["metadata"]["type"];
    assert_eq!(metadata_type["type"], "object");
    assert_eq!(metadata_type["additionalProperties"], true);

    // Verify required array only contains parameters without defaults
    let required: Vec<&str> = schema["required"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_str().unwrap())
        .collect();

    assert!(required.contains(&"name"), "name is required (no default)");
    assert!(
        required.contains(&"enabled"),
        "enabled is required (no default)"
    );
    assert!(required.contains(&"tags"), "tags is required (no default)");
    assert!(
        !required.contains(&"count"),
        "count has default, should NOT be required"
    );
    assert!(
        !required.contains(&"metadata"),
        "metadata has default, should NOT be required"
    );
}

/// Tests that input_schema preserves description from docstring Args.
#[test]
fn test_input_schema_with_param_descriptions() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="described")
def described_tool(
    message: str,
    count: int = 5,
) -> str:
    '''Tool with described parameters.

    Args:
        - message: str - The message to process (required)
        - count: int - Number of times to repeat (default: 5)

    Returns:
        Processed result.
    '''
    return message
"#;
    fs::write(&scripts_dir.join("described.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    let schema: serde_json::Value =
        serde_json::from_str(&tool.input_schema).expect("input_schema should be valid JSON");

    let props = schema["properties"].as_object().unwrap();

    // Verify descriptions are included
    assert!(
        props["message"]["description"].is_string(),
        "message should have description from docstring"
    );
    assert!(
        props["count"]["description"].is_string(),
        "count should have description from docstring"
    );

    // Verify description content
    let msg_desc = props["message"]["description"].as_str().unwrap();
    assert!(
        msg_desc.contains("message"),
        "description should mention parameter"
    );

    let count_desc = props["count"]["description"].as_str().unwrap();
    assert!(
        count_desc.contains("repeat"),
        "description should mention behavior"
    );
}

/// Tests input_schema handles Literal types correctly for enum-like behavior.
#[test]
fn test_input_schema_literal_types() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="literal_test")
def literal_tool(mode: Literal["fast", "slow", "normal"] = "normal") -> str:
    '''Test Literal type.'''
    return mode
"#;
    fs::write(&scripts_dir.join("literal_test.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    let schema: serde_json::Value =
        serde_json::from_str(&tool.input_schema).expect("input_schema should be valid JSON");

    let props = schema["properties"].as_object().unwrap();

    // Verify Literal becomes enum
    let mode_type = &props["mode"]["type"];
    assert_eq!(mode_type["type"], "string");
    assert!(mode_type["enum"].is_array(), "Literal should produce enum");
}

/// Test that *args and **kwargs are skipped.
#[test]
fn test_parameter_extraction_skips_varargs() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="varargs")
def with_varargs(a: str, *args, b: int, **kwargs) -> str:
    '''Function with *args and **kwargs.'''
    return "ok"
"#;
    fs::write(&scripts_dir.join("varargs.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Only named parameters should be extracted
    assert_eq!(tool.parameters, vec!["a", "b"]);
}

/// Test empty parameters for functions with no arguments.
#[test]
fn test_parameter_extraction_empty() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="no_args")
def no_args() -> str:
    '''Function with no arguments.'''
    return "ok"
"#;
    fs::write(&scripts_dir.join("no_args.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // No parameters should be extracted
    assert!(tool.parameters.is_empty());
}

// ============================================================================
// Annotation Heuristics Tests - Test automatic annotation inference
// ============================================================================

/// Test that read-only functions are auto-annotated.
#[test]
fn test_annotation_heuristics_read_only() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="get_data")
def get_data() -> dict:
    '''Get data from storage.'''
    return {}
"#;
    fs::write(&scripts_dir.join("getter.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // "get_" prefix should trigger read-only annotation
    assert!(tool.annotations.read_only);
    assert!(tool.annotations.idempotent);
}

/// Test that destructive functions are auto-annotated.
#[test]
fn test_annotation_heuristics_destructive() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="remove_file")
def remove_file(path: str) -> bool:
    '''Remove a file.'''
    return true
"#;
    fs::write(&scripts_dir.join("remover.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // "remove_" prefix should trigger destructive annotation
    assert!(tool.annotations.destructive);
    assert!(!tool.annotations.idempotent);
}

/// Test that network operations are auto-annotated as open_world.
#[test]
fn test_annotation_heuristics_open_world() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="fetch_url")
def fetch_url(url: str) -> str:
    '''Fetch content from URL.'''
    return ""
"#;
    fs::write(&scripts_dir.join("fetcher.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // "fetch_" and "url" should trigger open_world annotation
    assert!(tool.annotations.open_world);
}

/// Test that explicit decorator annotations override heuristics.
#[test]
fn test_explicit_annotation_overrides_heuristic() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="delete", destructive=False)
def delete_data() -> str:
    '''Delete operation marked as non-destructive.'''
    return "deleted"
"#;
    fs::write(&scripts_dir.join("delete.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Explicit destructive=False should override heuristic
    assert!(!tool.annotations.destructive);
}

/// Test multiple tools with different annotations.
#[test]
fn test_multiple_tools_different_annotations() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="query")
def query_data() -> list:
    '''Query database.'''
    return []

@skill_command(name="insert")
def insert_data(row: dict) -> bool:
    '''Insert into database.'''
    return true

@skill_command(name="delete")
def delete_data(id: str) -> bool:
    '''Delete from database.'''
    return true
"#;
    fs::write(&scripts_dir.join("db.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 3);

    // Find each tool and verify annotations
    let query_tool = tools.iter().find(|t| t.tool_name == "test.query").unwrap();
    assert!(query_tool.annotations.read_only);
    assert!(query_tool.annotations.idempotent);

    let insert_tool = tools.iter().find(|t| t.tool_name == "test.insert").unwrap();
    // insert_ prefix should trigger destructive
    assert!(insert_tool.annotations.destructive);

    let delete_tool = tools.iter().find(|t| t.tool_name == "test.delete").unwrap();
    assert!(delete_tool.annotations.destructive);
}

// ============================================================================
// JSON Serialization Tests - Verify enrichment data survives serialization
// ============================================================================

/// Test that enriched tool record serializes to JSON correctly.
#[test]
fn test_enriched_tool_record_json_serialization() {
    use serde_json;

    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
from agent.skills.decorators import skill_command

@skill_command(name="get_data", description="Get test data", category="test")
def get_data(param: str) -> str:
    '''Test docstring.'''
    return "ok"
"#;
    fs::write(&scripts_dir.join("test.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Serialize to JSON
    let json = serde_json::to_string(&tool).expect("Should serialize");

    // Deserialize back
    let deserialized: omni_scanner::ToolRecord =
        serde_json::from_str(&json).expect("Should deserialize");

    // Verify enrichment data survived serialization
    assert_eq!(deserialized.description, "Get test data");
    assert_eq!(deserialized.category, "test");
    assert_eq!(deserialized.parameters, vec!["param"]);
    assert!(deserialized.annotations.read_only);
}

// ============================================================================
// Triple-Quoted String Tests - Test multi-line string parsing in decorators
// ============================================================================

/// Test that triple-quoted description is parsed correctly.
#[test]
fn test_triple_quoted_description() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("memory/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(
    name="load_skill",
    description="""Load a skill's manifest into semantic memory for LLM recall.

    Usage:
    - load_skill("git")
    - load_skill("writer")

    Args:
        skill_name: Name of the skill to load
    """
)
def load_skill(skill_name: str) -> str:
    '''Load skill into memory.'''
    return "loaded"
"#;
    fs::write(&scripts_dir.join("load.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "memory", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Description should contain multi-line content
    assert!(tool.description.contains("Load a skill's manifest"));
    assert!(tool.description.contains("Usage:"));
    assert!(tool.description.contains("load_skill"));
    assert!(tool.description.contains("Args:"));
    assert!(tool.description.contains("skill_name"));
}

/// Test that category is extracted correctly.
#[test]
fn test_category_extraction() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="process", category="data_processing")
def process_data(input: str) -> str:
    '''Process input data.'''
    return input
"#;
    fs::write(&scripts_dir.join("process.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    assert_eq!(tool.category, "data_processing");
}

/// Test that input_schema is generated correctly from parameters.
#[test]
fn test_input_schema_generation() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="query")
def query_data(user_id: str, limit: int = 10) -> list:
    '''Query data from database.'''
    return []
"#;
    fs::write(&scripts_dir.join("query.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // Verify input_schema is valid JSON
    let schema: serde_json::Value =
        serde_json::from_str(&tool.input_schema).expect("Should be valid JSON");

    assert_eq!(schema["type"], "object");
    assert!(schema["properties"].is_object());
    assert!(schema["required"].is_array());

    // Verify properties
    let props = schema["properties"].as_object().unwrap();
    assert!(props.contains_key("user_id"));
    assert!(props.contains_key("limit"));

    // Verify required fields
    let required = schema["required"].as_array().unwrap();
    assert!(required.contains(&serde_json::json!("user_id")));
    // limit has default value, should not be required
}

/// Test that input_schema is empty for functions with no parameters.
#[test]
fn test_input_schema_empty_for_no_params() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="status")
def get_status() -> dict:
    '''Get system status.'''
    return {}
"#;
    fs::write(&scripts_dir.join("status.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    // input_schema should be valid JSON with empty properties
    let schema: serde_json::Value =
        serde_json::from_str(&tool.input_schema).expect("Should be valid JSON");

    assert_eq!(schema["type"], "object");
    assert_eq!(schema["properties"].as_object().unwrap().len(), 0);
    assert!(schema["required"].as_array().unwrap().is_empty());
}

/// Test that single-line description still works.
#[test]
fn test_single_line_description() {
    let temp_dir = TempDir::new().unwrap();
    let scripts_dir = temp_dir.path().join("test/scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    let script_content = r#"
@skill_command(name="fetch", description="Fetch data from API")
def fetch_data(url: str) -> str:
    '''Fetch data.'''
    return ""
"#;
    fs::write(&scripts_dir.join("fetch.py"), script_content).unwrap();

    let scanner = ToolsScanner::new();
    let tools = scanner
        .scan_scripts(&scripts_dir, "test", &[], &[])
        .unwrap();

    assert_eq!(tools.len(), 1);
    let tool = &tools[0];

    assert_eq!(tool.description, "Fetch data from API");
}

/// Test that IndexToolEntry includes category and input_schema.
#[test]
fn test_index_tool_entry_includes_category_and_schema() {
    use omni_scanner::SkillScanner;

    let temp_dir = TempDir::new().unwrap();
    let skill_path = temp_dir.path().join("test_skill");
    let scripts_dir = skill_path.join("scripts");
    fs::create_dir_all(&scripts_dir).unwrap();

    // Create SKILL.md with frontmatter
    let skill_md = r#"
---
name: "test_skill"
version: "1.0.0"
description: "Test skill"
routing_keywords: ["test"]
---
"#;
    fs::write(&skill_path.join("SKILL.md"), skill_md).unwrap();

    // Create script with category
    let script_content = r#"
@skill_command(name="process", category="processing")
def process_data(input: str) -> str:
    '''Process data.'''
    return input
"#;
    fs::write(&scripts_dir.join("process.py"), script_content).unwrap();

    let scanner = SkillScanner::new();
    let script_scanner = ToolsScanner::new();

    let entry = scanner.build_index_entry(
        scanner.scan_skill(&skill_path, None).unwrap().unwrap(),
        &script_scanner
            .scan_scripts(&scripts_dir, "test_skill", &[], &[])
            .unwrap(),
        &skill_path,
    );

    assert_eq!(entry.tools.len(), 1);
    let tool = &entry.tools[0];

    assert_eq!(tool.name, "test_skill.process");
    assert_eq!(tool.category, "processing");
    assert!(!tool.input_schema.is_empty());

    // Verify input_schema is valid JSON
    let schema: serde_json::Value =
        serde_json::from_str(&tool.input_schema).expect("Should be valid JSON");
    assert_eq!(schema["type"], "object");
}
