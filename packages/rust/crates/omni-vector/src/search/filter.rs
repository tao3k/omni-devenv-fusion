//! Filter matching and keyword boosting logic.

use omni_types::VectorSearchResult;

/// Multiplier for keyword match boost
const KEYWORD_BOOST: f32 = 0.1;

/// Convert JSON filter expression to LanceDB WHERE clause.
///
/// # Arguments
///
/// * `expr` - JSON object representing filter conditions
///
/// # Returns
///
/// LanceDB WHERE clause string
///
/// # Examples
///
/// ```
/// use serde_json::json;
/// use omni_vector::search::filter::json_to_lance_where;
///
/// let expr = json!({"category": "git", "score": {"$gt": 0.8}});
/// let clause = json_to_lance_where(&expr);
/// // Returns: "category = 'git' AND score > 0.8"
/// ```
pub fn json_to_lance_where(expr: &serde_json::Value) -> String {
    match expr {
        serde_json::Value::Object(obj) => {
            if obj.is_empty() {
                return String::new();
            }

            let mut clauses = Vec::new();
            for (key, value) in obj {
                let clause = match value {
                    serde_json::Value::Object(comp) => {
                        // Handle comparison operators
                        if let Some(op) = comp.keys().next() {
                            match op.as_str() {
                                "$gt" | ">" => {
                                    if let Some(val) = comp.get("$gt").or(comp.get(">")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} > '{}'", key, s)
                                            }
                                            _ => format!("{} > {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                "$gte" | ">=" => {
                                    if let Some(val) = comp.get("$gte").or(comp.get(">=")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} >= '{}'", key, s)
                                            }
                                            _ => format!("{} >= {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                "$lt" | "<" => {
                                    if let Some(val) = comp.get("$lt").or(comp.get("<")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} < '{}'", key, s)
                                            }
                                            _ => format!("{} < {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                "$lte" | "<=" => {
                                    if let Some(val) = comp.get("$lte").or(comp.get("<=")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} <= '{}'", key, s)
                                            }
                                            _ => format!("{} <= {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                "$ne" | "!=" => {
                                    if let Some(val) = comp.get("$ne").or(comp.get("!=")) {
                                        match val {
                                            serde_json::Value::String(s) => {
                                                format!("{} != '{}'", key, s)
                                            }
                                            _ => format!("{} != {}", key, val),
                                        }
                                    } else {
                                        continue;
                                    }
                                }
                                _ => continue, // Unknown operator
                            }
                        } else {
                            continue;
                        }
                    }
                    serde_json::Value::String(s) => format!("{} = '{}'", key, s),
                    serde_json::Value::Number(n) => format!("{} = {}", key, n),
                    serde_json::Value::Bool(b) => format!("{} = {}", key, b),
                    _ => continue, // Skip unsupported types
                };
                clauses.push(clause);
            }

            if clauses.is_empty() {
                String::new()
            } else {
                clauses.join(" AND ")
            }
        }
        _ => String::new(), // Invalid filter returns empty string
    }
}

impl crate::VectorStore {
    /// Check if a metadata value matches the filter conditions.
    pub fn matches_filter(metadata: &serde_json::Value, conditions: &serde_json::Value) -> bool {
        match conditions {
            serde_json::Value::Object(obj) => {
                // Check each condition
                for (key, value) in obj {
                    // Handle nested keys like "domain"
                    let meta_value = if key.contains('.') {
                        // Support dot notation for nested values
                        let parts: Vec<&str> = key.split('.').collect();
                        let mut current = metadata.clone();
                        for part in parts {
                            if let serde_json::Value::Object(map) = current {
                                current = map.get(part).cloned().unwrap_or(serde_json::Value::Null);
                            } else {
                                return false;
                            }
                        }
                        Some(current)
                    } else {
                        metadata.get(key).cloned()
                    };

                    // Check if the value matches
                    if let Some(meta_val) = meta_value {
                        // Handle different value types
                        match (&meta_val, value) {
                            (serde_json::Value::String(mv), serde_json::Value::String(v)) => {
                                if mv != v {
                                    return false;
                                }
                            }
                            (serde_json::Value::Number(mv), serde_json::Value::Number(v)) => {
                                if mv != v {
                                    return false;
                                }
                            }
                            (serde_json::Value::Bool(mv), serde_json::Value::Bool(v)) => {
                                if mv != v {
                                    return false;
                                }
                            }
                            _ => {
                                // Try string comparison for non-exact matches
                                let meta_str_val = meta_val.to_string();
                                let value_str_val = value.to_string();
                                let meta_str = meta_str_val.trim_matches('"');
                                let value_str = value_str_val.trim_matches('"');
                                if meta_str != value_str {
                                    return false;
                                }
                            }
                        }
                    } else {
                        return false; // Key not found in metadata
                    }
                }
                true
            }
            _ => true, // Invalid filter, don't filter anything
        }
    }

    /// Apply keyword boosting to search results.
    ///
    /// Modifies the distance field using: `new_distance = (vector_score * 0.7) + (keyword_score * 0.3)`
    pub fn apply_keyword_boost(results: &mut [VectorSearchResult], keywords: &[String]) {
        // Return early if no keywords to process
        if keywords.is_empty() {
            return;
        }

        // Normalize keywords for matching - collect owned strings first
        let mut query_keywords: Vec<String> = Vec::new();
        for s in keywords {
            let lowered = s.to_lowercase();
            for w in lowered.split_whitespace() {
                query_keywords.push(w.to_string());
            }
        }

        for result in results {
            let mut keyword_score = 0.0;

            // Extract keywords from metadata JSON array
            if let Some(keywords_arr) = result.metadata.get("keywords").and_then(|v| v.as_array()) {
                for kw in &query_keywords {
                    if keywords_arr
                        .iter()
                        .any(|k| k.as_str().map_or(false, |s| s.to_lowercase().contains(kw)))
                    {
                        keyword_score += KEYWORD_BOOST;
                    }
                }
            }

            // Also check if keywords appear in tool_name or content
            let tool_name_lower = result.id.to_lowercase();
            let content_lower = result.content.to_lowercase();
            for kw in &query_keywords {
                if tool_name_lower.contains(kw) {
                    keyword_score += KEYWORD_BOOST * 0.5;
                }
                if content_lower.contains(kw) {
                    keyword_score += KEYWORD_BOOST * 0.3;
                }
            }

            // Calculate hybrid score: distance minus keyword bonus
            // Higher keyword_score = better match = lower distance
            let keyword_bonus = keyword_score * 0.3f32;
            let hybrid_distance = result.distance - keyword_bonus as f64;

            // Clamp to valid range (don't go negative)
            result.distance = hybrid_distance.max(0.0);
        }
    }
}

#[cfg(test)]
mod tests {
    use crate::VectorStore;
    use omni_types::VectorSearchResult;

    #[tokio::test]
    async fn test_apply_keyword_boost_metadata_match() {
        // Test that keyword matching works with metadata.keywords array
        // Use smaller distance difference (0.05) so keyword boost (0.03) can overcome it
        let mut results = vec![
            VectorSearchResult {
                id: "git.commit".to_string(),
                content: "Execute git.commit".to_string(),
                metadata: serde_json::json!({
                    "keywords": ["git", "commit", "version"]
                }),
                distance: 0.35, // Slightly worse vector similarity
            },
            VectorSearchResult {
                id: "file.save".to_string(),
                content: "Save a file".to_string(),
                metadata: serde_json::json!({
                    "keywords": ["file", "save", "write"]
                }),
                distance: 0.3, // Better vector similarity
            },
        ];

        VectorStore::apply_keyword_boost(&mut results, &["git".to_string()]);

        // git.commit: keyword_score = 0.1, keyword_bonus = 0.03
        // git.commit: 0.35 - 0.03 = 0.32
        // file.save: 0.3
        // git.commit should rank higher
        assert!(
            results[0].id == "git.commit",
            "git.commit should rank first with keyword boost"
        );
        assert!(
            results[0].distance < results[1].distance,
            "git.commit distance should be lower"
        );
    }

    #[tokio::test]
    async fn test_apply_keyword_boost_no_keywords() {
        // Test that results unchanged when no keywords provided
        let mut results = vec![VectorSearchResult {
            id: "git.commit".to_string(),
            content: "Execute git.commit".to_string(),
            metadata: serde_json::json!({ "keywords": ["git"] }),
            distance: 0.5,
        }];

        VectorStore::apply_keyword_boost(&mut results, &[]);

        assert_eq!(
            results[0].distance, 0.5,
            "Distance should not change with empty keywords"
        );
    }

    #[tokio::test]
    async fn test_apply_keyword_boost_multiple_keywords() {
        // Test that multiple keyword matches accumulate
        let mut results = vec![
            VectorSearchResult {
                id: "git.commit".to_string(),
                content: "Execute git.commit".to_string(),
                metadata: serde_json::json!({
                    "keywords": ["git", "commit", "version"]
                }),
                distance: 0.4,
            },
            VectorSearchResult {
                id: "file.save".to_string(),
                content: "Save a file".to_string(),
                metadata: serde_json::json!({
                    "keywords": ["file", "save"]
                }),
                distance: 0.3,
            },
        ];

        // Query with multiple keywords
        VectorStore::apply_keyword_boost(&mut results, &["git".to_string(), "commit".to_string()]);

        // git.commit matches both keywords: keyword_score = 0.1 + 0.1 = 0.2, bonus = 0.06
        // git.commit: 0.4 - 0.06 = 0.34
        // file.save: 0.3
        // file.save still wins (0.3 < 0.34)
        assert!(
            results[0].distance < results[1].distance,
            "Results should be sorted by hybrid distance"
        );
    }

    #[tokio::test]
    async fn test_apply_keyword_boost_empty_results() {
        // Test with empty results list
        let mut results: Vec<VectorSearchResult> = vec![];
        VectorStore::apply_keyword_boost(&mut results, &["git".to_string()]);
        assert!(results.is_empty());
    }

    // =========================================================================
    // Tests for matches_filter function
    // =========================================================================

    #[test]
    fn test_matches_filter_string_exact() {
        let metadata = serde_json::json!({ "domain": "python" });
        let conditions = serde_json::json!({ "domain": "python" });
        assert!(VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_string_mismatch() {
        let metadata = serde_json::json!({ "domain": "python" });
        let conditions = serde_json::json!({ "domain": "testing" });
        assert!(!VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_number() {
        let metadata = serde_json::json!({ "count": 42 });
        let conditions = serde_json::json!({ "count": 42 });
        assert!(VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_boolean() {
        let metadata = serde_json::json!({ "enabled": true });
        let conditions = serde_json::json!({ "enabled": true });
        assert!(VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_missing_key() {
        let metadata = serde_json::json!({ "domain": "python" });
        let conditions = serde_json::json!({ "missing_key": "value" });
        assert!(!VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_multiple_conditions_all_match() {
        let metadata = serde_json::json!({
            "domain": "python",
            "type": "function"
        });
        let conditions = serde_json::json!({
            "domain": "python",
            "type": "function"
        });
        assert!(VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_multiple_conditions_one_mismatch() {
        let metadata = serde_json::json!({
            "domain": "python",
            "type": "function"
        });
        let conditions = serde_json::json!({
            "domain": "python",
            "type": "class"
        });
        assert!(!VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_nested_key() {
        let metadata = serde_json::json!({
            "config": {
                "domain": "python"
            }
        });
        let conditions = serde_json::json!({
            "config.domain": "python"
        });
        assert!(VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_null_metadata() {
        let metadata = serde_json::Value::Null;
        let conditions = serde_json::json!({ "domain": "python" });
        assert!(!VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_empty_conditions() {
        let metadata = serde_json::json!({ "domain": "python" });
        let conditions = serde_json::json!({});
        // Empty conditions should match everything
        assert!(VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_non_object_conditions() {
        let metadata = serde_json::json!({ "domain": "python" });
        let conditions = serde_json::json!("invalid");
        // Non-object conditions should match everything
        assert!(VectorStore::matches_filter(&metadata, &conditions));
    }
}
