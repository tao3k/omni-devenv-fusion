use std::sync::Arc;

use anyhow::Result;
use tokio::sync::Mutex;

mod markdown_fallback;
mod routing;
mod server_bootstrap;
use server_bootstrap::spawn_media_api_server;

#[derive(Clone, Debug)]
pub struct MediaCall {
    pub method: String,
    pub payload: serde_json::Value,
}

#[derive(Clone, Default)]
pub struct MockTelegramMediaState {
    pub calls: Arc<Mutex<Vec<MediaCall>>>,
    pub fail_send_media_group_remaining: Arc<Mutex<usize>>,
    pub first_markdown_error: Arc<Mutex<Option<String>>>,
}

impl MockTelegramMediaState {
    fn with_failures_and_markdown_error(
        fail_send_media_group_times: usize,
        first_markdown_error: Option<&str>,
    ) -> Self {
        Self {
            calls: Arc::new(Mutex::new(Vec::new())),
            fail_send_media_group_remaining: Arc::new(Mutex::new(fail_send_media_group_times)),
            first_markdown_error: Arc::new(Mutex::new(
                first_markdown_error.map(std::string::ToString::to_string),
            )),
        }
    }
}

pub async fn spawn_mock_telegram_media_api_with_group_failure_and_markdown_error(
    fail_send_media_group_times: usize,
    first_markdown_error: Option<&str>,
) -> Result<Option<(String, MockTelegramMediaState, tokio::task::JoinHandle<()>)>> {
    let state = MockTelegramMediaState::with_failures_and_markdown_error(
        fail_send_media_group_times,
        first_markdown_error,
    );
    spawn_media_api_server(state).await
}

pub async fn spawn_mock_telegram_media_api()
-> Result<Option<(String, MockTelegramMediaState, tokio::task::JoinHandle<()>)>> {
    spawn_mock_telegram_media_api_with_group_failure_and_markdown_error(0, None).await
}

pub async fn spawn_mock_telegram_media_api_with_group_failure(
    fail_send_media_group_times: usize,
) -> Result<Option<(String, MockTelegramMediaState, tokio::task::JoinHandle<()>)>> {
    spawn_mock_telegram_media_api_with_group_failure_and_markdown_error(
        fail_send_media_group_times,
        None,
    )
    .await
}

pub async fn spawn_mock_telegram_media_api_with_markdown_error(
    first_markdown_error: Option<&str>,
) -> Result<Option<(String, MockTelegramMediaState, tokio::task::JoinHandle<()>)>> {
    spawn_mock_telegram_media_api_with_group_failure_and_markdown_error(0, first_markdown_error)
        .await
}
