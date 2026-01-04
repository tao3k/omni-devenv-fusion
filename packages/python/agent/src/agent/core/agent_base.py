"""
src/agent/core/agent_base.py
Base Agent Class - The Foundation of The Hive

Every agent in the Hive inherits from BaseAgent, which provides:
- Cognitive loop (think -> decide -> act)
- Handoff protocol for agent-to-agent communication
- Shared memory access via Semantic Cortex
- Tool execution via invoke_skill

Usage:
    class CoderAgent(BaseAgent):
        name = "coder"
        role = "Builder"
        skills = ["filesystem", "software_engineering"]

        async def run(self, task: str, context: Dict) -> AgentResponse:
            # Implement agent-specific logic
            pass
"""
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Decision(Enum):
    """Possible decisions from agent thinking phase."""
    ACT = "act"          # Execute tool call
    HANDOFF = "handoff"  # Transfer to another agent
    ASK_USER = "ask_user"  # Need clarification
    FINISH = "finish"    # Task complete


class ToolCall(BaseModel):
    """Represents a tool call to be executed."""
    tool: str  # Format: "skill.function_name", e.g., "filesystem.list_directory"
    args: Dict[str, Any] = {}


class TaskBrief(BaseModel):
    """Context passed during agent handoff."""
    task_description: str
    constraints: List[str] = []
    relevant_files: List[str] = []
    previous_attempts: List[str] = []
    success_criteria: List[str] = []


class AgentResponse(BaseModel):
    """Response from agent's thinking phase."""
    decision: Decision
    tool_call: Optional[ToolCall] = None
    handoff_to: Optional[str] = None
    message: str = ""
    confidence: float = 0.5
    timestamp: float = 0.0

    def __init__(self, **data):
        super().__init__(**data)
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the Hive.

    Each agent implements:
    - run(): Main cognitive loop (think -> decide -> act)
    - Specific skills for their domain

    The agent lifecycle:
    1. Receive task from Orchestrator or another agent
    2. Think: Analyze task, consult memory, make decision
    3. Act: Execute tool call OR handoff to another agent
    4. Return response to orchestrator
    """

    # Subclasses must define these
    name: str = "base_agent"
    role: str = "Base"
    description: str = "Base agent class"
    skills: List[str] = []

    async def run(self, task: str, context: Dict[str, Any]) -> AgentResponse:
        """
        Main cognitive loop for the agent.

        Args:
            task: The task description from orchestrator
            context: Shared context including:
                - handoff_from: Name of agent that handed off
                - task_brief: TaskBrief if handoff
                - project_context: Project information
                - chat_history: Recent conversation

        Returns:
            AgentResponse with decision and supporting data
        """
        # Log entry
        print(f"[{self.name}] Processing: {task[:100]}...")

        # 1. Think phase: Analyze task and make decision
        response = await self.think(task, context)

        # 2. Log decision
        if response.decision == Decision.ACT:
            tool_name = response.tool_call.tool if response.tool_call else "unknown"
            print(f"[{self.name}] → ACT: {tool_name}")
        elif response.decision == Decision.HANDOFF:
            print(f"[{self.name}] → HANDOFF: {response.handoff_to}")
        elif response.decision == Decision.FINISH:
            print(f"[{self.name}] → FINISH")
        elif response.decision == Decision.ASK_USER:
            print(f"[{self.name}] → ASK_USER")

        return response

    async def think(self, task: str, context: Dict[str, Any]) -> AgentResponse:
        """
        Thinking phase: Analyze task and decide next action.

        Subclasses should override this to implement their specific logic.

        Default implementation:
        - For simple tasks: return ACT with appropriate tool call
        - For complex tasks: return HANDOFF to specialist
        - For unclear tasks: return ASK_USER
        """
        # Default: Ask user for clarification
        return AgentResponse(
            decision=Decision.ASK_USER,
            message=f"{self.name} needs more context to handle: {task}"
        )

    async def act(self, tool_call: ToolCall) -> str:
        """
        Execution phase: Execute the tool call.

        Uses invoke_skill mechanism to delegate to the appropriate skill.

        Args:
            tool_call: The tool to execute with arguments

        Returns:
            Result of the tool execution as string
        """
        from agent.capabilities.skill_manager import _execute_skill_operation
        from agent.core.skill_registry import get_skill_registry

        # Parse skill and function from tool name
        parts = tool_call.tool.split(".", 1)
        if len(parts) != 2:
            return f"Invalid tool format: {tool_call.tool}"

        skill_name, func_name = parts

        try:
            result = await _execute_skill_operation(
                skill=skill_name,
                operation=func_name,
                kwargs=tool_call.args,
                mcp=None,
                registry=get_skill_registry()
            )
            return result
        except Exception as e:
            return f"Error executing {tool_call.tool}: {e}"

    async def consult_memory(self, query: str) -> Optional[AgentResponse]:
        """
        Consult semantic memory for similar past experiences.

        Uses the Semantic Cortex to recall routing decisions.

        Args:
            query: The query to search for

        Returns:
            Cached AgentResponse if found, None otherwise
        """
        from agent.core.router import get_router

        try:
            router = get_router()
            if router.semantic_cortex:
                cached = await router.semantic_cortex.recall(query)
                if cached:
                    return AgentResponse(
                        decision=Decision.ACT,
                        tool_call=ToolCall(
                            tool="memory.recall_result",
                            args={"cached_result": cached.to_dict()}
                        ),
                        message="Recalled from memory",
                        confidence=cached.confidence
                    )
        except Exception as e:
            print(f"[{self.name}] Memory consult failed: {e}")

        return None

    async def learn_from_experience(self, task: str, response: AgentResponse):
        """
        Store this experience in semantic memory for future recall.

        Args:
            task: The original task
            response: The response generated
        """
        from agent.core.router import get_router

        try:
            router = get_router()
            if router.semantic_cortex:
                # Convert AgentResponse to RoutingResult-like format
                from agent.core.router import RoutingResult
                result = RoutingResult(
                    selected_skills=self.skills,
                    mission_brief=response.message,
                    reasoning=f"{self.name} handled: {task[:50]}...",
                    confidence=response.confidence,
                    from_cache=False
                )
                await router.semantic_cortex.learn(task, result)
        except Exception as e:
            print(f"[{self.name}] Learning failed: {e}")

    def get_task_brief(self, context: Dict[str, Any]) -> Optional[TaskBrief]:
        """
        Extract TaskBrief from handoff context.

        Args:
            context: The context dict from handoff

        Returns:
            TaskBrief if present, None otherwise
        """
        brief_data = context.get("task_brief")
        if brief_data:
            if isinstance(brief_data, dict):
                return TaskBrief(**brief_data)
            elif isinstance(brief_data, TaskBrief):
                return brief_data
        return None

    def log_thought(self, thought: str):
        """
        Log internal thought for debugging/audit.

        Args:
            thought: The thought to log
        """
        print(f"[{self.name}][THOUGHT] {thought}")


class HandoffProtocol:
    """
    Protocol for transferring control between agents.

    Ensures context is properly preserved during handoff.
    """

    @staticmethod
    async def handoff(
        from_agent: BaseAgent,
        to_agent: BaseAgent,
        task: str,
        brief: TaskBrief
    ) -> AgentResponse:
        """
        Transfer control from one agent to another.

        Args:
            from_agent: The agent handing off
            to_agent: The receiving agent
            task: Task description
            brief: TaskBrief with context

        Returns:
            Response from the receiving agent
        """
        # Log the handoff
        print(f"[HANDOFF] {from_agent.name} -> {to_agent.name}: {task[:50]}...")

        # Build context for receiving agent
        context = {
            "handoff_from": from_agent.name,
            "handoff_timestamp": time.time(),
            "task_brief": brief.model_dump(),
            "original_task": task
        }

        # Transfer control
        return await to_agent.run(task, context)


class Hive:
    """
    The Hive - Container for all agents and their coordination.

    Usage:
        hive = Hive()
        response = await hive.dispatch("user query")
    """

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.orchestrator: Optional[BaseAgent] = None

    def register(self, agent: BaseAgent):
        """
        Register an agent with the hive.

        Args:
            agent: The agent to register
        """
        self.agents[agent.name] = agent
        print(f"[HIVE] Registered: {agent.name} ({agent.role})")

    def set_orchestrator(self, agent: BaseAgent):
        """
        Set the orchestrator agent.

        Args:
            agent: The orchestrator agent
        """
        self.orchestrator = agent
        self.register(agent)

    async def dispatch(self, user_input: str) -> AgentResponse:
        """
        Dispatch user input to appropriate agent.

        Args:
            user_input: The user's request

        Returns:
            Response from the processing agent
        """
        if not self.orchestrator:
            raise ValueError("Orchestrator not set. Call set_orchestrator() first.")

        # Orchestrator handles initial routing
        return await self.orchestrator.run(user_input, {})

    async def handoff(
        self,
        from_name: str,
        to_name: str,
        task: str,
        brief: TaskBrief
    ) -> AgentResponse:
        """
        Perform handoff between agents.

        Args:
            from_name: Name of current agent
            to_name: Name of target agent
            task: Task description
            brief: TaskBrief

        Returns:
            Response from target agent
        """
        from_agent = self.agents.get(from_name)
        to_agent = self.agents.get(to_name)

        if not from_agent or not to_agent:
            raise ValueError(f"Unknown agent: {from_name} or {to_name}")

        return await HandoffProtocol.handoff(from_agent, to_agent, task, brief)

    def list_agents(self) -> List[str]:
        """List all registered agents."""
        return list(self.agents.keys())
