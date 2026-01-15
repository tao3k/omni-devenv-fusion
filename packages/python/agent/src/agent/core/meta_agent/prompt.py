"""
agent/core/meta_agent/prompt.py
 The Meta-Agent - LLM Prompt Templates

Provides structured prompts for LLM-driven skill generation.
遵循 ODF-EP 标准:
- Type hints required
- Async-first
"""

from typing import Any


# =============================================================================
# Skill Generation Prompt
# =============================================================================

SKILL_GENERATION_PROMPT = """You are the Omni Meta-Agent, an expert system that generates new skills for the Omni DevEnv Agent.

## Your Task
Generate a complete skill implementation based on the user's requirements.

## Input
User Requirement: {requirement}

## Output Format
Return a JSON object with the following structure:

```json
{{
  "skill_name": "short_name",
  "description": "Brief description (1-2 sentences)",
  "routing_keywords": ["keyword1", "keyword2", "keyword3"],
  "commands": [
    {{
      "name": "command_name",
      "description": "What this command does",
      "category": "read|write|execute|analyze",
      "parameters": [
        {{"name": "param1", "type": "string", "description": "Description", "required": true}}
      ],
      "implementation": "Python code for the function body"
    }}
  ]
}}
```

## Skill Naming Rules
- Use kebab-case (e.g., `csv_handler`, `data_transformer`)
- Maximum 3 words
- Must be descriptive and searchable

## Command Implementation Guidelines
1. Keep functions atomic and focused on one task
2. Use type hints for all parameters
3. Add Google-style docstrings
4. Return dict with `success`, `data`, `error` structure
5. Use existing skills when possible (e.g., `filesystem.read_file`)

## Example

User Requirement: "I need to parse CSV files and convert them to JSON"

Output:
```json
{{
  "skill_name": "csv_parser",
  "description": "Parse CSV files and convert to JSON format",
  "routing_keywords": ["csv", "parse", "convert", "json"],
  "commands": [
    {{
      "name": "csv_to_json",
      "description": "Convert a CSV file to JSON format",
      "category": "analyze",
      "parameters": [
        {{"name": "path", "type": "string", "description": "Path to CSV file", "required": true}},
        {{"name": "delimiter", "type": "string", "description": "CSV delimiter (default: ',')", "required": false}}
      ],
      "implementation": "import csv; import json; reader = csv.DictReader(f, delimiter=delimiter); return {{'success': True, 'data': list(reader)}}"
    }}
  ]
}}
```

## Important
- Return ONLY valid JSON (no markdown formatting)
- Ensure the skill name is unique
- Include at least 2 routing keywords
- All commands must have valid Python implementations
"""


# =============================================================================
# Skill Analysis Prompt (for harvesting)
# =============================================================================

SKILL_ANALYSIS_PROMPT = """You are analyzing session notes to identify reusable skills.

## Input
Session Notes:
{notes}

## Task
Identify patterns that should be extracted into reusable skills.

## Output Format
```json
{{
  "suggested_skills": [
    {{
      "name": "skill_name",
      "reason": "Why this should be a skill",
      "frequency": "How often this pattern appears",
      "commands": ["command1", "command2"]
    }}
  ]
}}
```

## Criteria for Skill Extraction
1. Pattern appears 3+ times across sessions
2. Involves 2+ tools working together
3. Has a clear, reusable purpose
4. Can be generalized beyond specific files/domains

Return ONLY valid JSON.
"""


# =============================================================================
# Test Generation Prompt
# =============================================================================

TEST_GENERATION_PROMPT = """Generate pytest tests for a skill command.

## Skill Command
Name: {name}
Description: {description}
Parameters: {parameters}
Implementation: {implementation}

## Output
Return a JSON object:
```json
{{
  "test_code": "# Pytest code here\\nimport pytest\\n..."
}}
```

## Testing Guidelines
1. Test happy path
2. Test edge cases (empty input, invalid input)
3. Use `pytest` framework
4. Follow project testing conventions (SSOT from `common.skills_path`)

Return ONLY valid JSON with test_code field.
"""


# =============================================================================
# MetaAgentPrompt Class
# =============================================================================


class MetaAgentPrompt:
    """Prompt templates for Meta-Agent operations."""

    @staticmethod
    def skill_generation(requirement: str) -> str:
        """Get the skill generation prompt with filled requirement."""
        return SKILL_GENERATION_PROMPT.format(requirement=requirement)

    @staticmethod
    def skill_analysis(notes: str) -> str:
        """Get the skill analysis prompt with filled notes."""
        return SKILL_ANALYSIS_PROMPT.format(notes=notes)

    @staticmethod
    def test_generation(
        name: str,
        description: str,
        parameters: list[dict[str, Any]],
        implementation: str,
    ) -> str:
        """Get the test generation prompt with filled details."""
        import json

        return TEST_GENERATION_PROMPT.format(
            name=name,
            description=description,
            parameters=json.dumps(parameters),
            implementation=implementation,
        )


# =============================================================================
# Prompt Utilities
# =============================================================================


def parse_skill_response(response: str) -> dict[str, Any]:
    """Parse LLM response into skill structure.

    Args:
        response: Raw LLM response (may contain markdown)

    Returns:
        Parsed skill dictionary
    """
    import json
    import re

    # Extract JSON from markdown code blocks
    json_match = re.search(r"```json\s*(.+?)\s*```", response, re.DOTALL)
    if json_match:
        response = json_match.group(1)

    # Clean up and parse
    response = response.strip()
    return json.loads(response)


def extract_json_from_response(response: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling various formats.

    Args:
        response: Raw LLM response

    Returns:
        Parsed JSON as dict
    """
    import json
    import re

    # Try direct JSON
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    code_match = re.search(r"```(?:json)?\s*(.+?)\s*```", response, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find JSON object in text
    start = response.find("{")
    end = response.rfind("}") + 1
    if start != -1 and end != 0:
        try:
            return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not extract valid JSON from response")


__all__ = [
    "MetaAgentPrompt",
    "parse_skill_response",
    "extract_json_from_response",
]
