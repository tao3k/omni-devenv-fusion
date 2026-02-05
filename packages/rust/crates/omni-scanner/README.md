# Skills Scanner

> Rust crate for skill discovery, metadata parsing, and tool scanning.

## Overview

The Skills Scanner provides comprehensive skill discovery and metadata extraction for the Omni-Dev-Fusion system. It scans skill directories, parses YAML frontmatter from SKILL.md files, discovers tools from script annotations, and generates the `skill_index.json` for semantic routing.

## Features

### 1. Skill Discovery

Scan skill directories and discover all available skills:

```rust
use skills_scanner::SkillScanner;

let scanner = SkillScanner::new();
let skills = scanner.scan_all("/path/to/skills").await?;
```

### 2. Metadata Parsing

Parse YAML frontmatter from SKILL.md files:

```rust
use skills_scanner::SkillMetadata;

let metadata = SkillMetadata::parse_frontmatter(content)?;
println!("Skill: {}", metadata.skill_name);
println!("Version: {}", metadata.version);
println!("Keywords: {:?}", metadata.routing_keywords);
```

### 3. Tool Discovery

Automatically discover tools from script annotations:

```rust
use skills_scanner::ScriptScanner;

let scanner = ScriptScanner::new();
let tools = scanner.scan_script("def git_commit():")?;
```

### 4. JSON Schema Generation

Generate JSON Schema for `skill_index.json` validation:

```rust
use skills_scanner::skill_index_schema;

let schema = skill_index_schema();
println!("{}", schema);
```

## Architecture

```
skills-scanner/
├── lib.rs              # Main entry point and exports
├── skill_metadata.rs   # SkillMetadata and related types
├── skill_scanner.rs    # Full skill scanning and index generation
├── script_scanner.rs   # Script annotation parsing
├── document_scanner.rs # Directory structure scanning
├── reference_path.rs   # ReferencePath validation
├── skill_structure.rs  # SkillStructure definition
└── records.rs          # Record types (ToolRecord, etc.)
```

## Data Structures

### SkillMetadata

Parsed metadata from SKILL.md frontmatter:

```rust
#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema)]
pub struct SkillMetadata {
    pub skill_name: String,
    pub version: String,
    pub description: String,
    pub routing_keywords: Vec<String>,
    pub authors: Vec<String>,
    pub intents: Vec<String>,
    pub require_refs: Vec<ReferencePath>,
}
```

### SkillIndexEntry

Complete skill entry for skill_index.json:

```rust
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct SkillIndexEntry {
    pub name: String,
    pub description: String,
    pub version: String,
    pub path: String,
    pub tools: Vec<IndexToolEntry>,
    pub routing_keywords: Vec<String>,
    pub intents: Vec<String>,
    pub authors: Vec<String>,
    pub docs_available: DocsAvailable,
    pub oss_compliant: Vec<String>,
    pub compliance_details: Vec<String>,
    pub require_refs: Vec<ReferencePath>,
}
```

### ReferencePath

Validated reference path with security checks:

```rust
use skills_scanner::ReferencePath;

let path = ReferencePath::new("docs/api-reference.md")?;
assert!(path.is_valid());
```

Validation rules:

- Not empty
- No absolute paths
- No path traversal (`..`)
- Valid extension (`.md`, `.pdf`, `.txt`, etc.)

## Python Integration

The scanner is exposed to Python via PyO3 bindings:

```python
from omni_core_rs import export_skill_index, scan_skill_tools, get_skill_index_schema

# Export full skill index
index_json = export_skill_index("assets/skills", "assets/skills/skill_index.json")

# Get JSON Schema for validation
schema = get_skill_index_schema()
```

## Example: Full Scan

```rust
use skills_scanner::{SkillScanner, ScriptScanner};
use std::path::Path;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let skill_scanner = SkillScanner::new();
    let script_scanner = ScriptScanner::new();
    let skills_path = Path::new("assets/skills");
    let output_path = Path::new("assets/skills/skill_index.json");

    skill_scanner
        .scan_all_full_to_index(skills_path, output_path, None, &script_scanner)
        .await?;

    println!("Skill index generated at: {}", output_path.display());
    Ok(())
}
```

## Version

Current version: 0.1.0

## License

Apache-2.0
