use std::sync::{PoisonError, RwLock};

use crate::channels::control_command_authorization::ControlCommandPolicy;
use crate::config::runtime_settings_paths;

use super::TelegramSlashCommandRule;
use super::acl::{
    build_slash_command_policy, normalize_allowed_group_entries,
    normalize_allowed_user_entries_with_context, normalize_control_command_policy,
    normalize_slash_command_policy,
};
use super::acl_reload::TelegramAclReloadState;
use super::admin_rules::{TelegramCommandAdminRule, parse_admin_command_rule_specs};
use super::client::build_telegram_http_client;
use super::constants::TELEGRAM_DEFAULT_API_BASE;
use super::group_policy::TelegramGroupPolicyConfig;
use super::send_gate::{TelegramSendRateLimitBackend, TelegramSendRateLimitGateState};
use super::{
    TELEGRAM_API_BASE_ENV, TelegramChannel, TelegramControlCommandPolicy, TelegramSessionPartition,
    TelegramSlashCommandPolicy,
};

impl TelegramChannel {
    fn default_api_base_url() -> String {
        std::env::var(TELEGRAM_API_BASE_ENV)
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| TELEGRAM_DEFAULT_API_BASE.to_string())
    }

    /// Create a new Telegram channel.
    pub fn new(bot_token: String, allowed_users: Vec<String>, allowed_groups: Vec<String>) -> Self {
        Self::new_with_partition(
            bot_token,
            allowed_users,
            allowed_groups,
            TelegramSessionPartition::from_env(),
        )
    }

    /// Create a new Telegram channel with explicit session partition strategy.
    pub fn new_with_partition(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        session_partition: TelegramSessionPartition,
    ) -> Self {
        let admin_users = Vec::new();
        Self::new_with_partition_and_admin_users(
            bot_token,
            allowed_users,
            allowed_groups,
            admin_users,
            session_partition,
        )
    }

    /// Create a new Telegram channel with explicit session partition and admin user allowlist.
    pub fn new_with_partition_and_admin_users(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        admin_users: Vec<String>,
        session_partition: TelegramSessionPartition,
    ) -> Self {
        let slash_command_policy =
            build_slash_command_policy(admin_users.clone(), TelegramSlashCommandPolicy::default());
        Self::new_with_base_url_and_partition_and_control_command_policy(
            bot_token,
            allowed_users,
            allowed_groups,
            Self::default_api_base_url(),
            ControlCommandPolicy::new(admin_users, None, Vec::new()),
            slash_command_policy,
            session_partition,
        )
    }

    /// Create a new Telegram channel with explicit session partition, admin user allowlist, and
    /// per-command admin authorization rules.
    ///
    /// `admin_command_rule_specs` format:
    /// `/session partition=>1001,1002;/reset,/clear=>2001;session.*=>3001`
    pub fn new_with_partition_and_admin_users_and_command_rule_specs(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        admin_users: Vec<String>,
        admin_command_rule_specs: Vec<String>,
        session_partition: TelegramSessionPartition,
    ) -> anyhow::Result<Self> {
        Self::new_with_partition_and_admin_users_and_control_command_allow_from_and_command_rule_specs(
            bot_token,
            allowed_users,
            allowed_groups,
            admin_users,
            None,
            admin_command_rule_specs,
            session_partition,
        )
    }

    /// Create a new Telegram channel with explicit session partition and structured control-command
    /// authorization policy.
    pub fn new_with_partition_and_control_command_policy(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        control_command_policy: TelegramControlCommandPolicy,
        session_partition: TelegramSessionPartition,
    ) -> anyhow::Result<Self> {
        let TelegramControlCommandPolicy {
            admin_users,
            control_command_allow_from,
            admin_command_rule_specs,
            slash_command_policy,
        } = control_command_policy;
        let admin_command_rules = parse_admin_command_rule_specs(admin_command_rule_specs)?;
        let slash_command_policy =
            build_slash_command_policy(admin_users.clone(), slash_command_policy);
        Ok(
            Self::new_with_base_url_and_partition_and_control_command_policy(
                bot_token,
                allowed_users,
                allowed_groups,
                Self::default_api_base_url(),
                ControlCommandPolicy::new(
                    admin_users,
                    control_command_allow_from,
                    admin_command_rules,
                ),
                slash_command_policy,
                session_partition,
            ),
        )
    }

    /// Create a new Telegram channel with explicit session partition, optional control-command
    /// allowlist override, admin user allowlist, and per-command admin authorization rules.
    ///
    /// Priority:
    /// 1) `control_command_allow_from`
    /// 2) `admin_command_rule_specs`
    /// 3) `admin_users`
    pub fn new_with_partition_and_admin_users_and_control_command_allow_from_and_command_rule_specs(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        admin_users: Vec<String>,
        control_command_allow_from: Option<Vec<String>>,
        admin_command_rule_specs: Vec<String>,
        session_partition: TelegramSessionPartition,
    ) -> anyhow::Result<Self> {
        Self::new_with_partition_and_control_command_policy(
            bot_token,
            allowed_users,
            allowed_groups,
            TelegramControlCommandPolicy::new(
                admin_users,
                control_command_allow_from,
                admin_command_rule_specs,
            ),
            session_partition,
        )
    }

    /// Create a Telegram channel with a custom API base URL (useful for tests/proxies).
    pub fn new_with_base_url(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        api_base_url: String,
    ) -> Self {
        let admin_users = Vec::new();
        Self::new_with_base_url_and_partition(
            bot_token,
            allowed_users,
            allowed_groups,
            api_base_url,
            admin_users,
            TelegramSessionPartition::from_env(),
        )
    }

    /// Create a Telegram channel with custom API base URL and explicit session partition.
    pub fn new_with_base_url_and_partition(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        api_base_url: String,
        admin_users: Vec<String>,
        session_partition: TelegramSessionPartition,
    ) -> Self {
        let slash_command_policy =
            build_slash_command_policy(admin_users.clone(), TelegramSlashCommandPolicy::default());
        Self::new_with_base_url_and_partition_and_control_command_policy(
            bot_token,
            allowed_users,
            allowed_groups,
            api_base_url,
            ControlCommandPolicy::new(admin_users, None, Vec::new()),
            slash_command_policy,
            session_partition,
        )
    }

    fn new_with_base_url_and_partition_and_control_command_policy(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        api_base_url: String,
        control_command_policy: ControlCommandPolicy<TelegramCommandAdminRule>,
        slash_command_policy: ControlCommandPolicy<TelegramSlashCommandRule>,
        session_partition: TelegramSessionPartition,
    ) -> Self {
        Self::new_with_base_url_and_partition_and_client_impl(
            bot_token,
            allowed_users,
            allowed_groups,
            api_base_url,
            control_command_policy,
            slash_command_policy,
            session_partition,
            build_telegram_http_client(),
        )
    }

    /// Create a Telegram channel with custom API base URL, explicit session partition, and HTTP client.
    #[doc(hidden)]
    pub fn new_with_base_url_and_partition_and_client(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        api_base_url: String,
        admin_users: Vec<String>,
        session_partition: TelegramSessionPartition,
        client: reqwest::Client,
    ) -> Self {
        let slash_command_policy =
            build_slash_command_policy(admin_users.clone(), TelegramSlashCommandPolicy::default());
        Self::new_with_base_url_and_partition_and_client_impl(
            bot_token,
            allowed_users,
            allowed_groups,
            api_base_url,
            ControlCommandPolicy::new(admin_users, None, Vec::new()),
            slash_command_policy,
            session_partition,
            client,
        )
    }

    fn new_with_base_url_and_partition_and_client_impl(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        api_base_url: String,
        control_command_policy: ControlCommandPolicy<TelegramCommandAdminRule>,
        slash_command_policy: ControlCommandPolicy<TelegramSlashCommandRule>,
        session_partition: TelegramSessionPartition,
        client: reqwest::Client,
    ) -> Self {
        let (system_settings_path, user_settings_path) = runtime_settings_paths();
        let control_command_policy = normalize_control_command_policy(control_command_policy);
        let slash_command_policy = normalize_slash_command_policy(slash_command_policy);
        Self {
            bot_token,
            api_base_url,
            allowed_users: RwLock::new(normalize_allowed_user_entries_with_context(
                allowed_users,
                "telegram.allowed_users",
            )),
            allowed_groups: RwLock::new(normalize_allowed_group_entries(allowed_groups)),
            control_command_policy: RwLock::new(control_command_policy),
            slash_command_policy: RwLock::new(slash_command_policy),
            group_policy_config: RwLock::new(TelegramGroupPolicyConfig::default()),
            session_admin_persist: RwLock::new(false),
            session_partition: RwLock::new(session_partition),
            acl_reload_state: RwLock::new(TelegramAclReloadState::new(
                system_settings_path,
                user_settings_path,
            )),
            send_rate_limit_gate: tokio::sync::Mutex::new(TelegramSendRateLimitGateState::default()),
            send_rate_limit_backend: TelegramSendRateLimitBackend::from_env(),
            client,
        }
    }

    #[doc(hidden)]
    pub fn new_with_base_url_and_send_rate_limit_valkey_for_test(
        bot_token: String,
        allowed_users: Vec<String>,
        allowed_groups: Vec<String>,
        api_base_url: String,
        redis_url: String,
        key_prefix: String,
    ) -> anyhow::Result<Self> {
        let mut channel =
            Self::new_with_base_url(bot_token, allowed_users, allowed_groups, api_base_url);
        channel.send_rate_limit_backend = TelegramSendRateLimitBackend::new_valkey_for_test(
            redis_url.as_str(),
            key_prefix.as_str(),
        )?;
        Ok(channel)
    }

    /// Current session partition mode used by this channel.
    pub fn session_partition(&self) -> TelegramSessionPartition {
        *self
            .session_partition
            .read()
            .unwrap_or_else(PoisonError::into_inner)
    }

    /// Update session partition mode at runtime.
    pub fn set_session_partition(&self, mode: TelegramSessionPartition) {
        *self
            .session_partition
            .write()
            .unwrap_or_else(PoisonError::into_inner) = mode;
    }
}
