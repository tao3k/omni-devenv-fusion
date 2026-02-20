use super::state::TelegramWebhookState;

pub(super) async fn is_duplicate_update(state: &TelegramWebhookState, update_id: i64) -> bool {
    match state.deduplicator.is_duplicate(update_id).await {
        Ok(is_duplicate) => is_duplicate,
        Err(error) => {
            // Fail-open to avoid dropping legitimate updates when dedup backend is transiently unavailable.
            tracing::warn!("Webhook dedup check failed for update_id={update_id}: {error}");
            false
        }
    }
}
