//! Parse dependencies from Cargo.toml - Root workspace priority.

use std::fs::read_to_string;
use std::path::Path;

use lazy_static::lazy_static;
use regex::Regex;

lazy_static! {
    /// Regex for complex dependency format: name = { version = "x.y.z", features = [...] }
    static ref RE_DEP_COMPLEX: Regex =
        Regex::new(r#"(\w+)\s*=\s*\{[^}]*version\s*=\s*"([^"]+)""#).unwrap();

    /// Regex for simple dependency format: name = "version"
    static ref RE_DEP_SIMPLE: Regex = Regex::new(r#"^(\w+)\s*=\s*"([^"]+)""#).unwrap();
}

/// A parsed dependency.
#[derive(Debug, Clone)]
pub struct CargoDependency {
    /// Dependency crate name.
    pub name: String,
    /// Resolved dependency version requirement.
    pub version: String,
}

impl CargoDependency {
    /// Create a new parsed dependency record.
    pub fn new(name: String, version: String) -> Self {
        Self { name, version }
    }
}

/// Parse dependencies from a Cargo.toml file.
/// Priority: If this is a workspace root, parse [workspace.dependencies].
/// Otherwise, parse [dependencies] section.
pub fn parse_cargo_dependencies(path: &Path) -> Result<Vec<CargoDependency>, std::io::Error> {
    let content = read_to_string(path)?;

    // Check if this is a workspace root by looking for [workspace] section
    let is_workspace =
        content.contains("[workspace]") || content.contains("[workspace.dependencies]");

    let deps = if is_workspace {
        // Parse [workspace.dependencies] for workspace roots
        parse_workspace_dependencies(&content)
    } else {
        // Parse regular [dependencies] section
        parse_regular_dependencies(&content)
    };

    Ok(deps)
}

/// Parse [workspace.dependencies] section.
fn parse_workspace_dependencies(content: &str) -> Vec<CargoDependency> {
    let mut deps = Vec::new();

    // Find [workspace.dependencies] section
    let section_start = match content.find("[workspace.dependencies]") {
        Some(pos) => pos,
        None => {
            // Try [dependencies] in workspace root
            return parse_regular_dependencies(content);
        }
    };

    // Find end of section
    let section_content = &content[section_start..];
    let mut depth = 0;
    let mut in_content = false;
    let mut section_end = section_content.len();

    for (i, c) in section_content.char_indices() {
        if !in_content {
            if c == '\n' {
                in_content = true;
            }
            continue;
        }

        if c == '{' {
            depth += 1;
        } else if c == '}' {
            if depth > 0 {
                depth -= 1;
            }
        } else if c == '[' && depth == 0 {
            section_end = i;
            break;
        } else if c == '\0' {
            section_end = i;
            break;
        }
    }

    let dep_content = &section_content[..section_end];

    for line in dep_content.lines() {
        let trimmed = line.trim();

        if trimmed.is_empty() || trimmed.starts_with('[') || trimmed.starts_with('#') {
            continue;
        }

        // Try complex format first: name = { version = "..." }
        if let Some(cap) = RE_DEP_COMPLEX.captures(trimmed) {
            let name = cap[1].to_string();
            let version = cap[2].to_string();
            deps.push(CargoDependency::new(name, version));
        }
        // Try simple format: name = "version"
        else if let Some(cap) = RE_DEP_SIMPLE.captures(trimmed) {
            let name = cap[1].to_string();
            let version = cap[2].to_string();
            deps.push(CargoDependency::new(name, version));
        }
    }

    deps
}

/// Parse regular [dependencies] section.
fn parse_regular_dependencies(content: &str) -> Vec<CargoDependency> {
    let mut deps = Vec::new();

    let dep_section = content.find("[dependencies]");
    if dep_section.is_none() {
        return deps;
    }

    let section_start = dep_section.unwrap();
    let section_content = &content[section_start..];

    let mut depth = 0;
    let mut in_content = false;
    let mut section_end = section_content.len();

    for (i, c) in section_content.char_indices() {
        if !in_content {
            if c == '\n' {
                in_content = true;
            }
            continue;
        }

        if c == '{' {
            depth += 1;
        } else if c == '}' {
            if depth > 0 {
                depth -= 1;
            }
        } else if c == '[' && depth == 0 {
            section_end = i;
            break;
        } else if c == '\0' {
            section_end = i;
            break;
        }
    }

    let dep_content = &section_content[..section_end];

    for line in dep_content.lines() {
        let trimmed = line.trim();

        if trimmed.is_empty() || trimmed.starts_with('[') || trimmed.starts_with('#') {
            continue;
        }

        // Try complex format first: name = { version = "..." }
        if let Some(cap) = RE_DEP_COMPLEX.captures(trimmed) {
            let name = cap[1].to_string();
            let version = cap[2].to_string();
            deps.push(CargoDependency::new(name, version));
        }
        // Try simple format: name = "version"
        else if let Some(cap) = RE_DEP_SIMPLE.captures(trimmed) {
            let name = cap[1].to_string();
            let version = cap[2].to_string();

            // Skip path/git dependencies
            if version.starts_with("path") || version.starts_with("git") {
                continue;
            }

            deps.push(CargoDependency::new(name, version));
        }
    }

    deps
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write as StdWrite;
    use tempfile::NamedTempFile;

    #[tokio::test]
    async fn test_parse_workspace_dependencies() {
        let content = r#"
[workspace]
members = ["crates/*"]

[workspace.dependencies]
tokio = { version = "1.49.0", features = ["full"] }
serde = { version = "1.0.228", features = ["derive"] }
serde_json = "1.0.149"
anyhow = "1.0.100"
thiserror = "2.0.17"
"#;

        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        let path = file.path().to_path_buf();

        let deps = parse_cargo_dependencies(&path).unwrap();

        assert!(deps.iter().any(|d| d.name == "tokio"), "tokio not found");
        assert!(deps.iter().any(|d| d.name == "serde"), "serde not found");
        assert!(deps.iter().any(|d| d.name == "anyhow"), "anyhow not found");
        assert_eq!(
            deps.iter().find(|d| d.name == "serde").unwrap().version,
            "1.0.228"
        );
    }

    #[tokio::test]
    async fn test_parse_regular_dependencies() {
        let content = r#"
[package]
name = "test"
version = "0.1.0"

[dependencies]
serde = "1.0"
anyhow = "1.0"
thiserror = "1.0"
"#;

        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        let path = file.path().to_path_buf();

        let deps = parse_cargo_dependencies(&path).unwrap();

        assert!(deps.iter().any(|d| d.name == "serde"), "serde not found");
        assert!(deps.iter().any(|d| d.name == "anyhow"), "anyhow not found");
    }
}
