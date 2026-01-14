# Phase 29: Trinity + Protocols

> **Status**: Implemented (Legacy - Superseded by Phase 36)
> **Date**: 2024-XX-XX
> **Related**: Phase 25 (Trinity v1.0), Phase 36 (Trinity v2.0)

## Overview

Phase 29 evolved the Trinity Architecture by introducing **Protocol-based design** for the skill registry. This modularized the monolithic `SkillManager` into separate concerns with runtime-checkable interfaces.

## The Problem

**Before Phase 29**: Monolithic skill management

```python
# Phase 25 - Monolithic registry (~887 lines)
class SkillManager:
    async def load_skill(self, name: str): ...
    async def execute_skill(self, name: str, cmd: str): ...
    def list_skills(self): ...
    def get_commands(self, name: str): ...
    # ... 800+ more lines
```

Issues:

- Hard to test (no interfaces)
- Single point of failure
- Difficult to extend
- No clear separation of concerns

## The Solution: Protocol-Based Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase 29: Modular Registry               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   SkillRegistry                      │   │
│  │              (Singleton - Discovery)                 │   │
│  │                                                     │   │
│  │  - list_available_skills()                          │   │
│  │  - get_skill_manifest()                             │   │
│  │  - discover_skills()                                │   │
│  └───────────────────────┬─────────────────────────────┘   │
│                          │                                   │
│          ┌───────────────┼───────────────┐                  │
│          ▼               ▼               ▼                  │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐             │
│  │  Loader   │   │ Context   │   │ Installer │             │
│  │ (Loading) │   │ (Repomix) │   │  (JIT)    │             │
│  └───────────┘   └───────────┘   └───────────┘             │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              SkillManager (Facade)                   │   │
│  │                                                     │   │
│  │  - Delegates to specialized modules                 │   │
│  │  - Provides unified @omni interface                 │   │
│  │  - ~200 lines (vs 887 in Phase 25)                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Protocol Definitions

### ISkill Protocol

```python
@runtime_checkable
class ISkill(Protocol):
    """Runtime-checkable skill interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill name."""

    @property
    @abstractmethod
    def commands(self) -> dict[str, "ISkillCommand"]:
        """Map of command names to command objects."""
```

### ISkillCommand Protocol

```python
@dataclass(slots=True)
class ISkillCommand(Protocol):
    """Runtime-checkable command interface."""

    name: str
    func: Callable[..., Any]
    description: str = ""
    category: SkillCategory = SkillCategory.GENERAL
```

### IRegistry Protocol

```python
class IRegistry(Protocol):
    """Skill registry interface."""

    @abstractmethod
    def list_available_skills(self) -> list[str]:
        """List all skills available in the system."""

    @abstractmethod
    async def get_skill(self, name: str) -> Optional[ISkill]:
        """Get a skill by name."""
```

## Module Structure

```
packages/python/agent/src/agent/core/registry/
├── __init__.py              # Unified exports + get_skill_tools()
├── core.py                  # SkillRegistry (singleton, discovery)
├── loader.py                # SkillLoader (spec-based loading)
├── context.py               # ContextBuilder (guide + prompts)
├── installer.py             # RemoteInstaller (Git-based)
├── resolver.py              # VersionResolver (multi-strategy)
└── jit.py                   # JIT skill acquisition
```

## Key Components

### 1. SkillRegistry

```python
class SkillRegistry:
    """Singleton skill registry with discovery."""

    _instance: Optional["SkillRegistry"] = None
    _skills: Dict[str, ISkill] = {}
    _manifests: Dict[str, SkillManifest] = {}

    def list_available_skills(self) -> list[str]:
        """Discover and return all available skills."""

    async def get_skill(self, name: str) -> Optional[ISkill]:
        """Get a skill by name, loading if necessary."""
```

### 2. SkillLoader

```python
class SkillLoader:
    """Load skills from specification files."""

    async def load_from_spec(self, skill_dir: Path) -> ISkill:
        """
        Load a skill from SKILL.md specification.

        Parses:
        - Skill name and description
        - Commands (from tools.py decorators)
        - Dependencies
        - Configuration
        """
```

### 3. ContextBuilder

```python
class ContextBuilder:
    """Build skill context for LLM understanding."""

    async def build_context(self, skill: ISkill) -> str:
        """
        Generate comprehensive skill context.

        Includes:
        - SKILL.md content
        - Command signatures and descriptions
        - Usage examples
        - Best practices
        """
```

## Memory Efficiency

Phase 29 introduced `@dataclass(slots=True)` for memory efficiency:

```python
@dataclass(slots=True)
class SkillCommand(ISkillCommand):
    """Memory-efficient command using slots."""
    name: str
    func: Callable[..., Any]
    description: str = ""
    category: SkillCategory = SkillCategory.GENERAL
```

| Metric                | Phase 25 (dict) | Phase 29 (slots) |
| --------------------- | --------------- | ---------------- |
| Memory per Skill      | ~3KB            | ~1KB             |
| Memory per Command    | ~500B           | ~200B            |
| 100 skills + 500 cmds | ~400KB          | ~150KB           |

## Integration with Trinity

```python
from agent.core.registry import get_skill_registry

# Registry provides skills
registry = get_skill_registry()
skills = registry.list_available_skills()

# Each skill implements ISkill protocol
skill = registry.get_skill("git")
print(skill.name)  # "git"
print(skill.commands.keys())  # ["status", "commit", "push", ...]

# SkillManager provides execution (Trinity Executor role)
from agent.core.skill_manager import get_skill_manager
manager = get_skill_manager()
await manager.run("git", "status")
```

## Benefits

| Benefit              | Description                                |
| -------------------- | ------------------------------------------ |
| **Modular**          | 6 files (~676 lines) vs 1 monolithic file  |
| **Testable**         | Protocol-based mocking                     |
| **Extensible**       | Add new modules without touching core      |
| **Memory Efficient** | slots=True reduces memory footprint by ~3x |
| **Lazy Loading**     | Skills loaded on demand, not at startup    |

## Evolution Timeline

| Phase | Architecture         | Lines | Key Innovation            |
| ----- | -------------------- | ----- | ------------------------- |
| 24    | Monolithic           | N/A   | Initial Trinity           |
| 25    | Trinity v1.0         | 887   | @omni("skill.command")    |
| 29    | Trinity + Protocols  | 676   | Protocol-based modularity |
| 35    | Trinity + Sidecar    | N/A   | Heavy deps isolation      |
| 36    | Trinity v2.0 + Swarm | N/A   | Hot reload, Swarm Engine  |

## Related Specs

- `assets/specs/phase25_trinity_architecture.md`
- `assets/specs/phase35_sidecar_pattern.md`
- `assets/specs/phase36_trinity_v2.md`
