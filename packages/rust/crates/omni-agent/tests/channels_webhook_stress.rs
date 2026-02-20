#![allow(missing_docs)]

use std::collections::{HashMap, HashSet};
use std::time::{Duration, Instant};

use anyhow::Result;
use axum::{
    Router,
    body::Body,
    http::{Request, StatusCode},
};
use omni_agent::{
    TelegramSessionPartition, WebhookDedupBackend, WebhookDedupConfig, build_telegram_webhook_app,
    build_telegram_webhook_app_with_partition,
};
use tokio::sync::mpsc;
use tower::util::ServiceExt;

fn sample_update(update_id: i64, message_id: i64) -> serde_json::Value {
    serde_json::json!({
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    })
}

fn sample_update_for_user(
    update_id: i64,
    message_id: i64,
    chat_id: i64,
    user_id: i64,
) -> serde_json::Value {
    serde_json::json!({
        "update_id": update_id,
        "message": {
            "message_id": message_id,
            "text": "hello",
            "chat": {"id": chat_id},
            "from": {"id": user_id, "username": format!("u{user_id}")}
        }
    })
}

async fn post_update(app: Router, path: String, payload: serde_json::Value) -> Result<StatusCode> {
    let request = Request::builder()
        .method("POST")
        .uri(path)
        .header("content-type", "application/json")
        .body(Body::from(payload.to_string()))?;
    let response = app.oneshot(request).await?;
    Ok(response.status())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn webhook_concurrent_duplicate_update_id_enqueues_once() -> Result<()> {
    const CONCURRENCY: usize = 256;

    let (tx, mut rx) = mpsc::channel(512);
    let webhook = build_telegram_webhook_app(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Memory,
            ttl_secs: 600,
        },
        tx,
    )?;

    let start = Instant::now();
    let mut tasks = Vec::with_capacity(CONCURRENCY);
    for _ in 0..CONCURRENCY {
        let app = webhook.app.clone();
        let path = webhook.path.clone();
        tasks.push(tokio::spawn(async move {
            post_update(app, path, sample_update(90001, 77)).await
        }));
    }

    for task in tasks {
        assert_eq!(task.await??, StatusCode::OK);
    }
    let elapsed = start.elapsed();
    assert!(
        elapsed < Duration::from_secs(10),
        "duplicate stress took too long: {elapsed:?}"
    );

    let first = tokio::time::timeout(Duration::from_secs(1), rx.recv()).await?;
    assert!(first.is_some(), "first message should be enqueued");
    assert!(
        tokio::time::timeout(Duration::from_millis(200), rx.recv())
            .await
            .is_err(),
        "duplicate updates should not enqueue additional messages"
    );
    Ok(())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
#[ignore = "requires live valkey server and socket access"]
async fn webhook_live_valkey_concurrent_duplicate_update_id_enqueues_once() -> Result<()> {
    const CONCURRENCY: usize = 256;
    let Some(valkey_url) = std::env::var("VALKEY_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
    else {
        eprintln!("skip: set VALKEY_URL for live dedup stress test");
        return Ok(());
    };
    let unique_prefix = format!(
        "omni-agent:test:dedup:{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_micros()
    );

    let (tx, mut rx) = mpsc::channel(512);
    let webhook = build_telegram_webhook_app(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Redis {
                url: valkey_url,
                key_prefix: unique_prefix,
            },
            ttl_secs: 600,
        },
        tx,
    )?;

    let start = Instant::now();
    let mut tasks = Vec::with_capacity(CONCURRENCY);
    for _ in 0..CONCURRENCY {
        let app = webhook.app.clone();
        let path = webhook.path.clone();
        tasks.push(tokio::spawn(async move {
            post_update(app, path, sample_update(91001, 88)).await
        }));
    }
    for task in tasks {
        assert_eq!(task.await??, StatusCode::OK);
    }
    let elapsed = start.elapsed();
    assert!(
        elapsed < Duration::from_secs(10),
        "live valkey duplicate stress took too long: {elapsed:?}"
    );

    let first = tokio::time::timeout(Duration::from_secs(1), rx.recv()).await?;
    assert!(first.is_some(), "first message should be enqueued");
    assert!(
        tokio::time::timeout(Duration::from_millis(250), rx.recv())
            .await
            .is_err(),
        "duplicate updates should not enqueue additional messages with live valkey backend"
    );
    Ok(())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
#[ignore = "requires live valkey server and socket access"]
async fn webhook_live_valkey_duplicate_update_id_across_two_http_servers_enqueues_once()
-> Result<()> {
    let Some(valkey_url) = std::env::var("VALKEY_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
    else {
        eprintln!("skip: set VALKEY_URL for live dual-http dedup test");
        return Ok(());
    };
    let unique_prefix = format!(
        "omni-agent:test:dedup:multi-http:{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_micros()
    );

    let (tx_a, mut rx_a) = mpsc::channel(32);
    let webhook_a = build_telegram_webhook_app(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Redis {
                url: valkey_url.clone(),
                key_prefix: unique_prefix.clone(),
            },
            ttl_secs: 600,
        },
        tx_a,
    )?;

    let (tx_b, mut rx_b) = mpsc::channel(32);
    let webhook_b = build_telegram_webhook_app(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Redis {
                url: valkey_url,
                key_prefix: unique_prefix,
            },
            ttl_secs: 600,
        },
        tx_b,
    )?;

    let payload = sample_update(91501, 901);
    let (resp_a, resp_b) = tokio::join!(
        post_update(
            webhook_a.app.clone(),
            webhook_a.path.clone(),
            payload.clone()
        ),
        post_update(webhook_b.app.clone(), webhook_b.path.clone(), payload),
    );
    assert_eq!(resp_a?, StatusCode::OK);
    assert_eq!(resp_b?, StatusCode::OK);

    let first = tokio::time::timeout(Duration::from_secs(1), async {
        tokio::select! {
            msg = rx_a.recv() => msg,
            msg = rx_b.recv() => msg,
        }
    })
    .await?;
    assert!(first.is_some(), "first message should be enqueued");

    assert!(
        tokio::time::timeout(Duration::from_millis(250), async {
            tokio::select! {
                msg = rx_a.recv() => msg,
                msg = rx_b.recv() => msg,
            }
        })
        .await
        .is_err(),
        "duplicate updates across two HTTP webhook servers should enqueue exactly once"
    );
    Ok(())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn webhook_concurrent_unique_updates_enqueue_all() -> Result<()> {
    const REQUESTS: usize = 400;

    let (tx, mut rx) = mpsc::channel(REQUESTS + 64);
    let webhook = build_telegram_webhook_app(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Memory,
            ttl_secs: 600,
        },
        tx,
    )?;

    let start = Instant::now();
    let mut tasks = Vec::with_capacity(REQUESTS);
    for i in 0..REQUESTS {
        let app = webhook.app.clone();
        let path = webhook.path.clone();
        let update_id = 100_000 + i as i64;
        let message_id = 1_000 + i as i64;
        tasks.push(tokio::spawn(async move {
            post_update(app, path, sample_update(update_id, message_id)).await
        }));
    }

    for task in tasks {
        assert_eq!(task.await??, StatusCode::OK);
    }
    let elapsed = start.elapsed();
    assert!(
        elapsed < Duration::from_secs(10),
        "unique stress took too long: {elapsed:?}"
    );

    let mut seen_ids = HashSet::with_capacity(REQUESTS);
    for _ in 0..REQUESTS {
        let msg = tokio::time::timeout(Duration::from_secs(2), rx.recv())
            .await?
            .expect("expected queued message");
        seen_ids.insert(msg.id);
    }

    assert_eq!(seen_ids.len(), REQUESTS, "all unique updates must enqueue");
    Ok(())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 8)]
#[ignore = "manual stress run"]
async fn webhook_manual_heavy_stress_unique_updates() -> Result<()> {
    const REQUESTS: usize = 2_000;

    let (tx, mut rx) = mpsc::channel(REQUESTS + 128);
    let webhook = build_telegram_webhook_app(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Memory,
            ttl_secs: 600,
        },
        tx,
    )?;

    let mut tasks = Vec::with_capacity(REQUESTS);
    for i in 0..REQUESTS {
        let app = webhook.app.clone();
        let path = webhook.path.clone();
        let update_id = 200_000 + i as i64;
        let message_id = 3_000 + i as i64;
        tasks.push(tokio::spawn(async move {
            post_update(app, path, sample_update(update_id, message_id)).await
        }));
    }

    for task in tasks {
        assert_eq!(task.await??, StatusCode::OK);
    }
    for _ in 0..REQUESTS {
        let _ = tokio::time::timeout(Duration::from_secs(5), rx.recv())
            .await?
            .expect("expected queued message");
    }
    Ok(())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 8)]
async fn webhook_concurrent_chat_user_partition_keeps_isolated_session_keys() -> Result<()> {
    const REQUESTS_PER_USER: usize = 200;
    const USER_A: i64 = 888;
    const USER_B: i64 = 999;
    const CHAT_ID: i64 = -200123;
    let total_requests = REQUESTS_PER_USER * 2;

    let (tx, mut rx) = mpsc::channel(total_requests + 64);
    let webhook = build_telegram_webhook_app_with_partition(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["*".to_string()],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Memory,
            ttl_secs: 600,
        },
        TelegramSessionPartition::ChatUser,
        tx,
    )?;

    let mut tasks = Vec::with_capacity(total_requests);
    for i in 0..REQUESTS_PER_USER {
        let app_a = webhook.app.clone();
        let path_a = webhook.path.clone();
        let update_id_a = 310_000 + i as i64;
        let message_id_a = 10_000 + i as i64;
        tasks.push(tokio::spawn(async move {
            post_update(
                app_a,
                path_a,
                sample_update_for_user(update_id_a, message_id_a, CHAT_ID, USER_A),
            )
            .await
        }));

        let app_b = webhook.app.clone();
        let path_b = webhook.path.clone();
        let update_id_b = 320_000 + i as i64;
        let message_id_b = 20_000 + i as i64;
        tasks.push(tokio::spawn(async move {
            post_update(
                app_b,
                path_b,
                sample_update_for_user(update_id_b, message_id_b, CHAT_ID, USER_B),
            )
            .await
        }));
    }

    for task in tasks {
        assert_eq!(task.await??, StatusCode::OK);
    }

    let mut per_session_counts: HashMap<String, usize> = HashMap::new();
    for _ in 0..total_requests {
        let msg = tokio::time::timeout(Duration::from_secs(2), rx.recv())
            .await?
            .expect("expected queued message");
        *per_session_counts.entry(msg.session_key).or_default() += 1;
    }

    let expected_a = format!("{CHAT_ID}:{USER_A}");
    let expected_b = format!("{CHAT_ID}:{USER_B}");
    assert_eq!(per_session_counts.len(), 2);
    assert_eq!(
        per_session_counts
            .get(&expected_a)
            .copied()
            .unwrap_or_default(),
        REQUESTS_PER_USER
    );
    assert_eq!(
        per_session_counts
            .get(&expected_b)
            .copied()
            .unwrap_or_default(),
        REQUESTS_PER_USER
    );
    Ok(())
}

#[tokio::test(flavor = "multi_thread", worker_threads = 8)]
#[ignore = "requires live valkey server"]
async fn webhook_live_valkey_chat_user_partition_keeps_isolated_session_keys() -> Result<()> {
    const REQUESTS_PER_USER: usize = 100;
    const USER_A: i64 = 888;
    const USER_B: i64 = 999;
    const CHAT_ID: i64 = -200123;
    let total_requests = REQUESTS_PER_USER * 2;

    let Some(valkey_url) = std::env::var("VALKEY_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
    else {
        eprintln!("skip: set VALKEY_URL for live chat-user session partition test");
        return Ok(());
    };
    let unique_prefix = format!(
        "omni-agent:test:session-partition:{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_micros()
    );

    let (tx, mut rx) = mpsc::channel(total_requests + 64);
    let webhook = build_telegram_webhook_app_with_partition(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        vec!["*".to_string()],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Redis {
                url: valkey_url,
                key_prefix: unique_prefix,
            },
            ttl_secs: 600,
        },
        TelegramSessionPartition::ChatUser,
        tx,
    )?;

    let mut tasks = Vec::with_capacity(total_requests);
    for i in 0..REQUESTS_PER_USER {
        let app_a = webhook.app.clone();
        let path_a = webhook.path.clone();
        let update_id_a = 410_000 + i as i64;
        let message_id_a = 30_000 + i as i64;
        tasks.push(tokio::spawn(async move {
            post_update(
                app_a,
                path_a,
                sample_update_for_user(update_id_a, message_id_a, CHAT_ID, USER_A),
            )
            .await
        }));

        let app_b = webhook.app.clone();
        let path_b = webhook.path.clone();
        let update_id_b = 420_000 + i as i64;
        let message_id_b = 40_000 + i as i64;
        tasks.push(tokio::spawn(async move {
            post_update(
                app_b,
                path_b,
                sample_update_for_user(update_id_b, message_id_b, CHAT_ID, USER_B),
            )
            .await
        }));
    }

    for task in tasks {
        assert_eq!(task.await??, StatusCode::OK);
    }

    let mut per_session_counts: HashMap<String, usize> = HashMap::new();
    for _ in 0..total_requests {
        let msg = tokio::time::timeout(Duration::from_secs(3), rx.recv())
            .await?
            .expect("expected queued message");
        *per_session_counts.entry(msg.session_key).or_default() += 1;
    }

    let expected_a = format!("{CHAT_ID}:{USER_A}");
    let expected_b = format!("{CHAT_ID}:{USER_B}");
    assert_eq!(per_session_counts.len(), 2);
    assert_eq!(
        per_session_counts
            .get(&expected_a)
            .copied()
            .unwrap_or_default(),
        REQUESTS_PER_USER
    );
    assert_eq!(
        per_session_counts
            .get(&expected_b)
            .copied()
            .unwrap_or_default(),
        REQUESTS_PER_USER
    );
    Ok(())
}
