# Documentation Standards

> Keywords: documentation, standards, structure, conventions

## Document Classification

| Directory           | Audience | Purpose                                   | Examples                               |
| ------------------- | -------- | ----------------------------------------- | -------------------------------------- |
| `agent/knowledge/`  | LLM      | Troubleshooting, patterns, best practices | deadlock patterns, cache strategies    |
| `agent/how-to/`     | LLM      | Step-by-step workflow guides              | git workflow, testing workflow         |
| `docs/explanation/` | Users    | Design decisions, philosophy              | architecture decisions, why we chose X |
| `docs/reference/`   | Users    | API documentation, config reference       | MCP tool reference                     |
| `docs/tutorials/`   | Users    | Step-by-step tutorials                    | getting started guide                  |

## Naming Conventions

### File Names

- Use kebab-case: `git-workflow.md`, `testing-guidelines.md`
- No spaces, no camelCase
- Descriptive and searchable

### Frontmatter

```markdown
# Document Title

> Keywords: keyword1, keyword2, keyword3

## Summary paragraph...

---
```

**Required:**

- H1 title (`# Title`)
- Keywords line (`> Keywords: ...`)
- Summary paragraph

## Content Guidelines

### agent/knowledge/

**Purpose:** Troubleshooting, patterns, anti-patterns, best practices

**Structure:**

```
# [Topic] Pattern/Guide

> Keywords: relevant, keywords

## Problem/Symptom
Describe the issue...

## Root Cause
Explain why it happens...

## Solution
Show how to fix it...

## Related
- Link to related docs
```

**Examples:**

- `threading-lock-deadlock.md`
- `uv-workspace-config.md`

### agent/how-to/

**Purpose:** Step-by-step workflows

**Structure:**

````
# [Action] Guide

> Keywords: action, workflow, steps

## When to Use
Briefly describe when to follow this guide...

## Steps
1. Step one
2. Step two
3. ...

## Example
```bash
# Code example
````

## Related

- Link to related docs

````

**Examples:**
- `gitops.md`
- `testing-workflows.md`

## Document Creation Rules

### Before Creating a Document

1. **Check existing docs** - Does this content already exist?
2. **Choose correct directory** - Is it knowledge or how-to?
3. **Verify uniqueness** - Will this duplicate existing content?

### Document Creation Protocol

```python
# Before creating ANY documentation:

1. Search existing docs:
   - Grep for keywords
   - Check table of contents

2. Determine correct location:
   - Troubleshooting → agent/knowledge/
   - Step-by-step → agent/how-to/
   - User explanation → docs/explanation/

3. Follow naming convention:
   - kebab-case.md
   - descriptive name
````

### What NOT to Do

| Violation         | Example                            | Why                     |
| ----------------- | ---------------------------------- | ----------------------- |
| Wrong directory   | RAG guide in agent/knowledge/      | Mixing concerns         |
| Wrong naming      | `MyDoc.md`                         | Should be `my-doc.md`   |
| Missing keywords  | No `> Keywords:` line              | Reduces discoverability |
| Duplicate content | `git-guide.md` + `git-workflow.md` | Duplication             |

## Document Review Checklist

- [ ] Correct directory placement
- [ ] Kebab-case filename
- [ ] H1 title present
- [ ] Keywords line present
- [ ] Summary paragraph present
- [ ] No duplicate content
- [ ] Follows structure template
- [ ] Related links included

## Enforcement

When creating documentation:

1. **Verify location** before creating file
2. **Check naming** matches convention
3. **Add keywords** for RAG discoverability
4. **Link to related** docs

This ensures the knowledge base remains organized and searchable.

## Related

- `agent/knowledge/README.md`
- `docs/index.md`
