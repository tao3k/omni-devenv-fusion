---
description: Smart Commit Workflow - Human-in-the-Loop Commit
argument-hint: [message]
---

# Smart Commit Workflow

## Steps

1. **Start**: `@omni git.smart_commit(action='start')`
   - LLM reads output: commit analysis table, git diff, valid scopes

2. **Analyze**: Review diff → Generate commit message (conventional format)

3. **Approve**: `@omni git.smart_commit(action='approve', workflow_id='xxx', message='type(scope): description')`

## User Confirmation

After step 2, print commit message and ask user:

- Reply **Yes** → Proceed to step 3
- Reply **No** → Cancel
