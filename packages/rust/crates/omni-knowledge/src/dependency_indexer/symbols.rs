//! Extract symbols from Rust/Python source files using omni-tags.

use std::io::Write;
use std::path::PathBuf;

use lazy_static::lazy_static;

/// A single extracted symbol.
#[derive(Debug, Clone)]
pub struct ExternalSymbol {
    /// Symbol identifier.
    pub name: String,
    /// Symbol classification.
    pub kind: SymbolKind,
    /// File path containing this symbol.
    pub file: PathBuf,
    /// 1-based source line.
    pub line: usize,
    /// Source crate/package name.
    pub crate_name: String,
}

impl ExternalSymbol {
    /// Create a new ExternalSymbol.
    pub fn new(name: &str, kind: SymbolKind, file: &str, line: usize, crate_name: &str) -> Self {
        Self {
            name: name.to_string(),
            kind,
            file: PathBuf::from(file),
            line,
            crate_name: crate_name.to_string(),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
/// Supported symbol kinds extracted from source files.
pub enum SymbolKind {
    /// `struct` declaration.
    Struct,
    /// `enum` declaration.
    Enum,
    /// `trait` declaration.
    Trait,
    /// Free function declaration.
    Function,
    /// Method declaration.
    Method,
    /// Field declaration.
    Field,
    /// `impl` block.
    Impl,
    /// `mod` declaration.
    Mod,
    /// `const` declaration.
    Const,
    /// `static` declaration.
    Static,
    /// `type` alias.
    TypeAlias,
    /// Fallback for unknown syntax.
    Unknown,
}

/// Symbol index for fast lookup.
#[derive(Debug, Default, Clone)]
pub struct SymbolIndex {
    /// Symbols grouped by crate/package
    by_crate: Vec<CrateSymbols>,
    /// Map crate_name -> index
    crate_map: std::collections::HashMap<String, usize>,
}

#[derive(Debug, Clone)]
struct CrateSymbols {
    name: String,
    symbols: Vec<ExternalSymbol>,
}

impl SymbolIndex {
    /// Create an empty symbol index.
    pub fn new() -> Self {
        Self {
            by_crate: Vec::new(),
            crate_map: std::collections::HashMap::new(),
        }
    }

    /// Add symbols from a source file.
    pub fn add_symbols(&mut self, crate_name: &str, _file: &PathBuf, symbols: &[ExternalSymbol]) {
        let idx = if let Some(&idx) = self.crate_map.get(crate_name) {
            idx
        } else {
            let idx = self.by_crate.len();
            self.crate_map.insert(crate_name.to_string(), idx);
            self.by_crate.push(CrateSymbols {
                name: crate_name.to_string(),
                symbols: Vec::new(),
            });
            idx
        };

        self.by_crate[idx].symbols.extend(symbols.to_vec());
    }

    /// Search for symbols matching a pattern.
    pub fn search(&self, pattern: &str, limit: usize) -> Vec<ExternalSymbol> {
        let pattern = pattern.to_lowercase();
        let mut results: Vec<&ExternalSymbol> = self
            .by_crate
            .iter()
            .flat_map(|c| c.symbols.iter())
            .filter(|s| s.name.to_lowercase().contains(&pattern))
            .collect();

        results.sort_by(|a, b| a.name.len().cmp(&b.name.len()));
        results.truncate(limit);

        results.into_iter().cloned().collect()
    }

    /// Search within a specific crate.
    pub fn search_crate(
        &self,
        crate_name: &str,
        pattern: &str,
        limit: usize,
    ) -> Vec<ExternalSymbol> {
        let pattern = pattern.to_lowercase();

        if let Some(&idx) = self.crate_map.get(crate_name) {
            let symbols = &self.by_crate[idx].symbols;
            let mut results: Vec<&ExternalSymbol> = symbols
                .iter()
                .filter(|s| s.name.to_lowercase().contains(&pattern))
                .collect();

            results.truncate(limit);
            return results.into_iter().cloned().collect();
        }

        Vec::new()
    }

    /// Get all indexed crate/package names.
    pub fn get_crates(&self) -> Vec<&str> {
        self.by_crate.iter().map(|c| c.name.as_str()).collect()
    }

    /// Get total symbol count.
    pub fn symbol_count(&self) -> usize {
        self.by_crate.iter().map(|c| c.symbols.len()).sum()
    }

    /// Get crate count.
    pub fn crate_count(&self) -> usize {
        self.by_crate.len()
    }

    /// Clear all symbols.
    pub fn clear(&mut self) {
        self.by_crate.clear();
        self.crate_map.clear();
    }

    /// Serialize to JSON string.
    pub fn serialize(&self) -> String {
        let mut output = Vec::new();

        for crate_sym in &self.by_crate {
            for sym in &crate_sym.symbols {
                let kind_str = match sym.kind {
                    SymbolKind::Struct => "struct",
                    SymbolKind::Enum => "enum",
                    SymbolKind::Trait => "trait",
                    SymbolKind::Function => "fn",
                    SymbolKind::Method => "method",
                    SymbolKind::Field => "field",
                    SymbolKind::Impl => "impl",
                    SymbolKind::Mod => "mod",
                    SymbolKind::Const => "const",
                    SymbolKind::Static => "static",
                    SymbolKind::TypeAlias => "type",
                    SymbolKind::Unknown => "unknown",
                };

                let line = sym.line;
                let file = sym.file.to_string_lossy();

                // Format: crate_name|symbol_name|kind|file:line
                writeln!(
                    output,
                    "{}|{}|{}|{}:{}",
                    crate_sym.name, sym.name, kind_str, file, line
                )
                .unwrap();
            }
        }

        String::from_utf8(output).unwrap_or_default()
    }

    /// Deserialize from JSON string.
    pub fn deserialize(&mut self, data: &str) -> bool {
        self.clear();

        for line in data.lines() {
            let parts: Vec<&str> = line.split('|').collect();
            if parts.len() < 4 {
                continue;
            }

            let crate_name = parts[0];
            let name = parts[1];
            let kind_str = parts[2];
            let loc = parts[3];

            let kind = match kind_str {
                "struct" => SymbolKind::Struct,
                "enum" => SymbolKind::Enum,
                "trait" => SymbolKind::Trait,
                "fn" => SymbolKind::Function,
                "method" => SymbolKind::Method,
                "field" => SymbolKind::Field,
                "impl" => SymbolKind::Impl,
                "mod" => SymbolKind::Mod,
                "const" => SymbolKind::Const,
                "static" => SymbolKind::Static,
                "type" => SymbolKind::TypeAlias,
                _ => SymbolKind::Unknown,
            };

            // Parse file:line
            let mut file_parts = loc.rsplitn(2, ':');
            let file = file_parts.nth(1).unwrap_or(loc);
            let line = file_parts
                .nth(0)
                .and_then(|s| s.parse::<usize>().ok())
                .unwrap_or(1);

            let symbol = ExternalSymbol {
                name: name.to_string(),
                kind,
                file: PathBuf::from(file),
                line,
                crate_name: crate_name.to_string(),
            };

            self.add_symbols(crate_name, &PathBuf::from(file), &vec![symbol]);
        }

        true
    }
}

/// Extract symbols from a source file (synchronous).
pub fn extract_symbols(path: &PathBuf, lang: &str) -> Result<Vec<ExternalSymbol>, std::io::Error> {
    use std::fs::read_to_string;
    let content = read_to_string(path)?;

    let mut symbols = Vec::new();

    match lang {
        "rust" => extract_rust_symbols(&content, path, &mut symbols),
        "python" => extract_python_symbols(&content, path, &mut symbols),
        _ => {}
    }

    Ok(symbols)
}

// Pre-compiled Rust regex patterns for extraction performance.
lazy_static! {
    static ref RE_STRUCT: regex::Regex = regex::Regex::new(r"(?:pub\s+)?struct\s+(\w+)").unwrap();
    static ref RE_ENUM: regex::Regex = regex::Regex::new(r"(?:pub\s+)?enum\s+(\w+)").unwrap();
    static ref RE_TRAIT: regex::Regex = regex::Regex::new(r"(?:pub\s+)?trait\s+(\w+)").unwrap();
    static ref RE_FN: regex::Regex = regex::Regex::new(r"(?:pub\s+)?fn\s+(\w+)").unwrap();
    static ref RE_IMPL: regex::Regex = regex::Regex::new(r"impl\s+(\w+)").unwrap();
    static ref RE_MOD: regex::Regex = regex::Regex::new(r"(?:pub\s+)?mod\s+(\w+)").unwrap();
    static ref RE_TYPE: regex::Regex = regex::Regex::new(r"(?:pub\s+)?type\s+(\w+)").unwrap();
    static ref RE_CONST: regex::Regex = regex::Regex::new(r"(?:pub\s+)?const\s+(\w+)").unwrap();
    static ref RE_STATIC: regex::Regex = regex::Regex::new(r"(?:pub\s+)?static\s+(\w+)").unwrap();
}

fn extract_rust_symbols(content: &str, path: &PathBuf, symbols: &mut Vec<ExternalSymbol>) {
    for (i, line) in content.lines().enumerate() {
        let line_num = i + 1;

        // pub struct Name
        if let Some(cap) = RE_STRUCT.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Struct,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // pub enum Name
        else if let Some(cap) = RE_ENUM.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Enum,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // pub trait Name
        else if let Some(cap) = RE_TRAIT.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Trait,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // pub fn name
        else if let Some(cap) = RE_FN.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Function,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // impl Name
        else if let Some(cap) = RE_IMPL.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Impl,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // mod name
        else if let Some(cap) = RE_MOD.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Mod,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // type Name
        else if let Some(cap) = RE_TYPE.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::TypeAlias,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // const NAME
        else if let Some(cap) = RE_CONST.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Const,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // static NAME
        else if let Some(cap) = RE_STATIC.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Static,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
    }
}

// Pre-compiled Python regex patterns for extraction performance.
lazy_static::lazy_static! {
    static ref RE_PY_CLASS: regex::Regex = regex::Regex::new(r"class\s+(\w+)").unwrap();
    static ref RE_PY_DEF: regex::Regex = regex::Regex::new(r"def\s+(\w+)").unwrap();
    static ref RE_PY_ASYNC_DEF: regex::Regex = regex::Regex::new(r"async\s+def\s+(\w+)").unwrap();
}

fn extract_python_symbols(content: &str, path: &PathBuf, symbols: &mut Vec<ExternalSymbol>) {
    for (i, line) in content.lines().enumerate() {
        let line_num = i + 1;

        // class Name
        if let Some(cap) = RE_PY_CLASS.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Struct, // Map class to struct
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // def name
        else if let Some(cap) = RE_PY_DEF.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Function,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
        // async def name
        else if let Some(cap) = RE_PY_ASYNC_DEF.captures(line) {
            symbols.push(ExternalSymbol {
                name: cap[1].to_string(),
                kind: SymbolKind::Function,
                file: path.clone(),
                line: line_num,
                crate_name: String::new(),
            });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write as IoWrite;

    #[test]
    fn test_extract_rust_symbols() {
        let temp_file = tempfile::NamedTempFile::new().unwrap();
        {
            let mut f = std::io::BufWriter::new(&temp_file);
            writeln!(f, "pub struct MyStruct {{").unwrap();
            writeln!(f, "    field: String,").unwrap();
            writeln!(f, "}}").unwrap();
            writeln!(f, "").unwrap();
            writeln!(f, "pub enum MyEnum {{").unwrap();
            writeln!(f, "    Variant,").unwrap();
            writeln!(f, "}}").unwrap();
            writeln!(f, "").unwrap();
            writeln!(f, "pub fn my_function() {{").unwrap();
            writeln!(f, "}}").unwrap();
        }

        let symbols = extract_symbols(&temp_file.path().to_path_buf(), "rust").unwrap();

        assert!(
            symbols
                .iter()
                .any(|s| s.name == "MyStruct" && s.kind == SymbolKind::Struct)
        );
        assert!(
            symbols
                .iter()
                .any(|s| s.name == "MyEnum" && s.kind == SymbolKind::Enum)
        );
        assert!(
            symbols
                .iter()
                .any(|s| s.name == "my_function" && s.kind == SymbolKind::Function)
        );
    }

    #[test]
    fn test_extract_python_symbols() {
        let temp_file = tempfile::NamedTempFile::new().unwrap();
        {
            let mut f = std::io::BufWriter::new(&temp_file);
            writeln!(f, "class MyClass:").unwrap();
            writeln!(f, "    pass").unwrap();
            writeln!(f, "").unwrap();
            writeln!(f, "def my_function():").unwrap();
            writeln!(f, "    pass").unwrap();
        }

        let symbols = extract_symbols(&temp_file.path().to_path_buf(), "python").unwrap();

        assert!(
            symbols
                .iter()
                .any(|s| s.name == "MyClass" && s.kind == SymbolKind::Struct)
        );
        assert!(
            symbols
                .iter()
                .any(|s| s.name == "my_function" && s.kind == SymbolKind::Function)
        );
    }

    #[test]
    fn test_symbol_index_search() {
        let mut index = SymbolIndex::new();

        // Add test symbols
        index.add_symbols(
            "serde",
            &PathBuf::from("lib.rs"),
            &vec![
                ExternalSymbol {
                    name: "Serializer".to_string(),
                    kind: SymbolKind::Struct,
                    file: PathBuf::from("lib.rs"),
                    line: 10,
                    crate_name: "serde".to_string(),
                },
                ExternalSymbol {
                    name: "serialize".to_string(),
                    kind: SymbolKind::Function,
                    file: PathBuf::from("lib.rs"),
                    line: 20,
                    crate_name: "serde".to_string(),
                },
            ],
        );

        index.add_symbols(
            "tokio",
            &PathBuf::from("lib.rs"),
            &vec![ExternalSymbol {
                name: "spawn".to_string(),
                kind: SymbolKind::Function,
                file: PathBuf::from("lib.rs"),
                line: 5,
                crate_name: "tokio".to_string(),
            }],
        );

        let results = index.search("serialize", 10);
        // Both "serialize" and "Serializer" match (case-insensitive contains)
        assert_eq!(results.len(), 2);
        assert!(results.iter().any(|s| s.name == "Serializer"));
        assert!(results.iter().any(|s| s.name == "serialize"));

        let results = index.search("spawn", 10);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "spawn");

        let results = index.search_crate("serde", "serialize", 10);
        // Both "serialize" and "Serializer" match within serde crate
        assert_eq!(results.len(), 2);
    }

    #[test]
    fn test_serialize_deserialize() {
        let mut index = SymbolIndex::new();

        index.add_symbols(
            "test",
            &PathBuf::from("lib.rs"),
            &vec![ExternalSymbol {
                name: "MyStruct".to_string(),
                kind: SymbolKind::Struct,
                file: PathBuf::from("lib.rs"),
                line: 10,
                crate_name: "test".to_string(),
            }],
        );

        let data = index.serialize();

        let mut index2 = SymbolIndex::new();
        index2.deserialize(&data);

        let results = index2.search("MyStruct", 10);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "MyStruct");
    }
}
