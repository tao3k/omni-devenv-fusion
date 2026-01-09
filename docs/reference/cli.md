# CLI Reference

> **Phase 35.2**: Cascading Templates & Structure Validation | **Phase 35.1**: Zero-Config Tests | **Phase 26**: Skill Network

The `omni` CLI provides unified access to all Omni-DevEnv Fusion capabilities.

## Quick Reference

| Command                               | Description              |
| ------------------------------------- | ------------------------ |
| `omni mcp`                            | Start MCP server         |
| `omni skill run <cmd>`                | Execute skill command    |
| `omni skill check`                    | Validate skill structure |
| `omni skill create <name>`            | Create new skill         |
| `omni skill install <url>`            | Install skill from URL   |
| `omni skill list`                     | List installed skills    |
| `omni skill templates <skill> --list` | List skill templates     |
| `omni skill test <name>`              | Run skill tests          |

## Global Options

```bash
omni --help              # Show help
omni --version           # Show version
```

---

## MCP Server

### `omni mcp`

Start the MCP server for integration with Claude Desktop or other MCP clients.

```bash
# Start in stdio mode (default)
omni mcp

# With custom port (for SSE transport)
omni mcp --port 8080
```

---

## Skill Management

### `omni skill run`

Execute a skill command directly from CLI.

```bash
# Basic usage
omni skill run git.status

# With arguments (JSON format)
omni skill run 'git.commit' '{"message": "feat: add new feature"}'

# Run any skill command
omni skill run filesystem.read '{"path": "README.md"}'
```

### `omni skill check`

Validate skill structure against `settings.yaml` configuration.

```bash
# Check all skills
omni skill check

# Check specific skill
omni skill check git

# Check with optional structure examples
omni skill check git --examples
```

**Output:**

```
🔍 git

✅ Valid: True
📊 Score: 100.0%
📁 Location: assets/skills/git

## 📁 Structure
├── SKILL.md
├── tools.py
├── templates/
├── scripts/
└── tests/
```

### `omni skill create`

Create a new skill from template.

```bash
# Basic usage
omni skill create my-skill --description "My new skill"

# With author and keywords
omni skill create my-skill \
  --description "Data processing skill" \
  --author "my-name" \
  --keyword "data" \
  --keyword "processing"
```

**Options:**
| Option | Description |
|--------|-------------|
| `--description` | Brief skill description (required) |
| `--author` | Author name (default: omni-dev) |
| `--keyword` | Routing keywords (repeatable) |

### `omni skill install`

Install a skill from a Git repository.

```bash
# Install from URL
omni skill install https://github.com/omni-dev/skill-pandas

# With custom name
omni skill install https://github.com/user/repo --name custom-name

# Specific version
omni skill install https://github.com/user/repo --version v2.0.0
```

### `omni skill update`

Update an installed skill to the latest version.

```bash
# Default (stash strategy)
omni skill update pandas-expert

# With conflict handling
omni skill update pandas-expert --strategy stash   # Stash changes, pull, pop
omni skill update pandas-expert --strategy abort   # Abort if dirty
omni skill update pandas-expert --strategy overwrite  # Force overwrite
```

### `omni skill list`

List all installed skills with status.

```
📦 Installed Skills
┌─────────────────┬──────────┬─────────┬────────┐
│ Skill           │ Status   │ Version │ Dirty  │
├─────────────────┼──────────┼─────────┼────────┤
│ git             │ loaded   │ 1.0.0   │ -      │
│ knowledge       │ loaded   │ 1.2.0   │ -      │
│ filesystem      │ loaded   │ 1.0.0   │ ⚠️ Yes │
└─────────────────┴──────────┴─────────┴────────┘
```

### `omni skill info`

Show detailed information about a skill.

```bash
omni skill info git
```

**Shows:** Path, revision, dirty status, manifest, lockfile.

### `omni skill discover`

Discover skills from the known index.

```bash
# Search skills
omni skill discover data analysis

# With limit
omni skill discover --limit 10
```

---

## Template Management (Phase 35.2)

### `omni skill templates`

Manage skill templates with **cascading pattern** (User Overrides > Skill Defaults).

#### `omni skill templates list`

List templates for a skill with their source.

```bash
omni skill templates list git
```

**Output:**

```
# 📄 Skill Templates: git

**Cascading Pattern**: User Overrides > Skill Defaults

## Templates

🟢 commit_message.j2 (User Override)
🟢 error_message.j2 (User Override)
⚪ workflow_result.j2 (Skill Default)

## Template Locations

User Overrides: assets/templates/git
Skill Defaults: assets/skills/git/templates
```

**Legend:**

- 🟢 User Override (highest priority)
- ⚪ Skill Default (fallback)

#### `omni skill templates eject`

Copy a skill default template to user override directory.

```bash
omni skill templates eject git commit_message.j2
```

**Output:**

```
# ✅ Template Ejected

Template: commit_message.j2
Source: Skill Default
Location: assets/templates/git/commit_message.j2

## Next Steps

1. Edit: code assets/templates/git/commit_message.j2
2. Test changes
3. Commit with /commit

💡 User templates override skill defaults automatically.
```

#### `omni skill templates info`

Show template content and source location.

```bash
omni skill templates info git commit_message.j2
```

---

## Testing (Phase 35.1)

### `omni skill test`

Run skill tests with zero-configuration framework.

```bash
# Test specific skill
omni skill test git

# Test all skills with tests/
omni skill test --all

# Custom skills directory
omni skill test git --skills-dir ./assets/skills
```

**Features:**

- Auto-discovers skills with `tests/` directory
- Pytest fixtures auto-injected
- No `conftest.py` needed in skill directories

---

## Cascading Template Architecture

### Template Resolution Order

```
1. User Overrides (Highest Priority)
   assets/templates/{skill}/

2. Skill Defaults (Fallback)
   assets/skills/{skill}/templates/
```

### Customizing Templates

To customize a skill's output format:

```bash
# 1. List available templates
omni skill templates list git

# 2. Eject default to user directory
omni skill templates eject git commit_message.j2

# 3. Edit the template
code assets/templates/git/commit_message.j2

# 4. Changes take effect immediately
```

### Example: Custom Commit Message Format

```jinja
{# assets/templates/git/commit_message.j2 #}
<commit_message format="custom">
    <type>{{ subject.split(':')[0] }}</type>
    <scope>{{ subject.split(':')[1].split('(')[0] if ':' in subject else 'none' }}</scope>
    <description>{{ subject.split(':')[-1] if ':' in subject else subject }}</description>
</commit_message>

{{ body }}
```

---

## Skill Structure Validation

### Required Files

| File       | Description                                       |
| ---------- | ------------------------------------------------- |
| `SKILL.md` | Skill metadata (YAML frontmatter) and LLM context |
| `tools.py` | @skill_command decorated functions                |

### Optional Directories

| Directory     | Description                         |
| ------------- | ----------------------------------- |
| `templates/`  | Jinja2 templates (Phase 35.2)       |
| `scripts/`    | Atomic implementations (Phase 35.2) |
| `references/` | RAG documentation                   |
| `tests/`      | Pytest tests (Phase 35.1)           |
| `assets/`     | Static resources                    |
| `data/`       | Data files                          |

### Validation Examples

```bash
# Valid skill structure
omni skill check git
# ✅ Valid: True | 📊 Score: 100.0%

# Missing required files
omni skill check my-skill
# ❌ Valid: False | Missing: SKILL.md, tools.py

# With disallowed files
omni skill check broken-skill
# 🚫 Disallowed: manifest.json, prompts.md
```

---

## Exit Codes

| Code | Description                              |
| ---- | ---------------------------------------- |
| 0    | Success                                  |
| 1    | Error (invalid command, not found, etc.) |

---

## Environment Variables

| Variable    | Description                                      |
| ----------- | ------------------------------------------------ |
| `PRJ_ROOT`  | Project root directory (overrides git detection) |
| `OMNI_CONF` | Configuration directory (default: `assets`)      |

---

## Related Documentation

- [Skills Documentation](../skills.md) - Skill architecture and usage
- [Trinity Architecture](../explanation/trinity-architecture.md) - Technical deep dive
- [Testing Guide](../developer/testing.md) - Zero-config test framework
