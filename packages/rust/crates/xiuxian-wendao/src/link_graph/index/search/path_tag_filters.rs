use super::super::{
    LinkGraphDocument, LinkGraphIndex, LinkGraphSearchOptions, normalize_with_case,
    path_matches_filter,
};
use std::collections::HashSet;

impl LinkGraphIndex {
    pub(super) fn matches_path_filters(
        doc: &LinkGraphDocument,
        include_paths: &[String],
        exclude_paths: &[String],
    ) -> bool {
        if !include_paths.is_empty()
            && !include_paths
                .iter()
                .any(|filter| path_matches_filter(&doc.path, filter))
        {
            return false;
        }

        if exclude_paths
            .iter()
            .any(|filter| path_matches_filter(&doc.path, filter))
        {
            return false;
        }

        true
    }

    pub(super) fn matches_tag_filters(
        doc: &LinkGraphDocument,
        options: &LinkGraphSearchOptions,
        tag_all: &[String],
        tag_any: &[String],
        tag_not: &[String],
    ) -> bool {
        if tag_all.is_empty() && tag_any.is_empty() && tag_not.is_empty() {
            return true;
        }

        let doc_tags: HashSet<String> = doc
            .tags
            .iter()
            .map(|tag| normalize_with_case(tag, options.case_sensitive))
            .collect();
        if !tag_all.iter().all(|tag| doc_tags.contains(tag)) {
            return false;
        }
        if !tag_any.is_empty() && !tag_any.iter().any(|tag| doc_tags.contains(tag)) {
            return false;
        }
        if tag_not.iter().any(|tag| doc_tags.contains(tag)) {
            return false;
        }

        true
    }
}
