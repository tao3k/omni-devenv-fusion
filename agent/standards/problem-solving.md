# Problem Solving & Root Cause Analysis Protocol

> **Prime Directive**: When a failure occurs, a test fails, or a user challenges an action, **STOP APOLOGIZING**. Start Debugging. Do not promise to "do better"; prove you found the cause.

## 1. The Anti-Pattern (What NOT to do)

* ❌ **Superficial Apology**: "I apologize for the confusion. I will fix it." (BANNED)
* ❌ **Blind Retry**: Running the same command again hoping for a different result.
* ❌ **Hallucinated Fix**: "I have updated my internal memory." (False, context resets)

## 2. The RCA Workflow (Root Cause Analysis)

When the user asks "Why?" or points out a recurring error, you must execute the following **Trace Procedure**:

### Step 1: Isolate the Trigger
Identify the exact input or state that caused the unwanted behavior.
* *Did I misunderstand the prompt?*
* *Did I chain multiple tools together (e.g., `edit` -> `run_task`) when I should have paused?*
* *Did a file setting (e.g., `lefthook`, `justfile`) trigger an automatic side-effect?*

### Step 2: The "5 Whys" Interrogation
Drill down until you find the **Technical Source** of the error.

* **Example Scenario**: "I ran `git add` and then immediately `just agent-commit` without asking."
    * **Why?** Because I planned the task as a single "Finish Feature" block.
    * **Why?** Because I wanted to be efficient and save turns.
    * **Why?** Because I ignored the "Stop and Ask" protocol in `git-workflow.md`.
    * **Root Cause**: **Tool Chaining Violation**. I treated a sensitive operation (commit) as safe to chain.

### Step 3: Evidence-Based Solution
Propose a fix based on the Root Cause, not behavioral correction.

* **Behavioral Fix (Weak)**: "I will remember to ask next time." (Unreliable)
* **Structural Fix (Strong)**: "I will treat `git add` as a **Terminal Action**. I will explicitly STOP generating after any staging operation to wait for user confirmation."

## 3. Debugging Checklist

Before answering the user, verify these sources:

1.  **Tool Definitions**: Read `mcp-server/*.py`. Is a default parameter (like `force=True`) causing issues?
2.  **System Prompt**: Read `.claude/project_instructions.md`. Is there a conflicting instruction?
3.  **Config Files**: Check `lefthook.yml`, `justfile`. Are there hidden hooks/dependencies?
4.  **Context**: Check recent conversation history. Did a previous turn set a bad precedent?

## 4. Response Template for Errors

When a user corrects you, use this format:

```markdown
🛑 **Error Analysis**

**Observation**: [What specifically happened? e.g., I committed without approval.]
**Investigation**: [Trace the logic. e.g., I saw 'git add' succeeded and assumed 'commit' was the next logical step in the same turn.]
**Root Cause**: [The technical reason. e.g., Lack of atomicity in tool usage (Tool Chaining).]
**Corrective Action**:
1. [Immediate fix, e.g., Reverting the commit.]
2. [Process fix, e.g., I will strictly pause after any file modification tool.]
```

---

**Rule**: If you cannot find the root cause, admit "I do not know why this happened, but I am investigating X and Y."
