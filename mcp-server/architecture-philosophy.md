# Architecture Philosophy: Dual-MCP & Knowledge Organization

> Date: 2024-12-31
> Author: Claude (Human: tao3k)
> Status: Implemented

## Core Philosophy

**Separation of Concerns**: Strategy vs. Tactics

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator (Strategy)               │
│  • SDLC Coordination                                    │
│  • Architecture Decisions                               │
│  • SRE/Platform Expertise                               │
│  • Delegates to specialists                             │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Delegates
                          ▼
┌─────────────────────────────────────────────────────────┐
│                      Coder (Tactics)                    │
│  • Surgical Coding                                      │
│  • AST Refactoring                                      │
│  • File Operations                                      │
│  • Executes delegated tasks                             │
└─────────────────────────────────────────────────────────┘
```

## Dual-MCP Pattern

See `mcp-server/dual-mode-context.md` for detailed implementation.

## The Cortex (Phase 6: Tool Router)

**The Cortex** is the Orchestrator's "metacognitive" layer - it knows which tools to use for a given task.

```
┌─────────────────────────────────────────────────────────┐
│                   The Cortex (router.py)                 │
│  Intent Classification → Tool Domain Mapping            │
│  "What should I use to create a login feature?"         │
│  → ProductOwner Domain                                  │
└─────────────────────────────────────────────────────────┘
                          │
                          │ consult_router()
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Tool Domains                          │
├──────────┬──────────┬──────────┬──────────┬────────────┤
│ GitOps   │ProductOwner│  Coder  │ QA       │ DevOps     │
│ commits  │ specs    │ code     │ review   │ nix        │
│ history  │ requir.  │ files    │ tests    │ infra      │
└──────────┴──────────┴──────────┴──────────┴────────────┘
```

**Benefits:**

- **Token Optimization**: Only relevant tool schemas sent to LLM
- **Reduced Confusion**: Clear tool selection guidance
- **Extensibility**: Add new domains without modifying core logic

## The Immune System (Phase 7: Code Review)

**The Immune System** is the Orchestrator's quality gate - it prevents low-quality code from entering the codebase.

```
┌─────────────────────────────────────────────────────────┐
│              The Immune System (reviewer.py)             │
│  1. Load Standards (agent/standards/*)                   │
│  2. Get Staged Diff (git diff --cached)                 │
│  3. AI Review against Standards                         │
│  4. APPROVE / REQUEST CHANGES                           │
└─────────────────────────────────────────────────────────┘
                          │
                          │ review_staged_changes()
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Quality Gate                          │
│  Coder → git add → review_staged_changes →              │
│    ❌ REQUEST CHANGES → Coder Fix → git add             │
│    ✅ APPROVE → run_tests → smart_commit                │
└─────────────────────────────────────────────────────────┘
```

**Checks:**

- **Style**: Language standards compliance
- **Safety**: Security vulnerabilities
- **Clarity**: Naming, complexity, duplication
- **Docs**: Docstrings and comments

### Practical Workflow

See `mcp-server/README.md` → "Practical Scenario: From Intent to Commit" for a step-by-step example of how The Cortex and The Immune System work together in a real development workflow.

## Phase 8: Singularity (Bootstrapping / Self-Evolution)

**The Singularity** is the moment when the Agentic OS becomes self-improving - it can safely modify its own codebase without human intervention.

```
┌─────────────────────────────────────────────────────────┐
│              The Singularity (Self-Evolution)            │
│  1. Human gives high-level goal                         │
│  2. Cortex routes to ProductOwner → Draft Spec          │
│  3. Coder implements → Immune System reviews            │
│  4. Tests validate → Smart Commit commits               │
│  5. System is now extended with new capability!         │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Self-Modification
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  The Agentic OS Kernel                   │
│  • Cortex (Phase 6): Intent routing                     │
│  • Immune System (Phase 7): Quality gate                │
│  • Singularity (Phase 8): Self-improvement              │
└─────────────────────────────────────────────────────────┘
```

**The Graduation Test**:
When you can give the Agent this prompt and it successfully adds a new capability:

```
"Orchestrator, add a high-performance code search tool called search_project_code
that uses ripgrep. Follow the full Agentic Workflow: spec, implement, review, test, commit."
```

**What Happens**:

1. 🧠 Cortex routes to ProductOwner → Spec is drafted
2. 📋 Spec is verified → Coder receives implementation task
3. 💻 Coder creates `advanced_search.py` → Registers in `orchestrator.py`
4. 🛡️ Immune System reviews → APPROVE
5. 🧪 Tests pass → Smart Commit

**Key Insight**: The Agent is no longer just executing tasks - it's extending itself.

---

**See Also**:

- `agent/specs/advanced_search_tool.md` - Example of a Phase 8 implementation spec

## Phase 9: Code Intelligence (ast-grep Integration)

**Code Intelligence** bridges the gap between text-based search and syntactic understanding using `ast-grep`.

```
┌─────────────────────────────────────────────────────────┐
│              Code Intelligence (ast-grep)               │
│  Text Search vs Syntax Search                           │
│  ─────────────────────────────────────────────────      │
│  ripgrep: Fast, universal, context-oblivious            │
│  ast-grep: Precise, structural, language-specific       │
└─────────────────────────────────────────────────────────┘
                          │
                          │ ast_search / ast_rewrite
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Tool Capabilities                     │
├─────────────────────────────────────────────────────────┤
│  ast_search: Query code by AST structure                │
│    - "Find all function definitions"                    │
│    - "Find all try-except blocks"                       │
│    - Wildcard patterns: "print($ARGS)"                  │
├─────────────────────────────────────────────────────────┤
│  ast_rewrite: Safe structural refactoring               │
│    - "Replace print with logger.info"                   │
│    - Preview before applying (--dry-run)                │
│    - Zero false positives                               │
└─────────────────────────────────────────────────────────┘
```

**Pattern Syntax (ast-grep)**:

```python
# Simple pattern
"def $NAME"                       # Find all function definitions
"async def $NAME"                 # Find async functions
"if $COND:"                       # Find if statements
"print($ARGS)"                    # Match print calls with any args
"import $MODULE"                  # Find import statements

# Note: ast-grep uses $VAR for wildcards, not pattern:kind syntax
```

**Comparison with ripgrep**:
| Aspect | ripgrep (Phase 8) | ast-grep (Phase 9) |
|--------|-------------------|-------------------|
| Speed | Fastest | Fast |
| Context | Oblivious | Structural |
| Precision | May have false positives | Zero false positives |
| Languages | All | Language-specific |
| Use Case | General search | Refactoring |

**Practical Example**:

```json
// Find all async function definitions
{"tool": "ast_search", "arguments": {
  "pattern": "function_def kind:async name:$_",
  "lang": "py",
  "path": "mcp-server"
}}

// Replace print with logger.info
{"tool": "ast_rewrite", "arguments": {
  "pattern": "print($MSG)",
  "replacement": "logger.info($MSG)",
  "lang": "py",
  "path": "mcp-server"
}}
```

**See Also**:

- `agent/specs/code_intelligence_phase9.md` - Phase 9 specification
- `mcp-server/tests/stress/` - Modular stress test framework

## Phase 9+: Stress Test Framework

**Modular testing system for performance, logic depth, and stability:**

```
mcp-server/tests/stress/
├── __init__.py           # Core: Config, Runner, Reporter
├── core/fixtures.py      # Pytest fixtures
└── suites/
    ├── phase9.py         # Phase 9 tests
    └── template.py       # Phase X template
```

**Test Categories:**

- **Benchmarks**: Performance measurement (ast-grep search/rewrite speed)
- **Logic Tests**: Pattern detection accuracy (Silent Killer detection)
- **Stability Tests**: Chaos engineering (malformed syntax, edge cases)

**Run:** `just stress-test`

**Extensibility:** Copy `template.py` to create Phase 10+ suites.

## Router-Augmented Coding (RAC)

**Three-Tier Knowledge System**:

```
┌─────────────────────────────────────────────────────────┐
│  L1: Standards (agent/standards/lang-*.md)             │
│  - Language-specific conventions                        │
│  - Best practices                                       │
│  - Anti-patterns to avoid                               │
└─────────────────────────────────────────────────────────┘
                          │
                          │ consult_language_expert
                          ▼
┌─────────────────────────────────────────────────────────┐
│  L2: Case Law (tool-router/data/examples/*.jsonl)      │
│  - Real-world examples                                  │
│  - Context-specific patterns                            │
│  - Few-shot learning                                    │
└─────────────────────────────────────────────────────────┘
                          │
                          │ LLM reasoning
                          ▼
┌─────────────────────────────────────────────────────────┐
│  L3: Execution (Coder MCP tools)                        │
│  - Read/Write/Refactor operations                       │
│  - AST-based structural changes                         │
│  - Safe sandbox execution                               │
└─────────────────────────────────────────────────────────┘
```

## Documentation Organization Principle

### The 5-Bucket Model

| Directory          | Content Type                       | Queryable By          |
| ------------------ | ---------------------------------- | --------------------- |
| `agent/standards/` | **公共标准** - 语言/框架无关的规范 | `consult_*` loads all |
| `agent/knowledge/` | **问题解决方案** - 症状→原因→修复  | `consult_*` searches  |
| `agent/specs/`     | **功能规格** - What to build       | `draft_feature_spec`  |
| `agent/how-to/`    | **操作指南** - How to do X         | `execute_doc_action`  |
| `design/`          | **设计决策** - Why we chose X      | Human reference       |

## problem-solving.md Philosophy

**定位**: 思维方式 (Thinking Method)，不是具体问题的解决方案

| ✅ Should Contain        | ❌ Should NOT Contain      |
| ------------------------ | -------------------------- |
| 调试协议 (Rule of Three) | Python 特定 threading 问题 |
| 问题诊断流程             | UV workspace 配置细节      |
| 纠错能力培养             | 特定语言的 import 冲突     |
| 工具使用心智模型         | 具体错误消息的解决方案     |

## knowledge/ Philosophy

**定位**: 可搜索的问题-解决方案知识库，MCP 工具可以查询

```markdown
# Title of the Problem

> Keywords: tag1, tag2, tag3 ← MCP search target

## Symptom

## Root Cause

## Solution

## Wrong Solutions ← Critical: anti-patterns to avoid

## Related
```

### Why Keywords?

- `consult_language_expert` can search by language tag
- `consult_specialist` can search by domain tag
- Enables **Router-Augmented Coding**
