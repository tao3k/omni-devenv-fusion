//! Example: run the agent as HTTP gateway or stdio.
//!
//! MCP servers from **mcp.json** only (default `.mcp.json`). Use `--mcp-config <path>` to override.
//!
//! Subcommands:
//!   gateway  — HTTP server (POST /message). Default: --bind 0.0.0.0:8080
//!   stdio    — Read lines from stdin, run turn, print output. Optional --session-id
//!
//! Examples:
//!   cargo run -p omni-agent --example gateway -- gateway --bind 0.0.0.0:8080
//!   cargo run -p omni-agent --example gateway -- stdio --session-id s1

use std::path::PathBuf;

use omni_agent::{
    Agent, AgentConfig, DEFAULT_STDIO_SESSION_ID, load_mcp_config, run_http, run_stdio,
};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (mode, rest) = args
        .split_first()
        .map(|(m, r)| (m.as_str(), r))
        .unwrap_or(("gateway", &[][..]));
    match mode {
        "stdio" => {
            let (session_id, mcp_config_path) = parse_stdio_args(rest);
            run_stdio_mode(session_id, mcp_config_path).await
        }
        _ => {
            let (bind_addr, mcp_config_path) = parse_gateway_args(rest);
            run_gateway(bind_addr, mcp_config_path).await
        }
    }
}

fn parse_gateway_args(args: &[String]) -> (String, PathBuf) {
    let mut bind = "0.0.0.0:8080".to_string();
    let mut mcp_config = PathBuf::from(".mcp.json");
    let mut i = 0;
    while i < args.len() {
        if args[i] == "--bind" && i + 1 < args.len() {
            bind = args[i + 1].clone();
            i += 2;
            continue;
        }
        if args[i] == "--mcp-config" && i + 1 < args.len() {
            mcp_config = PathBuf::from(&args[i + 1]);
            i += 2;
            continue;
        }
        i += 1;
    }
    (bind, mcp_config)
}

fn parse_stdio_args(args: &[String]) -> (String, PathBuf) {
    let mut session_id = DEFAULT_STDIO_SESSION_ID.to_string();
    let mut mcp_config = PathBuf::from(".mcp.json");
    let mut i = 0;
    while i < args.len() {
        if args[i] == "--session-id" && i + 1 < args.len() {
            session_id = args[i + 1].clone();
            i += 2;
            continue;
        }
        if args[i] == "--mcp-config" && i + 1 < args.len() {
            mcp_config = PathBuf::from(&args[i + 1]);
            i += 2;
            continue;
        }
        i += 1;
    }
    (session_id, mcp_config)
}

async fn run_gateway(bind_addr: String, mcp_config_path: PathBuf) -> anyhow::Result<()> {
    let mcp_servers = load_mcp_config(&mcp_config_path)?;
    let config = AgentConfig {
        inference_url: std::env::var("LITELLM_PROXY_URL")
            .unwrap_or_else(|_| AgentConfig::default().inference_url),
        model: std::env::var("OMNI_AGENT_MODEL").unwrap_or_else(|_| AgentConfig::default().model),
        api_key: None,
        mcp_servers,
        max_tool_rounds: 10,
        ..AgentConfig::default()
    };
    let agent = Agent::from_config(config).await?;
    run_http(agent, &bind_addr, None, None).await
}

async fn run_stdio_mode(session_id: String, mcp_config_path: PathBuf) -> anyhow::Result<()> {
    let mcp_servers = load_mcp_config(&mcp_config_path)?;
    let config = AgentConfig {
        inference_url: std::env::var("LITELLM_PROXY_URL")
            .unwrap_or_else(|_| AgentConfig::default().inference_url),
        model: std::env::var("OMNI_AGENT_MODEL").unwrap_or_else(|_| AgentConfig::default().model),
        api_key: None,
        mcp_servers,
        max_tool_rounds: 10,
        ..AgentConfig::default()
    };
    let agent = Agent::from_config(config).await?;
    run_stdio(agent, session_id).await
}
