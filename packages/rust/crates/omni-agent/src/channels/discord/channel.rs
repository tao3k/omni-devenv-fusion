//! Discord channel skeleton with shared control-command authorization policy.

use std::sync::{PoisonError, RwLock};

use async_trait::async_trait;

use crate::channels::control_command_authorization::{
    ControlCommandPolicy, resolve_control_command_authorization_with_policy,
};
use crate::channels::control_command_rule_specs::{
    CommandSelectorAuthRule, parse_control_command_rule_specs,
};
use crate::channels::managed_commands::{
    SLASH_SCOPE_BACKGROUND_SUBMIT, SLASH_SCOPE_JOB_STATUS, SLASH_SCOPE_JOBS_SUMMARY,
    SLASH_SCOPE_SESSION_BUDGET, SLASH_SCOPE_SESSION_FEEDBACK, SLASH_SCOPE_SESSION_MEMORY,
    SLASH_SCOPE_SESSION_STATUS,
};
use crate::channels::traits::{Channel, ChannelMessage};

use super::client::build_discord_http_client;
use super::constants::DISCORD_DEFAULT_API_BASE;
use super::session_partition::DiscordSessionPartition;

type DiscordCommandAdminRule = CommandSelectorAuthRule;

#[derive(Debug, Clone, PartialEq, Eq)]
struct DiscordSlashCommandRule {
    command_scope: &'static str,
    allowed_identities: Vec<String>,
}

impl DiscordSlashCommandRule {
    fn new(command_scope: &'static str, allowed_identities: Vec<String>) -> Self {
        Self {
            command_scope,
            allowed_identities,
        }
    }
}

impl crate::channels::control_command_authorization::ControlCommandAuthRule
    for DiscordSlashCommandRule
{
    fn matches(&self, command_text: &str) -> bool {
        self.command_scope == command_text
    }

    fn allows_identity(&self, identity: &str) -> bool {
        self.allowed_identities
            .iter()
            .any(|entry| entry == "*" || entry == identity)
    }
}

/// Authorization inputs for privileged Discord control commands.
#[derive(Debug, Clone, Default)]
pub struct DiscordControlCommandPolicy {
    pub admin_users: Vec<String>,
    pub control_command_allow_from: Option<Vec<String>>,
    pub admin_command_rule_specs: Vec<String>,
    pub slash_command_policy: DiscordSlashCommandPolicy,
}

/// User-friendly ACL fields for non-privileged Discord slash commands.
///
/// Priority order:
/// 1) `slash_command_allow_from` (global override for all listed slash scopes)
/// 2) command-specific allowlists (`*_allow_from`)
/// 3) fallback `admin_users` from [`DiscordControlCommandPolicy`]
#[derive(Debug, Clone, Default)]
pub struct DiscordSlashCommandPolicy {
    pub slash_command_allow_from: Option<Vec<String>>,
    pub session_status_allow_from: Option<Vec<String>>,
    pub session_budget_allow_from: Option<Vec<String>>,
    pub session_memory_allow_from: Option<Vec<String>>,
    pub session_feedback_allow_from: Option<Vec<String>>,
    pub job_status_allow_from: Option<Vec<String>>,
    pub jobs_summary_allow_from: Option<Vec<String>>,
    pub background_submit_allow_from: Option<Vec<String>>,
}

impl DiscordControlCommandPolicy {
    pub fn new(
        admin_users: Vec<String>,
        control_command_allow_from: Option<Vec<String>>,
        admin_command_rule_specs: Vec<String>,
    ) -> Self {
        Self {
            admin_users,
            control_command_allow_from,
            admin_command_rule_specs,
            slash_command_policy: DiscordSlashCommandPolicy::default(),
        }
    }

    pub fn with_slash_command_policy(
        mut self,
        slash_command_policy: DiscordSlashCommandPolicy,
    ) -> Self {
        self.slash_command_policy = slash_command_policy;
        self
    }
}

/// Discord channel skeleton.
///
/// This type currently provides:
/// - channel identity/allowlist configuration storage
/// - session partition and parser support for future transport integration
/// - shared control-command authorization policy resolution
/// - Discord REST send path (`send`) and typing indicator API call (`start_typing`)
///
/// `listen` remains intentionally unimplemented in this phase.
pub struct DiscordChannel {
    pub(super) bot_token: String,
    api_base_url: String,
    pub(super) allowed_users: Vec<String>,
    pub(super) allowed_guilds: Vec<String>,
    control_command_policy: ControlCommandPolicy<DiscordCommandAdminRule>,
    slash_command_policy: ControlCommandPolicy<DiscordSlashCommandRule>,
    session_partition: RwLock<DiscordSessionPartition>,
    pub(super) client: reqwest::Client,
}

impl DiscordChannel {
    /// Create a Discord channel skeleton with default admin policy (`admin_users=allowed_users`).
    pub fn new(bot_token: String, allowed_users: Vec<String>, allowed_guilds: Vec<String>) -> Self {
        Self::new_with_partition(
            bot_token,
            allowed_users,
            allowed_guilds,
            DiscordSessionPartition::from_env(),
        )
    }

    /// Create a Discord channel skeleton with explicit session partition.
    pub fn new_with_partition(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_guilds: Vec<String>,
        session_partition: DiscordSessionPartition,
    ) -> Self {
        let admin_users = allowed_users.clone();
        Self::new_with_partition_and_parsed_control_command_policy(
            bot_token,
            allowed_users,
            allowed_guilds,
            ControlCommandPolicy::new(admin_users, None, Vec::new()),
            DiscordSlashCommandPolicy::default(),
            session_partition,
        )
    }

    /// Create a Discord channel with custom API base URL (useful for tests/proxies).
    pub fn new_with_base_url(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_guilds: Vec<String>,
        api_base_url: String,
    ) -> Self {
        Self::new_with_base_url_and_partition(
            bot_token,
            allowed_users,
            allowed_guilds,
            api_base_url,
            DiscordSessionPartition::from_env(),
        )
    }

    /// Create a Discord channel with custom API base URL and explicit session partition.
    pub fn new_with_base_url_and_partition(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_guilds: Vec<String>,
        api_base_url: String,
        session_partition: DiscordSessionPartition,
    ) -> Self {
        let admin_users = allowed_users.clone();
        Self::new_with_base_url_and_partition_and_parsed_control_command_policy(
            bot_token,
            allowed_users,
            allowed_guilds,
            api_base_url,
            ControlCommandPolicy::new(admin_users, None, Vec::new()),
            DiscordSlashCommandPolicy::default(),
            session_partition,
            build_discord_http_client(),
        )
    }

    /// Create a Discord channel skeleton with explicit control-command policy.
    pub fn new_with_control_command_policy(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_guilds: Vec<String>,
        control_command_policy: DiscordControlCommandPolicy,
    ) -> anyhow::Result<Self> {
        Self::new_with_partition_and_control_command_policy(
            bot_token,
            allowed_users,
            allowed_guilds,
            control_command_policy,
            DiscordSessionPartition::from_env(),
        )
    }

    /// Create a Discord channel skeleton with explicit control-command policy and session
    /// partition.
    pub fn new_with_partition_and_control_command_policy(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_guilds: Vec<String>,
        control_command_policy: DiscordControlCommandPolicy,
        session_partition: DiscordSessionPartition,
    ) -> anyhow::Result<Self> {
        let DiscordControlCommandPolicy {
            admin_users,
            control_command_allow_from,
            admin_command_rule_specs,
            slash_command_policy,
        } = control_command_policy;
        let admin_command_rules = parse_admin_command_rule_specs(admin_command_rule_specs)?;
        Ok(Self::new_with_partition_and_parsed_control_command_policy(
            bot_token,
            allowed_users,
            allowed_guilds,
            ControlCommandPolicy::new(admin_users, control_command_allow_from, admin_command_rules),
            slash_command_policy,
            session_partition,
        ))
    }

    fn new_with_partition_and_parsed_control_command_policy(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_guilds: Vec<String>,
        control_command_policy: ControlCommandPolicy<DiscordCommandAdminRule>,
        slash_command_policy: DiscordSlashCommandPolicy,
        session_partition: DiscordSessionPartition,
    ) -> Self {
        Self::new_with_base_url_and_partition_and_parsed_control_command_policy(
            bot_token,
            allowed_users,
            allowed_guilds,
            DISCORD_DEFAULT_API_BASE.to_string(),
            control_command_policy,
            slash_command_policy,
            session_partition,
            build_discord_http_client(),
        )
    }

    #[doc(hidden)]
    pub fn new_with_base_url_and_partition_and_client(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_guilds: Vec<String>,
        api_base_url: String,
        session_partition: DiscordSessionPartition,
        client: reqwest::Client,
    ) -> Self {
        let admin_users = allowed_users.clone();
        Self::new_with_base_url_and_partition_and_parsed_control_command_policy(
            bot_token,
            allowed_users,
            allowed_guilds,
            api_base_url,
            ControlCommandPolicy::new(admin_users, None, Vec::new()),
            DiscordSlashCommandPolicy::default(),
            session_partition,
            client,
        )
    }

    fn new_with_base_url_and_partition_and_parsed_control_command_policy(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_guilds: Vec<String>,
        api_base_url: String,
        control_command_policy: ControlCommandPolicy<DiscordCommandAdminRule>,
        slash_command_policy: DiscordSlashCommandPolicy,
        session_partition: DiscordSessionPartition,
        client: reqwest::Client,
    ) -> Self {
        let control_command_policy = normalize_control_command_policy(control_command_policy);
        let slash_command_policy = build_slash_command_policy(
            control_command_policy.admin_users.clone(),
            slash_command_policy,
        );
        Self {
            bot_token,
            api_base_url,
            allowed_users: normalize_allowed_user_entries(allowed_users),
            allowed_guilds: normalize_allowed_guild_entries(allowed_guilds),
            control_command_policy,
            slash_command_policy,
            session_partition: RwLock::new(session_partition),
            client,
        }
    }

    /// Current session partition mode used by this channel.
    pub fn session_partition(&self) -> DiscordSessionPartition {
        *self
            .session_partition
            .read()
            .unwrap_or_else(PoisonError::into_inner)
    }

    /// Update session partition mode at runtime.
    pub fn set_session_partition(&self, mode: DiscordSessionPartition) {
        *self
            .session_partition
            .write()
            .unwrap_or_else(PoisonError::into_inner) = mode;
    }

    pub(super) fn normalize_identity(&self, identity: &str) -> String {
        normalize_discord_identity(identity)
    }

    fn authorize_control_command(&self, identity: &str, command_text: &str) -> bool {
        let normalized = normalize_discord_identity(identity);
        resolve_control_command_authorization_with_policy(
            &normalized,
            command_text,
            &self.control_command_policy,
        )
        .allowed
    }

    fn authorize_slash_command(&self, identity: &str, command_scope: &str) -> bool {
        let normalized = normalize_discord_identity(identity);
        resolve_control_command_authorization_with_policy(
            &normalized,
            command_scope,
            &self.slash_command_policy,
        )
        .allowed
    }

    pub(super) fn api_url(&self, path: &str) -> String {
        format!(
            "{}/{}",
            self.api_base_url.trim_end_matches('/'),
            path.trim_start_matches('/')
        )
    }
}

fn parse_admin_command_rule_specs(
    specs: Vec<String>,
) -> anyhow::Result<Vec<DiscordCommandAdminRule>> {
    parse_control_command_rule_specs(
        specs,
        "discord admin command rule",
        normalize_discord_identity,
    )
}

fn normalize_allowed_user_entries(entries: Vec<String>) -> Vec<String> {
    entries
        .into_iter()
        .map(|entry| normalize_discord_identity(&entry))
        .filter(|entry| !entry.is_empty())
        .collect()
}

fn normalize_allowed_guild_entries(entries: Vec<String>) -> Vec<String> {
    entries
        .into_iter()
        .map(|entry| entry.trim().to_string())
        .filter(|entry| !entry.is_empty())
        .collect()
}

fn normalize_optional_allowed_user_entries(entries: Option<Vec<String>>) -> Option<Vec<String>> {
    entries.map(normalize_allowed_user_entries)
}

fn normalize_slash_command_policy(policy: DiscordSlashCommandPolicy) -> DiscordSlashCommandPolicy {
    DiscordSlashCommandPolicy {
        slash_command_allow_from: normalize_optional_allowed_user_entries(
            policy.slash_command_allow_from,
        ),
        session_status_allow_from: normalize_optional_allowed_user_entries(
            policy.session_status_allow_from,
        ),
        session_budget_allow_from: normalize_optional_allowed_user_entries(
            policy.session_budget_allow_from,
        ),
        session_memory_allow_from: normalize_optional_allowed_user_entries(
            policy.session_memory_allow_from,
        ),
        session_feedback_allow_from: normalize_optional_allowed_user_entries(
            policy.session_feedback_allow_from,
        ),
        job_status_allow_from: normalize_optional_allowed_user_entries(
            policy.job_status_allow_from,
        ),
        jobs_summary_allow_from: normalize_optional_allowed_user_entries(
            policy.jobs_summary_allow_from,
        ),
        background_submit_allow_from: normalize_optional_allowed_user_entries(
            policy.background_submit_allow_from,
        ),
    }
}

fn normalize_control_command_policy(
    policy: ControlCommandPolicy<DiscordCommandAdminRule>,
) -> ControlCommandPolicy<DiscordCommandAdminRule> {
    ControlCommandPolicy::new(
        normalize_allowed_user_entries(policy.admin_users),
        normalize_optional_allowed_user_entries(policy.control_command_allow_from),
        policy.rules,
    )
}

fn build_slash_command_policy(
    admin_users: Vec<String>,
    slash_policy: DiscordSlashCommandPolicy,
) -> ControlCommandPolicy<DiscordSlashCommandRule> {
    let slash_policy = normalize_slash_command_policy(slash_policy);
    let mut rules = Vec::new();

    add_slash_rule(
        &mut rules,
        SLASH_SCOPE_SESSION_STATUS,
        slash_policy.session_status_allow_from,
        &admin_users,
    );
    add_slash_rule(
        &mut rules,
        SLASH_SCOPE_SESSION_BUDGET,
        slash_policy.session_budget_allow_from,
        &admin_users,
    );
    add_slash_rule(
        &mut rules,
        SLASH_SCOPE_SESSION_MEMORY,
        slash_policy.session_memory_allow_from,
        &admin_users,
    );
    add_slash_rule(
        &mut rules,
        SLASH_SCOPE_SESSION_FEEDBACK,
        slash_policy.session_feedback_allow_from,
        &admin_users,
    );
    add_slash_rule(
        &mut rules,
        SLASH_SCOPE_JOB_STATUS,
        slash_policy.job_status_allow_from,
        &admin_users,
    );
    add_slash_rule(
        &mut rules,
        SLASH_SCOPE_JOBS_SUMMARY,
        slash_policy.jobs_summary_allow_from,
        &admin_users,
    );
    add_slash_rule(
        &mut rules,
        SLASH_SCOPE_BACKGROUND_SUBMIT,
        slash_policy.background_submit_allow_from,
        &admin_users,
    );

    ControlCommandPolicy::new(admin_users, slash_policy.slash_command_allow_from, rules)
}

fn add_slash_rule(
    rules: &mut Vec<DiscordSlashCommandRule>,
    command_scope: &'static str,
    allow_from: Option<Vec<String>>,
    admin_users: &[String],
) {
    if let Some(mut allowed_identities) = allow_from {
        allowed_identities.extend(admin_users.iter().cloned());
        rules.push(DiscordSlashCommandRule::new(
            command_scope,
            allowed_identities,
        ));
    }
}

fn normalize_discord_identity(identity: &str) -> String {
    let trimmed = identity.trim();
    if trimmed == "*" {
        return "*".to_string();
    }
    trimmed.trim_start_matches('@').to_ascii_lowercase()
}

#[async_trait]
impl Channel for DiscordChannel {
    fn name(&self) -> &str {
        "discord"
    }

    fn session_partition_mode(&self) -> Option<String> {
        Some(self.session_partition().to_string())
    }

    fn set_session_partition_mode(&self, mode: &str) -> anyhow::Result<()> {
        let parsed = mode
            .parse::<DiscordSessionPartition>()
            .map_err(|_| anyhow::anyhow!("invalid discord session partition mode: {mode}"))?;
        self.set_session_partition(parsed);
        Ok(())
    }

    fn is_admin_user(&self, identity: &str) -> bool {
        let normalized = normalize_discord_identity(identity);
        self.control_command_policy
            .admin_users
            .iter()
            .any(|entry| entry == "*" || entry == &normalized)
    }

    fn is_authorized_for_control_command(&self, identity: &str, command_text: &str) -> bool {
        self.authorize_control_command(identity, command_text)
    }

    fn is_authorized_for_slash_command(&self, identity: &str, command_scope: &str) -> bool {
        self.authorize_slash_command(identity, command_scope)
    }

    async fn send(&self, message: &str, recipient: &str) -> anyhow::Result<()> {
        self.send_text(message, recipient).await
    }

    async fn listen(&self, _tx: tokio::sync::mpsc::Sender<ChannelMessage>) -> anyhow::Result<()> {
        anyhow::bail!("discord channel listen is not implemented yet")
    }

    async fn start_typing(&self, recipient: &str) -> anyhow::Result<()> {
        self.start_typing_indicator(recipient).await
    }

    async fn health_check(&self) -> bool {
        false
    }
}
