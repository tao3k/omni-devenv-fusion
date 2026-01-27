//! JSON Expression to LanceDB WHERE clause converter.
//!
//! Converts JSON Expression filters to SQL WHERE clauses for native
//! LanceDB filter pushdown.
//!
//! # Supported Operators
//!
//! | JSON Expression | WHERE Clause |
//! |-----------------|--------------|
//! | `{"category": "git"}` | `category = 'git'` |
//! | `{"score": {"$gt": 0.8}}` | `score > 0.8` |
//! | `{"count": {"$gte": 5}}` | `count >= 5` |
//! | `{"value": {"$lt": 100}}` | `value < 100` |
//! | `{"status": {"$lte": "active"}}` | `status <= 'active'` |
//! | `{"id": {"$ne": "deleted"}}` | `id != 'deleted'` |

use serde_json::Value;

/// Convert JSON Expression to LanceDB WHERE clause.
///
/// # Arguments
///
/// * `expr` - JSON Expression filter (e.g., `{"category": "git", "score": {"$gt": 0.8}}`)
///
/// # Returns
///
/// SQL WHERE clause string (e.g., `category = 'git' AND score > 0.8`)
///
/// # Examples
///
/// ```
/// use omni_vector::filter::json_to_lance_where;
/// use serde_json::json;
///
/// let expr = json!({"category": "git", "score": {"$gt": 0.8}});
/// let where_clause = json_to_lance_where(&expr);
/// assert_eq!(where_clause, "category = 'git' AND score > 0.8");
/// ```
pub fn json_to_lance_where(expr: &Value) -> String {
    match expr {
        Value::Object(map) => {
            let clauses: Vec<String> = map
                .iter()
                .map(|(k, v)| match v {
                    Value::String(s) => format!("{} = '{}'", k, s),
                    Value::Number(n) => format!("{} = {}", k, n),
                    Value::Bool(b) => format!("{} = {}", k, b),
                    Value::Object(inner) => {
                        // Handle comparison operators
                        if let Some(op) = inner.keys().next() {
                            let value = inner.get(op).unwrap_or(&Value::Null);
                            // Extract value as string for formatting
                            let value_str = match value {
                                Value::String(s) => format!("'{}'", s),
                                Value::Number(n) => n.to_string(),
                                Value::Bool(b) => b.to_string(),
                                _ => value.to_string(),
                            };
                            match op.as_str() {
                                "$gt" | ">" => format!("{} > {}", k, value_str),
                                "$gte" | ">=" => format!("{} >= {}", k, value_str),
                                "$lt" | "<" => format!("{} < {}", k, value_str),
                                "$lte" | "<=" => format!("{} <= {}", k, value_str),
                                "$ne" | "!=" => format!("{} != {}", k, value_str),
                                _ => format!("{} = '{}'", k, value),
                            }
                        } else {
                            format!("{} = '{}'", k, v)
                        }
                    }
                    _ => format!("{} = '{}'", k, v),
                })
                .collect();
            clauses.join(" AND ")
        }
        _ => String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
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
}
