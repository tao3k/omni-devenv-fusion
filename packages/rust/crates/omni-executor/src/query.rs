//! Query Builder - Safe Nushell Command Construction
//!
//! Prevents injection attacks by using a builder pattern instead of string concatenation.
//! Automatically optimizes queries by composing efficient Nushell pipelines.

/// Action type for semantic classification.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum QueryAction {
    /// Read-only intent.
    Observe,
    /// Side-effect intent.
    Mutate,
}

/// Builder for constructing safe Nushell queries.
#[derive(Debug, Clone)]
pub struct QueryBuilder {
    source_command: String,
    source_args: Vec<String>,
    filters: Vec<String>,
    output_columns: Vec<String>,
    sort_column: Option<String>,
    sort_descending: bool,
    limit: Option<u32>,
    action_type: QueryAction,
}

impl Default for QueryBuilder {
    fn default() -> Self {
        Self::new("ls")
    }
}

impl QueryBuilder {
    /// Create a new builder with the specified source command.
    ///
    /// Common sources: `ls`, `ps`, `git status`, `date`
    #[must_use]
    pub fn new(source: &str) -> Self {
        Self {
            source_command: source.to_string(),
            source_args: vec![],
            filters: vec![],
            output_columns: vec![],
            sort_column: None,
            sort_descending: false,
            limit: None,
            action_type: QueryAction::Observe,
        }
    }

    /// Set the source path/argument (e.g., directory for `ls`).
    #[must_use]
    pub fn source(mut self, path: &str) -> Self {
        self.source_args.push(path.to_string());
        self
    }

    /// Add a where clause for filtering.
    ///
    /// # Safety
    /// The predicate is validated to prevent injection.
    #[must_use]
    pub fn where_clause(mut self, predicate: &str) -> Self {
        // Validate predicate doesn't contain dangerous patterns
        if Self::is_safe_predicate(predicate) {
            self.filters.push(format!("where {predicate}"));
        }
        self
    }

    /// Add a complex filter using a closure-like predicate.
    ///
    /// Wraps the predicate in a safe manner.
    #[must_use]
    pub fn where_closure(mut self, closure: &str) -> Self {
        // Wrap in braces for closures: `where { |row| $row.size > 1kb }`
        if Self::is_safe_predicate(closure) {
            self.filters.push(format!("where {{ |row| {closure} }}"));
        }
        self
    }

    /// Select specific columns for output.
    #[must_use]
    pub fn select(mut self, columns: &[&str]) -> Self {
        self.output_columns
            .extend(columns.iter().map(std::string::ToString::to_string));
        self
    }

    /// Sort by column (ascending).
    #[must_use]
    pub fn sort_by(mut self, column: &str) -> Self {
        self.sort_column = Some(column.to_string());
        self.sort_descending = false;
        self
    }

    /// Sort by column (descending).
    #[must_use]
    pub fn sort_by_desc(mut self, column: &str) -> Self {
        self.sort_column = Some(column.to_string());
        self.sort_descending = true;
        self
    }

    /// Limit results to n items.
    #[must_use]
    pub fn take(mut self, n: u32) -> Self {
        self.limit = Some(n);
        self
    }

    /// Set the action type (for safety validation).
    #[must_use]
    pub fn with_action_type(mut self, action: QueryAction) -> Self {
        self.action_type = action;
        self
    }

    /// Build the final Nushell command string.
    ///
    /// Automatically composes the pipeline with `| to json --raw` for structured output.
    #[must_use]
    pub fn build(self) -> String {
        let mut cmd = self.build_base();

        // 6. Force JSON output for structured data (observation mode)
        if self.action_type == QueryAction::Observe {
            cmd.push_str(" | to json --raw");
        }

        cmd
    }

    /// Build without JSON conversion (for further processing).
    #[must_use]
    pub fn build_raw(&self) -> String {
        self.build_base()
    }

    /// Get the action type (for decision making).
    #[must_use]
    pub fn get_action_type(&self) -> &QueryAction {
        &self.action_type
    }

    fn build_base(&self) -> String {
        let mut cmd = String::new();

        // 1. Source command with arguments
        cmd.push_str(&self.source_command);
        for arg in &self.source_args {
            cmd.push(' ');
            cmd.push_str(arg);
        }

        // 2. Add filters (where clauses)
        for filter in &self.filters {
            cmd.push_str(" | ");
            cmd.push_str(filter);
        }

        // 3. Add column selection
        if !self.output_columns.is_empty() {
            let cols = self.output_columns.join(" ");
            cmd.push_str(" | select ");
            cmd.push_str(&cols);
        }

        // 4. Add sorting
        if let Some(col) = &self.sort_column {
            cmd.push_str(" | sort-by ");
            cmd.push_str(col);
            if self.sort_descending {
                cmd.push_str(" --reverse");
            }
        }

        // 5. Add limit
        if let Some(n) = self.limit {
            cmd.push_str(" | first ");
            cmd.push_str(&n.to_string());
        }

        cmd
    }

    /// Check if a predicate is safe (no injection patterns).
    fn is_safe_predicate(predicate: &str) -> bool {
        let p = predicate.to_lowercase();

        // Block dangerous patterns
        let dangerous = [
            ";",  // Command separator
            "&&", // Command chain
            "||", // Or chain
            "`",  // Command substitution
            "$0", // Positional params
            "$1", "$args", "(|", // Pipeline in predicate (suspicious)
        ];

        for pattern in &dangerous {
            if p.contains(pattern) {
                return false;
            }
        }

        // Allow common Nushell operators
        let allowed_operators = [
            "==", "!=", ">", "<", ">=", "<=", "and", "or", "not", "=~", "!~",
        ];
        allowed_operators.iter().any(|op| p.contains(op))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_query() {
        let query = QueryBuilder::new("ls")
            .source("packages/python/core/**/*.py")
            .where_clause("size > 2kb")
            .select(&["name", "size"])
            .build();

        assert!(query.contains("ls packages/python/core/**/*.py"));
        assert!(query.contains("where size > 2kb"));
        assert!(query.contains("select name size"));
        assert!(query.contains("to json --raw"));
    }

    #[test]
    fn test_sort_and_limit() {
        let query = QueryBuilder::new("ls")
            .source(".")
            .sort_by_desc("size")
            .take(5)
            .build();

        assert!(query.contains("sort-by size --reverse"));
        assert!(query.contains("first 5"));
    }

    #[test]
    fn test_unsafe_predicate_rejected() {
        let query = QueryBuilder::new("ls")
            .where_clause("size > 1kb; rm -rf /")
            .build();

        // Filter should not be added
        assert!(!query.contains("where size > 1kb; rm -rf /"));
        assert!(query.contains("to json --raw")); // But JSON output should still be there
    }

    #[test]
    fn test_closure_query() {
        let query = QueryBuilder::new("ls")
            .where_closure("$row.size > 1kb")
            .build();

        assert!(query.contains("where { |row| $row.size > 1kb }"));
    }

    #[test]
    fn test_mutation_mode_no_json() {
        let query = QueryBuilder::new("save")
            .source("content.txt")
            .with_action_type(QueryAction::Mutate)
            .build();

        // Mutation should NOT force JSON
        assert!(!query.contains("to json"));
    }

    #[test]
    fn test_build_raw() {
        let query = QueryBuilder::new("ls")
            .source(".")
            .where_clause("size > 1kb")
            .build_raw();

        assert!(query.contains("ls ."));
        assert!(query.contains("where size > 1kb"));
        assert!(!query.contains("to json"));
    }
}
