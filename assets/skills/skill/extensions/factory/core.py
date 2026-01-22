"""
core.py
 The Meta-Agent - Adaptation Factory Coordination

Implements the Build-Test-Improve loop for automatic skill generation:
1. Blueprint: Generate skill spec from natural language requirement
2. QA Sandbox: Test generated code in isolated environment
3. Self-Repair: Auto-fix failures using LLM reflection

Usage:
    from agent.skills.skill.extensions.factory.core import MetaAgent

    meta = MetaAgent()
    result = await meta.generate_skill("I need a CSV to JSON converter")
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from .prompt import MetaAgentPrompt, parse_skill_response, extract_json_from_response
from .validator import SandboxValidator, ValidationResult
from omni.foundation.config.skills import SKILLS_DIR

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from .result import GenerationResult

# Re-export GenerationResult for CLI access
from .result import GenerationResult


class MetaAgent:
    """
    Meta-Agent Coordination Factory.

    Orchestrates the Build-Test-Improve loop for automatic skill generation:

    Components:
    - Blueprint: Uses MetaAgentPrompt to generate skill specs from requirements
    - QA Sandbox: Uses SandboxValidator to test code in isolation
    - Self-Repair: Uses LLM reflection to auto-fix failures
    - Harvester: Uses SkillHarvester to discover patterns from history

    Usage:
        meta = MetaAgent()
        result = await meta.generate_skill("I need a CSV to JSON converter")
    """

    def __init__(self, llm_client: Any | None = None):
        """
        Initialize the Meta-Agent factory.

        Args:
            llm_client: LLM client for generation and refinement.
                       If None, uses InferenceClient.
        """
        self.prompt = MetaAgentPrompt()
        self.validator = SandboxValidator()

        if llm_client is None:
            self._init_llm_client()
        else:
            self.llm_client = llm_client

    def _init_llm_client(self) -> None:
        """Initialize the default LLM client."""
        try:
            from omni.foundation.services.llm import InferenceClient

            self.llm_client = InferenceClient()
            logger.info("MetaAgent: LLM client initialized (InferenceClient)")
        except Exception as e:
            logger.warning(f"MetaAgent: Failed to initialize LLM client: {e}")
            self.llm_client = None

    async def generate_skill(
        self,
        requirement: str,
        max_retries: int = 2,
        save_path: Path | None = None,
    ) -> "GenerationResult":
        """
        Generate and validate a new skill from a natural language requirement.

        This is the main entry point for on-demand skill generation.
        Implements the Build-Test-Improve loop:

        1. Blueprint: Generate skill specification from requirement
        2. QA: Run tests in sandbox
        3. Improve: Auto-fix if tests fail (up to max_retries)

        Args:
            requirement: Natural language description of needed skill
            max_retries: Maximum refinement attempts (default: 2)
            save_path: Optional path to save the skill (auto-generates if None)

        Returns:
            GenerationResult with success status and generated code
        """
        from .result import GenerationResult

        t0 = time.perf_counter()
        skill_name = ""
        skill_code = ""
        test_code = ""

        try:
            logger.info("meta_agent_generation_started", requirement=requirement[:100])

            # Step 1: Blueprint - Generate skill specification
            if self.llm_client is None:
                return GenerationResult(
                    success=False,
                    skill_name="",
                    error="No LLM client available",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            prompt = self.prompt.skill_generation(requirement)
            response = await self._call_llm(prompt)
            skill_spec = parse_skill_response(response)

            skill_name = skill_spec.get("skill_name", "unknown")
            logger.info("skill_spec_generated", skill_name=skill_name)

            # Step 2: Extract implementation and generate test
            commands = skill_spec.get("commands", [])
            if not commands:
                return GenerationResult(  # type: ignore[return-value]
                    success=False,
                    skill_name=skill_name,
                    error="No commands generated in skill specification",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # Use first command as primary implementation
            primary_cmd = commands[0]
            skill_code = primary_cmd.get("implementation", "")

            if not skill_code:
                return GenerationResult(  # type: ignore[return-value]
                    success=False,
                    skill_name=skill_name,
                    error="No implementation generated for command",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # Generate test code (deterministic - no LLM needed)
            test_code = self.prompt.test_generation(
                name=primary_cmd.get("name", skill_name),
                description=primary_cmd.get("description", ""),
                parameters=primary_cmd.get("parameters", []),
                implementation=skill_code,
                skill_name=skill_name,
            )

            logger.debug("test_code_generated", test_code_preview=test_code[:200])

            if not test_code:
                return GenerationResult(
                    success=False,
                    skill_name=skill_name,
                    error="No test code generated",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            # Step 3: QA Sandbox + Self-Repair Loop
            validation_result = await self._validate_with_retry(
                skill_name=skill_name,
                skill_code=skill_code,
                test_code=test_code,
                requirement=requirement,
                max_retries=max_retries,
            )

            duration_ms = (time.perf_counter() - t0) * 1000

            # Step 4: Save to disk (auto-save to SKILLS_DIR by default)
            saved_path = None
            if validation_result.success:
                actual_save_path = save_path if save_path else SKILLS_DIR()
                saved_path = self._save_skill(skill_name, skill_code, actual_save_path)

            logger.info(
                "meta_agent_generation_complete",
                skill_name=skill_name,
                success=validation_result.success,
                duration_ms=duration_ms,
                saved_path=str(saved_path) if saved_path else None,
            )

            return GenerationResult(  # type: ignore[return-value]
                success=validation_result.success,
                skill_name=skill_name,
                skill_code=skill_code,
                test_code=test_code,
                path=saved_path,
                validation_success=validation_result.success,
                duration_ms=duration_ms,
            )

        except json.JSONDecodeError as e:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.error("meta_agent_json_parse_error", error=str(e))
            return GenerationResult(  # type: ignore[return-value]
                success=False,
                skill_name=skill_name,
                error=f"Failed to parse LLM response as JSON: {e}",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - t0) * 1000
            logger.error("meta_agent_generation_failed", error=str(e))
            return GenerationResult(  # type: ignore[return-value]
                success=False,
                skill_name=skill_name,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def _validate_with_retry(
        self,
        skill_name: str,
        skill_code: str,
        test_code: str,
        requirement: str,
        max_retries: int = 2,
    ) -> ValidationResult:
        """Run validation with self-repair loop."""

        async def async_refine(code: str, error: str) -> str:
            """Call LLM to refine code based on error."""
            refine_prompt = self._create_refinement_prompt(requirement, code, error)
            response = await self._call_llm(refine_prompt)
            try:
                result = extract_json_from_response(response)
                return result.get("refined_code", response)
            except ValueError:
                return response

        validator = self.validator
        current_code = skill_code
        result = ValidationResult(success=False, stdout="", stderr="", error_summary="")

        for attempt in range(max_retries + 1):
            logger.info(
                "validation_attempt",
                skill=skill_name,
                attempt=attempt + 1,
                max_attempts=max_retries + 1,
            )

            result = validator.validate(skill_name, current_code, test_code)

            if result.success:
                return result

            logger.warning(
                "validation_failed",
                skill=skill_name,
                error_summary=result.error_summary[:200],
            )

            if attempt < max_retries:
                refined = await async_refine(
                    current_code,
                    result.stdout + "\n" + result.stderr,
                )
                if refined and not refined.startswith("# Error"):
                    current_code = refined
                    logger.info(
                        "refinement_applied",
                        skill=skill_name,
                        attempt=attempt + 1,
                    )
                    continue

            break

        return result

    def _create_refinement_prompt(
        self,
        requirement: str,
        code: str,
        error: str,
    ) -> str:
        """Create a prompt for code refinement based on test failures."""
        return f"""You are fixing a skill that failed validation tests.

## Original Requirement
{requirement}

## Current Implementation
```python
{code}
```

## Test Output (Errors)
```
{error[:1000]}
```

## Task
Fix the implementation to pass all tests. Return a JSON object:
```json
{{
  "refined_code": "Your fixed code here"
}}
```

Only return valid JSON, no markdown formatting."""

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM with a prompt and return the response."""
        if self.llm_client is None:
            raise ValueError("LLM client not initialized")

        try:
            response = await self.llm_client.complete(
                system_prompt="You are a skilled programmer.",
                user_query=prompt,
            )
            if isinstance(response, dict):
                return response.get("content", str(response))
            return str(response)
        except Exception as e:
            logger.error("llm_call_failed", error=str(e))
            raise

    def _save_skill(
        self,
        skill_name: str,
        skill_code: str,
        output_dir: Path,
    ) -> Path:
        """
        Save generated skill to disk.

        Creates the standard skill structure:
        - assets/skills/{skill_name}/scripts/{skill_name}.py
        - assets/skills/{skill_name}/SKILL.md
        """
        skills_dir = output_dir if output_dir else SKILLS_DIR()

        # Use underscores for directory name (Python imports require valid identifiers)
        skill_name_underscored = skill_name.replace("-", "_")
        skill_path = skills_dir / skill_name_underscored
        scripts_dir = skill_path / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Write the main script
        script_file = scripts_dir / f"{skill_name_underscored}.py"
        script_content = self._wrap_in_skill_script(skill_name_underscored, skill_code)
        script_file.write_text(script_content, encoding="utf-8")

        # Extract function name from implementation
        func_match = re.search(r"def\s+(\w+)\s*\(", skill_code)
        func_name = func_match.group(1) if func_match else skill_name_underscored

        # Create __init__.py that imports the skill function
        # Use the same pattern as existing skills: import from scripts/ directly
        init_content = f"""\"\"\"Generated skill: {skill_name}.\"\"\"

from agent.skills.{skill_name_underscored}.scripts.{skill_name_underscored} import {func_name}
"""
        (scripts_dir / "__init__.py").write_text(init_content, encoding="utf-8")

        # Create SKILL.md with proper YAML frontmatter
        skill_md = skill_path / "SKILL.md"
        skill_content = f"""---
name: {skill_name}
version: 1.0.0
description: Auto-generated skill from Meta-Agent Adaptation Factory
authors: ["omni-dev-fusion"]
license: Apache-2.0
execution_mode: library
routing_strategy: keyword
routing_keywords: ["{skill_name.replace("_", " ")}", "generated"]
intents: []
---

# {skill_name}

Auto-generated skill from Meta-Agent Adaptation Factory.

## Description
{skill_name} - Generated by Meta-Agent Adaptation Factory

## Commands
See `{skill_name}.py` for implementation details.
"""
        skill_md.write_text(skill_content, encoding="utf-8")

        logger.info("skill_saved", skill_name=skill_name, path=str(skill_path))
        return skill_path

    def _wrap_in_skill_script(
        self,
        skill_name: str,
        implementation: str,
    ) -> str:
        """Wrap raw implementation in skill script structure."""
        func_match = re.search(r"def\s+(\w+)\s*\(", implementation)
        func_name = func_match.group(1) if func_match else skill_name.replace("-", "_")

        return f'''"""Generated skill: {skill_name}."""

from typing import Any
from omni.core.skills.script_loader import skill_command


{implementation}


# Export the main function as skill_command
{func_name} = skill_command(
    name="{skill_name.replace("-", "_")}",
    category="generated",
    description="Auto-generated skill",
)({func_name})
'''


# =============================================================================
# Convenience Functions
# =============================================================================


async def generate_skill(
    requirement: str,
    llm_client: Any | None = None,
) -> "GenerationResult":
    """
    Convenience function to generate a skill from a requirement.
    """
    from .result import GenerationResult

    meta = MetaAgent(llm_client)
    return await meta.generate_skill(requirement)


async def harvest_skills(
    min_frequency: int = 2,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Convenience function to harvest skill patterns from sessions.
    """
    # Note: Harvester is optional - skip if not implemented
    logger.info("harvest_skills called (not yet implemented in factory extension)")
    return []


__all__ = [
    "MetaAgent",
    "generate_skill",
    "harvest_skills",
    "GenerationResult",
]
