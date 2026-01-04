"""
src/agent/core/agents/coder.py
Coder Agent - Primary Executor for Code Operations.

Phase 14 Enhancement:
- Context Narrowing: Coder only sees code-related tools
- Mission Brief: Focused on implementation, refactoring, bug fixes

Skills (Narrow Context):
- filesystem: Navigate and locate files
- file_ops: Read/write/modify files
- code_insight: AST analysis and code structure
- python_engineering: Python-specific refactoring
- terminal: Run simple shell commands for validation

Usage:
    from agent.core.agents import CoderAgent

    agent = CoderAgent()
    result = await agent.run(
        task="Fix the IndexError in router.py",
        mission_brief="Fix the IndexError in router.py. Validate the fix with tests.",
        constraints=["Run tests after fix", "Don't break existing tests"],
        relevant_files=["packages/python/agent/src/agent/core/router.py"]
    )
"""
from typing import List

from agent.core.agents.base import BaseAgent


class CoderAgent(BaseAgent):
    """
    Primary Executor Agent - Specializes in code writing and modification.

    The Coder focuses on:
    - Writing new code
    - Refactoring existing code
    - Fixing bugs
    - Implementing features

    Coder does NOT have access to:
    - Git operations (use ReviewerAgent)
    - Test execution (use ReviewerAgent)
    - Documentation (use ReviewerAgent)
    """

    name = "coder"
    role = "Senior Python Architect"
    description = "Primary executor for code writing, refactoring, and bug fixes"

    # ✅ Narrow Context: Only code-related skills
    default_skills = [
        "filesystem",        # Navigate and locate files
        "file_ops",          # Read/write/modify files
        "code_insight",      # AST analysis and code structure
        "python_engineering", # Python-specific refactoring tools
        "terminal",          # Simple shell commands (ls, python -c)
    ]

    async def run(
        self,
        task: str,
        mission_brief: str,
        constraints: List[str] = None,
        relevant_files: List[str] = None,
        chat_history: List[dict] = None
    ) -> dict:
        """
        Execute coding task with Mission Brief.

        Coder-specific enhancements:
        - Automatically adds "validate with tests" if not in constraints
        - Prefers file-based verification over terminal
        """
        # Add default constraints if not present
        if constraints is None:
            constraints = []
        if "test" not in " ".join(constraints).lower():
            constraints.append("Validate changes with appropriate checks")

        return await super().run(
            task=task,
            mission_brief=mission_brief,
            constraints=constraints,
            relevant_files=relevant_files,
            chat_history=chat_history
        )

    async def _execute_with_llm(
        self,
        task: str,
        context,
        history: List[dict]
    ) -> dict:
        """
        Execute coding task with LLM.

        Coder-specific behavior:
        - Generates precise code changes
        - Includes file paths in responses
        - Suggests tests when implementing features
        """
        # Placeholder for actual LLM integration
        # In real implementation: call inference.chat with context.system_prompt

        return {
            "success": True,
            "content": f"[CODER] Implemented: {task}",
            "message": f"Coder completed implementation",
            "confidence": 0.85,
            "tool_calls": [],
            "files_modified": context.relevant_files or []
        }
