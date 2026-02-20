use super::super::{
    DEFAULT_MIN_SECTION_WORDS, DEFAULT_PER_DOC_SECTION_CAP, LinkGraphDocument, LinkGraphIndex,
    LinkGraphScope, LinkGraphSearchFilters, LinkGraphSearchOptions,
};

impl LinkGraphIndex {
    fn has_tag_filters(filters: &LinkGraphSearchFilters) -> bool {
        filters.tags.as_ref().is_some_and(|tags| {
            !tags.all.is_empty() || !tags.any.is_empty() || !tags.not_tags.is_empty()
        })
    }

    pub(super) fn effective_scope(filters: &LinkGraphSearchFilters) -> LinkGraphScope {
        filters.scope.unwrap_or(LinkGraphScope::DocOnly)
    }

    pub(super) fn effective_per_doc_section_cap(
        filters: &LinkGraphSearchFilters,
        scope: LinkGraphScope,
    ) -> usize {
        if let Some(cap) = filters.per_doc_section_cap {
            return cap.max(1);
        }
        if matches!(scope, LinkGraphScope::SectionOnly | LinkGraphScope::Mixed) {
            return DEFAULT_PER_DOC_SECTION_CAP;
        }
        1
    }

    pub(super) fn effective_min_section_words(
        filters: &LinkGraphSearchFilters,
        scope: LinkGraphScope,
    ) -> usize {
        if let Some(min_words) = filters.min_section_words {
            return min_words;
        }
        if matches!(scope, LinkGraphScope::SectionOnly | LinkGraphScope::Mixed) {
            return DEFAULT_MIN_SECTION_WORDS;
        }
        0
    }

    pub(super) fn effective_max_heading_level(filters: &LinkGraphSearchFilters) -> usize {
        filters.max_heading_level.unwrap_or(6).clamp(1, 6)
    }

    pub(super) fn has_non_query_filters(options: &LinkGraphSearchOptions) -> bool {
        let filters = &options.filters;
        !filters.include_paths.is_empty()
            || !filters.exclude_paths.is_empty()
            || Self::has_tag_filters(filters)
            || Self::has_link_filter(&filters.link_to)
            || Self::has_link_filter(&filters.linked_by)
            || Self::has_related_filter(&filters.related)
            || !filters.mentions_of.is_empty()
            || !filters.mentioned_by_notes.is_empty()
            || filters.orphan
            || filters.tagless
            || filters.missing_backlink
            || filters.scope.is_some()
            || filters.max_heading_level.is_some()
            || filters.max_tree_hops.is_some()
            || filters.collapse_to_doc.is_some()
            || !filters.edge_types.is_empty()
            || filters.per_doc_section_cap.is_some()
            || filters.min_section_words.is_some()
            || options.created_after.is_some()
            || options.created_before.is_some()
            || options.modified_after.is_some()
            || options.modified_before.is_some()
    }

    pub(super) fn matches_temporal_filters(
        doc: &LinkGraphDocument,
        options: &LinkGraphSearchOptions,
    ) -> bool {
        if let Some(created_after) = options.created_after
            && doc.created_ts.is_none_or(|ts| ts < created_after)
        {
            return false;
        }
        if let Some(created_before) = options.created_before
            && doc.created_ts.is_none_or(|ts| ts > created_before)
        {
            return false;
        }
        if let Some(modified_after) = options.modified_after
            && doc.modified_ts.is_none_or(|ts| ts < modified_after)
        {
            return false;
        }
        if let Some(modified_before) = options.modified_before
            && doc.modified_ts.is_none_or(|ts| ts > modified_before)
        {
            return false;
        }
        true
    }

    pub(super) fn matches_structured_filters(
        &self,
        doc: &LinkGraphDocument,
        options: &LinkGraphSearchOptions,
        include_paths: &[String],
        exclude_paths: &[String],
        tag_all: &[String],
        tag_any: &[String],
        tag_not: &[String],
        mention_filters: &[String],
    ) -> bool {
        if !Self::matches_path_filters(doc, include_paths, exclude_paths) {
            return false;
        }

        if !Self::matches_tag_filters(doc, options, tag_all, tag_any, tag_not) {
            return false;
        }

        if !self.matches_graph_state_filters(doc, options, mention_filters) {
            return false;
        }

        true
    }
}
