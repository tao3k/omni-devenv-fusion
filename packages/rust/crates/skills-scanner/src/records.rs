//! Record Types - Discovered items from skill directory scanning.
//!
//! This module contains record types for various items discovered during
//! skill directory scanning:
//! - `ToolRecord` - Functions with @skill_command decorator
//! - `TemplateRecord` - Jinja2 templates
//! - `ReferenceRecord` - Markdown documentation (for RAG)
//! - `AssetRecord` - Static resources
//! - `DataRecord` - Data files
//! - `TestRecord` - Test files

use serde::{Deserialize, Serialize};

// =============================================================================
// Tool Record - Functions with @skill_command decorator
// =============================================================================

/// A discovered tool from script scanning.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ToolRecord {
    /// Full tool name (e.g., "git.commit")
    pub tool_name: String,
    /// Human-readable description
    pub description: String,
    /// Parent skill name (e.g., "git")
    pub skill_name: String,
    /// Physical file path (e.g., "assets/skills/git/scripts/commit.py")
    pub file_path: String,
    /// Function name in the Python file
    pub function_name: String,
    /// Execution mode (e.g., "script", "library")
    pub execution_mode: String,
    /// Keywords for vector search (includes skill routing_keywords)
    pub keywords: Vec<String>,
    /// SHA256 hash of file content (for incremental indexing)
    pub file_hash: String,
    /// JSON schema for tool parameters
    #[serde(default)]
    pub input_schema: String,
    /// Raw docstring content
    #[serde(default)]
    pub docstring: String,
}

impl ToolRecord {
    /// Create a new tool record.
    #[must_use]
    pub fn new(
        tool_name: String,
        description: String,
        skill_name: String,
        file_path: String,
        function_name: String,
    ) -> Self {
        Self {
            tool_name,
            description,
            skill_name,
            file_path,
            function_name,
            execution_mode: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
            input_schema: String::new(),
            docstring: String::new(),
        }
    }
}

// =============================================================================
// Template Record - Jinja2 templates
// =============================================================================

/// A discovered template from templates/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct TemplateRecord {
    /// Template name relative to skill (e.g., "git/commit_message.j2")
    pub template_name: String,
    /// Human-readable description
    pub description: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Template variables extracted from the file
    pub variables: Vec<String>,
    /// Template content preview (first 500 chars)
    pub content_preview: String,
    /// Keywords for search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl TemplateRecord {
    /// Create a new template record.
    #[must_use]
    pub fn new(
        template_name: String,
        description: String,
        skill_name: String,
        file_path: String,
        variables: Vec<String>,
    ) -> Self {
        Self {
            template_name,
            description,
            skill_name,
            file_path,
            variables,
            content_preview: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Reference Record - Markdown documentation (for RAG)
// =============================================================================

/// A discovered reference document from references/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct ReferenceRecord {
    /// Reference name relative to skill (e.g., "git/smart-commit-workflow.md")
    pub ref_name: String,
    /// Title extracted from markdown (first H1 or filename)
    pub title: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Content preview (first 500 chars)
    pub content_preview: String,
    /// Keywords extracted from headings and content
    pub keywords: Vec<String>,
    /// Section headings found in the document
    pub sections: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl ReferenceRecord {
    /// Create a new reference record.
    #[must_use]
    pub fn new(ref_name: String, title: String, skill_name: String, file_path: String) -> Self {
        Self {
            ref_name,
            title,
            skill_name,
            file_path,
            content_preview: String::new(),
            keywords: Vec::new(),
            sections: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Asset Record - Static resources (guides, docs)
// =============================================================================

/// A discovered asset from assets/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct AssetRecord {
    /// Asset name relative to skill (e.g., "git/Backlog.md")
    pub asset_name: String,
    /// Title extracted from content
    pub title: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Content preview
    pub content_preview: String,
    /// Keywords for search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl AssetRecord {
    /// Create a new asset record.
    #[must_use]
    pub fn new(asset_name: String, title: String, skill_name: String, file_path: String) -> Self {
        Self {
            asset_name,
            title,
            skill_name,
            file_path,
            content_preview: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Data Record - Data files (JSON, CSV, etc.)
// =============================================================================

/// A discovered data file from data/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct DataRecord {
    /// Data file name relative to skill (e.g., "git/config.json")
    pub data_name: String,
    /// Data format (json, csv, yaml, etc.)
    pub format: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Top-level keys/fields in the data
    pub fields: Vec<String>,
    /// Content preview
    pub content_preview: String,
    /// Keywords for search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl DataRecord {
    /// Create a new data record.
    #[must_use]
    pub fn new(
        data_name: String,
        format: String,
        skill_name: String,
        file_path: String,
        fields: Vec<String>,
    ) -> Self {
        Self {
            data_name,
            format,
            skill_name,
            file_path,
            fields,
            content_preview: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Test Record - Test files
// =============================================================================

/// A discovered test file from tests/ directory.
#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct TestRecord {
    /// Test name relative to skill (e.g., "git/test_git_commands.py")
    pub test_name: String,
    /// Parent skill name
    pub skill_name: String,
    /// Physical file path
    pub file_path: String,
    /// Test function names found
    pub test_functions: Vec<String>,
    /// Test class names found
    pub test_classes: Vec<String>,
    /// Docstring content
    pub docstring: String,
    /// Keywords for search
    pub keywords: Vec<String>,
    /// SHA256 hash of file content
    pub file_hash: String,
}

impl TestRecord {
    /// Create a new test record.
    #[must_use]
    pub fn new(
        test_name: String,
        skill_name: String,
        file_path: String,
        test_functions: Vec<String>,
        test_classes: Vec<String>,
    ) -> Self {
        Self {
            test_name,
            skill_name,
            file_path,
            test_functions,
            test_classes,
            docstring: String::new(),
            keywords: Vec::new(),
            file_hash: String::new(),
        }
    }
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tool_record_new() {
        let record = ToolRecord::new(
            "writer.write_text".to_string(),
            "Write text to file".to_string(),
            "writer".to_string(),
            "/path/to/scripts/text.py".to_string(),
            "write_text".to_string(),
        );

        assert_eq!(record.tool_name, "writer.write_text");
        assert_eq!(record.skill_name, "writer");
        assert_eq!(record.function_name, "write_text");
    }
}
