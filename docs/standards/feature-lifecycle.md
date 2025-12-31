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
- Documentation → docs/, design/
```

---

## 3. Reliability Protocol

### 3.0 Language-Specific Standards
Before writing code, consult language-specific standards:

| Language | Standards File | MCP Tool |
|----------|----------------|----------|
| Nix | `docs/standards/lang-nix.md` | `@omni-orchestrator consult_language_expert` |
| Python | `docs/standards/lang-python.md` | `@omni-orchestrator consult_language_expert` |
| Rust | `docs/standards/lang-rust.md` | `@omni-orchestrator consult_language_expert` |
| Julia | `docs/standards/lang-julia.md` | `@omni-orchestrator consult_language_expert` |

**Example Workflow**:
```bash
# Agent: "Add a new Nix module"
@omni-orchestrator consult_language_expert file_path="units/modules/new-module.nix" task="create module with mkNixago"
# Returns: L1 standards + L2 examples from tool-router
```

### 3.1 Test Coverage by Complexity

```
L1 → No test required (linting ok)
L2 → just test-unit (or pytest mcp-server/tests/)
L3 → just test-unit + just test-int
L4 → just test-unit + just test-int + manual E2E verification
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

**Rule**: Feature code cannot be merged until `docs/` are updated.

| If you modify... | You must update... |
| :--- | :--- |
| `mcp-server/*.py` | Relevant how-to or explanation in `docs/` |
| `units/modules/*.nix` | Infrastructure docs |
| `justfile` | Command documentation in `docs/` |

---

## 4. MCP Tools for Enforcement

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

## 5. Workflow Summary

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
| `docs/how-to/git-workflow.md` | Commit conventions, Agent-Commit Protocol |
| `docs/how-to/testing-workflows.md` | Test levels, Modified-Code Protocol |
| `docs/standards/lang-*.md` | Language-specific coding standards |
| `design/writing-style/01_philosophy.md` | Feynman clarity, Zinsser humanity |
| `design/mcp-architecture-roadmap.md` | Dual-MCP architecture, lang_expert |

---

*Built on the principle: "Quality is not an afterthought, it's a foundation."*
