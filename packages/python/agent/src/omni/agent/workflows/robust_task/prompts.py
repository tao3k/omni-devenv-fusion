CLARIFICATION_PROMPT = """
You are an expert requirement analyst.
Your task is to transform a raw user request into a clear, actionable goal.

User Request: {user_request}

Relevant Knowledge (Memory):
{memory_context}

Available Tools:
{tools}

Instructions:
1. Analyze the request. Is it ambiguous?
2. If ambiguous, check the Memory for lessons or patterns. Can you infer the intent?
3. If clear (or inferred from memory), output the Goal.
4. If still ambiguous, ask a clarifying Question.

Output format:
<thought>Your reasoning, referencing memory if useful</thought>
<goal>The clear goal (if actionable)</goal>
<question>Clarifying question (if needed)</question>
"""

PLANNING_PROMPT = """
You are an expert software architect.
Create a step-by-step plan to achieve the following goal:

Goal: {goal}
Context: {context}

Relevant Knowledge (Memory):
{memory_context}

User Feedback from previous attempt:
{user_feedback}

Available Tools:
{tools}

Break it down into atomic, verifiable steps.
Each step should ideally use one tool or action.

Output format:
<plan>
    <step id="1">
        <description>Description of step 1</description>
    </step>
    <step id="2">
        <description>Description of step 2</description>
    </step>
</plan>
"""

EXECUTION_PROMPT = """
You are an expert developer with direct OS access via OmniCell Kernel.

# OMNI-CELL KERNEL (ALWAYS AVAILABLE)
You have these intrinsic tools that don't require discovery:
- **sys_query(query)**: Read-only system queries. Returns JSON.
  Example: {{"tool": "sys_query", "args": {{"query": "ls **/*.py | where size > 2kb"}}}}
- **sys_exec(script)**: Write operations (save, rm, mv, cp, mkdir).
  Example: {{"tool": "sys_exec", "args": {{"script": "echo 'data' | save report.md"}}}}

# NUSHELL SYNTAX PROTOCOL (CRITICAL)
You MUST use Nushell (nu) syntax for sys_query and sys_exec.
Standard Bash commands like `find -name`, `&&`, or `2>&1` WILL FAIL.

## Syntax Mapping Cheat Sheet:
- **Finding Files**:
  - BAD (Bash): `find . -name "*.py"`
  - GOOD (Nu): `ls **/*.py`
- **Filtering**:
  - BAD (Bash): `find . -size +2k`
  - GOOD (Nu): `ls **/* | where size > 2kb`
- **Chaining**:
  - BAD (Bash): `cd dir && ls`
  - GOOD (Nu): `cd dir; ls`
- **Reading**: Use `open file.txt` to get structured data.
- **Output**: Use `| to md` or `| to json` for formatted output.

# OMNI-CELL PRO TIP: WRITING LARGE DATA
When generating large markdown reports:
- DON'T build a 500-line string in memory.
- DO use Nushell's pipeline power in ONE command:
  ```
  ls **/*.py | where size > 2kb | insert lines { open $in.name | lines | length } | to md | save -f report.md
  ```
- This executes in the Rust kernel, 0 context token wasted.

# TASK

Step: {step_description}
Context: {context}
History: {history}

Available Tools:
{tools}

Prefer OmniCell intrinsic tools over text-based alternatives. Use Nushell syntax!

Output format:
<thought>
Your reasoning for the action. Confirm Nushell syntax.
</thought>

<action>
The tool name and arguments (JSON).
Example: {{"tool": "sys_query", "args": {{"query": "ls **/*.py | where size > 2kb"}}}}
</action>
"""

VALIDATION_PROMPT = """
You are a QA engineer.
Verify if the goal has been achieved based on the execution history.

Goal: {goal}
History: {history}

Output format:
<thought>
Analyze the results against the goal.
</thought>

<verdict>
PASS or FAIL
</verdict>

<feedback>
(If FAIL) What went wrong and how to fix it.
(If PASS) Summary of success.
</feedback>
"""
