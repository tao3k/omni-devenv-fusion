#![allow(missing_docs)]

use omni_agent::TelegramSessionPartition;

#[test]
fn session_partition_default_is_chat_only() {
    assert_eq!(
        TelegramSessionPartition::default(),
        TelegramSessionPartition::ChatOnly
    );
}

#[test]
fn session_partition_parse_aliases() {
    assert_eq!(
        "chat_user".parse::<TelegramSessionPartition>().ok(),
        Some(TelegramSessionPartition::ChatUser)
    );
    assert_eq!(
        "chat".parse::<TelegramSessionPartition>().ok(),
        Some(TelegramSessionPartition::ChatOnly)
    );
    assert_eq!(
        "user".parse::<TelegramSessionPartition>().ok(),
        Some(TelegramSessionPartition::UserOnly)
    );
    assert_eq!(
        "topic-user".parse::<TelegramSessionPartition>().ok(),
        Some(TelegramSessionPartition::ChatThreadUser)
    );
}

#[test]
fn session_partition_build_session_key() {
    assert_eq!(
        TelegramSessionPartition::ChatUser.build_session_key("-200", "888", None),
        "-200:888"
    );
    assert_eq!(
        TelegramSessionPartition::ChatOnly.build_session_key("-200", "888", None),
        "-200"
    );
    assert_eq!(
        TelegramSessionPartition::UserOnly.build_session_key("-200", "888", None),
        "888"
    );
    assert_eq!(
        TelegramSessionPartition::ChatThreadUser.build_session_key("-200", "888", Some(42)),
        "-200:42:888"
    );
}
