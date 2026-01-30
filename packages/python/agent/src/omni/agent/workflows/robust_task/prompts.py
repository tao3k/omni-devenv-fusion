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
You are an expert developer.
Execute the following step:

Step: {step_description}
Context: {context}
History: {history}

Available Tools:
{tools}

Decide on the best tool to use.
If you need more information, search for it.

Output format:
<thought>
Your reasoning for the action.
</thought>

<action>
The tool name and arguments (JSON).
Example: {{"tool": "filesystem.read_file", "args": {{"file_path": "..."}}}}
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
