# Tiered Invocation Strategy: Brain vs. Kernel

> **Category**: ARCHITECTURE | **Date**: 2026-01-30

# Tiered Invocation Strategy: Brain vs. Kernel

## 1. Core Principle

**Claude-Code/Gemini-CLI** acts as the **Brain** (Logic, Reasoning, Code Generation).
**Omni-Dev-Fusion** acts as the **Enhanced Nervous System & Actuators** (Perception, Execution, Safety).

## 2. Decision Matrix: When to Switch?

| Scenario                 | **Host Native (Bash/Read)** | **OmniCell Runner (MCP)**      | **Rationale**                                                    |
| :----------------------- | :-------------------------- | :----------------------------- | :--------------------------------------------------------------- | -------------------- |
| **Single File Read**     | ✅ **Preferred**            | ❌ Avoid                       | Native tools have zero overhead and integrate with host caching. |
| **Simple `ls`**          | ✅ `ls -F` (Small dirs)     | ❌ Avoid                       | Text output is sufficient for <20 files.                         |
| **Complex Search**       | ❌ Text parsing fragile     | ✅ **Preferred** (`sys_query`) | Returns structured JSON. Zero hallucination risk.                |
| **Context Optimization** | ❌ `cat` floods context     | ✅ **Preferred** (Filtering)   | Server-side filtering: `open huge.log                            | where msg =~ 'ERR'`. |
| **Batch Operations**     | ❌ Slow, fragile loops      | ✅ **Preferred** (`sys_batch`) | Transactional Nushell scripts. Atomic execution.                 |
| **Safety Ops**           | ❌ No protection            | ✅ **Preferred** (`sys_exec`)  | Rust AST Shield intercepts dangerous commands (`rm -rf /`).      |

## 3. Interaction Modes

### Mode A: Structured Perception (The "Text-to-Struct" Gap)

- **Host Weakness**: `find .` returns raw text. LLMs often miss lines or misinterpret indentation.
- **Omni Strength**: `sys_query("ls **/*.py | to json")` returns a **JSON Object**. The LLM "receives" data rather than "reading" text.

### Mode B: Server-Side Filtering (Context Conservation)

- **Host Weakness**: Reading a 100MB log file to find 5 errors wastes tokens and memory.
- **Omni Strength**: `sys_query` executes filtering in Rust. Only the 5 relevant lines enter the Context Window.

## 4. Technical Implementation

### Rust Layer (`omni-executor`)

Enforce output formats to ensure clean data handover.

```rust
pub enum ExecutionMode {
    Query,  // Forces "| to json", Read-Only, Side-Effect Free
    Action, // Allows Side-Effects, returns Status/Error JSON
}
```

### Python Layer (MCP Tools)

Explicitly separate tools to guide LLM intent.

- `sys_query(query: str)`: **Perception Tool**. Returns JSON. Best for exploration.
- `sys_exec(script: str)`: **Action Tool**. Transactional execution. Best for batch changes.

## 5. System Prompt Strategy ("The Protocol")

We must explicitly instruct the Host (Claude/Gemini):

> **Omni-Dev System Protocol**
>
> 1. **For Reading**: Use your native `read_file`. It is faster.
> 2. **For Exploring**: Use `sys_query`. You get JSON, preventing context flooding.
>    - _Bad_: `ls -R` (Dumps text)
>    - _Good_: `ls **/*.py | where size < 50kb | to json` (Precise data)
> 3. **For Action**: Use `sys_exec`.
>    - Write transactional Nushell scripts instead of fragile loop chains.

## 6. User Story Example

**Task**: "Rename all passing test files to .verified"

1.  **Brain (Gemini)**: Needs list of files.
2.  **Perception (Omni)**: `sys_query("ls tests/*.py | to json")` -> JSON List.
3.  **Reasoning (Brain)**: "I need to run pytest on each and rename if pass."
4.  **Action (Omni)**: `sys_exec("ls tests/*.py | each { |f| if (pytest $f | complete).exit_code == 0 { mv $f ($f + '.verified') } }")`
5.  **Result**: 100 files processed in 1 atomic call. Zero network round-trips.
