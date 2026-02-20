//! LLM client: OpenAI-compatible chat completions (tool_calls supported).

use anyhow::Result;
use serde::{Deserialize, Serialize};

use crate::session::{ChatMessage, ToolCallOut};

/// Request body for chat completions (OpenAI format).
#[derive(Debug, Serialize)]
struct ChatCompletionRequest {
    model: String,
    messages: Vec<ChatMessage>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tools: Option<Vec<ToolDef>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_choice: Option<String>,
}

#[derive(Debug, Serialize)]
struct ToolDef {
    #[serde(rename = "type")]
    typ: String,
    function: FunctionDef,
}

#[derive(Debug, Serialize)]
struct FunctionDef {
    name: String,
    description: Option<String>,
    parameters: Option<serde_json::Value>,
}

/// Response: choices[0].message.
#[derive(Debug, Deserialize)]
pub struct ChatCompletionResponse {
    pub choices: Vec<Choice>,
}

#[derive(Debug, Deserialize)]
pub struct Choice {
    pub message: AssistantMessage,
    #[serde(skip_serializing_if = "Option::is_none")]
    #[allow(dead_code)]
    pub finish_reason: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct AssistantMessage {
    #[serde(default)]
    pub content: Option<String>,
    #[serde(default)]
    pub tool_calls: Option<Vec<ToolCallOut>>,
}

/// HTTP client for chat completions.
pub struct LlmClient {
    client: reqwest::Client,
    inference_url: String,
    model: String,
    api_key: Option<String>,
}

impl LlmClient {
    pub fn new(inference_url: String, model: String, api_key: Option<String>) -> Self {
        Self {
            client: reqwest::Client::new(),
            inference_url,
            model,
            api_key,
        }
    }

    /// Send messages and optionally tool definitions; returns content and/or tool_calls.
    pub async fn chat(
        &self,
        messages: Vec<ChatMessage>,
        tools_json: Option<Vec<serde_json::Value>>,
    ) -> Result<AssistantMessage> {
        let tools = tools_json.map(|list| {
            list.into_iter()
                .filter_map(|v| {
                    let name = v.get("name")?.as_str()?.to_string();
                    let description = v
                        .get("description")
                        .and_then(|d| d.as_str())
                        .map(String::from);
                    let parameters = v
                        .get("input_schema")
                        .cloned()
                        .or_else(|| v.get("parameters").cloned());
                    Some(ToolDef {
                        typ: "function".to_string(),
                        function: FunctionDef {
                            name,
                            description,
                            parameters,
                        },
                    })
                })
                .collect::<Vec<_>>()
        });
        let body = ChatCompletionRequest {
            model: self.model.clone(),
            messages,
            tool_choice: tools.as_ref().map(|_| "auto".to_string()),
            tools,
        };
        let mut req = self
            .client
            .post(&self.inference_url)
            .json(&body)
            .header("Content-Type", "application/json");
        if let Some(ref key) = self.api_key {
            req = req.header("Authorization", format!("Bearer {}", key));
        }
        let res = req.send().await?;
        let status = res.status();
        let text = res.text().await?;
        if !status.is_success() {
            return Err(anyhow::anyhow!("LLM API error {}: {}", status, text));
        }
        let parsed: ChatCompletionResponse = serde_json::from_str(&text)
            .map_err(|e| anyhow::anyhow!("LLM response parse error: {}; body: {}", e, text))?;
        let choice = parsed
            .choices
            .into_iter()
            .next()
            .ok_or_else(|| anyhow::anyhow!("LLM response has no choices"))?;
        Ok(choice.message)
    }
}
