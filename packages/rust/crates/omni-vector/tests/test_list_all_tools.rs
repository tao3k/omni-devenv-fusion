//! Tests for list_all_tools - verifies correct reading of dictionary-encoded columns.

use omni_scanner::skills::{ToolAnnotations, ToolRecord};
use omni_vector::VectorStore;

/// Test that list_all_tools correctly reads tool records from a table
/// with dictionary-encoded columns (skill_name, category, tool_name, etc).
#[tokio::test]
async fn test_list_all_tools_with_dictionary_columns() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_list_tools");

    // Create vector store with dimension 1024 (like Qwen3-Embedding)
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1024))
        .await
        .unwrap();

    // Create sample tool records (using the correct ToolRecord structure)
    let tools = vec![
        ToolRecord {
            tool_name: "commit".to_string(),
            description: "Create a git commit with proper message".to_string(),
            skill_name: "git".to_string(),
            file_path: "git/scripts/commit.py".to_string(),
            function_name: "commit".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["git".to_string(), "commit".to_string()],
            intents: vec!["Save code changes".to_string()],
            file_hash: "abc123".to_string(),
            input_schema: r#"{"type": "object", "properties": {"message": {"type": "string"}}}"#
                .to_string(),
            docstring: "Commit changes".to_string(),
            category: "version_control".to_string(),
            annotations: ToolAnnotations::default(),
            parameters: vec!["message".to_string()],
            skill_tools_refers: vec![],
            resource_uri: String::new(),
        },
        ToolRecord {
            tool_name: "push".to_string(),
            description: "Push commits to remote".to_string(),
            skill_name: "git".to_string(),
            file_path: "git/scripts/push.py".to_string(),
            function_name: "push".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["git".to_string(), "push".to_string()],
            intents: vec!["Upload code".to_string()],
            file_hash: "def456".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "Push to remote".to_string(),
            category: "version_control".to_string(),
            annotations: ToolAnnotations::default(),
            parameters: vec![],
            skill_tools_refers: vec![],
            resource_uri: String::new(),
        },
        ToolRecord {
            tool_name: "save".to_string(),
            description: "Save content to file".to_string(),
            skill_name: "writer".to_string(),
            file_path: "writer/scripts/save.py".to_string(),
            function_name: "save".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["write".to_string(), "save".to_string()],
            intents: vec!["Write to file".to_string()],
            file_hash: "ghi789".to_string(),
            input_schema: r#"{"type": "object", "properties": {"path": {"type": "string"}}}"#
                .to_string(),
            docstring: "Save file".to_string(),
            category: "file_editor".to_string(),
            annotations: ToolAnnotations::default(),
            parameters: vec!["path".to_string()],
            skill_tools_refers: vec![],
            resource_uri: String::new(),
        },
    ];

    // Add tools to table (this uses dictionary encoding for skill_name, category, tool_name)
    store.add("test_tools", tools).await.unwrap();

    // Verify count
    let count = store.count("test_tools").await.unwrap();
    assert_eq!(count, 3, "Should have 3 tools");

    // CRITICAL TEST: list_all_tools should correctly read dictionary-encoded columns
    let result = store.list_all_tools("test_tools").await.unwrap();

    // Parse the JSON result
    let tools_list: Vec<serde_json::Value> = serde_json::from_str(&result).unwrap();
    assert_eq!(tools_list.len(), 3, "Should return 3 tools");

    // Verify each tool has correct skill_name (this is where the bug manifested!)
    let mut skill_names: Vec<String> = tools_list
        .iter()
        .map(|t| t["skill_name"].as_str().unwrap_or("").to_string())
        .collect();
    skill_names.sort();

    assert_eq!(skill_names, vec!["git", "git", "writer"]);

    // Verify tool names are correctly extracted
    let tool_names: Vec<String> = tools_list
        .iter()
        .map(|t| t["tool_name"].as_str().unwrap_or("").to_string())
        .collect();
    assert!(tool_names.contains(&"commit".to_string()));
    assert!(tool_names.contains(&"push".to_string()));
    assert!(tool_names.contains(&"save".to_string()));
}

/// Test that list_all_tools handles empty table gracefully
#[tokio::test]
async fn test_list_all_tools_empty_table() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_empty");

    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1024))
        .await
        .unwrap();

    // Query non-existent table - should return empty array
    let result = store.list_all_tools("non_existent").await.unwrap();
    let tools_list: Vec<serde_json::Value> = serde_json::from_str(&result).unwrap();
    assert!(tools_list.is_empty());
}

/// Test that list_all_tools returns correct content field (which comes from description)
#[tokio::test]
async fn test_list_all_tools_content_field() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_content");

    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1024))
        .await
        .unwrap();

    let tools = vec![ToolRecord {
        tool_name: "tool".to_string(),
        description: "This is the description for embedding".to_string(),
        skill_name: "test".to_string(),
        file_path: "test/tool.py".to_string(),
        function_name: "tool".to_string(),
        execution_mode: "script".to_string(),
        keywords: vec![],
        intents: vec![],
        file_hash: "hash".to_string(),
        input_schema: "{}".to_string(),
        docstring: "Test".to_string(),
        category: "test".to_string(),
        annotations: ToolAnnotations::default(),
        parameters: vec![],
        skill_tools_refers: vec![],
        resource_uri: String::new(),
    }];

    store.add("content_test", tools).await.unwrap();

    let result = store.list_all_tools("content_test").await.unwrap();
    let tools_list: Vec<serde_json::Value> = serde_json::from_str(&result).unwrap();

    // Content comes from description field
    assert_eq!(
        tools_list[0]["content"],
        "This is the description for embedding"
    );
}

/// Test that list_all_tools handles multiple skills with same tool name correctly
#[tokio::test]
async fn test_list_all_tools_multiple_skills_same_tool_name() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_multi_skill");

    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1024))
        .await
        .unwrap();

    // Create tools from different skills with same tool name (e.g., "status")
    let tools = vec![
        ToolRecord {
            tool_name: "status".to_string(),
            description: "Git status command".to_string(),
            skill_name: "git".to_string(),
            file_path: "git/scripts/status.py".to_string(),
            function_name: "status".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["git".to_string(), "status".to_string()],
            intents: vec!["Check status".to_string()],
            file_hash: "abc123".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "Show git status".to_string(),
            category: "version_control".to_string(),
            annotations: ToolAnnotations::default(),
            parameters: vec![],
            skill_tools_refers: vec![],
            resource_uri: String::new(),
        },
        ToolRecord {
            tool_name: "status".to_string(),
            description: "Database status command".to_string(),
            skill_name: "database".to_string(),
            file_path: "database/scripts/status.py".to_string(),
            function_name: "status".to_string(),
            execution_mode: "script".to_string(),
            keywords: vec!["db".to_string(), "status".to_string()],
            intents: vec!["Check DB status".to_string()],
            file_hash: "def456".to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            docstring: "Show database status".to_string(),
            category: "database".to_string(),
            annotations: ToolAnnotations::default(),
            parameters: vec![],
            skill_tools_refers: vec![],
            resource_uri: String::new(),
        },
    ];

    store.add("multi_skill", tools).await.unwrap();

    let result = store.list_all_tools("multi_skill").await.unwrap();
    let tools_list: Vec<serde_json::Value> = serde_json::from_str(&result).unwrap();

    assert_eq!(tools_list.len(), 2);

    // Verify both skills are correctly identified
    let skill_names: Vec<String> = tools_list
        .iter()
        .map(|t| t["skill_name"].as_str().unwrap_or("").to_string())
        .collect();
    assert!(skill_names.contains(&"git".to_string()));
    assert!(skill_names.contains(&"database".to_string()));
}
