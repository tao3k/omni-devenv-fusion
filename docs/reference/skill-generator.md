# Skill Generator

> Hybrid Skill Generator (Jinja2 + LLM) - The Cyborg

## Overview

Skill Generator combines **deterministic scaffolding** (Jinja2) with **creative generation** (LLM) to create standards-compliant Omni skills.

```
┌─────────────────────────────────────────────────────────────┐
│                    Hybrid Generation Pipeline                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │ Wizard   │ → │ Template │ → │   LLM    │ → │   Disk   │ │
│  │ (Input)  │   │ (Jinja2) │   │ (Creative)│   │ (Write)  │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│       │              │              │              │        │
│  Metadata &      SKILL.md,      commands.py,    Create     │
│  Permissions     __init__.py     README.md      files      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Interactive Mode (Default)

```bash
uv run omni skill generate
```

Follow the wizard prompts:

1. **Skill Description**: What should this skill do?
2. **Routing Keywords**: Auto-inferred, can be customized
3. **Permissions**: Grant network, filesystem, or subprocess access

### Non-Interactive Mode

```bash
uv run omni skill generate "Parse CSV files and convert to JSON" \
    --no-interactive \
    -p filesystem:read_file \
    -p filesystem:write_file
```

### Options

| Option                               | Description                                                   |
| ------------------------------------ | ------------------------------------------------------------- |
| `name`                               | Skill name (auto-derived from description if not provided)    |
| `-d, --description`                  | Natural language description                                  |
| `-i, --interactive/--no-interactive` | Run wizard (default: True)                                    |
| `-p, --permission`                   | Add permission (e.g., `network:http`, `filesystem:read_file`) |
| `-l, --auto-load/--no-load`          | Auto-load skill (default: True)                               |

## Generated Structure

```
skills/
└── {skill-name}/
    ├── SKILL.md           # YAML frontmatter + documentation
    ├── scripts/
    │   ├── __init__.py    # Module exports
    │   └── commands.py    # @skill_command implementations
    └── README.md          # Usage guide
```

## ODF-EP Protocol

All generated commands **MUST** follow the Omni-Dev-Fusion Engineering Protocol.

### Rule 1: First Line Action Verb

The description's first line must start with an action verb:

```python
@skill_command(
    name="list_tools",
    description="""
List all available commands for this skill.

Returns:
    CommandResult with list of available commands.
""",
    autowire=True,
)
```

**Approved Verbs**:

- Create, Get, Search, Update, Delete, Execute, Run, Load, Save
- List, Show, Check, Build, Parse, Format, Validate, Generate
- Apply, Process, Clear, Index, Ingest, Consult, Bridge, Refine
- Summarize, Commit, Amend, Revert, Retrieve, Analyze, Suggest
- Write, Read, Extract, Query, Filter, Detect, Navigate, Refactor

### Rule 2: Args and Returns Sections

Multi-line descriptions must include `Args:` and `Returns:` sections:

```python
@skill_command(
    name="example",
    description="""
Execute the main functionality of this skill.

Args:
    param: Description of the parameter. Defaults to `default_value`.

Returns:
    CommandResult with execution result.
""",
    autowire=True,
)
```

### Rule 3: Explicit description= Parameter

Use `description=` in decorator, not just function docstrings:

```python
# ✅ Correct
@skill_command(name="cmd", description="...", autowire=True)
def cmd(): ...

# ❌ Avoid (only docstring)
@skill_command(name="cmd", autowire=True)
def cmd():
    """Description here..."""
```

## Security Gatekeeper

The generator includes a **security permission system** that requires explicit user consent:

```
🛡️ Step 2: Security Permissions

Grant permissions for this skill (recommended: minimum required):
  Need network/http access? [y/N]:
  Need filesystem read access? [y/N]:
  Need filesystem write access? [y/N]:
  Need subprocess execution? [y/N]:
```

### Available Permissions

| Permission                  | Capability              |
| --------------------------- | ----------------------- |
| `network:http`              | HTTP requests           |
| `filesystem:read_file`      | Read files              |
| `filesystem:list_directory` | List directory contents |
| `filesystem:write_file`     | Write files             |
| `process:run`               | Execute subprocesses    |

## LLM Integration

The generator uses LLM for creative code generation:

1. **Input**: Skill name, description, permissions
2. **Prompt**: ODF-EP Protocol + implementation requirements
3. **Output**: `commands.py` and `README.md`

### Graceful Fallback

If LLM is unavailable, the generator uses **deterministic fallback templates**:

```python
# Fallback maintains protocol compliance
@skill_command(
    name="list_tools",
    description="""
List all available commands for this skill.

Returns:
    CommandResult with list of available commands.
""",
    autowire=True,
)
```

## Example Session

```bash
$ uv run omni skill generate

🔧 Omni Hybrid Skill Generator (Jinja2 + LLM)

📝 Step 1: Skill Metadata
What should this skill do? › Parse CSV files and convert to JSON
Routing Keywords (comma-separated) › csv, parse, convert, json

🛡️ Step 2: Security Permissions
Grant permissions for this skill:
  Need filesystem read access? [y/N]: y
  Need filesystem write access? [y/N]: y

🏗️ Step 3: Generating Skeleton (Jinja2)
  ✅ Rendered 2 skeleton files

🧠 Step 4: AI Engineering (LLM)
  Generating commands.py...
  Generating README.md...

💾 Step 5: Writing Files
  ✅ Created SKILL.md
  ✅ Created scripts/__init__.py
  ✅ Created scripts/commands.py
  ✅ Created README.md

╔═══════════════════════════════════════════════════════════════╗
║ ✅ Skill Generated: csv-tool                                  ║
║ 📝 Description: Parse CSV files and convert to JSON           ║
║ 🛡️  Permissions: filesystem:read_file, filesystem:write_file  ║
║ 📁 Files: SKILL.md, scripts/__init__.py, scripts/commands.py  ║
║ ⏱️  Duration: 1250ms                                           ║
╚═══════════════════════════════════════════════════════════════╝

📖 Usage: @omni("csv_tool.example")
```

## Architecture

```
generate.py
├── _get_template_engine()      # Jinja2 template engine
├── _infer_routing_keywords()   # Auto-extract keywords
├── _sanitize_skill_name()      # Normalize name format
├── skill_generate()            # Main command entry
│   ├── _run()                  # Async pipeline
│   │   ├── Wizard Step         # Metadata collection
│   │   ├── Security Gate       # Permission prompts
│   │   ├── Jinja2 Skeleton     # Render templates
│   │   ├── LLM Generation      # Creative code
│   │   └── Materialization     # Write files
│   └── _generate_with_llm()    # LLM with fallback
└── _get_fallback_code()        # Deterministic template
```

## Troubleshooting

### LLM Generation Fails

The generator automatically falls back to template-based code. Check logs:

```bash
uv run omni skill generate -v  # Verbose mode
```

### Permission Denied

Ensure you've granted required permissions during generation:

```bash
uv run omni skill generate "My skill" -p filesystem:read_file
```

### Invalid Skill Name

Names are automatically sanitized:

- Lowercase
- Spaces → hyphens
- Special chars removed

```
"My New Skill" → "my-new-skill"
```

## See Also

- [Skills Architecture](../architecture/skills.md)
- [ODF-EP Protocol](odf-ep-protocol.md)
- [Trinity Architecture](../explanation/system-layering.md)
