//! Tests for the Tree-sitter Python parser.

use omni_ast::TreeSitterPythonParser;

#[test]
fn test_parse_skill_discover_decorator() {
    // This is the actual skill.discover decorator from assets/skills/skill/scripts/discovery.py
    // It has a complex multi-line description with commas
    let code = r#"
@skill_command(
    name="discover",
    category="system",
    description="""
    [CRITICAL] Capability Discovery & Intent Resolver - The Agent's PRIMARY Entry Point.

    MANDATORY WORKFLOW: This tool is the EXCLUSIVE gateway for solving any task. It maps high-level natural language goals to specific, executable @omni commands.

    CORE RESPONSIBILITIES:
    1. INTENT MAPPING: Converts vague requests (e.g., "debug network", "optimize rust") into concrete tool sequences.
    2. GLOBAL REGISTRY ACCESS: Searches the entire Skill Registry (Active + Inactive). If a tool is found but not loaded, it provides `jit_install` instructions.
    3. SYNTAX ENFORCEMENT: Resolves the EXACT @omni(...) invocation template. Direct @omni calls are FORBIDDEN without first retrieving the template from discovery.
    4. ARCHITECTURAL ORIENTATION: Use this at the START of every session or new sub-task to identify available "superpowers" before planning.

    WHEN TO USE:
    - To find out *how* to perform a task (e.g., "how to analyze a pcap").
    - To check if a specific capability (e.g., "image processing") exists.
    - To get the correct parameter schema for a tool.
    - Whenever you encounter a new domain you haven't worked with in the current session.

    Args:
        - intent: str - The natural language goal or action (required).
        - limit: int = 5 - Max results to return (increase for complex/ambiguous tasks).

    Returns:
        A structured map containing:
        - 'quick_guide': Direct usage templates to copy and paste.
        - 'details': Full metadata, descriptions, and scores for each tool.
    """,
)
def discover(intent: str, limit: int = 5) -> str:
    '''The discover function implementation.'''
    return "discover result"
"#;

    let mut parser = TreeSitterPythonParser::new();
    let funcs = parser.find_decorated_functions(code, "skill_command");

    assert_eq!(funcs.len(), 1, "Should find exactly one decorated function");

    let func = &funcs[0];
    assert_eq!(func.name, "discover");

    // Verify decorator was parsed
    let decorator = func.decorator.as_ref().expect("Should have decorator");
    assert_eq!(decorator.name, "skill_command");

    // Verify decorator arguments
    let args = &decorator.arguments;
    assert_eq!(args.name, Some("discover".to_string()));
    assert_eq!(args.category, Some("system".to_string()));

    // The critical test: description should be extracted correctly
    let desc = args.description.as_ref().expect("Should have description");
    assert!(
        desc.contains("CRITICAL"),
        "Description should contain CRITICAL"
    );
    assert!(
        desc.contains("INTENT MAPPING"),
        "Description should contain INTENT MAPPING"
    );
    assert!(
        desc.contains("CORE RESPONSIBILITIES"),
        "Description should contain CORE RESPONSIBILITIES"
    );

    // Verify parameters were parsed
    assert_eq!(func.parameters.len(), 2);
    assert_eq!(func.parameters[0].name, "intent");
    assert_eq!(func.parameters[0].type_annotation, Some("str".to_string()));
    assert!(func.parameters[0].default_value.is_none());

    assert_eq!(func.parameters[1].name, "limit");
    assert_eq!(func.parameters[1].type_annotation, Some("int".to_string()));
    assert_eq!(func.parameters[1].default_value, Some("5".to_string()));

    // Verify docstring was extracted
    assert!(func.docstring.contains("discover function implementation"));
}

#[test]
fn test_parse_decorator_with_triple_quotes_and_commas() {
    // Test case specifically for comma handling inside triple-quoted strings
    let code = r#"
@skill_command(
    name="test",
    description="""
    Multi-line,
    with, many, commas,
    here.
    """,
    category="test"
)
def test_func():
    pass
"#;

    let mut parser = TreeSitterPythonParser::new();
    let funcs = parser.find_decorated_functions(code, "skill_command");

    assert_eq!(funcs.len(), 1);

    let args = &funcs[0].decorator.as_ref().unwrap().arguments;
    let desc = args.description.as_ref().unwrap();

    // The description should contain the commas (not split on them)
    assert!(desc.contains("Multi-line"));
    assert!(desc.contains("with, many, commas"));
    assert!(desc.contains("here."));
}

#[test]
fn test_parse_multiple_decorated_functions() {
    let code = r#"
@skill_command(name="foo")
def foo(x: int) -> int:
    '''Foo function.'''
    return x * 2

@skill_command(name="bar")
def bar(y: str, z: str = "default") -> str:
    '''Bar function.'''
    return y + z
"#;

    let mut parser = TreeSitterPythonParser::new();
    let funcs = parser.find_decorated_functions(code, "skill_command");

    assert_eq!(funcs.len(), 2);

    // First function
    assert_eq!(funcs[0].name, "foo");
    assert_eq!(funcs[0].parameters.len(), 1);
    assert_eq!(funcs[0].parameters[0].name, "x");
    assert_eq!(
        funcs[0].decorator.as_ref().unwrap().arguments.name,
        Some("foo".to_string())
    );

    // Second function
    assert_eq!(funcs[1].name, "bar");
    assert_eq!(funcs[1].parameters.len(), 2);
    assert_eq!(funcs[1].parameters[0].name, "y");
    assert_eq!(funcs[1].parameters[1].name, "z");
    assert_eq!(
        funcs[1].parameters[1].default_value,
        Some("\"default\"".to_string())
    );
}

#[test]
fn test_parse_function_without_decorator() {
    let code = r#"
def regular_function(x: int) -> int:
    '''Not a skill command.'''
    return x * 2
"#;

    let mut parser = TreeSitterPythonParser::new();
    let funcs = parser.find_decorated_functions(code, "skill_command");

    // Should not find any skill_command decorated functions
    assert_eq!(funcs.len(), 0);
}
