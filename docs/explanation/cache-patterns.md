# Cache Patterns in Agentic OS

> Understanding how different types of context are loaded and cached in the MCP server.

---

## Overview

The Agentic OS uses a **dual-cache pattern** for context management:

| Cache Type | Source | Purpose | Behavior |
|------------|--------|---------|----------|
| **Protocol Cache** | `agent/how-to/*.md` | Enforce workflow rules | Singleton, load once at startup |
| **Spec Cache** | `agent/specs/*.md` | Feature context for commits | Per-commit, optional loading |

---

## 1. Protocol Cache (Rules & Policies)

### What It Is

Protocol caches store **static project policies** that rarely change:
- Git commit workflow rules (`git-workflow.md`)
- Writing style guidelines (`agent/writing-style/*.md`)
- Language-specific standards (`agent/standards/lang-*.md`)

### Characteristics

| Property | Description |
|----------|-------------|
| **Change Frequency** | Rare (project policy changes) |
| **Loading Pattern** | Singleton, lazy-load once at startup |
| **Access Pattern** | High-frequency reads, no writes |
| **Invalidation** | Process restart required |
| **Scope** | Global to the MCP server |

### Examples

```python
# WritingStyleCache - loads all writing style guides
class WritingStyleCache:
    """Singleton cache for writing style guidelines."""
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_guidelines(self, module: str) -> dict:
        """Get guidelines for a specific module."""
        if not self._loaded:
            self._load_all()
        return self._guidelines.get(module, self._default_guidelines)

# GitWorkflowCache - loads git-workflow.md
class GitWorkflowCache:
    """Singleton cache for git workflow protocol."""
    _instance = None
    _loaded = False

    def get_protocol(self) -> str:
        """Returns: 'stop_and_ask' or 'auto_commit'"""
        if not self._loaded:
            self._load("agent/how-to/git-workflow.md")
        return self._protocol

    def get_rules(self) -> dict:
        """Returns all protocol rules."""
        if not self._loaded:
            self._load("agent/how-to/git-workflow.md")
        return self._rules
```

### When to Use

Use Protocol Cache when you need:
- ✅ Enforce consistent behavior across all operations
- ✅ High-frequency reads (performance critical)
- ✅ Static configuration that rarely changes
- ✅ Global rules (not per-feature)

---

## 2. Spec Cache (Feature Context)

### What It Is

Spec caches store **dynamic feature context** that changes per feature:
- Feature specifications (`agent/specs/feature_name.md`)
- Implementation plans from SCRATCHPAD.md
- Design decisions and requirements

### Characteristics

| Property | Description |
|----------|-------------|
| **Change Frequency** | Per feature implementation |
| **Loading Pattern** | On-demand, per commit |
| **Access Pattern** | Low-frequency, read-once |
| **Invalidation** | Context expiry after commit |
| **Scope** | Per operation/feature |

### Examples

```python
# spec_aware_commit - loads spec at commit time
async def spec_aware_commit(spec_path: str = None) -> str:
    """Generate commit message from Spec + Scratchpad."""
    spec_content = ""
    if spec_path:
        spec_content = Path(spec_path).read_text(encoding="utf-8")

    # Spec is loaded PER COMMIT, not cached globally
    return generate_commit_message(spec_content)
```

### When to Use

Use Spec loading when you need:
- ✅ Context specific to a feature
- ✅ One-time context per operation
- ✅ Dynamic content that changes frequently
- ✅ Optional context (not always needed)

---

## 3. Comparison Table

| Aspect | Protocol Cache | Spec Loading |
|--------|---------------|--------------|
| **Files** | `agent/how-to/*.md`, `agent/writing-style/*.md` | `agent/specs/*.md` |
| **Caching Strategy** | Singleton, lazy-load at startup | On-demand, per operation |
| **Memory Lifetime** | MCP server lifetime | Single commit |
| **Refresh Mechanism** | Process restart | Each call |
| **Use Case** | Rules enforcement | Context injection |
| **Performance** | Optimized for frequent access | One-time read |
| **Examples** | `WritingStyleCache`, `GitWorkflowCache` | `spec_aware_commit()` |

---

## 4. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Server Startup                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Protocol Cache Layer                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ GitWorkflowCache│  │WritingStyleCache│  │ LanguageExpert  │  │
│  │                 │  │                 │  │                 │  │
│  │ git-workflow.md │  │ writing-style/  │  │ lang-*.md       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│                                │                                  │
│                    (Loaded once, cached globally)                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Tool Execution Layer                         │
│                                                                  │
│  ┌──────────────────────┐    ┌──────────────────────┐          │
│  │ smart_commit()       │    │ suggest_commit_msg() │          │
│  │                      │    │                      │          │
│  │ Uses:                │    │ Uses:                │          │
│  │ - GitWorkflowCache   │    │ - cog.toml (config)  │          │
│  │ - Validation rules   │    │ - Optional spec      │          │
│  └──────────────────────┘    └──────────────────────┘          │
│                                                                  │
│  ┌──────────────────────┐    ┌──────────────────────┐          │
│  │ spec_aware_commit()  │    │ polish_text()        │          │
│  │                      │    │                      │          │
│  │ Uses:                │    │ Uses:                │          │
│  │ - Per-commit spec    │    │ - WritingStyleCache  │          │
│  │ - SCRATCHPAD.md      │    │                      │          │
│  └──────────────────────┘    └──────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Implementation Checklist

### Protocol Cache Checklist

- [ ] Load file at startup (lazy, once)
- [ ] Use singleton pattern (`_instance`, `_loaded`)
- [ ] Provide `get_*()` methods for rules
- [ ] Thread-safe access (if needed)
- [ ] Document cache location and refresh mechanism

### Spec Loading Checklist

- [ ] Load file on-demand (per operation)
- [ ] No global caching (context expires)
- [ ] Handle missing files gracefully
- [ ] Truncate large content (2000 chars limit)
- [ ] Optional loading (spec_path can be null)

---

## 6. Related Documentation

| Document | Purpose |
|----------|---------|
| `agent/how-to/git-workflow.md` | Git commit protocol, "Stop and Ask" rule |
| `agent/writing-style/*.md` | Writing style guidelines |
| `agent/specs/template.md` | Feature spec template |
| `mcp-server/git_ops.py` | Git workflow MCP tools |

---

*Last updated: 2024-12-31*
