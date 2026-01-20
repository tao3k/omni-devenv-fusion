"""
prompt.py
 The Meta-Agent - LLM Prompt Templates

Provides structured prompts for LLM-driven skill generation.
"""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Skill Generation Prompt
# =============================================================================

SKILL_GENERATION_PROMPT = """You are the Omni Meta-Agent, an expert system that generates new skills for the Omni DevEnv Agent.

## Your Task
Generate a complete skill with ONE command that fulfills the user's requirement.

## Input
User Requirement: {requirement}

## CRITICAL: Generate Only ONE Command
Generate a skill with a SINGLE command that provides the requested functionality.
Do NOT generate multiple commands or functions - just ONE complete implementation.

## Output Format
Return your response in TWO code blocks:

1. First, a JSON code block with metadata:
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
      ]
    }}
  ]
}}
```

2. Second, a PYTHON code block with the COMPLETE implementation:
```python
# Implementation for command: command_name
import json

def command_name(param1: str) -> dict:
    \"\"\"
    One-line description.

    Args:
        param1: Description

    Returns:
        dict with success, data, error keys
    \"\"\"
    try:
        # Complete implementation here
        result = do_something(param1)
        return {{"success": True, "data": result, "error": None}}
    except Exception as e:
        return {{"success": False, "data": None, "error": str(e)}}
```

## Rules
- Generate ONE command only - not multiple functions
- Include all necessary imports
- Return dict with "success", "data", "error" keys
- Use double quotes for strings in the return dict
- The function name should match the command name in JSON

## CRITICAL: Implementation Format
- Use PROPER MULTI-LINE Python code with line breaks
- Do NOT compress code to one line with semicolons
- Use proper indentation (4 spaces)
- Each statement on its own line
- Use DOUBLE QUOTES for Python strings
- Start with "# Implementation for command: command_name"

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

## Important
- Return ONLY valid JSON (no markdown formatting)
- Ensure the skill name is unique
- Include at least 2 routing keywords
- All commands must have valid Python implementations
"""


# =============================================================================
# Test Generation Prompt
# =============================================================================

TEST_GENERATION_PROMPT = '''Generate a simple pytest test that imports and loads a skill module.

## Skill Details
Skill Name: {skill_name_underscore}
Command Name: {name}
Description: {description}

## CRITICAL: Use Skill Name for File Paths
The skill module file is named: {skill_name_underscore}.py
Use EXACTLY this name in the test - do NOT use the command name or any other variation.

## Output Format
```python
import pytest
import importlib.util
import os

# Resolve skill path relative to this test file (works in temp dirs)
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(TEST_DIR, "..", "scripts")
skill_path = os.path.join(SKILL_DIR, "{skill_name_underscore}.py")

# Load the skill module
spec = importlib.util.spec_from_file_location("{skill_name_underscore}", skill_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_{skill_name_underscore}_module_loads():
    """Test that the skill module loads without errors."""
    assert module is not None

def test_{skill_name_underscore}_has_functions():
    """Test that the skill module has callable functions."""
    # Get all functions that don't start with underscore
    functions = [attr for attr in dir(module) if not attr.startswith('_') and callable(getattr(module, attr))]
    assert len(functions) > 0, "No functions found in skill module"
```

## Rules
1. Use skill_name_underscore ({skill_name_underscore}) for the file path - NOT command name
2. Use importlib.util to load skill from scripts directory
3. Use os.path.dirname and os.path.join for path resolution (works in temp dirs)
4. Only test that the module loads and has functions - do NOT call functions with arguments
5. Return ONLY the test code in ```python tags
'''


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
    def test_generation(
        name: str,
        description: str,
        parameters: list[dict[str, Any]],
        implementation: str,
        skill_name: str = "",
    ) -> str:
        """Generate a simple test that just loads the skill module."""
        # Convert skill name to valid Python module name (underscores instead of hyphens)
        if skill_name:
            skill_name_underscore = skill_name.replace("-", "_")
        elif name:
            skill_name_underscore = name.replace("-", "_")
        else:
            skill_name_underscore = "test_module"

        # Generate deterministic test code - no LLM needed for simple module loading
        test_code = f'''import pytest
import importlib.util
import os

# Resolve skill path relative to this test file (works in temp dirs)
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.join(TEST_DIR, "..", "scripts")
skill_path = os.path.join(SKILL_DIR, "{skill_name_underscore}.py")

# Load the skill module
spec = importlib.util.spec_from_file_location("{skill_name_underscore}", skill_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_{skill_name_underscore}_module_loads():
    """Test that the skill module loads without errors."""
    assert module is not None

def test_{skill_name_underscore}_has_functions():
    """Test that the skill module has callable functions."""
    # Get all functions that don't start with underscore
    functions = [attr for attr in dir(module) if not attr.startswith('_') and callable(getattr(module, attr))]
    assert len(functions) > 0, "No functions found in skill module"
'''
        return test_code


# =============================================================================
# Prompt Utilities
# =============================================================================


def parse_skill_response(response: str) -> dict[str, Any]:
    """Parse LLM response into skill structure."""
    import json
    import re

    # Extract JSON from markdown code blocks
    json_match = re.search(r"```json\s*(.+?)\s*```", response, re.DOTALL)
    if json_match:
        json_content = json_match.group(1)
    else:
        json_content = response

    # Clean up and parse JSON with robust error handling
    json_content = json_content.strip()

    # Try standard JSON first
    try:
        skill_spec = json.loads(json_content)
    except json.JSONDecodeError:
        # Fix common issues: single quotes in Python dicts within JSON
        try:
            import ast

            skill_spec = ast.literal_eval(json_content)
        except (ValueError, SyntaxError):
            raise ValueError(f"Failed to parse JSON from response:\n{json_content[:500]}...")

    # Extract Python implementation from python code blocks
    py_match = re.search(
        r"```python\s*#?\s*Implementation for command:?\s*(\w+)\s*\n*(.+?)\s*```",
        response,
        re.DOTALL,
    )

    command_name = None
    if not py_match:
        # Fallback: look for any python code block after the JSON
        py_matches = list(re.finditer(r"```python\s*(.+?)\s*```", response, re.DOTALL))
        if len(py_matches) > 0:
            py_match = py_matches[-1]
        else:
            py_match = None

    if py_match:
        implementation = (
            py_match.group(2).strip() if py_match.lastindex and py_match.lastindex >= 2 else ""
        )

        # Add implementation to commands
        commands = skill_spec.get("commands", [])
        if commands:
            if command_name:
                for cmd in commands:
                    if cmd.get("name") == command_name:
                        cmd["implementation"] = implementation
                        break
            else:
                commands[0]["implementation"] = implementation

    return skill_spec


def extract_json_from_response(response: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling various formats."""
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
        json_content = code_match.group(1)
        try:
            return json.loads(json_content)
        except json.JSONDecodeError:
            pass

    # Try to find JSON object in text
    start = response.find("{")
    end = response.rfind("}") + 1
    if start != -1 and end != 0:
        json_str = response[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Last resort: try to extract using regex
    if '"refined_code"' in response:
        test_match = re.search(r'"refined_code"\s*:\s*"(.*?)"', response, re.DOTALL)
        if test_match:
            return {"refined_code": test_match.group(1)}

    raise ValueError(f"Could not extract valid JSON from response:\n{response[:500]}...")


__all__ = [
    "MetaAgentPrompt",
    "parse_skill_response",
    "extract_json_from_response",
]
