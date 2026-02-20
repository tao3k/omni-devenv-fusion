//! Session-scoped foreground gating.

mod config;
mod core;
mod local;
mod types;
mod valkey;

pub use types::SessionGate;
