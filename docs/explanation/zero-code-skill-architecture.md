# Zero-Code Skill Architecture

> Core architecture design for Omni-Dev-Fusion: achieving "code-free" skill loading

## Overview

Zero-Code Skill Architecture is a **data-driven** skill management system. Its core philosophy is: **skill definitions and extensions are entirely determined by files in the `assets/` directory, and the core framework code (Kernel/ScriptLoader/ExtensionLoader) requires no code changes for each skill**.

This architecture achieves:

- **O(1) Complexity**: Framework code is fixed and does not grow with the number of skills
- **USB Interface Pattern**: Unified interface supporting arbitrary plugin extensions
- **Hot-Swapping**: Seamless switching between pure Python and Rust-accelerated environments

## Architecture Diagram

```
                    ┌─────────────────────────────────────────────────────┐
                    │                 Kernel (Entry Point)                 │
                    │  Responsibilities: Init → Discover Skills → Dispatch│
                    └─────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        UniversalScriptSkill (Skill Container)                │
│                                                                              │
│   "The One Skill to Rule Them All" - Unified skill shell                    │
│                                                                              │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐      │
│   │  ExtensionLoader │    │   ScriptLoader   │    │    Dependency     │      │
│   │  (Load Rust)     │    │  (Load Scripts)  │    │    Injection      │      │
│   └──────────────────┘    └──────────────────┘    └──────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          assets/skills/<skill_name>/                         │
│                                                                              │
│   Skill Definition Directory - All skill logic here, purely data-driven     │
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │  extensions/              scripts/          SKILL.md               │   │
│   │  ┌──────────────┐        ┌─────────┐       ┌─────────────────┐     │   │
│   │  │ rust_bridge/ │        │ *.py    │       │ name: git       │     │   │
│   │  │   __init__.py│        │ (cmds)  │       │ version: 1.0    │     │   │
│   │  │   accelerator│        └─────────┘       │ description: ... │     │   │
│   │  └──────────────┘                          └─────────────────┘     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
packages/python/core/src/omni/core/skills/
├── universal.py          # [Core] Skill container, handles assembly and command dispatch
├── script_loader.py      # [Mechanism] Parses @skill_command decorators, loads .py scripts
│
└── extensions/           # [Extension Subsystem] Contains loading mechanism + built-in extensions
    ├── __init__.py
    ├── loader.py         # Mechanism: scans and loads extensions
    ├── wrapper.py        # Mechanism: wraps dynamically loaded plugin objects
    │
    └── rust_bridge/      # [Concrete Implementation] Rust accelerator extension
        ├── __init__.py
        └── accelerator.py

assets/skills/            # Skill definition directory (user/system skills)
├── git/
│   ├── SKILL.md          # Skill metadata
│   ├── extensions/       # Git-specific extensions
│   │   └── rust_bridge/  # Rust accelerator for Git
│   └── scripts/          # Git command scripts
│       ├── commit.py     # @skill_command decorated functions
│       ├── status.py
│       └── ...
├── filesystem/
│   ├── SKILL.md
│   └── scripts/
│       └── io.py
└── ...
```

## Component Roles

### 1. universal.py - Assembly Factory / Container

**Responsibilities**: Doesn't do the work, only coordinates.

```python
class UniversalScriptSkill:
    """Universal skill container - loads extensions/ and scripts/ directories"""

    async def load(self, context):
        # 1. Load extensions
        ext_loader = SkillExtensionLoader(str(self._path / "extensions"))
        ext_loader.load_all()

        # 2. Create script loader
        script_loader = create_script_loader(scripts_path, self._name)

        # 3. Inject Rust accelerator (if present)
        rust_bridge = ext_loader.get("rust_bridge")
        if rust_bridge:
            script_loader.inject("rust", rust_bridge.RustAccelerator(cwd))

        # 4. Load scripts (automatically receive rust injection)
        script_loader.load_all()
```

**Key Characteristics**:

- Fixed code size (~200 lines), does not grow with skill count
- No skill-specific `if/else` conditionals
- Fully data-driven

### 2. script_loader.py - Script Parser

**Responsibilities**: Parses Python scripts, registers `@skill_command` decorated functions.

```python
@skill_command(name="git_commit", category="write")
def commit(message: str, project_root: Path = None) -> str:
    """Commit code"""
    subprocess.run(["git", "commit", "-m", message], cwd=project_root)
    return "Commit created successfully"
```

**Workflow**:

1. Scans `scripts/*.py` files
2. Parses `@skill_command` decorators
3. Extracts function signatures as command parameters
4. Registers in command table

### 3. extensions/ - Plugin System

**Responsibilities**: Contains both "loading mechanism" and "concrete implementation".

#### Loading Mechanism (Mechanism)

```python
# loader.py
class SkillExtensionLoader:
    """Scans extensions/ directory and loads all plugins"""

    def load_all(self):
        for item in self.extensions_dir.iterdir():
            if item.is_dir():
                self._load_plugin(item)

    def get(self, name: str):
        return self._extensions.get(name)
```

#### Concrete Implementation (Implementation)

```python
# rust_bridge/accelerator.py
class RustAccelerator:
    """Rust accelerator - provides high-performance Git operations"""

    @property
    def is_active(self) -> bool:
        return self._rust_bindings.is_available()

    def status(self) -> Dict[str, Any]:
        # High-performance status query using Rust implementation
        return self._rust_bindings.git_status()
```

## Why This Design?

### Problem: Why Not Direct Import?

You might ask: "Since we only have Rust, why not just `import rust_bridge` directly in `universal.py`?"

### Solution: Transparency and Extensibility

1. **Decoupling**: `universal.py` doesn't need to know about `rust_bridge`

   ```python
   # Wrong way (tight coupling)
   if skill_name == "git":
       from git_extensions import RustAccelerator
   ```

2. **Hot-Swapping**: Pure Python environment can disable Rust

   ```python
   # If no Rust, just remove the rust_bridge directory
   # The entire system still works, just with degraded performance
   ```

3. **Future Extensions**: Adding new extensions requires no framework changes
   ```text
   extensions/
   ├── rust_bridge/      # Existing
   ├── memory_bank/      # New: shared memory extension
   └── docker_bridge/    # New: container runtime extension
   ```

## Auto-Wiring Flow

### 1. Loading Sequence

```
Kernel.load_universal_skill("git")
        │
        ▼
UniversalScriptSkill.load({"cwd": "/repo"})
        │
        ├────────────────────────────────────────────────────────┐
        │                                                        │
        ▼                                                        ▼
ExtensionLoader.load_all()                                ScriptLoader.init()
(Load extensions/rust_bridge/)                            (Initialize script env)
        │                                                        │
        ▼                                                        ▼
rust_bridge = ext_loader.get("rust_bridge")            script_loader.inject("rust", rust_bridge)
        │                                                        │
        └────────────────────────────────────────────────────────┘
                                │
                                ▼
                        script_loader.load_all()
                                │
                                ▼
                   Scripts receive `rust` variable (auto-injected)
```

### 2. Execution Sequence

```
User: @omni("git.git_commit", {"message": "fix: bug"})
           │
           ▼
UniversalScriptSkill.execute("git.git_commit", message="fix: bug")
           │
           ▼
handler = script_loader.get_command("git.git_commit")
           │
           ▼
# If function is async
result = await handler(message="fix: bug")
           │
           ▼
# Scripts can freely use `rust` variable (injected)
```

## Example: Writing a New Skill

### 1. Create Skill Directory

```bash
mkdir -p assets/skills/my_skill/{scripts,extensions}
```

### 2. Write Script Command

```python
# assets/skills/my_skill/scripts/hello.py
from omni.core.skills.script_loader import skill_command

@skill_command(name="hello", category="greeting")
def hello(name: str = "World") -> str:
    """Greet someone"""
    return f"Hello, {name}!"
```

### 3. Optional: Add Rust Extension

```python
# assets/skills/my_skill/extensions/fast_math/__init__.py
from .bindings import RustMathBindings

def create(context):
    return RustMathBindings()
```

### 4. No Framework Code Changes Needed!

```python
# Framework auto-discovers and loads
from omni.core.skills.universal import UniversalSkillFactory

factory = UniversalSkillFactory("assets/skills")
skills = factory.discover_skills()  # Auto-discovers "my_skill"

skill = factory.create_skill("my_skill")
await skill.load({"cwd": "/repo"})

# Use directly
result = await skill.execute("my_skill.hello", name="Claude")
# → "Hello, Claude!"
```

## Summary

| Component                 | Role                    | Code Size           | Responsibility             |
| ------------------------- | ----------------------- | ------------------- | -------------------------- |
| `universal.py`            | Container               | ~200 lines (fixed)  | Assembly, command dispatch |
| `script_loader.py`        | Parser                  | ~150 lines (fixed)  | Parse Python scripts       |
| `extensions/loader.py`    | Loading Mechanism       | ~100 lines (fixed)  | Scan plugin directories    |
| `extensions/rust_bridge/` | Concrete Implementation | Grows with features | Rust acceleration logic    |
| `assets/skills/*/`        | Business Logic          | Grows with skills   | Skill definitions          |

**Core Principles**:

- Framework code is O(1) fixed
- Skill logic is O(N) extensible
- Data-driven, no if/else hardcoding
