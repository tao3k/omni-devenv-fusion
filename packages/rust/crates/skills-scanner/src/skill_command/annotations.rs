//! Tool annotations builder.
//!
//! Provides heuristics for inferring tool annotations (read_only, destructive, etc.)
//! from function naming patterns.

use crate::skill_metadata::{DecoratorArgs, ToolAnnotations};

/// Build ToolAnnotations from decorator args and naming heuristics.
#[must_use]
pub fn build_annotations(
    args: &DecoratorArgs,
    func_name: &str,
    _parameters: &[String],
) -> ToolAnnotations {
    // Start with defaults
    let mut annotations = ToolAnnotations::default();

    // Override with explicit decorator values
    if let Some(read_only) = args.read_only {
        annotations.read_only = read_only;
        // If explicitly set to read-only, also set idempotent
        if read_only {
            annotations.idempotent = true;
        }
    }
    if let Some(destructive) = args.destructive {
        annotations.destructive = destructive;
        // If explicitly set to destructive, clear idempotent
        if destructive {
            annotations.idempotent = false;
        }
    }

    // Heuristics: infer from naming patterns if not explicitly set
    let name_lower = func_name.to_lowercase();

    // Read-only heuristics (only if not explicitly set)
    // Check args.read_only.is_none() to skip heuristic if decorator explicitly set it
    if args.read_only.is_none() {
        let read_indicators = [
            "get", "fetch", "read", "query", "list", "show", "display", "view", "check",
            "validate", "exists", "find", "search", "lookup", "describe",
        ];
        if read_indicators.iter().any(|i| name_lower.starts_with(i)) {
            annotations.read_only = true;
            annotations.idempotent = true;
        }
    }

    // Destructive heuristics (only if not explicitly set)
    // Check args.destructive.is_none() to skip heuristic if decorator explicitly set it
    if args.destructive.is_none() {
        let destructive_indicators = [
            "delete",
            "remove",
            "destroy",
            "drop",
            "truncate",
            "clear",
            "reset",
            "overwrite",
            "write",
            "create",
            "add",
            "insert",
            "update",
            "modify",
            "edit",
            "save",
            "commit",
            "push",
            "deploy",
        ];
        if destructive_indicators
            .iter()
            .any(|i| name_lower.starts_with(i))
        {
            annotations.destructive = true;
            annotations.idempotent = false;
        }
    }

    // Open world heuristics (network operations)
    if name_lower.contains("fetch")
        || name_lower.contains("http")
        || name_lower.contains("request")
        || name_lower.contains("api")
        || name_lower.contains("url")
        || name_lower.contains("web")
        || name_lower.contains("network")
    {
        annotations.open_world = true;
    }

    // Adjust idempotent based on destructive
    if annotations.destructive {
        annotations.idempotent = false;
    }

    annotations
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::skill_metadata::DecoratorArgs;

    #[test]
    fn test_read_only_heuristic() {
        let args = DecoratorArgs::default();
        let ann = build_annotations(&args, "get_data", &[]);
        assert!(ann.read_only);
        assert!(ann.idempotent);
    }

    #[test]
    fn test_destructive_heuristic() {
        let args = DecoratorArgs::default();
        let ann = build_annotations(&args, "delete_file", &[]);
        assert!(ann.destructive);
        assert!(!ann.idempotent);
    }

    #[test]
    fn test_network_heuristic() {
        let args = DecoratorArgs::default();
        let ann = build_annotations(&args, "fetch_url", &[]);
        assert!(ann.open_world);
    }

    #[test]
    fn test_explicit_override() {
        let mut args = DecoratorArgs::default();
        args.read_only = Some(false);
        let ann = build_annotations(&args, "get_data", &[]);
        // Explicit override should take precedence over heuristic
        assert!(!ann.read_only);
    }
}
