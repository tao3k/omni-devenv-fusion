use super::super::{
    LinkGraphIndex, LinkGraphMatchStrategy, LinkGraphSearchOptions, normalize_path_filter,
    normalize_with_case, tokenize,
};
use regex::{Regex, RegexBuilder};

#[derive(Debug, Clone)]
pub(super) struct SearchExecutionContext {
    pub(super) bounded: usize,
    pub(super) case_sensitive: bool,
    pub(super) raw_query: String,
    pub(super) clean_query: String,
    pub(super) query_tokens: Vec<String>,
    pub(super) include_paths: Vec<String>,
    pub(super) exclude_paths: Vec<String>,
    pub(super) tag_all: Vec<String>,
    pub(super) tag_any: Vec<String>,
    pub(super) tag_not: Vec<String>,
    pub(super) mention_filters: Vec<String>,
    pub(super) regex: Option<Regex>,
}

impl LinkGraphIndex {
    pub(super) fn prepare_execution_context(
        &self,
        query: &str,
        limit: usize,
        options: &LinkGraphSearchOptions,
    ) -> Option<SearchExecutionContext> {
        let raw_query = query.trim().to_string();
        let bounded = limit.max(1);
        let case_sensitive = options.case_sensitive;
        let clean_query = normalize_with_case(&raw_query, case_sensitive);
        let query_tokens = tokenize(&raw_query, case_sensitive);

        let include_paths: Vec<String> = options
            .filters
            .include_paths
            .iter()
            .map(|path| normalize_path_filter(path))
            .filter(|path| !path.is_empty())
            .collect();
        let exclude_paths: Vec<String> = options
            .filters
            .exclude_paths
            .iter()
            .map(|path| normalize_path_filter(path))
            .filter(|path| !path.is_empty())
            .collect();

        let (tag_all, tag_any, tag_not) = if let Some(tags) = options.filters.tags.as_ref() {
            (
                tags.all
                    .iter()
                    .map(|tag| normalize_with_case(tag, case_sensitive))
                    .collect::<Vec<String>>(),
                tags.any
                    .iter()
                    .map(|tag| normalize_with_case(tag, case_sensitive))
                    .collect::<Vec<String>>(),
                tags.not_tags
                    .iter()
                    .map(|tag| normalize_with_case(tag, case_sensitive))
                    .collect::<Vec<String>>(),
            )
        } else {
            (Vec::new(), Vec::new(), Vec::new())
        };

        let mention_filters: Vec<String> = options
            .filters
            .mentions_of
            .iter()
            .map(|phrase| normalize_with_case(phrase, case_sensitive))
            .filter(|phrase| !phrase.is_empty())
            .collect();

        let regex = if matches!(options.match_strategy, LinkGraphMatchStrategy::Re) {
            RegexBuilder::new(&raw_query)
                .case_insensitive(!case_sensitive)
                .build()
                .ok()
        } else {
            None
        };
        if matches!(options.match_strategy, LinkGraphMatchStrategy::Re) && regex.is_none() {
            return None;
        }

        Some(SearchExecutionContext {
            bounded,
            case_sensitive,
            raw_query,
            clean_query,
            query_tokens,
            include_paths,
            exclude_paths,
            tag_all,
            tag_any,
            tag_not,
            mention_filters,
            regex,
        })
    }
}
