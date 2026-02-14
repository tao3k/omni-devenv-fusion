//! Tests for schema migration (v1 → v2: TOOL_NAME Utf8 → Dictionary).

use lance::dataset::Dataset;
use lance::deps::arrow_array::types::Int32Type;
use lance::deps::arrow_array::{
    DictionaryArray, FixedSizeListArray, Float32Array, Int32Array, RecordBatch,
    RecordBatchIterator, StringArray,
};
use lance::deps::arrow_schema::{DataType, Field, Schema};
use omni_vector::{MigrateResult, OMNI_SCHEMA_VERSION, VectorStore, schema_version_from_schema};
use std::sync::Arc;

fn dict_from_strings(values: &[String]) -> DictionaryArray<Int32Type> {
    let uniq: Vec<String> = values.iter().cloned().collect();
    let keys: Vec<i32> = (0..values.len() as i32).collect();
    let value_arr = StringArray::from(uniq);
    DictionaryArray::<Int32Type>::try_new(Int32Array::from(keys), Arc::new(value_arr))
        .expect("dictionary")
}

/// Build a v1 schema (TOOL_NAME as Utf8; skill_name/category as Dictionary to match migration pass-through).
fn v1_batch(num_rows: usize) -> (Arc<Schema>, RecordBatch) {
    let dim = 4i32;
    let schema = Arc::new(Schema::new(vec![
        Field::new("id", DataType::Utf8, false),
        Field::new(
            "vector",
            DataType::FixedSizeList(Arc::new(Field::new("item", DataType::Float32, true)), dim),
            false,
        ),
        Field::new("content", DataType::Utf8, false),
        Field::new_dictionary("skill_name", DataType::Int32, DataType::Utf8, true),
        Field::new_dictionary("category", DataType::Int32, DataType::Utf8, true),
        Field::new("tool_name", DataType::Utf8, true),
        Field::new("file_path", DataType::Utf8, true),
        Field::new("routing_keywords", DataType::Utf8, true),
        Field::new("intents", DataType::Utf8, true),
    ]));

    let ids: Vec<_> = (0..num_rows).map(|i| format!("id-{i}")).collect();
    let vectors: Vec<f32> = (0..num_rows * dim as usize).map(|i| i as f32).collect();
    let contents: Vec<_> = (0..num_rows).map(|i| format!("content-{i}")).collect();
    let skill_names: Vec<_> = (0..num_rows).map(|i| format!("skill_{i}")).collect();
    let categories: Vec<_> = (0..num_rows).map(|i| format!("cat_{i}")).collect();
    let tool_names: Vec<_> = (0..num_rows).map(|i| format!("tool.cmd_{i}")).collect();
    let file_paths: Vec<_> = (0..num_rows).map(|i| format!("path/{i}.py")).collect();
    let routing: Vec<_> = (0..num_rows).map(|_| "kw".to_string()).collect();
    let intents: Vec<_> = (0..num_rows).map(|_| "intent".to_string()).collect();

    let id_arr = Arc::new(StringArray::from(ids));
    let values_arr = Arc::new(Float32Array::from(vectors));
    let vector_arr = Arc::new(FixedSizeListArray::new(
        Arc::new(Field::new("item", DataType::Float32, true)),
        dim,
        values_arr,
        None,
    ));
    let content_arr = Arc::new(StringArray::from(contents));
    let skill_arr = Arc::new(dict_from_strings(&skill_names));
    let category_arr = Arc::new(dict_from_strings(&categories));
    let tool_arr = Arc::new(StringArray::from(tool_names));
    let file_arr = Arc::new(StringArray::from(file_paths));
    let routing_arr = Arc::new(StringArray::from(routing));
    let intents_arr = Arc::new(StringArray::from(intents));

    let batch = RecordBatch::try_new(
        schema.clone(),
        vec![
            id_arr,
            vector_arr,
            content_arr,
            skill_arr,
            category_arr,
            tool_arr,
            file_arr,
            routing_arr,
            intents_arr,
        ],
    )
    .expect("v1 batch");

    (schema, batch)
}

#[tokio::test]
async fn migration_check_and_migrate_v1_to_v2() {
    let temp_dir = tempfile::tempdir().unwrap();
    let base = temp_dir.path();
    let table_name = "t";
    let table_uri = base.join(format!("{table_name}.lance"));

    let (v1_schema, v1_batch) = v1_batch(2);
    let reader = RecordBatchIterator::new(vec![Ok(v1_batch)], v1_schema);
    Dataset::write(Box::new(reader), table_uri.to_str().unwrap(), None)
        .await
        .expect("write v1 dataset");

    let mut store =
        VectorStore::new_with_keyword_index(base.to_str().unwrap(), Some(4), false, None, None)
            .await
            .expect("store");

    let pending = store
        .check_migrations(table_name)
        .await
        .expect("check_migrations");
    assert_eq!(pending.len(), 1, "one pending migration v1→v2");
    assert_eq!(pending[0].from_version, 1);
    assert_eq!(pending[0].to_version, 2);

    let MigrateResult {
        applied,
        rows_processed,
    } = store.migrate(table_name).await.expect("migrate");
    assert_eq!(applied.as_slice(), &[(1, 2)]);
    assert_eq!(rows_processed, 2);

    let count = store.count(table_name).await.expect("count");
    assert_eq!(count, 2, "row count preserved");

    let table_path = store.table_path(table_name);
    let dataset = store
        .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
        .await
        .expect("open after migrate");
    let arrow_schema = Arc::new(lance::deps::arrow_schema::Schema::from(dataset.schema()));
    let version = schema_version_from_schema(arrow_schema.as_ref());
    assert_eq!(version, OMNI_SCHEMA_VERSION, "schema is v2 after migrate");
}
