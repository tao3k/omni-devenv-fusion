//! Dependency Indexer - Index external Rust crate dependencies for API lookup.

mod cargo;
mod config;
mod indexer;
mod pyproject;
mod symbols;

pub use cargo::{CargoDependency, parse_cargo_dependencies};
pub use config::{ConfigExternalDependency, DependencyConfig as DependencyBuildConfig};
pub use indexer::{DependencyConfig, DependencyIndexResult, DependencyIndexer, DependencyStats};
pub use pyproject::{PyprojectDependency, parse_pyproject_dependencies};
pub use symbols::{ExternalSymbol, SymbolIndex, SymbolKind, extract_symbols};
