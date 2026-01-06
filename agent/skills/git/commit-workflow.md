# Smart Commit Workflow

## Usage

```bash
/commit
```

## Workflow

### Step 1: Preparation & Checks

1. Auto-stage all changes
2. Run lefthook `pre-commit` hooks
3. Re-stage any auto-fixed files
4. Check for sensitive files (`.env`, `.pem`, `.key`, etc.)

### Step 2: Analysis & Report

Claude analyzes staged changes and generates:

- **Commit Type** (feat, fix, refactor, docs, style, test, chore)
- **Scope** (affected component)
- **File List** with change descriptions
- **Lefthook Report** (version, hook output)
- **Security Check** (if sensitive files detected)

### Step 3: Execute Commit

**Press `Yes`** to confirm commit, or **`No`** to cancel.

---

## Example Output

```
🔄 Staged Files Detected - Ready to Commit

🥊 lefthook v2.0.12  hook: pre-commit
✔️ format-python (0.06s)
✔️ prettier (0.10s)

### Commit Analysis
| Type     | refactor |
| Scope    | git      |
| Desc     | Add security check |

📁 Files (2):
- agent/skills/git/tools.py - sensitive file detection
- .claude/commands/commit.md - usage docs

📝 Message:
refactor(git): Add sensitive file security check

- Add _check_sensitive_files() helper
- Detect .env, .pem, .key patterns
- Show LLM advisory warning

**Please confirm:** Press `Yes` to submit, or `No` to cancel.
```

---

## Security Features

| Check            | Action                         |
| ---------------- | ------------------------------ |
| Sensitive files  | Show warning with LLM advisory |
| Lefthook failure | Block commit, show errors      |
| Nothing staged   | Return clean status            |

## Sensitive File Patterns

```
*.env*, *.pem, *.key, *.secret, *.credentials*
*.psd, *.ai, *.sketch, .fig
id_rsa*, id_ed25519*, *.priv
secrets.yml, credentials.yml
```
