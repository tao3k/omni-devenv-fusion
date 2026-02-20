//! Dependency Config - Load external dependency settings from references.yaml.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// External dependency configuration (renamed to avoid conflict).
#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(
    from = "ConfigExternalDependencyHelper",
    into = "ConfigExternalDependencyHelper"
)]
pub struct ConfigExternalDependency {
    /// Package type: "rust" or "python"
    pub pkg_type: String,
    /// Registry type: "cargo" or "pip"
    pub registry: Option<String>,
    /// List of manifest file patterns
    pub manifests: Vec<String>,
}

#[derive(Deserialize, Serialize)]
struct ConfigExternalDependencyHelper {
    #[serde(rename = "type")]
    pkg_type: String,
    registry: Option<String>,
    manifests: Vec<String>,
}

impl From<ConfigExternalDependencyHelper> for ConfigExternalDependency {
    fn from(helper: ConfigExternalDependencyHelper) -> Self {
        Self {
            pkg_type: helper.pkg_type,
            registry: helper.registry,
            manifests: helper.manifests,
        }
    }
}

impl From<ConfigExternalDependency> for ConfigExternalDependencyHelper {
    fn from(dep: ConfigExternalDependency) -> Self {
        Self {
            pkg_type: dep.pkg_type,
            registry: dep.registry,
            manifests: dep.manifests,
        }
    }
}

/// Dependency configuration loaded from references.yaml.
#[derive(Debug, Clone, Default)]
pub struct DependencyConfig {
    /// List of external dependency configurations
    pub manifests: Vec<ConfigExternalDependency>,
}

impl DependencyConfig {
    /// Load configuration from YAML file.
    #[must_use]
    pub fn load(path: &str) -> Self {
        let path = if let Some(stripped) = path.strip_prefix('~') {
            if let Some(home) = dirs::home_dir() {
                home.join(stripped.trim_start_matches('/'))
            } else {
                PathBuf::from(path)
            }
        } else {
            PathBuf::from(path)
        };

        if !path.exists() {
            log::warn!("Config file not found: {}", path.display());
            return Self::default();
        }

        match std::fs::read_to_string(&path) {
            Ok(content) => {
                // Parse as YAML (not TOML - references.yaml is YAML format)
                let config: serde_yaml::Value = match serde_yaml::from_str(&content) {
                    Ok(v) => v,
                    Err(e) => {
                        log::warn!("Failed to parse config: {e}");
                        return Self::default();
                    }
                };

                // Parse ast_symbols_external section
                let manifests = if let Some(external) = config.get("ast_symbols_external") {
                    let mut list = Vec::new();
                    if let Some(arr) = external.as_sequence() {
                        for item in arr {
                            if let Some(table) = item.as_mapping() {
                                let pkg_type = table
                                    .get("type")
                                    .and_then(|v| v.as_str())
                                    .map(std::string::ToString::to_string)
                                    .unwrap_or_default();

                                let registry = table
                                    .get("registry")
                                    .and_then(|v| v.as_str())
                                    .map(std::string::ToString::to_string);

                                let manifests: Vec<String> = table
                                    .get("manifests")
                                    .and_then(|v| v.as_sequence())
                                    .map(|arr| {
                                        arr.iter()
                                            .filter_map(|v| {
                                                v.as_str().map(std::string::ToString::to_string)
                                            })
                                            .collect()
                                    })
                                    .unwrap_or_default();

                                if !pkg_type.is_empty() && !manifests.is_empty() {
                                    list.push(ConfigExternalDependency {
                                        pkg_type,
                                        registry,
                                        manifests,
                                    });
                                }
                            }
                        }
                    }
                    list
                } else {
                    Vec::new()
                };

                Self { manifests }
            }
            Err(e) => {
                log::warn!("Failed to read config: {e}");
                Self::default()
            }
        }
    }
}
