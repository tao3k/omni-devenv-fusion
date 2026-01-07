# Skills Index

> **Phase 27: JIT Skill Acquisition**

This directory contains the **Known Skills Index** - a registry of available skills that can be installed on-demand.

## Structure

```
skills_index/
├── known_skills.json    # Main index of available skills
├── README.md           # This file
└── sources/            # External skill sources (future)
```

## known_skills.json Format

```json
{
  "version": "1.0.0",
  "updated_at": "2025-12-01T00:00:00Z",
  "skills": [
    {
      "id": "pandas-expert",
      "name": "Pandas Expert",
      "description": "Advanced pandas operations for data analysis",
      "url": "https://github.com/omni-dev/skill-pandas",
      "version": "1.0.0",
      "keywords": ["python", "data", "analysis", "pandas"],
      "category": "data"
    }
  ]
}
```

## Skill Discovery

### Using MCP Tools

```python
# List all known skills
@omni("skill.list_index")

# Search by query
@omni("skill.discover", {"query": "data analysis"})

# Install a skill
@omni("skill.jit_install", {"skill_id": "pandas-expert"})

# Get AI suggestions
@omni("skill.suggest", {"task": "clean and analyze sales data"})
```

### Skill Fields

| Field         | Required | Description                    |
| ------------- | -------- | ------------------------------ |
| `id`          | Yes      | Unique identifier (kebab-case) |
| `name`        | Yes      | Human-readable name            |
| `url`         | Yes      | Git repository URL             |
| `version`     | Yes      | Current version (semver)       |
| `keywords`    | Yes      | Searchable tags                |
| `description` | No       | Longer description             |
| `category`    | No       | Skill category                 |

## Adding New Skills

1. Add skill entry to `known_skills.json`
2. Ensure skill has proper `manifest.json` in its repository
3. Test JIT install

```bash
# Test local install
omni skill install --test https://github.com/user/new-skill
```

## Related Documentation

- [Phase 27 Spec](./skills_index/README.md) - JIT Acquisition specification
- [Phase 26 Spec](../specs/phase26-skill-network.md) - Skill Network installer
- [Phase 28 Spec](../specs/phase28-safe-ingestion.md) - Security scanning
