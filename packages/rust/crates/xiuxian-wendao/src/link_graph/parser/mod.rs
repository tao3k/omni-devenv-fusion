//! Markdown note parsing for link-graph indexing.

mod content;
mod links;
mod paths;
mod sections;
mod time;

use super::models::LinkGraphDocument;
use std::path::Path;

use self::content::{
    count_words, extract_lead, extract_saliency_params, extract_tags, extract_title,
    parse_frontmatter,
};
use self::links::extract_links;
use self::paths::{normalize_slashes, relative_doc_id};
use self::sections::extract_sections;
use self::time::resolve_note_timestamps;

pub use self::paths::{is_supported_note, normalize_alias};
pub use self::sections::ParsedSection;

/// Parsed note payload + unresolved outgoing link targets.
#[derive(Debug, Clone)]
pub struct ParsedNote {
    /// Canonical document row.
    pub doc: LinkGraphDocument,
    /// Raw link targets extracted from content.
    pub link_targets: Vec<String>,
    /// Parsed markdown sections/headings for section-aware retrieval.
    pub sections: Vec<ParsedSection>,
}

/// Parse one note file into structured document row plus outgoing link targets.
#[must_use]
pub fn parse_note(path: &Path, root: &Path, content: &str) -> Option<ParsedNote> {
    let doc_id = relative_doc_id(path, root)?;
    let stem = path.file_stem()?.to_string_lossy().to_string();
    if stem.is_empty() {
        return None;
    }
    let rel_path = normalize_slashes(
        path.strip_prefix(root)
            .ok()
            .map_or_else(
                || path.to_string_lossy().to_string(),
                |p| p.to_string_lossy().to_string(),
            )
            .as_str(),
    );
    let (frontmatter, body) = parse_frontmatter(content);
    let title = extract_title(frontmatter.as_ref(), body, &stem);
    let tags = extract_tags(frontmatter.as_ref());
    let lead = extract_lead(body);
    let word_count = count_words(body);
    let (saliency_base, decay_rate) = extract_saliency_params(frontmatter.as_ref());
    let search_text = body.to_string();
    let search_text_lower = search_text.to_lowercase();
    let id_lower = doc_id.to_lowercase();
    let stem_lower = stem.to_lowercase();
    let path_lower = rel_path.to_lowercase();
    let title_lower = title.to_lowercase();
    let tags_lower: Vec<String> = tags.iter().map(|tag| tag.to_lowercase()).collect();
    let (created_ts, modified_ts) = resolve_note_timestamps(frontmatter.as_ref(), path);
    let links = extract_links(body, path, root);
    let sections = extract_sections(body);
    Some(ParsedNote {
        doc: LinkGraphDocument {
            id: doc_id,
            id_lower,
            stem,
            stem_lower,
            path: rel_path,
            path_lower,
            title,
            title_lower,
            tags,
            tags_lower,
            lead,
            word_count,
            search_text,
            search_text_lower,
            saliency_base,
            decay_rate,
            created_ts,
            modified_ts,
        },
        link_targets: links,
        sections,
    })
}
