# Omni Types

> Common type definitions for Omni DevEnv.

## Overview

This crate provides shared data structures used across all Omni crates. All types are designed to be serialization-compatible with Python and other languages.

## Key Types

### ToolRecord

```rust
pub struct ToolRecord {
    pub name: String,
    pub description: String,
    pub category: String,
    pub parameters: Option<JsonObject>,
}
```

### Context Types

- `ContextLevel` - Hierarchical context levels
- `SkillContext` - Skill-specific context data
- `AgentContext` - Full agent execution context

## License

Apache-2.0
