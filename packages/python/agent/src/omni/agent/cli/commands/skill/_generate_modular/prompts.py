"""
prompts.py - LLM Prompt Templates for Skill Generation

Provides structured prompts for generating skill code following
ODF-EP Protocol standards.
"""

from __future__ import annotations


# ODF-EP Protocol rules for skill_command descriptions
ODF_EP_RULES = """# ODF-EP PROTOCOL: skill_command Description Standards

## CRITICAL: This is a MANDATORY PROTOCOL, not a suggestion.

You MUST follow these rules strictly. Any deviation will result in INVALID output.

## Protocol Requirements

### Rule 1: First Line Must Start with Action Verb
The description's FIRST LINE must begin with one of these action verbs:
- Create, Get, Search, Update, Delete, Execute, Run, Load, Save, List, Show, Check, Build, Parse, Format, Validate, Generate, Apply, Process, Clear, Index, Ingest, Consult, Bridge, Refine, Summarize, Commit, Amend, Revert, Retrieve, Analyze, Suggest, Write, Read, Extract, Query, Filter, Detect, Navigate, Refactor

### Rule 2: Multi-line Description Must Include Args and Returns
For any function with parameters, the description MUST include:
```
Args:
    param_name: Description of the parameter. Defaults to `default_value`.

Returns:
    Description of the return value.
```

### Rule 3: Use description= Parameter (Not Docstring)
The @skill_command decorator MUST have an explicit description= parameter. Function docstrings are optional and secondary."""


def generate_commands_prompt(
    skill_name: str,
    description: str,
    permissions: str,
    rag_context: str,
) -> str:
    """Generate a prompt for creating commands.py.

    Args:
        skill_name: Name of the skill
        description: Natural language description
        permissions: Comma-separated permission list
        rag_context: RAG context string from similar skills

    Returns:
        Formatted prompt string
    """
    return f"""{ODF_EP_RULES}

---

## RAG CONTEXT

{rag_context}

---

Task: Write the `scripts/commands.py` file for a new skill.

Skill Name: {skill_name}
Description: {description}
Permissions: {permissions}

Commands to implement:
- `list_tools()`: List all commands (REQUIRED, always include this exact signature)
- `example()`: Main functionality based on description

Write ONLY the Python code for `scripts/commands.py`. Do NOT include markdown code blocks."""


def generate_readme_prompt(skill_name: str, description: str) -> str:
    """Generate a prompt for creating README.md.

    Args:
        skill_name: Name of the skill
        description: Natural language description

    Returns:
        Formatted prompt string
    """
    return f"""Write a short README.md for skill '{_escape_markdown(skill_name)}'.

Description: {_escape_markdown(description)}

Include:
1. Brief overview
2. Usage examples with @omni() syntax
3. Available commands

Write in Markdown format. No code blocks needed since this is markdown."""


def _escape_markdown(text: str) -> str:
    """Escape special markdown characters."""
    # Simple escaping for common cases
    return text.replace("_", r"\_").replace("*", r"\*")


__all__ = ["generate_commands_prompt", "generate_readme_prompt", "ODF_EP_RULES"]
