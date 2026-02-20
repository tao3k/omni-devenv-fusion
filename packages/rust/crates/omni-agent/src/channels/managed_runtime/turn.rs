use std::time::Duration;

use crate::agent::Agent;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum ForegroundTurnOutcome {
    Succeeded(String),
    Failed {
        reply: String,
        error_chain: String,
        error_kind: &'static str,
    },
    TimedOut {
        reply: String,
    },
}

pub(crate) fn build_session_id(channel: &str, session_key: &str) -> String {
    format!("{channel}:{session_key}")
}

pub(crate) async fn run_foreground_turn(
    agent: &Agent,
    session_id: &str,
    content: &str,
    timeout_secs: u64,
    timeout_reply: String,
) -> ForegroundTurnOutcome {
    let result = tokio::time::timeout(
        Duration::from_secs(timeout_secs),
        agent.run_turn(session_id, content),
    )
    .await;

    match result {
        Ok(Ok(output)) => ForegroundTurnOutcome::Succeeded(output),
        Ok(Err(error)) => {
            let error_chain = format!("{error:#}");
            let error_kind = classify_turn_error(&error_chain);
            ForegroundTurnOutcome::Failed {
                reply: format!("Error: {error}"),
                error_chain,
                error_kind,
            }
        }
        Err(_) => ForegroundTurnOutcome::TimedOut {
            reply: timeout_reply,
        },
    }
}

pub(crate) fn classify_turn_error(error: &str) -> &'static str {
    let e = error.to_ascii_lowercase();
    if e.contains("tools/list") {
        "mcp_tools_list"
    } else if e.contains("tools/call") {
        "mcp_tools_call"
    } else if e.contains("transport send error") || e.contains("error sending request") {
        "mcp_transport"
    } else if e.contains("mcp handshake timeout") || e.contains("connect failed") {
        "mcp_connect"
    } else if e.contains("llm") {
        "llm"
    } else {
        "unknown"
    }
}
