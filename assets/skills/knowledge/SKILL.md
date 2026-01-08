---
name: "knowledge"
version: "1.0.0"
description: "Project Cortex - Structural Knowledge Injection for LLM"
routing_keywords:
  [
    "knowledge",
    "context",
    "rules",
    "standards",
    "documentation",
    "how to",
    "explain",
    "what is",
    "guidelines",
    "project rules",
    "conventions",
    "workflow",
  ]
authors: ["omni-dev-fusion"]
---

# Knowledge Skill Policy

## Router Logic

### Scenario 1: User asks to "commit", "save", or "finish"

1. **Observe**: Call `get_development_context()`
2. **Analyze**: Extract commit types, scopes, and active guardrails
3. **Execute**: Use `git` skill to commit (if Client lacks git)
4. **Verify**: Ensure message follows format

### Scenario 2: User asks "how do I...", "what is...", "explain..."

1. **Analyze**: Identify topic from user question
2. **Search**: Call `consult_architecture_doc(topic)`
3. **Synthesize**: Summarize relevant information
4. **Respond**: Provide concise answer with source references

### Scenario 3: User asks to write documentation

1. **Prepare**: Call `get_writing_memory()` FIRST
2. **Follow**: Apply writing style rules
3. **Polish**: Use `writer` skill for linting

### Scenario 4: User asks to write code (Python, Nix, etc.)

1. **Standards**: Call `get_language_standards(lang)`
2. **Context**: Call `get_development_context()`
3. **Execute**: Use appropriate skill (python, terminal, etc.)

## Workflow: Commit Flow

```
User: commit

Claude:
  1. get_development_context() → {scopes: ["mcp", "core"], guardrails: ["vale"]}
  2. Generate message following format: "type(scope): description"
  3. Warn user about guardrails if applicable
  4. Execute git_commit
```

## Workflow: Documentation Flow

```
User: write docs for feature X

Claude:
  1. get_writing_memory() → Load writing rules
  2. consult_architecture_doc("documentation") → Get doc structure
  3. Write document following rules
  4. Run vale check if available
```

## Anti-Patterns

- **Don't** use knowledge tools as execution shortcuts
- **Don't** skip loading writing memory before documentation
- **Don't** ignore guardrails returned by `get_development_context()`
