use std::path::PathBuf;

use omni_agent::{RuntimeSettings, run_stdio};

use crate::agent_builder::build_agent;

pub(crate) async fn run_stdio_mode(
    session_id: String,
    mcp_config_path: PathBuf,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<()> {
    let agent = build_agent(&mcp_config_path, runtime_settings).await?;
    run_stdio(agent, session_id).await
}
