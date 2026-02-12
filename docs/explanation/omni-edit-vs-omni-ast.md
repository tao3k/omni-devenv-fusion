# Omni-Edit vs Omni-AST: Technical Responsibilities

> Based on codebase analysis, `omni-edit` and `omni-ast` are two Rust crates in the Omni-Dev Fusion architecture with distinct but closely collaborating responsibilities.

Simply put: **`omni-ast` is the "eyes and brain" (responsible for understanding code structure), while `omni-edit` is the "scalpel" (responsible for precise text modification).**

---

## 🔍 Omni-AST

**Positioning: Code Structure Analysis and Understanding Engine**

Its core task is to **"understand"** the code, rather than seeing it as a pile of characters. It uses AST (Abstract Syntax Tree) to parse the grammatical structure of the code.

### Core Responsibilities

- **Parsing**: Uses `tree-sitter` to parse source code into a syntax tree.
- **Extraction**: Identifies and extracts high-level semantic structures such as functions, classes, imports, and decorators.
- **Navigation**: Answers questions like "Where is the `User` class defined?" or "What is the end line of the `main` function?".
- **Multi-language Support**: Supports syntax differences of different programming languages through `lang.rs` and adapters (such as `python.rs`).

### Input and Output

| Type                | Description                                                                                                    |
| :------------------ | :------------------------------------------------------------------------------------------------------------- |
| **Input**           | Source code string                                                                                             |
| **Output**          | Structured data (e.g., `FunctionItem`, `ClassItem`), including name, parameters, docstrings, byte ranges, etc. |
| **Underlying Tech** | `tree-sitter`                                                                                                  |

### Core Modules

- `lib.rs`: Main entry and public API.
- `lang.rs`: Language detection and selection.
- `extractor.rs`: Symbol extractor (`TagExtractor`).
- `patterns.rs`: `ast-grep` pattern definitions.
- `types.rs`: Types such as `SymbolKind`, `Symbol`, `SearchMatch`.
- `error.rs`: Error handling.

---

## 🛠️ Omni-Edit

**Positioning: Atomic Text Operation and Editing Engine**

Its core task is to **"modify"** text, ensuring that editing operations are safe, atomic, and reversible. It doesn't care if the text is Python code or a novel; it only cares about line numbers, byte offsets, and string replacements.

### Core Responsibilities

- **Buffer Management**: Efficiently loads and operates on text content in memory.
- **Atomic Operations**: Supports transactional editing (Transactions), such as "modify line 10 and line 50 at the same time, either both succeed or both fail".
- **Diffing**: Generates Unified Diff patches for showing modification previews.
- **Applying Edits**: Executes specific Insert, Delete, and Replace operations.

### Input and Output

| Type                | Description                                                                                                 |
| :------------------ | :---------------------------------------------------------------------------------------------------------- |
| **Input**           | Source code string + editing instructions (e.g., `Replace(start=10, end=20, text="new_code")`)              |
| **Output**          | Modified new code string, Diff text                                                                         |
| **Underlying Tech** | Custom Rope or line vector structure (for efficient text processing), similar to text editor backend logic. |

### Core Modules

- `lib.rs`: Main entry and public API.
- `editor.rs`: Core implementation of `StructuralEditor`.
- `batch.rs`: Batch editing engine (The Ouroboros).
- `types.rs`: `EditConfig`, `EditLocation`, `EditResult`.
- `capture.rs`: Variable capture and replacement (`$NAME`, `$$$`).
- `diff.rs`: Unified Diff generation.
- `error.rs`: `EditError`.

---

## Core Comparison Table

| Feature               | omni-ast (Understanding Layer)                 | omni-edit (Operation Layer)                     |
| :-------------------- | :--------------------------------------------- | :---------------------------------------------- |
| **Perspective**       | **Structural** (Functions, Classes, Variables) | **Textual** (Lines, Columns, Bytes, Characters) |
| **Capability**        | Read-Only (Analysis and Queries)               | Read/Write (CRUD)                               |
| **Typical Operation** | "Find start and end of function `run`"         | "Replace lines 5 to 10 with `pass`"             |
| **Error Types**       | Parsing Error (Syntax Error)                   | Out of Bounds (Index Out of Bounds)             |
| **Dependencies**      | `tree-sitter`                                  | `similar` (for Diff), Standard Library I/O      |

---

## The Workflow

In **Structural Refactoring** scenarios, the two collaborate as follows:

### Scenario: Change all `print(x)` to `logger.info(x)`

1. **User Instruction**: "Change all `print(x)` to `logger.info(x)`"
2. **Step 1 (`omni-ast`)**:
   - Agent calls `omni-ast`.
   - `omni-ast` parses code, finding all AST nodes for `print` function calls.
   - Returns a list of position information.
3. **Step 2 (Python Logic Layer)**:
   - The Skill in the Python layer receives the position information.
   - Generates replacement text `logger.info(a)`.
   - Constructs a `BatchEdit` request.
4. **Step 3 (`omni-edit`)**:
   - Agent passes source code and `BatchEdit` request to `omni-edit`.
   - `omni-edit` checks for conflicts (e.g., overlapping ranges).
   - `omni-edit` executes replacements, generating the final code string.

### Sequence Diagram

```
┌─────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────┐
│  User   │     │ Python Skill │     │  omni-ast   │     │ omni-   │
│         │     │              │     │             │     │ edit    │
└────┬────┘     └──────┬───────┘     └──────┬──────┘     └────┬────┘
     │                 │                     │                 │
     │ "print→logger"  │                     │                 │
     │────────────────>│                     │                 │
     │                 │  find_calls("print")│                 │
     │                 │────────────────────>│                 │
     │                 │  [{pos, content}]   │                 │
     │                 │<────────────────────│                 │
     │                 │  build_batch_edit() │                 │
     │                 │          │          │                 │
     │                 │          ▼          │                 │
     │                 │  apply_edits(src,   │                 │
     │                 │              batch) │                 │
     │                 │───────────────────────────────────────>
     │                 │                 │      new_src + diff │
     │                 │<───────────────────────────────────────
     │                 │                     │                 │
     │  new_code       │                     │                 │
     │<────────────────│                     │                 │
```

## Summary

| Question                      | Answer                                                        |
| :---------------------------- | :------------------------------------------------------------ |
| What does `omni-ast` answer?  | **Where** - "Where to change?" (finding target locations)     |
| What does `omni-edit` answer? | **How** - "How to change?" (executing specific operations)    |
| Relationship?                 | `omni-ast` provides coordinates, `omni-edit` executes changes |

**`omni-ast` tells us where to change, and `omni-edit` is responsible for how to change.**
