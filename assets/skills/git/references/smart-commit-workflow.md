# Smart Commit Workflow (Phase 36.8)

## Architecture: Tool provides Data, LLM provides Intelligence

```
┌─────────┐     ┌─────────────────────┐     ┌─────────┐
│ prepare │────▶│  LLM Cognitive      │────▶│ execute │
│  Node   │     │  Space (Analysis)   │     │  Node   │
└─────────┘     └─────────────────────┘     └─────────┘
     │                  │                       │
     ▼                  ▼                       ▼
Pre-commit       Analyze diff            Commit hash
Re-stage         Generate message        With retry logic
Stage files      User approval
```

## Usage

```python
# Step 1: Start workflow (Tool stages & extracts diff)
@omni("git.smart_commit", {"action": "start"})

# Step 2: LLM analyzes diff, generates message, user confirms
@omni("git.smart_commit", {"action": "approve", "workflow_id": "abc123", "message": "refactor(core): ..."})

# Or reject
@omni("git.smart_commit", {"action": "reject", "workflow_id": "abc123"})

# Check status
@omni("git.commit_status", {"workflow_id": "abc123"})
```

---

## Workflow Steps

### Step 1: prepare (Tool)

The `prepare` node performs all "dirty work":

1. **Stage all changes**: `git add .`
2. **Run lefthook pre-commit**: May reformat files
3. **Re-stage reformatted files**: Detect and re-stage files that were unstaged by lefthook
4. **Get file list**: `git diff --cached --name-only`
5. **Extract diff**: `git diff --cached` (truncated to 6000 chars)
6. **Security scan**: Check for sensitive patterns (`.env`, `.pem`, `.key`, etc.)

Returns to LLM: `staged_files[]`, `diff_content`, `security_issues[]`

### Step 2: LLM Analysis (Cognitive Space)

LLM receives the tool output and performs analysis:

- **Analyze diff**: Understand what changed
- **Determine type**: `feat`, `fix`, `refactor`, `docs`, `style`, `test`, `chore`
- **Identify scope**: Affected component/module
- **Generate message**: Conventional Commits format: `type(scope): description`
- **Present to user**: Show analysis and ask for confirmation

### Step 3: execute (Tool) with Retry Logic

When user confirms, the execute node runs with intelligent retry:

```
approve
    │
    ├── First try: Original message
    │       │
    │       ├── ✅ Success → completed
    │       │
    │       └── ❌ Failed
    │               │
    │               ├── Retry 1: Lefthook format (re-stage only reformatted files)
    │               │       │
    │               │       ├── ✅ Success → completed
    │               │       │
    │               │       └── ❌ Failed → Retry 2
    │               │               │
    │               │               └── Retry 2: Fix invalid scope
    │               │                       │
    │               │                       ├── ✅ Success → completed
    │               │                       │
    │               │                       └── ❌ Failed → failed
    │
    └── Return result
```

#### Retry Strategy Details

| Error Type      | Retry Action                            | Safety                                        |
| --------------- | --------------------------------------- | --------------------------------------------- |
| Lefthook format | Re-stage only reformatted files         | Safe: only reformatted files, not `git add .` |
| Invalid scope   | Fix scope using `cog.toml` valid scopes | Safe: uses close match or first valid scope   |
| Unknown error   | Mark as failed                          | N/A                                           |

---

## Status Values

| Status               | Meaning                         | Next Action                       |
| -------------------- | ------------------------------- | --------------------------------- |
| `pending`            | Initial state                   | N/A                               |
| `prepared`           | Diff extracted, waiting for LLM | LLM analyzes & generates message  |
| `approved`           | User confirmed                  | Execute commit (with retry)       |
| `rejected`           | User cancelled                  | Workflow ends                     |
| `completed`          | Commit successful               | Done                              |
| `failed`             | All retries failed              | Fix issue, start new workflow     |
| `security_violation` | Sensitive files detected        | Remove files or add to .gitignore |
| `error`              | Workflow error                  | Check error message               |
| `empty`              | No files staged                 | Stage changes first               |

---

## Example Output

### Step 1: Tool returns review_card.j2 template (for LLM analysis)

The tool returns a Jinja2 template string from `templates/review_card.j2`. LLM parses and fills it.

````markdown
### 📋 Commit Analysis

| Field           | Value               |
| --------------- | ------------------- | --- | -------- | ---- | ----- | ---- | ------ |
| **Type**        | `feat               | fix | refactor | docs | style | test | chore` |
| **Scope**       | `git`               |
| **Description** | {short_description} |

#### 📁 Files to commit (already staged)

- `assets/skills/git/scripts/smart_workflow.py` - {change_summary}
- `assets/skills/git/scripts/prepare.py` - {change_summary}
- `assets/skills/git/tools.py` - {change_summary}

#### 📝 Message

```

refactor(git): simplify smart commit workflow architecture

- Simplified workflow from 3 nodes to 2 nodes
- Moved analysis logic from Python to LLM
- Added stage_and_scan() helper function

---
*🤖 Generated with [Claude Code](https://claude.com/claude-code)*

*Co-Authored-By: Claude <noreply@anthropic.com>*

**IMPORTANT**: Include ALL files shown in the staged diff in your analysis.

## ✅ Approval

After user confirms "Yes", call:
```

@omni("git.smart_commit", {
"action": "approve",
"workflow_id": "a1b2c3",
"message": "refactor(git): simplify smart commit workflow architecture\n\n- Simplified workflow..."
})

```

```
````

---

**🤖 LLM INSTRUCTION:**

1. **Parse** the Jinja2 template and fill placeholders
2. **Analyze** the diff to understand changes
3. **Generate** Conventional Commits message (type(scope): description + bullet points)
4. **Present** the analysis to user, ask for "Yes" confirmation
5. **On user "Yes"**: Call `git.smart_commit` with approve action

### Step 2: After approval (with retry note)

```markdown
## ✅ Commit Successful!

**refactor(git): simplify smart commit workflow architecture**

- Simplified workflow from 3 nodes to 2 nodes
- Moved analysis logic from Python to LLM
- Added stage_and_scan() helper function

---

📅 Date: 2026-01-12 19:56:27
📁 Files: 10 files changed

🛡️ **Verified by**: omni Git Skill (cog)
🔒 **Security Detection**: No sensitive files detected
```

### Failed Example

```markdown
## ❌ Commit Failed

**Commit Failed**

Invalid scope: git-ops

---

📅 Date: 2026-01-12 19:56:27

**Error**: Commit failed after retries. Invalid scope

Please fix the issue and start a new workflow.
```

---

## Security Features

| Check            | Action                                  |
| ---------------- | --------------------------------------- |
| Sensitive files  | Block with warning, list affected files |
| Lefthook failure | Block, show errors                      |
| Nothing staged   | Return clean status                     |

### Sensitive File Patterns

```
*.env*, *.pem, *.key, *.secret, *.credentials*
id_rsa*, id_ed25519*
secrets.yml, credentials.yml
```

---

## Technical Details

### State Schema

```python
class CommitState:
    project_root: str
    staged_files: List[str]
    diff_content: str      # For LLM analysis
    security_issues: List[str]
    status: str            # "pending", "prepared", "approved", "rejected", ...
    workflow_id: str       # Unique checkpoint ID
    final_message: str     # LLM-generated commit message
    commit_hash: str
    error: Optional[str]
    retry_note: Optional[str]  # For tracking retry actions
```

### LangGraph Flow

```
start_workflow() → [prepare] → (interrupt before execute)
                                 ↓
approve_workflow(msg) → [execute with retry] → END
reject_workflow() → END
```

### Files

| File                               | Purpose                               |
| ---------------------------------- | ------------------------------------- |
| `scripts/commit_state.py`          | State schema (TypedDict)              |
| `scripts/prepare.py`               | `stage_and_scan()` function           |
| `scripts/smart_workflow.py`        | LangGraph workflow with retry logic   |
| `scripts/rendering.py`             | Commit message template rendering     |
| `templates/review_card.j2`         | Review card template for LLM analysis |
| `templates/commit_message.j2`      | Final commit message template         |
| `tools.py`                         | `smart_commit` tool interface         |
| `tests/test_git_smart_workflow.py` | Unit tests                            |

### Tests

```bash
# Run smart workflow tests
pytest assets/skills/git/tests/test_git_smart_workflow.py -v

# Test categories:
# - TestCommitState: State schema validation
# - TestScopeFixing: Commit message scope fixing
# - TestWorkflowConstruction: Graph building
# - TestNodeExecute: Execute node with retry logic
# - TestRetryLogic: Retry edge cases
# - TestReviewCard: Review card formatting
```
