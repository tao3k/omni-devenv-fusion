---
# === Omni-Dev Fusion Skill Manifest ===
name: _template
version: 1.0.0
description: Template skill for new capabilities - demonstrates Trinity Architecture v2.0
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
- All commands are defined in `scripts/commands.py` with @skill_command decorator
- No tools.py needed - this is the single source of truth
```

## Trinity Architecture v2.0 Context

This skill operates within the **Trinity Architecture v2.0** with **scripts/commands.py** pattern:

```
_template/
├── SKILL.md           # Metadata + System Prompts
├── scripts/           # Commands (Phase 63+)
│   ├── __init__.py    # Dynamic module loader (importlib.util)
│   └── commands.py    # @skill_command decorated functions
└── tests/             # Test files
```

| Component   | Description                                                   |
| ----------- | ------------------------------------------------------------- |
| **Code**    | `scripts/commands.py` - Hot-reloaded via ModuleLoader         |
| **Context** | `@omni("template.help")` - Full skill context via Repomix XML |
| **State**   | `SKILL.md` - Skill metadata in YAML Frontmatter               |

## Why scripts/commands.py Pattern?

The new architecture simplifies the skill pattern:

**Old pattern:**

- `tools.py` - Router with `@skill_command` decorators
- `scripts/*.py` - Implementation functions

**New pattern:**

- `scripts/commands.py` - Commands with `@skill_command` decorators
- No `tools.py` needed

**Benefits:**

- Single source of truth
- No router-indirection layer
- Easier to understand and maintain
- Hot-reload works directly on commands

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

### Development Workflow

```
1. _template/                    # Start: Copy this template
   │
2. scripts/                     # Step 1: COMMANDS (actual logic)
   │
3. tests/                       # Step 2: TESTS (zero-config)
   │
4. README.md                    # Step 3: User documentation
   │
5. SKILL.md                     # Step 4: LLM context & manifest
```

### Step 1: Copy Template

```bash
cp -r assets/skills/_template assets/skills/my_new_skill
```

### Step 2: Add Commands (`scripts/commands.py`)

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="my_command",
    category="read",
    description="Brief description",
)
async def my_command(param: str) -> str:
    """Detailed docstring."""
    return f"Result: {param}"
```

**Note:** Command name is just `my_command`, not `my_new_skill.my_command`. MCP Server auto-prefixes.

### Step 3: Add Tests (`tests/test_*.py`)

```python
def test_my_command_exists():
    from agent.skills.my_new_skill.scripts import commands
    assert hasattr(commands, "my_command")
```

### Step 4: Update Documentation (`README.md`)

Add usage examples and command reference.

### Step 5: Update Manifest (`SKILL.md`)

Edit the frontmatter:

```yaml
---
name: my_new_skill
version: 1.0.0
description: My new skill description
routing_keywords: ["keyword1", "keyword2"]
---
```

### Step 6: (Optional) Subprocess Mode - Sidecar Execution Pattern

For heavy/conflicting dependencies (e.g., `crawl4ai`, `playwright`), use the **Sidecar Pattern**:

```
assets/skills/my_skill/
├── pyproject.toml        # Skill dependencies (uv isolation)
└── scripts/
    ├── __init__.py       # Module loader
    └── engine.py         # Heavy implementation (imports OK here!)
```

**Step A: Create `pyproject.toml`** (copied from `_template/pyproject.toml`)

**Step B: Write `scripts/engine.py`** (heavy imports allowed!)

```python
# scripts/engine.py - Heavy implementation
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

**Step C: Write `scripts/__init__.py`** (lightweight shim)

```python
# scripts/__init__.py - Lightweight loader
import importlib.util
from pathlib import Path
import subprocess
import json

_scripts_dir = Path(__file__).parent

def run_engine(param: str) -> dict:
    """Run engine.py as subprocess."""
    engine_path = _scripts_dir / "engine.py"
    result = subprocess.run(
        ["python", str(engine_path), param],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return json.loads(result.stdout)
```

**Why This Pattern?**

| Layer                 | What                 | Why                    |
| --------------------- | -------------------- | ---------------------- |
| `scripts/__init__.py` | Lightweight loader   | Main agent stays clean |
| `scripts/engine.py`   | Heavy implementation | Can import anything    |
| `pyproject.toml`      | Dependencies         | uv manages isolation   |

## Quick Reference

| Command                         | Category | Description             |
| ------------------------------- | -------- | ----------------------- |
| `template.example`              | read     | Example command         |
| `template.example_with_options` | read     | Example with options    |
| `template.process_data`         | write    | Process data strings    |
| `template.help`                 | view     | Show full skill context |

## Related Documentation

- [Skills Documentation](../../docs/skills.md) - Comprehensive guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md)
- [ODF-EP Planning Prompt](../../.claude/plans/odf-ep-v6-planning-prompt.md)
