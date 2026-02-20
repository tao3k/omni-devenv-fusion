#![allow(missing_docs)]

use std::net::TcpListener;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct MetricsResponse {
    enqueued: usize,
}

struct ChildGuard {
    child: Child,
}

impl ChildGuard {
    fn spawn(port: u16, valkey_url: &str, key_prefix: &str) -> Result<Self> {
        let bin = std::env::var("CARGO_BIN_EXE_webhook_dedup_probe")
            .context("CARGO_BIN_EXE_webhook_dedup_probe is not available")?;
        let child = Command::new(bin)
            .arg("--bind")
            .arg(format!("127.0.0.1:{port}"))
            .arg("--valkey-url")
            .arg(valkey_url)
            .arg("--key-prefix")
            .arg(key_prefix)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .context("failed to spawn webhook_dedup_probe process")?;
        Ok(Self { child })
    }
}

impl Drop for ChildGuard {
    fn drop(&mut self) {
        if let Ok(None) = self.child.try_wait() {
            let _ = self.child.kill();
            let _ = self.child.wait();
        }
    }
}

fn reserve_local_port() -> Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0").context("failed to reserve local port")?;
    let port = listener
        .local_addr()
        .context("failed to read reserved local port")?
        .port();
    Ok(port)
}

async fn wait_ready(client: &reqwest::Client, metrics_url: &str, timeout: Duration) -> Result<()> {
    let deadline = Instant::now() + timeout;
    loop {
        if Instant::now() >= deadline {
            anyhow::bail!("probe did not become ready at {metrics_url}");
        }

        match client.get(metrics_url).send().await {
            Ok(response) if response.status().is_success() => return Ok(()),
            Ok(_) | Err(_) => tokio::time::sleep(Duration::from_millis(40)).await,
        }
    }
}

async fn fetch_enqueued(client: &reqwest::Client, metrics_url: &str) -> Result<usize> {
    let response = client
        .get(metrics_url)
        .send()
        .await
        .with_context(|| format!("failed to fetch metrics from {metrics_url}"))?
        .error_for_status()
        .with_context(|| format!("non-success metrics response from {metrics_url}"))?;
    let metrics: MetricsResponse = response
        .json()
        .await
        .with_context(|| format!("failed to decode metrics from {metrics_url}"))?;
    Ok(metrics.enqueued)
}

async fn wait_total_enqueued(
    client: &reqwest::Client,
    metrics_url_a: &str,
    metrics_url_b: &str,
    timeout: Duration,
) -> Result<usize> {
    let deadline = Instant::now() + timeout;
    loop {
        if Instant::now() >= deadline {
            anyhow::bail!("timed out waiting for webhook enqueue result");
        }
        let total = fetch_enqueued(client, metrics_url_a).await?
            + fetch_enqueued(client, metrics_url_b).await?;
        if total >= 1 {
            return Ok(total);
        }
        tokio::time::sleep(Duration::from_millis(30)).await;
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
#[ignore = "requires live valkey server and process spawning support"]
async fn webhook_live_valkey_duplicate_update_id_across_two_processes_enqueues_once() -> Result<()>
{
    let Some(valkey_url) = std::env::var("VALKEY_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
    else {
        eprintln!("skip: set VALKEY_URL for live multi-process dedup test");
        return Ok(());
    };
    let key_prefix = format!(
        "omni-agent:test:dedup:multi-process:{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_micros()
    );

    let port_a = reserve_local_port()?;
    let port_b = reserve_local_port()?;
    let _probe_a = ChildGuard::spawn(port_a, &valkey_url, &key_prefix)?;
    let _probe_b = ChildGuard::spawn(port_b, &valkey_url, &key_prefix)?;

    let client = reqwest::Client::builder()
        .http1_only()
        .pool_max_idle_per_host(0)
        .build()?;

    let webhook_url_a = format!("http://127.0.0.1:{port_a}/telegram/webhook");
    let webhook_url_b = format!("http://127.0.0.1:{port_b}/telegram/webhook");
    let metrics_url_a = format!("http://127.0.0.1:{port_a}/metrics");
    let metrics_url_b = format!("http://127.0.0.1:{port_b}/metrics");

    wait_ready(&client, &metrics_url_a, Duration::from_secs(5)).await?;
    wait_ready(&client, &metrics_url_b, Duration::from_secs(5)).await?;

    let payload = serde_json::json!({
        "update_id": 94001,
        "message": {
            "message_id": 321,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    let (resp_a, resp_b) = tokio::join!(
        client.post(&webhook_url_a).json(&payload).send(),
        client.post(&webhook_url_b).json(&payload).send(),
    );
    assert_eq!(resp_a?.status(), reqwest::StatusCode::OK);
    assert_eq!(resp_b?.status(), reqwest::StatusCode::OK);

    let total = wait_total_enqueued(
        &client,
        &metrics_url_a,
        &metrics_url_b,
        Duration::from_secs(3),
    )
    .await?;
    assert_eq!(
        total, 1,
        "same update_id across two probe processes should enqueue exactly once globally"
    );

    tokio::time::sleep(Duration::from_millis(250)).await;
    let total_after = fetch_enqueued(&client, &metrics_url_a).await?
        + fetch_enqueued(&client, &metrics_url_b).await?;
    assert_eq!(
        total_after, 1,
        "duplicate update should remain globally deduplicated after short settle window"
    );
    Ok(())
}
