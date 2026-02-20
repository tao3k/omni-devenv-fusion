//! Integration tests for embedding client transport selection and fallback.

use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;

use anyhow::Result;
use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::post;
use axum::{Json, Router};
use omni_agent::EmbeddingClient;
use serde_json::json;

#[derive(Clone)]
struct EmbedTestState {
    http_delay: Duration,
    http_fail: bool,
    http_calls: Arc<AtomicUsize>,
    mcp_calls: Arc<AtomicUsize>,
}

async fn handle_embed_batch(
    State(state): State<EmbedTestState>,
) -> (StatusCode, Json<serde_json::Value>) {
    state.http_calls.fetch_add(1, Ordering::Relaxed);
    tokio::time::sleep(state.http_delay).await;
    if state.http_fail {
        return (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({
                "error": "embed backend unavailable"
            })),
        );
    }
    (
        StatusCode::OK,
        Json(json!({
            "vectors": [[1.0_f32, 1.0_f32]]
        })),
    )
}

async fn handle_mcp_embed(State(state): State<EmbedTestState>) -> Json<serde_json::Value> {
    state.mcp_calls.fetch_add(1, Ordering::Relaxed);
    Json(json!({
        "jsonrpc": "2.0",
        "id": "mcp-embed",
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": "{\"success\":true,\"vectors\":[[2.0,2.0]]}"
                }
            ]
        }
    }))
}

type SpawnedEmbeddingServer = (String, Arc<AtomicUsize>, Arc<AtomicUsize>);

async fn spawn_embedding_mock_server(
    http_delay: Duration,
    http_fail: bool,
) -> Result<Option<SpawnedEmbeddingServer>> {
    let http_calls = Arc::new(AtomicUsize::new(0));
    let mcp_calls = Arc::new(AtomicUsize::new(0));
    let state = EmbedTestState {
        http_delay,
        http_fail,
        http_calls: Arc::clone(&http_calls),
        mcp_calls: Arc::clone(&mcp_calls),
    };
    let app = Router::new()
        .route("/embed/batch", post(handle_embed_batch))
        .route("/messages/", post(handle_mcp_embed))
        .with_state(state);

    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping embedding client tests: local socket bind is not permitted");
            return Ok(None);
        }
        Err(err) => return Err(err.into()),
    };
    let addr = listener.local_addr()?;
    tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    Ok(Some((format!("http://{addr}"), http_calls, mcp_calls)))
}

#[tokio::test]
async fn embed_batch_prefers_http_primary_even_when_mcp_is_faster() -> Result<()> {
    let Some((base_url, http_calls, mcp_calls)) =
        spawn_embedding_mock_server(Duration::from_millis(900), false).await?
    else {
        return Ok(());
    };
    let client =
        EmbeddingClient::new_with_mcp_url(&base_url, 5, Some(format!("{base_url}/messages/")));
    let texts = vec!["hello".to_string()];
    let started = std::time::Instant::now();
    let vectors = client
        .embed_batch_with_model(&texts, None)
        .await
        .expect("expected embeddings from primary HTTP path");
    let elapsed = started.elapsed();

    assert_eq!(vectors, vec![vec![1.0, 1.0]]);
    assert!(
        elapsed >= Duration::from_millis(700),
        "expected HTTP-first completion, got elapsed={elapsed:?}"
    );
    assert_eq!(http_calls.load(Ordering::Relaxed), 1);
    assert_eq!(mcp_calls.load(Ordering::Relaxed), 0);
    Ok(())
}

#[tokio::test]
async fn embed_batch_falls_back_to_mcp_when_http_fails() -> Result<()> {
    let Some((base_url, http_calls, mcp_calls)) =
        spawn_embedding_mock_server(Duration::from_millis(5), true).await?
    else {
        return Ok(());
    };
    let client =
        EmbeddingClient::new_with_mcp_url(&base_url, 5, Some(format!("{base_url}/messages/")));
    let texts = vec!["hello".to_string()];
    let vectors = client
        .embed_batch_with_model(&texts, None)
        .await
        .expect("expected embeddings from MCP fallback path");
    assert_eq!(vectors, vec![vec![2.0, 2.0]]);
    assert_eq!(http_calls.load(Ordering::Relaxed), 1);
    assert_eq!(mcp_calls.load(Ordering::Relaxed), 1);
    Ok(())
}

#[tokio::test]
async fn embed_batch_falls_back_to_http_when_mcp_unconfigured() -> Result<()> {
    let Some((base_url, http_calls, mcp_calls)) =
        spawn_embedding_mock_server(Duration::from_millis(5), false).await?
    else {
        return Ok(());
    };
    let client = EmbeddingClient::new_with_mcp_url(&base_url, 5, None);
    let texts = vec!["hello".to_string()];
    let vectors = client
        .embed_batch_with_model(&texts, None)
        .await
        .expect("expected embeddings from http fallback path");
    assert_eq!(vectors, vec![vec![1.0, 1.0]]);
    assert_eq!(http_calls.load(Ordering::Relaxed), 1);
    assert_eq!(mcp_calls.load(Ordering::Relaxed), 0);
    Ok(())
}
