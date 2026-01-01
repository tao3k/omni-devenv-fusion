# Knowledge Base

> Problem-solution knowledge base for MCP tools. Searchable via `consult_*` tools.

## Structure

Each `.md` file contains:
- **Keywords**: Tags for search
- **Symptom**: What the problem looks like
- **Root Cause**: Why it happens
- **Investigation**: How to debug
- **Solution**: Correct approach
- **Wrong Solutions**: Common pitfalls to avoid

## How to Use

When encountering a technical issue:

1. Identify keywords (e.g., "threading", "deadlock", "uv")
2. Search files: `grep -r "keyword" agent/knowledge/`
3. Read matching `.md` file for solution
4. Apply fix

## Available Knowledge

| File | Topic | Keywords |
|------|-------|----------|
| `threading-lock-deadlock.md` | Threading.Lock deadlock in uv run | python, threading, deadlock, uv, fork |
| `uv-workspace-config.md` | UV workspace configuration | uv, workspace, pyproject, dependencies |

## Adding New Knowledge

Create a new `.md` file:

```markdown
# Title of the Problem

> Keywords: tag1, tag2, tag3

## Symptom
```
Error message or behavior
```

## Root Cause
Why this happens...

## Solution
Correct approach with code example

## Related
See: other/related/files.md
```

## MCP Tool Integration

Knowledge base files can be queried by:
- `consult_language_expert` - Language-specific issues
- `consult_specialist` - Architecture/Platform issues
- Future: `consult_knowledge` - Direct knowledge search
