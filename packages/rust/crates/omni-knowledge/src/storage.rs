//! LanceDB-backed storage operations for knowledge entries.

use crate::types::{KnowledgeCategory, KnowledgeEntry, KnowledgeStats};
use chrono::{DateTime, Utc};
use omni_vector::{SearchOptions, VectorStore};
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

/// Knowledge storage using LanceDB.
#[derive(Debug)]
pub struct KnowledgeStorage {
    /// Base storage path.
    path: PathBuf,
    /// Lance table name.
    table_name: String,
    /// Storage vector dimension.
    dimension: usize,
}

impl KnowledgeStorage {
    /// Create a new KnowledgeStorage instance.
    pub fn new(path: &str, table_name: &str) -> Self {
        Self {
            path: PathBuf::from(path),
            table_name: table_name.to_string(),
            dimension: 128,
        }
    }

    /// Get the dataset path.
    pub fn path(&self) -> &PathBuf {
        &self.path
    }

    /// Get the table name.
    pub fn table_name(&self) -> &str {
        &self.table_name
    }

    fn category_to_str(category: &KnowledgeCategory) -> &'static str {
        match category {
            KnowledgeCategory::Pattern => "patterns",
            KnowledgeCategory::Solution => "solutions",
            KnowledgeCategory::Error => "errors",
            KnowledgeCategory::Technique => "techniques",
            KnowledgeCategory::Note => "notes",
            KnowledgeCategory::Reference => "references",
            KnowledgeCategory::Architecture => "architecture",
            KnowledgeCategory::Workflow => "workflows",
        }
    }

    fn category_from_str(s: &str) -> KnowledgeCategory {
        match s {
            "patterns" | "pattern" => KnowledgeCategory::Pattern,
            "solutions" | "solution" => KnowledgeCategory::Solution,
            "errors" | "error" => KnowledgeCategory::Error,
            "techniques" | "technique" => KnowledgeCategory::Technique,
            "references" | "reference" => KnowledgeCategory::Reference,
            "architecture" => KnowledgeCategory::Architecture,
            "workflows" | "workflow" => KnowledgeCategory::Workflow,
            _ => KnowledgeCategory::Note,
        }
    }

    fn normalize_vector(&self, input: &[f32]) -> Vec<f32> {
        if input.len() == self.dimension {
            return input.to_vec();
        }
        let mut out = vec![0.0_f32; self.dimension];
        let copy_len = input.len().min(self.dimension);
        out[..copy_len].copy_from_slice(&input[..copy_len]);
        out
    }

    fn text_to_vector(&self, text: &str) -> Vec<f32> {
        let mut vec = vec![0.0_f32; self.dimension];
        for (idx, byte) in text.as_bytes().iter().enumerate() {
            let bucket = idx % self.dimension;
            vec[bucket] += (*byte as f32) / 255.0;
        }

        let norm = vec.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 0.0 {
            for v in &mut vec {
                *v /= norm;
            }
        }
        vec
    }

    fn tokenize(text: &str) -> Vec<String> {
        text.to_lowercase()
            .split(|c: char| !c.is_alphanumeric())
            .filter(|token| !token.is_empty())
            .map(ToString::to_string)
            .collect()
    }

    fn text_score(query: &str, entry: &KnowledgeEntry) -> f32 {
        let query_tokens = Self::tokenize(query);
        if query_tokens.is_empty() {
            return 0.0;
        }

        let mut doc_tokens = Self::tokenize(&entry.title);
        doc_tokens.extend(Self::tokenize(&entry.content));
        for tag in &entry.tags {
            doc_tokens.extend(Self::tokenize(tag));
        }

        if doc_tokens.is_empty() {
            return 0.0;
        }

        let doc_set: HashSet<String> = doc_tokens.iter().cloned().collect();
        let overlap = query_tokens.iter().filter(|t| doc_set.contains(*t)).count() as f32;
        overlap / query_tokens.len() as f32
    }

    fn parse_datetime(metadata: &serde_json::Value, key: &str) -> DateTime<Utc> {
        metadata
            .get(key)
            .and_then(|v| v.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| dt.with_timezone(&Utc))
            .unwrap_or_else(Utc::now)
    }

    fn metadata_to_entry(
        &self,
        id: String,
        content: String,
        metadata: serde_json::Value,
    ) -> KnowledgeEntry {
        let category = metadata
            .get("category")
            .and_then(|v| v.as_str())
            .map(Self::category_from_str)
            .unwrap_or(KnowledgeCategory::Note);

        let tags = metadata
            .get("tags")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(ToString::to_string))
                    .collect::<Vec<_>>()
            })
            .unwrap_or_default();

        let source = metadata
            .get("source")
            .and_then(|v| v.as_str())
            .map(ToString::to_string);

        let version = metadata
            .get("version")
            .and_then(|v| v.as_i64())
            .map(|v| v as i32)
            .unwrap_or(1);

        let extra = metadata
            .get("metadata")
            .and_then(|v| v.as_object())
            .map(|obj| {
                obj.iter()
                    .map(|(k, v)| (k.clone(), v.clone()))
                    .collect::<HashMap<String, serde_json::Value>>()
            })
            .unwrap_or_default();

        KnowledgeEntry {
            id: id.clone(),
            title: metadata
                .get("title")
                .and_then(|v| v.as_str())
                .unwrap_or(&id)
                .to_string(),
            content,
            category,
            tags,
            source,
            created_at: Self::parse_datetime(&metadata, "created_at"),
            updated_at: Self::parse_datetime(&metadata, "updated_at"),
            version,
            metadata: extra,
        }
    }

    async fn vector_store(&self) -> Result<VectorStore, Box<dyn std::error::Error>> {
        Ok(VectorStore::new(self.path.to_string_lossy().as_ref(), Some(self.dimension)).await?)
    }

    async fn all_entries(&self) -> Result<Vec<KnowledgeEntry>, Box<dyn std::error::Error>> {
        let store = self.vector_store().await?;
        let total = store.count(&self.table_name).await? as usize;
        if total == 0 {
            return Ok(Vec::new());
        }

        let results = store
            .search_optimized(
                &self.table_name,
                vec![0.0; self.dimension],
                total,
                SearchOptions::default(),
            )
            .await?;

        Ok(results
            .into_iter()
            .map(|r| self.metadata_to_entry(r.id, r.content, r.metadata))
            .collect())
    }

    /// Initialize the storage (create table if not exists).
    pub async fn init(&self) -> Result<(), Box<dyn std::error::Error>> {
        tokio::fs::create_dir_all(&self.path).await?;
        // Instantiate the store to validate base path and runtime dependencies.
        let _store = self.vector_store().await?;
        Ok(())
    }

    /// Upsert a knowledge entry.
    pub async fn upsert(&self, entry: &KnowledgeEntry) -> Result<(), Box<dyn std::error::Error>> {
        self.init().await?;
        let store = self.vector_store().await?;

        let mut existing = self
            .all_entries()
            .await?
            .into_iter()
            .filter(|e| e.id == entry.id)
            .collect::<Vec<_>>();
        let now = Utc::now();
        let (created_at, version) = if let Some(found) = existing.pop() {
            (found.created_at, found.version + 1)
        } else {
            (now, entry.version.max(1))
        };

        store
            .delete(&self.table_name, vec![entry.id.clone()])
            .await?;

        let metadata = serde_json::json!({
            "title": entry.title,
            "category": Self::category_to_str(&entry.category),
            "tags": entry.tags,
            "source": entry.source,
            "created_at": created_at.to_rfc3339(),
            "updated_at": now.to_rfc3339(),
            "version": version,
            "metadata": entry.metadata,
        });

        store
            .add_documents(
                &self.table_name,
                vec![entry.id.clone()],
                vec![self.text_to_vector(&entry.content)],
                vec![entry.content.clone()],
                vec![metadata.to_string()],
            )
            .await?;
        Ok(())
    }

    /// Search knowledge entries by vector similarity.
    pub async fn search(
        &self,
        query: &[f32],
        limit: i32,
    ) -> Result<Vec<KnowledgeEntry>, Box<dyn std::error::Error>> {
        let take_n = limit.max(0) as usize;
        if take_n == 0 {
            return Ok(Vec::new());
        }

        let store = self.vector_store().await?;
        let results = store
            .search(&self.table_name, self.normalize_vector(query), take_n)
            .await?;

        Ok(results
            .into_iter()
            .map(|r| self.metadata_to_entry(r.id, r.content, r.metadata))
            .collect())
    }

    /// Search knowledge entries by text (BM25).
    pub async fn search_text(
        &self,
        query: &str,
        limit: i32,
    ) -> Result<Vec<KnowledgeEntry>, Box<dyn std::error::Error>> {
        let take_n = limit.max(0) as usize;
        if take_n == 0 {
            return Ok(Vec::new());
        }

        let store = self.vector_store().await?;
        let all_entries = self.all_entries().await?;
        let mut by_id: HashMap<String, KnowledgeEntry> = all_entries
            .iter()
            .cloned()
            .map(|e| (e.id.clone(), e))
            .collect();

        if let Ok(fts_hits) = store
            .search_fts(&self.table_name, query, take_n.saturating_mul(3), None)
            .await
        {
            let mut ranked = Vec::new();
            for hit in fts_hits {
                if let Some(entry) = by_id.remove(&hit.name) {
                    ranked.push(entry);
                    if ranked.len() >= take_n {
                        break;
                    }
                }
            }
            if !ranked.is_empty() {
                return Ok(ranked);
            }
        }

        let mut scored: Vec<(f32, KnowledgeEntry)> = all_entries
            .into_iter()
            .map(|entry| {
                let mut score = Self::text_score(query, &entry);
                if entry.id == query {
                    score += 1.0;
                }
                (score, entry)
            })
            .filter(|(score, _)| *score > 0.0)
            .collect();
        scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(Ordering::Equal));
        Ok(scored.into_iter().take(take_n).map(|(_, e)| e).collect())
    }

    /// Get statistics about the knowledge base.
    pub async fn stats(&self) -> Result<KnowledgeStats, Box<dyn std::error::Error>> {
        let entries = self.all_entries().await?;
        if entries.is_empty() {
            return Ok(KnowledgeStats::default());
        }

        let mut by_category: HashMap<String, i64> = HashMap::new();
        let mut unique_tags: HashSet<String> = HashSet::new();
        let mut last_updated = entries[0].updated_at;

        for entry in &entries {
            let key = serde_json::to_string(&entry.category)
                .unwrap_or_else(|_| "\"notes\"".to_string())
                .trim_matches('"')
                .to_string();
            *by_category.entry(key).or_insert(0) += 1;

            for tag in &entry.tags {
                unique_tags.insert(tag.to_lowercase());
            }
            if entry.updated_at > last_updated {
                last_updated = entry.updated_at;
            }
        }

        Ok(KnowledgeStats {
            total_entries: entries.len() as i64,
            entries_by_category: by_category,
            total_tags: unique_tags.len() as i64,
            last_updated: Some(last_updated),
        })
    }

    /// Count total entries.
    pub async fn count(&self) -> Result<i64, Box<dyn std::error::Error>> {
        let store = self.vector_store().await?;
        Ok(i64::from(store.count(&self.table_name).await?))
    }

    /// Delete an entry by ID.
    pub async fn delete(&self, id: &str) -> Result<(), Box<dyn std::error::Error>> {
        let store = self.vector_store().await?;
        store.delete(&self.table_name, vec![id.to_string()]).await?;
        Ok(())
    }

    /// Clear all entries.
    pub async fn clear(&self) -> Result<(), Box<dyn std::error::Error>> {
        let mut store = self.vector_store().await?;
        store.drop_table(&self.table_name).await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::KnowledgeCategory;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_storage_creation() {
        let temp_dir = TempDir::new().unwrap();
        let storage = KnowledgeStorage::new(temp_dir.path().to_str().unwrap(), "knowledge");

        assert_eq!(storage.table_name(), "knowledge");
    }

    #[tokio::test]
    async fn test_upsert_count_delete_clear_roundtrip() {
        let temp_dir = TempDir::new().unwrap();
        let storage = KnowledgeStorage::new(temp_dir.path().to_str().unwrap(), "knowledge");

        storage.init().await.unwrap();

        let entry = KnowledgeEntry::new(
            "id-1".to_string(),
            "Rust Pattern".to_string(),
            "Use Result for error handling".to_string(),
            KnowledgeCategory::Pattern,
        )
        .with_tags(vec!["rust".to_string(), "error".to_string()]);
        storage.upsert(&entry).await.unwrap();
        assert_eq!(storage.count().await.unwrap(), 1);

        let updated = KnowledgeEntry::new(
            "id-1".to_string(),
            "Rust Pattern Updated".to_string(),
            "Use anyhow for context-rich errors".to_string(),
            KnowledgeCategory::Pattern,
        )
        .with_tags(vec!["rust".to_string(), "anyhow".to_string()]);
        storage.upsert(&updated).await.unwrap();
        assert_eq!(storage.count().await.unwrap(), 1);

        storage.delete("id-1").await.unwrap();
        assert_eq!(storage.count().await.unwrap(), 0);

        storage.upsert(&entry).await.unwrap();
        storage.clear().await.unwrap();
        assert_eq!(storage.count().await.unwrap(), 0);
    }

    #[tokio::test]
    async fn test_text_search_and_stats() {
        let temp_dir = TempDir::new().unwrap();
        let storage = KnowledgeStorage::new(temp_dir.path().to_str().unwrap(), "knowledge");
        storage.init().await.unwrap();

        let e1 = KnowledgeEntry::new(
            "id-a".to_string(),
            "TypeScript Error Handling".to_string(),
            "Typed errors improve maintainability".to_string(),
            KnowledgeCategory::Pattern,
        )
        .with_tags(vec!["typescript".to_string(), "error".to_string()]);
        let e2 = KnowledgeEntry::new(
            "id-b".to_string(),
            "Workflow notes".to_string(),
            "This note describes deployment workflow".to_string(),
            KnowledgeCategory::Workflow,
        )
        .with_tags(vec!["deploy".to_string()]);

        storage.upsert(&e1).await.unwrap();
        storage.upsert(&e2).await.unwrap();

        let text_results = storage.search_text("typed error", 10).await.unwrap();
        assert_eq!(text_results.len(), 1);
        assert_eq!(text_results[0].id, "id-a");

        let vector_results = storage.search(&[0.1, 0.3, 0.2, 0.4], 2).await.unwrap();
        assert_eq!(vector_results.len(), 2);

        let stats = storage.stats().await.unwrap();
        assert_eq!(stats.total_entries, 2);
        assert_eq!(stats.total_tags, 3);
        assert_eq!(stats.entries_by_category.get("patterns"), Some(&1));
        assert_eq!(stats.entries_by_category.get("workflows"), Some(&1));
        assert!(stats.last_updated.is_some());
    }

    #[tokio::test]
    async fn test_vector_search_prefers_semantically_closer_entry() {
        let temp_dir = TempDir::new().unwrap();
        let storage = KnowledgeStorage::new(temp_dir.path().to_str().unwrap(), "knowledge");
        storage.init().await.unwrap();

        let e1 = KnowledgeEntry::new(
            "vec-1".to_string(),
            "Typed language benefits".to_string(),
            "Type systems catch compile-time errors and improve refactoring safety.".to_string(),
            KnowledgeCategory::Pattern,
        );
        let e2 = KnowledgeEntry::new(
            "vec-2".to_string(),
            "Deployment workflow".to_string(),
            "Release flow focuses on canary rollout and rollback strategy.".to_string(),
            KnowledgeCategory::Workflow,
        );

        storage.upsert(&e1).await.unwrap();
        storage.upsert(&e2).await.unwrap();

        let query = storage.text_to_vector(
            "Type systems catch compile-time errors and improve refactoring safety.",
        );
        let hits = storage.search(&query, 1).await.unwrap();
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].id, "vec-1".to_string());
    }
}
