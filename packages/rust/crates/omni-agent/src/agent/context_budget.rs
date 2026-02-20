use omni_tokenizer::{count_tokens, truncate};

use crate::config::ContextBudgetStrategy;
use crate::session::ChatMessage;

pub(crate) const SESSION_SUMMARY_MESSAGE_NAME: &str = "session.summary.segment";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum MessageClass {
    NonSystem,
    RegularSystem,
    SummarySystem,
}

#[derive(Debug, Clone, Default)]
pub(crate) struct ContextBudgetClassStats {
    pub input_messages: usize,
    pub kept_messages: usize,
    pub truncated_messages: usize,
    pub input_tokens: usize,
    pub kept_tokens: usize,
    pub truncated_tokens: usize,
}

impl ContextBudgetClassStats {
    fn record_input(&mut self, tokens: usize) {
        self.input_messages = self.input_messages.saturating_add(1);
        self.input_tokens = self.input_tokens.saturating_add(tokens);
    }

    fn record_kept(&mut self, original_tokens: usize, kept_tokens: usize) {
        self.kept_messages = self.kept_messages.saturating_add(1);
        self.kept_tokens = self.kept_tokens.saturating_add(kept_tokens);
        if kept_tokens < original_tokens {
            self.truncated_messages = self.truncated_messages.saturating_add(1);
            self.truncated_tokens = self
                .truncated_tokens
                .saturating_add(original_tokens.saturating_sub(kept_tokens));
        }
    }

    pub fn dropped_messages(&self) -> usize {
        self.input_messages.saturating_sub(self.kept_messages)
    }

    pub fn dropped_tokens(&self) -> usize {
        self.input_tokens.saturating_sub(self.kept_tokens)
    }
}

#[derive(Debug, Clone)]
pub(crate) struct ContextBudgetReport {
    pub strategy: ContextBudgetStrategy,
    pub budget_tokens: usize,
    pub reserve_tokens: usize,
    pub effective_budget_tokens: usize,
    pub pre_messages: usize,
    pub post_messages: usize,
    pub pre_tokens: usize,
    pub post_tokens: usize,
    pub non_system: ContextBudgetClassStats,
    pub regular_system: ContextBudgetClassStats,
    pub summary_system: ContextBudgetClassStats,
}

impl ContextBudgetReport {
    fn new(
        strategy: ContextBudgetStrategy,
        budget_tokens: usize,
        reserve_tokens: usize,
        effective_budget_tokens: usize,
    ) -> Self {
        Self {
            strategy,
            budget_tokens,
            reserve_tokens,
            effective_budget_tokens,
            pre_messages: 0,
            post_messages: 0,
            pre_tokens: 0,
            post_tokens: 0,
            non_system: ContextBudgetClassStats::default(),
            regular_system: ContextBudgetClassStats::default(),
            summary_system: ContextBudgetClassStats::default(),
        }
    }

    fn class_mut(&mut self, class: MessageClass) -> &mut ContextBudgetClassStats {
        match class {
            MessageClass::NonSystem => &mut self.non_system,
            MessageClass::RegularSystem => &mut self.regular_system,
            MessageClass::SummarySystem => &mut self.summary_system,
        }
    }
}

#[derive(Clone)]
struct IndexedMessage {
    index: usize,
    class: MessageClass,
    original_tokens: usize,
    message: ChatMessage,
}

#[derive(Clone)]
struct SelectedMessage {
    index: usize,
    class: MessageClass,
    original_tokens: usize,
    kept_tokens: usize,
    message: ChatMessage,
}

pub(crate) struct ContextBudgetPruneResult {
    pub messages: Vec<ChatMessage>,
    pub report: ContextBudgetReport,
}

#[doc(hidden)]
pub fn prune_messages_for_token_budget(
    messages: Vec<ChatMessage>,
    budget_tokens: usize,
    reserve_tokens: usize,
) -> Vec<ChatMessage> {
    prune_messages_for_token_budget_with_strategy(
        messages,
        budget_tokens,
        reserve_tokens,
        ContextBudgetStrategy::RecentFirst,
    )
    .messages
}

pub(crate) fn prune_messages_for_token_budget_with_strategy(
    messages: Vec<ChatMessage>,
    budget_tokens: usize,
    reserve_tokens: usize,
    strategy: ContextBudgetStrategy,
) -> ContextBudgetPruneResult {
    let mut report = ContextBudgetReport::new(
        strategy,
        budget_tokens,
        reserve_tokens,
        budget_tokens.saturating_sub(reserve_tokens).max(1),
    );
    if messages.is_empty() {
        report.effective_budget_tokens = if budget_tokens == 0 {
            0
        } else {
            report.effective_budget_tokens
        };
        return ContextBudgetPruneResult { messages, report };
    }

    let effective_budget = if budget_tokens == 0 {
        0
    } else {
        budget_tokens.saturating_sub(reserve_tokens).max(1)
    };
    report.effective_budget_tokens = effective_budget;

    let mut regular_system = Vec::new();
    let mut summary_system = Vec::new();
    let mut non_system = Vec::new();

    for (index, message) in messages.into_iter().enumerate() {
        let class = classify_message(&message);
        let original_tokens = estimated_message_tokens(&message);
        report.class_mut(class).record_input(original_tokens);
        report.pre_messages = report.pre_messages.saturating_add(1);
        report.pre_tokens = report.pre_tokens.saturating_add(original_tokens);

        let indexed = IndexedMessage {
            index,
            class,
            original_tokens,
            message,
        };
        match class {
            MessageClass::NonSystem => non_system.push(indexed),
            MessageClass::RegularSystem => regular_system.push(indexed),
            MessageClass::SummarySystem => summary_system.push(indexed),
        }
    }

    if effective_budget == 0 {
        return ContextBudgetPruneResult {
            messages: Vec::new(),
            report,
        };
    }

    let mut selected = Vec::new();
    let mut used_tokens = 0usize;

    if let Some(latest_non_system) = non_system.last().cloned() {
        if let Some(trimmed) =
            truncate_message_to_budget(latest_non_system.message, effective_budget)
        {
            let kept_tokens = estimated_message_tokens(&trimmed);
            used_tokens = used_tokens.saturating_add(kept_tokens);
            selected.push(SelectedMessage {
                index: latest_non_system.index,
                class: latest_non_system.class,
                original_tokens: latest_non_system.original_tokens,
                kept_tokens,
                message: trimmed,
            });
        }
    }

    let mut candidates = Vec::new();
    candidates.extend(regular_system);
    match strategy {
        ContextBudgetStrategy::RecentFirst => {
            if !non_system.is_empty() {
                candidates.extend(
                    non_system[..non_system.len().saturating_sub(1)]
                        .iter()
                        .rev()
                        .cloned(),
                );
            }
            candidates.extend(summary_system.into_iter().rev());
        }
        ContextBudgetStrategy::SummaryFirst => {
            candidates.extend(summary_system.into_iter().rev());
            if !non_system.is_empty() {
                candidates.extend(
                    non_system[..non_system.len().saturating_sub(1)]
                        .iter()
                        .rev()
                        .cloned(),
                );
            }
        }
    }

    for candidate in candidates {
        if used_tokens >= effective_budget {
            break;
        }
        let remaining = effective_budget.saturating_sub(used_tokens);
        if let Some(trimmed) = truncate_message_to_budget(candidate.message, remaining) {
            let kept_tokens = estimated_message_tokens(&trimmed);
            used_tokens = used_tokens.saturating_add(kept_tokens);
            selected.push(SelectedMessage {
                index: candidate.index,
                class: candidate.class,
                original_tokens: candidate.original_tokens,
                kept_tokens,
                message: trimmed,
            });
        }
    }

    selected.sort_by_key(|entry| entry.index);
    let mut packed = Vec::with_capacity(selected.len());
    for entry in selected {
        report
            .class_mut(entry.class)
            .record_kept(entry.original_tokens, entry.kept_tokens);
        report.post_messages = report.post_messages.saturating_add(1);
        report.post_tokens = report.post_tokens.saturating_add(entry.kept_tokens);
        packed.push(entry.message);
    }

    ContextBudgetPruneResult {
        messages: packed,
        report,
    }
}

fn truncate_message_to_budget(message: ChatMessage, budget_tokens: usize) -> Option<ChatMessage> {
    if budget_tokens == 0 {
        return None;
    }
    let current = estimated_message_tokens(&message);
    if current <= budget_tokens {
        return Some(message);
    }

    let Some(content) = message.content.clone() else {
        return None;
    };

    let overhead = estimated_message_overhead_tokens(&message);
    if overhead >= budget_tokens {
        return None;
    }
    let content_budget = budget_tokens.saturating_sub(overhead).max(1);
    let truncated_content = truncate(&content, content_budget);
    if truncated_content.trim().is_empty() {
        return None;
    }
    let mut trimmed = message;
    trimmed.content = Some(truncated_content);
    Some(trimmed)
}

fn classify_message(message: &ChatMessage) -> MessageClass {
    if message.role == "system" {
        if is_summary_system_message(message) {
            MessageClass::SummarySystem
        } else {
            MessageClass::RegularSystem
        }
    } else {
        MessageClass::NonSystem
    }
}

fn estimated_message_tokens(message: &ChatMessage) -> usize {
    let mut total = estimated_message_overhead_tokens(message);
    if let Some(content) = &message.content {
        total = total.saturating_add(count_tokens(content));
    }
    total
}

fn estimated_message_overhead_tokens(message: &ChatMessage) -> usize {
    let mut total = 6usize.saturating_add(count_tokens(&message.role));
    if let Some(name) = &message.name {
        total = total.saturating_add(count_tokens(name));
    }
    if let Some(tool_call_id) = &message.tool_call_id {
        total = total.saturating_add(count_tokens(tool_call_id));
    }
    if let Some(tool_calls) = &message.tool_calls {
        let encoded = serde_json::to_string(tool_calls).unwrap_or_default();
        total = total.saturating_add(count_tokens(&encoded));
    }
    total
}

fn is_summary_system_message(message: &ChatMessage) -> bool {
    message.role == "system" && message.name.as_deref() == Some(SESSION_SUMMARY_MESSAGE_NAME)
}
