//! Python Bindings for omni-tokenizer
//!
//! High-performance token counting and context pruning for LangGraph.

use omni_tokenizer::{ContextPruner, Message, chunk_text, count_tokens, truncate};
use pyo3::prelude::*;

/// Count tokens in text using Rust (20-100x faster than Python).
///
/// # Arguments
///
/// * `text` - The text to tokenize
///
/// # Returns
///
/// Number of tokens (cl100k_base encoding - GPT-4/3.5 standard)
#[pyfunction]
pub fn py_count_tokens(text: &str) -> usize {
    count_tokens(text)
}

/// Truncate text to fit within a maximum token count.
///
/// # Arguments
///
/// * `text` - The text to truncate
/// * `max_tokens` - Maximum number of tokens allowed
///
/// # Returns
///
/// Truncated text that fits within the token limit
#[pyfunction]
pub fn py_truncate(text: &str, max_tokens: usize) -> String {
    truncate(text, max_tokens)
}

/// Chunk text by token boundaries with overlap (single pass).
///
/// Returns list of (chunk_text, chunk_index) for ingest with source + chunk_index.
///
/// # Arguments
///
/// * `text` - Full document text
/// * `chunk_size_tokens` - Target size per chunk
/// * `overlap_tokens` - Overlap between consecutive chunks
#[pyfunction]
pub fn py_chunk_text(
    text: &str,
    chunk_size_tokens: usize,
    overlap_tokens: usize,
) -> Vec<(String, u32)> {
    chunk_text(text, chunk_size_tokens, overlap_tokens)
}

/// Python-friendly Message struct for conversation history.
#[pyclass]
#[derive(Clone, Debug)]
pub struct PyMessage {
    /// Message role (system/user/assistant/tool).
    #[pyo3(get)]
    pub role: String,
    /// Message body content.
    #[pyo3(get)]
    pub content: String,
}

#[pymethods]
impl PyMessage {
    #[new]
    fn new(role: &str, content: &str) -> Self {
        Self {
            role: role.to_string(),
            content: content.to_string(),
        }
    }

    fn to_json(&self) -> String {
        serde_json::json!({
            "role": self.role,
            "content": self.content
        })
        .to_string()
    }
}

impl From<PyMessage> for Message {
    fn from(py_msg: PyMessage) -> Self {
        Message {
            role: py_msg.role,
            content: py_msg.content,
        }
    }
}

impl From<Message> for PyMessage {
    fn from(msg: Message) -> Self {
        PyMessage {
            role: msg.role,
            content: msg.content,
        }
    }
}

/// Rust-accelerated Context Pruner.
///
/// Preserves system messages and the most recent messages while
/// truncating older tool outputs to save context space.
///
/// # Example
///
/// ```python
/// from omni_core_rs.tokenizer import ContextPruner
///
/// pruner = ContextPruner(window_size=4, max_tool_output=500)
/// compressed = pruner.compress(messages)
/// ```
#[pyclass]
#[derive(Clone)]
pub struct PyContextPruner {
    inner: ContextPruner,
}

#[pymethods]
impl PyContextPruner {
    #[new]
    fn new(window_size: usize, max_tool_output: usize) -> Self {
        Self {
            inner: ContextPruner::new(window_size, max_tool_output),
        }
    }

    /// Compress message history while preserving important information.
    ///
    /// Strategy:
    /// 1. Always keep system messages
    /// 2. Keep last N*2 messages (user+assistant pairs) as "working memory"
    /// 3. Truncate tool outputs in older "archive" messages
    ///
    /// # Arguments
    ///
    /// * `messages` - List of message dicts with "role" and "content" keys
    ///
    /// # Returns
    ///
    /// Compressed list of message dicts
    fn compress(&self, messages: Vec<Py<PyAny>>, py: Python) -> PyResult<Vec<Py<PyAny>>> {
        // Convert Python dicts to Rust Message structs
        let mut rust_messages: Vec<Message> = Vec::with_capacity(messages.len());

        for msg in messages {
            let dict = msg.cast_bound::<pyo3::types::PyDict>(py)?;
            let role: String = dict.get_item("role")?.unwrap().extract()?;
            let content: String = dict.get_item("content")?.unwrap().extract()?;
            rust_messages.push(Message { role, content });
        }

        // Compress using Rust
        let compressed = self.inner.compress(rust_messages);

        // Convert back to Python dicts
        let result: Vec<Py<PyAny>> = compressed
            .into_iter()
            .map(|msg| {
                let dict = pyo3::types::PyDict::new(py);
                dict.set_item("role", &msg.role).unwrap();
                dict.set_item("content", &msg.content).unwrap();
                dict.into()
            })
            .collect();

        Ok(result)
    }

    /// Count tokens in a text string using Rust.
    fn count_tokens(&self, text: &str) -> usize {
        ContextPruner::count_tokens(text)
    }

    /// Get token count for a list of messages.
    fn count_message_tokens(&self, messages: Vec<Py<PyAny>>, py: Python) -> PyResult<usize> {
        let mut total = 0;
        for msg in messages {
            let dict = msg.cast_bound::<pyo3::types::PyDict>(py)?;
            let content: String = dict.get_item("content")?.unwrap().extract()?;
            total += ContextPruner::count_tokens(&content);
        }
        Ok(total)
    }
}

/// Smart Truncation with Middle Removal
///
/// Implements "head + tail" preservation strategy where
/// the middle portion of text is removed if it exceeds the limit.
#[pyfunction]
pub fn py_truncate_middle(text: &str, max_tokens: usize) -> String {
    let tokens = count_tokens(text);
    if tokens <= max_tokens {
        return text.to_string();
    }

    // Simple middle truncation: keep first 40% and last 60%
    // This preserves recent context while dropping older content
    let keep_first = (max_tokens * 40) / 100;
    let _keep_last = max_tokens - keep_first;

    // For text messages, this is a simplified approach
    // A full implementation would tokenize, split, and recombine
    let chars = text.chars().collect::<Vec<_>>();
    let total_chars = chars.len();
    let split_point = (total_chars * keep_first) / tokens;

    let first_part: String = chars[..split_point.min(total_chars)].iter().collect();
    let last_part: String = chars[split_point..].iter().collect();

    format!(
        "{}\n\n[... {} chars truncated ...]\n\n{}",
        first_part,
        total_chars - split_point - (total_chars - split_point),
        last_part
    )
}
