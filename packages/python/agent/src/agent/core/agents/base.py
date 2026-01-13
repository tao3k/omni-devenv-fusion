"""
src/agent/core/agents/base.py
Base Agent - Core Engine with Context Injection.

Phase 14 Enhancement:
- Context Injection: Converts TaskBrief to System Prompt
- Tool Loading: Dynamically loads skills based on agent type
- Mission Brief Protocol: Physical implementation of telepathic link

Phase 19 Enhancement:
- Dependency Injection: Accepts inference engine and tools
- ReAct Loop Support: Base implementation for think->act->observe
- UX Event Emission: Emits events for Glass Cockpit (Phase 18)

Usage:
    class CoderAgent(BaseAgent):
        name = "coder"
        role = "Senior Python Architect"
        default_skills = ["filesystem", "python_engineering"]
"""

from abc import ABC
from typing import Any, Callable, Dict, List, Optional
import json
from pathlib import Path

import structlog
from pydantic import BaseModel

from agent.core.registry import get_skill_registry
from agent.core.vector_store import get_vector_memory, SearchResult

logger = structlog.get_logger(__name__)


# UX Event Log Path (Phase 18: Glass Cockpit)
# Use project-specific cache directory
def _get_ux_event_log_path() -> Path:
    """Get UX event log path from project cache directory."""
    try:
        from common.cache_path import CACHE_DIR

        return CACHE_DIR.ensure_parent("omni_ux_events.jsonl")
    except Exception:
        return Path("/tmp/omni_ux_events.jsonl")


def _emit_ux_event(event_type: str, agent_name: str, payload: dict):
    """
    Emit UX event for Glass Cockpit (Phase 18).

    Writes events to project .cache/omni_ux_events.jsonl for the Sidecar Dashboard.

    Args:
        event_type: Type of event (think_start, act_execute, observe_result, etc.)
        agent_name: Name of the agent emitting the event
        payload: Event-specific data
    """
    import time

    event = {
        "type": event_type,
        "agent": agent_name,
        "payload": payload,
        "timestamp": time.time(),
    }
    try:
        event_log_path = _get_ux_event_log_path()
        with open(event_log_path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass  # UX events should not block execution


class AgentContext(BaseModel):
    """Context prepared for agent execution."""

    system_prompt: str
    tools: List[Dict[str, Any]] = []
    mission_brief: str
    constraints: List[str] = []
    relevant_files: List[str] = []
    knowledge_context: str = ""  # Phase 16: RAG knowledge injection
    rag_sources: List[Dict[str, Any]] = []  # Phase 18: RAG sources for UX


class AgentResult(BaseModel):
    """Result from agent execution."""

    success: bool
    content: str = ""
    tool_calls: List[Dict[str, Any]] = []
    message: str = ""
    confidence: float = 0.5
    # Phase 15: Feedback Loop fields
    audit_result: Optional[Dict[str, Any]] = None
    needs_review: bool = False
    # Phase 16: RAG sources (for UX visualization)
    rag_sources: List[Dict[str, Any]] = []


class AuditResult(BaseModel):
    """Result from Reviewer's audit of another agent's output."""

    approved: bool
    feedback: str = ""
    confidence: float = 0.5
    issues_found: List[str] = []
    suggestions: List[str] = []


class BaseAgent(ABC):
    """
    Abstract base class for all specialist agents in The Hive.

    Phase 19: Dependency Injection
    - inference: LLM engine for cognitive capabilities
    - tools: Dict of callable tools for action execution

    Each agent provides:
    - prepare_context(): Converts TaskBrief to System Prompt
    - run(): Main execution loop
    - Specialized skills for their domain

    The agent lifecycle:
    1. Receive task + TaskBrief from Orchestrator/Hive
    2. prepare_context(): Load skills, build system prompt with Mission Brief
    3. Execute: Call LLM with context (ReAct loop for agents with inference)
    4. Return: AgentResult with decision and supporting data
    """

    # Subclasses MUST define these
    name: str = "base_agent"
    role: str = "Base Assistant"
    description: str = "Base agent class"
    default_skills: List[str] = []

    def __init__(
        self,
        inference: Any = None,
        tools: Dict[str, Callable] = None,
    ):
        """
        Initialize BaseAgent with optional dependency injection.

        Args:
            inference: LLM inference client (e.g., InferenceClient)
            tools: Dict of tool name -> callable function
        """
        self.registry = get_skill_registry()
        self.inference = inference
        self.tools = tools or {}
        self._action_history: List[Dict] = []  # Track ReAct actions

    async def prepare_context(
        self,
        mission_brief: str,
        constraints: List[str] = None,
        relevant_files: List[str] = None,
        enable_rag: bool = True,  # Phase 16: Control RAG per agent
    ) -> AgentContext:
        """
        ⚡️ Core: Convert TaskBrief to System Prompt (Phase 14 Physical Implementation).
        Phase 16: Injects relevant project knowledge from VectorStore.
        Phase 18: Returns RAG sources for UX visualization.

        Args:
            mission_brief: The Commander's Intent from HiveRouter
            constraints: List of constraints for this task
            relevant_files: Files relevant to this task
            enable_rag: Whether to enable RAG knowledge retrieval (default: True)

        Returns:
            AgentContext with system_prompt and tools
        """
        # 1. Get skill tool info from manifests
        tools = self._get_skill_tools()

        # 2. Get skill prompts (capabilities) from registry
        skill_prompts = self._get_skill_capabilities()

        # 3. Phase 16: Retrieve relevant knowledge from VectorStore
        knowledge_context = ""
        rag_sources = []  # Phase 18: For UX display
        if enable_rag:
            knowledge_context, rag_sources = await self._retrieve_relevant_knowledge(mission_brief)

        # 4. Build Telepathic System Prompt with knowledge injection
        system_prompt = self._build_system_prompt(
            mission_brief=mission_brief,
            skill_prompts=skill_prompts,
            constraints=constraints or [],
            relevant_files=relevant_files or [],
            knowledge_context=knowledge_context,
        )

        return AgentContext(
            system_prompt=system_prompt,
            tools=tools,
            mission_brief=mission_brief,
            constraints=constraints or [],
            relevant_files=relevant_files or [],
            knowledge_context=knowledge_context,
            rag_sources=rag_sources,  # Phase 18: For UX display
        )

    def _get_skill_tools(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions from skill manifests.

        Returns list of tool dicts with name, description, etc.
        """
        tools = []
        for skill_name in self.default_skills:
            manifest = self.registry.get_skill_manifest(skill_name)
            if manifest:
                tools.append(
                    {
                        "skill": skill_name,
                        "tools_module": manifest.tools_module,
                        "description": manifest.description or f"Tools for {skill_name}",
                    }
                )
        return tools

    def _get_skill_capabilities(self) -> str:
        """
        Get capability descriptions for each skill.

        Returns formatted string of skill capabilities.
        """
        if not self.default_skills:
            return "No specific capabilities defined."

        capabilities = []
        for skill_name in self.default_skills:
            manifest = self.registry.get_skill_manifest(skill_name)
            if manifest:
                desc = manifest.description or skill_name
                capabilities.append(f"- [{skill_name}]: {desc}")
            else:
                capabilities.append(f"- [{skill_name}]: (skill manifest not found)")
        return "\n".join(capabilities)

    async def _retrieve_relevant_knowledge(
        self, query: str, n_results: int = 3
    ) -> tuple[str, list[dict]]:
        """
        Phase 16: Retrieve relevant project knowledge from VectorStore.

        This enables "Active RAG" - the agent automatically fetches relevant
        project documentation, coding standards, and patterns before execution.

        Args:
            query: The search query (typically the mission brief)
            n_results: Maximum number of results to retrieve

        Returns:
            Tuple of (formatted knowledge string, sources list for UX)
        """
        try:
            vm = get_vector_memory()
            results: list[SearchResult] = await vm.search(query, n_results=n_results)

            if not results:
                return "", []

            # Filter by similarity (distance < 0.3 means high similarity)
            # ChromaDB distance: 0.0 = identical, smaller = more similar
            filtered = [r for r in results if r.distance < 0.3]

            if not filtered:
                return "", []

            # Format as markdown sections
            sections = []
            sources = []
            for r in filtered:
                source = r.metadata.get("source_file", r.metadata.get("title", "Knowledge"))
                # Truncate to prevent context explosion (800 chars per doc)
                content = r.content[:800] + ("..." if len(r.content) > 800 else "")
                sections.append(f"- **{source}**:\n  {content}")

                # Build source dict for UX display
                sources.append(
                    {
                        "source_file": source,
                        "distance": r.distance,
                        "title": r.metadata.get("title", ""),
                    }
                )

            return "\n## 🧠 RELEVANT PROJECT KNOWLEDGE\n" + "\n".join(sections), sources

        except Exception as e:
            # RAG failure should not block execution
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning("RAG retrieval failed", error=str(e))
            return "", []

    def _build_system_prompt(
        self,
        mission_brief: str,
        skill_prompts: str,
        constraints: List[str],
        relevant_files: List[str],
        knowledge_context: str = "",  # Phase 16: RAG knowledge
    ) -> str:
        """
        Build the telepathic system prompt with Mission Brief.

        Phase 14: "Prompt is Policy" - The Brief IS the contract.
        Phase 16: Injects relevant project knowledge from VectorStore.
        """
        prompt_parts = [
            f"# ROLE: {self.role}",
            "",
            "You are a specialized worker agent in The Hive.",
            "",
            "## 📋 CURRENT MISSION (From Orchestrator)",
            "=" * 50,
            mission_brief,
            "=" * 50,
            "",
        ]

        # Phase 16: Inject knowledge if available
        if knowledge_context:
            prompt_parts.extend([knowledge_context, ""])

        prompt_parts.extend(
            [
                "## 🛠️ YOUR CAPABILITIES",
                skill_prompts,
                "",
            ]
        )

        if constraints:
            prompt_parts.extend(["## ⚠️ CONSTRAINTS", *(f"- {c}" for c in constraints), ""])

        if relevant_files:
            prompt_parts.extend(["## 📁 RELEVANT FILES", *(f"- {f}" for f in relevant_files), ""])

        prompt_parts.extend(
            [
                "## 🎯 EXECUTION RULES",
                "- Focus ONLY on the mission above",
                "- Use the provided tools precisely",
                "- If unclear, ask for clarification",
                "- Learn from success and failures for future tasks",
            ]
        )

        return "\n".join(prompt_parts)

    async def run(
        self,
        task: str,
        mission_brief: str,
        constraints: List[str] = None,
        relevant_files: List[str] = None,
        chat_history: List[Dict] = None,
    ) -> AgentResult:
        """
        Execute the agent's main loop.

        Args:
            task: The specific task to perform
            mission_brief: Commander's Intent from HiveRouter
            constraints: Task constraints
            relevant_files: Files to work with
            chat_history: Conversation history

        Returns:
            AgentResult with decision and supporting data, including rag_sources
        """
        # Prepare context with Mission Brief
        ctx = await self.prepare_context(
            mission_brief=mission_brief, constraints=constraints, relevant_files=relevant_files
        )

        # Log execution start
        logger.info(f"🚀 [{self.name}] Starting: {task[:80]}...")
        logger.info(f"📋 [{self.name}] Brief: {mission_brief[:100]}...")

        # Execute (placeholder - actual LLM call would go here)
        result = await self._execute_with_llm(task=task, context=ctx, history=chat_history or [])

        # Phase 18: Include RAG sources for UX display
        result.rag_sources = ctx.rag_sources

        logger.info(f"✅ [{self.name}] Complete: confidence={result.confidence}")

        return result

    async def _execute_with_llm(
        self, task: str, context: AgentContext, history: List[Dict]
    ) -> AgentResult:
        """
        Execute task with LLM. Override this for actual implementation.

        This is the bridge between agent context and LLM inference.
        """
        # Placeholder: In real implementation, this would call:
        # inference.chat(query=task, system_prompt=context.system_prompt, ...)

        return AgentResult(
            success=True,
            content=f"[{self.name}] Executed: {task}",
            message=f"Agent {self.name} completed the mission",
            confidence=0.8,
        )

    # =========================================================================
    # Phase 19: ReAct Loop Support
    # =========================================================================

    async def _run_react_loop(
        self,
        task: str,
        system_prompt: str,
        max_steps: int = 5,
    ) -> AgentResult:
        """
        Run ReAct (Reasoning + Action) loop.

        ReAct Pattern:
        1. Think: LLM decides what to do
        2. Act: Execute tool if needed
        3. Observe: Get result, repeat

        Args:
            task: The user task
            system_prompt: System prompt defining the agent's role
            max_steps: Maximum ReAct iterations

        Returns:
            AgentResult with final content
        """
        if not self.inference:
            logger.warning("No inference engine, falling back to placeholder")
            return AgentResult(
                success=True,
                content=f"[{self.name}] Executed: {task}",
                confidence=0.5,
            )

        self._action_history = []
        messages = []
        # Get tool schema for ReAct
        tool_schemas = (
            self.inference.get_tool_schema(self.default_skills)
            if hasattr(self.inference, "get_tool_schema")
            else []
        )

        for step in range(max_steps):
            # UX Event: Think phase starts
            _emit_ux_event(
                "think_start",
                self.name,
                {"step": step + 1, "task": task[:100], "history_length": len(self._action_history)},
            )

            # Build user content with task and history
            user_content = f"Task: {task}\n\nHistory:\n" + "\n".join(
                f"- {h['action']}: {h.get('result', '')}" for h in self._action_history
            )

            # Add user message to conversation
            current_messages = messages + [{"role": "user", "content": user_content}]

            try:
                # Call LLM with tools and conversation history
                result = await self.inference.complete(
                    system_prompt=system_prompt,
                    user_query=user_content,
                    messages=current_messages,  # Use full conversation history
                    tools=tool_schemas if step == 0 else [],  # Only send tools on first call
                )

                if not result["success"]:
                    return AgentResult(
                        success=False,
                        content=result.get("error", "LLM call failed"),
                        confidence=0.0,
                    )

                response = result["content"].strip()
                tool_calls = result.get("tool_calls", [])

                # Add assistant's response to messages
                messages.append({"role": "assistant", "content": response})

                # Check for tool calls (from API or text parsing)
                if tool_calls:
                    # Process each tool call from API
                    for tool_call in tool_calls:
                        tool_name = tool_call.get("name")
                        tool_args = tool_call.get("input", {})

                        # UX Event: Act phase starts (tool execution)
                        _emit_ux_event(
                            "act_execute",
                            self.name,
                            {"step": step + 1, "tool": tool_name, "args": tool_args},
                        )

                        # Execute tool
                        if tool_name in self.tools:
                            try:
                                if callable(self.tools[tool_name]):
                                    tool_result = await self.tools[tool_name](**tool_args)
                                else:
                                    tool_result = str(self.tools[tool_name])

                                # UX Event: Observe phase (tool result)
                                _emit_ux_event(
                                    "observe_result",
                                    self.name,
                                    {
                                        "step": step + 1,
                                        "tool": tool_name,
                                        "success": True,
                                        "result_preview": str(tool_result)[:100],
                                    },
                                )

                                self._action_history.append(
                                    {
                                        "step": step + 1,
                                        "action": f"TOOL: {tool_name}",
                                        "result": str(tool_result)[:500],
                                    }
                                )

                                # Add tool result as user message for next iteration
                                messages.append(
                                    {
                                        "role": "user",
                                        "content": f"Tool {tool_name} returned: {tool_result}",
                                    }
                                )

                                logger.info(f"ReAct step {step + 1}: {tool_name} executed")
                            except Exception as e:
                                self._action_history.append(
                                    {
                                        "step": step + 1,
                                        "action": f"TOOL: {tool_name}",
                                        "result": f"Error: {str(e)}",
                                    }
                                )
                                return AgentResult(
                                    success=False,
                                    content=f"Tool execution failed: {e}",
                                    confidence=0.0,
                                )
                        else:
                            self._action_history.append(
                                {
                                    "step": step + 1,
                                    "action": f"TOOL: {tool_name}",
                                    "result": f"Tool not available: {tool_name}",
                                }
                            )
                            # Add error as user message so LLM knows to try a different tool
                            messages.append(
                                {
                                    "role": "user",
                                    "content": f"Tool '{tool_name}' is not available. Available tools: {', '.join(self.tools.keys())}. Please try a different tool.",
                                }
                            )
                else:
                    # No tool call, this is the final answer
                    return AgentResult(
                        success=True,
                        content=response,
                        message=f"Completed in {step + 1} steps",
                        confidence=0.9,
                        tool_calls=self._action_history,
                    )

            except Exception as e:
                logger.error(f"ReAct loop error at step {step}: {e}")
                return AgentResult(
                    success=False,
                    content=f"Execution error: {str(e)}",
                    confidence=0.0,
                )

        # Max steps reached
        return AgentResult(
            success=False,
            content=f"Maximum steps ({max_steps}) reached. Progress:\n"
            + "\n".join(f"- {h['action']}" for h in self._action_history),
            confidence=0.3,
            tool_calls=self._action_history,
        )

    def _parse_tool_call(self, response: str) -> Optional[tuple[str, Dict[str, Any]]]:
        """
        Parse tool call from LLM response.

        Supports multiple formats:
        1. Simple: `TOOL: read_file(path="main.py")`
        2. XML/MCP: `<invoke><filesystem>\n<read>\n<path>main.py</path>...</invoke>`
        3. Bracket: `[TOOL] write_file(path="test.py", content="...")`

        Args:
            response: LLM response text

        Returns:
            Tuple of (tool_name, args_dict) or None
        """
        import re

        # Format 1: Simple TOOL: name(args)
        tool_pattern = r"(?:TOOL|ACTION|TOOL_CALL):\s*(\w+)\s*\(([^)]*)\)"
        match = re.search(tool_pattern, response, re.IGNORECASE)
        if match:
            tool_name = match.group(1)
            args_str = match.group(2)
            args = {}
            for arg_match in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', args_str):
                args[arg_match.group(1)] = arg_match.group(2)
            return tool_name, args

        # Format 2: XML/MCP style: <invoke><tool_name>\n<arg1>value</arg1>...</invoke>
        xml_pattern = r"<invoke>\s*<(\w+)>\s*(.*?)\s*</\1>\s*</invoke>"
        match = re.search(xml_pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            tool_name = match.group(1).lower()
            inner = match.group(2)

            # Parse nested tags
            args = {}
            for tag_match in re.finditer(r"<(\w+)>(.*?)</\1>", inner, re.DOTALL):
                arg_name = tag_match.group(1).lower()
                arg_value = tag_match.group(2).strip()
                # Remove any newlines in the value
                arg_value = re.sub(r"\s+", " ", arg_value).strip()
                args[arg_name] = arg_value

            return tool_name, args

        # Format 3: Bracket style: [TOOL] name(args)
        bracket_pattern = r"\[TOOL\]\s*(\w+)\s*\(([^)]*)\)"
        match = re.search(bracket_pattern, response, re.IGNORECASE)
        if match:
            tool_name = match.group(1)
            args_str = match.group(2)
            args = {}
            for arg_match in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', args_str):
                args[arg_match.group(1)] = arg_match.group(2)
            return tool_name, args

        return None

    def get_skill_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the agent's skills for routing decisions.

        Returns:
            Dict with agent metadata and skills
        """
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "skills": self.default_skills,
            "skill_count": len(self.default_skills),
        }
