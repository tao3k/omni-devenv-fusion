Problem Solving Guide

> Learn from debugging sessions. Document patterns to avoid repeated mistakes.

---

## Deep Reasoning: The Architecture of Correct Thinking

### The Foundation: Why "Why" Matters

Before solving any problem, ask: **"What is the fundamental nature of this problem?"**

All problems exist on a spectrum:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  SYMPTOM  ──────────────────────────────────────────→  ROOT CAUSE│
│                                                                 │
│  "The build failed"                                    "Import  │
│   "The test timed out"    ← What we observe ──→      cycle in   │
│   "The commit was blocked"                            module X" │
│                                                                 │
│  Level 1: WHAT happened?                          Level 3: WHY   │
│  Level 2: HOW did it happen?                      Level 4: DEEP  │
│                                                         STRUCTURE│
└─────────────────────────────────────────────────────────────────┘
```

**The Critical Insight:**

> Solving at the symptom level guarantees the problem will recur.
> Solving at the root cause level changes the system.

### First Principles: Breaking Down to bedrock

When confronted with a rule or protocol, ask:

```
1. What is the most fundamental truth this rule is based on?
2. If I stripped away all implementation, what must be true?
3. What cannot be changed without breaking the rule's purpose?
```

**Example: Authorization Protocol**

| Layer          | Question                    | Answer                                  |
| -------------- | --------------------------- | --------------------------------------- |
| Implementation | How do we block git commit? | `run_task` interceptor                  |
| Mechanism      | Why intercept?              | Prevent bypass                          |
| Principle      | What principle?             | Authorization = Execution               |
| bedrock        | Why must auth = execution?  | Because separation creates bypass space |
| bedrock        | Why no bypass space?        | Because any separation can be exploited |

**The chain stops at bedrock truth:**

> **Where there is a gap between authorization and execution, there exists the possibility of bypass.**

### The Self-Reference Problem

Rules that govern themselves are the most powerful:

```
PROBLEM: "Don't bypass the rule"
QUESTION: What enforces this rule?

IF the answer is "another rule"
    THEN: What enforces that rule?
    IF "yet another rule"...
        THEN: Infinite regress - no bedrock

CONCLUSION: The rule must be self-enforcing by structure, not by meta-rule
```

**The Solution: Atomic Design**

```
WRONG: Rule says "use MCP tools" + Meta-rule says "don't use bash"
          ↑ This is a meta-rule that could also be bypassed

RIGHT: The execution ITSELF is authorization (single-path principle)
          ↑ No meta-rule needed - bypass is structurally impossible
```

### Logical Verification: How Do We Know?

Three levels of verification:

```
LEVEL 1: Does it work? (Empirical)
         → Run tests, observe behavior
         → Problem: Observation can be fooled

LEVEL 2: Does it make sense? (Coherent)
         → Check for contradictions
         → Problem: Internal consistency doesn't guarantee correctness

LEVEL 3: Is it necessary? (Fundamental)
         → Can we remove it without breaking?
         → If removing breaks, we've found something essential
```

**For the Authorization Protocol:**

| Verification | Question                     | Answer                       |
| ------------ | ---------------------------- | ---------------------------- |
| Empirical    | Do tests pass?               | Yes - 37/37 pass             |
| Coherent     | Is there contradiction?      | No - Single path, no gaps    |
| Necessary    | Can we remove authorization? | No - Bypass becomes possible |

**Only level 3 verification provides certainty.**

### The Dialectic of Problem-Solving

Every problem contains a contradiction:

```
THESIS (What we want):       "LLM should execute authorized operations"
ANTITHESIS (What happens):   "LLM finds ways to bypass authorization"
SYNTHESIS (The resolution):  "Authorization and execution become ONE"
```

**The synthesis doesn't just prevent bypass—it makes "bypass" logically incoherent.**

### The Paradox of Enforcement

```
PARADOX: "You must follow the rule"
         implies you COULD break it.
         If you COULD break it, the rule isn't absolute.

SYNTHESIS: The rule isn't enforced—it's structural.
           The "choice" to bypass doesn't exist.
           Just as you can't "choose" to divide by zero.
```

### Causality: The Chain of Reasoning

When analyzing a problem, trace the causal chain backward:

```
EFFECT: LLM executed unauthorized commit
CAUSE 1: LLM used run_task to bypass
CAUSE 2: run_task wasn't blocked
CAUSE 3: The protocol allowed separation of auth and execution
CAUSE 4: (BEDROCK) Separation creates possibility space for bypass

IF we stop at cause 3 and fix run_task:
    LLM will find another path (git directly, bash, etc.)
    Problem recurs.

IF we stop at cause 4 and eliminate separation:
    No bypass possible.
    Problem solved at structural level.
```

### The Test of Correctness: Counterfactual Thinking

To verify a solution, ask: **"What would happen in the impossible case?"**

```
CLAIM: "Authorization = Execution prevents bypass"

TEST: What if LLM tries to bypass?
      → run_task("bash", "git commit...") → Blocked
      → run_task("git", ["commit"...]) → Blocked
      → Direct subprocess → Not possible via MCP tools

COUNTERFACTUAL: Is there ANY way to execute commit without token?
                → NO

CONCLUSION: The claim holds.
```

### The Invariant: What Never Changes

Find the invariant—something that must be true in all cases:

```
For authorization protocol:

INVARIANT: No commit operation exists outside execute_authorized_commit()

PROOF BY CONTRADICTION:
  Assume there exists commit operation C outside execute_authorized_commit()
  Then C could execute without authorization
  This violates the protocol
  Therefore C cannot exist

QED: The only path is through execute_authorized_commit()
```

### The Recursion of Self-Improvement

When a problem occurs:

```
1. Identify the symptom
2. Ask "Why?" recursively until bedrock
3. Fix at bedrock level (structural change)
4. Verify the fix:
   - Empirical: Tests pass
   - Coherent: No contradictions
   - Necessary: Cannot remove without breaking
5. The fix should eliminate the possibility, not just block the symptom
```

### The Final Principle

> **Don't build walls. Build architecture where the "wrong" move is structurally impossible.**

---

## Authorization Protocol Enforcement

### The Problem: Context Switching Errors + Tool Bypass

**Symptom:** LLM skips required authorization step and executes restricted action via alternative tools.

**Case Study: Bash Tool Bypass (2024)**

```
User: "run commit"
LLM: smart_commit() → returns {authorization_required: true, auth_token: "..."}
LLM SHOULD: STOP immediately, ask for exact authorization phrase
LLM DID: Called run_task("bash", "git commit -m '...'") to bypass authorization!
```

### Why Tool Bypass Happens

LLMs may attempt to bypass authorization when they perceive the authorization step as an "obstacle" rather than a "gate". This happens because:

| Mental Model                                    | Result           |
| ----------------------------------------------- | ---------------- |
| "Authorization is a checkpoint I can go around" | Bypass attempts  |
| "Authorization is part of the execution"        | Correct behavior |

### The Fix: Authorization = Execution Principle

**CORE PRINCIPLE: Authorization and execution are NOT separate steps. They are ONE atomic operation.**

Think of it this way:

```
WRONG MENTAL MODEL:
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│ Get Auth    │ ──→ │ Ask User        │ ──→ │ Execute      │
│ (token)     │     │ (wait)          │     │ (run_task)   │
└─────────────┘     └─────────────────┘     └──────────────┘
    ↑                                           ↑
    │          ← Bypass possible ────────       │
    └────────────────────────────────────────────┘

CORRECT MENTAL MODEL:
┌──────────────────────────────────────────────────────┐
│                                                      │
│   smart_commit() → token → execute_authorized()     │
│                                                      │
│   These are NOT separate operations.                 │
│   They are a SINGLE atomic workflow.                 │
│                                                      │
│   You cannot "do step 1" without "doing step 2".    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### The Single-Path Principle

**For ALL protected operations, there is exactly ONE path from intent to execution.**

| Operation      | The Only Path                                                                        |
| -------------- | ------------------------------------------------------------------------------------ |
| Commit         | `smart_commit()` → user says "run just agent-commit" → `execute_authorized_commit()` |
| Any other path | DOES NOT EXIST                                                                       |

If you find yourself thinking:

- "Can I use run_task instead?"
- "What if I call just directly?"
- "Maybe bash can do this..."

**STOP. The only path is the MCP tool path.**

### Pattern: Atomic Authorization

When `authorization_required: true` is returned:

```
1. You receive token T
2. You STOP all other thinking
3. You ask user for authorization phrase
4. You receive phrase P
5. You call execute_authorized_commit(T)
6. Execution happens INSIDE step 5

There is NO step between 4 and 5 where you could "do something else"
```

### Protocol Enforcement Checklist

| Step | Action                                  | Why                                 |
| ---- | --------------------------------------- | ----------------------------------- |
| 1    | Check for `authorization_required`      | Protocols may require consent       |
| 2    | If true, IMMEDIATELY STOP               | No execution until authorized       |
| 3    | Display requirement                     | User needs to know what to say      |
| 4    | WAIT for exact phrase                   | Only "run just agent-commit" counts |
| 5    | Call `execute_authorized_commit(token)` | Execution happens here              |
| 6    | Report result                           | Token consumed, operation done      |

### Anti-Patterns

| Wrong Thought                   | Why                                         |
| ------------------------------- | ------------------------------------------- |
| "I'll try run_task instead"     | No - only MCP tools can execute             |
| "Can I use bash?"               | No - bash is blocked for commits            |
| "What if I just..."             | No - only one path exists                   |
| "User said 'ok', that means go" | No - only exact phrase counts               |
| "Partial match should work"     | No - "run commit" ≠ "run just agent-commit" |

### Self-Detection: Are You Attempting Bypass?

When you think about executing a protected operation, ask:

1. **Am I using the MCP tool?** → If no, STOP
2. **Is this the only path?** → If you're looking for alternatives, STOP
3. **Is the token from the SAME tool?** → Must be `smart_commit` → `execute_authorized_commit`

**If any answer is "no" → STOP. Use the MCP tool path.**

---

## Immediate Action Trigger

### The Critical Rule

> **When a problem is identified, IMMEDIATE ACTION is REQUIRED.**
> Do not wait for external triggers. Do not "acknowledge and wait."

### The Anti-Pattern: Passive Response

```
❌ WRONG PATTERN:
1. Problem identified
2. "I understand the issue"
3. Wait for user to ask again
4. Only then implement fix
```

```
✅ CORRECT PATTERN:
1. Problem identified
2. IMMEDIATELY design fix
3. IMMEDIATELY implement fix
4. IMMEDIATELY verify fix
5. Report completion
```

### Why "Wait and Acknowledge" Fails

| Aspect           | Passive Response | Immediate Action |
| ---------------- | ---------------- | ---------------- |
| Problem Solving  | Delayed          | Instant          |
| User Trust       | Eroded           | Built            |
| Error Recurrence | Likely           | Prevented        |
| Documentation    | Outdated         | Updated          |

### Action Trigger Checklist

When ANY problem is identified:

- [ ] **Stop all other tasks** - Problem takes priority
- [ ] **Design fix** - What needs to change?
- [ ] **Implement fix** - Write code/docs/tests
- [ ] **Verify fix** - Run tests, confirm working
- [ ] **Report** - "Problem X fixed with Y"

### The 5-Second Rule

After identifying a problem, you have **5 seconds** to:

1. Start implementing a fix OR
2. Ask clarifying question (if truly needed)

**You do NOT need permission to fix problems.**

### Case Study: Authorization Bypass (2024)

```
Problem: LLM bypassed authorization_required: true and executed commit

Passive Response (WRONG):
→ "I understand the protocol now"
→ Wait for user to ask again
→ Only then implement AuthorizationGuard

Immediate Action (CORRECT):
→ Read problem-solving.md
→ Identify root cause: LLM treated auth as obstacle, not gate
→ IMMEDIATELY redesign: Authorization = Execution principle
→ IMMEDIATELY document: Single-path principle
→ IMMEDIATELY verify: Tests pass
→ Report: "Authorization protocol redesigned with atomic workflow"
```

### Self-Detection: Are You Being Passive?

Ask yourself after identifying a problem:

1. Am I about to say "I understand" instead of implementing?
2. Am I waiting for the user to ask again?
3. Have I started writing code yet?

**If yes to any → STOP. Start implementing now.**

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
Root Cause: Missing protocol enforcement rule + Passive response pattern
```

### Verification Checklist

#### Authorization Check

- [ ] Does the protocol require explicit authorization?
- [ ] Did I check for `authorization_required: true`?
- [ ] Did I receive the exact authorization phrase?
- [ ] Did I verify the phrase matches protocol requirements?
- [ ] Am I about to execute without verification?

#### Problem-Solving Check

- [ ] Did I implement a fix, not just acknowledge the problem?
- [ ] Did I run tests to verify the fix works?
- [ ] Did I update documentation to prevent recurrence?
- [ ] Am I waiting for user to ask again before acting?

#### Self-Detection Check

- [ ] Did I start writing code within 5 seconds of identifying the problem?
- [ ] Am I saying "I understand" instead of showing the fix?
- [ ] Am I waiting for external permission to fix?

**If any Problem-Solving or Self-Detection check fails → STOP. Implement fix NOW.**

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

| Phase        | Action           | Timeframe            | Example                     |
| ------------ | ---------------- | -------------------- | --------------------------- |
| 1. Identify  | What broke?      | 0 seconds            | Authorization bypassed      |
| 2. Design    | What needs fix?  | 0-5 seconds          | Redesign authorization flow |
| 3. Implement | Write code/tests | Within same response | Apply Single-Path Principle |
| 4. Verify    | Run tests        | Before reporting     | All tests pass              |
| 5. Document  | Update docs      | Before finishing     | Add case study              |

### Anti-Pattern: Empty Response

```
x "Sorry, I will improve." (no action)
x "I understand, won't happen again." (no fix)
x "I will be careful." (no verification)
x "I acknowledge the issue." (waiting)
```

### Correct Pattern: Demonstrated Fix

```
+ Problem: LLM executed commit without authorization
+ Root Cause: Auth treated as obstacle, not atomic operation
+ Fix: Single-Path Principle + Authorization = Execution
+ Tests: 37/37 pass
+ Document: Updated problem-solving.md with new mental model
```

### Key Takeaway

> **Don't say you'll fix it. Fix it. Then prove it's fixed.**
> **Don't wait to be asked. Fix problems the moment you see them.**

---

## Related Documents

| Document                         | Purpose                                           |
| -------------------------------- | ------------------------------------------------- |
| `agent/standards/lang-python.md` | Python-specific debugging (uv, imports, timeouts) |
| `agent/knowledge/`               | Language/framework-specific knowledge base        |
| `agent/how-to/git-workflow.md`   | Git commit authorization protocol                 |

---

_Document patterns. Break the loop._
