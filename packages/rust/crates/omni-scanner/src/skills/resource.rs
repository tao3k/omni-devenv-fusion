//! Resource Scanner - Parses Python scripts for @`skill_resource` decorated functions.
//!
//! Uses `TreeSitterPythonParser` for robust decorator extraction.

use std::fs;
use std::path::Path;

use hex;
use omni_ast::{DecoratedFunction, TreeSitterPythonParser};
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

use crate::skills::metadata::ResourceRecord;

/// Scanner for @`skill_resource` decorated functions.
#[derive(Debug)]
pub struct ResourceScanner;

impl Default for ResourceScanner {
    fn default() -> Self {
        Self::new()
    }
}

impl ResourceScanner {
    /// Create a new resource scanner.
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    /// Scan a scripts directory for @`skill_resource` decorated functions.
    ///
    /// # Arguments
    ///
    /// * `scripts_dir` - Path to the scripts directory
    /// * `skill_name` - Name of the parent skill
    ///
    /// # Returns
    ///
    /// A vector of `ResourceRecord` objects.
    ///
    /// # Errors
    ///
    /// Returns an error when `skill_name` is empty.
    pub fn scan(
        &self,
        scripts_dir: &Path,
        skill_name: &str,
    ) -> Result<Vec<ResourceRecord>, Box<dyn std::error::Error>> {
        let _ = self;
        if skill_name.trim().is_empty() {
            return Err("skill_name cannot be empty".into());
        }
        let mut resources = Vec::new();

        if !scripts_dir.exists() {
            log::debug!("Scripts directory not found: {}", scripts_dir.display());
            return Ok(resources);
        }

        for entry in WalkDir::new(scripts_dir)
            .follow_links(true)
            .sort_by_file_name()
        {
            let entry = match entry {
                Ok(e) => e,
                Err(e) => {
                    log::warn!("Error walking directory {}: {e}", scripts_dir.display());
                    continue;
                }
            };

            let path = entry.path();
            if !entry.file_type().is_file() {
                continue;
            }

            // Only scan Python files, skip __init__.py
            if path.extension().map(|e| e.to_string_lossy()) != Some("py".into()) {
                continue;
            }
            if path
                .file_name()
                .is_some_and(|n| n.to_string_lossy().starts_with("__"))
            {
                continue;
            }

            match Self::scan_file(path, skill_name) {
                Ok(file_resources) => resources.extend(file_resources),
                Err(e) => log::warn!("Error scanning {}: {e}", path.display()),
            }
        }

        log::debug!(
            "ResourceScanner: Found {} @skill_resource functions in {}",
            resources.len(),
            scripts_dir.display()
        );

        Ok(resources)
    }

    /// Scan a single file for @`skill_resource` decorated functions.
    fn scan_file(
        path: &Path,
        skill_name: &str,
    ) -> Result<Vec<ResourceRecord>, Box<dyn std::error::Error>> {
        let content = fs::read_to_string(path)?;
        let file_hash = hex::encode(Sha256::digest(content.as_bytes()));

        let mut parser = TreeSitterPythonParser::new();
        let decorated_funcs: Vec<DecoratedFunction> =
            parser.find_decorated_functions(&content, "skill_resource");

        let mut resources = Vec::new();

        for func in &decorated_funcs {
            let decorator_args = func.decorator.as_ref().map(|d| &d.arguments);

            // Get resource name from decorator or function name
            let name = decorator_args
                .and_then(|a| a.name.clone())
                .unwrap_or_else(|| func.name.clone());

            // Get description from docstring or decorator
            let description = decorator_args
                .and_then(|a| a.description.clone())
                .or_else(|| {
                    if func.docstring.is_empty() {
                        None
                    } else {
                        Some(func.docstring.clone())
                    }
                })
                .unwrap_or_else(|| format!("Resource {skill_name}.{name}"));

            // Get resource_uri from decorator or generate default
            let resource_uri = decorator_args
                .and_then(|a| a.resource_uri.clone())
                .unwrap_or_else(|| format!("omni://skill/{skill_name}/{name}"));

            resources.push(ResourceRecord::new(
                name,
                description,
                resource_uri,
                "application/json".to_string(),
                skill_name.to_string(),
                path.to_string_lossy().to_string(),
                func.name.clone(),
                file_hash.clone(),
            ));
        }

        Ok(resources)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn test_scan_empty_dir() {
        let scanner = ResourceScanner::new();
        let resources = scanner.scan(Path::new("/nonexistent"), "test").unwrap();
        assert!(resources.is_empty());
    }

    #[test]
    fn test_scan_finds_skill_resource() {
        let scanner = ResourceScanner::new();
        let files = vec![(
            "/virtual/skill/scripts/resource.py".to_string(),
            r#"
@skill_resource(
    name="status",
    description="Get system status",
    resource_uri="omni://skill/test/status"
)
def status_resource():
    '''Returns system status.'''
    return {"status": "ok"}
"#
            .to_string(),
        )];

        let resources = scanner.scan_paths(&files, "test").unwrap();
        assert_eq!(resources.len(), 1);
        assert_eq!(resources[0].name, "status");
        assert_eq!(resources[0].resource_uri, "omni://skill/test/status");
    }

    #[test]
    fn test_scan_skips_non_resource() {
        let scanner = ResourceScanner::new();
        let files = vec![(
            "/virtual/skill/scripts/command.py".to_string(),
            r#"
@skill_command(name="do_something")
def do_something():
    pass
"#
            .to_string(),
        )];

        let resources = scanner.scan_paths(&files, "test").unwrap();
        assert!(resources.is_empty());
    }
}

impl ResourceScanner {
    /// Scan multiple files for @`skill_resource` decorated functions.
    ///
    /// Used for testing.
    ///
    /// # Errors
    ///
    /// Returns an error when `skill_name` is empty.
    pub fn scan_paths(
        &self,
        files: &[(String, String)],
        skill_name: &str,
    ) -> Result<Vec<ResourceRecord>, Box<dyn std::error::Error>> {
        let _ = self;
        if skill_name.trim().is_empty() {
            return Err("skill_name cannot be empty".into());
        }
        let mut all_resources = Vec::new();

        for (file_path, content) in files {
            let _path = Path::new(file_path);
            let file_hash = hex::encode(Sha256::digest(content.as_bytes()));

            let mut parser = TreeSitterPythonParser::new();
            let decorated_funcs: Vec<DecoratedFunction> =
                parser.find_decorated_functions(content, "skill_resource");

            for func in &decorated_funcs {
                let decorator_args = func.decorator.as_ref().map(|d| &d.arguments);

                let name = decorator_args
                    .and_then(|a| a.name.clone())
                    .unwrap_or_else(|| func.name.clone());

                let description = decorator_args
                    .and_then(|a| a.description.clone())
                    .or_else(|| {
                        if func.docstring.is_empty() {
                            None
                        } else {
                            Some(func.docstring.clone())
                        }
                    })
                    .unwrap_or_else(|| format!("Resource {skill_name}.{name}"));

                let resource_uri = decorator_args
                    .and_then(|a| a.resource_uri.clone())
                    .unwrap_or_else(|| format!("omni://skill/{skill_name}/{name}"));

                all_resources.push(ResourceRecord::new(
                    name,
                    description,
                    resource_uri,
                    "application/json".to_string(),
                    skill_name.to_string(),
                    file_path.clone(),
                    func.name.clone(),
                    file_hash.clone(),
                ));
            }
        }

        Ok(all_resources)
    }
}
