//! Pattern utilities for AST matching.
//!
//! Provides high-level functions for creating patterns and scanning content.

use anyhow::{Context, Result};

use crate::lang::Lang;
use crate::re_exports::{Pattern, SupportLang, MetaVariable, LanguageExt, MatcherExt};
use crate::item::Match;

/// Create a search pattern for a language
pub fn pattern(pattern: &str, lang: Lang) -> Result<Pattern> {
    let lang_str = lang.as_str();
    let support_lang: SupportLang = lang_str.parse()
        .with_context(|| format!("Failed to parse language: {}", lang_str))?;
    Pattern::try_new(pattern, support_lang)
        .with_context(|| format!("Failed to parse pattern: {}", pattern))
}

/// Scan content and find all matches for a pattern
pub fn scan(content: &str, pat: &str, lang: Lang) -> Result<Vec<Match>> {
    let lang_str = lang.as_str();
    let support_lang: SupportLang = lang_str.parse()
        .with_context(|| format!("Failed to parse language: {}", lang_str))?;
    let grep_result = support_lang.ast_grep(content);
    let root_node = grep_result.root();

    let search_pattern = Pattern::try_new(pat, support_lang)
        .with_context(|| format!("Failed to parse pattern: {}", pat))?;

    let mut matches = Vec::new();

    for node in root_node.dfs() {
        if let Some(m) = search_pattern.match_node(node.clone()) {
            let env = m.get_env();

            // Extract captures using MetaVariable API
            let mut captures = Vec::new();
            for mv in env.get_matched_variables() {
                let name = match &mv {
                    MetaVariable::Capture(name, _) => name.as_str(),
                    MetaVariable::MultiCapture(name) => name.as_str(),
                    _ => continue,
                };
                if let Some(captured) = env.get_match(name) {
                    captures.push((name.to_string(), captured.text().to_string()));
                }
            }

            matches.push(Match {
                text: m.text().to_string(),
                start: m.range().start,
                end: m.range().end,
                captures,
            });
        }
    }

    Ok(matches)
}

/// Extract a single capture value from pattern matches
pub fn extract(content: &str, pattern: &str, var: &str, lang: Lang) -> Option<String> {
    let matches = scan(content, pattern, lang).ok()?;
    for m in matches {
        for (name, value) in m.captures {
            if name == var {
                return Some(value);
            }
        }
    }
    None
}

/// Scan with SupportLang directly
#[allow(dead_code)]
pub fn scan_with_lang(content: &str, pat: &str, support_lang: SupportLang) -> Result<Vec<Match>> {
    let grep_result = support_lang.ast_grep(content);
    let root_node = grep_result.root();

    let search_pattern = Pattern::try_new(pat, support_lang)
        .with_context(|| format!("Failed to parse pattern: {}", pat))?;

    let mut matches = Vec::new();

    for node in root_node.dfs() {
        if let Some(m) = search_pattern.match_node(node.clone()) {
            let env = m.get_env();

            let mut captures = Vec::new();
            for mv in env.get_matched_variables() {
                let name = match &mv {
                    MetaVariable::Capture(name, _) => name.as_str(),
                    MetaVariable::MultiCapture(name) => name.as_str(),
                    _ => continue,
                };
                if let Some(captured) = env.get_match(name) {
                    captures.push((name.to_string(), captured.text().to_string()));
                }
            }

            matches.push(Match {
                text: m.text().to_string(),
                start: m.range().start,
                end: m.range().end,
                captures,
            });
        }
    }

    Ok(matches)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scan_python() {
        let content = r#"
def hello(name: str) -> str:
    '''Greet someone.'''
    return f"Hello, {name}!"

def goodbye():
    pass
"#;

        let funcs = scan(content, "def $NAME", Lang::Python).unwrap();
        assert_eq!(funcs.len(), 2);

        let hello = &funcs[0];
        assert!(hello.captures.iter().any(|(n, v)| n == "NAME" && v == "hello"));
    }

    #[test]
    fn test_extract() {
        let content = "def hello(name: str): pass";
        let name = extract(content, "def $NAME($ARGS)", "NAME", Lang::Python);
        assert_eq!(name, Some("hello".to_string()));
    }
}
