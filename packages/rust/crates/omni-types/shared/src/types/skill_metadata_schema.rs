// Auto-generated Rust types from shared schema.
// Source: skill_metadata.schema

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::shared::types::*;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SkillMetadata {
    #[serde(rename = "authors", default)]
    pub authors: Option<Vec<Value>>,
    #[serde(rename = "description", default)]
    pub description: Option<String>,
    #[serde(rename = "intents", default)]
    pub intents: Option<Vec<Value>>,
    #[serde(rename = "permissions", default)]
    pub permissions: Option<Vec<Value>>,
    #[serde(rename = "repository", default)]
    pub repository: Option<String>,
    #[serde(rename = "require_refs", default)]
    pub require_refs: Option<Vec<Value>>,
    #[serde(rename = "routing_keywords", default)]
    pub routing_keywords: Option<Vec<Value>>,
    #[serde(rename = "skill_name", default)]
    pub skill_name: Option<String>,
    #[serde(rename = "version", default)]
    pub version: Option<String>,
}

pub type Referencepath = String;
