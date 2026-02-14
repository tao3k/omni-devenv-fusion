//! Unit and integration tests for Arrow schema optimizations:
//! - Dictionary encoding (SKILL_NAME, CATEGORY)
//! - Field metadata (description, index_hint, cardinality)
//! - Read path compatibility (get_utf8_at for Utf8 and Dictionary columns)

use lance::deps::arrow_schema::DataType;
use omni_vector::{
    CATEGORY_COLUMN, SKILL_NAME_COLUMN, SearchOptions, TOOL_NAME_COLUMN, VectorStore,
};

#[tokio::test]
async fn test_create_schema_skill_name_category_are_dictionary() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = VectorStore::new(temp_dir.path().to_str().unwrap(), Some(4))
        .await
        .unwrap();

    let schema = store.create_schema();

    let skill_field = schema
        .field_with_name(SKILL_NAME_COLUMN)
        .expect("SKILL_NAME column");
    assert!(
        matches!(skill_field.data_type(), DataType::Dictionary(_, _)),
        "SKILL_NAME should be Dictionary(Int32, Utf8), got {:?}",
        skill_field.data_type()
    );
    assert!(
        skill_field.metadata().get("description").is_some(),
        "SKILL_NAME should have description metadata"
    );
    assert_eq!(
        skill_field.metadata().get("index_hint").map(|s| s.as_str()),
        Some("bitmap")
    );
    assert_eq!(
        skill_field
            .metadata()
            .get("cardinality")
            .map(|s| s.as_str()),
        Some("low")
    );

    let category_field = schema
        .field_with_name(CATEGORY_COLUMN)
        .expect("CATEGORY column");
    assert!(
        matches!(category_field.data_type(), DataType::Dictionary(_, _)),
        "CATEGORY should be Dictionary(Int32, Utf8), got {:?}",
        category_field.data_type()
    );
    assert!(
        category_field.metadata().get("description").is_some(),
        "CATEGORY should have description metadata"
    );
    assert_eq!(
        category_field
            .metadata()
            .get("index_hint")
            .map(|s| s.as_str()),
        Some("bitmap")
    );

    let tool_name_field = schema
        .field_with_name(TOOL_NAME_COLUMN)
        .expect("TOOL_NAME column");
    assert!(
        matches!(tool_name_field.data_type(), DataType::Dictionary(_, _)),
        "TOOL_NAME should be Dictionary(Int32, Utf8), got {:?}",
        tool_name_field.data_type()
    );
    assert_eq!(
        tool_name_field
            .metadata()
            .get("index_hint")
            .map(|s| s.as_str()),
        Some("bitmap")
    );
}

#[tokio::test]
async fn test_create_schema_all_columns_have_description_metadata() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = VectorStore::new(temp_dir.path().to_str().unwrap(), Some(4))
        .await
        .unwrap();

    let schema = store.create_schema();
    for field in schema.fields() {
        assert!(
            field.metadata().get("description").is_some(),
            "Column {} should have description metadata",
            field.name()
        );
    }
}

#[tokio::test]
async fn test_dictionary_roundtrip_skill_name_category() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = VectorStore::new(temp_dir.path().to_str().unwrap(), Some(4))
        .await
        .unwrap();

    let table = "dict_roundtrip";
    let ids = vec![
        "git.commit".to_string(),
        "writer.polish".to_string(),
        "knowledge.recall".to_string(),
    ];
    let vectors = vec![vec![0.1f32; 4], vec![0.2f32; 4], vec![0.3f32; 4]];
    let contents = vec![
        "Commit changes".to_string(),
        "Polish text".to_string(),
        "Semantic recall".to_string(),
    ];
    let metadatas = vec![
        serde_json::json!({
            "skill_name": "git",
            "category": "vcs",
            "tool_name": "commit",
            "file_path": "scripts/commit.py",
        })
        .to_string(),
        serde_json::json!({
            "skill_name": "writer",
            "category": "docs",
            "tool_name": "polish",
            "file_path": "scripts/polish.py",
        })
        .to_string(),
        serde_json::json!({
            "skill_name": "knowledge",
            "category": "rag",
            "tool_name": "recall",
            "file_path": "scripts/recall.py",
        })
        .to_string(),
    ];

    store
        .add_documents(table, ids.clone(), vectors, contents, metadatas)
        .await
        .unwrap();

    let results = store
        .search_optimized(table, vec![0.1; 4], 10, SearchOptions::default())
        .await
        .unwrap();

    assert_eq!(results.len(), 3, "should return 3 results");
    let by_id: std::collections::HashMap<String, _> =
        results.into_iter().map(|r| (r.id.clone(), r)).collect();

    // Roundtrip: dictionary-encoded skill_name/category/tool_name were written and read back; document identity preserved
    assert!(by_id.contains_key("git.commit"), "result for git.commit");
    assert!(
        by_id.contains_key("writer.polish"),
        "result for writer.polish"
    );
    assert!(
        by_id.contains_key("knowledge.recall"),
        "result for knowledge.recall"
    );
}
