//! Capture substitution logic for AST pattern variables.
//!
//! Handles both single captures ($NAME) and variadic captures ($$$ARGS).

use omni_ast::{MetaVariable, Doc};

/// Substitute captured variables into replacement text.
///
/// Handles:
/// - Single captures: `$NAME` -> captured text
/// - Variadic captures: `$$$ARGS` or `$$$` -> captured text
///
/// # Arguments
/// * `replacement` - The replacement template with $VAR placeholders
/// * `env` - The match environment containing captured variables
/// * `original_text` - Original matched text (fallback for variadic extraction)
///
/// # Returns
/// The replacement text with all captures substituted.
pub fn substitute_captures<D: Doc>(
    replacement: &str,
    env: &omni_ast::MetaVarEnv<D>,
    original_text: &str,
) -> String {
    let mut new_text = replacement.to_string();

    // Extract and substitute all named captures
    for mv in env.get_matched_variables() {
        let (capture_name, is_multi) = match mv {
            MetaVariable::Capture(name, _) => (Some(name.to_string()), false),
            MetaVariable::MultiCapture(name) => (Some(name.to_string()), true),
            _ => (None, false),
        };

        if let Some(name) = capture_name {
            if let Some(captured) = env.get_match(&name) {
                let captured_text = captured.text().to_string();

                if is_multi {
                    // Variadic capture: try $$$NAME first, then fallback to $$$
                    let multi_placeholder = format!("$$${}", name);
                    if new_text.contains(&multi_placeholder) {
                        new_text = new_text.replace(&multi_placeholder, &captured_text);
                    } else if new_text.contains("$$$") {
                        new_text = new_text.replacen("$$$", &captured_text, 1);
                    }
                } else {
                    // Single capture: $NAME
                    let placeholder = format!("${}", name);
                    new_text = new_text.replace(&placeholder, &captured_text);
                }
            }
        }
    }

    // Handle remaining $$$ patterns by extracting from original text
    // Fallback for when ast-grep doesn't expose multi-captures directly
    if new_text.contains("$$$") {
        new_text = extract_variadic_fallback(&new_text, original_text);
    }

    new_text
}

/// Fallback extraction for variadic patterns from original text.
///
/// Extracts content between parentheses to substitute remaining $$$ patterns.
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

#[cfg(test)]
mod tests {
    #[test]
    fn test_variadic_fallback() {
        let replacement = "new_func($$$)";
        let original = "old_func(a, b, c)";
        let result = super::extract_variadic_fallback(replacement, original);
        assert_eq!(result, "new_func(a, b, c)");
    }

    #[test]
    fn test_named_variadic_fallback() {
        let replacement = "new_func($$$ARGS)";
        let original = "old_func(x, y)";
        let result = super::extract_variadic_fallback(replacement, original);
        assert_eq!(result, "new_func(x, y)");
    }
}
