---
description: Smart Commit Flow with lefthook checks and security scan
argument-hint: [message_hint]
---

# Smart Commit Workflow

See [agent/skills/git/commit-workflow.md](../../agent/skills/git/commit-workflow.md) for full documentation.

## Quick Usage

```bash
/commit
```

## Workflow

1. **Preparation** - Stage files, run lefthook, check security
2. **Analysis** - Generate commit message with type/scope/files
3. **Confirm** - Press `Yes` to submit, `No` to cancel

## Sensitive Files Detected

If sensitive files are staged, you'll see a security warning. Review carefully before confirming.
