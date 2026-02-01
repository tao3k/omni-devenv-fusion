//! Tests for extract module - AST-based code extraction.

use omni_ast::{Lang, extract, extract_items};

#[test]
fn test_extract_items_basic() {
    let content = r#"
def hello(name: str) -> str:
    '''Greet someone.'''
    return f"Hello, {name}!"

def goodbye():
    pass
"#;

    let results = extract_items(content, "def $NAME", Lang::Python, None);
    assert_eq!(results.len(), 2);

    // Verify first function
    let hello = &results[0];
    assert!(hello.text.starts_with("def hello"));
    assert_eq!(hello.captures.get("NAME"), Some(&"hello".to_string()));
    assert!(hello.line_start > 0);
    assert!(hello.line_end >= hello.line_start);
}

#[test]
fn test_extract_items_with_captures() {
    let content = r#"
def hello(name: str) -> str:
    return f"Hello, {name}!"

def goodbye():
    pass
"#;

    // Use simple pattern to match both functions
    let results = extract_items(content, "def $NAME", Lang::Python, Some(vec!["NAME"]));
    assert_eq!(results.len(), 2);

    for r in &results {
        assert!(r.captures.contains_key("NAME"));
    }
}

#[test]
fn test_extract_items_rust() {
    let content = r#"
fn hello(name: &str) -> String {
    format!("Hello, {}!", name)
}

fn goodbye() {
    println!("Goodbye");
}
"#;

    let results = extract_items(content, "fn $NAME", Lang::Rust, None);
    assert_eq!(results.len(), 2);

    let hello = &results[0];
    assert!(hello.text.starts_with("fn hello"));
    assert_eq!(hello.captures["NAME"], "hello");
}

#[test]
fn test_extract_items_classes() {
    let content = r#"
class MyClass:
    def method(self):
        pass

class AnotherClass:
    pass
"#;

    let results = extract_items(content, "class $NAME", Lang::Python, None);
    assert_eq!(results.len(), 2);

    let first = &results[0];
    assert!(first.captures.contains_key("NAME"));
}

#[test]
fn test_extract_items_empty() {
    let content = "let x = 42;";
    let results = extract_items(content, "def $NAME", Lang::Python, None);
    assert!(results.is_empty());
}

#[test]
fn test_extract_items_line_numbers() {
    let content = "x = 1\ny = 2\nz = 3\n";
    let results = extract_items(content, "$NAME = $VALUE", Lang::Python, Some(vec!["NAME"]));

    assert_eq!(results.len(), 3);

    // Line numbers should be 1-indexed
    assert_eq!(results[0].line_start, 1);
    assert_eq!(results[1].line_start, 2);
    assert_eq!(results[2].line_start, 3);
}

#[test]
fn test_extract_items_variables() {
    let content = r#"
x = 1
y = 2
name = "hello"
"#;

    let results = extract_items(content, "$NAME = $VALUE", Lang::Python, None);
    assert_eq!(results.len(), 3);

    for r in &results {
        assert!(r.captures.contains_key("NAME"));
        assert!(r.captures.contains_key("VALUE"));
    }
}

#[test]
fn test_extract_items_javascript() {
    let content = r#"
function hello(name) {
    return `Hello, ${name}!`;
}

const goodbye = () => {
    console.log("Goodbye");
};
"#;

    let results = extract_items(content, "function $NAME", Lang::JavaScript, None);
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].captures["NAME"], "hello");
}

#[test]
fn test_extract_extract_single() {
    let content = "def hello(name: str): pass";
    let name = extract(content, "def $NAME($ARGS)", "NAME", Lang::Python);
    assert_eq!(name, Some("hello".to_string()));
}

#[test]
fn test_extract_extract_not_found() {
    let content = "x = 42";
    let name = extract(content, "def $NAME", "NAME", Lang::Python);
    assert_eq!(name, None);
}
