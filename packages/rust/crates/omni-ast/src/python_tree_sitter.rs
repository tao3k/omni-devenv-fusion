//! Tree-sitter based Python parser for robust decorator and function extraction.

use std::collections::HashMap;
use tree_sitter::{Language, Node, Parser, Query, QueryCursor, StreamingIterator};

/// Tree-sitter based Python parser
pub struct TreeSitterPythonParser {
    parser: Parser,
    language: Language,
}

impl TreeSitterPythonParser {
    /// Create a new parser
    pub fn new() -> Self {
        let language: Language = tree_sitter_python::LANGUAGE.into();
        let mut parser = Parser::new();
        parser
            .set_language(&language)
            .expect("Failed to set Python language");
        Self { parser, language }
    }

    /// Find all decorated functions with a specific decorator name
    pub fn find_decorated_functions(
        &mut self,
        code: &str,
        decorator_name: &str,
    ) -> Vec<DecoratedFunction> {
        let tree = match self.parser.parse(code, None) {
            Some(t) => t,
            None => return Vec::new(),
        };

        let mut functions = Vec::new();

        let query = match Query::new(&self.language, "(function_definition) @func") {
            Ok(q) => q,
            Err(_) => return Vec::new(),
        };

        let root = tree.root_node();
        let mut cursor = QueryCursor::new();

        // QueryMatches implements StreamingIterator
        let capture_names = query.capture_names();
        let mut matches = cursor.matches(&query, root, code.as_bytes());
        while let Some(m) = matches.next() {
            for capture in m.captures {
                // Get capture name using index
                if let Some(capture_name) = capture_names.get(capture.index as usize) {
                    if *capture_name == "func" {
                        let func_node = capture.node;
                        if let Some(func) = self.parse_function(&func_node, code, decorator_name) {
                            // Only include functions that have the specified decorator
                            if func.decorator.is_some() {
                                functions.push(func);
                            }
                        }
                    }
                }
            }
        }

        functions
    }

    fn parse_function(
        &self,
        node: &Node,
        code: &str,
        decorator_name: &str,
    ) -> Option<DecoratedFunction> {
        let func_name = self.get_function_name(node, code);
        let params = self.get_parameters(node, code);
        let docstring = self.get_docstring(node, code);
        let text = node.utf8_text(code.as_bytes()).unwrap_or("").to_string();
        let decorator = self.find_decorator(node, code, decorator_name);

        Some(DecoratedFunction {
            name: func_name,
            parameters: params,
            docstring,
            text,
            decorator,
        })
    }

    fn get_function_name(&self, node: &Node, code: &str) -> String {
        let mut cursor = node.walk();
        if cursor.goto_first_child() {
            loop {
                let child = cursor.node();
                if child.kind() == "identifier" {
                    return child.utf8_text(code.as_bytes()).unwrap_or("").to_string();
                }
                if !cursor.goto_next_sibling() {
                    break;
                }
            }
        }
        String::new()
    }

    fn get_parameters(&self, node: &Node, code: &str) -> Vec<ParameterInfo> {
        let mut params = Vec::new();
        let mut cursor = node.walk();

        if cursor.goto_first_child() {
            loop {
                let child = cursor.node();
                if child.kind() == "parameters" {
                    self.extract_params(&child, code, &mut params);
                }
                if !cursor.goto_next_sibling() {
                    break;
                }
            }
        }
        params
    }

    fn extract_params(&self, node: &Node, code: &str, params: &mut Vec<ParameterInfo>) {
        let mut cursor = node.walk();

        // Walk through all children of the parameters node
        if cursor.goto_first_child() {
            loop {
                let child_node = cursor.node();
                let node_kind = child_node.kind();

                // Skip punctuation nodes
                if node_kind != "(" && node_kind != ")" && node_kind != "," {
                    // Try to extract parameter info from this child
                    let param_text = child_node.utf8_text(code.as_bytes()).unwrap_or("");

                    if matches!(
                        node_kind,
                        "typed_parameter"
                            | "default_parameter"
                            | "optional_parameter"
                            | "typed_default_parameter"
                            | "typed_optional_parameter"
                    ) {
                        self.parse_single_parameter(param_text, params);
                    }
                }

                if !cursor.goto_next_sibling() {
                    break;
                }
            }
        }
    }

    fn parse_single_parameter(&self, param_text: &str, params: &mut Vec<ParameterInfo>) {
        // Parse the parameter text to extract name, type, and default
        // Format: "name: type = default" or "name = default" or "name: type"

        let (name, type_annotation, default_value) = if let Some(colon_pos) = param_text.find(':') {
            let before_colon = &param_text[..colon_pos].trim();

            // Check for default before colon: "x = default: type"
            let mut eq_pos = None;
            let mut paren_depth = 0;
            for (i, c) in before_colon.chars().enumerate() {
                if c == '(' {
                    paren_depth += 1;
                } else if c == ')' {
                    if paren_depth > 0 {
                        paren_depth -= 1;
                    }
                } else if c == '=' && paren_depth == 0 {
                    eq_pos = Some(i);
                    break;
                }
            }

            if let Some(eq) = eq_pos {
                let n = before_colon[..eq].trim().to_string();
                let after_eq = &before_colon[eq + 1..].trim();
                let dv = Some(after_eq.to_string());
                let ta = Some(param_text[colon_pos + 1..].trim().to_string());
                (n, ta, dv)
            } else {
                let n = before_colon.to_string();
                let after_colon = &param_text[colon_pos + 1..].trim();

                // Check for default after type
                if let Some(eq_idx) = after_colon.find("= ") {
                    let ta = Some(after_colon[..eq_idx].trim().to_string());
                    let dv = Some(after_colon[eq_idx + 2..].trim().to_string());
                    (n, ta, dv)
                } else {
                    let ta = Some(after_colon.to_string());
                    (n, ta, None)
                }
            }
        } else if let Some(eq_pos) = param_text.find("= ") {
            let n = param_text[..eq_pos].trim().to_string();
            let dv = Some(param_text[eq_pos + 2..].trim().to_string());
            (n, None, dv)
        } else {
            let n = param_text.trim().to_string();
            (n, None, None)
        };

        params.push(ParameterInfo {
            name,
            type_annotation: type_annotation.filter(|s| !s.is_empty()),
            default_value: default_value.filter(|s| !s.is_empty()),
        });
    }

    fn get_docstring(&self, node: &Node, code: &str) -> String {
        let mut cursor = node.walk();

        if cursor.goto_first_child() {
            loop {
                let child = cursor.node();
                if child.kind() == "block" {
                    let mut block_cursor = child.walk();
                    if block_cursor.goto_first_child() {
                        loop {
                            let stmt = block_cursor.node();
                            if stmt.kind() == "expression_statement" {
                                let mut string_cursor = stmt.walk();
                                if string_cursor.goto_first_child() {
                                    let first = string_cursor.node();
                                    if first.kind() == "string" {
                                        let s = first.utf8_text(code.as_bytes()).unwrap_or("");
                                        return extract_string_content(s);
                                    }
                                }
                            }
                            if !block_cursor.goto_next_sibling() {
                                break;
                            }
                        }
                    }
                }
                if !cursor.goto_next_sibling() {
                    break;
                }
            }
        }
        String::new()
    }

    fn find_decorator(
        &self,
        func_node: &Node,
        code: &str,
        decorator_name: &str,
    ) -> Option<DecoratorInfo> {
        if let Some(parent) = func_node.parent() {
            let children: Vec<Node> = parent.children(&mut parent.walk()).collect();
            let func_index = children.iter().position(|n| n.id() == func_node.id())?;

            for i in (0..func_index).rev() {
                let child = &children[i];
                if child.kind() == "decorator" {
                    if let Some(info) = self.parse_decorator(child, code) {
                        if info.name == decorator_name {
                            return Some(info);
                        }
                    }
                }
            }
        }
        None
    }

    fn parse_decorator(&self, node: &Node, code: &str) -> Option<DecoratorInfo> {
        let decorator_text = node
            .utf8_text(code.as_bytes())
            .unwrap_or("")
            .trim_start_matches('@');

        if let Some(call_start) = decorator_text.find('(') {
            let name = &decorator_text[..call_start];
            let args_text = &decorator_text[call_start + 1..decorator_text.len().saturating_sub(1)];
            let args = parse_decorator_args(args_text);

            // Parse destructive and read_only as boolean values
            let destructive = args
                .get("destructive")
                .map(|v| v.trim().eq_ignore_ascii_case("True") || v.trim() == "true");
            let read_only = args
                .get("read_only")
                .map(|v| v.trim().eq_ignore_ascii_case("True") || v.trim() == "true");

            return Some(DecoratorInfo {
                name: name.to_string(),
                arguments: DecoratorArguments {
                    name: args.get("name").cloned(),
                    description: args.get("description").cloned(),
                    category: args.get("category").cloned(),
                    destructive,
                    read_only,
                },
            });
        }

        Some(DecoratorInfo {
            name: decorator_text.to_string(),
            arguments: DecoratorArguments::default(),
        })
    }
}

/// Parse decorator arguments string into a map
fn parse_decorator_args(args_text: &str) -> HashMap<String, String> {
    let mut result = HashMap::new();
    let mut current_key = String::new();
    let mut current_value = String::new();
    let mut in_string = false;
    let mut string_char = '\0';
    let mut depth: usize = 0;
    let mut saw_equals = false;
    let mut i = 0;

    let chars: Vec<char> = args_text.chars().collect();
    let len = chars.len();

    while i < len {
        let c = chars[i];

        if in_string {
            if c == string_char {
                if i + 2 < len {
                    let remaining: String = chars[i..].iter().collect();
                    if remaining.starts_with("\"\"\"") || remaining.starts_with("'''") {
                        in_string = false;
                        i += 2;
                        continue;
                    }
                }
                in_string = false;
            }
            current_value.push(c);
        } else {
            match c {
                '"' | '\'' => {
                    in_string = true;
                    string_char = c;
                    current_value.push(c);
                }
                '=' if i + 1 < len && chars[i + 1] != '=' => {
                    saw_equals = true;
                    i += 1;
                    continue;
                }
                ',' if depth == 0 => {
                    if !current_key.is_empty() {
                        let key = current_key.trim().to_string();
                        let value = extract_string_content(&current_value);
                        if !key.is_empty() {
                            result.insert(key, value);
                        }
                    }
                    current_key.clear();
                    current_value.clear();
                    saw_equals = false;
                }
                '(' | '{' | '[' => depth += 1,
                ')' | '}' | ']' => {
                    if depth > 0 {
                        depth -= 1;
                    }
                }
                _ => {
                    if depth == 0 {
                        if c == '=' {
                            saw_equals = true;
                        } else if c == ' ' {
                            // Skip spaces
                        } else if !saw_equals {
                            // Building the key
                            if c.is_alphanumeric() || c == '_' {
                                current_key.push(c);
                            }
                        } else {
                            // Building the value (after '=')
                            current_value.push(c);
                        }
                    } else {
                        current_value.push(c);
                    }
                }
            }
        }
        i += 1;
    }

    if !current_key.is_empty() {
        let key = current_key.trim().to_string();
        let value = extract_string_content(&current_value);
        if !key.is_empty() {
            result.insert(key, value);
        }
    }

    result
}

fn extract_string_content(s: &str) -> String {
    let trimmed = s.trim();
    if trimmed.starts_with("\"\"\"") && trimmed.ends_with("\"\"\"") {
        trimmed[3..trimmed.len() - 3].trim().to_string()
    } else if trimmed.starts_with("'''") && trimmed.ends_with("'''") {
        trimmed[3..trimmed.len() - 3].trim().to_string()
    } else if (trimmed.starts_with('"') && trimmed.ends_with('"'))
        || (trimmed.starts_with('\'') && trimmed.ends_with('\''))
    {
        trimmed[1..trimmed.len() - 1].to_string()
    } else {
        trimmed.to_string()
    }
}

/// Information about a decorated function
#[derive(Debug, Clone)]
pub struct DecoratedFunction {
    pub name: String,
    pub parameters: Vec<ParameterInfo>,
    pub docstring: String,
    pub text: String,
    pub decorator: Option<DecoratorInfo>,
}

/// Information about a decorator
#[derive(Debug, Clone, Default)]
pub struct DecoratorInfo {
    pub name: String,
    pub arguments: DecoratorArguments,
}

/// Decorator arguments
#[derive(Debug, Clone, Default)]
pub struct DecoratorArguments {
    pub name: Option<String>,
    pub description: Option<String>,
    pub category: Option<String>,
    pub destructive: Option<bool>,
    pub read_only: Option<bool>,
}

/// Information about a function parameter
#[derive(Debug, Clone)]
pub struct ParameterInfo {
    pub name: String,
    pub type_annotation: Option<String>,
    pub default_value: Option<String>,
}
