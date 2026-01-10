---
# === Omni-Dev Fusion Skill Manifest ===
name: _template
version: 1.0.0
description: Template skill for new capabilities - demonstrates Trinity Architecture with Isolated Sandbox
authors: ["omni-dev-fusion"]
license: Apache-2.0
execution_mode: library
routing_strategy: keyword
routing_keywords: ["template", "new skill", "create skill", "scaffold"]
intents: []
---

# Template Skill

## System Prompt Additions

When this skill is active, add these guidelines to the LLM context:

```markdown
# Template Skill Guidelines

When working with the Template skill:

- Use `template.example` for basic operations
- Use `template.process_data` for data processing tasks
- Remember to follow the Router-Controller pattern
- All implementation lives in scripts/ directory
```

## Trinity Architecture Context (Phase 35.2)

This skill operates within the **Trinity Architecture** with **Isolated Sandbox + Explicit Routing**:

```
_template/
├── SKILL.md           # Metadata + System Prompts
├── tools.py           # Router (dispatch only)
└── scripts/           # Controllers (isolated implementation)
    ├── __init__.py    # Package marker (required!)
    ├── example.py     # Atomic implementations
    └── ...
```

| Component   | Description                                                   |
| ----------- | ------------------------------------------------------------- |
| **Code**    | `tools.py` + `scripts/` - Hot-reloaded via ModuleLoader       |
| **Context** | `@omni("template.help")` - Full skill context via Repomix XML |
| **State**   | `SKILL.md` - Skill metadata in YAML Frontmatter               |

## Why Isolated Sandbox?

For large-scale deployments (100+ skills), namespace conflicts are inevitable:

- `git/scripts/utils.py` vs `docker/scripts/utils.py`
- `python/scripts/status.py` vs `docker/scripts/status.py`

**Solution**: Each skill's `scripts/` is an isolated Python package:

- `agent.skills.git.scripts.status` ← Git's status
- `agent.skills.docker.scripts.status` ← Docker's status

These are **completely different objects** in memory.

## ODF-EP Protocol Awareness

All core skill modules follow the **"Python Zenith" Engineering Protocol**:

| Pillar                             | Implementation in Skills              |
| ---------------------------------- | ------------------------------------- |
| **A: Pydantic Shield**             | DTOs use `ConfigDict(frozen=True)`    |
| **B: Protocol-Oriented Design**    | `ISkill`, `ISkillCommand` protocols   |
| **C: Tenacity Pattern**            | `@retry` for resilient I/O operations |
| **D: Context-Aware Observability** | `logger.bind()` for structured logs   |

## Creating a New Skill

Use `_template` as a scaffold for new skills:

### 1. Copy Template

```bash
cp -r assets/skills/_template assets/skills/my_new_skill
```

### 2. Update SKILL.md

Edit the frontmatter:

```yaml
---
name: my_new_skill
version: 1.0.0
description: My new skill description
routing_keywords: ["keyword1", "keyword2"]
---
```

### 3. Add Commands (`tools.py` - Router Layer)

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_new_skill.my_command",
    category="read",
    description="Brief description",
)
def my_command(param: str) -> str:
    """Detailed docstring."""
    from agent.skills.my_new_skill.scripts import example as example_mod
    return example_mod.my_implementation(param)
```

**Naming Convention**: Use `skill.command` format (e.g., `my_new_skill.my_command`)

### 4. Add Implementation (`scripts/example.py`)

```python
# scripts/example.py
def my_implementation(param: str) -> str:
    """Actual implementation."""
    return f"Result: {param}"
```

### 5. (Optional) Add Jinja2 Templates

For structured output:

```bash
mkdir -p assets/templates/my_new_skill/
# Add *.j2 template files
```

### 6. (Optional) Subprocess Mode - Sidecar Execution Pattern

For heavy/conflicting dependencies (e.g., `crawl4ai`, `playwright`), use the **Sidecar Pattern**:

```
assets/skills/my_skill/
├── pyproject.toml        # Skill dependencies (uv isolation)
├── tools.py              # Lightweight shim (no heavy imports!)
└── scripts/
    └── engine.py         # Heavy implementation (imports OK here!)
```

**Step A: Create `pyproject.toml`** (copied from `_template/pyproject.toml`)

**Step B: Write lightweight `tools.py` shim**

```python
# tools.py - Router (lightweight, no heavy imports!)
from pathlib import Path
from agent.skills.decorators import skill_command
from common.isolation import run_skill_script

def _get_skill_dir() -> Path:
    return Path(__file__).parent

@skill_command
def my_command(param: str) -> dict:
    """
    My command description.
    """
    return run_skill_script(
        skill_dir=_get_skill_dir(),
        script_name="engine.py",
        args={"param": param},
        timeout=60,
    )
```

**Step C: Write heavy `scripts/engine.py`** (imports OK here!)

```python
# scripts/engine.py - Controller (heavy imports allowed!)
import json
from heavy_lib import do_work  # This works!

def main(param: str):
    result = do_work(param)
    # Print JSON to stdout for the shim to capture
    print(json.dumps({"success": True, "result": result}))

if __name__ == "__main__":
    import sys
    main(sys.argv[1] if sys.argv[1:] else "")
```

**Why This Pattern?**

| Layer               | What                 | Why                    |
| ------------------- | -------------------- | ---------------------- |
| `tools.py`          | Lightweight shim     | Main agent stays clean |
| `scripts/engine.py` | Heavy implementation | Can import anything    |
| `pyproject.toml`    | Dependencies         | uv manages isolation   |

## Quick Reference

| Command            | Category | Description             |
| ------------------ | -------- | ----------------------- |
| `template.example` | read     | Example command         |
| `template.help`    | view     | Show full skill context |

## Related Documentation

- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md)
- [ODF-EP Planning Prompt](../../.claude/plans/odf-ep-v6-planning-prompt.md)
