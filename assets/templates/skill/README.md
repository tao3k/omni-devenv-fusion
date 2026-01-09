# Skill Templates (ODF-EP v7.0)

Centralized Jinja2 templates for skill generation.

## Templates

| Template      | Target     | Description                                 |
| ------------- | ---------- | ------------------------------------------- |
| `SKILL.md.j2` | `SKILL.md` | Skill metadata with YAML Frontmatter        |
| `tools.py.j2` | `tools.py` | Python tools with @skill_command decorators |
| `guide.md.j2` | `guide.md` | Procedural documentation for LLM            |

## Usage

```python
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

template_dir = Path("assets/templates/skill")
env = Environment(loader=FileSystemLoader(str(template_dir)))

template = env.get_template("SKILL.md.j2")
output = template.render(
    skill_name="my_skill",
    description="My new skill",
    author="me",
)

# Write to skill directory
(output_path / "SKILL.md").write_text(output)
```

## Configuration

Templates are configured in `assets/settings.yaml` under `skill_architecture.templates`.

See Also:

- [Skills Documentation](../../docs/skills.md)
- [ODF-EP v7.0 Standards](../../assets/settings.yaml)
