use std::fmt::{Display, Formatter};

/// Parse and validation errors for prompt injection payloads.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum InjectionError {
    /// Input XML payload is empty after trimming.
    EmptyPayload,
    /// Payload does not contain any parseable `<qa>` blocks.
    MissingQaBlock,
    /// A `<qa>` block is missing `<q>`.
    MissingQuestion,
    /// A `<qa>` block is missing `<a>`.
    MissingAnswer,
}

impl Display for InjectionError {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EmptyPayload => write!(f, "injection payload is empty"),
            Self::MissingQaBlock => write!(f, "injection payload must contain at least one <qa>"),
            Self::MissingQuestion => write!(f, "<qa> block missing required <q>"),
            Self::MissingAnswer => write!(f, "<qa> block missing required <a>"),
        }
    }
}

impl std::error::Error for InjectionError {}
