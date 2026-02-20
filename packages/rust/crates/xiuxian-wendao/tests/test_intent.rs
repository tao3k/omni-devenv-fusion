//! Tests for the lightweight query intent extractor.

use xiuxian_wendao::extract_intent;

#[test]
fn test_search_intent() {
    let intent = extract_intent("search for knowledge about rust");
    assert_eq!(intent.action.as_deref(), Some("search"));
    assert_eq!(intent.target.as_deref(), Some("knowledge"));
    assert!(intent.keywords.contains(&"rust".to_string()));
    assert!(intent.context.contains(&"rust".to_string()));
}

#[test]
fn test_git_commit_intent() {
    let intent = extract_intent("commit my changes");
    assert_eq!(intent.action.as_deref(), Some("commit"));
    // "commit" as action implies "git" target
    assert_eq!(intent.target.as_deref(), Some("git"));
    assert!(intent.keywords.contains(&"changes".to_string()));
}

#[test]
fn test_create_file_intent() {
    let intent = extract_intent("create a new python file");
    assert_eq!(intent.action.as_deref(), Some("create"));
    assert_eq!(intent.target.as_deref(), Some("code"));
    assert!(intent.keywords.contains(&"python".to_string()));
}

#[test]
fn test_research_web_intent() {
    let intent = extract_intent("research about LanceDB on the web");
    assert_eq!(intent.action.as_deref(), Some("research"));
    assert_eq!(intent.target.as_deref(), Some("web"));
    assert!(intent.keywords.contains(&"lancedb".to_string()));
}

#[test]
fn test_find_tool_intent() {
    let intent = extract_intent("find the right tool for code analysis");
    assert_eq!(intent.action.as_deref(), Some("search"));
    assert_eq!(intent.target.as_deref(), Some("skill"));
    assert!(intent.keywords.contains(&"analysis".to_string()));
}

#[test]
fn test_empty_query() {
    let intent = extract_intent("");
    assert!(intent.action.is_none());
    assert!(intent.target.is_none());
    assert!(intent.keywords.is_empty());
    assert!(intent.normalized_query.is_empty());
}

#[test]
fn test_pure_action_git_implies_target() {
    let intent = extract_intent("push to remote");
    assert_eq!(intent.action.as_deref(), Some("push"));
    // push implies git target
    assert_eq!(intent.target.as_deref(), Some("git"));
}

#[test]
fn test_dotted_command_tokenization() {
    let intent = extract_intent("run git.smart_commit");
    assert_eq!(intent.action.as_deref(), Some("run"));
    assert_eq!(intent.target.as_deref(), Some("git"));
    // "smart" and "commit" should be extracted as tokens
    assert!(
        intent.keywords.contains(&"smart".to_string()),
        "Keywords should contain 'smart', got: {:?}",
        intent.keywords
    );
    assert!(
        intent.keywords.contains(&"commit".to_string()),
        "Keywords should contain 'commit', got: {:?}",
        intent.keywords
    );
}

#[test]
fn test_stop_words_filtered() {
    let intent = extract_intent("please help me find the files in this project");
    assert_eq!(intent.action.as_deref(), Some("search"));
    // Stop words like "please", "help", "me", "the", "in", "this" should be filtered
    assert!(!intent.keywords.contains(&"the".to_string()));
    assert!(!intent.keywords.contains(&"please".to_string()));
    assert!(!intent.keywords.contains(&"in".to_string()));
    assert!(intent.keywords.contains(&"files".to_string()));
    assert!(intent.keywords.contains(&"project".to_string()));
}

#[test]
fn test_keywords_extraction() {
    let intent = extract_intent("analyze the codebase for async patterns");
    assert_eq!(intent.action.as_deref(), Some("analyze"));
    assert_eq!(intent.target.as_deref(), Some("code"));
    assert!(intent.keywords.contains(&"async".to_string()));
    assert!(intent.keywords.contains(&"patterns".to_string()));
    // "async" and "patterns" should be in context (not action/target words)
    assert!(intent.context.contains(&"async".to_string()));
    assert!(intent.context.contains(&"patterns".to_string()));
}

#[test]
fn test_index_command() {
    let intent = extract_intent("reindex the database");
    assert_eq!(intent.action.as_deref(), Some("index"));
    assert_eq!(intent.target.as_deref(), Some("database"));
}

#[test]
fn test_list_skills() {
    let intent = extract_intent("list all available skills");
    assert_eq!(intent.action.as_deref(), Some("list"));
    assert_eq!(intent.target.as_deref(), Some("skill"));
}

#[test]
fn test_crawl_implies_web() {
    let intent = extract_intent("crawl this page for me");
    assert_eq!(intent.action.as_deref(), Some("crawl"));
    // "page" maps to "web" target
    assert_eq!(intent.target.as_deref(), Some("web"));
}

#[test]
fn test_crawl_docs_targets_docs() {
    let intent = extract_intent("crawl the documentation page");
    assert_eq!(intent.action.as_deref(), Some("crawl"));
    // "documentation" appears first, maps to "docs"
    assert_eq!(intent.target.as_deref(), Some("docs"));
}
