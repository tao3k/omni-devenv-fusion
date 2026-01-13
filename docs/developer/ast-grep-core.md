# ast-grep-core 0.40.5 Developer Guide

> Based on Phase 50: The Cartographer migration experience
>
> **See also**: [AST-Based Code Navigation and Search](../reference/ast-grep.md) for full CCA-aligned implementation guide.

## 1. Core Concepts

ast-grep-core is an AST-based code search and transformation library that uses tree-sitter for syntax parsing.

### Key Types

```rust
use ast_grep_core::{matcher::MatcherExt, Pattern};
use ast_grep_language::{Language, LanguageExt, SupportLang};
```

| Type               | Description                           |
| ------------------ | ------------------------------------- |
| `Pattern`          | Search pattern for matching AST nodes |
| `Root<D>`          | Parsed AST root node                  |
| `Node<'t, D>`      | AST node                              |
| `NodeMatch<'t, D>` | Match result                          |
| `SupportLang`      | Supported languages enum              |
| `MetaVarEnv`       | Captured variable environment         |

## 2. Basic Usage

### 2.1 Parse Source Code

```rust
use ast_grep_language::{SupportLang, LanguageExt};

let lang = SupportLang::Python;
let root = lang.ast_grep(content);
let root_node = root.root();
```

### 2.2 Create Search Pattern

```rust
use ast_grep_core::{matcher::MatcherExt, Pattern};

const PYTHON_CLASS_PATTERN: &str = "class $NAME";
let pattern = Pattern::new(PYTHON_CLASS_PATTERN, lang);
```

### 2.3 Match Nodes

`Pattern` implements the `Matcher` trait, but methods require the `MatcherExt` trait:

```rust
// Method 1: Find first match
if let Some(m) = pattern.find_node(root_node.clone()) {
    // Handle match
}

// Method 2: Iterate all nodes to find matches
for node in root_node.dfs() {
    if let Some(m) = pattern.match_node(node.clone()) {
        // Handle each match
    }
}
```

**Note**: `Pattern` does not have a `find_all()` method. You must manually iterate through DFS.

### 2.4 Extract Captured Variables

```rust
// Get NAME capture
if let Some(captured) = m.get_env().get_match("NAME") {
    let name = captured.text().to_string();
}
```

## 3. Language Support

### 3.1 SupportLang Enum

```rust
SupportLang::Python
SupportLang::Rust
SupportLang::JavaScript
SupportLang::TypeScript
// ... more languages
```

### 3.2 Parse Language from String

```rust
use std::str::FromStr;
use ast_grep_language::SupportLang;

match SupportLang::from_str("python") {
    Ok(lang) => { /* use language */ },
    Err(e) => println!("Unsupported language: {}", e),
}
```

### 3.3 Infer Language from File Path

```rust
use ast_grep_language::SupportLang;

if let Some(lang) = SupportLang::from_path(path) {
    // Use inferred language
}
```

## 4. Pattern Syntax

### 4.1 Variable Capture

```rust
"class $NAME"           // Capture class name
"fn $NAME"              // Capture function name
"impl $NAME"            // Capture impl name
```

### 4.2 Rust Special Rules

```rust
// struct requires pub prefix
"pub struct $NAME"      // ✅ Correct
"struct $NAME"          // ❌ Cannot match pub struct

// fn works without pub
"pub fn $NAME"          // Matches pub fn
"fn $NAME"              // Matches fn (including pub fn)

// impl/trait/enum don't need pub
"impl $NAME"
"trait $NAME"
"enum $NAME"
```

### 4.3 Optional Modifier

```rust
"pub? struct $NAME"     // Optional pub (syntactic sugar)
```

## 5. Complete Example

```rust
use ast_grep_core::{matcher::MatcherExt, Pattern};
use ast_grep_language::{SupportLang, LanguageExt};

fn extract_symbols(content: &str, lang: SupportLang) -> Vec<Symbol> {
    let root = lang.ast_grep(content);
    let root_node = root.root();
    let mut symbols = Vec::new();

    // Define patterns
    let class_pattern = "class $NAME";
    let fn_pattern = "fn $NAME";

    // Extract classes
    let pattern = Pattern::new(class_pattern, lang);
    for node in root_node.dfs() {
        if let Some(m) = pattern.match_node(node.clone()) {
            if let Some(captured) = m.get_env().get_match("NAME") {
                symbols.push(Symbol {
                    name: captured.text().to_string(),
                    kind: SymbolKind::Class,
                    line: m.start_pos().line(),
                });
            }
        }
    }

    symbols
}
```

## 6. Common Issues

### 6.1 Method Not Found Error

```
error: method not found in `ast_grep_core::Pattern`
```

**Cause**: The `match_node` method is in the `MatcherExt` trait. Import it:

```rust
use ast_grep_core::matcher::MatcherExt;
```

### 6.2 Pattern Not Matching

**Possible causes**:

1. Language doesn't support the pattern
2. Rust `pub` keyword issue
3. Pattern syntax error

**Debugging**:

```rust
// Check AST node types
for node in root_node.dfs() {
    println!("Node kind: {}", node.kind());
}

// Test different patterns
let patterns = vec!["struct $NAME", "pub struct $NAME"];
for p in &patterns {
    let pattern = Pattern::new(p, lang);
    for node in root_node.dfs() {
        if pattern.match_node(node.clone()).is_some() {
            println!("'{}' matches!", p);
            break;
        }
    }
}
```

### 6.3 Capture is Empty

```rust
// Pattern must have $NAME capture
"impl"           // ❌ Cannot get NAME
"impl $NAME"     // ✅ Can get NAME
```

## 7. API Reference

### LanguageExt trait

```rust
pub trait LanguageExt {
    fn ast_grep(&self, source: &str) -> SgRoot<StrDoc<Self>>;
    fn get_ts_language(&self) -> TSLanguage;
    // ...
}
```

### Pattern methods

```rust
impl Pattern {
    pub fn new(pattern: &str, lang: impl Language) -> Result<Self, PatternError>;
}

impl MatcherExt for Pattern {
    fn match_node<'tree, D: Doc>(&self, node: Node<'tree, D>) -> Option<NodeMatch<'tree, D>>;
    fn find_node<'tree, D: Doc>(&self, node: Node<'tree, D>) -> Option<NodeMatch<'tree, D>>;
}
```

### NodeMatch methods

```rust
impl<'tree, D: Doc> NodeMatch<'tree, D> {
    fn start_pos(&self) -> Position;
    fn range(&self) -> Range;
    fn kind(&self) -> Cow<'_, str>;
    fn text(&self) -> Cow<'tree, str>;
    fn get_env(&self) -> &MetaVarEnv<'tree, D>;
}
```

## 8. Related Files

- `packages/rust/crates/omni-tags/src/lib.rs` - Implementation example
- `packages/rust/crates/omni-tags/Cargo.toml` - Dependency configuration
- `assets/specs/phase50_cca_navigation.md` - Phase 50 specification
