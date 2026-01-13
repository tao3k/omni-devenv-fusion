# Phase 44: The Experiential Agent

**Status**: Implemented
**Date**: 2025-01-13
**Related**: Phase 43 (Holographic Agent), Phase 36 (Memory System)

## Overview

Phase 44 extends the Holographic Agent with **Skill-Level Episodic Memory**. While Phase 43 gave the agent "holographic vision" (seeing the environment), Phase 44 gives it "experiential wisdom" (learning from past mistakes).

## The Problem

**Before Phase 44**: Agent has no institutional memory

- Agent makes the same mistakes repeatedly
- Hard-won lessons from one session are lost in the next
- Each task is approached as if it's the first time ever

```
Agent: "I'll try git commit without staging first..."
Result: Fails because nothing is staged
Next session: Same failure pattern repeats
```

## The Solution: Skill-Level Memory

Phase 44 integrates the existing `memory_harvest` system (Phase 36.4) into the agent's context:

```
Task Execution
    ↓
    ├─→ Phase 16: RAG Knowledge (static project docs)
    ├─→ Phase 43: Holographic Vision (live environment state)
    └─→ Phase 44: Experiential Memory (harvested lessons for skills)
    ↓
    LLM receives ALL three + mission brief
```

## Implementation Details

### 1. Librarian Extension

Added `get_skill_lessons()` to `librarian.py`:

```python
async def get_skill_lessons(skills: List[str], limit: int = 5) -> str:
    """
    [Phase 44] Retrieve lessons specifically tagged for these skills.

    Searches the vector store for harvested insights (past mistakes, pitfalls,
    best practices) that are relevant to the given skills.
    """
    vm = get_vector_memory()
    query = f"mistakes pitfalls best practices for {' '.join(skills)}"

    # Search specifically for harvested insights
    results = await vm.search(
        query=query,
        n_results=limit,
        where_filter={"type": "harvested_insight"}
    )

    # Format with header
    lines = ["### 🛑 KNOWN PITFALLS & PAST LESSONS", ""]
    for r in results:
        skill_tag = r.metadata.get("skill", "general")
        lines.append(f"- **{skill_tag}**: {r.content}")
```

### 2. BaseAgent Enhancement

Added `_get_agent_skill_lessons()` method in `base.py`:

```python
async def _get_agent_skill_lessons(self) -> str:
    """[Phase 44] Retrieve experiential lessons for the agent's skills."""
    if not self.default_skills:
        return ""
    return await get_skill_lessons(skills=self.default_skills, limit=5)
```

### 3. System Prompt Integration

Modified `prepare_context()` and `_build_system_prompt()` to inject skill lessons:

```
## 📋 CURRENT MISSION (From Orchestrator)
...

## 🧠 RELEVANT PROJECT KNOWLEDGE
...

### 🛑 KNOWN PITFALLS & PAST LESSONS
- **git**: Don't run git commit without staging first - always check git status
- **filesystem**: Always use absolute paths, never relative
...

## 🛠️ YOUR CAPABILITIES
...

## 📡 [Phase 43] HOLOGRAPHIC AWARENESS
...
```

## Data Flow

```
1. Developer uses /memory_harvest to log a lesson:
   - Content: "Don't run git commit without staging files first"
   - Skill tag: "git"
   - Type: "harvested_insight"

2. During agent initialization (prepare_context):
   - Agent identifies its skills (e.g., ["git", "filesystem"])
   - Calls get_skill_lessons(skills=["git", "filesystem"])

3. Vector store returns relevant lessons:
   - Searches for "mistakes pitfalls best practices for git filesystem"
   - Filters by type="harvested_insight"
   - Returns top 5 relevant lessons

4. Lessons injected into system prompt:
   - LLM receives mission + knowledge + lessons + holographic state
   - Can avoid repeating past mistakes
```

## Benefits

| Benefit                  | Description                                        |
| ------------------------ | -------------------------------------------------- |
| **No Repeated Mistakes** | Agent remembers what went wrong before             |
| **Continuous Learning**  | Each session improves future performance           |
| **Cross-Session Wisdom** | Hard-won lessons persist across sessions           |
| **Skill-Specific**       | Lessons are tagged by skill for targeted retrieval |

## Files Modified

| File                                        | Change                                                                                        |
| ------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `agent/capabilities/knowledge/librarian.py` | Added `get_skill_lessons()`                                                                   |
| `agent/core/agents/base.py`                 | Added `_get_agent_skill_lessons()`, modified `prepare_context()` and `_build_system_prompt()` |

## Future Enhancements

- **Auto-Harvesting**: Automatically log failures without manual harvest
- **Lesson Quality Scoring**: Weight lessons by success/failure feedback
- **Multi-Agent Memory Sharing**: Share lessons between agent instances
- **Learning Rate**: Prioritize recent lessons over old ones
