use comrak::{Arena, Options, nodes::NodeValue, parse_document};
use std::path::{Component, Path};

use super::paths::{normalize_slashes, trim_md_extension};

fn normalize_link_target(raw: &str) -> String {
    trim_md_extension(&normalize_slashes(raw.trim()))
        .trim_matches('/')
        .to_string()
}

fn normalize_wikilink_target(raw: &str) -> Option<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return None;
    }
    let mut candidate = trimmed.to_string();
    if let Some((left, _right)) = candidate.split_once('#') {
        candidate = left.to_string();
    }
    if let Some((left, _right)) = candidate.split_once('?') {
        candidate = left.to_string();
    }
    let normalized = normalize_link_target(&candidate);
    if normalized.is_empty() {
        None
    } else {
        Some(normalized)
    }
}

fn extract_relative_dir_parts(path: &Path, root: &Path) -> Vec<String> {
    let rel = path.strip_prefix(root).ok();
    let Some(parent) = rel.and_then(Path::parent) else {
        return Vec::new();
    };
    parent
        .components()
        .filter_map(|component| match component {
            Component::Normal(segment) => Some(segment.to_string_lossy().to_string()),
            _ => None,
        })
        .collect()
}

fn normalize_markdown_target(raw: &str, source_path: &Path, root: &Path) -> Option<String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return None;
    }

    // Support [text](<path/to/doc.md>) and [text](path/to/doc.md "title")
    let unwrapped = if trimmed.starts_with('<') {
        let end = trimmed.find('>')?;
        &trimmed[1..end]
    } else {
        trimmed.split_whitespace().next().unwrap_or_default()
    };
    if unwrapped.is_empty() {
        return None;
    }

    let mut candidate = normalize_slashes(unwrapped);
    if candidate.is_empty() {
        return None;
    }
    let lower_candidate = candidate.to_lowercase();
    if lower_candidate.starts_with('#') {
        return None;
    }
    if lower_candidate.starts_with("http://")
        || lower_candidate.starts_with("https://")
        || lower_candidate.starts_with("mailto:")
        || lower_candidate.starts_with("tel:")
        || lower_candidate.starts_with("data:")
        || lower_candidate.starts_with("javascript:")
    {
        return None;
    }

    if let Some((left, _right)) = candidate.split_once('#') {
        candidate = left.to_string();
    }
    if let Some((left, _right)) = candidate.split_once('?') {
        candidate = left.to_string();
    }
    if candidate.is_empty() {
        return None;
    }

    let absolute = candidate.starts_with('/');
    let mut parts: Vec<String> = if absolute {
        Vec::new()
    } else {
        extract_relative_dir_parts(source_path, root)
    };

    for segment in candidate.split('/') {
        let cleaned = segment.trim();
        if cleaned.is_empty() || cleaned == "." {
            continue;
        }
        if cleaned == ".." {
            parts.pop();
            continue;
        }
        parts.push(cleaned.to_string());
    }

    if parts.is_empty() {
        return None;
    }

    let normalized = trim_md_extension(&parts.join("/"))
        .trim_matches('/')
        .to_string();
    if normalized.is_empty() {
        None
    } else {
        Some(normalized)
    }
}

fn extract_markdown_links_with_comrak(body: &str, source_path: &Path, root: &Path) -> Vec<String> {
    let mut options = Options::default();
    // Support Obsidian-style `[[url|title]]` wikilinks in AST parsing.
    options.extension.wikilinks_title_after_pipe = true;

    let arena = Arena::new();
    let root_node = parse_document(&arena, body, &options);

    let mut out: Vec<String> = Vec::new();
    for node in root_node.descendants() {
        let normalized = match &node.data().value {
            NodeValue::Link(link) => normalize_markdown_target(&link.url, source_path, root),
            // Wikilinks are note IDs/aliases by design, not relative markdown paths.
            NodeValue::WikiLink(link) => normalize_wikilink_target(&link.url),
            _ => None,
        };
        let Some(normalized) = normalized else {
            continue;
        };
        out.push(normalized);
    }
    out
}

pub(super) fn extract_links(body: &str, source_path: &Path, root: &Path) -> Vec<String> {
    let mut out: Vec<String> = extract_markdown_links_with_comrak(body, source_path, root);
    out.sort();
    out.dedup();
    out
}
