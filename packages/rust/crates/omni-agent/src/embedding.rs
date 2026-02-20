//! Embedding client for HTTP /embed/batch or MCP tools/call (embedding.embed_texts).
//!
//! Primary path is HTTP `/embed/batch`; MCP is fallback only.

use reqwest::Client;
use serde::Deserialize;
use std::time::{Duration, Instant};

#[derive(Deserialize)]
struct EmbedBatchResponse {
    vectors: Option<Vec<Vec<f32>>>,
}

#[derive(Deserialize)]
struct McpEmbedResult {
    #[serde(default)]
    success: bool,
    #[serde(default)]
    vectors: Vec<Vec<f32>>,
}

/// Embedding client: HTTP /embed/batch or MCP embedding.embed_texts.
pub struct EmbeddingClient {
    client: Client,
    base_url: String,
    mcp_url: Option<String>,
}

impl EmbeddingClient {
    pub fn new(base_url: &str, timeout_secs: u64) -> Self {
        let mcp_url = std::env::var("OMNI_MCP_EMBED_URL")
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty());
        Self::new_with_mcp_url(base_url, timeout_secs, mcp_url)
    }

    pub fn new_with_mcp_url(base_url: &str, timeout_secs: u64, mcp_url: Option<String>) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_secs))
            .build()
            .unwrap_or_default();
        Self {
            client,
            base_url: base_url.trim_end_matches('/').to_string(),
            mcp_url,
        }
    }

    /// Embed via HTTP /embed/batch.
    async fn embed_http(&self, texts: &[String], model: Option<&str>) -> Option<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Some(vec![]);
        }
        let started = Instant::now();
        let url = format!("{}/embed/batch", self.base_url);
        let mut body = serde_json::json!({ "texts": texts });
        if let Some(model) = model.map(str::trim).filter(|value| !value.is_empty()) {
            body["model"] = serde_json::Value::String(model.to_string());
        }
        let resp = match self.client.post(&url).json(&body).send().await {
            Ok(resp) => resp,
            Err(error) => {
                tracing::debug!(
                    event = "agent.embedding.http.request_failed",
                    url,
                    elapsed_ms = started.elapsed().as_millis(),
                    error = %error,
                    "embedding http request failed"
                );
                return None;
            }
        };
        if !resp.status().is_success() {
            tracing::debug!(
                event = "agent.embedding.http.non_success_status",
                status = %resp.status(),
                elapsed_ms = started.elapsed().as_millis(),
                "embedding http returned non-success status"
            );
            return None;
        }
        let data: EmbedBatchResponse = match resp.json().await {
            Ok(data) => data,
            Err(error) => {
                tracing::debug!(
                    event = "agent.embedding.http.decode_failed",
                    elapsed_ms = started.elapsed().as_millis(),
                    error = %error,
                    "embedding http response decode failed"
                );
                return None;
            }
        };
        let vectors = data.vectors;
        tracing::debug!(
            event = "agent.embedding.http.completed",
            elapsed_ms = started.elapsed().as_millis(),
            success = vectors.is_some(),
            "embedding http path completed"
        );
        vectors
    }

    /// Embed via MCP tools/call embedding.embed_texts.
    async fn embed_mcp(&self, texts: &[String]) -> Option<Vec<Vec<f32>>> {
        let url = self.mcp_url.as_ref()?;
        if texts.is_empty() {
            return Some(vec![]);
        }
        let started = Instant::now();
        let body = serde_json::json!({
            "jsonrpc": "2.0",
            "id": "mcp-embed",
            "method": "tools/call",
            "params": {
                "name": "embedding.embed_texts",
                "arguments": { "texts": texts }
            }
        });
        let resp = match self.client.post(url).json(&body).send().await {
            Ok(resp) => resp,
            Err(error) => {
                tracing::debug!(
                    event = "agent.embedding.mcp.request_failed",
                    url,
                    elapsed_ms = started.elapsed().as_millis(),
                    error = %error,
                    "embedding mcp request failed"
                );
                return None;
            }
        };
        if !resp.status().is_success() {
            tracing::debug!(
                event = "agent.embedding.mcp.non_success_status",
                status = %resp.status(),
                elapsed_ms = started.elapsed().as_millis(),
                "embedding mcp returned non-success status"
            );
            return None;
        }
        let result: serde_json::Value = match resp.json().await {
            Ok(result) => result,
            Err(error) => {
                tracing::debug!(
                    event = "agent.embedding.mcp.decode_failed",
                    elapsed_ms = started.elapsed().as_millis(),
                    error = %error,
                    "embedding mcp response decode failed"
                );
                return None;
            }
        };
        let content = result.get("result")?.get("content")?.as_array()?;
        let text = content.first()?.get("text")?.as_str()?;
        let data: McpEmbedResult = match serde_json::from_str(text) {
            Ok(data) => data,
            Err(error) => {
                tracing::debug!(
                    event = "agent.embedding.mcp.payload_parse_failed",
                    elapsed_ms = started.elapsed().as_millis(),
                    error = %error,
                    "embedding mcp payload parse failed"
                );
                return None;
            }
        };
        if data.success {
            tracing::debug!(
                event = "agent.embedding.mcp.completed",
                elapsed_ms = started.elapsed().as_millis(),
                success = true,
                vector_count = data.vectors.len(),
                "embedding mcp path completed"
            );
            Some(data.vectors)
        } else {
            tracing::debug!(
                event = "agent.embedding.mcp.completed",
                elapsed_ms = started.elapsed().as_millis(),
                success = false,
                vector_count = data.vectors.len(),
                "embedding mcp path completed without success"
            );
            None
        }
    }

    /// Embed texts with an optional embedding model hint.
    pub async fn embed_batch_with_model(
        &self,
        texts: &[String],
        model: Option<&str>,
    ) -> Option<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Some(vec![]);
        }
        let started = Instant::now();
        if let Some(vectors) = self.embed_http(texts, model).await {
            tracing::debug!(
                event = "agent.embedding.batch.completed",
                selected_source = "http",
                fallback_used = false,
                success = true,
                elapsed_ms = started.elapsed().as_millis(),
                "embedding batch completed on primary source"
            );
            return Some(vectors);
        }

        let fallback_result = self.embed_mcp(texts).await;
        tracing::debug!(
            event = "agent.embedding.batch.completed",
            selected_source = "http",
            fallback_used = true,
            success = fallback_result.is_some(),
            elapsed_ms = started.elapsed().as_millis(),
            "embedding batch completed after fallback source"
        );
        fallback_result
    }

    /// Embed single text with an optional embedding model hint.
    pub async fn embed_with_model(&self, text: &str, model: Option<&str>) -> Option<Vec<f32>> {
        let texts = [text.to_string()];
        self.embed_batch_with_model(&texts, model)
            .await
            .and_then(|b| b.into_iter().next())
    }
}
