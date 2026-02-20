use std::sync::PoisonError;

use crate::channels::control_command_authorization::{
    ControlCommandAuthSource, ControlCommandAuthorization,
    resolve_control_command_authorization_with_policy,
};

use super::TelegramChannel;
use super::identity::normalize_user_identity;

impl TelegramChannel {
    pub(super) fn is_admin_identity(&self, identity: &str) -> bool {
        self.ensure_acl_fresh();
        let normalized = normalize_user_identity(identity);
        self.control_command_policy
            .read()
            .unwrap_or_else(PoisonError::into_inner)
            .admin_users
            .iter()
            .any(|entry| entry == "*" || entry == &normalized)
    }

    pub(super) fn authorize_control_command(&self, identity: &str, command_text: &str) -> bool {
        self.resolve_control_command_authorization(identity, command_text)
            .allowed
    }

    fn resolve_control_command_authorization(
        &self,
        identity: &str,
        command_text: &str,
    ) -> ControlCommandAuthorization {
        self.ensure_acl_fresh();
        let normalized = normalize_user_identity(identity);
        let control_command_policy = self
            .control_command_policy
            .read()
            .unwrap_or_else(PoisonError::into_inner);
        resolve_control_command_authorization_with_policy(
            &normalized,
            command_text,
            &control_command_policy,
        )
    }

    pub(super) fn authorize_control_command_for_recipient(
        &self,
        identity: &str,
        command_text: &str,
        recipient: &str,
    ) -> bool {
        let authorization = self.resolve_control_command_authorization(identity, command_text);
        if authorization.allowed {
            return true;
        }
        if authorization.source != ControlCommandAuthSource::AdminUsers {
            return false;
        }
        let Some(group_admin_users) = self.resolve_group_command_admin_users(recipient) else {
            return false;
        };
        let normalized = normalize_user_identity(identity);
        group_admin_users
            .iter()
            .any(|entry| entry == "*" || entry == &normalized)
    }

    pub(super) fn authorize_slash_command(&self, identity: &str, command_scope: &str) -> bool {
        self.resolve_slash_command_authorization(identity, command_scope)
            .allowed
    }

    fn resolve_slash_command_authorization(
        &self,
        identity: &str,
        command_scope: &str,
    ) -> ControlCommandAuthorization {
        self.ensure_acl_fresh();
        let normalized = normalize_user_identity(identity);
        let slash_command_policy = self
            .slash_command_policy
            .read()
            .unwrap_or_else(PoisonError::into_inner);
        resolve_control_command_authorization_with_policy(
            &normalized,
            command_scope,
            &slash_command_policy,
        )
    }

    pub(super) fn authorize_slash_command_for_recipient(
        &self,
        identity: &str,
        command_scope: &str,
        recipient: &str,
    ) -> bool {
        let authorization = self.resolve_slash_command_authorization(identity, command_scope);
        if authorization.allowed {
            return true;
        }
        if authorization.source != ControlCommandAuthSource::AdminUsers {
            return false;
        }
        let Some(group_admin_users) = self.resolve_group_command_admin_users(recipient) else {
            return false;
        };
        let normalized = normalize_user_identity(identity);
        group_admin_users
            .iter()
            .any(|entry| entry == "*" || entry == &normalized)
    }
}
