//! Search operations for the vector store.
//!
//! Provides nearest neighbor search using LanceDB 1.0's scanner API.
//! Supports both pure vector search and hybrid search with keyword boosting.

use futures::TryStreamExt;
use lance::dataset::Dataset;
use lance::deps::arrow_array::{Array, Float32Array, StringArray};

use omni_types::VectorSearchResult;

use crate::{CONTENT_COLUMN, ID_COLUMN, METADATA_COLUMN, VECTOR_COLUMN, VectorStoreError};

/// Weight for keyword match score in hybrid search
const KEYWORD_WEIGHT: f64 = 0.3;
/// Boost per keyword match
const KEYWORD_BOOST: f64 = 0.1;
/// Multiplier for fetch count to account for filtering loss
const FETCH_MULTIPLIER: usize = 2;

impl crate::VectorStore {
    /// Search for similar documents.
    ///
    /// Performs nearest neighbor search using `LanceDB` 1.0's scanner API.
    /// Supports flat search (brute force) for small datasets and ANN search
    /// when an index is created.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `query` - Query vector
    /// * `limit` - Maximum number of results
    /// * `where_filter` - Optional metadata filter (e.g., `{"domain": "python"}`)
    ///
    /// # Returns
    ///
    /// Vector of search results sorted by similarity (distance)
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
    pub async fn search(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        self.search_with_keywords(table_name, query, Vec::new(), limit, None)
            .await
    }

    /// Search with metadata filtering.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `query` - Query vector
    /// * `limit` - Maximum number of results
    /// * `where_filter` - Optional metadata filter as JSON string (e.g., `{"domain": "python"}`)
    ///
    /// # Returns
    ///
    /// Vector of search results filtered by metadata
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
    pub async fn search_filtered(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
        where_filter: Option<String>,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        self.search_with_keywords(table_name, query, Vec::new(), limit, where_filter)
            .await
    }

    /// Hybrid search with keyword boosting.
    ///
    /// Combines vector similarity with keyword matching for better relevance.
    /// Formula: `Score = Vector_Score * 0.7 + Keyword_Match * 0.3`
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `query` - Query vector
    /// * `keywords` - Keywords to boost (matched against metadata.keywords)
    /// * `limit` - Maximum number of results
    /// * `where_filter` - Optional metadata filter as JSON string
    ///
    /// # Returns
    ///
    /// Vector of search results sorted by hybrid score
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
    pub async fn search_hybrid(
        &self,
        table_name: &str,
        query: Vec<f32>,
        keywords: Vec<String>,
        limit: usize,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        self.search_with_keywords(table_name, query, keywords, limit, None)
            .await
    }

    /// Internal search implementation with optional keyword boosting and metadata filtering.
    async fn search_with_keywords(
        &self,
        table_name: &str,
        query: Vec<f32>,
        keywords: Vec<String>,
        limit: usize,
        where_filter: Option<String>,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        // Open dataset
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Build query vector array
        let query_arr = Float32Array::from(query);

        // Create scanner and execute nearest neighbor search
        let mut scanner = dataset.scan();
        let fetch_count = limit.saturating_mul(FETCH_MULTIPLIER).max(limit + 10);
        scanner
            .nearest(VECTOR_COLUMN, &query_arr, fetch_count)
            .map_err(VectorStoreError::LanceDB)?;

        // Get results as stream
        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Parse where_filter if provided
        let filter_conditions = where_filter
            .as_ref()
            .map(|f| serde_json::from_str::<serde_json::Value>(f).ok())
            .flatten();

        let mut results = Vec::new();

        // Process record batches
        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            // Extract columns
            let id_col = batch.column_by_name(ID_COLUMN).ok_or_else(|| {
                VectorStoreError::TableNotFound("id column not found".to_string())
            })?;
            let content_col = batch.column_by_name(CONTENT_COLUMN).ok_or_else(|| {
                VectorStoreError::TableNotFound("content column not found".to_string())
            })?;
            let distance_col = batch.column_by_name("_distance").ok_or_else(|| {
                VectorStoreError::TableNotFound("_distance column not found".to_string())
            })?;
            let metadata_col = batch.column_by_name(METADATA_COLUMN);

            let ids = id_col
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| {
                    VectorStoreError::TableNotFound("id column is not StringArray".to_string())
                })?;
            let contents = content_col
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| {
                    VectorStoreError::TableNotFound("content column is not StringArray".to_string())
                })?;
            let distances = distance_col
                .as_any()
                .downcast_ref::<Float32Array>()
                .ok_or_else(|| {
                    VectorStoreError::TableNotFound(
                        "distance column is not Float32Array".to_string(),
                    )
                })?;

            for i in 0..batch.num_rows() {
                // Extract metadata if present
                let metadata = if let Some(meta_col) = metadata_col {
                    if let Some(meta_arr) = meta_col.as_any().downcast_ref::<StringArray>() {
                        if meta_arr.is_null(i) {
                            serde_json::Value::Null
                        } else {
                            let meta_str = meta_arr.value(i);
                            serde_json::from_str(meta_str).unwrap_or_default()
                        }
                    } else {
                        serde_json::Value::Null
                    }
                } else {
                    serde_json::Value::Null
                };

                // Apply where_filter if specified
                if let Some(ref conditions) = filter_conditions {
                    if !Self::matches_filter(&metadata, conditions) {
                        continue; // Skip this result
                    }
                }

                results.push(VectorSearchResult {
                    id: ids.value(i).to_string(),
                    content: contents.value(i).to_string(),
                    metadata,
                    distance: f64::from(distances.value(i)),
                });
            }
        }

        // Apply keyword boosting if keywords provided
        if !keywords.is_empty() {
            Self::apply_keyword_boost(&mut results, &keywords);
        }

        // Sort by hybrid score (distance - smaller is better for cosine)
        results.sort_by(|a, b| {
            a.distance
                .partial_cmp(&b.distance)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        // Limit results after sorting
        results.truncate(limit);

        Ok(results)
    }

    /// Check if a metadata value matches the filter conditions.
    fn matches_filter(metadata: &serde_json::Value, conditions: &serde_json::Value) -> bool {
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
    fn apply_keyword_boost(results: &mut Vec<VectorSearchResult>, keywords: &[String]) {
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
            let keyword_bonus = keyword_score * KEYWORD_WEIGHT;
            let hybrid_distance = result.distance - keyword_bonus;

            // Clamp to valid range (don't go negative)
            result.distance = hybrid_distance.max(0.0);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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

        crate::VectorStore::apply_keyword_boost(&mut results, &["git".to_string()]);

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
            metadata: serde_json::json!({"keywords": ["git"]}),
            distance: 0.5,
        }];

        crate::VectorStore::apply_keyword_boost(&mut results, &[]);

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
        crate::VectorStore::apply_keyword_boost(
            &mut results,
            &["git".to_string(), "commit".to_string()],
        );

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
        crate::VectorStore::apply_keyword_boost(&mut results, &["git".to_string()]);
        assert!(results.is_empty());
    }

    // =========================================================================
    // Tests for matches_filter function
    // =========================================================================

    #[test]
    fn test_matches_filter_string_exact() {
        let metadata = serde_json::json!({"domain": "python"});
        let conditions = serde_json::json!({"domain": "python"});
        assert!(crate::VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_string_mismatch() {
        let metadata = serde_json::json!({"domain": "python"});
        let conditions = serde_json::json!({"domain": "testing"});
        assert!(!crate::VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_number() {
        let metadata = serde_json::json!({"count": 42});
        let conditions = serde_json::json!({"count": 42});
        assert!(crate::VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_boolean() {
        let metadata = serde_json::json!({"enabled": true});
        let conditions = serde_json::json!({"enabled": true});
        assert!(crate::VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_missing_key() {
        let metadata = serde_json::json!({"domain": "python"});
        let conditions = serde_json::json!({"missing_key": "value"});
        assert!(!crate::VectorStore::matches_filter(&metadata, &conditions));
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
        assert!(crate::VectorStore::matches_filter(&metadata, &conditions));
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
        assert!(!crate::VectorStore::matches_filter(&metadata, &conditions));
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
        assert!(crate::VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_null_metadata() {
        let metadata = serde_json::Value::Null;
        let conditions = serde_json::json!({"domain": "python"});
        assert!(!crate::VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_empty_conditions() {
        let metadata = serde_json::json!({"domain": "python"});
        let conditions = serde_json::json!({});
        // Empty conditions should match everything
        assert!(crate::VectorStore::matches_filter(&metadata, &conditions));
    }

    #[test]
    fn test_matches_filter_non_object_conditions() {
        let metadata = serde_json::json!({"domain": "python"});
        let conditions = serde_json::json!("invalid");
        // Non-object conditions should match everything
        assert!(crate::VectorStore::matches_filter(&metadata, &conditions));
    }
}
