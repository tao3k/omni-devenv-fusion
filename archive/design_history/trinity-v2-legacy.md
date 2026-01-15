# Trinity v2.0 - Swarm Engine (Legacy)

> **⚠️ DEPRECATED**: This document describes the legacy Swarm Engine architecture.
> The current architecture uses **OmniAgent + JIT Loader** instead.

> **Status**: Legacy (Superseded)
> **Date**: 2024-XX-XX
> **Related**: [Omni Loop](omni-loop.md) (Current), Trinity v1.0

## Overview

Trinity v2.0 introduced the **Swarm Engine** - a runtime orchestrator with skill dispatch. This has been superseded by OmniAgent with JIT (Just-In-Time) skill loading.

## Key Differences: Swarm Engine vs OmniAgent + JIT

| Aspect             | Swarm Engine (Legacy)     | OmniAgent + JIT (Current)     |
| ------------------ | ------------------------- | ----------------------------- |
| **Skill Loading**  | Eager loading via ISkill  | Lazy JIT loading              |
| **Dispatch**       | Swarm.execute_skill()     | JITSkillLoader.execute_tool() |
| **Hot Reload**     | Module reload + observers | File watcher + reindex        |
| **Tool Discovery** | Static ISkill registry    | Dynamic Rust scanner          |

## Migration Path

The Swarm Engine has been replaced by:

- **OmniAgent**: Main CCA runtime in `agent/core/omni_agent.py`
- **JITSkillLoader**: Just-in-time skill loading in `agent/core/skill_manager/jit_loader.py`

## Related Documentation

- [Omni Loop](omni-loop.md) (Current CCA Runtime)
- [Trinity Core](trinity-core.md) (v1.0 Architecture)
- [Skill Standard](skill-standard.md) (Current skill format)
