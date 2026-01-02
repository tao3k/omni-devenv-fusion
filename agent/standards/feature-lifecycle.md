# Feature Lifecycle & Integrity Standards

> **Core Principle**: Code is liability; features are assets only if they align with the Design and are robustly tested according to their complexity.

---

## 1. Complexity & Testing Taxonomy

When adding/modifying a feature, classify its complexity to determine the required testing update.

| Level             | Definition                                   | Test Requirements                | Examples                                          |
| :---------------- | :------------------------------------------- | :------------------------------- | :------------------------------------------------ |
| **L1 (Trivial)**  | Typos, config tweaks, doc updates            | **None** (linting only)          | Fix typo, update README, change comment           |
| **L2 (Minor)**    | New utility function, minor tweak            | **+Unit Tests**                  | Add helper function, refactor internal method     |
| **L3 (Major)**    | New module, API, or DB schema change         | **+Unit AND +Integration Tests** | New MCP tool, add API endpoint, DB migration      |
| **L4 (Critical)** | Core logic, Auth, Payments, breaking changes | **+E2E Tests**                   | Auth system, breaking API changes, security fixes |

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

| Question                        | Action                                                                      |
| :------------------------------ | :-------------------------------------------------------------------------- |
| Is this feature in roadmap?     | ✅ Proceed                                                                  |
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

| Language | Standards File                   | MCP Tool                                     |
| -------- | -------------------------------- | -------------------------------------------- |
| Nix      | `agent/standards/lang-nix.md`    | `@omni-orchestrator consult_language_expert` |
| Python   | `agent/standards/lang-python.md` | `@omni-orchestrator consult_language_expert` |
| Rust     | `agent/standards/lang-rust.md`   | `@omni-orchestrator consult_language_expert` |
| Julia    | `agent/standards/lang-julia.md`  | `@omni-orchestrator consult_language_expert` |

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

| If you modify...      | You must update...                                                 |
| :-------------------- | :----------------------------------------------------------------- |
| `mcp-server/*.py`     | Relevant how-to or explanation in `docs/` + update `agent/how-to/` |
| `units/modules/*.nix` | Infrastructure docs                                                |
| `justfile`            | Command documentation in `docs/`                                   |

---

## 4. Spec-Driven Development (Phase 5)

### 4.0 Pre-Implementation Enforcer (MANDATORY)

**BEFORE writing ANY code, you MUST verify:**

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Does a spec exist for this new work?                             │
│    - Call `start_spec(name="Feature Name")` FIRST                   │
│    - Returns "allowed" if spec exists → Proceed                     │
│    - Returns "blocked" if no spec → Create spec first               │
│                                                                      │
│ 2. Is the spec complete?                                            │
│    - Call `verify_spec_completeness()` (auto-detects spec_path)     │
│    - Fix any TODOs/empty sections before proceeding                 │
│                                                                      │
│ 3. Has the user approved the spec?                                  │
│    - Get explicit confirmation before implementation                 │
└─────────────────────────────────────────────────────────────────────┘

**VIOLATION**: Implementing without a verified spec = SYSTEMATIC ERROR
**ACTION**: If you catch yourself about to code without a spec → STOP → start_spec first
```

**Enforced by MCP Tools**:
| Tool | Purpose |
| :--- | :--- |
| `start_spec(name)` | Gatekeeper - checks if spec exists, auto-saves spec_path for downstream |
| `verify_spec_completeness()` | Checks for empty sections, TODOs, missing test plans (auto-detects spec_path) |
| `assess_feature_complexity()` | Requires code diff to determine testing level |

### 4.1 The Spec-First Workflow

Before writing code, Agents must focus on specifications:

```
┌─────────────────────────────────────────────────────────────────┐
│  User Request: "Add caching to MCP server"                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  start_spec(name="Caching Feature")                             │
│  → Checks if spec exists, auto-saves spec_path                  │
│  → "allowed" = proceed, "blocked" = create spec first           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
    Spec exists                            No spec
        ↓                                       ↓
    verify_spec_completeness()          draft_feature_spec(title="...", description="...")
    (auto-detects spec_path)             verify_spec_completeness(spec_path="...")
        ↓                                       ↓
    ┌─────────────────────┐                 ┌─────────────────────┐
    │ Spec complete?      │                 │ Spec complete?      │
    └─────────────────────┘                 └─────────────────────┘
            ↓                                       ↓
    Implement code per spec              Implement code per spec
            ↓                                       ↓
    pytest mcp-server/tests/             pytest mcp-server/tests/
            ↓                                       ↓
    just agent-commit                    just agent-commit
```

### 4.2 Spec Template

Use `agent/specs/template.md` for all new features. Key sections:

| Section               | Purpose                              |
| :-------------------- | :----------------------------------- |
| Context & Goal        | User story, why this feature matters |
| Architecture & Design | Components, data flow, file changes  |
| Implementation Plan   | Step-by-step checklist               |
| Validation Strategy   | Test requirements by complexity      |

---

## 5. MCP Tools for Enforcement

This document is enforced by MCP tools in `mcp-server/orchestrator.py` and `mcp-server/product_owner.py`:

| Tool                          | Purpose                                              |
| :---------------------------- | :--------------------------------------------------- |
| `start_spec(name)`            | Gatekeeper - enforces spec exists before coding      |
| `draft_feature_spec()`        | Creates structured spec from description             |
| `verify_spec_completeness()`  | Checks for empty sections, TODOs (auto-detects path) |
| `assess_feature_complexity()` | LLM-powered analysis → Returns L1-L4 level           |
| `verify_design_alignment()`   | Checks alignment with design/roadmap/philosophy      |
| `get_feature_requirements()`  | Returns complete requirements for a feature          |
| `check_doc_sync()`            | Verifies docs are updated with code changes          |

**Usage**:

```python
# Agent: "I want to add a Redis caching module"

# Step 1: Check if spec exists (GATEKEEPER)
@omni-orchestrator start_spec(name="Redis Caching")
    → Returns: {"status": "blocked", "next_action": "draft_feature_spec"}

# Step 2: Create spec
@omni-orchestrator draft_feature_spec(title="Redis Caching", description="...")
    → Returns: {"status": "success", "spec_path": "agent/specs/redis_caching.md"}

# Step 3: Verify completeness
@omni-orchestrator verify_spec_completeness()  # Auto-detects spec_path!
    → Returns: {"status": "passed"} or {"status": "failed", "issues": [...]}

# Step 4: Assess complexity
@omni-orchestrator assess_feature_complexity code_diff="..." files_changed=["..."]
    → Returns: "L3 (Major) - Requires Unit + Integration Tests"

# Step 5: Verify design alignment
@omni-orchestrator verify_design_alignment feature_description="Redis caching"
    → Returns: Alignment status with references
```

---

## 6. Workflow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  User Request: "Add a new MCP tool for file validation"        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 0: start_spec(name="File Validation")                     │
│  → Returns: "blocked" (no spec exists)                          │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: draft_feature_spec(title="File Validation", ...)       │
│  → Creates spec, returns spec_path                              │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: verify_spec_completeness()                             │
│  → Auto-detects spec_path, checks for empty sections            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: assess_feature_complexity()                            │
│  → Returns: L3 (Major) - New module, requires Integration Tests │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: verify_design_alignment()                              │
│  → Checks: Is this in roadmap? Does it fit architecture?        │
│  → Returns: Alignment status + references                       │
└─────────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
    Aligned?                               Not Aligned?
        ↓                                       ↓
    Implement code                     Update roadmap/design docs
    Add L3 tests                       Then retry Step 4
    Update docs
        ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: check_doc_sync()                                       │
│  → Verifies docs are updated                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Ready for commit: smart_commit() with proper message           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Related Documentation

| Document                                       | Purpose                                   |
| :--------------------------------------------- | :---------------------------------------- |
| `agent/how-to/git-workflow.md`                 | Commit conventions, Agent-Commit Protocol |
| `agent/how-to/testing-workflows.md`            | Test levels, Modified-Code Protocol       |
| `agent/standards/lang-*.md`                    | Language-specific coding standards        |
| `agent/writing-style/01_philosophy.md`         | Feynman clarity, Zinsser humanity         |
| `docs/explanation/mcp-architecture-roadmap.md` | Dual-MCP architecture, lang_expert        |

---

_Built on the principle: "Quality is not an afterthought, it's a foundation."_
