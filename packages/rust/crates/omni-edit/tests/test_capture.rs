//! Tests for capture module - capture substitution.

// Note: Full substitute_captures tests require MetaVarEnv from omni_ast.
// These tests verify the fallback extraction logic.

/// Test the variadic fallback extraction.
#[test]
fn test_extract_variadic_simple() {
    let original = "connect(a, b, c)";
    let result = extract_variadic_fallback("async_connect($$$)", original);
    assert_eq!(result, "async_connect(a, b, c)");
}

/// Test named variadic fallback.
#[test]
fn test_extract_variadic_named() {
    let original = "old_func(x, y)";
    let result = extract_variadic_fallback("new_func($$$ARGS)", original);
    assert_eq!(result, "new_func(x, y)");
}

/// Simple variadic fallback extraction for testing.
fn extract_variadic_fallback(replacement: &str, original_text: &str) -> String {
    let mut new_text = replacement.to_string();

    if let Some(start_paren) = original_text.find('(') {
        if let Some(end_paren) = original_text.rfind(')') {
            let args = &original_text[start_paren + 1..end_paren];

            // First handle named variadic like $$$ARGS
            if let Ok(re) = regex::Regex::new(r"\$\$\$\w+") {
                new_text = re.replace_all(&new_text, args).to_string();
            }

            // Then handle anonymous $$$
            if new_text.contains("$$$") {
                new_text = new_text.replacen("$$$", args, 1);
            }
        }
    }

    new_text
}
