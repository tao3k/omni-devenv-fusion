use super::super::models::{
    LinkGraphEdgeType, LinkGraphLinkFilter, LinkGraphMatchStrategy, LinkGraphPprSubgraphMode,
    LinkGraphRelatedFilter, LinkGraphRelatedPprOptions, LinkGraphScope, LinkGraphSearchFilters,
    LinkGraphSearchOptions, LinkGraphTagFilter,
};
use super::helpers::{
    infer_strategy_from_residual, is_boolean_connector_token, is_default_sort_terms, paren_balance,
    parse_bool, parse_directive_key, parse_edge_type, parse_list_values, parse_scope,
    parse_sort_term, parse_tag_expression, parse_time_filter, parse_timestamp, push_unique_many,
    split_terms_preserving_quotes,
};

fn parse_ppr_subgraph_mode(raw: &str) -> Option<LinkGraphPprSubgraphMode> {
    match raw.trim().to_lowercase().as_str() {
        "auto" => Some(LinkGraphPprSubgraphMode::Auto),
        "disabled" => Some(LinkGraphPprSubgraphMode::Disabled),
        "force" => Some(LinkGraphPprSubgraphMode::Force),
        _ => None,
    }
}

fn has_related_ppr_options(value: &LinkGraphRelatedPprOptions) -> bool {
    value.alpha.is_some()
        || value.max_iter.is_some()
        || value.tol.is_some()
        || value.subgraph_mode.is_some()
}

/// Parsed query payload used by search pipeline.
#[derive(Debug, Clone)]
pub struct ParsedLinkGraphQuery {
    /// Residual free-text query after directive extraction.
    pub query: String,
    /// Parsed/merged search options.
    pub options: LinkGraphSearchOptions,
}

/// Parse a user query into residual query text + merged options.
#[must_use]
pub fn parse_search_query(
    raw_query: &str,
    mut base: LinkGraphSearchOptions,
) -> ParsedLinkGraphQuery {
    let raw = raw_query.trim();
    if raw.is_empty() {
        return ParsedLinkGraphQuery {
            query: String::new(),
            options: base,
        };
    }

    let mut parsed_match_strategy: Option<LinkGraphMatchStrategy> = None;
    let mut parsed_sort_terms = Vec::new();
    let mut parsed_case_sensitive: Option<bool> = None;

    let mut parsed_filters = LinkGraphSearchFilters::default();
    let mut parsed_tags_all: Vec<String> = Vec::new();
    let mut parsed_tags_any: Vec<String> = Vec::new();
    let mut parsed_tags_not: Vec<String> = Vec::new();
    let mut parsed_link_to = LinkGraphLinkFilter::default();
    let mut parsed_linked_by = LinkGraphLinkFilter::default();
    let mut parsed_related = LinkGraphRelatedFilter::default();
    let mut parsed_related_ppr = LinkGraphRelatedPprOptions::default();
    let mut parsed_scope: Option<LinkGraphScope> = None;
    let mut parsed_max_heading_level: Option<usize> = None;
    let mut parsed_max_tree_hops: Option<usize> = None;
    let mut parsed_collapse_to_doc: Option<bool> = None;
    let mut parsed_edge_types: Vec<LinkGraphEdgeType> = Vec::new();
    let mut parsed_per_doc_section_cap: Option<usize> = None;
    let mut parsed_min_section_words: Option<usize> = None;

    let mut parsed_created_after: Option<i64> = None;
    let mut parsed_created_before: Option<i64> = None;
    let mut parsed_modified_after: Option<i64> = None;
    let mut parsed_modified_before: Option<i64> = None;

    let terms = split_terms_preserving_quotes(raw);
    let mut residual_terms: Vec<String> = Vec::new();
    let mut index = 0usize;
    while index < terms.len() {
        let term = terms[index].clone();
        let bare = term.trim().to_lowercase();
        if bare == "orphan" {
            parsed_filters.orphan = true;
            index += 1;
            continue;
        }
        if bare == "tagless" {
            parsed_filters.tagless = true;
            index += 1;
            continue;
        }
        if bare == "missing_backlink" {
            parsed_filters.missing_backlink = true;
            index += 1;
            continue;
        }
        if parse_time_filter(
            &term,
            &mut parsed_created_after,
            &mut parsed_created_before,
            &mut parsed_modified_after,
            &mut parsed_modified_before,
        ) {
            index += 1;
            continue;
        }

        let Some((raw_key, raw_value)) = term.split_once(':') else {
            residual_terms.push(term);
            index += 1;
            continue;
        };
        let (negated_key, key_raw) = parse_directive_key(raw_key);
        let key = key_raw.replace(['-', '.'], "_");
        let mut value = raw_value.trim().to_string();
        if value.is_empty() {
            residual_terms.push(term);
            index += 1;
            continue;
        }

        let mut consumed = index;
        while paren_balance(&value) > 0 && consumed + 1 < terms.len() {
            consumed += 1;
            let next = terms[consumed].trim();
            if next.is_empty() {
                continue;
            }
            if !value.is_empty() {
                value.push(' ');
            }
            value.push_str(next);
        }

        if matches!(key.as_str(), "tag" | "tags") {
            while consumed + 2 < terms.len() && is_boolean_connector_token(&terms[consumed + 1]) {
                let connector = terms[consumed + 1].trim();
                let atom = terms[consumed + 2].trim();
                if !connector.is_empty() {
                    if !value.is_empty() {
                        value.push(' ');
                    }
                    value.push_str(connector);
                }
                if !atom.is_empty() {
                    if !value.is_empty() {
                        value.push(' ');
                    }
                    value.push_str(atom);
                }
                consumed += 2;

                while paren_balance(&value) > 0 && consumed + 1 < terms.len() {
                    consumed += 1;
                    let next = terms[consumed].trim();
                    if next.is_empty() {
                        continue;
                    }
                    if !value.is_empty() {
                        value.push(' ');
                    }
                    value.push_str(next);
                }
            }
        }

        match key.as_str() {
            "match" | "strategy" | "match_strategy" => {
                parsed_match_strategy = Some(LinkGraphMatchStrategy::from_alias(&value));
            }
            "sort" => {
                let mut parsed_any = false;
                for item in parse_list_values(&value) {
                    parsed_sort_terms.push(parse_sort_term(&item));
                    parsed_any = true;
                }
                if !parsed_any {
                    parsed_sort_terms.push(parse_sort_term(&value));
                }
            }
            "case" | "case_sensitive" => {
                parsed_case_sensitive = parse_bool(&value);
            }
            "to" | "link_to" => {
                if negated_key {
                    parsed_link_to.negate = true;
                }
                push_unique_many(&mut parsed_link_to.seeds, parse_list_values(&value));
            }
            "to_not" | "no_link_to" | "link_to_not" => {
                parsed_link_to.negate = true;
                push_unique_many(&mut parsed_link_to.seeds, parse_list_values(&value));
            }
            "link_to_negate" => {
                if let Some(flag) = parse_bool(&value) {
                    parsed_link_to.negate = flag;
                }
            }
            "link_to_recursive" => {
                if let Some(flag) = parse_bool(&value) {
                    parsed_link_to.recursive = flag;
                }
            }
            "link_to_max_distance" => {
                if let Ok(distance) = value.parse::<usize>()
                    && distance > 0
                {
                    parsed_link_to.max_distance = Some(distance);
                }
            }
            "from" | "linked_by" => {
                if negated_key {
                    parsed_linked_by.negate = true;
                }
                push_unique_many(&mut parsed_linked_by.seeds, parse_list_values(&value));
            }
            "from_not" | "no_linked_by" | "linked_by_not" => {
                parsed_linked_by.negate = true;
                push_unique_many(&mut parsed_linked_by.seeds, parse_list_values(&value));
            }
            "linked_by_negate" => {
                if let Some(flag) = parse_bool(&value) {
                    parsed_linked_by.negate = flag;
                }
            }
            "linked_by_recursive" => {
                if let Some(flag) = parse_bool(&value) {
                    parsed_linked_by.recursive = flag;
                }
            }
            "linked_by_max_distance" => {
                if let Ok(distance) = value.parse::<usize>()
                    && distance > 0
                {
                    parsed_linked_by.max_distance = Some(distance);
                }
            }
            "related" => {
                for item in parse_list_values(&value) {
                    if let Some((seed, distance_raw)) = item.rsplit_once('~') {
                        let cleaned_seed = seed.trim();
                        if !cleaned_seed.is_empty() {
                            push_unique_many(
                                &mut parsed_related.seeds,
                                vec![cleaned_seed.to_string()],
                            );
                        }
                        if let Ok(distance) = distance_raw.trim().parse::<usize>()
                            && distance > 0
                        {
                            parsed_related.max_distance = Some(distance);
                        }
                    } else {
                        push_unique_many(&mut parsed_related.seeds, vec![item]);
                    }
                }
            }
            "max_distance" | "distance" | "hops" => {
                if let Ok(distance) = value.parse::<usize>()
                    && distance > 0
                {
                    parsed_related.max_distance = Some(distance);
                }
            }
            "related_ppr_alpha" | "ppr_alpha" => {
                if let Ok(alpha) = value.parse::<f64>()
                    && (0.0..=1.0).contains(&alpha)
                {
                    parsed_related_ppr.alpha = Some(alpha);
                }
            }
            "related_ppr_max_iter" | "ppr_max_iter" => {
                if let Ok(max_iter) = value.parse::<usize>()
                    && max_iter > 0
                {
                    parsed_related_ppr.max_iter = Some(max_iter);
                }
            }
            "related_ppr_tol" | "ppr_tol" => {
                if let Ok(tol) = value.parse::<f64>()
                    && tol > 0.0
                {
                    parsed_related_ppr.tol = Some(tol);
                }
            }
            "related_ppr_subgraph_mode" | "ppr_subgraph_mode" => {
                parsed_related_ppr.subgraph_mode = parse_ppr_subgraph_mode(&value);
            }
            "include" | "include_path" | "include_paths" | "path" => {
                if negated_key {
                    push_unique_many(&mut parsed_filters.exclude_paths, parse_list_values(&value));
                } else {
                    push_unique_many(&mut parsed_filters.include_paths, parse_list_values(&value));
                }
            }
            "exclude" | "exclude_path" | "exclude_paths" => {
                if negated_key {
                    push_unique_many(&mut parsed_filters.include_paths, parse_list_values(&value));
                } else {
                    push_unique_many(&mut parsed_filters.exclude_paths, parse_list_values(&value));
                }
            }
            "tag" | "tags" => {
                if negated_key {
                    push_unique_many(&mut parsed_tags_not, parse_list_values(&value));
                } else {
                    parse_tag_expression(
                        &value,
                        &mut parsed_tags_all,
                        &mut parsed_tags_any,
                        &mut parsed_tags_not,
                    );
                }
            }
            "tag_all" | "tags_all" => {
                if negated_key {
                    push_unique_many(&mut parsed_tags_not, parse_list_values(&value));
                } else {
                    push_unique_many(&mut parsed_tags_all, parse_list_values(&value));
                }
            }
            "tag_any" | "tags_any" => {
                if negated_key {
                    push_unique_many(&mut parsed_tags_not, parse_list_values(&value));
                } else {
                    push_unique_many(&mut parsed_tags_any, parse_list_values(&value));
                }
            }
            "tag_not" | "tags_not" => {
                if negated_key {
                    push_unique_many(&mut parsed_tags_all, parse_list_values(&value));
                } else {
                    push_unique_many(&mut parsed_tags_not, parse_list_values(&value));
                }
            }
            "mentions_of" | "mention" | "mentions" => {
                push_unique_many(&mut parsed_filters.mentions_of, parse_list_values(&value));
            }
            "mentioned_by" | "mentioned_by_notes" => {
                push_unique_many(
                    &mut parsed_filters.mentioned_by_notes,
                    parse_list_values(&value),
                );
            }
            "orphan" => {
                if let Some(flag) = parse_bool(&value) {
                    parsed_filters.orphan = flag;
                }
            }
            "tagless" => {
                if let Some(flag) = parse_bool(&value) {
                    parsed_filters.tagless = flag;
                }
            }
            "missing_backlink" => {
                if let Some(flag) = parse_bool(&value) {
                    parsed_filters.missing_backlink = flag;
                }
            }
            "scope" => {
                parsed_scope = parse_scope(&value);
            }
            "max_heading_level" | "heading_level" => {
                if let Ok(level) = value.parse::<usize>()
                    && (1..=6).contains(&level)
                {
                    parsed_max_heading_level = Some(level);
                }
            }
            "max_tree_hops" | "tree_hops" => {
                if let Ok(hops) = value.parse::<usize>() {
                    parsed_max_tree_hops = Some(hops);
                }
            }
            "collapse_to_doc" => {
                parsed_collapse_to_doc = parse_bool(&value);
            }
            "edge_type" | "edge_types" => {
                for item in parse_list_values(&value) {
                    if let Some(edge_type) = parse_edge_type(&item)
                        && !parsed_edge_types.contains(&edge_type)
                    {
                        parsed_edge_types.push(edge_type);
                    }
                }
            }
            "per_doc_section_cap" => {
                if let Ok(cap) = value.parse::<usize>()
                    && cap > 0
                {
                    parsed_per_doc_section_cap = Some(cap);
                }
            }
            "min_section_words" => {
                if let Ok(words) = value.parse::<usize>() {
                    parsed_min_section_words = Some(words);
                }
            }
            "created_after" => parsed_created_after = parse_timestamp(&value),
            "created_before" => parsed_created_before = parse_timestamp(&value),
            "modified_after" | "updated_after" => parsed_modified_after = parse_timestamp(&value),
            "modified_before" | "updated_before" => {
                parsed_modified_before = parse_timestamp(&value)
            }
            _ => residual_terms.push(format!("{}:{}", raw_key.trim(), value)),
        }
        index = consumed + 1;
    }

    if base.match_strategy == LinkGraphMatchStrategy::Fts {
        if let Some(strategy) = parsed_match_strategy {
            base.match_strategy = strategy;
        } else {
            let residual = residual_terms.join(" ");
            if let Some(inferred) = infer_strategy_from_residual(&residual) {
                base.match_strategy = inferred;
            }
        }
    }

    if !base.case_sensitive
        && let Some(case_sensitive) = parsed_case_sensitive
    {
        base.case_sensitive = case_sensitive;
    }

    if is_default_sort_terms(&base.sort_terms) && !parsed_sort_terms.is_empty() {
        base.sort_terms = parsed_sort_terms;
    }
    if base.sort_terms.is_empty() {
        base.sort_terms = vec![super::super::models::LinkGraphSortTerm::default()];
    }

    if !parsed_tags_all.is_empty() || !parsed_tags_any.is_empty() || !parsed_tags_not.is_empty() {
        let parsed_tag_filter = LinkGraphTagFilter {
            all: parsed_tags_all,
            any: parsed_tags_any,
            not_tags: parsed_tags_not,
        };
        if base.filters.tags.is_none() {
            base.filters.tags = Some(parsed_tag_filter);
        }
    }

    if !parsed_link_to.seeds.is_empty() && base.filters.link_to.is_none() {
        base.filters.link_to = Some(parsed_link_to);
    }
    if !parsed_linked_by.seeds.is_empty() && base.filters.linked_by.is_none() {
        base.filters.linked_by = Some(parsed_linked_by);
    }
    let parsed_related_has_ppr = has_related_ppr_options(&parsed_related_ppr);
    if base.filters.related.is_none() {
        if !parsed_related.seeds.is_empty() {
            if parsed_related_has_ppr {
                parsed_related.ppr = Some(parsed_related_ppr);
            }
            base.filters.related = Some(parsed_related);
        }
    } else if let Some(base_related) = base.filters.related.as_mut() {
        if base_related.max_distance.is_none() && parsed_related.max_distance.is_some() {
            base_related.max_distance = parsed_related.max_distance;
        }
        if base_related.ppr.is_none() && parsed_related_has_ppr {
            base_related.ppr = Some(parsed_related_ppr);
        }
    }

    if base.filters.include_paths.is_empty() && !parsed_filters.include_paths.is_empty() {
        base.filters.include_paths = parsed_filters.include_paths;
    }
    if base.filters.exclude_paths.is_empty() && !parsed_filters.exclude_paths.is_empty() {
        base.filters.exclude_paths = parsed_filters.exclude_paths;
    }
    if base.filters.mentions_of.is_empty() && !parsed_filters.mentions_of.is_empty() {
        base.filters.mentions_of = parsed_filters.mentions_of;
    }
    if base.filters.mentioned_by_notes.is_empty() && !parsed_filters.mentioned_by_notes.is_empty() {
        base.filters.mentioned_by_notes = parsed_filters.mentioned_by_notes;
    }
    if !base.filters.orphan && parsed_filters.orphan {
        base.filters.orphan = true;
    }
    if !base.filters.tagless && parsed_filters.tagless {
        base.filters.tagless = true;
    }
    if !base.filters.missing_backlink && parsed_filters.missing_backlink {
        base.filters.missing_backlink = true;
    }
    if base.filters.scope.is_none() {
        base.filters.scope = parsed_scope;
    }
    if base.filters.max_heading_level.is_none() {
        base.filters.max_heading_level = parsed_max_heading_level;
    }
    if base.filters.max_tree_hops.is_none() {
        base.filters.max_tree_hops = parsed_max_tree_hops;
    }
    if base.filters.collapse_to_doc.is_none() {
        base.filters.collapse_to_doc = parsed_collapse_to_doc;
    }
    if base.filters.edge_types.is_empty() && !parsed_edge_types.is_empty() {
        base.filters.edge_types = parsed_edge_types;
    }
    if base.filters.per_doc_section_cap.is_none() {
        base.filters.per_doc_section_cap = parsed_per_doc_section_cap;
    }
    if base.filters.min_section_words.is_none() {
        base.filters.min_section_words = parsed_min_section_words;
    }

    if base.created_after.is_none() {
        base.created_after = parsed_created_after;
    }
    if base.created_before.is_none() {
        base.created_before = parsed_created_before;
    }
    if base.modified_after.is_none() {
        base.modified_after = parsed_modified_after;
    }
    if base.modified_before.is_none() {
        base.modified_before = parsed_modified_before;
    }

    ParsedLinkGraphQuery {
        query: residual_terms.join(" ").trim().to_string(),
        options: base,
    }
}
