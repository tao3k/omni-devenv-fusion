//! Match types for AST analysis results.
//!
//! Provides the `Match` struct representing a single pattern match
/// A matched item from AST analysis
#[derive(Debug, Clone)]
pub struct Match {
    /// The matched text content
    pub text: String,
    /// Start byte position
    pub start: usize,
    /// End byte position
    pub end: usize,
    /// Captured variable names and values
    pub captures: Vec<(String, String)>,
}

impl Match {
    /// Create a new Match
    #[must_use]
    pub fn new(text: String, start: usize, end: usize, captures: Vec<(String, String)>) -> Self {
        Self {
            text,
            start,
            end,
            captures,
        }
    }

    /// Get the length of the matched text
    #[must_use]
    pub fn len(&self) -> usize {
        self.text.len()
    }

    /// Check if match is empty
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.text.is_empty()
    }

    /// Get a capture by name
    #[must_use]
    pub fn get_capture(&self, name: &str) -> Option<&str> {
        self.captures
            .iter()
            .find(|(n, _)| n == name)
            .map(|(_, v)| v.as_str())
    }
}
