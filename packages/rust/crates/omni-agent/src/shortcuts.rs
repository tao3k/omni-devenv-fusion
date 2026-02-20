//! Deterministic command-style shortcuts that map directly to MCP tool calls.

/// MCP tool name for web crawling.
pub const CRAWL_TOOL_NAME: &str = "crawl4ai.crawl_url";

/// Explicit REPL routing mode for workflow bridge shortcuts.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkflowBridgeMode {
    Graph,
    Omega,
}

impl WorkflowBridgeMode {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Graph => "graph",
            Self::Omega => "omega",
        }
    }
}

/// Parsed command-style graph bridge shortcut.
#[derive(Debug, Clone, PartialEq)]
pub struct GraphBridgeShortcut {
    /// Requested route mode.
    pub mode: WorkflowBridgeMode,
    /// Target MCP tool name (for example `researcher.run_research_graph`).
    pub tool_name: String,
    /// Optional JSON-object arguments forwarded to MCP tool call.
    pub arguments: Option<serde_json::Value>,
}

/// Parsed command-style crawl shortcut.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CrawlShortcut {
    /// Target page URL.
    pub url: String,
    /// Whether crawl4ai should fit/clean markdown output.
    pub fit_markdown: bool,
    /// Crawl depth (0 = single page in crawl4ai semantics).
    pub max_depth: u32,
    /// Optional crawl action (e.g. "crawl", "skeleton", "smart").
    pub action: Option<String>,
    /// Whether to include skeleton in result.
    pub return_skeleton: bool,
}

impl CrawlShortcut {
    /// Build MCP arguments payload for `crawl4ai.crawl_url`.
    pub fn to_arguments(&self) -> serde_json::Value {
        let mut args = serde_json::Map::new();
        args.insert(
            "url".to_string(),
            serde_json::Value::String(self.url.clone()),
        );
        args.insert(
            "fit_markdown".to_string(),
            serde_json::Value::Bool(self.fit_markdown),
        );
        args.insert(
            "max_depth".to_string(),
            serde_json::Value::Number(serde_json::Number::from(self.max_depth)),
        );
        if let Some(ref action) = self.action {
            args.insert(
                "action".to_string(),
                serde_json::Value::String(action.clone()),
            );
        }
        if self.return_skeleton {
            args.insert("return_skeleton".to_string(), serde_json::Value::Bool(true));
        }
        serde_json::Value::Object(args)
    }
}

/// Parse command-style crawl input:
/// `crawl <url> [--depth <n>] [--raw|--skeleton|--smart] [--fit-markdown|--no-fit-markdown] [--return-skeleton]`.
pub fn parse_crawl_shortcut(input: &str) -> Option<CrawlShortcut> {
    let mut parts = input.split_whitespace();
    let verb = parts.next()?;
    if !verb.eq_ignore_ascii_case("crawl") {
        return None;
    }
    let raw_url = parts.next()?;
    let url = raw_url.trim_matches(|c: char| {
        matches!(
            c,
            '"' | '\'' | '`' | '<' | '>' | '(' | ')' | '[' | ']' | '{' | '}' | ',' | ';'
        )
    });
    if !(url.starts_with("http://") || url.starts_with("https://")) {
        None
    } else {
        let mut shortcut = CrawlShortcut {
            url: url.to_string(),
            fit_markdown: true,
            max_depth: 1,
            action: None,
            return_skeleton: false,
        };
        let rest: Vec<&str> = parts.collect();
        let mut i = 0usize;
        while i < rest.len() {
            match rest[i] {
                "--depth" | "-d" => {
                    let value = *rest.get(i + 1)?;
                    let depth = value.parse::<u32>().ok()?;
                    shortcut.max_depth = depth;
                    i += 2;
                }
                "--raw" => {
                    shortcut.action = Some("crawl".to_string());
                    i += 1;
                }
                "--skeleton" => {
                    shortcut.action = Some("skeleton".to_string());
                    i += 1;
                }
                "--smart" => {
                    shortcut.action = Some("smart".to_string());
                    i += 1;
                }
                "--fit-markdown" => {
                    shortcut.fit_markdown = true;
                    i += 1;
                }
                "--no-fit-markdown" => {
                    shortcut.fit_markdown = false;
                    i += 1;
                }
                "--return-skeleton" => {
                    shortcut.return_skeleton = true;
                    i += 1;
                }
                _ => return None,
            }
        }
        Some(shortcut)
    }
}

/// Parse explicit REPL mode forcing regular ReAct path:
/// `react <message>`.
pub fn parse_react_shortcut(input: &str) -> Option<String> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return None;
    }

    let mut head_tail = trimmed.splitn(2, char::is_whitespace);
    let verb = head_tail.next()?;
    if !verb.eq_ignore_ascii_case("react") {
        return None;
    }

    let message = head_tail.next()?.trim();
    if message.is_empty() {
        return None;
    }
    Some(message.to_string())
}

/// Parse command-style graph bridge input:
/// `graph <tool_name> [<json_object_args>]`.
pub fn parse_graph_bridge_shortcut(input: &str) -> Option<GraphBridgeShortcut> {
    parse_workflow_bridge_shortcut(input)
        .filter(|shortcut| shortcut.mode == WorkflowBridgeMode::Graph)
}

/// Parse command-style workflow bridge input:
/// - `graph <tool_name> [<json_object_args>]`
/// - `omega <tool_name> [<json_object_args>]`
pub fn parse_workflow_bridge_shortcut(input: &str) -> Option<GraphBridgeShortcut> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        return None;
    }

    let mut head_tail = trimmed.splitn(2, char::is_whitespace);
    let verb = head_tail.next()?;
    let mode = if verb.eq_ignore_ascii_case("graph") {
        WorkflowBridgeMode::Graph
    } else if verb.eq_ignore_ascii_case("omega") {
        WorkflowBridgeMode::Omega
    } else {
        return None;
    };
    let remainder = head_tail.next()?.trim();
    if remainder.is_empty() {
        return None;
    }

    let mut tool_and_args = remainder.splitn(2, char::is_whitespace);
    let tool_name = tool_and_args.next()?.trim();
    if tool_name.is_empty() {
        return None;
    }
    let arguments = match tool_and_args.next().map(str::trim) {
        Some(raw) if !raw.is_empty() => {
            let parsed = serde_json::from_str::<serde_json::Value>(raw).ok()?;
            if !parsed.is_object() {
                return None;
            }
            Some(parsed)
        }
        _ => None,
    };

    Some(GraphBridgeShortcut {
        mode,
        tool_name: tool_name.to_string(),
        arguments,
    })
}
