//! Shared control-command authorization policy for channel adapters.
//!
//! Priority order:
//! 1) `control_command_allow_from` (if configured)
//! 2) command-scoped authorization rules
//! 3) fallback admin allowlist

/// Rule contract for command-scoped authorization (for example, regex-based rules).
pub(crate) trait ControlCommandAuthRule {
    /// Whether this rule should apply to the given command text.
    fn matches(&self, command_text: &str) -> bool;

    /// Whether this rule allows the given normalized identity.
    fn allows_identity(&self, identity: &str) -> bool;
}

/// Decision source for control-command authorization.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ControlCommandAuthSource {
    ControlCommandAllowFrom,
    Rule,
    AdminUsers,
}

/// Result of control-command authorization evaluation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct ControlCommandAuthorization {
    pub(crate) allowed: bool,
    pub(crate) source: ControlCommandAuthSource,
}

/// Resolved control-command authorization policy state for a channel adapter.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ControlCommandPolicy<R> {
    pub(crate) admin_users: Vec<String>,
    pub(crate) control_command_allow_from: Option<Vec<String>>,
    pub(crate) rules: Vec<R>,
}

impl<R> ControlCommandPolicy<R> {
    pub(crate) fn new(
        admin_users: Vec<String>,
        control_command_allow_from: Option<Vec<String>>,
        rules: Vec<R>,
    ) -> Self {
        Self {
            admin_users,
            control_command_allow_from,
            rules,
        }
    }
}

fn list_allows_identity(identity: &str, entries: &[String]) -> bool {
    entries
        .iter()
        .any(|entry| entry == "*" || entry == identity)
}

fn evaluate_rule_authorization<R: ControlCommandAuthRule>(
    identity: &str,
    command_text: &str,
    rules: &[R],
) -> Option<bool> {
    let mut matched_rule = false;
    for rule in rules {
        if !rule.matches(command_text) {
            continue;
        }
        matched_rule = true;
        if rule.allows_identity(identity) {
            return Some(true);
        }
    }
    if matched_rule { Some(false) } else { None }
}

/// Resolve whether a normalized identity can run a control command.
///
/// `control_command_allow_from` is optional:
/// - `None`: not configured, continue to rule/admin fallback chain.
/// - `Some(vec![])`: configured deny-all.
pub(crate) fn resolve_control_command_authorization_with_policy<R: ControlCommandAuthRule>(
    normalized_identity: &str,
    command_text: &str,
    policy: &ControlCommandPolicy<R>,
) -> ControlCommandAuthorization {
    if let Some(entries) = policy.control_command_allow_from.as_deref() {
        return ControlCommandAuthorization {
            allowed: list_allows_identity(normalized_identity, entries),
            source: ControlCommandAuthSource::ControlCommandAllowFrom,
        };
    }

    if let Some(allowed) =
        evaluate_rule_authorization(normalized_identity, command_text, &policy.rules)
    {
        return ControlCommandAuthorization {
            allowed,
            source: ControlCommandAuthSource::Rule,
        };
    }

    ControlCommandAuthorization {
        allowed: list_allows_identity(normalized_identity, &policy.admin_users),
        source: ControlCommandAuthSource::AdminUsers,
    }
}
