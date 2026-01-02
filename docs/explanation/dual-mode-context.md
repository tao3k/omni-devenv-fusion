# Dual-Mode Context System

> Project context delivery for Agentic OS MCP server.

## Overview

The dual-mode system provides two ways to deliver project-specific context:

| Mode        | Purpose                             | Trigger                           | Content                              |
| ----------- | ----------------------------------- | --------------------------------- | ------------------------------------ |
| **Passive** | Project conventions for development | Lazy-loaded at MCP server startup | UV, Nix, code style, architecture    |
| **Active**  | On-demand expert consultation       | `consult_language_expert` tool    | Standards, examples, project context |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Dual-Mode Context System                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────┐     ┌──────────────────────┐         │
│  │   Passive Mode       │     │    Active Mode       │         │
│  │   (Lazy Load)        │     │    (Consult)         │         │
│  │                      │     │                      │         │
│  │  ┌────────────────┐  │     │  ┌────────────────┐  │         │
│  │  │ project_context│  │     │  │consult_        │  │         │
│  │  │     .py        │  │     │  │language_expert │  │         │
│  │  │                │  │     │  │                │  │         │
│  │  │ - PythonContext│  │     │  │ - Get language │  │         │
│  │  │ - NixContext   │  │     │  │ - Get standards│  │         │
│  │  └────────────────┘  │     │  │ - Query examples│  │         │
│  │         │            │     │  └────────────────┘  │         │
│  │         ▼            │     │         │            │         │
│  │  ┌────────────────┐  │     │         ▼            │         │
│  │  │ Cached in      │  │     │  ┌────────────────┐  │         │
│  │  │ _PROJECT_      │  │     │  │ Return JSON    │  │         │
│  │  │ CONTEXT dict   │  │     │  │ with context   │  │         │
│  │  └────────────────┘  │     │  └────────────────┘  │         │
│  │                      │     │                      │         │
│  │  Loaded once per     │     │  Triggered per       │         │
│  │  MCP session         │     │  tool call           │         │
│  └──────────────────────┘     └──────────────────────┘         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Passive Mode (Lazy Load)

### How It Works

1. MCP server starts
2. `project_context.py` is imported
3. `ContextRegistry.initialize_all()` is called at startup
4. All contexts are loaded and cached in memory
5. Subsequent operations use cached values

### Usage

```python
# Automatic - context is always available
from mcp_core.project_context import get_project_context

# Get all Python context
python_ctx = get_project_context("python")

# Get specific category
tooling = get_project_context("python", category="tooling")
patterns = get_project_context("python", category="patterns")
```

### Available Contexts

| Language | Categories                                   |
| -------- | -------------------------------------------- |
| Python   | tooling, patterns, architecture, conventions |
| Nix      | tooling, patterns, architecture, conventions |

### Adding New Language

````python
from mcp_core.project_context import ProjectContext, ContextRegistry

class GoContext(ProjectContext):
    LANG_ID = "go"
    CATEGORIES = ["tooling", "patterns", "architecture", "conventions"]

    def _load_tooling(self) -> str:
        return """## 🛠️ Go Tooling

- Use `go mod` for dependency management
- `go fmt` for formatting
- `go test` for testing"""

    def _load_patterns(self) -> str:
        return """## 🔄 Common Patterns

### Error Handling
```go
if err != nil {
    return fmt.Errorf("failed: %w", err)
}
```"""

ContextRegistry.register(GoContext())
````

## Active Mode (Consult)

### How It Works

1. Agent calls `consult_language_expert` tool
2. Tool detects language from file extension
3. Loads relevant context from multiple sources:
   - L1a: Language standards (`agent/standards/lang-*.md`)
   - L1b: Project context (`mcp_core/project_context.py`)
   - L2: Examples (`tool-router/data/examples/*.jsonl`)
4. Returns combined context as JSON

### Usage

```python
# In Claude code
@omni-orchestrator consult_language_expert \
    file_path="mcp-server/git_ops.py" \
    task="implement singleton pattern"
```

### Response Structure

```json
{
  "status": "complete",
  "language": "Python",
  "file": "mcp-server/git_ops.py",
  "task": "implement singleton pattern",
  "sources": {
    "standards": "agent/standards/lang-python.md",
    "examples": "tool-router/data/examples/python.edit.jsonl",
    "project_context": "mcp_core/project_context.py (python)"
  },
  "project_context": "## 🛠️ Tooling (UV + Nix)\n\n...",
  "standards": "### Type Hints (Mandatory)\n\n...",
  "examples": "### 💡 Relevant Examples (Case Law)\n\n..."
}
```

## Comparison

| Aspect          | Passive Mode            | Active Mode           |
| --------------- | ----------------------- | --------------------- |
| **Trigger**     | MCP server startup      | Tool call             |
| **Content**     | All project conventions | Task-relevant subset  |
| **Updates**     | Requires restart        | Updates automatically |
| **Use Case**    | General development     | Specific problems     |
| **Performance** | Cached, fast            | On-demand, slower     |

## Integration Points

### MCP Server Startup

```python
# orchestrator.py
from mcp_core.project_context import initialize_project_contexts

# Preload all project contexts
initialize_project_contexts()
log_decision("project_contexts.initialized", {}, logger)
```

### Tool Registration

```python
# lang_expert.py
from mcp_core.project_context import get_project_context, has_project_context

@mcp.tool()
async def consult_language_expert(
    file_path: str,
    task_description: str,
    include_project_context: bool = True
) -> str:
    # Get language from file extension
    lang = detect_language(file_path)

    # Load project context (lazy-loaded)
    if include_project_context and has_project_context(lang):
        project_ctx = get_project_context(lang)
        result["project_context"] = project_ctx

    # ... rest of implementation
```

## File Structure

```
mcp-server/
├── mcp_core/
│   ├── __init__.py              # Exports: get_project_context, etc.
│   ├── project_context.py       # Framework: ProjectContext, ContextRegistry
│   ├── lazy_cache.py            # Singleton cache utilities
│   ├── memory.py                # Project memory
│   ├── inference.py             # LLM client
│   └── utils.py                 # Logging, path checking
├── lang_expert.py               # MCP tool: consult_language_expert
├── dual-mode-context.md         # This documentation
└── ...
```

## Best Practices

### 1. Use Passive Mode for

- General coding conventions
- Tooling setup (UV, Nix, ruff)
- Architecture patterns
- Error handling rules

### 2. Use Active Mode for

- Specific coding tasks
- Syntax questions
- Pattern selection
- Complex refactoring

### 3. Keep Contexts Updated

When adding new patterns or conventions:

1. Update the relevant `_load_*()` method in `project_context.py`
2. Test with `just test-mcp`
3. No restart needed (cache auto-reloads on next access)

## Related Documentation

- `agent/standards/lang-python.md` - Python language standards
- `agent/writing-style/*.md` - Writing style guidelines
- `tool-router/data/examples/*.jsonl` - Code examples
