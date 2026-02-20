use std::path::PathBuf;

use omni_agent::{RuntimeSettings, run_stdio};

use crate::agent_builder::build_agent;

pub(crate) async fn run_repl_mode(
    query: Option<String>,
    session_id: String,
    mcp_config_path: PathBuf,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<()> {
    let agent = build_agent(&mcp_config_path, runtime_settings).await?;
    if let Some(q) = query {
        let out = agent.run_turn(&session_id, q.trim()).await?;
        println!("{}", out);
        Ok(())
    } else {
        run_stdio(agent, session_id).await
    }
}
