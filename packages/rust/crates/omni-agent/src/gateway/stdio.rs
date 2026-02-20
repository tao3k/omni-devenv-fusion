//! Stdio gateway: read line from stdin → run agent turn → print output.

use anyhow::Result;
use tokio::io::{AsyncBufReadExt, BufReader};

use crate::agent::Agent;

/// Default session ID when not overridden by flag.
pub const DEFAULT_STDIO_SESSION_ID: &str = "default";

/// Run stdio loop: read lines, run turn, print output. Exits on EOF or Ctrl+C.
///
/// * `agent` — the agent instance
/// * `session_id` — session ID for the conversation (e.g. from `--session-id`)
pub async fn run_stdio(agent: Agent, session_id: String) -> Result<()> {
    let mut reader = BufReader::new(tokio::io::stdin()).lines();
    while let Some(line) = reader.next_line().await? {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let out = agent.run_turn(&session_id, line).await?;
        println!("{}", out);
    }
    Ok(())
}
