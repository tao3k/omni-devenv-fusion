# Context Orchestrator

> The Async Conductor - Modular 7-Layer Context Assembly Architecture

## Overview

ContextOrchestrator orchestrates parallel retrieval of context layers with optional Skill Memory injection. It builds prompts by executing layers in priority order, respecting token budgets.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ContextOrchestrator                       │
│                  (Async Conductor)                          │
├─────────────────────────────────────────────────────────────┤
│  Layer1: System Persona      │ System prompt (XML)          │
│  Layer1.5: Skill Memory      │ SKILL.md prompts (optional)  │
│  Layer2: Available Skills    │ Skill registry               │
│  Layer3: Knowledge           │ Project documentation        │
│  Layer4: Associative Memories│ Vector search results        │
│  Layer5: Environment         │ Git/file system state        │
│  Layer6: Code Maps           │ Tags and symbols             │
│  Layer7: Raw Code            │ Relevant source files        │
└─────────────────────────────────────────────────────────────┘
```

## Layer Priority

| Layer | Name                | Priority | Purpose                          |
| ----- | ------------------- | -------- | -------------------------------- |
| L1    | SystemPersona       | 1        | System prompt and XML structure  |
| L1.5  | SkillMemory         | -        | Dynamic skill prompts (optional) |
| L2    | AvailableSkills     | 2        | Available skills registry        |
| L3    | Knowledge           | 3        | Project documentation            |
| L4    | AssociativeMemories | 4        | Vector search results            |
| L5    | Environment         | 5        | Environment state                |
| L6    | CodeMaps            | 6        | Code symbols and tags            |
| L7    | RawCode             | 7        | Source code content              |

## Usage

```python
from agent.core.context_orchestrator import ContextOrchestrator, build_context

# Async usage (recommended)
orchestrator = ContextOrchestrator(max_tokens=128000, output_ratio=0.2)
prompt = await orchestrator.build_prompt(
    task="Fix the login bug",
    history=[{"role": "user", "content": "Login doesn't work"}],
    skill_prompts={"git": git_skill_content, "writer": writer_skill_content},
)

# Sync wrapper (legacy)
prompt = build_context("Fix the login bug", history)
```

## Token Budget Management

```python
orchestrator = ContextOrchestrator(
    max_tokens=128000,  # Total context window
    output_ratio=0.2,   # Reserve 20% for output
)
# input_budget = 128000 * 0.8 = 102400 tokens for input
```

## Layer Interface

All layers implement `ContextLayer`:

```python
class ContextLayer:
    name: str
    priority: int

    async def assemble(
        self,
        task: str,
        history: List[dict],
        budget: int,
    ) -> Tuple[str, int]:
        """Assemble context for the given task.

        Returns:
            Tuple of (content, tokens_used)
        """
```

## Skill Memory Injection

Layer1.5 (SkillMemory) is dynamically inserted when `skill_prompts` is provided:

```python
# Load SKILL.md content
skill_prompts = {
    "git": read("assets/skills/git/SKILL.md"),
    "writer": read("assets/skills/writer/SKILL.md"),
}

# Layer1.5 inserted between L1 and L2
prompt = await orchestrator.build_prompt(
    task="Make a commit",
    history=[],
    skill_prompts=skill_prompts,
)
```

## Statistics

```python
stats = orchestrator.get_context_stats(prompt)
# {
#     "total_tokens": 45000,
#     "max_tokens": 128000,
#     "utilization": 0.35,
# }
```

## Configuration

### Token Encoding

Uses `tiktoken` with `cl100k_base` encoding for accurate token counting.

### Singleton Pattern

```python
orch = get_context_orchestrator(max_tokens=128000)
# Subsequent calls return the same instance
```

## Related Documentation

- [Memory Mesh](./memory-mesh.md) - Memory architecture overview
- [Skill Discovery](../../llm/skill-discovery.md) - How skills are discovered
- [Knowledge Matrix](./knowledge-matrix.md) - Knowledge indexing

---

_Built on standards. Not reinventing the wheel._
