// Auto-generated Rust types from shared schema.
// Source: tool.schema

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::shared::types::*;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ToolSchema {
    #[serde(rename = "info", default)]
    pub info: Option<HashMap<String, Value>>,
    #[serde(rename = "tools", default)]
    pub tools: Option<Vec<Value>>,
}
