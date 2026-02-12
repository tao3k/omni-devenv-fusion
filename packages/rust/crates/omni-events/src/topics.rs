//! Event topic constants for type-safe routing.

/// File changed event
pub const FILE_CHANGED: &str = "file/changed";
/// File created event
pub const FILE_CREATED: &str = "file/created";
/// File deleted event
pub const FILE_DELETED: &str = "file/deleted";
/// File renamed event
pub const FILE_RENAMED: &str = "file/renamed";

/// Agent think event
pub const AGENT_THINK: &str = "agent/think";
/// Agent action event
pub const AGENT_ACTION: &str = "agent/action";
/// Agent result event
pub const AGENT_RESULT: &str = "agent/result";

/// MCP request event
pub const MCP_REQUEST: &str = "mcp/request";
/// MCP response event
pub const MCP_RESPONSE: &str = "mcp/response";

/// System shutdown event
pub const SYSTEM_SHUTDOWN: &str = "system/shutdown";
/// System ready event
pub const SYSTEM_READY: &str = "system/ready";

/// Cortex index updated event
pub const CORTEX_INDEX_UPDATED: &str = "cortex/index_updated";
/// Cortex query event
pub const CORTEX_QUERY: &str = "cortex/query";

/// Omega mission started
pub const OMEGA_MISSION_START: &str = "omega/mission/start";
/// Omega mission completed
pub const OMEGA_MISSION_COMPLETE: &str = "omega/mission/complete";
/// Omega mission failed
pub const OMEGA_MISSION_FAIL: &str = "omega/mission/fail";

/// Omega semantic scan started
pub const OMEGA_SEMANTIC_SCAN: &str = "omega/semantic/scan";
/// Omega semantic scan complete
pub const OMEGA_SEMANTIC_COMPLETE: &str = "omega/semantic/complete";

/// Omega experience load started
pub const OMEGA_EXPERIENCE_LOAD: &str = "omega/experience/load";
/// Omega experience loaded
pub const OMEGA_EXPERIENCE_LOADED: &str = "omega/experience/loaded";

/// Omega task decomposition started
pub const OMEGA_TASK_DECOMPOSE: &str = "omega/task/decompose";
/// Omega task decomposition complete
pub const OMEGA_TASK_DECOMPOSED: &str = "omega/task/decomposed";

/// Omega branch isolation started
pub const OMEGA_BRANCH_ISOLATE: &str = "omega/branch/isolate";
/// Omega branch created
pub const OMEGA_BRANCH_CREATED: &str = "omega/branch/created";
/// Omega branch merged
pub const OMEGA_BRANCH_MERGED: &str = "omega/branch/merged";
/// Omega branch rolled back
pub const OMEGA_BRANCH_ROLLBACK: &str = "omega/branch/rollback";

/// Omega task started
pub const OMEGA_TASK_START: &str = "omega/task/start";
/// Omega task completed
pub const OMEGA_TASK_COMPLETE: &str = "omega/task/complete";
/// Omega task failed
pub const OMEGA_TASK_FAIL: &str = "omega/task/fail";

/// Omega conflict detected
pub const OMEGA_CONFLICT_DETECTED: &str = "omega/conflict/detected";
/// Omega conflict resolved
pub const OMEGA_CONFLICT_RESOLVED: &str = "omega/conflict/resolved";

/// Omega recovery triggered
pub const OMEGA_RECOVERY_TRIGGER: &str = "omega/recovery/trigger";
/// Omega recovery success
pub const OMEGA_RECOVERY_SUCCESS: &str = "omega/recovery/success";

/// Omega skill crystallization started
pub const OMEGA_SKILL_CRYSTALLIZE: &str = "omega/skill/crystallize";
/// Omega skill crystallized
pub const OMEGA_SKILL_CRYSTALLIZED: &str = "omega/skill/crystallized";

/// TUI event (forwarded from Python)
pub const TUI_EVENT: &str = "tui/event";

/// All topics as a const array for iteration
pub const ALL_TOPICS: &[(&str, &str)] = &[
    ("FILE_CHANGED", FILE_CHANGED),
    ("FILE_CREATED", FILE_CREATED),
    ("FILE_DELETED", FILE_DELETED),
    ("FILE_RENAMED", FILE_RENAMED),
    ("AGENT_THINK", AGENT_THINK),
    ("AGENT_ACTION", AGENT_ACTION),
    ("AGENT_RESULT", AGENT_RESULT),
    ("MCP_REQUEST", MCP_REQUEST),
    ("MCP_RESPONSE", MCP_RESPONSE),
    ("SYSTEM_SHUTDOWN", SYSTEM_SHUTDOWN),
    ("SYSTEM_READY", SYSTEM_READY),
    ("CORTEX_INDEX_UPDATED", CORTEX_INDEX_UPDATED),
    ("CORTEX_QUERY", CORTEX_QUERY),
    ("OMEGA_MISSION_START", OMEGA_MISSION_START),
    ("OMEGA_MISSION_COMPLETE", OMEGA_MISSION_COMPLETE),
    ("OMEGA_MISSION_FAIL", OMEGA_MISSION_FAIL),
    ("OMEGA_SEMANTIC_SCAN", OMEGA_SEMANTIC_SCAN),
    ("OMEGA_SEMANTIC_COMPLETE", OMEGA_SEMANTIC_COMPLETE),
    ("OMEGA_EXPERIENCE_LOAD", OMEGA_EXPERIENCE_LOAD),
    ("OMEGA_EXPERIENCE_LOADED", OMEGA_EXPERIENCE_LOADED),
    ("OMEGA_TASK_DECOMPOSE", OMEGA_TASK_DECOMPOSE),
    ("OMEGA_TASK_DECOMPOSED", OMEGA_TASK_DECOMPOSED),
    ("OMEGA_BRANCH_ISOLATE", OMEGA_BRANCH_ISOLATE),
    ("OMEGA_BRANCH_CREATED", OMEGA_BRANCH_CREATED),
    ("OMEGA_BRANCH_MERGED", OMEGA_BRANCH_MERGED),
    ("OMEGA_BRANCH_ROLLBACK", OMEGA_BRANCH_ROLLBACK),
    ("OMEGA_TASK_START", OMEGA_TASK_START),
    ("OMEGA_TASK_COMPLETE", OMEGA_TASK_COMPLETE),
    ("OMEGA_TASK_FAIL", OMEGA_TASK_FAIL),
    ("OMEGA_CONFLICT_DETECTED", OMEGA_CONFLICT_DETECTED),
    ("OMEGA_CONFLICT_RESOLVED", OMEGA_CONFLICT_RESOLVED),
    ("OMEGA_RECOVERY_TRIGGER", OMEGA_RECOVERY_TRIGGER),
    ("OMEGA_RECOVERY_SUCCESS", OMEGA_RECOVERY_SUCCESS),
    ("OMEGA_SKILL_CRYSTALLIZE", OMEGA_SKILL_CRYSTALLIZE),
    ("OMEGA_SKILL_CRYSTALLIZED", OMEGA_SKILL_CRYSTALLIZED),
    ("TUI_EVENT", TUI_EVENT),
];

/// Topics grouped by category
pub mod file {
    use super::*;

    /// File-related topics.
    pub const TOPICS: &[(&str, &str)] = &[
        ("CHANGED", FILE_CHANGED),
        ("CREATED", FILE_CREATED),
        ("DELETED", FILE_DELETED),
        ("RENAMED", FILE_RENAMED),
    ];
}

/// Agent-related topics.
pub mod agent {
    use super::*;

    /// Agent lifecycle topics.
    pub const TOPICS: &[(&str, &str)] = &[
        ("THINK", AGENT_THINK),
        ("ACTION", AGENT_ACTION),
        ("RESULT", AGENT_RESULT),
    ];
}

/// Omega workflow topics.
pub mod omega {
    use super::*;

    /// Core omega execution topics.
    pub const TOPICS: &[(&str, &str)] = &[
        ("MISSION_START", OMEGA_MISSION_START),
        ("MISSION_COMPLETE", OMEGA_MISSION_COMPLETE),
        ("MISSION_FAIL", OMEGA_MISSION_FAIL),
        ("TASK_START", OMEGA_TASK_START),
        ("TASK_COMPLETE", OMEGA_TASK_COMPLETE),
        ("TASK_FAIL", OMEGA_TASK_FAIL),
    ];
}
