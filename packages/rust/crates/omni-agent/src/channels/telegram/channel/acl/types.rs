use crate::channels::control_command_authorization::ControlCommandPolicy;

use super::super::TelegramSlashCommandRule;
use super::super::admin_rules::TelegramCommandAdminRule;
use super::super::group_policy::TelegramGroupPolicyConfig;

pub(super) const TELEGRAM_ACL_FIELD_ALLOWED_USERS: &str = "telegram.allowed_users";
pub(super) const TELEGRAM_ACL_FIELD_GROUP_ALLOW_FROM: &str = "telegram.group_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_ADMIN_USERS: &str = "telegram.admin_users";
pub(super) const TELEGRAM_ACL_FIELD_CONTROL_COMMAND_ALLOW_FROM: &str =
    "telegram.control_command_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_ADMIN_COMMAND_RULES: &str = "telegram.admin_command_rules";
pub(super) const TELEGRAM_ACL_FIELD_SLASH_COMMAND_ALLOW_FROM: &str =
    "telegram.slash_command_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_SLASH_SESSION_STATUS_ALLOW_FROM: &str =
    "telegram.slash_session_status_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_SLASH_SESSION_BUDGET_ALLOW_FROM: &str =
    "telegram.slash_session_budget_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_SLASH_SESSION_MEMORY_ALLOW_FROM: &str =
    "telegram.slash_session_memory_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_SLASH_SESSION_FEEDBACK_ALLOW_FROM: &str =
    "telegram.slash_session_feedback_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_SLASH_JOB_ALLOW_FROM: &str = "telegram.slash_job_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_SLASH_JOBS_ALLOW_FROM: &str = "telegram.slash_jobs_allow_from";
pub(super) const TELEGRAM_ACL_FIELD_SLASH_BG_ALLOW_FROM: &str = "telegram.slash_bg_allow_from";

pub(in crate::channels::telegram::channel) struct TelegramAclConfig {
    pub(in crate::channels::telegram::channel) allowed_users: Vec<String>,
    pub(in crate::channels::telegram::channel) allowed_groups: Vec<String>,
    pub(in crate::channels::telegram::channel) control_command_policy:
        ControlCommandPolicy<TelegramCommandAdminRule>,
    pub(in crate::channels::telegram::channel) slash_command_policy:
        ControlCommandPolicy<TelegramSlashCommandRule>,
    pub(in crate::channels::telegram::channel) group_policy_config: TelegramGroupPolicyConfig,
    pub(in crate::channels::telegram::channel) session_admin_persist: bool,
}
