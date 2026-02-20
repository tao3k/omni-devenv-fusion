use anyhow::{Result, anyhow};

pub(super) fn normalize_secret_token(secret_token: Option<String>) -> Result<String> {
    secret_token
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            anyhow!("telegram webhook requires a non-empty secret token for request authentication")
        })
}
