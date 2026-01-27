"""
verify.py - Skill Code Verification & Self-Correction

Provides verification of generated skill code and self-correction
capabilities when code fails to pass validation.
"""

from __future__ import annotations

from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.cli.generate.verify")


async def verify_skill_code(code: str) -> dict[str, Any]:
    """Verify that code is syntactically valid and has required imports.

    Args:
        code: Python code string to verify

    Returns:
        Dict with 'valid' (bool), 'error' (str or None)
    """
    try:
        # Syntax check using compile
        compile(code, "<generated>", "exec")

        # Try to verify imports and basic structure
        lines = code.split("\n")

        # Check for required imports
        has_skill_command = any(
            "from omni.foundation.api.decorators import skill_command" in line for line in lines
        )
        if not has_skill_command:
            return {"valid": False, "error": "Missing required import: skill_command"}

        # Check for at least one @skill_command decorator
        has_decorator = any("@skill_command" in line for line in lines)
        if not has_decorator:
            return {"valid": False, "error": "No @skill_command decorators found"}

        return {"valid": True, "error": None}

    except SyntaxError as e:
        return {"valid": False, "error": f"Syntax error: {e}"}
    except Exception as e:
        return {"valid": False, "error": f"Verification failed: {e}"}


async def fix_skill_code(broken_code: str, error_msg: str, rag_context: str) -> str:
    """Use LLM to fix broken skill code.

    Args:
        broken_code: The code that failed verification
        error_msg: The error message from verification
        rag_context: RAG context for better fixes

    Returns:
        Fixed code string
    """
    from .prompts import generate_fix_prompt

    fix_prompt = generate_fix_prompt(broken_code, error_msg, rag_context)
    return await _call_llm_to_fix(fix_prompt)


def generate_fix_prompt(broken_code: str, error_msg: str, rag_context: str) -> str:
    """Generate a prompt for fixing broken skill code.

    Args:
        broken_code: The code that failed verification
        error_msg: The error message from verification
        rag_context: RAG context for better fixes

    Returns:
        Formatted prompt string
    """
    return f"""The following Python skill code has an error:

## ERROR
{error_msg}

## BROKEN CODE
```python
{broken_code}
```

## RAG CONTEXT (Reference patterns)
{rag_context}

## TASK
Fix the error and return ONLY the corrected Python code for `scripts/commands.py`.
Do NOT include markdown code blocks. Do NOT explain the fix.
Just return the fixed code."""


async def _call_llm_to_fix(prompt: str) -> str:
    """Call LLM to fix broken code.

    Internal helper - use fix_skill_code() instead.
    """
    try:
        from omni.foundation.services.llm.client import InferenceClient

        client = InferenceClient()
        result = await client.complete(
            system_prompt="You are an expert Python developer. Fix code errors concisely.",
            user_query=prompt,
            max_tokens=2000,
        )

        if result["success"]:
            return _clean_code(result["content"])
        else:
            logger.warning(f"LLM fix failed: {result.get('error')}")
            return ""  # Return empty on failure

    except Exception as e:
        logger.warning(f"LLM fix call failed: {e}")
        return ""


def _clean_code(code: str) -> str:
    """Strip markdown fences if LLM adds them."""
    code = code.strip()
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()


__all__ = ["verify_skill_code", "fix_skill_code", "generate_fix_prompt"]
