---
description: Smart Commit Workflow - Human-in-the-Loop Commit
argument-hint: [message]
---

# Smart Commit Workflow

## Steps

1. **Start**: `@omni("git.smart_commit", {"action": "start"})`
   - Stages files with `git add -A`
   - Runs lefthook pre-commit (formatting: cargo fmt, ruff, etc.)
   - Re-stages any modified files
   - Shows lefthook summary, git diff, valid scopes

2. **Analyze**: Review output → Generate commit message (conventional format)

3. **Approve**: `@omni("git.smart_commit", {"action": "approve", "workflow_id": "xxx", "message": "type(scope): description"})`

## User Confirmation

After step 1, print commit message and ask user:

- Reply **Yes** → Output approve command
- Reply **No** → Cancel

## After User Confirms "Yes"

Output the approve command:

```markdown
## Ready to Commit!

### Approve Commit

@omni("git.smart_commit", {"action": "approve", "workflow_id": "WORKFLOW_ID", "message": "COMMIT_MESSAGE"})
```
