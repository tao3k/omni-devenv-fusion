//! Snapshot tests for data-layer behavior and API contracts.

use insta::assert_json_snapshot;
use omni_vector::{
    ID_COLUMN, SearchOptions, TableColumnAlteration, TableColumnType, TableNewColumn, VectorStore,
    skill::{normalize_input_schema_value, resolve_routing_keywords},
};
use serde_json::json;

fn round6(v: f64) -> String {
    format!("{v:.6}")
}

#[test]
fn snapshot_input_schema_normalization_contract_v1() {
    let cases = vec![
        json!({"type":"object","properties":{"q":{"type":"string"}}}),
        json!("{\"type\":\"object\",\"properties\":{\"q\":{\"type\":\"string\"}}}"),
        json!(
            "\"{\\\"type\\\":\\\"object\\\",\\\"properties\\\":{\\\"q\\\":{\\\"type\\\":\\\"string\\\"}}}\""
        ),
        json!(null),
        json!("not-json"),
    ];

    let normalized: Vec<_> = cases
        .iter()
        .map(|c| normalize_input_schema_value(c))
        .collect();

    assert_json_snapshot!("input_schema_normalization_contract_v1", normalized);
}

#[test]
fn snapshot_routing_keywords_resolution_contract_v1() {
    let cases = vec![
        json!({"routing_keywords":["find","files"],"keywords":["legacy","noise"]}),
        json!({"keywords":["legacy","fallback"]}),
        json!({"routing_keywords":["find","find","  files  ",""]}),
        json!({}),
    ];
    let resolved: Vec<_> = cases
        .iter()
        .map(|meta| resolve_routing_keywords(meta))
        .collect();
    assert_json_snapshot!("routing_keywords_resolution_contract_v1", resolved);
}

#[tokio::test]
async fn snapshot_data_layer_contract_v1() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("data_layer_snapshot_store");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(4))
        .await
        .unwrap();
    let table = "skills";

    store
        .add_documents(
            table,
            vec!["tool.alpha".to_string(), "tool.beta".to_string()],
            vec![vec![1.0, 0.0, 0.0, 0.0], vec![0.0, 1.0, 0.0, 0.0]],
            vec!["alpha-old".to_string(), "beta-old".to_string()],
            vec![
                json!({"kind":"seed","rank":1}).to_string(),
                json!({"kind":"seed","rank":2}).to_string(),
            ],
        )
        .await
        .unwrap();

    let merge_stats = store
        .merge_insert_documents(
            table,
            vec!["tool.beta".to_string(), "tool.gamma".to_string()],
            vec![vec![0.0, 1.0, 0.0, 0.0], vec![0.0, 0.0, 1.0, 0.0]],
            vec!["beta-new".to_string(), "gamma-new".to_string()],
            vec![
                json!({"kind":"merged","rank":20}).to_string(),
                json!({"kind":"merged","rank":30}).to_string(),
            ],
            ID_COLUMN,
        )
        .await
        .unwrap();

    let mut results = store
        .search_optimized(
            table,
            vec![0.0, 1.0, 0.0, 0.0],
            10,
            SearchOptions::default(),
        )
        .await
        .unwrap()
        .into_iter()
        .map(|r| {
            json!({
                "id": r.id,
                "content": r.content,
                "kind": r.metadata.get("kind").and_then(|v| v.as_str()).unwrap_or(""),
                "rank": r.metadata.get("rank").and_then(|v| v.as_i64()).unwrap_or_default(),
                "distance": round6(r.distance),
            })
        })
        .collect::<Vec<_>>();
    results.sort_by(|a, b| a["id"].as_str().cmp(&b["id"].as_str()));

    let info = store.get_table_info(table).await.unwrap();
    let versions = store.list_versions(table).await.unwrap();
    let fragment_stats = store.get_fragment_stats(table).await.unwrap();

    let mut frag_view = fragment_stats
        .into_iter()
        .map(|f| {
            json!({
                "id": f.id,
                "num_rows": f.num_rows,
                "num_data_files": f.num_data_files,
                "physical_rows": f.physical_rows.unwrap_or_default(),
            })
        })
        .collect::<Vec<_>>();
    frag_view.sort_by(|a, b| a["id"].as_u64().cmp(&b["id"].as_u64()));

    let view = json!({
        "merge_stats": {
            "inserted": merge_stats.inserted,
            "updated": merge_stats.updated,
            "deleted": merge_stats.deleted,
        },
        "table": {
            "num_rows": info.num_rows,
            "fragment_count": info.fragment_count,
            "versions": versions.len(),
        },
        "search_results": results,
        "fragments": frag_view,
    });

    assert_json_snapshot!("data_layer_contract_v1", view);
}

#[tokio::test]
async fn test_schema_evolution_guardrails_for_reserved_columns() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("schema_guardrails_store");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(4))
        .await
        .unwrap();
    let table = "skills";

    store
        .add_documents(
            table,
            vec!["tool.one".to_string()],
            vec![vec![1.0, 0.0, 0.0, 0.0]],
            vec!["one".to_string()],
            vec![json!({"kind":"seed"}).to_string()],
        )
        .await
        .unwrap();

    let drop_err = store
        .drop_columns(table, vec!["metadata".to_string()])
        .await
        .unwrap_err();
    assert!(drop_err.to_string().contains("reserved"));

    let alter_err = store
        .alter_columns(
            table,
            vec![TableColumnAlteration::Rename {
                path: "id".to_string(),
                new_name: "id2".to_string(),
            }],
        )
        .await
        .unwrap_err();
    assert!(alter_err.to_string().contains("reserved"));
}

#[tokio::test]
async fn snapshot_schema_evolution_pipeline_v1() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("schema_pipeline_store");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(4))
        .await
        .unwrap();
    let table = "skills";

    store
        .add_documents(
            table,
            vec!["tool.one".to_string()],
            vec![vec![1.0, 0.0, 0.0, 0.0]],
            vec!["one".to_string()],
            vec![json!({"kind":"seed"}).to_string()],
        )
        .await
        .unwrap();

    let version_seed = store.get_dataset_version(table).await.unwrap();

    store
        .add_columns(
            table,
            vec![TableNewColumn {
                name: "custom_note".to_string(),
                data_type: TableColumnType::Utf8,
                nullable: true,
            }],
        )
        .await
        .unwrap();
    let version_added = store.get_dataset_version(table).await.unwrap();
    let ds_added = store.checkout_version(table, version_added).await.unwrap();
    assert!(ds_added.schema().field("custom_note").is_some());

    store
        .alter_columns(
            table,
            vec![TableColumnAlteration::Rename {
                path: "custom_note".to_string(),
                new_name: "custom_label".to_string(),
            }],
        )
        .await
        .unwrap();
    let version_renamed = store.get_dataset_version(table).await.unwrap();
    let ds_renamed = store
        .checkout_version(table, version_renamed)
        .await
        .unwrap();
    assert!(ds_renamed.schema().field("custom_note").is_none());
    assert!(ds_renamed.schema().field("custom_label").is_some());

    store
        .drop_columns(table, vec!["custom_label".to_string()])
        .await
        .unwrap();
    let version_dropped = store.get_dataset_version(table).await.unwrap();
    let ds_dropped = store
        .checkout_version(table, version_dropped)
        .await
        .unwrap();
    assert!(ds_dropped.schema().field("custom_label").is_none());

    let view = json!({
        "versions": {
            "seed": version_seed,
            "added": version_added,
            "renamed": version_renamed,
            "dropped": version_dropped,
        },
        "checks": {
            "added_custom_note": ds_added.schema().field("custom_note").is_some(),
            "renamed_custom_label": ds_renamed.schema().field("custom_label").is_some(),
            "dropped_custom_label": ds_dropped.schema().field("custom_label").is_none(),
        }
    });

    assert_json_snapshot!("schema_evolution_pipeline_v1", view);
}

#[tokio::test]
async fn snapshot_lance_fts_contract_v1() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("fts_snapshot_store");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(4))
        .await
        .unwrap();
    let table = "tools";

    store
        .add_documents(
            table,
            vec!["git.commit".to_string(), "git.rebase".to_string()],
            vec![vec![1.0, 0.0, 0.0, 0.0], vec![0.0, 1.0, 0.0, 0.0]],
            vec![
                "Commit staged changes with message checks".to_string(),
                "Interactive rebase and history cleanup".to_string(),
            ],
            vec![
                json!({
                    "type":"command",
                    "skill_name":"git",
                    "tool_name":"git.commit",
                    "keywords":["commit","message"],
                    "intents":["save changes"]
                })
                .to_string(),
                json!({
                    "type":"command",
                    "skill_name":"git",
                    "tool_name":"git.rebase",
                    "keywords":["rebase","history"],
                    "intents":["rewrite history"]
                })
                .to_string(),
            ],
        )
        .await
        .unwrap();
    store.create_fts_index(table).await.unwrap();

    let mut commit_hits = store.search_fts(table, "commit", 5, None).await.unwrap();
    commit_hits.sort_by(|a, b| a.tool_name.cmp(&b.tool_name));

    let mut history_hits = store.search_fts(table, "history", 5, None).await.unwrap();
    history_hits.sort_by(|a, b| a.tool_name.cmp(&b.tool_name));

    let view = json!({
        "commit_hits": commit_hits.into_iter().map(|h| json!({
            "tool": h.tool_name,
            "skill": h.skill_name,
        })).collect::<Vec<_>>(),
        "history_hits": history_hits.into_iter().map(|h| json!({
            "tool": h.tool_name,
            "skill": h.skill_name,
        })).collect::<Vec<_>>(),
    });

    assert_json_snapshot!("lance_fts_contract_v1", view);
}
