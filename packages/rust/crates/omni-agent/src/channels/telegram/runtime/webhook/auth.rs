use axum::http::{HeaderMap, StatusCode};

pub(super) const TELEGRAM_WEBHOOK_SECRET_HEADER: &str = "x-telegram-bot-api-secret-token";

pub(super) fn validate_secret_token(
    headers: &HeaderMap,
    expected_secret: Option<&str>,
) -> Result<(), (StatusCode, String)> {
    let Some(expected) = expected_secret else {
        return Ok(());
    };
    let provided = headers
        .get(TELEGRAM_WEBHOOK_SECRET_HEADER)
        .and_then(|v| v.to_str().ok())
        .unwrap_or_default();
    if provided == expected {
        Ok(())
    } else {
        Err((
            StatusCode::UNAUTHORIZED,
            "invalid telegram webhook secret token".to_string(),
        ))
    }
}
