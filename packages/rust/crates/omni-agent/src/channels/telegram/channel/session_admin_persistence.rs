use std::fs;
use std::path::Path;

use anyhow::Context;
use serde_yaml::{Mapping, Value};

pub(super) fn persist_session_admin_override_to_user_settings(
    user_settings_path: &Path,
    recipient: &str,
    admin_users: Option<&[String]>,
) -> anyhow::Result<()> {
    let scope = parse_scope(recipient)?;
    let mut root = load_settings_yaml(user_settings_path)?;
    let Some(root_map) = root.as_mapping_mut() else {
        return Err(anyhow::anyhow!(
            "invalid user settings yaml: root must be a mapping"
        ));
    };

    let changed = match scope {
        SessionAdminScope::Group { chat_id } => {
            apply_group_admin_override(root_map, chat_id.as_str(), admin_users)
        }
        SessionAdminScope::Topic { chat_id, thread_id } => {
            apply_topic_admin_override(root_map, chat_id.as_str(), thread_id, admin_users)
        }
    };
    if !changed {
        return Ok(());
    }

    if let Some(parent) = user_settings_path.parent() {
        fs::create_dir_all(parent).with_context(|| {
            format!(
                "failed to create user settings parent dir: {}",
                parent.display()
            )
        })?;
    }
    let serialized = serde_yaml::to_string(&root)
        .context("failed to serialize user settings yaml for session admin persistence")?;
    fs::write(user_settings_path, serialized).with_context(|| {
        format!(
            "failed to write user settings yaml: {}",
            user_settings_path.display()
        )
    })?;
    Ok(())
}

enum SessionAdminScope {
    Group { chat_id: String },
    Topic { chat_id: String, thread_id: i64 },
}

fn parse_scope(recipient: &str) -> anyhow::Result<SessionAdminScope> {
    let (chat_id, thread_id) = super::identity::parse_recipient_target(recipient);
    if !chat_id.starts_with('-') {
        return Err(anyhow::anyhow!(
            "recipient-scoped admin override is only supported for group chats"
        ));
    }
    match thread_id {
        Some(raw_thread_id) => {
            let parsed = raw_thread_id
                .parse::<i64>()
                .map_err(|_| anyhow::anyhow!("invalid topic id in recipient: {recipient}"))?;
            if parsed <= 0 {
                return Err(anyhow::anyhow!(
                    "invalid topic id in recipient: {recipient}"
                ));
            }
            Ok(SessionAdminScope::Topic {
                chat_id: chat_id.to_string(),
                thread_id: parsed,
            })
        }
        None => Ok(SessionAdminScope::Group {
            chat_id: chat_id.to_string(),
        }),
    }
}

fn load_settings_yaml(path: &Path) -> anyhow::Result<Value> {
    if !path.exists() {
        return Ok(Value::Mapping(Mapping::new()));
    }
    let raw = fs::read_to_string(path)
        .with_context(|| format!("failed to read user settings yaml: {}", path.display()))?;
    if raw.trim().is_empty() {
        return Ok(Value::Mapping(Mapping::new()));
    }
    let parsed = serde_yaml::from_str::<Value>(&raw)
        .with_context(|| format!("failed to parse user settings yaml: {}", path.display()))?;
    Ok(match parsed {
        Value::Null => Value::Mapping(Mapping::new()),
        other => other,
    })
}

fn yaml_key(key: &str) -> Value {
    Value::String(key.to_string())
}

fn apply_group_admin_override(
    root_map: &mut Mapping,
    chat_id: &str,
    admin_users: Option<&[String]>,
) -> bool {
    let Some(telegram_map) = ensure_child_mapping(root_map, "telegram", admin_users.is_some())
    else {
        return false;
    };
    let Some(groups_map) = ensure_child_mapping(telegram_map, "groups", admin_users.is_some())
    else {
        return false;
    };
    let group_key = yaml_key(chat_id);

    match admin_users {
        Some(entries) => {
            let group_value = groups_map
                .entry(group_key.clone())
                .or_insert_with(|| Value::Mapping(Mapping::new()));
            let Some(group_map) = ensure_value_mapping(group_value) else {
                return false;
            };
            set_admin_users(group_map, entries);
            true
        }
        None => {
            let Some(group_value) = groups_map.get_mut(&group_key) else {
                return false;
            };
            let Some(group_map) = ensure_value_mapping(group_value) else {
                return false;
            };
            let changed = group_map.remove(&yaml_key("admin_users")).is_some();
            if changed && group_map.is_empty() {
                groups_map.remove(&group_key);
            }
            prune_empty_groups_and_telegram(root_map);
            changed
        }
    }
}

fn apply_topic_admin_override(
    root_map: &mut Mapping,
    chat_id: &str,
    thread_id: i64,
    admin_users: Option<&[String]>,
) -> bool {
    let Some(telegram_map) = ensure_child_mapping(root_map, "telegram", admin_users.is_some())
    else {
        return false;
    };
    let Some(groups_map) = ensure_child_mapping(telegram_map, "groups", admin_users.is_some())
    else {
        return false;
    };
    let group_key = yaml_key(chat_id);
    let topic_key = yaml_key(&thread_id.to_string());

    match admin_users {
        Some(entries) => {
            let group_value = groups_map
                .entry(group_key.clone())
                .or_insert_with(|| Value::Mapping(Mapping::new()));
            let Some(group_map) = ensure_value_mapping(group_value) else {
                return false;
            };
            let Some(topics_map) = ensure_child_mapping(group_map, "topics", true) else {
                return false;
            };
            let topic_value = topics_map
                .entry(topic_key.clone())
                .or_insert_with(|| Value::Mapping(Mapping::new()));
            let Some(topic_map) = ensure_value_mapping(topic_value) else {
                return false;
            };
            set_admin_users(topic_map, entries);
            true
        }
        None => {
            let Some(group_value) = groups_map.get_mut(&group_key) else {
                return false;
            };
            let Some(group_map) = ensure_value_mapping(group_value) else {
                return false;
            };
            let Some(topics_value) = group_map.get_mut(&yaml_key("topics")) else {
                return false;
            };
            let Some(topics_map) = ensure_value_mapping(topics_value) else {
                return false;
            };
            let Some(topic_value) = topics_map.get_mut(&topic_key) else {
                return false;
            };
            let Some(topic_map) = ensure_value_mapping(topic_value) else {
                return false;
            };
            let changed = topic_map.remove(&yaml_key("admin_users")).is_some();
            if changed && topic_map.is_empty() {
                topics_map.remove(&topic_key);
            }
            if topics_map.is_empty() {
                group_map.remove(&yaml_key("topics"));
            }
            if group_map.is_empty() {
                groups_map.remove(&group_key);
            }
            prune_empty_groups_and_telegram(root_map);
            changed
        }
    }
}

fn ensure_child_mapping<'a>(
    parent: &'a mut Mapping,
    key: &str,
    create_if_missing: bool,
) -> Option<&'a mut Mapping> {
    let yaml_key = yaml_key(key);
    if !parent.contains_key(&yaml_key) {
        if !create_if_missing {
            return None;
        }
        parent.insert(yaml_key.clone(), Value::Mapping(Mapping::new()));
    }
    let value = parent.get_mut(&yaml_key)?;
    ensure_value_mapping(value)
}

fn ensure_value_mapping(value: &mut Value) -> Option<&mut Mapping> {
    if value.is_null() {
        *value = Value::Mapping(Mapping::new());
    }
    value.as_mapping_mut()
}

fn set_admin_users(target: &mut Mapping, admin_users: &[String]) {
    let value = admin_users.join(",");
    target.insert(yaml_key("admin_users"), Value::String(value));
}

fn prune_empty_groups_and_telegram(root_map: &mut Mapping) {
    let telegram_key = yaml_key("telegram");
    let groups_key = yaml_key("groups");
    let Some(telegram_value) = root_map.get_mut(&telegram_key) else {
        return;
    };
    let Some(telegram_map) = ensure_value_mapping(telegram_value) else {
        return;
    };
    let remove_groups = telegram_map
        .get(&groups_key)
        .and_then(Value::as_mapping)
        .is_some_and(Mapping::is_empty);
    if remove_groups {
        telegram_map.remove(&groups_key);
    }
    if telegram_map.is_empty() {
        root_map.remove(&telegram_key);
    }
}
