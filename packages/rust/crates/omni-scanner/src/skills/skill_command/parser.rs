//! Script parsing utilities for @skill_command decorator extraction.
//!
//! Provides functions to parse Python scripts and extract:
//! - Decorator positions and arguments
//! - Function docstrings
//! - Parameter names

use crate::skills::metadata::DecoratorArgs;

/// Find all @skill_command decorator positions in Python code.
///
/// Uses simple string matching (not regex) to find decorators.
/// Returns Vec of (start_pos, end_pos, full_decorator_text).
pub fn find_skill_command_decorators(content: &str) -> Vec<(usize, usize, String)> {
    let mut decorators = Vec::new();
    let prefix = "@skill_command";

    // Find all occurrences of @skill_command
    let mut search_start = 0usize;
    while let Some(start) = content[search_start..].find(prefix) {
        let absolute_start = search_start + start;
        let line_start = content[..absolute_start].rfind('\n').map_or(0, |p| p + 1);

        // Find the end of the decorator (matching closing paren or end of line)
        let after_decorator = &content[absolute_start + prefix.len()..];

        // Check if this is a valid decorator call with parentheses
        if after_decorator.starts_with('(') {
            let mut depth = 1;
            let mut end_offset = None;

            let mut in_string = false;
            let mut quote_char = '\0';
            let mut in_triple_quote = false;

            let paren_start = absolute_start + prefix.len();
            let search_content = &content[paren_start + 1..];

            let mut i = 0;
            let chars: Vec<char> = search_content.chars().collect();

            while i < chars.len() {
                let c = chars[i];

                if in_triple_quote {
                    if c == quote_char
                        && i + 2 < chars.len()
                        && chars[i + 1] == quote_char
                        && chars[i + 2] == quote_char
                    {
                        in_triple_quote = false;
                        i += 2;
                    }
                } else if in_string {
                    if c == quote_char && (i == 0 || chars[i - 1] != '\\') {
                        in_string = false;
                    }
                } else {
                    // Check for triple quotes
                    if i + 2 < chars.len() {
                        if (chars[i] == '"' && chars[i + 1] == '"' && chars[i + 2] == '"')
                            || (chars[i] == '\'' && chars[i + 1] == '\'' && chars[i + 2] == '\'')
                        {
                            in_triple_quote = true;
                            quote_char = chars[i];
                            i += 2;
                            i += 1;
                            continue;
                        }
                    }

                    if c == '"' || c == '\'' {
                        in_string = true;
                        quote_char = c;
                    } else if c == '(' {
                        depth += 1;
                    } else if c == ')' {
                        depth -= 1;
                        if depth == 0 {
                            end_offset = Some(paren_start + 1 + i + 1);
                            break;
                        }
                    }
                }
                i += 1;
            }

            if let Some(end_pos) = end_offset {
                // Extract the full decorator text including @ sign
                let full_text = &content[line_start..end_pos];
                decorators.push((line_start, end_pos, full_text.to_string()));
                search_start = end_pos;
            } else {
                search_start = absolute_start + prefix.len();
            }
        } else {
            // Invalid format, skip
            search_start = absolute_start + prefix.len();
        }
    }

    decorators
}

/// Parse decorator arguments from decorator text handling triple-quoted strings.
pub fn parse_decorator_args(decorator_text: &str) -> DecoratorArgs {
    let mut args = DecoratorArgs::default();

    // Extract the arguments from within the parentheses
    // Need to handle triple-quoted strings that may contain )
    if let Some(open_paren) = decorator_text.find('(') {
        let arg_text = extract_decorator_arg_text(decorator_text, open_paren + 1);

        // Parse key=value pairs with proper triple-quoted string handling
        let parts = split_args_respecting_strings(&arg_text);

        for part in parts {
            let part = part.trim();
            if part.is_empty() {
                continue;
            }

            // Parse key=value
            if let Some(eq_pos) = part.find('=') {
                let key = &part[..eq_pos].trim();
                let value = &part[eq_pos + 1..].trim();

                match *key {
                    "name" => {
                        let cleaned = extract_string_value(value);
                        args.name = Some(cleaned.to_string());
                    }
                    "description" => {
                        let cleaned = extract_string_value(value);
                        args.description = Some(cleaned.to_string());
                    }
                    "category" => {
                        let cleaned = extract_string_value(value);
                        args.category = Some(cleaned.to_string());
                    }
                    "destructive" => {
                        args.destructive = Some(value.trim().eq_ignore_ascii_case("True"));
                    }
                    "read_only" => {
                        args.read_only = Some(value.trim().eq_ignore_ascii_case("True"));
                    }
                    _ => {}
                }
            }
        }
    }

    args
}

/// Extract text between parentheses, respecting triple-quoted strings.
fn extract_decorator_arg_text(text: &str, start: usize) -> String {
    let mut depth = 1;
    let mut in_triple_quote = false;
    let mut triple_quote_char = '\0';
    let mut result = String::new();

    for (i, c) in text[start..].char_indices() {
        let absolute_pos = start + i;

        if in_triple_quote {
            if c == triple_quote_char {
                // Check for closing triple quote (3 consecutive quotes)
                let remaining = &text[absolute_pos..];
                if remaining.starts_with("\"\"\"") || remaining.starts_with("'''") {
                    // Include the closing triple quote and exit triple quote mode
                    result.push_str(&text[start + i..start + i + 3]);
                    in_triple_quote = false;
                    // Don't return yet! Continue to find the closing paren
                    continue;
                }
            }
            result.push(c);
        } else {
            // Check for start of triple quote
            let remaining = &text[absolute_pos..];
            if remaining.starts_with("\"\"\"") {
                in_triple_quote = true;
                triple_quote_char = '"';
                result.push_str("\"\"\"");
            } else if c == '(' {
                depth += 1;
                result.push(c);
            } else if c == ')' {
                depth -= 1;
                if depth == 0 {
                    return result;
                }
                result.push(c);
            } else {
                result.push(c);
            }
        }
    }

    result
}

/// Split argument text on commas, but respect triple-quoted strings.
fn split_args_respecting_strings(arg_text: &str) -> Vec<&str> {
    let mut result = Vec::new();
    let mut current_start = 0usize;
    let mut in_triple_quote = false;
    let mut triple_quote_char = '\0';
    let mut skip_next_chars = 0usize;

    for (i, c) in arg_text.char_indices() {
        // Skip characters if needed (after detecting triple quote end)
        if skip_next_chars > 0 {
            skip_next_chars -= 1;
            continue;
        }

        if in_triple_quote {
            // Check if we're at the end of triple quote (3 consecutive quotes)
            if c == triple_quote_char {
                let remaining = &arg_text[i..];
                if remaining.starts_with("\"\"\"") || remaining.starts_with("'''") {
                    in_triple_quote = false;
                    skip_next_chars = 2; // Skip the next 2 quote characters
                }
            }
        } else {
            // Check for start of triple quote
            let remaining = &arg_text[i..];
            if remaining.starts_with("\"\"\"") {
                in_triple_quote = true;
                triple_quote_char = '"';
                skip_next_chars = 2; // Skip the next 2 quote characters
            } else if remaining.starts_with("'''") {
                in_triple_quote = true;
                triple_quote_char = '\'';
                skip_next_chars = 2; // Skip the next 2 quote characters
            } else if c == ',' {
                // Split at comma
                result.push(&arg_text[current_start..i]);
                current_start = i + 1;
            }
        }
    }

    // Add the last part
    if current_start < arg_text.len() {
        result.push(&arg_text[current_start..]);
    }

    result
}

/// Extract value from a string literal (handles triple-quoted strings).
fn extract_string_value(value: &str) -> &str {
    // Check for triple-quoted strings
    if value.starts_with("\"\"\"") {
        if let Some(end) = value[3..].find("\"\"\"") {
            return &value[3..3 + end];
        }
    } else if value.starts_with("'''") {
        if let Some(end) = value[3..].find("'''") {
            return &value[3..3 + end];
        }
    } else if (value.starts_with('"') && value.ends_with('"'))
        || (value.starts_with('\'') && value.ends_with('\''))
    {
        // Single-quoted string
        return &value[1..value.len() - 1];
    }
    // Not a string or unclosed string, return as-is
    value
}

/// Extract docstring from matched function text.
pub fn extract_docstring_from_text(text: &str) -> String {
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

/// Parse parameter names from function signature string.
pub fn parse_parameters(params_text: &str) -> Vec<String> {
    split_parameters(params_text)
        .iter()
        .filter_map(|s| {
            // Handle "param: Type" -> "param"
            let clean = if let Some(colon_pos) = s.find(':') {
                &s[..colon_pos]
            } else {
                s
            };
            // Handle "param=default" -> "param"
            let clean = clean.split('=').next().unwrap_or(clean);
            let clean = clean.trim();

            // Skip *args and **kwargs
            if clean.starts_with('*') && clean != "*" {
                None
            } else if !clean.is_empty() {
                Some(clean.to_string())
            } else {
                None
            }
        })
        .collect()
}

/// Split parameters respecting nested brackets and `|` unions in type annotations.
///
/// This handles cases like `dict[str, Any] | None` by not splitting on commas inside
/// type annotations with brackets.
fn split_parameters(params_text: &str) -> Vec<String> {
    let mut result = Vec::new();
    let mut current = String::new();
    let mut depth = 0usize;

    for c in params_text.chars() {
        if c == '(' {
            depth += 1;
            current.push(c);
        } else if c == ')' {
            if depth > 0 {
                depth -= 1;
            }
            current.push(c);
        } else if c == '[' {
            depth += 1;
            current.push(c);
        } else if c == ']' {
            if depth > 0 {
                depth -= 1;
            }
            current.push(c);
        } else if c == ',' && depth == 0 {
            // Only split on comma if not inside brackets
            let trimmed = current.trim().to_string();
            if !trimmed.is_empty() {
                result.push(trimmed);
            }
            current.clear();
        } else {
            current.push(c);
        }
    }

    // Don't forget the last parameter
    let trimmed = current.trim().to_string();
    if !trimmed.is_empty() {
        result.push(trimmed);
    }

    result
}

/// Represents a parsed parameter with its type annotation and default value info.
#[derive(Debug, Clone)]
pub struct ParsedParameter {
    /// Parameter name.
    pub name: String,
    /// Python type annotation (e.g., "str", "int", "list[str]").
    pub type_annotation: Option<String>,
    /// Whether the parameter has a default value.
    pub has_default: bool,
    /// Default value as a string (e.g., "10", "'default'", "None").
    pub default_value: Option<String>,
}

impl ParsedParameter {
    /// Check if this parameter is optional (has a default value).
    pub fn is_optional(&self) -> bool {
        self.has_default
    }

    /// Infer JSON Schema type from Python type annotation.
    pub fn infer_json_type(&self) -> serde_json::Value {
        let Some(ref type_str) = self.type_annotation else {
            return serde_json::json!("string");
        };

        let type_str = type_str.trim();

        // Handle Optional/Union with None
        if type_str.contains("Optional") || type_str.contains("| None") {
            // Return minimal schema for optional types
            return self.infer_base_json_type();
        }

        // Handle Literal types for enums
        if type_str.starts_with("Literal") {
            if let Some(start) = type_str.find('[') {
                if let Some(end) = type_str.rfind(']') {
                    let values_str = &type_str[start + 1..end];
                    let values: Vec<serde_json::Value> = values_str
                        .split(',')
                        .map(|v| {
                            let v = v.trim().trim_matches(|c| c == '"' || c == '\'');
                            serde_json::json!(v)
                        })
                        .collect();
                    return serde_json::json!({
                        "type": "string",
                        "enum": values
                    });
                }
            }
        }

        self.infer_base_json_type()
    }

    /// Infer JSON Schema type for base types (without Optional/Union wrapper).
    fn infer_base_json_type(&self) -> serde_json::Value {
        let type_str = self
            .type_annotation
            .as_ref()
            .map(|s| s.as_str())
            .unwrap_or("");

        // Handle generic types like list[str], dict[str, int], etc.
        if type_str.starts_with("list[") || type_str.starts_with("List[") {
            let inner = if let Some(start) = type_str.find('[') {
                if let Some(end) = type_str.rfind(']') {
                    &type_str[start + 1..end]
                } else {
                    "string"
                }
            } else {
                "string"
            };

            let inner_type = match inner.trim() {
                "str" | "string" => "string",
                "int" | "integer" => "integer",
                "float" | "number" => "number",
                "bool" | "boolean" => "boolean",
                _ => "string",
            };

            return serde_json::json!({
                "type": "array",
                "items": { "type": inner_type }
            });
        }

        // Handle dict types like dict[str, str], Dict[str, int], etc.
        if type_str.starts_with("dict[") || type_str.starts_with("Dict[") {
            return serde_json::json!({
                "type": "object",
                "additionalProperties": true
            });
        }

        // Handle basic types
        let normalized = type_str.to_lowercase();
        match normalized.as_str() {
            "str" | "string" => serde_json::json!("string"),
            "int" | "integer" => serde_json::json!("integer"),
            "float" | "number" => serde_json::json!("number"),
            "bool" | "boolean" => serde_json::json!("boolean"),
            _ => serde_json::json!("string"),
        }
    }

    /// Generate JSON Schema property for this parameter.
    pub fn to_json_schema_property(&self) -> serde_json::Value {
        let mut schema = serde_json::Map::new();

        // Add type
        let json_type = self.infer_json_type();
        schema.insert("type".to_string(), json_type);

        // Add description from docstring if available
        // (Description is added separately in generate_input_schema)

        // Add default value if present
        if let Some(ref default) = self.default_value {
            // Only add default if it's not None
            if default != "None" {
                schema.insert("default".to_string(), serde_json::json!(default));
            }
        }

        serde_json::Value::Object(schema)
    }
}

/// Extract parameter names from full function signature text.
pub fn extract_parameters_from_text(func_text: &str) -> Vec<String> {
    // Find the parameter list between parentheses, handling nested parentheses
    if let Some(open_paren) = func_text.find('(') {
        let mut depth = 1;
        let mut close_paren = None;
        let search_content = &func_text[open_paren + 1..];

        for (i, c) in search_content.char_indices() {
            if c == '(' {
                depth += 1;
            } else if c == ')' {
                depth -= 1;
                if depth == 0 {
                    close_paren = Some(open_paren + 1 + i);
                    break;
                }
            }
        }

        if let Some(end_pos) = close_paren {
            let params_text = &func_text[open_paren + 1..end_pos];
            return parse_parameters(params_text);
        }
    }
    Vec::new()
}

/// Extract detailed parameter information from function signature text.
///
/// Returns a vector of ParsedParameter with name, type, default info.
pub fn extract_parsed_parameters(func_text: &str) -> Vec<ParsedParameter> {
    // Find the parameter list between parentheses, handling nested parentheses
    if let Some(open_paren) = func_text.find('(') {
        let mut depth = 1;
        let mut close_paren = None;
        let search_content = &func_text[open_paren + 1..];

        for (i, c) in search_content.char_indices() {
            if c == '(' {
                depth += 1;
            } else if c == ')' {
                depth -= 1;
                if depth == 0 {
                    close_paren = Some(open_paren + 1 + i);
                    break;
                }
            }
        }

        if let Some(end_pos) = close_paren {
            let params_text = &func_text[open_paren + 1..end_pos];
            return parse_detailed_parameters(params_text);
        }
    }
    Vec::new()
}

/// Parse detailed parameter information from parameter text.
fn parse_detailed_parameters(params_text: &str) -> Vec<ParsedParameter> {
    split_parameters(params_text)
        .iter()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .filter_map(|s| {
            // Parse "param: Type = default" format

            // Check for *args and **kwargs
            if s.starts_with("*") && s != "*" {
                return None;
            }

            // Split on default value "="
            let (before_eq, default_str) = if let Some(eq_pos) = s.find('=') {
                (&s[..eq_pos], Some(s[eq_pos + 1..].trim().to_string()))
            } else {
                (s, None)
            };

            // Split on type annotation ":"
            let (name, type_str) = if let Some(colon_pos) = before_eq.find(':') {
                let name_part = before_eq[..colon_pos].trim();
                let type_part = before_eq[colon_pos + 1..].trim().to_string();
                (name_part.to_string(), Some(type_part))
            } else {
                (before_eq.trim().to_string(), None)
            };

            let has_default = default_str.is_some();

            if name.is_empty() {
                None
            } else {
                Some(ParsedParameter {
                    name: name.to_string(),
                    type_annotation: type_str,
                    has_default,
                    default_value: default_str,
                })
            }
        })
        .filter(|p| !p.name.starts_with('*'))
        .collect()
}

/// Extract parameter descriptions from decorator description text.
///
/// Supports Google-style docstring format:
/// ```python
/// """
/// Tool description.
///
/// Args:
///     - query: str - The search query (required)
///     - limit: int - Maximum number of results
///
/// Returns:
///     List of results
/// """
/// ```
///
/// Returns a HashMap mapping parameter name to its description.
pub fn extract_param_descriptions(description: &str) -> std::collections::HashMap<String, String> {
    let mut result = std::collections::HashMap::new();

    // Find the Args section
    let args_start = description.find("Args:");
    if args_start.is_none() {
        return result;
    }

    let args_section = &description[args_start.unwrap()..];

    // Parse each parameter line: "- param_name: type - description"
    // or "- param_name: description"
    for line in args_section.lines() {
        let trimmed = line.trim();

        // Check if line starts with "- " or "• " (bullet point)
        if !trimmed.starts_with("- ") && !trimmed.starts_with("• ") {
            continue;
        }

        // Remove bullet point
        let content = if trimmed.starts_with("- ") {
            &trimmed[2..]
        } else {
            &trimmed[2..]
        };

        // Find the first colon to separate param name from description
        if let Some(colon_pos) = content.find(':') {
            let param_name = content[..colon_pos].trim();

            // Skip if param_name looks like a type (starts with capital or contains space)
            if param_name.is_empty()
                || param_name.contains(' ')
                || param_name
                    .chars()
                    .next()
                    .map_or(false, |c| c.is_uppercase())
            {
                continue;
            }

            // Get everything after the colon
            let after_colon = &content[colon_pos + 1..].trim();

            // Extract description after type and separator (- or —)
            let description =
                if let Some(sep_pos) = after_colon.find(|c| c == '-' || c == '—' || c == '–') {
                    let desc = &after_colon[sep_pos + 1..].trim();
                    // Clean up trailing newlines and whitespace
                    desc.trim().to_string()
                } else {
                    after_colon.to_string()
                };

            if !description.is_empty() {
                result.insert(param_name.to_string(), description);
            }
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_decorator_simple() {
        let decorator = r#"@skill_command(name="test", description="A test")"#;
        let args = parse_decorator_args(decorator);
        assert_eq!(args.name, Some("test".to_string()));
        assert_eq!(args.description, Some("A test".to_string()));
    }

    #[test]
    fn test_parse_decorator_triple_quote() {
        let decorator = r#"@skill_command(name="test", description="""A multi-line
description""")"#;
        let args = parse_decorator_args(decorator);
        assert_eq!(args.name, Some("test".to_string()));
        assert!(args.description.unwrap().contains("multi-line"));
    }

    #[test]
    fn test_extract_docstring() {
        let text = r#"def test():
    """This is a docstring."""
    pass"#;
        let doc = extract_docstring_from_text(text);
        assert_eq!(doc, "This is a docstring.");
    }

    #[test]
    fn test_parse_parameters() {
        let params = parse_parameters("a: str, b: int, c = None");
        assert_eq!(params, vec!["a", "b", "c"]);
    }

    #[test]
    fn test_parse_parameters_with_types() {
        let params = parse_parameters("content: str, mode: WriteMode = WriteMode::default()");
        assert_eq!(params, vec!["content", "mode"]);
    }

    #[test]
    fn test_extract_parameters_from_text() {
        let text = "def test(a: str, b: int) -> str: pass";
        let params = extract_parameters_from_text(text);
        assert_eq!(params, vec!["a", "b"]);
    }

    #[test]
    fn test_extract_param_descriptions() {
        let description = r#"
Tool description.

Args:
    - query: str - The search query to use (required)
    - limit: int - Maximum number of results (optional)
    - session_id: str - Optional session ID

Returns:
    List of results
"#;
        let params = extract_param_descriptions(description);

        assert_eq!(
            params.get("query"),
            Some(&"The search query to use (required)".to_string())
        );
        assert_eq!(
            params.get("limit"),
            Some(&"Maximum number of results (optional)".to_string())
        );
        assert_eq!(
            params.get("session_id"),
            Some(&"Optional session ID".to_string())
        );
        assert!(!params.contains_key("Returns")); // Not a parameter
    }

    #[test]
    fn test_extract_param_descriptions_no_args() {
        let description = "Tool description without Args section.";
        let params = extract_param_descriptions(description);
        assert!(params.is_empty());
    }

    #[test]
    fn test_find_skill_command_decorators() {
        let content = r#"
@skill_command(name="test1")
def foo():
    pass

@skill_command(name="test2")
def bar():
    pass
"#;
        let decs = find_skill_command_decorators(content);
        assert_eq!(decs.len(), 2);
    }
}

#[test]
fn test_extract_parameters_with_nested_parens() {
    // Test with type annotations containing parentheses like str | None
    let text = r#"def save_memory(content: str | None, metadata: dict[str, Any] | None) -> bool:"#;
    let params = extract_parameters_from_text(text);
    assert_eq!(params, vec!["content", "metadata"]);
}

#[test]
fn test_extract_param_descriptions_real_decorator_format() {
    // This is the actual format from commit.py decorator
    let description = r#"
    Commit staged changes with a message.

    Args:
        - message: str - The commit message for the changes (required)

    Returns:
        Success or failure message with commit hash.
    "#;

    let params = extract_param_descriptions(description);

    println!("Extracted params: {:?}", params);

    assert_eq!(
        params.get("message"),
        Some(&"The commit message for the changes (required)".to_string())
    );
}

#[test]
fn test_parse_decorator_skill_discover_real() {
    // This tests the actual skill.discover decorator from assets/skills/skill/scripts/discovery.py
    // The decorator has a complex multi-line description with commas
    let decorator = r#"@skill_command(
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
)"#;

    let args = parse_decorator_args(decorator);
    assert_eq!(args.name, Some("discover".to_string()));
    assert_eq!(args.category, Some("system".to_string()));
    assert!(args.description.is_some(), "description should be Some");
    let desc = args.description.unwrap();
    assert!(
        desc.contains("CRITICAL"),
        "description should contain CRITICAL"
    );
    assert!(
        desc.contains("INTENT MAPPING"),
        "description should contain INTENT MAPPING"
    );
    assert!(
        desc.contains("CORE RESPONSIBILITIES"),
        "description should contain CORE RESPONSIBILITIES"
    );
}
