# AST-Based Code Navigation and Search

> **The Cartographer & The Hunter**
> CCA-Aligned Code Navigation Using ast-grep-core 0.40.5

## 1. Philosophical Foundation

### 1.1 The CCA Perspective on Code Understanding

The Confucius Code Agent (CCA) paper establishes a fundamental insight: **code understanding is a mapping problem, not a reading problem**. Traditional approaches treat code as text to be scanned linearly. CCA reframes this as a **spatial reasoning task** where the agent constructs and navigates a mental model of code structure.

This philosophical shift has profound implications:

| Traditional Approach                 | CCA Approach                      |
| ------------------------------------ | --------------------------------- |
| Read file line by line               | Parse into AST, extract structure |
| Search text patterns                 | Match code patterns semantically  |
| Consume full context                 | Use summaries and outlines        |
| Searching for a needle in a haystack | Surgical precision                |

### 1.2 AX: The Agent's Internal Workspace

CCA introduces **AX (Agent Experience)** as a critical concept—the agent's working memory for reasoning. Key observations:

1. **Token budget is real**: Each line of context consumes AX capacity
2. **Noise propagates**: Irrelevant code fragments degrade reasoning quality
3. **Structure compresses**: A map (outline) conveys more meaning per token than raw text

Our implementation quantifies this:

```
Full file read:  ~5,800 tokens
AST outline:     ~159 tokens
Compression:     36.5x
```

This isn't just efficiency—it's cognitive load management for the LLM.

## 2. Architecture Overview

### 2.1 System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                        Code Tools Skill                           │
│  assets/skills/code_tools/scripts/                               │
│  - outline_file: Generate symbolic skeleton                      │
│  - search_code: Pattern matching in single file                  │
│  - search_directory: Recursive pattern search                    │
│  - structural_replace: AST-based code replacement                │
│  - structural_preview: Preview changes (dry-run)                 │
│  - structural_apply: Apply changes to file                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python Bindings Layer                         │
│  packages/rust/bindings/python/src/lib.rs                        │
│  - PyO3 bindings for Rust functions                              │
│  - GIL release for CPU-intensive operations                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Rust Core Layer                             │
│  packages/rust/crates/omni-tags/src/lib.rs                       │
│  - ast-grep-core 0.40.5 for AST parsing                         │
│  - Pattern matching and capture extraction                       │
│  - Multi-language support (Python, Rust, JS, TS)                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Tree-sitter Parsers                          │
│  - Python, Rust, JavaScript, TypeScript parsers                  │
│  - Syntax tree construction                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Components

#### The Cartographer (Outline Generation)

The Cartographer extracts symbolic structure from code:

```python
# Input: Full Python file (5,800 tokens)
# Output: Symbolic skeleton (159 tokens)

// OUTLINE: packages/python/agent/src/agent/core/agents/base.py
// Total symbols: 24
L48   [function]   _get_ux_event_log_path def _get_ux_event_log_path
L85   [class]      AgentContext class AgentContext
L122  [class]      BaseAgent class BaseAgent
```

**Key Patterns**:

- Python: `class $NAME`, `def $NAME`, `async def $NAME`
- Rust: `pub struct $NAME`, `pub fn $NAME`, `enum $NAME`, `trait $NAME`
- JavaScript: `class $NAME`, `function $NAME`
- TypeScript: Same as JS + `interface $NAME`

#### The Hunter (Structural Search)

The Hunter provides surgical precision in code search:

```python
# Naive grep "connect" finds 7 matches:
# - Comment: "This is a comment about connect function"
# - Comment: "Don't connect to unauthorized servers"
# - Definition: def connect(host: str, port: int)
# - Comment: "We don't connect here"
# - Method: def connect(self, db_url: str)
# - Docstring: "Method to connect to database."
# - Comment: "connect appears many times above"

# AST search "connect($ARGS)" finds 2 semantic matches:
# - def connect(host: str, port: int) -> bool
# - def connect(self, db_url: str)
```

This distinction—**semantic vs. textual**—is the core insight from CCA.

## 3. Implementation Details

### 3.1 Rust Core: omni-tags

#### File Structure

```
packages/rust/crates/omni-tags/src/lib.rs
├── Imports and error types
├── Symbol and SearchMatch structures
├── ast-grep patterns (constants)
└── TagExtractor implementation
    ├── outline_file()        # Cartographer
    ├── search_file()         # Hunter
    ├── search_directory()    # Hunter
    └── extract_*(content)    # Language-specific
```

#### Key Structures

```rust
// Search match result
pub struct SearchMatch {
    pub path: String,              // File path
    pub line: usize,               // Line number (1-indexed)
    pub column: usize,             // Column number
    pub content: String,           // Matched content
    pub captures: HashMap<String, String>,  // $VAR captures
}

// Search configuration
pub struct SearchConfig {
    pub file_pattern: String,      // Glob pattern
    pub max_file_size: u64,        // 1MB default
    pub max_matches_per_file: usize,
    pub languages: Vec<String>,
}
```

#### Pattern Matching API

```rust
// Using ast-grep-core 0.40.5
use ast_grep_core::{matcher::MatcherExt, Pattern};
use ast_grep_language::{SupportLang, LanguageExt};

// Create language context
let lang = SupportLang::Python;

// Parse source
let root = lang.ast_grep(content);
let root_node = root.root();

// Create pattern
let pattern = Pattern::try_new("class $NAME", lang)?;

// DFS search through all nodes
for node in root_node.dfs() {
    if let Some(m) = pattern.match_node(node.clone()) {
        // Extract captures
        let env = m.get_env();
        let name = env.get_match("NAME").map(|n| n.text().to_string());
    }
}
```

### 3.2 Python Bindings

#### Function Signatures

```python
## The Cartographer: Outline Generation
def get_file_outline(path: str, language: str | None = None) -> str:
    """
    Generate symbolic outline for a source file.
    Returns ~50 tokens instead of ~5000 for full content.
    """

## The Hunter: Structural Search
def search_code(path: str, pattern: str, language: str | None = None) -> str:
    """
    Search for AST patterns in a single file.
    Pattern examples: "class $NAME", "connect($ARGS)", "def $NAME($PARAMS)"
    """

def search_directory(path: str, pattern: str, file_pattern: str | None = None) -> str:
    """
    Search recursively for AST patterns across files.
    """
```

#### GIL Management

```rust
// Release GIL for CPU-intensive AST operations
#[pyfunction]
fn search_code(path: String, pattern: String, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            TagExtractor::search_file(&path, &pattern, language)
        })
    })
}
```

### 3.3 Skill Implementation

#### Tool Definitions

```python
from agent.skills.decorators import skill_command

@skill_command("outline_file")
def outline_file(path: str, language: str | None = None) -> str:
    """Generate high-level outline of a source file."""

@skill_command("search_code")
def search_code(path: str, pattern: str, language: str | None = None) -> str:
    """Search for AST patterns in a single file."""

@skill_command("search_directory")
def search_directory(path: str, pattern: str, file_pattern: str | None = None) -> str:
    """Search for AST patterns recursively in a directory."""
```

#### Fallback Mechanism

When Rust bindings are unavailable, Python fallbacks provide basic functionality:

```python
def search_code(path: str, pattern: str, language: str | None = None) -> str:
    if not RUST_AVAILABLE:
        # Fallback: simple text search
        content = Path(path).read_text()
        lines = content.split("\n")
        # ... basic matching
    # ... use Rust implementation
```

## 4. CCA Alignment Analysis

### 4.1 Extension: The Agent's Perception

CCA emphasizes that powerful agents need **extensions** to perceive and manipulate the world (in our case, code). Our implementation provides:

| Extension Capability | CCA Principle              | Implementation         |
| -------------------- | -------------------------- | ---------------------- |
| Structural awareness | "Map over territory"       | AST outline generation |
| Semantic search      | "Precision over noise"     | Pattern-based search   |
| Variable capture     | "Extract meaning"          | $VAR capture system    |
| Multi-language       | "Generalize across syntax" | SupportLang enum       |

### 4.2 AX Efficiency Quantification

```
┌──────────────────────┬──────────────┬─────────────────┐
│ Operation            │ Token Cost   │ Compression     │
├──────────────────────┼──────────────┼─────────────────┤
│ Full file read       │ 5,800        │ 1x (baseline)   │
│ AST outline          │ 159          │ 36.5x           │
│ Naive grep "connect" │ variable     │ high noise      │
│ AST search           │ 200-500      │ precision gain  │
└──────────────────────┴──────────────┴─────────────────┘
```

### 4.3 The "Hunt with Precision" Principle

From CCA's core insight: agents should **reason about code structure** rather than processing text. Our implementation embodies this through:

1. **Pattern Expression**: Agents express intent (`connect($ARGS)`) not string matching (`grep "connect"`)

2. **Capture Semantics**: `$NAME` means "any identifier" not "literally dollar-sign name"

3. **Language Models**: AST parsers understand Python's `def`, Rust's `fn`, JS's `function`

### 4.4 Memory vs. Extensions

CCA distinguishes:

- **Memory**: Storing and retrieving past interactions
- **Extensions**: Capabilities to perceive and act in the environment

Our code navigation system is primarily an **extension**:

- It doesn't store knowledge (memory)
- It provides perception (code structure awareness)
- It enables action (precise code location)

## 5. Usage Patterns

### 5.1 Code Navigation Workflow

```
1. Agent receives task: "Find where user authentication happens"
2. Agent uses search_directory("src/", "def $NAME($PARAMS)")
3. Agent finds: "def authenticate_user($CREDENTIALS)"
4. Agent uses outline_file("auth.py")
5. Agent navigates to specific implementation
```

### 5.2 Pattern Reference

| Pattern            | Meaning               | Example                      |
| ------------------ | --------------------- | ---------------------------- |
| `class $NAME`      | Class definitions     | `class Agent:`               |
| `def $NAME`        | Function definitions  | `def connect(host, port):`   |
| `async def $NAME`  | Async functions       | `async def fetch(url):`      |
| `pub fn $NAME`     | Rust functions        | `pub fn process() {}`        |
| `pub struct $NAME` | Rust structs          | `pub struct Context {}`      |
| `interface $NAME`  | TypeScript interfaces | `interface User {}`          |
| `connect($ARGS)`   | Function calls        | `connect("localhost", 8080)` |
| `$VAR = $EXPR`     | Assignments           | `result = calculate()`       |

## 6. Performance Characteristics

### 6.1 Benchmark Results

```
Single file outline (5,800 tokens):
  - Parse time: ~1ms
  - Match time: ~2ms
  - Total: ~3ms

Directory search (158 Python files):
  - Files searched: 158
  - Total matches: 322
  - Time: ~50ms
```

### 6.2 Memory Efficiency

- **Outline mode**: 1MB file limit, extracts ~100 symbols max
- **Search mode**: 1MB per file, 100 matches per file limit
- **No caching**: Results returned directly, no intermediate storage

## 7. Related Files

| File                                        | Purpose                             |
| ------------------------------------------- | ----------------------------------- |
| `packages/rust/crates/omni-tags/src/lib.rs` | Rust core implementation            |
| `packages/rust/crates/omni-tags/Cargo.toml` | Dependencies (ast-grep-core 0.40.5) |
| `packages/rust/bindings/python/src/lib.rs`  | PyO3 bindings                       |
| `assets/skills/code_tools/scripts/`         | Python skill tools                  |
| `assets/skills/code_tools/SKILL.md`         | Skill manifest                      |
| `docs/developer/ast-grep-core.md`           | Developer API guide                 |

## 8. Future Directions

### 8.1 Potential Enhancements

1. **Multi-file patterns**: Match patterns spanning multiple functions/classes
2. **Code transformation**: Use ast-grep's rewrite capabilities
3. **Incremental indexing**: Cache ASTs for faster repeated searches
4. **More languages**: Add Go, Java, C++ support

### 8.2 CCA Evolution

This implementation is aligned with CCA's vision of **code-aware agents**. Future extensions could include:

- **Code Reasoning**: Understand what functions do
- **Code Generation**: Write based on patterns
- **Code Refactoring**: Structural edits

## 9. Conclusion

The implementation of AST-based code navigation and search represents a concrete application of CCA principles:

1. **Understanding structure, not text**: AST parsing provides semantic understanding
2. **Managing AX efficiently**: 36.5x compression through symbolic representation
3. **Enabling surgical precision**: Pattern matching eliminates noise
4. **Extending agent capability**: New perception (code structure) for reasoning

The Cartographer gives agents a map. The Hunter gives them precision. Together, they transform code understanding from "reading" to "navigation."

> "A good map is worth a thousand lines of code."
> "Hunt with precision, not with a net."

---

_Part of Omni DevEnv Fusion - Code Navigation Skill_
