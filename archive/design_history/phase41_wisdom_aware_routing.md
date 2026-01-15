# Phase 41: Wisdom-Aware Routing

**Status**: Implemented
**Type**: Architecture Enhancement
**Owner**: SemanticRouter (The Brain)
**Vision**: From "muscle memory" to "intelligent guidance" - learn from past lessons

## 1. Problem Statement

**The Pain: Blind Routing**

```
User: "Modify tools.py and test it"
Router: "Use git skill" → Executes git status → Wrong tool!
(Lesson was learned: "Use filesystem for file edits, git is for version control")
```

**What's Missing:**

- Router knows WHICH skill to use (Phase 39)
- Router doesn't know LESSONS from past mistakes
- Same errors repeated across sessions
- No "wisdom" extracted from harvested knowledge

**Root Cause:**

Phase 39's FeedbackStore stores implicit learning ("git.status" → git +0.1), but the Router never consults the explicit knowledge base (`harvested/*.md`) for operational wisdom.

## 2. The Solution: Wisdom-Aware Routing

Inject retrieved lessons into the routing prompt so the LLM generates Mission Briefs that avoid known pitfalls:

```
User Query
     ↓
  SemanticRouter.route()
     ↓
  ┌─────────────────────────────────────┐
  │  Parallel:                          │
  │  - Build routing menu               │
  │  - Consult Librarian (harvested/)   │ ← NEW: Retrieve past lessons
  └─────────────────────────────────────┘
     ↓
  System Prompt + PAST LESSONS
     ↓
  LLM generates Mission Brief with:
  - "Use filesystem for file edits"
  - "NOTE: Remember to hot-reload after tools.py changes"
```

## 3. Architecture Specification

### 3.1 Librarian Integration

```python
class SemanticRouter:
    @property
    def librarian(self) -> "Librarian":
        """Lazy Librarian accessor for knowledge retrieval."""
        if self._librarian is None:
            from agent.capabilities.knowledge.librarian import consult_knowledge_base
            self._librarian = consult_knowledge_base
        return self._librarian
```

### 3.2 Parallel Knowledge Retrieval

```python
async def route(self, user_query: str, ...) -> RoutingResult:
    # 1. Parallel: Build menu AND retrieve relevant lessons
    menu_task = self._build_routing_menu()
    knowledge_task = self.librarian(
        query=user_query,
        n_results=3,  # Top 3 relevant lessons
        domain_filter="harvested_insight",  # Only harvested knowledge
    )

    menu_text, knowledge_results = await asyncio.gather(menu_task, knowledge_task)

    # 2. Format lessons for prompt
    lessons_text = self._format_lessons(knowledge_results)

    # 3. Inject into prompt
    system_prompt = f"""...
    AVAILABLE SKILLS:
    {menu_text}

    RELEVANT PAST LESSONS (Must Follow):
    {lessons_text}
    ...
    """
```

### 3.3 Lesson Formatting

```python
def _format_lessons(self, knowledge_results: dict) -> str:
    """Format retrieved lessons for the routing prompt."""
    if not knowledge_results.get("results"):
        return "No relevant past lessons found."

    lines = ["## Historical Lessons (Apply These):"]
    for i, result in enumerate(knowledge_results["results"], 1):
        content = result.get("content", "")[:500]  # Truncate
        title = result.get("metadata", {}).get("title", f"Lesson {i}")
        lines.append(f"\n### {title}")
        lines.append(content)

    return "\n".join(lines)
```

### 3.4 Updated Prompt Structure

```python
system_prompt = f"""You are the Omni Orchestrator. Your job is to:
1. Route user requests to the right Skills
2. Generate a concise MISSION BRIEF with operational wisdom

AVAILABLE SKILLS:
{menu_text}

RELEVANT PAST LESSONS (CRITICAL - Apply These):
{lessons_text}

MISSION BRIEF GUIDELINES:
- Reference relevant lessons from PAST LESSONS section
- If a lesson mentions a pitfall, mention it in constraints
- "Use filesystem skill. IMPORTANT: Previous session noted that
  modifying tools.py requires hot-reload - ensure skill is reloaded."
"""
```

## 4. File Changes

### 4.1 Modified Files

| File                                                             | Change                                                           |
| ---------------------------------------------------------------- | ---------------------------------------------------------------- |
| `packages/python/agent/src/agent/core/router/semantic_router.py` | Add librarian integration, knowledge retrieval, prompt injection |

### 4.2 New Methods

| Method                          | Purpose                             |
| ------------------------------- | ----------------------------------- |
| `_get_librarian()`              | Lazy load Librarian function        |
| `_format_lessons()`             | Format knowledge results for prompt |
| `_inject_lessons_into_prompt()` | Build prompt with lessons           |

## 5. Implementation Plan

### Step 1: Librarian Lazy Loading

- [x] Add `_cached_librarian` global
- [x] Implement `_get_librarian()` function
- [x] Add `librarian` property to SemanticRouter

### Step 2: Knowledge Retrieval

- [x] In `route()`, parallelize knowledge retrieval with menu building
- [x] Call `consult_knowledge_base` with `domain_filter="harvested_insight"`
- [x] Handle graceful fallback if knowledge unavailable

### Step 3: Lesson Formatting

- [x] Implement `_format_lessons()` to extract title + content
- [x] Limit to top 3 most relevant lessons
- [x] Handle empty results gracefully

### Step 4: Prompt Injection

- [x] Add `RELEVANT PAST LESSONS` section to system prompt
- [x] Update Mission Brief guidelines to reference lessons
- [x] Test prompt generation

### Step 5: Testing

- [x] Test knowledge retrieval (with/without harvested insights)
- [x] Test lesson formatting
- [x] Test routing with injected wisdom
- [x] Test graceful degradation

## 6. Success Criteria

1. **Knowledge Injection**: Routing prompt includes lessons from `harvested/`
2. **Relevant Retrieval**: Lessons match user query semantically
3. **Brief Enhancement**: Mission Brief references past lessons
4. **Graceful Fallback**: Works when no knowledge available
5. **Performance**: Parallel retrieval doesn't slow down routing

## 7. Before vs After Comparison

### Before (Phase 40)

```
User: "Edit tools.py and test"
Router: Selects "git" skill (wrong!)
Mission Brief: "Check git status"
Result: Wrong tool, user frustration
```

### After (Phase 41)

```
User: "Edit tools.py and test"
Router: Retrieves lesson "Use filesystem for file edits"
Router: Selects "filesystem" skill (correct!)
Mission Brief: "Edit tools.py using filesystem skill.
  IMPORTANT: Previous session noted that modifying tools.py
  requires hot-reload - ensure skill is reloaded after changes.
  Then run tests to verify the changes."
Result: Correct tool + operational wisdom applied
```

## 8. Example Interaction

**User Query**: "I need to commit my changes"

**Knowledge Retrieved** (from `harvested/*.md`):

```markdown
### Git Commit Workflow Best Practices

- Always run `git_status` first to see what's staged
- Use `git_stage_all` for bulk staging (more reliable than individual staging)
- Review diff before committing
```

**Generated Mission Brief**:

```
Commit staged changes with message 'feat(router): add wisdom-aware routing'.

Steps:
1. Run git_status to verify what's staged
2. Use git_stage_all to ensure all changes are staged
3. Review the diff before proceeding
4. Create commit with the provided message

NOTE: Previous session emphasized using git_stage_all for bulk staging
as individual staging can be unreliable.
```

## 9. Performance Impact

| Metric              | Before     | After                            |
| ------------------- | ---------- | -------------------------------- |
| Routing latency     | ~100-500ms | ~100-600ms (+parallel retrieval) |
| Knowledge retrieval | N/A        | ~50-100ms (parallel)             |
| Brief quality       | Generic    | Context-aware with lessons       |

## 10. Related Documentation

- `docs/explanation/trinity-architecture.md` - Trinity architecture
- `packages/python/agent/src/agent/capabilities/knowledge/librarian.py` - Librarian implementation
- `packages/python/agent/src/agent/capabilities/learning/harvester.py` - Harvester (Phase 39)
- `assets/specs/phase39_self_evolving_feedback_loop.md` - Phase 39 spec
- `assets/specs/phase40_automated_reinforcement_loop.md` - Phase 40 spec
