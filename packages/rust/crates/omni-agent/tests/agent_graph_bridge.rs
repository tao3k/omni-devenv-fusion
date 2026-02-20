#![allow(missing_docs)]

use omni_agent::{GraphBridgeRequest, validate_graph_bridge_request};
use serde_json::json;

#[test]
fn graph_bridge_rejects_empty_tool_name() {
    let request = GraphBridgeRequest {
        tool_name: "   ".to_string(),
        arguments: Some(json!({"query": "x"})),
    };
    let error = validate_graph_bridge_request(&request)
        .expect_err("empty tool name should fail validation");
    assert!(error.to_string().contains("tool_name"));
}

#[test]
fn graph_bridge_rejects_non_object_arguments() {
    let request = GraphBridgeRequest {
        tool_name: "researcher.run_research_graph".to_string(),
        arguments: Some(json!(["not", "an", "object"])),
    };
    let error = validate_graph_bridge_request(&request)
        .expect_err("non-object args should fail validation");
    assert!(error.to_string().contains("JSON object"));
}

#[test]
fn graph_bridge_request_serialization_contract_is_stable() {
    let request = GraphBridgeRequest {
        tool_name: "researcher.run_research_graph".to_string(),
        arguments: Some(json!({
            "repo_url": "https://github.com/example/project",
            "focus": ["architecture", "performance"]
        })),
    };

    let serialized = serde_json::to_value(&request).expect("serialize request");
    let expected = json!({
        "tool_name": "researcher.run_research_graph",
        "arguments": {
            "repo_url": "https://github.com/example/project",
            "focus": ["architecture", "performance"]
        }
    });
    assert_eq!(serialized, expected);
}
