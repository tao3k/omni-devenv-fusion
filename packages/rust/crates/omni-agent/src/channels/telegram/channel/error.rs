use std::time::Duration;

use reqwest::StatusCode;

use super::constants::{
    TELEGRAM_POLL_MAX_RATE_LIMIT_RETRY_SECS, TELEGRAM_SEND_RETRY_BASE_MS,
    TELEGRAM_SEND_RETRY_MAX_MS,
};

#[derive(Debug)]
pub(super) struct TelegramApiError {
    pub(super) status: Option<StatusCode>,
    pub(super) error_code: Option<i64>,
    pub(super) retry_after_secs: Option<u64>,
    pub(super) body: String,
}

impl TelegramApiError {
    pub(super) fn from_reqwest(err: reqwest::Error) -> Self {
        let body = if err.is_timeout() {
            format!("timed out: {err}")
        } else {
            err.to_string()
        };
        Self {
            status: None,
            error_code: None,
            retry_after_secs: None,
            body,
        }
    }

    pub(super) fn should_retry_without_parse_mode(&self) -> bool {
        let is_bad_request =
            self.status == Some(StatusCode::BAD_REQUEST) || self.error_code == Some(400);
        if !is_bad_request {
            return false;
        }

        let normalized = self.body.to_ascii_lowercase();
        normalized.contains("can't parse entities")
            || normalized.contains("can't parse")
            || normalized.contains("can't find end tag")
            || normalized.contains("unsupported start tag")
            || normalized.contains("wrong entity")
            || normalized.contains("markdown")
            || normalized.contains("html")
    }

    pub(super) fn should_retry_send(&self) -> bool {
        let retryable_status = match self.status {
            Some(status) => {
                status == StatusCode::TOO_MANY_REQUESTS
                    || status == StatusCode::REQUEST_TIMEOUT
                    || status.is_server_error()
            }
            None => true,
        };
        let retryable_code =
            matches!(self.error_code, Some(429)) || self.error_code.is_some_and(|code| code >= 500);
        retryable_status || retryable_code
    }

    pub(super) fn is_rate_limited(&self) -> bool {
        self.status == Some(StatusCode::TOO_MANY_REQUESTS) || self.error_code == Some(429)
    }

    pub(super) fn retry_delay(&self, attempt: usize) -> Duration {
        if let Some(retry_after_secs) = self.retry_after_secs {
            return Duration::from_secs(
                retry_after_secs.min(TELEGRAM_POLL_MAX_RATE_LIMIT_RETRY_SECS),
            );
        }
        let shift = attempt.min(10) as u32;
        let backoff_ms = TELEGRAM_SEND_RETRY_BASE_MS
            .saturating_mul(1_u64 << shift)
            .min(TELEGRAM_SEND_RETRY_MAX_MS);
        Duration::from_millis(backoff_ms)
    }
}

impl std::fmt::Display for TelegramApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match (self.status, self.error_code, self.retry_after_secs) {
            (Some(status), Some(code), Some(retry_after_secs)) => write!(
                f,
                "status={status}, error_code={code}, retry_after={retry_after_secs}s, body={}",
                self.body
            ),
            (Some(status), Some(code), None) => {
                write!(f, "status={status}, error_code={code}, body={}", self.body)
            }
            (Some(status), None, Some(retry_after_secs)) => write!(
                f,
                "status={status}, retry_after={retry_after_secs}s, body={}",
                self.body
            ),
            (Some(status), None, None) => write!(f, "status={status}, body={}", self.body),
            (None, Some(code), Some(retry_after_secs)) => write!(
                f,
                "error_code={code}, retry_after={retry_after_secs}s, body={}",
                self.body
            ),
            (None, Some(code), None) => write!(f, "error_code={code}, body={}", self.body),
            (None, None, Some(retry_after_secs)) => {
                write!(f, "retry_after={retry_after_secs}s, body={}", self.body)
            }
            (None, None, None) => write!(f, "{}", self.body),
        }
    }
}

impl std::error::Error for TelegramApiError {}

pub(super) fn telegram_api_error_retry_after_secs(data: &serde_json::Value) -> Option<u64> {
    data.get("parameters")
        .and_then(|v| v.get("retry_after"))
        .and_then(serde_json::Value::as_u64)
}

pub(super) fn telegram_api_error_code(data: &serde_json::Value) -> Option<i64> {
    data.get("error_code").and_then(serde_json::Value::as_i64)
}

pub(super) fn telegram_api_error_description<'a>(
    data: &'a serde_json::Value,
    fallback: &'a str,
) -> &'a str {
    data.get("description")
        .and_then(serde_json::Value::as_str)
        .filter(|s| !s.is_empty())
        .unwrap_or(fallback)
}
