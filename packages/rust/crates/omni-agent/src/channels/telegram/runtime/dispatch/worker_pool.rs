use std::sync::Arc;
use std::time::Instant;

use tokio::sync::{Semaphore, mpsc};
use tokio::task::JoinSet;

use crate::agent::Agent;
use crate::channels::managed_runtime::turn::build_session_id;
use crate::channels::telegram::runtime_config::TelegramRuntimeConfig;
use crate::channels::telegram::session_gate::SessionGate;
use crate::channels::traits::{Channel, ChannelMessage};

use super::turn::process_foreground_message;

pub(super) fn spawn_foreground_dispatcher(
    agent: Arc<Agent>,
    channel: Arc<dyn Channel>,
    mut rx: mpsc::Receiver<ChannelMessage>,
    runtime_config: TelegramRuntimeConfig,
    session_gate: SessionGate,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let semaphore = Arc::new(Semaphore::new(
            runtime_config.foreground_max_in_flight_messages,
        ));
        let mut workers = JoinSet::new();

        while let Some(msg) = rx.recv().await {
            let permit = match Arc::clone(&semaphore).acquire_owned().await {
                Ok(permit) => permit,
                Err(_) => break,
            };
            let worker_agent = Arc::clone(&agent);
            let worker_channel = Arc::clone(&channel);
            let worker_session_gate = session_gate.clone();
            workers.spawn(async move {
                let _permit = permit;
                let session_id = build_session_id(&msg.channel, &msg.session_key);
                let wait_started = Instant::now();
                let session_guard = worker_session_gate.acquire(&session_id).await;
                let _session_guard = match session_guard {
                    Ok(guard) => guard,
                    Err(error) => {
                        tracing::error!(
                            session_id = %session_id,
                            error = %error,
                            "failed to acquire session gate lock"
                        );
                        let _ = worker_channel
                            .send(
                                "Error: session lock unavailable; please retry.",
                                &msg.recipient,
                            )
                            .await;
                        return;
                    }
                };
                let wait_ms = wait_started.elapsed().as_millis();
                if wait_ms >= 50 {
                    tracing::debug!(
                        session_id = %session_id,
                        wait_ms,
                        "foreground worker waited for session lock"
                    );
                }
                process_foreground_message(
                    worker_agent,
                    worker_channel,
                    msg,
                    runtime_config.foreground_turn_timeout_secs,
                )
                .await;
            });

            while let Some(result) = workers.try_join_next() {
                if let Err(error) = result {
                    tracing::error!("foreground worker crashed: {error}");
                }
            }
        }

        while let Some(result) = workers.join_next().await {
            if let Err(error) = result {
                tracing::error!("foreground worker crashed: {error}");
            }
        }
    })
}
