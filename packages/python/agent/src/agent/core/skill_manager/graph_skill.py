"""
src/agent/core/skill_manager/graph_skill.py
 GraphSkill Base Class for Standardized Subgraph Skills.

Provides a base class for skills that can be used as LangGraph subgraphs.
Enables "Agent calling Agent" nesting capability.

Usage:
    class MyGraphSkill(GraphSkill):
        name = "my_graph_skill"
        description = "A composite skill that orchestrates other skills"

        def build_graph(self, builder: DynamicGraphBuilder) -> None:
            builder.add_skill_node("step1", "other_skill", "command1")
            builder.add_skill_node("step2", "another_skill", "command2")
            builder.add_edge("step1", "step2")
            builder.set_entry_point("step1")
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..orchestrator.dynamic_builder import DynamicGraphBuilder
    from .manager import SkillManager
    from ..planner.schemas import WorkflowBlueprint

logger = logging.getLogger(__name__)


class GraphSkill(ABC):
    """
    Base class for skills that can be executed as LangGraph subgraphs.

     Enables "Agent calling Agent" nesting capability.
    Each GraphSkill is a self-contained workflow that can be composed
    into larger graphs.

    Attributes:
        name: Unique name for this graph skill
        description: Human-readable description of what this skill does
        required_skills: List of skill names this skill depends on
        input_schema: JSON schema for input validation
        output_schema: JSON schema for output validation

    Example:
        class AnalyzeAndFix(GraphSkill):
            name = "analyze_and_fix"
            description = "Analyze code and fix issues"

            def build_graph(self, builder: DynamicGraphBuilder) -> None:
                builder.add_skill_node("analyze", "code_insight", "analyze")
                builder.add_skill_node("fix", "omni_edit", "apply_fix")
                builder.add_edge("analyze", "fix")
                builder.set_entry_point("analyze")
    """

    # Class attributes - override in subclasses
    name: str = "graph_skill"
    description: str = "A composite skill"
    required_skills: list[str] = []
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}

    def __init__(self, skill_manager: SkillManager | None = None) -> None:
        """Initialize the GraphSkill.

        Args:
            skill_manager: Optional SkillManager for skill lookups
        """
        self._skill_manager = skill_manager
        self._compiled_graph: Any | None = None

    def get_skill_manager(self) -> SkillManager | None:
        """Get the skill manager."""
        return self._skill_manager

    def set_skill_manager(self, skill_manager: SkillManager) -> None:
        """Set the skill manager."""
        self._skill_manager = skill_manager

    @abstractmethod
    def build_graph(self, builder: DynamicGraphBuilder) -> None:
        """Build the execution graph for this skill.

        Override this method to define the workflow structure.

        Args:
            builder: DynamicGraphBuilder to add nodes and edges
        """
        ...

    def compile(self) -> Any:
        """Compile the graph for execution.

        Returns:
            Compiled LangGraph graph
        """
        from ..orchestrator.dynamic_builder import DynamicGraphBuilder

        builder = DynamicGraphBuilder(self._skill_manager)
        self.build_graph(builder)
        self._compiled_graph = builder.compile()
        return self._compiled_graph

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run this graph skill with the given input.

        Args:
            input_data: Input data for the workflow

        Returns:
            Output data from the workflow
        """
        if self._compiled_graph is None:
            self.compile()

        # Create initial state as a dict (LangGraph compatible)
        initial_state: dict[str, Any] = {
            "messages": [{"role": "user", "content": str(input_data)}],
            "context_ids": [],
            "current_plan": "",
            "error_count": 0,
            "workflow_state": input_data,
        }

        # Invoke the graph
        if self._compiled_graph is not None:
            result = await self._compiled_graph.ainvoke(initial_state)

            # Extract workflow state from result
            if hasattr(result, "workflow_state"):
                return result.workflow_state
            elif isinstance(result, dict):
                return result.get("workflow_state", result)
            else:
                return {"result": str(result)}

        return {"error": "Graph not compiled"}

    def validate_input(self, input_data: dict[str, Any]) -> bool:
        """Validate input against input_schema.

        Args:
            input_data: Input data to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.input_schema:
            return True

        # Simple validation - check required fields
        required = self.input_schema.get("required", [])
        for field in required:
            if field not in input_data:
                logger.warning("Missing required field", extra={"field": field, "skill": self.name})
                return False

        return True

    def validate_output(self, output_data: dict[str, Any]) -> bool:
        """Validate output against output_schema.

        Args:
            output_data: Output data to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.output_schema:
            return True

        # Simple validation - check for required fields
        required = self.output_schema.get("required", [])
        for field in required:
            if field not in output_data:
                logger.warning(
                    "Missing required output field", extra={"field": field, "skill": self.name}
                )
                return False

        return True

    def get_info(self) -> dict[str, Any]:
        """Get information about this graph skill.

        Returns:
            Dictionary with skill information
        """
        return {
            "name": self.name,
            "description": self.description,
            "type": "graph_skill",
            "required_skills": self.required_skills,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


def create_graph_skill_from_blueprint(
    blueprint: WorkflowBlueprint,
    skill_manager: SkillManager,
) -> GraphSkill:
    """Create a GraphSkill from a WorkflowBlueprint.

    This factory function creates a GraphSkill instance from a
    dynamically generated workflow blueprint.

    Args:
        blueprint: WorkflowBlueprint to convert
        skill_manager: SkillManager for skill lookups

    Returns:
        GraphSkill instance that can execute the blueprint
    """
    from ..orchestrator.dynamic_builder import DynamicGraphBuilder

    class DynamicGraphSkill(GraphSkill):
        name = blueprint.name
        description = blueprint.description

        def build_graph(self, builder: DynamicGraphBuilder) -> None:
            # Add nodes from blueprint
            for node in blueprint.nodes:
                if node.type == "skill":
                    if "." in node.target:
                        skill_name, cmd_name = node.target.split(".", 1)
                    else:
                        skill_name = node.target
                        cmd_name = node.target

                    builder.add_skill_node(
                        node.id,
                        skill_name,
                        cmd_name,
                        fixed_args=node.fixed_args,
                        state_input=node.state_inputs,
                    )

            # Add edges from blueprint
            for edge in blueprint.edges:
                builder.add_edge(edge.source, edge.target)

            # Set entry point
            if blueprint.entry_point:
                builder.set_entry_point(blueprint.entry_point)

    return DynamicGraphSkill(skill_manager=skill_manager)


__all__ = [
    "GraphSkill",
    "create_graph_skill_from_blueprint",
]
