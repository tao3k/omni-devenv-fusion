# MCP Server Guidelines: Persistent Memory Strategy

> **Core Principle**: Prefer MCP for persistent memory unless Claude.md is clearly superior.

---

## 1. Why MCP Is the Preferred Choice for Memory

### 1.1 Memory as a "Swiss Army Knife"

MCP tools provide flexibility that Claude.md cannot match:

| Capability | MCP Tools | Claude.md |
|------------|-----------|-----------|
| Dynamic Query | ✅ Runtime filtering by params | ❌ Full content load |
| Structured Return | ✅ JSON / parsed data | ❌ Raw text |
| Cross-session Persistence | ✅ File system / DB | ❌ Current session only |
| Conditional Logic | ✅ Different content per input | ❌ Static content |
| Version Control | ✅ Tools can evolve | ❌ Manual sync needed |

### 1.2 Real-World Scenario

```bash
# User: "Validate the commit message"

# ❌ Claude.md approach: Load full git-workflow.md (500+ lines)
# Then search for validation rules in context

# ✅ MCP approach: Direct call to validate_commit_message
# Returns structured validation result
```

### 1.3 Performance Difference

- **Claude.md**: Reloads all content every conversation
- **MCP**: Singleton cache + on-demand calls + parsed return

---

## 2. When Claude.md Is Clearly Better

Claude.md remains the "top-level guidance," but excels in these scenarios:

| Scenario | Reason |
|----------|--------|
| Behavioral Rules | "What not to do" matters more than "what to query" |
| Workflow SOP | Multi-step processes need global view |
| Role Definition | System-level roles don't fit into tools |
| First Conversation | Avoid cold-start tool chain breakage |

### 2.1 Decision Boundary

```
When persistent memory is needed, ask yourself:

1. Need dynamic parameters?
   → Yes → MCP
   → No → Claude.md

2. Need structured return?
   → Yes → MCP
   → No → Claude.md

3. Frequently called?
   → Yes → MCP (cache advantage)
   → No → Either, lean toward Claude.md

4. Security/Permissions involved?
   → Yes → MCP (centralized control)
   → No → Claude.md
```

---

## 3. MCP Tool Design Guidelines

### 3.1 Memory Tool Responsibilities

All memory-related MCP tools should:

1. **Singleton Cache**: Like `GitRulesCache`, load rules once only
2. **Layered Return**:
   - Full content (for LLM context)
   - Parsed summary (for downstream tools)
3. **Stateless Query**: Tools don't maintain state; state lives in filesystem

### 3.2 Example: The Right Way

```python
# ✅ Correct: Trigger cache init + return structured data
async def load_git_workflow_memory() -> str:
    _git_rules_cache.get_full_doc()  # Trigger singleton init
    return json.dumps({
        "memory": _git_rules_cache.get_full_doc(),
        "rules_loaded": True
    })

# ❌ Wrong: Reload every time
async def load_git_workflow_memory() -> str:
    content = Path("docs/how-to/git-workflow.md").read_text()
    return content
```

### 3.3 Tool Naming Convention

| Type | Prefix | Example |
|------|--------|---------|
| Load/Read | `load_*` | `load_git_workflow_memory` |
| Validate | `validate_*` | `validate_commit_message` |
| Query | `get_*` | `get_feature_requirements` |
| Execute | `*_operation` | `execute_doc_action` |

---

## 4. Migration Checklist

When considering migrating Claude.md content to MCP tools:

- [ ] Will this knowledge be queried frequently?
- [ ] Need different results based on parameters?
- [ ] Will return be consumed by downstream tools (JSON)?
- [ ] Does this knowledge update often? (MCP tools evolve easier)

If mostly "Yes," use MCP.

---

## 5. Existing MCP Memory Tools Reference

| Tool | Persisted Content | Claude.md Equivalent |
|------|-------------------|----------------------|
| `load_git_workflow_memory` | git-workflow.md | ✅ CLAUDE.md git rules |
| `get_doc_protocol` | Document protocol summary | ✅ docs/*.md |
| `get_feature_requirements` | Complexity requirements | ✅ docs/standards/feature-lifecycle.md |
| `get_language_standards` | Language standards | ✅ docs/standards/lang-*.md |

---

## 6. Anti-Patterns

### 6.1 Don't Do This

```python
# ❌ Return raw file content in MCP (make LLM parse it)
async def get_rules() -> str:
    return Path("docs/how-to/git-workflow.md").read_text()

# ✅ Return parsed structured data
async def get_rules() -> str:
    return json.dumps({
        "valid_types": [...],
        "project_scopes": [...]
    })
```

### 6.2 Don't Do This

```markdown
# ❌ Claude.md with lots of queryable rules
## git-workflow.md rules
type can be: feat, fix, docs, style...
scope can be: nix, mcp, router...

# ✅ Migrate to MCP tool
@omni-orchestrator check_commit_scope scope="mcp"
```

---

## 7. Evolution Path

```
Current State:
├── CLAUDE.md (top-level guidance)
├── docs/*.md (detailed documentation)
└── MCP tools (specific functionality)

Target State:
├── CLAUDE.md (behavioral rules + workflow SOP)
├── MCP tools (all queryable knowledge)
└── docs/*.md (human-readable supplementary docs)
```

---

## 8. Summary

| Question | Answer |
|----------|--------|
| Memory via MCP or Claude.md? | **Prefer MCP** |
| When to use Claude.md? | Behavioral rules, workflow SOP, first-time guidance |
| MCP advantages? | Dynamic, cached, structured, composable |
| When to skip MCP? | Static content, low frequency, security-sensitive |

> **Remember**: MCP is the "API layer" for memory, Claude.md is the "documentation layer" for memory. APIs are more precise and reusable than documentation.
