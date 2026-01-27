"""
harvester.py - Session Analysis & Skill Extraction

Core Logic: Identify successful tool chains and abstract them into reusable patterns.

Dual-Path Evolution:
- Fast Path (System 1): Semantic memory for rules/preferences
- Slow Path (System 2): Procedural skills for complex workflows
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from omni.foundation.config.logging import get_logger
from omni.foundation.services.llm import InferenceClient

logger = get_logger("omni.evolution.harvester")


class CandidateSkill(BaseModel):
    """从会话历史中提取的候选技能"""

    intent: str
    description: str
    tool_chain: List[Dict[str, Any]]
    variables: List[str]
    success_count: int = 1


class ExtractedLesson(BaseModel):
    """从会话中提取的语义规则/偏好"""

    rule: str
    domain: str
    confidence: float = 1.0


class Harvester:
    """
    Analyzes session history to identify potential 'Macro Skills'.

    This is the core component of the Self-Evolution system:
    - Slow Path: Extracts successful workflows as new skills
    - Fast Path: Extracts rules/preferences as semantic memories
    """

    def __init__(self, llm: InferenceClient):
        self.llm = llm

    async def analyze_session(self, history: List[Dict[str, Any]]) -> Optional[CandidateSkill]:
        """
        Core Algorithm for Slow Path (Procedural Skills):

        1. Filter: Extract only Tool Calls and Tool Outputs from history.
        2. Evaluate: Did the session end with EXIT_LOOP_NOW? (Success signal)
        3. Abstract: Use LLM to pattern-match the tool sequence against the user intent.

        Args:
            history: List of conversation messages

        Returns:
            CandidateSkill if a reusable pattern is found, None otherwise
        """
        if len(history) < 3:
            logger.debug("Session too short for harvesting")
            return None

        # 1. Check Success Signal (EXIT_LOOP_NOW)
        last_msg = history[-1].get("content", "") if history else ""
        if "EXIT_LOOP_NOW" not in last_msg:
            logger.debug("Session did not end with EXIT_LOOP_NOW, skipping harvest")
            return None

        # 2. Extract tool execution trace
        execution_trace: List[Dict[str, Any]] = []
        for msg in history:
            # Extract tool calls
            if tool_calls := msg.get("tool_calls"):
                for tc in tool_calls:
                    execution_trace.append(
                        {
                            "type": "tool_call",
                            "tool": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments"),
                        }
                    )
            # Extract tool outputs
            if msg.get("role") == "user" and "[Tool:" in str(msg.get("content", "")):
                execution_trace.append(
                    {
                        "type": "tool_output",
                        "content": msg.get("content", ""),
                    }
                )

        if len(execution_trace) < 2:
            logger.debug("Not enough tool activity for skill extraction")
            return None

        # 3. LLM-based Pattern Extraction
        system_prompt = (
            "You are an AGI Skill Architect.\n"
            "Analyze the following execution trace from a successful session.\n"
            "If it represents a reusable, high-quality workflow, extract it as a CandidateSkill.\n"
            "Identify variables (e.g., replace 'main.py' with '{file_path}').\n"
            "Return JSON only with the following structure:\n"
            "{\n"
            '  "intent": "short_action_name_in_snake_case",\n'
            '  "description": "one_sentence_description_of_what_this_skill_does",\n'
            '  "tool_chain": [{"tool": "tool_name", "purpose": "why_this_tool_was_used"}],\n'
            '  "variables": ["variable1", "variable2"]\n'
            "}\n"
            'If the workflow is not reusable or too specific, return {"intent": null}.'
        )

        try:
            response = await self.llm.complete(
                system_prompt=system_prompt,
                user_query=json.dumps(execution_trace[-15:]),  # Analyze last 15 steps
                response_format={"type": "json_object"},
            )
            content = response.get("content", "{}")
            data = json.loads(content)

            if data.get("intent") is None:
                logger.debug("LLM determined workflow is not reusable")
                return None

            return CandidateSkill(**data)
        except json.JSONDecodeError as e:
            logger.warn(f"Failed to parse LLM response as JSON: {e}")
            return None
        except Exception as e:
            logger.warn(f"Harvesting failed: {e}")
            return None

    async def extract_lessons(self, history: List[Dict]) -> Optional[ExtractedLesson]:
        """
        Fast Path Harvester: Extracts rules/preferences from user feedback.

        Triggered when:
        1. User explicit feedback ("No, use X instead of Y")
        2. Recovery from error (Tool A failed -> Tool B succeeded)
        3. Strong user preferences expressed multiple times

        Args:
            session_id: Current session identifier
            history: Conversation history

        Returns:
            ExtractedLesson if a rule is found, None otherwise
        """
        # 1. Quick filter: Look for correction/feedback patterns
        correction_patterns = [
            "no,",
            "not",
            "wrong",
            "don't",
            "instead",
            "use",
            "prefer",
            "better",
            "always",
            "never",
        ]

        relevant_messages = [
            m
            for m in history
            if m.get("role") == "user"
            and any(p in m.get("content", "").lower() for p in correction_patterns)
        ]

        if not relevant_messages:
            return None

        # 2. LLM analysis for rule extraction
        system_prompt = (
            "You are a Learning Assistant.\n"
            "Analyze the user's corrections or feedback.\n"
            "Extract the underlying rule, preference, or pattern.\n"
            "Return JSON only:\n"
            "{\n"
            '  "rule": "concise_rule_or_preference",\n'
            '  "domain": "context_area_e.g._coding_style_git_workflow_testing",\n'
            '  "confidence": 0.0_to_1.0\n'
            "}\n"
            'If no clear rule exists, return {"rule": null}.'
        )

        try:
            response = await self.llm.complete(
                system_prompt=system_prompt,
                user_query=json.dumps(relevant_messages[-5:]),  # Last 5 correction messages
                response_format={"type": "json_object"},
            )
            content = response.get("content", "{}")
            data = json.loads(content)

            if data.get("rule") is None:
                return None

            return ExtractedLesson(**data)
        except json.JSONDecodeError:
            return None
        except Exception as e:
            logger.warn(f"Lesson extraction failed: {e}")
            return None

    async def detect_pattern_from_error(
        self, error_msg: str, recovery_steps: List[Dict]
    ) -> Optional[Dict]:
        """
        Extract learning from error recovery patterns.

        When a tool fails and the system recovers, this captures the recovery strategy.

        Args:
            error_msg: The error message that occurred
            recovery_steps: Steps taken to recover from the error

        Returns:
            Dict with error_pattern and recovery_strategy, or None
        """
        system_prompt = (
            "You are a Debugging Strategist.\n"
            "Analyze the error and recovery pattern.\n"
            "Return JSON:\n"
            "{\n"
            '  "error_pattern": "type_of_error",\n'
            '  "recovery_strategy": "what_worked_to_fix_it",\n'
            '  "prevention": "how_to_avoid_this_in_future"\n'
            "}"
        )

        try:
            response = await self.llm.complete(
                system_prompt=system_prompt,
                user_query=f"Error: {error_msg}\nRecovery: {json.dumps(recovery_steps)}",
                response_format={"type": "json_object"},
            )
            content = response.get("content", "{}")
            return json.loads(content)
        except Exception:
            return None
