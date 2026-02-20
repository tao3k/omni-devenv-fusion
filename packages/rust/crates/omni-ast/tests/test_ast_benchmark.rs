//! Benchmark tests for AST parsing performance.
//!
//! These tests measure the performance of Python AST parsing using
//! tree-sitter and ast-grep for pattern matching.

use std::time::Duration;

/// Generate a large Python file for benchmarking.
fn generate_python_file(line_count: usize) -> String {
    let mut content = String::with_capacity(line_count * 60);

    // Add imports
    content
        .push_str("import os\nimport sys\nfrom typing import Dict, List, Optional, Tuple, Any\n\n");

    // Add classes with methods
    for i in 0..(line_count / 30) {
        content.push_str(&format!(
            r#"class Class{i}:
    """A sample class for benchmarking."""

    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value
        self.cache: Dict[str, Any] = {{}}

    def process(self, data: List[str]) -> List[str]:
        """Process a list of strings."""
        result = []
        for item in data:
            if item:
                result.append(item.upper())
        return result

    async def async_process(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async processing method."""
        if not data:
            return None
        return {{"processed": True, "items": len(data)}}

    @property
    def summary(self) -> str:
        """Return a summary of the instance."""
        return f"Class{{self.name}} with value {{self.value}}"


"#,
            i = i
        ));
    }

    // Add functions
    for i in 0..(line_count / 20) {
        content.push_str(&format!(
            r#"def function_{i}(arg1: str, arg2: int, arg3: Optional[List[str]] = None) -> Tuple[str, int]:
    """A sample function for benchmarking."""
    if arg3 is None:
        arg3 = []
    result = []
    for item in arg3:
        if item and len(item) > arg2:
            result.append(item[:arg2])
    return arg1.upper(), len(result)


async def async_function_{i}(data: Dict[str, Any]) -> Any:
    """An async function for benchmarking."""
    results = []
    for key, value in data.items():
        if isinstance(value, list):
            results.extend(value)
    return results


def decorator_wrapper(func):
    """A decorator for benchmarking."""
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


"#,
            i = i
        ));
    }

    content
}

/// Generate Python file with decorators for benchmarking.
fn generate_python_with_decorators(line_count: usize) -> String {
    let mut content = String::with_capacity(line_count * 70);

    for i in 0..(line_count / 15) {
        content.push_str(&format!(
            r#"@skill_command(name="cmd_{i}")
@validate_input
@log_execution
def command_{i}(ctx, arg1: str, arg2: Optional[int] = None) -> Dict[str, Any]:
    """Command function {i} with decorators."""
    if arg2 is None:
        arg2 = 10
    result = {{
        "status": "success",
        "command": "cmd_{i}",
        "args": [arg1, arg2],
        "timestamp": "2024-01-01T00:00:00Z"
    }}
    return result


class BaseHandler{i}:
    """Base handler class {i}."""

    @abstractmethod
    def handle(self, event: Dict[str, Any]) -> None:
        pass


class SpecializedHandler{i}(BaseHandler{i}):
    """Specialized handler {i}."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cache: Dict[str, Any] = {{}}

    @property
    def handler_type(self) -> str:
        return "specialized"

    def handle(self, event: Dict[str, Any]) -> None:
        """Handle an event."""
        if "type" in event:
            self._process_event(event["type"], event.get("data", {{}}))

    def _process_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Process an event of specific type."""
        return True


"#,
            i = i
        ));
    }

    content
}

/// Benchmark test for Python pattern matching (ast-grep).
#[test]
fn test_python_pattern_matching_performance() {
    const LINE_COUNT: usize = 500;

    let content = generate_python_file(LINE_COUNT);

    let start = std::time::Instant::now();

    // Parse multiple times to get stable timing
    for _ in 0..10 {
        // Find all functions
        let _ = omni_ast::find_python_functions(&content);

        // Find all async functions
        let _ = omni_ast::find_python_async_functions(&content);

        // Find all classes
        let _ = omni_ast::find_python_classes(&content);
    }

    let elapsed = start.elapsed();

    // Should complete 10 iterations in under 5 seconds
    let max_duration = Duration::from_secs(5);
    assert!(
        elapsed < max_duration,
        "Python pattern matching took {:.2}s for 10 iterations, expected < 5s",
        elapsed.as_secs_f64()
    );

    println!(
        "Python pattern matching: {} lines x 10 iterations = {:.2}ms",
        LINE_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for tree-sitter decorated function extraction.
#[test]
fn test_tree_sitter_decorated_functions_performance() {
    const LINE_COUNT: usize = 500;

    let content = generate_python_with_decorators(LINE_COUNT);

    let start = std::time::Instant::now();

    // Test tree-sitter decorated function extraction
    for _ in 0..10 {
        let mut parser = omni_ast::TreeSitterPythonParser::new();
        let _ = parser.find_decorated_functions(&content, "skill_command");
    }

    let elapsed = start.elapsed();

    // Should complete 10 iterations in under 3 seconds
    let max_duration = Duration::from_secs(3);
    assert!(
        elapsed < max_duration,
        "Tree-sitter decorated functions took {:.2}s, expected < 3s",
        elapsed.as_secs_f64()
    );

    println!(
        "Tree-sitter decorated functions: {} lines x 10 iterations = {:.2}ms",
        LINE_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for docstring extraction.
#[test]
fn test_docstring_extraction_performance() {
    const LINE_COUNT: usize = 500;

    let content = generate_python_file(LINE_COUNT);

    let start = std::time::Instant::now();

    for _ in 0..20 {
        // Extract docstrings from all functions
        let functions = omni_ast::find_python_functions(&content);
        for func in &functions {
            let _ = omni_ast::extract_docstring_from_match(func);
        }
    }

    let elapsed = start.elapsed();

    // Should complete 20 iterations in under 10 seconds (relaxed for dev environment)
    let max_duration = Duration::from_secs(10);
    assert!(
        elapsed < max_duration,
        "Docstring extraction took {:.2}s, expected < 10s",
        elapsed.as_secs_f64()
    );

    println!(
        "Docstring extraction: {} lines x 20 iterations = {:.2}ms",
        LINE_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for large file pattern matching.
#[test]
fn test_large_python_file_matching() {
    const LINE_COUNT: usize = 1000;

    let content = generate_python_file(LINE_COUNT);

    let start = std::time::Instant::now();

    let functions = omni_ast::find_python_functions(&content);
    let async_functions = omni_ast::find_python_async_functions(&content);
    let classes = omni_ast::find_python_classes(&content);

    let elapsed = start.elapsed();

    // Should parse a 1000-line file in under 2 seconds
    let max_duration = Duration::from_secs(2);
    assert!(
        elapsed < max_duration,
        "Large file matching took {:.2}s for {} lines, expected < 2s",
        elapsed.as_secs_f64(),
        LINE_COUNT
    );

    println!(
        "Large file matching: {} lines = {:.2}ms ({} funcs, {} async, {} classes)",
        LINE_COUNT,
        elapsed.as_secs_f64() * 1000.0,
        functions.len(),
        async_functions.len(),
        classes.len()
    );
}

/// Benchmark test for mixed Python file parsing.
#[test]
fn test_mixed_python_parsing_performance() {
    // Mix of files with decorators and without
    let contents: Vec<String> = (0..10)
        .map(|i| {
            if i % 3 == 0 {
                generate_python_with_decorators(200)
            } else {
                generate_python_file(200)
            }
        })
        .collect();

    let start = std::time::Instant::now();

    for content in &contents {
        let _ = omni_ast::find_python_functions(content);
        let _ = omni_ast::find_python_classes(content);
    }

    let elapsed = start.elapsed();

    // Should parse 10 mixed files in under 3 seconds
    let max_duration = Duration::from_secs(3);
    assert!(
        elapsed < max_duration,
        "Mixed parsing took {:.2}s, expected < 3s",
        elapsed.as_secs_f64()
    );

    println!(
        "Mixed Python parsing: 10 files = {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for decorated functions with different decorators.
#[test]
fn test_multiple_decorator_types_performance() {
    const LINE_COUNT: usize = 300;

    let content = generate_python_with_decorators(LINE_COUNT);

    let start = std::time::Instant::now();

    for _ in 0..10 {
        let mut parser = omni_ast::TreeSitterPythonParser::new();

        // Find functions with different decorators
        let _ = parser.find_decorated_functions(&content, "skill_command");
        let _ = parser.find_decorated_functions(&content, "validate_input");
        let _ = parser.find_decorated_functions(&content, "log_execution");
    }

    let elapsed = start.elapsed();

    // Should complete in under 3 seconds
    let max_duration = Duration::from_secs(3);
    assert!(
        elapsed < max_duration,
        "Multiple decorator types took {:.2}s, expected < 3s",
        elapsed.as_secs_f64()
    );

    println!(
        "Multiple decorator types: {} lines x 10 x 3 decorators = {:.2}ms",
        LINE_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Verify correctness of pattern matching.
#[test]
fn test_pattern_matching_correctness() {
    let content = generate_python_file(100);

    let functions = omni_ast::find_python_functions(&content);
    let async_functions = omni_ast::find_python_async_functions(&content);
    let classes = omni_ast::find_python_classes(&content);

    // Verify we found some patterns
    assert!(!functions.is_empty(), "Should find some functions");
    assert!(
        !async_functions.is_empty(),
        "Should find some async functions"
    );
    assert!(!classes.is_empty(), "Should find some classes");

    // Verify structure
    for func in &functions {
        assert!(
            !func.captures.is_empty(),
            "Function match should have captures"
        );
    }
}
