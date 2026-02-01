"""
harvester.py - Trace-Based Skill Extraction

Core Logic: Identify successful execution patterns and abstract them into reusable skills.

Dual-Path Evolution:
- Fast Path (System 1): Semantic memory for rules/preferences
- Slow Path (System 2): Procedural skills for complex workflows
"""

from __future__ import annotations

import json
from typing import Any

from omni.foundation.config.logging import get_logger
from omni.foundation.services.llm import InferenceClient

logger = get_logger("omni.evolution.harvester")


class Harvester:
    """
    Analyzes execution traces to identify potential skills.

    This is the core component of the Self-Evolution system.
    """

    def __init__(self, llm: InferenceClient | None = None):
        """Initialize the harvester.

        Args:
            llm: Optional LLM client for structured extraction.
        """
        self.llm = llm


# =============================================================================
# Trace-Based Harvesting
# =============================================================================

from .schemas import CandidateSkill
from .prompts import SKILL_EXTRACTION_PROMPT


async def process_trace_for_skill(
    trace: "ExecutionTrace",
    llm: InferenceClient | None = None,
) -> CandidateSkill | None:
    """
    Process an execution trace and extract a CandidateSkill.

    Uses XML-tagged prompts for better LLM comprehension (Claude Cookbook best practice).

    Args:
        trace: Execution trace from TraceCollector
        llm: Optional LLM client for extraction

    Returns:
        CandidateSkill if trace is worthy, None otherwise
    """
    # Heuristic: Filter trivial traces
    if len(trace.commands) < 1 or trace.duration_ms < 100:
        logger.debug(f"Trace {getattr(trace, 'task_id', 'unknown')} too simple, skipping")
        return None

    if not trace.success:
        logger.debug(f"Trace {getattr(trace, 'task_id', 'unknown')} failed, skipping")
        return None

    if llm is None:
        # Fallback: Heuristic-based extraction
        return _heuristic_extract(trace)

    # LLM-based extraction with XML prompt
    try:
        # Format commands as XML
        commands_xml = "\n".join(f"    <cmd>{cmd}</cmd>" for cmd in trace.commands)
        outputs_xml = "\n".join(f"    <output>{out}</output>" for out in trace.outputs[:5])

        prompt = SKILL_EXTRACTION_PROMPT.format(
            task=trace.task_description,
            duration=int(trace.duration_ms),
            commands_xml=commands_xml,
            outputs_xml=outputs_xml,
        )

        response = await llm.complete(
            system_prompt="You are a skill extraction expert.",
            user_query=prompt,
            response_format={"type": "json_object"},
        )

        content = response.get("content", "{}")
        data = json.loads(content)

        if data.get("is_worthy") is False:
            logger.info(f"Trace not deemed worthy: {data.get('skip_reason', 'unknown')}")
            return None

        # Build CandidateSkill with trace metadata
        return CandidateSkill(
            suggested_name=data["suggested_name"],
            description=data["description"],
            category=data.get("category", "automation"),
            nushell_script=data["nushell_script"],
            parameters=data["parameters"],
            usage_scenarios=data.get("usage_scenarios", []),
            faq_items=data.get("faq_items", []),
            original_task=trace.task_description,
            trace_id=getattr(trace, "task_id", "unknown"),
            reasoning=data["reasoning"],
            confidence_score=data.get("confidence_score", 0.8),
            estimated_complexity=data.get("estimated_complexity", "medium"),
        )

    except json.JSONDecodeError as e:
        logger.warn(f"Failed to parse LLM response: {e}")
        return _heuristic_extract(trace)
    except Exception as e:
        logger.warn(f"Trace processing failed: {e}")
        return None


def _heuristic_extract(trace: "ExecutionTrace") -> CandidateSkill | None:
    """
    Fallback: Extract skill using heuristics when LLM is unavailable.

    Creates a simple skill from the trace commands.
    """
    if len(trace.commands) == 0:
        return None

    # Generate skill name from task description
    task_words = trace.task_description.lower().split()
    skill_name = "_".join(w[:8] for w in task_words if w.isalnum())

    # Extract potential parameters (simple heuristic)
    parameters: dict[str, str] = {}
    for cmd in trace.commands:
        if "*." in cmd:
            parameters["pattern"] = "File pattern to match"
        if "mv" in cmd:
            parameters["source"] = "Source path"
            parameters["dest"] = "Destination path"
        if "git" in cmd:
            if "commit" in cmd:
                parameters["message"] = "Commit message"
            if "push" in cmd:
                parameters["branch"] = "Branch name"

    # Use first command as script
    nushell_script = trace.commands[0]

    return CandidateSkill(
        suggested_name=skill_name,
        description=f"Skill extracted from: {trace.task_description}",
        category="automation",
        nushell_script=nushell_script,
        parameters=parameters,
        original_task=trace.task_description,
        trace_id=getattr(trace, "task_id", "unknown"),
        reasoning="Heuristic extraction (LLM unavailable)",
        confidence_score=0.5,  # Lower confidence for heuristic
        estimated_complexity="low",
    )


# Type hint for forward reference
from .tracer import ExecutionTrace

__all__ = [
    "Harvester",
    "process_trace_for_skill",
]
