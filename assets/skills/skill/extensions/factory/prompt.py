r"""
prompt.py - Meta-Agent Prompts
Aligned with Trinity Architecture v2.0 _template structure.

The LLM reads _template files and generates modified versions.
"""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def read_template_file(path: str) -> str:
    """Read a template file content."""
    from pathlib import Path

    p = Path(path)
    if p.exists():
        return p.read_text()
    return ""


SKILL_GENERATION_PROMPT = """You are a Python Expert Architect for Omni-Dev Fusion.

## Task
Generate skill files by modifying the _template based on user requirement.

## _template/SKILL.md
---
{skill_md}
---

## _template/scripts/commands.py
```python
{commands_py}
```

## User Requirement
{requirement}

## Output Format
Return ONLY a JSON object:

```json
{{
  "skill_name": "fibonacci-calculator",
  "description": "Brief description of the skill",
  "routing_keywords": ["keyword1", "keyword2"],
  "files": {{
    "SKILL.md": "Full content of modified SKILL.md",
    "scripts/commands.py": "Full content of modified commands.py"
  }}
}}
```

## Rules
1. skill_name: kebab-case, descriptive
2. Update SKILL.md: name, description, routing_keywords, title
3. Update commands.py: modify function name, description, implementation
4. Keep the @skill_command decorator structure
5. Use return dict format: {{"success": True, "data": result, "error": None}}
"""


def skill_generation_prompt(requirement: str, template_dir: str) -> str:
    """Build the skill generation prompt with template content."""
    skill_md = read_template_file(f"{template_dir}/SKILL.md")
    commands_py = read_template_file(f"{template_dir}/scripts/commands.py")

    return SKILL_GENERATION_PROMPT.format(
        skill_md=skill_md,
        commands_py=commands_py,
        requirement=requirement,
    )


def parse_skill_response(response: str) -> dict[str, Any]:
    """Parse LLM response into skill specification."""
    import json
    import re

    # Find JSON in response
    json_match = re.search(r"```json\s*(.+?)\s*```", response, re.DOTALL)
    if json_match:
        json_content = json_match.group(1)
    else:
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end != 0:
            json_content = response[start:end]
        else:
            json_content = response

    try:
        return json.loads(json_content)
    except json.JSONDecodeError:
        pass

    try:
        import ast

        return ast.literal_eval(json_content)
    except (ValueError, SyntaxError):
        pass

    raise ValueError(f"Failed to parse JSON from response")


__all__ = [
    "skill_generation_prompt",
    "parse_skill_response",
]
