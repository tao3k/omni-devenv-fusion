use std::collections::VecDeque;

use crate::{InjectionError, InjectionWindowConfig, QaEntry, xml};

/// Bounded session-level system prompt injection window.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SystemPromptInjectionWindow {
    config: InjectionWindowConfig,
    entries: VecDeque<QaEntry>,
}

impl SystemPromptInjectionWindow {
    /// Create an empty injection window with limits.
    #[must_use]
    pub fn new(config: InjectionWindowConfig) -> Self {
        Self {
            config,
            entries: VecDeque::new(),
        }
    }

    /// Parse XML and construct a bounded injection window.
    pub fn from_xml(raw: &str, config: InjectionWindowConfig) -> Result<Self, InjectionError> {
        let parsed = xml::parse_qa_entries(raw)?;
        let mut window = Self::new(config);
        for entry in parsed {
            window.push(entry);
        }
        Ok(window)
    }

    /// Parse and normalize XML under window limits.
    pub fn normalize_xml(
        raw: &str,
        config: InjectionWindowConfig,
    ) -> Result<String, InjectionError> {
        let window = Self::from_xml(raw, config)?;
        Ok(window.render_xml())
    }

    /// Add one Q&A entry and enforce window bounds.
    pub fn push(&mut self, entry: QaEntry) {
        self.entries.push_back(entry);
        self.enforce_limits();
    }

    /// Remove all Q&A entries.
    pub fn clear(&mut self) {
        self.entries.clear();
    }

    /// Number of retained Q&A entries.
    #[must_use]
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the window has no entries.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Total char count of retained entries.
    #[must_use]
    pub fn total_chars(&self) -> usize {
        self.entries.iter().map(QaEntry::char_len).sum()
    }

    /// Iterate over retained entries in chronological order.
    pub fn iter(&self) -> impl Iterator<Item = &QaEntry> {
        self.entries.iter()
    }

    /// Render bounded entries as canonical XML payload.
    #[must_use]
    pub fn render_xml(&self) -> String {
        xml::render_xml(self.entries.iter().cloned())
    }

    fn enforce_limits(&mut self) {
        let max_entries = self.config.max_entries.max(1);
        let max_chars = self.config.max_chars.max(1);

        while self.entries.len() > max_entries {
            let _ = self.entries.pop_front();
        }
        while self.total_chars() > max_chars && self.entries.len() > 1 {
            let _ = self.entries.pop_front();
        }
        if self.total_chars() > max_chars
            && let Some(last) = self.entries.pop_back()
        {
            self.entries
                .push_back(truncate_entry_to_budget(last, max_chars));
        }
    }
}

fn truncate_entry_to_budget(entry: QaEntry, max_chars: usize) -> QaEntry {
    let question_budget = (max_chars / 3).max(32).min(max_chars);
    let question = truncate_chars(&entry.question, question_budget);
    let mut remaining = max_chars.saturating_sub(question.chars().count());
    if remaining == 0 {
        remaining = 1;
    }
    let answer = truncate_chars(&entry.answer, remaining);
    QaEntry {
        question,
        answer,
        source: entry.source.map(|value| truncate_chars(&value, 128)),
    }
}

fn truncate_chars(input: &str, max_chars: usize) -> String {
    if max_chars == 0 {
        return String::new();
    }
    if max_chars <= 3 {
        return ".".repeat(max_chars);
    }
    let count = input.chars().count();
    if count <= max_chars {
        return input.to_string();
    }
    let mut out = String::new();
    for ch in input.chars().take(max_chars.saturating_sub(3)) {
        out.push(ch);
    }
    out.push_str("...");
    out
}
