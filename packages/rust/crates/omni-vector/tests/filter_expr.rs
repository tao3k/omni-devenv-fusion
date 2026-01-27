//! Tests for filter expression utilities.

use omni_vector::filter::json_to_lance_where;
use serde_json::json;

#[test]
fn test_string_equality() {
    let expr = json!({"category": "git"});
    assert_eq!(json_to_lance_where(&expr), "category = 'git'");
}

#[test]
fn test_number_equality() {
    let expr = json!({"score": 0.8});
    assert_eq!(json_to_lance_where(&expr), "score = 0.8");
}

#[test]
fn test_boolean_equality() {
    let expr = json!({"enabled": true});
    assert_eq!(json_to_lance_where(&expr), "enabled = true");
}

#[test]
fn test_greater_than() {
    let expr = json!({"score": {"$gt": 0.8}});
    assert_eq!(json_to_lance_where(&expr), "score > 0.8");
}

#[test]
fn test_greater_than_or_equal() {
    let expr = json!({"count": {"$gte": 5}});
    assert_eq!(json_to_lance_where(&expr), "count >= 5");
}

#[test]
fn test_less_than() {
    let expr = json!({"value": {"$lt": 100}});
    assert_eq!(json_to_lance_where(&expr), "value < 100");
}

#[test]
fn test_less_than_or_equal() {
    let expr = json!({"status": {"$lte": "active"}});
    assert_eq!(json_to_lance_where(&expr), "status <= 'active'");
}

#[test]
fn test_not_equal() {
    let expr = json!({"id": {"$ne": "deleted"}});
    assert_eq!(json_to_lance_where(&expr), "id != 'deleted'");
}

#[test]
fn test_multiple_conditions() {
    let expr = json!({
        "category": "git",
        "score": {"$gt": 0.8}
    });
    let where_clause = json_to_lance_where(&expr);
    assert!(where_clause.contains("category = 'git'"));
    assert!(where_clause.contains("score > 0.8"));
    assert!(where_clause.contains(" AND "));
}

#[test]
fn test_empty_object() {
    let expr = json!({});
    assert_eq!(json_to_lance_where(&expr), "");
}

#[test]
fn test_non_object() {
    let expr = json!("invalid");
    assert_eq!(json_to_lance_where(&expr), "");
}

#[test]
fn test_nested_comparison_aliases() {
    // Test that ">" works same as "$gt"
    let expr = json!({"score": {">": 0.5}});
    assert_eq!(json_to_lance_where(&expr), "score > 0.5");
}

#[test]
fn test_boolean_false() {
    let expr = json!({"enabled": false});
    assert_eq!(json_to_lance_where(&expr), "enabled = false");
}

#[test]
fn test_string_with_spaces() {
    let expr = json!({"category": "version control"});
    assert_eq!(json_to_lance_where(&expr), "category = 'version control'");
}
