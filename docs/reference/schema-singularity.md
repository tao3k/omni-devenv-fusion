# Schema Singularity: Unified Type System

> Philosophy: One Source of Truth, Zero Drift

The Schema Singularity is our architectural commitment to ensuring that types are defined **once** in Rust and automatically synchronized across Python and the LLM.

---

## 1. The Problem: Context Drift

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

---

## 2. The Solution: Rust as SSOT

We use Rust as the **Single Source of Truth (SSOT)**. All shared data structures are defined in the `omni-types` crate.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Rust (Single Source of Truth)                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ omni-types: JsonSchema derived structs                    │   │
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
│  │  - Automatically fetch authoritative Schema from Rust    │   │
│  │  - Cache to avoid duplicate FFI calls                    │   │
│  │  - Type safety guarantee                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ToolContextBuilder: LLM Format Conversion                │   │
│  │  - to_openai_tools() → OpenAI Function Calling          │   │
│  │  - to_anthropic_tools() → Anthropic Tool Format         │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Implementation Details

### Rust: Defining Types

We use `schemars` to generate JSON Schema from Rust structs.

```rust
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};

#[derive(JsonSchema, Serialize, Deserialize)]
pub struct TaskBrief {
    /// The unique identifier for the task
    pub id: String,
    /// Detailed description of what needs to be done
    pub goal: String,
    /// Priority level (1-10)
    pub priority: u8,
}
```

### Python: Validating Types

```python
from omni.foundation.bridge.rust_types import validate_schema

data = {"id": "task-1", "goal": "Fix bug", "priority": 5}
try:
    validate_schema("TaskBrief", data)
    print("✓ Validation passed")
except ValidationError as e:
    print(f"✗ Validation failed: {e.message}")
```

---

## 4. Best Practices

1. **Rust First**: Always define shared structures in Rust first.
2. **Never Hardcode**: Never manually define JSON schemas in Python strings.
3. **Docstrings Matter**: Rust docstrings become JSON Schema descriptions, which the LLM reads.
4. **Validation**: Use the bridge validation in Python tests to ensure data integrity.

---

## 5. Compliance Checklist

- [ ] Struct derives `JsonSchema`, `Serialize`, and `Deserialize`.
- [ ] Every field has a docstring (description for LLM).
- [ ] Type is registered in `omni-types` registry.
- [ ] Python bridge has been updated to include the new type.

---

## 6. Phase 2: Vector/Router Common Schema Contract

**Goal:** One contract for tool_search, vector search, and hybrid search; no legacy `keywords`; CI fails on field drift.

### Contract consistency (P0)

- **Legacy field:** `keywords` is forbidden in all vector/router payloads. Use `routing_keywords` (tool_search only).
- **Parsers:** `parse_tool_search_payload`, `parse_vector_payload`, and `parse_hybrid_payload` all reject payloads that contain the `keywords` field.
- **Shared schemas:** `packages/shared/schemas/`:
  - `omni.vector.tool_search.v1.schema.json` — tool search result (canonical field: `routing_keywords`)
  - `omni.vector.search.v1.schema.json` — single vector search result (`content` = document body; `keywords` forbidden)
  - `omni.vector.hybrid.v1.schema.json` — single hybrid result (same rule)

### E2E snapshot matrix (P0)

Snapshots under `packages/python/foundation/tests/unit/services/snapshots/` lock the following shapes; tests validate them against the JSON schemas so CI fails on drift:

| Snapshot                                   | Schema                        | Purpose                                          |
| ------------------------------------------ | ----------------------------- | ------------------------------------------------ |
| `tool_router_result_contract_v1.json`      | Tool router result (Pydantic) | Route CLI output shape                           |
| `route_test_with_stats_contract_v1.json`   | Route test payload            | `omni route test --json` (query, stats, results) |
| `vector_payload_contract_v1.json`          | omni.vector.search.v1         | Rust bridge vector search output                 |
| `hybrid_payload_contract_v1.json`          | omni.vector.hybrid.v1         | Rust bridge hybrid output                        |
| `db_search_vector_result_contract_v1.json` | list of search.v1             | Db search vector response shape                  |
| `db_search_hybrid_result_contract_v1.json` | list of hybrid.v1             | Db search hybrid response shape                  |

Tests: `test_contract_consistency.py`, `test_vector_schema.py` (snapshot vs schema validation).

---

## Related Documentation

- [Vector/Router Common Schema Contract](vector-router-schema-contract.md) — Field definitions, version rules, no-keywords policy
- [Trinity System Layers](../explanation/system-layering.md)
- [MCP Tool Schema](mcp-tool-schema.md)
- [Rust-Python Bridge](../explanation/rust-python-bridge.md)
