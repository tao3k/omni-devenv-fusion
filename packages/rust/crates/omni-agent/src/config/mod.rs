//! Config namespace: agent config and MCP config loading.

mod agent;
mod mcp;
mod settings;

pub use agent::{
    AgentConfig, ContextBudgetStrategy, LITELLM_DEFAULT_URL, McpServerEntry, MemoryConfig,
};
pub use mcp::{McpConfigFile, McpServerEntryFile, load_mcp_config};
pub use settings::{
    DiscordSettings, EmbeddingSettings, McpSettings, MemorySettings, RuntimeSettings,
    SessionSettings, TelegramGroupSettings, TelegramSettings, TelegramTopicSettings,
    load_runtime_settings, load_runtime_settings_from_paths, runtime_settings_paths,
    set_config_home_override,
};
