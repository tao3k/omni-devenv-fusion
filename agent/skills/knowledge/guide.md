# Knowledge Skill Guide

> "Knowledge is power." This skill fetches that power.

## Purpose

The **Knowledge Skill** is the **Project Cortex** - it reads project constraints, rules, and status to "enlighten" the LLM.

**It does NOT:**
- Execute commands
- Edit files
- Make decisions

**It ONLY:**
- Returns structured project knowledge
- Searches documentation
- Loads writing standards

## When to Use

### Before Writing Code
```python
# Get all rules that apply
get_development_context()
```

### Before Committing
```python
# Understand commit rules and scopes
context = get_development_context()
# Check writing standards
writing = get_writing_memory()
```

### When You Need Guidance
```python
# Search for specific topics
consult_architecture_doc("git workflow")
consult_architecture_doc("nix configuration")
consult_architecture_doc("writing style")
```

### When Writing Documentation
```python
# Always load writing memory first
get_writing_memory()
```

## Tools Reference

| Tool | Purpose | When to Call |
|------|---------|--------------|
| `get_development_context()` | Get project rules, scopes, guardrails | Before any work |
| `consult_architecture_doc(topic)` | Search documentation | When unsure about process |
| `get_writing_memory()` | Get writing style guide | Before writing docs |
| `get_language_standards(lang)` | Get language-specific standards | Before writing code |

## Output Examples

### get_development_context()
```json
{
  "project": "omni-devenv-fusion",
  "git_rules": {
    "types": ["feat", "fix", "docs", "style", "refactor", ...],
    "scopes": ["core", "mcp", "git"],
    "message_format": "<type>(<scope>): <description>"
  },
  "guardrails": [
    {"name": "vale", "description": "Writing style check"},
    {"name": "nixfmt", "description": "Format Nix code"}
  ]
}
```

### consult_architecture_doc()
Returns relevant markdown content from docs/ or agent/ directories.

## Anti-Patterns

### ❌ Don't: Use knowledge tools to execute
```python
# WRONG - Knowledge tools don't execute
result = consult_architecture_doc("git")
# ... then try to run git commands based on result
```

### ✅ Do: Use knowledge for context, then execute
```python
# CORRECT - Get context, then use appropriate skill
rules = get_development_context()
# ... now you know the rules
# ... use git/terminal skills to execute
```
