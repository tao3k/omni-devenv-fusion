use crate::TokenCounter;
use serde::{Deserialize, Serialize};

/// A message in the conversation history.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    /// The role of the message sender (e.g., "system", "user", "assistant", "tool").
    pub role: String,
    /// The content of the message.
    pub content: String,
    // Optional: Add name or other OpenAI fields if needed
}

/// Prunes context to fit within token limits while preserving important information.
#[derive(Clone)]
pub struct ContextPruner {
    window_size: usize,
    max_tool_output: usize,
}

impl ContextPruner {
    /// Create a new `ContextPruner`.
    ///
    /// # Arguments
    ///
    /// * `window_size` - Number of message pairs (user+assistant) to keep in the working memory (safety zone).
    /// * `max_tool_output` - Maximum length (in characters) for tool outputs in the archive.
    #[must_use]
    pub fn new(window_size: usize, max_tool_output: usize) -> Self {
        Self {
            window_size,
            max_tool_output,
        }
    }

    /// Compress the message history.
    ///
    /// Preserves system messages and the most recent messages (`window_size`).
    /// Truncates tool outputs in older messages (archive) to save space.
    #[must_use]
    pub fn compress(&self, messages: Vec<Message>) -> Vec<Message> {
        let total_count = messages.len();
        if total_count == 0 {
            return vec![];
        }

        // 1. Identify System Messages (Always Keep)
        let (system_msgs, other_msgs): (Vec<_>, Vec<_>) =
            messages.into_iter().partition(|m| m.role == "system");

        // 2. Determine Safety Zone (Window Size)
        // Keep last N*2 messages (User + Assistant pair) approximately
        let safe_count = self.window_size * 2;

        let (archive, working) = if other_msgs.len() > safe_count {
            other_msgs.split_at(other_msgs.len() - safe_count)
        } else {
            (other_msgs.as_slice(), &[][..])
        };

        let mut processed_archive = Vec::new();

        // 3. Process Archive (Compress Tool Outputs)
        for msg in archive {
            let mut new_msg = msg.clone();

            if new_msg.role == "tool" || new_msg.role == "function" {
                // Check length first (fastest)
                if new_msg.content.len() > self.max_tool_output {
                    // Check tokens (slower but more accurate, optional)
                    // Here we stick to char length for raw speed in Rust
                    let preview = &new_msg.content[..self.max_tool_output];
                    let removed_len = new_msg.content.len() - self.max_tool_output;

                    new_msg.content = format!(
                        "{preview}...\n[SYSTEM NOTE: Output truncated. {removed_len} chars hidden to save context.]"
                    );
                }
            }

            processed_archive.push(new_msg);
        }

        // 4. Reassemble
        let mut result = system_msgs;
        result.extend(processed_archive);
        result.extend_from_slice(working);

        result
    }

    /// Count tokens in a text string.
    #[must_use]
    pub fn count_tokens(text: &str) -> usize {
        TokenCounter::count_tokens(text)
    }
}
