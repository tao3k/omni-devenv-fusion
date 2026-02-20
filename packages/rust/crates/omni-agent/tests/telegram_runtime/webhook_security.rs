use anyhow::Result;

use crate::channels::telegram::{
    TelegramControlCommandPolicy, WebhookDedupBackend, WebhookDedupConfig,
};

use super::super::run_telegram_webhook_with_control_command_policy;
use super::build_agent;

#[tokio::test]
async fn runtime_webhook_requires_non_empty_secret_token() -> Result<()> {
    let agent = build_agent().await?;
    let error = run_telegram_webhook_with_control_command_policy(
        agent,
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        TelegramControlCommandPolicy::default(),
        "127.0.0.1:0",
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Memory,
            ttl_secs: 600,
        },
    )
    .await
    .expect_err("missing webhook secret should fail before starting runtime");

    assert!(
        error
            .to_string()
            .contains("requires a non-empty secret token"),
        "unexpected error: {error}"
    );
    Ok(())
}
