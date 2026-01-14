"""
Phase 61: Cognitive Scaffolding - Planner Prompts

Prompt templates for task decomposition and planning.
遵循 ODF-EP 标准:
- Type hints required
- No mutable defaults
- Clear structure
"""

from typing import Any


# =============================================================================
# Task Decomposition Prompt
# =============================================================================

DECOMPOSE_SYSTEM_PROMPT = """You are an expert task planner. Your job is to break down complex goals into actionable, independent tasks.

## Principles
1. Each task should be independent and testable
2. Tasks should have clear success criteria
3. Dependencies should be explicit
4. Order tasks logically ( prerequisites first)

## Output Format
Return a JSON object with a list of tasks. Each task must have:
- id: Short descriptive ID (e.g., "analyze", "implement", "test")
- description: Clear description of what to do
- priority: 1 (critical) to 4 (low)
- dependencies: List of task IDs this depends on
- tool_calls: Suggested tool(s) to use

## Available Tools
{available_tools}

## Context
{context}

## Goal
{goal}

Think step by step, then output your plan as JSON."""


DECOMPOSE_USER_PROMPT = """Break down this goal into tasks:

{goal}

Consider:
- What needs to be analyzed first?
- What can be done in parallel?
- What has dependencies on other tasks?

Respond with a JSON plan."""


# =============================================================================
# Reflexion/Review Prompt
# =============================================================================

REFLEXION_SYSTEM_PROMPT = """You are a task reviewer. After each major step, you evaluate:
1. Did we achieve the task goal?
2. Did we introduce any issues?
3. Should we continue, revise the plan, or stop?

## Review Criteria
- Goal Achievement: Did we accomplish what we set out to do?
- Code Quality: Did we maintain or improve code quality?
- Side Effects: Did we introduce any bugs or regressions?
- Next Steps: Should we continue, pivot, or stop?

## Output Format
Return JSON with:
- status: "continue" | "pivot" | "complete" | "abort"
- reflection: Brief assessment of what happened
- next_action: Recommended next step
- issues: List of any issues found"""


REFLEXION_TASK_PROMPT = """## Task
Goal: {task_goal}
Result: {task_result}
Output: {task_output}

## Review
Based on the above, evaluate the task execution."""


# =============================================================================
# Re-planning Prompt
# =============================================================================

REPLAN_SYSTEM_PROMPT = """You are a replanner. The current plan has encountered an issue.

## Current Plan Status
- Goal: {goal}
- Failed Task: {failed_task}
- Failure Reason: {failure_reason}
- Completed Tasks: {completed_tasks}

## Options
1. RETRY: Same task with different approach
2. SKIP: Skip this task (not critical)
3. REVISED: Modify plan to work around the issue
4. ABANDON: The goal is not achievable

Analyze the situation and propose a revised plan."""


REPLAN_USER_PROMPT = """The current task failed: {failed_task}

Reason: {failure_reason}

How should we proceed? Provide a revised plan if needed."""


# =============================================================================
# Summary Generation Prompt
# =============================================================================

SUMMARY_SYSTEM_PROMPT = """Generate a brief summary of what was accomplished in this task step.

## Summary Guidelines
- Focus on what was done, not how
- Mention any important discoveries or pivots
- Keep it concise (2-3 sentences)
- Use past tense

## Input
Task: {task_description}
Actions: {actions}
Results: {results}

Output a brief summary."""


# =============================================================================
# Helper Functions
# =============================================================================


def get_decompose_prompt(
    goal: str,
    available_tools: list[str],
    context: str | None = None,
) -> tuple[str, str]:
    """Get the decomposition prompt pair.

    Args:
        goal: The user goal to decompose.
        available_tools: List of available tool names.
        context: Optional context about the codebase.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    tools_str = "\n".join(f"- {t}" for t in available_tools)
    context_str = context or "No additional context provided."

    system_prompt = DECOMPOSE_SYSTEM_PROMPT.format(
        available_tools=tools_str,
        context=context_str,
        goal=goal,
    )

    user_prompt = DECOMPOSE_USER_PROMPT.format(goal=goal)

    return system_prompt, user_prompt


def get_reflexion_prompt(
    task_goal: str,
    task_result: str,
    task_output: Any,
) -> str:
    """Get the reflexion prompt for task review.

    Args:
        task_goal: Original task goal.
        task_result: Result of the task execution.
        task_output: Actual output from tools.

    Returns:
        Formatted reflexion prompt.
    """
    return REFLEXION_TASK_PROMPT.format(
        task_goal=task_goal,
        task_result=task_result,
        task_output=str(task_output),
    )


def get_replan_prompt(
    goal: str,
    failed_task: str,
    failure_reason: str,
    completed_tasks: list[str],
) -> tuple[str, str]:
    """Get the replanning prompt pair.

    Args:
        goal: Original user goal.
        failed_task: The task that failed.
        failure_reason: Why it failed.
        completed_tasks: List of completed task IDs.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    system_prompt = REPLAN_SYSTEM_PROMPT.format(
        goal=goal,
        failed_task=failed_task,
        failure_reason=failure_reason,
        completed_tasks=", ".join(completed_tasks) if completed_tasks else "None",
    )

    user_prompt = REPLAN_USER_PROMPT.format(
        failed_task=failed_task,
        failure_reason=failure_reason,
    )

    return system_prompt, user_prompt


def get_summary_prompt(
    task_description: str,
    actions: list[dict[str, Any]],
    results: list[str],
) -> str:
    """Get the summary generation prompt.

    Args:
        task_description: What the task was trying to do.
        actions: List of actions taken.
        results: List of results obtained.

    Returns:
        Formatted summary prompt.
    """
    return SUMMARY_SYSTEM_PROMPT.format(
        task_description=task_description,
        actions=str(actions),
        results=str(results),
    )
