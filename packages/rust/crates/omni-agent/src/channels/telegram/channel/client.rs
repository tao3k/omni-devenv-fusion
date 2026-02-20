use std::time::Duration;

use super::constants::{TELEGRAM_HTTP_CONNECT_TIMEOUT_SECS, TELEGRAM_HTTP_REQUEST_TIMEOUT_SECS};

pub(super) fn build_telegram_http_client() -> reqwest::Client {
    match reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(TELEGRAM_HTTP_CONNECT_TIMEOUT_SECS))
        .timeout(Duration::from_secs(TELEGRAM_HTTP_REQUEST_TIMEOUT_SECS))
        .build()
    {
        Ok(client) => client,
        Err(error) => {
            tracing::warn!(
                error = %error,
                "Failed to build Telegram HTTP client with timeouts; falling back to default client"
            );
            reqwest::Client::new()
        }
    }
}
