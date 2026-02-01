//! KeywordIndex - Tantivy wrapper for keyword search with BM25

use std::path::Path;

use tantivy::collector::TopDocs;
use tantivy::query::QueryParser;
use tantivy::schema::*;
use tantivy::tokenizer::{
    AsciiFoldingFilter, LowerCaser, RemoveLongFilter, SimpleTokenizer, TextAnalyzer,
};
use tantivy::{Index, IndexReader, ReloadPolicy, TantivyDocument, TantivyError, Term, doc};

use crate::ToolSearchResult;
use crate::error::VectorStoreError;

/// KeywordIndex - Tantivy wrapper for keyword search with BM25
#[derive(Clone)]
pub struct KeywordIndex {
    /// Tantivy index for full-text search
    index: Index,
    /// Index reader for search operations
    reader: IndexReader,
    /// Field handle for tool name (used for exact matching and boosting)
    pub tool_name: Field,
    /// Field handle for tool description (used for relevance scoring)
    pub description: Field,
    /// Field handle for skill category (used for filtering)
    pub category: Field,
    /// Field handle for routing keywords (used for keyword matching)
    pub keywords: Field,
    /// Field handle for intents (used for semantic alignment)
    pub intents: Field,
}

impl KeywordIndex {
    /// Helper to create a fresh index with correct schema
    fn create_new_index(path: &Path) -> Result<Index, TantivyError> {
        use tantivy::schema::TextFieldIndexing;

        let mut schema_builder = Schema::builder();

        // Use code_tokenizer with FULL indexing (including positions for phrase queries)
        let text_options = TextOptions::default()
            .set_indexing_options(
                TextFieldIndexing::default()
                    .set_tokenizer("code_tokenizer")
                    .set_index_option(tantivy::schema::IndexRecordOption::WithFreqsAndPositions),
            )
            .set_stored();

        schema_builder.add_text_field("tool_name", text_options.clone());
        schema_builder.add_text_field("description", text_options.clone());
        schema_builder.add_text_field("category", text_options.clone());
        schema_builder.add_text_field("keywords", text_options.clone());
        schema_builder.add_text_field("intents", text_options);

        let schema = schema_builder.build();
        Index::create_in_dir(path, schema)
    }

    /// Create a new KeywordIndex with schema migration (deletes old index if needed)
    fn new_with_migration<P: AsRef<Path>>(path: P) -> Result<Self, VectorStoreError> {
        let base_path = path.as_ref();
        let index_path = base_path.join("keyword_index");

        // Remove old index directory if it exists
        if index_path.exists() {
            std::fs::remove_dir_all(&index_path).map_err(|e| {
                VectorStoreError::General(format!("Failed to remove old index: {}", e))
            })?;
        }

        // Create fresh index with correct schema
        let index = Self::create_new_index(&index_path).map_err(VectorStoreError::Tantivy)?;

        // 1. Register Tokenizer
        let code_tokenizer = TextAnalyzer::builder(SimpleTokenizer::default())
            .filter(RemoveLongFilter::limit(40))
            .filter(LowerCaser)
            .filter(AsciiFoldingFilter)
            .build();
        index
            .tokenizers()
            .register("code_tokenizer", code_tokenizer);

        // 2. Resolve Fields from the new Schema
        let schema = index.schema();

        let tool_name = schema
            .get_field("tool_name")
            .map_err(|_| VectorStoreError::General("Missing tool_name field".to_string()))?;
        let description = schema
            .get_field("description")
            .map_err(|_| VectorStoreError::General("Missing description field".to_string()))?;
        let category = schema
            .get_field("category")
            .map_err(|_| VectorStoreError::General("Missing category field".to_string()))?;
        let keywords = schema
            .get_field("keywords")
            .map_err(|_| VectorStoreError::General("Missing keywords field".to_string()))?;
        let intents = schema
            .get_field("intents")
            .map_err(|_| VectorStoreError::General("Missing intents field".to_string()))?;

        // 3. Create Reader
        let reader = index
            .reader_builder()
            .reload_policy(ReloadPolicy::Manual)
            .try_into()
            .map_err(VectorStoreError::Tantivy)?;

        Ok(Self {
            index,
            reader,
            tool_name,
            description,
            category,
            keywords,
            intents,
        })
    }

    /// Create a new KeywordIndex or open existing one
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self, VectorStoreError> {
        let base_path = path.as_ref();
        let index_path = base_path.join("keyword_index");
        std::fs::create_dir_all(&index_path)?;

        let meta_path = index_path.join("meta.json");

        let index = if meta_path.exists() {
            match Index::open_in_dir(&index_path) {
                Ok(idx) => idx,
                Err(_e) => {
                    // Fallback: If corrupted, wipe and recreate
                    Self::create_new_index(&index_path).map_err(VectorStoreError::Tantivy)?
                }
            }
        } else {
            Self::create_new_index(&index_path).map_err(VectorStoreError::Tantivy)?
        };

        // 1. Register Tokenizer (Must be done every time we open/create)
        let code_tokenizer = TextAnalyzer::builder(SimpleTokenizer::default())
            .filter(RemoveLongFilter::limit(40))
            .filter(LowerCaser)
            .filter(AsciiFoldingFilter)
            .build();
        index
            .tokenizers()
            .register("code_tokenizer", code_tokenizer);

        // 2. Resolve Fields from the Index's Schema (Critical for consistency)
        let schema = index.schema();

        let tool_name = schema
            .get_field("tool_name")
            .map_err(|_| VectorStoreError::General("Missing tool_name field".to_string()))?;
        let description = schema
            .get_field("description")
            .map_err(|_| VectorStoreError::General("Missing description field".to_string()))?;
        let category = schema
            .get_field("category")
            .map_err(|_| VectorStoreError::General("Missing category field".to_string()))?;
        let keywords = schema
            .get_field("keywords")
            .map_err(|_| VectorStoreError::General("Missing keywords field".to_string()))?;
        // Check for intents field - if missing, recreate the index (schema migration)
        let intents = match schema.get_field("intents") {
            Ok(field) => field,
            Err(_) => {
                // Schema is missing intents field - recreate the index
                return Self::new_with_migration(path);
            }
        };

        // 3. Create Reader with Manual Policy (We control reloads)
        let reader = index
            .reader_builder()
            .reload_policy(ReloadPolicy::Manual)
            .try_into()
            .map_err(VectorStoreError::Tantivy)?;

        Ok(Self {
            index,
            reader,
            tool_name,
            description,
            category,
            keywords,
            intents,
        })
    }

    /// Add or update a document in the index
    pub fn upsert_document(
        &self,
        name: &str,
        description: &str,
        category: &str,
        keywords: &[String],
        intents: &[String],
    ) -> Result<(), VectorStoreError> {
        let mut index_writer = self
            .index
            .writer(50_000_000)
            .map_err(VectorStoreError::Tantivy)?;

        let term = Term::from_field_text(self.tool_name, name);
        index_writer.delete_term(term);

        index_writer
            .add_document(doc!(
                self.tool_name => name,
                self.description => description,
                self.category => category,
                self.keywords => keywords.join(" "),
                self.intents => intents.join(" | ")
            ))
            .map_err(VectorStoreError::Tantivy)?;

        index_writer.commit().map_err(VectorStoreError::Tantivy)?;
        self.reader.reload().map_err(VectorStoreError::Tantivy)?;
        Ok(())
    }

    /// Bulk upsert documents
    pub fn bulk_upsert<I>(&self, docs: I) -> Result<(), VectorStoreError>
    where
        I: IntoIterator<Item = (String, String, String, Vec<String>, Vec<String>)>,
    {
        let mut index_writer = self
            .index
            .writer(100_000_000)
            .map_err(VectorStoreError::Tantivy)?;

        for (name, description, category, kw_list, intent_list) in docs {
            let term = Term::from_field_text(self.tool_name, &name);
            index_writer.delete_term(term);

            index_writer
                .add_document(doc!(
                    self.tool_name => name,
                    self.description => description,
                    self.category => category,
                    self.keywords => kw_list.join(" "),
                    self.intents => intent_list.join(" | ")
                ))
                .map_err(VectorStoreError::Tantivy)?;
        }

        index_writer.commit().map_err(VectorStoreError::Tantivy)?;
        self.reader.reload().map_err(VectorStoreError::Tantivy)?;
        Ok(())
    }

    /// Batch index ToolRecords
    pub fn index_batch(&self, tools: &[ToolSearchResult]) -> Result<(), TantivyError> {
        let mut index_writer = self.index.writer(100_000_000)?;

        for tool in tools {
            let term = Term::from_field_text(self.tool_name, &tool.name);
            index_writer.delete_term(term);

            index_writer.add_document(doc!(
                self.tool_name => tool.name.as_str(),
                self.description => tool.description.as_str(),
                self.category => tool.skill_name.as_str(),
                self.keywords => tool.keywords.join(" "),
                self.intents => tool.intents.join(" | ")
            ))?;
        }

        index_writer.commit()?;
        self.reader.reload()?;
        Ok(())
    }

    /// Search the index with BM25 scoring
    pub fn search(
        &self,
        query_str: &str,
        limit: usize,
    ) -> Result<Vec<ToolSearchResult>, VectorStoreError> {
        let searcher = self.reader.searcher();

        if query_str.trim().is_empty() {
            return Ok(vec![]);
        }

        let mut query_parser = QueryParser::for_index(
            &self.index,
            vec![
                self.tool_name,
                self.keywords,
                self.intents,
                self.description,
            ],
        );

        query_parser.set_field_boost(self.tool_name, 5.0);
        query_parser.set_field_boost(self.intents, 4.0);
        query_parser.set_field_boost(self.keywords, 3.0);
        query_parser.set_field_boost(self.description, 1.0);

        let query = query_parser
            .parse_query(query_str)
            .map_err(|e| VectorStoreError::General(format!("Query parse error: {}", e)))?;

        let top_docs = searcher
            .search(&query, &TopDocs::with_limit(limit))
            .map_err(VectorStoreError::Tantivy)?;

        let mut results = Vec::new();
        for (score, doc_address) in top_docs {
            let doc: TantivyDocument = searcher
                .doc(doc_address)
                .map_err(VectorStoreError::Tantivy)?;

            let tool_name = doc
                .get_first(self.tool_name)
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let description = doc
                .get_first(self.description)
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let keywords_str = doc
                .get_first(self.keywords)
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let intents_str = doc
                .get_first(self.intents)
                .and_then(|v| v.as_str())
                .unwrap_or("");

            let keywords = keywords_str
                .split_whitespace()
                .map(|s| s.to_string())
                .collect();
            let intents = intents_str.split(" | ").map(|s| s.to_string()).collect();

            let skill_name = tool_name.split('.').next().unwrap_or("").to_string();

            results.push(ToolSearchResult {
                name: tool_name.clone(),
                description,
                input_schema: serde_json::json!({}),
                score,
                skill_name,
                tool_name,
                file_path: String::new(),
                keywords,
                intents,
            });
        }

        Ok(results)
    }

    /// Get the number of documents in the index
    pub fn count_documents(&self) -> Result<u64, VectorStoreError> {
        let searcher = self.reader.searcher();
        Ok(searcher.num_docs())
    }

    /// Check if index exists
    pub fn exists<P: AsRef<Path>>(path: P) -> bool {
        path.as_ref()
            .join("keyword_index")
            .join("meta.json")
            .exists()
    }

    /// Retrieve a full ToolSearchResult from the index by tool_name (Rescue Mode)
    pub fn get_tool(&self, name: &str) -> Result<Option<ToolSearchResult>, VectorStoreError> {
        let searcher = self.reader.searcher();
        let term = Term::from_field_text(self.tool_name, name);
        let term_query = tantivy::query::TermQuery::new(term, IndexRecordOption::Basic);

        let top_docs = searcher
            .search(&term_query, &TopDocs::with_limit(1))
            .map_err(VectorStoreError::Tantivy)?;

        if let Some((_score, doc_address)) = top_docs.first() {
            let doc: TantivyDocument = searcher
                .doc(*doc_address)
                .map_err(VectorStoreError::Tantivy)?;

            let tool_name = doc
                .get_first(self.tool_name)
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let description = doc
                .get_first(self.description)
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let keywords_str = doc
                .get_first(self.keywords)
                .and_then(|v| v.as_str())
                .unwrap_or("");
            let intents_str = doc
                .get_first(self.intents)
                .and_then(|v| v.as_str())
                .unwrap_or("");

            let keywords = keywords_str
                .split_whitespace()
                .map(|s| s.to_string())
                .collect();
            let intents = intents_str.split(" | ").map(|s| s.to_string()).collect();

            Ok(Some(ToolSearchResult {
                name: tool_name.clone(),
                description,
                input_schema: serde_json::json!({}),
                score: 1.0,
                skill_name: doc
                    .get_first(self.category)
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string(),
                tool_name,
                file_path: "".to_string(),
                keywords,
                intents,
            }))
        } else {
            Ok(None)
        }
    }
}
