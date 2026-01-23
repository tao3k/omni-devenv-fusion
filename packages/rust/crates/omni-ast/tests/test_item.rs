//! Tests for item module - AST item matching.

use omni_ast::Match;

#[test]
fn test_match_creation() {
    let m = Match::new(
        "def hello".to_string(),
        0,
        9,
        vec![("NAME".to_string(), "hello".to_string())],
    );
    assert_eq!(m.text, "def hello");
    assert_eq!(m.len(), 9);
    assert!(!m.is_empty());
    assert_eq!(m.get_capture("NAME"), Some("hello"));
    assert_eq!(m.get_capture("UNKNOWN"), None);
}

#[test]
fn test_empty_match() {
    let m = Match::new(String::new(), 0, 0, Vec::new());
    assert!(m.is_empty());
    assert_eq!(m.len(), 0);
}
