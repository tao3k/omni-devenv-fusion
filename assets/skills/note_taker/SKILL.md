---
# === Omni-Dev Fusion Skill Manifest ===
name: note_taker
version: 1.0.0
description: Persistent memory system for summarizing sessions and managing knowledge - The Scribe's Ledger
authors: ["omni-dev-fusion"]
license: Apache-2.0
execution_mode: library
routing_strategy: keyword
routing_keywords:
  ["note", "remember", "summary", "knowledge", "memory", "learn", "capture"]
---

# Note Taker Skill

## Purpose

The **Scribe's Ledger** enables the agent to maintain persistent memory across sessions by:

1. **Capturing** - Recording session trajectories, decisions, and outcomes
2. **Summarizing** - Extracting key insights from execution traces
3. **Retrieving** - Loading relevant past knowledge for new tasks
4. **Pattern Mining** - Identifying reusable solutions and anti-patterns

## System Prompt Additions

When this skill is active, add these guidelines to the LLM context:

```markdown
# Note Taker Guidelines

When working with knowledge management:

- Use `note_taker.summarize_session` to capture completed work before switching contexts
- Use `note_taker.update_knowledge_base` to save discovered patterns and solutions
- Use `note_taker.search_notes` to recall past approaches before reinventing
- Always record:
  - Key decision points and rationale
  - Failed approaches and why they failed
  - Final working solution and its context
  - Files modified and their purpose
```

## Commands

| Command                            | Description                                   |
| ---------------------------------- | --------------------------------------------- |
| `note_taker.summarize_session`     | Summarize current session into markdown notes |
| `note_taker.update_knowledge_base` | Save extracted knowledge for future retrieval |
| `note_taker.search_notes`          | Search existing notes and knowledge           |
| `note_taker.extract_patterns`      | Identify reusable patterns from sessions      |

## Key Directories

| Directory                     | Purpose                                         |
| ----------------------------- | ----------------------------------------------- |
| `.data/knowledge/sessions/`   | Session summaries (auto-generated, git-ignored) |
| `assets/knowledge/harvested/` | Extracted reusable knowledge                    |
| `assets/knowledge/patterns/`  | Identified patterns and anti-patterns           |

## Related Documentation

- [CCA Paper](assets/specs/phase61_cognitive_scaffolding.md) - Cognitive Scaffolding Architecture
- [Skills Documentation](../../docs/skills.md) - Comprehensive skill guide
