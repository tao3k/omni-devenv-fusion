use anyhow::Result;

use super::Agent;

pub(super) struct ToolCallOutput {
    pub(super) text: String,
    pub(super) is_error: bool,
}

impl Agent {
    pub(super) async fn mcp_tools_for_llm(&self) -> Result<Option<Vec<serde_json::Value>>> {
        let Some(ref mcp) = self.mcp else {
            return Ok(None);
        };
        let list = mcp.list_tools(None).await?;
        let tools: Vec<serde_json::Value> = list
            .tools
            .iter()
            .map(|t| {
                let mut obj = serde_json::Map::new();
                obj.insert(
                    "name".to_string(),
                    serde_json::Value::String(t.name.to_string()),
                );
                if let Some(ref d) = t.description {
                    obj.insert(
                        "description".to_string(),
                        serde_json::Value::String(d.to_string()),
                    );
                }
                let schema = serde_json::Value::Object(t.input_schema.as_ref().clone());
                obj.insert("parameters".to_string(), schema);
                serde_json::Value::Object(obj)
            })
            .collect();
        if tools.is_empty() {
            return Ok(None);
        }
        Ok(Some(tools))
    }

    pub(super) async fn call_mcp_tool_with_diagnostics(
        &self,
        name: &str,
        arguments: Option<serde_json::Value>,
    ) -> Result<ToolCallOutput> {
        let Some(ref mcp) = self.mcp else {
            return Err(anyhow::anyhow!("no MCP client"));
        };
        let result = mcp.call_tool(name.to_string(), arguments).await?;
        let text: String = result
            .content
            .iter()
            .filter_map(|c| {
                if let rmcp::model::RawContent::Text(t) = &c.raw {
                    Some(t.text.as_str())
                } else {
                    None
                }
            })
            .collect();
        Ok(ToolCallOutput {
            text,
            is_error: result.is_error.unwrap_or(false),
        })
    }
}
