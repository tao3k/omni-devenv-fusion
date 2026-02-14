//! Tests for scalar index creation (BTree, Bitmap) and optimal type selection.

use std::sync::{Arc, Mutex};

use omni_vector::{IndexBuildProgress, IndexProgressCallback, ScalarIndexType, VectorStore};

async fn add_tools_table(store: &VectorStore, n: usize, categories: &[&str]) {
    let mut ids = Vec::with_capacity(n);
    let mut vectors = Vec::with_capacity(n);
    let mut contents = Vec::with_capacity(n);
    let mut metadatas = Vec::with_capacity(n);
    for i in 0..n {
        let cat = categories[i % categories.len()];
        let skill = format!("skill_{}", cat);
        ids.push(format!("{}.cmd_{}", skill, i));
        vectors.push(vec![0.1; 64]);
        contents.push(format!("content {}", i));
        metadatas.push(
            serde_json::json!({
                "skill_name": skill,
                "category": cat,
                "file_path": format!("{}/scripts/x.py", skill),
                "tool_name": format!("cmd_{}", i),
            })
            .to_string(),
        );
    }
    store
        .add_documents("tools", ids, vectors, contents, metadatas)
        .await
        .unwrap();
}

#[tokio::test]
async fn test_create_btree_index_returns_stats() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("btree_stats");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, 5, &["a", "b", "c"]).await;

    let stats = store
        .create_btree_index("tools", "skill_name")
        .await
        .unwrap();

    assert_eq!(stats.column, "skill_name");
    assert_eq!(stats.index_type, "btree");
    assert!(
        stats.duration_ms <= 10000,
        "build should finish in reasonable time"
    );
}

#[tokio::test]
async fn test_index_build_progress_callback_receives_started_and_done() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("progress_cb");
    let events: Arc<Mutex<Vec<IndexBuildProgress>>> = Arc::new(Mutex::new(Vec::new()));
    let events_clone = Arc::clone(&events);
    let cb: IndexProgressCallback = Arc::new(move |p| {
        events_clone.lock().unwrap().push(p);
    });
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap()
        .with_index_progress_callback(cb);
    add_tools_table(&store, 5, &["a", "b"]).await;

    let _ = store
        .create_btree_index("tools", "skill_name")
        .await
        .unwrap();

    let collected = events.lock().unwrap();
    assert!(collected.len() >= 2, "expected Started and Done");
    match &collected[0] {
        IndexBuildProgress::Started {
            table_name,
            index_type,
        } => {
            assert_eq!(table_name, "tools");
            assert_eq!(index_type, "btree");
        }
        _ => panic!("expected Started first"),
    }
    match collected.last().unwrap() {
        IndexBuildProgress::Done { duration_ms } => assert!(*duration_ms <= 10000),
        _ => panic!("expected Done last"),
    }
}

#[tokio::test]
async fn test_create_bitmap_index_returns_stats() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("bitmap_stats");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, 5, &["x", "y"]).await;

    let stats = store
        .create_bitmap_index("tools", "category")
        .await
        .unwrap();

    assert_eq!(stats.column, "category");
    assert_eq!(stats.index_type, "bitmap");
    assert!(stats.duration_ms <= 10000);
}

#[tokio::test]
async fn test_estimate_cardinality() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("cardinality");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, 10, &["cat_a", "cat_b", "cat_c"]).await;

    let card = store
        .estimate_cardinality("tools", "category")
        .await
        .unwrap();
    assert!(
        card >= 1 && card <= 10,
        "cardinality in 1..10, got {}",
        card
    );
}

#[tokio::test]
async fn test_create_optimal_scalar_index_low_cardinality_uses_bitmap() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("optimal");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, 50, &["low1", "low2", "low3"]).await;

    let stats = store
        .create_optimal_scalar_index("tools", "category")
        .await
        .unwrap();

    assert_eq!(stats.column, "category");
    assert_eq!(stats.index_type, "bitmap");
}

#[tokio::test]
async fn test_create_optimal_scalar_index_high_cardinality_uses_btree() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("optimal_btree");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    let categories: Vec<String> = (0..150).map(|i| format!("cat_{}", i)).collect();
    let categories: Vec<&str> = categories.iter().map(String::as_str).collect();
    add_tools_table(&store, 150, &categories).await;

    let stats = store
        .create_optimal_scalar_index("tools", "skill_name")
        .await
        .unwrap();

    assert_eq!(stats.column, "skill_name");
    assert_eq!(stats.index_type, "btree");
}

#[tokio::test]
async fn test_create_scalar_index_after_add_documents() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("scalar_idx");

    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();

    let metadata1 = serde_json::json!({
        "skill_name": "git",
        "category": "vcs",
        "file_path": "git/commit.py",
        "tool_name": "commit",
    })
    .to_string();
    let metadata2 = serde_json::json!({
        "skill_name": "python",
        "category": "runtime",
        "file_path": "python/run.py",
        "tool_name": "run",
    })
    .to_string();

    store
        .add_documents(
            "tools",
            vec!["git.commit".to_string(), "python.run".to_string()],
            vec![vec![0.1; 64], vec![0.2; 64]],
            vec!["commit msg".to_string(), "run script".to_string()],
            vec![metadata1, metadata2],
        )
        .await
        .unwrap();

    store
        .create_scalar_index("tools", "skill_name", ScalarIndexType::BTree)
        .await
        .unwrap();
    store
        .create_scalar_index("tools", "category", ScalarIndexType::Bitmap)
        .await
        .unwrap();

    let count = store.count("tools").await.unwrap();
    assert_eq!(count, 2);
}

/// Snapshot contract: IndexStats shape and index type selection (duration redacted for stability).
#[tokio::test]
async fn snapshot_scalar_index_stats_contract_v1() {
    use insta::assert_json_snapshot;

    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("scalar_snapshot");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, 20, &["git", "docker", "python"]).await;

    let btree_stats = store
        .create_btree_index("tools", "skill_name")
        .await
        .unwrap();
    let bitmap_stats = store
        .create_bitmap_index("tools", "category")
        .await
        .unwrap();
    let optimal_stats = store
        .create_optimal_scalar_index("tools", "category")
        .await
        .unwrap();

    let view = serde_json::json!({
        "btree": { "column": btree_stats.column, "index_type": btree_stats.index_type },
        "bitmap": { "column": bitmap_stats.column, "index_type": bitmap_stats.index_type },
        "optimal_category": {
            "column": optimal_stats.column,
            "index_type": optimal_stats.index_type,
        },
    });
    assert_json_snapshot!("scalar_index_stats_contract_v1", view);
}
