use crate::channels::control_command_authorization::ControlCommandAuthRule;

/// Authorization inputs for privileged Telegram control commands.
#[derive(Debug, Clone, Default)]
pub struct TelegramControlCommandPolicy {
    pub admin_users: Vec<String>,
    pub control_command_allow_from: Option<Vec<String>>,
    pub admin_command_rule_specs: Vec<String>,
    pub slash_command_policy: TelegramSlashCommandPolicy,
}

impl TelegramControlCommandPolicy {
    pub fn new(
        admin_users: Vec<String>,
        control_command_allow_from: Option<Vec<String>>,
        admin_command_rule_specs: Vec<String>,
    ) -> Self {
        Self {
            admin_users,
            control_command_allow_from,
            admin_command_rule_specs,
            slash_command_policy: TelegramSlashCommandPolicy::default(),
        }
    }

    pub fn with_slash_command_policy(
        mut self,
        slash_command_policy: TelegramSlashCommandPolicy,
    ) -> Self {
        self.slash_command_policy = slash_command_policy;
        self
    }
}

/// User-friendly ACL fields for non-privileged Telegram slash commands.
///
/// Priority order:
/// 1) `slash_command_allow_from` (global override for all listed slash scopes)
/// 2) command-specific allowlists (`*_allow_from`)
/// 3) fallback `admin_users` from [`TelegramControlCommandPolicy`]
#[derive(Debug, Clone, Default)]
pub struct TelegramSlashCommandPolicy {
    pub slash_command_allow_from: Option<Vec<String>>,
    pub session_status_allow_from: Option<Vec<String>>,
    pub session_budget_allow_from: Option<Vec<String>>,
    pub session_memory_allow_from: Option<Vec<String>>,
    pub session_feedback_allow_from: Option<Vec<String>>,
    pub job_status_allow_from: Option<Vec<String>>,
    pub jobs_summary_allow_from: Option<Vec<String>>,
    pub background_submit_allow_from: Option<Vec<String>>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct TelegramSlashCommandRule {
    pub(super) command_scope: &'static str,
    pub(super) allowed_identities: Vec<String>,
}

impl TelegramSlashCommandRule {
    pub(super) fn new(command_scope: &'static str, allowed_identities: Vec<String>) -> Self {
        Self {
            command_scope,
            allowed_identities,
        }
    }
}

impl ControlCommandAuthRule for TelegramSlashCommandRule {
    fn matches(&self, command_text: &str) -> bool {
        self.command_scope == command_text
    }

    fn allows_identity(&self, identity: &str) -> bool {
        self.allowed_identities
            .iter()
            .any(|entry| entry == "*" || entry == identity)
    }
}
