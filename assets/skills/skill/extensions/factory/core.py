"""
core.py - The Meta-Agent Factory (Template-Based)

Simple workflow:
1. Read _template files
2. LLM generates modified versions
3. Save to assets/skills/<skill_name>/

Usage:
    from agent.skills.skill.extensions.factory.core import MetaAgent
    meta = MetaAgent()
    result = await meta.generate_skill("I need a CSV to JSON converter")
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

import structlog

from omni.foundation.config.skills import SKILLS_DIR
from .prompt import skill_generation_prompt, parse_skill_response

logger = structlog.get_logger(__name__)

from .result import GenerationResult


class MetaAgent:
    """Meta-Agent for skill generation using _template."""

    def __init__(self, llm_client: Any | None = None):
        self.llm_client = llm_client
        self._init_llm_client()

    def _init_llm_client(self) -> None:
        if self.llm_client:
            return
        try:
            from omni.foundation.services.llm import InferenceClient

            self.llm_client = InferenceClient()
            logger.info("MetaAgent: LLM client initialized")
        except Exception as e:
            logger.warning(f"MetaAgent: Failed to init LLM: {e}")
            self.llm_client = None

    async def generate_skill(self, requirement: str) -> GenerationResult:
        """Generate a skill from requirement using _template."""
        t0 = time.perf_counter()

        try:
            logger.info("meta_agent_generation_started", requirement=requirement[:100])

            # Check LLM availability
            if self.llm_client is None:
                return GenerationResult(
                    success=False,
                    skill_name="",
                    error="No LLM client",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # Get _template path
            skills_dir = SKILLS_DIR()
            template_dir = skills_dir / "_template"
            if not template_dir.exists():
                return GenerationResult(
                    success=False,
                    skill_name="",
                    error=f"Template not found: {template_dir}",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # Build prompt with template content
            prompt = skill_generation_prompt(requirement, str(template_dir))

            # Call LLM
            response = await self._call_llm(prompt)

            # Parse response
            spec = parse_skill_response(str(response))
            skill_name = spec.get("skill_name", "unknown-skill")
            files = spec.get("files", {})

            logger.info("skill_spec_generated", skill_name=skill_name)

            # Save skill
            skill_path = self._save_skill(skill_name, files, skills_dir)

            duration_ms = (time.perf_counter() - t0) * 1000
            return GenerationResult(
                success=True,
                skill_name=skill_name,
                skill_code="<template_based>",
                test_code="",
                path=skill_path,
                validation_success=True,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.error("meta_agent_generation_failed", error=str(e))
            return GenerationResult(
                success=False, skill_name="", error=str(e), duration_ms=duration_ms
            )

    def _save_skill(self, skill_name: str, files: dict, skills_dir: Path) -> Path:
        """Save generated skill files."""
        target_dir = skills_dir / skill_name

        # Clean existing
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Save files
        for rel_path, content in files.items():
            full_path = target_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)

        logger.info("skill_saved", skill_name=skill_name, path=str(target_dir))
        return target_dir

    async def _call_llm(self, prompt: str) -> str:
        if self.llm_client is None:
            raise ValueError("LLM client not initialized")
        try:
            response = await self.llm_client.complete(
                system_prompt="You are a skilled programmer.",
                user_query=prompt,
            )
            return (
                response.get("content", str(response))
                if isinstance(response, dict)
                else str(response)
            )
        except Exception as e:
            logger.error("llm_call_failed", error=str(e))
            raise


async def generate_skill(requirement: str, llm_client: Any | None = None) -> GenerationResult:
    """Convenience function to generate a skill."""
    meta = MetaAgent(llm_client)
    return await meta.generate_skill(requirement)


__all__ = ["MetaAgent", "generate_skill", "GenerationResult"]
