# Development Context

## Overview

The development context provides project-specific rules, conventions, and guardrails that AI agents must follow.

## Structure

```json
{
  "project": "omni-dev-fusion",
  "git_rules": {
    "types": ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore"],
    "scopes": ["mcp", "core", "foundation", ...],
    "message_format": "<type>(<scope>): <description>",
    "policy": "Conventional Commits + Atomic Steps"
  },
  "guardrails": [
    {"name": "nixfmt", "description": "Format Nix code"},
    {"name": "ruff", "description": "Python linting"}
  ],
  "writing_style": {
    "language": "english_only",
    "max_sentence_length": 25,
    "list_max_items": 4
  }
}
```

## Usage

```python
@omni("knowledge.get_development_context")
```

## Related Commands

- `get_development_context` - Retrieve full context
- `get_language_standards(lang)` - Get language-specific standards
