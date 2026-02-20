//! Category inference for script scanners.
//!
//! Provides sensible default categories when not explicitly specified
//! in the @`skill_command` decorator.

/// Infer category from skill name using pattern matching.
///
/// Provides a sensible default category when not explicitly specified
/// in the @`skill_command` decorator.
///
/// # Arguments
///
/// * `skill_name` - Name of the skill (e.g., "git", "filesystem", "writer")
///
/// # Returns
///
/// Inferred category string based on skill name patterns.
#[must_use]
pub fn infer_category_from_skill(skill_name: &str) -> String {
    let name_lower = skill_name.to_lowercase();

    // Version control and git operations
    if name_lower.contains("git") || name_lower.contains("version") || name_lower.contains("commit")
    {
        return "version_control".to_string();
    }

    // File system operations
    if name_lower.contains("file") || name_lower.contains("fs") || name_lower.contains("path") {
        return "filesystem".to_string();
    }

    // Code and engineering tools
    if name_lower.contains("code")
        || name_lower.contains("engineering")
        || name_lower.contains("refactor")
        || name_lower.contains("debug")
    {
        return "engineering".to_string();
    }

    // Writing and documentation
    if name_lower.contains("writer")
        || name_lower.contains("write")
        || name_lower.contains("edit")
        || name_lower.contains("document")
    {
        return "writing".to_string();
    }

    // Search and data tools
    if name_lower.contains("search")
        || name_lower.contains("grep")
        || name_lower.contains("query")
        || name_lower.contains("find")
    {
        return "search".to_string();
    }

    // Testing and QA
    if name_lower.contains("test")
        || name_lower.contains("qa")
        || name_lower.contains("coverage")
        || name_lower.contains("lint")
    {
        return "testing".to_string();
    }

    // Database operations
    if name_lower.contains("data")
        || name_lower.contains("database")
        || name_lower.contains("db")
        || name_lower.contains("sql")
    {
        return "data".to_string();
    }

    // Shell and execution
    if name_lower.contains("shell")
        || name_lower.contains("exec")
        || name_lower.contains("run")
        || name_lower.contains("command")
    {
        return "shell".to_string();
    }

    // API and network
    if name_lower.contains("api")
        || name_lower.contains("http")
        || name_lower.contains("network")
        || name_lower.contains("web")
    {
        return "network".to_string();
    }

    // Default to skill name if no pattern matches
    skill_name.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_infer_category_git() {
        assert_eq!(infer_category_from_skill("git"), "version_control");
        assert_eq!(infer_category_from_skill("github"), "version_control");
        assert_eq!(
            infer_category_from_skill("version_control"),
            "version_control"
        );
    }

    #[test]
    fn test_infer_category_filesystem() {
        assert_eq!(infer_category_from_skill("filesystem"), "filesystem");
        assert_eq!(infer_category_from_skill("files"), "filesystem");
        assert_eq!(infer_category_from_skill("path_utils"), "filesystem");
    }

    #[test]
    fn test_infer_category_engineering() {
        assert_eq!(infer_category_from_skill("code"), "engineering");
        assert_eq!(infer_category_from_skill("engineering"), "engineering");
        assert_eq!(infer_category_from_skill("refactor"), "engineering");
    }

    #[test]
    fn test_infer_category_writing() {
        assert_eq!(infer_category_from_skill("writer"), "writing");
        assert_eq!(infer_category_from_skill("write"), "writing");
        assert_eq!(infer_category_from_skill("editor"), "writing");
    }

    #[test]
    fn test_infer_category_search() {
        assert_eq!(infer_category_from_skill("search"), "search");
        assert_eq!(infer_category_from_skill("grep"), "search");
        assert_eq!(infer_category_from_skill("find_utils"), "search");
    }

    #[test]
    fn test_infer_category_testing() {
        assert_eq!(infer_category_from_skill("test"), "testing");
        assert_eq!(infer_category_from_skill("qa"), "testing");
        assert_eq!(infer_category_from_skill("lint"), "testing");
    }

    #[test]
    fn test_infer_category_data() {
        assert_eq!(infer_category_from_skill("data"), "data");
        assert_eq!(infer_category_from_skill("database"), "data");
        assert_eq!(infer_category_from_skill("sql"), "data");
    }

    #[test]
    fn test_infer_category_shell() {
        assert_eq!(infer_category_from_skill("shell"), "shell");
        assert_eq!(infer_category_from_skill("exec"), "shell");
        assert_eq!(infer_category_from_skill("runner"), "shell");
    }

    #[test]
    fn test_infer_category_network() {
        assert_eq!(infer_category_from_skill("api"), "network");
        assert_eq!(infer_category_from_skill("http"), "network");
        assert_eq!(infer_category_from_skill("web"), "network");
    }

    #[test]
    fn test_infer_category_unknown() {
        // Unknown skill should return the skill name as default
        assert_eq!(infer_category_from_skill("unknown_skill"), "unknown_skill");
        assert_eq!(infer_category_from_skill("xyz123"), "xyz123");
    }
}
