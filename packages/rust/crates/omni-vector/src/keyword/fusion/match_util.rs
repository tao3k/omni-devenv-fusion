//! Multi-pattern matching utilities for fusion (Aho-Corasick + batch lowercase).

use aho_corasick::{AhoCorasick, PatternID};
use std::collections::HashSet;

use lance::deps::arrow_array::{Array, StringArray};

/// Lowercase each element of a StringArray, returning a new StringArray.
///
/// **Swap-in point for Arrow kernel**: When Arrow provides a `compute::lowercase` (or
/// `arrow_string::lowercase`) kernel, replace the body with a call to that kernel for
/// SIMD-accelerated batch lowercase. Current implementation uses Rust `str::to_lowercase()`.
pub fn lowercase_string_array(arr: &StringArray) -> StringArray {
    let lower: Vec<String> = (0..arr.len())
        .map(|i| {
            if arr.is_null(i) {
                String::new()
            } else {
                arr.value(i).to_lowercase()
            }
        })
        .collect();
    StringArray::from(lower)
}

/// Build ordered keys and an Arrow StringArray of lowercased names for batch fusion (Arrow-native layout).
/// Returns `(keys_ordered, names_lower_array)` so that `names_lower_array.value(i)` is the lowercase of `keys_ordered[i]`.
///
/// Uses [`lowercase_string_array`] for the batch lowercase step; that function is the single swap-in
/// point when Arrow gains a `compute::lowercase` kernel.
pub fn build_name_lower_arrow(
    keys: impl Iterator<Item = impl AsRef<str>>,
) -> (Vec<String>, StringArray) {
    let keys_ordered: Vec<String> = keys.map(|k| k.as_ref().to_string()).collect();
    let input_array = StringArray::from(keys_ordered.clone());
    let names_lower_array = lowercase_string_array(&input_array);
    (keys_ordered, names_lower_array)
}

/// Result of one Aho-Corasick scan: token match count and whether exact phrase matched.
#[derive(Clone, Copy, Default)]
pub struct NameMatchResult {
    pub token_count: usize,
    pub exact_phrase: bool,
}

/// One-pass Aho-Corasick: token count + exact phrase. Pattern 0 is exact phrase when present.
pub fn count_name_token_matches_and_exact(
    ac: &AhoCorasick,
    haystack: &str,
    exact_phrase_pattern_id: Option<PatternID>,
) -> NameMatchResult {
    let mut seen = HashSet::new();
    let mut exact_phrase = false;
    for mat in ac.find_iter(haystack) {
        if exact_phrase_pattern_id == Some(mat.pattern()) {
            exact_phrase = true;
        } else {
            seen.insert(mat.pattern());
        }
    }
    NameMatchResult {
        token_count: seen.len(),
        exact_phrase,
    }
}

/// Build automaton with exact phrase as pattern 0 for one-pass token + phrase match (O(n+m)).
/// Returns (automaton, exact_phrase_pattern_id). Use with `count_name_token_matches_and_exact`.
/// Full query is pattern 0 so both single-word ("commit") and multi-word ("git commit") get exact-phrase boost.
pub fn build_name_token_automaton_with_phrase(
    query_parts: &[&str],
    full_query_lower: &str,
) -> Option<(AhoCorasick, Option<PatternID>)> {
    let mut patterns: Vec<&str> = Vec::new();
    let has_exact_pattern = full_query_lower.len() > 2;
    if has_exact_pattern {
        patterns.push(full_query_lower);
    }
    for t in query_parts.iter().filter(|t| t.len() > 2) {
        if !patterns.contains(t) {
            patterns.push(t);
        }
    }
    if patterns.is_empty() {
        return None;
    }
    let ac = AhoCorasick::new(&patterns).ok()?;
    let exact_id = if has_exact_pattern {
        Some(PatternID::ZERO)
    } else {
        None
    };
    Some((ac, exact_id))
}

#[cfg(test)]
mod tests {
    use super::*;
    use lance::deps::arrow_array::Array;

    #[test]
    fn lowercase_string_array_roundtrip() {
        let arr = StringArray::from(vec!["Git.Commit", "Writer.Polish", "KNOWLEDGE.RECALL"]);
        let lower = lowercase_string_array(&arr);
        assert_eq!(lower.len(), 3);
        assert_eq!(lower.value(0), "git.commit");
        assert_eq!(lower.value(1), "writer.polish");
        assert_eq!(lower.value(2), "knowledge.recall");
    }

    #[test]
    fn build_name_lower_arrow_indexed() {
        let keys = ["Git.Commit", "Writer.Polish", "knowledge.recall"];
        let (keys_ordered, names_lower) = build_name_lower_arrow(keys.iter());
        assert_eq!(keys_ordered.len(), 3);
        assert_eq!(names_lower.value(0), "git.commit");
        assert_eq!(names_lower.value(1), "writer.polish");
        assert_eq!(names_lower.value(2), "knowledge.recall");
        assert_eq!(keys_ordered[0], "Git.Commit");
    }

    #[test]
    fn automaton_with_phrase_single_word_exact() {
        let query_parts = ["commit"];
        let full = "commit";
        let (ac, exact_id) = build_name_token_automaton_with_phrase(&query_parts, full).unwrap();
        assert_eq!(exact_id, Some(PatternID::ZERO));

        let r = count_name_token_matches_and_exact(&ac, "git_commit", exact_id);
        assert!(r.exact_phrase, "commit is substring of git_commit");
        assert_eq!(
            r.token_count, 0,
            "single-word query is only pattern 0, not counted as token"
        );

        let r2 = count_name_token_matches_and_exact(&ac, "git_status", exact_id);
        assert_eq!(r2.token_count, 0);
        assert!(!r2.exact_phrase);
    }

    #[test]
    fn automaton_with_phrase_multi_word() {
        let query_parts = ["git", "commit"];
        let full = "git commit";
        let (ac, exact_id) = build_name_token_automaton_with_phrase(&query_parts, full).unwrap();
        assert_eq!(exact_id, Some(PatternID::ZERO));

        let r = count_name_token_matches_and_exact(&ac, "git_commit", exact_id);
        assert!(r.token_count >= 1, "token match for git and commit");
        assert!(
            !r.exact_phrase,
            "git_commit does not contain substring 'git commit'"
        );
    }
}
