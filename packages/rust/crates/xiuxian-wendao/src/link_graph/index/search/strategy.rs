use super::super::{
    LinkGraphDocument, LinkGraphIndex, LinkGraphMatchStrategy, LinkGraphScope,
    LinkGraphSearchOptions, SECTION_AGGREGATION_BETA, SectionCandidate, SectionMatch,
    WEIGHT_FTS_LEXICAL, WEIGHT_FTS_PATH, WEIGHT_FTS_SECTION, WEIGHT_PATH_FUZZY_PATH,
    WEIGHT_PATH_FUZZY_SECTION, score_document, score_document_exact, score_document_regex,
};
use regex::Regex;

impl LinkGraphIndex {
    pub(super) fn score_doc_for_strategy(
        &self,
        doc: &LinkGraphDocument,
        options: &LinkGraphSearchOptions,
        raw_query: &str,
        clean_query: &str,
        query_tokens: &[String],
        scope: LinkGraphScope,
        collapse_to_doc: bool,
        section_candidates: &[SectionCandidate],
        section_match: Option<&SectionMatch>,
        section_score: f64,
        path_score: f64,
        semantic_edges_enabled: bool,
        regex: Option<&Regex>,
    ) -> (f64, String) {
        let (mut doc_score, mut doc_reason) = match options.match_strategy {
            LinkGraphMatchStrategy::Fts if !raw_query.is_empty() => {
                let lexical =
                    score_document(doc, clean_query, query_tokens, options.case_sensitive);
                let blended = (lexical * WEIGHT_FTS_LEXICAL
                    + section_score * WEIGHT_FTS_SECTION
                    + path_score * WEIGHT_FTS_PATH)
                    .max(lexical);
                let reason = if let Some(section) = section_match {
                    format!("fts+{}", section.reason)
                } else {
                    "fts".to_string()
                };
                (blended, reason)
            }
            LinkGraphMatchStrategy::PathFuzzy if !raw_query.is_empty() => {
                let base = path_score.max(section_score);
                let blended = if base > 0.0 {
                    (path_score * WEIGHT_PATH_FUZZY_PATH
                        + section_score * WEIGHT_PATH_FUZZY_SECTION)
                        .max(base)
                } else {
                    0.0
                };
                let reason = if let Some(section) = section_match {
                    format!("path_fuzzy+{}", section.reason)
                } else {
                    "path_fuzzy".to_string()
                };
                (blended, reason)
            }
            LinkGraphMatchStrategy::Exact if !raw_query.is_empty() => (
                score_document_exact(doc, clean_query, options.case_sensitive),
                "exact".to_string(),
            ),
            LinkGraphMatchStrategy::Re if !raw_query.is_empty() => (
                regex
                    .map(|compiled| score_document_regex(doc, compiled))
                    .unwrap_or(0.0),
                "regex".to_string(),
            ),
            _ => (1.0, "filtered".to_string()),
        };

        if matches!(scope, LinkGraphScope::Mixed)
            && collapse_to_doc
            && !section_candidates.is_empty()
        {
            let max_section = section_candidates.first().map_or(0.0, |row| row.score);
            let section_tail_sum = section_candidates
                .iter()
                .skip(1)
                .map(|row| row.score)
                .sum::<f64>();
            let aggregated =
                (max_section + SECTION_AGGREGATION_BETA * section_tail_sum).clamp(0.0, 1.0);
            if aggregated > doc_score {
                doc_score = aggregated;
                doc_reason.push_str("+section_agg");
            }
        }

        if semantic_edges_enabled
            && !raw_query.is_empty()
            && matches!(
                options.match_strategy,
                LinkGraphMatchStrategy::Fts | LinkGraphMatchStrategy::PathFuzzy
            )
            && doc_score > 0.0
        {
            let boosted = self.apply_graph_rank_boost(&doc.id, doc_score);
            if boosted > doc_score {
                doc_reason.push_str("+graph_rank");
            }
            doc_score = boosted;
        }

        (doc_score, doc_reason)
    }
}
