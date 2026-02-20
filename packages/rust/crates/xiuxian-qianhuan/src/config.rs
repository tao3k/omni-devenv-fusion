/// Window limits for injected prompt content.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct InjectionWindowConfig {
    /// Maximum number of retained `<qa>` entries.
    pub max_entries: usize,
    /// Maximum retained character budget across entries.
    pub max_chars: usize,
}

impl Default for InjectionWindowConfig {
    fn default() -> Self {
        Self {
            max_entries: 8,
            max_chars: 4_000,
        }
    }
}
