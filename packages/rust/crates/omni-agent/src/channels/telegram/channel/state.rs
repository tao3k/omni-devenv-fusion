use std::sync::RwLock;
use std::time::Duration;

use crate::channels::control_command_authorization::ControlCommandPolicy;

use super::super::session_partition::TelegramSessionPartition;
use super::acl_reload::TelegramAclReloadState;
use super::admin_rules::TelegramCommandAdminRule;
use super::group_policy::TelegramGroupPolicyConfig;
use super::policy::TelegramSlashCommandRule;
use super::send_gate::{TelegramSendRateLimitBackend, TelegramSendRateLimitGateState};

pub(super) const TELEGRAM_ACL_RELOAD_CHECK_INTERVAL: Duration = Duration::from_millis(500);
pub(super) const TELEGRAM_API_BASE_ENV: &str = "OMNI_AGENT_TELEGRAM_API_BASE_URL";

/// Telegram channel — long-polls the Bot API for updates.
pub struct TelegramChannel {
    pub(super) bot_token: String,
    pub(super) api_base_url: String,
    pub(super) allowed_users: RwLock<Vec<String>>,
    pub(super) allowed_groups: RwLock<Vec<String>>,
    pub(super) control_command_policy: RwLock<ControlCommandPolicy<TelegramCommandAdminRule>>,
    pub(super) slash_command_policy: RwLock<ControlCommandPolicy<TelegramSlashCommandRule>>,
    pub(super) group_policy_config: RwLock<TelegramGroupPolicyConfig>,
    pub(super) session_admin_persist: RwLock<bool>,
    pub(super) session_partition: RwLock<TelegramSessionPartition>,
    pub(super) acl_reload_state: RwLock<TelegramAclReloadState>,
    pub(super) send_rate_limit_gate: tokio::sync::Mutex<TelegramSendRateLimitGateState>,
    pub(super) send_rate_limit_backend: TelegramSendRateLimitBackend,
    pub(super) client: reqwest::Client,
}

impl TelegramChannel {
    pub(super) fn api_url(&self, method: &str) -> String {
        format!(
            "{}/bot{}/{method}",
            self.api_base_url.trim_end_matches('/'),
            self.bot_token
        )
    }
}
