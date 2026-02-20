use serde::{Deserialize, Serialize};

use crate::PromptContextCategory;

/// Injection assembly mode selected by Omega.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum InjectionMode {
    /// Compact single-block injection.
    Single,
    /// Category-based block assembly.
    Classified,
    /// Mixed role + categorized injection.
    Hybrid,
}

/// Deterministic ordering strategy for snapshot assembly.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum InjectionOrderStrategy {
    /// Sort by descending priority only.
    PriorityDesc,
    /// Group by category, then descending priority.
    CategoryThenPriority,
}

/// Policy that constrains and orders injection blocks.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct InjectionPolicy {
    /// Selected assembly mode.
    pub mode: InjectionMode,
    /// Maximum number of blocks to keep.
    pub max_blocks: usize,
    /// Maximum char budget across all blocks.
    pub max_chars: usize,
    /// Deterministic ordering strategy.
    pub ordering: InjectionOrderStrategy,
    /// Allowed categories for this turn.
    pub enabled_categories: Vec<PromptContextCategory>,
    /// Non-evictable categories regardless of normal pruning.
    pub anchor_categories: Vec<PromptContextCategory>,
}

impl Default for InjectionPolicy {
    fn default() -> Self {
        Self {
            mode: InjectionMode::Classified,
            max_blocks: 12,
            max_chars: 8_000,
            ordering: InjectionOrderStrategy::CategoryThenPriority,
            enabled_categories: vec![
                PromptContextCategory::Safety,
                PromptContextCategory::Policy,
                PromptContextCategory::MemoryRecall,
                PromptContextCategory::SessionXml,
                PromptContextCategory::WindowSummary,
                PromptContextCategory::Knowledge,
                PromptContextCategory::Reflection,
                PromptContextCategory::RuntimeHint,
            ],
            anchor_categories: vec![PromptContextCategory::Safety, PromptContextCategory::Policy],
        }
    }
}
