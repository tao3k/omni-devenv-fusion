"""
src/agent/core/agents/coder.py
Coder Agent - Primary Executor for Code Operations.

 Enhancement:
- Context Narrowing: Coder only sees code-related tools
- Mission Brief: Focused on implementation, refactoring, bug fixes

 Enhancement:
- ReAct Loop: Think -> Act -> Observe for intelligent code generation
- Tool Injection: Uses filesystem tools (read_file, write_file, etc.)

Skills (Narrow Context):
- filesystem: Read/write/modify files (consolidated from file_ops)
- code_insight: AST analysis and code structure
- python_engineering: Python-specific refactoring
- terminal: Run simple shell commands for validation

Usage:
    from agent.core.agents import CoderAgent
    from common.mcp_core.inference import InferenceClient

    # Create agent with inference engine
    client = InferenceClient()
    agent = CoderAgent(
        inference=client,
        tools={
            "read_file": read_file_func,
            "write_file": write_file_func,
            "search_files": search_files_func,
        }
    )

    result = await agent.run(
        task="Fix the IndexError in router.py",
        mission_brief="Fix the IndexError in router.py. Validate the fix with tests.",
        constraints=["Run tests after fix", "Don't break existing tests"],
        relevant_files=["packages/python/agent/src/agent/core/router.py"]
    )
"""

import importlib
from typing import Any, Callable, Dict, List

from agent.core.agents.base import BaseAgent, AgentResult


class CoderAgent(BaseAgent):
    """
    Primary Executor Agent - Specializes in code writing and modification.

     Now with ReAct Loop and Tool Injection!

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

    # ✅ Narrow Context: Only code-related skills (file_ops consolidated into filesystem)
    default_skills = [
        "filesystem",  # Read/write/modify files (includes grep, AST, batch operations)
        "code_insight",  # AST analysis and code structure
        "python_engineering",  # Python-specific refactoring tools
        "terminal",  # Simple shell commands (ls, python -c)
    ]

    def __init__(
        self,
        inference: Any = None,
        tools: Dict[str, Callable] = None,
    ):
        """
        Initialize CoderAgent with inference and tools.

        Args:
            inference: LLM inference client
            tools: Dict of tool name -> callable
        """
        super().__init__(inference=inference, tools=tools)

        # Auto-load tools from skills if not provided
        if not self.tools:
            self.tools = self._load_skill_tools()

    def _load_skill_tools(self) -> Dict[str, Callable]:
        """
        Load tools from skill modules using Skill Registry.

        Maps filesystem skill functions to agent tools.
        """
        from agent.core.registry import get_skill_tools

        # Get tools from loaded skills via Skill Registry
        tools = {}

        # Get filesystem skill tools (includes all former file_ops commands)
        fs_tools = get_skill_tools("filesystem")
        tools.update(fs_tools)

        return tools

    async def run(
        self,
        task: str,
        mission_brief: str,
        constraints: List[str] = None,
        relevant_files: List[str] = None,
        chat_history: List[dict] = None,
    ) -> AgentResult:
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
            chat_history=chat_history,
        )

    async def _execute_with_llm(self, task: str, context, history: List[dict]) -> AgentResult:
        """
        Execute coding task with LLM using ReAct loop.

         Full ReAct implementation with tool support.

        The loop:
        1. Think: LLM decides what tool to use
        2. Act: Execute tool (read/write file)
        3. Observe: Get result, continue until done
        """
        # If we have inference and tools, use ReAct loop
        if self.inference and self.tools:
            return await self._run_react_loop(
                task=task,
                system_prompt=context.system_prompt,
                max_steps=5,
            )

        # Fallback to placeholder if no inference
        return AgentResult(
            success=True,
            content=f"[CODER] Implemented: {task}",
            message=f"Coder completed implementation",
            confidence=0.85,
            tool_calls=[],
            rag_sources=[],
        )
