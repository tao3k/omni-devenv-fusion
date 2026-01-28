//! Hybrid search combining vector similarity and keyword (BM25) search.
//!
//! Uses Reciprocal Rank Fusion (RRF) with Weighted RRF for result fusion.

use std::sync::Arc;

use crate::keyword::{
    HybridSearchResult, KEYWORD_WEIGHT, KeywordIndex, RRF_K, SEMANTIC_WEIGHT, apply_weighted_rrf,
};

impl crate::VectorStore {
    /// Hybrid search combining vector similarity and keyword (BM25) search.
    ///
    /// This method performs true dual-engine search:
    /// - **LanceDB**: Semantic/dense retrieval using vector embeddings
    /// - **Tantivy**: Keyword/sparse retrieval using BM25 scoring
    ///
    /// Results are fused using **Weighted Reciprocal Rank Fusion (RRF)** with k=10.
    /// Field boosting is applied for exact token/phrase matches in tool names.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `query` - Query text for keyword search
    /// * `query_vector` - Query vector for semantic search
    /// * `limit` - Maximum number of results
    ///
    /// # Returns
    ///
    /// Vector of hybrid search results sorted by RRF score
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist,
    /// or [`VectorStoreError::KeywordIndexNotEnabled`] if keyword index is not available.
    pub async fn hybrid_search(
        &self,
        table_name: &str,
        query: &str,
        query_vector: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<HybridSearchResult>, crate::VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Err(crate::VectorStoreError::TableNotFound(
                table_name.to_string(),
            ));
        }

        // Get keyword index or return error
        let keyword_index = self.keyword_index.as_ref().ok_or_else(|| {
            crate::VectorStoreError::General(
                "Keyword index not enabled. Use VectorStore::new_with_keyword_index()".to_string(),
            )
        })?;

        // Execute vector search in background
        let vector_future = self.search(table_name, query_vector.clone(), limit * 2);

        // Execute keyword search in blocking task (Tantivy is CPU-bound)
        // For code snippets, keyword search may fail with parse errors
        // In that case, we gracefully fall back to vector-only search
        let kw_query = query.to_string();
        let kw_index = keyword_index.clone();
        let kw_future = tokio::task::spawn_blocking(move || kw_index.search(&kw_query, limit * 2));

        // Await vector search first
        let vector_results = vector_future.await?;

        // Await keyword search and handle parse errors gracefully
        let kw_results: Vec<crate::ToolSearchResult> = match kw_future.await.map_err(|e| {
            crate::VectorStoreError::General(format!("Keyword search task failed: {}", e))
        })? {
            Ok(results) => results,
            Err(e) => {
                // Keyword search failed (e.g., code snippet with syntax characters)
                // Fall back to vector-only search
                log::debug!("Keyword search failed, falling back to vector-only: {}", e);
                Vec::new()
            }
        };

        // Convert vector results to (name, score) format
        let vector_scores: Vec<(String, f32)> = vector_results
            .iter()
            .map(|r| (r.id.clone(), 1.0 - r.distance as f32)) // Convert distance to similarity
            .collect();

        // Apply Weighted RRF with Field Boosting (SOTA algorithm)
        // k=10 for high precision, keyword_weight=1.5 for code/tools
        let fused_results = apply_weighted_rrf(
            vector_scores,
            kw_results,
            RRF_K,
            SEMANTIC_WEIGHT,
            KEYWORD_WEIGHT,
            query,
        );

        // Truncate to limit
        Ok(fused_results.into_iter().take(limit).collect())
    }

    /// Enable keyword index for an existing VectorStore.
    ///
    /// This allows hybrid search to be used on stores created without keyword index.
    pub fn enable_keyword_index(&mut self) -> Result<(), crate::VectorStoreError> {
        if self.keyword_index.is_some() {
            return Ok(()); // Already enabled
        }

        if self.base_path.as_os_str() == ":memory:" {
            return Err(crate::VectorStoreError::General(
                "Cannot enable keyword index in memory mode".to_string(),
            ));
        }

        self.keyword_index = Some(Arc::new(KeywordIndex::new(
            &self.base_path.join("keyword_index"),
        )?));
        Ok(())
    }

    /// Index a document in the keyword index.
    ///
    /// This must be called after adding documents if keyword index is enabled.
    pub fn index_keyword(
        &self,
        name: &str,
        description: &str,
        category: &str,
        keywords: &[String],
    ) -> Result<(), crate::VectorStoreError> {
        if let Some(index) = &self.keyword_index {
            index.upsert_document(name, description, category, keywords)?;
        }
        Ok(())
    }

    /// Bulk index documents in the keyword index.
    ///
    /// More efficient than individual index_keyword calls.
    pub fn bulk_index_keywords<I>(&self, docs: I) -> Result<(), crate::VectorStoreError>
    where
        I: IntoIterator<Item = (String, String, String, Vec<String>)>,
    {
        if let Some(index) = &self.keyword_index {
            index.bulk_upsert(docs)?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {

    #[tokio::test]
    async fn test_hybrid_search_requires_keyword_index() {
        let temp_dir = tempfile::TempDir::new().unwrap();
        let store = crate::VectorStore::new(temp_dir.path().to_str().unwrap(), None)
            .await
            .unwrap();

        // Add documents first so the table exists
        store
            .add_documents(
                "test",
                vec!["doc1".to_string()],
                vec![vec![0.1; 1024]],
                vec!["test content".to_string()],
                vec![r#"{"category": "test"}"#.to_string()],
            )
            .await
            .unwrap();

        // Attempt hybrid search without keyword index should fail
        let result = store
            .hybrid_search("test", "test query", vec![0.1; 1024], 10)
            .await;

        assert!(result.is_err());
        if let Err(e) = result {
            let err_msg = format!("{:?}", e);
            // Debug format includes error type, check for our message
            assert!(
                err_msg.contains("Keyword index not enabled") || err_msg.contains("keyword"),
                "Expected error about keyword index, got: {}",
                err_msg
            );
        }
    }

    #[tokio::test]
    async fn test_hybrid_search_with_enabled_index() {
        let temp_dir = tempfile::TempDir::new().unwrap();
        let store = crate::VectorStore::new_with_keyword_index(
            temp_dir.path().to_str().unwrap(),
            None,
            true,
        )
        .await
        .unwrap();

        // Add some test documents (use 1024 dimension to match DEFAULT_DIMENSION)
        store
            .add_documents(
                "test",
                vec!["git_commit".to_string(), "git_status".to_string()],
                vec![vec![0.1; 1024], vec![0.2; 1024]],
                vec![
                    "Commit changes to repository".to_string(),
                    "Show working tree status".to_string(),
                ],
                vec![
                    r#"{"category": "git", "keywords": ["commit", "save"]}"#.to_string(),
                    r#"{"category": "git", "keywords": ["status", "dirty"]}"#.to_string(),
                ],
            )
            .await
            .unwrap();

        // Index keywords
        let docs: Vec<(String, String, String, Vec<String>)> = vec![
            (
                "git_commit".to_string(),
                "Commit changes to repository".to_string(),
                "git".to_string(),
                vec!["commit".to_string(), "save".to_string()],
            ),
            (
                "git_status".to_string(),
                "Show working tree status".to_string(),
                "git".to_string(),
                vec!["status".to_string(), "dirty".to_string()],
            ),
        ];
        store.bulk_index_keywords(docs).unwrap();

        // Perform hybrid search (use 1024 dimension to match DEFAULT_DIMENSION)
        let results = store
            .hybrid_search("test", "commit", vec![0.1; 1024], 10)
            .await
            .unwrap();

        assert!(!results.is_empty());
        // git_commit should rank higher for "commit" query
        assert_eq!(results[0].tool_name, "git_commit");
    }

    #[tokio::test]
    async fn test_enable_keyword_index_on_existing_store() {
        let temp_dir = tempfile::TempDir::new().unwrap();
        let mut store = crate::VectorStore::new(temp_dir.path().to_str().unwrap(), None)
            .await
            .unwrap();

        // Enable keyword index
        store.enable_keyword_index().unwrap();

        assert!(store.keyword_index.is_some());

        // Add document to keyword index
        store
            .index_keyword(
                "test_tool",
                "A test tool",
                "test",
                &vec!["test".to_string(), "example".to_string()],
            )
            .unwrap();

        // Search should work
        let results = store
            .keyword_index
            .as_ref()
            .unwrap()
            .search("test", 10)
            .unwrap();
        assert!(!results.is_empty());
        assert_eq!(results[0].tool_name, "test_tool");
    }

    #[tokio::test]
    async fn test_hybrid_search_fallback_on_keyword_error() {
        let temp_dir = tempfile::TempDir::new().unwrap();
        let store = crate::VectorStore::new_with_keyword_index(
            temp_dir.path().to_str().unwrap(),
            None,
            true,
        )
        .await
        .unwrap();

        // Add document
        store
            .add_documents(
                "test",
                vec!["git_commit".to_string()],
                vec![vec![0.1; 1024]],
                vec!["Commit changes".to_string()],
                vec![r#"{"category": "git"}"#.to_string()],
            )
            .await
            .unwrap();

        // Index keywords
        store
            .bulk_index_keywords(vec![(
                "git_commit".to_string(),
                "Commit changes".to_string(),
                "git".to_string(),
                vec!["commit".to_string()],
            )])
            .unwrap();

        // Search with code snippet (should fallback to vector-only gracefully)
        let results = store
            .hybrid_search("test", "pub async fn add_documents", vec![0.1; 1024], 5)
            .await
            .unwrap();

        // Should still return results from vector search
        assert!(!results.is_empty());
    }
}
