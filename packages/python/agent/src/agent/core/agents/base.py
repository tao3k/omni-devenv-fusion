"""
src/agent/core/agents/base.py
Base Agent - Core Engine with Context Injection.

Phase 14 Enhancement:
- Context Injection: Converts TaskBrief to System Prompt
- Tool Loading: Dynamically loads skills based on agent type
- Mission Brief Protocol: Physical implementation of telepathic link

Usage:
    class CoderAgent(BaseAgent):
        name = "coder"
        role = "Senior Python Architect"
        default_skills = ["filesystem", "file_ops", "python_engineering"]
"""
from abc import ABC
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agent.core.skill_registry import get_skill_registry
from agent.core.vector_store import get_vector_memory, SearchResult


class AgentContext(BaseModel):
    """Context prepared for agent execution."""
    system_prompt: str
    tools: List[Dict[str, Any]] = []
    mission_brief: str
    constraints: List[str] = []
    relevant_files: List[str] = []
    knowledge_context: str = ""  # Phase 16: RAG knowledge injection


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

    Each agent provides:
    - prepare_context(): Converts TaskBrief to System Prompt
    - run(): Main execution loop
    - Specialized skills for their domain

    The agent lifecycle:
    1. Receive task + TaskBrief from Orchestrator/Hive
    2. prepare_context(): Load skills, build system prompt with Mission Brief
    3. Execute: Call LLM with context
    4. Return: AgentResult with decision and supporting data
    """

    # Subclasses MUST define these
    name: str = "base_agent"
    role: str = "Base Assistant"
    description: str = "Base agent class"
    default_skills: List[str] = []

    def __init__(self):
        self.registry = get_skill_registry()

    async def prepare_context(
        self,
        mission_brief: str,
        constraints: List[str] = None,
        relevant_files: List[str] = None,
        enable_rag: bool = True  # Phase 16: Control RAG per agent
    ) -> AgentContext:
        """
        ⚡️ Core: Convert TaskBrief to System Prompt (Phase 14 Physical Implementation).
        Phase 16: Injects relevant project knowledge from VectorStore.

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
        if enable_rag:
            knowledge_context = await self._retrieve_relevant_knowledge(mission_brief)

        # 4. Build Telepathic System Prompt with knowledge injection
        system_prompt = self._build_system_prompt(
            mission_brief=mission_brief,
            skill_prompts=skill_prompts,
            constraints=constraints or [],
            relevant_files=relevant_files or [],
            knowledge_context=knowledge_context
        )

        return AgentContext(
            system_prompt=system_prompt,
            tools=tools,
            mission_brief=mission_brief,
            constraints=constraints or [],
            relevant_files=relevant_files or [],
            knowledge_context=knowledge_context
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
                tools.append({
                    "skill": skill_name,
                    "tools_module": manifest.tools_module,
                    "description": manifest.description or f"Tools for {skill_name}"
                })
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
        self,
        query: str,
        n_results: int = 3
    ) -> str:
        """
        Phase 16: Retrieve relevant project knowledge from VectorStore.

        This enables "Active RAG" - the agent automatically fetches relevant
        project documentation, coding standards, and patterns before execution.

        Args:
            query: The search query (typically the mission brief)
            n_results: Maximum number of results to retrieve

        Returns:
            Formatted knowledge string for system prompt injection, or empty string
        """
        try:
            vm = get_vector_memory()
            results: list[SearchResult] = await vm.search(query, n_results=n_results)

            if not results:
                return ""

            # Filter by similarity (distance < 0.3 means high similarity)
            # ChromaDB distance: 0.0 = identical, smaller = more similar
            filtered = [r for r in results if r.distance < 0.3]

            if not filtered:
                return ""

            # Format as markdown sections
            sections = []
            for r in filtered:
                source = r.metadata.get("source_file", r.metadata.get("title", "Knowledge"))
                # Truncate to prevent context explosion (800 chars per doc)
                content = r.content[:800] + ("..." if len(r.content) > 800 else "")
                sections.append(f"- **{source}**:\n  {content}")

            return "\n## 🧠 RELEVANT PROJECT KNOWLEDGE\n" + "\n".join(sections)

        except Exception as e:
            # RAG failure should not block execution
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning("RAG retrieval failed", error=str(e))
            return ""

    def _build_system_prompt(
        self,
        mission_brief: str,
        skill_prompts: str,
        constraints: List[str],
        relevant_files: List[str],
        knowledge_context: str = ""  # Phase 16: RAG knowledge
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
            prompt_parts.extend([
                knowledge_context,
                ""
            ])

        prompt_parts.extend([
            "## 🛠️ YOUR CAPABILITIES",
            skill_prompts,
            "",
        ])

        if constraints:
            prompt_parts.extend([
                "## ⚠️ CONSTRAINTS",
                *(f"- {c}" for c in constraints),
                ""
            ])

        if relevant_files:
            prompt_parts.extend([
                "## 📁 RELEVANT FILES",
                *(f"- {f}" for f in relevant_files),
                ""
            ])

        prompt_parts.extend([
            "## 🎯 EXECUTION RULES",
            "- Focus ONLY on the mission above",
            "- Use the provided tools precisely",
            "- If unclear, ask for clarification",
            "- Learn from success and failures for future tasks"
        ])

        return "\n".join(prompt_parts)

    async def run(
        self,
        task: str,
        mission_brief: str,
        constraints: List[str] = None,
        relevant_files: List[str] = None,
        chat_history: List[Dict] = None
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
            AgentResult with decision and supporting data
        """
        # Prepare context with Mission Brief
        ctx = await self.prepare_context(
            mission_brief=mission_brief,
            constraints=constraints,
            relevant_files=relevant_files
        )

        # Log execution start
        print(f"[{self.name}] 🚀 Starting: {task[:80]}...")
        print(f"[{self.name}] 📋 Brief: {mission_brief[:100]}...")

        # Execute (placeholder - actual LLM call would go here)
        result = await self._execute_with_llm(
            task=task,
            context=ctx,
            history=chat_history or []
        )

        print(f"[{self.name}] ✅ Complete: confidence={result.confidence}")

        return result

    async def _execute_with_llm(
        self,
        task: str,
        context: AgentContext,
        history: List[Dict]
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
            confidence=0.8
        )

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
            "skill_count": len(self.default_skills)
        }
