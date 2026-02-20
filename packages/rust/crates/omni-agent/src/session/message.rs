//! Chat message types (OpenAI-compatible).

use serde::{Deserialize, Serialize};

/// One message in OpenAI-compatible chat format.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    /// Role: "system", "user", "assistant".
    pub role: String,
    /// Text content (none when tool_calls present).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub content: Option<String>,
    /// Assistant tool calls (when role is assistant).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_calls: Option<Vec<ToolCallOut>>,
    /// Tool call id for tool result messages.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_call_id: Option<String>,
    /// Tool name for tool result messages.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
}

/// Tool call from assistant message (OpenAI format).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolCallOut {
    /// Unique id for this tool call.
    pub id: String,
    /// Type (e.g. "function").
    #[serde(rename = "type")]
    pub typ: String,
    /// Function name and arguments.
    pub function: FunctionCall,
}

/// Function call payload.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FunctionCall {
    /// Tool/function name.
    pub name: String,
    /// JSON string of arguments.
    pub arguments: String,
}
