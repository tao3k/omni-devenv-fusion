---
description: Smart Commit Flow (Stage -> Lefthook -> Analyze -> Commit)
argument-hint: [message]
---

# Smart Commit Workflow

Please execute the following 3-step workflow to ensure code quality and meaningful commit messages.

## Step 1: Preparation & Checks

Call the Omni tool to stage files and run quality checks:
`@omni("git.prepare_commit")`

## Step 2: Analysis & Report

**IF** the preparation tool returns "✅ Checks Passed":

1. **Analyze** the staged diff provided in the tool output.
2. **Determine** the commit Type (feat, fix, refactor, docs, style, test, chore) and Scope.
3. **Generate** a commit analysis report using this template:

```markdown
### 📋 Commit Analysis

| Field           | Value               |
| --------------- | ------------------- |
| **Type**        | `{type}`            |
| **Scope**       | `{scope}`           |
| **Description** | {short_description} |

#### 📁 Files to commit (already staged)

- `{file1}` - {change1}
- `{file2}` - {change2}
- ...

#### 📝 Message
```

{type}({scope}): {description}

- {change_detail_1}
- {change_detail_2}
- ...

````

---
*🤖 Generated with [Claude Code](https://claude.com/claude-code)*

*Co-Authored-By: Claude <noreply@anthropic.com>*

**IMPORTANT**: Include ALL files shown in the staged diff in your analysis.

**Please confirm:** Reply Yes👍 to submit commit, or No👎 to cancel

<!-- LLM read only: invoke @omni("git.execute_commit", {"message": "YOUR_GENERATED_MESSAGE"}) - DON'T PRINT -->


---

**IF** the preparation tool returns "❌ Checks Failed":

- Stop the workflow.
- Display the errors to me so I can fix them.

```

```
````
