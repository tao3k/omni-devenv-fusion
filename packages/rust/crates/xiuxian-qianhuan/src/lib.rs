//! System prompt injection window based on XML Q&A blocks.
//!
//! Contract:
//! - Root tag: `<system_prompt_injection>`
//! - Entry tag: `<qa><q>...</q><a>...</a><source>...</source></qa>`
//! - `<source>` is optional.

mod config;
mod contracts;
mod entry;
mod error;
mod window;
mod xml;

pub use config::InjectionWindowConfig;
pub use contracts::{
    InjectionMode, InjectionOrderStrategy, InjectionPolicy, InjectionSnapshot, PromptContextBlock,
    PromptContextCategory, PromptContextSource, RoleMixProfile, RoleMixRole,
};
pub use entry::QaEntry;
pub use error::InjectionError;
pub use window::SystemPromptInjectionWindow;
pub use xml::SYSTEM_PROMPT_INJECTION_TAG;
