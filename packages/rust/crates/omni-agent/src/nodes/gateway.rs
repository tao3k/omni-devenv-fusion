use std::path::PathBuf;

use omni_agent::{RuntimeSettings, run_http};

use crate::agent_builder::build_agent;

pub(crate) async fn run_gateway_mode(
    bind_addr: String,
    turn_timeout: Option<u64>,
    max_concurrent: Option<usize>,
    mcp_config_path: PathBuf,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<()> {
    let agent = build_agent(&mcp_config_path, runtime_settings).await?;
    run_http(agent, &bind_addr, turn_timeout, max_concurrent).await
}
