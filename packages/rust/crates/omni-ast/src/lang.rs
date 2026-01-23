//! Language support for AST analysis.
//!
//! Provides a unified `Lang` enum supporting 23 programming languages
//! with automatic detection from file extensions.

use std::path::Path;

use anyhow::{Result, bail};

/// Supported languages for AST analysis
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Lang {
    /// Python
    Python,
    /// Rust
    Rust,
    /// JavaScript
    JavaScript,
    /// TypeScript
    TypeScript,
    /// Bash
    Bash,
    /// Go
    Go,
    /// Java
    Java,
    /// C
    C,
    /// C++
    Cpp,
    /// C#
    CSharp,
    /// Ruby
    Ruby,
    /// Swift
    Swift,
    /// Kotlin
    Kotlin,
    /// Lua
    Lua,
    /// PHP
    Php,
    /// JSON
    Json,
    /// YAML
    Yaml,
    /// TOML
    Toml,
    /// Markdown
    Markdown,
    /// Dockerfile
    Dockerfile,
    /// HTML
    Html,
    /// CSS
    Css,
    /// SQL
    Sql,
}

impl Lang {
    /// Get the ast-grep language string
    #[must_use]
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Python => "py",
            Self::Rust => "rust",
            Self::JavaScript => "js",
            Self::TypeScript => "ts",
            Self::Bash => "bash",
            Self::Go => "go",
            Self::Java => "java",
            Self::C => "c",
            Self::Cpp => "cpp",
            Self::CSharp => "csharp",
            Self::Ruby => "ruby",
            Self::Swift => "swift",
            Self::Kotlin => "kotlin",
            Self::Lua => "lua",
            Self::Php => "php",
            Self::Json => "json",
            Self::Yaml => "yaml",
            Self::Toml => "toml",
            Self::Markdown => "markdown",
            Self::Dockerfile => "dockerfile",
            Self::Html => "html",
            Self::Css => "css",
            Self::Sql => "sql",
        }
    }

    /// Try to detect language from file extension
    #[must_use]
    pub fn from_path(path: &Path) -> Option<Self> {
        let ext = path.extension()?.to_str()?.to_lowercase();
        Self::from_extension(&ext)
    }

    /// Try to detect language from extension string
    #[must_use]
    pub fn from_extension(ext: &str) -> Option<Self> {
        match ext {
            "py" => Some(Self::Python),
            "rs" => Some(Self::Rust),
            "js" | "mjs" => Some(Self::JavaScript),
            "ts" | "tsx" => Some(Self::TypeScript),
            "sh" | "bash" => Some(Self::Bash),
            "go" => Some(Self::Go),
            "java" => Some(Self::Java),
            "c" | "h" => Some(Self::C),
            "cpp" | "cc" | "cxx" | "hpp" => Some(Self::Cpp),
            "cs" => Some(Self::CSharp),
            "rb" => Some(Self::Ruby),
            "swift" => Some(Self::Swift),
            "kt" | "kts" => Some(Self::Kotlin),
            "lua" => Some(Self::Lua),
            "php" => Some(Self::Php),
            "json" => Some(Self::Json),
            "yaml" | "yml" => Some(Self::Yaml),
            "toml" => Some(Self::Toml),
            "md" => Some(Self::Markdown),
            "dockerfile" => Some(Self::Dockerfile),
            "html" | "htm" => Some(Self::Html),
            "css" => Some(Self::Css),
            "sql" => Some(Self::Sql),
            _ => None,
        }
    }

    /// Get file extensions for this language
    #[must_use]
    pub fn extensions(&self) -> Vec<&'static str> {
        match self {
            Self::Python => vec!["py"],
            Self::Rust => vec!["rs"],
            Self::JavaScript => vec!["js", "mjs"],
            Self::TypeScript => vec!["ts", "tsx"],
            Self::Bash => vec!["sh", "bash"],
            Self::Go => vec!["go"],
            Self::Java => vec!["java"],
            Self::C => vec!["c", "h"],
            Self::Cpp => vec!["cpp", "cc", "cxx", "hpp"],
            Self::CSharp => vec!["cs"],
            Self::Ruby => vec!["rb"],
            Self::Swift => vec!["swift"],
            Self::Kotlin => vec!["kt", "kts"],
            Self::Lua => vec!["lua"],
            Self::Php => vec!["php"],
            Self::Json => vec!["json"],
            Self::Yaml => vec!["yaml", "yml"],
            Self::Toml => vec!["toml"],
            Self::Markdown => vec!["md"],
            Self::Dockerfile => vec!["dockerfile"],
            Self::Html => vec!["html", "htm"],
            Self::Css => vec!["css"],
            Self::Sql => vec!["sql"],
        }
    }
}

impl TryFrom<&str> for Lang {
    type Error = anyhow::Error;

    fn try_from(s: &str) -> Result<Self> {
        match s.to_lowercase().as_str() {
            "py" | "python" => Ok(Self::Python),
            "rs" | "rust" => Ok(Self::Rust),
            "js" | "javascript" => Ok(Self::JavaScript),
            "ts" | "typescript" => Ok(Self::TypeScript),
            "bash" | "sh" => Ok(Self::Bash),
            "go" => Ok(Self::Go),
            "java" => Ok(Self::Java),
            "c" => Ok(Self::C),
            "cpp" | "c++" => Ok(Self::Cpp),
            "csharp" | "cs" => Ok(Self::CSharp),
            "rb" | "ruby" => Ok(Self::Ruby),
            "swift" => Ok(Self::Swift),
            "kt" | "kotlin" => Ok(Self::Kotlin),
            "lua" => Ok(Self::Lua),
            "php" => Ok(Self::Php),
            "json" => Ok(Self::Json),
            "yaml" | "yml" => Ok(Self::Yaml),
            "toml" => Ok(Self::Toml),
            "md" | "markdown" => Ok(Self::Markdown),
            "dockerfile" => Ok(Self::Dockerfile),
            "html" | "htm" => Ok(Self::Html),
            "css" => Ok(Self::Css),
            "sql" => Ok(Self::Sql),
            _ => bail!("Unsupported language: {}", s),
        }
    }
}
