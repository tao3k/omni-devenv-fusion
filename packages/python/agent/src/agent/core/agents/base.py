"""
src/agent/core/agents/base.py
Base Agent - Core Engine with Holographic OODA Loop.

Phase 14 Enhancement:
- Context Injection: Converts TaskBrief to System Prompt
- Tool Loading: Dynamically loads skills based on agent type
- Mission Brief Protocol: Physical implementation of telepathic link

Phase 19 Enhancement:
- Dependency Injection: Accepts inference engine and tools
- ReAct Loop Support: Base implementation for think->act->observe
- UX Event Emission: Emits events for Glass Cockpit (Phase 18)

Phase 43 Enhancement (The Holographic Agent):
- Continuous State Injection (CSI): Injects live environment snapshot (Git, Files)
  into the System Prompt at EVERY step of the ReAct loop.
- Agent OODA Loop: Enables agent to "see" the consequences of its actions immediately.

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

# [Phase 43] Import Sniffer for Holographic Context
from agent.core.router.sniffer import get_sniffer

# [Phase 44] Import Librarian for Skill-Level Memory
from agent.capabilities.knowledge.librarian import get_skill_lessons

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
    Now equipped with Phase 43 Holographic Perception.

    Phase 19: Dependency Injection
    - inference: LLM engine for cognitive capabilities
    - tools: Dict of callable tools for action execution

    Phase 43: Holographic Agent
    - sniffer: ContextSniffer for real-time environment state
    - CSI: Continuous State Injection into ReAct loop

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

        # [Phase 43] Initialize Sensory System (ContextSniffer)
        self.sniffer = get_sniffer()

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
        Phase 44: Injects skill-level experiential memory.

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

        # 4. Phase 44: Retrieve skill-level experiential lessons
        skill_lessons = await self._get_agent_skill_lessons()

        # 5. Build Telepathic System Prompt with knowledge injection
        system_prompt = self._build_system_prompt(
            mission_brief=mission_brief,
            skill_prompts=skill_prompts,
            constraints=constraints or [],
            relevant_files=relevant_files or [],
            knowledge_context=knowledge_context,
            skill_lessons=skill_lessons,  # Phase 44: Experiential memory
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

    async def _get_agent_skill_lessons(self) -> str:
        """
        [Phase 44] Retrieve experiential lessons for the agent's default skills.

        Searches the vector store for harvested insights (past mistakes, pitfalls,
        best practices) that are relevant to the agent's skills.

        Returns:
            Formatted string with skill lessons, or empty string if none found
        """
        if not self.default_skills:
            return ""

        try:
            lessons = await get_skill_lessons(skills=self.default_skills, limit=5)
            return lessons
        except Exception as e:
            logger.warning("Skill lessons retrieval failed", error=str(e))
            return ""

    def _build_system_prompt(
        self,
        mission_brief: str,
        skill_prompts: str,
        constraints: List[str],
        relevant_files: List[str],
        knowledge_context: str = "",  # Phase 16: RAG knowledge
        skill_lessons: str = "",  # Phase 44: Experiential memory
    ) -> str:
        """
        Build the telepathic system prompt with Mission Brief.

        Phase 14: "Prompt is Policy" - The Brief IS the contract.
        Phase 16: Injects relevant project knowledge from VectorStore.
        Phase 44: Injects skill-level experiential memory (past mistakes, pitfalls).
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

        # Phase 44: Inject skill-level experiential memory
        if skill_lessons:
            prompt_parts.extend([skill_lessons, ""])

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
                "",
                "## 📡 [Phase 43] HOLOGRAPHIC AWARENESS",
                "- You will receive a LIVE ENVIRONMENT SNAPSHOT at the start of each reasoning cycle",
                "- The snapshot shows current Git status (branch, modified files)",
                "- It also shows active context (what files are currently being worked on)",
                "- **TRUST THE SNAPSHOT**: If a file you expected isn't mentioned, it may have been deleted or moved",
                "- Don't assume previous actions succeeded - verify with the snapshot",
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
        Run ReAct (Reasoning + Action) loop with Phase 43 Holographic Perception.

        ReAct Pattern (Upgraded to OODA):
        1. Observe: Get live environment snapshot (Phase 43)
        2. Orient: LLM reasons with current state
        3. Act: Execute tool if needed
        4. Observe: Get result, repeat

        Phase 43: Every iteration injects the live environment snapshot
        into the system prompt, so the agent "sees" the consequences of
        its actions immediately (e.g., git status change, file deletion).

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
            # [Phase 43] 📸 HOLOGRAPHIC CONTEXT INJECTION
            # Capture the live environment state BEFORE thinking.
            # This ensures the agent sees the result of previous actions
            # (e.g., git status change, file created/deleted).
            env_snapshot = await self.sniffer.get_snapshot()

            # Inject snapshot into System Prompt dynamically
            # We append it to make it the most recent/authoritative context
            dynamic_system_prompt = f"{system_prompt}\n\n[LIVE ENVIRONMENT STATE]\n{env_snapshot}\n\nIMPORTANT: Use the environment state above to verify your assumptions. If files you expected to exist are not mentioned, they may have been deleted or moved. If git status shows no changes, your previous staging action may have failed."

            # UX Event: Think phase starts
            _emit_ux_event(
                "think_start",
                self.name,
                {
                    "step": step + 1,
                    "task": task[:100],
                    "history_length": len(self._action_history),
                    "env_snapshot": env_snapshot[:100] + "...",  # Log partial snapshot
                },
            )

            # Build user content with task and history
            user_content = f"Task: {task}\n\nHistory:\n" + "\n".join(
                f"- {h['action']}: {h.get('result', '')}" for h in self._action_history
            )

            # Add user message to conversation
            current_messages = messages + [{"role": "user", "content": user_content}]

            try:
                # Call LLM with DYNAMIC system prompt (includes environment snapshot)
                result = await self.inference.complete(
                    system_prompt=dynamic_system_prompt,  # [Phase 43] Updated with CSI
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
