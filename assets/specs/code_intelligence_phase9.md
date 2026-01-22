# Spec: Code Intelligence (ast-grep Integration)

> **Status**: Approved
> **Complexity**: L3
> **Owner**: @omni-orchestrator

## 1. Context & Goal (Why)

**Code Intelligence** bridges the gap between text-based search and syntactic understanding.

- **Text Search (ripgrep)**: Fast, universal, but context-oblivious
- **Syntax Search (ast-grep)**: Precise, structural, but language-specific

**Goal**: Enable the Agent to perform surgical code refactoring by understanding code structure (AST), not just text patterns.

## 2. Architecture & Interface (What)

### 2.1 Tool Definitions

| Tool          | Binary                                 | Purpose                |
| ------------- | -------------------------------------- | ---------------------- |
| `ast_search`  | `sg run -p <pattern>`                  | Structural code search |
| `ast_rewrite` | `sg run -p <pattern> -r <replacement>` | Safe code refactoring  |

### 2.2 Pattern Syntax (ast-grep)

```python
# Simple pattern
"function_def name:$_"           # Find all functions

# With wildcard
"print($ARGS)"                    # Match print calls with any args
"print($A, $B)"                   # Match print with exactly 2 args

# Conditional
"assign $left = $right where $right: string"  # String assignments only
```

### 2.3 File Changes

| File                   | Action   | Purpose                                           |
| ---------------------- | -------- | ------------------------------------------------- |
| `mcp-server/coder.py`  | Modified | Updated to use `sg` binary, added logging         |
| `mcp-server/router.py` | Modified | Added `ast_search`, `ast_rewrite` to Coder domain |

## 3. Usage Examples

### Search: Find all `print` calls

```json
{
  "tool": "ast_search",
  "arguments": {
    "pattern": "print($ARGS)",
    "lang": "py",
    "path": "mcp-server"
  }
}
```

### Rewrite: Replace `print` with `logger.info`

```json
{
  "tool": "ast_rewrite",
  "arguments": {
    "pattern": "print($MSG)",
    "replacement": "logger.info($MSG)",
    "lang": "py",
    "path": "mcp-server"
  }
}
```

## 4. Verification Plan

### 4.1 Unit Tests (L2)

| Test Case                  | Description                     | Expected                         |
| -------------------------- | ------------------------------- | -------------------------------- |
| `test_ast_search_basic`    | Search for function definitions | Returns matches with file:line   |
| `test_ast_rewrite_dry_run` | Preview refactoring changes     | Shows diff without modifying     |
| `test_pattern_syntax`      | Use wildcard patterns           | Correctly matches multiple forms |

### 4.2 Integration Tests (L3)

| Test Case                  | Description                                    | Expected                          |
| -------------------------- | ---------------------------------------------- | --------------------------------- |
| `test_router_coder_domain` | Router suggests ast tools for refactor queries | Coder domain, ast_search in tools |
| `test_coder_ast_tools`     | Coder has ast_search and ast_rewrite           | Tools registered and callable     |

### 4.3 Acceptance Criteria

- [ ] `sg` command available in devenv shell
- [ ] `ast_search` returns structured results
- [ ] `ast_rewrite` shows preview diff
- [ ] Router routes "refactor" queries to Coder with ast tools
