# Schema Singularity: Rust as Single Source of Truth

> **Version:** 1.0
> **Status:** Active
> **Philosophy:** "Type Once, Use Everywhere"

## 1. Problem Statement

In Agentic OS development, **Context Drift** is a silent killer:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Context Drift: The Hidden Threat                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Python Pydantic    ↔    Rust Structs    ↔    LLM JSON Schema     │
│   ──────────────          ──────────           ───────────────     │
│   model_a: str             name: String         properties: {      │
│   model_b: int                                 "a": { "type": ... } │
│   model_c: bool                                "b": { "type": ... } │
│                           MISMATCH!           "c": { ... }         │
│                                                                     │
│   Result: Runtime errors, LLM hallucinations, data corruption       │
└─────────────────────────────────────────────────────────────────────┘
```

When any layer changes independently, the system breaks silently.

## 2. Solution: Schema Singularity

**Establish Rust (`omni-types`) as the Single Source of Truth (SSOT).** All other layers dynamically retrieve schemas from Rust at runtime.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Rust (Single Source of Truth)                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ omni-types: JsonSchema 派生的结构体                       │   │
│  │  - Skill, SkillDefinition, TaskBrief                     │   │
│  │  - AgentResult, AgentContext, VectorSearchResult         │   │
│  │  - EnvironmentSnapshot                                   │   │
│  │                                                          │   │
│  │  #[derive(Debug, Clone, Serialize, Deserialize,         │   │
│  │   JsonSchema)]                                           │   │
│  │  pub struct SkillDefinition { ... }                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            │ get_schema_json()                 │
│                            ▼                                    │
┌─────────────────────────────────────────────────────────────────┐
│                    Python (Schema Consumer)                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ RustSchemaRegistry: FFI + Cache                         │   │
│  │  - 自动从 Rust 获取权威 Schema                           │   │
│  │  - 缓存避免重复 FFI 调用                                 │   │
│  │  - 类型安全保证                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ToolContextBuilder: LLM 格式转换                         │   │
│  │  - to_openai_tools() → OpenAI Function Calling          │   │
│  │  - to_anthropic_tools() → Anthropic Tool Format         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Implementation Details

### 3.1 Rust Layer (`omni-types`)

**Dependencies:**

```toml
# Cargo.toml (workspace)
[workspace.dependencies]
schemars = "0.8.21"
```

**Struct Definition with JsonSchema:**

```rust
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

/// Skill definition with generic metadata container.
/// This enables schema-driven metadata evolution without recompiling Rust.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(from = "SkillDefinitionHelper", into = "SkillDefinitionHelper")]
pub struct SkillDefinition {
    /// Unique identifier for the skill (e.g., "git", "writer")
    pub name: String,
    /// Semantic description used for vector embedding generation
    pub description: String,
    /// Generic metadata container for schema-defined fields
    pub metadata: serde_json::Value,
    /// Routing keywords for semantic search
    #[serde(default)]
    pub routing_keywords: Vec<String>,
}
```

**Schema Registry:**

```rust
/// Get JSON Schema for a registered type.
/// This enables Python to dynamically retrieve authoritative schemas from Rust.
pub fn get_schema_json(type_name: &str) -> Result<String, SchemaError> {
    let schema = match type_name {
        "Skill" => schemars::schema_for!(Skill),
        "SkillDefinition" => schemars::schema_for!(SkillDefinition),
        "TaskBrief" => schemars::schema_for!(TaskBrief),
        "AgentResult" => schemars::schema_for!(AgentResult),
        "AgentContext" => schemars::schema_for!(AgentContext),
        "VectorSearchResult" => schemars::schema_for!(VectorSearchResult),
        "EnvironmentSnapshot" => schemars::schema_for!(EnvironmentSnapshot),
        "OmniTool" => schemars::schema_for!(SkillDefinition), // Alias
        _ => return Err(SchemaError::UnknownType(type_name.to_string())),
    };
    serde_json::to_string_pretty(&schema).map_err(|e| {
        SchemaError::UnknownType(format!("Serialization failed: {e}"))
    })
}
```

### 3.2 Python Bindings

**Rust FFI (`bindings/python/src/schema.rs`):**

```rust
use pyo3::prelude::*;
use omni_types::SchemaError;

/// Get JSON Schema for a registered type.
#[pyfunction]
#[pyo3(signature = (type_name))]
pub fn py_get_schema_json(type_name: &str) -> PyResult<String> {
    match omni_types::get_schema_json(type_name) {
        Ok(schema) => Ok(schema),
        Err(SchemaError::UnknownType(name)) => Err(pyo3::exceptions::PyValueError::new_err(
            format!("Unknown type: {}. Available: {:?}", name, omni_types::get_registered_types())
        )),
    }
}

/// Get list of all registered type names.
#[pyfunction]
pub fn py_get_registered_types() -> Vec<&'static str> {
    omni_types::get_registered_types()
}
```

### 3.3 Python Core

**RustSchemaRegistry with Caching:**

```python
# omni/core/context/tools.py

from omni_core_rs import py_get_schema_json

class RustSchemaRegistry:
    """
    Cache for Rust-generated JSON Schemas to avoid repetitive FFI calls.

    This establishes Rust as the Single Source of Truth (SSOT) for type definitions.
    Python and LLM consumers retrieve authoritative schemas dynamically.
    """

    _cache: dict[str, dict[str, Any]] = {}

    @classmethod
    def get(cls, type_name: str) -> dict[str, Any]:
        """Get JSON Schema for a type from Rust SSOT."""
        if type_name not in cls._cache:
            schema_json = py_get_schema_json(type_name)
            cls._cache[type_name] = json.loads(schema_json)
        return cls._cache[type_name]

    @classmethod
    def clear(cls) -> None:
        """Clear the schema cache (useful for testing)."""
        cls._cache.clear()
```

## 4. Usage Examples

### 4.1 Get Schema from Rust SSOT

```python
from omni.core.context.tools import get_rust_schema, list_available_schemas

# List all available type schemas
schemas = list_available_schemas()
print(schemas)  # ['Skill', 'SkillDefinition', 'TaskBrief', ...]

# Get authoritative schema
schema = get_rust_schema('SkillDefinition')
print(schema['properties']['name']['description'])
# "Unique identifier for the skill (e.g., 'git', 'writer')"
```

### 4.2 Convert Tools to OpenAI Format

```python
from omni.core.context.tools import ToolContextBuilder
from omni.core.skills.registry.holographic import ToolMetadata

# ToolMetadata from HolographicRegistry
metadata = ToolMetadata(
    name='read_file',
    description='Read a file from disk',
    module='/path/to/file.py',
    args=[{'name': 'path', 'type': 'str', 'description': 'File path'}],
    return_type='str'
)

# Convert to OpenAI Function Calling format
tools = ToolContextBuilder.to_openai_tools([metadata])
# Returns:
# [{
#     "type": "function",
#     "function": {
#         "name": "read_file",
#         "description": "Read a file from disk",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "path": {"type": "string", "description": "File path"}
#             },
#             "required": ["path"]
#         }
#     }
# }]
```

### 4.3 Validate Tool Output (Future Strict Mode)

```python
import jsonschema
from omni.core.context.tools import RustSchemaRegistry

# Get schema for validation
schema = RustSchemaRegistry.get("SkillDefinition")

# Validate execution result against schema
try:
    jsonschema.validate(
        instance={"name": "test", "description": "..."},
        schema=schema
    )
    print("✓ Validation passed")
except jsonschema.ValidationError as e:
    print(f"✗ Validation failed: {e.message}")
```

## 5. Available Schemas

| Type Name             | Description               | Rust Struct                       |
| :-------------------- | :------------------------ | :-------------------------------- |
| `Skill`               | Basic skill definition    | `omni_types::Skill`               |
| `SkillDefinition`     | Full skill with metadata  | `omni_types::SkillDefinition`     |
| `TaskBrief`           | Orchestrator task brief   | `omni_types::TaskBrief`           |
| `AgentResult`         | Agent execution result    | `omni_types::AgentResult`         |
| `AgentContext`        | Agent execution context   | `omni_types::AgentContext`        |
| `VectorSearchResult`  | Vector search hit         | `omni_types::VectorSearchResult`  |
| `EnvironmentSnapshot` | Live environment state    | `omni_types::EnvironmentSnapshot` |
| `OmniTool`            | Alias for SkillDefinition | -                                 |

## 6. Benefits

### 6.1 Strict Typing

- LanceDB storage structure and LLM Schema are identical because they come from the same Rust struct
- No manual synchronization required

### 6.2 Zero Maintenance

- No code generation scripts
- Schema is retrieved at runtime via FFI
- Changes to Rust struct automatically propagate to Python/LLM

### 6.3 Rust Vector Integration

- `search_hybrid()` returns `SearchResult` with proper structure
- Data is already serialized standard JSON, no transformation needed

### 6.4 Developer Experience

```python
# Before: Manual sync with potential drift
class Skill(BaseModel):
    name: str
    description: str
    # ... manually keep in sync with Rust

# After: Dynamic schema from Rust SSOT
schema = get_rust_schema('SkillDefinition')  # Always authoritative
```

## 7. Architecture Rules

### 7.1 Adding New Types

1. Define struct in `omni-types` with `JsonSchema` derive
2. Add to `get_schema_json()` match arms
3. Export in `bindings/python/src/schema.rs` (if needed for Python)
4. Python auto-discovers via `py_get_registered_types()`

### 7.2 Modifying Existing Types

**Never** modify types directly in Python. Always:

1. Change the Rust struct in `omni-types`
2. Rebuild: `uv sync --reinstall-package omni-core-rs`
3. Python automatically gets updated schema

### 7.3 Forbidden Patterns

```python
# ❌ FORBIDDEN: Manual schema definition in Python
MANUAL_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}}
}

# ✅ CORRECT: Dynamic schema from Rust SSOT
from omni.core.context.tools import get_rust_schema
schema = get_rust_schema('SkillDefinition')
```

## 8. File References

| Layer  | File Path                                                        | Purpose                       |
| :----- | :--------------------------------------------------------------- | :---------------------------- |
| Rust   | `packages/rust/crates/omni-types/src/lib.rs`                     | Type definitions + JsonSchema |
| Rust   | `packages/rust/bindings/python/src/schema.rs`                    | Python FFI bindings           |
| Rust   | `packages/rust/bindings/python/src/lib.rs`                       | Module exports                |
| Python | `packages/python/core/src/omni/core/context/tools.py`            | Schema registry + converters  |
| Tests  | `packages/python/core/tests/integration/test_reactive_loader.py` | Schema Singularity tests      |

## 9. Performance Considerations

- **Cache Hit:** Schema retrieval is O(1) after first FFI call
- **Cache Miss:** Single FFI call + JSON parsing (~0.5ms)
- **Memory:** Cached schemas consume minimal memory (~1KB per type)
- **Benchmark:** For 8 registered types, total cache memory < 10KB

```python
# Benchmark schema retrieval
import time

start = time.perf_counter()
for _ in range(1000):
    schema = get_rust_schema('SkillDefinition')  # Cached after first call
elapsed = time.perf_counter() - start
print(f"1000 retrievals: {elapsed*1000:.2f}ms ({elapsed*1000/1000:.4f}ms each)")
# Output: ~0.00ms each (fully cached)
```

## 10. Future Extensions

### 10.1 Strict Mode Validation

Add runtime validation of tool inputs/outputs against Rust schemas:

```python
ToolContextBuilder.validate_tool_output("read_file", {"path": "/test"})
```

### 10.2 Multi-Language Bindings

The same `get_schema_json()` can be exposed to:

- Node.js (via napi-rs)
- Go (via cgo)
- TypeScript (via wasm-bindgen)

### 10.3 Schema Evolution

Support schema versioning for backward compatibility:

```rust
pub fn get_schema_json(type_name: &str, version: Option<u32>) -> Result<String, SchemaError>
```
