//! Agentic Search - Intent-aware tool routing (P0).
//!
//! Provides `agentic_search` with intent-based strategy selection:
//! - **Exact**: keyword-only (when query_text present), else hybrid
//! - **Semantic**: vector-only
//! - **Category** / **Hybrid**: vector + keyword fusion

use crate::VectorStore;
use crate::error::VectorStoreError;
use crate::skill::{ToolSearchOptions, ToolSearchResult};
use serde::{Deserialize, Serialize};
use std::str::FromStr;
use std::time::Instant;

/// Query intent for strategy selection.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QueryIntent {
    /// Exact name or command match → keyword-only when query_text present.
    Exact,
    /// Filter by category / skill (currently same as Hybrid).
    Category,
    /// Semantic similarity only (vector-only).
    Semantic,
    /// Hybrid vector + keyword (default).
    Hybrid,
}

impl Default for QueryIntent {
    fn default() -> Self {
        Self::Hybrid
    }
}

impl FromStr for QueryIntent {
    type Err = std::convert::Infallible;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Ok(match s.trim().to_lowercase().as_str() {
            "exact" => QueryIntent::Exact,
            "category" => QueryIntent::Category,
            "semantic" => QueryIntent::Semantic,
            "hybrid" | _ => QueryIntent::Hybrid,
        })
    }
}

/// Escapes a string for use in a Lance SQL predicate (single-quote doubling).
fn escape_sql_value(s: &str) -> String {
    s.replace('\'', "''")
}

/// Configuration for agentic tool search.
#[derive(Debug, Clone)]
pub struct AgenticSearchConfig {
    /// Max number of results to return.
    pub limit: usize,
    /// Minimum score threshold (0.0–1.0).
    pub threshold: f32,
    /// Optional intent hint; when None, hybrid is used.
    pub intent: Option<QueryIntent>,
    /// Tool search options (rerank, etc.).
    pub tool_options: ToolSearchOptions,
    /// Optional filter: only tools from this skill (e.g. `"git"`).
    pub skill_name_filter: Option<String>,
    /// Optional filter: only tools in this category.
    pub category_filter: Option<String>,
}

impl Default for AgenticSearchConfig {
    fn default() -> Self {
        Self {
            limit: 10,
            threshold: 0.2,
            intent: None,
            tool_options: ToolSearchOptions::default(),
            skill_name_filter: None,
            category_filter: None,
        }
    }
}

impl VectorStore {
    /// Intent-aware tool search. Selects strategy from config.intent:
    /// - **Exact**: keyword-only when query_text is present; otherwise hybrid.
    /// - **Semantic**: vector-only (no keyword fusion).
    /// - **Category** / **Hybrid**: full hybrid (vector + keyword + RRF).
    pub async fn agentic_search(
        &self,
        table_name: &str,
        query_vector: &[f32],
        query_text: Option<&str>,
        config: AgenticSearchConfig,
    ) -> Result<Vec<ToolSearchResult>, VectorStoreError> {
        let start = Instant::now();
        let intent = config.intent.unwrap_or(QueryIntent::Hybrid);

        let mut preds = Vec::new();
        if let Some(s) = &config.skill_name_filter {
            preds.push(format!("skill_name = '{}'", escape_sql_value(s)));
        }
        if let Some(c) = &config.category_filter {
            preds.push(format!("category = '{}'", escape_sql_value(c)));
        }
        let where_filter: Option<String> = if preds.is_empty() {
            None
        } else {
            Some(preds.join(" AND "))
        };
        let where_filter = where_filter.as_deref();

        let mut results = match intent {
            QueryIntent::Exact => {
                if let Some(text) = query_text {
                    match self
                        .keyword_search(table_name, text, config.limit.saturating_mul(2))
                        .await
                    {
                        Ok(kw) => kw,
                        Err(_) => {
                            self.search_tools_with_options(
                                table_name,
                                query_vector,
                                query_text,
                                config.limit,
                                config.threshold,
                                config.tool_options,
                                where_filter,
                            )
                            .await?
                        }
                    }
                } else {
                    self.search_tools_with_options(
                        table_name,
                        query_vector,
                        query_text,
                        config.limit,
                        config.threshold,
                        config.tool_options,
                        where_filter,
                    )
                    .await?
                }
            }
            QueryIntent::Semantic => {
                self.search_tools_with_options(
                    table_name,
                    query_vector,
                    None,
                    config.limit,
                    config.threshold,
                    config.tool_options,
                    where_filter,
                )
                .await?
            }
            QueryIntent::Category | QueryIntent::Hybrid => {
                self.search_tools_with_options(
                    table_name,
                    query_vector,
                    query_text,
                    config.limit,
                    config.threshold,
                    config.tool_options,
                    where_filter,
                )
                .await?
            }
        };

        if config.threshold > 0.0 {
            results.retain(|r| r.score >= config.threshold);
        }
        results.truncate(config.limit);
        self.record_query(table_name, start.elapsed().as_millis() as u64);
        Ok(results)
    }
}
