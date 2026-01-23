//! Tests for lang module - language support.

use omni_ast::Lang;

#[test]
fn test_from_extension() {
    assert_eq!(Lang::from_extension("py"), Some(Lang::Python));
    assert_eq!(Lang::from_extension("rs"), Some(Lang::Rust));
    assert_eq!(Lang::from_extension("js"), Some(Lang::JavaScript));
    assert_eq!(Lang::from_extension("unknown"), None);
}

#[test]
fn test_try_from() {
    let lang: Lang = "python".try_into().unwrap();
    assert_eq!(lang, Lang::Python);
    assert_eq!(lang.as_str(), "py");
}

#[test]
fn test_extensions() {
    assert_eq!(Lang::Python.extensions(), vec!["py"]);
    assert!(Lang::JavaScript.extensions().contains(&"js"));
}
