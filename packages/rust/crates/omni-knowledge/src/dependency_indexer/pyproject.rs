//! Parse dependencies from pyproject.toml.

use std::fs::read_to_string;
use std::path::Path;

use lazy_static::lazy_static;
use regex::Regex;

lazy_static! {
    /// Regex for parsing dependency format: name[extras]==version (handles comma-separated versions)
    /// Supports: ==, >=, <=, <, >, ~= (PEP 440 compatible)
    static ref RE_DEP: Regex =
        Regex::new(r"([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?(?:==|~=|>=|<=|<|>|=)([^,\]\s]+)").unwrap();

    /// Regex for parsing exact dependency format: package==version
    static ref RE_EXACT_DEP: Regex =
        Regex::new(r"^([a-zA-Z0-9_-]+)(?:\[[^\]]+\])?==([0-9][^\s,\]]*)").unwrap();

    /// Regex for simple package name extraction
    static ref RE_SIMPLE: Regex = Regex::new(r"^([a-zA-Z0-9_-]+)").unwrap();
}

/// A parsed Python dependency.
#[derive(Debug, Clone)]
pub struct PyprojectDependency {
    /// Python package name.
    pub name: String,
    /// Optional parsed version constraint/value.
    pub version: Option<String>,
}

impl PyprojectDependency {
    /// Create a parsed pyproject dependency record.
    pub fn new(name: String, version: Option<String>) -> Self {
        Self { name, version }
    }
}

/// Parse dependencies from a pyproject.toml file.
pub fn parse_pyproject_dependencies(
    path: &Path,
) -> Result<Vec<PyprojectDependency>, std::io::Error> {
    let content = read_to_string(path)?;

    let mut deps = Vec::new();

    // Try toml parsing first
    if let Ok(toml) = content.parse::<toml::Value>() {
        if let Some(dependencies) = toml.get("project").and_then(|p| p.get("dependencies")) {
            if let Some(dep_array) = dependencies.as_array() {
                for dep in dep_array {
                    if let Some(dep_str) = dep.as_str() {
                        // Parse format: name[extras]==version
                        if let Some((name, version)) = parse_pyproject_dep(dep_str) {
                            deps.push(PyprojectDependency::new(name, Some(version)));
                        }
                    }
                }
            }
        }
    } else {
        // Fallback to regex parsing
        for cap in RE_DEP.captures_iter(&content) {
            let name = cap[1].to_string();
            let version = cap[2].trim().to_string();
            deps.push(PyprojectDependency::new(name, Some(version)));
        }
    }

    Ok(deps)
}

fn parse_pyproject_dep(dep: &str) -> Option<(String, String)> {
    // Format: "package==1.0.0" or "package[extra]==1.0.0"
    if let Some(cap) = RE_EXACT_DEP.captures(dep) {
        Some((cap[1].to_string(), cap[2].to_string()))
    } else {
        // Try without version constraint
        if let Some(cap) = RE_SIMPLE.captures(dep) {
            Some((cap[1].to_string(), "latest".to_string()))
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write as StdWrite;
    use tempfile::NamedTempFile;

    #[tokio::test]
    async fn test_parse_pyproject_dependencies() {
        let content = r#"
[project]
name = "test"
version = "0.1.0"
dependencies = [
    "requests>=2.0",
    "click>=8.0",
    "rich>=13.0",
]
"#;

        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        let path = file.path().to_path_buf();

        let deps = parse_pyproject_dependencies(&path).unwrap();

        assert!(deps.iter().any(|d| d.name == "requests"));
        assert!(deps.iter().any(|d| d.name == "click"));
        assert!(deps.iter().any(|d| d.name == "rich"));
    }
}
