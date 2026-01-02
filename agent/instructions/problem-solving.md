Problem Solving Guide

> Learn from debugging sessions. Document patterns to avoid repeated mistakes.

---

## Timeout Debugging Protocol

### The Timeout Anti-Pattern

**Wrong Approach:**

```python
# Running the same command multiple times hoping it will succeed
uv run python test.py
uv run python test.py
uv run python test.py  # Still failing? Try again!
# Trapped in endless test loop
```

**Correct Approach - Error Correction:**

```
1st timeout: "Might be temporary issue, retry"
2nd timeout: "Pattern detected! Stop repeating, start investigating"
3rd timeout: "Definite issue! Systematic debugging required"
```

### Rule of Three

When a command times out **3 times**, must execute error correction:

| Attempt | Action                       | Reason                                       |
| ------- | ---------------------------- | -------------------------------------------- |
| 1       | Retry                        | Might be temporary issue                     |
| 2       | Check processes              | `ps aux \| grep python` for zombie processes |
| 3       | **Systematic investigation** | Start problem solving workflow               |

**Must stop doing:**

- ❌ Continue repeating same command
- ❌ Assume "next time will succeed"
- ❌ Ignore logs and process states

**Must start doing:**

- ✅ Check for lingering processes
- ✅ Simplify test case
- ✅ Binary search for problematic module
- ✅ Document findings

### Timeout Investigation Checklist

When a command times out repeatedly:

| Step | Action                     | Why                                  |
| ---- | -------------------------- | ------------------------------------ |
| 1    | Check for zombie processes | `ps aux \| grep python`              |
| 2    | Check for file locks       | `.pyc`, `__pycache__`                |
| 3    | Simplify the test case     | Remove unrelated imports             |
| 4    | Test in isolation          | Run file directly, not via framework |
| 5    | Check syntax first         | `python -m py_compile file.py`       |
| 6    | Check imports one by one   | Binary search the problematic module |

### Common Timeout Causes

| Cause                 | Solution                                         |
| --------------------- | ------------------------------------------------ |
| Process fork deadlock | See `agent/knowledge/threading-lock-deadlock.md` |
| Import cycle          | Refactor to break circular dependencies          |
| Network timeout       | Check connectivity, increase timeout             |
| Infinite loop         | Add timeout, simplify logic                      |

### Knowledge Base

For language-specific issues, search the knowledge base:

```bash
# When you encounter a specific technical issue:
# 1. Identify keywords (e.g., "threading", "deadlock", "uv")
# 2. Search in agent/knowledge/
# 3. Read the corresponding .md file for solution

# Example: Python threading deadlock
See: agent/knowledge/threading-lock-deadlock.md

---

## Import Path Conflicts

### Symptom
```

ModuleNotFoundError: No module named 'module_name'

````

### Diagnosis
```bash
# Check where Python is looking
python3 -c "import sys; print(sys.path)"

# Find all module locations
find /project -name "module_name" -type d
````

### Solution: Workspace Configuration

```toml
# pyproject.toml (root)
[tool.uv.workspace]
members = ["mcp-server"]

[tool.uv.sources]
package_name = { workspace = true }
```

**Key insight:** `project.dependencies` must be PEP 508 compliant. Use `[tool.uv.sources]` for workspace packages.

---

## Debugging Commands

```bash
# Check for hanging processes
ps aux | grep python

# Kill stuck processes
pkill -9 -f "python.*mcp"

# Clear cache
find . -name "__pycache__" -exec rm -rf {} +

# Syntax check
python -m py_compile suspicious.py

# Test in isolation
cd module_dir && python -c "import module"
```

---

## When to Ask for Help

- Timeout persists after 3 different investigation approaches
- Deadlock involving system resources (locks, threads, signals)
- Import path conflicts that `uv sync` doesn't resolve
- Language-specific issues → Search `agent/knowledge/`

---

## Authorization Protocol Enforcement

### The Problem: Context Switching Errors

**Symptom:** LLM skips required authorization step and executes restricted action.

**Case Study: Unauthorized Commit**

```
User: "run commit"
LLM: load_git_workflow_memory() → protocol: "stop_and_ask"
LLM: Check git status, show diff
User: "hao"
LLM: → Executes just agent-commit (WRONG!)
```

### Root Cause Analysis

**Wrong Interpretation:**

- User said "hao" → LLM interpreted as "authorization granted"

**Correct Interpretation:**

- Protocol requires: "run just agent-commit" (exact phrase)
- User said "hao" → Means "continue" or "ok I see", NOT authorization

**The Missing Step:**

```
User: "run commit"
LLM: smart_commit() → returns "authorization_required: true"
LLM SHOULD: STOP immediately, ask for exact authorization phrase
LLM DID: Assumed "hao" = authorization, proceeded
```

### The Fix: Explicit Authorization Pattern

When any tool returns `authorization_required: true`:

```python
# WRONG: Continue with assumption
if user_response == "hao":
    execute_operation()  # ❌ Skipped authorization check

# CORRECT: Require exact phrase
if "run just agent-commit" in user_message:
    execute_operation()  # ✅ Explicit authorization
else:
    stop_and_wait()  # ✅ Request exact phrase
```

### Protocol Enforcement Checklist

| Step | Action                                           | Why                                            |
| ---- | ------------------------------------------------ | ---------------------------------------------- |
| 1    | Check tool response for `authorization_required` | Some protocols require explicit consent        |
| 2    | If required=true, IMMEDIATELY STOP               | Do not proceed past this point                 |
| 3    | Display authorization requirement                | Show user what phrase is needed                |
| 4    | WAIT for exact authorization                     | Don't assume "ok", "yes", "go" = authorization |
| 5    | Only execute after exact match                   | Match the protocol's required phrase           |

### Anti-Patterns

| Wrong                          | Why                                      |
| ------------------------------ | ---------------------------------------- |
| Assuming "yes" = authorization | Protocol defines exact phrases           |
| Continuing after "ok"          | User may mean "I understand" not "do it" |
| Partial matches                | "run commit" ≠ "run just agent-commit"   |

### Pattern: Stop → Verify → Execute

```
STOP: When authorization_required: true, halt all actions
VERIFY: Check for exact authorization phrase in user response
EXECUTE: Only after verification passes
```

---

## Root Cause Analysis Framework

### The Five Whys Method

When a problem occurs, ask "why" repeatedly until reaching the root cause:

```
Problem: LLM executed unauthorized action
Why 1: User said "hao" and LLM proceeded
Why 2: LLM interpreted "hao" as authorization
Why 3: Protocol requires exact phrase but LLM accepted "hao"
Why 4: LLM didn't check for authorization_required flag
Why 5: No enforcement rule for authorization protocol
                      ↓
Root Cause: Missing protocol enforcement rule
```

### Verification Checklist

Before executing any action that requires authorization:

- [ ] Does the protocol require explicit authorization?
- [ ] Did I check for `authorization_required: true`?
- [ ] Did I receive the exact authorization phrase?
- [ ] Did I verify the phrase matches protocol requirements?
- [ ] Am I about to execute without verification?

### Self-Correction Loop

```
ACT → OBSERVE → ORIENT → ACT
          ↑___________|
```

1. **ACT**: Execute action
2. **OBSERVE**: Check response (did it require authorization?)
3. **ORIENT**: Adjust behavior based on response
4. **ACT**: Corrected action (stop and ask)

---

## Core Principle: Actions Over Apologies

> **When problems occur, do NOT say "sorry" or "I will improve".**
> **Instead, demonstrate concrete actions that solve the root cause.**

### The Problem-Solving Formula

```
Identify Problem → Do NOT Apologize → Execute Concrete Actions → Verify Fix → Document Lessons
```

### Concrete Action Checklist

| Phase           | Action                                | Example                                                 |
| --------------- | ------------------------------------- | ------------------------------------------------------- |
| 1. Verify Docs  | Check if rule docs are correct        | `git-workflow.md` authorization rules are explicit      |
| 2. Check Code   | Validate Python implementation        | `smart_commit()` returns `authorization_required: true` |
| 3. Update Rules | Fix docs or code                      | Add explicit enforcement rules                          |
| 4. Verify       | Ensure fix works                      | Test in new session                                     |
| 5. Document     | Update this file (problem-solving.md) | Add case study to prevent recurrence                    |

### Anti-Pattern: Empty Response

```
x "Sorry, I will improve." (no action)
x "I understand, won't happen again." (no fix)
x "I will be careful." (no verification)
```

### Correct Pattern: Demonstrated Fix

```
+ Problem: LLM executed commit without authorization
+ Check: git-workflow.md logic correct, Python implementation correct
+ Fix: Updated git-workflow.md with "IMMEDIATELY STOP" rule
+ Code: manage_context now auto-loads project rules
+ Verify: New session calls manage_context to get rules automatically
+ Document: Added case study to this file
```

### Key Takeaway

> **Don't say you'll fix it. Fix it. Then prove it's fixed.**

---

_Document patterns. Break the loop._
