#![allow(missing_docs)]
#![allow(dead_code)]

mod managed_runtime {
    pub mod parsing {
        include!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/src/channels/managed_runtime/parsing.rs"
        ));
    }
    pub mod session_partition {
        include!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/src/channels/managed_runtime/session_partition.rs"
        ));
    }
}

use managed_runtime::parsing::{
    SessionPartitionModeToken, parse_session_partition_mode_token, session_partition_mode_name,
};
use managed_runtime::session_partition::{SessionPartitionProfile, supported_modes};

#[test]
fn supported_modes_are_always_parseable() {
    for mode in supported_modes(SessionPartitionProfile::Telegram) {
        assert!(
            parse_session_partition_mode_token(mode).is_some(),
            "telegram mode should be parseable: {mode}",
        );
    }
    for mode in supported_modes(SessionPartitionProfile::Discord) {
        assert!(
            parse_session_partition_mode_token(mode).is_some(),
            "discord mode should be parseable: {mode}",
        );
    }
}

#[test]
fn partition_mode_name_and_parser_roundtrip() {
    let cases = [
        SessionPartitionModeToken::Chat,
        SessionPartitionModeToken::ChatUser,
        SessionPartitionModeToken::User,
        SessionPartitionModeToken::ChatThreadUser,
        SessionPartitionModeToken::GuildChannelUser,
        SessionPartitionModeToken::Channel,
        SessionPartitionModeToken::GuildUser,
    ];
    for case in cases {
        let name = session_partition_mode_name(case);
        assert_eq!(parse_session_partition_mode_token(name), Some(case));
    }
}
