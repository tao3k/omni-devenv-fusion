use std::time::{Duration, Instant};

use super::super::TelegramChannel;
use super::super::constants::{
    TELEGRAM_SEND_RATE_LIMIT_SPREAD_MAX_MS, TELEGRAM_SEND_RATE_LIMIT_SPREAD_STEP_MS,
};
use super::super::error::TelegramApiError;

impl TelegramChannel {
    pub(in crate::channels::telegram::channel) async fn wait_for_send_rate_limit_gate(
        &self,
        method: &str,
        request_kind: &str,
    ) {
        loop {
            if let Some((delay, spread_slot, spread_delay_ms)) =
                self.next_local_send_gate_wait().await
            {
                tracing::debug!(
                    method,
                    request_kind,
                    gate_source = "local",
                    gate_wait_ms = delay.as_millis(),
                    spread_slot,
                    spread_delay_ms,
                    "Telegram send gate active; waiting before request"
                );
                tokio::time::sleep(delay).await;
                continue;
            }

            let Some(backend) = self.send_rate_limit_backend.valkey() else {
                return;
            };

            let distributed_window = match backend.current_window_with_spread_slot().await {
                Ok(window) => window,
                Err(error) => {
                    tracing::warn!(
                        method,
                        request_kind,
                        gate_source = "valkey",
                        error = %error,
                        "failed to query distributed telegram send gate; proceeding without remote wait"
                    );
                    return;
                }
            };
            let Some((window_delay, spread_slot)) = distributed_window else {
                return;
            };

            let spread_delay_ms = TELEGRAM_SEND_RATE_LIMIT_SPREAD_STEP_MS
                .saturating_mul(spread_slot)
                .min(TELEGRAM_SEND_RATE_LIMIT_SPREAD_MAX_MS);
            let total_delay = window_delay + Duration::from_millis(spread_delay_ms);

            {
                let mut gate = self.send_rate_limit_gate.lock().await;
                gate.until = Some(Instant::now() + window_delay);
                gate.spread_slots_issued = 0;
            }

            tracing::debug!(
                method,
                request_kind,
                gate_source = "valkey",
                gate_wait_ms = total_delay.as_millis(),
                spread_slot,
                spread_delay_ms,
                "Telegram distributed send gate active; waiting before request"
            );
            tokio::time::sleep(total_delay).await;
        }
    }

    pub(in crate::channels::telegram::channel) async fn update_send_rate_limit_gate_from_error(
        &self,
        error: &TelegramApiError,
        delay: Duration,
        method: &str,
        request_kind: &str,
    ) {
        if !error.is_rate_limited() || delay.is_zero() {
            return;
        }

        self.update_local_send_rate_limit_gate(delay, method, request_kind, error)
            .await;

        let Some(backend) = self.send_rate_limit_backend.valkey() else {
            return;
        };
        match backend.extend_window(delay).await {
            Ok(Some(distributed_delay)) => {
                self.update_local_send_rate_limit_gate(
                    distributed_delay,
                    method,
                    request_kind,
                    error,
                )
                .await;
                tracing::debug!(
                    method,
                    request_kind,
                    gate_source = "valkey",
                    retry_after_ms = distributed_delay.as_millis(),
                    "Telegram distributed send gate synchronized from rate limit response"
                );
            }
            Ok(None) => {}
            Err(distributed_error) => {
                tracing::warn!(
                    method,
                    request_kind,
                    gate_source = "valkey",
                    error = %distributed_error,
                    "failed to update distributed telegram send gate from rate limit response"
                );
            }
        }
    }

    async fn next_local_send_gate_wait(&self) -> Option<(Duration, u32, u64)> {
        let mut gate = self.send_rate_limit_gate.lock().await;
        match gate.until {
            Some(deadline) => {
                let now = Instant::now();
                if deadline <= now {
                    gate.until = None;
                    gate.spread_slots_issued = 0;
                    None
                } else {
                    let spread_slot = gate.spread_slots_issued;
                    gate.spread_slots_issued = gate.spread_slots_issued.saturating_add(1);
                    let spread_delay_ms = TELEGRAM_SEND_RATE_LIMIT_SPREAD_STEP_MS
                        .saturating_mul(u64::from(spread_slot))
                        .min(TELEGRAM_SEND_RATE_LIMIT_SPREAD_MAX_MS);
                    let wait_duration =
                        deadline.duration_since(now) + Duration::from_millis(spread_delay_ms);
                    Some((wait_duration, spread_slot, spread_delay_ms))
                }
            }
            None => None,
        }
    }

    async fn update_local_send_rate_limit_gate(
        &self,
        delay: Duration,
        method: &str,
        request_kind: &str,
        error: &TelegramApiError,
    ) {
        let now = Instant::now();
        let next_deadline = now + delay;
        let mut gate = self.send_rate_limit_gate.lock().await;
        let previous_wait_ms = gate
            .until
            .as_ref()
            .and_then(|deadline| deadline.checked_duration_since(now))
            .map(|remaining| remaining.as_millis())
            .unwrap_or_default();

        let should_update = match gate.until {
            Some(existing_deadline) => existing_deadline < next_deadline,
            None => true,
        };
        if !should_update {
            return;
        }

        gate.until = Some(next_deadline);
        gate.spread_slots_issued = 0;
        tracing::warn!(
            method,
            request_kind,
            gate_source = "local",
            retry_after_ms = delay.as_millis(),
            previous_wait_ms,
            error = %error,
            "Telegram send gate updated from rate limit response"
        );
    }
}
