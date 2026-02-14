//! Canonical per-skill payload types.
//!
//! These types represent the agreed parsing shape for one skill directory:
//! skill_name, SKILL.md path, metadata, skill_tools (map: tool_full_name → tool entry with
//! skill_tool_references: ref_key → path), references (map: ref_id → record with frontmatter + path).
//! Refs may come from this skill or other skills; a tool may reference multiple markdown files.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use super::metadata::{ReferenceRecord, SkillMetadata, ToolRecord};

/// One tool in the canonical payload: full tool data plus ref_key → path map.
///
/// `skill_tool_references`: keys are ref keys (e.g. `"researcher.references.run_research_graph"`),
/// values are resolved file paths. May include refs from other skills; multiple entries per tool.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct CanonicalToolEntry {
    /// Full tool record (decorator params + enrichment from scripts).
    pub tool: ToolRecord,
    /// Map from ref_key (e.g. `"<skill_name>.references.<ref_stem>"`) to resolved path.
    /// Source: references/*.md front matter (for_tools). May be same-skill or cross-skill.
    #[serde(default)]
    pub skill_tool_references: HashMap<String, String>,
}

/// Canonical payload for one skill after parsing its directory.
///
/// Matches the agreed shape: skill_name, SKILL.md path, metadata, skill_tools map,
/// references map. Used for verification and downstream index/API.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct CanonicalSkillPayload {
    /// Skill id (e.g. `"researcher"`).
    pub skill_name: String,
    /// Path to this skill's SKILL.md file.
    pub skill_md_path: String,
    /// Parsed SKILL.md YAML front matter only.
    pub metadata: SkillMetadata,
    /// Map from full tool name (`skill_name.tool_name`) to tool entry (record + skill_tool_references).
    #[serde(default)]
    pub skill_tools: HashMap<String, CanonicalToolEntry>,
    /// Map from ref_id (e.g. filename stem) to reference record (frontmatter + path).
    /// May include refs from this skill only at first; cross-skill can add more.
    #[serde(default)]
    pub references: HashMap<String, ReferenceRecord>,
}
