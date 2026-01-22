# Context Sniffer - Declarative Skill Activation

> Skill activation based on file system context using declarative rules

## Overview

The **Context Sniffer** (codename: "The Nose") detects the current development context from the file system and automatically activates relevant skills. For example:

- `pyproject.toml` present → Activate **Python Engineering** skill
- `Cargo.toml` present → Activate **Rust** skill
- `package.json` present → Activate **Node.js** skill

### Key Design Principles

1. **Declarative Rules**: Skills define their activation rules in `rules.toml`
2. **Rust-First Indexing**: Rules are parsed at build time, consumed at runtime
3. **Zero Runtime Overhead**: Rules are pre-indexed in `skill_index.json`
4. **Three Detection Modes**:
   - Static rules (fast file existence checks)
   - Declarative rules (TOML-based configuration)
   - Dynamic rules (Python functions for complex logic)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Rust-First Indexing Pipeline                        │
└─────────────────────────────────────────────────────────────────────────────┘

  assets/skills/python_engineering/
  extensions/sniffer/rules.toml
            │
            ▼
    ┌─────────────────┐
    │  Rust Scanner   │  Parses rules.toml at build time
    │  (skills-       │
    │   scanner)      │
    └────────┬────────┘
             │
             ▼ Writes
    ┌─────────────────────────┐
    │  skill_index.json       │  Single Source of Truth
    │  {                     │
    │    "name": "python",   │
    │    "sniffing_rules": [  │
    │      {"type": "file_exists", "pattern": "pyproject.toml"} │
    │    ]                   │
    │  }                     │
    └────────┬───────────────┘
             │
             │ Reads at startup
             ▼
    ┌─────────────────────────┐
    │  Python Kernel          │  Loads rules into IntentSniffer
    │  (engine.py)            │
    └────────┬────────────────┘
             │
             ▼
    ┌─────────────────────────┐
    │  IntentSniffer.sniff()  │  Runtime context detection
    └─────────────────────────┘
```

## Rule Configuration

### Location

Rules are defined in each skill's `extensions/sniffer/rules.toml`:

```
assets/skills/{skill_name}/
├── SKILL.md
├── scripts/
│   └── *.py
└── extensions/
    └── sniffer/
        └── rules.toml        ← Sniffer rules configuration
```

### TOML Format

```toml
# extensions/sniffer/rules.toml

# Mode 1: file_exists - Fast O(1) exact file match
# Used for project markers (pyproject.toml, Cargo.toml, etc.)
[[match]]
type = "file_exists"
pattern = "pyproject.toml"

[[match]]
type = "file_exists"
pattern = "requirements.txt"

# Mode 2: file_pattern - Glob-style matching (O(N))
# Used for file extension detection (*.py, *.rs, etc.)
[[match]]
type = "file_pattern"
pattern = "*.py"

[[match]]
type = "file_pattern"
pattern = "**/test_*.py"
```

### Rule Types

| Type           | Complexity | Use Case                                     |
| -------------- | ---------- | -------------------------------------------- |
| `file_exists`  | O(1)       | Project markers (pyproject.toml, Cargo.toml) |
| `file_pattern` | O(N)       | File extension detection (_.py, _.rs)        |

**Performance Note**: Use `file_exists` for project root markers when possible. The sniffer only checks files in the current working directory.

## Example: Python Engineering Skill

```toml
# assets/skills/python_engineering/extensions/sniffer/rules.toml

# Python project markers (exact files in cwd)
[[match]]
type = "file_exists"
pattern = "pyproject.toml"

[[match]]
type = "file_exists"
pattern = "requirements.txt"

[[match]]
type = "file_exists"
pattern = "setup.py"

[[match]]
type = "file_exists"
pattern = "setup.cfg"

[[match]]
type = "file_exists"
pattern = "Pipfile"

[[match]]
type = "file_exists"
pattern = "pyrightconfig.json"

[[match]]
type = "file_exists"
pattern = "mypy.ini"

[[match]]
type = "file_exists"
pattern = "pytest.ini"

# Python file patterns
[[match]]
type = "file_pattern"
pattern = "*.py"

[[match]]
type = "file_pattern"
pattern = "**/*.py"
```

## Example: Git Skill

```toml
# assets/skills/git/extensions/sniffer/rules.toml

# Git repository markers
[[match]]
type = "file_exists"
pattern = ".git"

[[match]]
type = "file_exists"
pattern = ".gitignore"

[[match]]
type = "file_exists"
pattern = ".gitmodules"
```

## Python Runtime Integration

### Kernel Boot Sequence

The kernel loads sniffer rules during startup:

```python
# packages/python/core/src/omni/core/kernel/engine.py

async def _on_ready(self) -> None:
    # ... skill loading ...

    # Step 5: Initialize Intent Sniffer
    logger.info("👃 Initializing Context Sniffer...")
    self.load_sniffer_rules()
```

### Using the Sniffer

```python
from omni.core.router.sniffer import IntentSniffer

sniffer = IntentSniffer()

# Load rules from skill_index.json (generated by Rust scanner)
sniffer.load_from_index()

# Detect active skills in current directory
active_skills = sniffer.sniff("/path/to/project")

# Result: ["python_engineering", "git"]
```

### Three-Mode Detection

```python
from omni.core.router.sniffer import IntentSniffer

sniffer = IntentSniffer()

# Mode 1: Static Rules (from SKILL.md activation.files - deprecated)
# sniffer.register_rule(ActivationRule("python", files=["pyproject.toml"]))

# Mode 2: Declarative Rules (from rules.toml - via load_from_index)
sniffer.load_from_index()

# Mode 3: Dynamic Rules (Python functions for complex detection)
def detect_venv(cwd: str) -> float:
    import os
    venv_path = os.path.join(cwd, "venv")
    return 1.0 if os.path.exists(venv_path) else 0.0

sniffer.register_dynamic(detect_venv, "python", name="venv_check")

# Sniff with all modes
suggestions = sniffer.sniff("/project")
```

## Skill Index Schema

The `skill_index.json` contains sniffer rules for each skill:

```json
[
  {
    "name": "python_engineering",
    "description": "Python engineering skill",
    "version": "1.0.0",
    "path": "assets/skills/python_engineering",
    "routing_keywords": ["python", "py", "pip"],
    "tools": [...],
    "sniffing_rules": [
      {
        "type": "file_exists",
        "pattern": "pyproject.toml"
      },
      {
        "type": "file_pattern",
        "pattern": "*.py"
      }
    ]
  }
]
```

## Dynamic Sniffer Functions

For complex detection logic beyond file matching, use dynamic sniffer functions:

```python
# assets/skills/python_engineering/extensions/sniffer/detectors.py

def detect_poetry_project(cwd: str) -> float:
    """Detect Poetry-based Python project (score: 1.0)."""
    import os
    pyproject_path = os.path.join(cwd, "pyproject.toml")
    if not os.path.exists(pyproject_path):
        return 0.0

    with open(pyproject_path) as f:
        content = f.read()
        if "[tool.poetry]" in content:
            return 1.0
    return 0.0

# Mark as sniffer function
detect_poetry_project._sniffer_name = "poetry_detection"
detect_poetry_project._sniffer_priority = 50
```

## Best Practices

1. **Use `file_exists` for root markers**: Always prefer exact file matches for project root indicators
2. **Keep patterns simple**: `file_pattern` uses `fnmatch` - avoid complex regex needs
3. **Limit dynamic sniffers**: They run on every `sniff()` call - use sparingly
4. **Group related rules**: All rules for one skill should be in that skill's `rules.toml`

## Migration from SKILL.md

Previously, activation rules were defined in SKILL.md:

```yaml
---
name: "python"
activation:
  files:
    - "pyproject.toml"
    - "*.py"
---
```

**Migration**: Move these to `extensions/sniffer/rules.toml`:

```toml
[[match]]
type = "file_exists"
pattern = "pyproject.toml"

[[match]]
type = "file_pattern"
pattern = "*.py"
```

The Rust scanner now parses `rules.toml` instead of SKILL.md for activation rules.

## File Structure Summary

```
assets/skills/
├── python_engineering/
│   ├── SKILL.md
│   ├── scripts/
│   │   └── *.py
│   └── extensions/
│       └── sniffer/
│           ├── rules.toml      ← Declarative rules
│           └── detectors.py    ← Dynamic rules (optional)
│
├── git/
│   ├── SKILL.md
│   ├── scripts/
│   └── extensions/
│       └── sniffer/
│           └── rules.toml
│
└── skill_index.json             ← Generated by Rust scanner
```

## API Reference

### Python: IntentSniffer

```python
class IntentSniffer:
    def load_from_index(self, index_path: Optional[str] = None) -> int:
        """Load rules from skill_index.json. Returns rule count."""

    def register_rule(self, rule: ActivationRule) -> None:
        """Register static file-based rule."""

    def register_rules(self, skill_name: str, rules: List[Dict]) -> None:
        """Register declarative rules from dict format."""

    def register_dynamic(self, func: Callable[[str], float], skill_name: str,
                        name: Optional[str] = None, priority: int = 100) -> None:
        """Register dynamic sniffer function."""

    def sniff(self, cwd: str) -> List[str]:
        """Detect active skills. Returns skill names."""

    def sniff_with_scores(self, cwd: str) -> List[Tuple[str, float]]:
        """Detect skills with activation scores."""
```

### Rust: SnifferRule

```rust
pub struct SnifferRule {
    pub rule_type: String,  // "file_exists" or "file_pattern"
    pub pattern: String,
}
```
