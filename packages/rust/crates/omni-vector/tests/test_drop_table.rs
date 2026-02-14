//! Tests for drop_table and keyword index cleanup.
//!
//! These tests ensure that when dropping skills/router tables,
//! the keyword index is properly cleared to avoid stale data issues.

use omni_vector::VectorStore;
use std::path::PathBuf;

/// Helper to create a temporary directory for tests.
fn create_temp_db() -> (tempfile::TempDir, PathBuf) {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_db");
    (temp_dir, db_path)
}

/// Helper to add a tool to the store for testing.
async fn add_test_tool(store: &VectorStore, id: &str, skill_name: &str, tool_name: &str) {
    let metadata = serde_json::json!({
        "type": "command",
        "skill_name": skill_name,
        "tool_name": tool_name,
        "command": tool_name,
        "file_path": format!("{}/scripts/test.py", skill_name),
        "function_name": tool_name,
        "keywords": [skill_name, tool_name],
        "intents": [],
        "file_hash": "test_hash_123",
        "input_schema": "{}",
        "docstring": "Test tool"
    })
    .to_string();

    store
        .add_documents(
            "skills",
            vec![id.to_string()],
            vec![vec![0.1; 1024]],
            vec![format!("Test tool {}", tool_name)],
            vec![metadata],
        )
        .await
        .unwrap();
}

/// Helper to add tools to the keyword index for testing.
fn add_to_keyword_index(store: &VectorStore, name: &str, description: &str, category: &str) {
    if let Some(ref kw_index) = store.keyword_index {
        kw_index
            .upsert_document(name, description, category, &[], &[])
            .unwrap();
    }
}

#[tokio::test]
async fn test_drop_table_clears_keyword_index_for_skills() {
    // Create store with keyword index
    let (_temp_dir, db_path) = create_temp_db();
    let mut store = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add initial tools to both LanceDB and keyword index
    add_test_tool(&store, "git.commit", "git", "commit").await;
    add_to_keyword_index(&store, "git.commit", "Create git commits", "git");

    // Verify tools exist
    let count_before = store.count("skills").await.unwrap();
    assert_eq!(count_before, 1, "Should have 1 tool before drop");

    // Add some stale data directly to keyword index (simulating the bug)
    add_to_keyword_index(
        &store,
        "STALE_TOOL.stale_function",
        "Stale tool that should be removed",
        "stale_skill",
    );

    // Verify stale data exists before drop
    assert!(
        store.keyword_index_contains("stale"),
        "Stale tool should exist before drop_table"
    );

    // Drop the table (should also clear keyword index)
    store.drop_table("skills").await.unwrap();

    // Recreate and verify
    let store2 = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add tools again after drop
    add_test_tool(&store2, "git.commit", "git", "commit").await;

    // Verify the stale tool is NOT in the keyword index
    assert!(
        !store2.keyword_index_contains("stale"),
        "Stale tool should not exist in keyword index after drop_table"
    );

    // But valid tool should exist
    assert!(
        store2.keyword_index_contains("git"),
        "Valid tool 'git.commit' should exist in keyword index"
    );
}

#[tokio::test]
async fn test_drop_table_clears_keyword_index_for_router() {
    let (_temp_dir, db_path) = create_temp_db();
    let mut store = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add initial data
    add_test_tool(&store, "researcher.analyze", "researcher", "analyze").await;
    add_to_keyword_index(
        &store,
        "researcher.analyze",
        "Research and analyze",
        "researcher",
    );

    // Add stale data
    add_to_keyword_index(&store, "STALE.stale", "Stale entry", "stale");

    // Verify stale data exists
    assert!(
        store.keyword_index_contains("stale"),
        "Stale data should exist before drop"
    );

    // Drop router table (should also clear keyword index)
    store.drop_table("router").await.unwrap();

    // Recreate and verify
    let store2 = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add tools again
    add_test_tool(&store2, "researcher.analyze", "researcher", "analyze").await;

    // Verify stale data is gone
    assert!(
        !store2.keyword_index_contains("stale"),
        "Stale data should be removed after drop_table for router"
    );
}

#[tokio::test]
async fn test_drop_and_reindex_removes_stale_tools() {
    let (_temp_dir, db_path) = create_temp_db();
    let mut store = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add initial tools with routable "stale" names (simulating stale data; UUID-like
    // names are not indexed by design, so use a routable stale_skill)
    add_test_tool(
        &store,
        "stale_skill.stale_tool",
        "stale_skill",
        "stale_tool",
    )
    .await;

    // Verify stale tool exists in keyword index before drop
    assert!(
        store.keyword_index_contains("stale"),
        "Stale tool should exist before drop"
    );

    // Drop and recreate
    store.drop_table("skills").await.unwrap();

    // Create new store
    let store2 = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add clean tools (no UUID skill names)
    add_test_tool(&store2, "git.commit", "git", "commit").await;
    add_test_tool(&store2, "git.status", "git", "status").await;

    // Verify only clean tools exist
    let count = store2.count("skills").await.unwrap();
    assert_eq!(count, 2, "Should have exactly 2 clean tools");

    // Verify keyword index contains only clean tools
    assert!(
        !store2.keyword_index_contains("ee50478c"),
        "UUID tool should not exist in keyword index"
    );

    assert!(
        store2.keyword_index_contains("git"),
        "Git tools should exist in keyword index"
    );
}

#[tokio::test]
async fn test_clear_keyword_index_method() {
    let (_temp_dir, db_path) = create_temp_db();
    let mut store = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add data to keyword index with unique identifier
    add_to_keyword_index(&store, "UNIQUE_TEST_12345.tool", "Test description", "test");

    // Verify data exists
    assert!(
        store.keyword_index_contains("UNIQUE_TEST_12345"),
        "Test tool should exist before clear"
    );

    // Clear keyword index
    store.clear_keyword_index().unwrap();

    // Verify data is gone
    assert!(
        store.keyword_index_is_empty(),
        "Keyword index should be empty after clear"
    );

    // Verify the tool no longer exists
    assert!(
        !store.keyword_index_contains("UNIQUE_TEST_12345"),
        "Test tool should not exist after clear"
    );
}

#[tokio::test]
async fn test_drop_table_preserves_related_tools() {
    let (_temp_dir, db_path) = create_temp_db();
    let mut store = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add git-related tools
    add_test_tool(&store, "git.commit", "git", "commit").await;
    add_test_tool(&store, "git.status", "git", "status").await;
    add_test_tool(&store, "git.log", "git", "log").await;

    // Add a stale tool
    add_test_tool(&store, "STALE.stale", "STALE", "stale").await;

    // Verify all tools exist
    let count_before = store.count("skills").await.unwrap();
    assert_eq!(count_before, 4, "Should have 4 tools before drop");

    // Drop and recreate
    store.drop_table("skills").await.unwrap();
    let store2 = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1024),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Re-add only git tools (simulating clean reindex)
    add_test_tool(&store2, "git.commit", "git", "commit").await;
    add_test_tool(&store2, "git.status", "git", "status").await;
    add_test_tool(&store2, "git.log", "git", "log").await;

    // Verify only git tools exist
    let count_after = store2.count("skills").await.unwrap();
    assert_eq!(count_after, 3, "Should have exactly 3 git tools");

    // Verify stale tool is gone
    assert!(
        !store2.keyword_index_contains("stale"),
        "Stale tool should not exist after clean reindex"
    );

    // Verify git tools exist
    assert!(
        store2.keyword_index_contains("git"),
        "Git tools should exist"
    );
}
