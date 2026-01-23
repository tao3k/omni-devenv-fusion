//! Tests for omni-lance crate.

use lance::deps::arrow_array::RecordBatchReader;
use omni_lance::{
    CONTENT_COLUMN, ID_COLUMN, METADATA_COLUMN, VECTOR_COLUMN, VectorRecordBatchReader,
    extract_optional_string, extract_string,
};

#[test]
fn test_default_schema() {
    let schema = VectorRecordBatchReader::default_schema(1536);
    let fields = schema.fields();

    assert_eq!(fields.len(), 4);
    assert_eq!(fields[0].name(), ID_COLUMN);
    assert_eq!(fields[1].name(), VECTOR_COLUMN);
    assert_eq!(fields[2].name(), CONTENT_COLUMN);
    assert_eq!(fields[3].name(), METADATA_COLUMN);
}

#[test]
fn test_from_vectors() {
    let reader = VectorRecordBatchReader::from_vectors(
        vec!["id1".to_string(), "id2".to_string()],
        vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]],
        vec!["content1".to_string(), "content2".to_string()],
        vec!["{}".to_string(), "{}".to_string()],
        3,
    )
    .unwrap();

    let schema = reader.schema();
    assert_eq!(schema.fields().len(), 4);
}

#[test]
fn test_extract_string() {
    use lance::deps::arrow_array::StringArray;

    let array = StringArray::from(vec!["hello", "world"]);
    assert_eq!(extract_string(&array, 0), "hello");
    assert_eq!(extract_string(&array, 1), "world");
}

#[test]
fn test_extract_string_null() {
    use lance::deps::arrow_array::StringArray;

    // Create array with null value at index 1
    let array = StringArray::from(vec![Some("hello"), None]);
    assert_eq!(extract_string(&array, 0), "hello");
    assert_eq!(extract_string(&array, 1), "");
}

#[test]
fn test_extract_optional_string_some() {
    use lance::deps::arrow_array::StringArray;

    let array = StringArray::from(vec!["hello", "world"]);
    let result = extract_optional_string(Some(&array), 0);
    assert_eq!(result, Some("hello".to_string()));
}

#[test]
fn test_extract_optional_string_null() {
    use lance::deps::arrow_array::StringArray;

    // Create array with null value at index 1
    let array = StringArray::from(vec![Some("hello"), None]);
    assert_eq!(
        extract_optional_string(Some(&array), 0),
        Some("hello".to_string())
    );
    assert_eq!(extract_optional_string(Some(&array), 1), None);
}

#[test]
fn test_extract_optional_string_array_none() {
    let result = extract_optional_string(None, 0);
    assert_eq!(result, None);
}
