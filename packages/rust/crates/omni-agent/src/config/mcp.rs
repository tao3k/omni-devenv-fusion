//! MCP config loader: read mcp.json only (no env fallback).

use anyhow::{Context, Result};
use serde::Deserialize;
use std::path::Path;

use super::agent::McpServerEntry;

/// Top-level mcp.json shape: { "mcpServers": { "<name>": { ... } } }.
#[derive(Debug, Deserialize)]
pub struct McpConfigFile {
    /// Map of server name to server config (http URL or stdio command/args).
    #[serde(rename = "mcpServers")]
    pub mcp_servers: Option<std::collections::HashMap<String, McpServerEntryFile>>,
}

/// Per-server entry in mcp.json (type "http" | "stdio").
#[derive(Debug, Deserialize)]
pub struct McpServerEntryFile {
    /// Transport type: "http" or "stdio".
    #[serde(rename = "type")]
    pub typ: Option<String>,
    /// For http: base URL (e.g. `http://127.0.0.1:3002`).
    pub url: Option<String>,
    /// For stdio: command to run (e.g. `omni`).
    pub command: Option<String>,
    /// For stdio: command arguments (e.g. `["mcp", "--transport", "stdio"]`).
    #[serde(default)]
    pub args: Vec<String>,
}

/// Load MCP server list from a config file. No env fallback.
///
/// Returns empty list if file is missing or has no mcpServers.
pub fn load_mcp_config(path: &Path) -> Result<Vec<McpServerEntry>> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    let bytes = std::fs::read(path).context("read mcp config file")?;
    let file: McpConfigFile = serde_json::from_slice(&bytes).context("parse mcp.json")?;
    let servers = file.mcp_servers.unwrap_or_default();
    let out: Vec<McpServerEntry> = servers
        .into_iter()
        .map(|(name, e)| file_entry_to_mcp_server_entry(name, e))
        .collect();
    Ok(out)
}

fn file_entry_to_mcp_server_entry(name: String, e: McpServerEntryFile) -> McpServerEntry {
    let typ = e.typ.as_deref().unwrap_or("http");
    if typ == "stdio" {
        McpServerEntry {
            name: name.clone(),
            url: None,
            command: e.command.or(Some("omni".to_string())),
            args: if e.args.is_empty() {
                Some(vec![
                    "mcp".to_string(),
                    "--transport".to_string(),
                    "stdio".to_string(),
                ])
            } else {
                Some(e.args)
            },
        }
    } else {
        // Preserve configured HTTP URL exactly (trim + remove trailing slash only).
        // This supports both legacy `/sse` endpoints and newer root/message routes.
        let url = e
            .url
            .map(|u| u.trim().trim_end_matches('/').to_string())
            .filter(|u| !u.is_empty());
        McpServerEntry {
            name,
            url,
            command: None,
            args: None,
        }
    }
}
