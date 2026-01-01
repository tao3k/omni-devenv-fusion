# Feature Lifecycle & Integrity Standards

> **Core Principle**: Code is liability; features are assets only if they align with the Design and are robustly tested according to their complexity.

---

## 1. Complexity & Testing Taxonomy

When adding/modifying a feature, classify its complexity to determine the required testing update.

| Level | Definition | Test Requirements | Examples |
| :--- | :--- | :--- | :--- |
| **L1 (Trivial)** | Typos, config tweaks, doc updates | **None** (linting only) | Fix typo, update README, change comment |
| **L2 (Minor)** | New utility function, minor tweak | **+Unit Tests** | Add helper function, refactor internal method |
| **L3 (Major)** | New module, API, or DB schema change | **+Unit AND +Integration Tests** | New MCP tool, add API endpoint, DB migration |
| **L4 (Critical)** | Core logic, Auth, Payments, breaking changes | **+E2E Tests** | Auth system, breaking API changes, security fixes |

> **Rule**: If you add an L3 feature but only add L2 tests, the MR is invalid.

---

## 2. Design & Roadmap Alignment

Before implementation, every feature must pass the "Constitution Check":

### 2.1 Philosophy Check

Reference: `design/writing-style/01_philosophy.md`

- Does this align with "Simple is better than complex"?
- Does it follow the "Concrete First" principle (Example → Theory)?
- Is it "Human-readable" as per Zinsser's standards?

### 2.2 Roadmap Check

Reference: `design/*.md` (roadmap or architecture documents)

| Question | Action |
| :--- | :--- |
| Is this feature in roadmap? | ✅ Proceed |
| Is this feature NOT in roadmap? | 🛑 **Stop**. Update roadmap first OR explain why this is a necessary pivot. |

### 2.3 Architecture Fit

Reference: `design/mcp-architecture-roadmap.md`, `design/why-custom-mcp-architecture.md`

- Does it fit the Dual-MCP architecture (Orchestrator + Coder)?
- Does it follow module boundaries?
- Is it in the correct directory?

```
Correct Locations:
- MCP tools → mcp-server/orchestrator.py or coder.py
- Nix modules → units/modules/
- CLI tools → justfile, lefthook.yml
- Documentation → docs/ (user docs), agent/ (LLM context)
```

---

## 3. Reliability Protocol

### 3.0 Language-Specific Standards
Before writing code, consult language-specific standards:

| Language | Standards File | MCP Tool |
|----------|----------------|----------|
| Nix | `agent/standards/lang-nix.md` | `@omni-orchestrator consult_language_expert` |
| Python | `agent/standards/lang-python.md` | `@omni-orchestrator consult_language_expert` |
| Rust | `agent/standards/lang-rust.md` | `@omni-orchestrator consult_language_expert` |
| Julia | `agent/standards/lang-julia.md` | `@omni-orchestrator consult_language_expert` |

**Example Workflow**:
```bash
# Agent: "Add a new Nix module"
@omni-orchestrator consult_language_expert file_path="units/modules/new-module.nix" task="create module with mkNixago"
# Returns: L1 standards + L2 examples from tool-router
```

### 3.1 Test Coverage by Complexity

```
L1 → No test required (linting ok)
L2 → pytest mcp-server/tests/ (pytest, pytest-asyncio)
L3 → pytest mcp-server/tests/ + integration tests
L4 → pytest mcp-server/tests/ + integration tests + manual E2E verification
```

### 3.2 The "Whole Flow" Test

For L3+ features, verify the feature doesn't break upstream/downstream:

```bash
# Regression testing workflow
1. Run affected unit tests
2. Run affected integration tests
3. Verify no breaking changes in dependent modules
```

### 3.3 Documentation Sync

**Rule**: Feature code cannot be merged until `docs/` (user-facing) and `agent/` (LLM context) are updated.

| If you modify... | You must update... |
| :--- | :--- |
| `mcp-server/*.py` | Relevant how-to or explanation in `docs/` + update `agent/how-to/` |
| `units/modules/*.nix` | Infrastructure docs |
| `justfile` | Command documentation in `docs/` |

---

## 4. Spec-Driven Development (Phase 5)

### 4.0 Pre-Implementation Enforcer (MANDATORY)

**BEFORE writing ANY code, you MUST verify:**

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Does a spec exist?                                               │
│    - YES → Use it as the source of truth                            │
│    - NO  → Create `agent/specs/{feature_name}.md` FIRST             │
│                                                                      │
│ 2. Is the spec complete?                                            │
│    - Run `verify_spec_completeness(spec_path="...")`                │
│    - Fix any TODOs/empty sections before proceeding                 │
│                                                                      │
│ 3. Has the user approved the spec?                                  │
│    - Get explicit confirmation before implementation                 │
└─────────────────────────────────────────────────────────────────────┘

**VIOLATION**: Implementing without a verified spec = SYSTEMATIC ERROR
**ACTION**: If you catch yourself about to code without a spec → STOP → Create spec first
```

**Enforced by MCP Tools**:
| Tool | Purpose |
| :--- | :--- |
| `verify_spec_completeness()` | Checks for empty sections, TODOs, missing test plans |
| `assess_feature_complexity()` | Requires code diff to determine testing level |

### 4.1 The Spec-First Workflow

Before writing code, Agents must focus on specifications:

```
┌─────────────────────────────────────────────────────────────────┐
│  User Request: "Add caching to MCP server"                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  just agent-focus agent/specs/caching_feature.md                │
│  → Displays Spec content, code structure, backlog alignment     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Agent creates PLAN in SCRATCHPAD.md                            │
│  → Step-by-step implementation based on Spec                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Implement code per PLAN                                         │
│  → Follow spec sections: Context, Architecture, Implementation  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  pytest mcp-server/tests/test_*.py                              │
│  → Tests follow complexity level (L2-L4)                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  just agent-commit                                              │
│  → Smart commit with auto-fix on hook failures                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Spec Template

Use `agent/specs/template.md` for all new features. Key sections:

| Section | Purpose |
| :--- | :--- |
| Context & Goal | User story, why this feature matters |
| Architecture & Design | Components, data flow, file changes |
| Implementation Plan | Step-by-step checklist |
| Validation Strategy | Test requirements by complexity |

---

## 5. MCP Tools for Enforcement

This document is enforced by MCP tools in `mcp-server/product_owner.py`:

| Tool | Purpose |
| :--- | :--- |
| `assess_feature_complexity()` | LLM-powered analysis → Returns L1-L4 level |
| `verify_design_alignment()` | Checks alignment with design/roadmap/philosophy |
| `get_feature_requirements()` | Returns complete requirements for a feature |
| `check_doc_sync()` | Verifies docs are updated with code changes |

**Usage**:
```python
# Agent: "I want to add a Redis caching module"
@omni-orchestrator assess_feature_complexity code_diff="..." files_changed=["units/modules/redis.nix"]
    → Returns: "L3 (Major) - Requires Unit + Integration Tests"

@omni-orchestrator verify_design_alignment feature_description="Redis caching"
    → Returns: Alignment status with references to design docs
```

---

## 6. Workflow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  User Request: "Add a new MCP tool for file validation"        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: assess_feature_complexity()                            │
│  → Returns: L3 (Major) - New module, requires Integration Tests │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: verify_design_alignment()                              │
│  → Checks: Is this in roadmap? Does it fit architecture?        │
│  → Returns: Alignment status + references                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
    Aligned?                               Not Aligned?
        ↓                                       ↓
    Implement code                     Update roadmap/design docs
    Add L3 tests                       Then retry Step 2
    Update docs
        ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: check_doc_sync()                                       │
│  → Verifies docs are updated                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Ready for commit: smart_commit() with proper message           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Related Documentation

| Document | Purpose |
| :--- | :--- |
| `agent/how-to/git-workflow.md` | Commit conventions, Agent-Commit Protocol |
| `agent/how-to/testing-workflows.md` | Test levels, Modified-Code Protocol |
| `agent/standards/lang-*.md` | Language-specific coding standards |
| `agent/writing-style/01_philosophy.md` | Feynman clarity, Zinsser humanity |
| `docs/explanation/mcp-architecture-roadmap.md` | Dual-MCP architecture, lang_expert |

---

*Built on the principle: "Quality is not an afterthought, it's a foundation."*
