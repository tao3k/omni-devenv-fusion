#![allow(missing_docs)]

use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};

use anyhow::Result;
use axum::{Json, Router, routing::get};
use clap::Parser;
use omni_agent::{WebhookDedupBackend, WebhookDedupConfig, build_telegram_webhook_app};
use tokio::net::TcpListener;
use tokio::sync::mpsc;

#[derive(Parser, Debug)]
#[command(about = "Webhook dedup probe server for process-level integration tests")]
struct Args {
    /// HTTP bind address for probe server.
    #[arg(long, default_value = "127.0.0.1:18181")]
    bind: String,
    /// Telegram webhook path.
    #[arg(long, default_value = "/telegram/webhook")]
    webhook_path: String,
    /// Valkey URL (Redis protocol).
    #[arg(long)]
    valkey_url: Option<String>,
    /// Shared dedup key prefix.
    #[arg(long, default_value = "omni-agent:test:dedup:probe")]
    key_prefix: String,
    /// Dedup TTL in seconds.
    #[arg(long, default_value_t = 600)]
    ttl_secs: u64,
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();
    let valkey_url = args
        .valkey_url
        .or_else(|| std::env::var("VALKEY_URL").ok())
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| anyhow::anyhow!("set --valkey-url or VALKEY_URL"))?
        .to_string();

    let (tx, mut rx) = mpsc::channel(1024);
    let webhook = build_telegram_webhook_app(
        "probe-token".to_string(),
        vec!["*".to_string()],
        vec![],
        &args.webhook_path,
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Redis {
                url: valkey_url,
                key_prefix: args.key_prefix,
            },
            ttl_secs: args.ttl_secs,
        },
        tx,
    )?;

    let enqueued = Arc::new(AtomicUsize::new(0));
    let enqueued_rx = Arc::clone(&enqueued);
    tokio::spawn(async move {
        while rx.recv().await.is_some() {
            enqueued_rx.fetch_add(1, Ordering::Relaxed);
        }
    });

    let enqueued_metrics = Arc::clone(&enqueued);
    let app: Router = webhook.app.route(
        "/metrics",
        get(move || {
            let enqueued = Arc::clone(&enqueued_metrics);
            async move { Json(serde_json::json!({ "enqueued": enqueued.load(Ordering::Relaxed) })) }
        }),
    );

    let listener = TcpListener::bind(&args.bind).await?;
    println!(
        "webhook_dedup_probe listening on {}{}",
        args.bind, webhook.path
    );

    axum::serve(listener, app)
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await?;
    Ok(())
}
