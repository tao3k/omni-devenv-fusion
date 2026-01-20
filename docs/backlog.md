# Omni-Dev-Fusion Backlog

> Feature-based task tracking. No phases, just priorities.

---

## Legend

| Status        | Meaning                  |
| ------------- | ------------------------ |
| `Todo`        | Not started              |
| `In Progress` | Actively being worked on |
| `Blocked`     | Waiting on dependencies  |
| `Done`        | Completed                |

---

## High Priority

### Skill Ecosystem Standardization

After refactoring the core (`LoopState`, `ActionGuard`, `AdaptivePlanner`), existing skills need to align with the new architecture.

**Goal**: Ensure new skills created via `omni skill create` have proper schema metadata, and existing skills follow the new conventions.

| Task                       | Status | Description                                                                                  |
| -------------------------- | ------ | -------------------------------------------------------------------------------------------- |
| **Upgrade Skill Template** | `Todo` | Add schema fields (`require_refs`, `routing_keywords`) to `assets/skills/_template/SKILL.md` |
| **Add Guard Tests**        | `Todo` | Create `test_omni_guards.py` to verify `ActionGuard` blocks redundant reads                  |
| **Cleanup Writer Skill**   | `Todo` | Remove outdated "self-validation" instructions, emphasize "Trust the Context"                |
| **Verify All Skills**      | `Todo` | Run skill validation to ensure compatibility with new architecture                           |

**Related Files:**

- `assets/skills/_template/SKILL.md`
- `assets/skills/writer/SKILL.md`
- `packages/python/agent/src/agent/core/omni/interceptors.py`
- `packages/python/agent/src/agent/tests/unit/test_omni_guards.py`

---

## Medium Priority

### Schema-Driven Security

Implement permission boundaries for skills before allowing external/untrusted tools.

| Task                         | Status | Description                                                                  |
| ---------------------------- | ------ | ---------------------------------------------------------------------------- |
| **Define Permission Schema** | `Todo` | Design YAML schema for skill permissions (`fs:read`, `fs:write`, `net:http`) |
| **Permission Validator**     | `Todo` | Build `security/validator.py` to enforce permission boundaries               |
| **Integration Tests**        | `Todo` | Add tests for permission enforcement scenarios                               |

**Related Files:**

- `packages/python/agent/src/agent/core/security/`
- `assets/schemas/`

---

### Context Optimization

Reduce token usage in the CCA loop without losing context quality.

| Task                          | Status | Description                                                 |
| ----------------------------- | ------ | ----------------------------------------------------------- |
| **Smart Context Trimming**    | `Todo` | Implement tiered context (must-have vs nice-to-have layers) |
| **Vector Index Optimization** | `Todo` | Fine-tune LanceDB index parameters for faster retrieval     |
| **Compression Pipeline**      | `Todo` | Add message compression for long conversations              |

**Related Files:**

- `packages/python/agent/src/agent/core/context_orchestrator/`
- `packages/python/agent/src/agent/core/vector_store/`

---

## Low Priority

### Developer Experience

Improvements that make development easier but aren't blocking core functionality.

| Task                    | Status | Description                                          |
| ----------------------- | ------ | ---------------------------------------------------- |
| **Skill Generator CLI** | `Todo` | Interactive CLI for creating new skills with prompts |
| **Hot Reload Logs**     | `Todo` | Improve logging for skill hot-reload events          |
| **Dashboard Metrics**   | `Todo` | Real-time dashboard for session metrics              |
| **Tutorial: New Skill** | `Todo` | Step-by-step guide for creating a custom skill       |

---

## Completed

| Feature                    | Date       | Notes                                   |
| -------------------------- | ---------- | --------------------------------------- |
| **Core Omni Refactoring**  | 2026-01-19 | LoopState, ActionGuard, AdaptivePlanner |
| **Anti-Confusion Loop**    | 2026-01-19 | Prevents repeated file reads            |
| **Adaptive Planning**      | 2026-01-18 | Dynamic step estimation                 |
| **NoteTaker Optimization** | 2026-01-18 | Token reduction from 4000 to 500        |

---

## How to Use This Backlog

1. **Pick a task** from High Priority
2. **Create a branch** with descriptive name: `feature/skill-template-update`
3. **Complete the work** with tests
4. **Update this file** to mark as `Done` with date
5. **Commit** with: `docs(backlog): complete Skill Ecosystem Standardization`

---

_Built on standards. Not reinventing the wheel._
