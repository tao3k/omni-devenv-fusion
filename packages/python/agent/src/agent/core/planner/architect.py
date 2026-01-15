"""
src/agent/core/planner/architect.py
 Workflow Architect - Generates Dynamic Graph Blueprints.

This module provides the WorkflowArchitect class that uses LLM to generate
executable workflow blueprints from user goals. It bridges the gap between
natural language intent and LangGraph execution graphs.

Usage:
    architect = WorkflowArchitect(inference_client, available_tools)
    blueprint = await architect.design_workflow("Fix the bug in main.py")
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, List

from .schemas import WorkflowBlueprint

if TYPE_CHECKING:
    from common.mcp_core.inference import InferenceClient

logger = logging.getLogger(__name__)

ARCHITECT_PROMPT = """You are the Workflow Architect for the Omni Agent.
Your goal is to design a dynamic execution graph (WorkflowBlueprint) to solve the user's problem.

Available Skills:
{tools}

Output Format:
Return ONLY a valid JSON object matching this schema:
{{
  "name": "workflow_name",
  "description": "What this workflow accomplishes",
  "entry_point": "first_node_id",
  "nodes": [
    {{
      "id": "node_id",
      "type": "skill",
      "target": "skill.command",
      "fixed_args": {{"arg": "value"}},
      "state_inputs": {{"state_key": "arg_name"}}
    }}
  ],
  "edges": [
    {{"source": "node_id", "target": "next_node_id"}}
  ]
}}

Rules:
1. Use "skill" type for all nodes (function/llm not supported yet)
2. Target format: "skill_name.command_name" (e.g., "filesystem.read_file")
3. fixed_args: Static values passed to the command
4. state_inputs: Dynamic values read from state (state_key -> arg_name)
5. edges: Define execution flow (source -> target)
6. entry_point: ID of the first node to execute

Example for "Read main.py and analyze it":
{{
  "name": "read_and_analyze",
  "description": "Read file and analyze its contents",
  "entry_point": "read_file",
  "nodes": [
    {{"id": "read_file", "type": "skill", "target": "filesystem.read_file", "fixed_args": {{"path": "main.py"}}}},
    {{"id": "analyze_file", "type": "skill", "target": "code_insight.analyze", "state_inputs": {{"content": "file_content"}}}}
  ],
  "edges": [
    {{"source": "read_file", "target": "analyze_file"}}
  ]
}}
"""


class WorkflowArchitect:
    """Generates executable workflow blueprints from user goals.

    The architect uses LLM to translate natural language goals into
    structured workflow blueprints that can be compiled by DynamicGraphBuilder.

    Attributes:
        inference: LLM inference client.
        tools: List of available skill commands.
    """

    def __init__(
        self,
        inference_client: InferenceClient,
        tools: List[str],
    ) -> None:
        """Initialize the WorkflowArchitect.

        Args:
            inference_client: Client for LLM inference.
            tools: List of available tool/skill names.
        """
        self.inference = inference_client
        self.tools = tools

    async def design_workflow(self, goal: str, context: str = "") -> WorkflowBlueprint:
        """Design a workflow blueprint based on the goal.

        Args:
            goal: The user goal to achieve.
            context: Optional context about the project or task.

        Returns:
            A WorkflowBlueprint ready to be compiled into a graph.

        Raises:
            ValueError: If the LLM response cannot be parsed.
        """
        prompt = ARCHITECT_PROMPT.format(tools="\n".join(self.tools))
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Goal: {goal}\nContext: {context}"},
        ]

        logger.info(f"Architect designing workflow for: {goal[:50]}...")

        try:
            response = await self.inference.chat(messages=messages, temperature=0.2)
            content = response.content.strip()

            # Handle markdown code blocks
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()

            # Parse JSON
            data = json.loads(content)

            # Validate and create blueprint
            blueprint = WorkflowBlueprint(**data)

            logger.info(
                f"Workflow '{blueprint.name}' designed with {len(blueprint.nodes)} nodes, "
                f"{len(blueprint.edges)} edges"
            )
            return blueprint

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse workflow blueprint JSON: {e}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        except KeyError as e:
            logger.error(f"Missing required field in blueprint: {e}")
            raise ValueError(f"Missing required field in blueprint: {e}")
        except Exception as e:
            logger.error(f"Failed to design workflow: {e}", exc_info=True)
            raise


__all__ = [
    "WorkflowArchitect",
]
