# Skills Documentation

> **Architecture**: Trinity Architecture with @skill_script Pattern

Omni-DevEnv Fusion uses a skill-based architecture where each skill is a self-contained module in the `assets/skills/` directory. Skills are accessed via the single `@omni` MCP tool.

All skill metadata is unified in `SKILL.md` using YAML Frontmatter, following the Anthropic Agent Skills standard.

## Skill Architecture

### Pure MCP Server

Omni uses **pure `mcp.server.Server`** instead of FastMCP for better control and performance:

```python
# mcp_server.py - Pure MCP Server (no FastMCP)
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("omni-agent")

@server.list_tools()
async def list_tools(): ...

@server.call_tool()
async def call_tool(name, arguments): ...
```

**Benefits:**

- Direct control over tool listing/execution
- Explicit error handling for TaskGroup
- Optional uvloop (SSE mode) + orjson for performance
- No FastMCP dependency overhead

## Cascading Templates & @skill_script Pattern

### Template Structure (Cascading Pattern)

Skills support **cascading template loading** with "User Overrides > Skill Defaults" pattern:

```
assets/skills/git/                    # Skill Directory
├── templates/                         # Skill defaults (Fallback)
│   ├── commit_message.j2
│   ├── workflow_result.j2
│   └── error_message.j2
└── scripts/
    ├── __init__.py                   # Package marker (required!)
    └── commands.py                   # @skill_script decorated commands

assets/templates/                      # User overrides (Priority)
└── git/
    ├── commit_message.j2              # Overrides skill default
    └── workflow_result.j2
```

**Template Resolution Order:**

1. `assets/templates/{skill}/` - User customizations (highest priority)
2. `assets/skills/{skill}/templates/` - Skill defaults (fallback)

### @skill_script Pattern

Skills use `@skill_script` decorator for command registration:

```python
from agent.skills.decorators import skill_script

@skill_script(
    name="status",
    category="read",
    description="Show working tree status",
)
async def git_status() -> str:
    """Returns git status as formatted markdown."""
    ...
```

## Skill Components

| Component     | File                  | Purpose                           |
| ------------- | --------------------- | --------------------------------- |
| **Metadata**  | `SKILL.md`            | YAML frontmatter + LLM context    |
| **Commands**  | `scripts/commands.py` | @skill_script decorated functions |
| **Templates** | `templates/*.j2`      | Jinja2 templates for output       |
| **Tests**     | `tests/test_*.py`     | Pytest test files                 |

## Skill Lifecycle

### 1. Discovery

Skills are discovered from `assets/skills/` directories:

```
assets/skills/
├── git/              # Git skill
├── filesystem/       # File operations
├── terminal/         # Shell execution
├── code_navigation/  # AST-based navigation
├── structural_editing/ # AST-based editing
└── ...
```

### 2. Loading

Skills are loaded on-demand via SkillManager:

```python
from agent.core.skill_manager import get_skill_manager

manager = get_skill_manager()
await manager.load_skill("git")
```

### 3. Hot Reload

Skills support hot reload when `scripts/commands.py` is modified.

## Creating a New Skill

See [Template Skill](../assets/skills/_template/README.md) for the complete scaffold.

### Quick Start

```bash
# Copy template
cp -r assets/skills/_template assets/skills/my_skill

# Update SKILL.md frontmatter
# Add commands in scripts/commands.py
# Add tests in tests/
```

## Related Documentation

- [Template Skill](../assets/skills/_template/README.md)
- [Trinity Architecture](../explanation/trinity-architecture.md)
- [ODF-EP Protocol](../reference/odf-ep-protocol.md)
