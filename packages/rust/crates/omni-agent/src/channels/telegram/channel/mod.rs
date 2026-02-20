//! Telegram channel transport and message formatting.

mod acl;
mod acl_reload;
mod admin_rules;
mod authorization;
mod chunking;
mod client;
mod constants;
mod constructor;
mod error;
mod group_policy;
mod identity;
mod listen;
mod markdown;
mod media;
mod parsing;
mod policy;
mod recipient_admin;
mod send_api;
mod send_attachments;
mod send_gate;
mod send_text;
mod send_types;
mod session_admin_persistence;
mod state;
mod trait_impl;

pub(in crate::channels::telegram::channel) use super::session_partition::TelegramSessionPartition;
pub use chunking::{
    chunk_marker_reserve_chars, decorate_chunk_for_telegram, split_message_for_telegram,
};
pub use constants::TELEGRAM_MAX_MESSAGE_LENGTH;
pub(in crate::channels::telegram::channel) use group_policy::TelegramGroupPolicyMode;
#[doc(hidden)]
pub use markdown::{markdown_to_telegram_html, markdown_to_telegram_markdown_v2};
pub(in crate::channels::telegram::channel) use policy::TelegramSlashCommandRule;
pub use policy::{TelegramControlCommandPolicy, TelegramSlashCommandPolicy};
pub use state::TelegramChannel;
pub(in crate::channels::telegram::channel) use state::{
    TELEGRAM_ACL_RELOAD_CHECK_INTERVAL, TELEGRAM_API_BASE_ENV,
};
