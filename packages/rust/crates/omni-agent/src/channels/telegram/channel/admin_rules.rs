use crate::channels::control_command_rule_specs::{
    CommandSelectorAuthRule, parse_control_command_rule_specs,
};
use anyhow::Result;

use super::identity::normalize_user_identity;

pub(super) type TelegramCommandAdminRule = CommandSelectorAuthRule;

pub(super) fn parse_admin_command_rule_specs(
    specs: Vec<String>,
) -> Result<Vec<TelegramCommandAdminRule>> {
    parse_control_command_rule_specs(specs, "admin command rule", normalize_user_identity)
}
