---
description: Smart Commit Workflow - Human-in-the-Loop Commit with Approval
argument-hint: [message]
---

# Smart Commit Workflow

**Command**: `/smart-commit [message]`

## Usage

```python
# Start workflow (no message needed)
omni - git.smart_commit(action: "start")

# After LLM analysis, user approves
omni - git.smart_commit(action: "approve", workflow_id: "{{WORKFLOW_ID}}", message: "{{YOUR_COMMIT_MESSAGE}}")
```

## Workflow

```
User: /smart-commit [message]
    ↓
git.smart_commit (action="start")
    ↓
System: Stage files, scan security, extract diff
    ↓
LLM: Analyze diff → Generate commit message → Show to user
    ↓
User: Review & Confirm (Yes/No)
    ↓
System: Execute commit (if approved)
```

## Commands

| Action    | Description                        | Required Params          |
| --------- | ---------------------------------- | ------------------------ |
| `start`   | Begin workflow, stage & analyze    | -                        |
| `approve` | Approve with LLM-generated message | `workflow_id`, `message` |
| `reject`  | Cancel the commit                  | `workflow_id`            |

## Example

```python
# Step 1: Start workflow - LLM receives workflow_id in response
omni - git.smart_commit(action: "start")

# Step 2: After user confirms "Yes", LLM fills placeholders
omni - git.smart_commit(action: "approve", workflow_id: "{{WORKFLOW_ID}}", message: "{{COMMIT_MESSAGE}}")
```

## Security

- All commits go through security guard (sensitive file detection)
- Pre-commit hooks run automatically
- User must approve before commit executes
