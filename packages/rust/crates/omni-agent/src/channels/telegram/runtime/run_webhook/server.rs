use anyhow::Result;
use axum::Router;
use tokio::net::TcpListener;
use tokio::sync::oneshot;

pub(super) struct WebhookServer {
    pub(super) shutdown_tx: oneshot::Sender<()>,
    pub(super) task: tokio::task::JoinHandle<std::io::Result<()>>,
}

pub(super) async fn start_webhook_server(bind_addr: &str, app: Router) -> Result<WebhookServer> {
    let listener = TcpListener::bind(bind_addr).await?;
    let (shutdown_tx, shutdown_rx) = oneshot::channel::<()>();
    let task = tokio::spawn(async move {
        axum::serve(listener, app)
            .with_graceful_shutdown(async {
                let _ = shutdown_rx.await;
            })
            .await
    });
    Ok(WebhookServer { shutdown_tx, task })
}

pub(super) async fn stop_webhook_server(webhook_server: WebhookServer) {
    let WebhookServer { shutdown_tx, task } = webhook_server;
    let _ = shutdown_tx.send(());
    let _ = task.await;
}

pub(super) async fn drain_finished_webhook_server(
    task: &mut tokio::task::JoinHandle<std::io::Result<()>>,
) -> bool {
    if !task.is_finished() {
        return false;
    }

    match task.await {
        Ok(Ok(())) => tracing::warn!("Telegram webhook server exited"),
        Ok(Err(error)) => tracing::error!("Telegram webhook server failed: {error}"),
        Err(error) => tracing::error!("Telegram webhook task join error: {error}"),
    }
    true
}
