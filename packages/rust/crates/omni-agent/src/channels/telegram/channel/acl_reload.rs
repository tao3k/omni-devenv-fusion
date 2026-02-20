use std::path::{Path, PathBuf};
use std::sync::PoisonError;
use std::time::{Instant, UNIX_EPOCH};

use crate::config::{TelegramSettings, load_runtime_settings_from_paths};

use super::acl::resolve_acl_config_from_settings;
use super::{TELEGRAM_ACL_RELOAD_CHECK_INTERVAL, TelegramChannel};

#[derive(Debug, Clone, PartialEq, Eq, Default)]
struct SettingsFileFingerprint {
    exists: bool,
    modified_unix_ns: Option<u128>,
    len_bytes: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
struct SettingsFingerprint {
    system: SettingsFileFingerprint,
    user: SettingsFileFingerprint,
}

#[derive(Debug)]
pub(super) struct TelegramAclReloadState {
    pub(super) system_settings_path: PathBuf,
    pub(super) user_settings_path: PathBuf,
    last_fingerprint: SettingsFingerprint,
    last_check_at: Option<Instant>,
}

impl TelegramAclReloadState {
    pub(super) fn new(system_settings_path: PathBuf, user_settings_path: PathBuf) -> Self {
        let last_fingerprint =
            settings_fingerprint(system_settings_path.as_path(), user_settings_path.as_path());
        Self {
            system_settings_path,
            user_settings_path,
            last_fingerprint,
            last_check_at: None,
        }
    }
}

impl TelegramChannel {
    pub(super) fn ensure_acl_fresh(&self) {
        self.reload_acl_from_settings(false);
    }

    #[doc(hidden)]
    pub fn set_acl_reload_paths_for_test(
        &self,
        system_settings_path: PathBuf,
        user_settings_path: PathBuf,
    ) {
        let mut reload_state = self
            .acl_reload_state
            .write()
            .unwrap_or_else(PoisonError::into_inner);
        reload_state.system_settings_path = system_settings_path;
        reload_state.user_settings_path = user_settings_path;
        reload_state.last_fingerprint = SettingsFingerprint::default();
        reload_state.last_check_at = None;
    }

    #[doc(hidden)]
    pub fn reload_acl_from_settings_for_test(&self) {
        self.reload_acl_from_settings(true);
    }

    fn reload_acl_from_settings(&self, force: bool) {
        let (system_settings_path, user_settings_path, new_fingerprint) = {
            let mut reload_state = self
                .acl_reload_state
                .write()
                .unwrap_or_else(PoisonError::into_inner);
            if !force
                && reload_state
                    .last_check_at
                    .is_some_and(|last| last.elapsed() < TELEGRAM_ACL_RELOAD_CHECK_INTERVAL)
            {
                return;
            }
            reload_state.last_check_at = Some(Instant::now());
            let new_fingerprint = settings_fingerprint(
                reload_state.system_settings_path.as_path(),
                reload_state.user_settings_path.as_path(),
            );
            if !force && new_fingerprint == reload_state.last_fingerprint {
                return;
            }
            (
                reload_state.system_settings_path.clone(),
                reload_state.user_settings_path.clone(),
                new_fingerprint,
            )
        };

        let settings = load_runtime_settings_from_paths(
            system_settings_path.as_path(),
            user_settings_path.as_path(),
        );
        match self.apply_telegram_acl_settings(settings.telegram) {
            Ok(()) => {
                let policy = self
                    .control_command_policy
                    .read()
                    .unwrap_or_else(PoisonError::into_inner);
                let slash_policy = self
                    .slash_command_policy
                    .read()
                    .unwrap_or_else(PoisonError::into_inner);
                let group_policy = self
                    .group_policy_config
                    .read()
                    .unwrap_or_else(PoisonError::into_inner);
                tracing::info!(
                    event = "telegram.acl.settings_reloaded",
                    system_path = %system_settings_path.display(),
                    user_path = %user_settings_path.display(),
                    allowed_users = self
                        .allowed_users
                        .read()
                        .unwrap_or_else(PoisonError::into_inner)
                        .len(),
                    allowed_groups = self
                        .allowed_groups
                        .read()
                        .unwrap_or_else(PoisonError::into_inner)
                        .len(),
                    admin_users = policy.admin_users.len(),
                    control_allow_override = policy
                        .control_command_allow_from
                        .as_ref()
                        .map(|entries| entries.len())
                        .unwrap_or(0),
                    slash_global_override = slash_policy
                        .control_command_allow_from
                        .as_ref()
                        .map(|entries| entries.len())
                        .unwrap_or(0),
                    group_policy = ?group_policy.group_policy,
                    group_allow_override = group_policy
                        .group_allow_from
                        .as_ref()
                        .map(|entries| entries.len())
                        .unwrap_or(0),
                    require_mention = group_policy.require_mention,
                    group_overrides = group_policy.groups.len(),
                    "Telegram ACL reloaded from settings"
                );
            }
            Err(error) => {
                tracing::warn!(
                    event = "telegram.acl.settings_reload_failed",
                    system_path = %system_settings_path.display(),
                    user_path = %user_settings_path.display(),
                    error = %error,
                    "Telegram ACL reload failed; keeping existing ACL"
                );
            }
        }

        let mut reload_state = self
            .acl_reload_state
            .write()
            .unwrap_or_else(PoisonError::into_inner);
        reload_state.last_fingerprint = new_fingerprint;
        reload_state.last_check_at = Some(Instant::now());
    }

    fn apply_telegram_acl_settings(&self, settings: TelegramSettings) -> anyhow::Result<()> {
        let config = resolve_acl_config_from_settings(settings)?;
        *self
            .allowed_users
            .write()
            .unwrap_or_else(PoisonError::into_inner) = config.allowed_users;
        *self
            .allowed_groups
            .write()
            .unwrap_or_else(PoisonError::into_inner) = config.allowed_groups;
        *self
            .control_command_policy
            .write()
            .unwrap_or_else(PoisonError::into_inner) = config.control_command_policy;
        *self
            .slash_command_policy
            .write()
            .unwrap_or_else(PoisonError::into_inner) = config.slash_command_policy;
        *self
            .group_policy_config
            .write()
            .unwrap_or_else(PoisonError::into_inner) = config.group_policy_config;
        *self
            .session_admin_persist
            .write()
            .unwrap_or_else(PoisonError::into_inner) = config.session_admin_persist;
        Ok(())
    }
}

fn settings_fingerprint(
    system_settings_path: &Path,
    user_settings_path: &Path,
) -> SettingsFingerprint {
    SettingsFingerprint {
        system: settings_file_fingerprint(system_settings_path),
        user: settings_file_fingerprint(user_settings_path),
    }
}

fn settings_file_fingerprint(path: &Path) -> SettingsFileFingerprint {
    match std::fs::metadata(path) {
        Ok(metadata) => SettingsFileFingerprint {
            exists: true,
            modified_unix_ns: metadata
                .modified()
                .ok()
                .and_then(|modified| modified.duration_since(UNIX_EPOCH).ok())
                .map(|duration| duration.as_nanos()),
            len_bytes: Some(metadata.len()),
        },
        Err(_) => SettingsFileFingerprint::default(),
    }
}
